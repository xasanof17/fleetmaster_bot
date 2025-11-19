import os
import re
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile

from config.settings import settings
from utils.logger import get_logger
from keyboards.trailer import trailer_menu_kb, trailer_file_kb

router = Router()
logger = get_logger(__name__)

FILES_BASE = settings.FILES_BASE
TRAILER_BASE = os.path.join(FILES_BASE, "trailer")

REG_DIR = os.path.join(TRAILER_BASE, "registrations_2025")
INSP_DIR = os.path.join(TRAILER_BASE, "annualinspection_2025")

USER_TRAILER_MODE: dict[int, str] = {}


# ============================================================
# FIXED: CORRECT TYPE + YEAR DETECTION USING DIRECTORY NAME
# ============================================================
def build_caption(pdf_path: str, default_unit: str) -> str:
    filename = os.path.basename(pdf_path).upper()
    dirname = os.path.basename(os.path.dirname(pdf_path)).upper()

    # Extract unit from filename
    unit_match = re.match(r"([A-Z0-9]+)", filename)
    unit = unit_match.group(1) if unit_match else default_unit

    # Detect REG or INSPECT from directory
    if "REG" in dirname or "REGISTRATION" in dirname:
        file_type = "REG"
    elif "INSP" in dirname or "INSPECT" in dirname:
        file_type = "INSPECT"
    else:
        file_type = "UNKNOWN"

    # Detect year from directory name
    year_match = re.search(r"(20[0-9]{2})", dirname)
    if not year_match:
        # fallback, detect year from filename
        year_match = re.search(r"(20[0-9]{2})", filename)

    year = year_match.group(1) if year_match else ""

    return f"📄 {unit} — {file_type}{year}"


# ==============================================================


def find_pdf(directory: str, unit: str) -> str | None:
    if not os.path.exists(directory):
        return None

    unit_clean = unit.upper().replace(" ", "")

    for f in os.listdir(directory):
        if not f.lower().endswith(".pdf"):
            continue
        clean = f.upper().replace(" ", "")
        if clean.startswith(unit_clean):
            return os.path.join(directory, f)

    return None


# ==============================================================


@router.callback_query(F.data == "trailer")
async def trailer(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "🚛 **TRAILER INFORMATION**\nChoose an option:",
        reply_markup=trailer_menu_kb(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "trailer:intro")
async def trailer_intro(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "📘 **TRAILER INTRODUCTION**\n\n"
        "Here you can access Registration, Inspection, and Full Trailer Files.",
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "trailer:reg")
async def trailer_reg(cb: CallbackQuery):
    await cb.answer()
    USER_TRAILER_MODE[cb.from_user.id] = "reg"
    await cb.message.answer("📄 **REGISTRATION**\nSend trailer unit:", parse_mode="Markdown")


@router.callback_query(F.data == "trailer:insp")
async def trailer_insp(cb: CallbackQuery):
    await cb.answer()
    USER_TRAILER_MODE[cb.from_user.id] = "insp"
    await cb.message.answer("🧾 **INSPECTION**\nSend trailer unit:", parse_mode="Markdown")


@router.callback_query(F.data == "trailer:fullinfo")
async def trailer_fullinfo(cb: CallbackQuery):
    await cb.answer()
    USER_TRAILER_MODE[cb.from_user.id] = "info"
    await cb.message.answer("ℹ️ **FULL INFORMATION MODE**\nSend trailer unit:", parse_mode="Markdown")


# ==============================================================


@router.message(F.text.regexp(r"^[A-Za-z0-9]{4,10}$"))
async def unit_handler(msg: Message):
    unit = msg.text.strip().upper()
    user = msg.from_user.id
    mode = USER_TRAILER_MODE.get(user)

    if not mode:
        await msg.answer("❌ Choose a section from the trailer menu first.")
        return

    # --------------- REG ------------------
    if mode == "reg":
        pdf = find_pdf(REG_DIR, unit)
        if not pdf:
            await msg.answer("❌ Registration PDF not found.")
            return

        caption = build_caption(pdf, unit)

        await msg.answer_document(
            FSInputFile(pdf),
            caption=caption,
            reply_to_message_id=msg.message_id
        )
        return

    # --------------- INSP ------------------
    if mode == "insp":
        pdf = find_pdf(INSP_DIR, unit)
        if not pdf:
            await msg.answer("❌ Inspection PDF not found.")
            return

        caption = build_caption(pdf, unit)

        await msg.answer_document(
            FSInputFile(pdf),
            caption=caption,
            reply_to_message_id=msg.message_id
        )
        return

    # --------------- FULL INFO ------------------
    if mode == "info":
        pdf_reg = find_pdf(REG_DIR, unit)
        pdf_insp = find_pdf(INSP_DIR, unit)

        if not pdf_reg and not pdf_insp:
            await msg.answer("❌ No files found for this trailer.")
            return

        await msg.answer(
            f"### {unit}\n"
            f"VIN: *NOT SAVED YET*\n"
            f"Plate: *NOT SAVED YET*\n"
            f"Year: 2025\n"
            f"GPS: NOT KNOWN\n"
            "XTRA LEASE",
            parse_mode="Markdown",
            reply_markup=trailer_file_kb(unit),
        )


# ==============================================================


@router.callback_query(F.data.startswith("tr_pdf:"))
async def send_pdf_btn(cb: CallbackQuery):
    await cb.answer()
    _, unit, kind = cb.data.split(":")

    pdf_dir = REG_DIR if kind == "reg" else INSP_DIR
    pdf = find_pdf(pdf_dir, unit)

    if not pdf:
        await cb.message.answer("❌ PDF not found.")
        return

    caption = build_caption(pdf, unit)

    await cb.message.answer_document(
        FSInputFile(pdf),
        caption=caption,
        reply_to_message_id=cb.message.message_id
    )
