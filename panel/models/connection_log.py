"""
Connection Log Model
مدل لاگ اتصالات
"""

from sqlalchemy import Column, Integer, String, DateTime, BigInteger, ForeignKey
from sqlalchemy.sql import func
from .database import Base


class ConnectionLog(Base):
    """
    مدل لاگ اتصالات کاربران
    ثبت تمام اتصالات و قطع اتصالات
    """
    __tablename__ = "connection_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True)
    
    # اطلاعات اتصال
    client_ip = Column(String(45), nullable=True)  # IPv4/IPv6
    vpn_ip = Column(String(45), nullable=True)  # IP داخلی VPN
    device_type = Column(String(100), nullable=True)  # نوع دستگاه
    user_agent = Column(String(255), nullable=True)
    
    # زمان‌ها
    connected_at = Column(DateTime, server_default=func.now())
    disconnected_at = Column(DateTime, nullable=True)
    
    # ترافیک این اتصال
    traffic_in = Column(BigInteger, default=0)  # دانلود (bytes)
    traffic_out = Column(BigInteger, default=0)  # آپلود (bytes)
    
    # وضعیت
    disconnect_reason = Column(String(100), nullable=True)  # دلیل قطع
    
    def __repr__(self):
        return f"<ConnectionLog {self.username} @ {self.connected_at}>"
    
    @property
    def total_traffic(self) -> int:
        """مجموع ترافیک (bytes)"""
        return self.traffic_in + self.traffic_out
    
    @property
    def duration_seconds(self) -> int:
        """مدت اتصال (ثانیه)"""
        if self.disconnected_at is None:
            from datetime import datetime
            return int((datetime.now() - self.connected_at).total_seconds())
        return int((self.disconnected_at - self.connected_at).total_seconds())
