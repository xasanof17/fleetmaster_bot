import datetime
import re

def format_pm_vehicle_info(data, title=None, full=False):
    """
    Format PM Trucker info for Telegram messages.
    
    Parameters
    ----------
    data : list | dict
        - For list view: list of {truck,left,updated}
        - For full view: dict with detailed info
    title : str
        Title for list mode, e.g. "Urgent Oil Change"
    full : bool
        If True, format a single vehicle's full details
    """
    if full:
        return _format_vehicle_detail(data)
    else:
        return _format_vehicle_list(data, title)

# ==============================
# LIST MODE
# ==============================
def _format_vehicle_list(vehicles, title):
    """
    vehicles: list of dicts with keys
        truck, left, updated
    """
    if not vehicles:
        return f"UPDATED: {datetime.date.today():%m/%d/%Y}\nNo data found."
    updated = vehicles[0].get("updated") or f"{datetime.date.today():%m/%d/%Y}"
    lines = [f"UPDATED: {updated}", "=" * 27]
    for v in vehicles:
        # If title contains 'Urgent', use 🔴, else 🟡
        if "Urgent" in (title or ""):
            status_icon = "Urgent oil change📌"
        else:
            status_icon = "🟡Oil change📌"
        left = v.get("left", "")
        lines.append(f"{v.get('truck')} - {status_icon}  {left}")
    lines.append("=" * 27)
    return "\n".join(lines)

# ==============================
# FULL VEHICLE DETAILS
# ==============================
def _format_vehicle_detail(d):
    """
    d: dict with keys
        truck, pm_date, days, left, status, notes, last_history
    """
    days_val = d.get("days", "")
    left_val = d.get("left", "")
    status_val = d.get("status", "").upper()
    updated = d.get("updated", f"{datetime.date.today():%m/%d/%Y}")

    # Status indicator
    status_icon = ""
    if "urgent" in status_val.lower():
        status_icon = f"{left_val:,} // Urgent🔴"
    elif "oil" in status_val.lower():
        status_icon = f"{left_val:,} // Oil🟡"
    elif "good" in status_val.lower():
        status_icon = f"{left_val:,} // GOOD🟢"
    else:
        status_icon = f"{left_val:,} // BROKEN❌"

    # Last history shop extraction
    shop = d.get("last_history", "")
    # PM Shop statuses
    shop_display = (
        f"(at the Spartak)" if "SPARTAK" in shop.upper() else
        f"(at the speedco / loves truck care)" if "SPEEDCO" in shop.upper() or "LOVES" in shop.upper() else
        f"(at the local shop)" if "LOCAL" in shop.upper() else
        f"(BROKEN)" if "BROKEN" in shop.upper() else
        ""
    )

     # --- Current Issues ---
    notes = (d.get("notes") or "").strip()
    issues_block = ""
    if notes:
        # split on commas, slashes, semicolons, or pipes
        normalized = re.sub(r"[;,/|#]", "\n", notes)
        # Title-case every word in every item
        parts = [p.strip().title() for p in normalized.splitlines() if p.strip()]
        if parts:
            bullets = "\n".join(f"- {p}" for p in parts)
            issues_block = f"Current Issues:\n{bullets}\n"

    return (
        f"PM Service // Full Service\n\n"
        f"Truck: {d.get('truck')}\n"
        f"PM Date: {d.get('pm_date')}\n"
        f"Days: {days_val} ago\n"
        f"Status: {status_icon}\n"
        f"PM Shop: {shop_display}\n"
        f"{issues_block}"
        f"UPDATED: {updated}"
    )