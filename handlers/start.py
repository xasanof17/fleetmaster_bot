"""
Start and help handlers
"""
from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import get_main_menu_keyboard, get_help_keyboard
from keyboards.documents import documents_menu_kb
from utils.logger import get_logger
from config import settings
from datetime import date

logger = get_logger("handlers.start")
router = Router()

# FSM state for auth
class AuthStates(StatesGroup):
    waiting_for_password = State()

# >>> simple password (put real password in env)
BOT_PASSWORD = settings.BOT_PASSWORD
# >>> keep authorized users with date
authorized_users: dict[int, date] = {}


async def show_welcome(message: Message):
    """Send welcome/main menu (used when user is authorized)."""
    welcome_text = """
🚛 **Welcome to FleetMaster Bot!**

Your comprehensive fleet management assistant powered by Samsara Cloud.

🔹 **TRUCK INFORMATION** – View detailed vehicle information  
🔹 **PM SERVICES** – Track preventive maintenance, urgent oil changes, and service schedules  
🔹 **DOCUMENTS** – Access registrations, permits, lease agreements, and inspection records  
🔹 **Real-time Data** – Get up-to-date fleet info  
🔹 **Easy Navigation** – Simple button interface

**Features:**
📋 Vehicle details (VIN, Plate, Year, Name, Odometer)  
🛠 Preventive maintenance tracking and service alerts  
📂 Centralized document storage for fleet compliance  
🚛 Fleet overview and quick vehicle selection  
🔍 Search by Name, VIN, or Plate Number  
⚡ Fast caching for instant responses

Select an option below to get started:
    """.strip()

    try:
        await message.answer(
            text=welcome_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
        logger.success(f"Welcome message sent to user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error sending welcome message: {e}")
        await message.answer("❌ Something went wrong. Please try again.")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """/start — if authorized today show menu, otherwise request password."""
    logger.info(f"User {message.from_user.id} started bot")

    today = date.today()
    if authorized_users.get(message.from_user.id) == today:
        # user already authorized today -> show welcome
        await show_welcome(message)
        return

    # not authorized today -> ask for password
    await message.answer("🔒 Please enter the bot password to continue:")
    await state.set_state(AuthStates.waiting_for_password)


# Only runs when user is in waiting_for_password state
@router.message(AuthStates.waiting_for_password)
async def password_check(message: Message, state: FSMContext):
    attempt = (message.text or "").strip()
    if attempt == BOT_PASSWORD:
        authorized_users[message.from_user.id] = date.today()
        await state.clear()  # leave the auth state
        await message.answer("✅ Password correct! You are authorized until midnight today.\nSend /start to open the menu.")
        logger.success(f"User {message.from_user.id} authorized successfully for today")
    else:
        await message.answer("❌ Wrong password. Try again.")
        logger.warning(f"User {message.from_user.id} entered wrong password")


def is_authorized_today(user_id: int) -> bool:
    """Check if user is authorized today."""
    return authorized_users.get(user_id) == date.today()


def require_auth_message() -> str:
    """Standard message for expired/missing authorization."""
    return "🔑 Your authorization expired. Please re-enter today’s password with /start"


@router.callback_query(lambda c: c.data == "help")
async def cmd_help(callback: CallbackQuery):
    # protect help: only for authorized users
    if not is_authorized_today(callback.from_user.id):
        await callback.answer(require_auth_message(), show_alert=True)
        return

    logger.info(f"User {callback.from_user.id} requested help")

    help_text = """
❓ **FleetMaster Bot Help**

**Available Features**

🚛 **TRUCK INFORMATION**
• View all vehicles in your fleet
• Get detailed vehicle information
• See VIN, plate number, year, name and odometer

🔍 **Search Functionality**
• Search by vehicle name
• Search by VIN number
• Search by license plate
• Search all fields at once

🚚 **PM SERVICES**
• View trucks needing 📌*Urgent Oil Change*
• View trucks scheduled for routine 🟡*Oil Change*
• Search 🔢 by unit number (message or /slash)
• Browse all preventive-maintenance records

📂 **Documents**
• Access company and vehicle documents in one place
• View registrations, state permits, lease agreements
• Open annual inspection forms and more
• Quick navigation back to the dashboard

**How to Use**
1. Click 🚛**TRUCK INFORMATION** to browse or search your fleet
2. Click 🚚**PM SERVICES** to see upcoming maintenance or urgent oil changes
3. Click 📂**Documents** to open the document center and pick a category
4. Use search boxes or inline commands (like `/5071`) to jump directly to a truck
5. Use navigation buttons (Main Menu, Back, Refresh) to move around

**Navigation**
🏠 **Main Menu** – Return to dashboard  
🔙 **Back** – Go to previous screen  
🔄 **Refresh** – Update current data with the latest info
    """.strip()

    try:
        await callback.message.edit_text(
            text=help_text,
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
    """Handle main menu callback (protected)."""
    if not is_authorized_today(callback.from_user.id):
        await callback.answer(require_auth_message(), show_alert=True)
        return

    logger.info(f"User {callback.from_user.id} requested main menu")

    main_menu_text = """
🚛 **FleetMaster Dashboard**

Your fleet management command center.

**Current Features:**
🚛 **TRUCK INFORMATION** – View your entire fleet and get detailed vehicle info  
🚚 **PM SERVICES** – Track preventive maintenance, urgent oil changes, and service schedules  
📂 **DOCUMENTS** – Access registrations, permits, lease agreements, and inspection records  
🔍 **Search** – Find vehicles by name, VIN, or plate instantly  
⚡ **Fast Performance** – Cached data for near-instant responses

Choose an option below:
    """.strip()

    try:
        await callback.message.edit_text(
            text=main_menu_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        logger.success(f"Main menu shown to user {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Error showing main menu: {e}")
        await callback.answer("❌ Error loading main menu")


# Handle main menu "Documents" button (protected)
@router.message(lambda m: m.text == "📂 Documents")
async def open_documents(message: Message):
    if not is_authorized_today(message.from_user.id):
        await message.answer(require_auth_message())
        return
    doc_intro = (
    "📂 **DOCUMENTS** – Fleet & Compliance Files\n\n"
    "Access key paperwork in one place:\n"
    "• Registrations and state permits\n"
    "• Lease agreements and annual inspections\n\n"
    "Select a document category below to view or download:"
)
    await message.answer(doc_intro, reply_markup=documents_menu_kb(), parse_mode="Markdown")
