# handlers/admin_refresh.py

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from config.settings import settings
from utils.logger import get_logger
from services.group_map import list_all_groups, upsert_mapping
from utils.parsers import parse_title

router = Router()
logger = get_logger(__name__)

ADMINS = set(settings.ADMINS or [])


@router.message(Command("refresh_all_groups"))
async def refresh_all_groups(msg: Message):
    if msg.from_user.id not in ADMINS:
        return

    await msg.answer("🔄 Refreshing all truck groups… please wait.")

    groups = await list_all_groups()
    if not groups:
        return await msg.answer("⚠️ No groups found in DB.")

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
                parsed["phone"],
            )

            updated += 1
            logger.info(f"[REFRESH] Updated: {title}")

        except Exception as e:
            skipped += 1
            logger.warning(f"[REFRESH] Failed chat {chat_id}: {e}")

    await msg.answer(
        f"✅ Refresh finished!\n"
        f"• Updated: {updated}\n"
        f"• Skipped: {skipped}"
    )
