"""
handlers/auto_link_groups.py
Auto-detect new truck groups and sync them to Postgres.
Catches bot join, group rename, and rejoin events.
"""

import re
from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated
from services.group_map import upsert_mapping
from utils.logger import get_logger

logger = get_logger(__name__)
router = Router()


# ✅ 1️⃣ Detect when bot joins or is re-added to a group
@router.my_chat_member()
async def on_bot_added(event: ChatMemberUpdated):
    chat = event.chat
    chat_id = chat.id
    title = chat.title or ""

    if not title:
        logger.warning(f"⚠️ Missing title for chat {chat_id}")
        return

    logger.info(f"🤖 Bot added or updated membership in group: {title} ({chat_id})")

    # Extract 3–5 digit truck number from title
    match = re.search(r"\b(\d{3,5})\b", title)
    if not match:
        logger.warning(f"❌ No truck/unit number found in group title '{title}'")
        return

    unit = match.group(1)
    await upsert_mapping(unit, chat_id, title)
    logger.info(f"✅ Linked Truck {unit} -> Chat {chat_id}")

    try:
        await event.bot.send_message(
            chat_id,
            f"✅ This group is now linked to **Truck {unit}**.\n"
            "Database updated automatically 🧩",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"⚠️ Failed to send confirmation in group {chat_id}: {e}")


# ✅ 2️⃣ Also detect group renames or when bot is already inside
@router.message(F.chat.type.in_({"group", "supergroup"}))
async def auto_sync_title(msg: Message):
    chat = msg.chat
    title = chat.title or ""
    chat_id = chat.id

    if not title:
        return

    match = re.search(r"\b(\d{3,5})\b", title)
    if not match:
        return  # skip groups without truck numbers

    unit = match.group(1)
    await upsert_mapping(unit, chat_id, title)
    logger.info(f"🔁 Synced Truck {unit} with group {title} ({chat_id})")
