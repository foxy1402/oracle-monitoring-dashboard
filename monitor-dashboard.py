#!/usr/bin/env python3
"""
Oracle Instance Monitoring Dashboard
Real-time system monitoring with auto-refresh
"""

import subprocess
import json
import psutil
import time
import socket
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import html

class MonitorHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.get_dashboard_html().encode())
        
        elif self.path == '/api/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            metrics = self.get_system_metrics()
            self.wfile.write(json.dumps(metrics).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def get_system_metrics(self):
        """Collect comprehensive system metrics"""
        metrics = {}
        
        try:
            # System information (initialize early so it's always available)
            metrics['system'] = {
                'hostname': html.escape(socket.gethostname()),
                'platform': html.escape(self.get_os_info()),
                'kernel': html.escape(os.uname().release),
                'architecture': html.escape(os.uname().machine)
            }
            
            # System uptime
            uptime_seconds = time.time() - psutil.boot_time()
            metrics['uptime'] = self.format_uptime(uptime_seconds)
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.5, percpu=True)
            metrics['cpu'] = {
                'overall': sum(cpu_percent) / len(cpu_percent) if cpu_percent else 0,
                'per_core': cpu_percent,
                'core_count': psutil.cpu_count(),
                'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            }
            
            # Memory metrics
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            metrics['memory'] = {
                'total': self.format_bytes(mem.total),
                'used': self.format_bytes(mem.used),
                'free': self.format_bytes(mem.available),
                'percent': mem.percent,
                'swap_total': self.format_bytes(swap.total),
                'swap_used': self.format_bytes(swap.used),
                'swap_percent': swap.percent
            }
            
            # Disk metrics
            disk_usage = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    if partition.mountpoint not in ['/boot/efi', '/dev', '/run']:
                        disk_usage.append({
                            'mountpoint': partition.mountpoint,
                            'device': partition.device,
                            'fstype': partition.fstype,
                            'total': self.format_bytes(usage.total),
                            'used': self.format_bytes(usage.used),
                            'free': self.format_bytes(usage.free),
                            'percent': usage.percent
                        })
                except PermissionError:
                    continue
            
            metrics['disk'] = disk_usage
            
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            if disk_io:
                metrics['disk_io'] = {
                    'read_bytes': self.format_bytes(disk_io.read_bytes),
                    'write_bytes': self.format_bytes(disk_io.write_bytes),
                    'read_count': disk_io.read_count,
                    'write_count': disk_io.write_count
                }
            
            # Network metrics
            net_io = psutil.net_io_counters()
            metrics['network'] = {
                'bytes_sent': self.format_bytes(net_io.bytes_sent),
                'bytes_recv': self.format_bytes(net_io.bytes_recv),
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv,
                'errors_in': net_io.errin,
                'errors_out': net_io.errout,
                'drops_in': net_io.dropin,
                'drops_out': net_io.dropout
            }
            
            # Network connections
            try:
                connections = psutil.net_connections(kind='inet')
                metrics['connections'] = {
                    'established': len([c for c in connections if c.status == 'ESTABLISHED']),
                    'listen': len([c for c in connections if c.status == 'LISTEN']),
                    'time_wait': len([c for c in connections if c.status == 'TIME_WAIT']),
                    'total': len(connections)
                }
            except (psutil.AccessDenied, PermissionError):
                metrics['connections'] = {
                    'established': 0,
                    'listen': 0,
                    'time_wait': 0,
                    'total': 0,
                    'error': 'Access denied - requires root'
                }
            
            # Top processes by CPU
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
                try:
                    proc_info = proc.info
                    if proc_info['cpu_percent'] > 0:
                        # Sanitize process name and username to prevent XSS
                        proc_info['name'] = html.escape(str(proc_info.get('name', 'unknown')))
                        proc_info['username'] = html.escape(str(proc_info.get('username', 'unknown')))
                        processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            metrics['top_processes'] = processes[:10]
            
            # WireGuard status (if installed)
            metrics['wireguard'] = self.get_wireguard_status()
            
            # Service status
            metrics['services'] = self.get_service_status()
            
            # Firewall status
            metrics['firewall'] = self.get_firewall_status()
            
            # Last login information
            metrics['last_logins'] = self.get_last_logins()
            
            # Current timestamp
            metrics['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
        except Exception as e:
            metrics['error'] = str(e)
        
        return metrics
    
    def get_os_info(self):
        """Get OS information"""
        try:
            with open('/etc/os-release', 'r') as f:
                lines = f.readlines()
                for line in lines:
                    if line.startswith('PRETTY_NAME='):
                        return line.split('=')[1].strip().strip('"')
        except Exception:
            return 'Unknown'
        return 'Oracle Linux'
    
    def get_wireguard_status(self):
        """Get WireGuard VPN status"""
        wg_status = {'installed': False, 'running': False, 'peers': []}
        
        try:
            # Check if WireGuard is installed
            result = subprocess.run(['which', 'wg'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                wg_status['installed'] = True
                
                # Check if service is running
                result = subprocess.run(['systemctl', 'is-active', 'wg-quick@wg0'], 
                                      capture_output=True, text=True, timeout=5)
                wg_status['running'] = result.stdout.strip() == 'active'
                
                if wg_status['running']:
                    # Get peer information
                    result = subprocess.run(['wg', 'show', 'wg0'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        output = result.stdout
                        peers = []
                        current_peer = None
                        
                        for line in output.split('\n'):
                            line = line.strip()
                            if line.startswith('peer:'):
                                if current_peer:
                                    peers.append(current_peer)
                                parts = line.split(':', 1)
                                if len(parts) >= 2:
                                    current_peer = {'public_key': parts[1].strip()[:16] + '...'}
                            elif current_peer:
                                if line.startswith('endpoint:'):
                                    parts = line.split(':', 1)
                                    if len(parts) >= 2:
                                        endpoint = parts[1].strip()
                                        # Hide full IP, show only last octet
                                        if '.' in endpoint:
                                            ip_parts = endpoint.split('.')
                                            if len(ip_parts) >= 4:
                                                current_peer['endpoint'] = 'xxx.xxx.xxx.' + ip_parts[-1]
                                elif line.startswith('latest handshake:'):
                                    parts = line.split(':', 1)
                                    if len(parts) >= 2:
                                        current_peer['handshake'] = parts[1].strip()
                                elif line.startswith('transfer:'):
                                    parts = line.split(':', 1)
                                    if len(parts) >= 2:
                                        current_peer['transfer'] = parts[1].strip()
                        
                        if current_peer:
                            peers.append(current_peer)
                        
                        wg_status['peers'] = peers
                        wg_status['peer_count'] = len(peers)
        except Exception:
            pass
        
        return wg_status
    
    def get_service_status(self):
        """Get status of important services"""
        services = ['sshd', 'firewalld', 'wg-quick@wg0']
        status = {}
        
        for service in services:
            try:
                result = subprocess.run(['systemctl', 'is-active', service],
                                      capture_output=True, text=True, timeout=5)
                status[service] = result.stdout.strip()
            except Exception:
                status[service] = 'unknown'
        
        return status
    
    def get_firewall_status(self):
        """Get firewall information"""
        fw_status = {'active': False, 'rules': []}
        
        try:
            result = subprocess.run(['systemctl', 'is-active', 'firewalld'],
                                  capture_output=True, text=True, timeout=5)
            fw_status['active'] = result.stdout.strip() == 'active'
            
            if fw_status['active']:
                result = subprocess.run(['firewall-cmd', '--list-ports'],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    ports = result.stdout.strip().split()
                    fw_status['open_ports'] = ports
        except Exception:
            pass
        
        return fw_status
    
    def get_last_logins(self):
        """Get last login information"""
        logins = []
        try:
            result = subprocess.run(['last', '-n', '10', '-w'],
                                  capture_output=True, text=True, timeout=5)
            lines = result.stdout.strip().split('\n')
            for line in lines[:5]:  # Only show last 5
                if line and not line.startswith('wtmp') and not line.startswith('reboot'):
                    parts = line.split()
                    if len(parts) >= 4:
                        # Mask IP addresses for security
                        login_info = {
                            'user': html.escape(parts[0]),
                            'terminal': html.escape(parts[1]),
                            'date': html.escape(' '.join(parts[3:7]) if len(parts) >= 7 else 'Unknown')
                        }
                        logins.append(login_info)
        except Exception:
            pass
        
        return logins
    
    def format_bytes(self, bytes_value):
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"
    
    def format_uptime(self, seconds):
        """Format uptime to human readable format"""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{days}d {hours}h {minutes}m"
    
    def get_dashboard_html(self):
        """Generate the monitoring dashboard HTML"""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oracle Instance Monitor</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #333;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            color: #1e3c72;
            font-size: 28px;
            margin-bottom: 8px;
        }
        
        .header .subtitle {
            color: #666;
            font-size: 14px;
        }
        
        .last-update {
            float: right;
            color: #999;
            font-size: 13px;
            margin-top: 5px;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }
        
        .card h2 {
            color: #1e3c72;
            font-size: 18px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e5e7eb;
        }
        
        .metric-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #f3f4f6;
        }
        
        .metric-row:last-child {
            border-bottom: none;
        }
        
        .metric-label {
            color: #666;
            font-size: 14px;
            font-weight: 500;
        }
        
        .metric-value {
            color: #333;
            font-size: 14px;
            font-weight: 600;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e5e7eb;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 5px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #10b981 0%, #059669 100%);
            border-radius: 10px;
            transition: width 0.5s ease;
        }
        
        .progress-fill.warning {
            background: linear-gradient(90deg, #f59e0b 0%, #d97706 100%);
        }
        
        .progress-fill.danger {
            background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%);
        }
        
        .cpu-cores {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }
        
        .cpu-core {
            background: #f9fafb;
            padding: 10px;
            border-radius: 6px;
            text-align: center;
        }
        
        .cpu-core-label {
            font-size: 11px;
            color: #666;
            margin-bottom: 5px;
        }
        
        .cpu-core-value {
            font-size: 16px;
            font-weight: 700;
            color: #333;
        }
        
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        
        .status-active {
            background: #d1fae5;
            color: #065f46;
        }
        
        .status-inactive {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .status-unknown {
            background: #e5e7eb;
            color: #374151;
        }
        
        .process-table {
            width: 100%;
            font-size: 13px;
            margin-top: 10px;
        }
        
        .process-table th {
            text-align: left;
            padding: 8px 4px;
            color: #666;
            font-weight: 600;
            border-bottom: 2px solid #e5e7eb;
        }
        
        .process-table td {
            padding: 8px 4px;
            border-bottom: 1px solid #f3f4f6;
        }
        
        .process-table tr:last-child td {
            border-bottom: none;
        }
        
        .disk-item {
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid #f3f4f6;
        }
        
        .disk-item:last-child {
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }
        
        .disk-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
        }
        
        .disk-path {
            font-weight: 600;
            color: #333;
        }
        
        .disk-percent {
            color: #666;
            font-size: 14px;
        }
        
        .disk-info {
            font-size: 12px;
            color: #999;
            margin-top: 3px;
        }
        
        .wireguard-peer {
            background: #f9fafb;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 10px;
        }
        
        .wireguard-peer:last-child {
            margin-bottom: 0;
        }
        
        .peer-key {
            font-family: monospace;
            font-size: 12px;
            color: #666;
            margin-bottom: 5px;
        }
        
        .peer-info {
            font-size: 12px;
            color: #333;
        }
        
        .login-item {
            padding: 10px;
            background: #f9fafb;
            border-radius: 6px;
            margin-bottom: 8px;
            font-size: 13px;
        }
        
        .login-item:last-child {
            margin-bottom: 0;
        }
        
        .login-user {
            font-weight: 600;
            color: #333;
        }
        
        .login-details {
            color: #666;
            font-size: 12px;
            margin-top: 3px;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #999;
        }
        
        .alert {
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 12px 15px;
            border-radius: 6px;
            margin-bottom: 15px;
            font-size: 13px;
            color: #92400e;
        }
        
        .info-box {
            background: #dbeafe;
            border-left: 4px solid #3b82f6;
            padding: 12px 15px;
            border-radius: 6px;
            margin-top: 15px;
            font-size: 13px;
            color: #1e40af;
        }
        
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }
            
            .cpu-cores {
                grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
            }
        }
        
        .refresh-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #10b981;
            border-radius: 50%;
            margin-left: 8px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Oracle Instance Monitoring Dashboard</h1>
            <div class="subtitle">
                Real-time system metrics and performance monitoring
                <span class="refresh-indicator"></span>
            </div>
            <div class="last-update" id="last-update">Loading...</div>
        </div>
        
        <div id="dashboard-content" class="loading">
            Initializing monitoring system...
        </div>
    </div>
    
    <script>
        let updateInterval;
        
        function updateDashboard() {
            fetch('/api/metrics')
                .then(response => response.json())
                .then(data => {
                    renderDashboard(data);
                    document.getElementById('last-update').textContent = 'Last updated: ' + data.timestamp;
                })
                .catch(error => {
                    console.error('Error fetching metrics:', error);
                    document.getElementById('dashboard-content').innerHTML = 
                        '<div class="alert">Connection error. Retrying...</div>';
                });
        }
        
        function getProgressClass(percent) {
            if (percent >= 90) return 'danger';
            if (percent >= 75) return 'warning';
            return '';
        }
        
        function renderDashboard(data) {
            const content = document.getElementById('dashboard-content');
            
            // Check if data has an error or missing system info
            if (data.error || !data.system) {
                content.innerHTML = `<div class="alert">Error loading system metrics: ${data.error || 'Missing system data'}</div>`;
                return;
            }
            
            let html = '<div class="grid">';
            
            // System Information Card
            html += `
                <div class="card">
                    <h2>System Information</h2>
                    <div class="metric-row">
                        <span class="metric-label">Hostname</span>
                        <span class="metric-value">${data.system.hostname}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Operating System</span>
                        <span class="metric-value">${data.system.platform}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Kernel Version</span>
                        <span class="metric-value">${data.system.kernel}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Architecture</span>
                        <span class="metric-value">${data.system.architecture}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Uptime</span>
                        <span class="metric-value">${data.uptime}</span>
                    </div>
                </div>
            `;
            
            // CPU Card
            html += `
                <div class="card">
                    <h2>CPU Usage</h2>
                    <div class="metric-row">
                        <span class="metric-label">Overall CPU Usage</span>
                        <span class="metric-value">${data.cpu.overall.toFixed(1)}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill ${getProgressClass(data.cpu.overall)}" 
                             style="width: ${data.cpu.overall}%"></div>
                    </div>
                    
                    <div class="metric-row" style="margin-top: 15px;">
                        <span class="metric-label">Load Average (1m, 5m, 15m)</span>
                        <span class="metric-value">${data.cpu.load_avg[0].toFixed(2)}, ${data.cpu.load_avg[1].toFixed(2)}, ${data.cpu.load_avg[2].toFixed(2)}</span>
                    </div>
                    
                    <div style="margin-top: 15px;">
                        <div class="metric-label" style="margin-bottom: 10px;">Per-Core Usage</div>
                        <div class="cpu-cores">
                            ${data.cpu.per_core.map((cpu, index) => `
                                <div class="cpu-core">
                                    <div class="cpu-core-label">Core ${index}</div>
                                    <div class="cpu-core-value">${cpu.toFixed(0)}%</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            `;
            
            // Memory Card
            html += `
                <div class="card">
                    <h2>Memory Usage</h2>
                    <div class="metric-row">
                        <span class="metric-label">RAM Usage</span>
                        <span class="metric-value">${data.memory.used} / ${data.memory.total}</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill ${getProgressClass(data.memory.percent)}" 
                             style="width: ${data.memory.percent}%"></div>
                    </div>
                    <div class="metric-row" style="margin-top: 5px;">
                        <span class="metric-label">Available</span>
                        <span class="metric-value">${data.memory.free} (${(100 - data.memory.percent).toFixed(1)}%)</span>
                    </div>
                    
                    <div class="metric-row" style="margin-top: 15px;">
                        <span class="metric-label">Swap Usage</span>
                        <span class="metric-value">${data.memory.swap_used} / ${data.memory.swap_total}</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill ${getProgressClass(data.memory.swap_percent)}" 
                             style="width: ${data.memory.swap_percent}%"></div>
                    </div>
                </div>
            `;
            
            html += '</div>'; // Close first grid
            
            // Disk Usage Card (full width)
            html += `
                <div class="card" style="margin-bottom: 20px;">
                    <h2>Disk Usage</h2>
                    ${data.disk.map(disk => `
                        <div class="disk-item">
                            <div class="disk-header">
                                <span class="disk-path">${disk.mountpoint}</span>
                                <span class="disk-percent">${disk.percent.toFixed(1)}%</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill ${getProgressClass(disk.percent)}" 
                                     style="width: ${disk.percent}%"></div>
                            </div>
                            <div class="disk-info">
                                ${disk.used} used of ${disk.total} (${disk.free} free) - ${disk.device} (${disk.fstype})
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
            
            html += '<div class="grid">';
            
            // Network Card
            html += `
                <div class="card">
                    <h2>Network Statistics</h2>
                    <div class="metric-row">
                        <span class="metric-label">Data Sent</span>
                        <span class="metric-value">${data.network.bytes_sent}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Data Received</span>
                        <span class="metric-value">${data.network.bytes_recv}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Packets Sent</span>
                        <span class="metric-value">${data.network.packets_sent.toLocaleString()}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Packets Received</span>
                        <span class="metric-value">${data.network.packets_recv.toLocaleString()}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Errors (In / Out)</span>
                        <span class="metric-value">${data.network.errors_in} / ${data.network.errors_out}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Drops (In / Out)</span>
                        <span class="metric-value">${data.network.drops_in} / ${data.network.drops_out}</span>
                    </div>
                </div>
            `;
            
            // Disk I/O Card
            if (data.disk_io) {
                html += `
                    <div class="card">
                        <h2>Disk I/O Statistics</h2>
                        <div class="metric-row">
                            <span class="metric-label">Total Read</span>
                            <span class="metric-value">${data.disk_io.read_bytes}</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Total Written</span>
                            <span class="metric-value">${data.disk_io.write_bytes}</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Read Operations</span>
                            <span class="metric-value">${data.disk_io.read_count.toLocaleString()}</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Write Operations</span>
                            <span class="metric-value">${data.disk_io.write_count.toLocaleString()}</span>
                        </div>
                    </div>
                `;
            }
            
            // Network Connections Card
            html += `
                <div class="card">
                    <h2>Network Connections</h2>
                    <div class="metric-row">
                        <span class="metric-label">Established</span>
                        <span class="metric-value">${data.connections.established}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Listening</span>
                        <span class="metric-value">${data.connections.listen}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Time Wait</span>
                        <span class="metric-value">${data.connections.time_wait}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Total Connections</span>
                        <span class="metric-value">${data.connections.total}</span>
                    </div>
                </div>
            `;
            
            html += '</div>'; // Close second grid
            
            // Services Status Card
            html += `
                <div class="card" style="margin-bottom: 20px;">
                    <h2>Service Status</h2>
                    <div class="grid" style="gap: 15px;">
                        ${Object.entries(data.services).map(([service, status]) => `
                            <div class="metric-row">
                                <span class="metric-label">${service}</span>
                                <span class="status-badge status-${status === 'active' ? 'active' : status === 'inactive' ? 'inactive' : 'unknown'}">${status}</span>
                            </div>
                        `).join('')}
                    </div>
                    
                    ${data.firewall.active ? `
                        <div class="info-box">
                            Firewall is active. Open ports: ${data.firewall.open_ports ? data.firewall.open_ports.join(', ') : 'None'}
                        </div>
                    ` : ''}
                </div>
            `;
            
            // WireGuard Status (if installed)
            if (data.wireguard.installed) {
                html += `
                    <div class="card" style="margin-bottom: 20px;">
                        <h2>WireGuard VPN Status</h2>
                        <div class="metric-row">
                            <span class="metric-label">Service Status</span>
                            <span class="status-badge status-${data.wireguard.running ? 'active' : 'inactive'}">
                                ${data.wireguard.running ? 'Running' : 'Stopped'}
                            </span>
                        </div>
                        
                        ${data.wireguard.running && data.wireguard.peers ? `
                            <div class="metric-row">
                                <span class="metric-label">Connected Peers</span>
                                <span class="metric-value">${data.wireguard.peer_count || 0}</span>
                            </div>
                            
                            ${data.wireguard.peers.length > 0 ? `
                                <div style="margin-top: 15px;">
                                    <div class="metric-label" style="margin-bottom: 10px;">Active Connections</div>
                                    ${data.wireguard.peers.map(peer => `
                                        <div class="wireguard-peer">
                                            <div class="peer-key">Key: ${peer.public_key}</div>
                                            <div class="peer-info">
                                                Endpoint: ${peer.endpoint || 'Unknown'}<br>
                                                Last handshake: ${peer.handshake || 'Never'}<br>
                                                Transfer: ${peer.transfer || 'No data'}
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            ` : '<div class="info-box">No active peer connections</div>'}
                        ` : ''}
                    </div>
                `;
            }
            
            // Top Processes Card
            html += `
                <div class="card" style="margin-bottom: 20px;">
                    <h2>Top Processes by CPU Usage</h2>
                    <table class="process-table">
                        <thead>
                            <tr>
                                <th>PID</th>
                                <th>Process Name</th>
                                <th>User</th>
                                <th>CPU %</th>
                                <th>Memory %</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.top_processes.slice(0, 10).map(proc => `
                                <tr>
                                    <td>${proc.pid}</td>
                                    <td>${proc.name}</td>
                                    <td>${proc.username}</td>
                                    <td>${proc.cpu_percent.toFixed(1)}%</td>
                                    <td>${proc.memory_percent.toFixed(1)}%</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
            
            // Last Logins Card
            if (data.last_logins && data.last_logins.length > 0) {
                html += `
                    <div class="card" style="margin-bottom: 20px;">
                        <h2>Recent Login Activity</h2>
                        ${data.last_logins.map(login => `
                            <div class="login-item">
                                <div class="login-user">${login.user} via ${login.terminal}</div>
                                <div class="login-details">${login.date}</div>
                            </div>
                        `).join('')}
                    </div>
                `;
            }
            
            content.innerHTML = html;
        }
        
        // Initial update
        updateDashboard();
        
        // Update every 3 seconds
        updateInterval = setInterval(updateDashboard, 3000);
    </script>
</body>
</html>'''

def run_server(port=80):
    try:
        server = HTTPServer(('0.0.0.0', port), MonitorHandler)
        print(f'Oracle Instance Monitoring Dashboard running on port {port}')
        print(f'Access at: http://<your-instance-ip>')
        print('Dashboard will auto-refresh every 3 seconds')
        print('Press Ctrl+C to stop')
        server.serve_forever()
    except PermissionError:
        print('ERROR: Port 80 requires root privileges')
        print('Please run with: sudo python3 monitor-dashboard.py')
    except Exception as e:
        print(f'ERROR: {e}')

if __name__ == '__main__':
    run_server()
