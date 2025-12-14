"""
SAFE Auto-Link System + AUTO REFRESH LOOP
----------------------------------------

✔ Updates driver/unit/phone on title change
✔ Updates on bot permission changes
✔ Updates on group activity (debounced)
✔ Manual refresh via /refresh_all_groups
✔ Auto-refreshes all groups every 6 hours
✔ Prevents duplicate logs & admin spam
✔ GROUP UPDATED messages shown ONLY on request
"""

import asyncio
import time
from typing import Dict, Tuple

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import ChatMemberUpdated, Message

from config.settings import settings
from services.group_map import list_all_groups, upsert_mapping
from utils.logger import get_logger
from utils.parsers import parse_title

router = Router()
logger = get_logger(__name__)

ADMINS = settings.ADMINS or []
BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN

# ============================================================
# INTERNAL STATE (ANTI-SPAM / ANTI-FLOOD)
# ============================================================

# chat_id -> (unit, driver, phone, title)
_LAST_STATE: Dict[int, Tuple[str | None, str | None, str | None, str]] = {}

# chat_id -> last update timestamp
_LAST_TOUCH: Dict[int, float] = {}

TOUCH_COOLDOWN_SEC = 60
_REFRESH_TASK_STARTED = False


# ============================================================
# ADMIN NOTIFICATIONS
# ============================================================
async def notify_admins(text: str):
    """Send message to all admins (best-effort)."""
    from aiogram import Bot

    bot = Bot(BOT_TOKEN)

    for admin in ADMINS:
        try:
            await bot.send_message(admin, text, parse_mode="Markdown")
        except Exception:
            logger.debug("Admin notify failed for %s", admin)


# ============================================================
# CORE UPDATE LOGIC (DEDUPED + SILENT BY DEFAULT)
# ============================================================
async def update_mapping(chat_id: int, title: str, notify: bool = False):
    """
    Parse title → update DB only if something actually changed.
    Admin notifications are sent ONLY if notify=True.
    """
    parsed = parse_title(title)

    new_state = (
        parsed["unit"],
        parsed["driver"],
        parsed["phone"],
        title.strip(),
    )

    old_state = _LAST_STATE.get(chat_id)
    if old_state == new_state:
        return

    _LAST_STATE[chat_id] = new_state

    await upsert_mapping(
        unit=parsed["unit"],
        chat_id=chat_id,
        title=title,
        driver_name=parsed["driver"],
        phone_number=parsed["phone"],
    )

    logger.info(
        "GROUP UPDATED | chat=%s unit=%s driver=%s phone=%s",
        chat_id,
        parsed["unit"],
        parsed["driver"],
        parsed["phone"],
    )

    if notify:
        await notify_admins(
            f"🔄 **GROUP UPDATED**\n"
            f"Chat: `{chat_id}`\n"
            f"Unit: `{parsed['unit'] or 'UNKNOWN'}`\n"
            f"Driver: `{parsed['driver'] or 'UNKNOWN'}`\n"
            f"Phone: `{parsed['phone'] or 'UNKNOWN'}`"
        )


# ============================================================
# AUTO REFRESH LOOP
# ============================================================
async def auto_refresh_loop(bot, interval_hours: int = 6):
    await asyncio.sleep(5)

    while True:
        try:
            logger.info("AUTO-REFRESH START")

            groups = await list_all_groups()
            updated = 0
            skipped = 0

            for g in groups:
                try:
                    chat = await bot.get_chat(g["chat_id"])
                    await update_mapping(chat.id, chat.title or "")
                    updated += 1
                except Exception:
                    skipped += 1

            logger.info("AUTO-REFRESH DONE | updated=%s skipped=%s", updated, skipped)

        except Exception as e:
            logger.error("AUTO-REFRESH LOOP ERROR: %s", e)

        await asyncio.sleep(interval_hours * 3600)


@router.startup()
async def start_auto_refresh(bot):
    global _REFRESH_TASK_STARTED
    if _REFRESH_TASK_STARTED:
        return

    _REFRESH_TASK_STARTED = True
    asyncio.create_task(auto_refresh_loop(bot))
    logger.info("AUTO-REFRESH LOOP ACTIVATED")


# ============================================================
# EVENT HANDLERS (ALL SILENT)
# ============================================================

@router.message(F.new_chat_title)
async def on_title_change(msg: Message):
    await update_mapping(msg.chat.id, msg.new_chat_title or msg.chat.title)


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def on_group_message(msg: Message):
    now = time.time()
    last = _LAST_TOUCH.get(msg.chat.id, 0)

    if now - last < TOUCH_COOLDOWN_SEC:
        return

    _LAST_TOUCH[msg.chat.id] = now
    await update_mapping(msg.chat.id, msg.chat.title or "")


@router.my_chat_member()
async def on_bot_status(update: ChatMemberUpdated):
    chat = update.chat
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update_mapping(chat.id, chat.title or "")


# ============================================================
# MANUAL ADMIN REFRESH (SILENT)
# ============================================================
@router.message(F.text == "/refresh_all_groups")
async def refresh_all_groups(msg: Message):
    if msg.from_user.id not in ADMINS:
        return

    await msg.answer("🔄 Refreshing all truck groups…")

    groups = await list_all_groups()
    if not groups:
        return await msg.answer("⚠️ No groups in database.")

    updated = 0
    skipped = 0

    for g in groups:
        try:
            chat = await msg.bot.get_chat(g["chat_id"])
            await update_mapping(chat.id, chat.title or "")
            updated += 1
        except Exception:
            skipped += 1

    await msg.answer(f"✅ Refresh complete\nUpdated: {updated}\nSkipped: {skipped}")


# ============================================================
# GROUP STATUS (ADMIN — EXPLICIT REQUEST)
# ============================================================
@router.message(F.text == "/group_status")
async def group_status(msg: Message):
    """
    Show GROUP UPDATED messages ONLY when explicitly requested.
    """
    if msg.from_user.id not in ADMINS:
        return

    await msg.answer("📊 Fetching current group status…")

    groups = await list_all_groups()
    if not groups:
        return await msg.answer("⚠️ No groups in database.")

    sent = 0
    failed = 0

    for g in groups:
        try:
            chat = await msg.bot.get_chat(g["chat_id"])
            await update_mapping(chat.id, chat.title or "", notify=True)
            sent += 1
        except Exception:
            failed += 1

    await msg.answer(f"✅ Status complete\nSent: {sent}\nFailed: {failed}")
