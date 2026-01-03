"""
Logging Service
سرویس لاگ‌گیری مرکزی
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from config import settings

# Log directory
LOG_DIR = Path(settings.PANEL_PATH) / "panel" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Max log file size: 10MB, keep 3 backup files
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 3


def setup_logging():
    """تنظیم لاگ‌گیری برای کل سیستم"""
    
    # Panel log
    panel_handler = RotatingFileHandler(
        LOG_DIR / "panel.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    panel_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(name)s - %(message)s"
    ))
    
    # Traffic log
    traffic_handler = RotatingFileHandler(
        LOG_DIR / "traffic.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    traffic_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(message)s"
    ))
    
    # Connection log
    connection_handler = RotatingFileHandler(
        LOG_DIR / "connections.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    connection_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(message)s"
    ))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(panel_handler)
    
    # Configure specific loggers
    logging.getLogger("services.traffic").addHandler(traffic_handler)
    logging.getLogger("services.quota").addHandler(panel_handler)
    logging.getLogger("connections").addHandler(connection_handler)
    
    # Reduce noise from external libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    return panel_handler


class LogReader:
    """خواندن لاگ‌ها"""
    
    @staticmethod
    def read_panel_logs(lines: int = 100) -> list:
        """خواندن لاگ پنل"""
        return LogReader._read_log_file(LOG_DIR / "panel.log", lines)
    
    @staticmethod
    def read_traffic_logs(lines: int = 100) -> list:
        """خواندن لاگ ترافیک"""
        return LogReader._read_log_file(LOG_DIR / "traffic.log", lines)
    
    @staticmethod
    def read_connection_logs(lines: int = 100) -> list:
        """خواندن لاگ اتصالات"""
        return LogReader._read_log_file(LOG_DIR / "connections.log", lines)
    
    @staticmethod
    def read_ocserv_logs(lines: int = 100) -> list:
        """خواندن لاگ OCServ از journalctl"""
        import subprocess
        try:
            result = subprocess.run(
                ["journalctl", "-u", "ocserv", "-n", str(lines), "--no-pager", "-o", "short"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip().split("\n") if result.stdout else []
        except Exception as e:
            return [f"Error reading OCServ logs: {e}"]
    
    @staticmethod
    def _read_log_file(file_path: Path, lines: int) -> list:
        """خواندن آخرین خطوط از فایل لاگ"""
        try:
            if not file_path.exists():
                return []
            
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                # Read last N lines efficiently
                all_lines = f.readlines()
                return [line.strip() for line in all_lines[-lines:]]
        except Exception as e:
            return [f"Error reading log: {e}"]
    
    @staticmethod
    def get_log_stats() -> dict:
        """آمار فایل‌های لاگ"""
        stats = {}
        for log_file in LOG_DIR.glob("*.log*"):
            size = log_file.stat().st_size
            stats[log_file.name] = {
                "size": size,
                "size_mb": round(size / (1024 * 1024), 2)
            }
        return stats


# Initialize log reader
log_reader = LogReader()
