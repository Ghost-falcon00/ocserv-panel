"""
OCServ Panel Configuration
تنظیمات پنل مدیریت OCServ
"""

from pydantic_settings import BaseSettings
from pathlib import Path
import secrets


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "OCServ Panel"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent
    DATABASE_PATH: Path = BASE_DIR / "data" / "panel.db"
    
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
    
    # Traffic monitoring interval (seconds)
    TRAFFIC_CHECK_INTERVAL: int = 60
    QUOTA_CHECK_INTERVAL: int = 30
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
