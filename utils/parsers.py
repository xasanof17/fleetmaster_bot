# utils/parsers.py

import re
import emoji

# ─────────────────────────────────────────────
# REGEXES
# ─────────────────────────────────────────────

# Truck unit: 3–5 digits anywhere
UNIT_RE = re.compile(r"\b(\d{3,5})\b")

# US-style phone pattern (we'll normalize to (XXX) XXX-XXXX)
PHONE_RE = re.compile(
    r"(\+?1[\s\-\.]?)?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}"
)

# Driver name: optional Mr/Ms/Driver + 1–4 name parts
DRIVER_RE = re.compile(
    r"(?:Mr|Ms|Mrs|Driver)\s+[A-Za-z]{2,20}(?:\s+[A-Za-z]{2,20}){0,3}"
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def _strip_emojis(text: str) -> str:
    return emoji.replace_emoji(text or "", "")


def _normalize_separators(text: str) -> str:
    # Replace junk separators with spaces
    text = re.sub(r"[#\-\|_/.,]+", " ", text)
    # Collapse spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _format_us_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    # keep only digits
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 10:
        return None
    # last 10 digits as US number
    digits = digits[-10:]
    area = digits[0:3]
    pref = digits[3:6]
    line = digits[6:]
    return f"({area}) {pref}-{line}"


# ─────────────────────────────────────────────
# MAIN PARSER
# ─────────────────────────────────────────────
def parse_title(title: str) -> dict:
    """
    Parse Telegram group title and extract:
      • unit
      • driver
      • phone (formatted as (XXX) XXX-XXXX)
    """

    original = title or ""
    # remove emojis for logic, keep original for reference if needed
    cleaned = _strip_emojis(original)

    # truck unit
    unit = None
    m_unit = UNIT_RE.search(cleaned)
    if m_unit:
        unit = m_unit.group(1)

    # phone
    phone = None
    m_phone = PHONE_RE.search(cleaned)
    phone_raw = m_phone.group(0) if m_phone else None
    phone = _format_us_phone(phone_raw) if phone_raw else None

    # remove unit + phone from text before name detection
    normalized = _normalize_separators(cleaned)
    if unit:
        normalized = normalized.replace(unit, " ")
    if phone_raw:
        normalized = normalized.replace(phone_raw, " ")
    normalized = _normalize_separators(normalized)

    # driver name
    driver = None
    m_driver = DRIVER_RE.search(normalized)
    if m_driver:
        driver = m_driver.group(0).strip()

    return {
        "unit": unit,
        "driver": driver,
        "phone": phone,
        "raw_title": original,
        "normalized": normalized,
    }
