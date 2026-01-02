"""
OCServ Panel Configuration
تنظیمات پنل مدیریت OCServ
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path
from typing import Optional
import secrets


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "OCServ Panel"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent
    DATABASE_PATH: Path = Field(default=None)
    
    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
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
    PANEL_PATH: Optional[str] = None  # Secret path for extra security
    
    # Domain and Admin (set by installer)
    DOMAIN: Optional[str] = None
    ADMIN_USER: Optional[str] = None
    
    # Traffic monitoring interval (seconds)
    TRAFFIC_CHECK_INTERVAL: int = 60
    QUOTA_CHECK_INTERVAL: int = 30
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra fields in .env
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set default database path after init
        if self.DATABASE_PATH is None:
            self.DATABASE_PATH = self.BASE_DIR / "data" / "panel.db"


settings = Settings()
