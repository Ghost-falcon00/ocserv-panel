"""
Traffic Monitoring Service
سرویس مانیتورینگ ترافیک
"""

import asyncio
from typing import Dict, Optional
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import async_session
from models.user import User
from models.connection_log import ConnectionLog
from services.ocserv import ocserv_service
import logging

logger = logging.getLogger(__name__)


class TrafficService:
    """
    سرویس مانیتورینگ ترافیک کاربران
    به‌روزرسانی دوره‌ای ترافیک مصرفی
    """
    
    def __init__(self):
        self._last_traffic: Dict[str, Dict[str, int]] = {}
        self._running = False
    
    async def update_user_traffic(self, session: AsyncSession):
        """به‌روزرسانی ترافیک تمام کاربران آنلاین و اعمال فوری محدودیت‌ها"""
        try:
            online_users = await ocserv_service.get_online_users()
            
            for online_user in online_users:
                username = online_user['username']
                
                # Get user from database
                result = await session.execute(
                    select(User).where(User.username == username)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    continue
                
                # Get detailed traffic for this user
                traffic = await ocserv_service.get_user_traffic(username)
                current_rx = traffic['rx']
                current_tx = traffic['tx']
                
                # Calculate delta from last check
                last = self._last_traffic.get(username, {'rx': 0, 'tx': 0})
                delta_rx = max(0, current_rx - last['rx'])
                delta_tx = max(0, current_tx - last['tx'])
                delta_total = delta_rx + delta_tx
                
                if delta_total > 0:
                    # Update user's used_traffic
                    user.used_traffic += delta_total
                    user.is_online = True
                    user.current_connections = 1
                    
                    logger.debug(f"Traffic {username}: +{delta_total} bytes, total: {user.used_traffic}")
                    
                    # ═══════════════════════════════════════════════════════════
                    # فوری: چک محدودیت و قطع کاربر اگه رد کرده
                    # ═══════════════════════════════════════════════════════════
                    if user.max_traffic > 0 and user.used_traffic >= user.max_traffic:
                        logger.warning(f"User {username} EXCEEDED traffic limit! Disconnecting...")
                        await ocserv_service.disconnect_user(username)
                        await ocserv_service.lock_user(username)
                        user.is_active = False
                        user.is_online = False
                        user.current_connections = 0
                        logger.info(f"User {username} disconnected and locked - traffic exceeded")
                
                # Save current values for next check
                self._last_traffic[username] = {'rx': current_rx, 'tx': current_tx}
            
            # Mark offline users
            online_usernames = [u['username'] for u in online_users]
            stmt = (
                update(User)
                .where(User.is_online == True)
                .where(User.username.notin_(online_usernames) if online_usernames else True)
                .values(is_online=False, current_connections=0)
            )
            await session.execute(stmt)
            
            # Remove offline users from tracking
            self._last_traffic = {
                k: v for k, v in self._last_traffic.items() 
                if k in online_usernames
            }
            
            await session.commit()
            
        except Exception as e:
            logger.error(f"Error updating traffic: {e}")
            await session.rollback()
    
    async def log_connection(
        self,
        session: AsyncSession,
        username: str,
        client_ip: str,
        vpn_ip: str,
        user_agent: str = ""
    ):
        """ثبت لاگ اتصال جدید"""
        try:
            # Get user ID
            result = await session.execute(
                select(User).where(User.username == username)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"Unknown user connected: {username}")
                return
            
            # Create connection log
            log = ConnectionLog(
                user_id=user.id,
                username=username,
                client_ip=client_ip,
                vpn_ip=vpn_ip,
                user_agent=user_agent,
                connected_at=datetime.now()
            )
            session.add(log)
            
            # Update user stats
            user.last_connection = datetime.now()
            user.total_connections += 1
            user.is_online = True
            user.current_connections += 1
            
            await session.commit()
            logger.info(f"Logged connection for {username} from {client_ip}")
            
        except Exception as e:
            logger.error(f"Error logging connection: {e}")
            await session.rollback()
    
    async def log_disconnection(
        self,
        session: AsyncSession,
        username: str,
        reason: str = "",
        traffic_in: int = 0,
        traffic_out: int = 0
    ):
        """ثبت لاگ قطع اتصال"""
        try:
            # Find the active connection log
            result = await session.execute(
                select(ConnectionLog)
                .where(ConnectionLog.username == username)
                .where(ConnectionLog.disconnected_at == None)
                .order_by(ConnectionLog.connected_at.desc())
            )
            log = result.scalar_one_or_none()
            
            if log:
                log.disconnected_at = datetime.now()
                log.disconnect_reason = reason
                log.traffic_in = traffic_in
                log.traffic_out = traffic_out
            
            # Update user online status
            stmt = (
                update(User)
                .where(User.username == username)
                .values(
                    current_connections=User.current_connections - 1,
                    is_online=False
                )
            )
            await session.execute(stmt)
            
            await session.commit()
            logger.info(f"Logged disconnection for {username}: {reason}")
            
        except Exception as e:
            logger.error(f"Error logging disconnection: {e}")
            await session.rollback()
    
    async def get_daily_traffic(self, session: AsyncSession) -> Dict[str, int]:
        """دریافت ترافیک امروز"""
        from datetime import date
        today = date.today()
        
        result = await session.execute(
            select(ConnectionLog)
            .where(ConnectionLog.connected_at >= datetime.combine(today, datetime.min.time()))
        )
        logs = result.scalars().all()
        
        total_in = sum(log.traffic_in for log in logs)
        total_out = sum(log.traffic_out for log in logs)
        
        return {"in": total_in, "out": total_out, "total": total_in + total_out}


# Singleton instance
traffic_service = TrafficService()
