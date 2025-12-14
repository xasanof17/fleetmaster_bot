# services/google_service.py
import datetime
import time
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
            t = str(r.get("Truck Number") or r.get("TRUCK NUMBER") or r.get("Truck") or "").strip()
            if t:
                items.append({"id": t, "name": f"Truck {t}"})

        return items

    async def get_vehicle_details(self, truck: str):
        rows = await _get_all_records()

        for r in rows:
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


# =============================================================
#        TRAILER OWNERS SERVICE (FIXED)
# =============================================================
# =============================================================
#        TRAILER OWNERS SERVICE (FULL + FUZZY SEARCH)
# =============================================================
def _gps_label(value: str) -> str:
    v = str(value).strip().upper()
    if v in {"YES", "Y", "TRUE", "1"}:
        return "Yes ✅"
    if v in {"NO", "N", "FALSE", "0"}:
        return "No ❌"
    return "Unknown ❓"


class GoogleTrailerService:
    def __init__(self):
        self._cache: dict[str, dict] | None = None
        self._last_load: float = 0
        self._ttl: int = 120  # seconds (better for big sheets)

    # --------------------------------------------------
    async def _load_sheet(self):
        agcm = await _manager.authorize()
        ss = await agcm.open(PM_SPREADSHEET_NAME)
        ws = await ss.worksheet(TRAILER_SHEET_NAME)
        return await ws.get_all_values()

    # --------------------------------------------------
    def _parse_section(
        self,
        rows,
        trailer_col: int,
        vin_col: int,
        year_col: int,
        plate_col: int,
        make_col: int,
        gps_col: int,
        notes_col: int,
        owner: str,
    ):
        trailers = {}

        for i in range(2, len(rows)):  # row 3+
            row = rows[i]

            def cell(idx):
                return row[idx].strip() if idx < len(row) else ""

            trailer = cell(trailer_col)
            if not trailer:
                continue

            key = _normalize(trailer)

            trailers[key] = {
                # RAW
                "trailer": trailer,
                "vin": cell(vin_col) or "no vin",
                "year": cell(year_col) or "—",
                "plate": cell(plate_col) or "—",
                "make": cell(make_col) or "no make",
                "gps": cell(gps_col),
                "notes": cell(notes_col),
                "owner": owner,
                # SEARCH INDEXES
                "_key": key,
                "_n_trailer": key,
                "_n_vin": _normalize(cell(vin_col)),
                "_n_plate": _normalize(cell(plate_col)),
            }

        return trailers

    # --------------------------------------------------
    async def load_all_trailers(self):
        now = time.time()
        if self._cache and (now - self._last_load) < self._ttl:
            return self._cache

        rows = await self._load_sheet()

        xtra = self._parse_section(rows, 1, 2, 3, 4, 5, 6, 7, "XTRA LEASE")
        vanguard = self._parse_section(rows, 9, 10, 11, 12, 13, 14, 15, "VANGUARD")
        great_dane = self._parse_section(rows, 17, 18, 19, 20, 21, 22, 23, "GREAT DANE")

        self._cache = {**xtra, **vanguard, **great_dane}
        self._last_load = now
        return self._cache

    # --------------------------------------------------
    async def get_trailer_info(self, trailer: str):
        trailers = await self.load_all_trailers()
        return trailers.get(_normalize(trailer))

    # --------------------------------------------------
    def _query_allowed(self, q: str) -> bool:
        q = q.strip()
        if len(q) < 2:
            return False

        # must contain at least one letter or digit
        has_letter = any(c.isalpha() for c in q)
        has_digit = any(c.isdigit() for c in q)

        return has_letter or has_digit

    # --------------------------------------------------
    def fuzzy_score(self, query: str, data: dict) -> int:
        q = _normalize(query)

        if not self._query_allowed(q):
            return 0

        t = data["_n_trailer"]
        score = 0

        # 1️⃣ EXACT trailer match
        if q == t:
            return 1000

        # 2️⃣ STRONG trailer prefix match (preferred)
        if t.startswith(q):
            score += 250
        elif q in t:
            score += 150  # weaker than prefix

        # 3️⃣ VIN / PLATE only if trailer is weak
        if score < 200:
            for field in ("_n_vin", "_n_plate"):
                val = data.get(field, "")
                if val and q in val:
                    score += 120

        # 4️⃣ Length penalty
        score -= abs(len(t) - len(q))

        return score

    # --------------------------------------------------
    def fuzzy_best_match(self, query: str, trailers: dict):
        q = _normalize(query)
        if not self._query_allowed(q):
            return None

        best, best_score = None, 0
        for data in trailers.values():
            s = self.fuzzy_score(q, data)
            if s > best_score:
                best_score = s
                best = data["trailer"]

        return best

    # --------------------------------------------------
    def fuzzy_suggestions(self, query: str, trailers: dict, limit: int = 6):
        q = _normalize(query)
        if not self._query_allowed(q):
            return []

        scored = []
        for data in trailers.values():
            s = self.fuzzy_score(q, data)
            if s >= 50:  # strong matches only
                scored.append((s, data["trailer"]))

        scored.sort(reverse=True)
        return [name for _, name in scored[:limit]]

    # --------------------------------------------------
    async def build_trailer_template(self, trailer: str):
        data = await self.get_trailer_info(trailer)
        if not data:
            return None

        text = (
            f"### {data['trailer']}\n"
            f"VIN: {data['vin']}\n"
            f"Plate: {data['plate']}\n"
            f"Year: {data['year']}\n"
            f"GPS: {_gps_label(data.get('gps'))}\n"
            f"Make: {data['make']}\n"
            f"{data['owner']}"
        )

        if data.get("notes"):
            text += f"\nNotes: {data['notes']}"

        return text


google_trailer_service = GoogleTrailerService()
