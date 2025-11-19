"""
handlers/__init__.py
Centralized router registration for all bot handlers (CLEAN VERSION)
"""

from aiogram import Router

from handlers.admin import router as admin_router
from handlers.admin_refresh import router as admin_refresh_router
from handlers.admin_tools import router as admin_tools_router

# Safe Auto-Link System (unit/driver/phone detection)
from handlers.auto_link_groups import router as auto_link_router

# Document Handler
from handlers.documents import router as documents_router

# PM Trucker & Services
from handlers.pm_services import router as pm_services_router
from handlers.pm_trucker import router as pm_trucker_router

# Core handlers (admin must be first)
from handlers.start import router as start_router

# Trailer Handler
from handlers.trailer import router as trailer_router

# Optional search router
try:
    from handlers.search import router as search_router

    HAS_SEARCH = True
except Exception:
    search_router = None
    HAS_SEARCH = False


# No startup tasks (auto_link handles everything)
STARTUP_TASKS = []


# IMPORTANT ORDER:
routers = [
    start_router,
    admin_router,
    admin_tools_router,
    admin_refresh_router,  # <— NOW IN CORRECT POSITION
    auto_link_router,  # <— always after admin tools
    pm_services_router,
    pm_trucker_router,
    documents_router,
    trailer_router,
]

# Optional search router
if HAS_SEARCH and search_router:
    routers.append(search_router)

__all__ = ["routers", "STARTUP_TASKS"]
