# handlers/auto_link_groups.py

"""
FleetMaster — Unified Auto-Link Engine (Stable)
-----------------------------------------------

✔ Detects ALL title changes
✔ Handles fired / home / active drivers
✔ Handles no-unit drivers safely
✔ NEVER steals phone digits as unit
✔ Startup recovery (silent)
✔ Smart periodic refresh (no spam)
✔ Session-safe notifications
✔ Admin alerts ONLY on real transitions
"""

import asyncio
import re
import time
from contextlib import suppress

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import ChatMemberUpdated, Message

from config.settings import settings
from services.group_map import list_all_groups, upsert_mapping
from utils.logger import get_logger
from utils.parsers import parse_title

router = Router()
logger = get_logger(__name__)

ADMINS = set(settings.ADMINS or [])

# ─────────────────────────────────────────────
# INTERNAL STATE (SAFE & MINIMAL)
# ─────────────────────────────────────────────

_LAST_TOUCH: dict[int, float] = {}
_LAST_STATUS: dict[int, str] = {}
_LAST_UNIT: dict[int, str | None] = {}
_LAST_TITLE: dict[int, str] = {}

TOUCH_COOLDOWN_SEC = 60
FAST_REFRESH_SEC = 120  # 2 minutes


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────


def _is_admin(uid: int) -> bool:
    return uid in ADMINS


def _is_driver_new(title: str) -> bool:
    return "🔵" in (title or "")


def _detect_driver_status(title: str, unit: str | None) -> str:
    t = (title or "").upper()

    if any(x in t for x in ("FIRED", "TERMINATED", "REMOVED", "❌")):
        return "FIRED"

    if any(x in t for x in ("HOME", "HOME TIME", "🟡")):
        return "HOME"

    if not unit:
        return "HOME"

    return "ACTIVE"


def _extract_units_excluding_phone(title: str) -> list[str]:
    """
    Extract 3–5 digit numbers that are NOT part of phone numbers.
    Fallback only — parser is authoritative.
    """
    digits = re.findall(r"\b\d{3,5}\b", title or "")
    phone_digits = re.sub(r"\D", "", title or "")

    return [d for d in digits if d not in phone_digits]


async def _notify_admins(bot, text: str):
    """Uses existing bot instance — NO session leaks"""
    for admin in ADMINS:
        with suppress(Exception):
            await bot.send_message(admin, text, parse_mode="Markdown")


# ─────────────────────────────────────────────
# CORE SYNC (AUTHORITATIVE)
# ─────────────────────────────────────────────


async def sync_group(
    bot,
    chat_id: int,
    title: str,
    active: bool = True,
    force: bool = False,
):
    title = (title or "").strip()

    parsed = parse_title(title)
    unit: str | None = parsed.get("unit")
    driver = parsed.get("driver")
    phone = parsed.get("phone")

    issues: list[str] = []

    # ────────────────
    # Fallback unit logic
    # ────────────────
    if not unit:
        fallback_units = _extract_units_excluding_phone(title)
        if len(set(fallback_units)) > 1:
            issues.append(f"Multiple units detected: {sorted(set(fallback_units))}")
        elif fallback_units:
            unit = fallback_units[0]
            issues.append("Parser failed, fallback unit used")
        else:
            issues.append("Unit missing")

    # ────────────────
    # Status detection
    # ────────────────
    status = _detect_driver_status(title, unit)
    prev_status = _LAST_STATUS.get(chat_id)
    prev_unit = _LAST_UNIT.get(chat_id)

    # ────────────────
    # DB UPDATE (SOURCE OF TRUTH)
    # ────────────────
    await upsert_mapping(
        unit=unit,
        chat_id=chat_id,
        title=title or "UNKNOWN",
        raw_title=title or "UNKNOWN",
        driver_name=driver,
        phone_number=phone,
        driver_is_new=_is_driver_new(title),
        driver_status=status,
        active=active,
    )

    # ────────────────
    # Memory update (AFTER DB success)
    # ────────────────
    _LAST_UNIT[chat_id] = unit
    _LAST_STATUS[chat_id] = status
    _LAST_TITLE[chat_id] = title

    # ────────────────
    # Notifications (ONLY real transitions)
    # ────────────────

    if prev_unit and unit and prev_unit != unit:
        await _notify_admins(
            bot,
            f"🚚 **UNIT CHANGED**\nDriver: `{driver or 'UNKNOWN'}`\n{prev_unit} → {unit}",
        )

    if prev_status and prev_status != status:
        emoji = "❌" if status == "FIRED" else "🏠" if status == "HOME" else "✅"
        await _notify_admins(
            bot,
            f"{emoji} **STATUS CHANGED**\n"
            f"Driver: `{driver or 'UNKNOWN'}`\n"
            f"Unit: `{unit or 'NONE'}`\n"
            f"{prev_status} → {status}",
        )

    # Data integrity alerts ONLY on forced sync
    if issues and force:
        await _notify_admins(
            bot,
            f"🚨 **DATA ISSUE**\n"
            f"Chat: `{chat_id}`\n"
            f"Title: `{title}`\n\n" + "\n".join(f"• {i}" for i in issues),
        )


# ─────────────────────────────────────────────
# STARTUP RECOVERY (SILENT)
# ─────────────────────────────────────────────


@router.startup()
async def startup_recovery(bot):
    logger.info("Startup recovery: seeding state")

    groups = await list_all_groups()
    for g in groups:
        _LAST_UNIT[g["chat_id"]] = g.get("unit")
        _LAST_STATUS[g["chat_id"]] = g.get("driver_status")
        _LAST_TITLE[g["chat_id"]] = g.get("title")


# ─────────────────────────────────────────────
# PERIODIC REFRESH (SMART)
# ─────────────────────────────────────────────


async def periodic_refresh(bot):
    await asyncio.sleep(10)

    while True:
        groups = await list_all_groups()

        for g in groups:
            with suppress(Exception):
                chat = await bot.get_chat(g["chat_id"])
                if chat.title != _LAST_TITLE.get(chat.id):
                    await sync_group(
                        bot,
                        chat.id,
                        chat.title or "",
                        active=True,
                        force=False,
                    )

        await asyncio.sleep(FAST_REFRESH_SEC)


@router.startup()
async def start_periodic_refresh(bot):
    asyncio.create_task(periodic_refresh(bot))


# ─────────────────────────────────────────────
# EVENT HANDLERS
# ─────────────────────────────────────────────


@router.message(F.new_chat_title)
async def on_title_change(msg: Message):
    await sync_group(
        msg.bot,
        msg.chat.id,
        msg.new_chat_title or msg.chat.title,
        force=True,
    )


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def on_group_message(msg: Message):
    now = time.time()
    if now - _LAST_TOUCH.get(msg.chat.id, 0) < TOUCH_COOLDOWN_SEC:
        return

    _LAST_TOUCH[msg.chat.id] = now
    await sync_group(msg.bot, msg.chat.id, msg.chat.title or "")


@router.my_chat_member()
async def on_bot_status(update: ChatMemberUpdated):
    chat = update.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    status = getattr(update.new_chat_member, "status", "")
    active = status not in {"left", "kicked"}

    await sync_group(
        update.bot,
        chat.id,
        chat.title or "",
        active=active,
        force=True,
    )
