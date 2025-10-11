"""
PM Services: Google Sheet integration + admin broadcast + inline Telegram-style date & custom time scheduler (Asia/Tashkent).
"""

import asyncio
from typing import Dict, Any, List
from datetime import datetime, timedelta
import pytz

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
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
    get_calendar_keyboard,
    get_minute_picker_keyboard,
    get_time_picker_keyboard,
)
from config.settings import settings

logger = get_logger(__name__)
router = Router()
tz = pytz.timezone("Asia/Tashkent")

ADMINS = {int(x) for x in (settings.ADMINS or [])}
ALLOW_GROUPS = settings.ALLOW_GROUPS
ALLOWED_CHAT_TYPES = {"private"} if not ALLOW_GROUPS else {"private", "group", "supergroup"}


# ======================
# STATES
# ======================
class PMSearchState(StatesGroup):
    waiting_for_unit = State()


class PMTimerPicker(StatesGroup):
    waiting_for_date = State()
    waiting_for_hour = State()
    waiting_for_custom_time = State()


ACTIVE_TIMERS: Dict[str, asyncio.Task] = {}  # key: "listtype|timestamp" → asyncio.Task


# ======================
# HELPERS
# ======================
def _build_template(rows: List[Dict[str, Any]], title: str, icon: str) -> str:
    lines = [title.upper(), f"UPDATED: {datetime.now(tz):%m/%d/%Y}", "=" * 27]
    for r in rows:
        truck = str(r.get("truck"))
        left = r.get("left", 0)
        lines.append(f"/{truck} – {title} {icon} {left:,}")
    lines.append("=" * 27)
    return "\n".join(lines)


async def send_pm_updates_to_groups(bot, list_type: str):
    """Send PM updates to all mapped Telegram groups."""
    rows = await (google_pm_service.get_urgent_list() if list_type == "urgent" else google_pm_service.get_oil_list())
    if list_type == "urgent":
        rows = [r for r in rows if str(r.get("status", "")).lower().startswith("urgent")]
    else:
        rows = [r for r in rows if str(r.get("status", "")).lower().startswith("oil")]

    sent, skipped = 0, 0
    for r in rows:
        truck = str(r.get("truck"))
        group_id = await get_group_id_for_unit(truck)
        if not group_id:
            skipped += 1
            continue
        try:
            text = format_pm_vehicle_info(r, full=True)
            await bot.send_message(int(group_id), text, parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Failed to send PM for {truck}: {e}")
            skipped += 1

    logger.info(f"✅ Broadcast complete for {list_type}: Sent={sent}, Skipped={skipped}")
    return sent, skipped


async def schedule_send(bot, list_type: str, delay: float, target_time: datetime):
    """Background scheduler task."""
    key = f"{list_type}|{target_time.isoformat()}"
    try:
        await asyncio.sleep(delay)
        await bot.send_message(
            list(ADMINS)[0],
            f"📦 Sending scheduled *{list_type.upper()}* PM updates now "
            f"(Asia/Tashkent {datetime.now(tz):%H:%M %d.%m.%Y})",
            parse_mode="Markdown",
        )
        await send_pm_updates_to_groups(bot, list_type)
        ACTIVE_TIMERS.pop(key, None)
    except asyncio.CancelledError:
        ACTIVE_TIMERS.pop(key, None)
        logger.warning(f"🛑 Timer cancelled: {key}")
    except Exception as e:
        ACTIVE_TIMERS.pop(key, None)
        logger.error(f"💥 Timer failed: {e}")


# ======================
# MENUS
# ======================
@router.callback_query(F.data == "pm_services")
async def pm_services_menu(cb: CallbackQuery):
    intro = (
        "🛠 **PM SERVICES** – Preventive Maintenance & Service Center\n\n"
        "🔴 Urgent Oil Change – Needs immediate attention\n"
        "🟡 Oil Change – Routine scheduled service\n"
        "🚛 Show All Vehicles – View all PM data\n"
        "🔍 Search by Unit – Lookup specific truck\n\n"
        "Select an option below 👇"
    )
    await cb.message.edit_text(intro, reply_markup=get_pm_services_menu(), parse_mode="Markdown")


@router.callback_query(F.data == "pm_urgent")
async def urgent_list(cb: CallbackQuery):
    await cb.answer("⚡ Loading urgent list...")
    rows = await google_pm_service.get_urgent_list()
    urgent = [r for r in rows if str(r.get("status", "")).lower().startswith("urgent")]
    if not urgent:
        await cb.message.answer("🚨 No trucks marked as *Urgent oil change*.", parse_mode="Markdown")
        return
    text = _build_template(urgent, "Urgent oil change", "📌")
    await cb.message.answer(
        text,
        reply_markup=urgent_oil_list_keyboard("urgent", is_admin=cb.from_user.id in ADMINS),
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "pm_oil")
async def oil_list(cb: CallbackQuery):
    await cb.answer("⚡ Loading oil change list...")
    rows = await google_pm_service.get_oil_list()
    oil = [r for r in rows if str(r.get("status", "")).lower().startswith("oil")]
    if not oil:
        await cb.message.answer("🟡 No trucks currently due for oil change.")
        return
    text = _build_template(oil, "Oil change", "🟡")
    await cb.message.answer(
        text,
        reply_markup=urgent_oil_list_keyboard("oil", is_admin=cb.from_user.id in ADMINS),
        parse_mode="Markdown",
    )


# ======================
# CALENDAR + TIMER PICKER
# ======================
@router.callback_query(F.data.startswith("cal_prev:"))
async def calendar_prev(cb: CallbackQuery):
    _, year, month = cb.data.split(":")
    await cb.message.edit_reply_markup(reply_markup=get_calendar_keyboard(int(year), int(month)))


@router.callback_query(F.data.startswith("cal_next:"))
async def calendar_next(cb: CallbackQuery):
    _, year, month = cb.data.split(":")
    await cb.message.edit_reply_markup(reply_markup=get_calendar_keyboard(int(year), int(month)))


@router.callback_query(F.data.startswith("pm_timer_start:"))
async def timer_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMINS:
        await cb.answer("🚫 Only admins can schedule timers.", show_alert=True)
        return
    list_type = cb.data.split(":")[1]
    await state.update_data(list_type=list_type)
    await cb.message.edit_text(
        "🗓 Choose a date for scheduling (Asia/Tashkent):",
        reply_markup=get_calendar_keyboard(),
    )
    await state.set_state(PMTimerPicker.waiting_for_date)


@router.callback_query(PMTimerPicker.waiting_for_date, F.data.startswith("pick_date:"))
async def pick_date(cb: CallbackQuery, state: FSMContext):
    date_str = cb.data.split(":")[1]
    await state.update_data(date_str=date_str)
    await cb.message.edit_text(
        f"📅 Date selected: *{date_str}*\n\nNow choose an hour:",
        reply_markup=get_time_picker_keyboard("hour"),
        parse_mode="Markdown",
    )
    await state.set_state(PMTimerPicker.waiting_for_hour)


# ======================
# CUSTOM TIME INPUT
# ======================
@router.message(PMTimerPicker.waiting_for_custom_time)
async def handle_custom_time(msg: Message, state: FSMContext):
    """Handle manual HH or HH:MM input with safety and smooth UX."""
    user_input = msg.text.strip()

    try:
        # Accept both "HH" and "HH:MM"
        if ":" in user_input:
            time_obj = datetime.strptime(user_input, "%H:%M")
        else:
            time_obj = datetime.strptime(user_input, "%H")
    except ValueError:
        await msg.answer("❌ Invalid format! Please use HH:MM (e.g. 21:45).", parse_mode="Markdown")
        return

    data = await state.get_data()
    list_type = data.get("list_type")
    date_str = data.get("date_str")

    # 🧠 Validation safety
    if not list_type or not date_str:
        await msg.answer("⚠️ Session expired. Please start scheduling again.")
        await state.clear()
        return

    # 🕐 Time logic
    date = datetime.strptime(date_str, "%Y-%m-%d")
    target = tz.localize(datetime(date.year, date.month, date.day, time_obj.hour, time_obj.minute))
    now_tash = datetime.now(tz)

    # Move to next day if time already passed
    if target <= now_tash:
        target += timedelta(days=1)

    delay = (target - now_tash).total_seconds()
    key = f"{list_type}|{target.isoformat()}"

    # 🧹 Clear FSM first to avoid double triggers
    await state.clear()

    # ⏳ Small delay for smoother UX (looks natural)
    await asyncio.sleep(0.4)

    # 🚀 Schedule broadcast
    task = asyncio.create_task(schedule_send(msg.bot, list_type, delay, target))
    ACTIVE_TIMERS[key] = task

    # ✅ Confirmation message
    await msg.answer(
        f"✅ Timer set for *{target.strftime('%d %b %Y, %H:%M %Z')}*\n"
        f"Will send *{list_type.upper()}* PM updates automatically.\n"
        f"🕐 Total Active Timers: {len(ACTIVE_TIMERS)}",
        parse_mode="Markdown",
    )


@router.message(PMTimerPicker.waiting_for_custom_time)
async def handle_custom_time(msg: Message, state: FSMContext):
    """Handle manual HH or HH:MM input."""
    user_input = msg.text.strip()
    try:
        # support both HH and HH:MM
        if ":" in user_input:
            time_obj = datetime.strptime(user_input, "%H:%M")
        else:
            time_obj = datetime.strptime(user_input, "%H")
    except ValueError:
        await msg.answer("❌ Invalid format! Use HH:MM (e.g. 21:45).", parse_mode="Markdown")
        return

    data = await state.get_data()
    list_type = data.get("list_type")
    date_str = data.get("date_str")

    if not list_type or not date_str:
        await msg.answer("⚠️ Session expired. Please start scheduling again.")
        await state.clear()
        return

    date = datetime.strptime(date_str, "%Y-%m-%d")
    target = tz.localize(datetime(date.year, date.month, date.day, time_obj.hour, time_obj.minute))
    now_tash = datetime.now(tz)

    # auto move to next day if past
    if target <= now_tash:
        target = target + timedelta(days=1)

    delay = (target - now_tash).total_seconds()
    key = f"{list_type}|{target.isoformat()}"
    task = asyncio.create_task(schedule_send(msg.bot, list_type, delay, target))
    ACTIVE_TIMERS[key] = task

    await msg.answer(
        f"✅ Timer set for *{target.strftime('%d %b %Y, %H:%M %Z')}*\n"
        f"Will send *{list_type.upper()}* PM updates automatically.\n"
        f"🕐 Total Active Timers: {len(ACTIVE_TIMERS)}",
        parse_mode="Markdown",
    )
    await state.clear()


# ======================
# HOUR PICKER (STEP 1)
# ======================
@router.callback_query(PMTimerPicker.waiting_for_hour, F.data.startswith("pick_hour:"))
async def pick_hour(cb: CallbackQuery, state: FSMContext):
    hour = int(cb.data.split(":")[1])
    await state.update_data(hour=hour)
    await cb.message.edit_text(
        f"🕐 Hour selected: *{hour:02d}:--*\nNow choose minutes:",
        reply_markup=get_minute_picker_keyboard(hour),
        parse_mode="Markdown"
    )


# ======================
# MINUTE PICKER (STEP 2)
# ======================
@router.callback_query(F.data.startswith("pick_time:"))
async def pick_time(cb: CallbackQuery, state: FSMContext):
    _, hour_str, minute_str = cb.data.split(":")
    hour, minute = int(hour_str), int(minute_str)

    data = await state.get_data()
    list_type = data.get("list_type")
    date_str = data.get("date_str")

    date = datetime.strptime(date_str, "%Y-%m-%d")
    target = tz.localize(datetime(date.year, date.month, date.day, hour, minute))
    now_tash = datetime.now(tz)
    if target <= now_tash:
        target += timedelta(days=1)

    delay = (target - now_tash).total_seconds()
    key = f"{list_type}|{target.isoformat()}"
    task = asyncio.create_task(schedule_send(cb.bot, list_type, delay, target))
    ACTIVE_TIMERS[key] = task

    await cb.message.edit_text(
        f"✅ Timer set for *{target.strftime('%d %b %Y, %H:%M %Z')}*\n"
        f"Will send *{list_type.upper()}* PM updates automatically.\n"
        f"🕐 Total Active Timers: {len(ACTIVE_TIMERS)}",
        parse_mode="Markdown"
    )
    await state.clear()


# ======================
# CUSTOM MINUTE (manual)
# ======================
@router.callback_query(F.data.startswith("custom_minute:"))
async def custom_minute_input(cb: CallbackQuery, state: FSMContext):
    hour = int(cb.data.split(":")[1])
    await state.update_data(hour=hour)
    await cb.message.answer(
        f"⌨️ Enter the time manually as *{hour:02d}:MM* (e.g. {hour:02d}:30)",
        parse_mode="Markdown"
    )
    await state.set_state(PMTimerPicker.waiting_for_custom_time)
# ======================
# STOP TIMERS
# ======================
@router.callback_query(F.data.startswith("pm_timer_stop:"))
async def stop_timers(cb: CallbackQuery):
    if cb.from_user.id not in ADMINS:
        await cb.answer("🚫 Only admins can stop timers.", show_alert=True)
        return
    if not ACTIVE_TIMERS:
        await cb.message.answer("🛑 No active timers running.")
        return

    for k, task in list(ACTIVE_TIMERS.items()):
        task.cancel()
        ACTIVE_TIMERS.pop(k, None)

    await cb.message.answer("🧹 All scheduled PM timers cancelled successfully.")
    
# ======================
# VIEW TIMERS
# ======================
@router.callback_query(F.data == "pm_timer_view")
async def view_timers(cb: CallbackQuery):
    """Show all currently active PM timers."""
    if cb.from_user.id not in ADMINS:
        await cb.answer("🚫 Only admins can view timers.", show_alert=True)
        return

    if not ACTIVE_TIMERS:
        await cb.message.answer("🕐 No active PM timers right now.")
        return

    lines = ["⏰ **ACTIVE PM TIMERS**", "=" * 27]
    for key in list(ACTIVE_TIMERS.keys()):
        try:
            list_type, iso_time = key.split("|", 1)
            target = datetime.fromisoformat(iso_time)
            # format the display nicely in local timezone
            local_time = target.astimezone(tz)
            lines.append(
                f"• {list_type.upper()} → {local_time.strftime('%d %b %Y, %H:%M %Z')}"
            )
        except Exception:
            lines.append(f"• {key}")

    lines.append("=" * 27)
    lines.append(f"🧩 Total Active Timers: {len(ACTIVE_TIMERS)}")

    await cb.message.answer("\n".join(lines), parse_mode="Markdown")
