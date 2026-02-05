# Dashboard Connectivity Issues - FIXED

## Problem Summary
The Oracle monitoring dashboard at 140.245.63.92 was periodically becoming unresponsive with "took too long to respond" errors, even though the Python process was still running. This required manual SSH restarts multiple times per week.

## Root Cause Analysis
1. **Single-threaded HTTP server** - The original code used Python's basic `HTTPServer` which can only handle one request at a time
2. **Blocking CPU metrics** - The `/api/metrics` endpoint called `psutil.cpu_percent(interval=0.5)` which blocked the server for 0.5 seconds per request
3. **No connection timeouts** - Connections could hang indefinitely
4. **Accumulating CLOSE-WAIT connections** - Dead connections piled up (4 found during diagnosis), eventually causing the server to stop accepting new connections

## Fixes Applied

### 1. Multi-threaded Server
```python
from socketserver import ThreadingMixIn

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
```
- Now handles concurrent requests instead of blocking
- Prevents one slow request from blocking all others

### 2. Connection Timeouts
```python
class MonitorHandler(BaseHTTPRequestHandler):
    timeout = 10  # 10-second timeout for connections
```
- Prevents hung connections from accumulating
- Forces cleanup of stale requests

### 3. Optimized CPU Metrics
```python
cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)  # Was 0.5s
```
- Reduced blocking time by 80% (from 0.5s to 0.1s)
- Still provides accurate CPU readings

### 4. Proper Signal Handling
```python
def signal_handler(sig, frame):
    print('\nShutting down server...')
    if server:
        server.shutdown()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```
- Ensures clean shutdown
- Properly releases port 80

### 5. Systemd Service Setup
Created `/etc/systemd/system/monitor-dashboard.service`:
```ini
[Unit]
Description=Oracle Instance Monitoring Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/oracle-monitor
ExecStart=/usr/bin/python3 /opt/oracle-monitor/monitor-dashboard.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Benefits:
- Automatic startup on boot
- Auto-restart if it crashes
- Centralized logging via journalctl
- Easy management: `sudo systemctl start/stop/restart monitor-dashboard`

## Verification Results

### Before Fix:
- HTTP Status: 000 (timeout)
- 4 CLOSE-WAIT connections hanging
- Server became unresponsive after moderate load

### After Fix:
- HTTP Status: 200 (success)
- Response time: ~0.008-0.06 seconds
- 10 concurrent requests: All succeeded
- 0 CLOSE-WAIT connections
- Handles concurrent load without issues

## How to Manage

### Check Status:
```bash
sudo systemctl status monitor-dashboard
```

### View Logs:
```bash
sudo journalctl -u monitor-dashboard --no-pager -n 50
```

### Restart (if needed):
```bash
sudo systemctl restart monitor-dashboard
```

### Stop/Start:
```bash
sudo systemctl stop monitor-dashboard
sudo systemctl start monitor-dashboard
```

## Long-term Monitoring
Monitor for CLOSE-WAIT connections periodically:
```bash
sudo ss -tn | grep CLOSE-WAIT | grep :80 | wc -l
```
Should remain at 0 or very low (<3).

## Files Modified
- `/opt/oracle-monitor/monitor-dashboard.py` - Updated with threading and timeouts
- `/etc/systemd/system/monitor-dashboard.service` - New systemd service file

---
**Date Fixed:** February 5, 2026  
**Status:** ✅ Resolved - Dashboard now stable with proper connection handling
