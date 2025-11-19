# middlewares/chat_guard.py
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Chat, Message
from config.settings import settings
from utils import get_logger

logger = get_logger(__name__)


class ChatGuardMiddleware(BaseMiddleware):
    """
    If ALLOW_GROUPS=False, silently ignores all group/supergroup events.
    """

    async def __call__(self, handler, event, data):
        chat_type = None
        chat: Chat | None = None
        if isinstance(event, Message):
            chat = event.chat
        elif isinstance(event, CallbackQuery) and event.message:
            chat = event.message.chat

        if chat:
            chat_type = chat.type

        if not settings.ALLOW_GROUPS and chat_type in {"group", "supergroup"}:
            # No replies. No alerts. Quiet ignore.
            # logger.debug("ChatGuard: ignored event from group chat_id=%s", getattr(chat, "id", None))
            return

        return await handler(event, data)
