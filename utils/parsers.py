# utils/parsers.py

import re

import emoji

# ─────────────────────────────────────────────
# REGEX DEFINITIONS (FINAL V4 ENGINE)
# ─────────────────────────────────────────────

# Truck unit ALWAYS 3–5 digits, often first but not required
UNIT_RE = re.compile(r"\b(\d{3,5})\b")

# Ultra-flexible phone detection:
# Accepts ANY mix that contains 7–20 digits total.
PHONE_RE = re.compile(r"(\+?\d[\d\s\-\.\(\)]{5,40}\d)")

# Driver name:
# Supports African / Indian / English multi-part names
# Allows hyphens, prefixes, 1–4 words
DRIVER_RE = re.compile(
    r"(?:Mr|Ms|Mrs|Driver)?\s*"
    r"([A-Za-z][A-Za-z\-]{1,20}"
    r"(?:\s+[A-Za-z][A-Za-z\-]{1,20}){0,3})"
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────


def _strip_emoji(text: str) -> str:
    """Remove emojis but keep text intact."""
    return emoji.replace_emoji(text or "", "")


def _normalize(text: str) -> str:
    """Normalize symbols to spaces + collapse whitespace."""
    if not text:
        return ""

    t = _strip_emoji(text)

    # Replace separators (# - _ | . , / etc)
    t = re.sub(r"[\#\-\_\|\.,\/\(\)]+", " ", t)

    # Collapse multiple spaces
    t = re.sub(r"\s+", " ", t)

    return t.strip()


def _format_us_phone(raw: str | None) -> str | None:
    """Normalize ANY phone format into (XXX) XXX-XXXX."""
    if not raw:
        return None

    # keep digits only
    digits = re.sub(r"\D", "", raw)

    # require at least 10 digits
    if len(digits) < 10:
        return None

    # last 10 digits = US number
    digits = digits[-10:]

    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


# ─────────────────────────────────────────────
# CORE PARSER
# ─────────────────────────────────────────────


def parse_title(title: str) -> dict:
    """
    Extract:
        ✔ unit (3–5 digits)
        ✔ driver (1–4 word name)
        ✔ phone (ANY style → normalized)
    """

    original = title or ""

    # Clean version without emojis + normalized spacing
    cleaned = _normalize(original)

    # ─────────────────────────────────────────────
    # 1) Extract Unit
    # ─────────────────────────────────────────────
    m_unit = UNIT_RE.search(cleaned)
    unit = m_unit.group(1) if m_unit else None

    # ─────────────────────────────────────────────
    # 2) Extract Phone ANYWHERE
    # ─────────────────────────────────────────────
    m_phone = PHONE_RE.search(original)
    phone_raw = m_phone.group(1) if m_phone else None
    phone = _format_us_phone(phone_raw)

    # ─────────────────────────────────────────────
    # 3) Prepare temp text for name extraction
    #    (remove the phone + unit first)
    # ─────────────────────────────────────────────
    tmp = cleaned

    if unit:
        tmp = tmp.replace(unit, " ")

    if phone_raw:
        tmp = tmp.replace(phone_raw, " ")

    tmp = _normalize(tmp)

    # ─────────────────────────────────────────────
    # 4) Extract driver name
    # ─────────────────────────────────────────────
    driver = None
    m_driver = DRIVER_RE.search(tmp)
    if m_driver:
        driver = m_driver.group(1).strip()

    # Remove false positives like “Mr” or 1-letter
    if driver and len(driver) < 2:
        driver = None

    # ─────────────────────────────────────────────
    # RETURN
    # ─────────────────────────────────────────────
    return {
        "unit": unit,
        "driver": driver,
        "phone": phone,
        "raw_title": original,
        "clean_title": cleaned,
        "name_source": tmp,  # Useful for debugging name detection
    }
