"""
utils/pm_formatter.py
Formatter for PM vehicle information display
RESTORED: Original template with improvements
"""
import datetime
import re
from typing import Dict, Any, List, Optional


def format_pm_vehicle_info(data, title: Optional[str] = None, full: bool = False) -> str:
    """
    Format PM Trucker info for Telegram messages.
    
    Args:
        data: Either a single vehicle dict or list of vehicles
        title: Optional title for list mode (e.g., "Urgent Oil Change")
        full: If True, formats a single vehicle's full details
    
    Returns:
        Formatted markdown string
    """
    if full:
        return _format_vehicle_detail(data)
    else:
        return _format_vehicle_list(data, title)


# ==============================
# LIST MODE (urgent/oil change lists)
# ==============================
def _format_vehicle_list(vehicles: List[Dict[str, Any]], title: Optional[str]) -> str:
    """
    Format list of vehicles for PM lists
    
    Args:
        vehicles: list of dicts with keys truck, left, updated
        title: Title like "Urgent Oil Change" or "Oil Change"
    """
    if not vehicles:
        return f"**UPDATED:** {datetime.date.today():%m/%d/%Y}\n_No data found._"
    
    updated = vehicles[0].get("updated") or f"{datetime.date.today():%m/%d/%Y}"
    lines = [f"**UPDATED:** {updated}", "=" * 22]
    
    for v in vehicles:
        # Icon depends on title
        if title and "Urgent" in title:
            status_icon = "🔴 Urgent Oil Change"
        else:
            status_icon = "🟡 Oil Change"
        
        truck = v.get("truck", "")
        left = v.get("left", "")
        # **truck** bold, *left* italic
        lines.append(f"**{truck}** – {status_icon}  *{left}*")
    
    lines.append("=" * 20)
    return "\n".join(lines)


# ==============================
# FULL VEHICLE DETAILS
# ==============================
def _format_vehicle_detail(d: Dict[str, Any]) -> str:
    """
    Format full details for a single vehicle
    
    Args:
        d: dict with keys: truck, pm_date, days, left, status, notes, last_history
    """
    days_val = d.get("days", "")
    left_val = d.get("left", "")
    status_val = (d.get("status") or "").upper()
    updated = d.get("updated", f"{datetime.date.today():%m/%d/%Y}")
    
    # Status indicator with color emoji
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
        "at the SPEEDCO / LOVES TRUCK CARE" if any(x in shop.upper() for x in ["SPEEDCO", "LOVES"]) else
        "at the LOCAL SHOP" if "LOCAL" in shop.upper() else
        "BROKEN" if "BROKEN" in shop.upper() else
        shop if shop else "N/A"
    )
    
    # Current Issues block with *italic* bullets
    notes = (d.get("notes") or "").strip()
    issues_block = ""
    if notes and notes.upper() not in ["N/A", "NA", "NONE", "-"]:
        normalized = re.sub(r"[;,/|#]", "\n", notes)
        parts = [p.strip().title() for p in normalized.splitlines() if p.strip()]
        if parts:
            bullets = "\n".join(f"- _{p}_" for p in parts)
            issues_block = f"\n*CURRENT ISSUES:*\n{bullets}\n"
    
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


# ==============================
# ADDITIONAL HELPER (for lists with title)
# ==============================
def format_pm_list(vehicles: List[Dict[str, Any]], title: str = "PM List") -> str:
    """
    Format a list of PM vehicles with title
    
    Args:
        vehicles: List of PM vehicle dictionaries
        title: Title for the list
    
    Returns:
        Formatted markdown string
    """
    if not vehicles:
        return f"📋 **{title}**\n\n✅ No vehicles in this list"
    
    lines = [f"📋 **{title}**", "=" * 30, ""]
    
    for v in vehicles:
        truck = v.get("truck", "N/A")
        left = v.get("left", 0)
        days = v.get("days", 0)
        status = v.get("status", "N/A")
        
        emoji = "🔴" if "urgent" in str(status).lower() else "🟡"
        lines.append(f"/{truck} {emoji} — {left:,} mi | {days} days")
    
    lines.append("")
    lines.append("=" * 30)
    lines.append(f"**Total:** {len(vehicles)} vehicles")
    
    return "\n".join(lines)