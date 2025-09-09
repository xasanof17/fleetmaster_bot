from typing import List, Dict, Optional
from datetime import datetime
from .vehicle_helpers import extract_odometer_miles


def format_timestamp(timestamp: Optional[str] = None) -> str:
    if not timestamp:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return timestamp


def format_odometer_mi(miles: Optional[int]) -> str:
    if miles is None:
        return "Not available"
    return f"{miles:,} mi"


def truncate_text(text: Optional[str], max_length: int = 50) -> str:
    if text is None:
        return ""
    text = str(text)
    return text if len(text) <= max_length else text[: max_length - 1] + "…"


def format_vehicle_list(vehicles: List[Dict[str, any]], limit: int = 5) -> str:
    if not vehicles:
        return "❌ No vehicles found in your fleet."

    message = f"🚛 **Fleet Vehicles** ({len(vehicles)} total)\n\nSelect a vehicle to view details:\n\n"
    for i, v in enumerate(vehicles[:limit], 1):
        name = v.get("name", f"Vehicle {i}")
        make = v.get("make", "N/A")
        message += f"**{i}.** {name} - ({make})\n"
    if len(vehicles) > limit:
        message += f"\n... and {len(vehicles) - limit} more vehicles"

    return message


def format_vehicle_info(vehicle: Dict[str, any]) -> str:
    name = vehicle.get("name", "N/A")
    make = vehicle.get("make", "N/A")
    vin = vehicle.get("vin") or vehicle.get("externalIds", {}).get("samsara.vin", "N/A")
    plate = vehicle.get("licensePlate", "N/A")
    year = vehicle.get("year", "N/A")
    status = vehicle.get("status", vehicle.get("engineState", "N/A"))

    odometer = (
        vehicle.get("odometer")
        or vehicle.get("odometer_miles")
        or extract_odometer_miles(vehicle)
    )
    odometer_text = format_odometer_mi(odometer)

    last_updated = vehicle.get("lastUpdated") or vehicle.get("updatedAt")
    last_updated = format_timestamp(last_updated)
    refreshed_at = datetime.utcnow().strftime("%H:%M:%S UTC")

    return f"""🚛 **Vehicle Information**

📋 **Name**: {name} - {make}
🏷️ **VIN**: {vin}
🔢 **Plate**: {plate}
📅 **Year**: {year}
📊 **Status**: {status}
🛣️ **Odometer**: {odometer_text}

🕐 **Last Updated**: {last_updated}
⏳ **Refreshed at**: {refreshed_at}
""".strip()
