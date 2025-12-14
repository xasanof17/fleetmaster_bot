import os

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config.settings import settings
from utils.parsers import _normalize

# --------------------------------------------------
# PATHS
# --------------------------------------------------
FILES_BASE = settings.FILES_BASE
TRAILER_BASE = os.path.join(FILES_BASE, "trailer")

REG_DIR = os.path.join(TRAILER_BASE, "registrations_2025")
INSP_DIR = os.path.join(TRAILER_BASE, "annualinspection_2025")


# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def find_pdf(directory: str, unit: str) -> str | None:
    """
    Return full PDF path if a matching file exists, otherwise None.

    Matching rules:
    - Case-insensitive
    - Ignores spaces
    - Trailer unit must be a PREFIX of the filename
    """
    if not directory or not os.path.exists(directory):
        return None

    unit_key = _normalize(unit)

    try:
        for filename in os.listdir(directory):
            if not filename.lower().endswith(".pdf"):
                continue

            file_key = _normalize(filename)
            if file_key.startswith(unit_key):
                return os.path.join(directory, filename)
    except OSError:
        # Directory access issue – fail safely
        return None

    return None


# --------------------------------------------------
# MAIN TRAILER MENU (STATIC)
# --------------------------------------------------
def trailer_menu_kb() -> InlineKeyboardMarkup:
    """
    Static trailer menu.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📘 INTRODUCTION", callback_data="trailer:intro")],
            [InlineKeyboardButton(text="📄 REGISTRATION 2025", callback_data="trailer:reg")],
            [InlineKeyboardButton(text="🧾 INSPECTION 2025", callback_data="trailer:insp")],
            [InlineKeyboardButton(text="ℹ️ FULL INFORMATION", callback_data="trailer:fullinfo")],
        ]
    )


# --------------------------------------------------
# TRAILER FILE KEYBOARD (DYNAMIC)
# --------------------------------------------------
def trailer_file_kb(unit: str) -> InlineKeyboardMarkup:
    """
    Builds trailer document buttons dynamically.

    Rules:
    - Registration button is ALWAYS shown
    - Inspection button is shown ONLY if inspection PDF exists
    """
    unit_clean = unit.strip().upper()
    buttons: list[list[InlineKeyboardButton]] = []

    # --- REGISTRATION (always visible) ---
    buttons.append(
        [
            InlineKeyboardButton(
                text="📄 REGISTRATION PDF",
                callback_data=f"tr_pdf:{unit_clean}:reg",
            )
        ]
    )

    # --- INSPECTION (only if file exists) ---
    if find_pdf(INSP_DIR, unit_clean):
        buttons.append(
            [
                InlineKeyboardButton(
                    text="🧾 INSPECTION PDF",
                    callback_data=f"tr_pdf:{unit_clean}:insp",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
