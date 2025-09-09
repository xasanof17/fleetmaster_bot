import json
import re
from pathlib import Path
from typing import Optional, Tuple

INDEX_FILE = Path("logs/reg_index.json")
INDEX_FILE.parent.mkdir(exist_ok=True)

def index_file(file_name: str, file_id: str, message_id: int):
    """Save or update an indexed PDF in JSON storage"""
    try:
        if INDEX_FILE.exists():
            data = json.loads(INDEX_FILE.read_text())
        else:
            data = {}

        # always normalize file name
        file_name = file_name.strip()

        data[file_name] = {
            "file_id": file_id,
            "message_id": message_id,
        }

        INDEX_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        print(f"[RegIndex] Failed to index {file_name}: {e}")


def find_latest_for_vehicle(vehicle_key: str) -> Optional[Tuple[str, str]]:
    """
    Find the latest registration file for a vehicle by matching
    the vehicle number anywhere in the filename.
    Returns (file_id, file_name) or None.
    """
    if not INDEX_FILE.exists():
        return None

    try:
        data = json.loads(INDEX_FILE.read_text())
        # Normalize to digits (e.g. "5071" from "Truck 5071")
        digits = "".join(re.findall(r"\d+", vehicle_key))

        for fname, info in reversed(list(data.items())):  # newest last
            if digits and digits in fname:
                return info["file_id"], fname
            if vehicle_key.lower() in fname.lower():
                return info["file_id"], fname

        return None
    except Exception as e:
        print(f"[RegIndex] Failed lookup for {vehicle_key}: {e}")
        return None
