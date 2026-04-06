"""
Firewall & DNS Service
سرویس مدیریت فایروال (IPTables) و میکرودی‌ان‌اس (DNSMasq) به تفکیک گروه
"""

import os
import aiohttp
import asyncio
import logging
import json
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.group import UserGroup
from models.user import User

logger = logging.getLogger(__name__)

# System paths
OCSERV_DNS_DIR = "/etc/ocserv/dns"
DNSMASQ_BASE_PORT = 53000

# Category Blocklists
CATEGORIES = {
    "porn": "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/porn/hosts",
    "ads": "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
    "gambling": "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/gambling/hosts",
    "fakenews": "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/fakenews/hosts"
}

class FirewallService:

    @staticmethod
    async def get_online_users(group_id=None):
        """دریافت کاربران آنلاین و آی‌پی آن‌ها از طریق occtl"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "occtl", "show", "users", "-o", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"occtl error: {stderr.decode()}")
                return []
            
            output = stdout.decode().strip()
            if not output:
                return []
                
            users = json.loads(output)
            
            result = []
            for u in users:
                # Groupname in ocserv might be group ID if we set it up, but usually we just use the API DB
                result.append({
                    "username": u.get("Username"),
                    "vpn_ip": u.get("VPN-IPv4") or u.get("VPN-IP"),
                })
            return result
        except BaseException as e:
            logger.error(f"Failed to get online online users: {e}")
            return []

    @classmethod
    async def setup_group_dns(cls, group: UserGroup):
        """راه‌اندازی میکرو-دی‌ان‌اس برای دسته بندی‌های گروه"""
        categories = group.blocked_categories or []
        explicit_blocks = group.blocked_domains or []
        
        # Ensure dir exists
        os.makedirs(OCSERV_DNS_DIR, exist_ok=True)
        conf_file = f"{OCSERV_DNS_DIR}/group_{group.id}.conf"
        hosts_file = f"{OCSERV_DNS_DIR}/group_{group.id}.hosts"
        
        # Determine if we even need custom DNS
        if not categories and not explicit_blocks:
            # Cleanup if they turned it off
            if os.path.exists(conf_file): os.remove(conf_file)
            if os.path.exists(hosts_file): os.remove(hosts_file)
            await asyncio.create_subprocess_exec("systemctl", "stop", f"ocserv-dns@{group.id}")
            return
            
        # Download blocklists for categories
        domains = set()
        for cat in categories:
            url = CATEGORIES.get(cat)
            if not url: continue
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            for line in content.split('\n'):
                                line = line.strip()
                                if line.startswith("0.0.0.0"):
                                    parts = line.split()
                                    if len(parts) >= 2 and parts[1] != "0.0.0.0":
                                        domains.add(parts[1])
            except Exception as e:
                logger.error(f"Failed to fetch {cat}: {e}")
        
        # Add Explicitly Blocked Domains from user interface
        for domain in explicit_blocks:
            # Block the domain itself
            domains.add(domain)
            # And add wildcard conf structure for the domain in dnsmasq
            try:
                base_domain = domain.replace('www.', '')
                domains.add(base_domain)
            except Exception:
                pass
        
        # Write hosts file (Fast resolving)
        with open(hosts_file, "w") as f:
            for domain in domains:
                f.write(f"0.0.0.0 {domain}\n")
                
        # Write additional conf (for wildcard blocks)
        with open(conf_file, "w") as f:
            f.write(f"# Group {group.name} DNS Config\n")
            for domain in explicit_blocks:
                base = domain.replace('www.', '')
                f.write(f"address=/.{base}/0.0.0.0\n")
            
        # Restart the dns service for this group
        await asyncio.create_subprocess_exec(
            "systemctl", "restart", f"ocserv-dns@{group.id}", 
            stdout=asyncio.subprocess.DEVNULL, 
            stderr=asyncio.subprocess.DEVNULL
        )

    @classmethod
    async def sync_group(cls, group_id: int, db: AsyncSession):
        """همگام‌سازی فایروال تمام کاربران یک گروه"""
        result = await db.execute(select(UserGroup).where(UserGroup.id == group_id))
        group = result.scalar_one_or_none()
        if not group: return
        
        # 1. Setup DNS daemon for categories
        await cls.setup_group_dns(group)
        
        # 2. Re-apply iptables for all ONLINE users in this group
        online_users = await cls.get_online_users()
        
        for u in online_users:
            username = u['username']
            vpn_ip = u['vpn_ip']
            if not vpn_ip: continue
            
            # Check if user is in this group
            user_result = await db.execute(select(User).where(User.username == username))
            user = user_result.scalar_one_or_none()
            
            if user and user.group_id == group.id:
                # First remove old rules
                await cls.remove_user_rules(vpn_ip)
                # Then apply new rules
                await cls.apply_user_rules(user, group, vpn_ip)

    @staticmethod
    async def apply_user_rules(user: User, group: UserGroup, vpn_ip: str):
        """اعمال قوانین فایروال برای یک کاربر خاص"""
        import subprocess
        
        # 1. Explicit domain blocks (IPTables String Match)
        blocked_domains = group.blocked_domains or []
        for domain in blocked_domains:
            # Extract core keyword for DPI (e.g. "instagram.com" -> "instagram")
            # to match raw DNS packets (which don't use literal dots) and all subdomains efficiently.
            keyword = domain.split('.')[0] if '.' in domain else domain
            if len(keyword) < 3: 
                keyword = domain # Fallback if too short
                
            # Block DNS (UDP 53)
            subprocess.run(["iptables", "-I", "FORWARD", "-s", vpn_ip, "-p", "udp", "--dport", "53", 
                            "-m", "string", "--string", keyword, "--algo", "bm", "-j", "DROP"])
            # Block HTTPS (TCP 443) -> Kills SNI
            subprocess.run(["iptables", "-I", "FORWARD", "-s", vpn_ip, "-p", "tcp", "--dport", "443", 
                            "-m", "string", "--string", keyword, "--algo", "bm", "-j", "DROP"])
            # Block HTTP3/QUIC (UDP 443) -> Kills UDP bypass for instagram/youtube
            subprocess.run(["iptables", "-I", "FORWARD", "-s", vpn_ip, "-p", "udp", "--dport", "443", 
                            "-m", "string", "--string", keyword, "--algo", "bm", "-j", "DROP"])
            # Block HTTP (TCP 80)
            subprocess.run(["iptables", "-I", "FORWARD", "-s", vpn_ip, "-p", "tcp", "--dport", "80", 
                            "-m", "string", "--string", keyword, "--algo", "bm", "-j", "DROP"])

        # 2. DNS Interception (Categorical & Exact Domains)
        categories = group.blocked_categories or []
        domains = group.blocked_domains or []
        
        if categories or domains:
            port = DNSMASQ_BASE_PORT + group.id
            subprocess.run(["iptables", "-t", "nat", "-I", "PREROUTING", "-s", vpn_ip, "-p", "udp", 
                            "--dport", "53", "-j", "REDIRECT", "--to-ports", str(port)])
            subprocess.run(["iptables", "-t", "nat", "-I", "PREROUTING", "-s", vpn_ip, "-p", "tcp", 
                            "--dport", "53", "-j", "REDIRECT", "--to-ports", str(port)])
            # Block well-known DoH (DNS-over-HTTPS) providers to prevent bypass
            doh_ips = ["8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1", "9.9.9.9", "149.112.112.112"]
            for dip in doh_ips:
                subprocess.run(["iptables", "-I", "FORWARD", "-s", vpn_ip, "-d", dip, "-p", "tcp", "--dport", "443", "-j", "DROP"])
                subprocess.run(["iptables", "-I", "FORWARD", "-s", vpn_ip, "-d", dip, "-p", "udp", "--dport", "443", "-j", "DROP"])
        else:
            # Force them to use our global DNS (prevent bypass using DoH/Custom DNS)
            subprocess.run(["iptables", "-t", "nat", "-I", "PREROUTING", "-s", vpn_ip, "-p", "udp", 
                            "--dport", "53", "-j", "REDIRECT", "--to-ports", "53"])

    @staticmethod
    async def remove_user_rules(vpn_ip: str):
        """حذف تمامی رول‌های مربوط به کاربر آی‌پی"""
        import subprocess
        # We delete all PREROUTING NAT rules involving this IP
        while True:
            r = subprocess.run(f"iptables -t nat -S PREROUTING | grep '{vpn_ip}/32'", shell=True, capture_output=True, text=True)
            if not r.stdout.strip(): break
            # Parse the rule to delete it (e.g. "-A PREROUTING -s ...")
            rule = r.stdout.split('\n')[0]
            del_rule = rule.replace('-A ', '-D ')
            subprocess.run(f"iptables -t nat {del_rule}", shell=True)

        # Delete all FORWARD rules involving this IP
        while True:
            r = subprocess.run(f"iptables -S FORWARD | grep '{vpn_ip}/32'", shell=True, capture_output=True, text=True)
            if not r.stdout.strip(): break
            rule = r.stdout.split('\n')[0]
            del_rule = rule.replace('-A ', '-D ')
            subprocess.run(f"iptables {del_rule}", shell=True)
