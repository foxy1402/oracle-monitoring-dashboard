#!/bin/bash
# Simple update script for Oracle Monitoring Dashboard

echo "================================================"
echo "  Oracle Monitoring Dashboard - Update Script  "
echo "================================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo: sudo ./update.sh"
    exit 1
fi

# Navigate to the repository directory
REPO_DIR="/home/opc/oracle-monitoring-dashboard"
INSTALL_DIR="/opt/oracle-monitor"

echo "[1/4] Pulling latest changes from GitHub..."
cd "$REPO_DIR" || exit 1
sudo -u opc git pull

if [ $? -ne 0 ]; then
    echo "❌ Failed to pull updates from GitHub"
    exit 1
fi

echo ""
echo "[2/4] Copying files to installation directory..."
cp "$REPO_DIR/monitor-dashboard.py" "$INSTALL_DIR/monitor-dashboard.py"

if [ $? -ne 0 ]; then
    echo "❌ Failed to copy files"
    exit 1
fi

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
systemctl is-active --quiet oracle-monitor

if [ $? -eq 0 ]; then
    echo "✅ Update completed successfully!"
    echo ""
    echo "Dashboard is running at: http://$(hostname -I | awk '{print $1}')/"
    echo ""
    systemctl status oracle-monitor --no-pager -l
else
    echo "❌ Service is not running. Check logs with: sudo journalctl -u oracle-monitor -n 50"
    exit 1
fi
