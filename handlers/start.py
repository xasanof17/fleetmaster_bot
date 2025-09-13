"""
Start and help handlers
"""
from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from keyboards import get_main_menu_keyboard, get_help_keyboard
from keyboards.documents import documents_menu_kb
from utils.logger import get_logger

logger = get_logger("handlers.start")
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    logger.info(f"User {message.from_user.id} started bot")
    welcome_text = """
🚛 **Welcome to FleetMaster Bot!**

Your comprehensive fleet management assistant powered by Samsara Cloud.

🔹 **TRUCK INFORMATION** - View vehicle information
🔹 **Real-time Data** - Get up-to-date fleet info  
🔹 **Easy Navigation** - Simple button interface

**Features:**
📋 Vehicle details (VIN, Plate, Year, Name, Odometer)
🚛 Fleet overview and selection
🔍 Search by Name, VIN, or Plate Number
⚡ Fast caching for instant responses

Select an option below to get started:
    """
    try:
        await message.answer(
            text=welcome_text.strip(),
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
        logger.success(f"Welcome message sent to user {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error sending welcome message: {e}")
        await message.answer("❌ Something went wrong. Please try again.")


@router.callback_query(lambda c: c.data == "help")
async def cmd_help(callback: CallbackQuery):
    logger.info(f"User {callback.from_user.id} requested help")
    help_text = """
❓ **FleetMaster Bot Help**

**Available Features:**

🚛 **TRUCK INFORMATION**
• View all vehicles in your fleet
• Get detailed vehicle information
• See VIN, plate number, year, name, and odometer

🔍 **Search Functionality**
• Search by vehicle name
• Search by VIN number
• Search by license plate
• Search all fields at once

**How to Use:**
1. Click **TRUCK INFORMATION** from main menu
2. Choose **View All Vehicles** to see your fleet
3. Or choose **Search Vehicle** to find specific vehicles
4. Select any vehicle to view detailed information
5. Use navigation buttons to browse

**Navigation:**
🏠 **Main Menu** - Return to dashboard
🔙 **Back** - Go to previous screen
🔄 **Refresh** - Update current data with latest info

**Performance Features:**
⚡ Smart caching for instant loading
🔄 Auto-refresh every 3 minutes
🚀 Optimized API calls for speed

**Need Help?**
This bot connects to your Samsara Cloud account to provide real-time fleet information. Make sure your API token has proper permissions for vehicle data access.
    """
    try:
        await callback.message.edit_text(
            text=help_text.strip(),
            reply_markup=get_help_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        logger.success(f"Help shown to user {callback.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error showing help: {e}")
        await callback.answer("❌ Error loading help")



@router.callback_query(lambda c: c.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    """Handle main menu callback"""
    
    logger.info(f"User {callback.from_user.id} requested main menu")
    
    main_menu_text = """
🚛 **FleetMaster Dashboard**

Your fleet management command center.

**Current Features:**
🚛 **TRUCK INFORMATION** - Vehicle information and details
🔍 **Search** - Find vehicles by name, VIN, or plate
⚡ **Fast Performance** - Cached data for instant responses

Choose an option below:
    """
    
    try:
        await callback.message.edit_text(
            text=main_menu_text.strip(),
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        logger.success(f"Main menu shown to user {callback.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error showing main menu: {e}")
        await callback.answer("❌ Error loading main menu")

# Handle main menu "Documents" button
@router.message(lambda m: m.text == "📂 Documents")
async def open_documents(message: Message):
    await message.answer("📂 Choose a document type:", reply_markup=documents_menu_kb())