from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_documents_vehicle_keyboard(
    vehicles: list[dict[str, Any]], doc_type: str, page: int = 1, per_page: int = 5
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    start = (page - 1) * per_page
    page_items = vehicles[start : start + per_page]
    total_pages = (len(vehicles) + per_page - 1) // per_page

    for i, v in enumerate(page_items):
        # truck_id = v.get("id", "")
        name = v.get("name", f"Vehicle {start + i + 1}")
        plate = v.get("licensePlate", "No plate")
        text = f"{name} ({plate})"
        # 👇 callback_data encodes doc_type + truck
        b.add(InlineKeyboardButton(text=text[:50], callback_data=f"docs:{doc_type}:truck:{name}"))

    # Pagination row
    if total_pages > 1:
        row = []
        if page > 1:
            row.append(
                InlineKeyboardButton(
                    text="⬅️ Previous", callback_data=f"docs:{doc_type}:page:{page - 1}"
                )
            )
        row.append(
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="docs_page_info")
        )
        if page < total_pages:
            row.append(
                InlineKeyboardButton(
                    text="Next ➡️", callback_data=f"docs:{doc_type}:page:{page + 1}"
                )
            )
        for btn in row:
            b.add(btn)
        b.adjust(*([1] * len(page_items) + [len(row)]))
    else:
        b.adjust(1)

    b.add(InlineKeyboardButton(text="🔙 Back to Documents", callback_data="documents"))
    return b.as_markup()


def documents_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(
        InlineKeyboardButton(text="📄 Registrations 2026", callback_data="docs:registrations_2026")
    )
    b.add(InlineKeyboardButton(text="🪪 New Mexico Permission", callback_data="docs:new_mexico"))
    b.add(InlineKeyboardButton(text="📑 Lease Agreements", callback_data="docs:lease"))
    b.add(
        InlineKeyboardButton(text="🛠 Annual Inspection 2025", callback_data="docs:inspection_2025")
    )
    b.add(InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="main_menu"))
    b.adjust(1)
    return b.as_markup()


def vehicles_kb(vehicles: list[str], doc_type: str):
    # 2 per row
    rows = []
    row = []
    for i, v in enumerate(vehicles, 1):
        row.append(InlineKeyboardButton(text=v, callback_data=f"docs:{doc_type}:{v}"))
        if i % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_send_group_keyboard(truck_unit: str) -> InlineKeyboardMarkup:
    """Keyboard shown below the document message."""
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="📤 Send to Group", callback_data=f"send_group:{truck_unit}"))
    b.add(InlineKeyboardButton(text="🔙 Back to Documents", callback_data="documents"))
    b.adjust(1)
    return b.as_markup()
