"""
Logging configuration for FleetMaster Bot
"""
import sys
from pathlib import Path
from loguru import logger
from config import settings


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True,
    )

    if settings.LOG_TO_FILE:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        logger.add(
            "logs/fleetmaster_{time}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=settings.LOG_LEVEL,
            rotation="1 day",
            retention="30 days",
            compression="zip",
        )

    logger.info("Logging configured")


def get_logger(name: str = None):
    # returns a bound logger for consistent name usage
    if name:
        return logger.bind(module=name)
    return logger
