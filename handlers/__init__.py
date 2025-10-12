"""
handlers/__init__.py
Centralized router registration for all bot handlers
"""
from aiogram import Router

# Import all handler routers
from handlers.start import router as start_router
from handlers.pm_services import router as pm_services_router
from handlers.pm_trucker import router as pm_trucker_router
from handlers.admin import router as admin_router
from handlers.admin_dbcheck import router as admin_dbcheck_router
from handlers.auto_link_groups import router as auto_link_router
from handlers.sync_groups import router as sync_groups_router
from handlers.documents import router as documents_router
from handlers.trailer import router as trailer_router
from handlers.admin_tools import router as admin_tools_router

# Optional search router
try:
    from handlers.search import router as search_router
    HAS_SEARCH = True
except Exception:
    HAS_SEARCH = False
    search_router = None

# Startup utilities (NOT routers)
# You should call these in main.py explicitly (after Bot/Dispatcher initialized)
try:
    from handlers.auto_detect_groups import auto_detect_and_map_groups
    STARTUP_TASKS = [auto_detect_and_map_groups]
except Exception:
    STARTUP_TASKS = []

# Order matters: admin/core first, then features
routers = [
    start_router,
    admin_router,
    admin_dbcheck_router,
    admin_tools_router,   # admin tools with /rescan
    auto_link_router,     # reacts to my_chat_member etc.
    sync_groups_router,   # /syncgroups
    pm_services_router,
    pm_trucker_router,
    documents_router,
    trailer_router,
]

if HAS_SEARCH and search_router:
    routers.append(search_router)

__all__ = ["routers", "STARTUP_TASKS"]
