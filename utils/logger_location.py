import json
from datetime import datetime
from pathlib import Path
import pytz

LOG_FILE = Path("logs/location_requests.json")
LOG_FILE.parent.mkdir(exist_ok=True)
DEFAULT_TZ = pytz.timezone("Asia/Tashkent")


def log_location_request(user_id: int, vehicle_id: str, location_type: str, address: str = None):
    """Append a location request to logs/location_requests.json with Tashkent time."""
    try:
        dt_local = datetime.utcnow().replace(tzinfo=pytz.UTC).astimezone(DEFAULT_TZ)
        ts = dt_local.strftime("%d.%m.%y %H:%M:%S")

        entry = {
            "user_id": user_id,
            "vehicle_id": vehicle_id,
            "location_type": location_type,   # "static" or "live"
            "address": address or "N/A",
            "timestamp": ts,
        }

        if LOG_FILE.exists():
            data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        else:
            data = []

        data.append(entry)
        LOG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    except Exception as e:
        print(f"[LocationLogger] Failed to write log: {e}")


def read_logs(limit: int = 20):
    """Read the most recent logs"""
    if not LOG_FILE.exists():
        return []
    try:
        data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        return data[-limit:]  # last N entries
    except Exception as e:
        print(f"[LocationLogger] Failed to read logs: {e}")
        return []
