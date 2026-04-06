"""
System API
API مدیریت سیستم و آپدیت
"""

import os
import subprocess
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import aiohttp

from config import settings
from models.database import get_db
from models.admin import Admin
from api.auth import get_current_admin

router = APIRouter(prefix="/api/system", tags=["System"])
logger = logging.getLogger(__name__)

# Constants
GITHUB_REPO = "Ghost-falcon00/ocserv-panel"
BRANCH = "main"

class UpdateCheckResponse(BaseModel):
    update_available: bool
    local_hash: str
    latest_hash: Optional[str] = None
    message: Optional[str] = None
    date: Optional[str] = None


def get_local_commit_hash() -> str:
    """دریافت هش کامیت فعلی از گیت لوکال"""
    try:
        # Use simple git rev-parse
        panel_dir = "/opt/ocserv-panel"
        # For development environments like Windows, fallback to current dir
        if not os.path.exists(panel_dir):
            panel_dir = os.getcwd()
            
        result = subprocess.run(
            ["/usr/bin/git", "-c", "safe.directory=*", "rev-parse", "HEAD"],
            cwd=panel_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        logger.error(f"Failed to get local commit hash: {e}")
        return "unknown"


@router.get("/update/check", response_model=UpdateCheckResponse)
async def check_update(current_admin: Admin = Depends(get_current_admin)):
    """بررسی آپدیت از گیت‌هاب"""
    if not current_admin.is_superadmin:
        raise HTTPException(status_code=403, detail="دسترسی غیرمجاز")

    local_hash = get_local_commit_hash()
    
    # Fetch latest commit from GitHub API
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/{BRANCH}"
            async with session.get(url, timeout=10.0) as response:
                if response.status == 200:
                    data = await response.json()
                    latest_hash = data.get("sha")
                    commit_info = data.get("commit", {})
                    message = commit_info.get("message", "")
                    date = commit_info.get("author", {}).get("date", "")
                    
                    # Check if update is available
                    # If local_hash is unknown or there is a new hash
                    is_available = False
                    if local_hash != "unknown" and latest_hash:
                        # Simple equality check
                        if not latest_hash.startswith(local_hash):
                            is_available = True
                    elif local_hash == "unknown":
                        # Assume available if we can't read local hash
                        is_available = True
                        
                    return UpdateCheckResponse(
                        update_available=is_available,
                        local_hash=local_hash[:7] if local_hash != "unknown" else "unknown",
                        latest_hash=latest_hash[:7] if latest_hash else None,
                        message=message,
                        date=date
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"GitHub API Error: {response.status} {error_text}")
                    raise HTTPException(status_code=500, detail="خطا در ارتباط با گیت‌هاب")
                
    except Exception as e:
        logger.error(f"Update check failed: {e}")
        raise HTTPException(status_code=500, detail="خطا در بررسی آپدیت")


@router.post("/update/perform")
async def perform_update(current_admin: Admin = Depends(get_current_admin)):
    """اجرای اسکریپت آپدیت"""
    if not current_admin.is_superadmin:
        raise HTTPException(status_code=403, detail="دسترسی غیرمجاز")
        
    try:
        script_path = "/opt/ocserv-panel/update.sh"
        
        if not os.path.exists(script_path):
            raise HTTPException(status_code=404, detail="فایل آپدیت پیدا نشد")
            
        # Ensure it's executable
        os.chmod(script_path, 0o755)
        
        # Run process in background detached
        # Popen without waiting means it will continue in the background
        # Python will shutdown, systemd will kill our python process and start a new one
        subprocess.Popen(
            ["/bin/bash", script_path],
            cwd="/opt/ocserv-panel",
            start_new_session=True, # Detach from parent
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        return {"status": "updating", "message": "عملیات بروزرسانی آغاز شد. پنل به زودی ریستارت می‌شود."}
        
    except Exception as e:
        logger.error(f"Failed to trigger update: {e}")
        raise HTTPException(status_code=500, detail=str(e))
