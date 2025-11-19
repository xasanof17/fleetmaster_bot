# services/google_service.py
import datetime
from typing import Any

from google.oauth2.service_account import Credentials
from gspread_asyncio import AsyncioGspreadClientManager

from config import settings
from utils.parsers import _normalize  # ✔ use global normalize


# -------------------------------
# CONFIG
# -------------------------------
GOOGLE_CREDS_JSON = settings.GOOGLE_CREDS_JSON

PM_SPREADSHEET_NAME = settings.PM_SPREADSHEET_NAME
PM_WORKSHEET_NAME = settings.PM_WORKSHEET_NAME
TRAILER_SHEET_NAME = settings.PM_TRAILERS_NAME


# -------------------------------
# GOOGLE AUTH
# -------------------------------
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

    all_vals = await ws.get_all_values()
    if len(all_vals) < 2:
        return []

    headers = all_vals[0]

    # make headers unique
    seen = {}
    unique_headers = []
    for h in headers:
        h_clean = h.strip() or f"EMPTY_{len(unique_headers)}"

        if h_clean in seen:
            seen[h_clean] += 1
            unique_headers.append(f"{h_clean}_{seen[h_clean]}")
        else:
            seen[h_clean] = 0
            unique_headers.append(h_clean)

    records = []
    for row in all_vals[1:]:
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


# =============================================================
#        PM TRUCK SERVICE (ORIGINAL)
# =============================================================
class GooglePMService:
    """Sheet-driven PM logic."""

    async def get_urgent_list(self, mile_limit: int = 5000, day_limit: int = 30):
        rows = await _get_all_records()
        out = []
        for r in rows:
            status = str(r.get("STATUS", "")).strip().upper()
            if status == "BROKEN":
                continue

            left = _safe_int(r.get("Left"))
            days = _safe_int(r.get("Days"))

            if left <= mile_limit or days <= day_limit:
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

    async def get_oil_list(self, mile_limit: int = 10000):
        rows = await _get_all_records()
        out = []

        for r in rows:
            status = str(r.get("STATUS", "")).strip().upper()
            if status == "BROKEN" or "URGENT" in status:
                continue

            left = _safe_int(r.get("Left"))
            if left <= mile_limit:
                truck = str(
                    r.get("Truck Number") or r.get("TRUCK NUMBER") or r.get("Truck") or ""
                ).strip()
                if truck:
                    out.append(
                        {
                            "truck": truck,
                            "left": left,
                            "status": status,
                            "updated": _now_str(),
                        }
                    )
        return out

    async def list_all_vehicles(self):
        rows = await _get_all_records()
        items = []

        for r in rows:
            t = str(
                r.get("Truck Number")
                or r.get("TRUCK NUMBER")
                or r.get("Truck")
                or ""
            ).strip()
            if t:
                items.append({"id": t, "name": f"Truck {t}"})

        return items

    async def get_vehicle_details(self, truck: str):
        rows = await _get_all_records()

        for r in rows:
            truck_num = str(
                r.get("Truck Number")
                or r.get("TRUCK NUMBER")
                or r.get("Truck")
                or ""
            )

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
                    "latest_history": r.get("Lastest History")
                    or r.get("Latest History")
                    or "",
                    "updated": _now_str(),
                }

        return None


google_pm_service = GooglePMService()


# =============================================================
#        TRAILER OWNERS SERVICE (FIXED)
# =============================================================
class GoogleTrailerService:
    """
    Reads TRAILER OWNERS sheet and returns trailer info for:
       XTRA LEASE  (B–G)
       VANGUARD    (I–N)
       GREAT DANE  (P–U)
    """

    async def _load_sheet(self):
        agcm = await _manager.authorize()
        ss = await agcm.open(PM_SPREADSHEET_NAME)
        ws = await ss.worksheet(TRAILER_SHEET_NAME)
        return await ws.get_all_values()

    def _parse_section(self, all_rows, start_col, end_col, owner_name):
        trailers = {}

        for i in range(2, len(all_rows)):  # skip header rows
            row = all_rows[i]

            if len(row) <= start_col:
                continue

            trailer_raw = row[start_col].strip()
            if not trailer_raw:
                continue

            trailer_key = _normalize(trailer_raw)

            try:
                vin = row[start_col + 1].strip()
                year = row[start_col + 2].strip()
                plate = row[start_col + 3].strip()
                gps = row[start_col + 4].strip()
                notes = row[start_col + 5].strip() if start_col + 5 < len(row) else ""
            except:
                continue

            trailers[trailer_key] = {
                "trailer": trailer_raw,
                "vin": vin,
                "year": year,
                "plate": plate,
                "gps": gps,
                "notes": notes,
                "owner": owner_name,
            }

        return trailers   # ✔ FIXED — OUTSIDE loop

    async def load_all_trailers(self):
        all_rows = await self._load_sheet()

        xtra = self._parse_section(all_rows, 1, 6, "XTRA LEASE")
        vanguard = self._parse_section(all_rows, 8, 13, "VANGUARD")
        great_dane = self._parse_section(all_rows, 15, 20, "GREAT DANE")

        return {**xtra, **vanguard, **great_dane}

    async def get_trailer_info(self, trailer_number: str):
        key = _normalize(trailer_number)
        trailers = await self.load_all_trailers()
        return trailers.get(key)

    async def build_trailer_template(self, trailer_number: str):
        data = await self.get_trailer_info(trailer_number)
        if not data:
            return None

        return (
            f"### {data['trailer']}\n"
            f"VIN: {data['vin']}\n"
            f"Plate: {data['plate']}\n"
            f"Year: {data['year']}\n"
            f"GPS: {data['gps']}\n"
            f"{data['owner']}"
        )


google_trailer_service = GoogleTrailerService()
