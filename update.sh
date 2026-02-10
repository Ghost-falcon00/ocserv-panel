#!/bin/bash
# OCServ Panel Update Script
# آپدیت پنل از GitHub بدون حذف تنظیمات

# Fix getcwd error
cd / 2>/dev/null

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
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

# Cleanup function
cleanup() {
    rm -rf /tmp/ocserv-update.zip /tmp/ocserv-panel-update 2>/dev/null
}
trap cleanup EXIT

# Download URLs (direct + mirrors for Iran)
GITHUB_ZIP="https://github.com/Ghost-falcon00/ocserv-panel/archive/refs/heads/main.zip"
MIRROR_URLS=(
    "https://gh-proxy.com/$GITHUB_ZIP"
    "https://ghproxy.net/$GITHUB_ZIP"
    "https://mirror.ghproxy.com/$GITHUB_ZIP"
    "$GITHUB_ZIP"
)

echo -e "${YELLOW}[1/5]${NC} Downloading latest version..."
DOWNLOADED=false

for url in "${MIRROR_URLS[@]}"; do
    src=$(echo "$url" | cut -d'/' -f3)
    echo -e "  Trying ${CYAN}${src}${NC}..."
    if timeout 20 wget -q "$url" -O /tmp/ocserv-update.zip 2>/dev/null; then
        # Check file is valid zip
        if file /tmp/ocserv-update.zip | grep -q "Zip\|zip"; then
            DOWNLOADED=true
            echo -e "  ${GREEN}[✓] Downloaded from ${src}${NC}"
            break
        else
            rm -f /tmp/ocserv-update.zip
        fi
    fi
done

if [ "$DOWNLOADED" = false ]; then
    echo -e "${RED}[✗] Download failed from all sources${NC}"
    echo -e "Try manually: wget ${GITHUB_ZIP} -O /tmp/ocserv-update.zip"
    exit 1
fi

echo -e "${YELLOW}[2/5]${NC} Extracting files..."
rm -rf /tmp/ocserv-panel-update
unzip -qo /tmp/ocserv-update.zip -d /tmp/ocserv-panel-update
if [ $? -ne 0 ]; then
    echo -e "${RED}[✗] Extraction failed${NC}"
    exit 1
fi

# Find extracted directory
EXTRACT_DIR=$(find /tmp/ocserv-panel-update -maxdepth 1 -type d -name "ocserv-panel*" | head -1)
if [ -z "$EXTRACT_DIR" ]; then
    echo -e "${RED}[✗] Could not find extracted files${NC}"
    exit 1
fi

echo -e "${YELLOW}[3/5]${NC} Updating panel files..."
cd "$PANEL_DIR"

# Backup .env
cp -f panel/.env panel/.env.bak 2>/dev/null

# Copy panel files (preserves .env and database)
cp -rf "$EXTRACT_DIR/panel/api/"* panel/api/ 2>/dev/null
cp -rf "$EXTRACT_DIR/panel/services/"* panel/services/ 2>/dev/null
cp -rf "$EXTRACT_DIR/panel/templates/"* panel/templates/ 2>/dev/null
cp -rf "$EXTRACT_DIR/panel/static/"* panel/static/ 2>/dev/null
cp -rf "$EXTRACT_DIR/panel/models/"* panel/models/ 2>/dev/null
cp -f "$EXTRACT_DIR/panel/app.py" panel/app.py 2>/dev/null
cp -f "$EXTRACT_DIR/panel/config.py" panel/config.py 2>/dev/null
cp -f "$EXTRACT_DIR/panel/requirements.txt" panel/requirements.txt 2>/dev/null

# Copy remote-api files
mkdir -p remote-api
cp -rf "$EXTRACT_DIR/remote-api/"* remote-api/ 2>/dev/null

# Copy scripts
cp -f "$EXTRACT_DIR/france-setup.sh" . 2>/dev/null
cp -f "$EXTRACT_DIR/update.sh" . 2>/dev/null

# Restore .env
cp -f panel/.env.bak panel/.env 2>/dev/null

# Verify key files
echo ""
echo -e "  ${CYAN}Checking files:${NC}"
for f in panel/api/tunnel.py panel/services/remote_sync.py panel/services/tunnel.py panel/templates/tunnel.html; do
    if [ -f "$f" ]; then
        echo -e "    ${GREEN}✓${NC} $f"
    else
        echo -e "    ${RED}✗${NC} $f ${RED}(MISSING!)${NC}"
    fi
done

echo -e "${YELLOW}[4/5]${NC} Installing dependencies..."
source venv/bin/activate
pip install -q -r panel/requirements.txt 2>/dev/null

echo -e "${YELLOW}[5/5]${NC} Restarting panel..."
systemctl restart ocserv-panel

# Verify
sleep 3
if systemctl is-active --quiet ocserv-panel; then
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   [✓] Panel updated successfully!     ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
    echo ""
    echo -e "Check logs: ${YELLOW}journalctl -u ocserv-panel -n 20 --no-pager${NC}"
else
    echo ""
    echo -e "${RED}[✗] Panel failed to start!${NC}"
    echo -e "Logs: ${YELLOW}journalctl -u ocserv-panel -n 50 --no-pager${NC}"
fi
