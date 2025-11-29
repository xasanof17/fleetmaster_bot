from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import settings


def get_main_menu_keyboard(user_id: int | None = None) -> InlineKeyboardMarkup:
    """
    Main menu keyboard.
    Admins automatically see extra menu buttons.
    """

    buttons = [
        [InlineKeyboardButton(text="🚛 TRUCK INFORMATION", callback_data="pm_trucker")],
        [InlineKeyboardButton(text="📂 TRUCK DOCUMENTS", callback_data="documents")],
        [InlineKeyboardButton(text="🚚 PM SERVICES", callback_data="pm_services")],
        [InlineKeyboardButton(text="🗳 TRAILER INFORMATION", callback_data="trailer")],
        [InlineKeyboardButton(text="❓ Help", callback_data="help")],
    ]

    # Admin section
    if user_id is not None and user_id in settings.ADMINS:
        buttons.append(
            [InlineKeyboardButton(text="⚙️ Manage Users", callback_data="admin:users")]
        )
        buttons.append(
            [InlineKeyboardButton(text="🛠 Admin Tools", callback_data="admin:tools")]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_help_keyboard() -> InlineKeyboardMarkup:
    """
    Simple help keyboard: back to main menu.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
        ]
    )
