import asyncio
import os
from config.settings import settings
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.exceptions import TelegramBadRequest
from services.group_map import get_group_id_for_unit  # ✅ replaced TRUCK_GROUPS
from services.samsara_service import samsara_service
from services.google_ops_service import google_ops_service
from services.google_service import google_pm_service
from keyboards.pm_trucker import (
    get_pm_trucker_menu,
    get_vehicle_details_keyboard,
    get_search_options_keyboard,
    get_vehicles_list_keyboard,
    get_back_to_pm_keyboard
)
from utils.helpers import (
    format_vehicle_info,
    format_vehicle_list,
    location_choice_keyboard,
    build_static_location_message,
    build_live_location_message,
)
from utils.logger_location import log_location_request
from utils.logger import get_logger
from utils.pm_formatter import format_pm_vehicle_info

logger = get_logger(__name__)
router = Router()
LIVE_UPDATE_INTERVAL = 30
FILES_DIR = os.path.join(os.path.dirname(__file__), "..", "files", "registrations_2026")

# ────────────────────────────────
# PM Trucker Main Menu
# ────────────────────────────────
@router.callback_query(lambda c: c.data == "pm_trucker")
async def show_pm_trucker(callback: CallbackQuery):
    """Show TRUCK INFORMATION main menu"""
    await callback.answer()
    logger.info(f"User {callback.from_user.id} accessed TRUCK INFORMATION")

    text = (
        "🚛 **TRUCK INFORMATION**\n\n"
        "Vehicle information and management system.\n\n"
        "**Available Options:**\n\n"
        "🚛 **View All Vehicles** - Browse your complete fleet\n"
        "🔍 **Search Vehicle** - Find vehicles by name, VIN, or plate\n"
        "🔄 **Refresh Data** - Get latest vehicle information\n\n"
        "Select an option to continue:"
    )

    try:
        await callback.message.edit_text(text, reply_markup=get_pm_trucker_menu(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error showing TRUCK INFORMATION menu: {e}")
        await callback.answer("❌ Error loading TRUCK INFORMATION")


# ────────────────────────────────
# View All Vehicles
# ────────────────────────────────
@router.callback_query(lambda c: c.data == "pm_view_all_vehicles")
async def show_all_vehicles(callback: CallbackQuery):
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

        list_text = format_vehicle_list(vehicles)
        await callback.message.edit_text(
            text=list_text, reply_markup=get_vehicles_list_keyboard(vehicles), parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error fetching vehicles: {e}")
        await callback.message.edit_text(
            "❌ **Error Loading Vehicles**\n\nPlease check your connection and try again.",
            reply_markup=get_back_to_pm_keyboard(),
            parse_mode="Markdown",
        )


# ────────────────────────────────
# Show All Statuses (Google Sheet)
# ────────────────────────────────
@router.callback_query(lambda c: c.data == "pm_view_all_statuses")
async def show_all_statuses(callback: CallbackQuery):
    await callback.answer("⏳ Fetching statuses…")
    try:
        text = await google_ops_service.as_markdown()
        await callback.message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error fetching ops statuses: {e}")
        await callback.message.answer("❌ Error fetching status list.")


# ────────────────────────────────
# Pagination
# ────────────────────────────────
@router.callback_query(lambda c: c.data.startswith("pm_vehicles_page:"))
async def show_vehicles_page(callback: CallbackQuery):
    await callback.answer("⚡ Loading page...")
    try:
        page = int(callback.data.split(":")[1])
        async with samsara_service as service:
            vehicles = await service.get_vehicles(use_cache=True)

        list_text = format_vehicle_list(vehicles)
        await callback.message.edit_text(
            text=list_text, reply_markup=get_vehicles_list_keyboard(vehicles, page=page), parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error showing vehicles page: {e}")
        await callback.answer("❌ Error loading page")


# ────────────────────────────────
# Vehicle Details
# ────────────────────────────────
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
            "❌ **Error Loading Vehicle Details**", reply_markup=get_back_to_pm_keyboard(), parse_mode="Markdown"
        )


# ────────────────────────────────
# Search Vehicles
# ────────────────────────────────
@router.callback_query(lambda c: c.data == "pm_search_vehicle")
async def search_vehicle(callback: CallbackQuery):
    text = (
        "🔍 **Search Vehicles**\n\n"
        "Choose how you want to search for vehicles:\n\n"
        "🏷️ **By Name**\n🔢 **By VIN**\n🚗 **By Plate**\n🔍 **All Fields**"
    )
    await callback.message.edit_text(text, reply_markup=get_search_options_keyboard(), parse_mode="Markdown")


# ────────────────────────────────
# Refresh Cache
# ────────────────────────────────
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


# ────────────────────────────────
# Location Handlers
# ────────────────────────────────
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
        live_msg = await callback.message.answer_location(latitude=lat, longitude=lon, live_period=300)
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
                try:
                    await callback.bot.stop_message_live_location(
                        chat_id=callback.message.chat.id, message_id=live_msg.message_id
                    )
                except Exception:
                    pass

        asyncio.create_task(updater())
    except Exception as e:
        logger.error(f"Live location error: {e}")
        await callback.message.answer("❌ Error sending live location")


# ────────────────────────────────
# Registration File Handler
# ────────────────────────────────
@router.callback_query(F.data.startswith("pm_vehicle_reg:"))
async def handle_registration_file(callback: CallbackQuery):
    vehicle_name = callback.data.split(":", 1)[1]
    logger.info(f"User {callback.from_user.id} requested registration file for {vehicle_name}")
    await callback.answer()

    try:
        files = [f for f in os.listdir(FILES_DIR) if f.lower().endswith(".pdf")]
        found = next((os.path.join(FILES_DIR, f) for f in files if vehicle_name.lower() in f.lower()), None)

        if not found:
            await callback.message.answer(f"❌ No registration file found for **{vehicle_name}**.")
            return

        await callback.message.answer_document(
            document=FSInputFile(found), caption=f"📄 Registration File for {vehicle_name}"
        )
        logger.info(f"Sent registration file {found}")
    except Exception as e:
        logger.error(f"Error sending registration file: {e}")
        await callback.message.answer("❌ Error sending registration file.")


# ────────────────────────────────
# Send PM Info to Group (DB)
# ────────────────────────────────
@router.callback_query(F.data.startswith("pm_send_group:"))
async def auto_send_to_group(cb: CallbackQuery):
    """Send truck PM info to its linked group from DB."""
    try:
        unit = cb.data.split(":", 1)[1].strip()
        group_id = await get_group_id_for_unit(unit)

        if not group_id:
            await cb.answer(f"🚫 No group found for truck {unit}", show_alert=True)
            return

        details = await google_pm_service.get_vehicle_details(unit)
        if not details:
            await cb.answer("❌ Truck not found in PM sheet.", show_alert=True)
            return

        text = format_pm_vehicle_info(details, full=True)
        await cb.bot.send_message(int(group_id), text, parse_mode="Markdown")
        await cb.answer("✅ Sent to linked group")
        logger.info(f"Sent PM info for truck {unit} to group {group_id}")
    except TelegramBadRequest as e:
        await cb.answer(f"⚠️ Telegram Error: {e}", show_alert=True)
    except Exception as e:
        logger.error(f"Error sending PM info to group: {e}")
        await cb.answer("❌ Internal error while sending", show_alert=True)
