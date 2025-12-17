"""
handlers/admin.py
FleetMaster — Admin Controls & User Approval
"""

import contextlib
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from config.settings import settings
from services.group_map import upsert_mapping
from services.user_service import approve_user, get_user_by_id, update_last_active
from utils.logger import get_logger

router = Router()
logger = get_logger(__name__)
ADMINS = set(settings.ADMINS or [])

# ============================================================
# COMMANDS
# ============================================================


@router.message(F.text == "/id")
async def my_id(msg: Message):
    is_admin = msg.from_user.id in ADMINS
    await msg.answer(
        f"Your ID: `{msg.from_user.id}`\n"
        f"ADMINS List: `{list(ADMINS)}`\n"
        f"Admin Status: {'✅ Authorized' if is_admin else '❌ Unauthorized'}",
        parse_mode="Markdown",
    )


@router.message(F.chat.type.in_({"group", "supergroup"}), F.text.regexp(r"^/link\s+(\d+)$"))
async def link_group(msg: Message, regexp: re.Match):
    if msg.from_user.id not in ADMINS:
        return

    unit = regexp.group(1)
    try:
        await upsert_mapping(unit, msg.chat.id, msg.chat.title or "")
        await msg.answer(f"✅ Group linked to **Unit {unit}** successfully.")
    except Exception as e:
        logger.error(f"Link failed: {e}")
        await msg.answer("❌ Failed to link group. Check logs.")


# ============================================================
# USER APPROVAL HANDLERS
# ============================================================


@router.callback_query(F.data.startswith("approve_"))
async def handle_approve_user(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.answer("⛔ Only system admins can do this.", show_alert=True)
        return

    user_id = int(callback.data.split("_")[1])

    try:
        # 1. Update DB & Set initial activity
        await approve_user(user_id)
        await update_last_active(user_id)

        # 2. Update Admin View
        user = await get_user_by_id(user_id)
        await callback.message.edit_text(
            f"✅ **User Approved**\n"
            f"👤 Name: {user['full_name']}\n"
            f"💼 Role: {user['role']}\n"
            f"📞 Phone: {user['phone_number']}\n"
            f"📧 Gmail: {user['gmail']}\n"
            f"👮 Approved by: {callback.from_user.full_name}",
            parse_mode="Markdown",
        )

        # 3. Notify User
        await callback.bot.send_message(
            user_id,
            "🎉 **Access Granted!**\n\n"
            "An administrator has approved your request. \n"
            "Send /start to open the FleetMaster Dashboard.",
            parse_mode="Markdown",
        )
        await callback.answer("User approved.")

    except Exception as e:
        logger.error(f"Approval error: {e}")
        await callback.answer("❌ Error during approval.", show_alert=True)


@router.callback_query(F.data.startswith("reject_"))
async def handle_reject_user(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.answer("⛔ Access denied.", show_alert=True)
        return

    user_id = int(callback.data.split("_")[1])
    await callback.message.edit_text("❌ **Access Request Rejected**")

    with contextlib.suppress(Exception):
        await callback.bot.send_message(
            user_id,
            "❌ **Access Denied**\n\n"
            "Your request to access FleetMaster was declined. Please contact your manager.",
        )

    await callback.answer("Request rejected.")
