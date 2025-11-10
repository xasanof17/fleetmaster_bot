#!/usr/bin/env python3
"""
Fleet Master Bot — Samsara → Telegram (Templates + Dynamic Alert Mapping)

• Async aiohttp webhook server + aiogram Telegram sender
• Pulls /alerts/configurations from Samsara, merges with static specials
• Chooses the right template (exactly your formats) and thread per event
• Refreshes alert mapping every 12 hours
"""

import os
import json
import logging
import datetime
import asyncio
import aiohttp
from typing import Dict, Tuple, Optional, Any

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from dotenv import load_dotenv
from html import escape

# ────────────────────────────── BOOTSTRAP ──────────────────────────────
load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("fleetmaster")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SAMSARA_API_TOKEN = os.getenv("SAMSARA_API_TOKEN")
SAMSARA_BASE_URL = os.getenv("SAMSARA_BASE_URL", "https://api.samsara.com")
GROUP_ID = int(os.getenv("GROUP_ID", "-1003067846983"))
PORT = int(os.getenv("PORT", "8080"))

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is required")

bot = Bot(token=TELEGRAM_BOT_TOKEN,
          default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

_session: Optional[aiohttp.ClientSession] = None

async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
    return _session

async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()
    _session = None

# ────────────────────────────── THREAD MAP ─────────────────────────────
# Telegram forum thread IDs (message topics) under your GROUP_ID
THREADS = {
    "SPEEDING": 3,
    "CRITICAL": 7,
    "LOW_FUEL": 5,
    "DASHCAM": 9,
    "WEIGHT": 12,
    "SPARTAK": 14,
    "SCHEDULED_MAINT": 16,
    "GENERAL": None,
}

# ───────────────────────── STATIC SPECIALS (kept) ──────────────────────
# You can add address-based or special alert IDs here
ALERT_MAPPINGS: Dict[str, Dict[str, Any]] = {
    # Spartak Shop (explicit alert UUID from your board)
    "219a987e-b704-4e08-a825-8da11c58d33d": {
        "topic": (GROUP_ID, THREADS["SPARTAK"], "🏬 SPARTAK SHOP"),
        "template": "SPARTAK",
        "priority": "MEDIUM",
        "name": "Spartak Shop"
    },
    # Low Fuel
    "f87a1f80-c2ac-42fb-a371-069d696fe2cc": {
        "topic": (GROUP_ID, THREADS["LOW_FUEL"], "⛽️ LOW FUEL / DEF"),
        "template": "LOW_FUEL",
        "priority": "MEDIUM",
        "name": "Fuel below threshold"
    },
}

# Optional: hard pin popular address ids to threads (weight stations, Spartak, etc.)
ALERT_MAPPINGS.update({
    # Weight stations
    "497ee2fc-308c-4502-8f53-703f89b4c37f": {"topic": (GROUP_ID, THREADS["WEIGHT"], "⚖️ WEIGHT STATIONS"), "template": "WEIGHT"},
    # Speed zones
    "6ac80dbb-1457-4713-b6fb-8b61ff631f2f": {"topic": (GROUP_ID, THREADS["SPEEDING"], "🚨 OVER SPEEDING"), "template": "SPEEDING"},
    "c2aa07e4-4cca-4cdd-96f2-0fa6f0a17cd8": {"topic": (GROUP_ID, THREADS["SPEEDING"], "🚨 OVER SPEEDING"), "template": "SPEEDING"},
    # Spartak shop
    "219a987e-b704-4e08-a825-8da11c58d33d": {"topic": (GROUP_ID, THREADS["SPARTAK"], "🏬 SPARTAK SHOP"), "template": "SPARTAK"},
    # Dashcams / Gateway
    "3dc1e918-d864-427a-abc6-b95dabb3a45f": {"topic": (GROUP_ID, THREADS["DASHCAM"], "📷 DASHCAMS / GATEWAY"), "template": "DASHCAM"},
    "e3c9f1de-01b4-474e-b273-9e8473f7c22c": {"topic": (GROUP_ID, THREADS["DASHCAM"], "📷 DASHCAMS / GATEWAY"), "template": "DASHCAM"},
    # Panic / Harsh events
    "67ccad3d-7f19-400a-aaab-650b9dd09869": {"topic": (GROUP_ID, THREADS["CRITICAL"], "🚨 Panic Button"), "template": "CRITICAL:panic"},
    "6dc763d6-4adb-4d8f-a8e8-b1d0a7a8ef0d": {"topic": (GROUP_ID, THREADS["CRITICAL"], "⚡ Harsh Driving Event"), "template": "CRITICAL:harsh"},
    # Maintenance
    "6004a43b-eb59-4ea4-ba17-8464ad955f76": {"topic": (GROUP_ID, THREADS["SCHEDULED_MAINT"], "🛠 Scheduled Maintenance by Odometer"), "template": "SCHEDULED"},
    # Fuel
    "f87a1f80-c2ac-42fb-a371-069d696fe2cc": {"topic": (GROUP_ID, THREADS["LOW_FUEL"], "⛽️ LOW FUEL / DEF"), "template": "LOW_FUEL"},
    "705d3b8a-ddf1-4864-a81c-42e64f5a4967": {"topic": (GROUP_ID, THREADS["LOW_FUEL"], "⛽️ LOW FUEL / DEF"), "template": "LOW_FUEL"},
    # TPMS / Tire pressure
    "9d03a1c8-2755-4005-9177-c5b81e0e06e4": {"topic": (GROUP_ID, THREADS["CRITICAL"], "🛞 Tire Pressure Alert"), "template": "CRITICAL:overheat"},
    "0accfde8-b24a-48c6-b5ec-27aedfdb8bc1": {"topic": (GROUP_ID, THREADS["CRITICAL"], "🛞 Tire Pressure Alert"), "template": "CRITICAL:overheat"},
    "47342d86-5cc3-4188-b498-81cd49dc2b22": {"topic": (GROUP_ID, THREADS["CRITICAL"], "🛞 Tire Pressure Alert"), "template": "CRITICAL:overheat"},
})


# ─────────────────────────── UTILITIES ────────────────────────────────
def now_dt() -> datetime.datetime:
    return datetime.datetime.now()

def fmt_date(dt: Optional[datetime.datetime] = None) -> str:
    d = dt or now_dt()
    return d.strftime("%d.%m.%Y")

def fmt_time(dt: Optional[datetime.datetime] = None) -> str:
    d = dt or now_dt()
    return d.strftime("%H:%M:%S")

def coalesce_location_text(address: dict) -> str:
    """
    Prefer formattedAddress, else name; plain text (no link) to match templates.
    """
    if not isinstance(address, dict):
        return "Unknown"
    fa = address.get("formattedAddress")
    nm = address.get("name")
    return fa or nm or "Unknown"

def extract_lat_lon(address: dict) -> Tuple[Optional[float], Optional[float]]:
    if not isinstance(address, dict):
        return None, None
    g = address.get("geofence", {})
    circ = g.get("circle", {})
    lat = circ.get("latitude")
    lon = circ.get("longitude")
    if lat and lon:
        return lat, lon
    # polygon fallback
    poly = g.get("polygon", {})
    verts = poly.get("vertices", [])
    if verts:
        v = verts[0]
        return v.get("latitude"), v.get("longitude")
    return None, None

def extract_speed_limit_from_text(address: dict) -> Optional[int]:
    """
    Lightweight heuristic from address/name text: finds 'xx mph' or common limits.
    """
    text = f"{address.get('name','')} {address.get('formattedAddress','')}".lower()
    # exact 'xx mph'
    import re
    m = re.search(r"(\d{2,3})\s*mph", text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    # common defaults
    for n in [80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 25]:
        if f"{n}" in text and ("speed" in text or "zone" in text):
            return n
    if any(k in text for k in ["interstate", "i-", "hwy", "highway"]):
        return 70
    return None

def mph(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except Exception:
        return None

# ───────────────────── SAMSARA DYNAMIC CONFIG SYNC ────────────────────
async def fetch_alert_configurations() -> Dict[str, Dict[str, Any]]:
    """
    GET /alerts/configurations → build alert-id → routing/template mapping.
    We infer topic + template from the alert name/category/severity.
    """
    if not SAMSARA_API_TOKEN:
        log.warning("SAMSARA_API_TOKEN not set; skipping dynamic alert sync.")
        return {}
    try:
        session = await get_session()
        url = f"{SAMSARA_BASE_URL}/alerts/configurations"
        headers = {"Authorization": f"Bearer {SAMSARA_API_TOKEN}"}
        params = {"limit": 200}
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                log.warning("Failed to fetch alert configurations: %s", resp.status)
                return {}
            body = await resp.json()
            configs = body.get("data", [])
    except Exception as e:
        log.error("Error fetching alert configurations: %s", e)
        return {}

    def pick_topic_and_template(name: str, category: str) -> Tuple[int, Optional[int], str, str]:
        nm = (name or "").lower()
        cat = (category or "").lower()

        # SPEEDING OF WEIGHT STATION (hybrid): if both "speed" & "weight" seen
        if ("speed" in nm or "speed" in cat) and ("weight" in nm or "weight" in cat):
            return GROUP_ID, THREADS["WEIGHT"], "🚨 SPEEDING OF WEIGHT STATION", "SPEEDING_OF_WEIGHT"

        if "weight" in nm or "weight" in cat or "weigh" in nm:
            return GROUP_ID, THREADS["WEIGHT"], "⚖️ WEIGHT STATIONS", "WEIGHT"

        if "speed" in nm or "speed" in cat:
            return GROUP_ID, THREADS["SPEEDING"], "🚨 OVER SPEEDING", "SPEEDING"

        if "dashcam" in nm or "gateway" in nm or "device" in nm or "disconnect" in nm:
            return GROUP_ID, THREADS["DASHCAM"], "📷 DASHCAMS / GATEWAY", "DASHCAM"

        if "fuel" in nm or "def" in nm:
            return GROUP_ID, THREADS["LOW_FUEL"], "⛽️ LOW FUEL / DEF", "LOW_FUEL"

        if "maintenance" in nm or "odometer" in nm or "service" in nm:
            return GROUP_ID, THREADS["SCHEDULED_MAINT"], "🛠 Scheduled Maintenance by Odometer", "SCHEDULED"

        if "panic" in nm or "engine" in nm or "crash" in nm or "harsh" in nm or "distract" in nm or "brake" in nm or "turn" in nm or "rolling" in nm or "overheat" in nm:
            return GROUP_ID, THREADS["CRITICAL"], "🚨 CRITICAL MAINTENANCE", "CRITICAL"

        if "spartak" in nm or "shop" in nm:
            return GROUP_ID, THREADS["SPARTAK"], "🏬 SPARTAK SHOP", "SPARTAK"

        return GROUP_ID, THREADS["GENERAL"], "📋 General", "GENERAL"

    dynamic: Dict[str, Dict[str, Any]] = {}
    for c in configs:
        if not c.get("enabled", False):
            continue
        alert_id = c.get("id")
        if not alert_id:
            continue
        name = c.get("name", "")
        category = c.get("category", "")
        severity = (c.get("severity", "MEDIUM") or "MEDIUM").upper()

        chat_id, thread_id, topic_name, template_key = pick_topic_and_template(name, category)
        dynamic[alert_id] = {
            "topic": (chat_id, thread_id, topic_name),
            "template": template_key,
            "priority": severity,
            "name": name,
        }

    log.info("Loaded %d dynamic alert mappings from Samsara", len(dynamic))
    return dynamic

async def refresh_alerts_periodically():
    global ALERT_MAPPINGS
    while True:
        await asyncio.sleep(12 * 3600)
        try:
            new_map = await fetch_alert_configurations()
            if new_map:
                ALERT_MAPPINGS.update(new_map)
                log.info("Refreshed alert mappings: %d total", len(ALERT_MAPPINGS))
        except Exception as e:
            log.error("Alert refresh loop error: %s", e)

# ───────────────────────── VEHICLE/DRIVER ENRICHMENT ──────────────────
async def get_vehicle_details(vehicle_id: str) -> dict:
    if not SAMSARA_API_TOKEN or not vehicle_id:
        return {}
    try:
        session = await get_session()
        url = f"{SAMSARA_BASE_URL}/fleet/vehicles"
        headers = {"Authorization": f"Bearer {SAMSARA_API_TOKEN}"}
        params = {"vehicleIds": vehicle_id}
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                items = data.get("data", [])
                return items[0] if items else {}
    except Exception as e:
        log.warning("Vehicle lookup failed: %s", e)
    return {}

async def get_driver_details(driver_id: str) -> dict:
    if not SAMSARA_API_TOKEN or not driver_id:
        return {}
    try:
        session = await get_session()
        url = f"{SAMSARA_BASE_URL}/fleet/drivers"
        headers = {"Authorization": f"Bearer {SAMSARA_API_TOKEN}"}
        params = {"driverIds": driver_id}
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                items = data.get("data", [])
                return items[0] if items else {}
    except Exception as e:
        log.warning("Driver lookup failed: %s", e)
    return {}

# ────────────────────────── TEMPLATE RENDERERS ────────────────────────
def _veh_name(data: dict) -> str:
    v = data.get("vehicle", {}) if isinstance(data, dict) else {}
    return (
        v.get("name")
        or v.get("id")
        or v.get("serial")
        or v.get("licensePlate")
        or "Unknown"
    )

def _driver_name(data: dict) -> str:
    d = data.get("driver", {}) if isinstance(data, dict) else {}
    return d.get("name") or "N/A"

def _address_text(data: dict) -> str:
    a = data.get("address", {}) if isinstance(data, dict) else {}
    return coalesce_location_text(a)

def _speed_tuple(data: dict) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Return (current_speed, speed_limit, over_by)
    """
    v = data.get("vehicle", {}) if isinstance(data, dict) else {}
    a = data.get("address", {}) if isinstance(data, dict) else {}
    cur = mph(v.get("speed") or data.get("speed"))
    limit = extract_speed_limit_from_text(a)
    over = (cur - limit) if (cur is not None and limit is not None and cur > limit) else None
    return cur, limit, over

def tpl_weight_station(data: dict) -> str:
    return (
        "⚖️ WEIGHT STATIONS\n\n"
        "🟢 INFO: Vehicle entered at {entry}\n\n"
        "🚛 Vehicle: {veh}\n"
        "📍 Location: {loc}\n"
        "📅 Date: {date}\n"
        "🕐 Time: {time}"
    ).format(
        entry=(data.get("address", {}) or {}).get("name", "Zone"),
        veh=escape(_veh_name(data)),
        loc=escape(_address_text(data)),
        date=fmt_date(),
        time=fmt_time(),
    )

def tpl_speeding_of_weight(data: dict) -> str:
    cur, limit, over = _speed_tuple(data)
    over_str = f"\n⚠️ OVER BY {over} MPH" if over is not None else ""
    cur_s = f"{cur} mph" if cur is not None else "N/A"
    lim_s = f"{limit} mph" if limit is not None else "N/A"
    return (
        "🚨 SPEEDING OF WEIGHT STATION\n\n"
        "🟢 INFO: Vehicle entered at {entry}\n\n"
        "🚛 Vehicle: {veh}\n"
        "📍 Location: {loc}\n"
        "🏃 Current Speed: {cur}\n"
        "🚦 Speed Limit: {lim}{over}\n"
        "📅 Date: {date}\n"
        "🕐 Time: {time}"
    ).format(
        entry=(data.get("address", {}) or {}).get("name", "Zone"),
        veh=escape(_veh_name(data)),
        loc=escape(_address_text(data)),
        cur=cur_s,
        lim=lim_s,
        over=over_str,
        date=fmt_date(),
        time=fmt_time(),
    )

def tpl_speeding(data: dict) -> str:
    cur, limit, over = _speed_tuple(data)
    over_str = f"\n⚠️ OVER BY {over} MPH" if over is not None else ""
    cur_s = f"{cur} mph" if cur is not None else "N/A"
    lim_s = f"{limit} mph" if limit is not None else "N/A"
    return (
        "🚨 OVER SPEEDING\n\n"
        "🚛 Vehicle: {veh}\n"
        "📍 Location: {loc}\n"
        "🏃 Current Speed: {cur}\n"
        "🚦 Speed Limit: {lim}{over}\n"
        "📅 Date: {date}\n"
        "🕐 Time: {time}"
    ).format(
        veh=escape(_veh_name(data)),
        loc=escape(_address_text(data)),
        cur=cur_s,
        lim=lim_s,
        over=over_str,
        date=fmt_date(),
        time=fmt_time(),
    )

def tpl_spartak(data: dict) -> str:
    return (
        "🏬 SPARTAK SHOP\n\n"
        "🚛 Vehicle: {veh}\n"
        "📍 Location: {loc}\n"
        "📅 Date: {date}\n"
        "🕐 Time: {time}"
    ).format(
        veh=escape(_veh_name(data)),
        loc=escape(_address_text(data)),
        date=fmt_date(),
        time=fmt_time(),
    )

def tpl_dashcam_gateway(data: dict) -> str:
    # Try to infer status (Connected/Disconnected) from event hint fields
    status = data.get("status") or data.get("deviceStatus") or data.get("gatewayStatus")
    status_text = "Vehicle Disconnected" if str(status).lower() in ["disconnected", "unplugged", "false"] else "Vehicle Connected"
    return (
        "📷 DASHCAMS / GATEWAY\n\n"
        "🚛 Vehicle: {veh}\n"
        "🟠 Status: {status}\n"
        "📅 Date: {date}\n"
        "🕐 Time: {time}"
    ).format(
        veh=escape(_veh_name(data)),
        status=escape(status_text),
        date=fmt_date(),
        time=fmt_time(),
    )

def tpl_critical(data: dict, subtype: str = "") -> str:
    title = {
        "panic": "🚨 Panic Button Pressed!",
        "overheat": "🌡 Engine Overheat!",
        "crash": "💥 CRASHHHH!",
        "harsh": "⚡️ Harsh Driving Event",
        "harsh_brake": "🛑 Harsh Brake!",
        "rolling_stop": "🛑 Rolling Stop!",
        "harsh_turn": "↔️ Harsh Turn!",
        "distracted": "🛞 Distracted Driving!",
    }.get(subtype, "🚨 CRITICAL MAINTENANCE")

    return (
        f"{title}\n\n"
        "🚛 Vehicle: {veh}\n"
        "👤 Driver: {drv}\n"
        "📍 Location: {loc}\n"
        "📅 Date: {date}\n"
        "🕐 Time: {time}"
    ).format(
        veh=escape(_veh_name(data)),
        drv=escape(_driver_name(data)),
        loc=escape(_address_text(data)),
        date=fmt_date(),
        time=fmt_time(),
    )

def tpl_low_fuel(data: dict) -> str:
    v = data.get("vehicle", {}) if isinstance(data, dict) else {}
    fuel = v.get("fuelPercent")
    fuel_txt = f"{fuel}%" if fuel is not None else "N/A"
    heading = data.get("heading") or v.get("heading")
    heading_txt = f"{heading}°" if heading is not None else "N/A"
    return (
        "⛽️ LOW FUEL / DEF\n\n"
        "🚛 Vehicle: {veh}\n"
        "📍 Location: {loc}\n"
        "⛽ Fuel: {fuel} 🟢 OK\n"
        "🧭 Heading: {heading} (W)\n"
        "📅 Date: {date}\n"
        "🕐 Time: {time}"
    ).format(
        veh=escape(_veh_name(data)),
        loc=escape(_address_text(data)),
        fuel=fuel_txt,
        heading=heading_txt,
        date=fmt_date(),
        time=fmt_time(),
    )

# ────────────────────────── ROUTING / TEMPLATE PICKER ─────────────────
def pick_template_and_topic(event: dict) -> Tuple[str, Tuple[int, Optional[int], str]]:
    """
    Decide template + topic using (1) alertId mapping, (2) address id, (3) heuristics
    Returns: (template_key, (chat_id, thread_id, topic_name))
    """
    event_id = event.get("eventId")
    etype = (event.get("eventType") or "").lower()
    data = event.get("data", event)

    # 1) Direct alert-id mapping
    if event_id and event_id in ALERT_MAPPINGS:
        m = ALERT_MAPPINGS[event_id]
        return m["template"], m["topic"]

    # 2) Address ID mapping
    address = (data or {}).get("address", {}) if isinstance(data, dict) else {}
    addr_id = address.get("id")
    if addr_id and addr_id in ALERT_MAPPINGS:
        chat_id, thread_id, topic = ALERT_MAPPINGS[addr_id]["topic"]
        # choose by address topic name
        if "WEIGHT" in topic:
            return "WEIGHT", (chat_id, thread_id, topic)
        if "SPARTAK" in topic:
            return "SPARTAK", (chat_id, thread_id, topic)
        return "GENERAL", (chat_id, thread_id, topic)

    # 3) Heuristics from eventType/name/address text
    name_text = (address.get("name") or "") + " " + (address.get("formattedAddress") or "")
    name_text_l = name_text.lower()

    # hybrid
    if ("speed" in name_text_l or "speed" in etype) and ("weight" in name_text_l or "weigh" in name_text_l):
        return "SPEEDING_OF_WEIGHT", (GROUP_ID, THREADS["WEIGHT"], "🚨 SPEEDING OF WEIGHT STATION")

    # weight station
    if "weight" in name_text_l or "weigh" in etype or "weigh" in name_text_l:
        return "WEIGHT", (GROUP_ID, THREADS["WEIGHT"], "⚖️ WEIGHT STATIONS")

    # speeding
    if "speed" in etype or "speed" in name_text_l:
        return "SPEEDING", (GROUP_ID, THREADS["SPEEDING"], "🚨 OVER SPEEDING")

    # spartak
    if "spartak" in name_text_l or "shop" in name_text_l:
        return "SPARTAK", (GROUP_ID, THREADS["SPARTAK"], "🏬 SPARTAK SHOP")

    # dashcam/gateway
    if any(k in etype for k in ["dashcam", "gateway", "device"]) or any(k in name_text_l for k in ["dashcam", "gateway", "disconnect"]):
        return "DASHCAM", (GROUP_ID, THREADS["DASHCAM"], "📷 DASHCAMS / GATEWAY")

    # low fuel / def
    if "fuel" in etype or "def" in etype or "fuel" in name_text_l:
        return "LOW_FUEL", (GROUP_ID, THREADS["LOW_FUEL"], "⛽️ LOW FUEL / DEF")

    # critical variants
    crit_map = [
        ("panic", "panic"),
        ("overheat", "overheat"),
        ("crash", "crash"),
        ("harshbrake", "harsh_brake"),
        ("brake", "harsh_brake"),
        ("rolling", "rolling_stop"),
        ("harshturn", "harsh_turn"),
        ("distract", "distracted"),
        ("harsh", "harsh"),
        ("engine", "overheat"),
    ]
    for key, subtype in crit_map:
        if key in etype or key in name_text_l:
            return f"CRITICAL:{subtype}", (GROUP_ID, THREADS["CRITICAL"], "🚨 CRITICAL MAINTENANCE")

    # scheduled maintenance
    if "maintenance" in etype or "odometer" in name_text_l or "service" in name_text_l:
        return "SCHEDULED", (GROUP_ID, THREADS["SCHEDULED_MAINT"], "🛠 Scheduled Maintenance by Odometer")

    # default
    return "GENERAL", (GROUP_ID, THREADS["GENERAL"], "📋 General")

def render_template(template_key: str, data: dict) -> str:
    if template_key == "WEIGHT":
        return tpl_weight_station(data)
    if template_key == "SPEEDING_OF_WEIGHT":
        return tpl_speeding_of_weight(data)
    if template_key == "SPEEDING":
        return tpl_speeding(data)
    if template_key == "SPARTAK":
        return tpl_spartak(data)
    if template_key == "DASHCAM":
        return tpl_dashcam_gateway(data)
    if template_key == "LOW_FUEL":
        return tpl_low_fuel(data)
    if template_key.startswith("CRITICAL:"):
        subtype = template_key.split(":", 1)[1]
        return tpl_critical(data, subtype=subtype)
    if template_key == "SCHEDULED":
        # Basic scheduled maintenance phrasing using weight template structure
        return (
            "🛠 Scheduled Maintenance by Odometer\n\n"
            "🚛 Vehicle: {veh}\n"
            "📍 Location: {loc}\n"
            "📅 Date: {date}\n"
            "🕐 Time: {time}"
        ).format(
            veh=escape(_veh_name(data)),
            loc=escape(_address_text(data)),
            date=fmt_date(),
            time=fmt_time(),
        )
    # GENERAL fallback
    if template_key == "GENERAL":
        evt_type = data.get("eventType") or "Unknown Type"
        alert_name = data.get("alertName") or data.get("name") or evt_type
        v = data.get("vehicle", {}) or {}
        veh_name = (
            v.get("name")
            or v.get("id")
            or v.get("serial")
            or v.get("licensePlate")
            or "Unknown"
        )
        a = data.get("address", {}) or {}
        loc = a.get("formattedAddress") or a.get("name") or "Unknown"
        return (
            f"📋 UNKNOWN ALERT: {escape(alert_name)}\n\n"
            f"🚛 Vehicle: {escape(veh_name)}\n"
            f"📍 Location: {escape(loc)}\n"
            f"⚙️ Type: {escape(evt_type)}\n"
            f"📅 Date: {fmt_date()}\n"
            f"🕐 Time: {fmt_time()}"
        )

# ───────────────────────────── WEBHOOKS ───────────────────────────────
async def handle_samsara(request: web.Request):
    try:
        raw = await request.read()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Invalid JSON payload")
            return web.Response(text="Invalid JSON", status=400)

        events = [payload] if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])
        if not events:
            return web.Response(text="No events", status=200)

        log.info("Processing %d event(s)", len(events))

        for ev in events:
            if not isinstance(ev, dict):
                continue

            # normalize Samsara structure
            data = (
                ev.get("data")
                or ev.get("alert", {}).get("data")
                or ev.get("alert")
                or ev
            )

            # flatten vehicle/address/driver if buried deeper
            if "vehicle" not in data and "vehicle" in ev:
                data["vehicle"] = ev["vehicle"]
            if "address" not in data and "address" in ev:
                data["address"] = ev["address"]
            if "driver" not in data and "driver" in ev:
                data["driver"] = ev["driver"]

            template_key, (chat_id, thread_id, topic_name) = pick_template_and_topic(ev)

            # enrich vehicle/driver names if missing
            v = data.get("vehicle", {})
            if v.get("id") and not v.get("name"):
                details = await get_vehicle_details(v["id"])
                if details:
                    v["name"] = details.get("name", v.get("name"))
                    data["vehicle"] = v

            d = data.get("driver", {})
            if d.get("id") and not d.get("name"):
                dd = await get_driver_details(d["id"])
                if dd:
                    d["name"] = dd.get("name", d.get("name"))
                    data["driver"] = d

            text = render_template(template_key, data)
            send_kwargs = {"chat_id": chat_id, "text": text}
            if thread_id:
                send_kwargs["message_thread_id"] = thread_id

            await bot.send_message(**send_kwargs)
            log.info("Sent → %s (%s)", topic_name, template_key)

        return web.Response(text="OK", status=200)

    except Exception as e:
        log.exception("Webhook error: %s", e)
        return web.Response(text=f"Error: {e}", status=500)

# ───────────────────────────── MISC ROUTES ────────────────────────────
async def handle_health(_):
    info = {
        "status": "healthy",
        "timestamp": now_dt().isoformat(),
        "alerts_loaded": len(ALERT_MAPPINGS),
        "group_id": GROUP_ID
    }
    return web.Response(text=json.dumps(info, indent=2), content_type="application/json", status=200)

async def handle_test(_):
    """Sends a demo 'SevereSpeedingStarted' near a 65 zone (for smoke test)."""
    demo = {
        "eventType": "SevereSpeedingStarted",
        "eventId": "demo-speed-123",
        "data": {
            "address": {
                "name": "65 SPEED ZONE",
                "formattedAddress": "499 106th St NW, Albuquerque, NM 87121, USA",
                "geofence": {"circle": {"latitude": 35.0844, "longitude": -106.6504}}
            },
            "vehicle": {"id": "test-veh", "name": "5120", "speed": 73},
            "driver": {"name": "Test Driver"},
            "speed": 73
        }
    }
    tpl, topic = pick_template_and_topic(demo)
    text = render_template(tpl, demo["data"])
    chat_id, thread_id, _ = topic
    kwargs = {"chat_id": chat_id, "text": text}
    if thread_id:
        kwargs["message_thread_id"] = thread_id
    await bot.send_message(**kwargs)
    return web.Response(text="Sent test", status=200)

def create_app():
    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_get("/test", handle_test)
    app.router.add_post("/samsara", handle_samsara)
    app.router.add_get("/samsara", lambda _: web.Response(text="Samsara webhook endpoint. Use POST.", status=200))
    return app

# ───────────────────────────── STARTUP ────────────────────────────────
async def validate_and_bootstrap() -> bool:
    try:
        me = await bot.get_me()
        log.info("Telegram bot connected: @%s", me.username)
    except Exception as e:
        log.error("Telegram connection failed: %s", e)
        return False

    if SAMSARA_API_TOKEN:
        # probe API
        try:
            session = await get_session()
            headers = {"Authorization": f"Bearer {SAMSARA_API_TOKEN}"}
            async with session.get(f"{SAMSARA_BASE_URL}/fleet/vehicles?limit=1", headers=headers) as r:
                log.info("Samsara API probe status: %s", r.status)
        except Exception as e:
            log.warning("Samsara probe failed: %s", e)

    # initial dynamic sync
    dynamic = await fetch_alert_configurations()
    if dynamic:
        ALERT_MAPPINGS.update(dynamic)
        log.info("Alert mappings ready: %d total", len(ALERT_MAPPINGS))
    else:
        log.info("Using static mappings only: %d", len(ALERT_MAPPINGS))

    # background refresh loop
    asyncio.create_task(refresh_alerts_periodically())
    return True

async def main():
    ok = await validate_and_bootstrap()
    if not ok:
        log.error("Startup validation failed")
        return

    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    log.info("🚀 Fleet Master live on :%d", PORT)
    log.info("Endpoints: /health, /test, /samsara")

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await close_session()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutting down…")
