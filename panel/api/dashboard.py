"""
Dashboard API
API داشبورد
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.admin import Admin
from models.user import User
from models.connection_log import ConnectionLog
from services.ocserv import ocserv_service
from api.auth import get_current_admin

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# ========== Schemas ==========

class OnlineUser(BaseModel):
    """کاربر آنلاین"""
    id: int
    username: str
    vpn_ip: str
    client_ip: str
    connected_at: str
    user_agent: str
    rx: int
    tx: int


class ServerStatus(BaseModel):
    """وضعیت سرور"""
    online: bool
    status: str
    uptime: str = ""
    version: str = ""


class DashboardStats(BaseModel):
    """آمار داشبورد"""
    total_users: int
    active_users: int
    online_users: int
    online_connections: int
    today_traffic: int
    total_traffic: int
    today_connections: int
    near_expiry_users: int
    near_quota_users: int


class TrafficChartData(BaseModel):
    """داده نمودار ترافیک"""
    labels: List[str]
    traffic_in: List[int]
    traffic_out: List[int]


# ========== Endpoints ==========

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    آمار کلی داشبورد
    
    خلاصه وضعیت سیستم
    """
    # Users stats
    total_users = await db.execute(select(func.count(User.id)))
    total_users = total_users.scalar() or 0
    
    active_users = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    active_users = active_users.scalar() or 0
    
    online_users = await db.execute(
        select(func.count(User.id)).where(User.is_online == True)
    )
    online_users = online_users.scalar() or 0
    
    online_connections = await db.execute(
        select(func.sum(User.current_connections)).where(User.is_online == True)
    )
    online_connections = online_connections.scalar() or 0
    
    # Traffic stats
    total_traffic = await db.execute(select(func.sum(User.used_traffic)))
    total_traffic = total_traffic.scalar() or 0
    
    # Today's stats
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    
    today_logs = await db.execute(
        select(ConnectionLog).where(ConnectionLog.connected_at >= today_start)
    )
    today_logs = today_logs.scalars().all()
    today_traffic = sum(log.traffic_in + log.traffic_out for log in today_logs)
    today_connections = len(today_logs)
    
    # Users near limits
    all_users = await db.execute(
        select(User).where(User.is_active == True)
    )
    all_users = all_users.scalars().all()
    
    near_expiry = 0
    near_quota = 0
    now = datetime.now()
    
    for user in all_users:
        # Check expiry (within 3 days)
        if user.expire_date and 0 < (user.expire_date - now).days <= 3:
            near_expiry += 1
        
        # Check quota (above 80%)
        if user.max_traffic > 0 and user.traffic_percent >= 80:
            near_quota += 1
    
    return DashboardStats(
        total_users=total_users,
        active_users=active_users,
        online_users=online_users,
        online_connections=online_connections,
        today_traffic=today_traffic,
        total_traffic=total_traffic,
        today_connections=today_connections,
        near_expiry_users=near_expiry,
        near_quota_users=near_quota
    )


@router.get("/online-users", response_model=List[OnlineUser])
async def get_online_users(
    current_admin: Admin = Depends(get_current_admin)
):
    """
    لیست کاربران آنلاین
    
    اطلاعات real-time از OCServ
    """
    users = await ocserv_service.get_online_users()
    return users


@router.get("/server-status", response_model=ServerStatus)
async def get_server_status(
    current_admin: Admin = Depends(get_current_admin)
):
    """
    وضعیت سرور OCServ
    """
    status = await ocserv_service.get_status()
    
    return ServerStatus(
        online=status.get("online", False),
        status=status.get("status", "unknown"),
        uptime=status.get("uptime", ""),
        version=status.get("version", "")
    )


@router.get("/traffic-chart", response_model=TrafficChartData)
async def get_traffic_chart(
    days: int = 7,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    داده نمودار ترافیک
    
    ترافیک ورودی و خروجی در چند روز گذشته
    """
    labels = []
    traffic_in = []
    traffic_out = []
    today = date.today()
    
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        result = await db.execute(
            select(ConnectionLog).where(
                ConnectionLog.connected_at >= day_start,
                ConnectionLog.connected_at <= day_end
            )
        )
        logs = result.scalars().all()
        
        labels.append(day.strftime("%m/%d"))
        traffic_in.append(sum(log.traffic_in for log in logs))
        traffic_out.append(sum(log.traffic_out for log in logs))
    
    return TrafficChartData(
        labels=labels,
        traffic_in=traffic_in,
        traffic_out=traffic_out
    )


@router.get("/recent-connections")
async def get_recent_connections(
    limit: int = 10,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    آخرین اتصالات
    """
    result = await db.execute(
        select(ConnectionLog)
        .order_by(ConnectionLog.connected_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "username": log.username,
            "client_ip": log.client_ip,
            "connected_at": log.connected_at.isoformat() if log.connected_at else None,
            "disconnected_at": log.disconnected_at.isoformat() if log.disconnected_at else None,
            "traffic": log.total_traffic,
            "status": "online" if log.disconnected_at is None else "offline"
        }
        for log in logs
    ]


@router.get("/alerts")
async def get_alerts(
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    هشدارها
    
    کاربران نزدیک به محدودیت
    """
    alerts = []
    now = datetime.now()
    
    result = await db.execute(
        select(User).where(User.is_active == True)
    )
    users = result.scalars().all()
    
    for user in users:
        # Traffic warning
        if user.max_traffic > 0 and user.traffic_percent >= 80:
            alerts.append({
                "type": "traffic",
                "severity": "warning" if user.traffic_percent < 95 else "critical",
                "username": user.username,
                "message": f"حجم مصرفی {user.traffic_percent:.1f}%",
                "percent": user.traffic_percent
            })
        
        # Expiry warning
        if user.expire_date:
            days_left = (user.expire_date - now).days
            if 0 < days_left <= 3:
                alerts.append({
                    "type": "expiry",
                    "severity": "warning" if days_left > 1 else "critical",
                    "username": user.username,
                    "message": f"{days_left} روز تا انقضا",
                    "days_left": days_left
                })
            elif days_left <= 0:
                alerts.append({
                    "type": "expiry",
                    "severity": "critical",
                    "username": user.username,
                    "message": "منقضی شده",
                    "days_left": 0
                })
    
    return alerts
