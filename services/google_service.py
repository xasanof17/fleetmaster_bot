import os, json, datetime
from typing import List, Dict, Any, Tuple
from gspread_asyncio import AsyncioGspreadClientManager
from google.oauth2.service_account import Credentials

GOOGLE_CREDS_JSON   = os.getenv("GOOGLE_CREDS_JSON")
PM_SPREADSHEET_NAME = os.getenv("PM_SPREADSHEET_NAME")
PM_WORKSHEET_NAME   = os.getenv("PM_WORKSHEET_NAME", "PM_TRACKER")  # adjust to your real tab name

# ---- auth ----
def _creds():
    creds_dict = json.loads(GOOGLE_CREDS_JSON or "{}")
    return Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )

_manager = AsyncioGspreadClientManager(_creds)

async def _get_all_records() -> List[Dict[str, Any]]:
    """Always return list[dict] using header row."""
    agcm = await _manager.authorize()
    ss   = await agcm.open(PM_SPREADSHEET_NAME)
    ws   = await ss.worksheet(PM_WORKSHEET_NAME)
    return await ws.get_all_records()

def _now_str() -> str:
    return datetime.datetime.now().strftime("%m/%d/%Y")

def _safe_int(v, default=0) -> int:
    try:
        s = str(v).replace(",", "").strip()
        if s == "" or s.upper() in {"#VALUE!", "N/A", "NA"}:
            return default
        return int(float(s))
    except Exception:
        return default

class GooglePMService:
    """Sheet-driven PM logic with a consistent UI-facing shape."""

    # ------- Lists for the pinned messages -------
    async def get_urgent_list(self, mile_limit: int = 5000, day_limit: int = 30) -> List[Dict[str, Any]]:
        rows = await _get_all_records()
        out: List[Dict[str, Any]] = []
        for r in rows:
            status = str(r.get("STATUS", "")).strip().upper()
            if status == "BROKEN":
                continue
            left = _safe_int(r.get("Left"))
            days = _safe_int(r.get("Days"))
            if left <= mile_limit or days <= day_limit:
                truck = str(r.get("Truck Number") or r.get("Truck") or "").strip()
                if truck:
                    out.append({"truck": truck, "left": left, "days": days, "status": status, "updated": _now_str()})
        return out

    async def get_oil_list(self, mile_limit: int = 10000) -> List[Dict[str, Any]]:
        rows = await _get_all_records()
        out: List[Dict[str, Any]] = []
        for r in rows:
            status = str(r.get("STATUS", "")).strip().upper()
            if status == "BROKEN":
                continue
            left = _safe_int(r.get("Left"))
            if left <= mile_limit:
                truck = str(r.get("Truck Number") or r.get("Truck") or "").strip()
                if truck:
                    out.append({"truck": truck, "left": left, "status": status, "updated": _now_str()})
        return out

    # ------- Vehicles list for the keyboard (NO pagination here) -------
    async def list_all_vehicles(self) -> List[Dict[str, str]]:
        """Return every truck as {'id': '<unit>', 'name': 'Truck <unit>'}."""
        rows = await _get_all_records()
        items: List[Dict[str, str]] = []
        for r in rows:
            t = str(r.get("Truck Number") or r.get("Truck") or "").strip()
            if t:
                items.append({"id": t, "name": f"Truck {t}"})
        return items

    # ------- Full details for a single truck -------
    async def get_vehicle_details(self, truck: str) -> Dict[str, Any] | None:
        rows = await _get_all_records()
        for r in rows:
            if str(r.get("Truck Number")) == str(truck):
                return {
                    "truck":          str(r.get("Truck Number")),
                    "pm_date":        r.get("Oil change\ndate") or r.get("Oil change date"),
                    "days":           _safe_int(r.get("Days")),
                    "left":           _safe_int(r.get("Left")),
                    "status":         r.get("STATUS"),
                    "notes":          r.get("Notes"),
                    "last_history":   r.get("Last History"),
                    "latest_history": r.get("Lastest History"),
                    "updated":        _now_str(),
                }
        return None

google_pm_service = GooglePMService()
