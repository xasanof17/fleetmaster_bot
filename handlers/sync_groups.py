"""
handlers/sync_groups.py
Admin-only command to sync all Telegram groups with DB.
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


@router.message(Command("syncgroups"))
async def sync_groups_cmd(msg: Message):
    """Admin command: sync all groups where bot is a member."""
    user_id = msg.from_user.id
    if user_id not in settings.ADMINS:
        await msg.answer("🚫 You’re not authorized to run this command.")
        logger.warning(f"Unauthorized /syncgroups attempt by {user_id}")
        return

    await msg.answer("🔍 Scanning for groups... please wait ⏳")

    try:
        # 🔹 Telegram doesn’t allow fetching ALL groups at once,
        # so we only sync what the bot already knows (from DB & renames)
        existing_groups = await list_all_groups()

        if not existing_groups:
            await msg.answer("⚠️ No groups in database yet. Add the bot to some truck groups first.")
            return

        synced = 0
        skipped = 0

        for record in existing_groups:
            chat_id = record["chat_id"]
            try:
                chat = await msg.bot.get_chat(chat_id)
                title = chat.title or ""

                match = re.search(r"\b(\d{3,5})\b", title)
                if not match:
                    logger.info(f"❌ Skipped {title} (no truck number)")
                    skipped += 1
                    continue

                unit = match.group(1)
                await upsert_mapping(unit, chat_id, title)
                logger.info(f"✅ Synced {unit} → {chat_id}")
                synced += 1

            except Exception as e:
                logger.error(f"⚠️ Failed to fetch chat {chat_id}: {e}")
                skipped += 1

        await msg.answer(
            f"✅ Sync complete!\n\n"
            f"• Synced: {synced}\n"
            f"• Skipped: {skipped}\n"
            f"🗃 Total in DB: {len(existing_groups)}",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"💥 Sync error: {e}")
        await msg.answer("❌ Something went wrong during sync.")
