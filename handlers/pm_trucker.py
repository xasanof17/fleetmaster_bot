# handlers/pm_trucker.py (FIXED WITH PAGINATION)
import asyncio
import contextlib
import os

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from keyboards.pm_trucker import (
    get_back_to_pm_keyboard,
    get_pm_trucker_menu,
    get_search_options_keyboard,
    get_vehicle_details_keyboard,
    get_vehicles_list_keyboard,
)
from services.google_ops_service import google_ops_service
from services.samsara_service import samsara_service
from utils.helpers import (
    build_live_location_message,
    build_static_location_message,
    format_vehicle_info,
    location_choice_keyboard,
)
from utils.logger import get_logger
from utils.logger_location import log_location_request

logger = get_logger(__name__)
router = Router()
LIVE_UPDATE_INTERVAL = 30
FILES_DIR = os.path.join(os.path.dirname(__file__), "..", "files", "registrations_2026")


# FSM for search
class VehicleSearchState(StatesGroup):
    waiting_for_query = State()


# ────────────────────────────────────────
# PM Trucker Main Menu
# ────────────────────────────────────────
@router.callback_query(lambda c: c.data == "pm_trucker")
async def show_pm_trucker(callback: CallbackQuery):
    """Show TRUCK INFORMATION main menu"""
    await callback.answer()
    logger.info(f"User {callback.from_user.id} accessed TRUCK INFORMATION")

    text = (
        "🚛 **TRUCK INFORMATION**\n\n"
        "Vehicle information and management system.\n\n"
        "**Available Options:**\n\n"
        "⚡️ **Statuses List** - View fleet status summary\n"
        "🚛 **View All Vehicles** - Browse your complete fleet\n"
        "🔍 **Search Vehicle** - Find vehicles by name, VIN, or plate\n"
        "🔄 **Refresh Data** - Get latest vehicle information\n\n"
        "Select an option to continue:"
    )

    try:
        await callback.message.edit_text(
            text, reply_markup=get_pm_trucker_menu(), parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error showing TRUCK INFORMATION menu: {e}")
        await callback.answer("❌ Error loading TRUCK INFORMATION")


# ────────────────────────────────────────
# View All Vehicles (FIXED WITH PROPER PAGINATION)
# ────────────────────────────────────────
@router.callback_query(
    lambda c: c.data == "pm_view_all_vehicles" or c.data.startswith("pm_vehicles_page:")
)
async def show_all_vehicles(callback: CallbackQuery):
    """Show all vehicles with pagination - 10 per page"""
    # Parse page number
    page = int(callback.data.split(":")[1]) if callback.data.startswith("pm_vehicles_page:") else 1

    await callback.answer("⚡ Loading vehicles...")

    try:
        async with samsara_service as service:
            vehicles = await service.get_vehicles(use_cache=True)

        if not vehicles:
            await callback.message.edit_text(
                "❌ **No Vehicles Found**\n\nPlease check your configuration and try again.",
                reply_markup=get_back_to_pm_keyboard(),
                parse_mode="Markdown",
            )
            return

        # Calculate pagination (10 per page)
        per_page = 10
        total_vehicles = len(vehicles)
        total_pages = (total_vehicles + per_page - 1) // per_page

        list_text = f"🚛 **Fleet Vehicles** (Page {page}/{total_pages})\n\n"
        list_text += f"Total vehicles: {total_vehicles}\n\n"
        list_text += "Select a vehicle to view details:"

        await callback.message.edit_text(
            text=list_text,
            reply_markup=get_vehicles_list_keyboard(vehicles, page=page, per_page=per_page),
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error fetching vehicles: {e}")
        await callback.message.edit_text(
            "❌ **Error Loading Vehicles**\n\nPlease check your connection and try again.",
            reply_markup=get_back_to_pm_keyboard(),
            parse_mode="Markdown",
        )


# ────────────────────────────────────────
# Show All Statuses (Google Sheet)
# ────────────────────────────────────────
@router.callback_query(lambda c: c.data == "pm_view_all_statuses")
async def show_all_statuses(callback: CallbackQuery):
    await callback.answer("📊 Loading OPS statuses…")
    try:
        text = await google_ops_service.as_markdown()
        await callback.message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error Loading OPS statuses: {e}")
        try:
            await callback.answer("❌ Error Loading OPS data", show_alert=True)
        except TelegramBadRequest:
            await callback.message.answer("❌ OPS status fetch failed.")


# ────────────────────────────────────────
# Vehicle Details
# ────────────────────────────────────────
@router.callback_query(lambda c: c.data.startswith("pm_vehicle_details:"))
async def show_vehicle_details(callback: CallbackQuery):
    vehicle_id = callback.data.split(":", 1)[1]
    await callback.answer("⚡ Loading vehicle details...")

    try:
        async with samsara_service as service:
            vehicle = await service.get_vehicle_with_stats(vehicle_id)

        if not vehicle:
            await callback.message.edit_text(
                "❌ **Vehicle Not Found**\n\nThe requested vehicle could not be found.",
                reply_markup=get_back_to_pm_keyboard(),
                parse_mode="Markdown",
            )
            return

        vehicle_info = await format_vehicle_info(vehicle)
        await callback.message.edit_text(
            text=vehicle_info,
            reply_markup=get_vehicle_details_keyboard(vehicle_id, vehicle.get("name")),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error showing vehicle details: {e}")
        await callback.message.edit_text(
            "❌ **Error Loading Vehicle Details**",
            reply_markup=get_back_to_pm_keyboard(),
            parse_mode="Markdown",
        )


# ────────────────────────────────────────
# Search Vehicles (FIXED WITH FSM)
# ────────────────────────────────────────
@router.callback_query(lambda c: c.data == "pm_search_vehicle")
async def search_vehicle_menu(callback: CallbackQuery):
    text = (
        "🔍 **Search Vehicles**\n\n"
        "Choose how you want to search for vehicles:\n\n"
        "🏷️ **By Name**\n🔢 **By VIN**\n🚗 **By Plate**\n🔎 **All Fields**"
    )
    await callback.message.edit_text(
        text, reply_markup=get_search_options_keyboard(), parse_mode="Markdown"
    )


@router.callback_query(lambda c: c.data.startswith("pm_search_by:"))
async def start_vehicle_search(callback: CallbackQuery, state: FSMContext):
    """Start vehicle search by type"""
    search_type = callback.data.split(":", 1)[1]
    await state.update_data(search_type=search_type)
    await state.set_state(VehicleSearchState.waiting_for_query)

    prompts = {
        "name": "🏷️ **Search by Name**\nEnter vehicle name (or part):",
        "vin": "🔢 **Search by VIN**\nEnter VIN (or part):",
        "plate": "🚗 **Search by Plate**\nEnter plate (or part):",
        "all": "🔎 **Search all fields**\nEnter text to search:",
    }
    text = prompts.get(search_type, "Enter search query:")
    text += "\n\n❌ Send /cancel to stop."

    try:
        await callback.message.edit_text(text=text, parse_mode="Markdown")
        await callback.answer("🔍 Enter query")
    except TelegramBadRequest as e:
        logger.error(f"BadRequest when starting search: {e}")
        await callback.answer("❌ Error starting search")


@router.message(VehicleSearchState.waiting_for_query, F.text)
async def process_vehicle_search(message: Message, state: FSMContext):
    query = message.text.strip().lower()

    if len(query) < 2:
        await message.reply("Please enter at least 2 characters for search.")
        return

    data = await state.get_data()
    search_type = data.get("search_type", "all")

    searching = await message.reply("🔍 Searching...")

    try:
        # -----------------------------------------
        # ⚡ FAST SEARCH (CACHE ONLY)
        # -----------------------------------------
        async with samsara_service as svc:
            vehicles = await svc.get_vehicles(use_cache=True)

        def fast_match(v):
            name = (v.get("name") or "").lower()
            vin = (v.get("vin") or "").lower()
            plate = (v.get("licensePlate") or "").lower()

            if search_type == "name":
                return query in name
            if search_type == "vin":
                return query in vin
            if search_type == "plate":
                return query in plate

            return query in name or query in vin or query in plate

        fast_results = [v for v in vehicles if fast_match(v)]

        if fast_results:
            await searching.edit_text(
                text=f"⚡ **Fast results for '{query}'**:",
                reply_markup=get_vehicles_list_keyboard(fast_results[:50], page=1, per_page=10),
                parse_mode="Markdown",
            )
            return

        # -----------------------------------------
        # 🐢 FALLBACK: API SEARCH
        # -----------------------------------------
        async with samsara_service as svc:
            results = await svc.search_vehicles(query, search_type)

        if not results:
            await searching.edit_text(
                text=f"❌ No results for '{query}'",
                reply_markup=get_back_to_pm_keyboard(),
                parse_mode="Markdown",
            )
            return

        await searching.edit_text(
            text=f"🎯 Found {len(results)} result(s) for '{query}':",
            reply_markup=get_vehicles_list_keyboard(results, page=1, per_page=10),
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        await searching.edit_text(
            "❌ Search failed. Try again later.",
            reply_markup=get_back_to_pm_keyboard(),
            parse_mode="Markdown",
        )


@router.message(VehicleSearchState.waiting_for_query, F.text == "/cancel")
async def cancel_vehicle_search(message: Message, state: FSMContext):
    """Cancel vehicle search"""
    await state.clear()
    await message.reply(
        "❌ Search cancelled", reply_markup=get_back_to_pm_keyboard(), parse_mode="Markdown"
    )


# ────────────────────────────────────────
# Refresh Cache
# ────────────────────────────────────────
@router.callback_query(lambda c: c.data == "pm_refresh_cache")
async def refresh_cache(callback: CallbackQuery):
    await callback.answer("🔄 Refreshing data...")
    try:
        async with samsara_service as service:
            service.clear_cache()
            vehicles = await service.get_vehicles(use_cache=False)

        await callback.message.edit_text(
            f"🚛 **TRUCK INFORMATION**\n\n✅ **Data Refreshed!** Updated {len(vehicles)} vehicles.",
            reply_markup=get_pm_trucker_menu(),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error refreshing cache: {e}")
        await callback.answer("❌ Error refreshing data")


# ────────────────────────────────────────
# Location Handlers
# ────────────────────────────────────────
@router.callback_query(F.data.startswith("pm_vehicle_location:"))
async def show_location_choice(callback: CallbackQuery):
    """Show static/live location choice"""
    vehicle_id = callback.data.split(":", 1)[1]
    await callback.message.answer(
        "📍 **Choose Location Type**\n\n"
        "🗺 **Static** - One-time location\n"
        "📡 **Live** - Updates every 30 seconds for 5 minutes",
        reply_markup=location_choice_keyboard(vehicle_id),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("loc_static:"))
async def handle_static(callback: CallbackQuery):
    await callback.answer()
    vehicle_id = callback.data.split(":", 1)[1]
    await callback.message.delete()

    try:
        async with samsara_service as service:
            vehicle = await service.get_vehicle_by_id(vehicle_id)
            location = await service.get_vehicle_location(vehicle_id)

        if not vehicle or not location:
            await callback.message.answer("⚠️ Could not fetch vehicle/location data.")
            return

        lat, lon = location["latitude"], location["longitude"]
        await callback.message.answer_location(latitude=lat, longitude=lon)

        msg, _ = build_static_location_message(vehicle, location)
        await callback.message.answer(msg, parse_mode="Markdown")

        log_location_request(callback.from_user.id, vehicle_id, "static", location.get("address"))
    except Exception as e:
        logger.error(f"Error static location: {e}")
        await callback.message.answer("❌ Error fetching/sending location.")


@router.callback_query(F.data.startswith("loc_live:"))
async def handle_live(callback: CallbackQuery):
    await callback.answer()
    vehicle_id = callback.data.split(":", 1)[1]
    await callback.message.delete()

    try:
        async with samsara_service as service:
            vehicle = await service.get_vehicle_by_id(vehicle_id)
            location = await service.get_vehicle_location(vehicle_id)

        if not location:
            await callback.message.answer("⚠️ Location unavailable.")
            return

        lat, lon = location["latitude"], location["longitude"]
        live_msg = await callback.message.answer_location(
            latitude=lat, longitude=lon, live_period=300
        )
        msg, _ = build_live_location_message(vehicle, location)
        await callback.message.answer(msg, parse_mode="Markdown")

        async def updater():
            try:
                for _ in range(300 // LIVE_UPDATE_INTERVAL):
                    await asyncio.sleep(LIVE_UPDATE_INTERVAL)
                    async with samsara_service as service:
                        new_loc = await service.get_vehicle_location(vehicle_id)
                    if not new_loc:
                        continue
                    await callback.bot.edit_message_live_location(
                        chat_id=callback.message.chat.id,
                        message_id=live_msg.message_id,
                        latitude=new_loc["latitude"],
                        longitude=new_loc["longitude"],
                    )
            except Exception as e:
                logger.error(f"Live update error: {e}")
            finally:
                with contextlib.suppress(Exception):
                    await callback.bot.stop_message_live_location(
                        chat_id=callback.message.chat.id, message_id=live_msg.message_id
                    )

        asyncio.create_task(updater())
    except Exception as e:
        logger.error(f"Live location error: {e}")
        await callback.message.answer("❌ Error sending live location")


# ────────────────────────────────────────
# Registration File Handler
# ────────────────────────────────────────
@router.callback_query(F.data.startswith("pm_vehicle_reg:"))
async def handle_registration_file(callback: CallbackQuery):
    vehicle_name = callback.data.split(":", 1)[1]
    logger.info(f"User {callback.from_user.id} requested registration file for {vehicle_name}")
    await callback.answer()

    try:
        if not os.path.exists(FILES_DIR):
            # await callback.message.answer(f"❌ Registration files directory not found.")
            await callback.message.answer(
                "COMING SOON: Driver Information feature is under development."
            )
            return

        files = [f for f in os.listdir(FILES_DIR) if f.lower().endswith(".pdf")]
        found = next(
            (os.path.join(FILES_DIR, f) for f in files if vehicle_name.lower() in f.lower()), None
        )

        if not found:
            # await callback.message.answer(f"❌ No registration file found for **{vehicle_name}**.")
            await callback.message.answer(
                "COMING SOON: Driver Information feature is under development."
            )
            return

        # await callback.message.answer_document(
        #     document=FSInputFile(found), caption=f"📄 Registration File for {vehicle_name}"
        # )
        await callback.message.answer(
            "COMING SOON: Driver Information feature is under development."
        )
        # logger.info(f"Sent registration file {found}")
    except Exception as e:
        logger.error(f"Error sending registration file: {e}")
        await callback.message.answer("❌ Error sending registration file.")


# ────────────────────────────────────────
# Handle page info callback (no-op)
# ────────────────────────────────────────
@router.callback_query(F.data == "pm_page_info")
async def handle_page_info(callback: CallbackQuery):
    """Handle page info button (does nothing)"""
    await callback.answer()
