import csv
import html
import io

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from handlers.auto_link_groups import ADMINS
from services.group_map import list_all_groups

router = Router()

PAGE_SIZE = 10

FILTERS = {
    "active": "ACTIVE",
    "home": "HOME",
    "fired": "FIRED",
    "no_unit": "NO_UNIT",
}

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────


def normalize_status(status: str | None) -> str:
    if not status:
        return "UNKNOWN"
    return status.replace("🔵", "").replace("🟡", "").replace("❌", "").strip().upper()


def filter_groups(groups: list[dict], filter_key: str) -> list[dict]:
    if filter_key == "no_unit":
        return [g for g in groups if not g.get("unit")]

    wanted = FILTERS.get(filter_key)
    return [g for g in groups if normalize_status(g.get("driver_status")) == wanted]


def build_keyboard(filter_key: str, page: int, has_prev: bool, has_next: bool):
    rows = []

    nav = []
    if has_prev:
        nav.append(
            InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=f"status:{filter_key}:{page - 1}",
            )
        )
    if has_next:
        nav.append(
            InlineKeyboardButton(
                text="➡️ Next",
                callback_data=f"status:{filter_key}:{page + 1}",
            )
        )
    if nav:
        rows.append(nav)

    rows.append(
        [
            InlineKeyboardButton(
                text="📤 Export CSV",
                callback_data=f"status_export:csv:{filter_key}",
            ),
            InlineKeyboardButton(
                text="📊 Export Sheet",
                callback_data=f"status_export:sheet:{filter_key}",
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─────────────────────────────────────────────
# STATUS SUMMARY
# ─────────────────────────────────────────────


@router.message(Command("status_summary"))
async def cmd_status_summary(message: types.Message):
    if message.from_user.id not in ADMINS:
        return

    groups = await list_all_groups()

    total = len(groups)
    active = home = fired = no_unit = 0

    for g in groups:
        status = normalize_status(g.get("driver_status"))
        unit = g.get("unit")

        if not unit:
            no_unit += 1

        if status == "ACTIVE":
            active += 1
        elif status == "HOME":
            home += 1
        elif status == "FIRED":
            fired += 1

    text = (
        "<b>📊 FleetMaster Status Summary</b>\n"
        "───────────────────\n"
        f"🚛 <b>Total Groups:</b> <code>{total}</code>\n"
        f"✅ <b>Active Drivers:</b> <code>{active}</code>\n"
        f"🏠 <b>Home Time:</b> <code>{home}</code>\n"
        f"❌ <b>Fired / Removed:</b> <code>{fired}</code>\n"
        "───────────────────\n"
        f"⚠️ <b>Missing Units:</b> <code>{no_unit}</code>"
    )

    await message.answer(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# STATUS LIST COMMAND
# ─────────────────────────────────────────────


@router.message(Command("status_list"))
async def cmd_status_list(message: types.Message):
    if message.from_user.id not in ADMINS:
        return

    args = message.text.split()
    filter_key = args[1].lower() if len(args) > 1 else "active"

    if filter_key not in FILTERS and filter_key != "no_unit":
        filter_key = "active"

    await send_status_page(
        bot=message.bot,
        chat_id=message.chat.id,
        filter_key=filter_key,
        page=0,
    )


# ─────────────────────────────────────────────
# PAGE SENDER (HTML SAFE)
# ─────────────────────────────────────────────


async def send_status_page(bot, chat_id: int, filter_key: str, page: int):
    groups = await list_all_groups()
    filtered = filter_groups(groups, filter_key)

    total = len(filtered)
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = filtered[start:end]

    lines: list[str] = []

    for g in page_items:
        raw_unit = g.get("unit")
        raw_driver = g.get("driver_name")
        chat = g.get("chat_id")

        unit = html.escape(raw_unit) if raw_unit else "—"
        driver = html.escape(raw_driver) if raw_driver else "UNKNOWN"

        if raw_unit:
            link = f"https://t.me/c/{str(chat)[4:]}"
            line = f'• <a href="{link}"><code>{unit}</code></a> — {driver}'
        else:
            line = f"• <code>—</code> — {driver}"

        lines.append(line)

    safe_filter = html.escape(filter_key.upper())

    text = f"<b>📋 Status list: {safe_filter}</b>\nTotal: <code>{total}</code>\n\n" + (
        "\n".join(lines) if lines else "<i>No records</i>"
    )

    kb = build_keyboard(
        filter_key=filter_key,
        page=page,
        has_prev=page > 0,
        has_next=end < total,
    )

    await bot.send_message(
        chat_id,
        text,
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# ─────────────────────────────────────────────
# PAGINATION CALLBACK
# ─────────────────────────────────────────────


@router.callback_query(F.data.startswith("status:"))
async def on_status_page(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMINS:
        await cb.answer("Not allowed", show_alert=True)
        return

    _, filter_key, page = cb.data.split(":")
    await cb.message.delete()

    await send_status_page(
        bot=cb.bot,
        chat_id=cb.message.chat.id,
        filter_key=filter_key,
        page=int(page),
    )


# ─────────────────────────────────────────────
# EXPORT CSV
# ─────────────────────────────────────────────


@router.callback_query(F.data.startswith("status_export:csv"))
async def export_csv(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMINS:
        return

    _, _, filter_key = cb.data.split(":")
    groups = filter_groups(await list_all_groups(), filter_key)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Unit", "Driver", "Status", "Chat ID"])

    for g in groups:
        writer.writerow(
            [
                g.get("unit") or "",
                g.get("driver_name") or "",
                g.get("driver_status") or "",
                g.get("chat_id"),
            ]
        )

    csv_bytes = output.getvalue().encode("utf-8")
    output.close()

    file = BufferedInputFile(
        csv_bytes,
        filename=f"status_{filter_key}.csv",
    )

    await cb.message.answer_document(file)


# ─────────────────────────────────────────────
# EXPORT GOOGLE SHEET (HOOK)
# ─────────────────────────────────────────────


@router.callback_query(F.data.startswith("status_export:sheet"))
async def export_sheet(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMINS:
        return

    await cb.answer("Google Sheet export triggered ✅")
