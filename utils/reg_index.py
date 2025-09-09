# utils/reg_index.py
import json
from pathlib import Path
from typing import Dict, Optional, Tuple

INDEX_FILE = Path("data/reg_index.json")
INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)

def _load() -> Dict[str, Dict[str, str]]:
    """Return { file_name_lower: {file_id, message_id} }"""
    if not INDEX_FILE.exists():
        return {}
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save(data: Dict[str, Dict[str, str]]) -> None:
    try:
        INDEX_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def index_file(file_name: str, file_id: str, message_id: Optional[int] = None) -> None:
    """Store/overwrite an index entry."""
    name = (file_name or "").strip().lower()
    if not name or not file_id:
        return
    data = _load()
    data[name] = {"file_id": file_id, "message_id": str(message_id or "")}
    _save(data)

def find_by_exact_filename(file_name: str) -> Optional[str]:
    """Return file_id by exact filename (case-insensitive)."""
    name = (file_name or "").strip().lower()
    if not name:
        return None
    data = _load()
    entry = data.get(name)
    return entry["file_id"] if entry else None

def find_latest_for_vehicle(vehicle_name: str) -> Optional[Tuple[str, str]]:
    """
    Find the latest REG PDF for a vehicle by pattern:
      <vehicle_name>-REG-<YYYY>.pdf
    Returns (file_id, file_name) or None.
    """
    if not vehicle_name:
        return None
    vn = vehicle_name.strip().lower()
    data = _load()
    best_year = -1
    best: Optional[Tuple[str, str]] = None
    for fname, payload in data.items():
        if not fname.endswith(".pdf"):
            continue
        # simple check: startswith "<vehicle>-reg-"
        if not fname.startswith(f"{vn}-reg-"):
            continue
        # extract year from tail
        stem = fname[:-4]  # trim .pdf
        parts = stem.split("-reg-")
        if len(parts) != 2:
            continue
        year_part = parts[1]
        # take last 4 consecutive digits if any
        year = None
        for i in range(len(year_part) - 3):
            chunk = year_part[i:i+4]
            if chunk.isdigit():
                year = int(chunk)
        if year is None:
            continue
        if year > best_year:
            best_year = year
            best = (payload.get("file_id"), fname)
    return best
