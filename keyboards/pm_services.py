import calendar
from datetime import datetime, timedelta
from typing import Any

import pytz
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

tz = pytz.timezone("Asia/Tashkent")


# =======================================
# MAIN PM MENU
# =======================================
def get_pm_services_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🔴 Urgent Oil Change", callback_data="pm_urgent"))
    b.add(InlineKeyboardButton(text="🟡 Oil Change", callback_data="pm_oil"))
    b.add(InlineKeyboardButton(text="🚛 Show All Vehicles", callback_data="pm_all"))
    b.add(InlineKeyboardButton(text="🔍 Search by Unit", callback_data="pm_search"))
    b.add(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    b.adjust(1)
    return b.as_markup()


# =======================================
# SEARCH MENU
# =======================================
def get_pm_search_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🔙 Back to PM Menu", callback_data="pm_services"))
    b.adjust(1)
    return b.as_markup()


# =======================================
# PAGINATED VEHICLE LIST
# =======================================
def get_pm_vehicles_keyboard(
    vehicles: list[dict[str, Any]],
    page: int = 1,
    per_page: int = 10,
    back_callback: str = "pm_services",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    start = (page - 1) * per_page
    items = vehicles[start : start + per_page]
    total_pages = (len(vehicles) + per_page - 1) // per_page

    for v in items:
        vid = v.get("id", "")
        b.row(InlineKeyboardButton(text=str(vid), callback_data=f"pm_sheet_vehicle:{vid}"))

    if total_pages > 1:
        row = []
        if page > 1:
            row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"pm_all:{page - 1}"))
        row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="pm_page_info"))
        if page < total_pages:
            row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"pm_all:{page + 1}"))
        b.row(*row)

    b.row(InlineKeyboardButton(text="🔙 Back to PM Services", callback_data=back_callback))
    return b.as_markup()


# =======================================
# VEHICLE DETAILS MENU
# =======================================
def get_pm_vehicle_details_keyboard(
    truck_id: str,
    page: int = 1,
    is_admin: bool = False,
    chat_type: str = "private",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(
        InlineKeyboardButton(text="🔄 Refresh", callback_data=f"pm_sheet_vehicle:{truck_id}:{page}")
    )
    if is_admin and chat_type == "private":
        b.add(
            InlineKeyboardButton(text="📤 Send to Group", callback_data=f"pm_send_group:{truck_id}")
        )
    b.add(InlineKeyboardButton(text="🔙 Back to Vehicle List", callback_data=f"pm_all:{page}"))
    b.add(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    b.adjust(1)
    return b.as_markup()


# =======================================
# URGENT / OIL LIST MENU (with timer control)
# =======================================
def urgent_oil_list_keyboard(
    list_type: str,
    is_admin: bool = False,
    chat_type: str = "private",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if is_admin and chat_type == "private":
        b.row(
            InlineKeyboardButton(
                text="📤 Send List to Each Group", callback_data=f"pm_send_list:{list_type}"
            ),
            InlineKeyboardButton(
                text="⏰ Schedule Timer", callback_data=f"pm_timer_start:{list_type}"
            ),
        )
        b.row(
            InlineKeyboardButton(text="🕐 View Timers", callback_data="pm_timer_view"),
            InlineKeyboardButton(text="🛑 Stop Timers", callback_data=f"pm_timer_stop:{list_type}"),
        )
    b.row(InlineKeyboardButton(text="🔙 Back to PM Menu", callback_data="pm_services"))
    b.adjust(1)
    return b.as_markup()


# =======================================
# INLINE CALENDAR (MONTH VIEW)
# =======================================
def get_calendar_keyboard(year=None, month=None) -> InlineKeyboardMarkup:
    now = datetime.now(tz)
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    b = InlineKeyboardBuilder()
    cal = calendar.monthcalendar(year, month)
    month_name = datetime(year, month, 1).strftime("%B %Y")

    # Month header
    b.row(InlineKeyboardButton(text=f"📅 {month_name}", callback_data="noop"))

    # Weekday headers
    weekdays = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    b.row(*[InlineKeyboardButton(text=d, callback_data="noop") for d in weekdays])

    # Calendar days
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                row.append(
                    InlineKeyboardButton(text=str(day), callback_data=f"pick_date:{date_str}")
                )
        b.row(*row)

    # Navigation buttons
    prev_month = (datetime(year, month, 15) - timedelta(days=31)).replace(day=1)
    next_month = (datetime(year, month, 15) + timedelta(days=31)).replace(day=1)
    b.row(
        InlineKeyboardButton(
            text="⬅️ Prev", callback_data=f"cal_prev:{prev_month.year}:{prev_month.month}"
        ),
        InlineKeyboardButton(
            text="➡️ Next", callback_data=f"cal_next:{next_month.year}:{next_month.month}"
        ),
    )

    return b.as_markup()


# =======================================
# INLINE MINUTE PICKER (new)
# =======================================
def get_minute_picker_keyboard(selected_hour: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()

    b.row(InlineKeyboardButton(text=f"🕓 Hour: {selected_hour:02d}", callback_data="noop"))
    b.row(
        InlineKeyboardButton(text="00", callback_data=f"pick_time:{selected_hour}:00"),
        InlineKeyboardButton(text="15", callback_data=f"pick_time:{selected_hour}:15"),
        InlineKeyboardButton(text="30", callback_data=f"pick_time:{selected_hour}:30"),
        InlineKeyboardButton(text="45", callback_data=f"pick_time:{selected_hour}:45"),
    )
    b.row(
        InlineKeyboardButton(text="✏️ Custom Minute", callback_data=f"custom_minute:{selected_hour}")
    )
    return b.as_markup()


# =======================================
# INLINE TIME PICKER (hours + custom)
# =======================================
def get_time_picker_keyboard(mode: str = "hour") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()

    if mode == "hour":
        b.row(InlineKeyboardButton(text="🕐 Choose Hour", callback_data="noop"))
        for h in range(0, 24, 4):
            row = []
            for i in range(4):
                val = h + i
                if val < 24:
                    row.append(
                        InlineKeyboardButton(text=f"{val:02d}:00", callback_data=f"pick_hour:{val}")
                    )
            b.row(*row)
        b.row(InlineKeyboardButton(text="✏️ Enter Custom Hour (HH:MM)", callback_data="custom_hour"))

    return b.as_markup()
