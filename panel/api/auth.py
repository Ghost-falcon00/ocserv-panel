"""
Authentication API
API احراز هویت
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.database import get_db
from models.admin import Admin

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ========== Schemas ==========

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class TokenData(BaseModel):
    username: Optional[str] = None


class AdminCreate(BaseModel):
    username: str
    password: str


class AdminResponse(BaseModel):
    id: int
    username: str
    is_active: bool
    is_superadmin: bool
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


# ========== Helper Functions ==========

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """ایجاد توکن JWT"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Admin:
    """دریافت ادمین جاری از توکن"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="توکن نامعتبر است",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(
        select(Admin).where(Admin.username == username)
    )
    admin = result.scalar_one_or_none()
    
    if admin is None or not admin.is_active:
        raise credentials_exception
    
    return admin


# ========== Endpoints ==========

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    ورود به پنل
    
    - **username**: نام کاربری
    - **password**: رمز عبور
    """
    result = await db.execute(
        select(Admin).where(Admin.username == form_data.username)
    )
    admin = result.scalar_one_or_none()
    
    if not admin or not admin.verify_password(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری یا رمز عبور اشتباه است",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری غیرفعال است"
        )
    
    # Update last login
    admin.last_login = datetime.now()
    await db.commit()
    
    # Create token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": admin.username},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.get("/me", response_model=AdminResponse)
async def get_current_admin_info(
    current_admin: Admin = Depends(get_current_admin)
):
    """دریافت اطلاعات ادمین جاری"""
    return current_admin


@router.post("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """تغییر رمز عبور ادمین"""
    if not current_admin.verify_password(current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رمز عبور فعلی اشتباه است"
        )
    
    current_admin.set_password(new_password)
    await db.commit()
    
    return {"message": "رمز عبور با موفقیت تغییر کرد"}


@router.post("/create-admin", response_model=AdminResponse)
async def create_admin(
    admin_data: AdminCreate,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """ایجاد ادمین جدید (فقط سوپرادمین)"""
    if not current_admin.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="فقط سوپرادمین می‌تواند ادمین جدید بسازد"
        )
    
    # Check if username exists
    result = await db.execute(
        select(Admin).where(Admin.username == admin_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این نام کاربری قبلاً استفاده شده"
        )
    
    new_admin = Admin(
        username=admin_data.username,
        password_hash=Admin.hash_password(admin_data.password)
    )
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)
    
    return new_admin
