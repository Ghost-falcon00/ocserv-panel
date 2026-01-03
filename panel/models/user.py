"""
User Model
مدل کاربر VPN - نسخه کامل با تمام امکانات تجاری
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime, timedelta


class SubscriptionPlan(Base):
    """
    پلن اشتراک
    برای تعریف پکیج‌های آماده
    """
    __tablename__ = "subscription_plans"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)  # نام پلن: مثلاً "طلایی"
    
    # محدودیت‌ها
    traffic_limit = Column(BigInteger, default=0)  # حجم (bytes) - 0 = نامحدود
    duration_days = Column(Integer, default=30)  # مدت اعتبار (روز)
    max_connections = Column(Integer, default=2)  # اتصال همزمان
    
    # قیمت (اختیاری)
    price = Column(Integer, default=0)  # تومان
    
    # ریست
    reset_period_days = Column(Integer, default=0)  # دوره ریست حجم (روز) - 0 = بدون ریست
    
    # وضعیت
    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<Plan {self.name}>"


class User(Base):
    """
    مدل کاربر VPN
    شامل اطلاعات کاربر، محدودیت حجم و زمان، دوره ریست
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # ═══════════════════════════════════════════════════════════
    # اطلاعات کاربری
    # ═══════════════════════════════════════════════════════════
    username = Column(String(50), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)  # Plain text for ocpasswd
    
    # ═══════════════════════════════════════════════════════════
    # پلن اشتراک (اختیاری)
    # ═══════════════════════════════════════════════════════════
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=True)
    
    # ═══════════════════════════════════════════════════════════
    # محدودیت حجم
    # ═══════════════════════════════════════════════════════════
    max_traffic = Column(BigInteger, default=0)  # حداکثر ترافیک (bytes) - 0 = نامحدود
    used_traffic = Column(BigInteger, default=0)  # ترافیک مصرف شده (bytes)
    
    # دوره ریست حجم
    reset_period_days = Column(Integer, default=0)  # مثلاً 30 = ماهانه - 0 = بدون ریست
    last_reset_date = Column(DateTime, nullable=True)  # آخرین ریست
    
    # ═══════════════════════════════════════════════════════════
    # محدودیت زمان
    # ═══════════════════════════════════════════════════════════
    expire_days = Column(Integer, default=0)  # مدت اعتبار (روز) - 0 = نامحدود
    expire_date = Column(DateTime, nullable=True)  # تاریخ انقضا - محاسبه شده از اولین اتصال
    start_date = Column(DateTime, server_default=func.now())  # تاریخ شروع
    first_connection = Column(DateTime, nullable=True)  # اولین اتصال - برای محاسبه انقضا
    
    # ═══════════════════════════════════════════════════════════
    # محدودیت اتصال - PER USER
    # ═══════════════════════════════════════════════════════════
    max_connections = Column(Integer, default=2)  # حداکثر اتصال همزمان برای این کاربر
    
    # ═══════════════════════════════════════════════════════════
    # وضعیت
    # ═══════════════════════════════════════════════════════════
    is_active = Column(Boolean, default=True)
    is_online = Column(Boolean, default=False)
    current_connections = Column(Integer, default=0)  # اتصالات فعلی
    
    # ═══════════════════════════════════════════════════════════
    # اطلاعات اضافی
    # ═══════════════════════════════════════════════════════════
    note = Column(Text, nullable=True)  # یادداشت
    telegram_id = Column(BigInteger, nullable=True)  # برای ربات تلگرام
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    
    # ═══════════════════════════════════════════════════════════
    # تاریخ‌ها
    # ═══════════════════════════════════════════════════════════
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_connection = Column(DateTime, nullable=True)
    
    # ═══════════════════════════════════════════════════════════
    # آمار
    # ═══════════════════════════════════════════════════════════
    total_connections = Column(Integer, default=0)  # تعداد کل اتصالات
    total_traffic_all_time = Column(BigInteger, default=0)  # کل ترافیک از ابتدا
    
    def __repr__(self):
        return f"<User {self.username}>"
    
    # ═══════════════════════════════════════════════════════════
    # Properties - محاسبات
    # ═══════════════════════════════════════════════════════════
    
    @property
    def traffic_remaining(self) -> int:
        """ترافیک باقی‌مانده (bytes)"""
        if self.max_traffic == 0:
            return -1  # نامحدود
        return max(0, self.max_traffic - self.used_traffic)
    
    @property
    def traffic_percent(self) -> float:
        """درصد ترافیک مصرف شده"""
        if self.max_traffic == 0:
            return 0
        return min(100, (self.used_traffic / self.max_traffic) * 100)
    
    @property
    def is_expired(self) -> bool:
        """آیا کاربر منقضی شده؟"""
        if self.expire_date is None:
            return False
        return datetime.now() > self.expire_date
    
    @property
    def is_traffic_exceeded(self) -> bool:
        """آیا ترافیک تمام شده؟"""
        if self.max_traffic == 0:
            return False
        return self.used_traffic >= self.max_traffic
    
    @property
    def days_remaining(self) -> int:
        """روزهای باقی‌مانده تا انقضا"""
        if self.expire_date is None:
            return -1  # نامحدود
        delta = self.expire_date - datetime.now()
        return max(0, delta.days)
    
    @property
    def needs_traffic_reset(self) -> bool:
        """آیا نیاز به ریست حجم دارد؟"""
        if self.reset_period_days <= 0:
            return False
        if self.last_reset_date is None:
            return True
        next_reset = self.last_reset_date + timedelta(days=self.reset_period_days)
        return datetime.now() >= next_reset
    
    @property
    def next_reset_date(self) -> datetime:
        """تاریخ ریست بعدی"""
        if self.reset_period_days <= 0:
            return None
        if self.last_reset_date is None:
            return datetime.now()
        return self.last_reset_date + timedelta(days=self.reset_period_days)
    
    @property
    def can_connect(self) -> bool:
        """آیا کاربر می‌تواند متصل شود؟"""
        return (
            self.is_active and 
            not self.is_expired and 
            not self.is_traffic_exceeded
        )
    
    @property
    def connection_slots_available(self) -> int:
        """تعداد اسلات اتصال باقی‌مانده"""
        return max(0, self.max_connections - self.current_connections)
    
    @property
    def can_add_connection(self) -> bool:
        """آیا اتصال جدید مجاز است؟"""
        return (
            self.can_connect and 
            self.current_connections < self.max_connections
        )
    
    # ═══════════════════════════════════════════════════════════
    # Methods - عملیات
    # ═══════════════════════════════════════════════════════════
    
    def reset_traffic(self):
        """ریست حجم مصرفی"""
        self.used_traffic = 0
        self.last_reset_date = datetime.now()
    
    def extend_days(self, days: int):
        """تمدید به تعداد روز"""
        if self.expire_date is None or self.expire_date < datetime.now():
            self.expire_date = datetime.now() + timedelta(days=days)
        else:
            self.expire_date = self.expire_date + timedelta(days=days)
    
    def apply_plan(self, plan: SubscriptionPlan):
        """اعمال پلن اشتراک"""
        self.plan_id = plan.id
        self.max_traffic = plan.traffic_limit
        self.max_connections = plan.max_connections
        self.reset_period_days = plan.reset_period_days
        self.expire_date = datetime.now() + timedelta(days=plan.duration_days)
        self.used_traffic = 0
        self.last_reset_date = datetime.now()
        self.is_active = True
    
    def to_dict(self) -> dict:
        """تبدیل به دیکشنری برای API"""
        return {
            "id": self.id,
            "username": self.username,
            "max_traffic": self.max_traffic,
            "used_traffic": self.used_traffic,
            "traffic_remaining": self.traffic_remaining,
            "traffic_percent": self.traffic_percent,
            "expire_date": self.expire_date.isoformat() if self.expire_date else None,
            "days_remaining": self.days_remaining,
            "max_connections": self.max_connections,
            "current_connections": self.current_connections,
            "connection_slots_available": self.connection_slots_available,
            "reset_period_days": self.reset_period_days,
            "next_reset_date": self.next_reset_date.isoformat() if self.next_reset_date else None,
            "is_active": self.is_active,
            "is_online": self.is_online,
            "is_expired": self.is_expired,
            "is_traffic_exceeded": self.is_traffic_exceeded,
            "can_connect": self.can_connect,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_connection": self.last_connection.isoformat() if self.last_connection else None,
            "total_connections": self.total_connections,
        }
