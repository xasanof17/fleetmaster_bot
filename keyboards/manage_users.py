from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def manage_users_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(
            text="⏳ Pending Users",
            callback_data="manage_users_pending",
        )
    )
    builder.add(
        InlineKeyboardButton(
            text="👥 All Users",
            callback_data="manage_users_all",
        )
    )
    builder.add(
        InlineKeyboardButton(
            text="⬅️ Back",
            callback_data="main_menu",
        )
    )

    builder.adjust(1)
    return builder.as_markup()


def users_list_kb(users: list[dict], prefix: str) -> InlineKeyboardMarkup:
    """
    prefix example:
    - pending_user
    - all_user
    """
    builder = InlineKeyboardBuilder()

    for u in users:
        label = f"👤 {u['full_name']}" + (f" (@{u['nickname']})" if u.get("nickname") else "")

        builder.add(
            InlineKeyboardButton(
                text=label,
                callback_data=f"{prefix}:{u['user_id']}",
            )
        )

    builder.add(
        InlineKeyboardButton(
            text="⬅️ Back",
            callback_data="admin_manage_users",
        )
    )

    builder.adjust(1)
    return builder.as_markup()


def user_action_kb(user_id: int, active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(
            text="✅ Approve",
            callback_data=f"user_approve:{user_id}",
        )
    )

    if active:
        builder.add(
            InlineKeyboardButton(
                text="🚫 Disable",
                callback_data=f"user_disable:{user_id}",
            )
        )
    else:
        builder.add(
            InlineKeyboardButton(
                text="♻️ Enable",
                callback_data=f"user_enable:{user_id}",
            )
        )

    builder.add(
        InlineKeyboardButton(
            text="⬅️ Back",
            callback_data="admin_manage_users",
        )
    )

    builder.adjust(2, 1)
    return builder.as_markup()


def pagination_kb(prefix: str, page: int, has_next: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()

    if page > 0:
        b.add(
            InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=f"{prefix}:page:{page - 1}",
            )
        )

    if has_next:
        b.add(
            InlineKeyboardButton(
                text="➡️ Next",
                callback_data=f"{prefix}:page:{page + 1}",
            )
        )

    b.add(
        InlineKeyboardButton(
            text="⬅️ Back",
            callback_data="admin_manage_users",
        )
    )

    b.adjust(2, 1)
    return b.as_markup()
