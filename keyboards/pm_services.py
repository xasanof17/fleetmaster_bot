"""
keyboards/pm_services.py
Inline keyboards dedicated to the PM Services section.
"""
from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_pm_services_menu() -> InlineKeyboardMarkup:
    """Main PM Services menu."""
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🔴 Urgent Oil Change", callback_data="pm_urgent"))
    b.add(InlineKeyboardButton(text="🟡 Oil Change", callback_data="pm_oil"))
    b.add(InlineKeyboardButton(text="🚛 Show All Vehicles", callback_data="pm_all"))
    b.add(InlineKeyboardButton(text="🔍 Search by Unit", callback_data="pm_search"))
    b.add(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    b.adjust(1)
    return b.as_markup()


def get_pm_search_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown while waiting for a unit number."""
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
    """
    Paginated list of trucks where each truck button spans the full width.
    """
    b = InlineKeyboardBuilder()
    start = (page - 1) * per_page
    page_items = vehicles[start:start + per_page]
    total_pages = (len(vehicles) + per_page - 1) // per_page

    # 🚛 one full-width button per vehicle
    for v in page_items:
        vid = v.get("id", "")
        b.row(
            InlineKeyboardButton(
                text=str(vid),
                callback_data=f"pm_sheet_vehicle:{vid}"
            )
        )

    # ⏮️ navigation row
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"pm_all:{page-1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="pm_page_info"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"pm_all:{page+1}"))
        # all nav buttons in a single row
        b.row(*nav_buttons)

    # 🔙 back button full width
    b.row(InlineKeyboardButton(text="🔙 Back to PM Services", callback_data=back_callback))

    return b.as_markup()


def get_pm_vehicle_details_keyboard(truck_id: str, page: int = 1) -> InlineKeyboardMarkup:
    """Keyboard for a single truck detail view."""
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🔄 Refresh", callback_data=f"pm_sheet_vehicle:{truck_id}:{page}"))
    b.add(InlineKeyboardButton(text="📤 Send to Group", callback_data=f"pm_send_group:{truck_id}"))
    b.add(InlineKeyboardButton(text="🔙 Back to Vehicle List", callback_data=f"pm_all:{page}"))
    b.add(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    b.adjust(1)
    return b.as_markup()

# 🆕 NEW: keyboards for the Urgent/Oil lists with broadcast button
def urgent_oil_list_keyboard(list_type: str) -> InlineKeyboardMarkup:
    """
    Inline keyboard shown under the Urgent or Oil Change list
    list_type must be 'urgent' or 'oil'
    """
    b = InlineKeyboardBuilder()
    # broadcast button sends each truck’s line to its own group
    b.add(InlineKeyboardButton(
        text="📤 Send list to each group",
        callback_data=f"pm_send_list:{list_type}"
    ))
    b.add(InlineKeyboardButton(
        text="🔙 Back to PM Menu",
        callback_data="pm_services"
    ))
    b.adjust(1)
    return b.as_markup()
