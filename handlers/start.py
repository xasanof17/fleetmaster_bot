"""
handlers/start.py
FleetMaster — Entrance Logic (MARKDOWN SAFE)
"""

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import settings
from keyboards import get_main_menu_keyboard
from services.user_service import get_user_by_id, update_last_active
from utils.logger import get_logger

logger = get_logger("handlers.start")
router = Router()

ADMINS = set(settings.ADMINS or [])


# ============================================================
# FSM — Registration
# ============================================================
class RegistrationStates(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_nickname = State()
    waiting_for_role = State()
    waiting_for_phone = State()
    waiting_for_gmail = State()
    waiting_for_verification_code = State()


# ============================================================
# WELCOME
# ============================================================
async def show_welcome(message: Message) -> None:
    welcome_text = (
        "🚛 *Welcome to FleetMaster Bot!*\n\n"
        "Your comprehensive fleet management assistant powered by Samsara Cloud.\n\n"
        "🔹 *TRUCK INFORMATION* — Vehicle details\n"
        "🔹 *PM SERVICES* — Maintenance & service tracking\n"
        "🔹 *DOCUMENTS* — Registrations & inspections\n"
        "🔹 *Real-time Data*\n"
        "🔹 *Easy Navigation*\n\n"
        "*Features:*\n"
        "📋 VIN, Plate, Year, Odometer\n"
        "🛠 Maintenance alerts\n"
        "📂 Compliance documents\n"
        "🚛 Fleet overview\n"
        "🔍 Search vehicles\n\n"
        "Select an option below to get started:"
    )

    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


# ============================================================
# /START
# ============================================================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    logger.info(f"/start by user {user_id}")

    await state.clear()

    # ADMIN
    if user_id in ADMINS:
        await show_welcome(message)
        return

    user = await get_user_by_id(user_id)

    # NEW USER
    if not user:
        await message.answer(
            "🛡️ *FleetMaster Registration*\n\n"
            "To access the system, registration is required.\n"
            "Please enter your *Full Name*:",
            parse_mode=ParseMode.MARKDOWN,
        )
        await state.set_state(RegistrationStates.waiting_for_full_name)
        return

    if not user.get("is_verified"):
        await message.answer(
            "📧 Your Gmail is not verified yet.\nPlease complete verification.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if not user.get("is_approved"):
        await message.answer(
            "⏳ Your account is pending admin approval.\nYou will be notified once approved.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if not user.get("active"):
        await message.answer(
            "🚫 Your access has been disabled by an admin.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await update_last_active(user_id)
    await show_welcome(message)


# ============================================================
# MAIN MENU CALLBACK
# ============================================================
@router.callback_query(lambda c: c.data == "main_menu")
async def show_main_menu_callback(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🚛 *FleetMaster Dashboard*",
        reply_markup=get_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    await callback.answer()
