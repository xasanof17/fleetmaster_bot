"""
handlers/admin_dbcheck.py
Admin-only command to run database sanity checks on truck ↔ group mappings.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from utils.logger import get_logger
from services import group_map
from config.settings import settings

router = Router()
logger = get_logger(__name__)

ADMINS = {int(x) for x in (settings.ADMINS or [])}


# ====================================================
# /dbcheck COMMAND
# ====================================================
@router.message(Command("dbcheck"))
async def dbcheck_command(msg: Message):
    """Run a sanity scan of all group mappings."""
    if msg.from_user.id not in ADMINS:
        await msg.answer("🚫 You are not authorized to run this command.")
        return

    await msg.answer("🧠 Checking database consistency...\nPlease wait ⏳")

    try:
        await group_map.init_pool()
        report = await group_map.verify_all_mappings(auto_fix=True)

        summary = (
            f"✅ <b>Database Sanity Check Complete</b>\n"
            f"<b>Total Records:</b> {report['total']}\n"
            f"<b>Duplicates Found:</b> {len(report['duplicates'])}\n"
            f"<b>Null / Temp Units:</b> {len(report['null_units'])}\n"
            f"<b>Fixed Automatically:</b> {report['fixed']}\n\n"
        )

        if report["duplicates"]:
            dup_text = "\n".join(
                [f"• {a} ↔ {b}" for a, b in report["duplicates"][:10]]
            )
            summary += f"⚠️ <b>Duplicate Units:</b>\n{dup_text}\n\n"

        if report["null_units"]:
            null_text = "\n".join(
                [f"• {r['chat_id']} ({r['title']})" for r in report["null_units"][:10]]
            )
            summary += f"🟡 <b>Groups with Missing Unit:</b>\n{null_text}\n\n"

        summary += "🧩 Auto-fix cleaned invalid mappings (if any).\n🟢 DB now consistent."

        await msg.answer(summary, parse_mode="HTML")

    except Exception as e:
        logger.error(f"💥 DB check failed: {e}")
        await msg.answer(f"❌ <b>Error during DB check:</b> {e}", parse_mode="HTML")
