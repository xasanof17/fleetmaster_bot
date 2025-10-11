# handlers/auto_link_groups.py
import re
from aiogram import Router, F
from aiogram.types import ChatMemberUpdated, Message
from utils.logger import get_logger
from services.group_map import upsert_mapping
from config.settings import settings

router = Router()
logger = get_logger(__name__)

# 3..5 digit unit anywhere in the title, e.g. "Truck 2002" or "#5077"
TRUCK_RE = re.compile(r"\b(\d{3,5})\b")
ADMINS = {int(x) for x in (settings.ADMINS or [])}

async def _notify_admins(bot, text: str):
    """Optionally DM admins; no messages are sent in the group."""
    for uid in ADMINS:
        try:
            await bot.send_message(uid, text, parse_mode="HTML", disable_notification=True)
        except Exception as e:
            logger.warning(f"Could not notify admin {uid}: {e}")

@router.my_chat_member()
async def on_bot_membership_update(ev: ChatMemberUpdated):
    chat = ev.chat
    title = chat.title or ""
    chat_id = chat.id

    # try to parse truck/unit from the chat title
    unit = None
    m = TRUCK_RE.search(title)
    if m:
        unit = m.group(1)

    # persist mapping (unit can be None if not parseable)
    await upsert_mapping(unit, chat_id, title)

    # ✅ LOG ONLY (do not reply in the group)
    if unit:
        logger.info(f"✅ Linked Truck {unit} -> Chat {chat_id} ({title})")
        await _notify_admins(
            ev.bot,
            f"✅ Linked <b>Truck {unit}</b> → <code>{chat_id}</code>\n{title}"
        )
    else:
        logger.info(f"🧩 Group seen without unit in title -> Chat {chat_id} ({title})")
        await _notify_admins(
            ev.bot,
            f"🧩 Group has no unit number in title:\n<code>{chat_id}</code>\n<b>{title}</b>"
        )

@router.message(F.chat.type.in_({"group", "supergroup"}))
async def on_any_group_message(msg: Message):
    """Refresh mapping on any activity; still no replies to the group."""
    title = msg.chat.title or ""
    chat_id = msg.chat.id

    unit = None
    m = TRUCK_RE.search(title)
    if m:
        unit = m.group(1)

    await upsert_mapping(unit, chat_id, title)
    # light log (no await!)
    logger.debug(f"[GroupActivity] cached: chat={chat_id} title='{title}' unit={unit}")
