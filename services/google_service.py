import os, datetime, json
from gspread_asyncio import AsyncioGspreadClientManager
from google.oauth2.service_account import Credentials

GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")
SPREADSHEET_NAME  = os.getenv("PM_SPREADSHEET_NAME")
WORKSHEET_NAME    = os.getenv("PM_WORKSHEET_NAME", "Sheet1")
PAGE_SIZE         = 5


# ---- auth ----
def get_creds():
    creds_dict = json.loads(GOOGLE_CREDS_JSON)
    return Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

_manager = AsyncioGspreadClientManager(get_creds)


async def _get_all_rows():
    agcm = await _manager.authorize()
    ss   = await agcm.open(SPREADSHEET_NAME)
    ws   = await ss.worksheet(WORKSHEET_NAME)
    return await ws.get_all_records()


def _format_date() -> str:
    return datetime.datetime.now().strftime("%m/%d/%Y")


def _safe_int(value, default=0):
    """
    Convert to int safely: blanks, '#VALUE!' etc return default.
    """
    try:
        return int(float(str(value).replace(",", "").strip()))
    except Exception:
        return default


class GooglePMService:
    """
    All PM logic is sheet-driven:
      • urgent = Left <= 5000 miles OR Days <= 30  (and STATUS not BROKEN)
      • oil    = Left <= 10000 miles (and STATUS not BROKEN)
    """

    def _row_to_vehicle(self, r):
        return {
            "truck":  str(r.get("Truck Number")),
            "status": str(r.get("STATUS", "")).strip(),
            "left":   _safe_int(r.get("Left")),
        }

    async def get_urgent_list(self, mile_limit: int = 5000, day_limit: int = 30):
        rows = await _get_all_rows()
        urgent = []
        for r in rows:
            status = str(r.get("STATUS", "")).strip().upper()
            if status == "BROKEN":
                continue
            left = _safe_int(r.get("Left"))
            days = _safe_int(r.get("Days"))
            if left <= mile_limit or days <= day_limit:
                urgent.append({
                    "truck":  str(r.get("Truck Number")),
                    "left":   left,
                    "days":   days,
                    "status": status,
                    "updated": _format_date()
                })
        return urgent

    async def get_oil_list(self, mile_limit: int = 10000):
        rows = await _get_all_rows()
        oil_due = []
        for r in rows:
            status = str(r.get("STATUS", "")).strip().upper()
            if status == "BROKEN":
                continue
            left = _safe_int(r.get("Left"))
            if left <= mile_limit:
                oil_due.append({
                    "truck":  str(r.get("Truck Number")),
                    "left":   left,
                    "status": status,
                    "updated": _format_date()
                })
        return oil_due

    async def get_all(self, page: int = 1):
        """
        Full list (no filtering) with pagination.
        """
        rows = await _get_all_rows()
        start, end = (page - 1) * PAGE_SIZE, page * PAGE_SIZE
        sliced = rows[start:end]
        has_next = len(rows) > end
        return [self._row_to_vehicle(r) for r in sliced], has_next

    async def get_vehicle_details(self, truck: str):
        """
        Return *all* fields for a specific truck number,
        even if status is BROKEN or anything else.
        """
        rows = await _get_all_rows()
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
                    "updated":        _format_date(),
                }
        return None


# export singleton
google_pm_service = GooglePMService()
