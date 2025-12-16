import os
import re
import time

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config.settings import settings
from keyboards.trailer import trailer_file_kb, trailer_menu_kb
from services.google_service import google_trailer_service
from utils.parsers import _normalize

router = Router()

# --------------------------------------------------
# PATHS & CONSTANTS
# --------------------------------------------------
FILES_BASE = settings.FILES_BASE
TRAILER_BASE = os.path.join(FILES_BASE, "trailer")

REG_DIR = os.path.join(TRAILER_BASE, "registrations_2025")
INSP_DIR = os.path.join(TRAILER_BASE, "annualinspection_2025")

STRONG_MATCH_SCORE = 250  # Threshold for auto-opening results

# --------------------------------------------------
# GLOBAL CACHE (Memory Storage for Speed)
# --------------------------------------------------
_TRAILER_CACHE = {"data": None, "last_updated": 0}
CACHE_TTL = 600  # Data stays in memory for 10 minutes


async def get_cached_trailers():
    """Fetches from Google once, then returns from memory for 10 minutes."""
    now = time.time()
    if _TRAILER_CACHE["data"] and (now - _TRAILER_CACHE["last_updated"] < CACHE_TTL):
        return _TRAILER_CACHE["data"]

    try:
        data = await google_trailer_service.load_all_trailers()
        if data:
            _TRAILER_CACHE["data"] = data
            _TRAILER_CACHE["last_updated"] = now
        return data
    except Exception:
        return _TRAILER_CACHE["data"] or {}


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
    rows = [[InlineKeyboardButton(text=t, callback_data=f"tr_pick:{t}")] for t in trailers]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --------------------------------------------------
# MENU & CANCEL
# --------------------------------------------------
@router.message(F.text.in_({"/cancel", "cancel", "❌ cancel"}))
async def cancel_any(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Action cancelled.", reply_markup=trailer_menu_kb())


@router.callback_query(F.data == "trailer")
async def trailer_menu(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer(
        "🚛 **TRAILER INFORMATION**\nChoose an option:",
        reply_markup=trailer_menu_kb(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data.in_({"trailer:reg", "trailer:insp", "trailer:fullinfo"}))
async def trailer_input_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    if cb.data == "trailer:reg":
        await state.set_state(TrailerFSM.waiting_reg)
        prompt = "📄 Send trailer number for **Registration**:"
    elif cb.data == "trailer:insp":
        await state.set_state(TrailerFSM.waiting_insp)
        prompt = "🧾 Send trailer number for **Inspection**:"
    else:
        await state.set_state(TrailerFSM.waiting_info)
        prompt = "ℹ️ Send trailer number for **Full Info**:"

    await cb.message.answer(prompt, parse_mode="Markdown")


# --------------------------------------------------
# SEARCH LOGIC (WITH CACHING + LOADING STATUS)
# --------------------------------------------------


@router.message(TrailerFSM.waiting_info, F.text)
async def handle_info(msg: Message, state: FSMContext):
    raw = msg.text.strip()
    query = _normalize(raw)

    if len(query) < 2:
        await msg.answer("⚠️ Please enter at least 2 characters.")
        return

    # 🟢 VISUAL: Show "typing..."
    await msg.bot.send_chat_action(chat_id=msg.chat.id, action=ChatAction.TYPING)

    # STEP 1: Fast Cache Access
    trailers = await get_cached_trailers()
    if not trailers:
        await msg.answer("⚠️ Service temporarily unavailable.")
        return

    # STEP 2: Instant Scoring
    scored = []
    exact_match_unit = None

    for unit_id, data in trailers.items():
        if query == _normalize(unit_id):
            exact_match_unit = unit_id
            break
        score = google_trailer_service.fuzzy_score(raw, data)
        if score > 0:
            scored.append((score, data["trailer"]))

    target_unit = exact_match_unit
    is_strong = False

    if not target_unit and scored:
        scored.sort(reverse=True)
        best_score, best_trailer = scored[0]
        if best_score >= STRONG_MATCH_SCORE:
            target_unit = best_trailer
            is_strong = True

    # STEP 3: Return Results
    if target_unit:
        info = await google_trailer_service.build_trailer_template(target_unit)
        prefix = "🔎 *Best match:* " if is_strong else ""
        await msg.answer(
            f"{prefix}`{target_unit}`\n\n{info}",
            parse_mode="Markdown",
            reply_markup=trailer_file_kb(target_unit),
        )
        return

    # Fallback to Suggestions
    if scored:
        suggestions = [t for _, t in scored[:6]]
        await msg.answer(
            "🤔 *Did you mean one of these?*",
            parse_mode="Markdown",
            reply_markup=suggestions_kb(suggestions),
        )
    else:
        await msg.answer("🤔 No matches found. Use /cancel to exit.")


# --------------------------------------------------
# CALLBACK & PDF HANDLERS
# --------------------------------------------------


@router.callback_query(F.data.startswith("tr_pick:"))
async def pick_trailer(cb: CallbackQuery):
    await cb.answer()
    trailer = cb.data.split(":", 1)[1]

    await cb.message.bot.send_chat_action(chat_id=cb.message.chat.id, action=ChatAction.TYPING)
    info = await google_trailer_service.build_trailer_template(trailer)

    await cb.message.answer(
        info or "❌ Trailer not found.",
        parse_mode="Markdown",
        reply_markup=trailer_file_kb(trailer),
    )


@router.callback_query(F.data.startswith("tr_pdf:"))
async def trailer_pdf(cb: CallbackQuery):
    await cb.answer()
    parts = cb.data.split(":")
    if len(parts) < 3:
        return

    _, unit, kind = parts
    directory = REG_DIR if kind == "reg" else INSP_DIR
    pdf = find_pdf(directory, unit)

    if not pdf:
        await cb.message.answer(f"❌ {kind.upper()} PDF not found for {unit}.")
        return

    # 🟢 VISUAL: Show "uploading document..."
    await cb.message.bot.send_chat_action(
        chat_id=cb.message.chat.id, action=ChatAction.UPLOAD_DOCUMENT
    )

    await cb.message.answer_document(
        FSInputFile(pdf),
        caption=build_caption(pdf, unit),
    )
