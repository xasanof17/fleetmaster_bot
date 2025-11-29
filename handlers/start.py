"""
Start and access-control handlers
"""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from config import settings
from keyboards import get_help_keyboard, get_main_menu_keyboard
from keyboards.documents import documents_menu_kb
from services.access_control import AccessRequest, AccessStatus, access_storage
from utils.logger import get_logger

logger = get_logger("handlers.start")
router = Router()

ADMINS = set(settings.ADMINS or [])


# =====================================================
# FSM
# =====================================================

class AccessForm(StatesGroup):
    waiting_for_contact = State()
    waiting_for_gmail = State()
    waiting_for_full_name = State()
    waiting_for_role = State()


# =====================================================
# Helpers
# =====================================================

def has_access(user_id: int) -> bool:
    if user_id in ADMINS:
        return True
    return access_storage.has_access(user_id)


def require_auth_message() -> str:
    return (
        "🔒 You do not have access yet.\n"
        "Send /start and submit your info so an admin can review your request."
    )


async def show_welcome(message: Message) -> None:
    welcome_text = """
🚛 **Welcome to FleetMaster Bot!**

Your comprehensive fleet management assistant powered by Samsara Cloud.

🔹 **TRUCK INFORMATION** — View detailed vehicle information  
🔹 **PM SERVICES** — Track preventive maintenance and service schedules  
🔹 **DOCUMENTS** — Access registrations, permits, lease agreements, inspections  
🔹 **Real-time Data** — Samsara-powered fleet status  
🔹 **Easy Navigation** — One-tap menus

Select an option below:
""".strip()

    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(message.from_user.id),
        parse_mode="Markdown"
    )


def _admin_keyboard_for_user(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Give access", callback_data=f"access:approve:{uid}"),
                InlineKeyboardButton(text="❌ Remove access", callback_data=f"access:deny:{uid}"),
            ],
            [
                InlineKeyboardButton(text="🚫 Cancel", callback_data=f"access:cancel:{uid}")
            ]
        ]
    )


def _role_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Manager", callback_data="role:Manager")],
            [InlineKeyboardButton(text="Dispatcher", callback_data="role:Dispatcher")],
            [InlineKeyboardButton(text="Fleet specialist", callback_data="role:Fleet specialist")],
            [InlineKeyboardButton(text="Safety specialist", callback_data="role:Safety specialist")],
            [InlineKeyboardButton(text="Updater", callback_data="role:Updater")],
            [InlineKeyboardButton(text="Fuel coordinator", callback_data="role:Fuel coordinator")],
            [InlineKeyboardButton(text="Trailer coordinator", callback_data="role:Trailer coordinator")],
        ]
    )


# =====================================================
# /start
# =====================================================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user
    if not user:
        return

    user_id = user.id
    await state.clear()
    logger.info("User %s sent /start", user_id)

    # -----------------------------
    # 1. Admin -> direct access
    # -----------------------------
    if user_id in ADMINS:
        await show_welcome(message)
        return

    # -----------------------------
    # 2. Check saved access request
    # -----------------------------
    existing = access_storage.get(user_id)

    if existing:
        # APPROVED → go to welcome screen
        if existing.status == AccessStatus.APPROVED:
            await show_welcome(message)
            return

        # PENDING → no need to retry onboarding
        if existing.status == AccessStatus.PENDING:
            await message.answer(
                "⌛ Your access request is still under review.\n"
                "We will notify you once it's approved."
            )
            return

        # DENIED → do NOT show onboarding again
        if existing.status == AccessStatus.DENIED:
            await message.answer(
                "❌ Your previous request was denied.\n"
                "If this is incorrect, contact an admin."
            )
            return

    # -----------------------------
    # 3. NEW USER → ask for contact
    # -----------------------------
    share_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Share Contact 📱", request_contact=True)]],
        resize_keyboard=True,
    )

    await message.answer("👋 Welcome! To request access, please share your phone number:")
    await message.answer("Tap the button to share your contact:", reply_markup=share_kb)

    await state.set_state(AccessForm.waiting_for_contact)


# =====================================================
# Contact → Gmail → Full name → Role
# =====================================================

@router.message(AccessForm.waiting_for_contact)
async def process_contact(message: Message, state: FSMContext):
    if not message.contact:
        await message.answer("❗ Please use the button to share your contact.")
        return

    await state.update_data(phone=message.contact.phone_number)

    await message.answer(
        "✉️ Now send your *active Gmail address*.\nExample: `yourname@gmail.com`",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

    await state.set_state(AccessForm.waiting_for_gmail)


@router.message(AccessForm.waiting_for_gmail)
async def process_gmail(message: Message, state: FSMContext):
    gmail = (message.text or "").strip().lower()

    if "@" not in gmail or "." not in gmail:
        await message.answer("❌ Invalid email. Please send a correct Gmail address.")
        return

    await state.update_data(gmail=gmail)

    await message.answer("👤 Great. Now send your *full name* (First Last).", parse_mode="Markdown")
    await state.set_state(AccessForm.waiting_for_full_name)


@router.message(AccessForm.waiting_for_full_name)
async def process_full_name(message: Message, state: FSMContext):
    full_name = (message.text or "").strip()

    if len(full_name.split()) < 2:
        await message.answer("❌ Please send both first and last name.")
        return

    await state.update_data(full_name=full_name)

    await message.answer("🧑‍💼 Finally, choose your role:", reply_markup=_role_keyboard())
    await state.set_state(AccessForm.waiting_for_role)


@router.callback_query(AccessForm.waiting_for_role, F.data.startswith("role:"))
async def process_role(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split("role:", 1)[1]

    data = await state.get_data()
    await state.clear()

    user = callback.from_user

    req = AccessRequest(
        tg_id=user.id,
        telegram_username=f"@{user.username}" if user.username else None,
        full_name=data["full_name"],
        phone=data["phone"],
        gmail=data["gmail"],
        role=role,
        status=AccessStatus.PENDING,
    )

    access_storage.save_pending(req)

    await callback.message.edit_text(
        f"✅ Your access request has been submitted.\n"
        f"Role: <b>{role}</b>\n"
        f"Admins will review it soon.",
        parse_mode="HTML"
    )

    kb = _admin_keyboard_for_user(req.tg_id)

    for admin_id in ADMINS:
        try:
            await callback.bot.send_message(
                admin_id,
                (
                    "🆕 <b>New Access Request</b>\n\n"
                    f"<b>Name:</b> {req.full_name}\n"
                    f"<b>Phone:</b> {req.phone}\n"
                    f"<b>Email:</b> {req.gmail}\n"
                    f"<b>Telegram:</b> {req.telegram_username or '—'}\n"
                    f"<b>Role:</b> {req.role}\n"
                    f"<b>User ID:</b> <code>{req.tg_id}</code>"
                ),
                reply_markup=kb,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error("Failed to notify admin %s: %s", admin_id, e)

    await callback.answer()


# =====================================================
# Admin actions (approve / deny)
# =====================================================

@router.callback_query(F.data.startswith("access:"))
async def handle_access_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.answer("Not allowed.", show_alert=True)
        return

    _, action, user_id_str = callback.data.split(":")
    target_id = int(user_id_str)

    if action == "cancel":
        await callback.message.edit_reply_markup(None)
        await callback.answer("Cancelled.")
        return

    if action not in {"approve", "deny"}:
        await callback.answer("Unknown action.")
        return

    new_status = AccessStatus.APPROVED if action == "approve" else AccessStatus.DENIED
    req = access_storage.update_status(target_id, new_status, approved_by=callback.from_user.id)

    if not req:
        await callback.answer("User not found.", show_alert=True)
        return

    status_text = "✅ Access GRANTED" if new_status == AccessStatus.APPROVED else "❌ Access DENIED"

    await callback.message.edit_text(
        f"{callback.message.text}\n\n<b>{status_text}</b>\n<b>By:</b> @{callback.from_user.username}",
        parse_mode="HTML"
    )

    await callback.answer("Done.")

    # notify user
    try:
        if new_status == AccessStatus.APPROVED:
            await callback.bot.send_message(
                target_id,
                "✅ Your access has been approved.\nWelcome to FleetMaster Bot!",
                parse_mode="HTML",
            )
        else:
            await callback.bot.send_message(
                target_id,
                "❌ Your access request has been rejected.",
                parse_mode="HTML",
            )
    except:
        pass


# =====================================================
# Help & Main Menu
# =====================================================

@router.callback_query(lambda c: c.data == "help")
async def cmd_help(callback: CallbackQuery):
    if not has_access(callback.from_user.id):
        await callback.answer(require_auth_message(), show_alert=True)
        return

    help_text = """
❓ **FleetMaster Bot Help**

🚛 Truck Information  
🚚 PM Services  
📂 Documents  
🗳 Trailer Information  
🔍 Search  
""".strip()

    await callback.message.edit_text(help_text, reply_markup=get_help_keyboard(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(lambda c: c.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    if not has_access(callback.from_user.id):
        await callback.answer(require_auth_message(), show_alert=True)
        return

    await callback.message.edit_text(
        "🏠 **Main Menu**",
        reply_markup=get_main_menu_keyboard(callback.from_user.id),
        parse_mode="Markdown",
    )

    await callback.answer()


# =====================================================
# Legacy: Documents by text button
# =====================================================

@router.message(lambda m: m.text == "📂 Documents")
async def open_docs(message: Message):
    if not has_access(message.from_user.id):
        await message.answer(require_auth_message())
        return

    await message.answer(
        "📂 **DOCUMENTS** — Fleet & Compliance Files",
        reply_markup=documents_menu_kb(),
        parse_mode="Markdown",
    )
