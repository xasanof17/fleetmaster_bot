# handlers/admin/callbacks.py

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from services.access_control import access_storage, AccessStatus
from config import settings

router = Router()
ADMINS = set(settings.ADMINS or [])


def is_admin(uid: int) -> bool:
    return uid in ADMINS


# ======================================================
# SEARCH UI
# ======================================================

@router.callback_query(F.data == "admin:search")
async def search_prompt(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Not allowed")

    await callback.message.edit_text(
        "🔍 Send the <b>User ID</b> or <b>Full Name</b> to search:",
        parse_mode="HTML",
    )
    await callback.answer()

    # Set manual mode
    # ⚠️ Bitta bot instance uchun flag — dev mode uchun normal.
    callback.message.bot.admin_search_mode = True


@router.message()
async def search_input(message: Message):
    # Faqat adminlarga allow qilamiz va faqat search_mode true bo‘lsa
    if not getattr(message.bot, "admin_search_mode", False):
        return

    if not is_admin(message.from_user.id):
        return

    query = (message.text or "").strip().lower()
    results = []

    users = (
        access_storage.list_pending()
        + access_storage.list_approved()
        + access_storage.list_denied()
    )

    for u in users:
        if query in str(u.tg_id) or query in u.full_name.lower():
            results.append(u)

    # Turn off search mode (bir marta ishlaydi)
    message.bot.admin_search_mode = False

    if not results:
        await message.answer("❌ No matches found.")
        return

    for req in results:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Approve", callback_data=f"adminact:approve:{req.tg_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Deny", callback_data=f"adminact:deny:{req.tg_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🗑 Delete", callback_data=f"adminact:delete:{req.tg_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="♻ Change Role", callback_data=f"adminact:role:{req.tg_id}"
                    )
                ],
            ]
        )

        text = (
            f"<b>User:</b> {req.full_name}\n"
            f"ID: {req.tg_id}\n"
            f"Phone: {req.phone}\n"
            f"Gmail: {req.gmail}\n"
            f"Role: {req.role}\n"
            f"Status: {req.status.value}"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
