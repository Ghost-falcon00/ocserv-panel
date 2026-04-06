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
chmod +x scripts/*.py

# Apply Database Migrations safely using Python's built-in sqlite3 (avoids missing sqlite3 binary issues)
python3 -c '
import sqlite3
import os
db_path = "panel/data/panel.db"
if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("ALTER TABLE user_groups ADD COLUMN blocked_categories JSON;")
        conn.commit()
        conn.close()
    except sqlite3.OperationalError as e:
        pass # Column might already exist
'

# Setup OCServ DNS Template Service
cat > /etc/systemd/system/ocserv-dns@.service << 'EOF'
[Unit]
Description=OCServ per-group DNS for Group %I
After=network.target

[Service]
Type=simple
ExecStart=/usr/sbin/dnsmasq --no-daemon --port=5300%i --conf-file=/dev/null --addn-hosts=/etc/ocserv/dns/group_%i.hosts --server=1.1.1.1 --server=8.8.8.8
Restart=always

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload

# Inject Hooks into OCServ Configuration (Replace old ones if present)
if grep -q "^connect-script" /etc/ocserv/ocserv.conf; then
    sed -i 's|^connect-script.*|connect-script = /opt/ocserv-panel/scripts/on_connect.py|g' /etc/ocserv/ocserv.conf
else
    echo "connect-script = /opt/ocserv-panel/scripts/on_connect.py" >> /etc/ocserv/ocserv.conf
fi

if grep -q "^disconnect-script" /etc/ocserv/ocserv.conf; then
    sed -i 's|^disconnect-script.*|disconnect-script = /opt/ocserv-panel/scripts/on_disconnect.py|g' /etc/ocserv/ocserv.conf
else
    echo "disconnect-script = /opt/ocserv-panel/scripts/on_disconnect.py" >> /etc/ocserv/ocserv.conf
fi

systemctl restart ocserv

# Ensure dependencies
apt-get update -y
apt-get install -y python3-pip python3-venv sqlite3 git curl ipset > /dev/null 2>&1

# Update Python dependencies
./venv/bin/pip install -r requirements.txt > /dev/null 2>&1

# Restart the service (this script is spawned by the service, so we use nohup style)
systemctl restart ocserv-panel
