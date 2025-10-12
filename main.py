"""
FleetMaster Bot — App Entrypoint
Handles bot startup, DB init, and auto group re-scan from updates.
UPDATED: Sends admin DM after auto-scan completes
"""

import asyncio
import re
from core.bot import create_bot, create_dispatcher, on_startup, on_shutdown
from utils.logger import setup_logging, get_logger
from services.group_map import list_all_groups, upsert_mapping
from services.samsara_service import samsara_service
from config.db import init_db
from config import settings

logger = get_logger("main")

TRUCK_RE = re.compile(r"\b(\d{3,5})\b")


# =====================================================
#  Database Initialization with Retry
# =====================================================
async def init_db_with_retry(retries: int = 5, delay: int = 5):
    """Try to connect to DB multiple times before failing."""
    for attempt in range(1, retries + 1):
        try:
            await init_db()
            logger.info(f"✅ Database initialized successfully (attempt {attempt}).")
            return True
        except Exception as e:
            logger.warning(f"⚠️ DB attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
            else:
                logger.error("❌ Database initialization failed after all retries.")
                return False


# =====================================================
#  Samsara Background Auto-Refresh
# =====================================================
async def samsara_background_task(interval_hours: int = 1):
    """Refresh Samsara vehicle data every N hours."""
    logger.info(f"🌐 Samsara refresh task started (interval {interval_hours}h)")
    while True:
        try:
            async with samsara_service as svc:
                await svc.get_vehicles(use_cache=False)
                logger.info("✅ Samsara vehicle data refreshed successfully.")
        except Exception as e:
            logger.error(f"⚠️ Samsara refresh error: {e}")
        await asyncio.sleep(interval_hours * 3600)


# =====================================================
#  Auto Group Rescan from Updates
# =====================================================
async def auto_rescan_groups(bot):
    """
    Auto-detect all groups the bot has updates from (fresh DB rebuild).
    This will NOT use DB — it rebuilds everything from get_updates().
    """
    logger.info("🔍 Attempting to auto-detect groups where bot is a member...")
    try:
        updates = await bot.get_updates(limit=100, timeout=0)
        found = {}

        for update in updates:
            chat = getattr(update.message, "chat", None) if hasattr(update, "message") else None
            if not chat:
                continue

            if chat.type in ("group", "supergroup"):
                title = chat.title or ""
                match = TRUCK_RE.search(title)
                unit = match.group(1) if match else None
                found[chat.id] = (unit, title)

        if not found:
            logger.warning("⚠️ No groups detected via updates. Try sending a message in each group.")
            return 0

        for chat_id, (unit, title) in found.items():
            await upsert_mapping(unit, chat_id, title)
            logger.info(f"✅ Linked {title} → {chat_id} (unit={unit})")

        logger.info(f"🎯 Auto-rescan complete — {len(found)} groups detected.")
        return len(found)

    except Exception as e:
        logger.error(f"💥 Auto-rescan failed: {e}")
        return 0


# =====================================================
#  Notify Admins
# =====================================================
async def notify_admins(bot, message: str):
    """Send a private message to all admins from settings.ADMINS"""
    if not settings.ADMINS:
        return
    for admin_id in settings.ADMINS:
        try:
            await bot.send_message(admin_id, message, parse_mode="Markdown")
            logger.info(f"📩 Notified admin {admin_id}")
        except Exception as e:
            logger.warning(f"⚠️ Could not DM admin {admin_id}: {e}")


# =====================================================
#  Bot Startup
# =====================================================
async def _start():
    setup_logging()
    settings.validate()

    logger.info("🔌 Initializing PostgreSQL...")
    if not await init_db_with_retry():
        logger.error("🚫 Database init failed. Exiting startup.")
        return

    bot = create_bot()
    dp = create_dispatcher()

    # Startup tasks
    await on_startup(bot, dp)

    # 🧠 Check if DB empty — then auto-rescan groups
    detected = 0
    try:
        groups = await list_all_groups()
        if not groups:
            logger.info("📭 No groups found in DB. Triggering auto-rescan...")
            detected = await auto_rescan_groups(bot)
            logger.info(f"✅ Rescan added {detected} groups to DB.")
        else:
            logger.info(f"📦 DB already contains {len(groups)} group mappings.")
    except Exception as e:
        logger.error(f"⚠️ Group rescan error: {e}")

    # 📨 Notify Admin(s)
    try:
        if detected:
            await notify_admins(
                bot,
                f"✅ *FleetMaster Auto-Scan Complete*\n"
                f"Found **{detected}** truck groups and linked them successfully 🚛"
            )
        else:
            await notify_admins(
                bot,
                "ℹ️ *FleetMaster Online*\nNo new groups detected, using existing mappings 🧭"
            )
    except Exception as e:
        logger.warning(f"⚠️ Failed to notify admins: {e}")

    # Samsara API test
    try:
        async with samsara_service as svc:
            if await svc.test_connection():
                logger.info("🌐 Samsara API connection OK.")
            else:
                logger.warning("⚠️ Samsara API failed to respond at startup.")
    except Exception as e:
        logger.error(f"💥 Samsara API startup test error: {e}")

    # Background Samsara task
    samsara_task = asyncio.create_task(samsara_background_task(1))

    # Start polling
    try:
        logger.info("🚀 FleetMaster is live — starting polling...")
        await dp.start_polling(bot, allowed_updates=["message", "callback_query", "my_chat_member"])
    except Exception as e:
        logger.error(f"💀 Polling crash: {e}")
    finally:
        samsara_task.cancel()
        await on_shutdown(bot, dp)
        await bot.session.close()
        logger.info("🛑 Bot shutdown complete.")


# =====================================================
#  Entrypoint
# =====================================================
if __name__ == "__main__":
    try:
        asyncio.run(_start())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🧹 Gracefully stopped FleetMaster bot.")
