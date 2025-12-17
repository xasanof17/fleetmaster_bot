"""
keyboards/admin.py
FleetMaster — Administrative Keyboards
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_admin_approval_kb(user_id: int) -> InlineKeyboardMarkup:
    """
    Inline buttons for the Admin to Approve or Reject a user request.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Approve Access", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{user_id}"),
            ]
        ]
    )
