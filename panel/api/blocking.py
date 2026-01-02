"""
Blocking API
مسیرهای API مسدودسازی محتوا
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from services.blocking import blocking_service
from api.auth import get_current_admin

router = APIRouter(prefix="/api/blocking", tags=["blocking"])


# ═══════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════

class ToggleCategoryRequest(BaseModel):
    enabled: bool


class DomainRequest(BaseModel):
    domain: str


class BlockingStatus(BaseModel):
    categories: dict
    total_blocked: int
    custom_domains: List[str]
    whitelist: List[str]
    last_update: Optional[str]


# ═══════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════

@router.get("/status")
async def get_blocking_status(admin = Depends(get_current_admin)):
    """دریافت وضعیت مسدودسازی"""
    status = await blocking_service.get_status()
    return status


@router.post("/category/{category}")
async def toggle_category(
    category: str, 
    request: ToggleCategoryRequest,
    admin = Depends(get_current_admin)
):
    """فعال/غیرفعال کردن یک دسته بلاک"""
    valid_categories = ["ads", "porn", "gambling", "malware", "social"]
    
    if category not in valid_categories:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid category. Valid: {valid_categories}"
        )
    
    success = await blocking_service.toggle_category(category, request.enabled)
    
    if success:
        return {
            "success": True,
            "message": f"{'فعال' if request.enabled else 'غیرفعال'} شد: {category}",
            "category": category,
            "enabled": request.enabled
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to toggle category")


@router.post("/update")
async def update_blocklists(admin = Depends(get_current_admin)):
    """بروزرسانی دستی بلاک‌لیست‌ها"""
    success = await blocking_service.update_blocklists()
    
    if success:
        status = await blocking_service.get_status()
        return {
            "success": True,
            "message": "بلاک‌لیست‌ها بروزرسانی شدند",
            "total_blocked": status.get("total_blocked", 0)
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to update blocklists")


@router.post("/custom")
async def add_custom_domain(
    request: DomainRequest,
    admin = Depends(get_current_admin)
):
    """اضافه کردن دامنه سفارشی به بلاک‌لیست"""
    success = await blocking_service.add_custom_domain(request.domain)
    
    if success:
        return {
            "success": True,
            "message": f"دامنه {request.domain} به بلاک‌لیست اضافه شد"
        }
    else:
        return {
            "success": False,
            "message": "دامنه قبلاً در لیست موجود است"
        }


@router.delete("/custom/{domain}")
async def remove_custom_domain(
    domain: str,
    admin = Depends(get_current_admin)
):
    """حذف دامنه سفارشی از بلاک‌لیست"""
    success = await blocking_service.remove_custom_domain(domain)
    
    if success:
        return {
            "success": True,
            "message": f"دامنه {domain} از بلاک‌لیست حذف شد"
        }
    else:
        raise HTTPException(status_code=404, detail="Domain not found")


@router.post("/whitelist")
async def add_whitelist_domain(
    request: DomainRequest,
    admin = Depends(get_current_admin)
):
    """اضافه کردن دامنه به لیست سفید (استثنا)"""
    success = await blocking_service.add_whitelist(request.domain)
    
    if success:
        return {
            "success": True,
            "message": f"دامنه {request.domain} به لیست سفید اضافه شد"
        }
    else:
        return {
            "success": False,
            "message": "دامنه قبلاً در لیست موجود است"
        }


@router.delete("/whitelist/{domain}")
async def remove_whitelist_domain(
    domain: str,
    admin = Depends(get_current_admin)
):
    """حذف دامنه از لیست سفید"""
    await blocking_service.load_settings()
    
    whitelist = blocking_service.settings.get("whitelist", [])
    if domain in whitelist:
        whitelist.remove(domain)
        await blocking_service.save_settings()
        await blocking_service.update_blocklists()
        return {"success": True, "message": f"دامنه {domain} از لیست سفید حذف شد"}
    
    raise HTTPException(status_code=404, detail="Domain not found in whitelist")


@router.get("/search")
async def search_blocked_domains(
    q: str,
    admin = Depends(get_current_admin)
):
    """جستجو در دامنه‌های بلاک شده"""
    if len(q) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")
    
    # Load blocklist if empty
    if not blocking_service.blocked_domains:
        await blocking_service.update_blocklists()
    
    results = await blocking_service.search_blocked(q)
    return {
        "query": q,
        "count": len(results),
        "domains": results
    }
