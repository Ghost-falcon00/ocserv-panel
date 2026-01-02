"""
Routes API
مدیریت روت‌های VPN
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import aiofiles
import os
import re
from api.auth import get_current_admin
from services.ocserv import ocserv_service

router = APIRouter(prefix="/api/routes", tags=["routes"])


# ═══════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════

class RouteItem(BaseModel):
    network: str  # مثال: 192.168.1.0/24 یا 192.168.1.0
    netmask: Optional[str] = None  # مثال: 255.255.255.0
    type: str = "route"  # route یا no-route


class RouteListResponse(BaseModel):
    routes: List[RouteItem]
    no_routes: List[RouteItem]


# ═══════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════

OCSERV_CONFIG = "/etc/ocserv/ocserv.conf"


async def read_current_routes() -> dict:
    """خواندن روت‌های فعلی از کانفیگ"""
    routes = []
    no_routes = []
    
    try:
        async with aiofiles.open(OCSERV_CONFIG, 'r') as f:
            content = await f.read()
            
            for line in content.split('\n'):
                line = line.strip()
                
                if line.startswith('route = '):
                    value = line.replace('route = ', '').strip()
                    routes.append(parse_route(value, "route"))
                    
                elif line.startswith('no-route = '):
                    value = line.replace('no-route = ', '').strip()
                    no_routes.append(parse_route(value, "no-route"))
    
    except FileNotFoundError:
        pass
    
    return {"routes": routes, "no_routes": no_routes}


def parse_route(value: str, route_type: str) -> dict:
    """پارس کردن یک خط روت"""
    # Format: network/mask or network/netmask
    parts = value.split('/')
    network = parts[0]
    
    netmask = None
    if len(parts) > 1:
        netmask = parts[1]
    
    return {
        "network": network,
        "netmask": netmask,
        "type": route_type
    }


def format_route(route: dict) -> str:
    """فرمت کردن روت برای کانفیگ"""
    if route.get("netmask"):
        return f"{route['network']}/{route['netmask']}"
    return route['network']


async def update_config_routes(routes: list, no_routes: list) -> bool:
    """بروزرسانی روت‌ها در کانفیگ"""
    try:
        async with aiofiles.open(OCSERV_CONFIG, 'r') as f:
            lines = (await f.read()).split('\n')
        
        # حذف روت‌های قبلی
        new_lines = [
            line for line in lines 
            if not line.strip().startswith('route = ') 
            and not line.strip().startswith('no-route = ')
        ]
        
        # اضافه کردن روت‌های جدید
        new_lines.append('')
        new_lines.append('# Routes')
        for route in routes:
            new_lines.append(f"route = {format_route(route)}")
        
        new_lines.append('')
        new_lines.append('# No-Routes (bypass VPN)')
        for route in no_routes:
            new_lines.append(f"no-route = {format_route(route)}")
        
        async with aiofiles.open(OCSERV_CONFIG, 'w') as f:
            await f.write('\n'.join(new_lines))
        
        return True
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def validate_network(network: str) -> bool:
    """اعتبارسنجی آدرس شبکه"""
    # IPv4 pattern
    ipv4 = r'^(\d{1,3}\.){3}\d{1,3}$'
    # CIDR pattern
    cidr = r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$'
    # Network/Netmask pattern
    netmask = r'^(\d{1,3}\.){3}\d{1,3}/(\d{1,3}\.){3}\d{1,3}$'
    
    if network == 'default':
        return True
    
    return bool(
        re.match(ipv4, network) or 
        re.match(cidr, network) or
        re.match(netmask, network)
    )


# ═══════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════

@router.get("")
async def get_routes(admin = Depends(get_current_admin)):
    """دریافت لیست تمام روت‌ها"""
    routes_data = await read_current_routes()
    return routes_data


@router.post("/route")
async def add_route(
    route: RouteItem,
    admin = Depends(get_current_admin)
):
    """اضافه کردن روت جدید"""
    if not validate_network(f"{route.network}/{route.netmask}" if route.netmask else route.network):
        raise HTTPException(status_code=400, detail="Invalid network format")
    
    current = await read_current_routes()
    
    new_route = {
        "network": route.network,
        "netmask": route.netmask,
        "type": route.type
    }
    
    if route.type == "route":
        current["routes"].append(new_route)
    else:
        current["no_routes"].append(new_route)
    
    await update_config_routes(current["routes"], current["no_routes"])
    
    return {
        "success": True,
        "message": f"روت {route.network} اضافه شد",
        "note": "برای اعمال تغییرات، سرور را restart کنید"
    }


@router.delete("/route")
async def remove_route(
    network: str,
    route_type: str = "route",
    admin = Depends(get_current_admin)
):
    """حذف یک روت"""
    current = await read_current_routes()
    
    if route_type == "route":
        current["routes"] = [r for r in current["routes"] if r["network"] != network]
    else:
        current["no_routes"] = [r for r in current["no_routes"] if r["network"] != network]
    
    await update_config_routes(current["routes"], current["no_routes"])
    
    return {
        "success": True,
        "message": f"روت {network} حذف شد",
        "note": "برای اعمال تغییرات، سرور را restart کنید"
    }


@router.put("/bulk")
async def update_all_routes(
    routes: List[RouteItem],
    admin = Depends(get_current_admin)
):
    """بروزرسانی تمام روت‌ها یکجا"""
    route_list = []
    no_route_list = []
    
    for r in routes:
        if not validate_network(f"{r.network}/{r.netmask}" if r.netmask else r.network):
            raise HTTPException(status_code=400, detail=f"Invalid network: {r.network}")
        
        route_dict = {
            "network": r.network,
            "netmask": r.netmask,
            "type": r.type
        }
        
        if r.type == "route":
            route_list.append(route_dict)
        else:
            no_route_list.append(route_dict)
    
    await update_config_routes(route_list, no_route_list)
    
    return {
        "success": True,
        "message": f"تعداد {len(route_list)} route و {len(no_route_list)} no-route ذخیره شد",
        "note": "برای اعمال تغییرات، سرور را restart کنید"
    }


@router.post("/apply")
async def apply_route_changes(admin = Depends(get_current_admin)):
    """اعمال تغییرات روت‌ها با restart سرور"""
    success = await ocserv_service.restart_server()
    
    if success:
        return {
            "success": True,
            "message": "تغییرات اعمال شد و سرور restart شد"
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to restart server")


# ═══════════════════════════════════════════════════════════
# Iranian Routes Presets
# ═══════════════════════════════════════════════════════════

IRAN_IP_RANGES = [
    "2.144.0.0/255.254.0.0",
    "5.22.0.0/255.255.0.0",
    "5.23.0.0/255.255.0.0",
    "5.52.0.0/255.252.0.0",
    "5.56.0.0/255.248.0.0",
    "5.74.0.0/255.254.0.0",
    "5.106.0.0/255.255.0.0",
    "5.112.0.0/255.248.0.0",
    "5.120.0.0/255.248.0.0",
    "5.144.0.0/255.240.0.0",
    "5.160.0.0/255.224.0.0",
    "5.190.0.0/255.254.0.0",
    "5.198.0.0/255.254.0.0",
    "5.200.0.0/255.248.0.0",
    "31.2.0.0/255.254.0.0",
    "31.7.64.0/255.255.192.0",
    "31.14.0.0/255.254.0.0",
    "31.24.0.0/255.248.0.0",
    "31.40.0.0/255.248.0.0",
    "31.56.0.0/255.248.0.0",
    "31.130.0.0/255.254.0.0",
    "31.170.0.0/255.254.0.0",
    "31.193.192.0/255.255.192.0",
    "37.9.0.0/255.255.0.0",
    "37.32.0.0/255.224.0.0",
    "37.63.0.0/255.255.0.0",
    "37.75.0.0/255.255.0.0",
    "37.98.0.0/255.254.0.0",
    "37.114.0.0/255.254.0.0",
    "37.129.0.0/255.255.0.0",
    "37.143.0.0/255.255.0.0",
    "37.152.0.0/255.248.0.0",
    "37.191.0.0/255.255.0.0",
    "37.202.0.0/255.254.0.0",
    "37.228.0.0/255.252.0.0",
    "37.235.0.0/255.255.0.0",
]


@router.post("/preset/iran")
async def apply_iran_preset(admin = Depends(get_current_admin)):
    """اعمال پریست IP های ایران (bypass VPN)"""
    current = await read_current_routes()
    
    # اضافه کردن IP های ایران به no-route
    for ip_range in IRAN_IP_RANGES:
        parts = ip_range.split('/')
        new_route = {
            "network": parts[0],
            "netmask": parts[1] if len(parts) > 1 else None,
            "type": "no-route"
        }
        
        # چک وجود نداشتن
        exists = any(
            r["network"] == parts[0] 
            for r in current["no_routes"]
        )
        if not exists:
            current["no_routes"].append(new_route)
    
    await update_config_routes(current["routes"], current["no_routes"])
    
    return {
        "success": True,
        "message": f"تعداد {len(IRAN_IP_RANGES)} IP رنج ایرانی اضافه شد",
        "note": "این IP ها از VPN bypass میشن برای سرعت بالاتر سایت‌های داخلی"
    }
