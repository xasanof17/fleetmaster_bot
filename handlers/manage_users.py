"""
handlers/admin_users.py
FleetMaster — Admin User Management
FINAL • STABLE • AIROGRAM v3 SAFE
"""

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from keyboards.manage_users import (
    manage_users_menu,
    user_action_kb,
    users_list_kb,
)
from services.user_service import (
    approve_user,
    get_pending_users,
    get_user_by_id,
    get_users_paginated,
    search_users,
    set_user_active,
)
from utils.logger import get_logger

logger = get_logger("handlers.manage_users")
router = Router()

ADMINS = set(settings.ADMINS or [])
PAGE_SIZE = 10


# ============================================================
# HELPERS
# ============================================================
def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


# ============================================================
# ADMIN MENU ENTRY
# ============================================================
@router.callback_query(F.data == "admin_manage_users")
async def admin_manage_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return

    await callback.message.edit_text(
        "👥 <b>User Management</b>",
        reply_markup=manage_users_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# PENDING USERS
# ============================================================
@router.callback_query(F.data == "manage_users_pending")
async def manage_users_pending(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return

    users = await get_pending_users()

    if not users:
        await callback.message.edit_text(
            "⏳ <b>Pending Users</b>\n\nNo pending users.",
            reply_markup=manage_users_menu(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "⏳ <b>Pending Users</b>",
        reply_markup=users_list_kb(users, prefix="pending_user"),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# ALL USERS (FIRST PAGE)
# ============================================================
@router.callback_query(F.data == "manage_users_all")
async def manage_users_all(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return

    users = await get_users_paginated(PAGE_SIZE, 0)

    await callback.message.edit_text(
        "👥 <b>All Users (page 1)</b>",
        reply_markup=users_list_kb(users, prefix="all_user"),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# ALL USERS (PAGINATION)
# ============================================================
@router.callback_query(F.data.startswith("manage_users_all:page:"))
async def manage_users_all_page(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return

    page = int(callback.data.split(":")[-1])
    offset = page * PAGE_SIZE

    users = await get_users_paginated(PAGE_SIZE, offset)

    if not users:
        await callback.answer("No more users")
        return

    await callback.message.edit_text(
        f"👥 <b>All Users (page {page + 1})</b>",
        reply_markup=users_list_kb(users, prefix="all_user"),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# SEARCH USERS
# ============================================================
@router.callback_query(F.data == "manage_users_search")
async def start_user_search(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return

    await callback.message.edit_text(
        "🔍 <b>Search Users</b>\n\nEnter full name or nickname:",
        parse_mode="HTML",
    )
    await state.set_state("admin_search_users")
    await callback.answer()


@router.message(StateFilter("admin_search_users"))
async def handle_user_search(message: Message, state: FSMContext):
    query = message.text.strip()

    users = await search_users(query, PAGE_SIZE, 0)

    if not users:
        await message.answer("❌ No users found.")
        await state.clear()
        return

    await message.answer(
        f"🔍 <b>Results for:</b> {query}",
        reply_markup=users_list_kb(users, prefix="all_user"),
        parse_mode="HTML",
    )
    await state.clear()


# ============================================================
# OPEN USER PROFILE
# ============================================================
@router.callback_query(F.data.startswith(("pending_user:", "all_user:")))
async def open_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    user = await get_user_by_id(user_id)

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    status = (
        "⏳ Pending"
        if not user["is_approved"]
        else "✅ Active"
        if user["active"]
        else "🚫 Disabled"
    )

    text = (
        f"👤 <b>{user['full_name']}</b>\n\n"
        f"👤 Nickname: @{user.get('nickname') or '—'}\n"
        f"💼 Role: {user['role']}\n"
        f"📧 Gmail: {user['gmail']}\n"
        f"📞 Phone: {user['phone_number']}\n"
        f"📊 Status: {status}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=user_action_kb(user_id, user["active"]),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# ENABLE / DISABLE / APPROVE
# ============================================================
@router.callback_query(F.data.startswith("user_enable:"))
async def enable_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    await approve_user(user_id)
    await set_user_active(user_id, True)

    await callback.bot.send_message(
        user_id,
        "♻️ Your FleetMaster access has been enabled by admin.",
    )

    await callback.answer("User enabled ✅")


@router.callback_query(F.data.startswith("user_disable:"))
async def disable_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    await set_user_active(user_id, False)

    await callback.bot.send_message(
        user_id,
        "🚫 Your FleetMaster access has been disabled.\nContact admin if this is a mistake.",
    )

    await callback.answer("User disabled 🚫")


@router.callback_query(F.data.startswith("user_approve:"))
async def approve_user_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    await approve_user(user_id)
    await set_user_active(user_id, True)

    await callback.bot.send_message(
        user_id,
        "✅ Your FleetMaster access has been approved.\nWelcome aboard 🚛",
    )

    await callback.answer("User approved ✅")
