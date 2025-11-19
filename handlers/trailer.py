import os
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, Message

from config.settings import settings
from keyboards.trailer import trailer_file_kb, trailer_menu_kb

# IMPORT TRAILER SERVICE
from services.google_service import google_trailer_service
from utils.logger import get_logger
from utils.parsers import _normalize

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

    unit_match = re.match(r"([A-Z0-9]+)", filename)
    unit = unit_match.group(1) if unit_match else default_unit

    if "REG" in dirname or "REGISTRATION" in dirname:
        file_type = "REG"
    elif "INSP" in dirname or "INSPECT" in dirname:
        file_type = "INSPECT"
    else:
        file_type = "UNKNOWN"

    year_match = re.search(r"(20[0-9]{2})", dirname)
    if not year_match:
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
    await cb.message.answer(
        "📄 **TRAILER REGISTRATION 2025**\nSend trailer number: (example: A1001)",
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "trailer:insp")
async def trailer_insp(cb: CallbackQuery):
    await cb.answer()
    USER_TRAILER_MODE[cb.from_user.id] = "insp"
    await cb.message.answer(
        "🧾 **ANNUAL TRAILER INSPECTION 2025**\nSend trailer number: (example: A1001)",
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "trailer:fullinfo")
async def trailer_fullinfo(cb: CallbackQuery):
    await cb.answer()
    USER_TRAILER_MODE[cb.from_user.id] = "info"
    await cb.message.answer(
        "ℹ️ **FULL INFORMATION MODE**\nSend trailer number: (example: A1001)",
        parse_mode="Markdown",
    )


# ==============================================================


@router.message(F.text)
async def unit_handler(msg: Message):
    unit_raw = msg.text.strip().upper()

    # ignore long texts / spam
    if len(unit_raw) > 40:
        return

    # normalized key
    unit_key = _normalize(unit_raw)

    user = msg.from_user.id
    mode = USER_TRAILER_MODE.get(user)

    if not mode:
        await msg.answer("❌ Choose a section from the trailer menu first.")
        return

    # =====================================================
    # REGISTRATION PDF MODE
    # =====================================================
    if mode == "reg":
        pdf = find_pdf(REG_DIR, unit_key)
        if not pdf:
            await msg.answer("❌ Registration PDF not found.")
            return

        caption = build_caption(pdf, unit_raw)
        await msg.answer_document(
            FSInputFile(pdf), caption=caption, reply_to_message_id=msg.message_id
        )
        return

    # =====================================================
    # INSPECTION PDF MODE
    # =====================================================
    if mode == "insp":
        pdf = find_pdf(INSP_DIR, unit_key)
        if not pdf:
            await msg.answer("❌ Inspection PDF not found.")
            return

        caption = build_caption(pdf, unit_raw)
        await msg.answer_document(
            FSInputFile(pdf), caption=caption, reply_to_message_id=msg.message_id
        )
        return

    # =====================================================
    # FULL INFORMATION MODE (with fuzzy search)
    # =====================================================
    if mode == "info":
        # load the trailer dict once
        trailers = await google_trailer_service.load_all_trailers()

        # ---------- 1. EXACT / NORMALIZED MATCH ----------
        info = await google_trailer_service.build_trailer_template(unit_raw)
        if info:
            pdf_reg = find_pdf(REG_DIR, unit_key)
            pdf_insp = find_pdf(INSP_DIR, unit_key)

            await msg.answer(
                info,
                parse_mode="Markdown",
                reply_markup=trailer_file_kb(unit_raw) if (pdf_reg or pdf_insp) else None,
            )
            return

        # ---------- 2. FUZZY BEST MATCH ----------
        best = google_trailer_service.fuzzy_best_match(unit_raw, trailers)
        if best:
            info = await google_trailer_service.build_trailer_template(best)

            pdf_reg = find_pdf(REG_DIR, _normalize(best))
            pdf_insp = find_pdf(INSP_DIR, _normalize(best))

            await msg.answer(
                f"🔎 *Closest match:* `{best}`\n\n" + info,
                parse_mode="Markdown",
                reply_markup=trailer_file_kb(best) if (pdf_reg or pdf_insp) else None,
            )
            return

        # ---------- 3. AUTOCOMPLETE / SUGGESTIONS ----------
        suggestions = google_trailer_service.fuzzy_suggestions(unit_raw, trailers)
        if suggestions:
            listing = "\n".join(f"• `{s}`" for s in suggestions)
            await msg.answer(f"🤔 *Did you mean:*\n\n{listing}", parse_mode="Markdown")
            return

        # ---------- 4. NOTHING MATCHED ----------
        await msg.answer("❌ No matching trailers found.")


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
        FSInputFile(pdf), caption=caption, reply_to_message_id=cb.message.message_id
    )
