from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_pm_trucker_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🚛 View All Vehicles", callback_data="pm_view_all_vehicles"))
    b.add(InlineKeyboardButton(text="🔍 Search Vehicle", callback_data="pm_search_vehicle"))
    b.add(InlineKeyboardButton(text="🔄 Refresh Data", callback_data="pm_refresh_cache"))
    b.add(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    b.adjust(1)
    return b.as_markup()


def get_back_to_pm_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🔙 Back to PM TRUCKER", callback_data="pm_trucker"))
    return b.as_markup()


def get_vehicles_list_keyboard(vehicles: List[Dict[str, Any]], page: int = 1, per_page: int = 5) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    start = (page - 1) * per_page
    page_items = vehicles[start:start + per_page]
    total_pages = (len(vehicles) + per_page - 1) // per_page
    for i, v in enumerate(page_items):
        vid = v.get("id", "")
        name = v.get("name", f"Vehicle {start + i + 1}")
        plate = v.get("licensePlate", "No plate")
        # engine = v.get("engineState", "Unknown")
        # status = "🟢" if engine == "Running" else ("🔴" if engine == "Off" else "🟡")
        text = f"{name} ({plate})"
        b.add(InlineKeyboardButton(text=text[:50], callback_data=f"pm_vehicle_details:{vid}"))

    if total_pages > 1:
        row = []
        if page > 1:
            row.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"pm_vehicles_page:{page-1}"))
        row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="pm_page_info"))
        if page < total_pages:
            row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"pm_vehicles_page:{page+1}"))
        for btn in row:
            b.add(btn)
        b.adjust(*([1] * len(page_items) + [len(row)]))
    else:
        b.adjust(1)

    b.add(InlineKeyboardButton(text="🔙 Back to PM TRUCKER", callback_data="pm_trucker"))
    return b.as_markup()


def get_vehicle_details_keyboard(vehicle_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="📍 Current Location", callback_data=f"pm_vehicle_location:{vehicle_id}"))
    b.add(InlineKeyboardButton(text="📊 Statistics", callback_data=f"pm_vehicle_stats:{vehicle_id}"))
    b.add(InlineKeyboardButton(text="🔄 Refresh", callback_data=f"pm_vehicle_details:{vehicle_id}"))
    b.add(InlineKeyboardButton(text="🔙 Back to Vehicles", callback_data="pm_view_all_vehicles"))
    b.add(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    b.adjust(1)
    return b.as_markup()


def get_search_options_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🏷️ Search by Name", callback_data="pm_search_by:name"))
    b.add(InlineKeyboardButton(text="🔢 Search by VIN", callback_data="pm_search_by:vin"))
    b.add(InlineKeyboardButton(text="🚗 Search by Plate", callback_data="pm_search_by:plate"))
    b.add(InlineKeyboardButton(text="🔍 Search All Fields", callback_data="pm_search_by:all"))
    b.add(InlineKeyboardButton(text="🔙 Back to PM TRUCKER", callback_data="pm_trucker"))
    b.adjust(1)
    return b.as_markup()


def get_search_results_keyboard(results: List[Dict[str, Any]], search_query: str, search_type: str, page: int = 1, per_page: int = 5) -> InlineKeyboardMarkup:
    # Build keyboard similar to vehicles list but for search results
    return get_vehicles_list_keyboard(results, page=page, per_page=per_page)
