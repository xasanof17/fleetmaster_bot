# utils/parsers.py
import re

# ─────────────────────────────────────────────
# REGEX DEFINITIONS (FINAL V4.4 — STABLE+)
# ─────────────────────────────────────────────

LEADING_UNIT_RE = re.compile(r"^\s*(\d{3,5})(?=\s|[-|:/])")
UNIT_RE = re.compile(r"\b(\d{3,5})\b")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-\.\(\)]{5,40}\d)")

DRIVER_RE = re.compile(
    r"([A-Za-z][A-Za-z\-\.]{1,25}"
    r"(?:\s+[A-Za-z][A-Za-z\-\.]{1,25}){0,4})"
)

_NOISE_WORDS_RE = re.compile(
    r"\b(TOW\s*TRUCK|TOWTRUCK|TRUCK|GROUP|UNIT|DISPATCH|TEAM)\b",
    flags=re.IGNORECASE,
)

_PREFIX_RE = re.compile(r"\b(MR|MRS|MS|DRIVER)\b\.?", flags=re.IGNORECASE)

_BLOCKED_DRIVER_WORDS = {
    "FIRED",
    "HOME",
    "HOMETIME",
    "TERMINATED",
    "REMOVED",
    "ACTIVE",
    "ON",
    "DUTY",
    "UNKNOWN",
}

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _strip_emoji(text: str) -> str:
    return re.sub(
        r"[\U0001F600-\U0001F64F"
        r"\U0001F300-\U0001F5FF"
        r"\U0001F680-\U0001F6FF"
        r"\U0001F1E0-\U0001F1FF"
        r"\u2600-\u26FF\u2700-\u27BF]+",
        "",
        text or "",
    )


def _normalize(text: str) -> str:
    if not text:
        return ""
    t = _strip_emoji(text).upper()
    t = re.sub(r"[#\-\_\|\.,\/\(\)]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.replace(" ", "")


def _format_us_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 10:
        return None
    digits = digits[-10:]
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def _safe_strip_phone_from_text(tmp: str, phone_raw: str | None) -> str:
    if not phone_raw:
        return tmp
    tmp = tmp.replace(phone_raw, " ")
    digits = re.sub(r"\D", "", phone_raw)
    if digits:
        tmp = tmp.replace(digits, " ")
    return tmp


def _extract_driver_from_tmp(tmp: str) -> str | None:
    if not tmp:
        return None

    # remove noise + prefixes
    tmp = _NOISE_WORDS_RE.sub(" ", tmp)
    tmp = _PREFIX_RE.sub(" ", tmp)

    # 🚫 REMOVE STATUS WORDS FIRST (CRITICAL FIX)
    for w in _BLOCKED_DRIVER_WORDS:
        tmp = re.sub(rf"\b{w}\b", " ", tmp, flags=re.IGNORECASE)

    tmp = re.sub(r"\s+", " ", tmp).strip()

    m = DRIVER_RE.search(tmp)
    if not m:
        return None

    candidate = m.group(1).strip()

    # final sanity
    if len(candidate) < 2:
        return None

    return candidate


# ─────────────────────────────────────────────
# CORE PARSER (AUTHORITATIVE)
# ─────────────────────────────────────────────

def parse_title(title: str) -> dict:
    original = title or ""
    readable = _strip_emoji(original)

    unit: str | None = None

    # 1️⃣ strict leading unit
    m = LEADING_UNIT_RE.match(readable)
    if m:
        unit = m.group(1)
    else:
        # 2️⃣ fallback — earliest NON-phone 3–5 digit
        phone_match = PHONE_RE.search(original)
        phone_digits = (
            re.sub(r"\D", "", phone_match.group(1)) if phone_match else ""
        )

        candidates: list[tuple[int, str]] = []
        for m in UNIT_RE.finditer(readable):
            u = m.group(1)
            if u not in phone_digits:
                candidates.append((m.start(), u))

        if candidates:
            unit = sorted(candidates, key=lambda x: x[0])[0][1]

    # final unit safety
    if unit and not unit.isdigit():
        unit = None

    # phone
    phone_match = PHONE_RE.search(original)
    phone_raw = phone_match.group(1) if phone_match else None
    phone = _format_us_phone(phone_raw)

    # driver source text
    tmp = readable
    if unit:
        tmp = re.sub(rf"\b{re.escape(unit)}\b", " ", tmp)

    tmp = _safe_strip_phone_from_text(tmp, phone_raw)
    tmp = re.sub(r"\s+", " ", tmp).strip()

    driver = _extract_driver_from_tmp(tmp)

    return {
        "unit": unit,
        "driver": driver,
        "phone": phone,
        "raw_title": original,
        "clean_title": _normalize(original),
        "name_source": tmp,
    }
