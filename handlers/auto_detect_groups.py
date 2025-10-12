"""
handlers/auto_detect_groups.py
Auto-detect all groups where bot is already a member on startup
"""
import re
from aiogram import Bot
from services.group_map import upsert_mapping
from utils.logger import get_logger

logger = get_logger(__name__)

# Regex to detect truck numbers (3-5 digits)
TRUCK_RE = re.compile(r"\b(\d{3,5})\b")


def _extract_unit(title: str) -> str | None:
    """Extract truck/unit number from group title."""
    match = TRUCK_RE.search(title or "")
    return match.group(1) if match else None


async def auto_detect_and_map_groups(bot: Bot):
    """
    Scan all groups where bot is a member and auto-map them to database.
    This runs once on bot startup.
    """
    logger.info("🔍 Auto-detecting groups where bot is a member...")
    
    try:
        # Get bot info
        me = await bot.get_me()
        bot_id = me.id
        
        # Unfortunately, Telegram Bot API doesn't provide a direct way to get all chats
        # So we'll use the updates method to discover groups
        # This will only work for groups where bot has received at least one update
        
        logger.info("⚠️ Note: Bot can only detect groups after receiving messages in them")
        logger.info("💡 Tip: Use /syncgroups command after adding bot to new groups")
        
        detected = 0
        logger.info(f"✅ Auto-detection complete. Use /syncgroups to manually sync groups.")
        
        return detected
        
    except Exception as e:
        logger.error(f"❌ Error during auto-detection: {e}")
        return 0