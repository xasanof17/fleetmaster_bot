# keyboards/pm_trucker.py (FIXED WITH PROPER PAGINATION)
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_pm_trucker_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="⚡️ Statuses List", callback_data="pm_view_all_statuses"))
    b.add(InlineKeyboardButton(text="🚛 View All Vehicles", callback_data="pm_view_all_vehicles"))
    b.add(InlineKeyboardButton(text="🔍 Search Vehicle", callback_data="pm_search_vehicle"))
    b.add(InlineKeyboardButton(text="🔄 Refresh Data", callback_data="pm_refresh_cache"))
    b.add(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    b.adjust(1)
    return b.as_markup()


def get_back_to_pm_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="🔙 Back to TRUCK INFORMATION", callback_data="pm_trucker"))
    return b.as_markup()


def get_vehicles_list_keyboard(
    vehicles: list[dict[str, Any]], page: int = 1, per_page: int = 10
) -> InlineKeyboardMarkup:
    """
    FIXED: Proper pagination with 10 vehicles per page
    """
    b = InlineKeyboardBuilder()

    # Calculate pagination
    start = (page - 1) * per_page
    end = start + per_page
    page_items = vehicles[start:end]
    total_pages = (len(vehicles) + per_page - 1) // per_page

    # Add vehicle buttons
    for v in page_items:
        vid = v.get("id", "")
        name = v.get("name", "Unknown")
        plate = v.get("licensePlate", "No plate")

        # Create button text
        text = f"{name} ({plate})"
        b.add(InlineKeyboardButton(text=text[:50], callback_data=f"pm_vehicle_details:{vid}"))

    # Add pagination row if needed
    if total_pages > 1:
        row = []
        if page > 1:
            row.append(
                InlineKeyboardButton(
                    text="⬅️ Previous", callback_data=f"pm_vehicles_page:{page - 1}"
                )
            )
        row.append(
            InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="pm_page_info")
        )
        if page < total_pages:
            row.append(
                InlineKeyboardButton(text="Next ➡️", callback_data=f"pm_vehicles_page:{page + 1}")
            )

        # Add all vehicle buttons first, then pagination row
        b.adjust(*([1] * len(page_items)))
        for btn in row:
            b.add(btn)
    else:
        b.adjust(1)

    # Add back button
    b.add(InlineKeyboardButton(text="🔙 Back to TRUCK INFORMATION", callback_data="pm_trucker"))

    return b.as_markup()


def get_vehicle_details_keyboard(
    vehicle_id: str, vehicle_name: str | None = None
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(
        InlineKeyboardButton(
            text="📍 Current Location", callback_data=f"pm_vehicle_location:{vehicle_id}"
        )
    )
    safe_name = (vehicle_name or "").replace(":", "_").replace("|", "_")[:40]
    b.add(
        InlineKeyboardButton(
            text="📄 Driver Information", callback_data=f"pm_vehicle_reg:{safe_name or 'unknown'}"
        )
    )
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
    b.add(InlineKeyboardButton(text="🔎 Search All Fields", callback_data="pm_search_by:all"))
    b.add(InlineKeyboardButton(text="🔙 Back to TRUCK INFORMATION", callback_data="pm_trucker"))
    b.adjust(1)
    return b.as_markup()


def get_search_results_keyboard(
    results: list[dict[str, Any]],
    search_query: str,
    search_type: str,
    page: int = 1,
    per_page: int = 10,
) -> InlineKeyboardMarkup:
    """
    Keyboard for search results with pagination
    """
    # Just reuse the vehicles list keyboard since it's the same format
    return get_vehicles_list_keyboard(results, page=page, per_page=per_page)
