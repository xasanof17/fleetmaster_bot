"""
Start and access-control handlers

New logic:
- Admins are auto-authorized.
- Other users must submit an access request (Contact, Gmail, full name, position).
- Phone number is taken only from Telegram contact share (no manual input).
- Users select their job position (role) from inline buttons.
- Admins receive an approval message with buttons:
  • Give access
  • Remove access
  • Cancel
- User data is stored temporarily in JSON files (see services/access_control.py).
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

# Admins from .env (ADMINS=123,456)
ADMINS = set(settings.ADMINS or [])


# =====================================================
#  FSM for access onboarding
# =====================================================


class AccessForm(StatesGroup):
    waiting_for_contact = State()
    waiting_for_gmail = State()
    waiting_for_full_name = State()
    waiting_for_role = State()


# =====================================================
#  Helpers
# =====================================================


def has_access(user_id: int) -> bool:
    """
    Unified access check used across the bot.

    Admins always have access.
    Regular users must be APPROVED in access_storage.
    """
    if user_id in ADMINS:
        return True
    return access_storage.has_access(user_id)


def is_authorized_today(user_id: int) -> bool:
    """
    Backwards-compatible alias used by other handlers.

    Internally now just checks has_access().
    """
    return has_access(user_id)


def require_auth_message() -> str:
    """
    Standard message when user tries to open protected features without access.
    """
    return (
        "🔒 You do not have access yet.\n"
        "Send /start and submit your info so an admin can review your request."
    )


async def show_welcome(message: Message) -> None:
    """
    Send welcome/main menu for users who already have access.
    """
    welcome_text = """
🚛 **Welcome to FleetMaster Bot!**

Your comprehensive fleet management assistant powered by Samsara Cloud.

🔹 **TRUCK INFORMATION** — View detailed vehicle information  
🔹 **PM SERVICES** — Track preventive maintenance and service schedules  
🔹 **DOCUMENTS** — Access registrations, permits, lease agreements, inspections  
🔹 **Real-time Data** — Samsara-powered fleet status  
🔹 **Easy Navigation** — One-tap menus

📋 Vehicle details (VIN, Plate, Year, Name, Odometer)  
🛠 PM tracking and alerts  
📂 Centralized document storage  
🔍 Search by Name, VIN, or Plate  
⚡ Fast caching for instant responses

Select an option below to get started:
    """.strip()

    try:
        await message.answer(
            text=welcome_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown",
        )
        logger.info("Welcome message sent to user %s", message.from_user.id)
    except Exception as e:  # noqa: BLE001
        logger.error("Error sending welcome message: %s", e)
        await message.answer("❌ Something went wrong. Please try again.")


def _admin_keyboard_for_user(user_id: int) -> InlineKeyboardMarkup:
    """
    Inline buttons for admins to approve or deny access.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Give access",
                    callback_data=f"access:approve:{user_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Remove access",
                    callback_data=f"access:deny:{user_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Cancel",
                    callback_data=f"access:cancel:{user_id}",
                )
            ],
        ]
    )


def _role_keyboard() -> InlineKeyboardMarkup:
    """
    Inline keyboard for selecting user position / role.
    """
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
#  /start — main entrypoint
# =====================================================


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """
    /start flow:

    - Admins: auto-enter main menu (no form, no password).
    - Approved users: go straight to main menu.
    - Pending users: see status message.
    - New / denied users: start access request form (contact → gmail → full name → role).
    """
    user = message.from_user
    if not user:
        return

    user_id = user.id
    logger.info("User %s sent /start", user_id)

    # Clear any previous FSM state
    await state.clear()

    # 1) Admins: always in
    if user_id in ADMINS:
        logger.info("✅ Admin %s auto-authorized (no form required)", user_id)
        await show_welcome(message)
        return

    # 2) Check existing access record
    existing = access_storage.get(user_id)

    if existing and existing.status is AccessStatus.APPROVED:
        logger.info("✅ User %s already approved — showing main menu", user_id)
        await show_welcome(message)
        return

    if existing and existing.status is AccessStatus.PENDING:
        await message.answer(
            "⌛ Your access request is still under review by an admin.\n"
            "We will notify you as soon as the decision is made."
        )
        logger.info("User %s tried /start but request is still pending", user_id)
        return

    if existing and existing.status is AccessStatus.DENIED:
        await message.answer(
            "❌ Your previous access request was rejected.\n"
            "If this is a mistake, please contact an admin.\n\n"
            "You can submit a new request.\n"
            "📱 First, please share your phone number using the button below:",
        )
    else:
        # 3) Fresh user — start onboarding
        await message.answer(
            "👋 Welcome! To request access, please share your phone number using the button below:",
        )

    share_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Share Contact 📱", request_contact=True)]],
        resize_keyboard=True,
    )
    await message.answer(
        "Tap the button to share your contact:",
        reply_markup=share_kb,
    )
    await state.set_state(AccessForm.waiting_for_contact)


# =====================================================
#  AccessForm steps
# =====================================================


@router.message(AccessForm.waiting_for_contact)
async def process_contact(message: Message, state: FSMContext) -> None:
    """
    Get phone number only from Telegram contact.
    """
    if not message.contact:
        await message.answer("❗ Please use the button to share your contact.")
        return

    phone_number = message.contact.phone_number
    await state.update_data(phone=phone_number)

    # Remove reply keyboard and ask for Gmail
    await message.answer(
        "✉️ Now send your *active Gmail address*.\nExample: `yourname@gmail.com`",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    await state.set_state(AccessForm.waiting_for_gmail)


@router.message(AccessForm.waiting_for_gmail)
async def process_gmail(message: Message, state: FSMContext) -> None:
    gmail_raw = (message.text or "").strip()
    gmail = gmail_raw.lower()

    if "@" not in gmail or "." not in gmail:
        await message.answer("❌ This doesn't look like a valid email. Please send a correct Gmail address.")
        return

    await state.update_data(gmail=gmail)
    await message.answer(
        "👤 Great. Now send your *full name* (First Last).",
        parse_mode="Markdown",
    )
    await state.set_state(AccessForm.waiting_for_full_name)


@router.message(AccessForm.waiting_for_full_name)
async def process_full_name(message: Message, state: FSMContext) -> None:
    full_name = (message.text or "").strip()
    if not message.from_user:
        return

    if len(full_name.split()) < 2:
        await message.answer("❌ Please send full name: at least first and last name.")
        return

    await state.update_data(full_name=full_name)

    # Ask for role selection
    await message.answer(
        "🧑‍💼 Finally, select your job position:",
        reply_markup=_role_keyboard(),
    )
    await state.set_state(AccessForm.waiting_for_role)


@router.callback_query(AccessForm.waiting_for_role, F.data.startswith("role:"))
async def process_role(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Handle role selection, create AccessRequest, notify admins.
    """
    if not callback.from_user:
        return

    role = callback.data.split("role:", maxsplit=1)[1]

    data = await state.get_data()
    await state.clear()

    user = callback.from_user

    gmail = data.get("gmail", "")
    phone = data.get("phone", "")
    full_name = data.get("full_name", "")

    req = AccessRequest(
        tg_id=user.id,
        telegram_username=f"@{user.username}" if user.username else None,
        full_name=full_name,
        phone=phone,
        gmail=gmail,
        role=role,
        status=AccessStatus.PENDING,
    )

    # Persist as pending
    access_storage.save_pending(req)

    # Notify user
    await callback.message.edit_text(
        f"✅ Your access request has been submitted.\n"
        f"Role: <b>{role}</b>\n"
        f"Admins will review it and you will receive a notification once a decision is made.",
        parse_mode="HTML",
    )

    # Notify admins
    admins = list(ADMINS)
    if not admins:
        logger.warning("No ADMINS configured, cannot send access request notifications.")
        await callback.answer()
        return

    text_for_admin = (
        "🆕 <b>New User Access Request</b>\n\n"
        f"<b>Name:</b> {req.full_name}\n"
        f"<b>Phone:</b> {req.phone}\n"
        f"<b>Gmail:</b> {req.gmail}\n"
        f"<b>Telegram:</b> {req.telegram_username or '—'}\n"
        f"<b>Role:</b> {req.role}\n"
        f"<b>User ID:</b> <code>{req.tg_id}</code>\n\n"
        "What would you like to do?"
    )
    kb = _admin_keyboard_for_user(req.tg_id)

    for admin_id in admins:
        try:
            await callback.message.bot.send_message(
                chat_id=admin_id,
                text=text_for_admin,
                reply_markup=kb,
                parse_mode="HTML",
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to send access request to admin %s: %s", admin_id, e)

    await callback.answer()


# =====================================================
#  Admin callbacks: approve / deny / cancel
# =====================================================


@router.callback_query(F.data.startswith("access:"))
async def handle_access_callback(callback: CallbackQuery) -> None:
    if not callback.from_user:
        return

    admin_id = callback.from_user.id
    if admin_id not in ADMINS:
        await callback.answer("You are not allowed to manage access.", show_alert=True)
        return

    try:
        _, action, user_id_str = (callback.data or "").split(":")
        target_user_id = int(user_id_str)
    except Exception:  # noqa: BLE001
        await callback.answer("Invalid data.", show_alert=True)
        return

    if action == "cancel":
        await callback.answer("Cancelled.", show_alert=False)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass
        return

    if action not in {"approve", "deny"}:
        await callback.answer("Unknown action.", show_alert=True)
        return

    new_status = AccessStatus.APPROVED if action == "approve" else AccessStatus.DENIED
    req = access_storage.update_status(
        tg_id=target_user_id,
        new_status=new_status,
        approved_by=admin_id,
    )

    if not req:
        await callback.answer("Request not found.", show_alert=True)
        return

    status_text = "✅ Access GRANTED" if new_status is AccessStatus.APPROVED else "❌ Access DENIED"

    # Update admin message
    try:
        original_text = callback.message.text or ""
        updated = f"{original_text}\n\n<b>{status_text}</b>\n<b>By:</b> @{callback.from_user.username or admin_id}"
        await callback.message.edit_text(updated, parse_mode="HTML")
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to edit admin message: %s", e)

    await callback.answer("Done.", show_alert=False)

    # Notify user
    try:
        if new_status is AccessStatus.APPROVED:
            await callback.message.bot.send_message(
                chat_id=target_user_id,
                text=(
                    "✅ Your access request has been <b>approved</b>.\n\n"
                    "Welcome to FleetMaster Bot. You can now use dispatcher features."
                ),
                parse_mode="HTML",
            )
        else:
            await callback.message.bot.send_message(
                chat_id=target_user_id,
                text=(
                    "❌ Your access request has been <b>rejected</b>.\n"
                    "If you think this is a mistake, please contact an admin."
                ),
                parse_mode="HTML",
            )
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to notify user %s about decision: %s", target_user_id, e)


# =====================================================
#  Help & main menu (protected)
# =====================================================


@router.callback_query(lambda c: c.data == "help")
async def cmd_help(callback: CallbackQuery) -> None:
    # Protect: only for users with access
    if not has_access(callback.from_user.id):
        await callback.answer(require_auth_message(), show_alert=True)
        return

    logger.info("User %s requested help", callback.from_user.id)

    help_text = """
❓ **FleetMaster Bot Help**

**Available Features**

🚛 **TRUCK INFORMATION**
• View all vehicles in your fleet  
• See VIN, plate number, year, name and odometer  

🔍 **Search**
• Search by vehicle name  
• Search by VIN  
• Search by license plate  

🚚 **PM SERVICES**
• View PM schedules and mileage  
• See overdue or upcoming PM  
• Filter urgent oil changes  

📂 **DOCUMENTS**
• Truck registrations and permits  
• Lease agreements  
• Annual inspections  

🗳 **TRAILER INFORMATION**
• Trailer registrations  
• Inspections  
• Quick access per unit

Use the buttons below to navigate.
    """.strip()

    try:
        await callback.message.edit_text(
            text=help_text,
            reply_markup=get_help_keyboard(),
            parse_mode="Markdown",
        )
        await callback.answer()
        logger.info("Help message shown to user %s", callback.from_user.id)
    except Exception as e:  # noqa: BLE001
        logger.error("Error showing help: %s", e)
        await callback.answer("❌ Error loading help", show_alert=True)


@router.callback_query(lambda c: c.data == "main_menu")
async def main_menu(callback: CallbackQuery) -> None:
    # Protect: only for users with access
    if not has_access(callback.from_user.id):
        await callback.answer(require_auth_message(), show_alert=True)
        return

    logger.info("User %s requested main menu", callback.from_user.id)

    main_menu_text = """
🏠 **Main Menu**

Choose what you want to do:

• 🚛 Truck information  
• 🚚 PM services  
• 📂 Truck documents  
• 🗳 Trailer information  
• ❓ Help
    """.strip()

    try:
        await callback.message.edit_text(
            text=main_menu_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown",
        )
        await callback.answer()
        logger.info("Main menu shown to user %s", callback.from_user.id)
    except Exception as e:  # noqa: BLE001
        logger.error("Error showing main menu: %s", e)
        await callback.answer("❌ Error loading main menu", show_alert=True)


# =====================================================
#  (Optional) Legacy text button for Documents
# =====================================================


@router.message(lambda m: m.text == "📂 Documents")
async def open_documents(message: Message) -> None:
    if not has_access(message.from_user.id):
        await message.answer(require_auth_message())
        return

    doc_intro = (
        "📂 **DOCUMENTS** — Fleet & Compliance Files\n\n"
        "Access key paperwork in one place:\n"
        "• Registrations and state permits\n"
        "• Lease agreements and annual inspections\n\n"
        "Select a document category below to view or download:"
    )
    await message.answer(doc_intro, reply_markup=documents_menu_kb(), parse_mode="Markdown")
