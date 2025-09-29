import os
import json
import datetime
from typing import Dict, List, Any
from gspread_asyncio import AsyncioGspreadClientManager
from google.oauth2.service_account import Credentials
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ── Environment ──────────────────────────────────────────────
GOOGLE_CREDS_JSON    = os.getenv("GOOGLE_CREDS_JSON")
OPS_SPREADSHEET_NAME = os.getenv("OPS_SPREADSHEET_NAME", "OPERATION DEPARTMENT")
OPS_WORKSHEET_NAME   = os.getenv("OPS_WORKSHEET_NAME", "OPERATIONS")

# ── Google Auth ──────────────────────────────────────────────
def _get_creds():
    creds_dict = json.loads(GOOGLE_CREDS_JSON)
    return Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

_manager = AsyncioGspreadClientManager(_get_creds)

# ── Helpers ──────────────────────────────────────────────────
def _today() -> str:
    return datetime.datetime.now().strftime("%m/%d/%Y")

async def _read_all_sections() -> Dict[str, Any]:
    agcm = await _manager.authorize()
    ss   = await agcm.open(OPS_SPREADSHEET_NAME)
    ws   = await ss.worksheet(OPS_WORKSHEET_NAME)

    all_vals = await ws.get_all_values()
    if len(all_vals) < 3:
        return {"stats": {}, "fleet_rows": [], "broken_road": [], "side_tow": [], "side_owner": []}

    # Top stats (first row)
    stats: Dict[str, str] = {}
    for cell in all_vals[0]:
        if ":" in cell:
            k, v = cell.split(":", 1)
            stats[k.strip().upper()] = v.strip()

    # Find “Broken on the Road” start
    second_table_idx = None
    for idx, row in enumerate(all_vals):
        if any("Broken on the Road" in c for c in row):
            second_table_idx = idx
            break

    # Fleet rows
    fleet_end = second_table_idx if second_table_idx else len(all_vals)
    headers_main = [h.strip() or f"COL{i}" for i, h in enumerate(all_vals[1])]
    fleet_rows = [
        {headers_main[i]: (row[i] if i < len(row) else "") for i in range(len(headers_main))}
        for row in all_vals[2:fleet_end]
        if any(cell.strip() for cell in row)
    ]

    # Broken-road rows
    broken_road_rows: List[Dict[str, str]] = []
    if second_table_idx is not None and second_table_idx + 1 < len(all_vals):
        headers_br = [h.strip() or f"COL{i}" for i, h in enumerate(all_vals[second_table_idx + 1])]
        broken_road_rows = [
            {headers_br[i]: (row[i] if i < len(row) else "") for i in range(len(headers_br))}
            for row in all_vals[second_table_idx + 2:]
            if any(cell.strip() for cell in row)
        ]

    # Tow & Owner
    side_tow, side_owner = [], []
    for row in all_vals[3:]:
        if len(row) > 16:
            num  = (row[15] or "").strip()
            name = (row[16] or "").strip()
            if (num or name) and num.lower() != "tow truck":
                side_tow.append(f"{num} - _{name}_" if name else num)
        if len(row) > 18:
            num  = (row[17] or "").strip()
            name = (row[18] or "").strip()
            if (num or name) and num.lower() != "owner":
                side_owner.append(f"{num} - _{name}_" if name else num)

    return {
        "stats":       stats,
        "fleet_rows":  fleet_rows,
        "broken_road": broken_road_rows,
        "side_tow":    side_tow,
        "side_owner":  side_owner,
    }

# ── Public API ───────────────────────────────────────────────
# services/google_ops_service.py
async def get_data_for_vehicle_info(unit: str) -> Dict[str, str]:
    """
    Returns {'status': str, 'driver': str} for the given truck number.
    Reads row 3 as header and data from row 4 onward.
    """
    agcm = await _manager.authorize()
    ss   = await agcm.open(OPS_SPREADSHEET_NAME)
    ws   = await ss.worksheet(OPS_WORKSHEET_NAME)

    # Grab all rows, skip the first two banner rows
    all_vals = await ws.get_all_values()
    if len(all_vals) < 4:
        return {"status": "N/A", "driver": "N/A"}

    headers = [h.strip() for h in all_vals[2]]  # row 3 is the real header
    data_rows = all_vals[3:]                   # from row 4 down

    for row in data_rows:
        record = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        if str(record.get("TRUCK NUMBER")).strip() == str(unit).strip():
            return {
                "status": record.get("CURRENT STATUS", "N/A") or "N/A",
                "driver": record.get("DRIVER NAME", "N/A") or "N/A"
            }

    return {"status": "N/A", "driver": "N/A"}

class GoogleOpsService:
    async def get_summary(self) -> Dict[str, Any]:
        data  = await _read_all_sections()
        stats = data["stats"]

        road_lines = []
        for r in data["broken_road"]:
            t   = r.get("Trucks") or r.get("TRUCKS") or ""
            drv = r.get("Previous Driver") or r.get("PREVIOUS DRIVER") or ""
            if t:
                road_lines.append(f"{t} - _{drv}_")

        def g(k: str) -> str:
            return stats.get(k, "0")

        return {
            "date":          _today(),
            "total":         g("TOTAL"),
            "active":        g("ACTIVE"),
            "home_time":     g("HOME TIME"),
            "broken":        g("BROKEN TRUCK"),
            "getting_ready": g("GETTING READY"),
            "accident":      g("ACCIDENT"),
            "lost":          g("TOTAL LOST"),
            "tow_list":      data["side_tow"],
            "owner_list":    data["side_owner"],
            "broken_road":   road_lines,
        }

    async def as_markdown(self) -> str:
        d = await self.get_summary()
        tow_lines   = "\n".join(d["tow_list"])   or "None"
        owner_lines = "\n".join(d["owner_list"]) or "None"
        road_lines  = "\n".join(d["broken_road"]) or "None"

        return (
            f"======= **DELTA TRUCKS** =======\n"
            f"**TOTAL** : {d['total']}\n"
            f"**HOME TIME** : {d['home_time']}\n"
            f"**BROKEN TRUCK** : {d['broken']}\n"
            f"**GETTING READY** : {d['getting_ready']}\n"
            f"**ACCIDENT** : {d['accident']}\n"
            f"**TOTAL LOST** : {d['lost']}\n"
            f"**ACTIVE** : {d['active']}\n"
            f"=========================\n"
            f"**TOW TRUCKS** : {len(d['tow_list'])}\n"
            f"{tow_lines}\n\n"
            f"**OWNER OPERATOR** : {len(d['owner_list'])}\n"
            f"{owner_lines}\n"
            f"=========================\n"
            f"**BROKEN ON THE ROAD ({len(d['broken_road'])})**:\n"
            f"{road_lines}\n"
            f"=========================\n"
            f"**DATE** : {d['date']}"
        )

# Singleton export
google_ops_service = GoogleOpsService()
