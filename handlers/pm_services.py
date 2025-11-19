"""
PM Services: Google Sheet integration + admin broadcast + inline Telegram-style date & custom time scheduler (Asia/Tashkent).
FIXED: Added search by unit, pagination, and /unit command support
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import pytz
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from config.settings import settings
from keyboards.pm_services import (
    get_calendar_keyboard,
    get_minute_picker_keyboard,
    get_pm_search_keyboard,
    get_pm_services_menu,
    get_pm_vehicle_details_keyboard,
    get_pm_vehicles_keyboard,
    get_time_picker_keyboard,
    urgent_oil_list_keyboard,
)
from services import google_pm_service
from services.group_map import get_group_id_for_unit
from utils import format_pm_vehicle_info, get_logger

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


ACTIVE_TIMERS: dict[str, asyncio.Task] = {}  # key: "listtype|timestamp" → asyncio.Task


# ======================
# HELPERS
# ======================
def _build_template(rows: list[dict[str, Any]], title: str, icon: str) -> str:
    lines = [title.upper(), f"UPDATED: {datetime.now(tz):%m/%d/%Y}", "=" * 27]
    for r in rows:
        truck = str(r.get("truck"))
        left = r.get("left", 0)
        lines.append(f"/{truck} — {title} {icon} {left:,}")
    lines.append("=" * 27)
    return "\n".join(lines)


async def send_pm_updates_to_groups(bot, list_type: str):
    """Send PM updates to all mapped Telegram groups with FULL details."""
    # Get the list of trucks needing PM
    rows = await (
        google_pm_service.get_urgent_list()
        if list_type == "urgent"
        else google_pm_service.get_oil_list()
    )

    if list_type == "urgent":
        rows = [r for r in rows if "urgent" in str(r.get("status", "")).lower()]
    else:
        rows = [r for r in rows if "oil" in str(r.get("status", "")).lower()]

    sent_list = []
    skipped_list = []

    for r in rows:
        truck = str(r.get("truck"))
        group_id = await get_group_id_for_unit(truck)

        if not group_id:
            logger.warning(f"No group mapped for truck {truck}, skipping...")
            skipped_list.append(f"Truck {truck} - No group mapped")
            continue

        try:
            # ✅ Fetch FULL details for this truck (not just summary)
            full_details = await google_pm_service.get_vehicle_details(truck)

            if not full_details:
                logger.warning(f"No full details found for truck {truck}, skipping...")
                skipped_list.append(f"Truck {truck} - No details in sheet")
                continue

            # ✅ Format with FULL template (includes PM Date, PM Shop, etc.)
            text = format_pm_vehicle_info(full_details, full=True)

            # Send to group
            await bot.send_message(int(group_id), text, parse_mode="Markdown")
            sent_list.append(f"Truck {truck} → Group {group_id}")
            logger.info(f"✅ Sent PM update for truck {truck} to group {group_id}")

            # Small delay to avoid rate limits
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Failed to send PM for truck {truck} to group {group_id}: {e}")
            skipped_list.append(f"Truck {truck} - Error: {str(e)[:50]}")

    logger.info(
        f"✅ Broadcast complete for {list_type}: Sent={len(sent_list)}, Skipped={len(skipped_list)}"
    )
    return sent_list, skipped_list


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
        "🛠 **PM SERVICES** — Preventive Maintenance & Service Center\n\n"
        "🔴 Urgent Oil Change — Needs immediate attention\n"
        "🟡 Oil Change — Routine scheduled service\n"
        "🚛 Show All Vehicles — View all PM data\n"
        "🔍 Search by Unit — Lookup specific truck\n\n"
        "Select an option below 👇"
    )
    await cb.message.edit_text(intro, reply_markup=get_pm_services_menu(), parse_mode="Markdown")


@router.callback_query(F.data == "pm_urgent")
async def urgent_list(cb: CallbackQuery):
    await cb.answer("⚡ Loading urgent list...")

    try:
        rows = await google_pm_service.get_urgent_list()
        urgent = [r for r in rows if "urgent" in str(r.get("status", "")).lower()]

        if not urgent:
            await cb.message.answer(
                "🚨 No trucks marked as *Urgent oil change*.",
                parse_mode="Markdown",
                reply_markup=get_pm_services_menu(),
            )
            return

        # Build the list message without empty lines
        lines = ["*URGENT OIL CHANGE*", f"UPDATED: {datetime.now(tz):%m/%d/%Y}", "=" * 27]

        for r in urgent:
            truck = str(r.get("truck", ""))
            left = r.get("left", 0)
            lines.append(f"/{truck} — Urgent oil change 📌 {left:,}")

        lines.append("=" * 27)
        text = "\n".join(lines)

        await cb.message.answer(
            text,
            reply_markup=urgent_oil_list_keyboard(
                "urgent", is_admin=cb.from_user.id in ADMINS, chat_type=cb.message.chat.type
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error loading urgent list: {e}")
        await cb.answer("❌ Error loading urgent list", show_alert=True)


@router.callback_query(F.data == "pm_oil")
async def oil_list(cb: CallbackQuery):
    await cb.answer("⚡ Loading oil change list...")

    try:
        rows = await google_pm_service.get_oil_list()
        oil = [r for r in rows if "oil" in str(r.get("status", "")).lower()]

        if not oil:
            await cb.message.answer(
                "🟡 No trucks currently due for oil change.", reply_markup=get_pm_services_menu()
            )
            return

        # Build the list message without empty lines
        lines = ["*OIL CHANGE*", f"UPDATED: {datetime.now(tz):%m/%d/%Y}", "=" * 27]

        for r in oil:
            truck = str(r.get("truck", ""))
            left = r.get("left", 0)
            lines.append(f"/{truck} — Oil change 🟡 {left:,}")

        lines.append("=" * 27)
        text = "\n".join(lines)

        await cb.message.answer(
            text,
            reply_markup=urgent_oil_list_keyboard(
                "oil", is_admin=cb.from_user.id in ADMINS, chat_type=cb.message.chat.type
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error loading oil list: {e}")
        await cb.answer("❌ Error loading oil list", show_alert=True)


# ======================
# SHOW ALL VEHICLES (FIXED WITH PAGINATION)
# ======================
@router.callback_query(F.data.startswith("pm_all"))
async def show_all_vehicles(cb: CallbackQuery):
    """Show all vehicles from Google Sheet with pagination"""
    parts = cb.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 1

    await cb.answer("📋 Loading vehicles...")

    try:
        # Get all vehicles from Google Sheet
        all_vehicles = await google_pm_service.list_all_vehicles()

        if not all_vehicles:
            await cb.message.edit_text(
                "❌ No vehicles found in PM sheet.",
                reply_markup=get_pm_services_menu(),
                parse_mode="Markdown",
            )
            return

        # Show paginated list
        await cb.message.edit_text(
            f"🚛 **All Vehicles** ({len(all_vehicles)} total)\n\nSelect a vehicle to view PM details:",
            reply_markup=get_pm_vehicles_keyboard(all_vehicles, page=page, per_page=10),
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error showing all vehicles: {e}")
        await cb.message.edit_text(
            "❌ Error loading vehicles. Please try again.",
            reply_markup=get_pm_services_menu(),
            parse_mode="Markdown",
        )


# ======================
# SEARCH BY UNIT (FIXED)
# ======================
@router.callback_query(F.data == "pm_search")
async def start_pm_search(cb: CallbackQuery, state: FSMContext):
    """Start search for a specific truck unit"""
    await cb.message.edit_text(
        "🔍 **Search by Unit Number**\n\n"
        "Enter the truck unit number (e.g. 5071, 5096):\n\n"
        "Send /cancel to stop.",
        reply_markup=get_pm_search_keyboard(),
        parse_mode="Markdown",
    )
    await state.set_state(PMSearchState.waiting_for_unit)
    await cb.answer()


@router.message(PMSearchState.waiting_for_unit, F.text)
async def process_pm_search(msg: Message, state: FSMContext):
    """Process the unit search query"""
    query = msg.text.strip().lstrip("/")  # Remove / if user types /5071

    if not query:
        await msg.reply("Please enter a valid unit number.")
        return

    try:
        # Search in Google Sheet
        details = await google_pm_service.get_vehicle_details(query)

        if not details:
            await msg.reply(
                f"❌ Truck *{query}* not found in PM records.",
                reply_markup=get_pm_search_keyboard(),
                parse_mode="Markdown",
            )
            return

        # Format and send details
        text = format_pm_vehicle_info(details, full=True)
        keyboard = get_pm_vehicle_details_keyboard(
            query, page=1, is_admin=msg.from_user.id in ADMINS, chat_type=msg.chat.type
        )

        await msg.reply(text, reply_markup=keyboard, parse_mode="Markdown")
        logger.info(f"User {msg.from_user.id} searched for truck {query}")

    except Exception as e:
        logger.error(f"Error in PM search: {e}")
        await msg.reply("❌ Error searching. Please try again.")


@router.message(PMSearchState.waiting_for_unit, F.text == "/cancel")
async def cancel_pm_search(msg: Message, state: FSMContext):
    """Cancel the search"""
    await state.clear()
    await msg.reply(
        "❌ Search cancelled.", reply_markup=get_pm_services_menu(), parse_mode="Markdown"
    )


# ======================
# /UNIT COMMAND HANDLER (NEW)
# ======================
@router.message(Command(commands=["5071", "5096", "5097", "5157", "5174", "5003", "2002"]))
@router.message(F.text.regexp(r"^/(\d{4})$"))
async def handle_unit_command(msg: Message):
    """Handle /unit commands like /5071, /5096, etc."""
    # Extract unit number from command
    unit = msg.text.strip().lstrip("/")

    try:
        # Get PM details from Google Sheet
        details = await google_pm_service.get_vehicle_details(unit)

        if not details:
            await msg.reply(f"❌ Truck *{unit}* not found in PM records.", parse_mode="Markdown")
            return

        # Format and send
        text = format_pm_vehicle_info(details, full=True)
        keyboard = get_pm_vehicle_details_keyboard(
            unit, page=1, is_admin=msg.from_user.id in ADMINS, chat_type=msg.chat.type
        )

        await msg.reply(text, reply_markup=keyboard, parse_mode="Markdown")
        logger.info(f"User {msg.from_user.id} used /{unit} command")

    except Exception as e:
        logger.error(f"Error handling /{unit} command: {e}")
        await msg.reply("❌ Error fetching truck details.")


# ======================
# VEHICLE DETAILS FROM SHEET
# ======================
@router.callback_query(F.data.startswith("pm_sheet_vehicle:"))
async def show_pm_vehicle_details(cb: CallbackQuery):
    """Show PM details for a specific vehicle from Google Sheet"""
    parts = cb.data.split(":")
    truck_id = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 1

    # Check if this is a refresh action
    is_refresh = len(parts) > 2 and parts[0] == "pm_sheet_vehicle"

    if is_refresh:
        await cb.answer("🔄 Checking for updates...")
    else:
        await cb.answer("📋 Loading PM details...")

    try:
        details = await google_pm_service.get_vehicle_details(truck_id)

        if not details:
            await cb.message.edit_text(
                f"❌ Truck *{truck_id}* not found in PM records.",
                reply_markup=get_pm_services_menu(),
                parse_mode="Markdown",
            )
            return

        new_text = format_pm_vehicle_info(details, full=True)
        keyboard = get_pm_vehicle_details_keyboard(
            truck_id, page=page, is_admin=cb.from_user.id in ADMINS, chat_type=cb.message.chat.type
        )

        # Check if content changed (for refresh action)
        if is_refresh and cb.message.text:
            old_text = cb.message.text
            # Compare content (ignore timestamp differences)
            old_without_timestamp = (
                old_text.split("UPDATED:")[0] if "UPDATED:" in old_text else old_text
            )
            new_without_timestamp = (
                new_text.split("UPDATED:")[0] if "UPDATED:" in new_text else new_text
            )

            if old_without_timestamp.strip() == new_without_timestamp.strip():
                # No changes detected
                await cb.answer("✅ Already up to date", show_alert=True)
                return

        # Update message with new content
        try:
            await cb.message.edit_text(text=new_text, reply_markup=keyboard, parse_mode="Markdown")
            if is_refresh:
                await cb.answer("✅ Updated successfully")
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await cb.answer("✅ Already up to date", show_alert=True)
            else:
                raise

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await cb.answer("✅ Already up to date", show_alert=True)
        else:
            logger.error(f"Telegram error showing PM vehicle details: {e}")
            await cb.answer("❌ Error loading details", show_alert=True)
    except Exception as e:
        logger.error(f"Error showing PM vehicle details: {e}")
        try:
            await cb.message.edit_text(
                "❌ Error loading details.",
                reply_markup=get_pm_services_menu(),
                parse_mode="Markdown",
            )
        except:
            await cb.answer("❌ Error loading details", show_alert=True)


# ======================
# SEND PM TO GROUP
# ======================
@router.callback_query(F.data.startswith("pm_send_group:"))
async def send_pm_to_group(cb: CallbackQuery):
    """Send PM info to truck's mapped group"""
    if cb.from_user.id not in ADMINS:
        await cb.answer("🚫 Admin only", show_alert=True)
        return

    truck_id = cb.data.split(":")[1]

    try:
        group_id = await get_group_id_for_unit(truck_id)
        if not group_id:
            await cb.answer(f"❌ No group mapped for truck {truck_id}", show_alert=True)
            return

        details = await google_pm_service.get_vehicle_details(truck_id)
        if not details:
            await cb.answer("❌ Truck not found in PM sheet", show_alert=True)
            return

        text = format_pm_vehicle_info(details, full=True)
        await cb.bot.send_message(int(group_id), text, parse_mode="Markdown")
        await cb.answer(f"✅ Sent to group {group_id}")

    except Exception as e:
        logger.error(f"Error sending PM to group: {e}")
        await cb.answer("❌ Error sending to group", show_alert=True)


# ======================
# SEND LIST TO ALL GROUPS
# ======================
@router.callback_query(F.data.startswith("pm_send_list:"))
async def send_list_to_groups(cb: CallbackQuery):
    """Send PM list updates to all mapped groups"""
    if cb.from_user.id not in ADMINS:
        await cb.answer("🚫 Admin only", show_alert=True)
        return

    list_type = cb.data.split(":")[1]
    await cb.answer("📤 Sending to groups...")

    try:
        sent_list, skipped_list = await send_pm_updates_to_groups(cb.bot, list_type)

        # Build detailed report
        lines = [
            "✅ **Broadcast Complete**",
            f"**Type:** {list_type.upper()}",
            "",
            f"📤 **Sent: {len(sent_list)}**",
        ]

        if sent_list:
            for item in sent_list[:10]:  # Show first 10
                lines.append(f"✅ {item}")
            if len(sent_list) > 10:
                lines.append(f"... and {len(sent_list) - 10} more")

        lines.append("")
        lines.append(f"⚠️ **Skipped: {len(skipped_list)}**")

        if skipped_list:
            for item in skipped_list[:10]:  # Show first 10
                lines.append(f"❌ {item}")
            if len(skipped_list) > 10:
                lines.append(f"... and {len(skipped_list) - 10} more")

        report = "\n".join(lines)

        await cb.message.answer(report, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error broadcasting PM list: {e}")
        await cb.answer("❌ Error broadcasting", show_alert=True)


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


@router.callback_query(PMTimerPicker.waiting_for_hour, F.data.startswith("pick_hour:"))
async def pick_hour(cb: CallbackQuery, state: FSMContext):
    hour = int(cb.data.split(":")[1])
    await state.update_data(hour=hour)
    await cb.message.edit_text(
        f"🕐 Hour selected: *{hour:02d}:--*\nNow choose minutes:",
        reply_markup=get_minute_picker_keyboard(hour),
        parse_mode="Markdown",
    )


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
        parse_mode="Markdown",
    )
    await state.clear()


@router.callback_query(F.data.startswith("custom_minute:"))
async def custom_minute_input(cb: CallbackQuery, state: FSMContext):
    hour = int(cb.data.split(":")[1])
    await state.update_data(hour=hour)
    await cb.message.answer(
        f"⌨️ Enter the time manually as *{hour:02d}:MM* (e.g. {hour:02d}:30)", parse_mode="Markdown"
    )
    await state.set_state(PMTimerPicker.waiting_for_custom_time)


@router.message(PMTimerPicker.waiting_for_custom_time)
async def handle_custom_time(msg: Message, state: FSMContext):
    """Handle manual HH or HH:MM input with safety and smooth UX."""
    user_input = msg.text.strip()

    try:
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

    if not list_type or not date_str:
        await msg.answer("⚠️ Session expired. Please start scheduling again.")
        await state.clear()
        return

    date = datetime.strptime(date_str, "%Y-%m-%d")
    target = tz.localize(datetime(date.year, date.month, date.day, time_obj.hour, time_obj.minute))
    now_tash = datetime.now(tz)

    if target <= now_tash:
        target += timedelta(days=1)

    delay = (target - now_tash).total_seconds()
    key = f"{list_type}|{target.isoformat()}"

    await state.clear()
    await asyncio.sleep(0.4)

    task = asyncio.create_task(schedule_send(msg.bot, list_type, delay, target))
    ACTIVE_TIMERS[key] = task

    await msg.answer(
        f"✅ Timer set for *{target.strftime('%d %b %Y, %H:%M %Z')}*\n"
        f"Will send *{list_type.upper()}* PM updates automatically.\n"
        f"🕐 Total Active Timers: {len(ACTIVE_TIMERS)}",
        parse_mode="Markdown",
    )


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
            local_time = target.astimezone(tz)
            lines.append(f"• {list_type.upper()} → {local_time.strftime('%d %b %Y, %H:%M %Z')}")
        except Exception:
            lines.append(f"• {key}")

    lines.append("=" * 27)
    lines.append(f"🧩 Total Active Timers: {len(ACTIVE_TIMERS)}")

    await cb.message.answer("\n".join(lines), parse_mode="Markdown")


@router.callback_query(F.data == "pm_page_info")
async def page_info(cb: CallbackQuery):
    """Handle page info button click (does nothing)"""
    await cb.answer()
