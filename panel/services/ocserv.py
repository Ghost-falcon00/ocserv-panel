"""
OCServ Service
سرویس ارتباط با OCServ - کنترل سرور و کاربران
با قابلیت سینک از راه دور به سرور فرانسه
"""

import asyncio
import subprocess
import re
from typing import Optional, List, Dict, Any
from config import settings
import logging

logger = logging.getLogger(__name__)

# Import remote sync (lazy load)
_remote_sync = None

def get_remote_sync():
    """Get remote sync service (lazy initialization)"""
    global _remote_sync
    if _remote_sync is None:
        try:
            from services.remote_sync import remote_sync
            _remote_sync = remote_sync
        except ImportError:
            _remote_sync = None
    return _remote_sync


class OCServService:
    """
    سرویس ارتباط با OCServ
    کنترل سرور، مدیریت کاربران، و دریافت آمار
    با قابلیت سینک خودکار به سرور فرانسه
    """
    
    def __init__(self):
        self.occtl = settings.OCCTL_PATH
        self.ocpasswd = settings.OCPASSWD_PATH
        self.passwd_file = settings.OCSERV_PASSWD_PATH
        self.config_file = settings.OCSERV_CONFIG_PATH
    
    @property
    def _sync(self):
        """دسترسی به سرویس سینک"""
        return get_remote_sync()
    
    @property
    def _sync_enabled(self) -> bool:
        """آیا سینک فعاله؟"""
        sync = self._sync
        return sync is not None and sync.is_enabled
    
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
        اگر سینک فعال باشه، روی سرور فرانسه هم ساخته میشه
        """
        try:
            import os
            cmd = [self.ocpasswd, "-c", self.passwd_file, username]
            password_input = f"{password}\n{password}\n"
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate(input=password_input.encode())
            
            local_success = process.returncode == 0
            
            if local_success:
                logger.info(f"User {username} added locally")
                
                # Sync to France server
                if self._sync_enabled:
                    try:
                        remote_ok = await self._sync.add_user(username, password)
                        if remote_ok:
                            logger.info(f"User {username} synced to France server")
                        else:
                            logger.warning(f"Failed to sync user {username} to France")
                    except Exception as e:
                        logger.warning(f"Remote sync error for {username}: {e}")
                
                return True
            else:
                logger.error(f"Failed to add user {username}: {stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"Error adding user {username}: {e}")
            return False
    
    async def delete_user(self, username: str) -> bool:
        """حذف کاربر از OCServ + سرور فرانسه"""
        try:
            cmd = [self.ocpasswd, "-c", self.passwd_file, "-d", username]
            returncode, _, stderr = await self._run_command(cmd)
            
            local_success = returncode == 0
            
            if local_success:
                logger.info(f"User {username} deleted locally")
                
                if self._sync_enabled:
                    try:
                        await self._sync.delete_user(username)
                        logger.info(f"User {username} deleted from France")
                    except Exception as e:
                        logger.warning(f"Remote delete error for {username}: {e}")
                
                return True
            else:
                logger.error(f"Failed to delete user {username}: {stderr}")
                return False
        except Exception as e:
            logger.error(f"Error deleting user {username}: {e}")
            return False
    
    async def update_password(self, username: str, new_password: str) -> bool:
        """تغییر رمز عبور کاربر + سینک"""
        await self.delete_user(username)
        return await self.add_user(username, new_password)
    
    async def lock_user(self, username: str) -> bool:
        """قفل کردن کاربر + سینک"""
        try:
            cmd = [self.ocpasswd, "-c", self.passwd_file, "-l", username]
            returncode, _, _ = await self._run_command(cmd)
            
            if returncode == 0 and self._sync_enabled:
                try:
                    await self._sync.lock_user(username)
                except Exception as e:
                    logger.warning(f"Remote lock error: {e}")
            
            return returncode == 0
        except Exception as e:
            logger.error(f"Error locking user {username}: {e}")
            return False
    
    async def unlock_user(self, username: str) -> bool:
        """باز کردن قفل کاربر + سینک"""
        try:
            cmd = [self.ocpasswd, "-c", self.passwd_file, "-u", username]
            returncode, _, _ = await self._run_command(cmd)
            
            if returncode == 0 and self._sync_enabled:
                try:
                    await self._sync.unlock_user(username)
                except Exception as e:
                    logger.warning(f"Remote unlock error: {e}")
            
            return returncode == 0
        except Exception as e:
            logger.error(f"Error unlocking user {username}: {e}")
            return False
    
    # ========== کاربران آنلاین ==========
    
    async def get_online_users(self) -> List[Dict[str, Any]]:
        """
        دریافت لیست کاربران آنلاین
        اگر سینک فعال باشه، از سرور فرانسه میخونه
        """
        # If sync enabled, get remote users (they connect to France)
        if self._sync_enabled:
            try:
                remote_users = await self._sync.get_online_users()
                if remote_users:
                    return remote_users
            except Exception as e:
                logger.warning(f"Remote get_online_users error: {e}")
        
        # Fallback to local
        try:
            cmd = [self.occtl, "show", "users"]
            returncode, stdout, _ = await self._run_command(cmd)
            
            if returncode != 0:
                return []
            
            users = []
            lines = stdout.strip().split('\n')
            
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
                        "rx": 0,
                        "tx": 0
                    }
                    users.append(user)
            
            return users
        except Exception as e:
            logger.error(f"Error getting online users: {e}")
            return []
    
    async def disconnect_user(self, username: str) -> bool:
        """قطع اتصال کاربر + سینک"""
        if self._sync_enabled:
            try:
                await self._sync.disconnect_user(username)
            except Exception as e:
                logger.warning(f"Remote disconnect error: {e}")
        
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
        """دریافت وضعیت سرور (ترکیب لوکال و ریموت)"""
        status = {"status": "running", "online": True}
        
        if self._sync_enabled:
            try:
                remote_status = await self._sync.get_status()
                status["remote"] = remote_status
                status["remote_active"] = remote_status.get("service_active", False)
            except Exception as e:
                status["remote"] = {"error": str(e)}
                status["remote_active"] = False
        
        try:
            cmd = [self.occtl, "show", "status"]
            returncode, stdout, _ = await self._run_command(cmd)
            
            if returncode != 0:
                status["status"] = "error"
                status["online"] = False
                return status
            
            status["raw"] = stdout
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
        """دریافت ترافیک کاربر (از فرانسه اگه سینک فعاله)"""
        if self._sync_enabled:
            try:
                remote_traffic = await self._sync.get_user_traffic(username)
                if remote_traffic and (remote_traffic.get("rx", 0) > 0 or remote_traffic.get("tx", 0) > 0):
                    return remote_traffic
            except Exception as e:
                logger.warning(f"Remote traffic error: {e}")
        
        try:
            cmd = [self.occtl, "show", "user", username]
            returncode, stdout, _ = await self._run_command(cmd)
            
            if returncode != 0:
                return {"rx": 0, "tx": 0}
            
            rx, tx = 0, 0
            
            for line in stdout.split('\n'):
                line = line.strip()
                if line.startswith('RX:'):
                    rx_match = re.search(r'^RX:\s*(\d+)', line)
                    if rx_match:
                        rx = int(rx_match.group(1))
                    tx_match = re.search(r'TX:\s*(\d+)', line)
                    if tx_match:
                        tx = int(tx_match.group(1))
                    break
            
            logger.debug(f"Traffic for {username}: RX={rx}, TX={tx}")
            return {"rx": rx, "tx": tx}
        except Exception as e:
            logger.error(f"Error getting traffic for {username}: {e}")
            return {"rx": 0, "tx": 0}
    
    # ========== مدیریت سرور ==========
    
    async def reload_config(self) -> bool:
        """بارگذاری مجدد تنظیمات"""
        if self._sync_enabled:
            try:
                await self._sync.reload_config()
            except:
                pass
        
        try:
            cmd = [self.occtl, "reload"]
            returncode, _, _ = await self._run_command(cmd)
            return returncode == 0
        except Exception as e:
            logger.error(f"Error reloading config: {e}")
            return False
    
    async def restart_service(self) -> bool:
        """راه‌اندازی مجدد سرویس"""
        if self._sync_enabled:
            try:
                await self._sync.restart_service()
            except:
                pass
        
        try:
            cmd = ["/usr/bin/systemctl", "restart", "ocserv"]
            returncode, _, _ = await self._run_command(cmd)
            return returncode == 0
        except Exception as e:
            logger.error(f"Error restarting service: {e}")
            return False
    
    async def stop_service(self) -> bool:
        """توقف سرویس"""
        try:
            cmd = ["/usr/bin/systemctl", "stop", "ocserv"]
            returncode, _, _ = await self._run_command(cmd)
            return returncode == 0
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
            return False
    
    async def start_service(self) -> bool:
        """شروع سرویس"""
        try:
            cmd = ["/usr/bin/systemctl", "start", "ocserv"]
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
        """به‌روزرسانی تنظیمات + سینک"""
        if self._sync_enabled:
            try:
                await self._sync.update_config(key, value)
            except:
                pass
        
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
