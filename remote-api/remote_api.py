#!/usr/bin/env python3
"""
OCServ Remote API - France Server
API خفیف برای مدیریت از راه دور OCServ روی سرور فرانسه
توسط پنل ایران فراخوانی می‌شود

Security:
- Token-based authentication
- HTTPS only
- IP whitelisting optional
"""

import asyncio
import json
import os
import re
import hashlib
import hmac
import secrets
import time
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Header, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Config
API_PORT = int(os.getenv("REMOTE_API_PORT", "6443"))
API_TOKEN = os.getenv("REMOTE_API_TOKEN", "")
TOKEN_FILE = "/etc/ocserv-remote/token"
OCCTL = "/usr/bin/occtl"
OCPASSWD = "/usr/bin/ocpasswd"
PASSWD_FILE = "/etc/ocserv/ocpasswd"
CONFIG_FILE = "/etc/ocserv/ocserv.conf"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("remote-api")

# Load token from file if not in env
if not API_TOKEN and os.path.exists(TOKEN_FILE):
    API_TOKEN = Path(TOKEN_FILE).read_text().strip()

app = FastAPI(title="OCServ Remote API", docs_url=None, redoc_url=None)


# ========== Auth ==========

async def verify_token(authorization: str = Header(...)):
    """Verify bearer token"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    token = authorization.replace("Bearer ", "")
    if not hmac.compare_digest(token, API_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid token")
    return True


# ========== Helpers ==========

async def run_cmd(cmd: list) -> tuple:
    """Execute command and return (returncode, stdout, stderr)"""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return (
            process.returncode,
            stdout.decode('utf-8', errors='ignore'),
            stderr.decode('utf-8', errors='ignore')
        )
    except Exception as e:
        return (-1, "", str(e))


async def run_shell(cmd: str) -> tuple:
    """Execute shell command"""
    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return (
            process.returncode,
            stdout.decode('utf-8', errors='ignore'),
            stderr.decode('utf-8', errors='ignore')
        )
    except Exception as e:
        return (-1, "", str(e))


# ========== Schemas ==========

class UserCreate(BaseModel):
    username: str
    password: str

class UserAction(BaseModel):
    username: str

class PasswordChange(BaseModel):
    username: str
    new_password: str

class ConfigUpdate(BaseModel):
    key: str
    value: str

class ApiResponse(BaseModel):
    success: bool
    message: str = ""
    data: Optional[dict] = None


# ========== User Management ==========

@app.post("/api/users/add", response_model=ApiResponse)
async def add_user(user: UserCreate, auth: bool = Depends(verify_token)):
    """افزودن کاربر جدید"""
    try:
        password_input = f"{user.password}\n{user.password}\n"
        process = await asyncio.create_subprocess_exec(
            OCPASSWD, "-c", PASSWD_FILE, user.username,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate(input=password_input.encode())
        
        if process.returncode == 0:
            logger.info(f"User added: {user.username}")
            return ApiResponse(success=True, message=f"User {user.username} created")
        return ApiResponse(success=False, message="Failed to create user")
    except Exception as e:
        return ApiResponse(success=False, message=str(e))


@app.post("/api/users/delete", response_model=ApiResponse)
async def delete_user(user: UserAction, auth: bool = Depends(verify_token)):
    """حذف کاربر"""
    try:
        rc, _, err = await run_cmd([OCPASSWD, "-c", PASSWD_FILE, "-d", user.username])
        if rc == 0:
            # Disconnect user if online
            await run_cmd([OCCTL, "disconnect", "user", user.username])
            logger.info(f"User deleted: {user.username}")
            return ApiResponse(success=True, message=f"User {user.username} deleted")
        return ApiResponse(success=False, message=err)
    except Exception as e:
        return ApiResponse(success=False, message=str(e))


@app.post("/api/users/password", response_model=ApiResponse)
async def change_password(data: PasswordChange, auth: bool = Depends(verify_token)):
    """تغییر رمز عبور"""
    try:
        password_input = f"{data.new_password}\n{data.new_password}\n"
        process = await asyncio.create_subprocess_exec(
            OCPASSWD, "-c", PASSWD_FILE, data.username,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate(input=password_input.encode())
        
        if process.returncode == 0:
            return ApiResponse(success=True, message="Password changed")
        return ApiResponse(success=False, message="Failed to change password")
    except Exception as e:
        return ApiResponse(success=False, message=str(e))


@app.post("/api/users/lock", response_model=ApiResponse)
async def lock_user(user: UserAction, auth: bool = Depends(verify_token)):
    """قفل کردن کاربر"""
    rc, _, err = await run_cmd([OCPASSWD, "-c", PASSWD_FILE, "-l", user.username])
    await run_cmd([OCCTL, "disconnect", "user", user.username])
    return ApiResponse(success=rc == 0, message="User locked" if rc == 0 else err)


@app.post("/api/users/unlock", response_model=ApiResponse)
async def unlock_user(user: UserAction, auth: bool = Depends(verify_token)):
    """باز کردن قفل کاربر"""
    rc, _, err = await run_cmd([OCPASSWD, "-c", PASSWD_FILE, "-u", user.username])
    return ApiResponse(success=rc == 0, message="User unlocked" if rc == 0 else err)


@app.post("/api/users/disconnect", response_model=ApiResponse)
async def disconnect_user(user: UserAction, auth: bool = Depends(verify_token)):
    """قطع اتصال کاربر"""
    rc, _, err = await run_cmd([OCCTL, "disconnect", "user", user.username])
    return ApiResponse(success=rc == 0, message="User disconnected" if rc == 0 else err)


# ========== Status & Monitoring ==========

@app.get("/api/status")
async def get_status(auth: bool = Depends(verify_token)):
    """دریافت وضعیت سرور"""
    rc, stdout, _ = await run_cmd([OCCTL, "show", "status"])
    
    status_data = {}
    if rc == 0:
        for line in stdout.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                status_data[key.strip()] = value.strip()
    
    # Check service status
    svc_rc, svc_out, _ = await run_shell("systemctl is-active ocserv")
    status_data["service_active"] = svc_out.strip() == "active"
    
    return {"success": True, "data": status_data}


@app.get("/api/users/online")
async def get_online_users(auth: bool = Depends(verify_token)):
    """دریافت لیست کاربران آنلاین"""
    rc, stdout, _ = await run_cmd([OCCTL, "-j", "show", "users"])
    
    users = []
    if rc == 0 and stdout.strip():
        try:
            raw_users = json.loads(stdout)
            for u in raw_users:
                users.append({
                    "id": u.get("ID", 0),
                    "username": u.get("Username", ""),
                    "ip": u.get("IP", ""),
                    "vpn_ip": u.get("IPv4", ""),
                    "hostname": u.get("Hostname", ""),
                    "connected_since": u.get("Connected at", ""),
                    "rx": u.get("RX", 0),
                    "tx": u.get("TX", 0),
                    "user_agent": u.get("User-Agent", ""),
                    "dtls": u.get("DTLS", ""),
                    "tls_ciphersuite": u.get("TLS ciphersuite", ""),
                })
        except json.JSONDecodeError:
            # Parse text output fallback
            pass
    
    return {"success": True, "data": users, "count": len(users)}


@app.get("/api/users/traffic/{username}")
async def get_user_traffic(username: str, auth: bool = Depends(verify_token)):
    """دریافت ترافیک یک کاربر"""
    rc, stdout, _ = await run_cmd([OCCTL, "-j", "show", "users"])
    
    traffic = {"rx": 0, "tx": 0, "total": 0}
    
    if rc == 0 and stdout.strip():
        try:
            users = json.loads(stdout)
            for u in users:
                if u.get("Username") == username:
                    rx = int(u.get("RX", 0))
                    tx = int(u.get("TX", 0))
                    traffic["rx"] += rx
                    traffic["tx"] += tx
                    traffic["total"] = traffic["rx"] + traffic["tx"]
        except:
            pass
    
    return {"success": True, "data": traffic}


@app.get("/api/users/all-traffic")
async def get_all_traffic(auth: bool = Depends(verify_token)):
    """دریافت ترافیک تمام کاربران آنلاین"""
    rc, stdout, _ = await run_cmd([OCCTL, "-j", "show", "users"])
    
    traffic_map = {}
    
    if rc == 0 and stdout.strip():
        try:
            users = json.loads(stdout)
            for u in users:
                username = u.get("Username", "")
                rx = int(u.get("RX", 0))
                tx = int(u.get("TX", 0))
                
                if username not in traffic_map:
                    traffic_map[username] = {"rx": 0, "tx": 0}
                
                traffic_map[username]["rx"] += rx
                traffic_map[username]["tx"] += tx
        except:
            pass
    
    return {"success": True, "data": traffic_map}


# ========== OCServ Service Control ==========

@app.post("/api/service/restart", response_model=ApiResponse)
async def restart_service(auth: bool = Depends(verify_token)):
    """ری‌استارت OCServ"""
    rc, _, err = await run_shell("systemctl restart ocserv")
    return ApiResponse(success=rc == 0, message="Service restarted" if rc == 0 else err)


@app.post("/api/service/reload", response_model=ApiResponse)
async def reload_service(auth: bool = Depends(verify_token)):
    """ریلود تنظیمات"""
    rc, _, err = await run_cmd([OCCTL, "reload"])
    return ApiResponse(success=rc == 0, message="Config reloaded" if rc == 0 else err)


@app.post("/api/service/stop", response_model=ApiResponse)
async def stop_service(auth: bool = Depends(verify_token)):
    """توقف سرویس"""
    rc, _, err = await run_shell("systemctl stop ocserv")
    return ApiResponse(success=rc == 0, message="Service stopped" if rc == 0 else err)


@app.post("/api/service/start", response_model=ApiResponse)
async def start_service(auth: bool = Depends(verify_token)):
    """شروع سرویس"""
    rc, _, err = await run_shell("systemctl start ocserv")
    return ApiResponse(success=rc == 0, message="Service started" if rc == 0 else err)


# ========== Config Management ==========

@app.get("/api/config")
async def get_config(auth: bool = Depends(verify_token)):
    """دریافت تنظیمات OCServ"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            content = f.read()
        
        config = {}
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
        
        return {"success": True, "data": config}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/config/update", response_model=ApiResponse)
async def update_config(data: ConfigUpdate, auth: bool = Depends(verify_token)):
    """به‌روزرسانی تنظیمات"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            lines = f.readlines()
        
        found = False
        new_lines = []
        for line in lines:
            if line.strip().startswith(f"{data.key}") and '=' in line:
                new_lines.append(f"{data.key} = {data.value}\n")
                found = True
            else:
                new_lines.append(line)
        
        if not found:
            new_lines.append(f"{data.key} = {data.value}\n")
        
        with open(CONFIG_FILE, 'w') as f:
            f.writelines(new_lines)
        
        return ApiResponse(success=True, message="Config updated")
    except Exception as e:
        return ApiResponse(success=False, message=str(e))


# ========== Health Check ==========

@app.get("/api/health")
async def health_check():
    """بررسی سلامت سرور - بدون احراز هویت"""
    return {"status": "ok", "service": "ocserv-remote-api"}


# ========== Main ==========

if __name__ == "__main__":
    if not API_TOKEN:
        logger.error("No API token configured! Set REMOTE_API_TOKEN or create /etc/ocserv-remote/token")
        exit(1)
    
    logger.info(f"Starting OCServ Remote API on port {API_PORT}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=API_PORT,
        ssl_certfile="/etc/ocserv/ssl/server-cert.pem",
        ssl_keyfile="/etc/ocserv/ssl/server-key.pem",
        log_level="warning"
    )
