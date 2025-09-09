# Expose routers for dispatcher inclusion
from .start import router as start_router
from .pm_trucker import router as pm_router
from .search import router as search_router

routers = [start_router, pm_router, search_router]
