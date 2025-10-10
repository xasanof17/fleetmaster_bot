"""
handlers/pm_services.py
PM Services section: read-only Google Sheet integration
- Urgent & Oil Change lists (admin broadcast restricted)
- FSM-based Search by Unit
- Show all PM rows
- Config-driven private/group restriction (silent ignore)
"""

from typing import Dict, Any, List
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from services import google_pm_service
from services.group_map import get_group_id_for_unit
from utils import get_logger, format_pm_vehicle_info
from keyboards.pm_services import (
    get_pm_services_menu,
    get_pm_vehicles_keyboard,
    get_pm_vehicle_details_keyboard,
    get_pm_search_keyboard,
    urgent_oil_list_keyboard,
)
from config.settings import settings


# ────────────────────────────────
# CONFIG
# ────────────────────────────────
logger = get_logger(__name__)
router = Router()

# ✅ Safe Admin Load
try:
    ADMINS = set(settings.ADMINS)
    logger.info(f"Loaded admins: {ADMINS}")
except Exception as e:
    ADMINS = set()
    logger.warning(f"Failed to load ADMINS from settings: {e}")

# ✅ Group Permission Setting
ALLOW_GROUPS = getattr(settings, "ALLOW_GROUPS", False)
ALLOWED_CHAT_TYPES = {"private"} if not ALLOW_GROUPS else {"private", "group", "supergroup"}
logger.info(f"Group access allowed: {ALLOW_GROUPS}")


# ────────────────────────────────
# FSM for Search-by-Unit
# ────────────────────────────────
class PMSearchState(StatesGroup):
    waiting_for_unit = State()


def _build_template(rows: List[Dict[str, Any]], title: str, icon: str) -> str:
    """Build the pinned-message style block."""
    lines = [
        f"{title.upper()}",
        f"UPDATED: {datetime.now():%m/%d/%Y}",
        "=" * 27,
    ]
    for r in rows:
        truck = str(r.get("truck"))
        left = r.get("left", 0)
        lines.append(f"/{truck} – {title} {icon} {left:,}")
    lines.append("=" * 27)
    return "\n".join(lines)


# ────────────────────────────────
# Main Menu
# ────────────────────────────────
@router.callback_query(F.data == "pm_services")
async def pm_services_menu(cb: CallbackQuery):
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
        parse_mode="Markdown",
    )


# ────────────────────────────────
# Urgent List (Admin-limited Broadcast)
# ────────────────────────────────
@router.callback_query(F.data == "pm_urgent")
async def urgent_list(cb: CallbackQuery):
    await cb.answer("⚡ Loading urgent list...")
    rows = await google_pm_service.get_urgent_list()
    urgent_only = [r for r in rows if str(r.get("status", "")).lower().startswith("urgent")]

    if not urgent_only:
        await cb.message.answer("🚨 No trucks currently marked as *Urgent oil change*.", parse_mode="Markdown")
        return

    text = _build_template(urgent_only, "Urgent oil change", "📌")
    markup = urgent_oil_list_keyboard("urgent") if cb.from_user.id in ADMINS else get_pm_services_menu()
    await cb.message.answer(text, reply_markup=markup, parse_mode="Markdown")


# ────────────────────────────────
# Oil Change List
# ────────────────────────────────
@router.callback_query(F.data == "pm_oil")
async def oil_change_list(cb: CallbackQuery):
    await cb.answer("⚡ Loading oil change list...")
    rows = await google_pm_service.get_oil_list()
    oil_only = [r for r in rows if str(r.get("status", "")).lower().startswith("oil")]

    if not oil_only:
        await cb.message.answer("🟡 No trucks currently scheduled for a regular oil change.")
        return

    text = _build_template(oil_only, "Oil change", "🟡")
    markup = urgent_oil_list_keyboard("oil") if cb.from_user.id in ADMINS else get_pm_services_menu()
    await cb.message.answer(text, reply_markup=markup, parse_mode="Markdown")


# ────────────────────────────────
# Broadcast Handler
# ────────────────────────────────
@router.callback_query(F.data.startswith("pm_send_list:"))
async def send_list_to_groups(cb: CallbackQuery):
    """Admin-only broadcast of urgent/oil lists to each truck group."""
    if cb.from_user.id not in ADMINS:
        await cb.answer("🚫 Only admins can send broadcasts.", show_alert=True)
        return

    list_type = cb.data.split(":")[1]
    await cb.answer("📡 Sending to groups…")

    rows = (
        await google_pm_service.get_urgent_list()
        if list_type == "urgent"
        else await google_pm_service.get_oil_list()
    )

    if list_type == "urgent":
        rows = [r for r in rows if str(r.get("status", "")).lower().startswith("urgent")]
        icon, title = "📌", "Urgent oil change"
    else:
        rows = [r for r in rows if str(r.get("status", "")).lower().startswith("oil")]
        icon, title = "🟡", "Oil change"

    sent_count, skipped = 0, 0
    for r in rows:
        truck = str(r.get("truck"))
        left = r.get("left", 0)
        group_id = get_group_id_for_unit(truck)
        if not group_id:
            skipped += 1
            continue
        line = f"{truck} – {title} {icon} {left:,}"
        try:
            await cb.bot.send_message(chat_id=int(group_id), text=line)
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send {truck} to {group_id}: {e}")
            skipped += 1

    await cb.message.answer(f"✅ Sent {sent_count} messages. Skipped {skipped}.")


# ────────────────────────────────
# Show All
# ────────────────────────────────
@router.callback_query(F.data.startswith("pm_all"))
async def show_all(cb: CallbackQuery):
    logger.info(f"User {cb.from_user.id} requested all list of trucks")
    await cb.answer("⚡ Loading all vehicles...")

    page = int(cb.data.split(":")[1]) if ":" in cb.data else 1
    per_page = 10
    vehicles = await google_pm_service.list_all_vehicles()

    total = len(vehicles)
    shown = max(0, min(per_page, total - (page - 1) * per_page))
    title = f"🚛 PM Sheet Vehicles ({shown} shown of {total})"

    await cb.message.edit_text(
        title,
        reply_markup=get_pm_vehicles_keyboard(vehicles, page=page, per_page=per_page),
    )


# ────────────────────────────────
# FSM Search by Unit
# ────────────────────────────────
@router.callback_query(F.data == "pm_search")
async def pm_search_start(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(
        "🔍 *Search by Unit*\n\nSend the truck/unit number as a message.\n\n❌ Send /cancel to stop.",
        reply_markup=get_pm_search_keyboard(),
        parse_mode="Markdown",
    )
    await state.set_state(PMSearchState.waiting_for_unit)


@router.message(PMSearchState.waiting_for_unit, F.chat.type.in_(ALLOWED_CHAT_TYPES), F.text.regexp(r"^\d+$"))
async def pm_search_result(msg: Message, state: FSMContext):
    unit = msg.text.strip()
    details = await google_pm_service.get_vehicle_details(unit)
    if not details:
        await msg.answer(f"❌ Truck {unit} not found in the PM sheet.", reply_markup=get_pm_services_menu())
        await state.clear()
        return

    text = format_pm_vehicle_info(details, full=True)
    await msg.answer(text, reply_markup=get_pm_vehicle_details_keyboard(unit), parse_mode="Markdown")
    await state.clear()


@router.message(PMSearchState.waiting_for_unit, F.chat.type.in_(ALLOWED_CHAT_TYPES), F.text == "/cancel")
async def cancel_pm_search(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Search cancelled.", reply_markup=get_pm_services_menu())


# ────────────────────────────────
# Slash Command /<unit>
# ────────────────────────────────
@router.message(F.chat.type.in_(ALLOWED_CHAT_TYPES), F.text.regexp(r"^/\d+$"))
async def pm_search_slash(msg: Message):
    unit = msg.text.lstrip("/")
    details = await google_pm_service.get_vehicle_details(unit)
    if not details:
        await msg.answer(f"❌ Truck {unit} not found in the PM sheet.", reply_markup=get_pm_services_menu())
        return

    text = format_pm_vehicle_info(details, full=True)
    await msg.answer(text, reply_markup=get_pm_vehicle_details_keyboard(unit), parse_mode="Markdown")


# ────────────────────────────────
# Vehicle Details
# ────────────────────────────────
@router.callback_query(F.data.startswith("pm_sheet_vehicle:"))
async def vehicle_detail(cb: CallbackQuery):
    parts = cb.data.split(":")
    truck_id = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 1

    details = await google_pm_service.get_vehicle_details(truck_id)
    if not details:
        await cb.answer("Vehicle not found in PM sheet.", show_alert=True)
        return

    new_text = format_pm_vehicle_info(details, full=True)
    new_markup = get_pm_vehicle_details_keyboard(truck_id, page)

    try:
        await cb.message.edit_text(new_text, parse_mode="Markdown", reply_markup=new_markup)
        await cb.answer("✅ Data refreshed")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await cb.answer("🔄 Already up to date")
        else:
            raise


# ────────────────────────────────
# Group Ignore (Silent Mode)
# ────────────────────────────────
@router.message(F.chat.type.in_({"group", "supergroup"}))
async def ignore_groups_silently(_: Message):
    """Completely ignore all commands and messages in groups."""
    return
