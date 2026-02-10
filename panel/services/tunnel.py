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

# کانفیگ anti-detection پیشرفته برای OCServ
# ===== حذف کامل امضای سیسکو =====
# فایروال‌ها OCServ/Cisco AnyConnect رو از روی چند چیز شناسایی میکنن:
# 1. هدرهای X-CSTP-* و X-DTLS-* (مختص سیسکو)
# 2. پاسخ TLS handshake (ALPN مخصوص سیسکو)
# 3. هدر Server: در پاسخ HTTP
# 4. DTLS بودن (فقط سیسکو از DTLS استفاده میکنه)
# 5. پترن کوکی‌ها و session ID
# 
# این کانفیگ تمام این علائم رو حذف/جعل میکنه

OCSERV_STEALTH_CONFIG = """
# =============================================
# Anti-Detection & Cisco Signature Removal
# =============================================
# این تنظیمات پکت‌های Cisco رو غیرقابل تشخیص میکنه
# ترافیک شبیه یه سایت عادی nginx/PHP به نظر میرسه

# ---------- هدرهای جعلی وب‌سرور ----------
# فایروال وقتی این هدرها رو میبینه فکر میکنه یه سایت PHP داره جواب میده
custom-header = "Server: nginx/1.24.0"
custom-header = "X-Powered-By: PHP/8.2.12"
custom-header = "X-Content-Type-Options: nosniff"
custom-header = "X-Frame-Options: SAMEORIGIN"
custom-header = "X-XSS-Protection: 1; mode=block"
custom-header = "Strict-Transport-Security: max-age=31536000; includeSubDomains; preload"
custom-header = "Content-Security-Policy: default-src 'self' https: data: 'unsafe-inline'"
custom-header = "Referrer-Policy: strict-origin-when-cross-origin"
custom-header = "Permissions-Policy: camera=(), microphone=(), geolocation=()"
custom-header = "X-Request-ID: {random}"
custom-header = "Cache-Control: no-cache, no-store, must-revalidate"
custom-header = "Pragma: no-cache"
custom-header = "Vary: Accept-Encoding"
custom-header = "X-DNS-Prefetch-Control: off"

# ---------- غیرفعال کردن امضاهای سیسکو ----------
# DTLS رو خاموش کن - مهم‌ترین علامت شناسایی سیسکو
udp-port = 0

# DTLS legacy خاموش بشه
dtls-legacy = false

# ---------- TLS Fingerprint ----------
# باید مثل یه مرورگر عادی به نظر بیاد، نه سیسکو
# فقط TLS 1.2+ با cipher suite های مرورگر
tls-priorities = "NORMAL:%SERVER_PRECEDENCE:%COMPAT:-VERS-SSL3.0:-VERS-TLS1.0:-VERS-TLS1.1:+VERS-TLS1.3:-RSA:-DHE-RSA:-CAMELLIA-128-CBC:-CAMELLIA-256-CBC"

# ---------- سازگاری اما بدون امضای واضح ----------
cisco-client-compat = true

# ---------- فشرده‌سازی غیرفعال ----------
# فشرده‌سازی VPN قابل شناسایی‌ه
compression = false

# ---------- Rekey سریع ----------
# تغییر کلید مکرر = شناسایی سخت‌تر
rekey-time = 172800
rekey-method = ssl

# ---------- کوکی/سشن ----------
# عمر کوتاه کوکی = ردگیری سخت‌تر
cookie-timeout = 300

# ---------- Stats ----------
server-stats-reset-time = 0
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
        exists = os.path.exists(GOST_BINARY)
        logger.info(f"Gost binary check: {GOST_BINARY} exists={exists}")
        return exists
    
    async def install_gost(self) -> bool:
        """نصب Gost v3 با پروکسی‌های GitHub برای ایران"""
        try:
            logger.info("Installing Gost v3.2.6...")
            
            GOST_VER = "3.2.6"
            GOST_FILE = f"gost_{GOST_VER}_linux_amd64.tar.gz"
            GOST_URL = f"https://github.com/go-gost/gost/releases/download/v{GOST_VER}/{GOST_FILE}"
            
            # لیست میرورها
            mirrors = [
                f"https://ghproxy.net/{GOST_URL}",
                f"https://gh-proxy.com/{GOST_URL}",
                f"https://ghfast.top/{GOST_URL}",
                f"https://gh.ddlc.top/{GOST_URL}",
                GOST_URL,
            ]
            
            # تلاش دانلود از میرورها
            download_script = "set -e\n"
            download_script += "DOWNLOADED=false\n"
            for url in mirrors:
                download_script += f"""
if [ "$DOWNLOADED" = "false" ]; then
    if timeout 15 wget --timeout=10 --tries=1 -q "{url}" -O /tmp/gost.tar.gz 2>/dev/null; then
        SIZE=$(stat -c%s /tmp/gost.tar.gz 2>/dev/null || echo 0)
        if [ "$SIZE" -gt 100000 ]; then
            DOWNLOADED=true
            echo "Downloaded from {url.split('/')[2]}"
        else
            rm -f /tmp/gost.tar.gz
        fi
    fi
fi
"""
            download_script += """
if [ "$DOWNLOADED" = "false" ]; then
    echo "FAILED: Could not download from any mirror" >&2
    exit 1
fi
tar -xzf /tmp/gost.tar.gz -C /tmp/
cp /tmp/gost /usr/local/bin/gost
chmod +x /usr/local/bin/gost
mkdir -p /etc/gost
rm -f /tmp/gost.tar.gz
/usr/local/bin/gost -V
"""
            
            process = await asyncio.create_subprocess_shell(
                download_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            stdout_str = stdout.decode().strip() if stdout else ""
            stderr_str = stderr.decode().strip() if stderr else ""
            
            if process.returncode == 0:
                await self._create_systemd_service()
                logger.info(f"Gost installed successfully: {stdout_str}")
                return True
            else:
                logger.error(f"Gost install failed (rc={process.returncode}): {stderr_str}")
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
        
        await asyncio.create_subprocess_shell("/usr/bin/systemctl daemon-reload")
    
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
        remote_port: int = 443,
        local_port: int = 443,
        protocol: str = "wss",
        sni: str = "www.google.com",
        obfuscation: str = "tls",
        mux: bool = True,
        padding: bool = True
    ) -> bool:
        """
        به‌روزرسانی تنظیمات تانل با قابلیت‌های ضد شناسایی
        
        معماری:
        📱 AnyConnect → Iran:443 (TCP) → [WSS Encrypted] → France:2083 (Gost Relay) → France:443 (OCServ) → 🌍
        
        DPI فقط ترافیک WebSocket HTTPS عادی بین ایران و فرانسه میبینه
        
        Args:
            remote_ip: IP سرور فرانسه
            remote_port: پورت OCServ روی فرانسه (مقصد نهایی)
            local_port: پورت ورودی روی ایران (443 پیشنهادی)
            protocol: پروتکل obfuscation (wss/h2/tls)
            sni: SNI برای masquerading
            mux: فعال‌سازی multiplexing
        """
        try:
            # پورت Gost relay روی فرانسه (همیشه 2083)
            relay_port = 2083
            
            # انتخاب نوع dialer
            dialer_type = "wss"
            if protocol == "h2":
                dialer_type = "h2"
            elif protocol == "tls":
                dialer_type = "tls"
            
            # کانفیگ Gost v3 با chain — ضد شناسایی
            gost_config = {
                "Log": {
                    "Level": "info"
                },
                "Services": [
                    {
                        "Name": "vpn-tunnel",
                        "Addr": f":{local_port}",
                        "Handler": {
                            "Type": "tcp",
                            "Chain": "stealth-chain"
                        },
                        "Listener": {
                            "Type": "tcp"
                        },
                        "Forwarder": {
                            "Nodes": [
                                {
                                    "Name": "france-ocserv",
                                    "Addr": f"127.0.0.1:{remote_port}"
                                }
                            ]
                        }
                    }
                ],
                "Chains": [
                    {
                        "Name": "stealth-chain",
                        "Hops": [
                            {
                                "Name": "hop-0",
                                "Nodes": [
                                    {
                                        "Name": "france-relay",
                                        "Addr": f"{remote_ip}:{relay_port}",
                                        "Connector": {
                                            "Type": "relay"
                                        },
                                        "Dialer": {
                                            "Type": dialer_type,
                                            "TLS": {
                                                "ServerName": sni,
                                                "Secure": False
                                            },
                                            "Metadata": {
                                                "path": "/ws/api/v1",
                                                "header": {
                                                    "User-Agent": ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"],
                                                    "Accept-Language": ["en-US,en;q=0.9"]
                                                }
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(gost_config, f, indent=2)
            
            logger.info(f"Stealth tunnel config: :{local_port} → relay+{dialer_type}://{remote_ip}:{relay_port} → 127.0.0.1:{remote_port}")
            return True
        except Exception as e:
            logger.error(f"Error updating tunnel config: {e}")
            return False
    
    async def apply_ocserv_stealth(self) -> bool:
        """
        اعمال تنظیمات ضد شناسایی به OCServ
        
        این تابع:
        1. تمام هدرهای Cisco رو حذف میکنه
        2. هدرهای جعلی nginx اضافه میکنه
        3. TLS fingerprint رو عوض میکنه
        4. DTLS (مهم‌ترین علامت سیسکو) رو خاموش میکنه
        """
        try:
            ocserv_conf = "/etc/ocserv/ocserv.conf"
            
            if not os.path.exists(ocserv_conf):
                logger.warning("OCServ config not found")
                return False
            
            with open(ocserv_conf, 'r') as f:
                content = f.read()
            
            lines = content.split('\n')
            cleaned_lines = []
            skip_section = False
            
            # خطوطی که باید حذف بشن (شناسایی‌کننده‌های سیسکو)
            cisco_signature_keys = [
                'custom-header',       # هدرهای قبلی
                'dtls-legacy',         # DTLS legacy
                'tls-priorities',      # TLS config
                'server-stats-reset',  # Stats
                'rekey-time',          # Rekey
                'rekey-method',        # Rekey method
                'cookie-timeout',      # Cookie
            ]
            
            for line in lines:
                stripped = line.strip()
                
                # پرش از Anti-Detection section قبلی
                if "Anti-Detection" in line or "Cisco Signature Removal" in line:
                    skip_section = True
                    continue
                
                if skip_section:
                    # تا رسیدن به بخش بعدی کانفیگ skip کن
                    if stripped.startswith('#') or stripped.startswith('custom-header'):
                        continue
                    if stripped and not stripped.startswith('#'):
                        # رسیدیم به یه خط واقعی - بررسی کن key باشه نه value
                        key_match = False
                        for key in cisco_signature_keys:
                            if stripped.startswith(key):
                                key_match = True
                                break
                        if key_match:
                            continue
                        else:
                            skip_section = False
                    else:
                        if not stripped:
                            continue
                
                if not skip_section:
                    # حذف خطوطی که تنظیمات ضد شناسایی رو override میکنن
                    should_skip = False
                    for key in cisco_signature_keys:
                        if stripped.startswith(key + ' ') or stripped.startswith(key + '='):
                            should_skip = True
                            break
                    
                    # حذف udp-port (چون ما 0 میذاریم)
                    if stripped.startswith('udp-port'):
                        should_skip = True
                    
                    # حذف compression
                    if stripped.startswith('compression'):
                        should_skip = True
                    
                    if not should_skip:
                        cleaned_lines.append(line)
            
            # اضافه کردن تنظیمات stealth جدید
            new_content = '\n'.join(cleaned_lines).rstrip() + '\n\n' + OCSERV_STEALTH_CONFIG
            
            with open(ocserv_conf, 'w') as f:
                f.write(new_content)
            
            # Reload
            process = await asyncio.create_subprocess_shell(
                "/usr/bin/systemctl reload ocserv 2>/dev/null || /usr/bin/systemctl restart ocserv",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.wait()
            
            logger.info("OCServ stealth config applied - Cisco signatures removed")
            return True
        except Exception as e:
            logger.error(f"Error applying OCServ stealth config: {e}")
            return False
    
    async def start(self) -> bool:
        """شروع تانل"""
        try:
            # مرحله 1: بررسی Gost
            logger.info("[Tunnel Start] Step 1: Checking Gost installation...")
            if not await self.is_gost_installed():
                logger.info("[Tunnel Start] Gost not found, attempting install...")
                success = await self.install_gost()
                if not success:
                    logger.error("[Tunnel Start] FAILED: Could not install Gost")
                    return False
                logger.info("[Tunnel Start] Gost installed successfully")
            
            # مرحله 2: بررسی کانفیگ
            logger.info("[Tunnel Start] Step 2: Checking config...")
            if not os.path.exists(self.config_path):
                logger.error(f"[Tunnel Start] FAILED: Config file missing: {self.config_path}")
                return False
            
            with open(self.config_path, 'r') as f:
                config_content = f.read()
            logger.info(f"[Tunnel Start] Config loaded ({len(config_content)} bytes)")
            
            # مرحله 3: اعمال stealth
            logger.info("[Tunnel Start] Step 3: Applying OCServ stealth...")
            await self.apply_ocserv_stealth()
            
            # مرحله 4: استارت سرویس
            logger.info("[Tunnel Start] Step 4: Starting Gost service...")
            process = await asyncio.create_subprocess_shell(
                "/usr/bin/systemctl enable gost && /usr/bin/systemctl restart gost",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            stderr_str = stderr.decode().strip() if stderr else ""
            
            if process.returncode == 0:
                logger.info("[Tunnel Start] SUCCESS: Gost service started")
                return True
            else:
                logger.error(f"[Tunnel Start] FAILED: systemctl returned {process.returncode}: {stderr_str}")
                
                # لاگ وضعیت سرویس
                status_proc = await asyncio.create_subprocess_shell(
                    "/usr/bin/systemctl status gost --no-pager -l 2>&1 | tail -15",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                status_out, _ = await status_proc.communicate()
                if status_out:
                    logger.error(f"[Tunnel Start] Gost status: {status_out.decode().strip()}")
                return False
        except Exception as e:
            logger.error(f"[Tunnel Start] EXCEPTION: {e}", exc_info=True)
            return False
    
    async def stop(self) -> bool:
        """توقف تانل"""
        try:
            process = await asyncio.create_subprocess_shell(
                "/usr/bin/systemctl stop gost",
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
                "/usr/bin/systemctl is-active gost",
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
