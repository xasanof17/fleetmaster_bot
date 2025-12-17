"""
middlewares/auth_guard.py
FleetMaster — The Security Bouncer
FINAL • ADMIN-SAFE • FSM-SAFE • PRODUCTION READY
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from services.user_service import get_user_by_id

ADMINS = set(settings.ADMINS or [])


class AuthGuardMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id

        # =====================================================
        # 0. ADMIN BYPASS
        # =====================================================
        if user_id in ADMINS:
            return await handler(event, data)

        # =====================================================
        # 1. FSM BYPASS
        # =====================================================
        state: FSMContext | None = data.get("state")
        if state:
            current_state = await state.get_state()
            if current_state:
                return await handler(event, data)

        # =====================================================
        # 2. COMMAND BYPASS
        # =====================================================
        if (
            isinstance(event, Message)
            and event.text
            and event.text.startswith(("/start", "/verify_gmail"))
        ):
            return await handler(event, data)

        # =====================================================
        # 3. DB AUTH CHECK
        # =====================================================
        user = await get_user_by_id(user_id)

        if not user:
            return await self._block(
                event,
                "⛔ You are not registered.\nUse /start to begin.",
            )

        if not user.get("is_verified"):
            return await self._block(
                event,
                "📧 Gmail not verified.\nPlease complete verification.",
            )

        if not user.get("is_approved"):
            return await self._block(
                event,
                "⏳ Your account is pending admin approval.",
            )

        if not user.get("active"):
            return await self._block(
                event,
                "🚫 Your access has been disabled by admin.",
            )

        # ✅ Access granted
        return await handler(event, data)

    async def _block(self, event: Message | CallbackQuery, text: str):
        if isinstance(event, Message):
            await event.answer(text)
        else:
            await event.answer(text, show_alert=True)
        return
