"""
OCServ Panel Configuration
تنظیمات پنل مدیریت OCServ
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path
from typing import Optional
import secrets
import os


# Get base directory
BASE_DIR = Path(__file__).parent


def _ensure_secret_key() -> str:
    """
    SECRET_KEY را از .env می‌خواند.
    اگر وجود نداشت، یکبار تولید و در .env ذخیره می‌کند.
    اینطوری بعد از restart، توکن‌های قبلی معتبر می‌مونن.
    """
    env_path = BASE_DIR / ".env"
    
    # Check if .env already has SECRET_KEY
    if env_path.exists():
        try:
            content = env_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("SECRET_KEY="):
                    value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                    if value:
                        return value
        except Exception:
            pass
    
    # Generate new key and persist to .env
    key = secrets.token_urlsafe(32)
    try:
        os.makedirs(env_path.parent, exist_ok=True)
        with open(env_path, "a", encoding="utf-8") as f:
            f.write(f"\nSECRET_KEY={key}\n")
    except Exception:
        pass  # In worst case, will generate a new key next restart
    
    return key


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "OCServ Panel"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Paths - use computed default
    DATABASE_PATH: str = str(BASE_DIR / "data" / "panel.db")
    
    # Security - persistent across restarts
    SECRET_KEY: str = Field(default_factory=_ensure_secret_key)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # OCServ paths
    OCSERV_CONFIG_PATH: str = "/etc/ocserv/ocserv.conf"
    OCSERV_PASSWD_PATH: str = "/etc/ocserv/ocpasswd"
    OCCTL_PATH: str = "/usr/bin/occtl"
    OCPASSWD_PATH: str = "/usr/bin/ocpasswd"
    
    # Panel settings
    PANEL_PORT: int = 8443
    PANEL_HOST: str = "0.0.0.0"
    PANEL_PATH: str = str(BASE_DIR.parent)  # Default to project root for file paths
    
    # Domain and Admin (set by installer)
    DOMAIN: str = ""
    ADMIN_USER: str = ""
    
    # Traffic monitoring interval (seconds) - shorter for real-time accuracy
    TRAFFIC_CHECK_INTERVAL: int = 10  # Check traffic every 10 seconds
    QUOTA_CHECK_INTERVAL: int = 10    # Check quotas every 10 seconds
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra fields in .env
    )
    
    @property
    def base_dir(self) -> Path:
        return BASE_DIR
    
    @property
    def database_path(self) -> Path:
        return Path(self.DATABASE_PATH)
    
    @property
    def log_dir(self) -> Path:
        """مسیر صحیح دایرکتوری لاگ‌ها"""
        return BASE_DIR / "logs"


settings = Settings()
