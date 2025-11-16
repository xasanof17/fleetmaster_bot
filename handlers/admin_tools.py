# handlers/admin_tools.py
"""
Admin Tools for FleetMaster
Powerful commands for inspecting driver + truck group metadata.
"""

from aiogram import Router, F
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


# ------------------------------------------------------------
# Admin check helper
# ------------------------------------------------------------
def is_admin(uid: int) -> bool:
    return uid in ADMINS


# ------------------------------------------------------------
# /groupinfo <unit>
# ------------------------------------------------------------
@router.message(Command("groupinfo"))
async def group_info(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    args = msg.text.strip().split()
    if len(args) < 2:
        await msg.answer("Usage: `/groupinfo <unit>`", parse_mode="Markdown")
        return

    unit = args[1].strip()

    rec = await get_truck_group(unit)
    if not rec:
        await msg.answer(f"❌ No record found for unit `{unit}`.")
        return

    text = (
        f"### 📦 Group Info for Unit {unit}\n"
        f"**Unit:** {rec.get('unit')}\n"
        f"**Driver:** {rec.get('driver_name') or '❓ Unknown'}\n"
        f"**Phone:** {rec.get('phone_number') or '❓ Unknown'}\n"
        f"**Chat ID:** `{rec.get('chat_id')}`\n"
        f"**Title:** {rec.get('title')}\n"
        f"**Created:** {rec.get('created_at')}\n"
        f"**Updated:** {rec.get('updated_at')}\n"
    )
    await msg.answer(text, parse_mode="Markdown")


# ------------------------------------------------------------
# /bychat <chat_id>
# ------------------------------------------------------------
@router.message(Command("bychat"))
async def get_by_chat(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    args = msg.text.strip().split()
    if len(args) < 2:
        await msg.answer("Usage: `/bychat <chat_id>`")
        return

    chat_id = int(args[1])
    rec = await get_group_by_chat(chat_id)

    if not rec:
        await msg.answer("❌ No record found for that chat.")
        return

    await msg.answer(
        f"### 🔎 Lookup by Chat ID `{chat_id}`\n"
        f"**Unit:** {rec.get('unit')}\n"
        f"**Driver:** {rec.get('driver_name')}\n"
        f"**Phone:** {rec.get('phone_number')}\n"
        f"**Title:** {rec.get('title')}\n"
        f"**Updated:** {rec.get('updated_at')}\n",
        parse_mode="Markdown",
    )


# ------------------------------------------------------------
# /find keyword
# search driver name or phone number
# ------------------------------------------------------------
@router.message(Command("find"))
async def find_group(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    args = msg.text.strip().split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("Usage: `/find <keyword>`")
        return

    keyword = args[1].lower()
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
        await msg.answer("❌ No groups matched your search.")
        return

    text = "### 🔍 Results:\n"
    for g in results:
        text += (
            f"\n**Unit:** {g['unit']} | **Driver:** {g['driver_name']} | **Phone:** {g['phone_number']}\n"
            f"`Chat ID:` {g['chat_id']} — *{g['title']}*"
        )

    await msg.answer(text, parse_mode="Markdown")


# ------------------------------------------------------------
# /allgroups
# ------------------------------------------------------------
@router.message(Command("allgroups"))
async def all_groups(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    groups = await list_all_groups()
    if not groups:
        await msg.answer("❌ No groups found in DB.")
        return

    text = "### 📋 All Truck Groups\n"
    for g in groups:
        text += (
            f"\n**{g['unit']}** — {g['driver_name'] or 'Unknown'} "
            f"({g['phone_number'] or 'No phone'})\n"
            f"`Chat ID:` {g['chat_id']} — *{g['title']}*"
        )

    await msg.answer(text, parse_mode="Markdown")


# ------------------------------------------------------------
# /missed
# groups missing driver or phone
# ------------------------------------------------------------
@router.message(Command("missed"))
async def missing_data(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    groups = await list_all_groups()
    missing = [
        g for g in groups
        if not g.get("driver_name") or not g.get("phone_number")
    ]

    if not missing:
        await msg.answer("🎉 All groups have full driver info!")
        return

    text = "### ⚠️ Groups Missing Driver or Phone\n"
    for g in missing:
        text += (
            f"\n**Unit:** {g['unit']}\n"
            f"Driver: {g['driver_name'] or '❓ Missing'}\n"
            f"Phone: {g['phone_number'] or '❓ Missing'}\n"
            f"`Chat:` {g['chat_id']} — {g['title']}\n"
        )

    await msg.answer(text, parse_mode="Markdown")
