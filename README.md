# Linux Instance Monitoring Dashboard

A comprehensive, real-time monitoring dashboard for Linux servers — works on **any Linux distribution** via Docker/Portainer, or installed directly on Oracle Linux / Ubuntu.

## ⚡ Quick Start

### Docker / Portainer (recommended — any Linux)

Paste into Portainer **Stacks → Add stack**:

```yaml
services:
  oracle-monitor:
    image: ghcr.io/foxy1402/oracle-monitoring-dashboard:latest
    container_name: oracle-monitor
    restart: unless-stopped
    ports:
      - "80:80"
    pid: host
    volumes:
      - /:/rootfs:ro,rslave
      - /sys:/sys:ro
      - /etc/os-release:/etc/os-release:ro
      - /etc/hostname:/etc/hostname:ro
      - /var/log:/var/log:ro
    cap_add:
      - SYS_PTRACE
```

**Access at**: `http://YOUR_SERVER_IP`

---

### For Oracle Linux 8/9 (bare-metal / VM)

```bash
git clone https://github.com/foxy1402/oracle-monitoring-dashboard.git
cd oracle-monitoring-dashboard
chmod +x install-monitor.sh
sudo ./install-monitor.sh
```

### For Ubuntu 20.04/22.04 (bare-metal / VM)

```bash
git clone https://github.com/foxy1402/oracle-monitoring-dashboard.git
cd oracle-monitoring-dashboard
chmod +x install-monitor-ubuntu.sh
sudo ./install-monitor-ubuntu.sh
```

Then configure your cloud provider firewall/security group to allow TCP port 80.

**Access at**: `http://YOUR_INSTANCE_IP`

## 📊 Features

### System Monitoring
- **CPU Usage**: Overall and per-core CPU utilization with load averages
- **Memory Usage**: RAM and swap memory statistics with usage percentages
- **Disk Usage**: All mounted filesystems with space utilization
- **Disk I/O**: Read/write statistics and operation counts

### Network Monitoring
- **Live Throughput**: Real-time RX/TX bandwidth (KB/s or MB/s) updated every 3 s
- **Host-scoped Counters**: Docker image reads `/proc/1/net/dev` (host network namespace) — shows real interface traffic, not just the container veth pair
- **Per-interface Breakdown**: Cumulative bytes/packets per physical NIC
- **Active Connections**: Established, listening, and time-wait connections

### Process Monitoring
- **Top Processes**: Top 15 host processes by CPU usage (all host PIDs visible via `pid: host`)
- **Process Details**: PID, process name, full command line, user, CPU%, and memory%

### Service Monitoring
- **Auto-detected Services**: Scans host listening sockets (`/proc/1/net/tcp`, `tcp6`, `udp`, `udp6`) — no systemd required, works on any Linux distro
- **Port → Service mapping**: 45+ well-known ports mapped to friendly names (SSH, HTTP, MySQL, Redis, WireGuard, etc.)
- **Firewall**: Detects both firewalld (Oracle Linux) and UFW (Ubuntu) when present
- **WireGuard VPN**: Detected via `wg*` network interfaces — no `wg` binary required

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

**Via Docker (any Linux, recommended)**
- ✅ Any Linux distribution with Docker Engine
- ✅ Google Cloud, AWS, Azure, Oracle Cloud, Hetzner, bare-metal…
- ✅ amd64 and arm64 architectures

**Bare-metal / VM install scripts**
- ✅ Oracle Linux 8/9 (x86_64 & ARM64)
- ✅ Ubuntu 20.04 LTS (x86_64 & ARM64)
- ✅ Ubuntu 22.04 LTS (x86_64 & ARM64)
- ✅ Ubuntu Minimal variants

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

### Docker / Portainer Deployment

The pre-built image is published to GitHub Container Registry and supports both `linux/amd64` and `linux/arm64`. No installation script or Python setup required — deploy on **any** Linux host running Docker.

#### Option A — Portainer Stack (GUI)

1. Open Portainer → **Stacks** → **Add stack**
2. Give it a name (e.g. `linux-monitor`)
3. Paste the compose below into the **Web editor**
4. Click **Deploy the stack**

```yaml
services:
  oracle-monitor:
    image: ghcr.io/foxy1402/oracle-monitoring-dashboard:latest
    container_name: oracle-monitor
    restart: unless-stopped
    ports:
      - "80:80"
    pid: host
    volumes:
      - /:/rootfs:ro,rslave
      - /sys:/sys:ro
      - /etc/os-release:/etc/os-release:ro
      - /etc/hostname:/etc/hostname:ro
      - /var/log:/var/log:ro
    cap_add:
      - SYS_PTRACE
```

#### Option B — Docker CLI

```bash
docker run -d \
  --name oracle-monitor \
  --restart unless-stopped \
  -p 80:80 \
  --pid host \
  -v /:/rootfs:ro,rslave \
  -v /sys:/sys:ro \
  -v /etc/os-release:/etc/os-release:ro \
  -v /etc/hostname:/etc/hostname:ro \
  -v /var/log:/var/log:ro \
  --cap-add SYS_PTRACE \
  ghcr.io/foxy1402/oracle-monitoring-dashboard:latest
```

#### Option C — Docker Compose CLI

```bash
# Clone just the compose file
curl -O https://raw.githubusercontent.com/foxy1402/oracle-monitoring-dashboard/main/docker-compose.yml

# Pull image and start
docker compose up -d
```

#### Why those mounts?

| Mount | Purpose |
|---|---|
| `/:/rootfs:ro,rslave` | Host filesystem — the script reads `/proc/1/mounts` to list real disk partitions and calls `disk_usage('/rootfs/<mountpoint>')` for accurate usage |
| `/sys:/sys:ro` | Hardware/block device info |
| `/etc/os-release:/etc/os-release:ro` | Shows correct OS name in the dashboard |
| `/etc/hostname:/etc/hostname:ro` | Shows host hostname instead of container ID |
| `/var/log:/var/log:ro` | Login history (`last` command) |
| `pid: host` | Shares host PID namespace — psutil sees **all host processes** via `/proc`; also exposes `/proc/1/net/dev` (host NIC stats) and `/proc/1/net/tcp*` (host listening ports) for accurate network and service detection |
| `SYS_PTRACE` | Allows psutil to inspect process details |

> **Note on `/proc`**: `/proc` is intentionally **not** bind-mounted. `pid: host` already makes the container's own `/proc` reflect host data, and avoids the AppArmor conflict (`/proc/self/attr/apparmor/exec` must be writable at container init).

#### Managing the container

```bash
# View logs
docker logs -f oracle-monitor

# Restart
docker restart oracle-monitor

# Stop and remove
docker stop oracle-monitor && docker rm oracle-monitor

# Pull latest image and recreate
docker pull ghcr.io/foxy1402/oracle-monitoring-dashboard:latest
docker restart oracle-monitor
```

#### GHCR package visibility

If the image pull fails with a 401/403 error, the package may still be set to private after the first push. Fix it once:

1. GitHub → your profile → **Packages** → `oracle-monitoring-dashboard`
2. **Package settings** → **Change visibility** → **Public**

Or add a Portainer registry credential with a GitHub Personal Access Token (PAT) that has the `read:packages` scope.

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
   - **Live throughput**: real-time Download (RX) and Upload (TX) speed
   - Source badge: **host** (green) = reading from host NIC, **container** (yellow) = fallback
   - Cumulative total sent/received since boot
   - Packet counts, errors, and drops
   - Per-interface breakdown (each physical NIC listed separately)

7. **Disk I/O Statistics Card**
   - Total bytes read/written
   - Read/write operation counts

8. **Network Connections Card**
   - Established connections
   - Listening sockets
   - Time-wait connections
   - Total connections

9. **Detected Services Card**
   - Auto-detected from host listening sockets — no systemd or service manager required
   - Table of Port / Protocol / Service name for every bound socket
   - Works identically on any Linux distribution
   - Firewall status shown when firewalld or UFW is active

10. **WireGuard VPN Card** (if installed)
    - VPN service status
    - Connected peer count
    - Active peer details with transfer stats

11. **Top Processes Card**
    - Top 15 host processes by CPU usage (table always populated — no empty first-load)
    - Process name (bold) + full command line for easy identification
    - PID, user, CPU%, memory% columns
    - CPU% values become accurate from the second refresh onward (psutil baseline)

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
A: Via Docker — any Linux distribution (Debian, Ubuntu, CentOS, Fedora, Alpine, GCP/AWS/Azure images, etc.) on amd64 or arm64. For bare-metal install scripts: Oracle Linux 8/9 and Ubuntu 20.04/22.04.

**Q: Can multiple people view the dashboard simultaneously?**  
A: Yes! Each browser session is independent. The dashboard handles multiple concurrent viewers.

**Q: Does this work on other cloud providers?**  
A: Yes! Via Docker it works on Google Cloud, AWS, Azure, Hetzner, DigitalOcean, or any Linux host. Just open TCP port 80 in your provider's firewall/security group.

**Q: How do I update the Docker image?**  
A: The `:latest` image is rebuilt automatically on every push to `main`. To update your running container:
```bash
docker pull ghcr.io/foxy1402/oracle-monitoring-dashboard:latest
docker restart oracle-monitor
```
In Portainer: **Stacks → your stack → Editor → Update the stack** (or use the **Recreate** button on the container).

**Q: Can I run it on a different port?**  
A: Yes — change the left side of the port mapping: `-p 8080:80` exposes it on host port 8080.

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
├── monitor-dashboard.py          # Bare-metal dashboard (Oracle Linux / Ubuntu install scripts)
├── monitor-dashboard-docker.py   # Docker/GHCR edition (host /proc/1/net/*, port-based services)
├── Dockerfile                    # Multi-stage Alpine build — copies monitor-dashboard-docker.py
├── docker-compose.yml            # Portainer/Docker Compose deployment
├── requirements.txt              # Python dependencies (psutil)
├── .github/
│   └── workflows/
│       └── docker-publish.yml   # CI: builds & pushes :latest to GHCR on every push
├── install-monitor.sh            # Oracle Linux bare-metal installer
├── install-monitor-ubuntu.sh     # Ubuntu bare-metal installer
├── update.sh                     # Oracle Linux updater
├── update-ubuntu.sh              # Ubuntu updater
└── README.md                     # This file
```

## 🌟 Credits

Built for Linux infrastructure monitoring with focus on:
- ✅ Real-time performance tracking
- ✅ Security and privacy (XSS protection, input sanitization)
- ✅ Universal Linux support via Docker (any distro, amd64 + arm64)
- ✅ Bare-metal install for Oracle Linux and Ubuntu
- ✅ Lightweight Docker image (~65 MB, Alpine-based)
- ✅ Lightweight resource usage (~1-2% CPU, ~30-50 MB RAM)
- ✅ Zero configuration — no env vars required

---

**Repository**: https://github.com/foxy1402/oracle-monitoring-dashboard

**Docker image**: `ghcr.io/foxy1402/oracle-monitoring-dashboard:latest`

**Access your dashboard**: `http://YOUR_SERVER_IP`
