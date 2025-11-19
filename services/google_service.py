import datetime
from typing import Any

from config import settings
from google.oauth2.service_account import Credentials
from gspread_asyncio import AsyncioGspreadClientManager

GOOGLE_CREDS_JSON = settings.GOOGLE_CREDS_JSON
PM_SPREADSHEET_NAME = settings.PM_SPREADSHEET_NAME
PM_WORKSHEET_NAME = settings.PM_WORKSHEET_NAME


# ---- auth ----
def _creds():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    info = settings.GOOGLE_CREDS_JSON or {}
    return Credentials.from_service_account_info(info, scopes=scopes)


_manager = AsyncioGspreadClientManager(_creds)


async def _get_all_records() -> list[dict[str, Any]]:
    """
    Manually parse sheet to handle duplicate headers.
    Returns list[dict] using header row.
    """
    agcm = await _manager.authorize()
    ss = await agcm.open(PM_SPREADSHEET_NAME)
    ws = await ss.worksheet(PM_WORKSHEET_NAME)

    # Get all values manually
    all_vals = await ws.get_all_values()

    if len(all_vals) < 2:
        return []

    # First row is headers
    headers = all_vals[0]

    # Make headers unique by adding suffix if duplicate
    seen = {}
    unique_headers = []
    for h in headers:
        h_clean = h.strip()
        if not h_clean:
            h_clean = f"EMPTY_{len(unique_headers)}"

        if h_clean in seen:
            seen[h_clean] += 1
            unique_headers.append(f"{h_clean}_{seen[h_clean]}")
        else:
            seen[h_clean] = 0
            unique_headers.append(h_clean)

    # Build records
    records = []
    for row in all_vals[1:]:  # Skip header row
        record = {}
        for i, value in enumerate(row):
            if i < len(unique_headers):
                record[unique_headers[i]] = value
        records.append(record)

    return records


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
    async def get_urgent_list(
        self, mile_limit: int = 5000, day_limit: int = 30
    ) -> list[dict[str, Any]]:
        rows = await _get_all_records()
        out: list[dict[str, Any]] = []
        for r in rows:
            status = str(r.get("STATUS", "")).strip().upper()
            if status == "BROKEN":
                continue
            left = _safe_int(r.get("Left"))
            days = _safe_int(r.get("Days"))
            if left <= mile_limit or days <= day_limit:
                # Try different possible column names
                truck = str(
                    r.get("Truck Number") or r.get("TRUCK NUMBER") or r.get("Truck") or ""
                ).strip()
                if truck:
                    out.append(
                        {
                            "truck": truck,
                            "left": left,
                            "days": days,
                            "status": status,
                            "updated": _now_str(),
                        }
                    )
        return out

    async def get_oil_list(self, mile_limit: int = 10000) -> list[dict[str, Any]]:
        rows = await _get_all_records()
        out: list[dict[str, Any]] = []
        for r in rows:
            status = str(r.get("STATUS", "")).strip().upper()
            if status == "BROKEN":
                continue
            left = _safe_int(r.get("Left"))

            if "URGENT" in status:
                continue

            if left <= mile_limit:
                # Try different possible column names
                truck = str(
                    r.get("Truck Number") or r.get("TRUCK NUMBER") or r.get("Truck") or ""
                ).strip()
                if truck:
                    out.append(
                        {"truck": truck, "left": left, "status": status, "updated": _now_str()}
                    )
        return out

    # ------- Vehicles list for the keyboard (NO pagination here) -------
    async def list_all_vehicles(self) -> list[dict[str, str]]:
        """Return every truck as {'id': '<unit>', 'name': 'Truck <unit>'}."""
        rows = await _get_all_records()
        items: list[dict[str, str]] = []
        for r in rows:
            # Try different possible column names
            t = str(r.get("Truck Number") or r.get("TRUCK NUMBER") or r.get("Truck") or "").strip()
            if t:
                items.append({"id": t, "name": f"Truck {t}"})
        return items

    # ------- Full details for a single truck -------
    async def get_vehicle_details(self, truck: str) -> dict[str, Any] | None:
        rows = await _get_all_records()
        for r in rows:
            # Try different possible column names
            truck_num = str(r.get("Truck Number") or r.get("TRUCK NUMBER") or r.get("Truck") or "")
            if truck_num == str(truck):
                return {
                    "truck": truck_num,
                    "pm_date": r.get("Oil change\ndate")
                    or r.get("Oil change date")
                    or r.get("PM Date")
                    or "N/A",
                    "days": _safe_int(r.get("Days")),
                    "left": _safe_int(r.get("Left")),
                    "status": r.get("STATUS") or "N/A",
                    "notes": r.get("Notes") or "",
                    "last_history": r.get("Last History") or "",
                    "latest_history": r.get("Lastest History") or r.get("Latest History") or "",
                    "updated": _now_str(),
                }
        return None


google_pm_service = GooglePMService()
