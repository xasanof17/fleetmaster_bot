"""
handlers/auto_detect_groups.py
Auto-detect placeholder — logs guidance, no destructive actions.
"""
from aiogram import Bot
from utils.logger import get_logger

logger = get_logger(__name__)

async def auto_detect_and_map_groups(bot: Bot) -> int:
    """
    Telegram Bot API doesn't provide a way to enumerate all chats.
    This startup task logs guidance and returns 0.
    Use /rescan (known chats) or /syncgroups instead.
    """
    try:
        me = await bot.get_me()
        logger.info(f"🤖 Bot online: @{me.username} (id={me.id})")
        logger.info("ℹ️ Auto-detection skipped (Telegram API cannot list all chats).")
        logger.info("👉 Use /rescan to refresh known groups or /syncgroups to re-derive units from DB chats.")
        return 0
    except Exception as e:
        logger.error(f"Auto-detect error: {e}")
        return 0
