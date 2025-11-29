# handlers/admin/__init__.py

from .panel import router as admin_panel_router
from .callbacks import router as admin_callbacks_router
from .actions import router as admin_actions_router

__all__ = [
    "admin_panel_router",
    "admin_callbacks_router",
    "admin_actions_router",
]
