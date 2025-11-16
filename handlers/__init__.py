"""
handlers/__init__.py
Centralized router registration for all bot handlers (CLEAN VERSION)
"""

from aiogram import Router

# Core handlers
from handlers.start import router as start_router
from handlers.admin import router as admin_router
from handlers.admin_tools import router as admin_tools_router

# PM Trucker & Services
from handlers.pm_services import router as pm_services_router
from handlers.pm_trucker import router as pm_trucker_router

# Document Handler
from handlers.documents import router as documents_router

# Trailer Handler
from handlers.trailer import router as trailer_router

# NEW Safe Auto-Link System (unit/driver/phone detection)
from handlers.auto_link_groups import router as auto_link_router


# Optional search router
try:
    from handlers.search import router as search_router
    HAS_SEARCH = True
except Exception:
    search_router = None
    HAS_SEARCH = False


# No startup tasks needed anymore — everything auto-detects in auto_link_groups.py
STARTUP_TASKS = []


# Router registration order matters:
# 1) Admin / core
# 2) Auto-linking (group detection)
# 3) PM features
# 4) Documents / Trailer
routers = [
    start_router,
    admin_router,
    admin_tools_router,
    auto_link_router,
    pm_services_router,
    pm_trucker_router,
    documents_router,
    trailer_router,
]

# Optional search
if HAS_SEARCH and search_router:
    routers.append(search_router)

__all__ = ["routers", "STARTUP_TASKS"]
