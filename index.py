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

GROUP_ID = int(os.getenv("GROUP_ID", "-1001234567890"))

# ===================== TOPIC MAPPING =====================
TOPIC_MAP = {
    "spartak": (GROUP_ID, 14),
    "scheduled maintenance": (GROUP_ID, 16),
    "speed": (GROUP_ID, 3),
    "zone": (GROUP_ID, 12),   # covers weigh_station_zone, line zone, left lane
    "coolant": (GROUP_ID, 7),
    "panic": (GROUP_ID, 7),
    "idle": (GROUP_ID, 7),
    "harsh": (GROUP_ID, 7),
    "dashcam": (GROUP_ID, 9),
    "gateway": (GROUP_ID, 9),
    "fuel": (GROUP_ID, 5),
}

# ===================== FORMAT ALERT =====================
def format_alert(alert_name: str, data: dict) -> str:
    vehicle = escape(str(data.get("vehicle", {}).get("name", "Unknown Vehicle")))
    driver = escape(str(data.get("driver", {}).get("name", "Unknown Driver")))
    location = escape(str(data.get("location", {}).get("formattedAddress", "Unknown Location")))
    speed = escape(str(data.get("vehicle", {}).get("speed", "N/A")))
    odometer = escape(str(data.get("vehicle", {}).get("odometerMeters", "N/A")))
    fuel = escape(str(data.get("vehicle", {}).get("fuelPercent", "N/A")))

    name_lower = alert_name.lower()

    if "spartak" in name_lower:
        return f"🏬 <b>Geofence Entry: Spartak Shop</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Location: {location}"
    elif "maintenance" in name_lower:
        return f"🛠 <b>Scheduled Maintenance Due</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Odometer: {odometer} m"
    elif "speed" in name_lower:
        return f"🚨 <b>Speeding Alert</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Speed: {speed} mph\n• Location: {location}"
    elif "zone" in name_lower:
        return f"⚖️ <b>Weight Station / Zone Alert</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Location: {location}\n• Event: {escape(alert_name)}"
    elif "coolant" in name_lower:
        return f"🌡 <b>Engine Overheat</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Location: {location}"
    elif "panic" in name_lower:
        return f"🚨 <b>Panic Button Pressed!</b>\n\n• Driver: <b>{driver}</b>\n• Vehicle: {vehicle}\n• Location: {location}"
    elif "idle" in name_lower:
        return f"🛑 <b>Excessive Idling</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Duration exceeded idle limit"
    elif "harsh" in name_lower:
        return f"⚡ <b>Harsh Driving Event</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}"
    elif "dashcam" in name_lower or "gateway" in name_lower:
        return f"📷 <b>Device Disconnected</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Alert: {escape(alert_name)}"
    elif "fuel" in name_lower:
        return f"⛽ <b>Low Fuel Alert</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Fuel Level: {fuel}%"

    return f"⚠️ <b>{escape(alert_name)}</b>\n\n<pre>{escape(str(data))}</pre>"

# ===================== GET VEHICLE LOCATION =====================
async def get_vehicle_location(vehicle_id: str) -> dict:
    url = f"{os.getenv('SAMSARA_BASE_URL')}/fleet/vehicles/states"
    params = {"vehicleIds": vehicle_id}
    async with aiohttp.ClientSession(headers={"Authorization": f"Bearer {os.getenv('SAMSARA_API_TOKEN')}"}) as session:
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
        alert_name = data.get("name", "").strip()
        name_lower = alert_name.lower()

        # Match topic dynamically
        topic_info = None
        for key, info in TOPIC_MAP.items():
            if key in name_lower:
                topic_info = info
                break

        if topic_info:
            chat_id, thread_id = topic_info
        else:
            chat_id, thread_id = GROUP_ID, None
            logger.warning("⚠️ Unknown alert received: '%s'. Sending to General topic.", alert_name)

        text = format_alert(alert_name, data)

        send_kwargs = {"chat_id": chat_id}
        if thread_id:
            send_kwargs["message_thread_id"] = thread_id

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

    except Exception:
        logger.exception("❌ Failed to send alert")

    return web.Response(text="ok")

# ===================== CREATE APP =====================
def create_app(argv=None):
    app = web.Application()
    app.router.add_post("/samsara", handle_samsara)
    return app
