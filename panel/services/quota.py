"""
Quota Enforcement Service
سرویس اعمال محدودیت‌ها - با پشتیبانی از ریست خودکار
"""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import async_session
from models.user import User
from services.ocserv import ocserv_service
import logging

logger = logging.getLogger(__name__)


class QuotaService:
    """
    سرویس اعمال محدودیت‌های حجم و زمان
    شامل:
    - بررسی دوره‌ای و قطع کاربران متخلف
    - ریست خودکار حجم بر اساس دوره
    - کنترل تعداد اتصال همزمان per-user
    """
    
    BLOCKED_FILE = "/etc/ocserv/blocked_ips.txt"
    
    def __init__(self):
        self._blocked_ips = {}  # IP -> {unblock_time, username, reason}
    
    async def _temp_block_ip(self, ip: str, username: str = "", seconds: int = 86400):
        """
        بلاک موقت IP با فایل - برای OCServ connect-script
        پیشفرض: 1 روز (86400 ثانیه)
        """
        try:
            import subprocess
            
            # Add IP to blocked file (OCServ connect-script will check this)
            with open(self.BLOCKED_FILE, "a") as f:
                f.write(f"{ip}\n")
            
            # Also try iptables as backup
            cmd = f"iptables -I INPUT -s {ip} -p tcp --dport 443 -j DROP 2>/dev/null || true"
            subprocess.run(cmd, shell=True, check=False)
            
            # Kill existing connections
            kill_cmd = f"ss -K dst {ip} 2>/dev/null || true"
            subprocess.run(kill_cmd, shell=True, check=False)
            
            logger.info(f"Blocked IP {ip} for {seconds} seconds (user: {username})")
            
            # Store block info
            self._blocked_ips[ip] = {
                "unblock_time": datetime.now() + timedelta(seconds=seconds),
                "blocked_at": datetime.now(),
                "username": username,
                "reason": "excess_connections"
            }
            
            # Schedule unblock
            asyncio.create_task(self._unblock_ip_later(ip, seconds))
            
        except Exception as e:
            logger.error(f"Error blocking IP {ip}: {e}")
    
    async def _unblock_ip_later(self, ip: str, seconds: int):
        """رفع بلاک IP بعد از مدت مشخص"""
        await asyncio.sleep(seconds)
        await self.unblock_ip(ip)
    
    async def _unlock_user_later(self, username: str, seconds: int):
        """آنلاک کاربر بعد از مدت مشخص"""
        await asyncio.sleep(seconds)
        try:
            await ocserv_service.unlock_user(username)
            logger.info(f"Auto-unlocked user {username} after {seconds} seconds")
        except Exception as e:
            logger.error(f"Error unlocking user {username}: {e}")
    
    async def unblock_ip(self, ip: str) -> bool:
        """رفع بلاک IP - دستی یا خودکار"""
        try:
            import subprocess
            
            # Remove IP from blocked file
            try:
                with open(self.BLOCKED_FILE, "r") as f:
                    lines = f.readlines()
                with open(self.BLOCKED_FILE, "w") as f:
                    for line in lines:
                        if line.strip() != ip:
                            f.write(line)
            except FileNotFoundError:
                pass
            
            # Remove iptables rule as backup
            cmd = f"iptables -D INPUT -s {ip} -p tcp --dport 443 -j DROP 2>/dev/null || true"
            subprocess.run(cmd, shell=True, check=False)
            
            if ip in self._blocked_ips:
                del self._blocked_ips[ip]
            
            logger.info(f"Unblocked IP {ip}")
            return True
        except Exception as e:
            logger.error(f"Error unblocking IP {ip}: {e}")
            return False
    
    def get_blocked_ips(self) -> list:
        """دریافت لیست IP های بلاک شده"""
        result = []
        now = datetime.now()
        
        for ip, info in list(self._blocked_ips.items()):
            # Check if still blocked
            if info["unblock_time"] > now:
                remaining = (info["unblock_time"] - now).total_seconds()
                result.append({
                    "ip": ip,
                    "username": info.get("username", ""),
                    "blocked_at": info.get("blocked_at", now).isoformat(),
                    "unblock_time": info["unblock_time"].isoformat(),
                    "remaining_seconds": int(remaining),
                    "reason": info.get("reason", "")
                })
            else:
                # Expired, remove from dict
                del self._blocked_ips[ip]
        
        return result
    
    async def check_quotas(self):
        """بررسی محدودیت‌های تمام کاربران"""
        async with async_session() as session:
            try:
                # Get all active users
                result = await session.execute(
                    select(User).where(User.is_active == True)
                )
                users = result.scalars().all()
                
                now = datetime.now()
                
                for user in users:
                    # ═══════════════════════════════════════════════════════════
                    # بررسی ریست خودکار حجم
                    # ═══════════════════════════════════════════════════════════
                    if user.needs_traffic_reset:
                        user.reset_traffic()
                        logger.info(f"Auto-reset traffic for user {user.username}")
                        # اگر قبلاً غیرفعال شده بود، فعال کن
                        if not user.is_active:
                            user.is_active = True
                            await ocserv_service.unlock_user(user.username)
                    
                    # ═══════════════════════════════════════════════════════════
                    # بررسی محدودیت‌ها
                    # ═══════════════════════════════════════════════════════════
                    should_disconnect = False
                    reason = ""
                    
                    # Check traffic quota
                    if user.is_traffic_exceeded:
                        should_disconnect = True
                        reason = "traffic_exceeded"
                        user.is_active = False
                        logger.info(f"User {user.username} exceeded traffic quota")
                    
                    # Check expiry date
                    elif user.is_expired:
                        should_disconnect = True
                        reason = "expired"
                        user.is_active = False
                        logger.info(f"User {user.username} account expired")
                    
                    # Disconnect if needed
                    if should_disconnect and user.is_online:
                        await ocserv_service.disconnect_user(user.username)
                        await ocserv_service.lock_user(user.username)
                        logger.info(f"Disconnected and locked user {user.username}: {reason}")
                
                await session.commit()
                
            except Exception as e:
                logger.error(f"Error checking quotas: {e}")
                await session.rollback()
    
    async def check_connection_limits(self):
        """
        بررسی محدودیت تعداد اتصال همزمان هر کاربر
        قطع اتصالات اضافی
        """
        async with async_session() as session:
            try:
                # Get online users from OCServ
                online_users = await ocserv_service.get_online_users()
                
                # Group connections by username
                user_connections = {}
                for conn in online_users:
                    username = conn.get("username")
                    if username not in user_connections:
                        user_connections[username] = []
                    user_connections[username].append(conn)
                
                # Check each user's connection count
                for username, connections in user_connections.items():
                    # Handle (none) or stuck sessions specially
                    if username == "(none)":
                        from datetime import datetime
                        current_time = datetime.now()
                        for conn in connections:
                            # Try to parse connection time
                            try:
                                conn_time_str = conn.get("connected_at", "")
                                if conn_time_str:
                                    conn_time = datetime.strptime(conn_time_str, "%Y-%m-%d %H:%M:%S")
                                    # If connected for more than 2 minutes and still (none), kill it
                                    if (current_time - conn_time).total_seconds() > 120:
                                        conn_id = conn.get("id")
                                        if conn_id:
                                            await ocserv_service.disconnect_by_id(conn_id)
                                            logger.info(f"Killed stuck (none) session {conn_id}")
                            except Exception as e:
                                logger.error(f"Error checking stuck session: {e}")
                        continue

                    result = await session.execute(
                        select(User).where(User.username == username)
                    )
                    user = result.scalar_one_or_none()
                    
                    if user and len(connections) > user.max_connections:
                        # Sort connections by ID (higher ID = newer connection)
                        sorted_connections = sorted(connections, key=lambda x: x.get("id", 0))
                        
                        # قطع اتصالات جدید (آخرین‌ها) - نه قدیمی‌ها
                        excess_count = len(connections) - user.max_connections
                        
                        # -------------------------------------------------------------
                        # FIX ZOMBIE ISSUE:
                        # If the newest connection is very new (< 10s) and oldest is very old,
                        # the user might be trying to reconnect while the old one is stuck.
                        # Ideally OCServ DPD handles this, but if not, logic "Disconnect Newest"
                        # prevents reconnection.
                        # -------------------------------------------------------------
                        
                        # Take the LAST (newest) connections to disconnect
                        connections_to_disconnect = sorted_connections[-excess_count:]
                        
                        for conn in connections_to_disconnect:
                            conn_id = conn.get("id")
                            client_ip = conn.get("client_ip")
                            
                            if conn_id:
                                # Disconnect only this specific session
                                success = await ocserv_service.disconnect_by_id(conn_id)
                                if success:
                                    logger.info(f"Disconnected NEWEST session {conn_id} for {username}")
                                    
                                    # Block the IP of this NEW connection for 1 day
                                    if client_ip:
                                        await self._temp_block_ip(client_ip, username, 86400)
                        
                        logger.warning(
                            f"User {username} had {len(connections)} connections, "
                            f"max allowed is {user.max_connections}. Disconnected {excess_count} newest."
                        )
                
            except Exception as e:
                logger.error(f"Error checking connection limits: {e}")
    
    async def reset_user_quota(
        self, 
        session: AsyncSession, 
        user_id: int, 
        new_traffic: int = None
    ) -> bool:
        """
        ریست کردن حجم کاربر
        new_traffic: حجم جدید (bytes) - None = حفظ محدودیت فعلی
        """
        try:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            # استفاده از متد مدل
            user.reset_traffic()
            
            if new_traffic is not None:
                user.max_traffic = new_traffic
            
            user.is_active = True
            
            # Unlock in OCServ
            await ocserv_service.unlock_user(user.username)
            
            await session.commit()
            logger.info(f"Reset quota for user {user.username}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting quota: {e}")
            await session.rollback()
            return False
    
    async def extend_user_expiry(
        self, 
        session: AsyncSession, 
        user_id: int, 
        days: int = None,
        new_expire_date: datetime = None
    ) -> bool:
        """
        تمدید تاریخ انقضای کاربر
        days: تعداد روز اضافه
        new_expire_date: تاریخ جدید (اگر days نباشد)
        """
        try:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            if days:
                user.extend_days(days)
            elif new_expire_date:
                user.expire_date = new_expire_date
            
            user.is_active = True
            
            # Unlock in OCServ
            await ocserv_service.unlock_user(user.username)
            
            await session.commit()
            logger.info(f"Extended expiry for user {user.username}")
            return True
            
        except Exception as e:
            logger.error(f"Error extending expiry: {e}")
            await session.rollback()
            return False
    
    async def get_users_near_limit(
        self, 
        session: AsyncSession, 
        traffic_threshold: float = 0.8,
        days_threshold: int = 3
    ) -> list:
        """
        دریافت کاربرانی که به محدودیت نزدیک هستند
        traffic_threshold: آستانه حجم (0.8 = 80%)
        days_threshold: آستانه روز تا انقضا
        """
        try:
            result = await session.execute(
                select(User).where(User.is_active == True)
            )
            users = result.scalars().all()
            
            alerts = []
            
            for user in users:
                # Check traffic
                if user.max_traffic > 0:
                    percent = user.used_traffic / user.max_traffic
                    if percent >= traffic_threshold:
                        alerts.append({
                            "username": user.username,
                            "user_id": user.id,
                            "type": "traffic",
                            "severity": "critical" if percent >= 0.95 else "warning",
                            "message": f"ترافیک: {percent*100:.1f}% مصرف شده",
                            "percent": percent * 100
                        })
                
                # Check expiry
                if user.expire_date:
                    days_left = (user.expire_date - datetime.now()).days
                    if 0 < days_left <= days_threshold:
                        alerts.append({
                            "username": user.username,
                            "user_id": user.id,
                            "type": "expiry",
                            "severity": "critical" if days_left <= 1 else "warning",
                            "message": f"انقضا: {days_left} روز باقی‌مانده",
                            "days_left": days_left
                        })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting users near limit: {e}")
            return []
    
    async def get_quota_stats(self, session: AsyncSession) -> dict:
        """آمار کلی محدودیت‌ها"""
        try:
            result = await session.execute(select(User))
            users = result.scalars().all()
            
            total = len(users)
            expired = sum(1 for u in users if u.is_expired)
            traffic_exceeded = sum(1 for u in users if u.is_traffic_exceeded)
            active = sum(1 for u in users if u.can_connect)
            online = sum(1 for u in users if u.is_online)
            
            return {
                "total_users": total,
                "active_users": active,
                "online_users": online,
                "expired_users": expired,
                "traffic_exceeded_users": traffic_exceeded,
                "inactive_users": total - active
            }
            
        except Exception as e:
            logger.error(f"Error getting quota stats: {e}")
            return {}


# Singleton instance
quota_service = QuotaService()
