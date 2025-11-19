"""
Bot initialization and lifecycle helpers for FleetMaster Bot
Includes: create_bot, create_dispatcher, setup_bot_commands, on_startup, on_shutdown
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
    """Create and configure bot instance"""
    logger.info("Creating Bot instance")
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    logger.info("Bot instance created")
    return bot


def create_dispatcher() -> Dispatcher:
    """Create dispatcher and register routers from handlers"""
    logger.info("Creating Dispatcher")
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # ✅ attach middleware before including routers
    dp.message.middleware(ChatGuardMiddleware())
    dp.callback_query.middleware(ChatGuardMiddleware())

    # import routers (handlers/__init__.py exposes 'routers' list)
    try:
        from handlers import routers
    except Exception as e:
        logger.error(f"Failed to import handlers.routers: {e}")
        raise

    for r in routers:
        dp.include_router(r)
        logger.info(f"Included router: {getattr(r, 'name', getattr(r, '__name__', 'router'))}")
    logger.info("Dispatcher ready")
    return dp


async def setup_bot_commands(bot: Bot) -> None:
    """Set bot menu commands (safe wrapper)"""
    logger.info("Setting up bot commands")
    commands = [
        BotCommand(command="start", description="🚛 Start FleetMaster Bot"),
        BotCommand(command="help", description="❓ Get help"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Bot commands set")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")


async def on_startup(bot: Bot, dispatcher: Dispatcher | None = None) -> None:
    logger.info("🚀 FleetMaster startup initiated.")
    logger.info(f"ADMINS loaded: {settings.ADMINS}")

    try:
        await setup_bot_commands(bot)
    except Exception as e:
        logger.error(f"Error while setting bot commands: {e}")

    # Test Samsara API
    try:
        async with samsara_service as svc:
            ok = await svc.test_connection()
            if ok:
                logger.info("Samsara API test succeeded during startup")
            else:
                logger.warning("Samsara API test failed during startup")
    except Exception as e:
        logger.error(f"Samsara test error during startup: {e}")

    try:
        me = await bot.get_me()
        logger.info(f"✅ Bot ready: @{getattr(me, 'username', 'unknown')}")
    except Exception as e:
        logger.error(f"Failed to get bot info on startup: {e}")


# ─────────────────────────────────────────────
# SHUTDOWN HOOK
# ─────────────────────────────────────────────
async def on_shutdown(bot: Bot, dispatcher: Dispatcher | None = None) -> None:
    """Clean shutdown and resource cleanup."""
    logger.info("🛑 FleetMaster shutdown initiated...")

    try:
        samsara_service.clear_cache()
        logger.info("🧹 Cleared Samsara cache.")
    except Exception as e:
        logger.warning(f"⚠️ Error clearing Samsara cache: {e}")

    try:
        if hasattr(bot, "session") and bot.session:
            await bot.session.close()
            logger.info("🔒 Bot session closed.")
    except Exception as e:
        logger.error(f"❌ Error closing bot session: {e}")

    logger.info("✅ Shutdown complete.")
