"""
FleetMaster Bot — Clean App Entrypoint
"""

import asyncio
import contextlib

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
#  Samsara Background Polling
# =====================================================
async def samsara_background_task(interval_hours: int = 1):
    """Refresh Samsara vehicle data every N hours."""
    logger.info(f"🌐 Samsara refresh task started ({interval_hours}h interval)")
    while True:
        try:
            # Note: The session is now managed by the context manager in _start()
            await samsara_service.get_vehicles(use_cache=False)
            logger.info("🔁 Samsara vehicle data refreshed")
        except Exception as e:
            logger.error(f"⚠️ Samsara refresh error: {e}")
        await asyncio.sleep(interval_hours * 3600)


# =====================================================
#  Main Startup Function (FIXED VERSION)
# =====================================================
async def _start():
    setup_logging()
    settings.validate()

    if not await init_db_with_retry():
        return

    bot = create_bot()
    dp = create_dispatcher()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Use "_" if you don't need to call methods directly on the service object here
    async with samsara_service as _:
        # Start background task
        samsara_task = asyncio.create_task(samsara_background_task(1))

        try:
            logger.info("🚀 FleetMaster is LIVE")
            await bot.delete_webhook(drop_pending_updates=True)

            # Start polling
            await dp.start_polling(
                bot, allowed_updates=["message", "callback_query", "chat_member", "my_chat_member"]
            )
        except Exception as e:
            logger.error(f"💀 Polling crash: {e}")
        finally:
            samsara_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await samsara_task

            logger.info("🛑 Polling stopped.")

    await asyncio.sleep(0.5)
    logger.info("🛑 Shutdown complete.")


# =====================================================
#  Entrypoint (FIXED VERSION)
# =====================================================
if __name__ == "__main__":
    # Use suppress for a cleaner exit without try/except/pass blocks
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(_start())
        logger.info("🧹 Gracefully stopped FleetMaster bot.")
