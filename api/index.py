import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from core.bot import create_dispatcher, create_bot

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-vercel-app.vercel.app/

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
