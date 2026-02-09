"""
Tunnel Service - Advanced Anti-Detection
سرویس تانل پیشرفته با قابلیت‌های ضد شناسایی

Features:
- TLS 1.3 with browser fingerprint mimicry
- HTTP/2 multiplexing for traffic pattern hiding
- Random padding to prevent packet size analysis
- Fake HTTPS headers (looks like normal web traffic)
- SNI camouflage (masquerading as popular websites)
"""

import asyncio
import subprocess
import os
import json
import secrets
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

# مسیر فایل‌های Gost
GOST_BINARY = "/usr/local/bin/gost"
GOST_CONFIG = "/etc/gost/config.json"
GOST_SERVICE = "/etc/systemd/system/gost.service"

# لیست SNI های امن (سایت‌های محبوب که فیلتر نمیشن)
SAFE_SNI_LIST = [
    "www.google.com",
    "www.cloudflare.com", 
    "www.microsoft.com",
    "www.apple.com",
    "www.amazon.com",
    "www.github.com",
    "update.microsoft.com",
    "dl.google.com",
    "cdn.jsdelivr.net",
    "ajax.googleapis.com",
]

# کانفیگ anti-detection برای OCServ
OCSERV_STEALTH_CONFIG = """
# Anti-Detection Headers
# Makes OCServ look like a regular HTTPS website

# Disable default server identification
server-stats-reset-time = 0

# Custom HTTP headers to mimic regular web server
custom-header = "Server: nginx/1.24.0"
custom-header = "X-Powered-By: PHP/8.2.0"
custom-header = "X-Content-Type-Options: nosniff"
custom-header = "X-Frame-Options: SAMEORIGIN"
custom-header = "Strict-Transport-Security: max-age=31536000; includeSubDomains"
custom-header = "Content-Security-Policy: default-src 'self'"
custom-header = "Referrer-Policy: strict-origin-when-cross-origin"

# TLS fingerprint that looks like browser
tls-priorities = "NORMAL:%SERVER_PRECEDENCE:%COMPAT:-VERS-SSL3.0:-VERS-TLS1.0:-VERS-TLS1.1:+VERS-TLS1.3"

# Disable compression (prevents CRIME attack and detection)
compression = false

# Disable DTLS/UDP (easier to detect)
udp-port = 0

# Cisco AnyConnect compatibility with stealth
cisco-client-compat = true
dtls-legacy = false
"""


class TunnelService:
    """
    سرویس مدیریت تانل پیشرفته
    با قابلیت‌های ضد شناسایی و رمزنگاری امن
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
        """ایجاد سرویس systemd برای Gost با پارامترهای امنیتی"""
        service_content = """[Unit]
Description=Gost Secure Tunnel Service
After=network.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/gost -C /etc/gost/config.json
Restart=always
RestartSec=3
LimitNOFILE=65535
# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/etc/gost

[Install]
WantedBy=multi-user.target
"""
        with open(GOST_SERVICE, 'w') as f:
            f.write(service_content)
        
        await asyncio.create_subprocess_shell("systemctl daemon-reload")
    
    def _generate_random_path(self) -> str:
        """تولید مسیر تصادفی برای WebSocket (شبیه URL واقعی)"""
        paths = [
            "/api/v1/stream",
            "/ws/connect",
            "/socket.io/?EIO=4",
            "/graphql/subscriptions",
            "/cdn-cgi/trace",
            "/ajax/libs/update",
            "/_next/webpack-hmr",
            "/signalr/connect",
        ]
        return secrets.choice(paths)
    
    def _get_random_sni(self) -> str:
        """انتخاب SNI تصادفی از لیست امن"""
        return secrets.choice(SAFE_SNI_LIST)
    
    async def get_config(self) -> Dict[str, Any]:
        """دریافت تنظیمات فعلی تانل"""
        default_config = {
            "enabled": False,
            "remote_ip": "",
            "remote_port": 2083,
            "local_port": 443,
            "protocol": "h2",  # HTTP/2 by default
            "sni": "www.google.com",
            "obfuscation": "tls",
            "mux": True,  # Multiplexing enabled
            "padding": True,  # Random padding enabled
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    gost_config = json.load(f)
                
                if gost_config.get("Services"):
                    service = gost_config["Services"][0]
                    listener = service.get("Listener", {})
                    forwarder = service.get("Forwarder", {})
                    
                    default_config["enabled"] = True
                    default_config["local_port"] = int(listener.get("Addr", ":443").split(":")[-1])
                    
                    if forwarder.get("Nodes"):
                        node = forwarder["Nodes"][0]
                        addr = node.get("Addr", "")
                        if ":" in addr:
                            default_config["remote_ip"], port = addr.rsplit(":", 1)
                            default_config["remote_port"] = int(port)
                    
                    tls_config = listener.get("TLS", {})
                    default_config["sni"] = tls_config.get("ServerName", "www.google.com")
                    
                    # Check for mux
                    handler = service.get("Handler", {})
                    if handler.get("Metadata", {}).get("mux"):
                        default_config["mux"] = True
                    
            except Exception as e:
                logger.error(f"Error reading Gost config: {e}")
        
        return default_config
    
    async def update_config(
        self,
        remote_ip: str,
        remote_port: int = 2083,
        local_port: int = 443,
        protocol: str = "h2",
        sni: str = "www.google.com",
        obfuscation: str = "tls",
        mux: bool = True,
        padding: bool = True
    ) -> bool:
        """
        به‌روزرسانی تنظیمات تانل با قابلیت‌های ضد شناسایی
        
        Args:
            remote_ip: IP سرور فرانسه
            remote_port: پورت OCServ
            local_port: پورت ورودی (443 پیشنهادی)
            protocol: پروتکل اتصال (h2/wss/tls)
            sni: SNI برای masquerading
            obfuscation: نوع obfuscation
            mux: فعال‌سازی multiplexing
            padding: فعال‌سازی padding تصادفی
        """
        try:
            # تعیین نوع listener بر اساس پروتکل
            listener_type = "tls"
            if protocol == "h2":
                listener_type = "h2"
            elif protocol in ["wss", "ws"]:
                listener_type = "wss"
            
            # ساختار کانفیگ Gost v3 با anti-detection
            gost_config = {
                "Log": {
                    "Level": "warn"
                },
                "Services": [
                    {
                        "Name": "stealth-tunnel",
                        "Addr": f":{local_port}",
                        "Handler": {
                            "Type": "relay",
                            "Metadata": {
                                "mux": mux,
                                "mux.version": 2,
                            }
                        },
                        "Listener": {
                            "Type": listener_type,
                            "Addr": f":{local_port}",
                            "TLS": {
                                "ServerName": sni,
                                "MinVersion": "TLS1.2",
                                "MaxVersion": "TLS1.3",
                                "CipherSuites": [
                                    "TLS_AES_128_GCM_SHA256",
                                    "TLS_AES_256_GCM_SHA384",
                                    "TLS_CHACHA20_POLY1305_SHA256",
                                    "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
                                    "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
                                ],
                                "ALPN": ["h2", "http/1.1"],
                            },
                            "Metadata": {
                                # Fake HTTP headers
                                "header": {
                                    "Server": ["nginx/1.24.0"],
                                    "X-Powered-By": ["PHP/8.2.0"],
                                    "X-Content-Type-Options": ["nosniff"],
                                    "Cache-Control": ["no-cache, no-store"],
                                }
                            }
                        },
                        "Forwarder": {
                            "Nodes": [
                                {
                                    "Name": "france-exit",
                                    "Addr": f"{remote_ip}:{remote_port}",
                                    "Connector": {
                                        "Type": "relay",
                                        "Metadata": {
                                            "mux": mux
                                        }
                                    }
                                }
                            ]
                        }
                    }
                ],
                # اضافه کردن limiter برای traffic shaping
                "Limiters": [
                    {
                        "Name": "traffic-shaper",
                        "Limits": ["$", "100MB", "1GB"]
                    }
                ]
            }
            
            # اگر padding فعاله
            if padding:
                gost_config["Services"][0]["Handler"]["Metadata"]["padding"] = True
                gost_config["Services"][0]["Handler"]["Metadata"]["padding.max"] = 255
            
            # WebSocket path برای obfuscation بیشتر
            if protocol in ["wss", "ws"]:
                gost_config["Services"][0]["Listener"]["Metadata"]["path"] = self._generate_random_path()
            
            with open(self.config_path, 'w') as f:
                json.dump(gost_config, f, indent=2)
            
            logger.info(f"Stealth tunnel config updated: {remote_ip}:{remote_port} (protocol={protocol}, mux={mux})")
            return True
        except Exception as e:
            logger.error(f"Error updating tunnel config: {e}")
            return False
    
    async def apply_ocserv_stealth(self) -> bool:
        """اعمال تنظیمات ضد شناسایی به OCServ"""
        try:
            ocserv_conf = "/etc/ocserv/ocserv.conf"
            
            # بررسی وجود فایل
            if not os.path.exists(ocserv_conf):
                logger.warning("OCServ config not found")
                return False
            
            # خواندن کانفیگ فعلی
            with open(ocserv_conf, 'r') as f:
                content = f.read()
            
            # حذف تنظیمات قبلی anti-detection
            lines = content.split('\n')
            cleaned_lines = []
            skip_section = False
            
            for line in lines:
                if "# Anti-Detection Headers" in line:
                    skip_section = True
                    continue
                if skip_section and line.strip() and not line.startswith('#') and not line.startswith('custom-header'):
                    skip_section = False
                if not skip_section:
                    # حذف custom-header های قبلی
                    if not line.strip().startswith('custom-header'):
                        cleaned_lines.append(line)
            
            # اضافه کردن تنظیمات جدید
            new_content = '\n'.join(cleaned_lines).rstrip() + '\n\n' + OCSERV_STEALTH_CONFIG
            
            with open(ocserv_conf, 'w') as f:
                f.write(new_content)
            
            # Reload کردن OCServ
            await asyncio.create_subprocess_shell(
                "systemctl reload ocserv || systemctl restart ocserv",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            logger.info("OCServ stealth config applied")
            return True
        except Exception as e:
            logger.error(f"Error applying OCServ stealth config: {e}")
            return False
    
    async def start(self) -> bool:
        """شروع تانل"""
        try:
            if not await self.is_gost_installed():
                success = await self.install_gost()
                if not success:
                    return False
            
            # اعمال تنظیمات stealth به OCServ (اگر موجوده)
            await self.apply_ocserv_stealth()
            
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
            installed = await self.is_gost_installed()
            
            process = await asyncio.create_subprocess_shell(
                "systemctl is-active gost",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            is_running = stdout.decode().strip() == "active"
            
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
            # تست با curl (شبیه‌سازی درخواست مرورگر)
            process = await asyncio.create_subprocess_shell(
                f"""curl -sk --connect-timeout 5 \
                    -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
                    -H "Accept: text/html,application/xhtml+xml" \
                    https://{remote_ip}:{remote_port} -o /dev/null -w '%{{http_code}}'""",
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
            
            latency = None
            if "avg" in ping_output:
                try:
                    latency = float(ping_output.split("avg")[0].split("/")[-1])
                except:
                    pass
            
            return {
                "reachable": http_code in ["200", "401", "403", "405", "400"],
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
    
    def get_safe_sni_list(self) -> List[str]:
        """دریافت لیست SNI های امن"""
        return SAFE_SNI_LIST.copy()


# Singleton instance
tunnel_service = TunnelService()
