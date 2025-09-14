import os
import logging
from aiohttp import web
from aiogram import Bot

# ===================== LOGGING =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ===================== BOT INIT =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "-1001234567890"))  # default test group
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")

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
    vehicle = data.get("vehicle", {}).get("name", "Unknown Vehicle")
    driver = data.get("driver", {}).get("name", "Unknown Driver")
    location = data.get("location", {}).get("formattedAddress", "Unknown Location")
    speed = data.get("vehicle", {}).get("speed", "N/A")
    odometer = data.get("vehicle", {}).get("odometerMeters", "N/A")
    fuel = data.get("vehicle", {}).get("fuelPercent", "N/A")

    if alert_name == "Spartak Shop":
        return f"🏬 <b>Geofence Entry: Spartak Shop</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Location: {location}"
    elif alert_name == "Scheduled Maintenance by Odometer":
        return f"🛠 <b>Scheduled Maintenance Due</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Odometer: {odometer} m"
    elif alert_name in ["Vehicle Severely Speeding Above Limit", "SPEEDING ZONE", "45 SPEED ZONE AHEAD"]:
        return f"🚨 <b>Speeding Alert</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Speed: {speed} mph\n• Location: {location}"
    elif alert_name in ["LINE ZONE", "LEFT LANE", "Weigh_Station_Zone", "Policy Violation Occurred"]:
        return f"⚖️ <b>Weight Station / Zone Alert</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Location: {location}\n• Event: {alert_name}"
    elif alert_name == "Engine Coolant Temperature is above 200F":
        return f"🌡 <b>Engine Overheat</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Location: {location}"
    elif alert_name == "Panic Button":
        return f"🚨 <b>Panic Button Pressed!</b>\n\n• Driver: <b>{driver}</b>\n• Vehicle: {vehicle}\n• Location: {location}"
    elif alert_name == "Vehicle Engine Idle":
        return f"🛑 <b>Excessive Idling</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Duration exceeded idle limit"
    elif alert_name == "Harsh Event":
        return f"⚡ <b>Harsh Driving Event</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}"
    elif alert_name in ["DASHCAM DISCONNECTED", "Gateway Unplugged"]:
        return f"📷 <b>Device Disconnected</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Alert: {alert_name}"
    elif alert_name in ["Fuel up", "Fuel level is getting down from 40%"]:
        return f"⛽ <b>Low Fuel Alert</b>\n\n• Vehicle: <b>{vehicle}</b>\n• Driver: {driver}\n• Fuel Level: {fuel}%"

    return f"⚠️ <b>{alert_name}</b>\n\n<pre>{data}</pre>"

# ===================== SAMSARA HANDLER =====================
async def handle_samsara(request):
    data = await request.json()
    alert_name = data.get("alertName", "").strip()

    logging.info("Received Samsara alert: %s", alert_name)

    chat_info = TOPIC_MAP.get(alert_name, (GROUP_ID, None))
    chat_id, thread_id = chat_info
    text = format_alert(alert_name, data)

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            message_thread_id=thread_id
        )
        logging.info("✅ Alert sent to chat_id=%s thread_id=%s", chat_id, thread_id)
    except Exception as e:
        logging.error("❌ Failed to send alert %s: %s", alert_name, str(e))

    return web.Response(text="ok")

# ===================== APP =====================
def create_app(argv=None):
    app = web.Application()
    app.router.add_post("/samsara", handle_samsara)  # only samsara webhook
    return app
