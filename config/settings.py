"""
Configuration settings for FleetMaster Bot
"""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings"""

    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    SAMSARA_API_TOKEN: str = os.getenv("SAMSARA_API_TOKEN", "")
    SAMSARA_BASE_URL: str = os.getenv("SAMSARA_BASE_URL", "https://api.samsara.com")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "true").lower() == "true"

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
