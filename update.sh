#!/bin/bash
# OCServ Panel Auto-Updater Script

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Ensure we are in the right directory
cd /opt/ocserv-panel || exit 1

# Fix git dubious ownership if executed as different user or root
git config --global --add safe.directory /opt/ocserv-panel

# Fetch latest from GitHub
git fetch origin main > /dev/null 2>&1

# Hard reset to ensure clean state
git reset --hard origin/main > /dev/null 2>&1

# Fix permissions
chmod +x install.sh
chmod +x update.sh

# Update Python dependencies
./venv/bin/pip install -r requirements.txt > /dev/null 2>&1

# Restart the service (this script is spawned by the service, so we use nohup style)
systemctl restart ocserv-panel
