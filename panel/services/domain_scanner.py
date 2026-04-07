import asyncio
import socket
import logging
import shutil
from typing import List, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import async_session
from models.group import UserGroup

# Use uvicorn's active logger so it appears in journalctl
logger = logging.getLogger("uvicorn.error")

CMD_IPSET = shutil.which("ipset") or "/sbin/ipset"

# Common proxy subdomains used by apps to bypass SNI/DNS
COMMON_SUBDOMAINS = [
    "", "www", "api", "graph", "mqtt", "chat", "edge-chat", "edge", 
    "b.i", "i", "scontent", "cdn", "m", "developer"
]

class DomainScanner:
    """
    Background worker that actively scans and resolves domains to IPv4/IPv6 addresses
    and continually feeds them into the Linux Kernel IPSet for each group.
    """
    
    @staticmethod
    async def resolve_domain(domain: str) -> Set[str]:
        """Resolves a domain name to a set of IP addresses."""
        ips = set()
        loop = asyncio.get_event_loop()
        try:
            # getaddrinfo resolves both IPv4 and IPv6
            # We use thread executor to not block the async loop
            info = await loop.run_in_executor(None, socket.getaddrinfo, domain, None)
            for item in info:
                # item[4][0] contains the IP address
                ips.add(item[4][0])
        except Exception:
            pass # Domain not found or offline
        return ips

    @classmethod
    async def scan_and_update(cls):
        """Main loop execution for full IP aggregation."""
        logger.info("DomainScanner: Starting scheduled IP extraction...")
        
        async with async_session() as db:
            result = await db.execute(select(UserGroup))
            groups = result.scalars().all()
            
            for group in groups:
                explicit_blocks = group.blocked_domains or []
                if not explicit_blocks:
                    continue
                    
                target_ips = set()
                # 1. Resolve all domains and common subdomains
                for root_domain in explicit_blocks:
                    # Clean the domain
                    clean_domain = root_domain.strip().replace("www.", "")
                    if not clean_domain: continue
                    
                    for sub in COMMON_SUBDOMAINS:
                        target = f"{sub}.{clean_domain}" if sub else clean_domain
                        resolved = await cls.resolve_domain(target)
                        target_ips.update(resolved)
                        
                if target_ips:
                    logger.info(f"DomainScanner: Found {len(target_ips)} IPs for Group {group.name}")
                
                
                # 2. Inject into IPSet
                await cls.sync_group_ipset(group.id, target_ips)
                
        logger.info("DomainScanner: Finished IP aggregation cycle.")

    @classmethod
    async def scan_group(cls, group: UserGroup):
        """Actively scans IPs for a single group, called upon group update."""
        try:
            explicit_blocks = group.blocked_domains or []
            if not explicit_blocks:
                logger.info(f"DomainScanner: No explicit blocks for group {group.name}")
                return
                
            target_ips = set()
            for root_domain in explicit_blocks:
                clean_domain = root_domain.strip().replace("www.", "")
                if not clean_domain: continue
                
                for sub in COMMON_SUBDOMAINS:
                    target = f"{sub}.{clean_domain}" if sub else clean_domain
                    target_ips.update(await cls.resolve_domain(target))
                    
            if target_ips:
                await cls.sync_group_ipset(group.id, target_ips)
                logger.info(f"DomainScanner: Sync'd {len(target_ips)} IPs for group {group.name} instantly.")
            else:
                logger.warning(f"DomainScanner: Could not resolve ANY IPs for group {group.name} domains.")
        except Exception as e:
            logger.error(f"DomainScanner: ERROR in scan_group for {group.name}: {e}", exc_info=True)

    @classmethod
    async def sync_group_ipset(cls, group_id: int, ips: Set[str]):
        """Creates/Updates the Linux IPSet with the scanned IPs"""
        import subprocess
        
        set_name = f"ocserv_g_{group_id}_ips"
        
        # 1. Ensure IPSet exists
        subprocess.run([CMD_IPSET, "create", set_name, "hash:ip", "-exist"], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([CMD_IPSET, "create", f"{set_name}_v6", "hash:ip", "family", "inet6", "-exist"], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 2. Add IPs (we use a loop to handle ipv4/ipv6 separately)
        for ip in ips:
            # Detect ipv6
            if ":" in ip:
                subprocess.run([CMD_IPSET, "add", f"{set_name}_v6", ip, "-exist"], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run([CMD_IPSET, "add", set_name, ip, "-exist"], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @classmethod
    async def start_background_loop(cls, interval_seconds: int = 10800):
        """Runs the scanner periodically (default: 3 hours)"""
        # Sleep initially to let the server startup cleanly
        await asyncio.sleep(10)
        while True:
            try:
                await cls.scan_and_update()
            except Exception as e:
                logger.error(f"DomainScanner encountered an error: {e}")
            await asyncio.sleep(interval_seconds)
