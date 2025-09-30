import datetime
import re

def format_pm_vehicle_info(data, title=None, full=False):
    """
    Format PM Trucker info for Telegram messages.
    If full=True, formats a single vehicle’s full details.
    """
    if full:
        return _format_vehicle_detail(data)
    else:
        return _format_vehicle_list(data, title)


# ==============================
# LIST MODE  (urgent/oil change lists)
# ==============================
def _format_vehicle_list(vehicles, title):
    """
    vehicles: list of dicts with keys truck, left, updated
    """
    if not vehicles:
        return f"**UPDATED:** {datetime.date.today():%m/%d/%Y}\n_No data found._"

    updated = vehicles[0].get("updated") or f"{datetime.date.today():%m/%d/%Y}"
    lines = [f"**UPDATED:** {updated}", "=" * 22]

    for v in vehicles:
        # icon depends on title
        if "Urgent" in (title or ""):
            status_icon = "🔴 Urgent Oil Change"
        else:
            status_icon = "🟡 Oil Change"

        truck = v.get("truck", "")
        left  = v.get("left", "")
        # **truck** bold, *left* italic
        lines.append(f"**{truck}** – {status_icon}  *{left}*")

    lines.append("=" * 20)
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
    status_val = (d.get("status") or "").upper()
    updated = d.get("updated", f"{datetime.date.today():%m/%d/%Y}")

    # Status indicator
    if "urgent" in status_val.lower():
        status_icon = f"*{left_val:,}* // 🔴 Urgent"
    elif "oil" in status_val.lower():
        status_icon = f"*{left_val:,}* // 🟡 Oil"
    elif "good" in status_val.lower():
        status_icon = f"*{left_val:,}* // 🟢 Good"
    else:
        status_icon = f"*{left_val:,}* // ❌ Broken"

    # PM shop display
    shop = (d.get("last_history") or "")
    shop_display = (
        "at the SPARTAK" if "SPARTAK" in shop.upper() else
        "at the SPEEDCO / LOVES TRUCK CARE)" if any(x in shop.upper() for x in ["SPEEDCO", "LOVES"]) else
        "at the LOCAL SHOP)" if "LOCAL" in shop.upper() else
        "BROKEN" if "BROKEN" in shop.upper() else
        ""
    )

    # Current Issues block with *italic* bullets
    notes = (d.get("notes") or "").strip()
    issues_block = ""
    if notes:
        normalized = re.sub(r"[;,/|#]", "\n", notes)
        parts = [p.strip().title() for p in normalized.splitlines() if p.strip()]
        if parts:
            bullets = "\n".join(f"- _{p}_" for p in parts)
            issues_block = f"*CURRENT ISSUES:*\n{bullets}\n"

    return (
        f"*PM SERVICE // FULL SERVICE*\n\n"
        f"*TRUCK:* {d.get('truck')}\n"
        f"*PM DATE:* {d.get('pm_date')}\n"
        f"*DAYS:* {days_val} ago\n"
        f"*STATUS:* {status_icon}\n"
        f"*PM SHOP:* {shop_display}\n"
        f"{issues_block}"
        f"=========================\n"
        f"*UPDATED:* {updated}"
    )
