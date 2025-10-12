"""
Universal Search Handler (clean + optimized)
Handles Truck, PM Services, and Document searches
Keeps all existing button callbacks intact
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from keyboards.pm_trucker import get_vehicles_list_keyboard, get_back_to_pm_keyboard
from services import samsara_service, google_pm_service
from utils import format_pm_vehicle_info
from utils.logger import get_logger
from config import settings
import os

router = Router()
logger = get_logger("unified.search")

FILES_BASE = getattr(settings, "FILES_BASE", "./files")
DOC_FOLDERS = {
    "registrations_2026": "registrations_2026",
    "new_mexico": "new_mexico",
    "lease": "lease_agreements",
    "inspection_2025": "annual_inspection",
}


# ==============================
# FSM State
# ==============================
class SearchState(StatesGroup):
    waiting_for_query = State()


# ==============================
# Start Search by Callback
# ==============================
@router.callback_query(lambda c: c.data in ["pm_search_vehicle", "pm_search"])
async def start_vehicle_search(callback: CallbackQuery, state: FSMContext):
    mode = "truck" if callback.data == "pm_search_vehicle" else "pm"
    await state.update_data(mode=mode)
    await state.set_state(SearchState.waiting_for_query)

    menu_name = "🚛 Truck" if mode == "truck" else "🛠 PM Service"
    await callback.message.answer(
        f"{menu_name} Search Mode\n\n"
        "Please enter unit name or number to search.\n"
        "❌ Send /cancel to stop searching.",
        parse_mode="Markdown"
    )
    await callback.answer("Search started!")


# ==============================
# Start Search for Documents
# ==============================
@router.callback_query(lambda c: c.data.startswith("docs:"))
async def start_doc_search(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("Invalid document search")
        return

    doc_type = parts[1]
    await state.update_data(mode="doc", doc_type=doc_type)
    await state.set_state(SearchState.waiting_for_query)

    await callback.message.answer(
        f"📄 Document Search — *{doc_type.replace('_', ' ').title()}*\n\n"
        "Please enter the truck number or name.\n"
        "❌ Send /cancel to stop searching.",
        parse_mode="Markdown"
    )
    await callback.answer("Search started!")


# ==============================
# Handle Search Queries
# ==============================
@router.message(SearchState.waiting_for_query, F.text)
async def process_search(msg: Message, state: FSMContext):
    query = msg.text.strip()
    if query.lower() == "/cancel":
        await cancel_search(msg, state)
        return

    data = await state.get_data()
    mode = data.get("mode", "truck")
    doc_type = data.get("doc_type")

    await msg.answer(f"🔍 Searching `{query}`...", parse_mode="Markdown")

    try:
        if mode == "truck":
            await handle_truck_search(msg, query)
        elif mode == "pm":
            await handle_pm_search(msg, query)
        elif mode == "doc":
            await handle_doc_search(msg, query, doc_type)
        else:
            await msg.answer("❌ Unknown search mode. Please try again.")
    except Exception as e:
        logger.error(f"Search error: {e}")
        await msg.answer("❌ Error while searching. Try again later.")


# ==============================
# Truck Search
# ==============================
async def handle_truck_search(msg: Message, query: str):
    async with samsara_service as svc:
        results = await svc.search_vehicles(query, "all")

    if not results:
        await msg.answer(f"❌ No trucks found for *{query}*.", parse_mode="Markdown")
        return

    await msg.answer(
        f"🎯 Found {len(results)} result(s) for `{query}`:",
        parse_mode="Markdown",
        reply_markup=get_vehicles_list_keyboard(results, page=1, per_page=10)
    )


# ==============================
# PM Search
# ==============================
async def handle_pm_search(msg: Message, query: str):
    details = await google_pm_service.get_vehicle_details(query)
    if not details:
        await msg.answer(f"⚠️ Truck *{query}* not found in PM records.", parse_mode="Markdown")
        return

    text = format_pm_vehicle_info(details, full=True)
    await msg.answer(text, parse_mode="Markdown")


# ==============================
# Document Search
# ==============================
async def handle_doc_search(msg: Message, query: str, doc_type: str):
    folder = DOC_FOLDERS.get(doc_type)
    if not folder:
        await msg.answer("❌ Invalid document type.")
        return

    folder_path = os.path.join(FILES_BASE, folder)
    if not os.path.exists(folder_path):
        await msg.answer("⚠️ Folder not found on server.")
        return

    try:
        for filename in os.listdir(folder_path):
            if query.lower() in filename.lower():
                await msg.answer_document(
                    FSInputFile(os.path.join(folder_path, filename)),
                    caption=f"📄 {doc_type.replace('_', ' ').title()} — Truck {query}"
                )
                return
        await msg.answer(f"❌ No document found for *{query}*.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Doc search error: {e}")
        await msg.answer("❌ Document search failed.")


# ==============================
# Cancel Search
# ==============================
@router.message(F.text == "/cancel")
async def cancel_search(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Search cancelled.", reply_markup=get_back_to_pm_keyboard())
