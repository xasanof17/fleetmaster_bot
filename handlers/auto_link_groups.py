# handlers/auto_link_groups.py
"""
SAFE Auto-Link System (Unified Version)

Uses ONE MASTER PARSER:
    utils.parsers.parse_title()
"""

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.types import Message, ChatMemberUpdated

from utils.parsers import parse_title
from services.group_map import upsert_mapping
from utils.logger import get_logger
from config.settings import settings

router = Router()
logger = get_logger(__name__)

ADMINS = settings.ADMINS or []


# -------------------------------------------------------------
# Admin Alerts
# -------------------------------------------------------------
async def notify_admins(text: str):
    from aiogram import Bot
    bot = Bot(settings.TELEGRAM_BOT_TOKEN)
    for admin in ADMINS:
        try:
            await bot.send_message(admin, text, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin}: {e}")


# -------------------------------------------------------------
# DB UPDATE WRAPPER
# -------------------------------------------------------------
async def update_mapping(chat_id: int, title: str):
    parsed = parse_title(title)

    await upsert_mapping(
        unit=parsed["unit"],
        chat_id=chat_id,
        title=title,
        driver_name=parsed["driver"],
        phone_number=parsed["phone"],
    )

    log_msg = (
        f"🔄 **GROUP UPDATED**\n"
        f"Chat: `{chat_id}`\n"
        f"Title: {title}\n"
        f"Unit: `{parsed['unit'] or 'UNKNOWN'}`\n"
        f"Driver: `{parsed['driver'] or 'UNKNOWN'}`\n"
        f"Phone: `{parsed['phone'] or 'UNKNOWN'}`"
    )

    logger.info(log_msg)
    await notify_admins(log_msg)


# -------------------------------------------------------------
# 1) Detect Title Change
# -------------------------------------------------------------
@router.message(F.new_chat_title)
async def on_title_change(msg: Message):
    new_title = msg.new_chat_title or msg.chat.title
    await update_mapping(msg.chat.id, new_title)


# -------------------------------------------------------------
# 2) Detect ANY Message in Group
# -------------------------------------------------------------
@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def on_group_message(msg: Message):
    title = msg.chat.title or ""
    await update_mapping(msg.chat.id, title)


# -------------------------------------------------------------
# 3) Bot Join / Leave / Role Change
# -------------------------------------------------------------
@router.my_chat_member()
async def on_bot_member_status(update: ChatMemberUpdated):
    chat = update.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    title = chat.title or ""
    await update_mapping(chat.id, title)
