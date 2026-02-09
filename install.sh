#!/bin/bash

#############################################################
#                                                           #
#   OCServ Panel - One-Click Installer                      #
#   اسکریپت نصب یک‌کلیکی پنل مدیریت OCServ                   #
#                                                           #
#   https://github.com/Ghost-falcon00/ocserv-panel          #
#                                                           #
#############################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Variables
PANEL_DIR="/opt/ocserv-panel"
OCSERV_PORT=4443
GITHUB_RAW="https://raw.githubusercontent.com/Ghost-falcon00/ocserv-panel/main"

# Functions
print_banner() {
    clear
    echo -e "${PURPLE}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                                                           ║"
    echo "║   ██████╗  ██████╗███████╗███████╗██████╗ ██╗   ██╗      ║"
    echo "║  ██╔═══██╗██╔════╝██╔════╝██╔════╝██╔══██╗██║   ██║      ║"
    echo "║  ██║   ██║██║     ███████╗█████╗  ██████╔╝██║   ██║      ║"
    echo "║  ██║   ██║██║     ╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝      ║"
    echo "║  ╚██████╔╝╚██████╗███████║███████╗██║  ██║ ╚████╔╝       ║"
    echo "║   ╚═════╝  ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝        ║"
    echo "║                                                           ║"
    echo "║               OCServ Management Panel                     ║"
    echo "║                   نسخه بهینه ایران                        ║"
    echo "║                                                           ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

check_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        log_error "Cannot detect OS"
        exit 1
    fi
    
    if [[ "$OS" != "ubuntu" && "$OS" != "debian" ]]; then
        log_error "This script only supports Ubuntu and Debian"
        exit 1
    fi
    
    log_info "Detected: $OS $VERSION"
}

get_public_ip() {
    PUBLIC_IP=$(curl -s https://api.ipify.org || curl -s https://ifconfig.me || curl -s https://icanhazip.com)
    log_info "Public IP: $PUBLIC_IP"
}

find_free_port() {
    # Find a free port starting from 8443
    local port=8443
    while netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; do
        port=$((port + 1))
    done
    echo $port
}

generate_random_string() {
    # Generate random string for panel URL path
    cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w ${1:-16} | head -n 1
}

# Server mode selection
SERVER_MODE="iran"  # Default to Iran mode

select_server_mode() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}                 انتخاب نوع سرور                           ${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}این سرور کجا قرار داره؟${NC}"
    echo ""
    echo "  1) ${GREEN}سرور ایران${NC} (Entry Point - کاربران بهش وصل میشن)"
    echo "     پنل + تانل نصب میشه"
    echo ""
    echo "  2) ${BLUE}سرور خارج (فرانسه و...)${NC} (Exit Point - VPN اصلی)"
    echo "     فقط OCServ نصب میشه"
    echo ""
    read -p "انتخاب [1/2]: " mode_choice
    
    case $mode_choice in
        1)
            SERVER_MODE="iran"
            log_info "حالت: سرور ایران (با تانل)"
            ;;
        2)
            SERVER_MODE="france"
            log_info "حالت: سرور خارج (بدون تانل)"
            ;;
        *)
            SERVER_MODE="iran"
            log_info "حالت پیش‌فرض: سرور ایران"
            ;;
    esac
}

# Install Gost for tunnel
install_gost() {
    log_info "Installing Gost tunnel..."
    
    GOST_VERSION=$(curl -s https://api.github.com/repos/ginuerzh/gost/releases/latest | grep -oP '"tag_name": "v\K[^"]+' || echo "3.0.0")
    
    wget -q "https://github.com/ginuerzh/gost/releases/download/v${GOST_VERSION}/gost-linux-amd64-${GOST_VERSION}.gz" -O /tmp/gost.gz || {
        log_warning "Failed to download Gost, will be installed later from panel"
        return
    }
    
    gunzip -f /tmp/gost.gz
    mv /tmp/gost /usr/local/bin/gost
    chmod +x /usr/local/bin/gost
    mkdir -p /etc/gost
    
    # Create systemd service
    cat > /etc/systemd/system/gost.service << 'EOF'
[Unit]
Description=Gost Tunnel Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/gost -C /etc/gost/config.json
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    
    log_success "Gost installed"
}

get_user_input() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}                    تنظیمات اولیه                          ${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Domain
    while [[ -z "$DOMAIN" ]]; do
        read -p "$(echo -e ${YELLOW}Enter your domain \(required\): ${NC})" DOMAIN
        if [[ -z "$DOMAIN" ]]; then
            log_error "Domain is required for SSL certificate"
        fi
    done
    
    # Admin username
    while [[ -z "$ADMIN_USER" ]]; do
        read -p "$(echo -e ${YELLOW}Enter panel admin username: ${NC})" ADMIN_USER
        if [[ -z "$ADMIN_USER" ]]; then
            log_error "Username is required"
        fi
    done
    
    # Admin password
    while [[ -z "$ADMIN_PASS" ]]; do
        read -sp "$(echo -e ${YELLOW}Enter panel admin password: ${NC})" ADMIN_PASS
        echo ""
        if [[ ${#ADMIN_PASS} -lt 6 ]]; then
            log_error "Password must be at least 6 characters"
            ADMIN_PASS=""
        fi
    done
    
    # Confirm password
    read -sp "$(echo -e ${YELLOW}Confirm password: ${NC})" ADMIN_PASS_CONFIRM
    echo ""
    
    if [[ "$ADMIN_PASS" != "$ADMIN_PASS_CONFIRM" ]]; then
        log_error "Passwords do not match"
        exit 1
    fi
    
    # Find free port for panel
    PANEL_PORT=$(find_free_port)
    
    # Generate random path for extra security
    PANEL_PATH=$(generate_random_string 12)
    
    echo ""
    log_info "Domain: $DOMAIN"
    log_info "Admin: $ADMIN_USER"
    log_info "Panel Port: $PANEL_PORT"
    log_info "Panel Secret Path: /$PANEL_PATH"
    echo ""
    
    read -p "$(echo -e ${YELLOW}Continue with these settings? \[Y/n\]: ${NC})" CONFIRM
    if [[ "$CONFIRM" =~ ^[Nn]$ ]]; then
        log_warning "Installation cancelled"
        exit 0
    fi
}

install_dependencies() {
    log_info "Installing dependencies..."
    
    apt-get update -qq
    
    # Remove old broken certbot first
    apt-get remove -y certbot python3-certbot 2>/dev/null || true
    apt-get autoremove -y 2>/dev/null || true
    
    apt-get install -y -qq \
        curl \
        wget \
        git \
        python3 \
        python3-pip \
        python3-venv \
        ocserv \
        gnutls-bin \
        net-tools \
        openssl \
        psmisc \
        conntrack \
        > /dev/null 2>&1
    
    log_success "Dependencies installed"
}

setup_ssl() {
    log_info "Setting up SSL certificate for $DOMAIN..."
    
    # Create SSL directory
    mkdir -p /etc/ocserv/ssl
    
    # Check if Let's Encrypt cert already exists
    if [[ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]]; then
        log_info "Found existing Let's Encrypt certificate"
        ln -sf /etc/letsencrypt/live/$DOMAIN/fullchain.pem /etc/ocserv/ssl/server-cert.pem
        ln -sf /etc/letsencrypt/live/$DOMAIN/privkey.pem /etc/ocserv/ssl/server-key.pem
        USE_LETSENCRYPT=true
        log_success "Using existing Let's Encrypt certificate"
        return
    fi
    
    # Check if port 80 is available
    PORT_80_BUSY=false
    if ss -tuln 2>/dev/null | grep -q ":80 " || netstat -tuln 2>/dev/null | grep -q ":80 "; then
        PORT_80_BUSY=true
        log_warning "Port 80 is in use by another service"
    fi
    
    # Check if domain resolves to this server
    DOMAIN_IP=$(dig +short $DOMAIN 2>/dev/null | head -1)
    if [[ "$DOMAIN_IP" != "$PUBLIC_IP" ]]; then
        log_warning "Domain $DOMAIN does not point to this server ($PUBLIC_IP)"
        log_warning "DNS record points to: $DOMAIN_IP"
    fi
    
    # Ask user about SSL type
    echo ""
    if [[ "$PORT_80_BUSY" == "true" ]]; then
        log_warning "Port 80 is busy. Let's Encrypt requires port 80 to be free."
        read -p "$(echo -e ${YELLOW}Use self-signed certificate? [Y/n]: ${NC})" USE_SELFSIGNED
        USE_SELFSIGNED=${USE_SELFSIGNED:-y}
    else
        log_info "Port 80 is available for Let's Encrypt"
        read -p "$(echo -e ${YELLOW}Try Let's Encrypt certificate? [Y/n]: ${NC})" TRY_LETSENCRYPT
        TRY_LETSENCRYPT=${TRY_LETSENCRYPT:-y}
        
        if [[ "$TRY_LETSENCRYPT" =~ ^[Nn]$ ]]; then
            USE_SELFSIGNED="y"
        else
            USE_SELFSIGNED="n"
        fi
    fi
    
    if [[ "$USE_SELFSIGNED" =~ ^[Yy]$ ]]; then
        log_info "Creating self-signed certificate..."
        create_self_signed_cert
    else
        log_info "Attempting to get Let's Encrypt certificate..."
        
        # Stop services that might use port 80
        systemctl stop nginx 2>/dev/null || true
        systemctl stop apache2 2>/dev/null || true
        systemctl stop ocserv 2>/dev/null || true
        fuser -k 80/tcp 2>/dev/null || true
        
        sleep 2
        
        # Try snap certbot first
        if command -v snap &> /dev/null; then
            snap install core 2>/dev/null || true
            snap install --classic certbot 2>/dev/null || true
            ln -sf /snap/bin/certbot /usr/bin/certbot 2>/dev/null || true
            CERTBOT_CMD="/snap/bin/certbot"
        else
            # Install certbot via apt if snap not available
            apt-get install -y -qq certbot > /dev/null 2>&1 || true
            CERTBOT_CMD="certbot"
        fi
        
        # Try to get certificate
        if $CERTBOT_CMD certonly --standalone --non-interactive --agree-tos \
            --email admin@$DOMAIN \
            -d $DOMAIN \
            --preferred-challenges http 2>&1; then
            
            if [[ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]]; then
                ln -sf /etc/letsencrypt/live/$DOMAIN/fullchain.pem /etc/ocserv/ssl/server-cert.pem
                ln -sf /etc/letsencrypt/live/$DOMAIN/privkey.pem /etc/ocserv/ssl/server-key.pem
                log_success "Let's Encrypt certificate obtained"
                
                # Setup auto-renewal
                cat > /etc/cron.d/certbot-ocserv << 'CRONEOF'
0 0 1 * * root /snap/bin/certbot renew --quiet && systemctl reload ocserv
CRONEOF
                return
            fi
        fi
        
        log_warning "Let's Encrypt failed. Creating self-signed certificate..."
        create_self_signed_cert
    fi
}

create_self_signed_cert() {
    log_info "Generating self-signed certificate (valid for 10 years)..."
    
    openssl req -new -newkey rsa:4096 -days 3650 -nodes -x509 \
        -subj "/C=IR/ST=Tehran/L=Tehran/O=OCServ/CN=$DOMAIN" \
        -keyout /etc/ocserv/ssl/server-key.pem \
        -out /etc/ocserv/ssl/server-cert.pem \
        > /dev/null 2>&1
    
    chmod 600 /etc/ocserv/ssl/*.pem
    
    log_success "Self-signed certificate created"
    log_warning "Note: Clients will see a certificate warning (normal for self-signed)"
}

configure_ocserv() {
    log_info "Configuring OCServ with Iran-optimized settings..."
    
    # Backup original config
    if [[ -f /etc/ocserv/ocserv.conf ]]; then
        cp /etc/ocserv/ocserv.conf /etc/ocserv/ocserv.conf.backup.$(date +%Y%m%d)
    fi
    
    # Create optimized config for Iran
    cat > /etc/ocserv/ocserv.conf << EOF
# OCServ Configuration - Optimized for Iran
# Generated by OCServ Panel Installer

# Authentication
auth = "plain[passwd=/etc/ocserv/ocpasswd]"
tcp-port = ${OCSERV_PORT}
udp-port = ${OCSERV_PORT}

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

# Timeouts optimized for Iran filtering
keepalive = 32400
dpd = 90
mobile-dpd = 1800
switch-to-tcp-timeout = 25

# MTU optimization for better speed
try-mtu-discovery = true
mtu = 1400

# TLS optimization
tls-priorities = "PERFORMANCE:%SERVER_PRECEDENCE:%COMPAT:-VERS-SSL3.0:-VERS-TLS1.0"
auth-timeout = 240
idle-timeout = 1200
mobile-idle-timeout = 2400
min-reauth-time = 300
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
server-stats-reset-time = 604800

# Connect script - check blocked IPs before allowing connection
connect-script = /etc/ocserv/check_blocked.sh

# Network
device = vpns
predictable-ips = true
default-domain = ${DOMAIN}
ipv4-network = 192.168.100.0
ipv4-netmask = 255.255.255.0

# DNS - Best DNS for Iran
dns = 1.1.1.1
dns = 1.0.0.1
dns = 8.8.8.8
dns = 8.8.4.4

# Routing - Only filtered traffic goes through VPN
tunnel-all-dns = true
no-route = 192.168.0.0/255.255.0.0
no-route = 172.16.0.0/255.240.0.0
no-route = 10.0.0.0/255.0.0.0

# Iranian sites bypass VPN (faster access)
no-route = 2.144.0.0/255.254.0.0
no-route = 5.22.0.0/255.255.0.0
no-route = 5.23.0.0/255.255.0.0
no-route = 5.52.0.0/255.252.0.0
no-route = 5.56.0.0/255.248.0.0
no-route = 5.74.0.0/255.254.0.0
no-route = 5.106.0.0/255.255.0.0
no-route = 5.112.0.0/255.248.0.0
no-route = 5.120.0.0/255.248.0.0
no-route = 5.144.0.0/255.240.0.0
no-route = 5.160.0.0/255.224.0.0
no-route = 5.190.0.0/255.254.0.0
no-route = 5.198.0.0/255.254.0.0
no-route = 5.200.0.0/255.248.0.0
no-route = 31.2.0.0/255.254.0.0
no-route = 31.7.64.0/255.255.192.0
no-route = 31.14.0.0/255.254.0.0
no-route = 31.24.0.0/255.248.0.0
no-route = 31.40.0.0/255.248.0.0
no-route = 31.56.0.0/255.248.0.0
no-route = 31.130.0.0/255.254.0.0
no-route = 31.170.0.0/255.254.0.0
no-route = 31.193.192.0/255.255.192.0
no-route = 37.9.0.0/255.255.0.0
no-route = 37.32.0.0/255.224.0.0
no-route = 37.63.0.0/255.255.0.0
no-route = 37.75.0.0/255.255.0.0
no-route = 37.98.0.0/255.254.0.0
no-route = 37.114.0.0/255.254.0.0
no-route = 37.129.0.0/255.255.0.0
no-route = 37.143.0.0/255.255.0.0
no-route = 37.152.0.0/255.248.0.0
no-route = 37.191.0.0/255.255.0.0
no-route = 37.202.0.0/255.254.0.0
no-route = 37.228.0.0/255.252.0.0
no-route = 37.235.0.0/255.255.0.0

ping-leases = false

# Cisco compatibility for Iran
cisco-client-compat = true
dtls-legacy = true

# Compression (can help with speed)
compression = true
no-compress-limit = 256

# Output buffer for better performance
output-buffer = 23000
EOF

    # Create password file
    touch /etc/ocserv/ocpasswd
    chmod 600 /etc/ocserv/ocpasswd
    
    # Create blocked IPs file and connect script
    touch /etc/ocserv/blocked_ips.txt
    chmod 644 /etc/ocserv/blocked_ips.txt
    
    log_success "OCServ configured with Iran-optimized settings"
}

setup_panel() {
    log_info "Installing OCServ Panel..."
    
    # Clean existing installation if exists
    if [[ -d "$PANEL_DIR" ]]; then
        rm -rf $PANEL_DIR
    fi
    
    # Create panel directory
    mkdir -p $PANEL_DIR
    cd $PANEL_DIR
    
    # Clone from GitHub
    git clone --depth 1 https://github.com/Ghost-falcon00/ocserv-panel.git .
    
    # Create virtual environment
    python3 -m venv venv
    source venv/bin/activate
    
    # Install Python dependencies
    pip install -q --upgrade pip
    pip install -q -r panel/requirements.txt
    
    # Create .env file with settings
    cat > panel/.env << EOF
SECRET_KEY=$(generate_random_string 32)
PANEL_PORT=${PANEL_PORT}
PANEL_PATH=${PANEL_PATH}
ADMIN_USER=${ADMIN_USER}
DOMAIN=${DOMAIN}
EOF
    
    # Create data directory
    mkdir -p panel/data
    
    # Create logs directory
    mkdir -p panel/logs
    chmod 755 panel/logs
    
    # Copy connect script to OCServ
    cp scripts/check_blocked.sh /etc/ocserv/check_blocked.sh
    chmod +x /etc/ocserv/check_blocked.sh
    
    log_success "Panel installed"
}

create_admin_user() {
    log_info "Creating admin user..."
    
    cd $PANEL_DIR
    source venv/bin/activate
    
    # Create Python script to add admin
    python3 << EOF
import asyncio
import sys
sys.path.insert(0, 'panel')

from models.database import init_db, async_session
from models.admin import Admin

async def create_admin():
    await init_db()
    async with async_session() as session:
        admin = Admin(
            username="${ADMIN_USER}",
            password_hash=Admin.hash_password("${ADMIN_PASS}"),
            is_superadmin=True
        )
        session.add(admin)
        await session.commit()

asyncio.run(create_admin())
EOF

    log_success "Admin user created"
}

create_systemd_service() {
    log_info "Creating systemd service..."
    
    cat > /etc/systemd/system/ocserv-panel.service << EOF
[Unit]
Description=OCServ Management Panel
After=network.target ocserv.service

[Service]
Type=simple
User=root
WorkingDirectory=${PANEL_DIR}/panel
Environment="PATH=${PANEL_DIR}/venv/bin:\$PATH"
ExecStart=${PANEL_DIR}/venv/bin/uvicorn app:app --host 0.0.0.0 --port ${PANEL_PORT} --workers 1 --ssl-keyfile /etc/ocserv/ssl/server-key.pem --ssl-certfile /etc/ocserv/ssl/server-cert.pem
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable ocserv-panel
    
    log_success "Systemd service created"
}

optimize_vps_network() {
    log_info "Optimizing VPS network for maximum performance..."
    
    # ═══════════════════════════════════════════════════════════
    # TCP BBR + Advanced Network Optimization
    # ═══════════════════════════════════════════════════════════
    
    cat > /etc/sysctl.d/99-ocserv-optimized.conf << 'EOF'
# ╔═══════════════════════════════════════════════════════════╗
# ║      OCServ Panel - VPS Network Optimization              ║
# ║      بهینه‌سازی شبکه برای حداکثر سرعت و پایداری            ║
# ╚═══════════════════════════════════════════════════════════╝

# ═══════════════════════════════════════════════════════════
# IP Forwarding - ضروری برای VPN
# ═══════════════════════════════════════════════════════════
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1

# ═══════════════════════════════════════════════════════════
# TCP BBR Congestion Control - بهترین الگوریتم برای سرعت
# ═══════════════════════════════════════════════════════════
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr

# ═══════════════════════════════════════════════════════════
# TCP Buffer Optimization - افزایش سرعت انتقال
# ═══════════════════════════════════════════════════════════
# افزایش بافر دریافت
net.core.rmem_default = 1048576
net.core.rmem_max = 16777216
net.ipv4.tcp_rmem = 4096 1048576 16777216

# افزایش بافر ارسال
net.core.wmem_default = 1048576
net.core.wmem_max = 16777216
net.ipv4.tcp_wmem = 4096 1048576 16777216

# بافر عمومی
net.core.optmem_max = 65535
net.core.netdev_max_backlog = 65536

# ═══════════════════════════════════════════════════════════
# TCP Performance Tuning - بهینه‌سازی عملکرد TCP
# ═══════════════════════════════════════════════════════════
# فعال کردن TCP Fast Open - اتصال سریع‌تر
net.ipv4.tcp_fastopen = 3

# Window Scaling - پنجره بزرگ‌تر = سرعت بیشتر
net.ipv4.tcp_window_scaling = 1

# افزایش محدودیت اتصالات
net.ipv4.tcp_max_syn_backlog = 65536
net.core.somaxconn = 65535

# کاهش زمان انتظار اتصالات
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_tw_reuse = 1

# Keepalive بهینه
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_intvl = 60
net.ipv4.tcp_keepalive_probes = 5

# غیرفعال کردن Timestamps (کاهش فیلترینگ)
net.ipv4.tcp_timestamps = 0

# غیرفعال کردن SACK (برخی فیلترها ازش استفاده میکنن)
net.ipv4.tcp_sack = 0

# MTU Probing - کشف بهترین MTU
net.ipv4.tcp_mtu_probing = 1

# ═══════════════════════════════════════════════════════════
# Anti-Filtering Settings - ضد فیلترینگ
# ═══════════════════════════════════════════════════════════
# غیرفعال کردن ECN (فیلترها ازش استفاده میکنن)
net.ipv4.tcp_ecn = 0

# افزایش تنوع پورت منبع
net.ipv4.ip_local_port_range = 1024 65535

# ═══════════════════════════════════════════════════════════
# Security Hardening - امنیت
# ═══════════════════════════════════════════════════════════
# محافظت در برابر SYN Flood
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_orphans = 65536

# جلوگیری از IP Spoofing
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# غیرفعال کردن ICMP Redirect (امنیت بالاتر)
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# ═══════════════════════════════════════════════════════════
# Memory Optimization - بهینه‌سازی حافظه
# ═══════════════════════════════════════════════════════════
net.ipv4.tcp_mem = 786432 1048576 1572864
net.ipv4.udp_mem = 786432 1048576 1572864

# ═══════════════════════════════════════════════════════════
# Connection Tracking - برای NAT بهتر
# ═══════════════════════════════════════════════════════════
net.netfilter.nf_conntrack_max = 1048576
net.nf_conntrack_max = 1048576

# VFS Cache
vm.swappiness = 10
vm.dirty_ratio = 60
vm.dirty_background_ratio = 5
EOF

    # اعمال تنظیمات
    sysctl -p /etc/sysctl.d/99-ocserv-optimized.conf > /dev/null 2>&1 || true
    
    log_success "VPS network optimized with BBR + advanced settings"
}

setup_firewall() {
    log_info "Configuring firewall (safe mode - won't break existing rules)..."
    
    # Get default interface
    DEFAULT_IF=$(ip route | grep default | awk '{print $5}' | head -1)
    
    if [[ -z "$DEFAULT_IF" ]]; then
        log_warning "Could not detect default interface, skipping firewall config"
        return
    fi
    
    # ═══════════════════════════════════════════════════════════
    # SAFE MODE: Only ADD rules, never DELETE or FLUSH
    # This prevents breaking SSH or other services
    # ═══════════════════════════════════════════════════════════
    
    # Check if MASQUERADE rule already exists before adding
    if ! iptables -t nat -C POSTROUTING -o $DEFAULT_IF -j MASQUERADE 2>/dev/null; then
        iptables -t nat -A POSTROUTING -o $DEFAULT_IF -j MASQUERADE
        log_info "Added NAT MASQUERADE rule"
    fi
    
    # Check if forwarding rules exist before adding
    if ! iptables -C FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null; then
        iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
    fi
    
    if ! iptables -C FORWARD -s 192.168.100.0/24 -j ACCEPT 2>/dev/null; then
        iptables -A FORWARD -s 192.168.100.0/24 -j ACCEPT
    fi
    
    # MSS Clamping (safe to add)
    iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu 2>/dev/null || true
    
    # Save iptables rules (non-interactive)
    if command -v netfilter-persistent &> /dev/null; then
        netfilter-persistent save > /dev/null 2>&1 || true
    else
        # Pre-configure answers for iptables-persistent
        echo iptables-persistent iptables-persistent/autosave_v4 boolean true | debconf-set-selections 2>/dev/null || true
        echo iptables-persistent iptables-persistent/autosave_v6 boolean true | debconf-set-selections 2>/dev/null || true
        DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent > /dev/null 2>&1 || true
        netfilter-persistent save > /dev/null 2>&1 || true
    fi
    
    # ═══════════════════════════════════════════════════════════
    # UFW: Only add ALLOW rules, never disable or reset
    # ═══════════════════════════════════════════════════════════
    if command -v ufw &> /dev/null; then
        # Make sure SSH is always allowed first!
        ufw allow 22/tcp > /dev/null 2>&1 || true
        ufw allow ssh > /dev/null 2>&1 || true
        
        # Then allow our ports
        ufw allow ${OCSERV_PORT}/tcp > /dev/null 2>&1 || true
        ufw allow ${OCSERV_PORT}/udp > /dev/null 2>&1 || true
        ufw allow ${PANEL_PORT}/tcp > /dev/null 2>&1 || true
        
        log_info "UFW rules added (SSH: allowed, VPN: ${OCSERV_PORT}, Panel: ${PANEL_PORT})"
    fi
    
    log_success "Firewall configured (safe mode - existing rules preserved)"
}

start_services() {
    log_info "Starting services..."
    
    systemctl restart ocserv
    systemctl start ocserv-panel
    
    sleep 3
    
    if systemctl is-active --quiet ocserv; then
        log_success "OCServ is running"
    else
        log_error "OCServ failed to start"
        journalctl -u ocserv -n 10 --no-pager
    fi
    
    if systemctl is-active --quiet ocserv-panel; then
        log_success "OCServ Panel is running"
    else
        log_error "OCServ Panel failed to start"
        journalctl -u ocserv-panel -n 10 --no-pager
    fi
}

save_install_info() {
    # Save installation info for reference
    cat > /root/.ocserv-panel-info << EOF
Domain: ${DOMAIN}
Panel URL: https://${DOMAIN}:${PANEL_PORT}
Panel Secret Path: /${PANEL_PATH}
Full Panel URL: https://${DOMAIN}:${PANEL_PORT}/${PANEL_PATH}
Admin Username: ${ADMIN_USER}
VPN Port: ${OCSERV_PORT}
Installed: $(date)
EOF
    chmod 600 /root/.ocserv-panel-info
}

print_info() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║        🎉 Installation Completed Successfully! 🎉         ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}                      🌐 Panel Access                        ${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${YELLOW}Panel URL:${NC}"
    echo -e "  ${GREEN}https://${DOMAIN}:${PANEL_PORT}${NC}"
    echo ""
    echo -e "  ${YELLOW}Admin Username:${NC} ${GREEN}${ADMIN_USER}${NC}"
    echo -e "  ${YELLOW}Admin Password:${NC} ${GREEN}[your password]${NC}"
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}                      🔐 VPN Server                         ${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${YELLOW}Server:${NC} ${GREEN}${DOMAIN}${NC}"
    echo -e "  ${YELLOW}Port:${NC}   ${GREEN}${OCSERV_PORT}${NC}"
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}                      📋 Commands                           ${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${YELLOW}Panel Logs:${NC}    journalctl -u ocserv-panel -f"
    echo -e "  ${YELLOW}OCServ Logs:${NC}   journalctl -u ocserv -f"
    echo -e "  ${YELLOW}Restart Panel:${NC} systemctl restart ocserv-panel"
    echo -e "  ${YELLOW}Restart VPN:${NC}   systemctl restart ocserv"
    echo ""
    echo -e "  ${YELLOW}Install Info:${NC}  cat /root/.ocserv-panel-info"
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Main installation flow
main() {
    print_banner
    check_root
    check_os
    get_public_ip
    select_server_mode
    get_user_input
    
    echo ""
    log_info "Starting installation..."
    echo ""
    
    install_dependencies
    setup_ssl
    configure_ocserv
    setup_panel
    create_admin_user
    create_systemd_service
    optimize_vps_network
    setup_firewall
    
    # Install Gost for Iran server mode
    if [[ "$SERVER_MODE" == "iran" ]]; then
        install_gost
    fi
    
    start_services
    save_install_info
    print_info
    
    # Print tunnel instructions for Iran mode
    if [[ "$SERVER_MODE" == "iran" ]]; then
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${CYAN}                    🔗 تنظیم تانل                            ${NC}"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo -e "  ${YELLOW}مراحل تنظیم تانل:${NC}"
        echo -e "  1. وارد پنل شو و به بخش ${GREEN}تانل${NC} برو"
        echo -e "  2. IP سرور خارج (فرانسه) رو وارد کن"
        echo -e "  3. تانل رو روشن کن"
        echo ""
        echo -e "  ${YELLOW}روی سرور خارج این دستور رو بزن:${NC}"
        echo -e "  ${GREEN}bash <(curl -sL ${GITHUB_RAW}/france-setup.sh)${NC}"
        echo ""
        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    fi
}

# Uninstall function
uninstall() {
    log_warning "Uninstalling OCServ Panel..."
    
    systemctl stop ocserv-panel 2>/dev/null || true
    systemctl disable ocserv-panel 2>/dev/null || true
    rm -f /etc/systemd/system/ocserv-panel.service
    systemctl daemon-reload
    
    rm -rf $PANEL_DIR
    rm -f /root/.ocserv-panel-info
    
    log_success "OCServ Panel uninstalled"
    log_info "OCServ VPN service was kept intact"
}

# Parse arguments
case "${1:-}" in
    uninstall)
        uninstall
        ;;
    *)
        main
        ;;
esac
