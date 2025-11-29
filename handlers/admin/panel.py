# handlers/admin/panel.py

from aiogram import Router, F
from aiogram.filters import Command      # ✅ /admin uchun
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,                              # ✅ /admin uchun
)
from config import settings
from services.access_control import access_storage
from utils.logger import get_logger

logger = get_logger("admin.panel")
router = Router()

ADMINS = set(settings.ADMINS or [])


def is_admin(uid: int) -> bool:
    return uid in ADMINS


# ======================================================
# MAIN ADMIN PANEL UI
# ======================================================
def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟡 Pending Users", callback_data="admin:pending")],
            [InlineKeyboardButton(text="🟢 Approved Users", callback_data="admin:approved")],
            [InlineKeyboardButton(text="🔴 Denied Users", callback_data="admin:denied")],
            [InlineKeyboardButton(text="🔍 Search User", callback_data="admin:search")],
            [InlineKeyboardButton(text="⚙ Manage Users", callback_data="admin:manage")],
        ]
    )


async def _render_admin_panel_message(message: Message | CallbackQuery) -> None:
    """
    Helper: bitta joydan admin panel text + keyboard yuborish.
    Message ham, CallbackQuery ham bilan ishlay oladi.
    """
    if isinstance(message, CallbackQuery):
        msg = message.message
    else:
        msg = message

    await msg.edit_text(
        "🛠 <b>ADMIN PANEL</b>\nChoose an option:",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )


# ======================================================
# /admin command (MESSAGE)
# ======================================================

@router.message(Command("admin"))
async def admin_command(message: Message) -> None:
    """
    /admin — faqat ADMINS uchun.
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ You do not have admin permissions.")
        return

    # /admin kelganda yangi message bilan admin menyu chiqaramiz
    await message.answer(
        "🛠 <b>ADMIN PANEL</b>\nChoose an option:",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )
    logger.info("Admin %s opened /admin panel", message.from_user.id)


# ======================================================
# ADMIN PANEL CALLBACK ENTRY POINT
# ======================================================

@router.callback_query(F.data == "admin")
async def open_admin_panel(callback: CallbackQuery) -> None:
    """
    “⬅ Back” tugmasidan qaytishda, yoki ichki joylardan admin menuga qaytish.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Not allowed", show_alert=True)
        return

    await _render_admin_panel_message(callback)
    await callback.answer()


# ======================================================
# ENTRY FROM MAIN MENU BUTTONS
# ======================================================

@router.callback_query(F.data == "admin:users")
async def open_admin_from_main_menu(callback: CallbackQuery) -> None:
    """
    Main menu dagi ⚙️ Manage Users tugmasi.
    Hozircha to‘g‘ridan-to‘g‘ri ADMIN PANEL ga olib boradi.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Not allowed", show_alert=True)
        return

    await _render_admin_panel_message(callback)
    await callback.answer()


@router.callback_query(F.data == "admin:tools")
async def open_admin_tools_from_main_menu(callback: CallbackQuery) -> None:
    """
    Main menu dagi 🛠 Admin Tools tugmasi.
    Agar alohida handlers.admin_tools ishlayotgan bo‘lsa ham, bu fallback sifatida ishlaydi.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Not allowed", show_alert=True)
        return

    # Agar alohida admin tools paneling bo‘lmasa, shunchaki text
    await callback.message.edit_text(
        "🛠 <b>Admin Tools</b>\n\nTools panel is under construction.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:manage")
async def open_manage_users(callback: CallbackQuery) -> None:
    """
    Admin panel ichidagi ⚙ Manage Users tugmasi.
    Hozircha simple summary + instruction.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Not allowed", show_alert=True)
        return

    pending = len(access_storage.list_pending())
    approved = len(access_storage.list_approved())
    denied = len(access_storage.list_denied())

    text = (
        "👤 <b>USER MANAGEMENT</b>\n\n"
        f"🟡 Pending: <b>{pending}</b>\n"
        f"🟢 Approved: <b>{approved}</b>\n"
        f"🔴 Denied: <b>{denied}</b>\n\n"
        "Use buttons below to view lists or search users."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟡 Pending", callback_data="admin:pending")],
            [InlineKeyboardButton(text="🟢 Approved", callback_data="admin:approved")],
            [InlineKeyboardButton(text="🔴 Denied", callback_data="admin:denied")],
            [InlineKeyboardButton(text="🔍 Search", callback_data="admin:search")],
            [InlineKeyboardButton(text="⬅ Admin Panel", callback_data="admin")],
        ]
    )

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()
