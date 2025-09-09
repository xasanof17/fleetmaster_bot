import re
from typing import Dict, Optional
from aiogram import Bot
from config.settings import settings

# cache storage
_registration_cache: Dict[str, int] = {}


async def build_registration_cache(bot: Bot, limit: int = 1000):
    """
    Scan the channel and build a mapping of truck_id -> message_id.
    Example filename: 1030-REG-2026.pdf
    """
    global _registration_cache
    _registration_cache.clear()

    async for msg in bot.get_chat_history(chat_id=settings.CHANNEL_ID, limit=limit):
        if msg.document and msg.document.file_name:
            filename = msg.document.file_name
            match = re.match(r"(\d+)-REG-\d+\.pdf", filename)
            if match:
                truck_id = match.group(1)
                _registration_cache[truck_id] = msg.message_id

    return _registration_cache


def get_registration_file_id(truck_id: str) -> Optional[int]:
    """Return cached message_id for a given truck"""
    return _registration_cache.get(truck_id)
