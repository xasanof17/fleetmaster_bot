import json
from pathlib import Path
from typing import Tuple, Optional

INDEX_FILE = Path("logs/reg_index.json")
INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_index() -> dict:
    """Load index file or return empty dict"""
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_index(data: dict) -> None:
    """Save index file safely"""
    try:
        INDEX_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        print(f"[reg_index] Failed to save index: {e}")


def index_file(file_name: str, file_id: str, message_id: int) -> None:
    """
    Add or update an entry in the index.
    File name is used as key.
    """
    data = _load_index()
    data[file_name] = {
        "file_id": file_id,
        "message_id": message_id,
    }
    _save_index(data)


def find_latest_for_vehicle(vehicle_key: str) -> Optional[Tuple[str, str]]:
    """
    Find the latest indexed file that starts with the given vehicle_key.
    Returns: (file_id, file_name) or None
    """
    data = _load_index()
    matches = [
        (fname, meta)
        for fname, meta in data.items()
        if fname.startswith(vehicle_key.lower())
    ]
    if not matches:
        return None

    # pick the last inserted (latest)
    fname, meta = matches[-1]
    return meta["file_id"], fname
