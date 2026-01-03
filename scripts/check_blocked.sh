#!/bin/bash
# OCServ Connect Script - Check if IP is blocked
# This script runs BEFORE a connection is established
# Return 0 = allow, Return 1 = block

BLOCKED_FILE="/etc/ocserv/blocked_ips.txt"

# Get client IP from environment (set by OCServ)
CLIENT_IP="${IP_REAL:-$REMOTE_IP}"

# If no blocked file exists, allow
if [[ ! -f "$BLOCKED_FILE" ]]; then
    exit 0
fi

# Check if IP is in blocked list
if grep -q "^${CLIENT_IP}$" "$BLOCKED_FILE" 2>/dev/null; then
    logger -t ocserv-connect "BLOCKED connection from $CLIENT_IP (user: ${USERNAME:-unknown})"
    exit 1  # Block the connection
fi

# Allow the connection
exit 0
