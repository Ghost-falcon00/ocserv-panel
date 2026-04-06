#!/opt/ocserv-panel/venv/bin/python3
import os
import sys
import asyncio

# Add panel directory to path
sys.path.insert(0, '/opt/ocserv-panel/panel')

from services.firewall_service import FirewallService

async def main():
    vpn_ip = os.environ.get('IP_REMOTE')
    
    if not vpn_ip:
        return
        
    await FirewallService.remove_user_rules(vpn_ip)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        pass
