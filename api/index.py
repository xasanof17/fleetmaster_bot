import asyncio

from aiogram import types
from aiohttp import web
from config import settings
from core.bot import create_bot, create_dispatcher

TOKEN = settings.TELEGRAM_BOT_TOKEN
WEBHOOK_URL = settings.WEBHOOK_URL  # e.g. https://your-vercel-app.vercel.app/

bot = create_bot()
dp = create_dispatcher()


async def handle(request):
    body = await request.json()
    update = types.Update(**body)
    await dp.feed_update(bot, update)
    return web.Response()


def vercel_app(request):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(handle(request))
