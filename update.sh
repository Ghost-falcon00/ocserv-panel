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

# Apply Database Migrations safely (Fixed path to panel/data/panel.db)
sqlite3 panel/data/panel.db "ALTER TABLE user_groups ADD COLUMN blocked_categories JSON;" 2>/dev/null

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

# Inject Hooks into OCServ Configuration if lacking
if ! grep -q "^connect-script" /etc/ocserv/ocserv.conf; then
    echo "connect-script = /opt/ocserv-panel/scripts/on_connect.py" >> /etc/ocserv/ocserv.conf
    echo "disconnect-script = /opt/ocserv-panel/scripts/on_disconnect.py" >> /etc/ocserv/ocserv.conf
    systemctl restart ocserv
fi

# Update Python dependencies
./venv/bin/pip install -r requirements.txt > /dev/null 2>&1

# Restart the service (this script is spawned by the service, so we use nohup style)
systemctl restart ocserv-panel
