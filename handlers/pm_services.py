"""
handlers/pm_services.py
PM Services section: read-only Google Sheet integration
- Urgent & Oil Change lists in pinned-message style
- Search by Unit (text or /slash)
- Show all PM rows
"""
from typing import Dict, Any, List
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from services import google_pm_service
from utils import get_logger, format_pm_vehicle_info
from keyboards.pm_services import (
    get_pm_services_menu,
    get_pm_vehicles_keyboard,
    get_pm_vehicle_details_keyboard,
    get_pm_search_keyboard,
)

logger = get_logger(__name__)
router = Router()

# ---------- Helpers ----------
def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k.lower().replace(" ", "").replace("\n", ""): v for k, v in row.items()}

def _vehicle_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    n = _normalize_row(row)
    truck = str(n.get("trucknumber") or n.get("truck") or "").strip()
    return {"id": truck, "name": f"Truck {truck}"}

def _build_template(rows: List[Dict[str, Any]], title: str, icon: str) -> str:
    """
    Build the pinned-message style block.
    Every line starts with /<truck> so Telegram treats it as a command link.
    """
    lines = [
        f"{title.upper()}",
        f"UPDATED: {datetime.now():%m/%d/%Y}",
        "=" * 34,
    ]
    for r in rows:
        truck = str(r.get("truck"))
        left  = r.get("left", 0)
        lines.append(f"/{truck} – {title} {icon} {left:,}")
    lines.append("=" * 34)
    return "\n".join(lines)

# ---------- Main menu ----------
@router.callback_query(F.data == "pm_services")
async def pm_services_menu(cb: CallbackQuery):
    """Enhanced intro text for PM Services menu."""
    intro = (
        "🛠 **PM SERVICES** – Preventive Maintenance & Service Center\n\n"
        "Stay ahead of breakdowns and keep your fleet healthy.\n\n"
        "Available Options:\n"
        "🔴 **Urgent Oil Change** – Trucks needing immediate attention\n"
        "🟡 **Oil Change** – Scheduled routine service\n"
        "🚛 **Show All Vehicles** – Browse every truck’s service status\n"
        "🔍 **Search by Unit** – Find a specific truck’s PM record\n\n"
        "Select an option to continue:"
    )
    await cb.message.edit_text(
        intro,
        reply_markup=get_pm_services_menu(),
        parse_mode="Markdown"
    )

# ---------- Urgent ----------
@router.callback_query(F.data == "pm_urgent")
async def urgent_list(cb: CallbackQuery):
    rows = await google_pm_service.get_urgent_list()
    # Only those actually marked urgent (skip “Good”, skip broken)
    urgent_only = [
        r for r in rows
        if str(r.get("status", "")).lower().startswith("urgent")
    ]
    if not urgent_only:
        await cb.message.answer("🚨 No trucks currently marked as *Urgent oil change*.", parse_mode="Markdown")
        return
    text = _build_template(urgent_only, "Urgent oil change", "📌")
    await cb.message.answer(text, parse_mode="Markdown")

# ---------- Oil Change ----------
@router.callback_query(F.data == "pm_oil")
async def oil_change_list(cb: CallbackQuery):
    rows = await google_pm_service.get_oil_list()
    oil_only = [
        r for r in rows
        if str(r.get("status", "")).lower().startswith("oil")
    ]
    if not oil_only:
        await cb.message.answer("🟡 No trucks currently scheduled for a regular oil change.")
        return
    text = _build_template(oil_only, "Oil change", "🟡")
    await cb.message.answer(text, parse_mode="Markdown")

# ---------- Show All ----------
@router.callback_query(F.data.startswith("pm_all"))
async def show_all(cb: CallbackQuery):
    page = int(cb.data.split(":")[1]) if ":" in cb.data else 1
    rows, _ = await google_pm_service.get_all(page)
    vehicles = [_vehicle_dict(r) for r in rows]
    await cb.message.edit_text(
        f"🚛 PM Sheet Vehicles ({len(vehicles)} shown)",
        reply_markup=get_pm_vehicles_keyboard(vehicles, page=page, per_page=5),
    )

# ---------- Search by Unit ----------
@router.callback_query(F.data == "pm_search")
async def pm_search_start(cb: CallbackQuery):
    await cb.message.edit_text(
        "🔍 *Search by Unit*\n\nSend the truck/unit number as a message.",
        reply_markup=get_pm_search_keyboard(),
        parse_mode="Markdown"
    )

@router.message(F.text.regexp(r"^\d+$"))
async def pm_search_result(msg: Message):
    unit = msg.text.strip()
    details = await google_pm_service.get_vehicle_details(unit)
    if not details:
        await msg.answer(
            f"❌ Truck {unit} not found in the PM sheet.",
            reply_markup=get_pm_services_menu()
        )
        return
    text = format_pm_vehicle_info(details, full=True)
    await msg.answer(text, reply_markup=get_pm_vehicle_details_keyboard(unit))

# ---------- Slash-command style /<unit> ----------
@router.message(F.text.regexp(r"^/\d+$"))
async def pm_search_slash(msg: Message):
    unit = msg.text.lstrip("/")
    details = await google_pm_service.get_vehicle_details(unit)
    if not details:
        await msg.answer(
            f"❌ Truck {unit} not found in the PM sheet.",
            reply_markup=get_pm_services_menu()
        )
        return
    text = format_pm_vehicle_info(details, full=True)
    await msg.answer(text, reply_markup=get_pm_vehicle_details_keyboard(unit))

# ---------- Inline button detail ----------
@router.callback_query(F.data.startswith("pm_sheet_vehicle:"))
async def vehicle_detail(cb: CallbackQuery):
    truck = cb.data.split(":")[1]
    details = await google_pm_service.get_vehicle_details(truck)
    if not details:
        await cb.answer("Vehicle not found in PM sheet.", show_alert=True)
        return
    text = format_pm_vehicle_info(details, full=True)
    await cb.message.edit_text(
        text,
        reply_markup=get_pm_vehicle_details_keyboard(truck)
    )
