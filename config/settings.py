"""
Configuration settings for FleetMaster Bot
"""

import json
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def _json(v: str | None, default):
    if not v:
        return default
    try:
        return json.loads(v)
    except Exception:
        return default


class Settings:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    SAMSARA_API_TOKEN: str = os.getenv("SAMSARA_API_TOKEN", "")
    SAMSARA_BASE_URL: str = os.getenv("SAMSARA_BASE_URL", "https://api.samsara.com")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_TO_FILE: bool = _bool(os.getenv("LOG_TO_FILE", "true"), True)

    # Accept ADMINS=1553271433,1291874110  (no brackets)
    _admins_raw = os.getenv("ADMINS") or os.getenv("ADMIN", "")
    ADMINS: list[int] = [int(x) for x in re.findall(r"\d+", _admins_raw)]

    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    ALLOW_GROUPS: bool = _bool(os.getenv("ALLOW_GROUPS", "false"))
    BOT_PASSWORD: str = os.getenv("BOT_PASSWORD", "")

    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    PORT: int = int(os.getenv("PORT", "8080"))

    # Google Sheets creds
    GOOGLE_CREDS_JSON: dict[str, Any] = _json(os.getenv("GOOGLE_CREDS_JSON", ""), {}) or {}

    OPS_SPREADSHEET_NAME: str = os.getenv("OPS_SPREADSHEET_NAME", "OPERATION DEPARTMENT")
    OPS_WORKSHEET_NAME: str = os.getenv("OPS_WORKSHEET_NAME", "OPERATIONS")
    PM_SPREADSHEET_NAME: str = os.getenv("PM_SPREADSHEET_NAME", "PM TRUCKER")
    PM_WORKSHEET_NAME: str = os.getenv("PM_WORKSHEET_NAME", "PM_TRACKER")
    PM_TRAILERS_NAME: str = os.getenv("PM_TRAILERS_NAME", "TRAILER OWNERS")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Backward compatible key
    FILES_BASE: str = os.getenv("FILES_BASE", os.getenv("FILEBASE", "files"))

    AUTO_CLEAN_GROUPS: bool = _bool(os.getenv("AUTO_CLEAN_GROUPS", "false"), False)

    try:
        CHANNEL_ID: int = int(os.getenv("CHANNEL_ID", "0"))
    except ValueError:
        CHANNEL_ID = 0

    @classmethod
    def validate(cls) -> bool:
        missing = []
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not cls.SAMSARA_API_TOKEN:
            missing.append("SAMSARA_API_TOKEN")
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")
        return True


settings = Settings()
