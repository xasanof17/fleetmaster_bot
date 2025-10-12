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

# Import search router if exists, otherwise skip
try:
    from handlers.search import router as search_router
    has_search = True
except ImportError:
    has_search = False
    search_router = None

# Import documents router if exists
try:
    from handlers.documents import router as documents_router
    has_documents = True
except ImportError:
    has_documents = False
    documents_router = None

# List of all routers to include in dispatcher
routers = [
    # Core handlers (highest priority)
    start_router,
    admin_router,
    admin_dbcheck_router,
    
    # Auto-linking and sync (must be early for my_chat_member)
    auto_link_router,
    sync_groups_router,
    
    # Main feature handlers
    pm_services_router,
    pm_trucker_router,
]

# Add optional routers if they exist
if has_search and search_router:
    routers.append(search_router)

if has_documents and documents_router:
    routers.append(documents_router)

__all__ = ["routers"]