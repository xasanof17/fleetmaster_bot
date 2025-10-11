# handlers/auto_link_groups.py
"""
Auto-link Telegram groups to trucks by scanning group titles.
Now also auto-removes groups when the bot is kicked or leaves.

✅ Features:
- Detects truck/unit numbers (3–5 digits) in group titles automatically.
- Updates mapping when:
    • bot joins or is promoted,
    • bot leaves or is kicked,
    • any message is sent in group,
    • group title changes.
- No replies or messages inside groups.
- Optionally DMs admins privately.
- Safe logging (no await logger, no format crashes).
"""

import re
from aiogram import Router, F
from aiogram.types import ChatMemberUpdated, Message
from utils.logger import get_logger
from services.group_map import upsert_mapping, unlink_chat  # ✅ needs unlink_chat() in service
from config.settings import settings

router = Router()
logger = get_logger(__name__)

# Detect unit numbers like "Truck 5021", "#4509", "Fleet 5310"
TRUCK_RE = re.compile(r"\b(\d{3,5})\b")

# Admins for optional DM notifications
ADMINS = {int(x) for x in (settings.ADMINS or [])}


# ---------------------------------------
# Helpers
# ---------------------------------------
async def _notify_admins(bot, text: str):
    """Optionally DM admins; no messages are sent in the group."""
    # Fix unsupported HTML tags before sending
    safe_text = text.replace("<br>", "\n")

    for uid in ADMINS:
        try:
            await bot.send_message(uid, safe_text, parse_mode="HTML", disable_notification=True)
        except Exception as e:
            logger.warning(f"Could not notify admin {uid}: {e}")

def _extract_unit(title: str) -> str | None:
    """Extract truck/unit number from group title."""
    match = TRUCK_RE.search(title or "")
    return match.group(1) if match else None


# ---------------------------------------
# Membership Updates
# ---------------------------------------
@router.my_chat_member()
async def on_bot_membership_update(ev: ChatMemberUpdated):
    """
    Handles events where the bot joins, leaves, or is kicked from a group.
    Automatically links or unlinks the group.
    """
    chat = ev.chat
    chat_id = chat.id
    title = chat.title or ""
    unit = _extract_unit(title)
    status = ev.new_chat_member.status

    if status in ("left", "kicked"):
        # 🧹 Remove mapping when bot leaves/kicked
        try:
            await unlink_chat(chat_id)
            logger.info(f"🗑️ Removed group mapping → Chat {chat_id} ({title})")
            await _notify_admins(
                ev.bot,
                f"🗑️ <b>Bot removed</b> from <code>{chat_id}</code><br><b>{title}</b><br>Mapping deleted."
            )
        except Exception as e:
            logger.error(f"❌ Failed to unlink chat {chat_id}: {e}")
        return

    # Otherwise, (re)link when added or promoted
    await upsert_mapping(unit, chat_id, title)

    if unit:
        logger.info(f"✅ Linked Truck {unit} → Chat {chat_id} ({title})")
        await _notify_admins(
            ev.bot,
            f"✅ Linked <b>Truck {unit}</b> → <code>{chat_id}</code><br><b>{title}</b>",
        )
    else:
        logger.info(f"🧩 Group without unit number → Chat {chat_id} ({title})")
        await _notify_admins(
            ev.bot,
            f"🧩 No unit number in title<br><code>{chat_id}</code><br><b>{title}</b>",
        )


# ---------------------------------------
# On Any Message (keep mapping fresh)
# ---------------------------------------
@router.message(F.chat.type.in_({"group", "supergroup"}))
async def on_any_group_message(msg: Message):
    """Refresh mapping silently whenever there's activity."""
    title = msg.chat.title or ""
    chat_id = msg.chat.id
    unit = _extract_unit(title)

    await upsert_mapping(unit, chat_id, title)
    logger.debug(f"[auto-map] Updated: chat={chat_id}, unit={unit or '—'}, title='{title}'")


# ---------------------------------------
# Group Title Change
# ---------------------------------------
@router.message(F.new_chat_title)
async def on_group_title_change(msg: Message):
    """Triggered when group title changes → instantly updates mapping."""
    new_title = msg.new_chat_title or msg.chat.title or ""
    chat_id = msg.chat.id
    unit = _extract_unit(new_title)

    await upsert_mapping(unit, chat_id, new_title)
    logger.info(f"🔄 Title changed → chat={chat_id}, unit={unit or '—'}, title={new_title}")
