# handlers/admin_refresh.py

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from config.settings import settings
from services.group_map import list_all_groups, upsert_mapping
from utils.logger import get_logger
from utils.parsers import parse_title

router = Router()
logger = get_logger(__name__)

ADMINS = set(settings.ADMINS or [])


@router.message(Command("refresh_all_groups"))
async def refresh_all_groups(msg: Message):
    """Re-scan every known truck group using the latest parser (unit/driver/phone)."""

    if msg.from_user.id not in ADMINS:
        return  # not admin — silent ignore

    await msg.answer("🔄 Refreshing all truck groups…\nThis may take a few seconds.")

    groups = await list_all_groups()
    if not groups:
        return await msg.answer("⚠️ Database is empty — no groups to refresh.")

    updated = 0
    skipped = 0

    for rec in groups:
        chat_id = rec["chat_id"]

        try:
            # Fetch latest group title from Telegram
            chat = await msg.bot.get_chat(chat_id)
            title = (chat.title or "").strip()

            # Parse title using new aggressive parser
            parsed = parse_title(title)

            # Update DB
            await upsert_mapping(
                unit=parsed["unit"],
                chat_id=chat_id,
                title=title,
                driver_name=parsed["driver"],
                phone_number=parsed["phone"],
            )

            updated += 1
            logger.info(f"[REFRESH] Updated: {title}")

        except Exception as e:
            skipped += 1
            logger.warning(f"[REFRESH] FAILED chat_id={chat_id}: {e}")

    # Final admin result message
    await msg.answer(
        f"✅ **Refresh Complete**\n"
        f"• Updated: **{updated}** groups\n"
        f"• Skipped: **{skipped}** (unavailable or deleted)\n"
        f"🗂 Parser Version: **V4.0**"
    )
