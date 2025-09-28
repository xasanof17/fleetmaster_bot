"""
App entrypoint
"""
import asyncio
from core.bot import (create_bot, create_dispatcher)
from utils.logger import setup_logging, get_logger
from config import settings
from services.samsara_service import samsara_service

logger = get_logger("main")


async def _start():
    setup_logging()
    settings.validate()
    bot = create_bot()
    dp = create_dispatcher()

    # Test samsara on startup (best-effort)
    try:
        async with samsara_service as svc:
            ok = await svc.test_connection()
            if ok:
                logger.info("Samsara connection OK at startup")
            else:
                logger.warning("Samsara connection failed at startup")
    except Exception as e:
        logger.error(f"Startup Samsara test error: {e}")

    try:
        # Start polling
        logger.info("Starting bot polling")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(_start())
