from typing import List, Dict, Optional
from services.google_ops_service import get_data_for_vehicle_info
from datetime import datetime
from .vehicle_helpers import extract_odometer_miles
import pytz


DEFAULT_TZ = pytz.timezone("Asia/Tashkent")

def format_timestamp(timestamp: str, tz: pytz.timezone = DEFAULT_TZ) -> str:
    """
    Convert ISO timestamp (UTC) into given timezone (default Asia/Tashkent).
    Format: DD.MM.YY HH:MM:SS
    """
    if not timestamp:
        return "Unknown time"

    try:
        # parse UTC time from Samsara
        dt_utc = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        # convert to target timezone
        dt_local = dt_utc.astimezone(tz)

        # format output
        return dt_local.strftime("%d.%m.%y %H:%M:%S")
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


async def format_vehicle_info(vehicle: Dict[str, any]) -> str:
    """
    Combine Samsara vehicle info with Ops CURRENT STATUS + Driver Name.
    """
    name  = vehicle.get("name", "N/A")
    make  = vehicle.get("make", "N/A")
    vin   = vehicle.get("vin") or vehicle.get("externalIds", {}).get("samsara.vin", "N/A")
    plate = vehicle.get("licensePlate", "N/A")
    year  = vehicle.get("year", "N/A")

    # 🔑 Pull Ops status + driver
    unit_number = vehicle.get("name") or vehicle.get("id")
    ops_data    = await get_data_for_vehicle_info(unit_number)
    ops_status  = ops_data["status"]
    driver_name = ops_data["driver"]
    
    odometer_text  = format_odometer_mi(
        vehicle.get("odometer")
        or vehicle.get("odometer_miles")
        or extract_odometer_miles(vehicle)
    )

    last_updated = format_timestamp(vehicle.get("lastUpdated") or vehicle.get("updatedAt"))
    refreshed_at = format_timestamp(datetime.utcnow().isoformat() + "Z")
    
    return (
            f"-------- 🚛 *VEHICLE INFORMATION* --------\n\n"
            f"📋 *NAME*: {name} - {make}\n"  
            f"👤 *DRIVER*: {driver_name}\n"
            f"🏷️ *VIN*: {vin}\n"
            f"🔢 *PLATE*: {plate}\n"
            f"📅 *YEAR*: {year}\n"
            f"📊 *CURRENT STATUS*: _{ops_status}_\n"
            f"🛣️ *ODOMETER*: {odometer_text}\n"
            f"=============================\n"
            f"🕐 *Last Updated*: {last_updated}\n"
            f"⏳ *Refreshed at*: {refreshed_at}"
    )