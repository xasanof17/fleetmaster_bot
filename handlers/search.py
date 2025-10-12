"""
Search handlers using FSM for query input
FIXED: Corrected imports and removed duplicate functionality
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from keyboards.pm_trucker import get_vehicles_list_keyboard, get_back_to_pm_keyboard
from services.samsara_service import samsara_service
from utils.logger import get_logger

logger = get_logger("handlers.search")
router = Router()


class SearchStates(StatesGroup):
    waiting_for_query = State()


@router.callback_query(lambda c: c.data.startswith("pm_search_by:"))
async def start_search(callback: CallbackQuery, state: FSMContext):
    search_type = callback.data.split(":", 1)[1]
    await state.update_data(search_type=search_type)
    await state.set_state(SearchStates.waiting_for_query)

    prompts = {
        "name": "🏷️ Search by Name\nEnter vehicle name (or part):",
        "vin": "🔢 Search by VIN\nEnter VIN (or part):",
        "plate": "🚗 Search by Plate\nEnter plate (or part):",
        "all": "🔎 Search all fields\nEnter text to search:"
    }
    text = prompts.get(search_type, "Enter search query:")
    text += "\n\n❌ Send /cancel to stop."
    try:
        await callback.message.edit_text(text=text, parse_mode="Markdown")
        await callback.answer("🔍 Enter query")
    except TelegramBadRequest as e:
        logger.error(f"BadRequest when starting search: {e}")
        await callback.answer("❌ Error starting search")


@router.message(SearchStates.waiting_for_query, F.text)
async def process_search(message: Message, state: FSMContext):
    query = message.text.strip()
    if not query or len(query) < 2:
        await message.reply("Please enter at least 2 characters for search.")
        return
    data = await state.get_data()
    search_type = data.get("search_type", "all")
    searching = await message.reply("🔍 Searching...")

    try:
        async with samsara_service as svc:
            results = await svc.search_vehicles(query, search_type)
        if not results:
            await searching.edit_text(
                text=f"❌ No results for '{query}'", 
                reply_markup=get_back_to_pm_keyboard(), 
                parse_mode="Markdown"
            )
        else:
            text = f"🎯 Found {len(results)} result(s) for '{query}':"
            await searching.edit_text(
                text=text, 
                reply_markup=get_vehicles_list_keyboard(results, page=1, per_page=10), 
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Search error: {e}")
        try:
            await searching.edit_text(
                text="❌ Search failed. Try again later.", 
                reply_markup=get_back_to_pm_keyboard(), 
                parse_mode="Markdown"
            )
        except:
            await message.reply("❌ Search failed.")
    finally:
        await state.clear()


@router.callback_query(lambda c: c.data.startswith("pm_search_page:"))
async def search_page(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("❌ Invalid page request")
        return
    _, search_type, search_query, page_str = parts
    try:
        page = int(page_str)
    except Exception:
        await callback.answer("❌ Invalid page")
        return
    await callback.answer("⚡ Loading page...")
    try:
        async with samsara_service as svc:
            results = await svc.search_vehicles(search_query, search_type)
        if not results:
            await callback.answer("❌ No results")
            return
        await callback.message.edit_text(
            text=f"🎯 Results for '{search_query}'", 
            reply_markup=get_vehicles_list_keyboard(results, page=page, per_page=10), 
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Search page error: {e}")
        await callback.answer("❌ Error loading page")


@router.message(SearchStates.waiting_for_query, F.text == "/cancel")
async def cancel_search(message: Message, state: FSMContext):
    await state.clear()
    await message.reply(
        "❌ Search cancelled", 
        reply_markup=get_back_to_pm_keyboard(), 
        parse_mode="Markdown"
    )