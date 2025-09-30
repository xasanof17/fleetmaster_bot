import os
import json

# Load once
_group_map_env = os.getenv("TRUCK_GROUP_MAP", "{}")

try:
    TRUCK_GROUPS = json.loads(_group_map_env)
except json.JSONDecodeError:
    TRUCK_GROUPS = {}

def get_group_id_for_unit(unit: str) -> int | None:
    """
    Return group chat_id for given truck number.
    Example: "2000" -> -1001234567890
    """
    return TRUCK_GROUPS.get(str(unit))
