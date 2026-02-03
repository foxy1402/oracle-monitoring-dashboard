#!/bin/bash
# Update script for Oracle Monitoring Dashboard on Ubuntu

echo "================================================"
echo "  Oracle Monitoring Dashboard - Update Script  "
echo "         Ubuntu Edition                         "
echo "================================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo: sudo ./update-ubuntu.sh"
    exit 1
fi

# Determine the repository directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/monitor-dashboard.py" ]; then
    REPO_DIR="$SCRIPT_DIR"
    echo "✓ Using current directory: $REPO_DIR"
elif [ -d "/home/ubuntu/oracle-monitoring-dashboard" ]; then
    REPO_DIR="/home/ubuntu/oracle-monitoring-dashboard"
    echo "✓ Using repository: $REPO_DIR"
elif [ -d "/home/opc/oracle-monitoring-dashboard" ]; then
    REPO_DIR="/home/opc/oracle-monitoring-dashboard"
    echo "✓ Using repository: $REPO_DIR"
else
    echo "❌ Repository directory not found"
    echo "Please run from the repository directory or clone to:"
    echo "  /home/ubuntu/oracle-monitoring-dashboard"
    echo "  /home/opc/oracle-monitoring-dashboard"
    exit 1
fi

INSTALL_DIR="/opt/oracle-monitor"

echo "[1/4] Pulling latest changes from GitHub..."
cd "$REPO_DIR" || exit 1

# Determine the actual user (not root when using sudo)
ACTUAL_USER="${SUDO_USER:-ubuntu}"

# Only pull if it's a git repository
if [ -d ".git" ]; then
    sudo -u "$ACTUAL_USER" git pull
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to pull updates from GitHub"
        exit 1
    fi
else
    echo "⚠ Not a git repository, skipping git pull"
fi

echo ""
echo "[2/4] Copying files to installation directory..."

if [ ! -f "$REPO_DIR/monitor-dashboard.py" ]; then
    echo "❌ monitor-dashboard.py not found in $REPO_DIR"
    exit 1
fi

cp "$REPO_DIR/monitor-dashboard.py" "$INSTALL_DIR/monitor-dashboard.py"

if [ $? -ne 0 ]; then
    echo "❌ Failed to copy files"
    exit 1
fi

echo "✓ Files copied successfully"

echo ""
echo "[3/4] Restarting oracle-monitor service..."
systemctl restart oracle-monitor

if [ $? -ne 0 ]; then
    echo "❌ Failed to restart service"
    exit 1
fi

echo ""
echo "[4/4] Checking service status..."
sleep 2

if systemctl is-active --quiet oracle-monitor; then
    echo "✅ Update completed successfully!"
    echo ""
    
    # Get the public IP
    PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || hostname -I | awk '{print $1}')
    
    echo "Dashboard is running at: http://$PUBLIC_IP/"
    echo ""
    systemctl status oracle-monitor --no-pager -l
else
    echo "❌ Service is not running. Check logs with:"
    echo "   sudo journalctl -u oracle-monitor -n 50"
    exit 1
fi
