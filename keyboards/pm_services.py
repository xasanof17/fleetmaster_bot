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
    per_page: int = 5,
    back_callback: str = "pm_services",
) -> InlineKeyboardMarkup:
    """
    Paginated list of trucks.
    Only the unit number is displayed.
    """
    b = InlineKeyboardBuilder()
    start = (page - 1) * per_page
    page_items = vehicles[start:start + per_page]
    total_pages = (len(vehicles) + per_page - 1) // per_page

    for v in page_items:
        vid = v.get("id", "")
        b.add(
            InlineKeyboardButton(
                text=f"Truck {vid}",
                callback_data=f"pm_sheet_vehicle:{vid}"
            )
        )

    # Pagination controls
    if total_pages > 1:
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"pm_all:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="pm_page_info"))
        if page < total_pages:
            nav.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"pm_all:{page+1}"))
        for btn in nav:
            b.add(btn)
        b.adjust(*([1] * len(page_items) + [len(nav)]))
    else:
        b.adjust(1)

    b.add(InlineKeyboardButton(text="🔙 Back to PM Menu", callback_data=back_callback))
    return b.as_markup()


def get_pm_vehicle_details_keyboard(vehicle_id: str) -> InlineKeyboardMarkup:
    """Keyboard for a single truck’s detail view."""
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🔄 Refresh", callback_data=f"pm_sheet_vehicle:{vehicle_id}"))
    b.add(InlineKeyboardButton(text="🔙 Back to PM Services", callback_data="pm_services"))
    b.add(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    b.adjust(1)
    return b.as_markup()
