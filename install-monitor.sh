#!/bin/bash

###############################################################################
# Oracle Instance Monitoring Dashboard - Installation Script
# Installs and configures the monitoring dashboard on port 80
###############################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}Oracle Instance Monitoring Dashboard${NC}"
echo -e "${BLUE}Installation Script${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   echo "Please run: sudo ./install-monitor.sh"
   exit 1
fi

echo -e "${BLUE}[1/7]${NC} Installing required dependencies..."

# Install Python and psutil
if ! python3 -c "import psutil" 2>/dev/null; then
    echo "Installing psutil..."
    pip3 install psutil --break-system-packages 2>/dev/null || \
    pip3 install psutil 2>/dev/null || \
    dnf install -y python3-psutil
fi

echo -e "${GREEN}✓ Dependencies installed${NC}"

echo -e "${BLUE}[2/7]${NC} Creating installation directory..."

# Create directory
mkdir -p /opt/oracle-monitor
cp monitor-dashboard.py /opt/oracle-monitor/
chmod +x /opt/oracle-monitor/monitor-dashboard.py

echo -e "${GREEN}✓ Files copied to /opt/oracle-monitor${NC}"

echo -e "${BLUE}[3/7]${NC} Creating systemd service..."

# Create systemd service
cat > /etc/systemd/system/oracle-monitor.service <<EOF
[Unit]
Description=Oracle Instance Monitoring Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/oracle-monitor
ExecStart=/usr/bin/python3 /opt/oracle-monitor/monitor-dashboard.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓ Systemd service created${NC}"

echo -e "${BLUE}[4/7]${NC} Configuring firewall for port 80..."

# Configure firewalld if active
if systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --add-service=http 2>/dev/null || firewall-cmd --permanent --add-port=80/tcp
    firewall-cmd --reload
    echo -e "${GREEN}✓ Firewalld configured${NC}"
else
    echo -e "${YELLOW}! Firewalld not active, skipping${NC}"
fi

# Add iptables rule
iptables -I INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || true

echo -e "${GREEN}✓ Firewall configured${NC}"

echo -e "${BLUE}[5/7]${NC} Configuring Oracle Cloud Security List..."
echo ""
echo -e "${YELLOW}IMPORTANT: You must configure Oracle Cloud Security List!${NC}"
echo ""
echo "1. Go to Oracle Cloud Console: https://cloud.oracle.com"
echo "2. Navigate to: Menu → Networking → Virtual Cloud Networks"
echo "3. Click your VCN → Security Lists → Default Security List"
echo "4. Click 'Add Ingress Rules'"
echo "5. Enter:"
echo "   - Source Type: CIDR"
echo "   - Source CIDR: 0.0.0.0/0"
echo "   - IP Protocol: TCP"
echo "   - Destination Port Range: 80"
echo "   - Description: Oracle Monitoring Dashboard"
echo "6. Click 'Add Ingress Rules'"
echo ""
read -p "Press Enter after configuring Oracle Cloud Security List..."

echo -e "${BLUE}[6/7]${NC} Starting monitoring service..."

# Reload systemd
systemctl daemon-reload

# Enable and start service
systemctl enable oracle-monitor
systemctl restart oracle-monitor

# Wait for service to start
sleep 3

if systemctl is-active --quiet oracle-monitor; then
    echo -e "${GREEN}✓ Monitoring service started successfully${NC}"
else
    echo -e "${RED}✗ Service failed to start${NC}"
    echo "Checking logs..."
    journalctl -u oracle-monitor -n 20 --no-pager
    exit 1
fi

echo -e "${BLUE}[7/7]${NC} Verifying installation..."

# Get public IP
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null)

if [ -z "$PUBLIC_IP" ]; then
    echo -e "${YELLOW}! Could not automatically detect public IP${NC}"
    read -p "Enter your instance's public IP address: " PUBLIC_IP
fi

echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""
echo -e "${BLUE}Dashboard Access:${NC}"
echo "  URL: http://${PUBLIC_IP}"
echo ""
echo -e "${BLUE}Service Management:${NC}"
echo "  Status:  systemctl status oracle-monitor"
echo "  Restart: systemctl restart oracle-monitor"
echo "  Logs:    journalctl -u oracle-monitor -f"
echo ""
echo -e "${BLUE}Features:${NC}"
echo "  - Real-time CPU, memory, disk monitoring"
echo "  - Network statistics and connections"
echo "  - Process monitoring"
echo "  - WireGuard VPN status (if installed)"
echo "  - Service status tracking"
echo "  - Auto-refresh every 3 seconds"
echo "  - No buttons or forms (read-only)"
echo ""
echo -e "${YELLOW}Security Notes:${NC}"
echo "  - Dashboard runs on port 80 (default HTTP)"
echo "  - No authentication required (consider restricting access)"
echo "  - IP addresses are partially masked for security"
echo "  - No sensitive credentials are displayed"
echo ""
echo -e "${GREEN}Access your dashboard now at: http://${PUBLIC_IP}${NC}"
echo ""
