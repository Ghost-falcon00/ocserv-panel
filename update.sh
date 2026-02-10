#!/bin/bash
# OCServ Panel Update Script
# آپدیت پنل از GitHub بدون حذف تنظیمات

cd / 2>/dev/null

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PANEL_DIR="/opt/ocserv-panel"

echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   OCServ Panel Updater v2             ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
echo ""

if [ ! -d "$PANEL_DIR" ]; then
    echo -e "${RED}[✗] Panel not found at $PANEL_DIR${NC}"
    exit 1
fi

# Cleanup
cleanup() { rm -rf /tmp/ocserv-update.zip /tmp/ocserv-panel-update 2>/dev/null; }
trap cleanup EXIT

# ========== Download ==========
GITHUB_ZIP="https://github.com/Ghost-falcon00/ocserv-panel/archive/refs/heads/main.zip"
URLS=(
    "https://gh-proxy.com/$GITHUB_ZIP"
    "https://ghproxy.net/$GITHUB_ZIP"
    "https://mirror.ghproxy.com/$GITHUB_ZIP"
    "https://ghfast.top/$GITHUB_ZIP"
    "https://gh.ddlc.top/$GITHUB_ZIP"
    "$GITHUB_ZIP"
)

echo -e "${YELLOW}[1/5]${NC} Downloading latest version..."
DOWNLOADED=false

for url in "${URLS[@]}"; do
    src=$(echo "$url" | cut -d'/' -f3)
    echo -ne "  ⏳ ${CYAN}${src}${NC} ... "
    
    # Try wget first with timeout and progress
    if wget --timeout=10 --tries=1 -q "$url" -O /tmp/ocserv-update.zip 2>/dev/null; then
        SIZE=$(stat -c%s /tmp/ocserv-update.zip 2>/dev/null || echo 0)
        if [ "$SIZE" -gt 1000 ]; then
            echo -e "${GREEN}✓ (${SIZE} bytes)${NC}"
            DOWNLOADED=true
            break
        else
            echo -e "${RED}✗ (empty/invalid)${NC}"
            rm -f /tmp/ocserv-update.zip
        fi
    else
        echo -e "${RED}✗ (timeout/blocked)${NC}"
        rm -f /tmp/ocserv-update.zip 2>/dev/null
    fi
done

# Fallback: try curl
if [ "$DOWNLOADED" = false ]; then
    echo -e "  Trying curl..."
    for url in "${URLS[@]}"; do
        src=$(echo "$url" | cut -d'/' -f3)
        echo -ne "  ⏳ curl ${CYAN}${src}${NC} ... "
        if curl -sL --connect-timeout 8 --max-time 20 -o /tmp/ocserv-update.zip "$url" 2>/dev/null; then
            SIZE=$(stat -c%s /tmp/ocserv-update.zip 2>/dev/null || echo 0)
            if [ "$SIZE" -gt 1000 ]; then
                echo -e "${GREEN}✓ (${SIZE} bytes)${NC}"
                DOWNLOADED=true
                break
            else
                echo -e "${RED}✗ (empty)${NC}"
                rm -f /tmp/ocserv-update.zip
            fi
        else
            echo -e "${RED}✗${NC}"
            rm -f /tmp/ocserv-update.zip 2>/dev/null
        fi
    done
fi

if [ "$DOWNLOADED" = false ]; then
    echo ""
    echo -e "${RED}[✗] Download failed from all sources!${NC}"
    echo -e "${YELLOW}GitHub is likely blocked. Try one of these:${NC}"
    echo ""
    echo "  Option 1: Download manually on your PC and scp to server:"
    echo "    scp ocserv-panel-main.zip root@YOUR_SERVER_IP:/tmp/ocserv-update.zip"
    echo "    Then run this script again"
    echo ""
    echo "  Option 2: Use a proxy on the server:"
    echo "    export https_proxy=http://PROXY:PORT"
    echo "    Then run this script again"
    echo ""
    
    # Check if manual file exists
    if [ -f "/tmp/ocserv-update.zip" ]; then
        SIZE=$(stat -c%s /tmp/ocserv-update.zip 2>/dev/null || echo 0)
        if [ "$SIZE" -gt 1000 ]; then
            echo -e "${GREEN}[!] Found /tmp/ocserv-update.zip (${SIZE} bytes) - using it${NC}"
            DOWNLOADED=true
        fi
    fi
    
    if [ "$DOWNLOADED" = false ]; then
        exit 1
    fi
fi

echo ""
echo -e "${YELLOW}[2/5]${NC} Extracting..."
rm -rf /tmp/ocserv-panel-update
unzip -qo /tmp/ocserv-update.zip -d /tmp/ocserv-panel-update 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}[✗] Extraction failed - file may be corrupt${NC}"
    exit 1
fi

EXTRACT_DIR=$(find /tmp/ocserv-panel-update -maxdepth 1 -type d -name "ocserv*" | head -1)
if [ -z "$EXTRACT_DIR" ]; then
    echo -e "${RED}[✗] Could not find extracted files${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ Extracted${NC}"

echo -e "${YELLOW}[3/5]${NC} Copying files..."
cd "$PANEL_DIR"

# Copy with feedback
copy_dir() {
    local src="$1" dst="$2" name="$3"
    if [ -d "$src" ]; then
        cp -rf "$src"/* "$dst"/ 2>/dev/null
        echo -e "  ${GREEN}✓${NC} $name"
    fi
}

copy_file() {
    local src="$1" dst="$2" name="$3"
    if [ -f "$src" ]; then
        cp -f "$src" "$dst" 2>/dev/null
        echo -e "  ${GREEN}✓${NC} $name"
    fi
}

# Backup .env
cp -f panel/.env panel/.env.bak 2>/dev/null

copy_dir "$EXTRACT_DIR/panel/api" "panel/api" "api/"
copy_dir "$EXTRACT_DIR/panel/services" "panel/services" "services/"
copy_dir "$EXTRACT_DIR/panel/templates" "panel/templates" "templates/"
copy_dir "$EXTRACT_DIR/panel/static" "panel/static" "static/"
copy_dir "$EXTRACT_DIR/panel/models" "panel/models" "models/"
copy_file "$EXTRACT_DIR/panel/app.py" "panel/app.py" "app.py"
copy_file "$EXTRACT_DIR/panel/config.py" "panel/config.py" "config.py"
copy_file "$EXTRACT_DIR/panel/requirements.txt" "panel/requirements.txt" "requirements.txt"

mkdir -p remote-api
copy_dir "$EXTRACT_DIR/remote-api" "remote-api" "remote-api/"
copy_file "$EXTRACT_DIR/france-setup.sh" "france-setup.sh" "france-setup.sh"
copy_file "$EXTRACT_DIR/update.sh" "update.sh" "update.sh"

# Restore .env
cp -f panel/.env.bak panel/.env 2>/dev/null

# Verify critical files
echo ""
echo -e "  ${CYAN}Critical files check:${NC}"
MISSING=0
for f in panel/api/tunnel.py panel/services/remote_sync.py panel/services/tunnel.py panel/templates/tunnel.html panel/services/ocserv.py; do
    if [ -f "$f" ]; then
        echo -e "    ${GREEN}✓${NC} $f"
    else
        echo -e "    ${RED}✗ MISSING:${NC} $f"
        MISSING=$((MISSING+1))
    fi
done

if [ $MISSING -gt 0 ]; then
    echo -e "  ${RED}[!] $MISSING critical file(s) missing!${NC}"
fi

echo ""
echo -e "${YELLOW}[4/5]${NC} Installing dependencies..."
source venv/bin/activate 2>/dev/null
pip install -q -r panel/requirements.txt 2>/dev/null
echo -e "  ${GREEN}✓ Done${NC}"

echo -e "${YELLOW}[5/5]${NC} Restarting panel..."
systemctl restart ocserv-panel 2>/dev/null

sleep 3
if systemctl is-active --quiet ocserv-panel; then
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   ✓ Panel updated and running!            ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Logs: ${YELLOW}journalctl -u ocserv-panel -n 20 --no-pager${NC}"
    echo -e "  Panel: ${YELLOW}https://$(hostname -I | awk '{print $1}'):8443${NC}"
else
    echo ""
    echo -e "${RED}[✗] Panel failed to start!${NC}"
    echo -e "  ${YELLOW}journalctl -u ocserv-panel -n 50 --no-pager${NC}"
fi
