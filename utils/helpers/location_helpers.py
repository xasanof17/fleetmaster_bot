from typing import Any

from .keyboard_helpers import after_location_keyboard
from .text_helpers import format_timestamp


# --------------------------------------------------
# Internal helper
# --------------------------------------------------
def _gps_status_badge(location: dict[str, Any]) -> str:
    """
    Returns a human-readable GPS status badge.
    Expects location["confidence"] = LIVE | STALE
    """
    status = location.get("confidence", "STALE")

    if status == "LIVE":
        return "📡 **GPS Status:** 🟢 LIVE"

    return "📡 **GPS Status:** 🟡 STALE (data may be delayed)"


# --------------------------------------------------
# Static location message (one-time snapshot)
# --------------------------------------------------
def build_static_location_message(
    vehicle: dict[str, Any], location: dict[str, Any]
) -> tuple[str, object]:
    address = location.get("address") or "Unknown location"
    ts = format_timestamp(location.get("time"))
    gps_status = _gps_status_badge(location)

    msg = f"""
🚛 **Truck**: {vehicle.get("name", "N/A")}

📍 **Address:** {address}
⏰ **Time:** {ts}
{gps_status}
""".strip()

    kb = after_location_keyboard()
    return msg, kb


# --------------------------------------------------
# Live location message (tracking started)
# --------------------------------------------------
def build_live_location_message(
    vehicle: dict[str, Any], location: dict[str, Any]
) -> tuple[str, object]:
    address = location.get("address") or "Unknown location"
    ts = format_timestamp(location.get("time"))
    gps_status = _gps_status_badge(location)

    msg = f"""
🚛 **Truck**: {vehicle.get("name", "N/A")}

📡 **Live Location Started**
📍 **Address:** {address}
⏳ **Last Update:** {ts}
{gps_status}
""".strip()

    kb = after_location_keyboard()
    return msg, kb
