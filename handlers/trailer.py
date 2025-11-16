# handlers/trailer.py
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from utils.logger import get_logger

logger = get_logger(__name__)
router = Router()


# ────────────────────────────────────────
# MAIN TRAILER MENU
# ────────────────────────────────────────
def trailer_main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📘 INTRODUCTION", callback_data="trailer:intro")],
            [InlineKeyboardButton(text="📄 REGISTRATION 2026", callback_data="trailer:reg2026")],
            [InlineKeyboardButton(text="🧾 ANNUAL INSPECTION 2025", callback_data="trailer:inspect2025")],
            [InlineKeyboardButton(text="ℹ️ FULL INFORMATION", callback_data="trailer:info")]
        ]
    )


@router.callback_query(F.data == "trailer_info")
async def trailer_info_menu(callback: CallbackQuery):
    await callback.answer()
    logger.info(f"User {callback.from_user.id} opened TRAILER menu")

    await callback.message.answer(
        "🚛 **TRAILER INFORMATION MENU**\nChoose a section below:",
        reply_markup=trailer_main_menu()
    )


# ────────────────────────────────────────
# PDF BUTTONS (AFTER SEARCH)
# ────────────────────────────────────────
def trailer_file_buttons(unit: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📄 Registration 2026 PDF",
                callback_data=f"trailer_pdf:{unit}:registration_2026"
            )],
            [InlineKeyboardButton(
                text="🧾 Inspection 2025 PDF",
                callback_data=f"trailer_pdf:{unit}:inspection_2025"
            )],
        ]
    )


# ────────────────────────────────────────
# STATIC SECTION HANDLERS
# ────────────────────────────────────────
@router.callback_query(F.data == "trailer:intro")
async def trailer_intro(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "📘 **TRAILER INTRODUCTION**\n\n"
        "All trailer-related documents, registration, inspections and info "
        "will be available here. Choose other sections to continue."
    )


@router.callback_query(F.data == "trailer:reg2026")
async def trailer_registration(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "📄 **TRAILER REGISTRATION 2026**\n\n"
        "1. Search by unit:\nSend trailer number (example: `H13137`)."
    )


@router.callback_query(F.data == "trailer:inspect2025")
async def trailer_inspection(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🧾 **ANNUAL TRAILER INSPECTION | 2025**\n\n"
        "1. Search by unit:\nSend trailer number (example: `H13137`)."
    )


# ────────────────────────────────────────
# TRAILER INFORMATION SEARCH ENTRY
# ────────────────────────────────────────
@router.callback_query(F.data == "trailer:info")
async def trailer_info_search(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "ℹ️ **TRAILER INFORMATION LOOKUP**\n\n"
        "Enter trailer unit to search (example: `H13137`)."
    )


# ────────────────────────────────────────
# UNIT SEARCH HANDLER
# ────────────────────────────────────────
@router.message(F.text.regexp(r"^[A-Za-z0-9]{4,10}$"))
async def trailer_unit_handler(message: Message):
    unit = message.text.strip().upper()
    logger.info(f"Searching trailer info for unit: {unit}")

    # Dummy database
    sample_data = {
        "H13137": {
            "vin": "1GR1P0628SK-634580",
            "plate": "537-6688",
            "year": "2025",
            "gps": "NOT KNOWN",
            "lease": "XTRA LEASE"
        }
    }

    if unit not in sample_data:
        await message.answer("❌ Trailer not found. Try again.")
        return

    t = sample_data[unit]

    # Trailer info message
    await message.answer(
        f"### {unit}  📌\n"
        f"**VIN:** {t['vin']}\n"
        f"**Plate Number:** {t['plate']}\n"
        f"**Year:** {t['year']}\n"
        f"**GPS:** {t['gps']}\n"
        "======================\n"
        f"{t['lease']}",
        reply_markup=trailer_file_buttons(unit)
    )
