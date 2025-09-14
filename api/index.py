import os
import asyncio
import logging
from aiohttp import web
from aiogram import types
from core.bot import create_dispatcher, create_bot
from config.settings import settings

# ===================== LOGGING =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("alerts.log", encoding="utf-8"),  # log to file
        logging.StreamHandler()  # log to console
    ]
)

bot = create_bot()
dp = create_dispatcher()

# ===================== TOPIC MAPPING =====================
TOPIC_MAP = {
    # Spartak Shop
    "Spartak Shop": (settings.GROUP_ID, 14),

    # Scheduled Maintenance
    "Scheduled Maintenance by Odometer": (settings.GROUP_ID, 16),

    # Speeding
    "Vehicle Severely Speeding Above Limit": (settings.GROUP_ID, 3),
    "SPEEDING ZONE": (settings.GROUP_ID, 3),
    "45 SPEED ZONE AHEAD": (settings.GROUP_ID, 3),

    # Weight Stations
    "LINE ZONE": (settings.GROUP_ID, 12),
    "LEFT LANE": (settings.GROUP_ID, 12),
    "Weigh_Station_Zone": (settings.GROUP_ID, 12),
    "Policy Violation Occurred": (settings.GROUP_ID, 12),

    # Critical Maintenance
    "Engine Coolant Temperature is above 200F": (settings.GROUP_ID, 7),
    "Panic Button": (settings.GROUP_ID, 7),
    "Vehicle Engine Idle": (settings.GROUP_ID, 7),
    "Harsh Event": (settings.GROUP_ID, 7),

    # Dashcams / Gateway
    "DASHCAM DISCONNECTED": (settings.GROUP_ID, 9),
    "Gateway Unplugged": (settings.GROUP_ID, 9),

    # Low Fuel / DEF
    "Fuel up": (settings.GROUP_ID, 5),
    "Fuel level is getting down from 40%": (settings.GROUP_ID, 5),
}

# ===================== FORMAT ALERTS =====================
def format_alert(alert_name: str, data: dict) -> str:
    vehicle = data.get("vehicle", {}).get("name", "Unknown Vehicle")
    driver = data.get("driver", {}).get("name", "Unknown Driver")
    location = data.get("location", {}).get("formattedAddress", "Unknown Location")
    speed = data.get("vehicle", {}).get("speed", "N/A")
    odometer = data.get("vehicle", {}).get("odometerMeters", "N/A")
    fuel = data.get("vehicle", {}).get("fuelPercent", "N/A")

    if alert_name == "Spartak Shop":
        return (
            f"🏬 <b>Geofence Entry: Spartak Shop</b>\n\n"
            f"• Vehicle: <b>{vehicle}</b>\n"
            f"• Driver: {driver}\n"
            f"• Location: {location}"
        )

    elif alert_name == "Scheduled Maintenance by Odometer":
        return (
            f"🛠 <b>Scheduled Maintenance Due</b>\n\n"
            f"• Vehicle: <b>{vehicle}</b>\n"
            f"• Odometer: {odometer} m"
        )

    elif alert_name in ["Vehicle Severely Speeding Above Limit", "SPEEDING ZONE", "45 SPEED ZONE AHEAD"]:
        return (
            f"🚨 <b>Speeding Alert</b>\n\n"
            f"• Vehicle: <b>{vehicle}</b>\n"
            f"• Driver: {driver}\n"
            f"• Speed: {speed} mph\n"
            f"• Location: {location}"
        )

    elif alert_name in ["LINE ZONE", "LEFT LANE", "Weigh_Station_Zone", "Policy Violation Occurred"]:
        return (
            f"⚖️ <b>Weight Station / Zone Alert</b>\n\n"
            f"• Vehicle: <b>{vehicle}</b>\n"
            f"• Location: {location}\n"
            f"• Event: {alert_name}"
        )

    elif alert_name == "Engine Coolant Temperature is above 200F":
        return (
            f"🌡 <b>Engine Overheat</b>\n\n"
            f"• Vehicle: <b>{vehicle}</b>\n"
            f"• Driver: {driver}\n"
            f"• Location: {location}"
        )

    elif alert_name == "Panic Button":
        return (
            f"🚨 <b>Panic Button Pressed!</b>\n\n"
            f"• Driver: <b>{driver}</b>\n"
            f"• Vehicle: {vehicle}\n"
            f"• Location: {location}"
        )

    elif alert_name == "Vehicle Engine Idle":
        return (
            f"🛑 <b>Excessive Idling</b>\n\n"
            f"• Vehicle: <b>{vehicle}</b>\n"
            f"• Driver: {driver}\n"
            f"• Duration exceeded idle limit"
        )

    elif alert_name == "Harsh Event":
        return (
            f"⚡ <b>Harsh Driving Event</b>\n\n"
            f"• Vehicle: <b>{vehicle}</b>\n"
            f"• Driver: {driver}\n"
            f"• Event: Harsh acceleration/braking/turn"
        )

    elif alert_name in ["DASHCAM DISCONNECTED", "Gateway Unplugged"]:
        return (
            f"📷 <b>Device Disconnected</b>\n\n"
            f"• Vehicle: <b>{vehicle}</b>\n"
            f"• Alert: {alert_name}"
        )

    elif alert_name in ["Fuel up", "Fuel level is getting down from 40%"]:
        return (
            f"⛽ <b>Low Fuel Alert</b>\n\n"
            f"• Vehicle: <b>{vehicle}</b>\n"
            f"• Driver: {driver}\n"
            f"• Fuel Level: {fuel}%"
        )

    return f"⚠️ <b>{alert_name}</b>\n\n<pre>{data}</pre>"

# ===================== TELEGRAM HANDLER =====================
async def handle(request):
    """Telegram webhook handler"""
    body = await request.json()
    update = types.Update(**body)
    await dp.feed_update(bot, update)
    return web.Response(text="ok")

# ===================== SAMSARA HANDLER =====================
async def handle_samsara(request):
    """Samsara webhook handler"""
    data = await request.json()
    alert_name = data.get("alertName", "").strip()

    logging.info("Received Samsara alert: %s", alert_name)
    logging.debug("Payload: %s", data)

    chat_info = TOPIC_MAP.get(alert_name)
    if not chat_info:
        logging.warning("No topic mapping found for alert: %s", alert_name)
        chat_info = (settings.GROUP_ID, 999)  # fallback

    chat_id, thread_id = chat_info
    text = format_alert(alert_name, data)

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            message_thread_id=thread_id,
        )
        logging.info("Alert sent to chat_id=%s thread_id=%s", chat_id, thread_id)
    except Exception as e:
        logging.error("Failed to send alert %s: %s", alert_name, str(e))

    return web.Response(text="ok")

# ===================== CREATE APP =====================
def create_app(argv=None):
    app = web.Application()
    app.router.add_post("/", handle)                 # Telegram webhook
    app.router.add_post("/samsara", handle_samsara)  # Samsara alerts
    return app
