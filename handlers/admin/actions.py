# handlers/admin/actions.py

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from services.access_control import access_storage, AccessStatus
from config import settings

router = Router()
ADMINS = set(settings.ADMINS or [])


# ======================================================
# UTILS
# ======================================================

def is_admin(uid: int) -> bool:
    return uid in ADMINS


def _user_row(req):
    return (
        f"{req.tg_id} — <b>{req.full_name}</b>\n"
        f"{req.telegram_username or '—'}\n"
        f"Role: {req.role}\n"
        f"Status: {req.status.value}"
    )


def _pager_kb(prefix: str, page: int, has_next: bool):
    rows = []

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅", callback_data=f"{prefix}:{page-1}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="➡", callback_data=f"{prefix}:{page+1}"))

    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="⬅ Back", callback_data="admin")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


ITEMS_PER_PAGE = 5


async def _send_user_list(callback: CallbackQuery, title: str, users: list, prefix: str, page: int):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Not allowed", show_alert=True)

    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    sliced = users[start:end]

    if not sliced:
        return await callback.answer("No users on this page", show_alert=True)

    text = f"📄 <b>{title}</b>\n\n"
    for u in sliced:
        text += _user_row(u) + "\n\n"

    has_next = end < len(users)
    kb = _pager_kb(prefix, page, has_next)

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ======================================================
# LIST ROUTES
# ======================================================

@router.callback_query(F.data == "admin:pending")
async def show_pending(callback: CallbackQuery):
    await _send_user_list(callback, "Pending Users", access_storage.list_pending(), "pending_page", 0)


@router.callback_query(F.data.startswith("pending_page:"))
async def pending_page(callback: CallbackQuery):
    await _send_user_list(
        callback,
        "Pending Users",
        access_storage.list_pending(),
        "pending_page",
        int(callback.data.split(":")[1])
    )


@router.callback_query(F.data == "admin:approved")
async def show_approved(callback: CallbackQuery):
    await _send_user_list(callback, "Approved Users", access_storage.list_approved(), "approved_page", 0)


@router.callback_query(F.data.startswith("approved_page:"))
async def approved_page(callback: CallbackQuery):
    await _send_user_list(
        callback,
        "Approved Users",
        access_storage.list_approved(),
        "approved_page",
        int(callback.data.split(":")[1])
    )


@router.callback_query(F.data == "admin:denied")
async def show_denied(callback: CallbackQuery):
    await _send_user_list(callback, "Denied Users", access_storage.list_denied(), "denied_page", 0)


@router.callback_query(F.data.startswith("denied_page:"))
async def denied_page(callback: CallbackQuery):
    await _send_user_list(
        callback,
        "Denied Users",
        access_storage.list_denied(),
        "denied_page",
        int(callback.data.split(":")[1])
    )


# ======================================================
# ACTION BUTTONS (Approve/Deny/Delete/Role)
# ======================================================

def _admin_actions_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Approve", callback_data=f"adminact:approve:{user_id}")],
            [InlineKeyboardButton(text="❌ Deny", callback_data=f"adminact:deny:{user_id}")],
            [InlineKeyboardButton(text="🗑 Delete", callback_data=f"adminact:delete:{user_id}")],
            [InlineKeyboardButton(text="♻ Change Role", callback_data=f"adminact:role:{user_id}")],
            [InlineKeyboardButton(text="⬅ Back", callback_data="admin")],
        ]
    )



def _role_keyboard(user_id: int) -> InlineKeyboardMarkup:
    roles = [
        "Manager",
        "Dispatcher",
        "Fleet specialist",
        "Safety specialist",
        "Updater",
        "Fuel coordinator",
        "Trailer coordinator"
    ]

    keyboard = [
        [InlineKeyboardButton(text=role, callback_data=f"setrole:{role}:{user_id}")]
        for role in roles
    ]

    # Add BACK button
    keyboard.append(
        [InlineKeyboardButton(text="⬅ Back", callback_data=f"adminact:back:{user_id}")]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)



@router.callback_query(F.data.startswith("adminact:"))
async def admin_action_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Not allowed", show_alert=True)

    _, action, user_id = callback.data.split(":")
    user_id = int(user_id)

    req = access_storage.get(user_id)
    if not req:
        return await callback.answer("User not found", show_alert=True)

    # -------- approve --------
    if action == "approve":
        access_storage.update_status(user_id, AccessStatus.APPROVED)
        await callback.message.edit_text(
            f"✅ <b>User Approved</b>\n\n{_user_row(req)}",
            parse_mode="HTML"
        )
        return await callback.answer("Approved")

    # -------- deny --------
    if action == "deny":
        access_storage.update_status(user_id, AccessStatus.DENIED)
        await callback.message.edit_text(
            f"❌ <b>User Denied</b>\n\n{_user_row(req)}",
            parse_mode="HTML"
        )
        return await callback.answer("Denied")

    # -------- delete --------
    if action == "delete":
        access_storage.delete_user(user_id)
        await callback.message.edit_text(
            f"🗑 <b>User Deleted</b>\n\nID: {user_id}",
            parse_mode="HTML"
        )
        return await callback.answer("Deleted")

    # -------- role change --------
    if action == "role":
        await callback.message.edit_text(
            f"♻ <b>Change Role</b>\nUser: {req.full_name}",
            parse_mode="HTML",
            reply_markup=_role_keyboard(user_id)
        )
        return await callback.answer()

    # -------- back --------
    if action == "back":
        await callback.message.edit_text(
            _user_row(req),
            parse_mode="HTML",
            reply_markup=_admin_actions_kb(user_id)
        )
        return await callback.answer()


# ======================================================
# SET ROLE CALLBACK
# ======================================================

@router.callback_query(F.data.startswith("setrole:"))
async def set_role(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Not allowed", show_alert=True)

    _, role, user_id = callback.data.split(":")
    user_id = int(user_id)

    req = access_storage.update_role(user_id, role)

    await callback.message.edit_text(
        f"✅ <b>Role Updated</b>\n\nUser: {req.full_name}\nNew Role: <b>{role}</b>",
        parse_mode="HTML"
    )
    await callback.answer("Role updated")
