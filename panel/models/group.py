"""
User Group Model
مدل گروه‌بندی کاربران - کنترل دسترسی و محدودیت‌ها
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


class UserGroup(Base):
    """
    مدل گروه کاربران
    هر گروه شامل:
    - لیست دامنه‌های مسدود (اختصاصی گروه)
    - لیست دامنه‌های مجاز (whitelist اختصاصی)
    - محدودیت‌های پیش‌فرض برای کاربران
    """
    __tablename__ = "user_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ═══════════════════════════════════════════════════════════
    # اطلاعات گروه
    # ═══════════════════════════════════════════════════════════
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    color = Column(String(7), default="#6366f1")  # رنگ نمایشی (hex)

    # ═══════════════════════════════════════════════════════════
    # کنترل دسترسی دامنه‌ها
    # ═══════════════════════════════════════════════════════════
    blocked_domains = Column(JSON, default=list)   # لیست دامنه‌های مسدود
    allowed_domains = Column(JSON, default=list)   # لیست سفید (استثنا)
    blocked_categories = Column(JSON, default=list) # لیست دسته‌های مسدود (تبلیغات، پورن و...)

    # ═══════════════════════════════════════════════════════════
    # محدودیت‌های پیش‌فرض (هنگام ساخت کاربر جدید)
    # ═══════════════════════════════════════════════════════════
    default_max_traffic = Column(Integer, default=0)       # bytes - 0=نامحدود
    default_expire_days = Column(Integer, default=30)
    default_max_connections = Column(Integer, default=2)
    default_reset_period_type = Column(String(10), default="monthly")  # daily/weekly/monthly

    # ═══════════════════════════════════════════════════════════
    # وضعیت
    # ═══════════════════════════════════════════════════════════
    is_active = Column(Boolean, default=True)

    # ═══════════════════════════════════════════════════════════
    # تاریخ‌ها
    # ═══════════════════════════════════════════════════════════
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationship
    users = relationship("User", back_populates="group", lazy="selectin")

    def __repr__(self):
        return f"<UserGroup {self.name}>"

    @property
    def user_count(self) -> int:
        """تعداد کاربران گروه"""
        if self.users:
            return len(self.users)
        return 0

    @property
    def blocked_domains_count(self) -> int:
        if self.blocked_domains:
            return len(self.blocked_domains)
        return 0
