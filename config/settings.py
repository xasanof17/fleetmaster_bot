"""
Configuration settings for FleetMaster Bot
"""
import os
import re
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Application settings"""

    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    SAMSARA_API_TOKEN: str = os.getenv("SAMSARA_API_TOKEN", "")
    SAMSARA_BASE_URL: str = os.getenv("SAMSARA_BASE_URL", "https://api.samsara.com")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "true").lower() == "true",
    # Parse admins safely (accepts "123", "123,456", or "[123,456]")
    # Read admins robustly
    raw_admins = os.getenv("ADMIN", "")
    # remove [] and quotes
    raw_admins = raw_admins.strip("[]\"' ")
    # extract only digits (ignore weird characters)
    ADMIN: List[int] = [int(x) for x in re.findall(r"\d+", raw_admins)],
    CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

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
