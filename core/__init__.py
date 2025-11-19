"""
Core package for FleetMaster Bot
"""

from .bot import create_bot, create_dispatcher, on_shutdown, on_startup, setup_bot_commands

__all__ = ["create_bot", "create_dispatcher", "setup_bot_commands", "on_startup", "on_shutdown"]
