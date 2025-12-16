"""
Bot initialization and lifecycle helpers for FleetMaster Bot
"""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import settings
from middlewares.chat_guard import ChatGuardMiddleware
from services.samsara_service import samsara_service
from utils.logger import get_logger

logger = get_logger("core.bot")


def create_bot() -> Bot:
    """Create and configure bot instance with default Markdown support"""
    return Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )


def create_dispatcher() -> Dispatcher:
    """Dispatcher setup with Middleware and Router inclusion"""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Attach guard middleware first
    dp.message.middleware(ChatGuardMiddleware())
    dp.callback_query.middleware(ChatGuardMiddleware())

    # Include all routers from handlers/__init__.py
    try:
        from handlers import routers

        for r in routers:
            dp.include_router(r)
    except Exception as e:
        logger.error(f"Router import failed: {e}")
        raise

    return dp


async def setup_bot_commands(bot: Bot) -> None:
    """Menu commands setup"""
    commands = [
        BotCommand(command="start", description="🚛 Start FleetMaster"),
        BotCommand(command="status_summary", description="📊 Fleet Status"),
        BotCommand(command="help", description="❓ Get help"),
    ]
    await bot.set_my_commands(commands)


async def on_startup(bot: Bot) -> None:
    """Execution on bot boot"""
    logger.info("🚀 FleetMaster starting up...")

    await setup_bot_commands(bot)

    # Verify Samsara connectivity
    async with samsara_service as svc:
        if await svc.test_connection():
            logger.info("✅ Samsara API: Connected")
        else:
            logger.warning("⚠️ Samsara API: Connection Failed")

    me = await bot.get_me()
    logger.info(f"✅ Bot @{me.username} is active.")


async def on_shutdown(bot: Bot) -> None:
    """Graceful shutdown sequence"""
    logger.info("🛑 Shutdown sequence initiated...")

    samsara_service.clear_cache()

    if bot.session:
        await bot.session.close()

    logger.info("✅ Goodbye!")
