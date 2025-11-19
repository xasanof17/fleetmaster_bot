"""
FleetMaster Bot — Clean App Entrypoint
Handles:
  • DB init
  • Bot + Dispatcher creation
  • Startup middlewares
  • Optional background Samsara refresh
  • Starts polling cleanly
"""

import asyncio

from config import settings
from config.db import init_db
from core.bot import create_bot, create_dispatcher, on_shutdown, on_startup
from services.samsara_service import samsara_service
from utils.logger import get_logger, setup_logging

logger = get_logger("main")


# =====================================================
#  Database Initialization with Retry
# =====================================================
async def init_db_with_retry(retries: int = 5, delay: int = 5):
    """Keep retrying DB until ready."""
    for attempt in range(1, retries + 1):
        try:
            await init_db()
            logger.info(f"✅ DB initialized (attempt {attempt})")
            return True
        except Exception as e:
            logger.warning(f"⚠️ DB attempt {attempt} failed: {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
    logger.error("❌ Database initialization failed after all retries.")
    return False


# =====================================================
#  OPTIONAL: Samsara Background Polling
# =====================================================
async def samsara_background_task(interval_hours: int = 1):
    """Refresh Samsara vehicle data every N hours."""
    logger.info(f"🌐 Samsara refresh task started ({interval_hours}h interval)")
    while True:
        try:
            async with samsara_service as svc:
                await svc.get_vehicles(use_cache=False)
            logger.info("🔁 Samsara vehicle data refreshed")
        except Exception as e:
            logger.error(f"⚠️ Samsara refresh error: {e}")
        await asyncio.sleep(interval_hours * 3600)


# =====================================================
#  Main Startup Function
# =====================================================
async def _start():
    setup_logging()
    settings.validate()

    logger.info("🔌 Initializing PostgreSQL...")
    if not await init_db_with_retry():
        logger.error("🚫 DB init failed. Exiting.")
        return

    bot = create_bot()
    dp = create_dispatcher()

    # General startup
    await on_startup(bot, dp)

    # Test Samsara API
    try:
        async with samsara_service as svc:
            ok = await svc.test_connection()
            logger.info("🌐 Samsara OK" if ok else "⚠️ Samsara test failed")
    except Exception as e:
        logger.error(f"💥 Samsara startup test error: {e}")

    # OPTIONAL background Samsara polling task
    samsara_task = asyncio.create_task(samsara_background_task(1))

    # Start bot
    try:
        logger.info("🚀 FleetMaster is LIVE — polling updates...")
        await dp.start_polling(bot, allowed_updates=["message", "callback_query", "my_chat_member"])
    except Exception as e:
        logger.error(f"💀 Polling crash: {e}")
    finally:
        samsara_task.cancel()
        await on_shutdown(bot, dp)
        await bot.session.close()
        logger.info("🛑 Shutdown complete.")


# =====================================================
#  Entrypoint
# =====================================================
if __name__ == "__main__":
    try:
        asyncio.run(_start())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🧹 Gracefully stopped FleetMaster bot.")
