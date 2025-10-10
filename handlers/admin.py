# handlers/admin.py
from aiogram import Router, F
from aiogram.types import Message
from config.settings import settings
from services.group_map import upsert_mapping
from utils import get_logger

router = Router()
logger = get_logger(__name__)
ADMINS = set(settings.ADMINS or [])

@router.message(F.text == "/id")
async def my_id(msg: Message):
    await msg.answer(f"Your ID: {msg.from_user.id}\nADMINS: {settings.ADMINS}\nYou're admin: {msg.from_user.id in ADMINS}")

@router.message(F.chat.type.in_({"group", "supergroup"}), F.text.regexp(r"^/link\s+(\d+)$"))
async def link_group(msg: Message, regexp: dict):
    # admin-only
    if msg.from_user.id not in ADMINS:
        return
    unit = regexp.group(1)
    await upsert_mapping(unit, msg.chat.id, msg.chat.title or "")
    await msg.reply(f"✅ Linked this group to unit **{unit}**.")
