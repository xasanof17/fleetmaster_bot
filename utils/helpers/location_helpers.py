from typing import Tuple, Dict, Any
from .text_helpers import format_timestamp
from .keyboard_helpers import after_location_keyboard


def build_static_location_message(vehicle: Dict[str, Any], location: Dict[str, Any]) -> Tuple[str, object]:
    address = location.get("address") or "Unknown location"
    ts = format_timestamp(location.get("time"))
    msg = f"""
📍**Address:** {address}\n
⏰**Time:** {ts}
""".strip()
    kb = after_location_keyboard()
    return msg, kb


def build_live_location_message(vehicle: Dict[str, Any], location: Dict[str, Any]) -> Tuple[str, object]:
    address = location.get("address") or "Unknown location"
    ts = format_timestamp(location.get("time"))
    msg = f"""
📡 **Live Location Started**
📍**Address:** {address}\n

⏳**Last Update:** {ts}
""".strip()
    kb = after_location_keyboard()
    return msg, kb
