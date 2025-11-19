from typing import Any

from .keyboard_helpers import after_location_keyboard
from .text_helpers import format_timestamp


def build_static_location_message(
    vehicle: dict[str, Any], location: dict[str, Any]
) -> tuple[str, object]:
    address = location.get("address") or "Unknown location"
    ts = format_timestamp(location.get("time"))
    msg = f"""
🚛**Truck**: {vehicle.get("name", "N/A")}\n
📍**Address:** {address}\n
⏰**Time:** {ts}
""".strip()
    kb = after_location_keyboard()
    return msg, kb


def build_live_location_message(
    vehicle: dict[str, Any], location: dict[str, Any]
) -> tuple[str, object]:
    address = location.get("address") or "Unknown location"
    ts = format_timestamp(location.get("time"))
    msg = f"""
🚛**Truck**: {vehicle.get("name", "N/A")}\n
📡**Live Location Started**\n
📍**Address:** {address}\n
⏳**Last Update:** {ts}
""".strip()
    kb = after_location_keyboard()
    return msg, kb
