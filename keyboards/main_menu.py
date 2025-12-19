from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings


def get_main_menu_keyboard(user_id: int | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(text="🚛 TRUCK INFORMATION", callback_data="pm_trucker"))
    builder.add(InlineKeyboardButton(text="📂 TRUCK DOCUMENTS", callback_data="documents"))
    builder.add(InlineKeyboardButton(text="🚚 PM SERVICES", callback_data="pm_services"))
    builder.add(InlineKeyboardButton(text="🗳 TRAILER INFORMATION", callback_data="trailer"))

    # 🔐 ADMIN ONLY
    if user_id is not None and user_id in settings.ADMINS:
        builder.add(
            InlineKeyboardButton(
                text="👥 MANAGE USERS",
                callback_data="admin_manage_users",
            )
        )

    builder.add(InlineKeyboardButton(text="❓ Help", callback_data="help"))
    builder.adjust(1)

    return builder.as_markup()


def get_help_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    builder.adjust(1)
    return builder.as_markup()
