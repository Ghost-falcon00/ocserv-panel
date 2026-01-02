"""
Logs API
API لاگ‌ها و اتصالات
"""

from datetime import datetime, date, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.admin import Admin
from models.user import User
from models.connection_log import ConnectionLog
from api.auth import get_current_admin

router = APIRouter(prefix="/api/logs", tags=["Logs"])


# ========== Schemas ==========

class ConnectionLogResponse(BaseModel):
    """لاگ اتصال"""
    id: int
    user_id: int
    username: str
    client_ip: Optional[str]
    vpn_ip: Optional[str]
    device_type: Optional[str]
    user_agent: Optional[str]
    connected_at: datetime
    disconnected_at: Optional[datetime]
    traffic_in: int
    traffic_out: int
    disconnect_reason: Optional[str]
    duration_seconds: int
    total_traffic: int

    class Config:
        from_attributes = True


class LogListResponse(BaseModel):
    """لیست لاگ‌ها"""
    logs: List[ConnectionLogResponse]
    total: int
    page: int
    per_page: int
    pages: int


class DailyStats(BaseModel):
    """آمار روزانه"""
    date: date
    connections: int
    traffic_in: int
    traffic_out: int
    unique_users: int


# ========== Endpoints ==========

@router.get("", response_model=LogListResponse)
async def list_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    username: Optional[str] = Query(None, description="فیلتر بر اساس نام کاربری"),
    from_date: Optional[datetime] = Query(None, description="از تاریخ"),
    to_date: Optional[datetime] = Query(None, description="تا تاریخ"),
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    لیست لاگ‌های اتصال
    
    با قابلیت فیلتر بر اساس کاربر و بازه زمانی
    """
    query = select(ConnectionLog)
    
    # Apply filters
    conditions = []
    if username:
        conditions.append(ConnectionLog.username == username)
    if from_date:
        conditions.append(ConnectionLog.connected_at >= from_date)
    if to_date:
        conditions.append(ConnectionLog.connected_at <= to_date)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar()
    
    # Apply pagination and ordering
    query = query.order_by(ConnectionLog.connected_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return {
        "logs": logs,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


@router.get("/user/{user_id}", response_model=LogListResponse)
async def get_user_logs(
    user_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """لاگ‌های یک کاربر خاص"""
    # Check user exists
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    
    query = select(ConnectionLog).where(ConnectionLog.user_id == user_id)
    
    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar()
    
    # Apply pagination
    query = query.order_by(ConnectionLog.connected_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return {
        "logs": logs,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


@router.get("/stats/daily", response_model=List[DailyStats])
async def get_daily_stats(
    days: int = Query(7, ge=1, le=90, description="تعداد روز"),
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    آمار روزانه
    
    شامل تعداد اتصالات، ترافیک و کاربران یکتا
    """
    stats = []
    today = date.today()
    
    for i in range(days):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        result = await db.execute(
            select(ConnectionLog).where(
                and_(
                    ConnectionLog.connected_at >= day_start,
                    ConnectionLog.connected_at <= day_end
                )
            )
        )
        logs = result.scalars().all()
        
        unique_users = set(log.username for log in logs)
        
        stats.append(DailyStats(
            date=day,
            connections=len(logs),
            traffic_in=sum(log.traffic_in for log in logs),
            traffic_out=sum(log.traffic_out for log in logs),
            unique_users=len(unique_users)
        ))
    
    return stats


@router.get("/stats/summary")
async def get_summary_stats(
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    آمار کلی
    
    خلاصه آمار سیستم
    """
    # Total users
    total_users = await db.execute(select(func.count(User.id)))
    total_users = total_users.scalar()
    
    # Active users
    active_users = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    active_users = active_users.scalar()
    
    # Online users
    online_users = await db.execute(
        select(func.count(User.id)).where(User.is_online == True)
    )
    online_users = online_users.scalar()
    
    # Today's connections
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    
    today_connections = await db.execute(
        select(func.count(ConnectionLog.id)).where(
            ConnectionLog.connected_at >= today_start
        )
    )
    today_connections = today_connections.scalar()
    
    # Today's traffic
    today_logs = await db.execute(
        select(ConnectionLog).where(ConnectionLog.connected_at >= today_start)
    )
    today_logs = today_logs.scalars().all()
    today_traffic_in = sum(log.traffic_in for log in today_logs)
    today_traffic_out = sum(log.traffic_out for log in today_logs)
    
    # Total traffic
    total_traffic = await db.execute(
        select(func.sum(User.used_traffic))
    )
    total_traffic = total_traffic.scalar() or 0
    
    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "online": online_users
        },
        "today": {
            "connections": today_connections,
            "traffic_in": today_traffic_in,
            "traffic_out": today_traffic_out,
            "traffic_total": today_traffic_in + today_traffic_out
        },
        "total_traffic": total_traffic
    }


@router.delete("/{log_id}")
async def delete_log(
    log_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """حذف یک لاگ"""
    result = await db.execute(
        select(ConnectionLog).where(ConnectionLog.id == log_id)
    )
    log = result.scalar_one_or_none()
    
    if not log:
        raise HTTPException(status_code=404, detail="لاگ یافت نشد")
    
    await db.delete(log)
    await db.commit()
    
    return {"message": "لاگ حذف شد"}


@router.delete("/cleanup")
async def cleanup_old_logs(
    days: int = Query(30, ge=7, description="حذف لاگ‌های قدیمی‌تر از این تعداد روز"),
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """حذف لاگ‌های قدیمی"""
    cutoff = datetime.now() - timedelta(days=days)
    
    result = await db.execute(
        select(ConnectionLog).where(ConnectionLog.connected_at < cutoff)
    )
    old_logs = result.scalars().all()
    
    count = len(old_logs)
    for log in old_logs:
        await db.delete(log)
    
    await db.commit()
    
    return {"message": f"{count} لاگ قدیمی حذف شد"}
