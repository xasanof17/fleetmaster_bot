"""
Configuration settings for FleetMaster Bot
"""
import os
import re
import json
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()


def parse_bool(value: str, default: bool = False) -> bool:
    """Convert env string to bool"""
    if not value:
        return default
    return str(value).lower() in ("true", "1", "yes", "y")


def parse_json(value: str, default: Any = None):
    """Safely parse JSON or return default"""
    try:
        return json.loads(value)
    except Exception:
        return default


class Settings:
    """Application-wide configuration"""

    # ── Core tokens ────────────────────────────
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    SAMSARA_API_TOKEN: str = os.getenv("SAMSARA_API_TOKEN", "")
    SAMSARA_BASE_URL: str = os.getenv("SAMSARA_BASE_URL", "https://api.samsara.com")

    # ── Logging ────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_TO_FILE: bool = parse_bool(os.getenv("LOG_TO_FILE", "true"))

    # ── Telegram Admins ────────────────────────
    # Supports ADMIN or ADMINS variable
    raw_admins = os.getenv("ADMINS") or os.getenv("ADMIN", "")
    raw_admins = raw_admins.strip("[]\"' {}")
    ADMINS: List[int] = [int(x) for x in re.findall(r"\d+", raw_admins)] if raw_admins else []

    # ── Optional Flags ─────────────────────────
    ALLOW_GROUPS: bool = parse_bool(os.getenv("ALLOW_GROUPS", "false"))

    # ── Webhook / Bot Config ───────────────────
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    PORT: int = int(os.getenv("PORT", "8080"))
    BOT_PASSWORD: str = os.getenv("BOT_PASSWORD", "mypassword")

    # ── Google Sheets Config ───────────────────
    GOOGLE_CREDS_JSON: str = os.getenv("GOOGLE_CREDS_JSON", "{}")
    OPS_SPREADSHEET_NAME: str = os.getenv("OPS_SPREADSHEET_NAME", "OPERATION DEPARTMENT")
    OPS_WORKSHEET_NAME: str = os.getenv("OPS_WORKSHEET_NAME", "OPERATIONS")
    PM_SPREADSHEET_NAME: str = os.getenv("PM_SPREADSHEET_NAME", "PM TRUCKER")
    PM_WORKSHEET_NAME: str = os.getenv("PM_WORKSHEET_NAME", "PM_TRACKER")

    # ── Truck → Group mapping ──────────────────
    TRUCK_GROUP_MAP: Dict[str, int] = parse_json(os.getenv("TRUCK_GROUP_MAP", "{}")) or {}

    # ── Telegram Channels / Groups ─────────────
    try:
        CHANNEL_ID: int = int(os.getenv("CHANNEL_ID", "0"))
        GROUP_ID: int = int(os.getenv("GROUP_ID", "0"))
    except ValueError:
        CHANNEL_ID = 0
        GROUP_ID = 0

    # ── Database Config ────────────────────────
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # ── Misc Files Base ────────────────────────
    FILES_BASE: str = os.getenv("FILES_BASE", "files")

    # ── Validation ─────────────────────────────
    @classmethod
    def validate(cls) -> bool:
        """Ensure required environment variables are set"""
        missing = []
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not cls.SAMSARA_API_TOKEN:
            missing.append("SAMSARA_API_TOKEN")

        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")
        return True


# ── Instantiate for global import ─────────────
settings = Settings()
