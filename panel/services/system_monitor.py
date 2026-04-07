"""
System Monitor Service
مانیتورینگ منابع سرور (CPU, RAM, Disk)
"""
import psutil
import logging
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from models.system_metric import SystemMetric

logger = logging.getLogger(__name__)

class SystemMonitorService:
    async def collect_metrics(self, session: AsyncSession):
        """جمع‌آوری و ذخیره متریک‌های فعلی"""
        try:
            # CPU (interval 0.1 to get actual usage instead of since last call globally)
            cpu = psutil.cpu_percent(interval=0.1)
            
            # RAM
            mem = psutil.virtual_memory()
            ram = mem.percent
            
            # Disk (root)
            disk = psutil.disk_usage('/')
            disk_pc = disk.percent
            
            metric = SystemMetric(
                cpu_percent=cpu,
                ram_percent=ram,
                disk_percent=disk_pc
            )
            session.add(metric)
            
            # پاک کردن داده‌های قدیمی‌تر از ۲۴ ساعت برای جلوگیری از حجیم شدن دیتابیس
            cutoff = datetime.utcnow() - timedelta(hours=24)
            await session.execute(
                delete(SystemMetric).where(SystemMetric.timestamp < cutoff)
            )
            
            await session.commit()
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            await session.rollback()

    async def get_latest_metrics(self) -> dict:
        """گرفتن وضعیت لحظه‌ای برای داشبورد (خارج از DB برای سرعت بیشتر)"""
        try:
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "ram_percent": mem.percent,
                "ram_used": mem.used,
                "ram_total": mem.total,
                "disk_percent": disk.percent,
                "disk_used": disk.used,
                "disk_total": disk.total
            }
        except Exception as e:
            logger.error(f"Error reading live metrics: {e}")
            return {}

monitor_service = SystemMonitorService()
