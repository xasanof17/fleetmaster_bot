# middlewares/chat_guard.py
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

class PrivateOnlyMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        chat_type = None
        if isinstance(event, Message):
            chat_type = event.chat.type
        elif isinstance(event, CallbackQuery):
            chat_type = event.message.chat.type

        if chat_type in ("group", "supergroup"):
            # silently ignore or send a short notice
            if isinstance(event, Message):
                await event.reply("🚫 This bot works only in private chats.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 This bot works only in private chats.", show_alert=True)
            return  # stop further processing

        return await handler(event, data)
