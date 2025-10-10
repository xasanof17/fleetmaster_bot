import logging
import os
from config.settings import settings
from colorlog import ColoredFormatter


def setup_logging():
    """Set up global logging with color in console and file output."""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "fleetmaster.log")

    # ───────────────────────────────
    # 🎨 Define color format for console
    # ───────────────────────────────
    color_formatter = ColoredFormatter(
        fmt="%(log_color)s%(asctime)s [%(levelname)s] %(name)s:%(reset)s %(message_log_color)s%(message)s",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
        secondary_log_colors={
            "message": {
                "ERROR": "red",
                "CRITICAL": "bold_red",
                "WARNING": "yellow",
                "INFO": "white",
                "DEBUG": "cyan",
            }
        },
        style="%",
    )

    # ───────────────────────────────
    # 🧱 Base config
    # ───────────────────────────────
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)

    # Console handler (colored)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(color_formatter)
    root_logger.addHandler(console_handler)

    # File handler (plain text)
    if getattr(settings, "LOG_TO_FILE", True):
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root_logger.addHandler(file_handler)

    # Final confirmation
    root_logger.info("🌿 Logging initialized with color + file output")


def get_logger(name: str):
    """Return a namespaced logger."""
    return logging.getLogger(name)
