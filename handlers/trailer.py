# handlers/trailer.py
from aiogram import Router, F
from aiogram.types import CallbackQuery
from utils.logger import get_logger


logger = get_logger(__name__)
router = Router()


# ────────────────────────────────────────
# PM Trucker Main Menu
# ────────────────────────────────────────
@router.callback_query(lambda c: c.data == "trailer_info")
async def trailer_info_menu(callback: CallbackQuery):
    """Show TRAILER INFORMATION main menu"""
    # await callback.answer("⚡ Loading trailer information...")
    logger.info(f"User {callback.from_user.id} accessed TRAILER INFORMATION")
    await callback.message.answer("COMING SOON: TRAILER INFORMATION feature is under development.")