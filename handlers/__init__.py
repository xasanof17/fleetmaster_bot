# Expose routers for dispatcher inclusion
from .start import router as start_router
from .pm_trucker import router as pm_router
from .search import router as search_router
from .documents import documents_router
from .pm_services import router as pm_services_router
from .admin import router as admin_router
from .auto_link_groups import router as auto_link_router
from .sync_groups import router as sync_groups_router
from .admin_dbcheck import router as admin_dbcheck_router

routers = [start_router, pm_router, search_router, documents_router, pm_services_router, admin_router, auto_link_router, sync_groups_router, admin_dbcheck_router]
