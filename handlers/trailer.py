import os
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, Message, InlineKeyboardMarkup, InlineKeyboardButton
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
# CONSTANTS
# --------------------------------------------------
STRONG_MATCH_SCORE = 250  # auto-open threshold

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


def suggestions_kb(trailers: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t, callback_data=f"tr_pick:{t}")]
        for t in trailers
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

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
# FULL INFORMATION (SMART SEARCH)
# --------------------------------------------------
@router.message(TrailerFSM.waiting_info, F.text)
async def handle_info(msg: Message, state: FSMContext):
    raw = msg.text.strip()
    query = _normalize(raw)

    if len(query) < 3:
        await msg.answer("⚠️ Please enter at least 3 characters.\nOr use /cancel")
        return

    trailers = await google_trailer_service.load_all_trailers()

    # 1️⃣ Exact
    info = await google_trailer_service.build_trailer_template(raw)
    if info:
        await msg.answer(info, parse_mode="Markdown", reply_markup=trailer_file_kb(raw))
        return

    # 2️⃣ Score all trailers
    scored = []
    for data in trailers.values():
        score = google_trailer_service.fuzzy_score(raw, data)
        if score > 0:
            scored.append((score, data["trailer"]))

    if not scored:
        await msg.answer("❌ No matching trailer found.\nTry again or /cancel")
        return

    scored.sort(reverse=True)
    best_score, best_trailer = scored[0]

    # 3️⃣ Auto-open if confident
    if best_score >= STRONG_MATCH_SCORE:
        info = await google_trailer_service.build_trailer_template(best_trailer)
        await msg.answer(
            f"🔎 *Best match:* `{best_trailer}`\n\n{info}",
            parse_mode="Markdown",
            reply_markup=trailer_file_kb(best_trailer),
        )
        return

    # 4️⃣ Suggestions (clickable)
    suggestions = [t for _, t in scored[:6]]
    await msg.answer(
        "🤔 *Did you mean one of these?*",
        parse_mode="Markdown",
        reply_markup=suggestions_kb(suggestions),
    )

# --------------------------------------------------
# PICK FROM SUGGESTIONS
# --------------------------------------------------
@router.callback_query(F.data.startswith("tr_pick:"))
async def pick_trailer(cb: CallbackQuery):
    await cb.answer()
    trailer = cb.data.split(":", 1)[1]

    info = await google_trailer_service.build_trailer_template(trailer)
    if not info:
        await cb.message.answer("❌ Trailer not found.")
        return

    await cb.message.answer(
        info,
        parse_mode="Markdown",
        reply_markup=trailer_file_kb(trailer),
    )

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
