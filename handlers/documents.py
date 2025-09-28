from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.documents import documents_menu_kb, get_documents_vehicle_keyboard
from services.samsara_service import samsara_service
import os

documents_router = Router()
FILES_BASE = "files"

DOC_FOLDERS = {
    "registrations_2026": "registrations_2026",
    "new_mexico": "new_mexico",
    "lease": "lease_agreements",
    "inspection_2025": "annual_inspection",
}


class DocumentSearch(StatesGroup):
    waiting_for_truck = State()


# 📂 Entry point
@documents_router.callback_query(F.data == "documents")
async def show_documents_menu(callback: CallbackQuery):
    doc_intro = (
    "📂 **DOCUMENTS** – Fleet & Compliance Files\n\n"
    "Access key paperwork in one place:\n"
    "• Registrations and state permits\n"
    "• Lease agreements and annual inspections\n\n"
    "Select a document category below to view or download:"
)
    await callback.message.edit_text(
        doc_intro,
        reply_markup=documents_menu_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


# 📂 Document type chosen
@documents_router.callback_query(F.data.startswith("docs:"))
async def documents_flow(callback: CallbackQuery):
    parts = callback.data.split(":")

    # docs:<doc_type>
    if len(parts) == 2:
        _, doc_type = parts

        kb = InlineKeyboardBuilder()
        kb.button(text="🏷️ Search by Truck Number", callback_data=f"docs_search:{doc_type}")
        kb.button(text="🚛 Show Vehicles", callback_data=f"docs:{doc_type}:page:1")
        kb.button(text="⬅ Back", callback_data="documents")
        kb.adjust(1)

        await callback.message.edit_text(
            f"📂 {doc_type.replace('_',' ').title()} — choose an option:",
            reply_markup=kb.as_markup(),
            parse_mode=None
        )
        await callback.answer()
        return

    # docs:<doc_type>:page:<n>
    if len(parts) == 4 and parts[2] == "page":
        _, doc_type, _, page_str = parts
        page = int(page_str)

        async with samsara_service as service:
            vehicles = await service.get_vehicles(use_cache=True)

        kb = get_documents_vehicle_keyboard(vehicles, doc_type, page=page)
        await callback.message.edit_text(
            f"🚛 Choose a vehicle for {doc_type.replace('_',' ').title()} (page {page}):",
            reply_markup=kb,
            parse_mode=None
        )
        await callback.answer()
        return

    # docs:<doc_type>:truck:<id>
    if len(parts) == 4 and parts[2] == "truck":
        _, doc_type, _, truck = parts
        file_path = find_document(truck, doc_type)

        if file_path:
            await callback.message.answer_document(FSInputFile(file_path))
        else:
            await callback.message.answer(
                f"❌ No document found for truck {truck} in {doc_type.replace('_',' ').title()}.",
                reply_markup=documents_menu_kb()
            )
        await callback.answer()
        return


# 📄 Vehicle button → send document
@documents_router.callback_query(F.data.startswith("docs_vehicle:"))
async def send_vehicle_document(callback: CallbackQuery):
    _, doc_type, truck_number = callback.data.split(":")
    file_path = find_document(truck_number, doc_type)

    if file_path:
        await callback.message.answer_document(FSInputFile(file_path))
    else:
        await callback.message.answer(
            f"❌ No document found for truck {truck_number} in {doc_type.replace('_',' ').title()}.",
            reply_markup=documents_menu_kb()
        )


# 🔎 user clicks "Search Truck"
@documents_router.callback_query(F.data.startswith("docs_search:"))
async def ask_truck_number(callback: CallbackQuery, state: FSMContext):
    _, doc_type = callback.data.split(":")
    await state.update_data(doc_type=doc_type)
    await callback.message.answer(
        f"🔎 Enter truck number to search in {doc_type.replace('_',' ').title()}:\n\n❌ Send /cancel to stop."
    )
    await state.set_state(DocumentSearch.waiting_for_truck)
    await callback.answer()


# 🔎 user types truck number
@documents_router.message(StateFilter(DocumentSearch.waiting_for_truck))
async def search_truck_number(message: Message, state: FSMContext):
    data = await state.get_data()
    doc_type = data.get("doc_type")
    truck_number = message.text.strip()

    file_path = find_document(truck_number, doc_type)
    if file_path:
        await message.answer_document(FSInputFile(file_path))
    else:
        await message.answer(
            f"❌ No document found for truck *{truck_number}* in {doc_type.replace('_',' ').title()}.\n\n"
            "➡ Try again or go back to Documents menu.",
            reply_markup=documents_menu_kb(),
            parse_mode=None
        )

    await state.clear()


# ❌ Cancel search
@documents_router.message(F.text == "/cancel", StateFilter(DocumentSearch.waiting_for_truck))
async def cancel_search(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Search cancelled.", reply_markup=documents_menu_kb())


# helper to find documents
def find_document(truck: str, doc_type: str) -> str | None:
    folder = DOC_FOLDERS.get(doc_type)
    if not folder:
        return None

    folder_path = os.path.join(FILES_BASE, folder)
    if not os.path.exists(folder_path):
        return None

    for f in os.listdir(folder_path):
        if f.startswith(truck):
            return os.path.join(folder_path, f)
    return None
