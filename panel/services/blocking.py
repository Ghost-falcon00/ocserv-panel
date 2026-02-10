"""
Content Blocking Service
سرویس مسدودسازی محتوا - Ad Blocker, Porn, Gambling
"""

import asyncio
import aiohttp
import aiofiles
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BlockingService:
    """
    سرویس مسدودسازی محتوا
    - Ad Blocker
    - بلاک سایت‌های پورن
    - بلاک سایت‌های قمار
    - بلاک سایت‌های مخرب
    """
    
    # ═══════════════════════════════════════════════════════════
    # منابع بلاک‌لیست از GitHub (بروز و رایگان)
    # ═══════════════════════════════════════════════════════════
    BLOCKLIST_SOURCES = {
        "ads": {
            "name": "Ad Blocker",
            "description": "بلاک تبلیغات و ترکرها",
            "sources": [
                "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
                "https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/EnglishFilter/sections/adservers.txt",
                "https://raw.githubusercontent.com/anudeepND/blacklist/master/adservers.txt",
            ],
            "enabled": False,
        },
        "porn": {
            "name": "Porn Blocker",
            "description": "بلاک سایت‌های پورنوگرافی",
            "sources": [
                "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/porn-only/hosts",
                "https://raw.githubusercontent.com/Sinfonietta/hostfiles/master/pornography-hosts",
            ],
            "enabled": False,
        },
        "gambling": {
            "name": "Gambling Blocker",
            "description": "بلاک سایت‌های قمار و شرط‌بندی",
            "sources": [
                "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/gambling-only/hosts",
                "https://raw.githubusercontent.com/Sinfonietta/hostfiles/master/gambling-hosts",
            ],
            "enabled": False,
        },
        "malware": {
            "name": "Malware Blocker",
            "description": "بلاک سایت‌های مخرب و فیشینگ",
            "sources": [
                "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/fakenews-gambling-porn/hosts",
                "https://raw.githubusercontent.com/mitchellkrogza/Phishing.Database/master/phishing-domains-ACTIVE.txt",
            ],
            "enabled": False,
        },
        "social": {
            "name": "Social Media Blocker",
            "description": "بلاک شبکه‌های اجتماعی (اختیاری)",
            "sources": [
                "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/social-only/hosts",
            ],
            "enabled": False,
        },
    }
    
    HOSTS_FILE = "/etc/ocserv/blocked-hosts.txt"
    DNSMASQ_CONFIG = "/etc/dnsmasq.d/ocserv-block.conf"
    SETTINGS_FILE = "/opt/ocserv-panel/panel/data/blocking_settings.json"
    
    def __init__(self):
        self.blocked_domains: set = set()
        self.settings: Dict = {}
        self.last_update: Optional[datetime] = None
    
    async def load_settings(self) -> Dict:
        """بارگذاری تنظیمات از فایل"""
        import json
        try:
            if os.path.exists(self.SETTINGS_FILE):
                async with aiofiles.open(self.SETTINGS_FILE, 'r') as f:
                    content = await f.read()
                    self.settings = json.loads(content)
            else:
                self.settings = {
                    "ads": False,
                    "porn": False,
                    "gambling": False,
                    "malware": False,
                    "social": False,
                    "custom_domains": [],
                    "whitelist": [],
                    "last_update": None,
                }
            return self.settings
        except Exception as e:
            logger.error(f"Error loading blocking settings: {e}")
            return {}
    
    async def save_settings(self) -> bool:
        """ذخیره تنظیمات"""
        import json
        try:
            os.makedirs(os.path.dirname(self.SETTINGS_FILE), exist_ok=True)
            async with aiofiles.open(self.SETTINGS_FILE, 'w') as f:
                await f.write(json.dumps(self.settings, indent=2, default=str))
            return True
        except Exception as e:
            logger.error(f"Error saving blocking settings: {e}")
            return False
    
    async def toggle_category(self, category: str, enabled: bool) -> bool:
        """فعال/غیرفعال کردن یک دسته"""
        await self.load_settings()
        
        if category not in self.BLOCKLIST_SOURCES:
            return False
        
        self.settings[category] = enabled
        await self.save_settings()
        
        # بروزرسانی بلاک‌لیست
        await self.update_blocklists()
        
        logger.info(f"Blocking category '{category}' {'enabled' if enabled else 'disabled'}")
        return True
    
    async def add_custom_domain(self, domain: str) -> bool:
        """اضافه کردن دامنه سفارشی به بلاک‌لیست"""
        await self.load_settings()
        
        if "custom_domains" not in self.settings:
            self.settings["custom_domains"] = []
        
        domain = domain.lower().strip()
        if domain and domain not in self.settings["custom_domains"]:
            self.settings["custom_domains"].append(domain)
            await self.save_settings()
            await self.update_blocklists()
            return True
        return False
    
    async def remove_custom_domain(self, domain: str) -> bool:
        """حذف دامنه سفارشی"""
        await self.load_settings()
        
        domain = domain.lower().strip()
        if domain in self.settings.get("custom_domains", []):
            self.settings["custom_domains"].remove(domain)
            await self.save_settings()
            await self.update_blocklists()
            return True
        return False
    
    async def add_whitelist(self, domain: str) -> bool:
        """اضافه کردن دامنه به لیست سفید (استثنا)"""
        await self.load_settings()
        
        if "whitelist" not in self.settings:
            self.settings["whitelist"] = []
        
        domain = domain.lower().strip()
        if domain and domain not in self.settings["whitelist"]:
            self.settings["whitelist"].append(domain)
            await self.save_settings()
            await self.update_blocklists()
            return True
        return False
    
    async def fetch_blocklist(self, url: str) -> set:
        """دانلود بلاک‌لیست از یک URL"""
        domains = set()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        for line in content.split('\n'):
                            line = line.strip()
                            
                            # Skip comments and empty lines
                            if not line or line.startswith('#') or line.startswith('!'):
                                continue
                            
                            # Parse hosts file format (0.0.0.0 domain.com or 127.0.0.1 domain.com)
                            if line.startswith('0.0.0.0') or line.startswith('127.0.0.1'):
                                parts = line.split()
                                if len(parts) >= 2:
                                    domain = parts[1].lower()
                                    if domain and domain != 'localhost':
                                        domains.add(domain)
                            else:
                                # Plain domain format
                                domain = line.split()[0].lower()
                                if '.' in domain and not domain.startswith('!'):
                                    domains.add(domain)
        
        except Exception as e:
            logger.error(f"Error fetching blocklist from {url}: {e}")
        
        return domains
    
    async def update_blocklists(self) -> bool:
        """بروزرسانی تمام بلاک‌لیست‌ها"""
        await self.load_settings()
        
        all_domains = set()
        
        # جمع‌آوری دامنه‌ها از منابع فعال
        for category, info in self.BLOCKLIST_SOURCES.items():
            if self.settings.get(category, False):
                logger.info(f"Fetching blocklist: {category}")
                for source_url in info["sources"]:
                    domains = await self.fetch_blocklist(source_url)
                    all_domains.update(domains)
                    logger.info(f"  - Got {len(domains)} domains from {source_url}")
        
        # اضافه کردن دامنه‌های سفارشی
        custom = self.settings.get("custom_domains", [])
        all_domains.update(custom)
        
        # حذف دامنه‌های لیست سفید
        whitelist = set(self.settings.get("whitelist", []))
        all_domains -= whitelist
        
        self.blocked_domains = all_domains
        
        # ذخیره در فایل
        await self._write_hosts_file()
        await self._write_dnsmasq_config()
        
        self.settings["last_update"] = datetime.now().isoformat()
        self.settings["total_blocked"] = len(all_domains)
        await self.save_settings()
        
        logger.info(f"Updated blocklists: {len(all_domains)} domains blocked")
        return True
    
    async def _write_hosts_file(self):
        """نوشتن فایل hosts برای بلاک"""
        try:
            os.makedirs(os.path.dirname(self.HOSTS_FILE), exist_ok=True)
            
            async with aiofiles.open(self.HOSTS_FILE, 'w') as f:
                await f.write("# OCServ Panel - Blocked Hosts\n")
                await f.write(f"# Updated: {datetime.now().isoformat()}\n")
                await f.write(f"# Total: {len(self.blocked_domains)} domains\n\n")
                
                for domain in sorted(self.blocked_domains):
                    await f.write(f"0.0.0.0 {domain}\n")
            
            logger.info(f"Wrote {len(self.blocked_domains)} domains to hosts file")
        
        except Exception as e:
            logger.error(f"Error writing hosts file: {e}")
    
    async def _write_dnsmasq_config(self):
        """نوشتن کانفیگ dnsmasq برای بلاک DNS"""
        try:
            os.makedirs(os.path.dirname(self.DNSMASQ_CONFIG), exist_ok=True)
            
            async with aiofiles.open(self.DNSMASQ_CONFIG, 'w') as f:
                await f.write("# OCServ Panel - DNS Blocklist\n")
                await f.write(f"# Updated: {datetime.now().isoformat()}\n\n")
                
                for domain in sorted(self.blocked_domains):
                    # Return NXDOMAIN for blocked domains
                    await f.write(f"address=/{domain}/\n")
            
            # Reload dnsmasq if running
            os.system("/usr/bin/systemctl reload dnsmasq 2>/dev/null || true")
            
            logger.info("Updated dnsmasq config")
        
        except Exception as e:
            logger.error(f"Error writing dnsmasq config: {e}")
    
    async def get_status(self) -> Dict:
        """دریافت وضعیت بلاک‌ها"""
        await self.load_settings()
        
        categories = {}
        for cat, info in self.BLOCKLIST_SOURCES.items():
            categories[cat] = {
                "name": info["name"],
                "description": info["description"],
                "enabled": self.settings.get(cat, False),
            }
        
        return {
            "categories": categories,
            "total_blocked": self.settings.get("total_blocked", 0),
            "custom_domains": self.settings.get("custom_domains", []),
            "whitelist": self.settings.get("whitelist", []),
            "last_update": self.settings.get("last_update"),
        }
    
    async def search_blocked(self, query: str) -> List[str]:
        """جستجو در دامنه‌های بلاک شده"""
        query = query.lower()
        results = [d for d in self.blocked_domains if query in d]
        return results[:100]  # حداکثر 100 نتیجه


# Singleton instance
blocking_service = BlockingService()
