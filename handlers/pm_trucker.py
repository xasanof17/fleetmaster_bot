import asyncio
import os
from config.settings import settings
from aiogram import Router, F
from aiogram.types import CallbackQuery,  FSInputFile
from services.samsara_service import samsara_service
from keyboards.pm_trucker import (
    get_pm_trucker_menu,
    get_vehicle_details_keyboard,
    get_search_options_keyboard,
    get_vehicles_list_keyboard,
)
from utils.helpers import (
    format_vehicle_info,
    format_vehicle_list,
    location_choice_keyboard,
    build_static_location_message,
    build_live_location_message,
)
from utils.logger_location import (log_location_request, read_logs)

from utils.logger import get_logger

logger = get_logger(__name__)
router = Router()
LIVE_UPDATE_INTERVAL = 30

FILES_DIR = os.path.join(os.path.dirname(__file__), "..", "files")

@router.callback_query(lambda c: c.data == "pm_trucker")
async def show_pm_trucker(callback: CallbackQuery):
    """Show PM TRUCKER main menu"""
    
    await callback.answer()
    logger.info(f"User {callback.from_user.id} accessed PM TRUCKER")

    pm_trucker_text = """🚛 **PM TRUCKER**

Vehicle information and management system.

**Available Options:**

🚛 **View All Vehicles** - Browse your complete fleet
🔍 **Search Vehicle** - Find vehicles by name, VIN, or plate
🔄 **Refresh Data** - Get latest vehicle information

Select an option to continue:"""

    try:
        await callback.message.edit_text(
            text=pm_trucker_text,
            reply_markup=get_pm_trucker_menu(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error showing PM TRUCKER menu: {e}")
        await callback.answer("❌ Error loading PM TRUCKER")

@router.callback_query(lambda c: c.data == "pm_view_all_vehicles")
async def show_all_vehicles(callback: CallbackQuery):
    """Show all vehicles in fleet"""
    logger.info(f"User {callback.from_user.id} requested vehicle list")
    await callback.answer("⚡ Loading vehicles...")

    try:
        async with samsara_service as service:
            vehicles = await service.get_vehicles(use_cache=True)

        if not vehicles:
            error_text = """❌ **No Vehicles Found**

This could mean:
• No vehicles in your fleet
• API connection issue
• Invalid API token

Please check your configuration and try again."""
            
            await callback.message.edit_text(
                text=error_text,
                reply_markup=get_back_to_pm_keyboard(),
                parse_mode="Markdown"
            )
            return

        list_text = format_vehicle_list(vehicles)
        await callback.message.edit_text(
            text=list_text,
            reply_markup=get_vehicles_list_keyboard(vehicles),
            parse_mode="Markdown"
        )
        logger.info(f"Showed {len(vehicles)} vehicles to user {callback.from_user.id}")

    except Exception as e:
        logger.error(f"Error fetching vehicles: {e}")
        await callback.message.edit_text(
            text="❌ **Error Loading Vehicles**\n\nPlease check your connection and try again.",
            reply_markup=get_back_to_pm_keyboard(),
            parse_mode="Markdown"
        )

@router.callback_query(lambda c: c.data.startswith("pm_vehicles_page:"))
async def show_vehicles_page(callback: CallbackQuery):
    """Show specific page of vehicles"""
    await callback.answer("⚡ Loading page...")
    try:
        page = int(callback.data.split(":")[1])

        async with samsara_service as service:
            vehicles = await service.get_vehicles(use_cache=True)

        if not vehicles:
            await callback.answer("❌ No vehicles found")
            return

        list_text = format_vehicle_list(vehicles)
        await callback.message.edit_text(
            text=list_text,
            reply_markup=get_vehicles_list_keyboard(vehicles, page=page),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error showing vehicles page: {e}")
        await callback.answer("❌ Error loading page")

@router.callback_query(lambda c: c.data.startswith("pm_vehicle_details:"))
async def show_vehicle_details(callback: CallbackQuery):
    """Show detailed information for specific vehicle"""
    await callback.answer()
    vehicle_id = callback.data.split(":", 1)[1]
    try:
        await callback.answer("⚡ Loading vehicle details...")

        async with samsara_service as service:
            vehicle = await service.get_vehicle_with_stats(vehicle_id)

        if not vehicle:
            error_text = """❌ **Vehicle Not Found**

The requested vehicle could not be found.

This might be due to:
• Vehicle ID not valid
• Insufficient permissions
• Vehicle removed from fleet"""
            
            await callback.message.edit_text(
                text=error_text,
                reply_markup=get_back_to_pm_keyboard(),
                parse_mode="Markdown"
            )
            return

        vehicle_info = format_vehicle_info(vehicle)
        await callback.message.edit_text(
            text=vehicle_info,
            reply_markup=get_vehicle_details_keyboard(vehicle_id, vehicle.get("name")),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error showing vehicle details: {e}")
        await callback.message.edit_text(
            text="❌ **Error Loading Vehicle Details**\n\nPlease try again later.",
            reply_markup=get_back_to_pm_keyboard(),
            parse_mode="Markdown"
        )

@router.callback_query(lambda c: c.data == "pm_search_vehicle")
async def search_vehicle(callback: CallbackQuery):
    """Show search options"""
    search_text = """🔍 **Search Vehicles**

Choose how you want to search for vehicles:

🏷️ **By Name** - Search by vehicle name
🔢 **By VIN** - Search by VIN number  
🚗 **By Plate** - Search by license plate
🔍 **All Fields** - Search in all fields at once

Select a search type:"""

    try:
        await callback.message.edit_text(
            text=search_text,
            reply_markup=get_search_options_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer("🔍 Choose search type")
    except Exception as e:
        logger.error(f"Error showing search options: {e}")
        await callback.answer("❌ Error loading search options")

@router.callback_query(lambda c: c.data == "pm_refresh_cache")
async def refresh_cache(callback: CallbackQuery):
    """Refresh vehicle cache"""
    await callback.answer("🔄 Refreshing data...")
    try:
        async with samsara_service as service:
            service.clear_cache()
            vehicles = await service.get_vehicles(use_cache=False)

        if vehicles:
            await callback.message.edit_text(
                text=f"🚛 **PM TRUCKER**\n\n✅ **Data Refreshed!** Updated {len(vehicles)} vehicles.\n\nSelect an option:",
                reply_markup=get_pm_trucker_menu(),
                parse_mode="Markdown"
            )
            await callback.answer(f"✅ Refreshed {len(vehicles)} vehicles!")
        else:
            await callback.answer("❌ No data available")
    except Exception as e:
        logger.error(f"Error refreshing cache: {e}")
        await callback.answer("❌ Error refreshing data")

@router.callback_query(lambda c: c.data == "pm_page_info")
async def show_page_info(callback: CallbackQuery):
    """Handle page info button click"""
    await callback.answer("📄 Use Previous/Next buttons to navigate pages")
    

# Ask user static or live
@router.callback_query(F.data.startswith("live_loc:"))
async def ask_location_type(callback: CallbackQuery):
    vehicle_id = callback.data.split(":", 1)[1]
    await callback.message.answer(
        "How would you like the location?",
        reply_markup=location_choice_keyboard(vehicle_id),
    )
    await callback.answer()

@router.callback_query(F.data.startswith("loc_static:"))
async def handle_static(callback: CallbackQuery):
    
    await callback.answer()
    
    vehicle_id = callback.data.split(":", 1)[1]
    
    # 🗑️ delete the "Choose location type" message
    await callback.message.delete()
    
    try:
        async with samsara_service as service:
            vehicle = await service.get_vehicle_by_id(vehicle_id)
            location = await service.get_vehicle_location(vehicle_id)

        if not vehicle or not location:
            await callback.message.answer("⚠️ Could not fetch vehicle/location data.")
            await callback.answer()
            return

        lat = location["latitude"]
        lon = location["longitude"]

        # send map pin (one-time static)
        await callback.message.answer_location(latitude=lat, longitude=lon)

        # build & send human-readable message + keyboard
        msg, _ = build_static_location_message(vehicle, location)
        await callback.message.answer(text=msg, parse_mode="Markdown")

        # log to file
        try:
            log_location_request(
                user_id=callback.from_user.id,
                vehicle_id=vehicle_id,
                location_type="static",
                address=location.get("address"),
            )
        except Exception:
            # don't crash user flow if logging fails
            logger.exception("Failed to log location request")

    except Exception as e:
        logger.error(f"Error handling static location: {e}")
        await callback.message.answer("❌ Error fetching/sending location.")
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("loc_live:"))
async def handle_live(callback: CallbackQuery):
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

        lat = location["latitude"]
        lon = location["longitude"]

        # 1️⃣ send initial live location
        live_msg = await callback.message.answer_location(
            latitude=lat,
            longitude=lon,
            live_period=300,  # X minutes
        )

        # 2️⃣ send address/time text
        msg, _ = build_live_location_message(vehicle, location)
        await callback.message.answer(msg, parse_mode="Markdown")

        # 3️⃣ log request
        log_location_request(
            user_id=callback.from_user.id,
            vehicle_id=vehicle_id,
            location_type="live",
            address=location.get("address"),
        )

        # 4️⃣ background updater
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
                logger.error(f"Error updating live location: {e}")
            finally:
                # stop live location gracefully when time is up
                try:
                    await callback.bot.stop_message_live_location(
                        chat_id=callback.message.chat.id,
                        message_id=live_msg.message_id,
                    )
                except Exception:
                    pass

        asyncio.create_task(updater())  # run in background

    except Exception as e:
        logger.error(f"Error handling live location: {e}")
        await callback.message.answer("❌ Error sending live location")
        

@router.callback_query(F.data.startswith("pm_vehicle_location:"))
async def handle_pm_vehicle_location(callback: CallbackQuery):
    
    await callback.answer()
    vehicle_id = callback.data.split(":", 1)[1]

    # Step 1. Ask user: static or live?
    await callback.message.answer(
        "📍 Choose location type:",
        reply_markup=location_choice_keyboard(vehicle_id),
    )

    await callback.answer()
      
# ---------------- REGISTRATION FILE HANDLER ----------------
@router.callback_query(F.data.startswith("pm_vehicle_reg:"))
async def handle_registration_file(callback: CallbackQuery):
    """Send registration PDF for a vehicle from local files/ folder"""
    await callback.answer()

    vehicle_name = callback.data.split(":", 1)[1]
    logger.info(f"User {callback.from_user.id} requested registration file for {vehicle_name}")

    found_file = None
    try:
        available_files = os.listdir(FILES_DIR)
        for fname in available_files:
            if fname.lower().endswith(".pdf") and vehicle_name.lower() in fname.lower():
                found_file = os.path.join(FILES_DIR, fname)
                break
    except Exception as e:
        logger.error(f"Error reading files directory {FILES_DIR}: {e}")
        await callback.message.answer("❌ Error accessing registration files.")
        return

    if not found_file:
        await callback.message.answer(f"❌ Registration file for **{vehicle_name}** not found.")
        return

    try:
        # ✅ Correct way: wrap with FSInputFile
        document = FSInputFile(found_file)
        await callback.message.answer_document(
            document=document,
            caption=f"📄 Registration File for {vehicle_name}"
        )
        logger.info(f"✅ Sent {found_file} to user {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Error sending registration file {found_file}: {e}")
        await callback.message.answer("❌ Error sending registration file.")