"""
handlers/start.py
FleetMaster — Entrance Logic (Custom Welcome + DB Auth)
FINAL • STABLE • AIROGRAM v3 SAFE
"""

from aiogram import Router
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
        "🚛 **Welcome to FleetMaster Bot!**\n\n"
        "Your comprehensive fleet management assistant powered by Samsara Cloud.\n\n"
        "🔹 **TRUCK INFORMATION** — View detailed vehicle information\n"
        "🔹 **PM SERVICES** — Track preventive maintenance and service schedules\n"
        "🔹 **DOCUMENTS** — Access registrations, permits, and inspection records\n"
        "🔹 **Real-time Data** — Up-to-date fleet information\n"
        "🔹 **Easy Navigation** — Simple button interface\n\n"
        "**Features:**\n"
        "📋 Vehicle details (VIN, Plate, Year, Odometer)\n"
        "🛠 Preventive maintenance tracking\n"
        "📂 Centralized compliance documents\n"
        "🚛 Fleet overview and quick selection\n"
        "🔍 Search by VIN, Plate, or Name\n"
        "⚡ Fast cached responses\n\n"
        "Select an option below to get started:"
    )

    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(),
    )

    logger.info(f"Welcome shown to user {message.from_user.id}")


# ============================================================
# /START
# ============================================================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    logger.info(f"/start by user {user_id}")

    # Always reset FSM on /start
    await state.clear()

    # =========================
    # ADMIN BYPASS
    # =========================
    if user_id in ADMINS:
        await show_welcome(message)
        return

    user = await get_user_by_id(user_id)

    # =========================
    # NEW USER → REGISTRATION
    # =========================
    if not user:
        await message.answer(
            "🛡️ **FleetMaster Registration**\n\n"
            "To access the Fleet Dashboard, you must register first.\n"
            "Please enter your **Full Name**:"
        )
        await state.set_state(RegistrationStates.waiting_for_full_name)
        return

    # =========================
    # GMAIL NOT VERIFIED
    # =========================
    if not user.get("is_verified"):
        await message.answer(
            "📧 Your Gmail is not verified yet.\nPlease complete the verification process."
        )
        return

    # =========================
    # WAITING FOR ADMIN
    # =========================
    if not user.get("is_approved"):
        await message.answer(
            "⏳ Your account is verified and pending admin approval.\n"
            "You will be notified once access is granted."
        )
        return

    # =========================
    # DISABLED USER
    # =========================
    if not user.get("active"):
        await message.answer("🚫 Your access has been disabled by an admin.")
        return

    # =========================
    # AUTHORIZED USER
    # =========================
    await update_last_active(user_id)
    await show_welcome(message)


# ============================================================
# ACCESS CONTROL HELPER
# ============================================================
async def is_authorized(user_id: int) -> bool:
    if user_id in ADMINS:
        return True

    user = await get_user_by_id(user_id)
    if not user:
        return False

    return (
        user.get("is_verified") is True
        and user.get("is_approved") is True
        and user.get("active") is True
    )


# ============================================================
# MAIN MENU CALLBACK
# ============================================================
@router.callback_query(lambda c: c.data == "main_menu")
async def show_main_menu_callback(callback: CallbackQuery) -> None:
    if not await is_authorized(callback.from_user.id):
        await callback.answer("🔒 Access Denied. Contact Admin.", show_alert=True)
        return

    await callback.message.edit_text(
        "🚛 **FleetMaster Dashboard**",
        reply_markup=get_main_menu_keyboard(),
    )
    await callback.answer()
