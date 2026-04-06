#!/usr/bin/env python3
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

async def main():
    username = os.environ.get('USERNAME')
    vpn_ip = os.environ.get('IP_REMOTE')
    
    if not username or not vpn_ip:
        return
        
    async with async_session() as session:
        user_result = await session.execute(select(User).where(User.username == username))
        user = user_result.scalar_one_or_none()
        
        if not user or not user.group_id:
            return
            
        group_result = await session.execute(select(UserGroup).where(UserGroup.id == user.group_id))
        group = group_result.scalar_one_or_none()
        
        if not group:
            return
            
        # Optional: update user's last_connection here if we want!
        
        # Apply rules
        await FirewallService.apply_user_rules(user, group, vpn_ip)

if __name__ == "__main__":
    asyncio.run(main())
