# handlers/auto_link_groups.py
"""
Automatically links group chats to trucks by reading the pinned message
when the bot is added or unmuted.
Pattern: any pinned message containing digits (e.g. "Truck 5120", "#5021", "UNIT 5021")
"""
import re
from aiogram import Router, F
from aiogram.types import ChatMemberUpdated
from services.group_map import upsert_mapping
from utils import get_logger

router = Router()
logger = get_logger(__name__)

# Regex pattern for unit numbers like 5120, 5031, #5120, UNIT 5031 etc.
UNIT_PATTERN = re.compile(r"(?:#?\s*unit\s*|#?\s*)(\d{3,5})", re.IGNORECASE)

@router.my_chat_member(F.chat.type.in_({"group", "supergroup"}))
async def on_bot_added(event: ChatMemberUpdated):
    """Triggered when the bot is added to a group or reactivated"""
    try:
        chat = event.chat
        chat_id = chat.id
        title = chat.title or "Unknown Group"

        # only proceed if bot just became a member
        new_status = event.new_chat_member.status
        if new_status not in ("member", "administrator"):
            return

        # try get pinned message
        pinned = await event.bot.get_chat(chat_id)
        if not pinned.pinned_message or not pinned.pinned_message.text:
            logger.info(f"No pinned message found for {title} ({chat_id})")
            return

        text = pinned.pinned_message.text.strip()
        match = UNIT_PATTERN.search(text)
        if not match:
            logger.info(f"No unit pattern found in pinned message of {title}")
            return

        unit = match.group(1)
        await upsert_mapping(unit, chat_id, title)
        await event.bot.send_message(
            chat_id,
            f"✅ Auto-linked this group to truck **{unit}** based on pinned message.",
            parse_mode="Markdown"
        )
        logger.info(f"Auto-linked group {title} ({chat_id}) -> unit {unit}")

    except Exception as e:
        logger.error(f"Auto-link failed: {e}")
