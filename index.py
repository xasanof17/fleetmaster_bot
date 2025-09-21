#!/usr/bin/env python3
"""
Fixed Samsara Telegram Bot with Speed Data
- Fixed middleware issues
- Proper session management
- Corrected API endpoints
- Enhanced error handling
"""

import os
import logging
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from html import escape
from dotenv import load_dotenv
import json
import datetime
import asyncio

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

# ===================== GLOBAL SESSION MANAGER =====================
_session = None

async def get_session():
    """Get or create a global aiohttp session"""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session

async def close_session():
    """Close the global session"""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None

# ===================== ENHANCED ALERT MAPPINGS =====================
ALERT_MAPPINGS = {
    # Vehicle Engine Idle
    "1950fc10-a418-439a-8fd0-ef8c13b3406b": {
        "topic": (GROUP_ID, 7, "🚨 CRITICAL MAINTENANCE"),
        "priority": "HIGH",
        "type": "engine_idle",
        "name": "Vehicle Engine Idle"
    },
    
    # Spartak Shop
    "219a987e-b704-4e08-a825-8da11c58d33d": {
        "topic": (GROUP_ID, 14, "🏬 SPARTAK SHOP"),
        "priority": "MEDIUM",
        "type": "geofence_entry",
        "name": "Spartak Shop"
    },
    
    # DASHCAM DISCONNECTED
    "3dc1e918-d864-427a-abc6-b95dabb3a45f": {
        "topic": (GROUP_ID, 9, "📷 DASHCAMS / GATEWAY"),
        "priority": "HIGH",
        "type": "device_disconnect",
        "name": "DASHCAM DISCONNECTED"
    },
    
    # Weigh Station Zone
    "497ee2fc-308c-4502-8f53-703f89b4c37f": {
        "topic": (GROUP_ID, 12, "⚖️ WEIGHT STATIONS"),
        "priority": "MEDIUM",
        "type": "zone_entry",
        "name": "Weigh_Station_Zone"
    },
    
    # Scheduled Maintenance by Odometer
    "6004a43b-eb59-4ea4-ba17-8464ad955f76": {
        "topic": (GROUP_ID, 16, "🛠 Scheduled Maintenance by Odometer"),
        "priority": "MEDIUM",
        "type": "maintenance",
        "name": "Scheduled Maintenance by Odometer"
    },
    
    # Panic Button
    "67ccad3d-7f19-400a-aaab-650b9dd09869": {
        "topic": (GROUP_ID, 7, "🚨 CRITICAL MAINTENANCE"),
        "priority": "CRITICAL",
        "type": "panic",
        "name": "Panic Button"
    },
    
    # SPEEDING ZONE
    "6ac80dbb-1457-4713-b6fb-8b61ff631f2f": {
        "topic": (GROUP_ID, 3, "🚨 SPEEDING"),
        "priority": "HIGH",
        "type": "speed_zone",
        "name": "SPEEDING ZONE"
    },
    
    # Harsh Event
    "6dc763d6-4adb-4d8f-a8e8-b1d0a7a8ef0d": {
        "topic": (GROUP_ID, 7, "🚨 CRITICAL MAINTENANCE"),
        "priority": "HIGH",
        "type": "harsh_event",
        "name": "Harsh Event"
    },
    
    # Vehicle Severely Speeding Above Limit
    "903a2139-c3d1-4697-b4a7-5fd960d4a805": {
        "topic": (GROUP_ID, 3, "🚨 SPEEDING"),
        "priority": "CRITICAL",
        "type": "severe_speeding",
        "name": "Vehicle Severely Speeding Above Limit"
    },
    
    # 45 SPEED ZONE AHEAD
    "c2aa07e4-4cca-4cdd-96f2-0fa6f0a17cd8": {
        "topic": (GROUP_ID, 3, "🚨 SPEEDING"),
        "priority": "MEDIUM",
        "type": "speed_zone",
        "name": "45 SPEED ZONE AHEAD"
    },
    
    # Gateway Unplugged
    "e3c9f1de-01b4-474e-b273-9e8473f7c22c": {
        "topic": (GROUP_ID, 9, "📷 DASHCAMS / GATEWAY"),
        "priority": "HIGH",
        "type": "gateway_unplugged",
        "name": "Gateway Unplugged"
    },
    
    # Fuel level down
    "f87a1f80-c2ac-42fb-a371-069d696fe2cc": {
        "topic": (GROUP_ID, 5, "⛽ LOW FUEL / DEF"),
        "priority": "MEDIUM",
        "type": "low_fuel",
        "name": "Fuel level is getting down from 40%"
    }
}

# Address ID mappings
ADDRESS_MAPPINGS = {
    "97508177": (GROUP_ID, 14, "🏬 SPARTAK SHOP"),
    "199883244": (GROUP_ID, 3, "🚨 SPEEDING"),
    "255668228": (GROUP_ID, 3, "🚨 SPEEDING"),
    "199889131": (GROUP_ID, 3, "🚨 SPEEDING"),
    "245653269": (GROUP_ID, 3, "🚨 SPEEDING"),
    "219848684": (GROUP_ID, 12, "⚖️ WEIGHT STATIONS"),
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
    "GeofenceEntry": "analyze_content",
    "GeofenceExit": "analyze_content",
    # Add fuel and dashcam related event types
    "FuelLevelLow": (GROUP_ID, 5, "⛽ LOW FUEL / DEF"),
    "FuelLevel": (GROUP_ID, 5, "⛽ LOW FUEL / DEF"),
    "DashcamDisconnected": (GROUP_ID, 9, "📷 DASHCAMS / GATEWAY"),
    "DeviceDisconnected": (GROUP_ID, 9, "📷 DASHCAMS / GATEWAY"),
    "DeviceUnplugged": (GROUP_ID, 9, "📷 DASHCAMS / GATEWAY"),
}

# ===================== SIMPLIFIED API FUNCTIONS =====================
async def get_vehicle_details(vehicle_id: str) -> dict:
    """Fetch basic vehicle information"""
    if not SAMSARA_API_TOKEN or not vehicle_id:
        return {}
        
    try:
        session = await get_session()
        url = f"{SAMSARA_BASE_URL}/fleet/vehicles"
        headers = {"Authorization": f"Bearer {SAMSARA_API_TOKEN}"}
        
        # Use the list endpoint with filter instead of direct vehicle endpoint
        params = {"vehicleIds": vehicle_id}
        
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                vehicles = data.get("data", [])
                if vehicles:
                    return vehicles[0]
            else:
                logger.warning(f"Failed to fetch vehicle {vehicle_id}: {response.status}")
    except Exception as e:
        logger.error(f"Error fetching vehicle details: {e}")
    
    return {}

async def get_driver_details(driver_id: str) -> dict:
    """Fetch driver information"""
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
                drivers = data.get("data", [])
                if drivers:
                    return drivers[0]
            else:
                logger.warning(f"Failed to fetch driver {driver_id}: {response.status}")
    except Exception as e:
        logger.error(f"Error fetching driver details: {e}")
    
    return {}

# ===================== ADDRESS AND LOCATION UTILITIES =====================
def format_address_display(address: dict) -> tuple:
    """Format address display and extract coordinates"""
    address_name = address.get("name", "")
    formatted_address = address.get("formattedAddress", "")
    
    # Priority: Use formatted address if available, otherwise use name
    display_address = formatted_address or address_name or "Location unavailable"
    
    # Get coordinates
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
    
    return display_address, latitude, longitude

def create_map_link(latitude: float, longitude: float, address_name: str = "") -> str:
    """Create Google Maps link"""
    if latitude and longitude:
        maps_url = f"https://maps.google.com/?q={latitude},{longitude}"
        if address_name:
            return f"<a href='{maps_url}'>{escape(address_name)}</a>"
        else:
            return f"<a href='{maps_url}'>📍 View on Map</a>"
    return escape(address_name) if address_name else "Location unavailable"

def extract_speed_limit_from_address(address: dict) -> int:
    """Extract speed limit from address name or formatted address"""
    address_name = address.get("name", "").lower()
    formatted_address = address.get("formattedAddress", "").lower()
    
    full_address_text = f"{address_name} {formatted_address}"
    
    # Speed limit patterns
    speed_patterns = {
        "65": 65, "55": 55, "45": 45, "35": 35, "25": 25, "70": 70, "75": 75, "80": 80
    }
    
    for pattern, limit in speed_patterns.items():
        if pattern in full_address_text and ("speed" in full_address_text or "mph" in full_address_text):
            return limit
    
    # Interstate default
    if any(keyword in full_address_text for keyword in ["interstate", "i-", "highway"]):
        return 70
    
    # City/residential default
    if any(keyword in full_address_text for keyword in ["city", "residential", "downtown", "main st"]):
        return 35
    
    return None

# ===================== EVENT ANALYSIS =====================
async def analyze_and_enrich_event(event: dict) -> tuple:
    """Analyze event and determine routing"""
    
    event_type = event.get("eventType", "Unknown")
    event_id = event.get("eventId")
    data = event.get("data", {}) if isinstance(event.get("data"), dict) else event
    
    # Skip ping events
    if event_type == "Ping":
        return None, None, None, None, None
    
    logger.info(f"🔍 Analyzing event: {event_type} (ID: {event_id})")
    
    # Debug logging for fuel and dashcam events
    if event_id in ["f87a1f80-c2ac-42fb-a371-069d696fe2cc", "3dc1e918-d864-427a-abc6-b95dabb3a45f"]:
        logger.info(f"🔋 FUEL/DASHCAM EVENT DETECTED: {event_type} - {event_id}")
    
    # Step 1: Alert ID mapping
    if event_id and event_id in ALERT_MAPPINGS:
        mapping = ALERT_MAPPINGS[event_id]
        chat_id, thread_id, topic_name = mapping["topic"]
        priority = mapping["priority"]
        logger.info(f"✅ Matched by Alert ID: {event_id} -> {topic_name}")
        return data, chat_id, thread_id, topic_name, priority
    
    # Step 2: Address ID routing
    address = data.get("address", {})
    address_id = address.get("id")
    
    if address_id and address_id in ADDRESS_MAPPINGS:
        chat_id, thread_id, topic_name = ADDRESS_MAPPINGS[address_id]
        priority = "MEDIUM"
        logger.info(f"✅ Matched by Address ID: {address_id} -> {topic_name}")
        return data, chat_id, thread_id, topic_name, priority
    
    # Step 3: Event type patterns
    if event_type in EVENT_TYPE_PATTERNS:
        mapping_result = EVENT_TYPE_PATTERNS[event_type]
        
        if mapping_result == "analyze_content":
            chat_id, thread_id, topic_name = analyze_content_routing(event_type, address)
            priority = "MEDIUM"
            logger.info(f"✅ Content Analysis: {event_type} -> {topic_name}")
        else:
            chat_id, thread_id, topic_name = mapping_result
            priority = "HIGH" if "Severe" in event_type else "MEDIUM"
            logger.info(f"✅ Event Type Match: {event_type} -> {topic_name}")
        
        return data, chat_id, thread_id, topic_name, priority
    
    # Step 4: Fallback
    chat_id, thread_id, topic_name = analyze_content_routing(event_type, address)
    priority = "LOW"
    logger.info(f"⚠️ Fallback routing: {event_type} -> {topic_name}")
    
    return data, chat_id, thread_id, topic_name, priority

def analyze_content_routing(text_content: str, address_data: dict = None) -> tuple:
    """Analyze content for routing"""
    
    content_lower = text_content.lower()
    address_text = ""
    
    if address_data:
        address_name = address_data.get("name", "")
        formatted_address = address_data.get("formattedAddress", "")
        address_text = f"{address_name} {formatted_address}".lower()
    
    full_text = f"{content_lower} {address_text}".strip()
    
    # Fuel-related keywords (more comprehensive)
    if any(keyword in full_text for keyword in ["fuel", "def", "diesel", "gas", "40%", "low fuel", "fuel level", "tank"]):
        return GROUP_ID, 5, "⛽ LOW FUEL / DEF"
    
    # Device/dashcam keywords (more comprehensive)
    if any(keyword in full_text for keyword in ["dashcam", "gateway", "disconnect", "unplug", "device", "camera", "unplugged"]):
        return GROUP_ID, 9, "📷 DASHCAMS / GATEWAY"
    
    # Speed-related
    if any(keyword in full_text for keyword in ["speed", "limit", "mph", "speeding"]):
        return GROUP_ID, 3, "🚨 SPEEDING"
    
    # Weight stations
    if any(keyword in full_text for keyword in ["weigh", "weight", "zone", "interstate"]):
        return GROUP_ID, 12, "⚖️ WEIGHT STATIONS"
        
    # Spartak
    if any(keyword in full_text for keyword in ["spartak", "shop"]):
        return GROUP_ID, 14, "🏬 SPARTAK SHOP"
    
    # Maintenance
    if any(keyword in full_text for keyword in ["maintenance", "service", "scheduled", "odometer"]):
        return GROUP_ID, 16, "🛠 Scheduled Maintenance by Odometer"
    
    # Engine/critical
    if any(keyword in full_text for keyword in ["idle", "engine", "panic", "harsh", "coolant"]):
        return GROUP_ID, 7, "🚨 CRITICAL MAINTENANCE"
    
    return GROUP_ID, None, "📋 General"

# ===================== MESSAGE FORMATTING =====================
def format_priority_indicator(priority: str) -> str:
    """Format priority indicator"""
    indicators = {
        "CRITICAL": "🔴 CRITICAL",
        "HIGH": "🟠 HIGH PRIORITY", 
        "MEDIUM": "🟡 ALERT",
        "LOW": "🟢 INFO",
        "INFO": "🟢 INFO"  # Added INFO priority to match old format
    }
    return indicators.get(priority, "🟡 ALERT")

async def format_comprehensive_message(event_type: str, data: dict, topic_name: str, priority: str) -> str:
    """Create formatted message"""
    
    # Extract basic data
    vehicle = data.get("vehicle", {})
    vehicle_id = vehicle.get("id")
    vehicle_name = vehicle.get("name", "Unknown Vehicle")
    
    # Try to enrich vehicle data
    if vehicle_id and vehicle_name == "Unknown Vehicle":
        vehicle_details = await get_vehicle_details(vehicle_id)
        if vehicle_details:
            vehicle_name = vehicle_details.get("name", vehicle_name)
    
    # Extract driver data
    driver = data.get("driver", {})
    driver_id = driver.get("id")
    driver_name = driver.get("name", "Unknown Driver")
    
    if driver_id and driver_name == "Unknown Driver":
        driver_details = await get_driver_details(driver_id)
        if driver_details:
            driver_name = driver_details.get("name", driver_name)
    
    # Address handling
    address = data.get("address", {})
    display_address, latitude, longitude = format_address_display(address)
    
    # Create location display
    if latitude and longitude and display_address != "Location unavailable":
        location_display = create_map_link(latitude, longitude, display_address)
    else:
        location_display = escape(display_address) if display_address != "Location unavailable" else "Location unavailable"
    
    # Create old-style event descriptions with location details
    if event_type == "GeofenceEntry" and display_address != "Location unavailable":
        # Extract just the address name for the alert description
        address_name = address.get("name", "")
        if address_name:
            alert_desc = f"entered geofence at {address_name}"
        else:
            alert_desc = f"entered geofence at {display_address}"
    elif event_type == "GeofenceExit" and display_address != "Location unavailable":
        address_name = address.get("name", "")
        if address_name:
            alert_desc = f"exited geofence at {address_name}"
        else:
            alert_desc = f"exited geofence at {display_address}"
    else:
        # Other event descriptions
        alert_descriptions = {
            "GeofenceEntry": "entered zone",
            "GeofenceExit": "exited zone",
            "SevereSpeedingStarted": "started severe speeding",
            "SevereSpeedingEnded": "stopped severe speeding", 
            "EngineIdleOn": "excessive idling started",
            "EngineIdleOff": "excessive idling ended"
        }
        alert_desc = alert_descriptions.get(event_type, event_type)
    
    # Use INFO priority for geofence events to match old format
    if event_type in ["GeofenceEntry", "GeofenceExit"] and priority == "MEDIUM":
        priority = "INFO"
    
    priority_indicator = format_priority_indicator(priority)
    
    # Build message
    header = f"<b>{topic_name}</b>"
    alert_line = f"{priority_indicator}: Vehicle {alert_desc}"
    
    details = []
    details.append(f"🚛 <b>Vehicle:</b> {escape(vehicle_name)}")
    
    if driver_name and driver_name != "Unknown Driver":
        details.append(f"👤 <b>Driver:</b> {escape(driver_name)}")
    
    if location_display != "Location unavailable":
        details.append(f"📍 <b>Location:</b> {location_display}")
    
    # Speed information
    current_speed = vehicle.get("speed") or data.get("speed")
    speed_limit = extract_speed_limit_from_address(address)
    
    if current_speed:
        speed_display = f"🏃 <b>Current Speed:</b> {current_speed} mph"
        if speed_limit:
            speed_display += f" (Limit: {speed_limit} mph)"
            if current_speed > speed_limit:
                over_limit = current_speed - speed_limit
                speed_display += f" ⚠️ <b>OVER BY {over_limit} MPH</b>"
        details.append(speed_display)
    elif speed_limit:
        details.append(f"🚦 <b>Speed Limit:</b> {speed_limit} mph")
        
    # Fuel information
    fuel_percent = vehicle.get("fuelPercent")
    if fuel_percent:
        details.append(f"⛽ <b>Fuel:</b> {fuel_percent}%")
    
    # Timestamp
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    details.append(f"🕐 <b>Time:</b> {timestamp}")
    
    return f"{header}\n\n<b>{alert_line}</b>\n\n" + "\n".join(details)

# ===================== WEBHOOK HANDLER =====================
async def handle_samsara(request):
    """Handle Samsara webhook"""
    try:
        raw_body = await request.read()
        logger.info("📨 Received webhook")
        
        try:
            data_json = json.loads(raw_body)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return web.Response(text="Invalid JSON", status=400)

        # Handle event structure
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
            
            # Analyze event
            enriched_data, chat_id, thread_id, topic_name, priority = await analyze_and_enrich_event(event)
            
            if enriched_data is None:
                logger.info(f"⏭️ Skipping {event_type}")
                continue
            
            try:
                # Create message
                message_text = await format_comprehensive_message(event_type, enriched_data, topic_name, priority)
                
                # Send message
                send_kwargs = {"chat_id": chat_id, "text": message_text}
                if thread_id:
                    send_kwargs["message_thread_id"] = thread_id

                await bot.send_message(**send_kwargs)
                logger.info(f"✅ Sent to {topic_name}: {event_type}")
                
                # Send location pin - you can customize when to send location pins
                # Option 1: Send location for all events (uncomment next line)
                # await send_location_pin(enriched_data, chat_id, thread_id)
                
                # Option 2: Send location only for critical/high priority events
                if priority in ["CRITICAL", "HIGH"]:
                    await send_location_pin(enriched_data, chat_id, thread_id)
                
                # Option 3: Send location for specific event types (uncomment if needed)
                # if event_type in ["GeofenceEntry", "GeofenceExit", "SevereSpeedingStarted"]:
                #     await send_location_pin(enriched_data, chat_id, thread_id)
                
                # Option 4: Send location for speeding events only (uncomment if needed)
                # if "SPEEDING" in topic_name:
                #     await send_location_pin(enriched_data, chat_id, thread_id)
                
            except Exception as e:
                logger.error(f"❌ Failed to send message: {e}")

        return web.Response(text="✅ Processed", status=200)

    except Exception as e:
        logger.exception(f"❌ Webhook error: {e}")
        return web.Response(text="❌ Error", status=500)

async def send_location_pin(data: dict, chat_id: int, thread_id: int = None):
    """Send location pin"""
    try:
        address = data.get("address", {})
        display_address, latitude, longitude = format_address_display(address)
        
        if latitude and longitude:
            send_kwargs = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude}
            if thread_id:
                send_kwargs["message_thread_id"] = thread_id
                
            await bot.send_location(**send_kwargs)
            logger.info(f"📍 Location pin sent for: {display_address}")
            
    except Exception as e:
        logger.error(f"❌ Failed to send location: {e}")

# ===================== TEST ENDPOINTS =====================
async def handle_test(request):
    """Test endpoint"""
    try:
        test_data = {
            "eventType": "SevereSpeedingStarted",
            "eventId": "903a2139-c3d1-4697-b4a7-5fd960d4a805",
            "data": {
                "address": {
                    "id": "199883244", 
                    "name": "65 SPEED ZONE",
                    "formattedAddress": "Interstate 65, Mile Marker 234, Alabama, USA",
                    "geofence": {
                        "circle": {"latitude": 32.2876, "longitude": -86.8404}
                    }
                },
                "vehicle": {"id": "test-vehicle-123", "name": "Unit 5151", "speed": 78, "fuelPercent": 62},
                "driver": {"id": "test-driver-123", "name": "John Smith"},
                "speed": 78
            }
        }
        
        enriched_data, chat_id, thread_id, topic_name, priority = await analyze_and_enrich_event(test_data)
        
        if enriched_data:
            message = await format_comprehensive_message("SevereSpeedingStarted", enriched_data, topic_name, priority)
            
            send_kwargs = {"chat_id": chat_id, "text": message}
            if thread_id:
                send_kwargs["message_thread_id"] = thread_id
                
            await bot.send_message(**send_kwargs)
            return web.Response(text=f"✅ Test sent to {topic_name}", status=200)
        else:
            return web.Response(text="❌ Test event was filtered out", status=200)
            
    except Exception as e:
        logger.error(f"Test error: {e}")
        return web.Response(text=f"❌ Test failed: {e}", status=500)

async def handle_fuel_test(request):
    """Test fuel alert"""
    try:
        fuel_test_data = {
            "eventType": "FuelLevel",
            "eventId": "f87a1f80-c2ac-42fb-a371-069d696fe2cc",
            "data": {
                "vehicle": {"id": "fuel-test", "name": "Unit 1234", "fuelPercent": 35},
                "driver": {"name": "Test Driver"},
                "address": {"name": "Fuel Station", "formattedAddress": "Test Location"}
            }
        }
        
        enriched_data, chat_id, thread_id, topic_name, priority = await analyze_and_enrich_event(fuel_test_data)
        
        if enriched_data:
            message = await format_comprehensive_message("FuelLevel", enriched_data, topic_name, priority)
            
            send_kwargs = {"chat_id": chat_id, "text": message}
            if thread_id:
                send_kwargs["message_thread_id"] = thread_id
                
            await bot.send_message(**send_kwargs)
            return web.Response(text=f"✅ Fuel test sent to {topic_name}", status=200)
        else:
            return web.Response(text="❌ Fuel test filtered out", status=200)
            
    except Exception as e:
        return web.Response(text=f"❌ Fuel test failed: {e}", status=500)

async def handle_dashcam_test(request):
    """Test dashcam alert"""
    try:
        dashcam_test_data = {
            "eventType": "DashcamDisconnected",
            "eventId": "3dc1e918-d864-427a-abc6-b95dabb3a45f",
            "data": {
                "vehicle": {"id": "dashcam-test", "name": "Unit 5678"},
                "driver": {"name": "Test Driver"},
                "address": {"name": "Highway Location", "formattedAddress": "I-75 North"}
            }
        }
        
        enriched_data, chat_id, thread_id, topic_name, priority = await analyze_and_enrich_event(dashcam_test_data)
        
        if enriched_data:
            message = await format_comprehensive_message("DashcamDisconnected", enriched_data, topic_name, priority)
            
            send_kwargs = {"chat_id": chat_id, "text": message}
            if thread_id:
                send_kwargs["message_thread_id"] = thread_id
                
            await bot.send_message(**send_kwargs)
            return web.Response(text=f"✅ Dashcam test sent to {topic_name}", status=200)
        else:
            return web.Response(text="❌ Dashcam test filtered out", status=200)
            
    except Exception as e:
        return web.Response(text=f"❌ Dashcam test failed: {e}", status=500)

async def handle_health(request):
    """Health check"""
    try:
        health_info = {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "bot_configured": bool(TELEGRAM_BOT_TOKEN),
            "samsara_configured": bool(SAMSARA_API_TOKEN),
            "group_id": GROUP_ID,
            "alert_mappings": len(ALERT_MAPPINGS),
            "address_mappings": len(ADDRESS_MAPPINGS)
        }
        
        return web.Response(
            text=json.dumps(health_info, indent=2), 
            status=200,
            content_type="application/json"
        )
    except Exception as e:
        return web.Response(text=f"❌ Health check failed: {e}", status=500)
    """Health check"""
    try:
        health_info = {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "bot_configured": bool(TELEGRAM_BOT_TOKEN),
            "samsara_configured": bool(SAMSARA_API_TOKEN),
            "group_id": GROUP_ID,
            "alert_mappings": len(ALERT_MAPPINGS),
            "address_mappings": len(ADDRESS_MAPPINGS)
        }
        
        return web.Response(
            text=json.dumps(health_info, indent=2), 
            status=200,
            content_type="application/json"
        )
    except Exception as e:
        return web.Response(text=f"❌ Health check failed: {e}", status=500)

# ===================== APP SETUP =====================
def create_app():
    """Create web application"""
    app = web.Application()
    
    # Add routes
    app.router.add_get("/health", handle_health)
    app.router.add_get("/test", handle_test)
    app.router.add_get("/fuel-test", handle_fuel_test)
    app.router.add_get("/dashcam-test", handle_dashcam_test)
    app.router.add_post("/samsara", handle_samsara)
    
    return app

# ===================== CONFIGURATION VALIDATION =====================
async def validate_configuration():
    """Validate setup"""
    logger.info("🔍 Validating configuration...")
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set")
        return False
    
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Telegram bot connected: @{bot_info.username}")
    except Exception as e:
        logger.error(f"❌ Telegram bot connection failed: {e}")
        return False
    
    if SAMSARA_API_TOKEN:
        try:
            session = await get_session()
            headers = {"Authorization": f"Bearer {SAMSARA_API_TOKEN}"}
            async with session.get(f"{SAMSARA_BASE_URL}/fleet/vehicles?limit=1", headers=headers) as response:
                if response.status == 200:
                    logger.info("✅ Samsara API connection successful")
                else:
                    logger.warning(f"⚠️ Samsara API returned {response.status}")
        except Exception as e:
            logger.warning(f"⚠️ Samsara API test failed: {e}")
    else:
        logger.warning("⚠️ SAMSARA_API_TOKEN not set - limited functionality")
    
    logger.info(f"✅ Configuration validated - {len(ALERT_MAPPINGS)} alerts, {len(ADDRESS_MAPPINGS)} addresses")
    return True

# ===================== MAIN FUNCTION =====================
async def main():
    """Main function"""
    
    if not await validate_configuration():
        logger.error("❌ Configuration validation failed")
        return
    
    app = create_app()
    
    logger.info(f"🚀 Starting Bot on port {PORT}")
    logger.info(f"📊 Monitoring {len(ALERT_MAPPINGS)} alert types")
    logger.info(f"📍 Tracking {len(ADDRESS_MAPPINGS)} addresses")
    logger.info(f"💬 Sending to group {GROUP_ID}")
    
    try:
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        await site.start()
        
        logger.info("✅ Bot started successfully!")
        logger.info("🔗 Endpoints: /health, /test, /fuel-test, /dashcam-test, /samsara")
        
        # Keep running
        while True:
            await asyncio.sleep(3600)  # Sleep for 1 hour
                
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
    except Exception as e:
        logger.error(f"❌ Application error: {e}")
    finally:
        await close_session()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Bot stopped")
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        print(f"❌ Error: {e}")