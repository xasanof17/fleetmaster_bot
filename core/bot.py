"""
core/bot.py
Bot initialization and lifecycle helpers for FleetMaster Bot
"""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import settings
from middlewares.auth_guard import AuthGuardMiddleware  # Ensure this is imported
from middlewares.chat_guard import ChatGuardMiddleware
from services.group_map import ensure_table as ensure_group_table
from services.samsara_service import samsara_service
from services.user_service import ensure_user_table
from utils.logger import get_logger

logger = get_logger("core.bot")


def create_bot() -> Bot:
    """Create and configure bot instance."""
    return Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )


def create_dispatcher() -> Dispatcher:
    """Dispatcher setup with Middleware and Router inclusion."""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Attach middlewares in correct order
    dp.message.middleware(ChatGuardMiddleware())
    dp.callback_query.middleware(ChatGuardMiddleware())

    # The Bouncer: Protects all routes from unapproved users
    dp.message.middleware(AuthGuardMiddleware())
    dp.callback_query.middleware(AuthGuardMiddleware())

    try:
        from handlers import routers

        for r in routers:
            dp.include_router(r)
    except Exception as e:
        logger.error(f"Router import failed: {e}")
        raise

    return dp


async def setup_bot_commands(bot: Bot) -> None:
    """Setup bot menu commands."""
    commands = [
        BotCommand(command="start", description="🚛 Start FleetMaster"),
        BotCommand(command="status_summary", description="📊 Fleet Status"),
        BotCommand(command="verify_gmail", description="📧 Verify Gmail Access"),
        BotCommand(command="help", description="❓ Get help"),
    ]
    await bot.set_my_commands(commands)


async def on_startup(bot: Bot) -> None:
    """Logic executed when the bot starts polling."""
    logger.info("🚀 FleetMaster starting up...")

    # Initialize Database Tables
    try:
        await ensure_user_table()
        await ensure_group_table()
        logger.info("✅ Database: Tables verified")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")

    await setup_bot_commands(bot)

    # Test API Connectivity
    async with samsara_service as svc:
        if await svc.test_connection():
            logger.info("✅ Samsara API: Connected")
        else:
            logger.warning("⚠️ Samsara API: Connection Failed")

    me = await bot.get_me()
    logger.info(f"✅ Bot @{me.username} is active.")


async def on_shutdown(bot: Bot) -> None:
    """Graceful shutdown sequence."""
    logger.info("🛑 Shutdown sequence initiated...")
    samsara_service.clear_cache()
    if bot.session:
        await bot.session.close()
    logger.info("✅ Goodbye!")
