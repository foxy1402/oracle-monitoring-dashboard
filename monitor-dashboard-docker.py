#!/usr/bin/env python3
"""
Oracle Instance Monitoring Dashboard — Docker / GHCR Edition
Designed for containerised deployment with:
  pid: host        → /proc covers ALL host PIDs and /proc/1/net/* is host-scoped
  /:/rootfs:ro     → real disk usage via /rootfs + /proc/1/mounts
  cap_add: SYS_PTRACE → full psutil process inspection

Key differences from the bare-metal install version:
  • Network stats read from /proc/1/net/dev  (host NIC, not container veth)
  • Real-time RX/TX bandwidth via class-level snapshot cache
  • Service detection from /proc/1/net/{tcp,tcp6,udp} — no systemd needed
  • Top-processes table always populated (no cpu_percent > 0 gate)
  • WireGuard detected via wg* interfaces in /proc/1/net/dev
"""

import html
import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

import psutil

# ─── Threading HTTP Server ────────────────────────────────────────────────────


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# ─── Port → friendly service name ────────────────────────────────────────────

PORT_TO_SERVICE: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    67: "DHCP",
    80: "HTTP",
    110: "POP3",
    111: "RPC/portmap",
    123: "NTP",
    143: "IMAP",
    179: "BGP",
    389: "LDAP",
    443: "HTTPS",
    465: "SMTPS",
    500: "IKE/IPSec",
    514: "Syslog",
    587: "SMTP Submission",
    636: "LDAPS",
    993: "IMAPS",
    995: "POP3S",
    1194: "OpenVPN",
    1433: "MSSQL",
    1521: "Oracle DB",
    2375: "Docker (plain)",
    2376: "Docker (TLS)",
    3000: "Grafana / Node",
    3306: "MySQL / MariaDB",
    4369: "RabbitMQ EPMD",
    5000: "Flask / Dev",
    5432: "PostgreSQL",
    5601: "Kibana",
    5672: "RabbitMQ AMQP",
    6379: "Redis",
    6443: "Kubernetes API",
    8080: "HTTP Alt",
    8443: "HTTPS Alt",
    8888: "Jupyter",
    9090: "Prometheus",
    9100: "Node Exporter",
    9200: "Elasticsearch HTTP",
    9300: "Elasticsearch Transport",
    15672: "RabbitMQ Management",
    27017: "MongoDB",
    51820: "WireGuard",
}


# ─── Request Handler ──────────────────────────────────────────────────────────


class MonitorHandler(BaseHTTPRequestHandler):
    timeout = 10

    # Class-level snapshot for real-time bandwidth (shared across requests)
    _prev_net_bytes: dict = {"recv": 0, "sent": 0}
    _prev_net_ts: float | None = None

    # ── Logging ───────────────────────────────────────────────────────────────

    def log_message(self, format, *args):
        pass  # suppress per-request noise

    # ── Routing ───────────────────────────────────────────────────────────────

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self.get_dashboard_html().encode())

        elif self.path == "/api/metrics":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(self.get_system_metrics()).encode())

        else:
            self.send_response(404)
            self.end_headers()

    # =========================================================================
    # Metrics orchestrator
    # =========================================================================

    def get_system_metrics(self) -> dict:
        m: dict = {}
        try:
            # ── System info ───────────────────────────────────────────────────
            m["system"] = {
                "hostname": html.escape(socket.gethostname()),
                "platform": html.escape(self.get_os_info()),
                "kernel": html.escape(os.uname().release),
                "architecture": html.escape(os.uname().machine),
            }
            m["uptime"] = self.format_uptime(time.time() - psutil.boot_time())

            # ── CPU ───────────────────────────────────────────────────────────
            cpu_pct = psutil.cpu_percent(interval=0.1, percpu=True)
            m["cpu"] = {
                "overall": round(sum(cpu_pct) / len(cpu_pct), 1) if cpu_pct else 0,
                "per_core": [round(c, 1) for c in cpu_pct],
                "core_count": psutil.cpu_count(),
                "load_avg": [round(x, 2) for x in os.getloadavg()]
                if hasattr(os, "getloadavg")
                else [0, 0, 0],
            }

            # ── Memory ────────────────────────────────────────────────────────
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            m["memory"] = {
                "total": self.format_bytes(mem.total),
                "used": self.format_bytes(mem.used),
                "free": self.format_bytes(mem.available),
                "percent": mem.percent,
                "swap_total": self.format_bytes(swap.total),
                "swap_used": self.format_bytes(swap.used),
                "swap_percent": swap.percent,
                "zram": self.get_zram_info(),
            }

            # ── Disk ──────────────────────────────────────────────────────────
            m["disk"] = self.get_disk_metrics()
            m["disk_io"] = self._get_disk_io()

            # ── Network (host-scoped via /proc/1/net/dev) ─────────────────────
            m["network"] = self.get_network_metrics()

            # ── TCP connections ────────────────────────────────────────────────
            try:
                conns = psutil.net_connections(kind="inet")
                m["connections"] = {
                    "established": sum(1 for c in conns if c.status == "ESTABLISHED"),
                    "listen": sum(1 for c in conns if c.status == "LISTEN"),
                    "time_wait": sum(1 for c in conns if c.status == "TIME_WAIT"),
                    "total": len(conns),
                }
            except (psutil.AccessDenied, PermissionError):
                m["connections"] = {
                    "established": 0,
                    "listen": 0,
                    "time_wait": 0,
                    "total": 0,
                }

            # ── Top processes (all host PIDs via pid:host) ────────────────────
            m["top_processes"] = self.get_top_processes()

            # ── Service detection (listening-port based, no systemd) ──────────
            m["services"] = self.get_detected_services()

            # ── Firewall & WireGuard ───────────────────────────────────────────
            m["firewall"] = self.get_firewall_status()
            m["wireguard"] = self.get_wireguard_status()

            # ── Last logins ───────────────────────────────────────────────────
            m["last_logins"] = self.get_last_logins()

            m["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        except Exception as exc:
            m["error"] = str(exc)

        return m

    # =========================================================================
    # OS / host-root helpers
    # =========================================================================

    def get_os_info(self) -> str:
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass
        return "Unknown Linux"

    def get_host_root(self) -> str:
        """Return '/rootfs' when the host filesystem is bind-mounted there."""
        return "/rootfs" if os.path.isdir("/rootfs/etc") else ""

    # =========================================================================
    # Disk metrics  (identical logic to bare-metal version — already correct)
    # =========================================================================

    def get_disk_metrics(self) -> list:
        disk_usage: list = []
        host_root = self.get_host_root()

        skip_fstypes = {
            "tmpfs",
            "devtmpfs",
            "sysfs",
            "proc",
            "cgroup",
            "cgroup2",
            "devpts",
            "overlay",
            "aufs",
            "squashfs",
            "nsfs",
            "fusectl",
            "hugetlbfs",
            "mqueue",
            "pstore",
            "securityfs",
            "debugfs",
            "tracefs",
            "configfs",
            "ramfs",
            "bpf",
            "efivarfs",
        }
        skip_mounts = {"/boot/efi", "/dev", "/run", "/proc", "/sys", "/rootfs"}

        if host_root:
            try:
                with open("/proc/1/mounts") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) < 3:
                            continue
                        device, mp, fstype = parts[0], parts[1], parts[2]
                        if fstype in skip_fstypes or mp in skip_mounts:
                            continue
                        try:
                            u = psutil.disk_usage(host_root + mp)
                            disk_usage.append(
                                {
                                    "mountpoint": mp,
                                    "device": device,
                                    "fstype": fstype,
                                    "total": self.format_bytes(u.total),
                                    "used": self.format_bytes(u.used),
                                    "free": self.format_bytes(u.free),
                                    "percent": u.percent,
                                }
                            )
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
            except Exception:
                pass

        if not disk_usage:
            for p in psutil.disk_partitions():
                if p.mountpoint in skip_mounts:
                    continue
                try:
                    u = psutil.disk_usage(p.mountpoint)
                    disk_usage.append(
                        {
                            "mountpoint": p.mountpoint,
                            "device": p.device,
                            "fstype": p.fstype,
                            "total": self.format_bytes(u.total),
                            "used": self.format_bytes(u.used),
                            "free": self.format_bytes(u.free),
                            "percent": u.percent,
                        }
                    )
                except (PermissionError, OSError):
                    continue

        return disk_usage

    def _get_disk_io(self) -> dict | None:
        try:
            d = psutil.disk_io_counters()
            if d:
                return {
                    "read_bytes": self.format_bytes(d.read_bytes),
                    "write_bytes": self.format_bytes(d.write_bytes),
                    "read_count": d.read_count,
                    "write_count": d.write_count,
                }
        except Exception:
            pass
        return None

    # =========================================================================
    # ZRAM
    # =========================================================================

    def get_zram_info(self) -> list:
        zram: list = []
        try:
            with open("/proc/swaps") as f:
                for line in f.readlines()[1:]:
                    parts = line.split()
                    if parts and "zram" in parts[0].lower():
                        size_kb = int(parts[2]) if len(parts) > 2 else 0
                        used_kb = int(parts[3]) if len(parts) > 3 else 0
                        zram.append(
                            {
                                "device": parts[0],
                                "total": self.format_bytes(size_kb * 1024),
                                "used": self.format_bytes(used_kb * 1024),
                                "percent": round(used_kb / size_kb * 100, 1)
                                if size_kb
                                else 0,
                            }
                        )
        except Exception:
            pass
        return zram

    # =========================================================================
    # Network  — host-scoped via /proc/1/net/dev
    # =========================================================================

    def _read_proc_net_dev(self, path: str) -> dict:
        """
        Parse /proc/net/dev or /proc/1/net/dev.
        Returns {iface: {bytes_recv, packets_recv, errin, dropin,
                         bytes_sent, packets_sent, errout, dropout}}
        """
        ifaces: dict = {}
        try:
            with open(path) as f:
                for line in f.readlines()[2:]:  # skip the two header lines
                    if ":" not in line:
                        continue
                    iface, data = line.split(":", 1)
                    v = data.split()
                    if len(v) < 16:
                        continue
                    ifaces[iface.strip()] = {
                        "bytes_recv": int(v[0]),
                        "packets_recv": int(v[1]),
                        "errin": int(v[2]),
                        "dropin": int(v[3]),
                        "bytes_sent": int(v[8]),
                        "packets_sent": int(v[9]),
                        "errout": int(v[10]),
                        "dropout": int(v[11]),
                    }
        except Exception:
            pass
        return ifaces

    def get_network_metrics(self) -> dict:
        """
        Read host-level network counters.

        Why /proc/1/net/dev instead of psutil?
          psutil reads /proc/net/dev which is scoped to the container's own
          network namespace (just the veth pair).  With pid:host, PID 1 is the
          host init process and lives in the host network namespace, so
          /proc/1/net/dev contains the real host interface counters.

        Real-time RX/TX rate is calculated from a class-level snapshot that
        persists between the 3-second API poll intervals.
        """
        now = time.monotonic()

        # Prefer host path; fall back to container-scoped path
        iface_stats: dict = {}
        source = "container"
        for path, label in (
            ("/proc/1/net/dev", "host"),
            ("/proc/net/dev", "container"),
        ):
            s = self._read_proc_net_dev(path)
            if s:
                iface_stats, source = s, label
                break

        # Aggregate totals, skipping loopback
        agg = dict(
            recv=0,
            sent=0,
            pkts_recv=0,
            pkts_sent=0,
            errin=0,
            errout=0,
            dropin=0,
            dropout=0,
        )
        for iface, s in iface_stats.items():
            if iface == "lo":
                continue
            agg["recv"] += s["bytes_recv"]
            agg["sent"] += s["bytes_sent"]
            agg["pkts_recv"] += s["packets_recv"]
            agg["pkts_sent"] += s["packets_sent"]
            agg["errin"] += s["errin"]
            agg["errout"] += s["errout"]
            agg["dropin"] += s["dropin"]
            agg["dropout"] += s["dropout"]

        # Real-time bandwidth from class-level snapshot
        rx_rate = tx_rate = 0.0
        cls = MonitorHandler
        if cls._prev_net_ts is not None:
            dt = now - cls._prev_net_ts
            if dt >= 0.5:  # ignore sub-half-second jitter
                rx_rate = max(0.0, (agg["recv"] - cls._prev_net_bytes["recv"]) / dt)
                tx_rate = max(0.0, (agg["sent"] - cls._prev_net_bytes["sent"]) / dt)
        cls._prev_net_bytes = {"recv": agg["recv"], "sent": agg["sent"]}
        cls._prev_net_ts = now

        # Per-interface breakdown (no loopback)
        interfaces = [
            {
                "name": iface,
                "bytes_recv": self.format_bytes(s["bytes_recv"]),
                "bytes_sent": self.format_bytes(s["bytes_sent"]),
                "packets_recv": s["packets_recv"],
                "packets_sent": s["packets_sent"],
            }
            for iface, s in sorted(iface_stats.items())
            if iface != "lo"
        ]

        return {
            "bytes_recv": self.format_bytes(agg["recv"]),
            "bytes_sent": self.format_bytes(agg["sent"]),
            "packets_recv": agg["pkts_recv"],
            "packets_sent": agg["pkts_sent"],
            "errors_in": agg["errin"],
            "errors_out": agg["errout"],
            "drops_in": agg["dropin"],
            "drops_out": agg["dropout"],
            "rx_rate": self.format_bytes(rx_rate) + "/s",
            "tx_rate": self.format_bytes(tx_rate) + "/s",
            "interfaces": interfaces,
            "source": source,  # 'host' or 'container'
        }

    # =========================================================================
    # Service detection  — /proc/1/net/{tcp,tcp6,udp,udp6}
    # =========================================================================

    def get_detected_services(self) -> list:
        """
        Auto-detect running services by scanning listening sockets in the host's
        /proc/1/net/{tcp,tcp6,udp,udp6}.  This requires no systemd, no service
        manager, and works identically on any Linux distribution.

        TCP  LISTEN state  = 0A
        UDP  bound sockets = 07  (UDP has no connection state)
        """
        seen_ports: set = set()
        detected: list = []

        def parse_listening(path: str, is_udp: bool) -> list[int]:
            want = "07" if is_udp else "0a"
            ports: list[int] = []
            try:
                with open(path) as f:
                    for line in f.readlines()[1:]:
                        cols = line.split()
                        if len(cols) < 4:
                            continue
                        if cols[3].lower() != want:
                            continue
                        port_hex = cols[1].split(":")[1]
                        port = int(port_hex, 16)
                        if 0 < port < 65536:
                            ports.append(port)
            except Exception:
                pass
            return ports

        for proto, is_udp in (
            ("tcp", False),
            ("tcp6", False),
            ("udp", True),
            ("udp6", True),
        ):
            # Try host namespace first, fall back to container namespace
            for base in ("/proc/1/net", "/proc/net"):
                path = f"{base}/{proto}"
                if not os.path.exists(path):
                    continue
                for port in parse_listening(path, is_udp):
                    if port not in seen_ports:
                        seen_ports.add(port)
                        detected.append(
                            {
                                "port": port,
                                "proto": "UDP" if is_udp else "TCP",
                                "name": PORT_TO_SERVICE.get(port, f"Port {port}"),
                            }
                        )
                break  # stop after first working base path

        detected.sort(key=lambda x: x["port"])
        return detected

    # =========================================================================
    # Top processes  — all host PIDs via pid:host
    # =========================================================================

    def get_top_processes(self) -> list:
        """
        Return top-15 processes sorted by CPU%.

        Why the old version looked empty / container-only:
          1. psutil.cpu_percent() returns 0.0 on the FIRST call for every process
             (it needs two measurements to establish a baseline).
          2. The original code filtered with `if cpu_percent > 0`, so on the very
             first poll ALL processes were silently dropped.
          3. From the second poll onward psutil's internal Process cache gives real
             values — but users often refreshed before that happened.

        Fix: remove the > 0 gate entirely.  Sort by CPU%, show top 15 regardless.
        The table is always populated; active processes rise to the top on each
        subsequent 3-second refresh.

        With pid:host the container's /proc IS the host's /proc, so all host
        processes are visible.  cmdline is fetched for better identification.
        """
        procs: list = []
        for p in psutil.process_iter(
            [
                "pid",
                "name",
                "cpu_percent",
                "memory_percent",
                "username",
                "cmdline",
                "status",
            ]
        ):
            try:
                inf = p.info
                cmdline = inf.get("cmdline") or []
                # Build short command string; fall back to process name
                cmd = " ".join(cmdline[:5]).strip() if cmdline else ""
                if not cmd:
                    cmd = inf.get("name", "?")
                if len(cmd) > 80:
                    cmd = cmd[:77] + "..."

                procs.append(
                    {
                        "pid": inf["pid"],
                        "name": html.escape(str(inf.get("name", "?"))),
                        "cmd": html.escape(cmd),
                        "cpu_percent": round(inf.get("cpu_percent") or 0.0, 1),
                        "memory_percent": round(inf.get("memory_percent") or 0.0, 2),
                        "username": html.escape(str(inf.get("username", "?"))),
                        "status": html.escape(str(inf.get("status", "?"))),
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
        return procs[:15]

    # =========================================================================
    # WireGuard  — interface-based detection, no wg binary required
    # =========================================================================

    def get_wireguard_status(self) -> dict:
        """
        Detect WireGuard by looking for wg* interfaces in /proc/1/net/dev.
        Optionally enriches with `wg show` peer data if the binary is on PATH.
        """
        result: dict = {"installed": False, "running": False, "peers": []}

        for path in ("/proc/1/net/dev", "/proc/net/dev"):
            ifaces = self._read_proc_net_dev(path)
            wg_ifaces = [i for i in ifaces if i.startswith("wg")]
            if wg_ifaces:
                result.update(
                    {"installed": True, "running": True, "interfaces": wg_ifaces}
                )
                break

        if result["running"]:
            try:
                out = subprocess.run(
                    ["wg", "show"], capture_output=True, text=True, timeout=5
                )
                if out.returncode == 0:
                    peers: list = []
                    cur: dict | None = None
                    for line in out.stdout.splitlines():
                        line = line.strip()
                        if line.startswith("peer:"):
                            if cur:
                                peers.append(cur)
                            cur = {
                                "public_key": line.split(":", 1)[1].strip()[:16] + "..."
                            }
                        elif cur:
                            if line.startswith("endpoint:"):
                                ep = line.split(":", 1)[1].strip()
                                if "." in ep:
                                    cur["endpoint"] = "x.x.x." + ep.rsplit(".", 1)[-1]
                            elif line.startswith("latest handshake:"):
                                cur["handshake"] = line.split(":", 1)[1].strip()
                            elif line.startswith("transfer:"):
                                cur["transfer"] = line.split(":", 1)[1].strip()
                    if cur:
                        peers.append(cur)
                    result["peers"] = peers
                    result["peer_count"] = len(peers)
            except Exception:
                pass

        return result

    # =========================================================================
    # Firewall  (best-effort; systemctl may not be present in all containers)
    # =========================================================================

    def get_firewall_status(self) -> dict:
        fw: dict = {"active": False, "rules": [], "type": "none"}
        try:
            r = subprocess.run(
                ["systemctl", "is-active", "firewalld"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r.stdout.strip() == "active":
                fw.update({"active": True, "type": "firewalld"})
                return fw
            r2 = subprocess.run(
                ["systemctl", "is-active", "ufw"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r2.stdout.strip() == "active":
                fw.update({"active": True, "type": "ufw"})
        except Exception:
            pass
        return fw

    # =========================================================================
    # Last logins
    # =========================================================================

    def get_last_logins(self) -> list:
        logins: list = []
        try:
            r = subprocess.run(
                ["last", "-n", "10", "-w"], capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.strip().splitlines()[:5]:
                if not line or line.startswith(("wtmp", "reboot")):
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    logins.append(
                        {
                            "user": html.escape(parts[0]),
                            "terminal": html.escape(parts[1]),
                            "date": html.escape(
                                " ".join(parts[3:7]) if len(parts) >= 7 else "Unknown"
                            ),
                        }
                    )
        except Exception:
            pass
        return logins

    # =========================================================================
    # Formatting helpers
    # =========================================================================

    def format_bytes(self, b: float) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if b < 1024.0:
                return f"{b:.2f} {unit}"
            b /= 1024.0
        return f"{b:.2f} PB"

    def format_uptime(self, seconds: float) -> str:
        d = int(seconds // 86400)
        h = int((seconds % 86400) // 3600)
        mn = int((seconds % 3600) // 60)
        return f"{d}d {h}h {mn}m"

    # =========================================================================
    # Dashboard HTML  (CSS + JS)
    # =========================================================================

    def get_dashboard_html(self) -> str:
        return r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Linux Instance Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #333;
            padding: 20px;
            min-height: 100vh;
        }

        .container { max-width: 1600px; margin: 0 auto; }

        .header {
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 5px 20px rgba(0,0,0,.1);
        }
        .header h1 { color: #1e3c72; font-size: 28px; margin-bottom: 8px; }
        .header .subtitle { color: #666; font-size: 14px; }
        .last-update { float: right; color: #999; font-size: 13px; margin-top: 5px; }

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
            box-shadow: 0 5px 20px rgba(0,0,0,.1);
        }
        .card h2 {
            color: #1e3c72;
            font-size: 18px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e5e7eb;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .badge-host      { background:#d1fae5; color:#065f46; font-size:11px; font-weight:600; padding:2px 8px; border-radius:10px; }
        .badge-container { background:#fef3c7; color:#92400e; font-size:11px; font-weight:600; padding:2px 8px; border-radius:10px; }

        .metric-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #f3f4f6;
        }
        .metric-row:last-child { border-bottom: none; }
        .metric-label { color: #666; font-size: 14px; font-weight: 500; }
        .metric-value { color: #333; font-size: 14px; font-weight: 600; }
        .metric-value.green { color: #059669; }
        .metric-value.blue  { color: #2563eb; }

        .section-label {
            font-size: 12px;
            font-weight: 600;
            color: #888;
            text-transform: uppercase;
            letter-spacing: .5px;
            margin: 14px 0 6px;
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
            background: linear-gradient(90deg,#10b981,#059669);
            border-radius: 10px;
            transition: width .5s ease;
        }
        .progress-fill.warning { background: linear-gradient(90deg,#f59e0b,#d97706); }
        .progress-fill.danger  { background: linear-gradient(90deg,#ef4444,#dc2626); }

        .cpu-cores {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }
        .cpu-core { background:#f9fafb; padding:10px; border-radius:6px; text-align:center; }
        .cpu-core-label { font-size:11px; color:#666; margin-bottom:5px; }
        .cpu-core-value { font-size:16px; font-weight:700; color:#333; }

        /* ── Service detection table ── */
        .svc-table {
            width: 100%;
            font-size: 13px;
            border-collapse: collapse;
            margin-top: 6px;
        }
        .svc-table th {
            text-align: left;
            padding: 7px 8px;
            color: #666;
            font-weight: 600;
            border-bottom: 2px solid #e5e7eb;
            font-size: 12px;
        }
        .svc-table td {
            padding: 7px 8px;
            border-bottom: 1px solid #f3f4f6;
            vertical-align: middle;
        }
        .svc-table tr:last-child td { border-bottom: none; }
        .svc-table .port-cell { font-family: monospace; font-weight: 700; color: #1e3c72; }
        .proto-badge {
            display: inline-block;
            padding: 2px 7px;
            border-radius: 8px;
            font-size: 11px;
            font-weight: 700;
        }
        .proto-tcp  { background:#dbeafe; color:#1d4ed8; }
        .proto-udp  { background:#fce7f3; color:#9d174d; }

        /* ── Process table ── */
        .process-table {
            width: 100%;
            font-size: 13px;
            margin-top: 10px;
            table-layout: fixed;
            border-collapse: collapse;
        }
        .process-table th {
            text-align: left;
            padding: 8px 6px;
            color: #666;
            font-weight: 600;
            border-bottom: 2px solid #e5e7eb;
            overflow: hidden;
        }
        .process-table td {
            padding: 8px 6px;
            border-bottom: 1px solid #f3f4f6;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .process-table tr:last-child td { border-bottom: none; }
        .process-table col.col-pid  { width: 7%; }
        .process-table col.col-cmd  { width: 42%; }
        .process-table col.col-user { width: 22%; }
        .process-table col.col-cpu  { width: 15%; }
        .process-table col.col-mem  { width: 14%; }
        .process-table th.align-right,
        .process-table td.align-right { text-align: right; }
        .process-table .proc-name { font-weight: 600; color: #1e3c72; }
        .process-table .proc-cmdline { font-size: 11px; color: #888; overflow: hidden; text-overflow: ellipsis; }

        /* ── Disk ── */
        .disk-item { margin-bottom:15px; padding-bottom:15px; border-bottom:1px solid #f3f4f6; }
        .disk-item:last-child { border-bottom:none; margin-bottom:0; padding-bottom:0; }
        .disk-header { display:flex; justify-content:space-between; margin-bottom:5px; }
        .disk-path   { font-weight:600; color:#333; }
        .disk-percent { color:#666; font-size:14px; }
        .disk-info   { font-size:12px; color:#999; margin-top:3px; }

        /* ── Interface rows ── */
        .iface-row { display:flex; justify-content:space-between; font-size:12px; padding:4px 0; }
        .iface-name { font-family:monospace; font-weight:600; color:#1e3c72; min-width:60px; }
        .iface-stat { color:#555; }

        /* ── Interface groups ── */
        .iface-group { margin-bottom:8px; }
        .iface-group-label { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:#888; padding:4px 0 2px; }
        .iface-group details { margin:0; }
        .iface-group summary { font-size:12px; font-weight:600; color:#1e3c72; cursor:pointer; padding:6px 8px; background:#f0f4f8; border-radius:4px; list-style:none; display:flex; align-items:center; gap:6px; }
        .iface-group summary::-webkit-details-marker { display:none; }
        .iface-group summary::before { content:'▶'; font-size:9px; transition:transform 0.15s; }
        .iface-group details[open] summary::before { transform:rotate(90deg); }
        .iface-group summary .iface-summary-stats { margin-left:auto; font-weight:400; color:#555; font-size:11px; }
        .iface-group .iface-group-body { padding:4px 0 0 8px; }

        /* ── WireGuard ── */
        .wireguard-peer { background:#f9fafb; padding:12px; border-radius:6px; margin-bottom:10px; }
        .wireguard-peer:last-child { margin-bottom:0; }
        .peer-key  { font-family:monospace; font-size:12px; color:#666; margin-bottom:5px; }
        .peer-info { font-size:12px; color:#333; }

        /* ── Login items ── */
        .login-item { padding:10px; background:#f9fafb; border-radius:6px; margin-bottom:8px; font-size:13px; }
        .login-item:last-child { margin-bottom:0; }
        .login-user    { font-weight:600; color:#333; }
        .login-details { color:#666; font-size:12px; margin-top:3px; }

        /* ── Misc ── */
        .loading { text-align:center; padding:40px; color:#999; }
        .alert   { background:#fef3c7; border-left:4px solid #f59e0b; padding:12px 15px; border-radius:6px; margin-bottom:15px; font-size:13px; color:#92400e; }
        .info-box { background:#dbeafe; border-left:4px solid #3b82f6; padding:12px 15px; border-radius:6px; margin-top:15px; font-size:13px; color:#1e40af; }
        .subtitle-note { font-size:12px; color:#999; margin-bottom:10px; }

        .refresh-indicator { display:inline-block; width:8px; height:8px; background:#10b981; border-radius:50%; margin-left:8px; animation:pulse 2s infinite; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

        @media (max-width:768px) {
            .grid { grid-template-columns:1fr; }
            .cpu-cores { grid-template-columns:repeat(auto-fill,minmax(60px,1fr)); }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Linux Instance Monitoring Dashboard</h1>
        <div class="subtitle">
            Real-time system metrics and performance monitoring
            <span class="refresh-indicator"></span>
        </div>
        <div class="last-update" id="last-update">Loading…</div>
    </div>

    <div id="dashboard-content" class="loading">Initialising monitoring system…</div>
</div>

<script>
    function pct(p) {
        if (p >= 90) return 'danger';
        if (p >= 75) return 'warning';
        return '';
    }

    function renderDashboard(d) {
        const content = document.getElementById('dashboard-content');
        if (d.error || !d.system) {
            content.innerHTML = `<div class="alert">Error: ${d.error || 'Missing system data'}</div>`;
            return;
        }

        let h = '<div class="grid">';

        // ── System Info ──────────────────────────────────────────────────────
        h += `
        <div class="card">
            <h2>System Information</h2>
            <div class="metric-row"><span class="metric-label">Hostname</span><span class="metric-value">${d.system.hostname}</span></div>
            <div class="metric-row"><span class="metric-label">Operating System</span><span class="metric-value">${d.system.platform}</span></div>
            <div class="metric-row"><span class="metric-label">Kernel Version</span><span class="metric-value">${d.system.kernel}</span></div>
            <div class="metric-row"><span class="metric-label">Architecture</span><span class="metric-value">${d.system.architecture}</span></div>
            <div class="metric-row"><span class="metric-label">Uptime</span><span class="metric-value">${d.uptime}</span></div>
        </div>`;

        // ── CPU ──────────────────────────────────────────────────────────────
        h += `
        <div class="card">
            <h2>CPU Usage</h2>
            <div class="metric-row">
                <span class="metric-label">Overall CPU Usage</span>
                <span class="metric-value">${d.cpu.overall.toFixed(1)}%</span>
            </div>
            <div class="progress-bar"><div class="progress-fill ${pct(d.cpu.overall)}" style="width:${d.cpu.overall}%"></div></div>
            <div class="metric-row" style="margin-top:15px;">
                <span class="metric-label">Load Average (1m / 5m / 15m)</span>
                <span class="metric-value">${d.cpu.load_avg[0].toFixed(2)}, ${d.cpu.load_avg[1].toFixed(2)}, ${d.cpu.load_avg[2].toFixed(2)}</span>
            </div>
            <div style="margin-top:15px;">
                <div class="metric-label" style="margin-bottom:10px;">Per-Core Usage</div>
                <div class="cpu-cores">
                    ${d.cpu.per_core.map((c,i) => `
                    <div class="cpu-core">
                        <div class="cpu-core-label">Core ${i}</div>
                        <div class="cpu-core-value">${c.toFixed(0)}%</div>
                    </div>`).join('')}
                </div>
            </div>
        </div>`;

        // ── Memory ───────────────────────────────────────────────────────────
        h += `
        <div class="card">
            <h2>Memory Usage</h2>
            <div class="metric-row"><span class="metric-label">RAM Usage</span><span class="metric-value">${d.memory.used} / ${d.memory.total}</span></div>
            <div class="progress-bar"><div class="progress-fill ${pct(d.memory.percent)}" style="width:${d.memory.percent}%"></div></div>
            <div class="metric-row" style="margin-top:5px;">
                <span class="metric-label">Available</span>
                <span class="metric-value">${d.memory.free} (${(100-d.memory.percent).toFixed(1)}%)</span>
            </div>
            <div class="metric-row" style="margin-top:15px;"><span class="metric-label">Swap Usage</span><span class="metric-value">${d.memory.swap_used} / ${d.memory.swap_total}</span></div>
            <div class="progress-bar"><div class="progress-fill ${pct(d.memory.swap_percent)}" style="width:${d.memory.swap_percent}%"></div></div>
            ${d.memory.zram && d.memory.zram.length > 0 ? d.memory.zram.map(z => `
            <div style="margin-top:15px;">
                <div class="metric-row">
                    <span class="metric-label">ZRAM <span style="font-size:11px;color:#888;">${z.device}</span></span>
                    <span class="metric-value">${z.used} / ${z.total}</span>
                </div>
                <div class="progress-bar"><div class="progress-fill ${pct(z.percent)}" style="width:${z.percent}%"></div></div>
                <div class="metric-row" style="margin-top:5px;">
                    <span class="metric-label">Compressed swap in RAM</span>
                    <span class="metric-value">${z.percent}%</span>
                </div>
            </div>`).join('') : ''}
        </div>`;

        h += '</div>'; // close first grid

        // ── Disk Usage (full width) ───────────────────────────────────────────
        h += `
        <div class="card" style="margin-bottom:20px;">
            <h2>Disk Usage</h2>
            ${d.disk.map(dk => `
            <div class="disk-item">
                <div class="disk-header">
                    <span class="disk-path">${dk.mountpoint}</span>
                    <span class="disk-percent">${dk.percent.toFixed(1)}%</span>
                </div>
                <div class="progress-bar"><div class="progress-fill ${pct(dk.percent)}" style="width:${dk.percent}%"></div></div>
                <div class="disk-info">${dk.used} used of ${dk.total} (${dk.free} free) — ${dk.device} (${dk.fstype})</div>
            </div>`).join('')}
        </div>`;

        h += '<div class="grid">';

        // ── Network Statistics ────────────────────────────────────────────────
        const srcBadge = d.network.source === 'host'
            ? '<span class="badge-host">host</span>'
            : '<span class="badge-container">container</span>';
        h += `
        <div class="card">
            <h2>Network Statistics ${srcBadge}</h2>

            <div class="section-label">Live Throughput</div>
            <div class="metric-row">
                <span class="metric-label">&#8595; Download (RX)</span>
                <span class="metric-value green">${d.network.rx_rate}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">&#8593; Upload (TX)</span>
                <span class="metric-value blue">${d.network.tx_rate}</span>
            </div>

            <div class="section-label">Cumulative (since boot)</div>
            <div class="metric-row"><span class="metric-label">Total Received</span><span class="metric-value">${d.network.bytes_recv}</span></div>
            <div class="metric-row"><span class="metric-label">Total Sent</span><span class="metric-value">${d.network.bytes_sent}</span></div>
            <div class="metric-row"><span class="metric-label">Packets Received</span><span class="metric-value">${d.network.packets_recv.toLocaleString()}</span></div>
            <div class="metric-row"><span class="metric-label">Packets Sent</span><span class="metric-value">${d.network.packets_sent.toLocaleString()}</span></div>
            <div class="metric-row"><span class="metric-label">Errors (In / Out)</span><span class="metric-value">${d.network.errors_in} / ${d.network.errors_out}</span></div>
            <div class="metric-row"><span class="metric-label">Drops (In / Out)</span><span class="metric-value">${d.network.drops_in} / ${d.network.drops_out}</span></div>

            ${d.network.interfaces.length > 0 ? `
            <div class="section-label">Per Interface</div>
            ${(() => {
                const dockerRe = /^(docker|br-|veth)/;
                const sys = [], dkr = [];
                d.network.interfaces.forEach(i => (dockerRe.test(i.name) ? dkr : sys).push(i));
                const row = i => '<div class="iface-row"><span class="iface-name">' + i.name + '</span><span class="iface-stat">&#8595; ' + i.bytes_recv + ' &nbsp; &#8593; ' + i.bytes_sent + '</span></div>';
                let out = '<div class="iface-group">';
                sys.forEach(i => { out += row(i); });
                if (dkr.length > 0) {
                    let drx = 0, dtx = 0;
                    dkr.forEach(i => {
                        const parseVal = s => { const m = s.match(/([\d.]+)\s*(\w+)/); if(!m) return 0; const v=parseFloat(m[1]), u=m[2].toUpperCase(); const mul={B:1,KB:1024,MB:1048576,GB:1073741824,TB:1099511627776}; return v*(mul[u]||1); };
                        drx += parseVal(i.bytes_recv);
                        dtx += parseVal(i.bytes_sent);
                    });
                    const fmtBytes = b => { if(b<1024) return b+' B'; if(b<1048576) return (b/1024).toFixed(1)+' KB'; if(b<1073741824) return (b/1048576).toFixed(1)+' MB'; if(b<1099511627776) return (b/1073741824).toFixed(1)+' GB'; return (b/1099511627776).toFixed(1)+' TB'; };
                    out += '<details><summary>Docker <span style="font-weight:400;color:#888">(' + dkr.length + ' interfaces)</span><span class="iface-summary-stats">&#8595; ' + fmtBytes(drx) + ' &nbsp; &#8593; ' + fmtBytes(dtx) + '</span></summary><div class="iface-group-body">';
                    dkr.forEach(i => { out += row(i); });
                    out += '</div></details>';
                }
                out += '</div>';
                return out;
            })()}` : ''}
        </div>`;

        // ── Disk I/O ─────────────────────────────────────────────────────────
        if (d.disk_io) {
            h += `
            <div class="card">
                <h2>Disk I/O Statistics</h2>
                <div class="metric-row"><span class="metric-label">Total Read</span><span class="metric-value">${d.disk_io.read_bytes}</span></div>
                <div class="metric-row"><span class="metric-label">Total Written</span><span class="metric-value">${d.disk_io.write_bytes}</span></div>
                <div class="metric-row"><span class="metric-label">Read Operations</span><span class="metric-value">${d.disk_io.read_count.toLocaleString()}</span></div>
                <div class="metric-row"><span class="metric-label">Write Operations</span><span class="metric-value">${d.disk_io.write_count.toLocaleString()}</span></div>
            </div>`;
        }

        // ── Network Connections ───────────────────────────────────────────────
        h += `
        <div class="card">
            <h2>Network Connections</h2>
            <div class="metric-row"><span class="metric-label">Established</span><span class="metric-value">${d.connections.established}</span></div>
            <div class="metric-row"><span class="metric-label">Listening</span><span class="metric-value">${d.connections.listen}</span></div>
            <div class="metric-row"><span class="metric-label">Time Wait</span><span class="metric-value">${d.connections.time_wait}</span></div>
            <div class="metric-row"><span class="metric-label">Total Connections</span><span class="metric-value">${d.connections.total}</span></div>
        </div>`;

        h += '</div>'; // close second grid

        // ── Detected Services (full width) ────────────────────────────────────
        h += `
        <div class="card" style="margin-bottom:20px;">
            <h2>Detected Services</h2>
            <p class="subtitle-note">Auto-detected from listening sockets in the host network namespace — no service manager dependency.</p>
            ${d.services.length > 0 ? `
            <table class="svc-table">
                <thead>
                    <tr>
                        <th style="width:10%">Port</th>
                        <th style="width:12%">Protocol</th>
                        <th>Service</th>
                    </tr>
                </thead>
                <tbody>
                    ${d.services.map(svc => `
                    <tr>
                        <td class="port-cell">${svc.port}</td>
                        <td><span class="proto-badge proto-${svc.proto.toLowerCase()}">${svc.proto}</span></td>
                        <td>${svc.name}</td>
                    </tr>`).join('')}
                </tbody>
            </table>` : '<div class="info-box">No listening services detected</div>'}

            ${d.firewall.active ? `
            <div class="info-box">
                Firewall active (${d.firewall.type})
            </div>` : ''}
        </div>`;

        // ── WireGuard (if present) ────────────────────────────────────────────
        if (d.wireguard.installed) {
            h += `
            <div class="card" style="margin-bottom:20px;">
                <h2>WireGuard VPN</h2>
                <div class="metric-row">
                    <span class="metric-label">Status</span>
                    <span class="metric-value green">Active</span>
                </div>
                ${d.wireguard.interfaces ? `
                <div class="metric-row">
                    <span class="metric-label">Interfaces</span>
                    <span class="metric-value">${d.wireguard.interfaces.join(', ')}</span>
                </div>` : ''}
                ${d.wireguard.peer_count !== undefined ? `
                <div class="metric-row">
                    <span class="metric-label">Connected Peers</span>
                    <span class="metric-value">${d.wireguard.peer_count}</span>
                </div>` : ''}
                ${d.wireguard.peers && d.wireguard.peers.length > 0 ? `
                <div style="margin-top:15px;">
                    <div class="metric-label" style="margin-bottom:10px;">Active Peers</div>
                    ${d.wireguard.peers.map(p => `
                    <div class="wireguard-peer">
                        <div class="peer-key">Key: ${p.public_key}</div>
                        <div class="peer-info">
                            Endpoint: ${p.endpoint || 'Unknown'}<br>
                            Last handshake: ${p.handshake || 'Never'}<br>
                            Transfer: ${p.transfer || 'No data'}
                        </div>
                    </div>`).join('')}
                </div>` : ''}
            </div>`;
        }

        // ── Top Processes ─────────────────────────────────────────────────────
        h += `
        <div class="card" style="margin-bottom:20px;">
            <h2>Top Processes by CPU Usage</h2>
            <p class="subtitle-note">All host processes visible via pid:host. CPU % accurate from the second refresh onward (psutil baseline).</p>
            <table class="process-table">
                <colgroup>
                    <col class="col-pid"><col class="col-cmd">
                    <col class="col-user"><col class="col-cpu"><col class="col-mem">
                </colgroup>
                <thead>
                    <tr>
                        <th>PID</th>
                        <th>Command</th>
                        <th>User</th>
                        <th class="align-right">CPU %</th>
                        <th class="align-right">MEM %</th>
                    </tr>
                </thead>
                <tbody>
                    ${d.top_processes.map(p => `
                    <tr>
                        <td>${p.pid}</td>
                        <td title="${p.cmd}">
                            <div class="proc-name">${p.name}</div>
                            <div class="proc-cmdline">${p.cmd}</div>
                        </td>
                        <td title="${p.username}">${p.username}</td>
                        <td class="align-right">${p.cpu_percent.toFixed(1)}%</td>
                        <td class="align-right">${p.memory_percent.toFixed(1)}%</td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>`;

        // ── Last Logins ───────────────────────────────────────────────────────
        if (d.last_logins && d.last_logins.length > 0) {
            h += `
            <div class="card" style="margin-bottom:20px;">
                <h2>Recent Login Activity</h2>
                ${d.last_logins.map(l => `
                <div class="login-item">
                    <div class="login-user">${l.user} via ${l.terminal}</div>
                    <div class="login-details">${l.date}</div>
                </div>`).join('')}
            </div>`;
        }

        content.innerHTML = h;
    }

    function updateDashboard() {
        fetch('/api/metrics')
            .then(r => r.json())
            .then(data => {
                renderDashboard(data);
                document.getElementById('last-update').textContent =
                    'Last updated: ' + data.timestamp;
            })
            .catch(() => {
                document.getElementById('dashboard-content').innerHTML =
                    '<div class="alert">Connection error — retrying…</div>';
            });
    }

    updateDashboard();
    setInterval(updateDashboard, 3000);
</script>
</body>
</html>"""  # end of get_dashboard_html


# =============================================================================
# Server bootstrap
# =============================================================================


def run_server(port: int = 8080) -> None:
    server = None

    def _shutdown(sig, frame):
        print("\nShutting down…")
        if server:
            server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), MonitorHandler)
        server.timeout = 10
        print(f"Oracle Monitoring Dashboard (Docker edition) running on port {port}")
        port_suffix = "" if port == 8080 else f":{port}"
        print(f"Access at http://<host-ip>{port_suffix}")
        print("Auto-refreshes every 3 seconds.  Press Ctrl+C to stop.")
        server.serve_forever()
    except PermissionError:
        print(f"ERROR: port {port} requires root privileges")
        print("Run with: sudo python3 monitor-dashboard-docker.py")
    except Exception as exc:
        print(f"ERROR: {exc}")
    finally:
        if server:
            server.server_close()


if __name__ == "__main__":
    port = 8080
    raw_port = os.environ.get("PORT", "").strip()
    if raw_port:
        try:
            port = int(raw_port)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            print(f"ERROR: invalid PORT env var: {raw_port!r} (must be 1-65535)")
            sys.exit(2)
    run_server(port)
