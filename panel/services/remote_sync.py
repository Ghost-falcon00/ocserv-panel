"""
Remote Sync Service
سرویس سینک از راه دور - ارتباط پنل ایران با OCServ فرانسه

این سرویس تمام عملیات مدیریت کاربران، ترافیک و تنظیمات را
از طریق API روی سرور فرانسه انجام می‌دهد
"""

import aiohttp
import json
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

# مسیر فایل تنظیمات سینک
SYNC_CONFIG_FILE = "/etc/ocserv-panel/remote.json"


class RemoteSyncService:
    """
    سرویس سینک از راه دور
    تمام عملیات OCServ را از طریق API فرانسه انجام می‌دهد
    """
    
    def __init__(self):
        self.config = self._load_config()
        self._session = None
    
    def _load_config(self) -> dict:
        """بارگذاری تنظیمات سینک"""
        default = {
            "enabled": False,
            "remote_ip": "",
            "remote_api_port": 6443,
            "api_token": "",
        }
        
        try:
            config_path = Path(SYNC_CONFIG_FILE)
            if config_path.exists():
                with open(config_path, 'r') as f:
                    saved = json.load(f)
                default.update(saved)
        except Exception as e:
            logger.error(f"Error loading sync config: {e}")
        
        return default
    
    def save_config(self, config: dict):
        """ذخیره تنظیمات سینک"""
        try:
            config_path = Path(SYNC_CONFIG_FILE)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            self.config = config
            logger.info("Sync config saved")
        except Exception as e:
            logger.error(f"Error saving sync config: {e}")
    
    @property
    def is_enabled(self) -> bool:
        """آیا سینک فعاله؟"""
        return bool(self.config.get("enabled") and self.config.get("remote_ip") and self.config.get("api_token"))
    
    @property
    def base_url(self) -> str:
        """URL پایه API فرانسه"""
        ip = self.config.get("remote_ip", "")
        port = self.config.get("remote_api_port", 6443)
        return f"https://{ip}:{port}"
    
    @property
    def headers(self) -> dict:
        """هدرهای احراز هویت"""
        return {
            "Authorization": f"Bearer {self.config.get('api_token', '')}",
            "Content-Type": "application/json"
        }
    
    async def _request(self, method: str, path: str, data: dict = None) -> dict:
        """ارسال درخواست به API فرانسه"""
        if not self.is_enabled:
            return {"success": False, "message": "Remote sync is not configured"}
        
        url = f"{self.base_url}{path}"
        
        try:
            async with aiohttp.ClientSession() as session:
                kwargs = {
                    "headers": self.headers,
                    "ssl": False,  # Self-signed cert
                    "timeout": aiohttp.ClientTimeout(total=10)
                }
                
                if data and method in ["POST", "PUT"]:
                    kwargs["json"] = data
                
                async with session.request(method, url, **kwargs) as resp:
                    result = await resp.json()
                    return result
        except aiohttp.ClientError as e:
            logger.error(f"Remote API request failed: {e}")
            return {"success": False, "message": f"Connection failed: {str(e)}"}
        except Exception as e:
            logger.error(f"Remote API error: {e}")
            return {"success": False, "message": str(e)}
    
    # ========== User Management ==========
    
    async def add_user(self, username: str, password: str) -> bool:
        """افزودن کاربر به سرور فرانسه"""
        result = await self._request("POST", "/api/users/add", {
            "username": username,
            "password": password
        })
        if result.get("success"):
            logger.info(f"Remote user added: {username}")
        return result.get("success", False)
    
    async def delete_user(self, username: str) -> bool:
        """حذف کاربر از سرور فرانسه"""
        result = await self._request("POST", "/api/users/delete", {
            "username": username
        })
        return result.get("success", False)
    
    async def update_password(self, username: str, new_password: str) -> bool:
        """تغییر رمز عبور در سرور فرانسه"""
        result = await self._request("POST", "/api/users/password", {
            "username": username,
            "new_password": new_password
        })
        return result.get("success", False)
    
    async def lock_user(self, username: str) -> bool:
        """قفل کردن کاربر"""
        result = await self._request("POST", "/api/users/lock", {
            "username": username
        })
        return result.get("success", False)
    
    async def unlock_user(self, username: str) -> bool:
        """باز کردن قفل کاربر"""
        result = await self._request("POST", "/api/users/unlock", {
            "username": username
        })
        return result.get("success", False)
    
    async def disconnect_user(self, username: str) -> bool:
        """قطع اتصال کاربر"""
        result = await self._request("POST", "/api/users/disconnect", {
            "username": username
        })
        return result.get("success", False)
    
    # ========== Monitoring ==========
    
    async def get_online_users(self) -> List[dict]:
        """دریافت لیست کاربران آنلاین"""
        result = await self._request("GET", "/api/users/online")
        return result.get("data", [])
    
    async def get_user_traffic(self, username: str) -> dict:
        """دریافت ترافیک یک کاربر"""
        result = await self._request("GET", f"/api/users/traffic/{username}")
        return result.get("data", {"rx": 0, "tx": 0, "total": 0})
    
    async def get_all_traffic(self) -> dict:
        """دریافت ترافیک تمام کاربران"""
        result = await self._request("GET", "/api/users/all-traffic")
        return result.get("data", {})
    
    async def get_status(self) -> dict:
        """دریافت وضعیت سرور فرانسه"""
        result = await self._request("GET", "/api/status")
        return result.get("data", {})
    
    # ========== Service Control ==========
    
    async def restart_service(self) -> bool:
        """ری‌استارت OCServ فرانسه"""
        result = await self._request("POST", "/api/service/restart")
        return result.get("success", False)
    
    async def reload_config(self) -> bool:
        """ریلود تنظیمات"""
        result = await self._request("POST", "/api/service/reload")
        return result.get("success", False)
    
    # ========== Config ==========
    
    async def get_config(self) -> dict:
        """دریافت تنظیمات OCServ فرانسه"""
        result = await self._request("GET", "/api/config")
        return result.get("data", {})
    
    async def update_config(self, key: str, value: str) -> bool:
        """به‌روزرسانی تنظیمات"""
        result = await self._request("POST", "/api/config/update", {
            "key": key,
            "value": value
        })
        return result.get("success", False)
    
    # ========== Health ==========
    
    async def check_health(self) -> bool:
        """بررسی سلامت ارتباط با فرانسه"""
        try:
            result = await self._request("GET", "/api/health")
            return result.get("status") == "ok"
        except:
            return False


# Singleton
remote_sync = RemoteSyncService()
