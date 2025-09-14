import os
import logging
import aiohttp
from aiohttp import web
from aiogram import Bot
from aiogram.client.bot import DefaultBotProperties
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

bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)

GROUP_ID = int(os.getenv("GROUP_ID", "-1003067846983"))

# ===================== SAMSARA CONFIG =====================
SAMSARA_API_TOKEN = os.getenv("SAMSARA_API_TOKEN")
SAMSARA_BASE_URL = os.getenv("SAMSARA_BASE_URL", "https://api.samsara.com")
HEADERS = {"Authorization": f"Bearer {SAMSARA_API_TOKEN}"}

# ===================== THREAD TRACKING =====================
THREADS = {}  # vehicle_id + alert_name => thread_id

# ===================== ALERT TYPE MAPPING =====================
ALERT_CATEGORIES = {
    "geofence": {"emoji": "🏬", "label": "Geofence Alert"},
    "speeding": {"emoji": "🚨", "label": "Speeding Alert"},
    "maintenance": {"emoji": "🛠", "label": "Maintenance Alert"},
    "engine_idle": {"emoji": "🛑", "label": "Excessive Idling"},
    "fuel": {"emoji": "⛽", "label": "Fuel Alert"},
    "panic": {"emoji": "🚨", "label": "Panic Button Pressed!"},
    "harsh": {"emoji": "⚡", "label": "Harsh Driving Event"},
    "device_disconnect": {"emoji": "📷", "label": "Device Disconnected"},
    "temperature": {"emoji": "🌡", "label": "Engine Overheat"},
    "default": {"emoji": "⚠️", "label": "Alert"}
}

def categorize_alert(alert_name: str) -> dict:
    name = alert_name.lower()
    if "shop" in name or "weigh" in name or "zone" in name:
        return ALERT_CATEGORIES["geofence"]
    if "speed" in name:
        return ALERT_CATEGORIES["speeding"]
    if "maintenance" in name or "odometer" in name:
        return ALERT_CATEGORIES["maintenance"]
    if "engine idle" in name:
        return ALERT_CATEGORIES["engine_idle"]
    if "fuel" in name:
        return ALERT_CATEGORIES["fuel"]
    if "panic" in name:
        return ALERT_CATEGORIES["panic"]
    if "harsh" in name:
        return ALERT_CATEGORIES["harsh"]
    if "dashcam" in name or "gateway" in name:
        return ALERT_CATEGORIES["device_disconnect"]
    if "temperature" in name:
        return ALERT_CATEGORIES["temperature"]
    return ALERT_CATEGORIES["default"]

# ===================== FORMAT ALERT =====================
def format_alert(data: dict) -> tuple[str, float | None, float | None, str, str]:
    alert_name = data.get("alertName") or data.get("eventType", "Unknown Alert")
    vehicle = data.get("vehicle", {}).get("name", "Unknown Vehicle")
    driver = data.get("driver", {}).get("name", "Unknown Driver")
    location_info = data.get("location", {}) or data.get("data", {}).get("address", {})
    location_name = location_info.get("formattedAddress", location_info.get("name", "Unknown Location"))
    latitude = location_info.get("latitude")
    longitude = location_info.get("longitude")
    speed = data.get("vehicle", {}).get("speed", "N/A")
    odometer = data.get("vehicle", {}).get("odometerMeters", "N/A")
    fuel = data.get("vehicle", {}).get("fuelPercent", "N/A")

    category = categorize_alert(alert_name)
    emoji = category["emoji"]
    label = category["label"]

    text = f"{emoji} <b>{label}</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Location: {location_name}\n• Speed: {speed} mph\n• Odometer: {odometer} m\n• Fuel: {fuel}%"
    return text, latitude, longitude, alert_name, vehicle

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
                    return {"latitude": states[0].get("latitude"), "longitude": states[0].get("longitude")}
    return {}

# ===================== SAMSARA HANDLER =====================
async def handle_samsara(request):
    data = await request.json()
    text, latitude, longitude, alert_name, vehicle_name = format_alert(data)
    vehicle_id = data.get("vehicle", {}).get("id")

    thread_key = f"{vehicle_id}_{alert_name}"
    thread_id = THREADS.get(thread_key)

    try:
        # Send message
        if thread_id is None:
            message = await bot.send_message(
                chat_id=GROUP_ID,
                text=text,
                message_thread_name=f"{vehicle_name} | {alert_name}"[:128]
            )
            thread_id = message.message_thread_id
            THREADS[thread_key] = thread_id
            logger.info("✅ New thread created: %s | thread_id=%s", alert_name, thread_id)
        else:
            await bot.send_message(
                chat_id=GROUP_ID,
                text=text,
                message_thread_id=thread_id
            )
            logger.info("✅ Alert sent: %s | thread_id=%s", alert_name, thread_id)

        # Send location
        if (latitude is None or longitude is None) and vehicle_id:
            loc_data = await get_vehicle_location(vehicle_id)
            latitude = loc_data.get("latitude")
            longitude = loc_data.get("longitude")

        if latitude is not None and longitude is not None:
            await bot.send_location(
                chat_id=GROUP_ID,
                latitude=latitude,
                longitude=longitude,
                message_thread_id=thread_id
            )
            logger.info("📍 Live location sent: (%s, %s)", latitude, longitude)

    except Exception as e:
        logger.exception("❌ Failed to send alert: %s", alert_name)

    return web.Response(text="ok")

# ===================== CREATE APP =====================
def create_app(argv=None):
    app = web.Application()
    app.router.add_post("/samsara", handle_samsara)
    return app
