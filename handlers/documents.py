"""
handlers/documents.py
Document management and access — ADMIN-ONLY SEND TO GROUP (per truck, DB-mapped)
"""

import os
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.documents import (
    documents_menu_kb,
    get_documents_vehicle_keyboard,
    get_send_group_keyboard,
)
from services.samsara_service import samsara_service
from services.group_map import get_group_id_for_unit
from config import settings
from utils.logger import get_logger

# ─────────────────────────────────────────────
logger = get_logger(__name__)
router = Router()

FILES_BASE = settings.FILES_BASE
ADMINS = set(map(int, settings.ADMINS)) if getattr(settings, "ADMINS", None) else set()

DOC_FOLDERS = {
    "registrations_2026": "registrations_2026",
    "new_mexico": "new_mexico",
    "lease": "lease_agreements",
    "inspection_2025": "annual_inspection",
}


class DocumentSearch(StatesGroup):
    waiting_for_truck = State()


# ─────────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────────
@router.callback_query(F.data == "documents")
async def show_documents_menu(cb: CallbackQuery):
    """Show main documents menu"""
    await cb.answer()
    doc_intro = (
        "📂 *DOCUMENTS — Fleet & Compliance Files*\n\n"
        "Access all key documents:\n"
        "• Vehicle Registrations 2026\n"
        "• New Mexico Permits\n"
        "• Lease Agreements\n"
        "• Annual Inspections 2025\n\n"
        "Select a category below 👇"
    )
    await cb.message.edit_text(doc_intro, reply_markup=documents_menu_kb(), parse_mode="Markdown")


# ─────────────────────────────────────────────
# DOCUMENT NAVIGATION
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("docs:"))
async def documents_flow(cb: CallbackQuery):
    """Handle navigation inside document categories"""
    parts = cb.data.split(":")

    # docs:<doc_type>
    if len(parts) == 2:
        _, doc_type = parts
        doc_title = doc_type.replace("_", " ").title()

        kb = InlineKeyboardBuilder()
        kb.button(text="🔍 Search by Truck Unit", callback_data=f"docs_search:{doc_type}")
        kb.button(text="🚛 Browse All Vehicles", callback_data=f"docs:{doc_type}:page:1")
        kb.button(text="🔙 Back to Documents", callback_data="documents")
        kb.adjust(1)

        await cb.message.edit_text(
            f"📄 *{doc_title}*\n\nChoose how to find your document:",
            reply_markup=kb.as_markup(),
            parse_mode="Markdown",
        )
        await cb.answer()
        return

    # docs:<doc_type>:page:<n>
    if len(parts) == 4 and parts[2] == "page":
        _, doc_type, _, page_str = parts
        page = int(page_str)

        try:
            async with samsara_service as service:
                vehicles = await service.get_vehicles(use_cache=True)

            if not vehicles:
                await cb.message.edit_text(
                    "❌ No vehicles found in system.",
                    reply_markup=documents_menu_kb(),
                    parse_mode="Markdown",
                )
                await cb.answer()
                return

            kb = get_documents_vehicle_keyboard(vehicles, doc_type, page=page)
            await cb.message.edit_text(
                f"🚛 *{doc_type.replace('_',' ').title()}*\n\nSelect a vehicle:",
                reply_markup=kb,
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.error(f"Error loading vehicles: {e}")
            await cb.answer("❌ Error loading vehicles", show_alert=True)
        return

    # docs:<doc_type>:truck:<unit>
    if len(parts) == 4 and parts[2] == "truck":
        _, doc_type, _, truck = parts
        await send_document_file(cb, truck, doc_type)
        await cb.answer()
        return


# ─────────────────────────────────────────────
# SEND DOCUMENT FILE
# ─────────────────────────────────────────────
async def send_document_file(cb: CallbackQuery, truck_number: str, doc_type: str):
    """Send the document; only admins see Send Group button"""
    try:
        file_path = find_document(truck_number, doc_type)
        if not file_path:
            await cb.message.answer(
                f"❌ No document found for *Truck {truck_number}*.",
                reply_markup=documents_menu_kb(),
                parse_mode="Markdown",
            )
            return

        caption = f"📄 *Truck {truck_number}* — {doc_type.replace('_',' ').title()}"
        markup = get_send_group_keyboard(truck_number) if cb.from_user.id in ADMINS else None

        await cb.message.answer_document(
            FSInputFile(file_path),
            caption=caption,
            parse_mode="Markdown",
            reply_markup=markup,
        )
        logger.info(f"Sent document for truck {truck_number} ({doc_type})")

    except Exception as e:
        logger.error(f"Error sending document {truck_number}: {e}")
        await cb.answer("❌ Error sending document", show_alert=True)


# ─────────────────────────────────────────────
# ADMIN: SEND FILE TO MAPPED GROUP
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("send_group:"))
async def handle_send_group(cb: CallbackQuery):
    """Admin-only: send this truck's file to its mapped group"""
    if cb.from_user.id not in ADMINS:
        await cb.answer("🚫 Only admins can send to groups.", show_alert=True)
        return

    truck_unit = cb.data.split(":")[1]
    try:
        group_id = await get_group_id_for_unit(truck_unit)
        if not group_id:
            await cb.answer(f"❌ No group mapped for Truck {truck_unit}", show_alert=True)
            return

        # Find document for this truck (any folder)
        for doc_type in DOC_FOLDERS:
            file_path = find_document(truck_unit, doc_type)
            if file_path:
                caption = (
                    f"📎 *Shared from Bot*\n"
                    f"🚛 Truck: *{truck_unit}*\n"
                    f"📄 {doc_type.replace('_',' ').title()}"
                )
                await cb.bot.send_document(
                    chat_id=int(group_id),
                    document=FSInputFile(file_path),
                    caption=caption,
                    parse_mode="Markdown",
                )
                await cb.answer("✅ File sent to group!")
                logger.info(f"Document for Truck {truck_unit} sent to group {group_id}")
                return

        await cb.answer("❌ No file found for this truck.", show_alert=True)

    except Exception as e:
        logger.error(f"Error sending document to group: {e}")
        await cb.answer("❌ Error sending file to group.", show_alert=True)


# ─────────────────────────────────────────────
# SEARCH TRUCK FLOW
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("docs_search:"))
async def ask_truck_number(cb: CallbackQuery, state: FSMContext):
    """Start document search by truck number"""
    _, doc_type = cb.data.split(":")
    await state.update_data(doc_type=doc_type)
    await cb.message.answer(
        f"🔎 **Search {doc_type.replace('_',' ').title()}**\n\n"
        "Enter truck number (e.g. 5071):\n\n"
        "Send /cancel to stop.",
        parse_mode="Markdown",
    )
    await state.set_state(DocumentSearch.waiting_for_truck)
    await cb.answer()


@router.message(StateFilter(DocumentSearch.waiting_for_truck), F.text)
async def search_truck_number(msg: Message, state: FSMContext):
    """Process truck number search"""
    data = await state.get_data()
    doc_type = data.get("doc_type")
    truck_number = msg.text.strip().lstrip("/")

    try:
        file_path = find_document(truck_number, doc_type)
        if not file_path:
            await msg.answer(f"❌ No document found for *Truck {truck_number}*", parse_mode="Markdown")
            return

        caption = f"📄 **Truck {truck_number}** — {doc_type.replace('_',' ').title()}"
        markup = get_send_group_keyboard(truck_number) if msg.from_user.id in ADMINS else None

        await msg.answer_document(
            FSInputFile(file_path),
            caption=caption,
            parse_mode="Markdown",
            reply_markup=markup,
        )
        logger.info(f"Search: Sent document for truck {truck_number}")

    except Exception as e:
        logger.error(f"Error searching document {truck_number}: {e}")
        await msg.answer("❌ Error searching document.", parse_mode="Markdown")
    finally:
        await state.clear()


@router.message(F.text == "/cancel", StateFilter(DocumentSearch.waiting_for_truck))
async def cancel_search(msg: Message, state: FSMContext):
    """Cancel document search"""
    await state.clear()
    await msg.answer("❌ Search cancelled.", reply_markup=documents_menu_kb())


# ─────────────────────────────────────────────
# FILE LOCATOR
# ─────────────────────────────────────────────
def find_document(truck: str, doc_type: str) -> str | None:
    """Locate a PDF document for the given truck & doc type"""
    folder = DOC_FOLDERS.get(doc_type)
    if not folder:
        return None

    folder_path = os.path.join(FILES_BASE, folder)
    if not os.path.exists(folder_path):
        return None

    try:
        for filename in os.listdir(folder_path):
            if filename.startswith(truck) and filename.lower().endswith(".pdf"):
                return os.path.join(folder_path, filename)
    except Exception as e:
        logger.error(f"Error scanning {folder_path}: {e}")
    return None
