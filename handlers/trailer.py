import os
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config.settings import settings
from keyboards.trailer import trailer_menu_kb, trailer_file_kb
from services.google_service import google_trailer_service
from utils.parsers import _normalize

router = Router()

# --------------------------------------------------
# PATHS
# --------------------------------------------------
FILES_BASE = settings.FILES_BASE
TRAILER_BASE = os.path.join(FILES_BASE, "trailer")

REG_DIR = os.path.join(TRAILER_BASE, "registrations_2025")
INSP_DIR = os.path.join(TRAILER_BASE, "annualinspection_2025")


# --------------------------------------------------
# FSM
# --------------------------------------------------
class TrailerFSM(StatesGroup):
    waiting_reg = State()
    waiting_insp = State()
    waiting_info = State()


# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def build_caption(pdf_path: str, unit: str) -> str:
    name = os.path.basename(pdf_path).upper()
    folder = os.path.basename(os.path.dirname(pdf_path)).upper()

    file_type = "REG" if "REG" in folder else "INSPECT"
    year_match = re.search(r"(20\d{2})", name)
    year = year_match.group(1) if year_match else ""

    return f"📄 {unit} — {file_type} {year}".strip()


def find_pdf(directory: str, unit: str):
    if not os.path.exists(directory):
        return None

    key = unit.upper().replace(" ", "")
    for f in os.listdir(directory):
        if f.lower().endswith(".pdf") and f.upper().replace(" ", "").startswith(key):
            return os.path.join(directory, f)
    return None


# --------------------------------------------------
# CANCEL (GLOBAL)
# --------------------------------------------------
@router.message(F.text.in_({"/cancel", "cancel", "❌ cancel"}))
async def cancel_any(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        "❌ Action cancelled.\n\nChoose an option:",
        reply_markup=trailer_menu_kb(),
    )


# --------------------------------------------------
# MENU
# --------------------------------------------------
@router.callback_query(F.data == "trailer")
async def trailer_menu(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer(
        "🚛 **TRAILER INFORMATION**\nChoose an option:",
        reply_markup=trailer_menu_kb(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "trailer:intro")
async def trailer_intro(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "You can get trailer registration and inspection PDFs here."
    )


@router.callback_query(F.data == "trailer:reg")
async def trailer_reg(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(TrailerFSM.waiting_reg)
    await cb.message.answer("📄 Send trailer number:")


@router.callback_query(F.data == "trailer:insp")
async def trailer_insp(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(TrailerFSM.waiting_insp)
    await cb.message.answer("🧾 Send trailer number:")


@router.callback_query(F.data == "trailer:fullinfo")
async def trailer_info(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(TrailerFSM.waiting_info)
    await cb.message.answer("ℹ️ Send trailer number:")


# --------------------------------------------------
# REGISTRATION
# --------------------------------------------------
@router.message(TrailerFSM.waiting_reg, F.text)
async def handle_reg(msg: Message, state: FSMContext):
    unit = _normalize(msg.text)
    pdf = find_pdf(REG_DIR, unit)

    if not pdf:
        await msg.answer("❌ Registration PDF not found.\nTry again or /cancel")
        return

    await msg.answer_document(
        FSInputFile(pdf),
        caption=build_caption(pdf, msg.text),
    )


# --------------------------------------------------
# INSPECTION
# --------------------------------------------------
@router.message(TrailerFSM.waiting_insp, F.text)
async def handle_insp(msg: Message, state: FSMContext):
    unit = _normalize(msg.text)
    pdf = find_pdf(INSP_DIR, unit)

    if not pdf:
        await msg.answer("❌ Inspection PDF not found.\nTry again or /cancel")
        return

    await msg.answer_document(
        FSInputFile(pdf),
        caption=build_caption(pdf, msg.text),
    )


# --------------------------------------------------
# FULL INFORMATION (REPEATABLE – FIXED)
# --------------------------------------------------
@router.message(TrailerFSM.waiting_info, F.text)
async def handle_info(msg: Message, state: FSMContext):
    query = msg.text.strip()
    trailers = await google_trailer_service.load_all_trailers()

    # 1️⃣ EXACT / NORMALIZED
    info = await google_trailer_service.build_trailer_template(query)
    if info:
        await msg.answer(
            info,
            parse_mode="Markdown",
            reply_markup=trailer_file_kb(query),
        )
        return

    # 2️⃣ FUZZY BEST MATCH
    best = google_trailer_service.fuzzy_best_match(query, trailers)
    if best:
        info = await google_trailer_service.build_trailer_template(best)
        await msg.answer(
            f"🔎 *Closest match:* `{best}`\n\n{info}",
            parse_mode="Markdown",
            reply_markup=trailer_file_kb(best),
        )
        return

    # 3️⃣ SUGGESTIONS
    suggestions = google_trailer_service.fuzzy_suggestions(query, trailers)
    if suggestions:
        await msg.answer(
            "🤔 *Did you mean:*\n" + "\n".join(f"• `{s}`" for s in suggestions),
            parse_mode="Markdown",
        )
        return

    await msg.answer("❌ No matching trailer found.\nTry again or /cancel")


# --------------------------------------------------
# PDF BUTTON HANDLER
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
