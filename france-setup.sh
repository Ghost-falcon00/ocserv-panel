#!/bin/bash
#
# OCServ France Server Setup Script v2
# اسکریپت نصب و تنظیم سرور فرانسه (سرور خارجی)
# شامل Remote API برای سینک با پنل ایران
#
# Usage: bash <(curl -sL https://raw.githubusercontent.com/Ghost-falcon00/ocserv-panel/main/france-setup.sh)
#

# Don't exit on error — we handle errors ourselves
set +e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Variables
API_PORT=6443
GOST_PORT=2083
OCSERV_PORT=443
VPN_USER=""
VPN_PASS=""
SERVER_IP=""
API_TOKEN=""

# ========== Utility Functions ==========

print_banner() {
    echo -e "${PURPLE}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                                                           ║"
    echo "║     OCServ France Server Setup v2                         ║"
    echo "║     اسکریپت نصب سرور فرانسه (خارجی)                       ║"
    echo "║     + Remote API + Full Stealth Mode                      ║"
    echo "║                                                           ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warning() { echo -e "${YELLOW}[!]${NC} $1"; }
err()     { echo -e "${RED}[✗]${NC} $1"; }
fatal()   { echo -e "${RED}[FATAL]${NC} $1"; exit 1; }

generate_token() {
    python3 -c "import secrets; print(secrets.token_urlsafe(48))" 2>/dev/null || \
    openssl rand -base64 48 | tr -d '/+=' | head -c 48
}

# ========== Pre-flight Checks ==========

check_root() {
    if [[ $EUID -ne 0 ]]; then
        fatal "This script must be run as root (sudo)"
    fi
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        fatal "Cannot detect OS"
    fi
    
    if [[ "$OS" != "ubuntu" && "$OS" != "debian" ]]; then
        fatal "This script only supports Ubuntu/Debian"
    fi
    
    info "Detected: $OS $VERSION"
}

get_server_ip() {
    SERVER_IP=$(curl -s4 --connect-timeout 5 ifconfig.me 2>/dev/null || \
                curl -s4 --connect-timeout 5 icanhazip.com 2>/dev/null || \
                curl -s4 --connect-timeout 5 ip.sb 2>/dev/null || \
                hostname -I | awk '{print $1}')
    
    if [ -z "$SERVER_IP" ]; then
        fatal "Cannot detect server IP"
    fi
    info "Server IP: $SERVER_IP"
}

# ========== Port & Process Management ==========

# Kill everything on a specific port
kill_port() {
    local port=$1
    local pids=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pids" ]; then
        warning "Port $port is in use. Killing processes: $pids"
        kill -9 $pids 2>/dev/null || true
        sleep 1
    fi
}

# Stop and disable services that might conflict
cleanup_conflicts() {
    info "Checking for conflicting services..."
    
    # Stop services that might use our ports
    for svc in nginx apache2 httpd lighttpd caddy haproxy; do
        if systemctl is-active --quiet $svc 2>/dev/null; then
            warning "Stopping $svc (conflicts with OCServ port)"
            systemctl stop $svc 2>/dev/null
            systemctl disable $svc 2>/dev/null
        fi
    done
    
    # Stop old OCServ if running
    if systemctl is-active --quiet ocserv 2>/dev/null; then
        info "Stopping existing OCServ..."
        systemctl stop ocserv 2>/dev/null
    fi
    
    # Stop old remote API if running
    if systemctl is-active --quiet ocserv-remote-api 2>/dev/null; then
        info "Stopping existing Remote API..."
        systemctl stop ocserv-remote-api 2>/dev/null
    fi
    
    # Kill anything on the OCServ port
    kill_port $OCSERV_PORT
    
    # Kill anything on the API port
    kill_port $API_PORT
    
    success "No conflicting services"
}

# Check if port is actually free
check_port() {
    local port=$1
    local name=$2
    if lsof -ti:$port &>/dev/null; then
        err "Port $port is STILL in use after cleanup!"
        lsof -i:$port 2>/dev/null
        fatal "Cannot continue — free port $port manually"
    fi
    success "Port $port is free for $name"
}

# ========== Installation ==========

install_dependencies() {
    info "Installing dependencies..."
    
    export DEBIAN_FRONTEND=noninteractive
    
    apt-get update -qq 2>/dev/null
    apt-get install -y -qq \
        ocserv gnutls-bin curl wget lsof \
        python3 python3-pip python3-venv \
        unzip iptables > /dev/null 2>&1
    
    if ! command -v ocserv &>/dev/null; then
        fatal "OCServ installation failed"
    fi
    
    success "Dependencies installed"
}

# ========== SSL Certificate ==========

create_ssl() {
    info "Creating self-signed SSL certificate..."
    
    mkdir -p /etc/ocserv/ssl
    
    # Generate CA
    certtool --generate-privkey --outfile /etc/ocserv/ssl/ca-key.pem 2>/dev/null
    
    cat > /tmp/ca.tmpl << EOF
cn = "OCServ CA"
organization = "OCServ"
serial = 1
expiration_days = 3650
ca
signing_key
cert_signing_key
crl_signing_key
EOF
    
    certtool --generate-self-signed \
        --load-privkey /etc/ocserv/ssl/ca-key.pem \
        --template /tmp/ca.tmpl \
        --outfile /etc/ocserv/ssl/ca-cert.pem 2>/dev/null
    
    # Generate server cert
    certtool --generate-privkey --outfile /etc/ocserv/ssl/server-key.pem 2>/dev/null
    
    cat > /tmp/server.tmpl << EOF
cn = "$SERVER_IP"
organization = "OCServ"
serial = 2
expiration_days = 3650
signing_key
encryption_key
tls_www_server
EOF
    
    certtool --generate-certificate \
        --load-privkey /etc/ocserv/ssl/server-key.pem \
        --load-ca-certificate /etc/ocserv/ssl/ca-cert.pem \
        --load-ca-privkey /etc/ocserv/ssl/ca-key.pem \
        --template /tmp/server.tmpl \
        --outfile /etc/ocserv/ssl/server-cert.pem 2>/dev/null
    
    rm -f /tmp/ca.tmpl /tmp/server.tmpl
    
    if [ -f /etc/ocserv/ssl/server-cert.pem ]; then
        success "SSL certificate created"
    else
        fatal "SSL certificate creation failed"
    fi
}

# ========== OCServ Configuration ==========

create_config() {
    info "Creating OCServ configuration..."
    
    # Port selection
    echo ""
    echo -e "${CYAN}پورت OCServ را انتخاب کنید:${NC}"
    echo "1) 443  (استاندارد HTTPS - پیشنهادی)"
    echo "2) 2083 (پورت Cloudflare - کمتر فیلتر میشه)"
    echo "3) 8443 (HTTPS آلترنیتیو)"
    echo "4) Custom"
    echo ""
    read -p "انتخاب [1-4]: " port_choice
    
    case $port_choice in
        1) OCSERV_PORT=443 ;;
        2) OCSERV_PORT=2083 ;;
        3) OCSERV_PORT=8443 ;;
        4) read -p "پورت دلخواه: " OCSERV_PORT ;;
        *) OCSERV_PORT=443 ;;
    esac
    
    # Kill anything on the chosen port
    kill_port $OCSERV_PORT
    
    # Write config
    cat > /etc/ocserv/ocserv.conf << EOF
# OCServ Configuration - Full Stealth Mode v2
# Generated: $(date)
# تمام امضاهای سیسکو حذف شدن - ترافیک شبیه وبسایت عادی‌ه

# Authentication
auth = "plain[passwd=/etc/ocserv/ocpasswd]"

# Ports - DTLS غیرفعال (مهم‌ترین علامت شناسایی سیسکو)
tcp-port = $OCSERV_PORT
udp-port = 0

# Performance & Security
run-as-user = nobody
run-as-group = daemon
socket-file = /run/ocserv.socket
isolate-workers = false

# SSL Certificate
server-cert = /etc/ocserv/ssl/server-cert.pem
server-key = /etc/ocserv/ssl/server-key.pem

# Connection Limits
max-clients = 128
max-same-clients = 4

# Timeouts for Iran tunnel
keepalive = 32400
dpd = 90
mobile-dpd = 1800
switch-to-tcp-timeout = 25

# MTU
try-mtu-discovery = false
mtu = 1280

# TLS fingerprint مثل مرورگر عادی (نه سیسکو)
tls-priorities = "NORMAL:%SERVER_PRECEDENCE:%COMPAT:-VERS-SSL3.0:-VERS-TLS1.0:-VERS-TLS1.1:+VERS-TLS1.3:-RSA:-DHE-RSA:-CAMELLIA-128-CBC:-CAMELLIA-256-CBC"

# Auth & Session
auth-timeout = 240
idle-timeout = 1200
mobile-idle-timeout = 2400
min-reauth-time = 300

# Rekey سریع - شناسایی سخت‌تر
rekey-time = 172800
rekey-method = ssl

# Security
max-ban-score = 80
ban-reset-time = 1200
cookie-timeout = 300
deny-roaming = false

# System
use-occtl = true
pid-file = /run/ocserv.pid

# Network
device = vpns
predictable-ips = true
ipv4-network = 192.168.100.0
ipv4-netmask = 255.255.255.0

# DNS
dns = 1.1.1.1
dns = 8.8.8.8

# Routing
tunnel-all-dns = true

# سازگاری Cisco بدون امضای واضح
cisco-client-compat = true
dtls-legacy = false

# =============================================
# Anti-Detection & Cisco Signature Removal
# =============================================
custom-header = "Server: nginx/1.24.0"
custom-header = "X-Powered-By: PHP/8.2.12"
custom-header = "X-Content-Type-Options: nosniff"
custom-header = "X-Frame-Options: SAMEORIGIN"
custom-header = "X-XSS-Protection: 1; mode=block"
custom-header = "Strict-Transport-Security: max-age=31536000; includeSubDomains; preload"
custom-header = "Content-Security-Policy: default-src 'self' https: data: 'unsafe-inline'"
custom-header = "Referrer-Policy: strict-origin-when-cross-origin"
custom-header = "Permissions-Policy: camera=(), microphone=(), geolocation=()"
custom-header = "Cache-Control: no-cache, no-store, must-revalidate"
custom-header = "Pragma: no-cache"
custom-header = "Vary: Accept-Encoding"
custom-header = "X-DNS-Prefetch-Control: off"

# فشرده‌سازی غیرفعال (anti-DPI)
compression = false

# Stats
server-stats-reset-time = 0
EOF
    
    success "OCServ configured on port $OCSERV_PORT (Full Stealth Mode)"
}

# ========== VPN User ==========

create_user() {
    info "Creating VPN user..."
    
    echo ""
    read -p "نام کاربری VPN: " VPN_USER
    read -s -p "رمز عبور VPN: " VPN_PASS
    echo ""
    
    if [ -z "$VPN_USER" ] || [ -z "$VPN_PASS" ]; then
        VPN_USER="admin"
        VPN_PASS=$(openssl rand -base64 12 | tr -d '/+=' | head -c 12)
        warning "Using default user: $VPN_USER / $VPN_PASS"
    fi
    
    echo "$VPN_PASS" | ocpasswd -c /etc/ocserv/ocpasswd "$VPN_USER"
    
    success "User '$VPN_USER' created"
}

# ========== IP Forwarding ==========

enable_forwarding() {
    info "Enabling IP forwarding..."
    
    # Enable now
    sysctl -w net.ipv4.ip_forward=1 > /dev/null 2>&1
    
    # Persist
    echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-ocserv.conf
    sysctl -p /etc/sysctl.d/99-ocserv.conf > /dev/null 2>&1
    
    success "IP forwarding enabled"
}

# ========== Firewall ==========

configure_firewall() {
    info "Configuring firewall..."
    
    # Get default interface
    DEFAULT_IF=$(ip route | grep default | awk '{print $5}' | head -1)
    
    if [ -z "$DEFAULT_IF" ]; then
        DEFAULT_IF="eth0"
        warning "Could not detect default interface, using $DEFAULT_IF"
    fi
    
    # Flush existing OCServ rules (avoid duplicates)
    iptables -D INPUT -p tcp --dport $OCSERV_PORT -j ACCEPT 2>/dev/null || true
    iptables -D INPUT -p tcp --dport $API_PORT -j ACCEPT 2>/dev/null || true
    iptables -D INPUT -p tcp --dport $GOST_PORT -j ACCEPT 2>/dev/null || true
    
    # Allow OCServ port
    iptables -I INPUT -p tcp --dport $OCSERV_PORT -j ACCEPT
    success "  Opened port $OCSERV_PORT (OCServ)"
    
    # Allow Remote API port
    iptables -I INPUT -p tcp --dport $API_PORT -j ACCEPT
    success "  Opened port $API_PORT (Remote API)"
    
    # Allow Gost relay port
    iptables -I INPUT -p tcp --dport $GOST_PORT -j ACCEPT
    success "  Opened port $GOST_PORT (Gost Relay)"
    
    # NAT for VPN clients  
    iptables -t nat -A POSTROUTING -s 192.168.100.0/24 -o $DEFAULT_IF -j MASQUERADE
    iptables -A FORWARD -s 192.168.100.0/24 -j ACCEPT
    iptables -A FORWARD -d 192.168.100.0/24 -j ACCEPT
    
    # MSS clamping
    iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1240
    
    # Save rules — NONINTERACTIVE
    if ! command -v netfilter-persistent &> /dev/null; then
        echo iptables-persistent iptables-persistent/autosave_v4 boolean true | debconf-set-selections
        echo iptables-persistent iptables-persistent/autosave_v6 boolean true | debconf-set-selections
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iptables-persistent > /dev/null 2>&1
    fi
    netfilter-persistent save > /dev/null 2>&1 || true
    
    success "Firewall configured"
}

# ========== Remote API ==========

install_remote_api() {
    info "Installing Remote API for panel sync..."
    
    # Generate token
    API_TOKEN=$(generate_token)
    
    # Create directories
    mkdir -p /opt/ocserv-remote
    mkdir -p /etc/ocserv-remote
    
    # Save token
    echo "$API_TOKEN" > /etc/ocserv-remote/token
    chmod 600 /etc/ocserv-remote/token
    
    # Download from GitHub (with mirrors)
    GITHUB_RAW="https://raw.githubusercontent.com/Ghost-falcon00/ocserv-panel/main"
    MIRROR_RAWS=(
        "https://ghproxy.net/$GITHUB_RAW"
        "https://gh-proxy.com/$GITHUB_RAW"
        "https://ghfast.top/$GITHUB_RAW"
        "$GITHUB_RAW"
    )
    
    DOWNLOADED=false
    for raw_url in "${MIRROR_RAWS[@]}"; do
        src=$(echo "$raw_url" | cut -d'/' -f3)
        echo -ne "  ⏳ ${CYAN}${src}${NC} ... "
        if timeout 15 curl -sL "$raw_url/remote-api/remote_api.py" -o /opt/ocserv-remote/remote_api.py 2>/dev/null; then
            SIZE=$(stat -c%s /opt/ocserv-remote/remote_api.py 2>/dev/null || echo 0)
            if [ "$SIZE" -gt 1000 ]; then
                echo -e "${GREEN}✓ (${SIZE} bytes)${NC}"
                timeout 10 curl -sL "$raw_url/remote-api/requirements.txt" -o /opt/ocserv-remote/requirements.txt 2>/dev/null
                DOWNLOADED=true
                break
            else
                echo -e "${RED}✗ (too small)${NC}"
            fi
        else
            echo -e "${RED}✗${NC}"
        fi
    done
    
    if [[ "$DOWNLOADED" == "false" ]]; then
        warning "Could not download remote API files"
        echo -e "  ${YELLOW}Creating minimal requirements.txt...${NC}"
        cat > /opt/ocserv-remote/requirements.txt << 'REQEOF'
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.3
aiofiles==23.2.1
REQEOF
        warning "You need to manually copy remote_api.py later"
    fi
    
    # Setup Python venv
    cd /opt/ocserv-remote
    
    if [ -d "venv" ]; then
        info "  Removing old venv..."
        rm -rf venv
    fi
    
    python3 -m venv venv
    source venv/bin/activate
    pip install -q --upgrade pip 2>/dev/null
    pip install -q -r requirements.txt 2>&1 | tail -3
    deactivate
    
    # Kill anything on API port
    kill_port $API_PORT
    
    # Create systemd service
    cat > /etc/systemd/system/ocserv-remote-api.service << EOF
[Unit]
Description=OCServ Remote API
After=network.target ocserv.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ocserv-remote
Environment=REMOTE_API_PORT=$API_PORT
Environment=REMOTE_API_TOKEN=$API_TOKEN
ExecStart=/opt/ocserv-remote/venv/bin/python /opt/ocserv-remote/remote_api.py
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable ocserv-remote-api > /dev/null 2>&1
    systemctl restart ocserv-remote-api
    
    sleep 3
    
    if systemctl is-active --quiet ocserv-remote-api; then
        success "Remote API running on port $API_PORT"
    else
        warning "Remote API installed but failed to start. Check: journalctl -u ocserv-remote-api -n 20"
    fi
}

# ========== Gost Relay Server ==========

install_gost_relay() {
    info "Installing Gost relay server (for encrypted tunnel from Iran)..."
    
    # Check if already installed
    if command -v gost &> /dev/null; then
        CURRENT_VER=$(gost -V 2>&1 | head -1)
        info "Gost already installed: $CURRENT_VER"
    else
        GOST_VERSION="3.2.6"
        GOST_FILE="gost_${GOST_VERSION}_linux_amd64.tar.gz"
        GOST_URL="https://github.com/go-gost/gost/releases/download/v${GOST_VERSION}/${GOST_FILE}"
        
        GOST_DOWNLOADED=false
        
        for url in "$GOST_URL" "https://ghproxy.net/${GOST_URL}" "https://gh-proxy.com/${GOST_URL}"; do
            src=$(echo "$url" | cut -d'/' -f3)
            echo -ne "  ⏳ ${CYAN}${src}${NC} ... "
            
            if timeout 15 wget --timeout=10 --tries=1 -q "$url" -O /tmp/gost.tar.gz 2>/dev/null; then
                SIZE=$(stat -c%s /tmp/gost.tar.gz 2>/dev/null || echo 0)
                if [ "$SIZE" -gt 100000 ]; then
                    echo -e "${GREEN}✓ (${SIZE} bytes)${NC}"
                    GOST_DOWNLOADED=true
                    break
                else
                    echo -e "${RED}✗ (invalid)${NC}"
                    rm -f /tmp/gost.tar.gz
                fi
            else
                echo -e "${RED}✗${NC}"
                rm -f /tmp/gost.tar.gz 2>/dev/null
            fi
        done
        
        if [[ "$GOST_DOWNLOADED" == "false" ]]; then
            warning "Could not download Gost. Tunnel relay will not work."
            warning "Install manually: wget $GOST_URL && tar xzf ..."
            return
        fi
        
        tar -xzf /tmp/gost.tar.gz -C /tmp/
        cp /tmp/gost /usr/local/bin/gost
        chmod +x /usr/local/bin/gost
        rm -f /tmp/gost.tar.gz
        success "Gost $(gost -V 2>&1 | head -1) installed"
    fi
    
    # Create Gost relay config — WSS relay server
    # Iran's Gost connects here with relay+wss, then traffic is forwarded to local OCServ
    mkdir -p /etc/gost
    
    cat > /etc/gost/config.json << EOF
{
  "Log": {
    "Level": "warn"
  },
  "Services": [
    {
      "Name": "stealth-relay-server",
      "Addr": ":${GOST_PORT}",
      "Handler": {
        "Type": "relay",
        "Metadata": {
          "mux": true,
          "mux.version": 2,
          "mux.keepAliveDisabled": false,
          "mux.keepAliveInterval": "15s",
          "mux.keepAliveTimeout": "30s",
          "mux.maxFrameSize": 32768,
          "mux.maxReceiveBuffer": 4194304,
          "mux.maxStreamBuffer": 65536,
          "padding": true,
          "padding.max": 255
        }
      },
      "Listener": {
        "Type": "wss",
        "TLS": {
          "CertFile": "/etc/ocserv/ssl/server-cert.pem",
          "KeyFile": "/etc/ocserv/ssl/server-key.pem",
          "MinVersion": "VersionTLS12",
          "MaxVersion": "VersionTLS13",
          "CipherSuites": [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256"
          ],
          "ALPN": ["h2", "http/1.1"]
        },
        "Metadata": {
          "path": "/api/v1/stream,/ws/connect,/socket.io/?EIO=4,/graphql/subscriptions,/cdn-cgi/trace,/ajax/libs/update,/_next/webpack-hmr,/signalr/connect",
          "keepAlive": true,
          "keepAlivePeriod": "30s",
          "header": {
            "Server": ["nginx/1.24.0"],
            "X-Powered-By": ["PHP/8.2.12"],
            "X-Content-Type-Options": ["nosniff"],
            "X-Frame-Options": ["SAMEORIGIN"],
            "Strict-Transport-Security": ["max-age=31536000; includeSubDomains"],
            "Content-Security-Policy": ["default-src 'self' https:"]
          }
        }
      }
    }
  ]
}
EOF
    
    # Create systemd service
    cat > /etc/systemd/system/gost.service << 'EOF'
[Unit]
Description=Gost Relay Tunnel Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/gost -C /etc/gost/config.json
Restart=always
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF
    
    # Kill anything on the relay port
    kill_port $GOST_PORT
    
    systemctl daemon-reload
    systemctl enable gost > /dev/null 2>&1
    systemctl restart gost
    
    sleep 2
    
    if systemctl is-active --quiet gost; then
        success "Gost relay running on port $GOST_PORT (WSS+TLS)"
    else
        warning "Gost relay installed but failed to start"
        journalctl -u gost -n 5 --no-pager 2>/dev/null
    fi
}

# ========== Start OCServ ==========

start_ocserv() {
    info "Starting OCServ..."
    
    # Make sure port is free
    kill_port $OCSERV_PORT
    
    systemctl enable ocserv > /dev/null 2>&1
    systemctl restart ocserv
    
    sleep 2
    
    if systemctl is-active --quiet ocserv; then
        success "OCServ is running on port $OCSERV_PORT"
    else
        err "OCServ failed to start!"
        echo -e "  ${YELLOW}Check logs: journalctl -u ocserv -n 20 --no-pager${NC}"
        journalctl -u ocserv -n 10 --no-pager 2>/dev/null
    fi
}

# ========== Summary ==========

print_summary() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              نصب با موفقیت انجام شد! ✓                    ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}═══ اطلاعات سرور ═══${NC}"
    echo -e "  IP سرور:        ${YELLOW}$SERVER_IP${NC}"
    echo -e "  پورت OCServ:    ${YELLOW}$OCSERV_PORT${NC}"
    echo -e "  کاربر VPN:      ${YELLOW}$VPN_USER${NC}"
    echo ""
    echo -e "${CYAN}═══ اطلاعات Remote API (برای سینک پنل) ═══${NC}"
    echo -e "  پورت API:       ${YELLOW}$API_PORT${NC}"
    echo -e "  توکن API:       ${YELLOW}$API_TOKEN${NC}"
    echo ""
    echo -e "${RED}⚠️  توکن API رو یادداشت کن! بدون این، پنل ایران نمیتونه سینک بشه${NC}"
    echo ""
    echo -e "${CYAN}═══ وضعیت سرویس‌ها ═══${NC}"
    
    # Check all services
    for svc in ocserv ocserv-remote-api gost; do
        if systemctl is-active --quiet $svc 2>/dev/null; then
            echo -e "  ${GREEN}●${NC} $svc: ${GREEN}running${NC}"
        else
            echo -e "  ${RED}●${NC} $svc: ${RED}stopped${NC}"
        fi
    done
    
    # Check ports
    echo ""
    echo -e "${CYAN}═══ وضعیت پورت‌ها ═══${NC}"
    for port in $OCSERV_PORT $API_PORT $GOST_PORT; do
        if lsof -ti:$port &>/dev/null; then
            echo -e "  ${GREEN}●${NC} Port $port: ${GREEN}listening${NC}"
        else
            echo -e "  ${RED}●${NC} Port $port: ${RED}not listening${NC}"
        fi
    done
    
    echo ""
    echo -e "${CYAN}═══ مرحله بعدی ═══${NC}"
    echo -e "  1. وارد پنل ایران شو"
    echo -e "  2. برو به بخش ${YELLOW}'تانل'${NC}"
    echo -e "  3. اطلاعات زیر رو وارد کن:"
    echo -e "     - IP سرور فرانسه: ${YELLOW}$SERVER_IP${NC}"
    echo -e "     - پورت OCServ:    ${YELLOW}$OCSERV_PORT${NC}"
    echo -e "     - پورت API:       ${YELLOW}$API_PORT${NC}"
    echo -e "     - توکن API:       ${YELLOW}$API_TOKEN${NC}"
    echo -e "  4. 'ذخیره و اتصال' رو بزن"
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════${NC}"
    
    # Save info
    cat > /root/ocserv-info.txt << EOF
OCServ France Server Info
=========================
Server IP:      $SERVER_IP
OCServ Port:    $OCSERV_PORT
Gost Relay:     $GOST_PORT
VPN User:       $VPN_USER
API Port:       $API_PORT
API Token:      $API_TOKEN
=========================
Generated:      $(date)
EOF
    echo -e "${CYAN}اطلاعات در فایل /root/ocserv-info.txt ذخیره شد${NC}"
}

# ========== Main ==========

main() {
    print_banner
    check_root
    detect_os
    get_server_ip
    
    # Phase 1: Cleanup & Deps
    install_dependencies
    cleanup_conflicts
    
    # Phase 2: SSL & Config
    create_ssl
    create_config
    create_user
    
    # Phase 3: Network
    enable_forwarding
    configure_firewall
    
    # Phase 4: Services
    install_remote_api
    install_gost_relay
    
    # Phase 5: Start
    start_ocserv
    
    # Done
    print_summary
}

main
