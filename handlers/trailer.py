import os
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, Message

from config.settings import settings
from keyboards.trailer import trailer_menu_kb, trailer_file_kb
from services.google_service import google_trailer_service
from utils.parsers import _normalize

router = Router()

FILES_BASE = settings.FILES_BASE
TRAILER_BASE = os.path.join(FILES_BASE, "trailer")

REG_DIR = os.path.join(TRAILER_BASE, "registrations_2025")
INSP_DIR = os.path.join(TRAILER_BASE, "annualinspection_2025")

USER_TRAILER_MODE: dict[int, str] = {}


# --------------------------------------------------
def build_caption(pdf_path: str, unit: str) -> str:
    name = os.path.basename(pdf_path).upper()
    folder = os.path.basename(os.path.dirname(pdf_path)).upper()

    file_type = "REG" if "REG" in folder else "INSPECT"
    year = re.search(r"(20\d{2})", name)
    y = year.group(1) if year else ""

    return f"📄 {unit} — {file_type} {y}".strip()


def find_pdf(directory: str, unit: str):
    if not os.path.exists(directory):
        return None

    unit = unit.upper().replace(" ", "")
    for f in os.listdir(directory):
        if f.lower().endswith(".pdf") and f.upper().replace(" ", "").startswith(unit):
            return os.path.join(directory, f)
    return None


# --------------------------------------------------
@router.callback_query(F.data == "trailer")
async def trailer_menu(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "🚛 **TRAILER INFORMATION**",
        reply_markup=trailer_menu_kb(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "trailer:reg")
async def trailer_reg(cb: CallbackQuery):
    USER_TRAILER_MODE[cb.from_user.id] = "reg"
    await cb.message.answer("📄 Send trailer number:", parse_mode="Markdown")


@router.callback_query(F.data == "trailer:insp")
async def trailer_insp(cb: CallbackQuery):
    USER_TRAILER_MODE[cb.from_user.id] = "insp"
    await cb.message.answer("🧾 Send trailer number:", parse_mode="Markdown")


@router.callback_query(F.data == "trailer:fullinfo")
async def trailer_info(cb: CallbackQuery):
    USER_TRAILER_MODE[cb.from_user.id] = "info"
    await cb.message.answer("ℹ️ Send trailer number:", parse_mode="Markdown")


# --------------------------------------------------
@router.message(F.text)
async def trailer_text_handler(msg: Message):
    unit_raw = msg.text.strip().upper()
    if len(unit_raw) > 40:
        return

    unit_key = _normalize(unit_raw)
    mode = USER_TRAILER_MODE.get(msg.from_user.id)

    if not mode:
        await msg.answer("❌ Please choose Trailer menu first.")
        return

    if mode == "reg":
        pdf = find_pdf(REG_DIR, unit_key)
        if not pdf:
            await msg.answer("❌ Registration PDF not found.")
            return
        await msg.answer_document(FSInputFile(pdf), caption=build_caption(pdf, unit_raw))
        return

    if mode == "insp":
        pdf = find_pdf(INSP_DIR, unit_key)
        if not pdf:
            await msg.answer("❌ Inspection PDF not found.")
            return
        await msg.answer_document(FSInputFile(pdf), caption=build_caption(pdf, unit_raw))
        return

    trailers = await google_trailer_service.load_all_trailers()

    info = await google_trailer_service.build_trailer_template(unit_raw)
    if info:
        await msg.answer(
            info,
            parse_mode="Markdown",
            reply_markup=trailer_file_kb(unit_raw),
        )
        return

    best = google_trailer_service.fuzzy_best_match(unit_raw, trailers)
    if best:
        info = await google_trailer_service.build_trailer_template(best)
        await msg.answer(
            f"🔎 *Closest match:* `{best}`\n\n{info}",
            parse_mode="Markdown",
            reply_markup=trailer_file_kb(best),
        )
        return

    suggestions = google_trailer_service.fuzzy_suggestions(unit_raw, trailers)
    if suggestions:
        await msg.answer(
            "🤔 *Did you mean:*\n" + "\n".join(f"• `{s}`" for s in suggestions),
            parse_mode="Markdown",
        )
        return

    await msg.answer("❌ No matching trailer found.")


# --------------------------------------------------
@router.callback_query(F.data.startswith("tr_pdf:"))
async def trailer_pdf(cb: CallbackQuery):
    await cb.answer()
    _, unit, kind = cb.data.split(":")
    directory = REG_DIR if kind == "reg" else INSP_DIR

    pdf = find_pdf(directory, unit)
    if not pdf:
        await cb.message.answer("❌ PDF not found.")
        return

    await cb.message.answer_document(
        FSInputFile(pdf),
        caption=build_caption(pdf, unit),
    )
