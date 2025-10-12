# handlers/admin_tools.py
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
import re

from utils.logger import get_logger
from services.group_map import upsert_mapping, list_all_groups

router = Router()
logger = get_logger(__name__)

UNIT_RE = re.compile(r"\b(\d{3,5})\b")

@router.message(Command("rescan"))
async def rescan_groups(message: Message):
    """
    Rebuild unit→group mapping using groups we already know in DB.
    - Pull all groups from DB
    - Fetch current titles from Telegram
    - Extract unit (3-5 digits) from title
    - Upsert mapping
    NOTE: Telegram Bot API cannot list 'all chats', so we rescan known chats only.
    """
    msg = await message.answer("🔍 Rescanning known groups…")

    try:
        groups = await list_all_groups()
        if not groups:
            await msg.edit_text("⚠️ No groups in DB yet. Add the bot to truck groups first.")
            return

        synced = 0
        skipped = 0
        for rec in groups:
            chat_id = rec["chat_id"]
            try:
                chat = await message.bot.get_chat(chat_id)
                title = (chat.title or "").strip()
                m = UNIT_RE.search(title)
                unit = m.group(1) if m else None

                await upsert_mapping(unit, chat_id, title or rec.get("title", ""))
                if unit:
                    synced += 1
                    logger.info(f"[RESCAN] {chat_id} ⇒ unit {unit} ({title})")
                else:
                    skipped += 1
                    logger.info(f"[RESCAN] {chat_id} (no unit in title '{title}')")
            except Exception as e:
                skipped += 1
                logger.warning(f"[RESCAN] Failed to fetch chat {chat_id}: {e}")

        await msg.edit_text(f"✅ Done! Updated {synced} groups, skipped {skipped}.")
    except Exception as e:
        logger.error(f"[RESCAN] Error: {e}")
        await msg.edit_text("❌ Rescan failed. Check logs.")
