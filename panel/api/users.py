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
    expire_date: Optional[datetime] = Field(default=None, description="تاریخ انقضا")
    max_connections: int = Field(default=2, ge=1, description="حداکثر اتصال همزمان")
    note: Optional[str] = Field(default=None, description="یادداشت")


class UserUpdate(BaseModel):
    """ویرایش کاربر"""
    password: Optional[str] = Field(default=None, min_length=4, description="رمز عبور جدید")
    max_traffic: Optional[int] = Field(default=None, ge=0, description="حداکثر ترافیک")
    expire_date: Optional[datetime] = Field(default=None, description="تاریخ انقضا")
    max_connections: Optional[int] = Field(default=None, ge=1, description="حداکثر اتصال همزمان")
    is_active: Optional[bool] = Field(default=None, description="فعال/غیرفعال")
    note: Optional[str] = Field(default=None, description="یادداشت")


class UserResponse(BaseModel):
    """پاسخ کاربر"""
    id: int
    username: str
    max_traffic: int
    used_traffic: int
    expire_date: Optional[datetime]
    max_connections: int
    is_active: bool
    is_online: bool
    current_connections: int
    note: Optional[str]
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

@router.get("", response_model=UserListResponse)
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
    
    # Apply pagination
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(User.created_at.desc())
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return {
        "users": users,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
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
    
    # Add to database
    new_user = User(
        username=user_data.username,
        password=user_data.password,  # Stored for password changes
        max_traffic=user_data.max_traffic,
        expire_date=user_data.expire_date,
        max_connections=user_data.max_connections,
        note=user_data.note
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """دریافت اطلاعات کاربر"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="کاربر یافت نشد"
        )
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """ویرایش کاربر"""
    result = await db.execute(
        select(User).where(User.id == user_id)
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
    if user_data.expire_date is not None:
        user.expire_date = user_data.expire_date
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
    
    await db.commit()
    await db.refresh(user)
    
    return user


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
