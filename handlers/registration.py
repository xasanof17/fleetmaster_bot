import contextlib

from aiogram import F, Router
from aiogram.enums import ParseMode  # Added for cleaner mode selection
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from config import settings
from handlers.start import RegistrationStates
from services import create_or_resend_code, verify_code
from services.user_service import get_user_by_id, save_signup_data
from utils.logger import get_logger
from utils.mailer import send_verification_email

logger = get_logger("handlers.registration")
router = Router()

# ============================================================
# 1. NAME & NICKNAME
# ============================================================


@router.message(RegistrationStates.waiting_for_full_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text, user_id=message.from_user.id)
    await message.answer(
        f"Thanks, *{message.text}*! Now, what is your nickname (or Telegram @username)?",
        parse_mode=ParseMode.MARKDOWN,
    )
    await state.set_state(RegistrationStates.waiting_for_nickname)


@router.message(RegistrationStates.waiting_for_nickname)
async def process_nickname(message: Message, state: FSMContext):
    await state.update_data(nickname=message.text)

    role_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Dispatcher"), KeyboardButton(text="Fleet Dispatcher")],
            [KeyboardButton(text="Accounting Manager"), KeyboardButton(text="Quality Manager")],
            [KeyboardButton(text="Updater"), KeyboardButton(text="Fuel Coordinator")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await message.answer(
        "What is your *role* at the company?",
        reply_markup=role_kb,
        parse_mode=ParseMode.MARKDOWN,
    )
    await state.set_state(RegistrationStates.waiting_for_role)


# ============================================================
# 2. ROLE & PHONE
# ============================================================


@router.message(RegistrationStates.waiting_for_role)
async def process_role(message: Message, state: FSMContext):
    allowed_roles = [
        "Dispatcher",
        "Fleet Dispatcher",
        "Accounting Manager",
        "Quality Manager",
        "Updater",
        "Fuel Coordinator",
    ]

    if message.text not in allowed_roles:
        await message.answer(
            "Please select a role from the keyboard.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await state.update_data(role=message.text)

    phone_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Share Phone Number", request_contact=True)]],
        resize_keyboard=True,
    )

    await message.answer(
        "Please share your *phone number* using the button below:",
        reply_markup=phone_kb,
        parse_mode=ParseMode.MARKDOWN,
    )
    await state.set_state(RegistrationStates.waiting_for_phone)


@router.message(RegistrationStates.waiting_for_phone, F.contact | F.text)
async def process_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    await state.update_data(phone_number=phone)

    await message.answer(
        "Almost done! Please enter your *Gmail address* for verification:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.MARKDOWN,
    )
    await state.set_state(RegistrationStates.waiting_for_gmail)


# ============================================================
# 3. GMAIL & VERIFICATION CODE
# ============================================================


@router.message(RegistrationStates.waiting_for_gmail)
async def process_gmail(message: Message, state: FSMContext):
    gmail = message.text.strip().lower()

    if "@gmail.com" not in gmail:
        await message.answer(
            "❌ Please enter a valid *Gmail* address (@gmail.com).",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await state.update_data(gmail=gmail)
    user_data = await state.get_data()

    # 1. Save data to DB
    await save_signup_data(user_data)

    # 2. Generate and Send Code
    code = await create_or_resend_code(message.from_user.id, gmail)
    if not code:
        await message.answer(
            "⏳ Please wait 60 seconds before requesting another code.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    sent = await send_verification_email(gmail, code)
    if sent:
        await message.answer(
            f"🔢 Code has been sent to *{gmail}*.\nPlease enter it here:",
            parse_mode=ParseMode.MARKDOWN,
        )
        await state.set_state(RegistrationStates.waiting_for_verification_code)
    else:
        await message.answer(
            "❌ Error sending email. Please try again later or contact support.",
            parse_mode=ParseMode.MARKDOWN,
        )


@router.message(RegistrationStates.waiting_for_verification_code)
async def process_code(message: Message, state: FSMContext):
    input_code = message.text.strip()
    user_id = message.from_user.id

    is_valid = await verify_code(user_id, input_code)

    if not is_valid:
        await message.answer(
            "❌ Invalid or expired code. Please try again.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await state.clear()
    await message.answer(
        "✅ *Email Verified!*\n\n"
        "Your profile has been sent to the Admins for final approval.\n"
        "You will receive a notification once access is granted.",
        parse_mode=ParseMode.MARKDOWN,
    )
    await notify_admins_of_request(message, user_id)


# ============================================================
# 4. ADMIN NOTIFICATION
# ============================================================


async def notify_admins_of_request(message: Message, user_id: int):
    user = await get_user_by_id(user_id)
    if not user:
        return

    admin_text = (
        "🆕 *New Access Request*\n\n"
        f"👤 *Full Name:* {user['full_name']}\n"
        f"🆔 *Nickname:* {user.get('nickname', 'N/A')}\n"
        f"💼 *Role:* {user['role']}\n"
        f"📞 *Phone:* {user['phone_number']}\n"
        f"📧 *Gmail:* {user['gmail']} (VERIFIED ✅)\n\n"
        "Do you grant access to this user?"
    )

    from keyboards.admin import get_admin_approval_kb

    for admin_id in settings.ADMINS:
        with contextlib.suppress(Exception):
            await message.bot.send_message(
                admin_id,
                text=admin_text,
                reply_markup=get_admin_approval_kb(user_id),
                parse_mode=ParseMode.MARKDOWN,
            )


@router.message(Command("verify_gmail"))
async def cmd_verify_gmail(message: Message, state: FSMContext):
    user = await get_user_by_id(message.from_user.id)

    if not user:
        await message.answer(
            "⛔ Please register first using /start.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if user.get("gmail_verified"):
        await message.answer(
            "✅ Your Gmail is already verified.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await message.answer(
        "📧 Please enter your *Gmail address*:",
        parse_mode=ParseMode.MARKDOWN,
    )
    await state.set_state(RegistrationStates.waiting_for_gmail)
