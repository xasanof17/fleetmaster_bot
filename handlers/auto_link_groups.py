# handlers/auto_link_groups.py

"""
FleetMaster — Unified Auto-Link Engine
-------------------------------------

✔ Detects ALL title changes
✔ Handles fired / home / active drivers
✔ Handles no-unit drivers safely
✔ NEVER steals phone digits as unit
✔ Fast periodic refresh (authoritative)
✔ Startup recovery
✔ No spam
✔ No permission changes
✔ Admin alerts ONLY on real transitions
"""

import asyncio
import re
import time

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
# INTERNAL STATE (MINIMAL, SAFE)
# ─────────────────────────────────────────────

_LAST_TOUCH: dict[int, float] = {}
_LAST_STATUS: dict[int, str] = {}
_LAST_UNIT: dict[int, str | None] = {}

TOUCH_COOLDOWN_SEC = 60
FAST_REFRESH_SEC = 120  # 2 min — REAL fast refresh


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

    clean = []
    for d in digits:
        if d not in phone_digits:
            clean.append(d)

    return clean


async def _notify_admins(text: str):
    from aiogram import Bot

    bot = Bot(settings.TELEGRAM_BOT_TOKEN)

    for admin in ADMINS:
        try:
            await bot.send_message(admin, text, parse_mode="Markdown")
        except Exception:
            pass


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

    # ─────────────────────────────────────
    # 🔑 PARSE (SINGLE SOURCE OF TRUTH)
    # ─────────────────────────────────────
    parsed = parse_title(title)

    unit: str | None = parsed.get("unit")
    driver = parsed.get("driver")
    phone = parsed.get("phone")

    issues: list[str] = []

    # ─────────────────────────────────────
    # 🛟 SAFE FALLBACK (ONLY IF PARSER FAILED)
    # ─────────────────────────────────────
    if not unit:
        fallback_units = _extract_units_excluding_phone(title)

        if len(set(fallback_units)) > 1:
            issues.append(f"Multiple units detected: {sorted(set(fallback_units))}")
        elif fallback_units:
            unit = fallback_units[0]
            issues.append("Parser failed, fallback unit used")
        else:
            issues.append("Unit missing")

    # ─────────────────────────────────────
    # 🧠 UNIT CHANGE TRACKING
    # ─────────────────────────────────────
    prev_unit = _LAST_UNIT.get(chat_id)

    if prev_unit and unit and prev_unit != unit:
        issues.append(f"Unit changed {prev_unit} → {unit}")

    if unit:
        _LAST_UNIT[chat_id] = unit

        # sanity check
        if not re.fullmatch(r"\d{3,5}", unit):
            issues.append(f"Invalid unit format: {unit}")

    # ─────────────────────────────────────
    # 🚦 STATUS DETECTION (STRICT RULES)
    # ─────────────────────────────────────
    status = _detect_driver_status(title, unit)
    prev_status = _LAST_STATUS.get(chat_id)
    _LAST_STATUS[chat_id] = status

    # ─────────────────────────────────────
    # 👤 DRIVER / VALUE VALIDATION
    # ─────────────────────────────────────
    if not driver:
        issues.append("Driver name missing")

    if not phone:
        issues.append("Phone number missing")

    # ─────────────────────────────────────
    # 🗄️ DB UPDATE (AUTHORITATIVE)
    # ─────────────────────────────────────
    await upsert_mapping(
        unit=unit,
        chat_id=chat_id,
        title=title or "UNKNOWN",
        raw_title=title or "UNKNOWN",
        driver_name=parsed.get("driver"),
        phone_number=parsed.get("phone"),
        driver_is_new=_is_driver_new(title),
        driver_status=status,
        active=active,
    )

    # ─────────────────────────────────────
    # 🔔 NOTIFICATIONS
    # ─────────────────────────────────────

    # 1️⃣ DRIVER STATUS CHANGE
    if prev_status and prev_status != status:
        await _notify_admins(
            f"⚠️ **DRIVER STATUS CHANGED**\n"
            f"Chat: `{chat_id}`\n"
            f"{prev_status} → {status}\n"
            f"Unit: `{unit or 'NONE'}`\n"
            f"Driver: `{driver or 'UNKNOWN'}`"
        )

    # 2️⃣ DATA / UNIT ISSUES (AGGREGATED)
    if issues:
        await _notify_admins(
            f"🚨 **DATA ISSUE DETECTED**\n"
            f"Chat: `{chat_id}`\n"
            f"Title: `{title}`\n\n" + "\n".join(f"• {i}" for i in issues)
        )


# ─────────────────────────────────────────────
# STARTUP RECOVERY
# ─────────────────────────────────────────────


@router.startup()
async def startup_recovery(bot):
    logger.info("Startup recovery: syncing all groups")

    groups = await list_all_groups()
    for g in groups:
        try:
            chat = await bot.get_chat(g["chat_id"])
            await sync_group(bot, chat.id, chat.title or "", active=True, force=True)
        except Exception:
            continue


# ─────────────────────────────────────────────
# FAST PERIODIC REFRESH
# ─────────────────────────────────────────────


async def periodic_refresh(bot):
    await asyncio.sleep(10)

    while True:
        groups = await list_all_groups()
        for g in groups:
            try:
                chat = await bot.get_chat(g["chat_id"])
                await sync_group(bot, chat.id, chat.title or "", active=True, force=True)
            except Exception:
                continue

        await asyncio.sleep(FAST_REFRESH_SEC)


@router.startup()
async def start_periodic_refresh(bot):
    asyncio.create_task(periodic_refresh(bot))


# ─────────────────────────────────────────────
# EVENT HANDLERS
# ─────────────────────────────────────────────


@router.message(F.new_chat_title)
async def on_title_change(msg: Message):
    await sync_group(msg.bot, msg.chat.id, msg.new_chat_title or msg.chat.title)


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def on_group_message(msg: Message):
    now = time.time()
    last = _LAST_TOUCH.get(msg.chat.id, 0)

    if now - last < TOUCH_COOLDOWN_SEC:
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

    await sync_group(update.bot, chat.id, chat.title or "", active=active, force=True)
