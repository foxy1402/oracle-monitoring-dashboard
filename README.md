# Oracle Instance Monitoring Dashboard

A comprehensive, real-time monitoring dashboard for Oracle Cloud instances running **Oracle Linux** or **Ubuntu**. Access directly via your instance IP address with no port number required.

## ⚡ Quick Start

### For Oracle Linux 8/9

```bash
git clone https://github.com/foxy1402/oracle-monitoring-dashboard.git
cd oracle-monitoring-dashboard
chmod +x install-monitor.sh
sudo ./install-monitor.sh
```

### For Ubuntu 20.04/22.04

```bash
git clone https://github.com/foxy1402/oracle-monitoring-dashboard.git
cd oracle-monitoring-dashboard
chmod +x install-monitor-ubuntu.sh
sudo ./install-monitor-ubuntu.sh
```

Then configure Oracle Cloud Security List (instructions shown during installation).

**Access at**: `http://YOUR_INSTANCE_IP`

## 📊 Features

### System Monitoring
- **CPU Usage**: Overall and per-core CPU utilization with load averages
- **Memory Usage**: RAM and swap memory statistics with usage percentages
- **Disk Usage**: All mounted filesystems with space utilization
- **Disk I/O**: Read/write statistics and operation counts

### Network Monitoring
- **Network Statistics**: Data sent/received, packets, errors, and drops
- **Active Connections**: Established, listening, and time-wait connections
- **Connection Details**: Real-time network connection tracking

### Process Monitoring
- **Top Processes**: Top 10 processes by CPU usage
- **Process Details**: PID, name, user, CPU%, and memory%

### Service Monitoring
- **SSH Service**: Status of SSH daemon
- **Firewall**: Detects both firewalld (Oracle Linux) and UFW (Ubuntu)
- **WireGuard VPN**: Connection status and active peers (if installed)

### Security Features
- **Read-only Dashboard**: No buttons or forms that execute commands
- **IP Masking**: Partial masking of IP addresses for security
- **No Credentials**: No passwords or sensitive keys displayed
- **XSS Protection**: All user input properly sanitized
- **Login Tracking**: Recent login activity (sanitized)

### User Experience
- **Auto-refresh**: Updates every 3 seconds automatically
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Clean Interface**: Professional, easy-to-read metrics
- **Color-coded Alerts**: Visual warnings for high resource usage
- **No Port Number**: Access via http://YOUR_IP (runs on port 80)

### OS Compatibility
- ✅ **Oracle Linux 8/9** (x86_64 & ARM64)
- ✅ **Ubuntu 20.04 LTS** (x86_64 & ARM64)
- ✅ **Ubuntu 22.04 LTS** (x86_64 & ARM64)
- ✅ **Ubuntu Minimal** variants

## 🚀 Installation

### Oracle Linux 8/9 Installation

**Step 1: Clone Repository**

```bash
# SSH into your Oracle instance
ssh opc@YOUR_INSTANCE_IP

# Clone the repository
git clone https://github.com/foxy1402/oracle-monitoring-dashboard.git
cd oracle-monitoring-dashboard
```

**Step 2: Run Installation Script**

```bash
chmod +x install-monitor.sh
sudo ./install-monitor.sh
```

The script will:
1. Install Python dependencies (psutil)
2. Create systemd service
3. Configure firewalld
4. Start the monitoring service
5. Provide Oracle Cloud Security List instructions

---

### Ubuntu 20.04/22.04 Installation

**Step 1: Clone Repository**

```bash
# SSH into your Ubuntu instance  
ssh ubuntu@YOUR_INSTANCE_IP

# Ensure git is installed
sudo apt-get update
sudo apt-get install -y git

# Clone the repository
git clone https://github.com/foxy1402/oracle-monitoring-dashboard.git
cd oracle-monitoring-dashboard
```

**Step 2: Run Ubuntu Installation Script**

```bash
chmod +x install-monitor-ubuntu.sh
sudo ./install-monitor-ubuntu.sh
```

The script will:
1. Install Python 3 and psutil
2. Create systemd service
3. Auto-detect and configure firewall (UFW or firewalld)
4. Test local HTTP connection
5. Start the monitoring service
6. Provide Oracle Cloud Security List instructions

---

### Configure Oracle Cloud Security List

⚠️ **CRITICAL - Required for both Oracle Linux and Ubuntu!**

1. Login to Oracle Cloud Console: https://cloud.oracle.com
2. Navigate to: **Menu (☰)** → **Networking** → **Virtual Cloud Networks**
3. Click your VCN name
4. Click **Security Lists** → **Default Security List**
5. Click **Add Ingress Rules**
6. Fill in:
   - **Source Type**: CIDR
   - **Source CIDR**: `0.0.0.0/0`
   - **IP Protocol**: TCP
   - **Destination Port Range**: `80`
   - **Description**: Oracle Monitoring Dashboard
7. Click **Add Ingress Rules**

**Done!** Access your dashboard at: `http://YOUR_INSTANCE_IP`

## Usage

### Accessing the Dashboard

Simply open a web browser and navigate to:
```
http://YOUR_INSTANCE_IP
```

No port number needed! The dashboard runs on port 80 (default HTTP).

### What You'll See

The dashboard displays:

1. **Header Section**
   - System hostname
   - Last update timestamp
   - Auto-refresh indicator

2. **System Information Card**
   - Hostname
   - Operating system
   - Kernel version
   - Architecture
   - System uptime

3. **CPU Usage Card**
   - Overall CPU percentage
   - Load averages (1m, 5m, 15m)
   - Per-core CPU usage with individual percentages

4. **Memory Usage Card**
   - RAM usage (used/total)
   - Available memory
   - Swap usage
   - Percentage indicators with color coding

5. **Disk Usage Card**
   - All mounted filesystems
   - Used/free space per partition
   - Percentage bars with color coding
   - Device and filesystem type

6. **Network Statistics Card**
   - Total data sent/received
   - Packet counts
   - Network errors and drops

7. **Disk I/O Statistics Card**
   - Total bytes read/written
   - Read/write operation counts

8. **Network Connections Card**
   - Established connections
   - Listening sockets
   - Time-wait connections
   - Total connections

9. **Service Status Card**
   - SSH daemon status
   - Firewall status and open ports
   - WireGuard VPN status (if installed)

10. **WireGuard VPN Card** (if installed)
    - VPN service status
    - Connected peer count
    - Active peer details with transfer stats

11. **Top Processes Card**
    - Top 10 processes by CPU usage
    - Process details (PID, name, user, CPU%, memory%)

12. **Recent Login Activity Card**
    - Last 5 login events
    - Username and terminal
    - Login timestamp

### Color Coding

The dashboard uses color-coded progress bars:

- **Green**: Normal usage (0-74%)
- **Yellow**: Warning level (75-89%)
- **Red**: Critical level (90-100%)

## Management

### Service Commands

```bash
# Check service status
sudo systemctl status oracle-monitor

# Restart service
sudo systemctl restart oracle-monitor

# Stop service
sudo systemctl stop oracle-monitor

# Start service
sudo systemctl start oracle-monitor

# View live logs
sudo journalctl -u oracle-monitor -f

# View last 50 log entries
sudo journalctl -u oracle-monitor -n 50
```

### File Locations

```
/opt/oracle-monitor/
├── monitor-dashboard.py          # Main application

/etc/systemd/system/
└── oracle-monitor.service        # Systemd service file
```

### Update the Dashboard

#### For Oracle Linux

```bash
cd ~/oracle-monitoring-dashboard
chmod +x update.sh
sudo ./update.sh
```

#### For Ubuntu

```bash
cd ~/oracle-monitoring-dashboard
chmod +x update-ubuntu.sh
sudo ./update-ubuntu.sh
```

Both update scripts automatically:
- ✅ Pull latest code from GitHub
- ✅ Copy files to installation directory
- ✅ Restart the service
- ✅ Verify everything is working
- ✅ Display your public IP

#### Manual Update

To update manually on either OS:

```bash
# Navigate to repository
cd ~/oracle-monitoring-dashboard

# Pull latest changes
git pull

# Copy updated file
sudo cp monitor-dashboard.py /opt/oracle-monitor/

# Restart service
sudo systemctl restart oracle-monitor
```

## 🔒 Security

### Built-in Security Features

1. **Read-only Interface**: No forms or buttons that execute commands
2. **XSS Protection**: All user input is sanitized with HTML escaping
3. **IP Address Masking**: External IP addresses are partially hidden
4. **No Credential Display**: Passwords and keys are never shown
5. **Process Filtering**: Only shows necessary process information
6. **Limited History**: Only recent login events are shown
7. **Timeout Protection**: All subprocess calls have 5-second timeouts

### Recommended Security Practices

**1. Restrict Access by IP (Highly Recommended)**

Instead of allowing `0.0.0.0/0` in Oracle Cloud Security List:

1. Go to Oracle Cloud Console
2. Find the port 80 ingress rule
3. Edit the rule
4. Change **Source CIDR** from `0.0.0.0/0` to `YOUR_HOME_IP/32`
5. Get your IP from: https://whatismyip.com

This allows only YOUR IP address to access the dashboard.

**2. Add HTTP Authentication (Advanced)**

If you want password protection, you can add a reverse proxy with authentication:

```bash
# Install nginx
sudo dnf install -y nginx

# Configure nginx with basic auth
sudo htpasswd -c /etc/nginx/.htpasswd admin

# Configure nginx to proxy to the dashboard
# (See nginx documentation for proxy configuration)
```

**3. Use HTTPS Instead of HTTP**

For encrypted access:

1. Get a free SSL certificate from Let's Encrypt
2. Configure nginx as reverse proxy with SSL
3. Dashboard will still run on port 80 internally
4. Users access via HTTPS on port 443

**4. Firewall Best Practices**

Oracle Linux (firewalld):
```bash
# Only allow specific IP ranges
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="YOUR_IP/32" port protocol="tcp" port="80" accept'
sudo firewall-cmd --reload
```

Ubuntu (UFW):
```bash
# Only allow specific IP
sudo ufw allow from YOUR_IP to any port 80 proto tcp
```

## Troubleshooting

### Dashboard Not Loading

**Problem**: Cannot access http://YOUR_INSTANCE_IP

**Solutions**:

1. **Check if service is running**:
   ```bash
   sudo systemctl status oracle-monitor
   ```
   If not running: `sudo systemctl start oracle-monitor`

2. **Check Oracle Cloud Security List**:
   - Verify TCP port 80 ingress rule exists
   - Source should be `0.0.0.0/0` (or your IP)

3. **Check firewall**:
   
   Oracle Linux:
   ```bash
   sudo firewall-cmd --list-ports
   # Should include: 80/tcp
   ```
   If missing: `sudo firewall-cmd --permanent --add-port=80/tcp && sudo firewall-cmd --reload`
   
   Ubuntu:
   ```bash
   sudo ufw status
   # Should show: 80/tcp ALLOW
   ```
   If missing: `sudo ufw allow 80/tcp`

4. **Check if port 80 is in use**:
   ```bash
   sudo netstat -tlnp | grep :80
   ```
   If another service is using port 80, you may need to stop it.

### Service Fails to Start

**Problem**: Service won't start or crashes

**Check logs**:
```bash
sudo journalctl -u oracle-monitor -n 50
```

**Common causes**:

1. **Missing psutil module**:
   
   Oracle Linux:
   ```bash
   sudo pip3 install psutil --break-system-packages
   ```
   
   Ubuntu:
   ```bash
   sudo apt-get install python3-psutil
   # OR
   sudo pip3 install psutil
   ```

2. **Permission issues**:
   ```bash
   sudo chmod +x /opt/oracle-monitor/monitor-dashboard.py
   ```

3. **Port 80 already in use**:
   ```bash
   # Check what's using port 80
   sudo lsof -i :80
   
   # Stop conflicting service (e.g., httpd)
   sudo systemctl stop httpd
   ```

### Metrics Not Updating

**Problem**: Dashboard loads but shows old data

**Solutions**:

1. **Refresh browser**: Press Ctrl+F5 (hard refresh)

2. **Check browser console**: Press F12, look for JavaScript errors

3. **Verify API endpoint**:
   ```bash
   curl http://localhost/api/metrics
   # Should return JSON data
   ```

### High CPU Usage

**Problem**: Dashboard uses too much CPU

**This is normal** - The dashboard updates every 3 seconds and collects comprehensive metrics. However, you can:

1. **Reduce update frequency**: Edit `monitor-dashboard.py`, find:
   ```javascript
   updateInterval = setInterval(updateDashboard, 3000);
   ```
   Change `3000` to `5000` (5 seconds) or `10000` (10 seconds)

2. **Restart after edit**:
   ```bash
   sudo systemctl restart oracle-monitor
   ```

## Performance Impact

The monitoring dashboard is designed to be lightweight:

- **CPU Usage**: ~1-2% on average
- **Memory Usage**: ~30-50 MB
- **Network**: Minimal (only when browser is open)
- **Disk I/O**: Very low (read-only operations)

The dashboard only collects metrics when your browser requests them (every 3 seconds while viewing).

## Customization

### Change Update Frequency

Edit `/opt/oracle-monitor/monitor-dashboard.py`:

Find this line near the end:
```javascript
updateInterval = setInterval(updateDashboard, 3000);
```

Change `3000` to your desired milliseconds:
- `1000` = 1 second (may increase CPU usage)
- `5000` = 5 seconds
- `10000` = 10 seconds

Restart: `sudo systemctl restart oracle-monitor`

### Add Custom Metrics

You can extend the dashboard by editing the `get_system_metrics()` function in `monitor-dashboard.py`.

Example - Add custom application monitoring:

```python
# In get_system_metrics() function, add:
try:
    # Check if your app is running
    result = subprocess.run(['systemctl', 'is-active', 'your-app'],
                          capture_output=True, text=True)
    metrics['custom_app'] = {
        'status': result.stdout.strip(),
        'running': result.stdout.strip() == 'active'
    }
except:
    metrics['custom_app'] = {'status': 'unknown'}
```

Then update the HTML rendering section to display it.

## Uninstallation

To completely remove the monitoring dashboard:

```bash
# Stop and disable service
sudo systemctl stop oracle-monitor
sudo systemctl disable oracle-monitor

# Remove service file
sudo rm /etc/systemd/system/oracle-monitor.service
sudo systemctl daemon-reload

# Remove application files
sudo rm -rf /opt/oracle-monitor

# Remove firewall rule
# Oracle Linux:
sudo firewall-cmd --permanent --remove-port=80/tcp
sudo firewall-cmd --reload

# Ubuntu:
sudo ufw delete allow 80/tcp

# Remove Oracle Cloud Security List rule
# (Do this manually in Oracle Cloud Console)
```

## FAQ

**Q: Can I use a custom port instead of 80?**  
A: Yes! Edit `monitor-dashboard.py`, find `run_server(port=80)` and change to your desired port. Then update firewall rules and Oracle Cloud Security List accordingly.

**Q: What operating systems are supported?**  
A: Oracle Linux 8/9 and Ubuntu 20.04/22.04 (including Minimal variants) on both x86_64 and ARM64 architectures.

**Q: Can multiple people view the dashboard simultaneously?**  
A: Yes! Each browser session is independent. The dashboard handles multiple concurrent viewers.

**Q: Does this work on other cloud providers?**  
A: Yes! It works on any Linux server with Python 3 and systemd. Just adjust the firewall configuration for your provider.

**Q: Which firewall systems are supported?**  
A: Both firewalld (Oracle Linux, RHEL, CentOS) and UFW (Ubuntu, Debian) are automatically detected and configured.

**Q: Can I add authentication?**  
A: The dashboard itself doesn't have authentication, but you can add it using a reverse proxy like nginx with basic auth or by restricting access to specific IPs.

**Q: Will this interfere with my WireGuard setup?**  
A: No! The dashboard only reads WireGuard status. It doesn't modify any configurations or connections.

**Q: What happens if I restart my instance?**  
A: The monitoring service starts automatically on boot. The dashboard will be available immediately after restart.

**Q: Can I customize the colors or layout?**  
A: Yes! Edit the CSS in the `<style>` section of `monitor-dashboard.py`. All styling is inline for easy customization.

## 🛠️ Support

For issues or questions:

1. Check the Troubleshooting section above
2. Review service logs: `sudo journalctl -u oracle-monitor -n 50`
3. Verify Oracle Cloud Security List configuration
4. Ensure firewall allows port 80 (firewalld or UFW)
5. Check GitHub repository: https://github.com/foxy1402/oracle-monitoring-dashboard

## 🐛 Recent Bug Fixes

### Critical Security Fixes Applied

1. **XSS Vulnerability** - All user input now properly sanitized with HTML escaping
2. **Platform Compatibility** - Fixed `os.getloadavg()` crash on non-Unix systems
3. **Subprocess Timeouts** - Added 5-second timeout to prevent hanging
4. **Exception Handling** - Improved error handling throughout
5. **Network Permissions** - Graceful fallback for permission-denied scenarios
6. **UFW Support** - Added Ubuntu firewall detection and configuration

All fixes are included in the current version.

## License

This monitoring dashboard is provided as-is for Oracle Cloud instance monitoring. Feel free to modify and customize for your needs.

## 📦 What's Included

```
oracle-monitoring-dashboard/
├── monitor-dashboard.py          # Main dashboard (works on all supported OS)
├── install-monitor.sh            # Oracle Linux installer
├── install-monitor-ubuntu.sh     # Ubuntu installer  
├── update.sh                     # Oracle Linux updater
├── update-ubuntu.sh              # Ubuntu updater
└── README.md                     # This file
```

## 🌟 Credits

Built specifically for Oracle Cloud Infrastructure monitoring with focus on:
- ✅ Real-time performance tracking
- ✅ Security and privacy (XSS protection, input sanitization)
- ✅ Multi-OS support (Oracle Linux + Ubuntu)
- ✅ Ease of use (one-command installation)
- ✅ No external dependencies
- ✅ Lightweight resource usage (~1-2% CPU, ~30-50MB RAM)

---

**Repository**: https://github.com/foxy1402/oracle-monitoring-dashboard

**Access your dashboard**: `http://YOUR_INSTANCE_IP`

**Made with ❤️ for Oracle Cloud users running Oracle Linux or Ubuntu**
