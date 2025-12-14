from datetime import datetime, timedelta
from typing import Any

from google.oauth2.service_account import Credentials
from gspread_asyncio import AsyncioGspreadClientManager

from config import settings

# ─────────────────────────────────────────────
# Environment
# ─────────────────────────────────────────────
GOOGLE_CREDS_JSON = settings.GOOGLE_CREDS_JSON
OPS_SPREADSHEET_NAME = settings.OPS_SPREADSHEET_NAME
OPS_WORKSHEET_NAME = settings.OPS_WORKSHEET_NAME

# Cache
_CACHE: dict[str, Any] = {"data": None, "time": None}
_CACHE_TTL = timedelta(minutes=5)


# ─────────────────────────────────────────────
# Google Auth
# ─────────────────────────────────────────────
def _get_creds():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    info = GOOGLE_CREDS_JSON or {}
    return Credentials.from_service_account_info(info, scopes=scopes)


_manager = AsyncioGspreadClientManager(_get_creds)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _today() -> str:
    return datetime.now().strftime("%m/%d/%Y")


# ─────────────────────────────────────────────
# Sheet Reader
# ─────────────────────────────────────────────
async def _read_all_sections() -> dict[str, Any]:
    agcm = await _manager.authorize()
    ss = await agcm.open(OPS_SPREADSHEET_NAME)
    ws = await ss.worksheet(OPS_WORKSHEET_NAME)

    all_vals = await ws.get_all_values()
    if len(all_vals) < 6:
        return {
            "stats": {},
            "fleet_rows": [],
            "broken_road": [],
            "side_tow": [],
            "side_owner": [],
        }

    # ── Top stats (row 1)
    stats: dict[str, str] = {}
    for cell in all_vals[0]:
        if ":" in cell:
            k, v = cell.split(":", 1)
            stats[k.strip().upper()] = v.strip()

    # ── Find "Broken on the Road" table
    broken_start = None
    for idx, row in enumerate(all_vals):
        if any("Broken on the Road" in c for c in row):
            broken_start = idx
            break

    # ── Fleet table
    fleet_end = broken_start if broken_start else len(all_vals)
    headers = [h.strip() or f"COL{i}" for i, h in enumerate(all_vals[2])]
    fleet_rows = [
        {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
        for row in all_vals[3:fleet_end]
        if any(cell.strip() for cell in row)
    ]

    # ── Broken on the road table
    broken_road = []
    if broken_start is not None and broken_start + 2 < len(all_vals):
        br_headers = [
            h.strip() or f"COL{i}"
            for i, h in enumerate(all_vals[broken_start + 1])
        ]
        for row in all_vals[broken_start + 2 :]:
            if not any(cell.strip() for cell in row):
                continue
            broken_road.append(
                {
                    br_headers[i]: (row[i] if i < len(row) else "")
                    for i in range(len(br_headers))
                }
            )

    # ─────────────────────────────────────────
    # SIDE TABLES (O6:P = Tow, Q6:R = Owner)
    # ─────────────────────────────────────────
    side_tow: list[str] = []
    side_owner: list[str] = []

    # Start from row 6 (index 5)
    for row in all_vals[5:]:
        # Tow Truck → O (14), P (15)
        if len(row) > 15:
            tow_unit = (row[14] or "").strip()
            tow_name = (row[15] or "").strip()
            if tow_unit and tow_name:
                side_tow.append(f"{tow_unit} - {tow_name} ( Tow Truck )")

        # Owner Operator → Q (16), R (17)
        if len(row) > 17:
            owner_unit = (row[16] or "").strip()
            owner_name = (row[17] or "").strip()
            if owner_unit and owner_name:
                side_owner.append(f"{owner_unit} - {owner_name} ( Owner )")

    return {
        "stats": stats,
        "fleet_rows": fleet_rows,
        "broken_road": broken_road,
        "side_tow": side_tow,
        "side_owner": side_owner,
    }


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────
async def get_data_for_vehicle_info(unit: str) -> dict[str, str]:
    agcm = await _manager.authorize()
    ss = await agcm.open(OPS_SPREADSHEET_NAME)
    ws = await ss.worksheet(OPS_WORKSHEET_NAME)

    all_vals = await ws.get_all_values()
    if len(all_vals) < 4:
        return {"status": "N/A", "driver": "N/A"}

    headers = [h.strip() for h in all_vals[2]]
    for row in all_vals[3:]:
        record = {
            headers[i]: (row[i] if i < len(row) else "")
            for i in range(len(headers))
        }
        if str(record.get("TRUCK NUMBER", "")).strip() == str(unit).strip():
            return {
                "status": record.get("CURRENT STATUS", "N/A") or "N/A",
                "driver": record.get("DRIVER NAME", "N/A") or "N/A",
            }

    return {"status": "N/A", "driver": "N/A"}


class GoogleOpsService:
    async def get_summary(self) -> dict[str, Any]:
        global _CACHE

        if _CACHE["data"] and _CACHE["time"]:
            if datetime.now() - _CACHE["time"] < _CACHE_TTL:
                return _CACHE["data"]

        data = await _read_all_sections()
        stats = data["stats"]

        broken_road_lines = []
        for r in data["broken_road"]:
            truck = r.get("Trucks") or r.get("TRUCKS") or ""
            driver = r.get("Previous Driver") or r.get("PREVIOUS DRIVER") or ""
            if truck:
                broken_road_lines.append(f"{truck} - _{driver}_")

        def g(k: str) -> str:
            return stats.get(k, "0")

        summary = {
            "date": _today(),
            "total": g("TOTAL"),
            "active": g("ACTIVE"),
            "home_time": g("HOME TIME"),
            "broken": g("BROKEN TRUCK"),
            "getting_ready": g("GETTING READY"),
            "accident": g("ACCIDENT"),
            "lost": g("TOTAL LOST"),
            "tow_list": data["side_tow"],
            "owner_list": data["side_owner"],
            "broken_road": broken_road_lines,
        }

        _CACHE["data"] = summary
        _CACHE["time"] = datetime.now()
        return summary

    async def as_markdown(self) -> str:
        d = await self.get_summary()

        tow_lines = "\n".join(d["tow_list"]) or "None"
        owner_lines = "\n".join(d["owner_list"]) or "None"
        road_lines = "\n".join(d["broken_road"]) or "None"

        return (
            "======= *DELTA TRUCKS* =======\n"
            f"*TOTAL* : {d['total']}\n"
            f"*HOME TIME* : {d['home_time']}\n"
            f"*BROKEN TRUCK* : {d['broken']}\n"
            f"*GETTING READY* : {d['getting_ready']}\n"
            f"*ACCIDENT* : {d['accident']}\n"
            f"*TOTAL LOST* : {d['lost']}\n"
            f"*ACTIVE* : {d['active']}\n"
            "=========================\n"
            f"*TOW TRUCKS* : {len(d['tow_list'])}\n"
            f"{tow_lines}\n\n"
            f"*OWNER OPERATOR* : {len(d['owner_list'])}\n"
            f"{owner_lines}\n"
            "=========================\n"
            f"*BROKEN ON THE ROAD ({len(d['broken_road'])})*:\n"
            f"{road_lines}\n"
            "=========================\n"
            f"*DATE* : {d['date']}"
        )


# Singleton
google_ops_service = GoogleOpsService()
