# handlers/admin_tools.py

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config.settings import settings
from services.group_map import (
    list_all_groups,
    get_truck_group,
    get_group_by_chat,
)
from utils.logger import get_logger

router = Router()
logger = get_logger(__name__)

ADMINS = set(settings.ADMINS or [])


def is_admin(uid: int) -> bool:
    return uid in ADMINS


# ------------------------------------------------------------
# /groupinfo <unit>
# ------------------------------------------------------------
@router.message(Command("groupinfo"))
async def cmd_groupinfo(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    args = msg.text.split()
    if len(args) < 2:
        return await msg.answer("Usage: `/groupinfo <unit>`", parse_mode="Markdown")

    unit = args[1]
    rec = await get_truck_group(unit)

    if not rec:
        return await msg.answer(f"❌ No group found for `{unit}`")

    await msg.answer(
        f"### 📦 Group Info for {unit}\n"
        f"**Driver:** {rec.get('driver_name') or '❓'}\n"
        f"**Phone:** {rec.get('phone_number') or '❓'}\n"
        f"**Chat ID:** `{rec.get('chat_id')}`\n"
        f"**Title:** {rec.get('title')}\n"
        f"**Updated:** {rec.get('updated_at')}",
        parse_mode="Markdown",
    )


# ------------------------------------------------------------
# /bychat <chat_id>
# ------------------------------------------------------------
@router.message(Command("bychat"))
async def cmd_bychat(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    args = msg.text.split()
    if len(args) < 2:
        return await msg.answer("Usage: `/bychat <chat_id>`")

    chat_id = int(args[1])
    rec = await get_group_by_chat(chat_id)

    if not rec:
        return await msg.answer("❌ No record for that chat ID.")

    await msg.answer(
        f"### 🔎 Chat Lookup\n"
        f"**Unit:** {rec.get('unit')}\n"
        f"**Driver:** {rec.get('driver_name')}\n"
        f"**Phone:** {rec.get('phone_number')}\n"
        f"**Title:** {rec.get('title')}\n"
        f"**Updated:** {rec.get('updated_at')}",
        parse_mode="Markdown",
    )


# ------------------------------------------------------------
# /find <keyword>
# ------------------------------------------------------------
@router.message(Command("find"))
async def cmd_find(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        return await msg.answer("Usage: `/find <keyword>`")

    keyword = args[1].lower()
    groups = await list_all_groups()

    found = []
    for g in groups:
        if (
            keyword in (g.get("driver_name") or "").lower()
            or keyword in (g.get("phone_number") or "").lower()
            or keyword in (g.get("unit") or "").lower()
        ):
            found.append(g)

    if not found:
        return await msg.answer("❌ No matches found.")

    text = "### 🔍 Matches:\n"
    for g in found:
        text += (
            f"\n**{g['unit']}** — {g['driver_name'] or '?'} "
            f"({g['phone_number'] or 'No phone'})\n"
            f"`Chat:` {g['chat_id']} | *{g['title']}*"
        )

    await msg.answer(text, parse_mode="Markdown")


# ------------------------------------------------------------
# /missed
# ------------------------------------------------------------
@router.message(Command("missed"))
async def cmd_missed(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    groups = await list_all_groups()
    missing = [g for g in groups if not g["driver_name"] or not g["phone_number"]]

    if not missing:
        return msg.answer("🎉 All groups have complete data!")

    text = "### ⚠️ Missing Driver / Phone\n"
    for g in missing:
        text += (
            f"\n**{g['unit']}**\n"
            f"Driver: {g['driver_name'] or '❌ Missing'}\n"
            f"Phone: {g['phone_number'] or '❌ Missing'}\n"
            f"`Chat:` {g['chat_id']} | {g['title']}\n"
        )

    await msg.answer(text, parse_mode="Markdown")
