"""
Users API
API مدیریت کاربران VPN
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.user import User
from models.admin import Admin
from services.ocserv import ocserv_service
from api.auth import get_current_admin

router = APIRouter(prefix="/api/users", tags=["Users"])


# ========== Schemas ==========

class UserCreate(BaseModel):
    """ایجاد کاربر جدید"""
    username: str = Field(..., min_length=3, max_length=50, description="نام کاربری")
    password: str = Field(..., min_length=4, description="رمز عبور")
    max_traffic: int = Field(default=0, ge=0, description="حداکثر ترافیک (bytes) - 0 = نامحدود")
    expire_days: int = Field(default=0, ge=0, description="مدت اعتبار (روز) - 0 = نامحدود")
    max_connections: int = Field(default=2, ge=1, description="حداکثر اتصال همزمان")
    note: Optional[str] = Field(default=None, description="یادداشت")
    group_id: Optional[int] = Field(default=None, description="شناسه گروه")
    reset_period_type: Optional[str] = Field(default="monthly", description="نوع دوره ریست: daily/weekly/monthly")


class UserUpdate(BaseModel):
    """ویرایش کاربر"""
    password: Optional[str] = Field(default=None, min_length=4, description="رمز عبور جدید")
    max_traffic: Optional[int] = Field(default=None, ge=0, description="حداکثر ترافیک")
    expire_days: Optional[int] = Field(default=None, ge=0, description="مدت اعتبار (روز)")
    max_connections: Optional[int] = Field(default=None, ge=1, description="حداکثر اتصال همزمان")
    is_active: Optional[bool] = Field(default=None, description="فعال/غیرفعال")
    note: Optional[str] = Field(default=None, description="یادداشت")
    group_id: Optional[int] = Field(default=None, description="شناسه گروه")
    reset_period_type: Optional[str] = Field(default=None, description="نوع دوره ریست")


class UserResponse(BaseModel):
    """پاسخ کاربر"""
    id: int
    username: str
    max_traffic: int
    used_traffic: int
    expire_date: Optional[datetime]
    expire_days: Optional[int] = 0
    max_connections: int
    is_active: bool
    is_online: bool
    current_connections: int
    note: Optional[str]
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    group_color: Optional[str] = None
    reset_period_type: Optional[str] = "monthly"
    created_at: datetime
    last_connection: Optional[datetime]
    total_connections: int
    traffic_remaining: int
    traffic_percent: float
    is_expired: bool
    is_traffic_exceeded: bool
    can_connect: bool

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """لیست کاربران با pagination"""
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    pages: int


class QuotaReset(BaseModel):
    """ریست حجم"""
    new_traffic: int = Field(default=0, ge=0, description="حجم جدید (bytes)")


class ExpiryExtend(BaseModel):
    """تمدید تاریخ"""
    new_expire_date: datetime = Field(..., description="تاریخ انقضای جدید")


# ========== Endpoints ==========

@router.get("")
async def list_users(
    page: int = Query(1, ge=1, description="شماره صفحه"),
    per_page: int = Query(20, ge=1, le=100, description="تعداد در هر صفحه"),
    search: Optional[str] = Query(None, description="جستجو در نام کاربری"),
    is_active: Optional[bool] = Query(None, description="فیلتر فعال/غیرفعال"),
    is_online: Optional[bool] = Query(None, description="فیلتر آنلاین/آفلاین"),
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    لیست کاربران
    
    با قابلیت جستجو، فیلتر و صفحه‌بندی
    """
    query = select(User)
    
    # Apply filters
    if search:
        query = query.where(
            or_(
                User.username.ilike(f"%{search}%"),
                User.note.ilike(f"%{search}%")
            )
        )
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    if is_online is not None:
        query = query.where(User.is_online == is_online)
    
    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar()
    
    # Apply ordering first, then pagination
    from sqlalchemy.orm import selectinload
    query = query.options(selectinload(User.group))
    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return {
        "users": [u.to_dict() for u in users],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


@router.post("")
async def create_user(
    user_data: UserCreate,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    ایجاد کاربر جدید
    
    - کاربر در دیتابیس و OCServ ایجاد می‌شود
    """
    # Check if username exists
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این نام کاربری قبلاً استفاده شده"
        )
    
    # Add to OCServ
    success = await ocserv_service.add_user(user_data.username, user_data.password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در ایجاد کاربر در OCServ"
        )
    
    # Add to database - expire_date will be calculated on first connection
    new_user = User(
        username=user_data.username,
        password=user_data.password,
        max_traffic=user_data.max_traffic,
        expire_days=user_data.expire_days,
        expire_date=None,
        max_connections=user_data.max_connections,
        note=user_data.note,
        group_id=user_data.group_id,
        reset_period_type=user_data.reset_period_type or "monthly"
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Reload with relationships
    from sqlalchemy.orm import selectinload
    stmt = select(User).options(selectinload(User.group)).where(User.id == new_user.id)
    result = await db.execute(stmt)
    loaded_user = result.scalar_one()
    
    return loaded_user.to_dict()


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """دریافت اطلاعات کاربر"""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User).options(selectinload(User.group)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="کاربر یافت نشد"
        )
    
    return user.to_dict()


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """ویرایش کاربر"""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User).options(selectinload(User.group)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="کاربر یافت نشد"
        )
    
    # Update password in OCServ if provided
    if user_data.password:
        success = await ocserv_service.update_password(user.username, user_data.password)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="خطا در تغییر رمز عبور در OCServ"
            )
        user.password = user_data.password
    
    # Update other fields
    if user_data.max_traffic is not None:
        user.max_traffic = user_data.max_traffic
    if user_data.expire_days is not None:
        user.expire_days = user_data.expire_days
        # Recalculate expire_date if user has already connected
        if user.first_connection and user_data.expire_days > 0:
            from datetime import timedelta
            user.expire_date = user.first_connection + timedelta(days=user_data.expire_days)
        elif user_data.expire_days == 0:
            user.expire_date = None  # Unlimited
    if user_data.max_connections is not None:
        user.max_connections = user_data.max_connections
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
        # Lock/unlock in OCServ
        if user_data.is_active:
            await ocserv_service.unlock_user(user.username)
        else:
            await ocserv_service.lock_user(user.username)
    if user_data.note is not None:
        user.note = user_data.note
    group_changed = False
    if user_data.group_id is not None:
        new_group_id = user_data.group_id if user_data.group_id != 0 else None
        if user.group_id != new_group_id:
            user.group_id = new_group_id
            group_changed = True
            
    if user_data.reset_period_type is not None:
        user.reset_period_type = user_data.reset_period_type
    
    await db.commit()
    await db.refresh(user)
    
    # Instantaneous Firewall tracking: If group changed and user is online, disconnect them to force openconnect to re-authenticate and apply the new group's DNS/Firewall rules immediately (auto-reconnects in 2s).
    if group_changed and user.is_online:
        await ocserv_service.disconnect_user(user.username)
    
    # Reload with relationships
    from sqlalchemy.orm import selectinload
    stmt = select(User).options(selectinload(User.group)).where(User.id == user.id)
    result = await db.execute(stmt)
    loaded_user = result.scalar_one()
    
    return loaded_user.to_dict()


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """حذف کاربر"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="کاربر یافت نشد"
        )
    
    # Disconnect if online
    if user.is_online:
        await ocserv_service.disconnect_user(user.username)
    
    # Delete from OCServ
    await ocserv_service.delete_user(user.username)
    
    # Delete from database
    await db.delete(user)
    await db.commit()
    
    return {"message": f"کاربر {user.username} با موفقیت حذف شد"}


@router.post("/{user_id}/disconnect")
async def disconnect_user(
    user_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """قطع اتصال کاربر"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="کاربر یافت نشد"
        )
    
    success = await ocserv_service.disconnect_user(user.username)
    if success:
        user.is_online = False
        user.current_connections = 0
        await db.commit()
        return {"message": f"اتصال کاربر {user.username} قطع شد"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در قطع اتصال"
        )


@router.post("/{user_id}/reset-traffic")
async def reset_user_traffic(
    user_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """ریست کردن ترافیک مصرفی کاربر به صفر"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    
    if user.used_traffic >= user.max_traffic and user.max_traffic > 0:
        await ocserv_service.unlock_user(user.username)
        user.is_active = True
        
    user.reset_traffic()
    await db.commit()
    
    return {"message": f"ترافیک مصرفی {user.username} با موفقیت صفر شد"}


@router.post("/{user_id}/reset-quota")
async def reset_quota(
    user_id: int,
    quota_data: QuotaReset,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """ریست حجم کاربر"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="کاربر یافت نشد"
        )
    
    user.used_traffic = 0
    user.max_traffic = quota_data.new_traffic
    user.is_active = True
    
    await ocserv_service.unlock_user(user.username)
    await db.commit()
    
    return {"message": f"حجم کاربر {user.username} ریست شد"}


@router.post("/{user_id}/extend-expiry")
async def extend_expiry(
    user_id: int,
    expiry_data: ExpiryExtend,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """تمدید تاریخ انقضا"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="کاربر یافت نشد"
        )
    
    user.expire_date = expiry_data.new_expire_date
    user.is_active = True
    
    await ocserv_service.unlock_user(user.username)
    await db.commit()
    
    return {"message": f"تاریخ انقضای کاربر {user.username} تمدید شد"}


@router.get("/{user_id}/traffic")
async def get_user_traffic(
    user_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """دریافت ترافیک کاربر"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="کاربر یافت نشد"
        )
    
    # Get real-time traffic if online
    if user.is_online:
        live_traffic = await ocserv_service.get_user_traffic(user.username)
    else:
        live_traffic = {"rx": 0, "tx": 0}
    
    return {
        "username": user.username,
        "used_traffic": user.used_traffic,
        "max_traffic": user.max_traffic,
        "remaining": user.traffic_remaining,
        "percent": user.traffic_percent,
        "live": live_traffic
    }
