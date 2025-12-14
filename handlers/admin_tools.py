# handlers/admin_tools.py
"""
Admin Tools for FleetMaster Bot
Uses NEW V4 Parser logic (unit, driver, phone)
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config.settings import settings
from services.group_map import (
    get_group_by_chat,
    get_truck_group,
    list_all_groups,
)
from utils.logger import get_logger

router = Router()
logger = get_logger(__name__)

ADMINS = set(settings.ADMINS or [])


# ------------------------------------------------------------
# Helper
# ------------------------------------------------------------
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
        return await msg.answer("Usage:\n`/groupinfo <unit>`", parse_mode="Markdown")

    unit = args[1].strip()
    rec = await get_truck_group(unit)

    if not rec:
        return await msg.answer(f"❌ No group found for `{unit}`")

    await msg.answer(
        f"### 📦 Group Info for `{unit}`\n"
        f"**Driver:** {rec.get('driver_name') or '❓ Unknown'}\n"
        f"**Phone:** {rec.get('phone_number') or '❓ Unknown'}\n"
        f"**Chat ID:** `{rec.get('chat_id')}`\n"
        f"**Title:** {rec.get('title')}\n"
        f"**Created:** {rec.get('created_at')}\n"
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

    try:
        chat_id = int(args[1])
    except (IndexError, ValueError):
        return await msg.answer("❌ Chat ID must be an integer.")

    rec = await get_group_by_chat(chat_id)

    if not rec:
        return await msg.answer("❌ No record found for that chat ID.")

    await msg.answer(
        f"### 🔎 Chat Lookup: `{chat_id}`\n"
        f"**Unit:** {rec.get('unit')}\n"
        f"**Driver:** {rec.get('driver_name') or '❓'}\n"
        f"**Phone:** {rec.get('phone_number') or '❓'}\n"
        f"**Title:** {rec.get('title')}\n"
        f"**Updated:** {rec.get('updated_at')}",
        parse_mode="Markdown",
    )


# ------------------------------------------------------------
# /find <keyword>
# Search by driver, phone, or unit
# ------------------------------------------------------------
@router.message(Command("find"))
async def cmd_find(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        return await msg.answer("Usage: `/find <keyword>`")

    keyword = args[1].lower().strip()
    groups = await list_all_groups()

    results = []
    for g in groups:
        if (
            keyword in (g.get("driver_name") or "").lower()
            or keyword in (g.get("phone_number") or "").lower()
            or keyword in (g.get("unit") or "").lower()
        ):
            results.append(g)

    if not results:
        return await msg.answer("❌ No records matched your search.")

    text = "### 🔍 Search Results\n"
    for g in results:
        text += (
            f"\n**Unit:** {g['unit']}\n"
            f"Driver: {g['driver_name'] or '❓'}\n"
            f"Phone: {g['phone_number'] or '❓'}\n"
            f"`Chat:` {g['chat_id']} | *{g['title']}*\n"
        )

    await msg.answer(text, parse_mode="Markdown")


# ------------------------------------------------------------
# /allgroups
# ------------------------------------------------------------
@router.message(Command("allgroups"))
async def cmd_allgroups(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    groups = await list_all_groups()
    if not groups:
        return await msg.answer("❌ No groups in DB.")

    text = "### 📋 All Truck Groups\n"
    for g in groups:
        text += (
            f"\n**{g['unit']}** — {g['driver_name'] or '❓'} "
            f"({g['phone_number'] or '❓'})\n"
            f"`Chat:` {g['chat_id']} — *{g['title']}*\n"
        )

    await msg.answer(text, parse_mode="Markdown")


# ------------------------------------------------------------
# /missed
# List groups missing driver or phone
# ------------------------------------------------------------
@router.message(Command("missed"))
async def cmd_missed(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    groups = await list_all_groups()
    missing = [g for g in groups if not g.get("driver_name") or not g.get("phone_number")]

    if not missing:
        return await msg.answer("🎉 All groups have full driver + phone info!")

    text = "### ⚠️ Missing Driver / Phone\n"
    for g in missing:
        text += (
            f"\n**Unit:** {g['unit']}\n"
            f"Driver: {g['driver_name'] or '❗ Missing'}\n"
            f"Phone: {g['phone_number'] or '❗ Missing'}\n"
            f"`Chat:` {g['chat_id']} — {g['title']}\n"
        )

    await msg.answer(text, parse_mode="Markdown")
