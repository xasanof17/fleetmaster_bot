"""
handlers/__init__.py
Centralized router registration for all bot handlers (CLEAN + MODULAR ADMIN)
"""

from aiogram import Router

# ================================
# ADMIN PACKAGE (CORE)
# ================================
from handlers.admin import (
    admin_panel_router,
    admin_callbacks_router,
    admin_actions_router,
)

# Extra admin modules
from handlers.admin_users import router as admin_users_router
from handlers.admin_tools import router as admin_tools_router
from handlers.admin_refresh import router as admin_refresh_router


# ================================
# OTHER MODULES
# ================================
from handlers.start import router as start_router
from handlers.auto_link_groups import router as auto_link_router
from handlers.pm_services import router as pm_services_router
from handlers.pm_trucker import router as pm_trucker_router
from handlers.documents import router as documents_router
from handlers.trailer import router as trailer_router

# Optional search
try:
    from handlers.search import router as search_router
    HAS_SEARCH = True
except Exception:
    search_router = None
    HAS_SEARCH = False


# ================================
# ROUTER ORDER (IMPORTANT)
# ================================
routers: list[Router] = []

# 1) Start must be first
routers.append(start_router)

# 2) Full ADMIN SYSTEM (core)
routers.extend([
    admin_panel_router,
    admin_callbacks_router,
    admin_actions_router,
])

# 3) Admin secondary modules
routers.extend([
    admin_users_router,
    admin_tools_router,
    admin_refresh_router,
])

# 4) Auto-link must be BEFORE PM handlers
routers.append(auto_link_router)

# 5) Main functional handlers
routers.extend([
    pm_services_router,
    pm_trucker_router,
    documents_router,
    trailer_router,
])

# 6) Optional search
if HAS_SEARCH and search_router:
    routers.append(search_router)


# No startup tasks for now
STARTUP_TASKS: list = []

__all__ = ["routers", "STARTUP_TASKS"]
