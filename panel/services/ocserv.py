"""
OCServ Service
سرویس ارتباط با OCServ - کنترل سرور و کاربران
"""

import asyncio
import subprocess
import re
from typing import Optional, List, Dict, Any
from config import settings
import logging

logger = logging.getLogger(__name__)


class OCServService:
    """
    سرویس ارتباط با OCServ
    کنترل سرور، مدیریت کاربران، و دریافت آمار
    """
    
    def __init__(self):
        self.occtl = settings.OCCTL_PATH
        self.ocpasswd = settings.OCPASSWD_PATH
        self.passwd_file = settings.OCSERV_PASSWD_PATH
        self.config_file = settings.OCSERV_CONFIG_PATH
    
    async def _run_command(self, cmd: List[str]) -> tuple[int, str, str]:
        """اجرای دستور و برگرداندن نتیجه"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return (
                process.returncode,
                stdout.decode('utf-8', errors='ignore'),
                stderr.decode('utf-8', errors='ignore')
            )
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return (-1, "", str(e))
    
    # ========== مدیریت کاربران ==========
    
    async def add_user(self, username: str, password: str) -> bool:
        """
        افزودن کاربر جدید به OCServ
        از ocpasswd برای مدیریت فایل رمز عبور استفاده می‌کند
        """
        try:
            # Use echo to pipe password to ocpasswd
            cmd = f'echo -e "{password}\\n{password}" | {self.ocpasswd} -c {self.passwd_file} {username}'
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"User {username} added successfully")
                return True
            else:
                logger.error(f"Failed to add user {username}: {stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"Error adding user {username}: {e}")
            return False
    
    async def delete_user(self, username: str) -> bool:
        """حذف کاربر از OCServ"""
        try:
            cmd = [self.ocpasswd, "-c", self.passwd_file, "-d", username]
            returncode, _, stderr = await self._run_command(cmd)
            
            if returncode == 0:
                logger.info(f"User {username} deleted successfully")
                return True
            else:
                logger.error(f"Failed to delete user {username}: {stderr}")
                return False
        except Exception as e:
            logger.error(f"Error deleting user {username}: {e}")
            return False
    
    async def update_password(self, username: str, new_password: str) -> bool:
        """تغییر رمز عبور کاربر"""
        # ابتدا حذف و سپس اضافه کردن مجدد
        await self.delete_user(username)
        return await self.add_user(username, new_password)
    
    async def lock_user(self, username: str) -> bool:
        """قفل کردن کاربر (غیرفعال کردن)"""
        try:
            cmd = [self.ocpasswd, "-c", self.passwd_file, "-l", username]
            returncode, _, _ = await self._run_command(cmd)
            return returncode == 0
        except Exception as e:
            logger.error(f"Error locking user {username}: {e}")
            return False
    
    async def unlock_user(self, username: str) -> bool:
        """باز کردن قفل کاربر (فعال کردن)"""
        try:
            cmd = [self.ocpasswd, "-c", self.passwd_file, "-u", username]
            returncode, _, _ = await self._run_command(cmd)
            return returncode == 0
        except Exception as e:
            logger.error(f"Error unlocking user {username}: {e}")
            return False
    
    # ========== کاربران آنلاین ==========
    
    async def get_online_users(self) -> List[Dict[str, Any]]:
        """
        دریافت لیست کاربران آنلاین
        پارس کردن خروجی occtl show users
        """
        try:
            cmd = [self.occtl, "show", "users"]
            returncode, stdout, _ = await self._run_command(cmd)
            
            if returncode != 0:
                return []
            
            users = []
            lines = stdout.strip().split('\n')
            
            # Skip header line
            for line in lines[1:]:
                if not line.strip():
                    continue
                    
                parts = line.split()
                if len(parts) >= 7:
                    user = {
                        "id": int(parts[0]) if parts[0].isdigit() else 0,
                        "username": parts[1],
                        "vpn_ip": parts[2],
                        "client_ip": parts[3],
                        "connected_at": parts[4] + " " + parts[5] if len(parts) > 5 else parts[4],
                        "user_agent": " ".join(parts[6:]) if len(parts) > 6 else "",
                        "rx": 0,  # Will be updated by traffic stats
                        "tx": 0
                    }
                    users.append(user)
            
            return users
        except Exception as e:
            logger.error(f"Error getting online users: {e}")
            return []
    
    async def disconnect_user(self, username: str) -> bool:
        """قطع اتصال کاربر"""
        try:
            cmd = [self.occtl, "disconnect", "user", username]
            returncode, _, _ = await self._run_command(cmd)
            return returncode == 0
        except Exception as e:
            logger.error(f"Error disconnecting user {username}: {e}")
            return False
    
    async def disconnect_by_id(self, session_id: int) -> bool:
        """قطع اتصال با شناسه نشست"""
        try:
            cmd = [self.occtl, "disconnect", "id", str(session_id)]
            returncode, _, _ = await self._run_command(cmd)
            return returncode == 0
        except Exception as e:
            logger.error(f"Error disconnecting session {session_id}: {e}")
            return False
    
    # ========== آمار و وضعیت ==========
    
    async def get_status(self) -> Dict[str, Any]:
        """دریافت وضعیت سرور"""
        try:
            cmd = [self.occtl, "show", "status"]
            returncode, stdout, _ = await self._run_command(cmd)
            
            if returncode != 0:
                return {"status": "error", "online": False}
            
            status = {
                "status": "running",
                "online": True,
                "raw": stdout
            }
            
            # Parse status output
            for line in stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace(' ', '_')
                    status[key] = value.strip()
            
            return status
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {"status": "error", "online": False, "error": str(e)}
    
    async def get_user_traffic(self, username: str) -> Dict[str, int]:
        """دریافت ترافیک یک کاربر خاص"""
        try:
            cmd = [self.occtl, "show", "user", username]
            returncode, stdout, _ = await self._run_command(cmd)
            
            if returncode != 0:
                return {"rx": 0, "tx": 0}
            
            rx, tx = 0, 0
            for line in stdout.split('\n'):
                if 'RX' in line:
                    match = re.search(r'(\d+)', line)
                    if match:
                        rx = int(match.group(1))
                elif 'TX' in line:
                    match = re.search(r'(\d+)', line)
                    if match:
                        tx = int(match.group(1))
            
            return {"rx": rx, "tx": tx}
        except Exception as e:
            logger.error(f"Error getting traffic for {username}: {e}")
            return {"rx": 0, "tx": 0}
    
    # ========== مدیریت سرور ==========
    
    async def reload_config(self) -> bool:
        """بارگذاری مجدد تنظیمات"""
        try:
            cmd = [self.occtl, "reload"]
            returncode, _, _ = await self._run_command(cmd)
            return returncode == 0
        except Exception as e:
            logger.error(f"Error reloading config: {e}")
            return False
    
    async def restart_service(self) -> bool:
        """راه‌اندازی مجدد سرویس"""
        try:
            cmd = ["systemctl", "restart", "ocserv"]
            returncode, _, _ = await self._run_command(cmd)
            return returncode == 0
        except Exception as e:
            logger.error(f"Error restarting service: {e}")
            return False
    
    async def stop_service(self) -> bool:
        """توقف سرویس"""
        try:
            cmd = ["systemctl", "stop", "ocserv"]
            returncode, _, _ = await self._run_command(cmd)
            return returncode == 0
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
            return False
    
    async def start_service(self) -> bool:
        """شروع سرویس"""
        try:
            cmd = ["systemctl", "start", "ocserv"]
            returncode, _, _ = await self._run_command(cmd)
            return returncode == 0
        except Exception as e:
            logger.error(f"Error starting service: {e}")
            return False
    
    # ========== تنظیمات ==========
    
    async def get_config(self) -> Dict[str, str]:
        """خواندن تنظیمات OCServ"""
        config = {}
        try:
            with open(self.config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
        except Exception as e:
            logger.error(f"Error reading config: {e}")
        return config
    
    async def update_config(self, key: str, value: str) -> bool:
        """به‌روزرسانی یک تنظیم در فایل کانفیگ"""
        try:
            with open(self.config_file, 'r') as f:
                lines = f.readlines()
            
            updated = False
            new_lines = []
            
            for line in lines:
                if line.strip().startswith(key + ' ') or line.strip().startswith(key + '='):
                    new_lines.append(f"{key} = {value}\n")
                    updated = True
                else:
                    new_lines.append(line)
            
            if not updated:
                new_lines.append(f"{key} = {value}\n")
            
            with open(self.config_file, 'w') as f:
                f.writelines(new_lines)
            
            return True
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return False


# Singleton instance
ocserv_service = OCServService()
