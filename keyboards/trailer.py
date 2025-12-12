import os
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config.settings import settings

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
    Returns full PDF path if exists, otherwise None.
    """
    if not os.path.exists(directory):
        return None

    unit_clean = unit.upper().replace(" ", "")
    for filename in os.listdir(directory):
        if not filename.lower().endswith(".pdf"):
            continue

        if filename.upper().replace(" ", "").startswith(unit_clean):
            return os.path.join(directory, filename)

    return None


# --------------------------------------------------
# MAIN TRAILER MENU (STATIC)
# --------------------------------------------------
def trailer_menu_kb() -> InlineKeyboardMarkup:
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
    Builds trailer file buttons dynamically.
    - Registration button is ALWAYS shown
    - Inspection button is shown ONLY if inspection PDF exists
    """
    buttons: list[list[InlineKeyboardButton]] = []

    # --- REGISTRATION (always available) ---
    buttons.append(
        [
            InlineKeyboardButton(
                text="📄 REGISTRATION PDF",
                callback_data=f"tr_pdf:{unit}:reg",
            )
        ]
    )

    # --- INSPECTION (only if file exists) ---
    inspection_pdf = find_pdf(INSP_DIR, unit)
    if inspection_pdf:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="🧾 INSPECTION PDF",
                    callback_data=f"tr_pdf:{unit}:insp",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
