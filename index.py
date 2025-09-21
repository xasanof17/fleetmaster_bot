#!/usr/bin/env python3
"""
Comprehensive Fixed Samsara Telegram Bot
- Proper data extraction
- Formatted addresses with map links
- Correct topic routing
- Rich message formatting
"""

import os
import logging
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from html import escape
from dotenv import load_dotenv
import hmac
import hashlib
import base64
import json
import datetime
import urllib.parse

load_dotenv()

# ===================== LOGGING =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ===================== ENVIRONMENT CHECK =====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "-1003067846983"))
PORT = int(os.getenv("PORT", 8080))
SAMSARA_API_TOKEN = os.getenv("SAMSARA_API_TOKEN")
SAMSARA_BASE_URL = os.getenv("SAMSARA_BASE_URL", "https://api.samsara.com")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set!")

# ===================== BOT INIT =====================
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ===================== ENHANCED TOPIC MAPPING =====================
ALERT_MAPPINGS = {
    # Alert IDs from your alerts_samsara.json
    "219a987e-b704-4e08-a825-8da11c58d33d": {  # Spartak Shop
        "topic": (GROUP_ID, 14, "🏬 SPARTAK SHOP"),
        "priority": "HIGH",
        "type": "geofence_entry"
    },
    "6004a43b-eb59-4ea4-ba17-8464ad955f76": {  # Scheduled Maintenance
        "topic": (GROUP_ID, 16, "🛠 Scheduled Maintenance by Odometer"),
        "priority": "MEDIUM",
        "type": "maintenance"
    },
    "903a2139-c3d1-4697-b4a7-5fd960d4a805": {  # Vehicle Severely Speeding
        "topic": (GROUP_ID, 3, "🚨 SPEEDING"),
        "priority": "CRITICAL",
        "type": "severe_speeding"
    },
    "497ee2fc-308c-4502-8f53-703f89b4c37f": {  # Weigh_Station_Zone
        "topic": (GROUP_ID, 12, "⚖️ WEIGHT STATIONS"),
        "priority": "MEDIUM",
        "type": "zone_entry"
    },
    "67ccad3d-7f19-400a-aaab-650b9dd09869": {  # Panic Button
        "topic": (GROUP_ID, 7, "🚨 CRITICAL MAINTENANCE"),
        "priority": "CRITICAL",
        "type": "panic"
    },
    "1950fc10-a418-439a-8fd0-ef8c13b3406b": {  # Vehicle Engine Idle
        "topic": (GROUP_ID, 7, "🚨 CRITICAL MAINTENANCE"),
        "priority": "HIGH",
        "type": "engine_idle"
    },
    "3dc1e918-d864-427a-abc6-b95dabb3a45f": {  # DASHCAM DISCONNECTED
        "topic": (GROUP_ID, 9, "📷 DASHCAMS / GATEWAY"),
        "priority": "HIGH",
        "type": "device_disconnect"
    },
    "f87a1f80-c2ac-42fb-a371-069d696fe2cc": {  # Fuel level down
        "topic": (GROUP_ID, 5, "⛽ LOW FUEL / DEF"),
        "priority": "MEDIUM",
        "type": "low_fuel"
    }
}

# Geofence-based routing for addresses
GEOFENCE_MAPPINGS = {
    # Spartak
    "97508177": (GROUP_ID, 14, "🏬 SPARTAK SHOP"),
    
    # Speed zones
    "167700536": (GROUP_ID, 3, "🚨 SPEEDING"),  # SP limit 65
    "199883244": (GROUP_ID, 3, "🚨 SPEEDING"),  # Speed zones
    "255668228": (GROUP_ID, 3, "🚨 SPEEDING"),
    "199889131": (GROUP_ID, 3, "🚨 SPEEDING"),
    "245653269": (GROUP_ID, 3, "🚨 SPEEDING"),  # 45 SPEED ZONE
    
    # Weight stations and zones
    "236015922": (GROUP_ID, 12, "⚖️ WEIGHT STATIONS"),  # SC- I95N
    "219848684": (GROUP_ID, 12, "⚖️ WEIGHT STATIONS"),  # LINE ZONE
    "241759414": (GROUP_ID, 12, "⚖️ WEIGHT STATIONS"),
    "266650120": (GROUP_ID, 12, "⚖️ WEIGHT STATIONS"),
}

# Event type patterns
EVENT_TYPE_PATTERNS = {
    "SevereSpeedingStarted": (GROUP_ID, 3, "🚨 SPEEDING"),
    "SevereSpeedingEnded": (GROUP_ID, 3, "🚨 SPEEDING"),
    "EngineIdleOn": (GROUP_ID, 7, "🚨 CRITICAL MAINTENANCE"),
    "EngineIdleOff": (GROUP_ID, 7, "🚨 CRITICAL MAINTENANCE"),
    "GatewayUnplugged": (GROUP_ID, 9, "📷 DASHCAMS / GATEWAY"),
    "PredictiveMaintenanceAlert": (GROUP_ID, 16, "🛠 Scheduled Maintenance by Odometer"),
}

# Content-based routing
def analyze_content_routing(text_content: str, address_name: str = ""):
    """Analyze text content to determine routing"""
    
    content_lower = text_content.lower()
    address_lower = address_name.lower()
    
    # Speed-related keywords
    if any(keyword in content_lower or keyword in address_lower for keyword in [
        "speed", "limit", "mph", "sp limit", "speeding", "65 mph", "45 mph"
    ]):
        return GROUP_ID, 3, "🚨 SPEEDING"
    
    # Weight station/zone keywords  
    if any(keyword in content_lower or keyword in address_lower for keyword in [
        "weigh", "weight", "zone", "interstate", "i-95", "i95", "i-75", "i75", 
        "highway", "port of entry", "inspection"
    ]):
        return GROUP_ID, 12, "⚖️ WEIGHT STATIONS"
        
    # Spartak keywords
    if any(keyword in content_lower or keyword in address_lower for keyword in [
        "spartak", "shop"
    ]):
        return GROUP_ID, 14, "🏬 SPARTAK SHOP"
    
    # Maintenance keywords
    if any(keyword in content_lower for keyword in [
        "maintenance", "service", "scheduled", "odometer"
    ]):
        return GROUP_ID, 16, "🛠 Scheduled Maintenance by Odometer"
        
    # Fuel keywords
    if any(keyword in content_lower for keyword in [
        "fuel", "def", "diesel", "gas"
    ]):
        return GROUP_ID, 5, "⛽ LOW FUEL / DEF"
    
    # Engine/critical keywords
    if any(keyword in content_lower for keyword in [
        "idle", "engine", "panic", "harsh", "coolant", "emergency"
    ]):
        return GROUP_ID, 7, "🚨 CRITICAL MAINTENANCE"
        
    # Device keywords
    if any(keyword in content_lower for keyword in [
        "dashcam", "gateway", "disconnect", "unplug", "device"
    ]):
        return GROUP_ID, 9, "📷 DASHCAMS / GATEWAY"
    
    # Default to general
    return GROUP_ID, None, "📋 General"

# ===================== VEHICLE DATA FETCHING =====================
async def get_vehicle_details(vehicle_id: str) -> dict:
    """Fetch detailed vehicle information from Samsara API"""
    if not SAMSARA_API_TOKEN or not vehicle_id:
        return {}
        
    try:
        url = f"{SAMSARA_BASE_URL}/fleet/vehicles/{vehicle_id}"
        headers = {"Authorization": f"Bearer {SAMSARA_API_TOKEN}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", {})
                else:
                    logger.warning(f"Failed to fetch vehicle {vehicle_id}: {response.status}")
    except Exception as e:
        logger.error(f"Error fetching vehicle details: {e}")
    
    return {}

async def get_driver_details(driver_id: str) -> dict:
    """Fetch driver information from Samsara API"""
    if not SAMSARA_API_TOKEN or not driver_id:
        return {}
        
    try:
        url = f"{SAMSARA_BASE_URL}/fleet/drivers/{driver_id}"
        headers = {"Authorization": f"Bearer {SAMSARA_API_TOKEN}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", {})
    except Exception as e:
        logger.error(f"Error fetching driver details: {e}")
    
    return {}

# ===================== SMART EVENT ANALYZER =====================
async def analyze_and_enrich_event(event: dict) -> tuple:
    """Analyze event and enrich with additional data"""
    
    event_type = event.get("eventType", "Unknown")
    event_id = event.get("eventId")
    data = event.get("data", {}) if isinstance(event.get("data"), dict) else event
    
    # Skip ping events
    if event_type == "Ping":
        return None, None, None, None, None
    
    # Step 1: Try alert ID mapping first
    if event_id and event_id in ALERT_MAPPINGS:
        mapping = ALERT_MAPPINGS[event_id]
        chat_id, thread_id, topic_name = mapping["topic"]
        priority = mapping["priority"]
        alert_type = mapping["type"]
        logger.info(f"✅ Matched by Alert ID: {event_id} -> {topic_name}")
        return data, chat_id, thread_id, topic_name, priority
    
    # Step 2: Check geofence routing
    address = data.get("address", {})
    address_id = address.get("id")
    address_name = address.get("name", "")
    
    if address_id and address_id in GEOFENCE_MAPPINGS:
        chat_id, thread_id, topic_name = GEOFENCE_MAPPINGS[address_id]
        priority = "MEDIUM"
        logger.info(f"✅ Matched by Address ID: {address_id} -> {topic_name}")
        return data, chat_id, thread_id, topic_name, priority
    
    # Step 3: Check event type patterns
    if event_type in EVENT_TYPE_PATTERNS:
        chat_id, thread_id, topic_name = EVENT_TYPE_PATTERNS[event_type]
        priority = "HIGH" if "Severe" in event_type else "MEDIUM"
        logger.info(f"✅ Matched by Event Type: {event_type} -> {topic_name}")
        return data, chat_id, thread_id, topic_name, priority
    
    # Step 4: Content-based analysis
    full_content = f"{event_type} {address_name}".lower()
    chat_id, thread_id, topic_name = analyze_content_routing(full_content, address_name)
    
    if thread_id is not None:  # Found a match
        priority = "MEDIUM"
        logger.info(f"✅ Matched by Content: '{full_content}' -> {topic_name}")
        return data, chat_id, thread_id, topic_name, priority
    
    # Default to general with low priority
    logger.info(f"⚠️ No specific match found, using General")
    return data, GROUP_ID, None, "📋 General", "LOW"

# ===================== ENHANCED MESSAGE FORMATTER =====================
def create_map_link(latitude: float, longitude: float, address_name: str = "") -> str:
    """Create Google Maps link"""
    if latitude and longitude:
        maps_url = f"https://maps.google.com/?q={latitude},{longitude}"
        if address_name:
            return f"<a href='{maps_url}'>{escape(address_name)}</a>"
        else:
            return f"<a href='{maps_url}'>📍 View on Map</a>"
    return escape(address_name) if address_name else "Location unavailable"

def format_priority_indicator(priority: str) -> str:
    """Format priority with appropriate emoji"""
    indicators = {
        "CRITICAL": "🔴 CRITICAL",
        "HIGH": "🟠 HIGH PRIORITY", 
        "MEDIUM": "🟡 ALERT",
        "LOW": "🟢 INFO"
    }
    return indicators.get(priority, "🟡 ALERT")

async def format_comprehensive_message(event_type: str, data: dict, topic_name: str, priority: str) -> str:
    """Create comprehensive formatted message"""
    
    # Extract basic data
    vehicle = data.get("vehicle", {})
    vehicle_id = vehicle.get("id")
    vehicle_name = vehicle.get("name", "Unknown Vehicle")
    
    # Enrich vehicle data if possible
    if vehicle_id and vehicle_name == "Unknown Vehicle":
        vehicle_details = await get_vehicle_details(vehicle_id)
        if vehicle_details:
            vehicle_name = vehicle_details.get("name", vehicle_name)
            vehicle.update(vehicle_details)
    
    # Extract driver data
    driver = data.get("driver", {})
    driver_id = driver.get("id")
    driver_name = driver.get("name", "Unknown Driver")
    
    # Enrich driver data if possible  
    if driver_id and driver_name == "Unknown Driver":
        driver_details = await get_driver_details(driver_id)
        if driver_details:
            driver_name = driver_details.get("name", driver_name)
    
    # Extract location data
    address = data.get("address", {})
    address_name = address.get("name", "")
    formatted_address = address.get("formattedAddress", "")
    
    # Get coordinates for map link
    latitude = longitude = None
    geofence = address.get("geofence", {})
    
    if "circle" in geofence:
        circle = geofence["circle"]
        latitude = circle.get("latitude")
        longitude = circle.get("longitude")
    elif "polygon" in geofence and geofence["polygon"].get("vertices"):
        vertex = geofence["polygon"]["vertices"][0]
        latitude = vertex.get("latitude") 
        longitude = vertex.get("longitude")
    
    # Create location display with map link
    if latitude and longitude:
        if address_name:
            location_display = create_map_link(latitude, longitude, address_name)
        elif formatted_address:
            location_display = create_map_link(latitude, longitude, formatted_address)
        else:
            location_display = create_map_link(latitude, longitude, "Location")
    else:
        location_display = address_name or formatted_address or "Location unavailable"
    
    # Create alert description based on event type
    alert_descriptions = {
        "GeofenceEntry": f"entered geofence at {address_name}",
        "GeofenceExit": f"exited geofence at {address_name}",
        "SevereSpeedingStarted": "started severe speeding",
        "SevereSpeedingEnded": "stopped severe speeding", 
        "EngineIdleOn": "excessive idling started",
        "EngineIdleOff": "excessive idling ended"
    }
    
    alert_desc = alert_descriptions.get(event_type, event_type)
    priority_indicator = format_priority_indicator(priority)
    
    # Build comprehensive message
    header = f"<b>{topic_name}</b>"
    alert_line = f"{priority_indicator}: Vehicle {alert_desc}"
    
    details = []
    details.append(f"🚛 <b>Vehicle:</b> {escape(vehicle_name)}")
    
    if driver_name and driver_name != "Unknown Driver":
        details.append(f"👤 <b>Driver:</b> {escape(driver_name)}")
    
    if location_display and location_display != "Location unavailable":
        details.append(f"📍 <b>Location:</b> {location_display}")
    
    # Add additional vehicle data if available
    speed = vehicle.get("speed")
    if speed:
        details.append(f"🏃 <b>Speed:</b> {speed} mph")
        
    fuel_percent = vehicle.get("fuelPercent")
    if fuel_percent:
        details.append(f"⛽ <b>Fuel:</b> {fuel_percent}%")
    
    # Add timestamp
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    details.append(f"🕐 <b>Time:</b> {timestamp}")
    
    return f"{header}\n\n<b>{alert_line}</b>\n\n" + "\n".join(details)

# ===================== WEBHOOK HANDLER =====================
async def handle_samsara(request):
    try:
        raw_body = await request.read()
        logger.info("📨 Received webhook")
        
        try:
            data_json = json.loads(raw_body)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return web.Response(text="Invalid JSON", status=400)

        # Handle Samsara webhook structure
        if isinstance(data_json, dict) and data_json.get("eventType"):
            events = [data_json]
        else:
            events = data_json if isinstance(data_json, list) else []

        logger.info(f"📋 Processing {len(events)} events")

        for i, event in enumerate(events):
            if not isinstance(event, dict):
                continue

            event_type = event.get("eventType", "Unknown")
            logger.info(f"🔍 Event {i+1}: {event_type}")
            
            # Analyze and enrich event
            enriched_data, chat_id, thread_id, topic_name, priority = await analyze_and_enrich_event(event)
            
            # Skip if filtered out
            if enriched_data is None:
                logger.info(f"⏭️ Skipping {event_type}")
                continue
            
            try:
                # Create comprehensive message
                message_text = await format_comprehensive_message(event_type, enriched_data, topic_name, priority)
                
                # Send message
                send_kwargs = {"chat_id": chat_id, "text": message_text}
                if thread_id:
                    send_kwargs["message_thread_id"] = thread_id

                await bot.send_message(**send_kwargs)
                logger.info(f"✅ Sent to {topic_name}: {event_type}")
                
                # Send location for important events
                if priority in ["CRITICAL", "HIGH"]:
                    await send_location_pin(enriched_data, chat_id, thread_id)
                
            except Exception as e:
                logger.error(f"❌ Failed to send message: {e}")

        return web.Response(text="✅ Processed", status=200)

    except Exception as e:
        logger.exception(f"❌ Webhook error: {e}")
        return web.Response(text="❌ Error", status=500)

async def send_location_pin(data: dict, chat_id: int, thread_id: int = None):
    """Send location pin for important events"""
    try:
        address = data.get("address", {})
        geofence = address.get("geofence", {})
        
        latitude = longitude = None
        
        if "circle" in geofence:
            circle = geofence["circle"]
            latitude = circle.get("latitude")
            longitude = circle.get("longitude")
        elif "polygon" in geofence and geofence["polygon"].get("vertices"):
            vertex = geofence["polygon"]["vertices"][0]
            latitude = vertex.get("latitude")
            longitude = vertex.get("longitude")

        if latitude and longitude:
            send_kwargs = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude}
            if thread_id:
                send_kwargs["message_thread_id"] = thread_id
                
            await bot.send_location(**send_kwargs)
            logger.info("📍 Location pin sent")
            
    except Exception as e:
        logger.error(f"❌ Failed to send location: {e}")

# ===================== ENDPOINTS =====================
async def handle_test(request):
    """Test with realistic data"""
    try:
        test_data = {
            "eventType": "GeofenceExit",
            "eventId": "test-123",
            "data": {
                "address": {
                    "id": "167700536", 
                    "name": "65 SPEED ZONE",
                    "formattedAddress": "Interstate 65, Alabama, USA",
                    "geofence": {
                        "circle": {
                            "latitude": 32.2876,
                            "longitude": -106.8404
                        }
                    }
                },
                "vehicle": {
                    "id": "test-vehicle-123",
                    "name": "5151"
                }
            }
        }
        
        enriched_data, chat_id, thread_id, topic_name, priority = await analyze_and_enrich_event(test_data)
        
        if enriched_data:
            message = await format_comprehensive_message("GeofenceExit", enriched_data, topic_name, priority)
            
            send_kwargs = {"chat_id": chat_id, "text": message}
            if thread_id:
                send_kwargs["message_thread_id"] = thread_id
                
            await bot.send_message(**send_kwargs)
            return web.Response(text=f"✅ Test sent to {topic_name}", status=200)
        else:
            return web.Response(text="❌ Test event was filtered out", status=200)
            
    except Exception as e:
        return web.Response(text=f"❌ Test failed: {e}", status=500)

async def handle_health(request):
    return web.Response(text="✅ Bot is healthy", status=200)

# ===================== APP SETUP =====================
def create_app():
    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_get("/test", handle_test) 
    app.router.add_post("/samsara", handle_samsara)
    return app

if __name__ == "__main__":
    try:
        logger.info(f"🚀 Starting Comprehensive Bot on port {PORT}")
        app = create_app()
        web.run_app(app, host="0.0.0.0", port=PORT)
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        print(f"❌ Error: {e}")