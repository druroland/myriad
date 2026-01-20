"""HTTP routers."""

from myriad.routers.auth import router as auth_router
from myriad.routers.dashboard import router as dashboard_router
from myriad.routers.hosts import router as hosts_router

__all__ = ["auth_router", "dashboard_router", "hosts_router"]
