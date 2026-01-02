"""
Settings API
API تنظیمات OCServ
"""

from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.admin import Admin
from models.settings import SystemSettings, DEFAULT_SETTINGS
from services.ocserv import ocserv_service
from api.auth import get_current_admin

router = APIRouter(prefix="/api/settings", tags=["Settings"])


# ========== Schemas ==========

class SettingItem(BaseModel):
    """یک تنظیم"""
    key: str
    value: str
    description: Optional[str] = None
    category: str = "general"


class SettingUpdate(BaseModel):
    """به‌روزرسانی تنظیم"""
    value: str


class SettingsList(BaseModel):
    """لیست تنظیمات"""
    settings: Dict[str, SettingItem]
    categories: List[str]


class ServerControlResponse(BaseModel):
    """پاسخ کنترل سرور"""
    success: bool
    message: str


# ========== Endpoints ==========

@router.get("", response_model=SettingsList)
async def get_settings(
    category: Optional[str] = None,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت تنظیمات
    
    با توضیحات فارسی برای هر تنظیم
    """
    result = await db.execute(select(SystemSettings))
    db_settings = result.scalars().all()
    
    # Merge with defaults
    settings = {}
    categories = set()
    
    # Add defaults first
    for key, data in DEFAULT_SETTINGS.items():
        if category and data["category"] != category:
            continue
        settings[key] = SettingItem(
            key=key,
            value=data["value"],
            description=data["description"],
            category=data["category"]
        )
        categories.add(data["category"])
    
    # Override with database values
    for setting in db_settings:
        if category and setting.category != category:
            continue
        settings[setting.key] = SettingItem(
            key=setting.key,
            value=setting.value,
            description=setting.description,
            category=setting.category
        )
        categories.add(setting.category)
    
    return {
        "settings": settings,
        "categories": sorted(list(categories))
    }


@router.get("/{key}", response_model=SettingItem)
async def get_setting(
    key: str,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """دریافت یک تنظیم خاص"""
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()
    
    if setting:
        return SettingItem(
            key=setting.key,
            value=setting.value,
            description=setting.description,
            category=setting.category
        )
    
    # Check defaults
    if key in DEFAULT_SETTINGS:
        data = DEFAULT_SETTINGS[key]
        return SettingItem(
            key=key,
            value=data["value"],
            description=data["description"],
            category=data["category"]
        )
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="تنظیم یافت نشد"
    )


@router.put("/{key}", response_model=SettingItem)
async def update_setting(
    key: str,
    setting_data: SettingUpdate,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    به‌روزرسانی تنظیم
    
    تنظیم در دیتابیس و فایل کانفیگ OCServ اعمال می‌شود
    """
    # Get or create setting in database
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()
    
    default = DEFAULT_SETTINGS.get(key, {
        "description": "",
        "category": "general"
    })
    
    if setting:
        setting.value = setting_data.value
    else:
        setting = SystemSettings(
            key=key,
            value=setting_data.value,
            description=default.get("description", ""),
            category=default.get("category", "general")
        )
        db.add(setting)
    
    await db.commit()
    
    # Update OCServ config file
    success = await ocserv_service.update_config(key, setting_data.value)
    if not success:
        # Rollback is not critical, setting is saved in DB
        pass
    
    return SettingItem(
        key=setting.key,
        value=setting.value,
        description=setting.description,
        category=setting.category
    )


@router.post("/apply", response_model=ServerControlResponse)
async def apply_settings(
    current_admin: Admin = Depends(get_current_admin)
):
    """
    اعمال تنظیمات
    
    بارگذاری مجدد تنظیمات OCServ
    """
    success = await ocserv_service.reload_config()
    
    if success:
        return ServerControlResponse(
            success=True,
            message="تنظیمات با موفقیت اعمال شد"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در اعمال تنظیمات"
        )


@router.post("/server/restart", response_model=ServerControlResponse)
async def restart_server(
    current_admin: Admin = Depends(get_current_admin)
):
    """راه‌اندازی مجدد OCServ"""
    success = await ocserv_service.restart_service()
    
    if success:
        return ServerControlResponse(
            success=True,
            message="سرور با موفقیت راه‌اندازی مجدد شد"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در راه‌اندازی مجدد سرور"
        )


@router.post("/server/stop", response_model=ServerControlResponse)
async def stop_server(
    current_admin: Admin = Depends(get_current_admin)
):
    """توقف OCServ"""
    success = await ocserv_service.stop_service()
    
    if success:
        return ServerControlResponse(
            success=True,
            message="سرور متوقف شد"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در توقف سرور"
        )


@router.post("/server/start", response_model=ServerControlResponse)
async def start_server(
    current_admin: Admin = Depends(get_current_admin)
):
    """شروع OCServ"""
    success = await ocserv_service.start_service()
    
    if success:
        return ServerControlResponse(
            success=True,
            message="سرور شروع به کار کرد"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در شروع سرور"
        )


@router.get("/server/config")
async def get_ocserv_config(
    current_admin: Admin = Depends(get_current_admin)
):
    """دریافت تنظیمات فایل کانفیگ OCServ"""
    config = await ocserv_service.get_config()
    return {"config": config}
