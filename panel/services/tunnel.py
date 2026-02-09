"""
Tunnel Service
سرویس مدیریت تانل Gost برای عبور از فیلترینگ
"""

import asyncio
import subprocess
import os
import json
import aiohttp
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# مسیر فایل‌های Gost
GOST_BINARY = "/usr/local/bin/gost"
GOST_CONFIG = "/etc/gost/config.json"
GOST_SERVICE = "/etc/systemd/system/gost.service"


class TunnelService:
    """
    سرویس مدیریت تانل
    اتصال امن و ضد فیلتر به سرور خارجی
    """
    
    def __init__(self):
        self.config_path = Path(GOST_CONFIG)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def is_gost_installed(self) -> bool:
        """بررسی نصب بودن Gost"""
        return os.path.exists(GOST_BINARY)
    
    async def install_gost(self) -> bool:
        """نصب Gost"""
        try:
            # دانلود آخرین نسخه
            install_script = """
            set -e
            GOST_VERSION=$(curl -s https://api.github.com/repos/ginuerzh/gost/releases/latest | grep -oP '"tag_name": "v\\K[^"]+')
            wget -q https://github.com/ginuerzh/gost/releases/download/v${GOST_VERSION}/gost-linux-amd64-${GOST_VERSION}.gz -O /tmp/gost.gz
            gunzip -f /tmp/gost.gz
            mv /tmp/gost /usr/local/bin/gost
            chmod +x /usr/local/bin/gost
            mkdir -p /etc/gost
            """
            
            process = await asyncio.create_subprocess_shell(
                install_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            if process.returncode == 0:
                await self._create_systemd_service()
                logger.info("Gost installed successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Error installing Gost: {e}")
            return False
    
    async def _create_systemd_service(self):
        """ایجاد سرویس systemd برای Gost"""
        service_content = """[Unit]
Description=Gost Tunnel Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/gost -C /etc/gost/config.json
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
        with open(GOST_SERVICE, 'w') as f:
            f.write(service_content)
        
        await asyncio.create_subprocess_shell("systemctl daemon-reload")
    
    async def get_config(self) -> Dict[str, Any]:
        """دریافت تنظیمات فعلی تانل"""
        default_config = {
            "enabled": False,
            "remote_ip": "",
            "remote_port": 2083,
            "local_port": 443,
            "protocol": "relay+tls",
            "sni": "www.google.com",
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    gost_config = json.load(f)
                
                # Parse Gost config to our format
                if gost_config.get("Services"):
                    service = gost_config["Services"][0]
                    listener = service.get("Listener", {})
                    forwarder = service.get("Forwarder", {})
                    
                    default_config["enabled"] = True
                    default_config["local_port"] = listener.get("Addr", ":443").split(":")[-1]
                    
                    if forwarder.get("Nodes"):
                        node = forwarder["Nodes"][0]
                        addr = node.get("Addr", "")
                        if ":" in addr:
                            default_config["remote_ip"], default_config["remote_port"] = addr.rsplit(":", 1)
                            default_config["remote_port"] = int(default_config["remote_port"])
                    
                    tls_config = listener.get("TLS", {})
                    default_config["sni"] = tls_config.get("ServerName", "www.google.com")
                    
            except Exception as e:
                logger.error(f"Error reading Gost config: {e}")
        
        return default_config
    
    async def update_config(
        self,
        remote_ip: str,
        remote_port: int = 2083,
        local_port: int = 443,
        protocol: str = "relay+tls",
        sni: str = "www.google.com"
    ) -> bool:
        """به‌روزرسانی تنظیمات تانل"""
        try:
            # ساختار کانفیگ Gost v3
            gost_config = {
                "Services": [
                    {
                        "Name": "ocserv-tunnel",
                        "Addr": f":{local_port}",
                        "Handler": {
                            "Type": "relay"
                        },
                        "Listener": {
                            "Type": "tls",
                            "Addr": f":{local_port}",
                            "TLS": {
                                "ServerName": sni
                            }
                        },
                        "Forwarder": {
                            "Nodes": [
                                {
                                    "Name": "france-server",
                                    "Addr": f"{remote_ip}:{remote_port}"
                                }
                            ]
                        }
                    }
                ]
            }
            
            # اگر پروتکل WebSocket باشه
            if "ws" in protocol:
                gost_config["Services"][0]["Listener"]["Type"] = "wss"
            
            with open(self.config_path, 'w') as f:
                json.dump(gost_config, f, indent=2)
            
            logger.info(f"Tunnel config updated: {remote_ip}:{remote_port}")
            return True
        except Exception as e:
            logger.error(f"Error updating tunnel config: {e}")
            return False
    
    async def start(self) -> bool:
        """شروع تانل"""
        try:
            if not await self.is_gost_installed():
                success = await self.install_gost()
                if not success:
                    return False
            
            process = await asyncio.create_subprocess_shell(
                "systemctl enable gost && systemctl start gost",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            return process.returncode == 0
        except Exception as e:
            logger.error(f"Error starting tunnel: {e}")
            return False
    
    async def stop(self) -> bool:
        """توقف تانل"""
        try:
            process = await asyncio.create_subprocess_shell(
                "systemctl stop gost",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except Exception as e:
            logger.error(f"Error stopping tunnel: {e}")
            return False
    
    async def restart(self) -> bool:
        """راه‌اندازی مجدد تانل"""
        await self.stop()
        return await self.start()
    
    async def get_status(self) -> Dict[str, Any]:
        """دریافت وضعیت تانل"""
        try:
            # بررسی نصب بودن
            installed = await self.is_gost_installed()
            
            # بررسی وضعیت سرویس
            process = await asyncio.create_subprocess_shell(
                "systemctl is-active gost",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            is_running = stdout.decode().strip() == "active"
            
            # خواندن تنظیمات
            config = await self.get_config()
            
            return {
                "installed": installed,
                "running": is_running,
                "config": config,
                "error": None
            }
        except Exception as e:
            return {
                "installed": False,
                "running": False,
                "config": {},
                "error": str(e)
            }
    
    async def test_connection(self, remote_ip: str, remote_port: int = 2083) -> Dict[str, Any]:
        """تست اتصال به سرور فرانسه"""
        try:
            # تست با curl
            process = await asyncio.create_subprocess_shell(
                f"curl -sk --connect-timeout 5 https://{remote_ip}:{remote_port} -o /dev/null -w '%{{http_code}}'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            http_code = stdout.decode().strip()
            
            # تست پینگ
            ping_process = await asyncio.create_subprocess_shell(
                f"ping -c 3 -W 2 {remote_ip}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            ping_stdout, _ = await ping_process.communicate()
            ping_output = ping_stdout.decode()
            
            # استخراج میانگین پینگ
            latency = None
            if "avg" in ping_output:
                try:
                    latency = float(ping_output.split("avg")[0].split("/")[-1])
                except:
                    pass
            
            return {
                "reachable": http_code in ["200", "401", "403", "405"],
                "http_code": http_code,
                "latency_ms": latency,
                "error": None if http_code != "000" else "Connection timeout"
            }
        except Exception as e:
            return {
                "reachable": False,
                "http_code": None,
                "latency_ms": None,
                "error": str(e)
            }


# Singleton instance
tunnel_service = TunnelService()
