"""
Logs API
API لاگ‌ها
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from api.auth import get_current_admin
from models.admin import Admin
from services.logging_service import log_reader
import asyncio

router = APIRouter(prefix="/api/logs", tags=["Logs"])


@router.get("/panel")
async def get_panel_logs(
    lines: int = Query(default=100, le=500),
    current_admin: Admin = Depends(get_current_admin)
):
    """لاگ‌های پنل"""
    return {
        "logs": log_reader.read_panel_logs(lines),
        "type": "panel"
    }


@router.get("/traffic")
async def get_traffic_logs(
    lines: int = Query(default=100, le=500),
    current_admin: Admin = Depends(get_current_admin)
):
    """لاگ‌های ترافیک"""
    return {
        "logs": log_reader.read_traffic_logs(lines),
        "type": "traffic"
    }


@router.get("/connections")
async def get_connection_logs(
    lines: int = Query(default=100, le=500),
    current_admin: Admin = Depends(get_current_admin)
):
    """لاگ‌های اتصالات"""
    return {
        "logs": log_reader.read_connection_logs(lines),
        "type": "connections"
    }


@router.get("/ocserv")
async def get_ocserv_logs(
    lines: int = Query(default=100, le=500),
    current_admin: Admin = Depends(get_current_admin)
):
    """لاگ‌های OCServ"""
    return {
        "logs": log_reader.read_ocserv_logs(lines),
        "type": "ocserv"
    }


@router.get("/all")
async def get_all_logs(
    lines: int = Query(default=50, le=200),
    current_admin: Admin = Depends(get_current_admin)
):
    """همه لاگ‌ها"""
    return {
        "panel": log_reader.read_panel_logs(lines),
        "traffic": log_reader.read_traffic_logs(lines),
        "connections": log_reader.read_connection_logs(lines),
        "ocserv": log_reader.read_ocserv_logs(lines)
    }


@router.get("/stats")
async def get_log_stats(
    current_admin: Admin = Depends(get_current_admin)
):
    """آمار فایل‌های لاگ"""
    return log_reader.get_log_stats()


@router.get("/stream")
async def stream_logs(
    log_type: str = Query(default="panel"),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    استریم لاگ real-time
    با Server-Sent Events
    """
    async def event_generator():
        last_count = 0
        
        while True:
            # Get appropriate logs
            if log_type == "panel":
                logs = log_reader.read_panel_logs(50)
            elif log_type == "traffic":
                logs = log_reader.read_traffic_logs(50)
            elif log_type == "connections":
                logs = log_reader.read_connection_logs(50)
            elif log_type == "ocserv":
                logs = log_reader.read_ocserv_logs(50)
            else:
                logs = log_reader.read_panel_logs(50)
            
            # Send new logs only
            if len(logs) > last_count:
                new_logs = logs[last_count:]
                for log in new_logs:
                    yield f"data: {log}\n\n"
                last_count = len(logs)
            
            await asyncio.sleep(2)  # Check every 2 seconds
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
