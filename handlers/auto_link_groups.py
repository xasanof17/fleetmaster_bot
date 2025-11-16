"""
SAFE Auto-Link System + AUTO REFRESH LOOP (NO EXTRA FILES)
-----------------------------------------------------------

This version:
  ✔ Updates driver/unit/phone on ANY message
  ✔ Updates on title change
  ✔ Updates when bot joins/leaves
  ✔ Manual refresh via /refresh_all_groups
  ✔ AUTO REFRESHES ALL GROUPS EVERY 6 HOURS (even silent groups)
"""

import asyncio
import re
import emoji
from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.types import Message, ChatMemberUpdated

from utils.parsers import parse_title
from services.group_map import upsert_mapping, list_all_groups
from utils.logger import get_logger
from config.settings import settings

router = Router()
logger = get_logger(__name__)

ADMINS = settings.ADMINS or []
BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN


# ============================================================
#   ADMIN ALERTS
# ============================================================
async def notify_admins(text: str):
    from aiogram import Bot
    bot = Bot(BOT_TOKEN)

    for admin in ADMINS:
        try:
            await bot.send_message(admin, text, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin}: {e}")


# ============================================================
#   UPDATE DB MAPPING
# ============================================================
async def update_mapping(chat_id: int, title: str):
    parsed = parse_title(title)

    await upsert_mapping(
        unit=parsed["unit"],
        chat_id=chat_id,
        title=title,
        driver_name=parsed["driver"],
        phone_number=parsed["phone"],
    )

    msg = (
        f"🔄 **GROUP UPDATED**\n"
        f"Chat ID: `{chat_id}`\n"
        f"Title: {title}\n"
        f"Unit: `{parsed['unit'] or 'UNKNOWN'}`\n"
        f"Driver: `{parsed['driver'] or 'UNKNOWN'}`\n"
        f"Phone: `{parsed['phone'] or 'UNKNOWN'}`"
    )

    logger.info(msg)
    await notify_admins(msg)


# ============================================================
#   AUTO REFRESH LOOP (NO EXTRA FILES)
# ============================================================
async def auto_refresh_loop(bot, interval_hours: int = 6):
    """Auto refresh all groups every X hours even if silent."""
    await asyncio.sleep(5)  # let bot start fully

    while True:
        try:
            logger.info("🔄 AUTO-REFRESH STARTED...")

            groups = await list_all_groups()
            updated = 0
            skipped = 0

            for g in groups:
                chat_id = g["chat_id"]
                try:
                    chat = await bot.get_chat(chat_id)
                    title = (chat.title or "").strip()

                    parsed = parse_title(title)

                    await upsert_mapping(
                        parsed["unit"],
                        chat_id,
                        title,
                        parsed["driver"],
                        parsed["phone"],
                    )

                    updated += 1

                except Exception as e:
                    skipped += 1
                    logger.warning(f"AUTO-REFRESH FAIL chat={chat_id}: {e}")

            logger.info(f"🔄 AUTO-REFRESH DONE → Updated={updated}, Skipped={skipped}")

        except Exception as e:
            logger.error(f"AUTO-REFRESH LOOP ERROR: {e}")

        await asyncio.sleep(interval_hours * 3600)


# ============================================================
#   START AUTO REFRESH WHEN BOT STARTS
# ============================================================
@router.startup()
async def start_auto_refresh(bot):
    asyncio.create_task(auto_refresh_loop(bot, interval_hours=6))
    logger.info("⏳ AUTO REFRESH LOOP ACTIVATED")


# ============================================================
#   1) TITLE CHANGE
# ============================================================
@router.message(F.new_chat_title)
async def on_title_change(msg: Message):
    new_title = msg.new_chat_title or msg.chat.title
    await update_mapping(msg.chat.id, new_title)


# ============================================================
#   2) ANY MESSAGE IN GROUP
# ============================================================
@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def on_group_message(msg: Message):
    title = msg.chat.title or ""
    await update_mapping(msg.chat.id, title)


# ============================================================
#   3) BOT PERMISSION CHANGES
# ============================================================
@router.my_chat_member()
async def on_bot_status(update: ChatMemberUpdated):
    chat = update.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    title = chat.title or ""
    await update_mapping(chat.id, title)


# ============================================================
#   4) MANUAL ADMIN REFRESH (/refresh_all_groups)
# ============================================================
@router.message(F.text == "/refresh_all_groups")
async def refresh_all_groups(msg: Message):
    if msg.from_user.id not in ADMINS:
        return

    await msg.answer("🔄 Refreshing all truck groups… This may take a moment.")

    groups = await list_all_groups()
    if not groups:
        return await msg.answer("⚠️ No groups in DB.")

    updated = 0
    skipped = 0

    for rec in groups:
        chat_id = rec["chat_id"]

        try:
            chat = await msg.bot.get_chat(chat_id)
            title = (chat.title or "").strip()

            parsed = parse_title(title)

            await upsert_mapping(
                parsed["unit"],
                chat_id,
                title,
                parsed["driver"],
                parsed["phone"]
            )

            updated += 1

        except Exception as e:
            skipped += 1
            logger.warning(f"[MANUAL REFRESH] chat={chat_id} failed: {e}")

    await msg.answer(
        f"✅ Refresh finished!\n"
        f"• Updated: {updated}\n"
        f"• Skipped: {skipped}"
    )
