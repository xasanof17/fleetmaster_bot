"""
handlers/documents.py
Document management and access - FIXED & IMPROVED
"""
import os
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.documents import documents_menu_kb, get_documents_vehicle_keyboard
from services.samsara_service import samsara_service
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)
router = Router()

FILES_BASE = settings.FILES_BASE

DOC_FOLDERS = {
    "registrations_2026": "registrations_2026",
    "new_mexico": "new_mexico",
    "lease": "lease_agreements",
    "inspection_2025": "annual_inspection",
}


class DocumentSearch(StatesGroup):
    waiting_for_truck = State()


# 📂 Entry point
@router.callback_query(F.data == "documents")
async def show_documents_menu(callback: CallbackQuery):
    """Show main documents menu"""
    await callback.answer()
    
    doc_intro = (
        "📂 **DOCUMENTS** — Fleet & Compliance Files\n\n"
        "Access key paperwork in one place:\n"
        "• Registrations and state permits\n"
        "• Lease agreements and annual inspections\n\n"
        "Select a document category below to view or download:"
    )
    
    try:
        await callback.message.edit_text(
            doc_intro,
            reply_markup=documents_menu_kb(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error showing documents menu: {e}")
        await callback.answer("❌ Error loading documents menu")


# 📂 Document type chosen
@router.callback_query(F.data.startswith("docs:"))
async def documents_flow(callback: CallbackQuery):
    """Handle document category selection and navigation"""
    parts = callback.data.split(":")

    # docs:<doc_type>
    if len(parts) == 2:
        _, doc_type = parts
        
        doc_names = {
            "registrations_2026": "Vehicle Registrations 2026",
            "new_mexico": "New Mexico Permits",
            "lease": "Lease Agreements",
            "inspection_2025": "Annual Inspections 2025"
        }
        
        doc_title = doc_names.get(doc_type, doc_type.replace('_', ' ').title())

        kb = InlineKeyboardBuilder()
        kb.button(text="🏷️ Search by Truck Number", callback_data=f"docs_search:{doc_type}")
        kb.button(text="🚛 Browse All Vehicles", callback_data=f"docs:{doc_type}:page:1")
        kb.button(text="🔙 Back to Documents", callback_data="documents")
        kb.adjust(1)

        await callback.message.edit_text(
            f"📂 **{doc_title}**\n\nChoose how to find your document:",
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    # docs:<doc_type>:page:<n>
    if len(parts) == 4 and parts[2] == "page":
        _, doc_type, _, page_str = parts
        page = int(page_str)

        try:
            async with samsara_service as service:
                vehicles = await service.get_vehicles(use_cache=True)

            if not vehicles:
                await callback.message.edit_text(
                    "❌ No vehicles found in system.",
                    reply_markup=documents_menu_kb(),
                    parse_mode="Markdown"
                )
                await callback.answer()
                return

            kb = get_documents_vehicle_keyboard(vehicles, doc_type, page=page)
            
            doc_names = {
                "registrations_2026": "Vehicle Registrations 2026",
                "new_mexico": "New Mexico Permits",
                "lease": "Lease Agreements",
                "inspection_2025": "Annual Inspections 2025"
            }
            
            doc_title = doc_names.get(doc_type, doc_type.replace('_', ' ').title())
            
            await callback.message.edit_text(
                f"🚛 **{doc_title}**\n\nPage {page} - Select a vehicle:",
                reply_markup=kb,
                parse_mode="Markdown"
            )
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Error loading vehicles for documents: {e}")
            await callback.answer("❌ Error loading vehicles", show_alert=True)
        return

    # docs:<doc_type>:truck:<id>
    if len(parts) == 4 and parts[2] == "truck":
        _, doc_type, _, truck = parts
        await send_document_file(callback, truck, doc_type)
        await callback.answer()
        return


# 📄 Vehicle button → send document
@router.callback_query(F.data.startswith("docs_vehicle:"))
async def send_vehicle_document(callback: CallbackQuery):
    """Send document for selected vehicle"""
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ Invalid request", show_alert=True)
        return
    
    _, doc_type, truck_number = parts
    await send_document_file(callback, truck_number, doc_type)


async def send_document_file(callback: CallbackQuery, truck_number: str, doc_type: str):
    """Helper to send document file"""
    try:
        file_path = find_document(truck_number, doc_type)

        if file_path:
            doc_names = {
                "registrations_2026": "Registration 2026",
                "new_mexico": "NM Permit",
                "lease": "Lease Agreement",
                "inspection_2025": "Inspection 2025"
            }
            
            doc_name = doc_names.get(doc_type, doc_type.replace('_', ' ').title())
            caption = f"📄 **Truck {truck_number}** - {doc_name}"
            
            await callback.message.answer_document(
                FSInputFile(file_path),
                caption=caption,
                parse_mode="Markdown"
            )
            logger.info(f"Sent document for truck {truck_number} ({doc_type})")
        else:
            doc_names = {
                "registrations_2026": "Vehicle Registrations 2026",
                "new_mexico": "New Mexico Permits",
                "lease": "Lease Agreements",
                "inspection_2025": "Annual Inspections 2025"
            }
            
            doc_title = doc_names.get(doc_type, doc_type.replace('_', ' ').title())
            
            await callback.message.answer(
                f"❌ No document found for **Truck {truck_number}** in {doc_title}.",
                reply_markup=documents_menu_kb(),
                parse_mode="Markdown"
            )
            logger.warning(f"Document not found for truck {truck_number} in {doc_type}")
            
    except Exception as e:
        logger.error(f"Error sending document for truck {truck_number}: {e}")
        await callback.message.answer(
            "❌ Error sending document. Please try again.",
            reply_markup=documents_menu_kb()
        )


# 🔎 User clicks "Search Truck"
@router.callback_query(F.data.startswith("docs_search:"))
async def ask_truck_number(callback: CallbackQuery, state: FSMContext):
    """Start document search by truck number"""
    _, doc_type = callback.data.split(":")
    await state.update_data(doc_type=doc_type)
    
    doc_names = {
        "registrations_2026": "Vehicle Registrations 2026",
        "new_mexico": "New Mexico Permits",
        "lease": "Lease Agreements",
        "inspection_2025": "Annual Inspections 2025"
    }
    
    doc_title = doc_names.get(doc_type, doc_type.replace('_', ' ').title())
    
    await callback.message.answer(
        f"🔎 **Search {doc_title}**\n\n"
        f"Enter truck number (e.g. 5071, 5096):\n\n"
        f"❌ Send /cancel to stop.",
        parse_mode="Markdown"
    )
    await state.set_state(DocumentSearch.waiting_for_truck)
    await callback.answer()


# 🔎 User types truck number
@router.message(StateFilter(DocumentSearch.waiting_for_truck), F.text)
async def search_truck_number(message: Message, state: FSMContext):
    """Process truck number search"""
    data = await state.get_data()
    doc_type = data.get("doc_type")
    truck_number = message.text.strip().lstrip("/")  # Remove / if user types /5071

    try:
        file_path = find_document(truck_number, doc_type)
        
        if file_path:
            doc_names = {
                "registrations_2026": "Registration 2026",
                "new_mexico": "NM Permit",
                "lease": "Lease Agreement",
                "inspection_2025": "Inspection 2025"
            }
            
            doc_name = doc_names.get(doc_type, doc_type.replace('_', ' ').title())
            caption = f"📄 **Truck {truck_number}** - {doc_name}"
            
            await message.answer_document(
                FSInputFile(file_path),
                caption=caption,
                parse_mode="Markdown"
            )
            logger.info(f"Search: Sent document for truck {truck_number} ({doc_type})")
        else:
            doc_names = {
                "registrations_2026": "Vehicle Registrations 2026",
                "new_mexico": "New Mexico Permits",
                "lease": "Lease Agreements",
                "inspection_2025": "Annual Inspections 2025"
            }
            
            doc_title = doc_names.get(doc_type, doc_type.replace('_', ' ').title())
            
            await message.answer(
                f"❌ No document found for **Truck {truck_number}** in {doc_title}.\n\n"
                f"💡 Try another truck number or browse all vehicles.",
                reply_markup=documents_menu_kb(),
                parse_mode="Markdown"
            )
            logger.warning(f"Search: Document not found for truck {truck_number} in {doc_type}")

    except Exception as e:
        logger.error(f"Error searching document for truck {truck_number}: {e}")
        await message.answer(
            "❌ Error searching document. Please try again.",
            reply_markup=documents_menu_kb()
        )
    finally:
        await state.clear()


# ❌ Cancel search
@router.message(F.text == "/cancel", StateFilter(DocumentSearch.waiting_for_truck))
async def cancel_search(message: Message, state: FSMContext):
    """Cancel document search"""
    await state.clear()
    await message.answer(
        "❌ Search cancelled.",
        reply_markup=documents_menu_kb()
    )


# Helper to find documents
def find_document(truck: str, doc_type: str) -> str | None:
    """
    Find document file for a truck in specified category
    
    Args:
        truck: Truck number (e.g. "5071")
        doc_type: Document category (e.g. "registrations_2026")
    
    Returns:
        Full path to document file if found, None otherwise
    """
    folder = DOC_FOLDERS.get(doc_type)
    if not folder:
        logger.warning(f"Unknown document type: {doc_type}")
        return None

    folder_path = os.path.join(FILES_BASE, folder)
    
    if not os.path.exists(folder_path):
        logger.warning(f"Document folder not found: {folder_path}")
        return None

    try:
        # Look for files starting with truck number
        for filename in os.listdir(folder_path):
            if filename.startswith(truck) and filename.lower().endswith('.pdf'):
                file_path = os.path.join(folder_path, filename)
                logger.debug(f"Found document: {file_path}")
                return file_path
        
        logger.debug(f"No document found for truck {truck} in {folder_path}")
        return None
        
    except Exception as e:
        logger.error(f"Error searching for document: {e}")
        return None