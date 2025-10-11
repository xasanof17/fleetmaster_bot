"""
FleetMaster Bot — App Entrypoint
Handles bot startup, database initialization, and polling lifecycle.
"""

import asyncio
from core.bot import (
    create_bot,
    create_dispatcher,
    on_startup,
    on_shutdown,
)
from utils.logger import setup_logging, get_logger
from services.samsara_service import samsara_service
from config.db import init_db
from config import settings

logger = get_logger("main")


# =====================================================
#  Database Initialization with Retry
# =====================================================
async def init_db_with_retry(retries: int = 5, delay: int = 5):
    """
    Try to initialize the PostgreSQL database connection multiple times.
    Retries if Railway is still waking up.
    """
    for attempt in range(1, retries + 1):
        try:
            await init_db()
            logger.info(f"✅ Database initialized successfully on attempt {attempt}.")
            return True
        except Exception as e:
            logger.warning(f"⚠️ DB connection attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                logger.info(f"⏳ Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                logger.error("❌ Database initialization failed after all retries.")
                return False


# =====================================================
#  Samsara Background Auto-Refresh Loop
# =====================================================
async def samsara_background_task(interval_hours: int = 1):
    """
    Periodically refresh Samsara data every N hours (default: 1 hour).
    Runs non-blocking alongside the bot.
    """
    logger.info(f"🌐 Samsara background refresh loop started (every {interval_hours}h)")
    while True:
        try:
            async with samsara_service as svc:
                await svc.get_vehicles(use_cache=False)
                logger.info("✅ Samsara vehicle data refreshed successfully.")
        except Exception as e:
            logger.error(f"⚠️ Samsara background task error: {e}")
        await asyncio.sleep(interval_hours * 3600)  # ⏰ sleep for hours


# =====================================================
#  Bot Startup and Lifecycle
# =====================================================
async def _start():
    """Main async entrypoint for FleetMaster."""
    setup_logging()
    settings.validate()

    # ✅ 1. Initialize PostgreSQL (with retry)
    logger.info("🔌 Attempting to initialize PostgreSQL connection...")
    db_ready = await init_db_with_retry()
    if not db_ready:
        logger.error("🚫 Database could not be initialized. Exiting startup.")
        return

    # ✅ 2. Create bot & dispatcher
    bot = create_bot()
    dp = create_dispatcher()

    # ✅ 3. Run startup hooks
    try:
        await on_startup(bot, dp)
    except Exception as e:
        logger.error(f"⚠️ Error during on_startup: {e}")

    # ✅ 4. Samsara API test
    try:
        async with samsara_service as svc:
            ok = await svc.test_connection()
            if ok:
                logger.info("🌐 Samsara API connection OK at startup.")
            else:
                logger.warning("⚠️ Samsara API test failed at startup.")
    except Exception as e:
        logger.error(f"💥 Samsara startup test error: {e}")

    # ✅ 5. Start non-blocking background Samsara updater
    samsara_task = asyncio.create_task(samsara_background_task(interval_hours=1))

    # ✅ 6. Start bot polling
    try:
        logger.info("🚀 Starting bot polling (FleetMaster is now live!)")
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "my_chat_member"],
        )
    except Exception as e:
        logger.error(f"💀 Polling error: {e}")
    finally:
        # ✅ 7. Graceful shutdown
        samsara_task.cancel()
        await on_shutdown(bot, dp)
        await bot.session.close()
        logger.info("🛑 Bot session closed. Shutdown complete.")


# =====================================================
#  Entrypoint
# =====================================================
if __name__ == "__main__":
    try:
        asyncio.run(_start())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🧹 Gracefully stopped FleetMaster bot.")
