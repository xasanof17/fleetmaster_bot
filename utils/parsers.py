# utils/parsers.py

import re
import emoji

# ─────────────────────────────────────────────
# REGEX DEFINITIONS (FINAL VERSION)
# ─────────────────────────────────────────────

# Truck unit ALWAYS 3–5 digits, usually at start
UNIT_RE = re.compile(r"\b(\d{3,5})\b")

# Ultra-aggressive phone matcher (7–20 digits with symbols)
PHONE_RE = re.compile(
    r"(\+?\d[\d\-\.\s\(\)]{5,30}\d)"
)

# Driver name detector:
# Supports Mr/Ms/Mrs/Driver but DOES NOT REQUIRE THEM.
# Supports 1–4 name parts, African/Indian/English.
DRIVER_RE = re.compile(
    r"(?:Mr|Ms|Mrs|Driver)?\s*"
    r"([A-Za-z][A-Za-z\-]{1,20}"
    r"(?:\s+[A-Za-z][A-Za-z\-]{0,20}){0,3})"
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _strip_emoji(text: str) -> str:
    return emoji.replace_emoji(text or "", "")


def _normalize(text: str) -> str:
    """Remove emojis + replace symbols with spaces + collapse spaces."""
    if not text:
        return ""

    t = _strip_emoji(text)

    t = re.sub(r"[\#\-\_\|\.,\/]+", " ", t)
    t = re.sub(r"\s+", " ", t)

    return t.strip()


def _format_us_phone(raw: str | None) -> str | None:
    """Extract last 10 digits and return (XXX) XXX-XXXX."""
    if not raw:
        return None

    digits = re.sub(r"\D", "", raw)
    if len(digits) < 10:
        return None

    digits = digits[-10:]

    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:]}"


# ─────────────────────────────────────────────
# PARSER ENGINE
# ─────────────────────────────────────────────

def parse_title(title: str) -> dict:
    """
    Extract:
        • unit (digits)
        • driver (1–4 name parts)
        • phone (ANY format → formatted)
    """

    original = title or ""

    # Step 1: Clean title (remove emojis, normalize separators)
    cleaned = _normalize(original)

    # ─────────────────────────────────────────────
    # EXTRACT UNIT
    # ─────────────────────────────────────────────
    m_unit = UNIT_RE.search(cleaned)
    unit = m_unit.group(1) if m_unit else None

    # ─────────────────────────────────────────────
    # EXTRACT PHONE
    # ─────────────────────────────────────────────
    m_phone = PHONE_RE.search(original)
    phone_raw = m_phone.group(1) if m_phone else None
    phone = _format_us_phone(phone_raw)

    # ─────────────────────────────────────────────
    # PREP TEXT FOR NAME EXTRACTION
    # ─────────────────────────────────────────────
    tmp = cleaned

    if unit:
        tmp = tmp.replace(unit, " ")

    if phone_raw:
        tmp = tmp.replace(phone_raw, " ")

    tmp = _normalize(tmp)

    # ─────────────────────────────────────────────
    # EXTRACT DRIVER NAME (Most flexible version)
    # ─────────────────────────────────────────────
    driver = None
    m_driver = DRIVER_RE.search(tmp)
    if m_driver:
        driver = m_driver.group(1).strip()

    # Fix stupid cases like just "Mr"
    if driver and len(driver) < 2:
        driver = None

    return {
        "unit": unit,
        "driver": driver,
        "phone": phone,
        "raw_title": original,
        "clean_title": cleaned,
        "name_source": tmp,  # for debugging
    }
