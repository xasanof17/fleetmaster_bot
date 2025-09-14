import os
import logging
import aiohttp
from aiohttp import web
from aiogram import Bot
from aiogram.client.bot import DefaultBotProperties
from dotenv import load_dotenv
from html import escape

load_dotenv()

# ===================== LOGGING =====================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ===================== BOT INIT =====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment variables")

bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)

GROUP_ID = int(os.getenv("GROUP_ID", "-1003067846983"))  # default group

# ===================== SAMSARA CONFIG =====================
SAMSARA_API_TOKEN = os.getenv("SAMSARA_API_TOKEN")
SAMSARA_BASE_URL = os.getenv("SAMSARA_BASE_URL", "https://api.samsara.com")

HEADERS = {
    "Authorization": f"Bearer {SAMSARA_API_TOKEN}"
}

# ===================== TOPIC MAPPING =====================
# Mapping Samsara alert names to group_id and optional thread_id
TOPIC_MAP = {
    "Spartak Shop": (GROUP_ID, None),
    "Scheduled Maintenance by Odometer": (GROUP_ID, None),
    "Vehicle Severely Speeding Above Limit": (GROUP_ID, None),
    "SPEEDING ZONE": (GROUP_ID, None),
    "45 SPEED ZONE AHEAD": (GROUP_ID, None),
    "LINE ZONE": (GROUP_ID, None),
    "LEFT LANE": (GROUP_ID, None),
    "Weigh_Station_Zone": (GROUP_ID, None),
    "Policy Violation Occurred": (GROUP_ID, None),
    "Engine Coolant Temperature is above 200F": (GROUP_ID, None),
    "Panic Button": (GROUP_ID, None),
    "Vehicle Engine Idle": (GROUP_ID, None),
    "Harsh Event": (GROUP_ID, None),
    "DASHCAM DISCONNECTED": (GROUP_ID, None),
    "Gateway Unplugged": (GROUP_ID, None),
    "Fuel up": (GROUP_ID, None),
    "Fuel level is getting down from 40%": (GROUP_ID, None),
}

# ===================== FORMAT ALERT =====================
def format_alert(alert_name: str, data: dict) -> str:
    vehicle = escape(data.get("vehicle", {}).get("name") or "Unknown Vehicle")
    driver = escape(data.get("driver", {}).get("name") or "Unknown Driver")
    location = escape(data.get("location", {}).get("formattedAddress") or "Unknown Location")
    speed = escape(str(data.get("vehicle", {}).get("speed") or "N/A"))
    odometer = escape(str(data.get("vehicle", {}).get("odometerMeters") or "N/A"))
    fuel = escape(str(data.get("vehicle", {}).get("fuelPercent") or "N/A"))

    if alert_name == "Spartak Shop":
        return f"🏬 <b>Geofence Entry: Spartak Shop</b>\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Location: {location}"
    elif alert_name == "Scheduled Maintenance by Odometer":
        return f"🛠 <b>Scheduled Maintenance Due</b>\n• Vehicle: <b>{vehicle}</b>\n• Odometer: {odometer} m"
    elif alert_name in ["Vehicle Severely Speeding Above Limit", "SPEEDING ZONE", "45 SPEED ZONE AHEAD"]:
        return f"🚨 <b>Speeding Alert</b>\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Speed: {speed} mph\n• Location: {location}"
    elif alert_name in ["LINE ZONE", "LEFT LANE", "Weigh_Station_Zone", "Policy Violation Occurred"]:
        return f"⚖️ <b>Weight Station / Zone Alert</b>\n• Vehicle: <b>{vehicle}</b>\n• Location: {location}\n• Event: {alert_name}"
    elif alert_name == "Panic Button":
        return f"🚨 <b>Panic Button Pressed!</b>\n• Driver: <b>{driver}</b>\n• Vehicle: {vehicle}\n• Location: {location}"
    elif alert_name == "Vehicle Engine Idle":
        return f"🛑 <b>Excessive Idling</b>\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Duration exceeded idle limit"
    elif alert_name == "Harsh Event":
        return f"⚡ <b>Harsh Driving Event</b>\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}"
    elif alert_name in ["DASHCAM DISCONNECTED", "Gateway Unplugged"]:
        return f"📷 <b>Device Disconnected</b>\n• Vehicle: <b>{vehicle}</b>\n• Alert: {alert_name}"
    elif alert_name in ["Fuel up", "Fuel level is getting down from 40%"]:
        return f"⛽ <b>Low Fuel Alert</b>\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Fuel Level: {fuel}%"

    return f"⚠️ <b>{alert_name}</b>\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}</b>\n• Location: {location}"
# ===================== GET VEHICLE LOCATION =====================
async def get_vehicle_location(vehicle_id: str) -> dict:
    url = f"{SAMSARA_BASE_URL}/fleet/vehicles/states"
    params = {"vehicleIds": vehicle_id}
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                result = await resp.json()
                states = result.get("data", [])
                if states:
                    lat = states[0].get("latitude")
                    lon = states[0].get("longitude")
                    return {"latitude": lat, "longitude": lon}
    return {}

# ===================== SAMSARA HANDLER =====================
async def handle_samsara(request):
    payload = await request.json()
    alert_name = payload.get("alertName", "").strip()
    chat_info = TOPIC_MAP.get(alert_name, (GROUP_ID, None))
    chat_id, thread_id = chat_info
    text = format_alert(alert_name, payload)

    send_kwargs = {"chat_id": chat_id}
    if thread_id:
        send_kwargs["message_thread_id"] = thread_id

    try:
        await bot.send_message(text=text, **send_kwargs)
        logger.info("✅ Alert sent to chat_id=%s thread_id=%s", chat_id, thread_id)

        # Send live location if available
        location = payload.get("location", {})
        latitude = location.get("latitude")
        longitude = location.get("longitude")

        vehicle_id = payload.get("vehicle", {}).get("id")
        if (latitude is None or longitude is None) and vehicle_id:
            loc_data = await get_vehicle_location(vehicle_id)
            latitude = loc_data.get("latitude")
            longitude = loc_data.get("longitude")

        if latitude is not None and longitude is not None:
            await bot.send_location(latitude=latitude, longitude=longitude, **send_kwargs)
            logger.info("📍 Live location sent: (%s, %s)", latitude, longitude)

    except Exception as e:
        logger.exception("❌ Failed to send alert %s", alert_name)

    return web.Response(text="ok")

# ===================== CREATE APP =====================
def create_app(argv=None):
    app = web.Application()
    app.router.add_post("/samsara", handle_samsara)
    return app

# ===================== START SERVER =====================
if __name__ == "__main__":
    import asyncio

    app = create_app()
    port = int(os.getenv("PORT", 8080))
    logger.info(f"🌐 Starting server on 0.0.0.0:{port}")
    web.run_app(app, host="0.0.0.0", port=port)
