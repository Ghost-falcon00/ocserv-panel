"""
Tunnel API
API مدیریت تانل برای عبور از فیلترینگ
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, IPvAnyAddress
from models.admin import Admin
from api.auth import get_current_admin
from services.tunnel import tunnel_service

router = APIRouter(prefix="/api/tunnel", tags=["Tunnel"])


# ========== Schemas ==========

class TunnelConfig(BaseModel):
    """تنظیمات تانل"""
    remote_ip: str
    remote_port: int = 2083
    local_port: int = 443
    protocol: str = "relay+tls"
    sni: str = "www.google.com"


class TunnelStatus(BaseModel):
    """وضعیت تانل"""
    installed: bool
    running: bool
    config: dict
    error: Optional[str] = None


class TunnelResponse(BaseModel):
    """پاسخ عملیات تانل"""
    success: bool
    message: str


class ConnectionTest(BaseModel):
    """نتیجه تست اتصال"""
    reachable: bool
    http_code: Optional[str] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


# ========== Endpoints ==========

@router.get("/status", response_model=TunnelStatus)
async def get_tunnel_status(
    current_admin: Admin = Depends(get_current_admin)
):
    """
    دریافت وضعیت تانل
    
    نمایش وضعیت نصب، اجرا، و تنظیمات فعلی
    """
    status = await tunnel_service.get_status()
    return TunnelStatus(**status)


@router.get("/config", response_model=TunnelConfig)
async def get_tunnel_config(
    current_admin: Admin = Depends(get_current_admin)
):
    """دریافت تنظیمات فعلی تانل"""
    config = await tunnel_service.get_config()
    return TunnelConfig(**config)


@router.put("/config", response_model=TunnelResponse)
async def update_tunnel_config(
    config: TunnelConfig,
    current_admin: Admin = Depends(get_current_admin)
):
    """
    به‌روزرسانی تنظیمات تانل
    
    تنظیم IP سرور فرانسه، پورت، پروتکل و SNI
    """
    success = await tunnel_service.update_config(
        remote_ip=config.remote_ip,
        remote_port=config.remote_port,
        local_port=config.local_port,
        protocol=config.protocol,
        sni=config.sni
    )
    
    if success:
        return TunnelResponse(
            success=True,
            message="تنظیمات تانل با موفقیت ذخیره شد"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در ذخیره تنظیمات"
        )


@router.post("/start", response_model=TunnelResponse)
async def start_tunnel(
    current_admin: Admin = Depends(get_current_admin)
):
    """
    شروع تانل
    
    اگر Gost نصب نباشد، ابتدا نصب می‌شود
    """
    # بررسی تنظیمات
    config = await tunnel_service.get_config()
    if not config.get("remote_ip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لطفاً ابتدا IP سرور فرانسه را تنظیم کنید"
        )
    
    success = await tunnel_service.start()
    
    if success:
        return TunnelResponse(
            success=True,
            message="تانل با موفقیت شروع شد"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در شروع تانل"
        )


@router.post("/stop", response_model=TunnelResponse)
async def stop_tunnel(
    current_admin: Admin = Depends(get_current_admin)
):
    """توقف تانل"""
    success = await tunnel_service.stop()
    
    if success:
        return TunnelResponse(
            success=True,
            message="تانل متوقف شد"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در توقف تانل"
        )


@router.post("/restart", response_model=TunnelResponse)
async def restart_tunnel(
    current_admin: Admin = Depends(get_current_admin)
):
    """راه‌اندازی مجدد تانل"""
    success = await tunnel_service.restart()
    
    if success:
        return TunnelResponse(
            success=True,
            message="تانل با موفقیت راه‌اندازی مجدد شد"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در راه‌اندازی مجدد تانل"
        )


@router.post("/test", response_model=ConnectionTest)
async def test_connection(
    remote_ip: str,
    remote_port: int = 2083,
    current_admin: Admin = Depends(get_current_admin)
):
    """
    تست اتصال به سرور فرانسه
    
    بررسی دسترسی و اندازه‌گیری تأخیر
    """
    result = await tunnel_service.test_connection(remote_ip, remote_port)
    return ConnectionTest(**result)


@router.post("/install", response_model=TunnelResponse)
async def install_gost(
    current_admin: Admin = Depends(get_current_admin)
):
    """
    نصب Gost
    
    دانلود و نصب آخرین نسخه Gost
    """
    if await tunnel_service.is_gost_installed():
        return TunnelResponse(
            success=True,
            message="Gost قبلاً نصب شده است"
        )
    
    success = await tunnel_service.install_gost()
    
    if success:
        return TunnelResponse(
            success=True,
            message="Gost با موفقیت نصب شد"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در نصب Gost"
        )
