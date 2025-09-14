import os
import logging
import aiohttp
from aiohttp import web
from aiogram import Bot
from aiogram.client.bot import DefaultBotProperties
from html import escape
from dotenv import load_dotenv

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
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

GROUP_ID = int(os.getenv("GROUP_ID", "-1001234567890"))  # default group

# ===================== SAMSARA CONFIG =====================
SAMSARA_API_TOKEN = os.getenv("SAMSARA_API_TOKEN")
SAMSARA_BASE_URL = os.getenv("SAMSARA_BASE_URL", "https://api.samsara.com")

HEADERS = {"Authorization": f"Bearer {SAMSARA_API_TOKEN}"}

# ===================== TOPIC MAPPING =====================
TOPIC_MAP = {
    "Spartak Shop": (GROUP_ID, 14),
    "Scheduled Maintenance by Odometer": (GROUP_ID, 16),
    "Vehicle Severely Speeding Above Limit": (GROUP_ID, 3),
    "SPEEDING ZONE": (GROUP_ID, 3),
    "45 SPEED ZONE AHEAD": (GROUP_ID, 3),
    "LINE ZONE": (GROUP_ID, 12),
    "LEFT LANE": (GROUP_ID, 12),
    "Weigh_Station_Zone": (GROUP_ID, 12),
    "Policy Violation Occurred": (GROUP_ID, 12),
    "Engine Coolant Temperature is above 200F": (GROUP_ID, 7),
    "Panic Button": (GROUP_ID, 7),
    "Vehicle Engine Idle": (GROUP_ID, 7),
    "Harsh Event": (GROUP_ID, 7),
    "DASHCAM DISCONNECTED": (GROUP_ID, 9),
    "Gateway Unplugged": (GROUP_ID, 9),
    "Fuel up": (GROUP_ID, 5),
    "Fuel level is getting down from 40%": (GROUP_ID, 5),
}

# ===================== FORMAT ALERT =====================
def format_alert(alert_name: str, data: dict) -> str:
    vehicle = escape(str(data.get("vehicle", {}).get("name", "Unknown Vehicle")))
    driver = escape(str(data.get("driver", {}).get("name", "Unknown Driver")))
    location = escape(str(data.get("location", {}).get("formattedAddress", "Unknown Location")))
    speed = escape(str(data.get("vehicle", {}).get("speed", "N/A")))
    odometer = escape(str(data.get("vehicle", {}).get("odometerMeters", "N/A")))
    fuel = escape(str(data.get("vehicle", {}).get("fuelPercent", "N/A")))

    if alert_name == "Spartak Shop":
        return f"🏬 <b>Geofence Entry: Spartak Shop</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Location: {location}"
    elif alert_name == "Scheduled Maintenance by Odometer":
        return f"🛠 <b>Scheduled Maintenance Due</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Odometer: {odometer} m"
    elif alert_name in ["Vehicle Severely Speeding Above Limit", "SPEEDING ZONE", "45 SPEED ZONE AHEAD"]:
        return f"🚨 <b>Speeding Alert</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Speed: {speed} mph\n• Location: {location}"
    elif alert_name in ["LINE ZONE", "LEFT LANE", "Weigh_Station_Zone", "Policy Violation Occurred"]:
        return f"⚖️ <b>Weight Station / Zone Alert</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Location: {location}\n• Event: {escape(alert_name)}"
    elif alert_name == "Engine Coolant Temperature is above 200F":
        return f"🌡 <b>Engine Overheat</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Location: {location}"
    elif alert_name == "Panic Button":
        return f"🚨 <b>Panic Button Pressed!</b>\n\n• Driver: <b>{driver}</b>\n• Vehicle: {vehicle}\n• Location: {location}"
    elif alert_name == "Vehicle Engine Idle":
        return f"🛑 <b>Excessive Idling</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Duration exceeded idle limit"
    elif alert_name == "Harsh Event":
        return f"⚡ <b>Harsh Driving Event</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}"
    elif alert_name in ["DASHCAM DISCONNECTED", "Gateway Unplugged"]:
        return f"📷 <b>Device Disconnected</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Alert: {escape(alert_name)}"
    elif alert_name in ["Fuel up", "Fuel level is getting down from 40%"]:
        return f"⛽ <b>Low Fuel Alert</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Fuel Level: {fuel}%"

    return f"⚠️ <b>{escape(alert_name)}</b>\n\n<pre>{escape(str(data))}</pre>"

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
                    return {
                        "latitude": states[0].get("latitude"),
                        "longitude": states[0].get("longitude")
                    }
    return {}

# ===================== SAMSARA HANDLER =====================
async def handle_samsara(request):
    try:
        data = await request.json()
        alert_name = data.get("alertName", "").strip()
        chat_info = TOPIC_MAP.get(alert_name, (GROUP_ID, None))
        chat_id, thread_id = chat_info

        text = format_alert(alert_name, data)

        send_kwargs = {"chat_id": chat_id}
        if thread_id:
            send_kwargs["message_thread_id"] = thread_id

        # Send alert message
        await bot.send_message(text=text, **send_kwargs)
        logger.info("✅ Alert sent to chat_id=%s thread_id=%s", chat_id, thread_id)

        # Send live location if available
        location = data.get("location", {})
        latitude = location.get("latitude")
        longitude = location.get("longitude")

        vehicle_id = data.get("vehicle", {}).get("id")
        if (latitude is None or longitude is None) and vehicle_id:
            loc_data = await get_vehicle_location(vehicle_id)
            latitude = loc_data.get("latitude")
            longitude = loc_data.get("longitude")

        if latitude is not None and longitude is not None:
            await bot.send_location(latitude=latitude, longitude=longitude, **send_kwargs)
            logger.info("📍 Live location sent: (%s, %s)", latitude, longitude)

    except Exception as e:
        logger.exception("❌ Failed to send alert")

    return web.Response(text="ok")

# ===================== CREATE APP =====================
def create_app(argv=None):
    app = web.Application()
    app.router.add_post("/samsara", handle_samsara)
    return app

# ===================== REQUIRED ENV VARIABLES =====================
"""
TELEGRAM_BOT_TOKEN=<your bot token>
SAMSARA_API_TOKEN=<your samsara API token>
GROUP_ID=-1003067846983
LOG_LEVEL=INFO
SAMSARA_BASE_URL=https://api.samsara.com
"""
