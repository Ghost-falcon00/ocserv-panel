"""
OCServ Panel - FastAPI Application
اپلیکیشن اصلی پنل مدیریت OCServ
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from models.database import init_db, async_session
from models.admin import Admin
from services.traffic import traffic_service
from services.quota import quota_service
from api import (
    auth_router,
    users_router,
    settings_router,
    logs_router,
    dashboard_router,
    blocking_router,
    routes_router,
    tunnel_router
)
from services.logging_service import setup_logging

# Configure logging with file rotation
setup_logging()
logger = logging.getLogger(__name__)


# Scheduler for background tasks
scheduler = AsyncIOScheduler()


async def traffic_update_task():
    """Task to update traffic periodically"""
    async with async_session() as session:
        await traffic_service.update_user_traffic(session)


async def quota_check_task():
    """Task to check quotas periodically"""
    await quota_service.check_quotas()


async def connection_limit_task():
    """Task to check per-user connection limits"""
    await quota_service.check_connection_limits()


async def create_default_admin():
    """Create default admin if not exists"""
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(Admin).limit(1))
        existing = result.scalar()
        if not existing:
            admin = Admin(
                username="admin",
                password_hash=Admin.hash_password("admin"),
                is_superadmin=True
            )
            session.add(admin)
            await session.commit()
            logger.info("Default admin created: admin/admin")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting OCServ Panel...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Create default admin
    await create_default_admin()
    
    # Start scheduler
    scheduler.add_job(
        traffic_update_task,
        'interval',
        seconds=settings.TRAFFIC_CHECK_INTERVAL,
        id='traffic_update'
    )
    scheduler.add_job(
        quota_check_task,
        'interval',
        seconds=settings.QUOTA_CHECK_INTERVAL,
        id='quota_check'
    )
    scheduler.add_job(
        connection_limit_task,
        'interval',
        seconds=30,  # Check every 30 seconds
        id='connection_limit'
    )
    scheduler.start()
    logger.info("Scheduler started")
    
    yield
    
    # Shutdown
    scheduler.shutdown()
    logger.info("OCServ Panel stopped")


# Create FastAPI app
app = FastAPI(
    title="OCServ Panel",
    description="پنل مدیریت OCServ VPN",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
static_path = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Templates
templates_path = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_path, exist_ok=True)
templates = Jinja2Templates(directory=templates_path)

# Include routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(dashboard_router)
app.include_router(blocking_router)
app.include_router(routes_router)
app.include_router(tunnel_router)


# ========== Frontend Routes ==========

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """صفحه اصلی - ریدایرکت به داشبورد"""
    return RedirectResponse(url="/dashboard")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """صفحه ورود"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """صفحه داشبورد"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    """صفحه مدیریت کاربران"""
    return templates.TemplateResponse("users.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """صفحه تنظیمات"""
    return templates.TemplateResponse("settings.html", {"request": request})


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """صفحه لاگ‌ها"""
    return templates.TemplateResponse("logs.html", {"request": request})


@app.get("/system-logs", response_class=HTMLResponse)
async def system_logs_page(request: Request):
    """صفحه لاگ سیستم"""
    return templates.TemplateResponse("system_logs.html", {"request": request})


@app.get("/tunnel", response_class=HTMLResponse)
async def tunnel_page(request: Request):
    """صفحه مدیریت تانل"""
    return templates.TemplateResponse("tunnel.html", {"request": request})


# ========== Health Check ==========

@app.get("/health")
async def health_check():
    """بررسی سلامت سرویس"""
    return {"status": "healthy", "version": settings.APP_VERSION}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.PANEL_HOST,
        port=settings.PANEL_PORT,
        reload=settings.DEBUG
    )
