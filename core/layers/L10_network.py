"""L10: Network Automation Layer — advanced network operations.

Actions: 38
Privilege: admin (most actions)
Libraries: psutil, subprocess, winreg, socket, httpx
"""

from __future__ import annotations

import asyncio
import logging
import json
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.engine.verifier import Verifiers
from core.layers._utils import run_ps, run_cmd, create_escalation_fn, create_preflight_fn

logger = logging.getLogger("may.core.layers.L10_network")

# Layer capability map
LAYER_NAME = "network"
ACTIONS = [
    # Network info (12)
    "get_network_interfaces", "get_network_stats", "get_connections",
    "get_listening_ports", "get_established_connections", "get_network_bytes",
    "get_dns_cache", "get_dns_servers", "get_proxy_settings",
    "get_network_latency", "get_traceroute", "get_whois",
    # WiFi management (8)
    "get_wifi_profiles", "connect_wifi_profile", "disconnect_wifi_profile",
    "forget_wifi_profile", "get_wifi_signal_strength", "set_wifi_autoconnect",
    "create_wifi_hotspot", "stop_wifi_hotspot",
    # Firewall (6)
    "list_firewall_rules", "add_firewall_rule", "remove_firewall_rule",
    "enable_firewall", "disable_firewall", "get_firewall_status",
    # Network config (6)
    "set_dns_servers", "set_static_ip", "set_dhcp",
    "set_network_proxy", "clear_proxy", "set_network_priority",
    # Network tools (6)
    "ping_host", "nslookup", "netstat_listening",
    "arp_table", "route_table", "get_public_ip_extended",
]


# ── Network info ──────────────────────────────────────────────────────

async def _get_network_interfaces_ps(params: dict) -> Any:
    success, output = await run_ps(
        "Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,MacAddress,LinkSpeed | ConvertTo-Json"
    )
    if success:
        try:
            return {"interfaces": json.loads(output)}
        except json.JSONDecodeError:
            return {"interfaces": [], "raw": output}
    return {"interfaces": [], "error": output}


async def _get_network_interfaces_cmd(params: dict) -> Any:
    success, output = await run_cmd(["ipconfig", "/all"], timeout=10)
    if success:
        return {"raw": output[:5000]}
    return {"interfaces": [], "error": output}


async def _get_network_stats_ps(params: dict) -> Any:
    success, output = await run_ps(
        "Get-NetAdapterStatistics | Select-Object Name,ReceivedBytes,SentBytes,ReceivedUnicastPackets | ConvertTo-Json"
    )
    if success:
        try:
            return {"stats": json.loads(output)}
        except json.JSONDecodeError:
            return {"stats": [], "raw": output}
    return {"stats": [], "error": output}


async def _get_network_stats_psutil(params: dict) -> Any:
    try:
        import psutil
        counters = psutil.net_io_counters()
        return {
            "bytes_sent": counters.bytes_sent,
            "bytes_recv": counters.bytes_recv,
            "packets_sent": counters.packets_sent,
            "packets_recv": counters.packets_recv,
        }
    except Exception as e:
        return {"error": str(e)}


async def _get_connections_psutil(params: dict) -> Any:
    kind = params.get("kind", "inet")
    try:
        import psutil
        connections = []
        for conn in psutil.net_connections(kind=kind if kind != "all" else None):
            connections.append({
                "fd": conn.fd, "family": str(conn.family),
                "type": str(conn.type), "laddr": str(conn.laddr) if conn.laddr else "",
                "raddr": str(conn.raddr) if conn.raddr else "",
                "status": conn.status, "pid": conn.pid,
            })
        return {"connections": connections[:100]}
    except Exception as e:
        return {"error": str(e)}


async def _get_connections_netstat(params: dict) -> Any:
    success, output = await run_cmd(["netstat", "-an"], timeout=10)
    if success:
        lines = [l.strip() for l in output.strip().split("\n") if l.strip()]
        return {"connections": lines[:100]}
    return {"error": output}


async def _get_listening_ports_psutil(params: dict) -> Any:
    try:
        import psutil
        listening = []
        for conn in psutil.net_connections(kind="inet"):
            if conn.status == "LISTEN":
                listening.append({
                    "address": str(conn.laddr) if conn.laddr else "",
                    "pid": conn.pid,
                    "status": conn.status,
                })
        return {"listening": listening}
    except Exception as e:
        return {"error": str(e)}


async def _get_listening_ports_netstat(params: dict) -> Any:
    success, output = await run_cmd(["netstat", "-an"], timeout=10)
    if success:
        listening = [l.strip() for l in output.strip().split("\n") if "LISTENING" in l]
        return {"listening": listening[:50]}
    return {"error": output}


async def _get_established_connections_psutil(params: dict) -> Any:
    try:
        import psutil
        established = []
        for conn in psutil.net_connections(kind="inet"):
            if conn.status == "ESTABLISHED":
                established.append({
                    "local": str(conn.laddr) if conn.laddr else "",
                    "remote": str(conn.raddr) if conn.raddr else "",
                    "pid": conn.pid,
                })
        return {"established": established[:50]}
    except Exception as e:
        return {"error": str(e)}


async def _get_established_connections_netstat(params: dict) -> Any:
    success, output = await run_cmd(["netstat", "-an"], timeout=10)
    if success:
        lines = [l.strip() for l in output.strip().split("\n") if "ESTABLISHED" in l]
        return {"established": lines[:50]}
    return {"error": output}


async def _get_network_bytes_psutil(params: dict) -> Any:
    try:
        import psutil
        counters = psutil.net_io_counters()
        return {
            "bytes_sent": counters.bytes_sent,
            "bytes_recv": counters.bytes_recv,
            "packets_sent": counters.packets_sent,
            "packets_recv": counters.packets_recv,
        }
    except Exception as e:
        return {"error": str(e)}


async def _get_network_bytes_cmd(params: dict) -> Any:
    success, output = await run_cmd(["netstat", "-e"], timeout=10)
    if success:
        return {"raw": output}
    return {"error": output}


async def _get_dns_cache_ps(params: dict) -> Any:
    success, output = await run_ps("Get-DnsClientCache | Select-Object Entry,RecordName,Data | ConvertTo-Json")
    if success:
        try:
            return {"dns_cache": json.loads(output)}
        except json.JSONDecodeError:
            return {"dns_cache": [], "raw": output}
    return {"error": output}


async def _get_dns_cache_ipconfig(params: dict) -> Any:
    success, output = await run_cmd(["ipconfig", "/displaydns"], timeout=10)
    if success:
        return {"raw": output[:5000]}
    return {"error": output}


async def _get_dns_servers_ps(params: dict) -> Any:
    success, output = await run_ps("Get-DnsClientServerAddress | Select-Object InterfaceAlias,ServerAddresses | ConvertTo-Json")
    if success:
        try:
            return {"dns_servers": json.loads(output)}
        except json.JSONDecodeError:
            return {"dns_servers": [], "raw": output}
    return {"error": output}


async def _get_dns_servers_ipconfig(params: dict) -> Any:
    success, output = await run_cmd(["ipconfig", "/all"], timeout=10)
    if success:
        dns_lines = [l.strip() for l in output.split("\n") if "DNS" in l]
        return {"dns": dns_lines}
    return {"error": output}


async def _get_proxy_settings_ps(params: dict) -> Any:
    success, output = await run_ps("Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' | Select-Object ProxyEnable,ProxyServer,ProxyOverride | ConvertTo-Json")
    if success:
        try:
            return {"proxy": json.loads(output)}
        except json.JSONDecodeError:
            return {"proxy": {}, "raw": output}
    return {"error": output}


async def _get_proxy_settings_reg(params: dict) -> Any:
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        try:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        except FileNotFoundError:
            enabled = 0
        try:
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
        except FileNotFoundError:
            server = ""
        winreg.CloseKey(key)
        return {"proxy_enabled": bool(enabled), "proxy_server": server}
    except Exception as e:
        return {"error": str(e)}


async def _get_network_latency_ps(params: dict) -> Any:
    host = params.get("host", "8.8.8.8")
    success, output = await run_ps(f"(Test-Connection -ComputerName {host} -Count 1 -ErrorAction SilentlyContinue).Latency")
    return {"host": host, "latency_ms": output.strip() if success else "timeout"}


async def _get_network_latency_ping(params: dict) -> Any:
    host = params.get("host", "8.8.8.8")
    count = params.get("count", 1)
    success, output = await run_cmd(["ping", "-n", str(count), host], timeout=10)
    if success:
        return {"host": host, "raw": output[:1000]}
    return {"host": host, "error": output}


async def _get_traceroute_ps(params: dict) -> Any:
    host = params.get("host", "8.8.8.8")
    success, output = await run_ps(f"Test-NetConnection -ComputerName {host} -TraceRoute -ErrorAction SilentlyContinue | Select-Object ComputerName,RemotePort,TraceRoute | ConvertTo-Json", timeout=30)
    if success:
        try:
            return {"traceroute": json.loads(output)}
        except json.JSONDecodeError:
            return {"traceroute": [], "raw": output}
    return {"error": output}


async def _get_traceroute_tracert(params: dict) -> Any:
    host = params.get("host", "8.8.8.8")
    success, output = await run_cmd(["tracert", "-d", host], timeout=30)
    if success:
        hops = [l.strip() for l in output.strip().split("\n") if l.strip()]
        return {"traceroute": hops[:30]}
    return {"error": output}


async def _get_whois_nslookup(params: dict) -> Any:
    domain = params.get("domain", "")
    if not domain:
        return {"error": "Domain required"}
    success, output = await run_cmd(["nslookup", domain], timeout=10)
    return {"domain": domain, "result": output}


async def _get_whois_ps(params: dict) -> Any:
    domain = params.get("domain", "")
    if not domain:
        return {"error": "Domain required"}
    success, output = await run_ps(f"Resolve-DnsName -Name {domain} -Type A -ErrorAction SilentlyContinue | Select-Object Name,Type,TTL,IPAddress | ConvertTo-Json")
    if success:
        try:
            return {"whois": json.loads(output)}
        except json.JSONDecodeError:
            return {"whois": [], "raw": output}
    return {"error": output}


# ── WiFi management ──────────────────────────────────────────────────

async def _get_wifi_profiles_netsh(params: dict) -> Any:
    success, output = await run_ps("netsh wlan show profiles | Select-String 'All User Profile' | ForEach-Object { ($_ -split ':\\s+', 2)[1] }")
    profiles = [p.strip() for p in output.strip().split("\n") if p.strip()] if success else []
    return {"profiles": profiles}


async def _get_wifi_profiles_cmd(params: dict) -> Any:
    success, output = await run_cmd(["netsh", "wlan", "show", "profiles"], timeout=10)
    if success:
        profiles = []
        for line in output.split("\n"):
            if "All User Profile" in line:
                parts = line.split(":", 1)
                if len(parts) >= 2:
                    profiles.append(parts[1].strip())
        return {"profiles": profiles}
    return {"error": output}


async def _connect_wifi_profile(params: dict) -> Any:
    profile = params.get("profile", "")
    if not profile:
        return {"error": "Profile name required"}
    success, output = await run_ps(f'netsh wlan connect name="{profile}"')
    return {"status": "connected" if success else "failed", "output": output}


async def _connect_wifi_cmd(params: dict) -> Any:
    profile = params.get("profile", "")
    if not profile:
        return {"error": "Profile name required"}
    success, output = await run_cmd(["netsh", "wlan", "connect", f"name={profile}"], timeout=10)
    return {"status": "connected" if success else "failed", "output": output}


async def _disconnect_wifi_netsh(params: dict) -> Any:
    success, output = await run_ps("netsh wlan disconnect")
    return {"status": "disconnected" if success else "failed", "output": output}


async def _disconnect_wifi_cmd(params: dict) -> Any:
    success, output = await run_cmd(["netsh", "wlan", "disconnect"], timeout=10)
    return {"status": "disconnected" if success else "failed", "output": output}


async def _forget_wifi_profile(params: dict) -> Any:
    profile = params.get("profile", "")
    if not profile:
        return {"error": "Profile name required"}
    success, output = await run_ps(f'netsh wlan delete profile name="{profile}"')
    return {"status": "deleted" if success else "failed", "output": output}


async def _forget_wifi_cmd(params: dict) -> Any:
    profile = params.get("profile", "")
    if not profile:
        return {"error": "Profile name required"}
    success, output = await run_cmd(["netsh", "wlan", "delete", "profile", f"name={profile}"], timeout=10)
    return {"status": "deleted" if success else "failed", "output": output}


async def _get_wifi_signal_strength(params: dict) -> Any:
    success, output = await run_ps("(netsh wlan show interfaces) -match 'Signal|State|SSID' | ForEach-Object { ($_ -split ':\\s+', 2)[1] }")
    return {"signal": output.strip() if success else "unknown"}


async def _get_wifi_signal_cmd(params: dict) -> Any:
    success, output = await run_cmd(["netsh", "wlan", "show", "interfaces"], timeout=10)
    if success:
        info = {}
        for line in output.split("\n"):
            if "Signal" in line:
                info["signal"] = line.split(":", 1)[-1].strip()
            elif "SSID" in line:
                info["ssid"] = line.split(":", 1)[-1].strip()
        return info
    return {"error": output}


async def _set_wifi_autoconnect(params: dict) -> Any:
    profile = params.get("profile", "")
    if not profile:
        return {"error": "Profile required"}
    success, output = await run_ps(f'netsh wlan set profileorder name="{profile}" priority=1')
    return {"status": "ok" if success else "failed", "output": output}


async def _create_hotspot(params: dict) -> Any:
    ssid = params.get("ssid", "")
    password = params.get("password", "")
    if not ssid:
        return {"error": "SSID required"}
    success, output = await run_ps(f'netsh wlan set hostednetwork mode=allow ssid="{ssid}" key="{password}"')
    if success:
        await run_ps("netsh wlan start hostednetwork")
    return {"status": "started" if success else "failed", "output": output}


async def _stop_hotspot(params: dict) -> Any:
    success, output = await run_ps("netsh wlan stop hostednetwork")
    return {"status": "stopped" if success else "failed", "output": output}


# ── Firewall ──────────────────────────────────────────────────────────

async def _list_firewall_rules_ps(params: dict) -> Any:
    success, output = await run_ps("Get-NetFirewallRule | Where-Object {$_.Enabled -eq 'True'} | Select-Object DisplayName,Direction,Action,Profile | ConvertTo-Json", timeout=30)
    if success:
        try:
            return {"rules": json.loads(output)}
        except json.JSONDecodeError:
            return {"rules": [], "raw": output}
    return {"error": output}


async def _list_firewall_rules_cmd(params: dict) -> Any:
    success, output = await run_cmd(["netsh", "advfirewall", "firewall", "show", "rule", "name=all", "dir=in"], timeout=15)
    if success:
        return {"raw": output[:5000]}
    return {"error": output}


async def _add_firewall_rule_ps(params: dict) -> Any:
    name = params.get("name", "MayRule")
    port = params.get("port", "")
    direction = params.get("direction", "Inbound")
    action = params.get("action", "Allow")
    ps_cmd = f'New-NetFirewallRule -DisplayName "{name}" -Direction {direction} -Action {action}'
    if port:
        ps_cmd += f' -LocalPort {port} -Protocol TCP'
    success, output = await run_ps(ps_cmd)
    return {"status": "added" if success else "failed", "output": output}


async def _add_firewall_rule_cmd(params: dict) -> Any:
    name = params.get("name", "MayRule")
    port = params.get("port", "80")
    direction = params.get("direction", "in")
    action = params.get("action", "allow")
    protocol = params.get("protocol", "TCP")
    success, output = await run_cmd(["netsh", "advfirewall", "firewall", "add", "rule", f"name={name}", f"dir={direction}", f"action={action}", f"protocol={protocol}", f"localport={port}"], timeout=10)
    return {"status": "added" if success else "failed", "output": output}


async def _remove_firewall_rule_ps(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Rule name required"}
    success, output = await run_ps(f'Remove-NetFirewallRule -DisplayName "{name}" -ErrorAction SilentlyContinue')
    return {"status": "removed" if success else "failed", "output": output}


async def _remove_firewall_rule_cmd(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Rule name required"}
    success, output = await run_cmd(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"], timeout=10)
    return {"status": "removed" if success else "failed", "output": output}


async def _enable_firewall_ps(params: dict) -> Any:
    profile = params.get("profile", "allprofiles")
    success, output = await run_ps(f"Set-NetFirewallProfile -Profile {profile} -Enabled $True")
    return {"status": "ok" if success else "failed", "output": output}


async def _enable_firewall_cmd(params: dict) -> Any:
    success, output = await run_cmd(["netsh", "advfirewall", "set", "allprofiles", "state", "on"], timeout=10)
    return {"status": "ok" if success else "failed", "output": output}


async def _disable_firewall_ps(params: dict) -> Any:
    profile = params.get("profile", "allprofiles")
    success, output = await run_ps(f"Set-NetFirewallProfile -Profile {profile} -Enabled $False")
    return {"status": "ok" if success else "failed", "output": output}


async def _disable_firewall_cmd(params: dict) -> Any:
    success, output = await run_cmd(["netsh", "advfirewall", "set", "allprofiles", "state", "off"], timeout=10)
    return {"status": "ok" if success else "failed", "output": output}


async def _get_firewall_status_ps(params: dict) -> Any:
    success, output = await run_ps("Get-NetFirewallProfile | Select-Object Name,Enabled | ConvertTo-Json")
    if success:
        try:
            return {"status": json.loads(output)}
        except json.JSONDecodeError:
            return {"status": [], "raw": output}
    return {"error": output}


async def _get_firewall_status_cmd(params: dict) -> Any:
    success, output = await run_cmd(["netsh", "advfirewall", "show", "allprofiles", "state"], timeout=10)
    if success:
        return {"raw": output}
    return {"error": output}


# ── Network config ────────────────────────────────────────────────────

async def _set_dns_servers_ps(params: dict) -> Any:
    adapter = params.get("adapter", "")
    servers = params.get("servers", [])
    if not adapter or not servers:
        return {"error": "Adapter and servers required"}
    server_str = ", ".join(servers)
    success, output = await run_ps(f'Set-DnsClientServerAddress -InterfaceAlias "{adapter}" -ServerAddresses ({server_str})')
    return {"status": "ok" if success else "failed", "output": output}


async def _set_dns_servers_cmd(params: dict) -> Any:
    adapter = params.get("adapter", "")
    servers = params.get("servers", [])
    if not adapter or not servers:
        return {"error": "Adapter and servers required"}
    # netsh doesn't set DNS directly; use PowerShell fallback
    return await _set_dns_servers_ps(params)


async def _set_static_ip_ps(params: dict) -> Any:
    adapter = params.get("adapter", "")
    ip = params.get("ip", "")
    gateway = params.get("gateway", "")
    if not adapter or not ip:
        return {"error": "Adapter and IP required"}
    ps_cmd = f'New-NetIPAddress -InterfaceAlias "{adapter}" -IPAddress "{ip}"'
    if gateway:
        ps_cmd += f' -DefaultGateway "{gateway}"'
    success, output = await run_ps(ps_cmd)
    return {"status": "ok" if success else "failed", "output": output}


async def _set_dhcp_ps(params: dict) -> Any:
    adapter = params.get("adapter", "")
    if not adapter:
        return {"error": "Adapter required"}
    success, output = await run_ps(f'Set-NetIPInterface -InterfaceAlias "{adapter}" -Dhcp Enabled')
    return {"status": "ok" if success else "failed", "output": output}


async def _set_network_proxy_ps(params: dict) -> Any:
    server = params.get("server", "")
    port = params.get("port", 8080)
    if not server:
        return {"error": "Server required"}
    proxy = f"http://{server}:{port}"
    success, output = await run_ps(f'Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name ProxyEnable -Value 1; Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name ProxyServer -Value "{proxy}"')
    return {"status": "ok" if success else "failed", "proxy": proxy}


async def _set_network_proxy_reg(params: dict) -> Any:
    server = params.get("server", "")
    port = params.get("port", 8080)
    if not server:
        return {"error": "Server required"}
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"http://{server}:{port}")
        winreg.CloseKey(key)
        return {"status": "ok", "proxy": f"http://{server}:{port}"}
    except Exception as e:
        return {"error": str(e)}


async def _clear_proxy_ps(params: dict) -> Any:
    success, output = await run_ps('Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name ProxyEnable -Value 0')
    return {"status": "ok" if success else "failed", "output": output}


async def _clear_proxy_reg(params: dict) -> Any:
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}


async def _set_network_priority(params: dict) -> Any:
    metric = params.get("metric", 10)
    success, output = await run_ps(f"Get-NetAdapter | Where-Object Status -eq 'Up' | Set-NetIPInterface -InterfaceMetric {metric}")
    return {"status": "ok" if success else "failed", "metric": metric}


# ── Network tools ─────────────────────────────────────────────────────

async def _ping_host_ps(params: dict) -> Any:
    host = params.get("host", "8.8.8.8")
    count = params.get("count", 4)
    success, output = await run_ps(f"Test-Connection -ComputerName {host} -Count {count} | Select-Object Address,Latency | ConvertTo-Json")
    if success:
        try:
            return {"ping": json.loads(output)}
        except json.JSONDecodeError:
            return {"ping": [], "raw": output}
    return {"error": output}


async def _ping_host_cmd(params: dict) -> Any:
    host = params.get("host", "8.8.8.8")
    count = params.get("count", 4)
    success, output = await run_cmd(["ping", "-n", str(count), host], timeout=15)
    if success:
        return {"raw": output[:2000]}
    return {"error": output}


async def _nslookup_ps(params: dict) -> Any:
    domain = params.get("domain", "")
    if not domain:
        return {"error": "Domain required"}
    server = params.get("server", "")
    cmd = f"Resolve-DnsName -Name {domain} -Type A"
    if server:
        cmd += f" -Server {server}"
    success, output = await run_ps(f"{cmd} | Select-Object Name,Type,TTL,IPAddress | ConvertTo-Json")
    if success:
        try:
            return {"nslookup": json.loads(output)}
        except json.JSONDecodeError:
            return {"nslookup": [], "raw": output}
    return {"error": output}


async def _nslookup_cmd(params: dict) -> Any:
    domain = params.get("domain", "")
    if not domain:
        return {"error": "Domain required"}
    success, output = await run_cmd(["nslookup", domain], timeout=10)
    if success:
        return {"raw": output}
    return {"error": output}


async def _netstat_listening(params: dict) -> Any:
    success, output = await run_cmd(["netstat", "-an"], timeout=10)
    if success:
        listening = [l.strip() for l in output.strip().split("\n") if "LISTENING" in l]
        return {"listening": listening[:50]}
    return {"error": output}


async def _arp_table(params: dict) -> Any:
    success, output = await run_cmd(["arp", "-a"], timeout=10)
    if success:
        entries = [l.strip() for l in output.strip().split("\n") if l.strip()]
        return {"arp": entries}
    return {"error": output}


async def _route_table(params: dict) -> Any:
    success, output = await run_cmd(["route", "print"], timeout=10)
    if success:
        entries = [l.strip() for l in output.strip().split("\n") if l.strip()]
        return {"routes": entries}
    return {"error": output}


async def _get_public_ip_extended(params: dict) -> Any:
    success, output = await run_ps("(Invoke-WebRequest -Uri 'https://api.ipify.org?format=json' -UseBasicParsing -TimeoutSec 5).Content")
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"ip": output.strip()}
    return {"error": output}


async def _get_public_ip_cmd(params: dict) -> Any:
    success, output = await run_cmd(["curl", "-s", "https://api.ipify.org?format=json"], timeout=10)
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"ip": output.strip()}
    return {"error": output}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION MAP
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    # Network info
    "get_network_interfaces":   ([_get_network_interfaces_ps, _get_network_interfaces_cmd], None),
    "get_network_stats":        ([_get_network_stats_ps, _get_network_stats_psutil], None),
    "get_connections":          ([_get_connections_psutil, _get_connections_netstat], None),
    "get_listening_ports":      ([_get_listening_ports_psutil, _get_listening_ports_netstat], None),
    "get_established_connections": ([_get_established_connections_psutil, _get_established_connections_netstat], None),
    "get_network_bytes":        ([_get_network_bytes_psutil, _get_network_bytes_cmd], None),
    "get_dns_cache":            ([_get_dns_cache_ps, _get_dns_cache_ipconfig], None),
    "get_dns_servers":          ([_get_dns_servers_ps, _get_dns_servers_ipconfig], None),
    "get_proxy_settings":       ([_get_proxy_settings_ps, _get_proxy_settings_reg], None),
    "get_network_latency":      ([_get_network_latency_ps, _get_network_latency_ping], None),
    "get_traceroute":           ([_get_traceroute_ps, _get_traceroute_tracert], None),
    "get_whois":                ([_get_whois_ps, _get_whois_nslookup], None),
    # WiFi management
    "get_wifi_profiles":        ([_get_wifi_profiles_netsh, _get_wifi_profiles_cmd], None),
    "connect_wifi_profile":     ([_connect_wifi_profile, _connect_wifi_cmd], None),
    "disconnect_wifi_profile":  ([_disconnect_wifi_netsh, _disconnect_wifi_cmd], None),
    "forget_wifi_profile":      ([_forget_wifi_profile, _forget_wifi_cmd], None),
    "get_wifi_signal_strength": ([_get_wifi_signal_strength, _get_wifi_signal_cmd], None),
    "set_wifi_autoconnect":     ([_set_wifi_autoconnect], None),
    "create_wifi_hotspot":      ([_create_hotspot], None),
    "stop_wifi_hotspot":        ([_stop_hotspot], None),
    # Firewall
    "list_firewall_rules":      ([_list_firewall_rules_ps, _list_firewall_rules_cmd], None),
    "add_firewall_rule":        ([_add_firewall_rule_ps, _add_firewall_rule_cmd], None),
    "remove_firewall_rule":     ([_remove_firewall_rule_ps, _remove_firewall_rule_cmd], None),
    "enable_firewall":          ([_enable_firewall_ps, _enable_firewall_cmd], None),
    "disable_firewall":         ([_disable_firewall_ps, _disable_firewall_cmd], None),
    "get_firewall_status":      ([_get_firewall_status_ps, _get_firewall_status_cmd], None),
    # Network config
    "set_dns_servers":          ([_set_dns_servers_ps, _set_dns_servers_cmd], None),
    "set_static_ip":            ([_set_static_ip_ps], None),
    "set_dhcp":                 ([_set_dhcp_ps], None),
    "set_network_proxy":        ([_set_network_proxy_ps, _set_network_proxy_reg], None),
    "clear_proxy":              ([_clear_proxy_ps, _clear_proxy_reg], None),
    "set_network_priority":     ([_set_network_priority], None),
    # Network tools
    "ping_host":                ([_ping_host_ps, _ping_host_cmd], None),
    "nslookup":                 ([_nslookup_ps, _nslookup_cmd], None),
    "netstat_listening":        ([_netstat_listening], None),
    "arp_table":                ([_arp_table], None),
    "route_table":              ([_route_table], None),
    "get_public_ip_extended":   ([_get_public_ip_extended, _get_public_ip_cmd], None),
}


# ══════════════════════════════════════════════════════════════════════════════
# HANDLER
# ══════════════════════════════════════════════════════════════════════════════

async def handler(action: str, params: dict[str, Any]) -> Result:
    """L10 Network layer handler — routes actions to their fallback chains."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown network action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"network.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("network", action),
        escalation_fn=create_escalation_fn("network", action),
    )

    suggested = None
    if not success and error:
        suggested = f"Try running as Administrator. Error: {error[:120]}"

    return Result(
        command_id=params.get("id", ""),
        success=success,
        data=data,
        error=error if not success else None,
        verified=verifier is not None and success,
        method_used=method_used,
        suggested_action=suggested,
    )
