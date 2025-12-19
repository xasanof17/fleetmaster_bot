"""
handlers/__init__.py
Centralized router registration for all bot handlers (CLEAN VERSION)
"""

from handlers.admin import router as admin_router
from handlers.admin_commands import router as admin_commands_router
from handlers.admin_tools import router as admin_tools_router
from handlers.auto_link_groups import router as auto_link_router
from handlers.documents import router as documents_router
from handlers.manage_users import router as manage_users_router
from handlers.pm_services import router as pm_services_router
from handlers.pm_trucker import router as pm_trucker_router
from handlers.registration import router as registration_router
from handlers.start import router as start_router
from handlers.trailer import router as trailer_router

# Optional search router
try:
    from handlers.search import router as search_router

    HAS_SEARCH = True
except ImportError:
    search_router = None
    HAS_SEARCH = False

# IMPORTANT ORDER:
# 1. Start/Global commands
# 2. Specific Admin commands
# 3. Broad Catch-all filters (like auto_link)
routers = [
    start_router,
    admin_router,
    admin_tools_router,
    admin_commands_router,  # Moved up
    pm_services_router,
    pm_trucker_router,
    documents_router,
    trailer_router,
    registration_router,
    auto_link_router,  # Moved down to prevent intercepting specific commands
    manage_users_router,
]

if HAS_SEARCH and search_router:
    routers.append(search_router)

__all__ = ["routers"]
