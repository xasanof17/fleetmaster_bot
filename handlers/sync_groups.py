"""
handlers/sync_groups.py
Admin-only command to sync Telegram groups from DB state.
"""
import re
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from config.settings import settings
from services.group_map import upsert_mapping, list_all_groups
from utils.logger import get_logger

logger = get_logger(__name__)
router = Router()

UNIT_RE = re.compile(r"\b(\d{3,5})\b")

@router.message(Command("syncgroups"))
async def sync_groups_cmd(msg: Message):
    """Admin command: sync groups known in DB with current Telegram titles."""
    user_id = msg.from_user.id
    if user_id not in settings.ADMINS:
        await msg.answer("🚫 You’re not authorized to run this command.")
        logger.warning(f"Unauthorized /syncgroups attempt by {user_id}")
        return

    note = await msg.answer("🔍 Syncing groups… please wait ⏳")

    try:
        existing_groups = await list_all_groups()
        if not existing_groups:
            await note.edit_text("⚠️ No groups in database yet. Add the bot to some groups first.")
            return

        synced = 0
        skipped = 0

        for record in existing_groups:
            chat_id = record["chat_id"]
            try:
                chat = await msg.bot.get_chat(chat_id)
                title = (chat.title or "").strip()
                m = UNIT_RE.search(title)
                unit = m.group(1) if m else None

                await upsert_mapping(unit, chat_id, title or record.get("title", ""))
                if unit:
                    synced += 1
                    logger.info(f"✅ Synced {unit} → {chat_id} ({title})")
                else:
                    skipped += 1
                    logger.info(f"⏭️ Skipped {chat_id} (no unit in title '{title}')")
            except Exception as e:
                skipped += 1
                logger.error(f"⚠️ Failed to fetch chat {chat_id}: {e}")

        await note.edit_text(
            f"✅ Sync complete!\n\n"
            f"• Synced: {synced}\n"
            f"• Skipped: {skipped}\n"
            f"🗃 Total in DB: {len(existing_groups)}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"💥 Sync error: {e}")
        await note.edit_text("❌ Something went wrong during sync.")
