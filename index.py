import os
import logging
import aiohttp
from aiohttp import web
from aiogram import Bot
from dotenv import load_dotenv
from aiogram.client.bot import DefaultBotProperties

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

GROUP_ID = int(os.getenv("GROUP_ID", "-1001234567890"))

# ===================== SAMSARA CONFIG =====================
SAMSARA_API_TOKEN = os.getenv("SAMSARA_API_TOKEN")
SAMSARA_BASE_URL = os.getenv("SAMSARA_BASE_URL", "https://api.samsara.com")

HEADERS = {
    "Authorization": f"Bearer {SAMSARA_API_TOKEN}"
}

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
def format_alert(data: dict) -> tuple[str, float | None, float | None]:
    """Return formatted alert text, latitude, longitude."""
    alert_name = data.get("alertName") or data.get("eventType", "Unknown Alert")
    
    # Use geofence name for GeofenceEntry/Exit
    if alert_name in ["GeofenceEntry", "GeofenceExit"]:
        address = data.get("data", {}).get("address", {})
        alert_name = address.get("name", "Unknown Zone")

    vehicle = data.get("vehicle", {}).get("name", "Unknown Vehicle")
    driver = data.get("driver", {}).get("name", "Unknown Driver")
    location_info = data.get("location", {}) or data.get("data", {}).get("address", {})
    location_name = location_info.get("formattedAddress", location_info.get("name", "Unknown Location"))
    latitude = location_info.get("latitude")
    longitude = location_info.get("longitude")
    speed = data.get("vehicle", {}).get("speed", "N/A")
    odometer = data.get("vehicle", {}).get("odometerMeters", "N/A")
    fuel = data.get("vehicle", {}).get("fuelPercent", "N/A")

    if alert_name == "Spartak Shop":
        text = f"🏬 <b>Geofence Entry: Spartak Shop</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Location: {location_name}"
    elif alert_name == "Scheduled Maintenance by Odometer":
        text = f"🛠 <b>Scheduled Maintenance Due</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Odometer: {odometer} m"
    elif alert_name in ["Vehicle Severely Speeding Above Limit", "SPEEDING ZONE", "45 SPEED ZONE AHEAD"]:
        text = f"🚨 <b>Speeding Alert</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Speed: {speed} mph\n• Location: {location_name}"
    elif alert_name in ["LINE ZONE", "LEFT LANE", "Weigh_Station_Zone", "Policy Violation Occurred"]:
        text = f"⚖️ <b>Weight Station / Zone Alert</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Location: {location_name}\n• Event: {alert_name}"
    elif alert_name == "Engine Coolant Temperature is above 200F":
        text = f"🌡 <b>Engine Overheat</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Location: {location_name}"
    elif alert_name == "Panic Button":
        text = f"🚨 <b>Panic Button Pressed!</b>\n\n• Driver: <b>{driver}</b>\n• Vehicle: {vehicle}\n• Location: {location_name}"
    elif alert_name == "Vehicle Engine Idle":
        text = f"🛑 <b>Excessive Idling</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Duration exceeded idle limit"
    elif alert_name == "Harsh Event":
        text = f"⚡ <b>Harsh Driving Event</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}"
    elif alert_name in ["DASHCAM DISCONNECTED", "Gateway Unplugged"]:
        text = f"📷 <b>Device Disconnected</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Alert: {alert_name}"
    elif alert_name in ["Fuel up", "Fuel level is getting down from 40%"]:
        text = f"⛽ <b>Low Fuel Alert</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Fuel Level: {fuel}%"
    else:
        text = f"⚠️ <b>{alert_name}</b>\n\n<pre>{data}</pre>"

    return text, latitude, longitude, alert_name

# ===================== GET VEHICLE LOCATION FROM SAMSARA =====================
async def get_vehicle_location(vehicle_id: str) -> dict:
    url = f"{SAMSARA_BASE_URL}/fleet/vehicles/states"
    params = {"vehicleIds": vehicle_id}
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                result = await resp.json()
                states = result.get("data", [])
                if states:
                    return {"latitude": states[0].get("latitude"), "longitude": states[0].get("longitude")}
    return {}

# ===================== SAMSARA HANDLER =====================
async def handle_samsara(request):
    data = await request.json()
    text, latitude, longitude, alert_name = format_alert(data)

    # Determine chat_id/thread_id
    chat_info = TOPIC_MAP.get(alert_name, (GROUP_ID, None))
    chat_id, thread_id = chat_info
    send_kwargs = {"chat_id": chat_id}
    if thread_id:
        send_kwargs["message_thread_id"] = thread_id

    try:
        # Send alert
        await bot.send_message(text=text, **send_kwargs)
        logger.info("✅ Alert sent to chat_id=%s thread_id=%s", chat_id, thread_id)

        # Send live location
        vehicle_id = data.get("vehicle", {}).get("id")
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

# ===================== REQUIRED ENVIRONMENT VARIABLES =====================
"""
TELEGRAM_BOT_TOKEN=<your bot token>
SAMSARA_API_TOKEN=<your samsara API token>
GROUP_ID=-1003067846983
LOG_LEVEL=INFO
SAMSARA_BASE_URL=https://api.samsara.com
"""
