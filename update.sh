#!/bin/bash
# OCServ Panel Update Script
# آپدیت پنل از GitHub بدون حذف تنظیمات

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PANEL_DIR="/opt/ocserv-panel"

echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   OCServ Panel Updater                ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
echo ""

# Check panel exists
if [ ! -d "$PANEL_DIR" ]; then
    echo -e "${RED}[✗] Panel not found at $PANEL_DIR${NC}"
    exit 1
fi

cd $PANEL_DIR

echo -e "${YELLOW}[1/5]${NC} Downloading latest version..."
wget -q https://github.com/Ghost-falcon00/ocserv-panel/archive/refs/heads/main.zip -O /tmp/ocserv-update.zip
if [ $? -ne 0 ]; then
    echo -e "${RED}[✗] Download failed${NC}"
    exit 1
fi

echo -e "${YELLOW}[2/5]${NC} Extracting files..."
rm -rf /tmp/ocserv-panel-update
unzip -qo /tmp/ocserv-update.zip -d /tmp/ocserv-panel-update

echo -e "${YELLOW}[3/5]${NC} Updating panel files..."
# Copy panel files (preserves .env and data)
cp -rf /tmp/ocserv-panel-update/ocserv-panel-main/panel/api/* panel/api/ 2>/dev/null || true
cp -rf /tmp/ocserv-panel-update/ocserv-panel-main/panel/services/* panel/services/ 2>/dev/null || true
cp -rf /tmp/ocserv-panel-update/ocserv-panel-main/panel/templates/* panel/templates/ 2>/dev/null || true
cp -rf /tmp/ocserv-panel-update/ocserv-panel-main/panel/static/* panel/static/ 2>/dev/null || true
cp -f /tmp/ocserv-panel-update/ocserv-panel-main/panel/app.py panel/app.py 2>/dev/null || true
cp -f /tmp/ocserv-panel-update/ocserv-panel-main/panel/config.py panel/config.py 2>/dev/null || true
cp -f /tmp/ocserv-panel-update/ocserv-panel-main/panel/requirements.txt panel/requirements.txt 2>/dev/null || true

# Copy remote-api files
mkdir -p remote-api
cp -rf /tmp/ocserv-panel-update/ocserv-panel-main/remote-api/* remote-api/ 2>/dev/null || true

# Copy scripts
cp -f /tmp/ocserv-panel-update/ocserv-panel-main/france-setup.sh . 2>/dev/null || true
cp -f /tmp/ocserv-panel-update/ocserv-panel-main/update.sh . 2>/dev/null || true

echo -e "${YELLOW}[4/5]${NC} Installing dependencies..."
source venv/bin/activate
pip install -q -r panel/requirements.txt 2>/dev/null

echo -e "${YELLOW}[5/5]${NC} Restarting panel..."
systemctl restart ocserv-panel

# Cleanup
rm -rf /tmp/ocserv-update.zip /tmp/ocserv-panel-update

# Verify
sleep 2
if systemctl is-active --quiet ocserv-panel; then
    echo ""
    echo -e "${GREEN}[✓] Panel updated and running!${NC}"
    echo ""
    # Check if remote_sync loaded
    if [ -f "panel/services/remote_sync.py" ]; then
        echo -e "${GREEN}[✓] Remote sync module installed${NC}"
    fi
    echo ""
    echo -e "Check logs: ${YELLOW}journalctl -u ocserv-panel -n 30 --no-pager${NC}"
else
    echo ""
    echo -e "${RED}[✗] Panel failed to start!${NC}"
    echo -e "Check logs: ${YELLOW}journalctl -u ocserv-panel -n 50 --no-pager${NC}"
fi
