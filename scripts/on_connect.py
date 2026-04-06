#!/opt/ocserv-panel/venv/bin/python3
import os
import sys
import asyncio

# Add panel directory to path
sys.path.insert(0, '/opt/ocserv-panel/panel')

from sqlalchemy import select
from models.database import async_session
from models.user import User
from models.group import UserGroup
from services.firewall_service import FirewallService

import logging

# Configure logging to see what happens on connect
logging.basicConfig(filename='/opt/ocserv-panel/panel/logs/firewall.log', level=logging.DEBUG, 
                    format='%(asctime)s %(levelname)s: %(message)s')

async def main():
    username = os.environ.get('USERNAME')
    vpn_ip = os.environ.get('IP_REMOTE')
    
    logging.info(f"Connect triggered: User={username}, vpn_ip={vpn_ip}")
    
    if not username or not vpn_ip:
        logging.error("Missing USERNAME or IP_REMOTE in environment.")
        return
        
    async with async_session() as session:
        user_result = await session.execute(select(User).where(User.username == username))
        user = user_result.scalar_one_or_none()
        
        if not user or not user.group_id:
            logging.info(f"User {username} not found or has no group.")
            return
            
        group_result = await session.execute(select(UserGroup).where(UserGroup.id == user.group_id))
        group = group_result.scalar_one_or_none()
        
        if not group:
            logging.info(f"Group {user.group_id} not found.")
            return
            
        logging.info(f"Applying firewall rules for {username} (IP: {vpn_ip}, Group: {group.name})")
        # Apply rules
        await FirewallService.apply_user_rules(user, group, vpn_ip)
        logging.info("Firewall rules applied.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Fatal error in on_connect hook: {e}")
