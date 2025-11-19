from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def trailer_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📘 INTRODUCTION", callback_data="trailer:intro")],
            [InlineKeyboardButton(text="📄 REGISTRATION 2025", callback_data="trailer:reg")],
            [InlineKeyboardButton(text="🧾 INSPECTION 2025", callback_data="trailer:insp")],
            [InlineKeyboardButton(text="ℹ️ FULL INFORMATION", callback_data="trailer:fullinfo")],
        ]
    )


def trailer_file_kb(unit: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📄 REGISTRATION PDF", callback_data=f"tr_pdf:{unit}:reg")],
            [InlineKeyboardButton(text="🧾 INSPECTION PDF", callback_data=f"tr_pdf:{unit}:insp")],
        ]
    )
