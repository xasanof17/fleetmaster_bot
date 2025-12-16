from aiogram import Router, types
from aiogram.filters import Command

from handlers.auto_link_groups import ADMINS
from services.group_map import list_all_groups

router = Router()


def normalize_status(status: str | None) -> str:
    if not status:
        return "UNKNOWN"
    return status.replace("🔵", "").replace("🟡", "").replace("❌", "").strip().upper()


@router.message(Command("status_summary"))
async def cmd_status_summary(message: types.Message):
    # Security check
    if message.from_user.id not in ADMINS:
        return

    groups = await list_all_groups()

    total = len(groups)

    active = 0
    home = 0
    fired = 0
    no_unit = 0

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
        "📊 **FleetMaster Status Summary**\n"
        "───────────────────\n"
        f"🚛 **Total Groups:** `{total}`\n"
        f"✅ **Active Drivers:** `{active}`\n"
        f"🏠 **Home Time:** `{home}`\n"
        f"❌ **Fired / Removed:** `{fired}`\n"
        "───────────────────\n"
        f"⚠️ **Missing Units:** `{no_unit}`\n"
    )

    await message.answer(text, parse_mode="Markdown")
