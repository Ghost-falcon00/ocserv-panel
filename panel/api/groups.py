"""
Groups API
API مدیریت گروه‌های کاربری
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.admin import Admin
from models.group import UserGroup
from models.user import User
from api.auth import get_current_admin

router = APIRouter(prefix="/api/groups", tags=["Groups"])


# ========== Schemas ==========

class GroupCreate(BaseModel):
    """ایجاد گروه"""
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#6366f1"
    blocked_domains: Optional[List[str]] = []
    allowed_domains: Optional[List[str]] = []
    blocked_categories: Optional[List[str]] = []
    default_max_traffic: Optional[int] = 0
    default_expire_days: Optional[int] = 30
    default_max_connections: Optional[int] = 2
    default_reset_period_type: Optional[str] = "monthly"


class GroupUpdate(BaseModel):
    """ویرایش گروه"""
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    blocked_domains: Optional[List[str]] = None
    allowed_domains: Optional[List[str]] = None
    blocked_categories: Optional[List[str]] = None
    default_max_traffic: Optional[int] = None
    default_expire_days: Optional[int] = None
    default_max_connections: Optional[int] = None
    default_reset_period_type: Optional[str] = None
    is_active: Optional[bool] = None


class GroupDomainAction(BaseModel):
    """اضافه/حذف دامنه"""
    domains: List[str]


class GroupAssignUsers(BaseModel):
    """انتساب کاربران به گروه"""
    user_ids: List[int]


# ========== Endpoints ==========

@router.get("")
async def list_groups(
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """لیست تمام گروه‌ها"""
    result = await db.execute(
        select(UserGroup).order_by(UserGroup.created_at.desc())
    )
    groups = result.scalars().all()

    return {
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "description": g.description,
                "color": g.color,
                "blocked_domains": g.blocked_domains or [],
                "allowed_domains": g.allowed_domains or [],
                "blocked_categories": g.blocked_categories or [],
                "default_max_traffic": g.default_max_traffic,
                "default_expire_days": g.default_expire_days,
                "default_max_connections": g.default_max_connections,
                "default_reset_period_type": g.default_reset_period_type,
                "is_active": g.is_active,
                "user_count": g.user_count,
                "blocked_domains_count": g.blocked_domains_count,
                "created_at": g.created_at.isoformat() if g.created_at else None,
            }
            for g in groups
        ],
        "total": len(groups)
    }


@router.get("/{group_id}")
async def get_group(
    group_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """دریافت اطلاعات یک گروه"""
    result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="گروه یافت نشد"
        )

    # Get users in this group
    users_result = await db.execute(
        select(User).where(User.group_id == group_id)
    )
    users = users_result.scalars().all()

    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "color": group.color,
        "blocked_domains": group.blocked_domains or [],
        "allowed_domains": group.allowed_domains or [],
        "blocked_categories": group.blocked_categories or [],
        "default_max_traffic": group.default_max_traffic,
        "default_expire_days": group.default_expire_days,
        "default_max_connections": group.default_max_connections,
        "default_reset_period_type": group.default_reset_period_type,
        "is_active": group.is_active,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "is_active": u.is_active,
                "is_online": u.is_online
            }
            for u in users
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupCreate,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """ایجاد گروه جدید"""
    # Check duplicate name
    existing = await db.execute(
        select(UserGroup).where(UserGroup.name == group_data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="گروهی با این نام وجود دارد"
        )

    # Normalize domains (lowercase, strip whitespace)
    blocked = [d.strip().lower() for d in (group_data.blocked_domains or []) if d.strip()]
    allowed = [d.strip().lower() for d in (group_data.allowed_domains or []) if d.strip()]
    categories = [c.strip().lower() for c in (group_data.blocked_categories or []) if c.strip()]

    group = UserGroup(
        name=group_data.name,
        description=group_data.description,
        color=group_data.color or "#6366f1",
        blocked_domains=blocked,
        allowed_domains=allowed,
        blocked_categories=categories,
        default_max_traffic=group_data.default_max_traffic,
        default_expire_days=group_data.default_expire_days,
        default_max_connections=group_data.default_max_connections,
        default_reset_period_type=group_data.default_reset_period_type,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    # Apply domain blocks
    if blocked or categories:
        from services.firewall_service import FirewallService
        await FirewallService.sync_group(group.id, db)

    return {"message": "گروه ایجاد شد", "id": group.id}


@router.put("/{group_id}")
async def update_group(
    group_id: int,
    group_data: GroupUpdate,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """ویرایش گروه"""
    result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="گروه یافت نشد"
        )

    # Update fields
    update_data = group_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field in ("blocked_domains", "allowed_domains", "blocked_categories") and value is not None:
            value = [d.strip().lower() for d in value if d.strip()]
        setattr(group, field, value)

    await db.commit()

    # Apply firewall rules dynamically
    if any(k in update_data for k in ("blocked_domains", "blocked_categories")):
        # We will write the firewall sync function next
        from services.firewall_service import FirewallService
        await FirewallService.sync_group(group.id, db)

    return {"message": "گروه ویرایش شد"}


@router.delete("/{group_id}")
async def delete_group(
    group_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """حذف گروه"""
    result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="گروه یافت نشد"
        )

    # Remove group assignment from users
    users_result = await db.execute(
        select(User).where(User.group_id == group_id)
    )
    users = users_result.scalars().all()
    for user in users:
        user.group_id = None

    await db.delete(group)
    await db.commit()

    return {"message": "گروه حذف شد"}


@router.post("/{group_id}/assign")
async def assign_users(
    group_id: int,
    data: GroupAssignUsers,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """انتساب کاربران به گروه"""
    # Verify group exists
    result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="گروه یافت نشد"
        )

    # Update users
    for user_id in data.user_ids:
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            user.group_id = group_id

    await db.commit()
    return {"message": f"{len(data.user_ids)} کاربر به گروه {group.name} اضافه شدند"}


@router.post("/{group_id}/unassign")
async def unassign_users(
    group_id: int,
    data: GroupAssignUsers,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """حذف کاربران از گروه"""
    for user_id in data.user_ids:
        user_result = await db.execute(
            select(User).where(User.id == user_id, User.group_id == group_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            user.group_id = None

    await db.commit()
    return {"message": "کاربران از گروه خارج شدند"}


@router.post("/{group_id}/domains/block")
async def add_blocked_domains(
    group_id: int,
    data: GroupDomainAction,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """اضافه کردن دامنه به لیست بلاک شده"""
    result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="گروه یافت نشد")

    current = group.blocked_domains or []
    new_domains = [d.strip().lower() for d in data.domains if d.strip()]
    # Avoid duplicates
    merged = list(set(current + new_domains))
    group.blocked_domains = merged
    await db.commit()

    from services.firewall_service import FirewallService
    await FirewallService.sync_group(group.id, db)
    return {"message": f"{len(new_domains)} دامنه بلاک شد", "total": len(merged)}


@router.delete("/{group_id}/domains/block")
async def remove_blocked_domains(
    group_id: int,
    data: GroupDomainAction,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """حذف دامنه از لیست بلاک شده"""
    result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="گروه یافت نشد")

    current = group.blocked_domains or []
    remove_set = {d.strip().lower() for d in data.domains}
    group.blocked_domains = [d for d in current if d not in remove_set]
    await db.commit()

    from services.firewall_service import FirewallService
    await FirewallService.sync_group(group.id, db)
    return {"message": "دامنه‌ها حذف شدند"}


# ========== Helper ==========

# Old DNS script removed
