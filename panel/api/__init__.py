"""
API Package
ماژول‌های API
"""

from .auth import router as auth_router
from .users import router as users_router
from .settings import router as settings_router
from .logs import router as logs_router
from .dashboard import router as dashboard_router
from .blocking import router as blocking_router
from .routes import router as routes_router

__all__ = [
    "auth_router",
    "users_router",
    "settings_router",
    "logs_router",
    "dashboard_router",
    "blocking_router",
    "routes_router"
]
