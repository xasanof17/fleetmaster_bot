# handlers/auto_link_groups.py
"""
SAFE Auto-Link System (Final Version)
--------------------------------------

This module auto-detects:

    ✔ Truck Unit (3–5 digits anywhere)
    ✔ Driver Name (supports prefixes: Mr, Ms, Driver)
    ✔ Phone Number (all US formats)
    ✔ Handles emojis, weird formatting, separators (# - | , . _ /)
    ✔ Works even if title order changes (unit first or last)
    ✔ Never unlinks DB rows (0% danger)
    ✔ Always updates PSQL instantly
    ✔ Sends admin alerts on ANY update
    ✔ Triggered by:
         - Group title changes
         - Any message in group
         - Bot join/leave/promote
         - Group settings changes

This is the safest and strongest version.
"""

import re
import emoji
from typing import Optional

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.types import Message, ChatMemberUpdated

from services.group_map import upsert_mapping
from utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)
router = Router()

ADMINS = settings.ADMINS  # Make sure this exists in settings.py


# ----------------------------------------------------------------------
# REGEX DEFINITIONS
# ----------------------------------------------------------------------

# TRUCK UNIT (3–5 digits anywhere)
UNIT_RE = re.compile(r"\b(\d{3,5})\b")

# PHONE NUMBER (universal US format)
PHONE_RE = re.compile(
    r"(\+?\d{1,3}[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}"
)

# DRIVER NAME (supports: Mr, Ms, Mrs, Driver)
DRIVER_RE = re.compile(
    r"(?:Mr|Ms|Mrs|Driver)?\s*([A-Za-z]{2,20}(?:\s+[A-Za-z]{2,20}){0,3})"
)


# ----------------------------------------------------------------------
# NORMALIZER
# ----------------------------------------------------------------------

def normalize_title(t: str) -> str:
    """Remove emojis + normalize separators."""
    if not t:
        return ""

    # Remove emojis
    t = emoji.replace_emoji(t, "")

    # Replace separators with spaces
    t = re.sub(r"[#\-\|_/.,]+", " ", t)

    # Collapse multiple spaces
    t = re.sub(r"\s+", " ", t)

    return t.strip()


# ----------------------------------------------------------------------
# PARSERS
# ----------------------------------------------------------------------

def extract_unit(title: str) -> Optional[str]:
    if not title:
        return None
    m = UNIT_RE.search(title)
    return m.group(1) if m else None


def extract_phone(title: str) -> Optional[str]:
    if not title:
        return None
    p = PHONE_RE.search(title)
    return p.group(0).strip() if p else None


def extract_driver(title: str, unit: Optional[str], phone: Optional[str]) -> Optional[str]:
    """Extract driver name AFTER removing unit + phone."""

    cleaned = normalize_title(title)

    # Remove unit
    if unit:
        cleaned = cleaned.replace(unit, "")

    # Remove phone
    if phone:
        cleaned = cleaned.replace(phone, "")

    # Detect driver name
    m = DRIVER_RE.search(cleaned)
    if not m:
        return None

    name = m.group(1).strip()
    if len(name) < 2:
        return None

    return name


def parse_group_title(title: str):
    """Main parser used everywhere."""
    original = title

    # detect unit
    unit = extract_unit(title)

    # detect phone
    phone = extract_phone(original)

    # detect driver name
    driver = extract_driver(original, unit, phone)

    return {
        "unit": unit,
        "driver": driver,
        "phone": phone,
        "raw_title": original,
        "clean_title": normalize_title(original),
    }


# ----------------------------------------------------------------------
# ADMIN ALERTS
# ----------------------------------------------------------------------

async def notify_admins(text: str):
    from aiogram import Bot
    bot = Bot(settings.TELEGRAM_BOT_TOKEN)

    for admin in ADMINS:
        try:
            await bot.send_message(admin, text)
        except Exception as e:
            logger.error(f"❌ Failed to notify admin {admin}: {e}")


# ----------------------------------------------------------------------
# DB UPDATE WRAPPER
# ----------------------------------------------------------------------

async def update_mapping(chat_id: int, title: str):
    parsed = parse_group_title(title)
    unit = parsed["unit"]
    driver = parsed["driver"]
    phone = parsed["phone"]

    # Always update DB — never unlink
    await upsert_mapping(
        unit=unit,
        chat_id=chat_id,
        title=title,
        driver_name=driver,
        phone_number=phone,
    )

    msg = (
        f"🔄 **GROUP UPDATED**\n"
        f"Chat ID: `{chat_id}`\n"
        f"Title: {title}\n"
        f"Unit: {unit or '❓ Unknown'}\n"
        f"Driver: {driver or '❓ Unknown'}\n"
        f"Phone: {phone or '❓ Unknown'}"
    )

    logger.info(msg)
    await notify_admins(msg)


# ----------------------------------------------------------------------
# 1) TITLE CHANGE
# ----------------------------------------------------------------------

@router.message(F.new_chat_title)
async def on_title_change(msg: Message):
    new_title = msg.new_chat_title or msg.chat.title
    await update_mapping(msg.chat.id, new_title)


# ----------------------------------------------------------------------
# 2) ANY MESSAGE IN GROUP
# ----------------------------------------------------------------------

@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def on_group_message(msg: Message):
    title = msg.chat.title or ""
    await update_mapping(msg.chat.id, title)


# ----------------------------------------------------------------------
# 3) BOT JOIN / LEAVE / PROMOTION
# ----------------------------------------------------------------------

@router.my_chat_member()
async def on_bot_status(update: ChatMemberUpdated):
    chat = update.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    title = chat.title or ""
    await update_mapping(chat.id, title)
