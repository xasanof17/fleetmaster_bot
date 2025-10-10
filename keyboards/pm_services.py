# keyboards/pm_services.py
from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_pm_services_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🔴 Urgent Oil Change", callback_data="pm_urgent"))
    b.add(InlineKeyboardButton(text="🟡 Oil Change", callback_data="pm_oil"))
    b.add(InlineKeyboardButton(text="🚛 Show All Vehicles", callback_data="pm_all"))
    b.add(InlineKeyboardButton(text="🔍 Search by Unit", callback_data="pm_search"))
    b.add(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    b.adjust(1)
    return b.as_markup()

def get_pm_search_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🔙 Back to PM Menu", callback_data="pm_services"))
    b.adjust(1)
    return b.as_markup()

def get_pm_vehicles_keyboard(
    vehicles: List[Dict[str, Any]],
    page: int = 1,
    per_page: int = 10,
    back_callback: str = "pm_services",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    start = (page - 1) * per_page
    items = vehicles[start:start + per_page]
    total_pages = (len(vehicles) + per_page - 1) // per_page

    for v in items:
        vid = v.get("id", "")
        b.row(InlineKeyboardButton(text=str(vid), callback_data=f"pm_sheet_vehicle:{vid}"))

    if total_pages > 1:
        row = []
        if page > 1:
            row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"pm_all:{page-1}"))
        row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="pm_page_info"))
        if page < total_pages:
            row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"pm_all:{page+1}"))
        b.row(*row)

    b.row(InlineKeyboardButton(text="🔙 Back to PM Services", callback_data=back_callback))
    return b.as_markup()

def get_pm_vehicle_details_keyboard(
    truck_id: str,
    page: int = 1,
    is_admin: bool = False,
    chat_type: str = "private",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🔄 Refresh", callback_data=f"pm_sheet_vehicle:{truck_id}:{page}"))
    if is_admin and chat_type == "private":
        b.add(InlineKeyboardButton(text="📤 Send to Group", callback_data=f"pm_send_group:{truck_id}"))
    b.add(InlineKeyboardButton(text="🔙 Back to Vehicle List", callback_data=f"pm_all:{page}"))
    b.add(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    b.adjust(1)
    return b.as_markup()

def urgent_oil_list_keyboard(
    list_type: str,
    is_admin: bool = False,
    chat_type: str = "private",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if is_admin and chat_type == "private":
        b.add(InlineKeyboardButton(
            text="📤 Send list to each group",
            callback_data=f"pm_send_list:{list_type}"
        ))
    b.add(InlineKeyboardButton(text="🔙 Back to PM Menu", callback_data="pm_services"))
    b.adjust(1)
    return b.as_markup()
