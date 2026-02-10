"""
Tunnel API - Advanced Anti-Detection + Remote Sync
API مدیریت تانل پیشرفته با قابلیت‌های ضد شناسایی و سینک از راه دور
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from models.admin import Admin
from api.auth import get_current_admin
from services.tunnel import tunnel_service
from services.remote_sync import remote_sync

router = APIRouter(prefix="/api/tunnel", tags=["Tunnel"])


# ========== Schemas ==========

class TunnelConfig(BaseModel):
    """تنظیمات تانل پیشرفته"""
    remote_ip: str
    remote_port: int = 2083
    local_port: int = 443
    protocol: str = "h2"  # h2, wss, tls
    sni: str = "www.google.com"
    obfuscation: str = "tls"
    mux: bool = True  # Multiplexing
    padding: bool = True  # Random padding


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


class SNIList(BaseModel):
    """لیست SNI های امن"""
    sni_list: List[str]


# ========== Endpoints ==========

@router.get("/status", response_model=TunnelStatus)
async def get_tunnel_status(
    current_admin: Admin = Depends(get_current_admin)
):
    """
    دریافت وضعیت تانل
    
    نمایش وضعیت نصب، اجرا، و تنظیمات فعلی
    شامل اطلاعات multiplexing و padding
    """
    status = await tunnel_service.get_status()
    return TunnelStatus(**status)


@router.get("/config", response_model=TunnelConfig)
async def get_tunnel_config(
    current_admin: Admin = Depends(get_current_admin)
):
    """دریافت تنظیمات فعلی تانل شامل گزینه‌های anti-detection"""
    config = await tunnel_service.get_config()
    return TunnelConfig(
        remote_ip=config.get("remote_ip", ""),
        remote_port=config.get("remote_port", 2083),
        local_port=config.get("local_port", 443),
        protocol=config.get("protocol", "h2"),
        sni=config.get("sni", "www.google.com"),
        obfuscation=config.get("obfuscation", "tls"),
        mux=config.get("mux", True),
        padding=config.get("padding", True)
    )


@router.put("/config", response_model=TunnelResponse)
async def update_tunnel_config(
    config: TunnelConfig,
    current_admin: Admin = Depends(get_current_admin)
):
    """
    به‌روزرسانی تنظیمات تانل با قابلیت‌های ضد شناسایی
    
    - protocol: h2 (HTTP/2 - پیشنهادی), wss (WebSocket), tls
    - mux: Multiplexing برای پنهان کردن پترن ترافیک
    - padding: Random padding برای جلوگیری از تحلیل اندازه پکت
    """
    success = await tunnel_service.update_config(
        remote_ip=config.remote_ip,
        remote_port=config.remote_port,
        local_port=config.local_port,
        protocol=config.protocol,
        sni=config.sni,
        obfuscation=config.obfuscation,
        mux=config.mux,
        padding=config.padding
    )
    
    if success:
        return TunnelResponse(
            success=True,
            message="تنظیمات تانل با موفقیت ذخیره شد (قابلیت‌های ضد شناسایی فعال)"
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
    شروع تانل با قابلیت‌های ضد شناسایی
    
    - نصب خودکار Gost
    - اعمال تنظیمات stealth به OCServ
    - فعال‌سازی TLS fingerprint mimicry
    """
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
            message="تانل امن با قابلیت‌های ضد شناسایی شروع شد"
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
    remote_ip: str = Query(..., description="IP سرور فرانسه"),
    remote_port: int = Query(2083, description="پورت OCServ"),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    تست اتصال به سرور فرانسه
    
    با شبیه‌سازی درخواست مرورگر واقعی
    """
    result = await tunnel_service.test_connection(remote_ip, remote_port)
    return ConnectionTest(**result)


@router.post("/install", response_model=TunnelResponse)
async def install_gost(
    current_admin: Admin = Depends(get_current_admin)
):
    """نصب Gost با تنظیمات امنیتی"""
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


@router.get("/sni-list", response_model=SNIList)
async def get_sni_list(
    current_admin: Admin = Depends(get_current_admin)
):
    """
    دریافت لیست SNI های امن
    
    سایت‌های محبوب که فیلتر نمی‌شوند
    """
    return SNIList(sni_list=tunnel_service.get_safe_sni_list())


@router.post("/apply-stealth", response_model=TunnelResponse)
async def apply_stealth_config(
    current_admin: Admin = Depends(get_current_admin)
):
    """
    اعمال تنظیمات ضد شناسایی به OCServ
    
    - تغییر هدرها به شبیه nginx
    - غیرفعال کردن امضای Cisco
    - فعال‌سازی TLS 1.3
    """
    success = await tunnel_service.apply_ocserv_stealth()
    
    if success:
        return TunnelResponse(
            success=True,
            message="تنظیمات ضد شناسایی به OCServ اعمال شد"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در اعمال تنظیمات ضد شناسایی"
        )


# ========== Remote Sync Endpoints ==========

class SyncConfig(BaseModel):
    """تنظیمات سینک با سرور فرانسه"""
    enabled: bool = True
    remote_ip: str
    remote_api_port: int = 6443
    api_token: str


class SyncStatus(BaseModel):
    """وضعیت سینک"""
    enabled: bool
    connected: bool
    remote_ip: str = ""
    remote_api_port: int = 6443
    message: str = ""


@router.get("/sync/status", response_model=SyncStatus)
async def get_sync_status(
    current_admin: Admin = Depends(get_current_admin)
):
    """دریافت وضعیت سینک با سرور فرانسه"""
    config = remote_sync.config
    
    connected = False
    message = "سینک تنظیم نشده"
    
    if remote_sync.is_enabled:
        try:
            connected = await remote_sync.check_health()
            message = "متصل به سرور فرانسه ✓" if connected else "ارتباط برقرار نیست ✗"
        except Exception as e:
            message = f"خطا: {str(e)}"
    
    return SyncStatus(
        enabled=remote_sync.is_enabled,
        connected=connected,
        remote_ip=config.get("remote_ip", ""),
        remote_api_port=config.get("remote_api_port", 6443),
        message=message
    )


@router.put("/sync/config", response_model=TunnelResponse)
async def update_sync_config(
    config: SyncConfig,
    current_admin: Admin = Depends(get_current_admin)
):
    """
    تنظیم سینک با سرور فرانسه
    
    اطلاعات لازم:
    - IP سرور فرانسه
    - پورت Remote API (پیش‌فرض: 6443)
    - توکن API (از خروجی france-setup.sh)
    """
    sync_data = {
        "enabled": config.enabled,
        "remote_ip": config.remote_ip,
        "remote_api_port": config.remote_api_port,
        "api_token": config.api_token
    }
    
    remote_sync.save_config(sync_data)
    
    # Test connection
    try:
        connected = await remote_sync.check_health()
        if connected:
            return TunnelResponse(
                success=True,
                message="سینک با سرور فرانسه تنظیم و متصل شد ✓"
            )
        else:
            return TunnelResponse(
                success=True,
                message="تنظیمات ذخیره شد ولی ارتباط برقرار نشد. IP/پورت/توکن رو چک کنید"
            )
    except Exception as e:
        return TunnelResponse(
            success=True,
            message=f"تنظیمات ذخیره شد ولی خطا: {str(e)}"
        )


@router.post("/sync/test", response_model=TunnelResponse)
async def test_sync_connection(
    current_admin: Admin = Depends(get_current_admin)
):
    """تست ارتباط سینک با سرور فرانسه"""
    if not remote_sync.is_enabled:
        return TunnelResponse(
            success=False,
            message="سینک تنظیم نشده. ابتدا اطلاعات سرور فرانسه رو وارد کنید"
        )
    
    try:
        connected = await remote_sync.check_health()
        if connected:
            # Get remote status too
            status_data = await remote_sync.get_status()
            return TunnelResponse(
                success=True,
                message=f"ارتباط با سرور فرانسه برقراره ✓ - سرویس OCServ: {'فعال' if status_data.get('service_active') else 'غیرفعال'}"
            )
        else:
            return TunnelResponse(
                success=False,
                message="ارتباط برقرار نشد. IP/پورت/توکن رو بررسی کنید"
            )
    except Exception as e:
        return TunnelResponse(
            success=False,
            message=f"خطا در اتصال: {str(e)}"
        )
