"""
Admin Model
مدل ادمین پنل
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from passlib.context import CryptContext
from .database import Base


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Admin(Base):
    """
    مدل ادمین پنل
    برای ورود به پنل مدیریت
    """
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # وضعیت
    is_active = Column(Boolean, default=True)
    is_superadmin = Column(Boolean, default=False)
    
    # زمان‌ها
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Admin {self.username}>"
    
    def set_password(self, password: str):
        """تنظیم رمز عبور با هش"""
        self.password_hash = pwd_context.hash(password)
    
    def verify_password(self, password: str) -> bool:
        """بررسی رمز عبور"""
        return pwd_context.verify(password, self.password_hash)
    
    @staticmethod
    def hash_password(password: str) -> str:
        """هش کردن رمز عبور"""
        return pwd_context.hash(password)
