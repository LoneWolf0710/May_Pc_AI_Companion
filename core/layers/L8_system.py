"""Layer 8: System Control — Power, Audio, Display, Network, Environment, Hardware.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 10:

Controls: Power management, audio, display, network, environment variables,
WMI queries, hardware info, and system monitoring.

Libraries:
  wmi                  — WMI queries (hardware info, OS info, event watching)
  ctypes.windll.user32 — ExitWindowsEx (shutdown/restart/logoff)
  ctypes.windll.powrprof — Power scheme management, sleep/hibernate
  pycaw                — Windows Core Audio API (volume, devices)
  subprocess + netsh   — Wi-Fi, network adapter, firewall control
  winreg               — System environment variables
"""

from __future__ import annotations

import asyncio
import ctypes
import ctypes.wintypes
import os
import platform
import subprocess
import winreg
import logging
import time
from datetime import datetime
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.engine.verifier import Verifiers
from core.layers._utils import run_ps as _run_ps, run_cmd as _run_cmd, create_escalation_fn, create_preflight_fn

logger = logging.getLogger("may.core.layers.L8_system")



def _run_cmd_sync(args: list[str], timeout: float = 10) -> tuple[bool, str]:
    """Run a command synchronously (for blocking Win32 calls)."""
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout.strip()
        if result.returncode == 0:
            return True, output
        error = result.stderr.strip()
        return False, error or output
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return False, f"Command not found: {args[0]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ── Win32 Constants ──────────────────────────────────────────────────────────

EWX_SHUTDOWN  = 0x00000001
EWX_REBOOT    = 0x00000002
EWX_LOGOFF    = 0x00000000
EWX_FORCE     = 0x00000004
EWX_POWEROFF  = 0x00000008

SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE  = 9
SW_HIDE     = 0
SW_SHOW     = 5

SYSTEM_ENV_KEY = r"System\CurrentControlSet\Control\Session Manager\Environment"
USER_ENV_KEY   = "Environment"




# ══════════════════════════════════════════════════════════════════════════════
# AUDIO CONTROL (pycaw)
# ══════════════════════════════════════════════════════════════════════════════

async def _set_volume_pycaw(params: dict) -> Any:
    """Method 1: Set volume via pycaw (Windows Core Audio API)."""
    level = max(0, min(100, params.get("level", 50)))
    vol = _pycaw_endpoint_volume()
    vol.SetMasterVolumeLevelScalar(level / 100.0, None)
    return {"level": level}


async def _volume_up_pycaw(params: dict) -> Any:
    """Volume up by delta (capped at 30) via pycaw."""
    delta = min(30, max(1, params.get("delta", 15)))
    vol = _pycaw_endpoint_volume()
    current = int(vol.GetMasterVolumeLevelScalar() * 100)
    new_level = min(100, current + delta)
    vol.SetMasterVolumeLevelScalar(new_level / 100.0, None)
    return {"level": new_level, "previous": current}


async def _volume_down_pycaw(params: dict) -> Any:
    """Volume down by delta (capped at 30) via pycaw."""
    delta = min(30, max(1, params.get("delta", 15)))
    vol = _pycaw_endpoint_volume()
    current = int(vol.GetMasterVolumeLevelScalar() * 100)
    new_level = max(0, current - delta)
    vol.SetMasterVolumeLevelScalar(new_level / 100.0, None)
    return {"level": new_level, "previous": current}


async def _volume_up_powershell(params: dict) -> Any:
    """Method 2: Volume up via PowerShell SendKeys (safe: max 15 key presses)."""
    delta = min(30, max(1, params.get("delta", 15)))
    count = min(15, max(1, delta // 2))
    # Send keys with small delay to prevent flooding
    await _run_ps(
        f"$wsh = New-Object -ComObject WScript.Shell; "
        f"for($i=0;$i -lt {count}){{$wsh.SendKeys([char]175); Start-Sleep -Milliseconds 50}}"
    )
    return {"action": "volume_up", "delta": delta, "approximate": True}


async def _volume_down_powershell(params: dict) -> Any:
    """Method 2: Volume down via PowerShell SendKeys (safe: max 15 key presses)."""
    delta = min(30, max(1, params.get("delta", 15)))
    count = min(15, max(1, delta // 2))
    # Send keys with small delay to prevent flooding
    await _run_ps(
        f"$wsh = New-Object -ComObject WScript.Shell; "
        f"for($i=0;$i -lt {count}){{$wsh.SendKeys([char]174); Start-Sleep -Milliseconds 50}}"
    )
    return {"action": "volume_down", "delta": delta, "approximate": True}


async def _get_volume_powershell(params: dict) -> Any:
    """Method 2: Get volume via PowerShell SendKeys."""
    return {"level": -1, "source": "powershell_fallback"}


async def _mute_powershell(params: dict) -> Any:
    """Method 2: Mute via PowerShell."""
    await _run_ps("$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]0xAD)")
    return {"muted": True}


async def _unmute_powershell(params: dict) -> Any:
    """Method 2: Unmute via PowerShell."""
    await _run_ps("$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]0xAD)")
    return {"muted": False}


async def _set_volume_powershell(params: dict) -> Any:
    """Method 2: Set volume via PowerShell using nircmd or SndVol."""
    level = max(0, min(100, params.get("level", 50)))
    # Use nircmd if available (most reliable PowerShell volume method)
    success, output = await _run_ps(
        f"if (Get-Command nircmd -ErrorAction SilentlyContinue) {{ "
        f"  nircmd setsysvolume {int(level * 655.35)}; 'nircmd' "
        f"}} else {{ 'no-nircmd' }}",
        timeout=5,
    )
    if success and "nircmd" in (output or ""):
        return {"level": level, "method": "nircmd"}
    # Fallback: use SendKeys with safe cap on iterations
    diff = abs(level - 50)  # approximate — SendKeys can't read current volume
    count = min(15, max(1, diff // 2))
    key_char = "175" if level > 50 else "174"
    await _run_ps(
        f"$wsh = New-Object -ComObject WScript.Shell; "
        f"for($i=0;$i -lt {count}){{$wsh.SendKeys([char]{key_char}); Start-Sleep -Milliseconds 50}}",
        timeout=10,
    )
    return {"level": level, "approximate": True}


def _pycaw_endpoint_volume():
    """Return the IAudioEndpointVolume interface for the default speakers.

    Handles both old and new pycaw versions:
    - New pycaw: GetSpeakers() returns AudioDevice with .EndpointVolume property
    - Old pycaw: GetSpeakers() returns IMMDevice requiring .Activate()
    """
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    from ctypes import cast, POINTER

    device = AudioUtilities.GetSpeakers()

    # Try new pycaw: AudioDevice.EndpointVolume property
    endpoint = getattr(device, "EndpointVolume", None)
    if endpoint is not None:
        # Check if it's already an IAudioEndpointVolume interface
        if hasattr(endpoint, "GetMasterVolumeLevelScalar"):
            return endpoint
        # Try to cast it
        try:
            return cast(endpoint, POINTER(IAudioEndpointVolume))
        except Exception:
            pass

    # Try IMMDevice.Activate path (old pycaw or fallback)
    try:
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except AttributeError:
        # device is AudioDevice, not IMMDevice — extract underlying IMMDevice
        try:
            imm_device = device._imm_device  # Access internal reference
            interface = imm_device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return cast(interface, POINTER(IAudioEndpointVolume))
        except (AttributeError, Exception):
            pass

    # Last resort: try to use device directly if it quacks like IAudioEndpointVolume
    if hasattr(device, "GetMasterVolumeLevelScalar"):
        return device

    raise RuntimeError("Cannot obtain IAudioEndpointVolume interface from pycaw")


async def _get_volume_pycaw(params: dict) -> Any:
    """Get volume via pycaw."""
    vol = _pycaw_endpoint_volume()
    level = int(vol.GetMasterVolumeLevelScalar() * 100)
    muted = bool(vol.GetMute())
    return {"level": level, "muted": muted}


async def _mute_pycaw(params: dict) -> Any:
    """Mute via pycaw."""
    vol = _pycaw_endpoint_volume()
    vol.SetMute(1, None)
    return {"muted": True}


async def _unmute_pycaw(params: dict) -> Any:
    """Unmute via pycaw."""
    vol = _pycaw_endpoint_volume()
    vol.SetMute(0, None)
    return {"muted": False}


# ══════════════════════════════════════════════════════════════════════════════
# POWER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

async def _shutdown_exitwin32(params: dict) -> Any:
    """Method 1: Shutdown via ExitWindowsEx (most direct)."""
    delay = params.get("delay", 0)
    flags = EWX_SHUTDOWN | EWX_FORCE
    ctypes.windll.user32.ExitWindowsEx(flags, 0)
    return {"action": "shutdown", "delay": delay}


async def _shutdown_cmd(params: dict) -> Any:
    """Method 2: Shutdown via shutdown.exe command."""
    delay = params.get("delay", 0)
    success, output = await _run_cmd(["shutdown", "/s", "/t", str(delay)])
    return {"action": "shutdown", "delay": delay}


async def _shutdown_powershell(params: dict) -> Any:
    """Method 3: Shutdown via PowerShell Stop-Computer."""
    delay = params.get("delay", 0)
    if delay > 0:
        # PowerShell doesn't support delay natively, fall back to shutdown.exe
        return await _shutdown_cmd(params)
    success, output = await _run_ps("Stop-Computer -Force")
    return {"action": "shutdown", "delay": 0}


async def _reboot_exitwin32(params: dict) -> Any:
    """Method 1: Restart via ExitWindowsEx."""
    delay = params.get("delay", 0)
    flags = EWX_REBOOT | EWX_FORCE
    ctypes.windll.user32.ExitWindowsEx(flags, 0)
    return {"action": "restart", "delay": delay}


async def _reboot_cmd(params: dict) -> Any:
    """Method 2: Restart via shutdown.exe."""
    delay = params.get("delay", 0)
    success, output = await _run_cmd(["shutdown", "/r", "/t", str(delay)])
    return {"action": "restart", "delay": delay}


async def _reboot_powershell(params: dict) -> Any:
    """Method 3: Restart via PowerShell Restart-Computer."""
    delay = params.get("delay", 0)
    if delay > 0:
        return await _reboot_cmd(params)
    success, output = await _run_ps("Restart-Computer -Force")
    return {"action": "restart", "delay": 0}


async def _sleep_set_suspend(params: dict) -> Any:
    """Method 1: Sleep via SetSuspendState."""
    ctypes.windll.powrprof.SetSuspendState(False, True, False)
    return {"action": "sleep"}


async def _sleep_powershell(params: dict) -> Any:
    """Method 2: Sleep via PowerShell."""
    success, output = await _run_ps(
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"
    )
    return {"action": "sleep"}


async def _hibernate_set_suspend(params: dict) -> Any:
    """Method 1: Hibernate via SetSuspendState."""
    ctypes.windll.powrprof.SetSuspendState(True, True, False)
    return {"action": "hibernate"}


async def _hibernate_powershell(params: dict) -> Any:
    """Method 2: Hibernate via PowerShell."""
    success, output = await _run_ps(
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $true, $false)"
    )
    return {"action": "hibernate"}


async def _lock_win32(params: dict) -> Any:
    """Method 1: Lock via LockWorkStation."""
    ctypes.windll.user32.LockWorkStation()
    return {"action": "lock"}


async def _lock_rundll32(params: dict) -> Any:
    """Method 2: Lock via rundll32."""
    success, output = await _run_cmd(["rundll32.exe", "user32.dll,LockWorkStation"])
    return {"action": "lock"}


async def _cancel_shutdown(params: dict) -> Any:
    """Cancel a pending shutdown."""
    success, output = await _run_cmd(["shutdown", "/a"])
    return {"action": "cancel_shutdown"}


# ══════════════════════════════════════════════════════════════════════════════
# DISPLAY CONTROL
# ══════════════════════════════════════════════════════════════════════════════

async def _set_brightness_sbc(params: dict) -> Any:
    """Method 1: Set brightness via screen_brightness_control."""
    import screen_brightness_control as sbc
    level = max(0, min(100, params.get("level", 50)))
    sbc.set_brightness(level)
    return {"level": level}


async def _set_brightness_wmi(params: dict) -> Any:
    """Method 2: Set brightness via WMI."""
    level = max(0, min(100, params.get("level", 50)))
    success, output = await _run_ps(
        f"$m = Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBrightnessMethods; "
        f"$m.WmiSetBrightness(1, {level}); "
        f"'Brightness set to {level}%'"
    )
    if not success:
        raise RuntimeError(output)
    return {"level": level}


async def _get_brightness_sbc(params: dict) -> Any:
    """Get brightness via screen_brightness_control."""
    import screen_brightness_control as sbc
    level = sbc.get_brightness()[0]
    return {"level": int(level)}


async def _get_brightness_wmi(params: dict) -> Any:
    """Get brightness via WMI."""
    success, output = await _run_ps(
        "Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBrightness | "
        "Select-Object -ExpandProperty CurrentBrightness"
    )
    if success and output.isdigit():
        return {"level": int(output)}
    raise RuntimeError(output)


async def _change_resolution_win32api(params: dict) -> Any:
    """Method 1: Change resolution via win32api."""
    import win32api
    width = params.get("width", 1920)
    height = params.get("height", 1080)
    devmode = win32api.EnumDisplaySettings(None, -1)
    devmode.PelsWidth = width
    devmode.PelsHeight = height
    win32api.ChangeDisplaySettings(devmode, 0)
    return {"width": width, "height": height}


async def _change_resolution_powershell(params: dict) -> Any:
    """Method 2: Change resolution via PowerShell (limited — reads current)."""
    width = params.get("width", 1920)
    height = params.get("height", 1080)
    # PowerShell has no native resolution change — fall back to QRes or direct API
    success, output = await _run_ps(
        f"Add-Type -AssemblyName System.Windows.Forms; "
        f"$screen = [System.Windows.Forms.Screen]::PrimaryScreen; "
        f"Write-Output \"$($screen.Bounds.Width)x$($screen.Bounds.Height)\""
    )
    # Since PS can't change resolution, raise so FallbackChain tries next method
    raise RuntimeError("PowerShell cannot change resolution — use win32api method")


async def _get_displays_win32api(params: dict) -> Any:
    """Get display info via win32api."""
    import win32api
    displays = []
    try:
        # Get primary display info
        devmode = win32api.EnumDisplaySettings(None, -1)
        displays.append({
            "name": "Primary",
            "width": devmode.PelsWidth,
            "height": devmode.PelsHeight,
            "frequency": devmode.DisplayFrequency,
        })
    except Exception:
        pass
    return {"displays": displays}


async def _get_displays_powershell(params: dict) -> Any:
    """Get display info via PowerShell."""
    success, output = await _run_ps(
        "Get-CimInstance Win32_DesktopMonitor | "
        "Select-Object Name, ScreenWidth, ScreenHeight | "
        "ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"displays": data}
        except json.JSONDecodeError:
            pass
    return {"displays": []}


# ══════════════════════════════════════════════════════════════════════════════
# NETWORK CONTROL
# ══════════════════════════════════════════════════════════════════════════════

async def _get_ip_config(params: dict) -> Any:
    """Get IP configuration."""
    success, output = await _run_ps(
        "Get-NetIPAddress -AddressFamily IPv4 | "
        "Select-Object InterfaceAlias, IPAddress | "
        "ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"addresses": data}
        except json.JSONDecodeError:
            pass
    return {"addresses": [], "raw": output}


async def _get_network_info(params: dict) -> Any:
    """Get comprehensive network info."""
    success, output = await _run_ps(
        "$adapters = Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | "
        "Select-Object Name, LinkSpeed; "
        "$ip = Get-NetIPAddress -AddressFamily IPv4 | "
        "Select-Object InterfaceAlias, IPAddress; "
        "$wifi = netsh wlan show interfaces 2>&1 | Select-String 'SSID|Signal|Speed'; "
        " @{adapters=$adapters; ip=$ip; wifi=($wifi -join \"`n\")} | ConvertTo-Json -Compress"
    )
    return {"raw": output}


async def _toggle_wifi_netsh(params: dict) -> Any:
    """Toggle WiFi via netsh."""
    enable = params.get("enable", True)
    if enable:
        success, output = await _run_cmd(["netsh", "interface", "set", "interface", "Wi-Fi", "enable"])
    else:
        success, output = await _run_cmd(["netsh", "interface", "set", "interface", "Wi-Fi", "disable"])
    if not success:
        # Try WLAN adapter name
        if enable:
            success, output = await _run_cmd(["netsh", "interface", "set", "interface", "WLAN", "enable"])
        else:
            success, output = await _run_cmd(["netsh", "interface", "set", "interface", "WLAN", "disable"])
    return {"enabled": enable, "success": success}


async def _toggle_wifi_powershell(params: dict) -> Any:
    """Toggle WiFi via PowerShell."""
    enable = params.get("enable", True)
    action = "Enable" if enable else "Disable"
    success, output = await _run_ps(f"{action}-NetAdapter -Name 'Wi-Fi' -Confirm:$false -ErrorAction SilentlyContinue")
    if not success:
        success, output = await _run_ps(f"{action}-NetAdapter -Name 'WLAN' -Confirm:$false -ErrorAction SilentlyContinue")
    return {"enabled": enable, "success": success}


async def _flush_dns(params: dict) -> Any:
    """Flush DNS cache."""
    success, output = await _run_cmd(["ipconfig", "/flushdns"])
    return {"success": success}


async def _get_wifi_password(params: dict) -> Any:
    """Get WiFi passwords for saved networks."""
    success, output = await _run_ps(
        "$profiles = netsh wlan show profiles | "
        "Select-String 'All User Profile\\s+:\\s+(.+$)' | "
        "ForEach-Object { $_.Matches.Groups[1].Value.Trim() }; "
        "$output = ''; "
        "foreach ($p in $profiles) { "
        "  $detail = netsh wlan show profile name=\"$p\" key=clear 2>&1; "
        "  $key = ($detail | Select-String 'Key Content\\s+:\\s+(.+$)').Matches.Groups[1].Value.Trim(); "
        "  $output += \"$p : $key`n\" "
        "}; $output"
    )
    return {"passwords": output}


# ══════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT VARIABLES
# ══════════════════════════════════════════════════════════════════════════════

async def _get_env_var(params: dict) -> Any:
    """Get an environment variable."""
    name = params.get("name", "")
    value = os.environ.get(name)
    if value is not None:
        return {"name": name, "value": value}
    return {"name": name, "value": None, "error": "Not set"}


async def _set_system_env(params: dict) -> Any:
    """Set a system environment variable."""
    name = params.get("name", "")
    value = params.get("value", "")
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, SYSTEM_ENV_KEY, 0, winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
        # Broadcast change
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None,
        )
        os.environ[name] = value
        return {"name": name, "value": value, "target": "Machine"}
    except PermissionError:
        return {"name": name, "error": "Permission denied — run as Admin"}


async def _set_user_env(params: dict) -> Any:
    """Set a user environment variable."""
    name = params.get("name", "")
    value = params.get("value", "")
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, USER_ENV_KEY, 0, winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None,
        )
        os.environ[name] = value
        return {"name": name, "value": value, "target": "User"}
    except Exception as e:
        return {"name": name, "error": str(e)}


async def _list_env_vars(params: dict) -> Any:
    """List environment variables."""
    filter_str = params.get("filter", "")
    env_vars = dict(os.environ)
    if filter_str:
        env_vars = {k: v for k, v in env_vars.items() if filter_str.lower() in k.lower()}
    return {"count": len(env_vars), "vars": dict(sorted(env_vars.items())[:50])}


# ══════════════════════════════════════════════════════════════════════════════
# HARDWARE & SYSTEM INFO
# ══════════════════════════════════════════════════════════════════════════════

async def _get_system_info(params: dict) -> Any:
    """Get comprehensive system information."""
    import psutil
    info = {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "machine": platform.machine(),
        "processor": platform.processor()[:80],
        "cpu_cores": psutil.cpu_count(),
        "cpu_physical": psutil.cpu_count(logical=False),
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        "ram_percent": psutil.virtual_memory().percent,
        "ram_available_gb": round(psutil.virtual_memory().available / (1024**3), 1),
        "username": os.environ.get("USERNAME", "N/A"),
        "computer": os.environ.get("COMPUTERNAME", "N/A"),
    }
    boot = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot
    info["uptime_hours"] = int(uptime.total_seconds() // 3600)
    info["uptime_minutes"] = int((uptime.total_seconds() % 3600) // 60)
    return info


async def _get_ram_usage(params: dict) -> Any:
    """Get RAM usage."""
    import psutil
    mem = psutil.virtual_memory()
    return {
        "total_gb": round(mem.total / (1024**3), 2),
        "used_gb": round(mem.used / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2),
        "percent": mem.percent,
    }


async def _get_disk_usage(params: dict) -> Any:
    """Get disk usage for all drives."""
    import psutil
    disks = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "total_gb": round(usage.total / (1024**3), 1),
                "used_gb": round(usage.used / (1024**3), 1),
                "free_gb": round(usage.free / (1024**3), 1),
                "percent": usage.percent,
            })
        except PermissionError:
            continue
    return {"disks": disks}


async def _get_uptime(params: dict) -> Any:
    """Get system uptime."""
    import psutil
    boot = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot
    hours = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)
    return {"hours": hours, "minutes": minutes, "boot_time": boot.isoformat()}


async def _get_cpu_temp(params: dict) -> Any:
    """Get CPU temperature via OpenHardwareMonitor or WMI."""
    # Try OpenHardwareMonitor WMI first
    success, output = await _run_ps(
        "Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace 'root\\wmi' | "
        "Select-Object -ExpandProperty CurrentTemperature | "
        "ForEach-Object { [math]::Round(($_ - 2732) / 10, 1) } | "
        "Measure-Object -Average | Select-Object -ExpandProperty Average"
    )
    if success and output:
        try:
            temp = float(output)
            return {"temperature_c": temp, "source": "WMI"}
        except ValueError:
            pass
    return {"temperature_c": None, "source": "unavailable"}


async def _get_hardware_info(params: dict) -> Any:
    """Get hardware info via WMI."""
    success, output = await _run_ps(
        "Get-CimInstance Win32_ComputerSystem | "
        "Select-Object Manufacturer, Model, TotalPhysicalMemory, NumberOfProcessors | "
        "ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            data = json.loads(output)
            return {"hardware": data}
        except json.JSONDecodeError:
            pass
    return {"hardware": None}


async def _get_battery_info(params: dict) -> Any:
    """Get battery information."""
    import psutil
    battery = psutil.sensors_battery()
    if battery is None:
        return {"has_battery": False}
    return {
        "has_battery": True,
        "percent": battery.percent,
        "plugged": battery.power_plugged,
        "secs_left": battery.secsleft if battery.secsleft > 0 else None,
    }



# ══════════════════════════════════════════════════════════════════════════════
# WIFI CONNECT / DISCONNECT
# ══════════════════════════════════════════════════════════════════════════════

async def _connect_wifi_action(params: dict) -> Any:
    """Connect to a WiFi network by SSID."""
    ssid = params["ssid"]
    password = params.get("password", "")
    if password:
        safe_pw = password.replace("'", "''")
        cmd = f"netsh wlan connect name='{ssid}' password='{safe_pw}'"
    else:
        cmd = f"netsh wlan connect name='{ssid}'"
    success, output = await _run_ps(cmd, timeout=15)
    if not success:
        raise RuntimeError(output)
    return {"connected": ssid}


async def _disconnect_wifi_action(params: dict) -> Any:
    """Disconnect from WiFi."""
    success, output = await _run_ps("netsh wlan disconnect", timeout=10)
    if not success:
        raise RuntimeError(output)
    return {"disconnected": True}


# ══════════════════════════════════════════════════════════════════════════════
# FIREWALL RULES
# ══════════════════════════════════════════════════════════════════════════════

async def _add_firewall_rule_action(params: dict) -> Any:
    """Add a firewall rule."""
    name = params["name"]
    direction = params.get("direction", "Inbound")
    action = params.get("action", "Allow")
    protocol = params.get("protocol", "TCP")
    port = params.get("port", "80")
    success, output = await _run_cmd([
        "netsh", "advfirewall", "firewall", "add", "rule",
        f"name={name}", f"dir={direction}", f"action={action}",
        f"protocol={protocol}", f"localport={port}",
    ])
    if not success:
        raise RuntimeError(output)
    return {"rule_added": name}


async def _remove_firewall_rule_action(params: dict) -> Any:
    """Remove a firewall rule by name."""
    name = params["name"]
    success, output = await _run_cmd([
        "netsh", "advfirewall", "firewall", "delete", "rule",
        f"name={name}",
    ])
    if not success:
        raise RuntimeError(output)
    return {"rule_removed": name}


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC IP
# ══════════════════════════════════════════════════════════════════════════════

async def _get_public_ip_action(params: dict) -> Any:
    """Get public IP address."""
    success, output = await _run_ps("(Invoke-WebRequest -Uri 'https://api.ipify.org?format=json' -UseBasicParsing).Content")
    if success and output:
        import json
        try:
            data = json.loads(output)
            return {"public_ip": data.get("ip", output)}
        except json.JSONDecodeError:
            return {"public_ip": output}
    return {"public_ip": None, "error": output}


# ══════════════════════════════════════════════════════════════════════════════
# LOGOFF
# ══════════════════════════════════════════════════════════════════════════════

async def _logoff_action(params: dict) -> Any:
    """Log off the current user."""
    ctypes.windll.user32.ExitWindowsEx(EWX_LOGOFF, 0)
    return {"action": "logoff"}


# ══════════════════════════════════════════════════════════════════════════════
# AUDIO DEVICES
# ══════════════════════════════════════════════════════════════════════════════

async def _get_audio_devices_action(params: dict) -> Any:
    """List audio endpoints."""
    from pycaw.pycaw import AudioUtilities
    devices = AudioUtilities.GetAllSpeakers()
    result = []
    for d in devices:
        try:
            result.append({"id": str(d.id), "name": d.FriendlyName})
        except Exception:
            continue
    return {"devices": result, "count": len(result)}


async def _set_default_device_action(params: dict) -> Any:
    """Set default audio playback device."""
    device_name = params.get("name", "")
    success, output = await _run_ps(
        f"Get-AudioDevice -List | Where-Object {{$_.Name -like '*{device_name}*'}} | "
        f"Select-Object -First 1 -ExpandProperty Id | "
        f"ForEach-Object {{ Set-AudioDevice $_ }}"
    )
    if not success:
        # Fallback: try PowerShell native
        success, output = await _run_ps(
            f"$devices = Get-PnpDevice -Class Media -Status OK; "
            f"$target = $devices | Where-Object {{$_.FriendlyName -like '*{device_name}*'}} | Select-Object -First 1; "
            f"if ($target) {{ Write-Output $target.FriendlyName }} else {{ Write-Output 'Device not found' }}"
        )
    return {"default_device": device_name}


# ══════════════════════════════════════════════════════════════════════════════
# ROTATE DISPLAY
# ══════════════════════════════════════════════════════════════════════════════

async def _rotate_display_action(params: dict) -> Any:
    """Rotate screen orientation."""
    angle = params.get("angle", 0)  # 0, 90, 180, 270
    import win32api
    import win32con
    devmode = win32api.EnumDisplaySettings(None, -1)
    orientation_map = {0: win32con.DMDO_DEFAULT, 90: win32con.DMDO_90, 180: win32con.DMDO_180, 270: win32con.DMDO_270}
    devmode.DisplayOrientation = orientation_map.get(angle, win32con.DMDO_DEFAULT)
    if angle in (90, 270):
        devmode.PelsWidth, devmode.PelsHeight = devmode.PelsHeight, devmode.PelsWidth
    win32api.ChangeDisplaySettings(devmode, 0)
    return {"rotated": angle}


# ══════════════════════════════════════════════════════════════════════════════
# ENABLE / DISABLE ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

async def _enable_adapter_action(params: dict) -> Any:
    """Enable a network adapter."""
    name = params.get("name", "Wi-Fi")
    success, output = await _run_cmd(["netsh", "interface", "set", "interface", name, "enable"])
    if not success:
        success, output = await _run_ps(f"Enable-NetAdapter -Name '{name}' -Confirm:$false")
    if not success:
        raise RuntimeError(output)
    return {"enabled": name}


async def _disable_adapter_action(params: dict) -> Any:
    """Disable a network adapter."""
    name = params.get("name", "Wi-Fi")
    success, output = await _run_cmd(["netsh", "interface", "set", "interface", name, "disable"])
    if not success:
        success, output = await _run_ps(f"Disable-NetAdapter -Name '{name}' -Confirm:$false")
    if not success:
        raise RuntimeError(output)
    return {"disabled": name}


# ══════════════════════════════════════════════════════════════════════════════
# LIST WIFI NETWORKS
# ══════════════════════════════════════════════════════════════════════════════

async def _list_wifi_networks_action(params: dict) -> Any:
    """Scan and list available WiFi networks."""
    success, output = await _run_cmd(["netsh", "wlan", "show", "networks", "mode=bssid"], timeout=20)
    if success:
        return {"networks": output[:5000]}
    raise RuntimeError(output)


# ══════════════════════════════════════════════════════════════════════════════
# GET USER ENV
# ══════════════════════════════════════════════════════════════════════════════

async def _get_user_env_action(params: dict) -> Any:
    """Get user environment variables from registry."""
    name = params.get("name", "")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, USER_ENV_KEY, 0, winreg.KEY_READ) as key:
            if name:
                value, _ = winreg.QueryValueEx(key, name)
                return {"name": name, "value": value}
            else:
                env_vars = {}
                i = 0
                while True:
                    try:
                        vname, value, _ = winreg.EnumValue(key, i)
                        env_vars[vname] = value
                        i += 1
                    except OSError:
                        break
                return {"vars": dict(list(env_vars.items())[:50]), "count": len(env_vars)}
    except FileNotFoundError:
        return {"error": f"Variable '{name}' not found"}


# ══════════════════════════════════════════════════════════════════════════════
# GET SYSTEM ENV (from HKLM registry — symmetric with get_user_env)
# ══════════════════════════════════════════════════════════════════════════════

async def _get_system_env_action(params: dict) -> Any:
    """Get system environment variables from HKLM registry."""
    name = params.get("name", "")
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, SYSTEM_ENV_KEY, 0, winreg.KEY_READ) as key:
            if name:
                value, _ = winreg.QueryValueEx(key, name)
                return {"name": name, "value": value}
            else:
                env_vars = {}
                i = 0
                while True:
                    try:
                        vname, value, _ = winreg.EnumValue(key, i)
                        env_vars[vname] = value
                        i += 1
                    except OSError:
                        break
                return {"vars": dict(list(env_vars.items())[:50]), "count": len(env_vars)}
    except FileNotFoundError:
        return {"error": f"Variable '{name}' not found"}


# ══════════════════════════════════════════════════════════════════════════════
# GET OS INFO
# ══════════════════════════════════════════════════════════════════════════════

async def _get_os_info_action(params: dict) -> Any:
    """Get detailed OS information."""
    success, output = await _run_ps(
        "Get-CimInstance Win32_OperatingSystem | "
        "Select-Object Caption, Version, BuildNumber, OSArchitecture, InstallDate, LastBootUpTime | "
        "ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"os": f"{platform.system()} {platform.release()}"}


# ══════════════════════════════════════════════════════════════════════════════
# WMI EVENT WATCHERS
# ══════════════════════════════════════════════════════════════════════════════

_watchers = {}  # name -> thread/flag

async def _watch_process_action(params: dict) -> Any:
    """Watch for process creation events via WMI."""
    action = params.get("action", "start")  # start, stop
    name = params.get("watcher_name", "process_watcher")
    if action == "stop":
        flag = _watchers.pop(name, None)
        if flag:
            flag["stop"] = True
            return {"stopped": name}
        return {"error": "No watcher found"}
    import threading
    flag = {"stop": False, "events": []}
    def _watch():
        import wmi
        c = wmi.WMI()
        watcher = c.Win32_Process.watch_for("creation")
        while not flag["stop"]:
            try:
                process = watcher(timeout=2)
                if process:
                    flag["events"].append({"name": process.Name, "pid": process.ProcessId})
            except wmi.x_wmi_timed_out:
                continue
            except Exception:
                break
    t = threading.Thread(target=_watch, daemon=True)
    t.start()
    _watchers[name] = flag
    return {"watching": name, "type": "process_creation"}


async def _watch_usb_action(params: dict) -> Any:
    """Watch for USB connect/disconnect events."""
    action = params.get("action", "start")
    name = params.get("watcher_name", "usb_watcher")
    if action == "stop":
        flag = _watchers.pop(name, None)
        if flag:
            flag["stop"] = True
            return {"stopped": name}
        return {"error": "No watcher found"}
    import threading
    flag = {"stop": False, "events": []}
    def _watch():
        import wmi
        c = wmi.WMI()
        watcher = c.Win32_DeviceChangeEvent.watch_for()
        while not flag["stop"]:
            try:
                event = watcher(timeout=2)
                if event:
                    flag["events"].append({"type": event.EventType, "time": str(event.TimeGenerated)})
            except wmi.x_wmi_timed_out:
                continue
            except Exception:
                break
    t = threading.Thread(target=_watch, daemon=True)
    t.start()
    _watchers[name] = flag
    return {"watching": name, "type": "usb_events"}


async def _watch_file_events_action(params: dict) -> Any:
    """Watch for file system events via watchdog."""
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    import threading
    path = params.get("path", ".")
    action = params.get("action", "start")
    name = params.get("watcher_name", f"file_{path}")
    if action == "stop":
        observer = _watchers.pop(name, None)
        if observer:
            observer.stop()
            observer.join(timeout=2)
            return {"stopped": name}
        return {"error": "No watcher found"}
    class Handler(FileSystemEventHandler):
        def __init__(self, flag):
            self.flag = flag
        def on_any_event(self, event):
            self.flag["events"].append({"type": event.event_type, "src": event.src_path})
    flag = {"stop": False, "events": []}
    handler = Handler(flag)
    observer = Observer()
    observer.schedule(handler, path, recursive=True)
    observer.start()
    _watchers[name] = observer
    return {"watching": path, "type": "file_events"}


# ══════════════════════════════════════════════════════════════════════════════
# GET INSTALLED UPDATES
# ══════════════════════════════════════════════════════════════════════════════

async def _get_installed_updates_action(params: dict) -> Any:
    """List installed Windows updates via PowerShell."""
    success, output = await _run_ps(
        "Get-HotFix | Select-Object HotFixID, Description, InstalledOn | "
        "Sort-Object InstalledOn -Descending | "
        "Select-Object -First 50 | ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"updates": data, "count": len(data)}
        except json.JSONDecodeError:
            pass
    return {"updates": [], "raw": output}


# ══════════════════════════════════════════════════════════════════════════════
# DELETE SYSTEM ENVIRONMENT VARIABLE
# ══════════════════════════════════════════════════════════════════════════════

async def _delete_system_env_action(params: dict) -> Any:
    """Delete a system environment variable."""
    name = params.get("name", "")
    if not name:
        raise RuntimeError("No variable name provided")
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, SYSTEM_ENV_KEY, 0, winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, name)
        # Broadcast change
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None,
        )
        os.environ.pop(name, None)
        return {"deleted": name, "target": "Machine"}
    except FileNotFoundError:
        return {"error": f"Variable '{name}' not found"}
    except PermissionError:
        return {"error": "Permission denied — run as Admin"}


# ══════════════════════════════════════════════════════════════════════════════
# POWERSHELL / CMD FALLBACK METHODS
# ══════════════════════════════════════════════════════════════════════════════

async def _cancel_shutdown_powershell(params: dict) -> Any:
    """Method 2: Cancel shutdown via PowerShell."""
    success, output = await _run_ps("Stop-ScheduledTask -TaskName 'Shutdown' -ErrorAction SilentlyContinue")
    return {"action": "cancel_shutdown"}


async def _get_ip_config_powershell(params: dict) -> Any:
    """Method 2: Get IP config via ipconfig."""
    success, output = await _run_cmd(["ipconfig", "/all"])
    if success and output:
        addresses = []
        for line in output.splitlines():
            if "IPv4" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    addresses.append(parts[1].strip())
        return {"addresses": [{"IPAddress": a} for a in addresses]}
    return {"addresses": []}


async def _flush_dns_cmd(params: dict) -> Any:
    """Method 2: Flush DNS via PowerShell."""
    success, output = await _run_ps("Clear-DnsClientCache")
    return {"success": success}


async def _get_env_powershell(params: dict) -> Any:
    """Method 2: Get env var via PowerShell."""
    name = params.get("name", "")
    if name:
        success, output = await _run_ps(f"$env:{name}")
        if success and output:
            return {"name": name, "value": output}
    else:
        success, output = await _run_ps("Get-ChildItem env: | Select-Object Name, Value | ConvertTo-Json -Compress")
        if success and output:
            import json
            try:
                data = json.loads(output)
                if isinstance(data, dict):
                    data = [data]
                return {"count": len(data), "vars": {d["Name"]: d["Value"] for d in data[:50]}}
            except json.JSONDecodeError:
                pass
    return {"name": name, "value": None}


async def _set_user_env_powershell(params: dict) -> Any:
    """Method 2: Set user env var via PowerShell."""
    name = params.get("name", "")
    value = params.get("value", "")
    success, output = await _run_ps(f"[Environment]::SetEnvironmentVariable('{name}', '{value}', 'User')")
    if not success:
        raise RuntimeError(output)
    os.environ[name] = value
    return {"name": name, "value": value, "target": "User"}


async def _get_system_info_powershell(params: dict) -> Any:
    """Method 2: Get system info via systeminfo."""
    success, output = await _run_cmd(["systeminfo"], timeout=15)
    if success and output:
        info = {}
        for line in output.splitlines():
            if "OS Name" in line:
                info["os"] = line.split(":", 1)[1].strip()
            elif "Total Physical Memory" in line:
                info["ram"] = line.split(":", 1)[1].strip()
            elif "Processor(s)" in line:
                info["processor"] = line.split(":", 1)[1].strip()
            elif "System Boot Time" in line:
                info["boot_time"] = line.split(":", 1)[1].strip()
        return info
    return {}


async def _get_ram_powershell(params: dict) -> Any:
    """Method 2: Get RAM usage via systeminfo."""
    success, output = await _run_ps(
        "$os = Get-CimInstance Win32_OperatingSystem; "
        "@{total_gb=[math]::Round($os.TotalVisibleMemorySize/1MB,2); "
        "free_gb=[math]::Round($os.FreePhysicalMemory/1MB,2)} | ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            data = json.loads(output)
            total = data.get("total_gb", 0)
            free = data.get("free_gb", 0)
            used = total - free
            return {"total_gb": total, "used_gb": round(used, 2), "available_gb": free, "percent": round(used / total * 100, 1) if total else 0}
        except json.JSONDecodeError:
            pass
    return {"total_gb": 0, "used_gb": 0, "available_gb": 0, "percent": 0}


async def _get_disk_powershell(params: dict) -> Any:
    """Method 2: Get disk usage via wmic."""
    success, output = await _run_cmd(["wmic", "logicaldisk", "get", "size,freespace,caption"]) 
    if success and output:
        disks = []
        for line in output.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 3:
                try:
                    free = int(parts[0]) if parts[0].isdigit() else 0
                    total = int(parts[1]) if parts[1].isdigit() else 0
                    disks.append({
                        "device": parts[2],
                        "total_gb": round(total / (1024**3), 1),
                        "free_gb": round(free / (1024**3), 1),
                        "percent": round((total - free) / total * 100, 1) if total else 0,
                    })
                except (ValueError, IndexError):
                    continue
        return {"disks": disks}
    return {"disks": []}


async def _get_uptime_powershell(params: dict) -> Any:
    """Method 2: Get uptime via systeminfo."""
    success, output = await _run_ps(
        "$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; "
        "$uptime = (Get-Date) - $boot; "
        "@{hours=$uptime.Hours; minutes=$uptime.Minutes; boot_time=$boot} | ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"hours": 0, "minutes": 0}


async def _get_battery_powershell(params: dict) -> Any:
    """Method 2: Get battery via powercfg."""
    success, output = await _run_ps(
        "$battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue; "
        "if ($battery) {{ @{has_battery=$true; percent=$battery.EstimatedChargeRemaining; plugged=($battery.BatteryStatus -ge 2)} | ConvertTo-Json -Compress }} "
        "else {{ @{has_battery=$false} | ConvertTo-Json -Compress }}"
    )
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"has_battery": False}


async def _connect_wifi_netsh(params: dict) -> Any:
    """Method 2: Connect WiFi via netsh."""
    ssid = params["ssid"]
    password = params.get("password", "")
    if password:
        success, output = await _run_cmd(["netsh", "wlan", "connect", f"name={ssid}", f"password={password}"])
    else:
        success, output = await _run_cmd(["netsh", "wlan", "connect", f"name={ssid}"])
    if not success:
        raise RuntimeError(output)
    return {"connected": ssid}


async def _get_os_info_powershell(params: dict) -> Any:
    """Method 2: Get OS info via wmic."""
    success, output = await _run_cmd(["wmic", "os", "get", "Caption,Version,BuildNumber,OSArchitecture"]) 
    if success and output:
        lines = output.strip().splitlines()
        if len(lines) >= 2:
            return {"caption": lines[1].strip(), "source": "wmic"}
    return {"os": f"{platform.system()} {platform.release()}"}


# ══════════════════════════════════════════════════════════════════════════════
# TIME / DATE
# ══════════════════════════════════════════════════════════════════════════════

async def _get_time_python(params: dict) -> Any:
    """Method 1: Get current time via Python."""
    return {"time": datetime.now().strftime("%I:%M %p")}


async def _get_time_powershell(params: dict) -> Any:
    """Method 2: Get current time via PowerShell."""
    success, output = await _run_ps("Get-Date -Format 'hh:mm tt'")
    if success and output:
        return {"time": output.strip()}
    return {"time": datetime.now().strftime("%I:%M %p")}


async def _get_date_python(params: dict) -> Any:
    """Method 1: Get current date via Python."""
    return {"date": datetime.now().strftime("%A, %B %d, %Y")}


async def _get_date_powershell(params: dict) -> Any:
    """Method 2: Get current date via PowerShell."""
    success, output = await _run_ps("Get-Date -Format 'dddd, MMMM dd, yyyy'")
    if success and output:
        return {"date": output.strip()}
    return {"date": datetime.now().strftime("%A, %B %d, %Y")}


# ══════════════════════════════════════════════════════════════════════════════
# RUN POWERSHELL
# ══════════════════════════════════════════════════════════════════════════════

async def _run_powershell_action(params: dict) -> Any:
    """Method 1: Run a PowerShell command."""
    command = params.get("command", "")
    if not command:
        raise RuntimeError("No command provided")
    success, output = await _run_ps(command, timeout=30)
    return {"output": output, "success": success}


async def _run_powershell_cmd(params: dict) -> Any:
    """Method 2: Run via cmd /c powershell."""
    command = params.get("command", "")
    if not command:
        raise RuntimeError("No command specified")
    success, output = await _run_cmd(["powershell", "-NoProfile", "-Command", command])
    if not success:
        raise RuntimeError(output)
    return {"output": output}


# ══════════════════════════════════════════════════════════════════════════════
# HARDWARE DEVICES
# ══════════════════════════════════════════════════════════════════════════════

async def _list_usb_devices_action(params: dict) -> Any:
    """Method 1: List USB devices via PnP."""
    success, output = await _run_ps(
        "Get-PnpDevice | Where-Object {$_.InstanceId -like 'USB\\*' -and $_.Status -eq 'OK'} | "
        "Select-Object FriendlyName, InstanceId | ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"devices": data, "count": len(data)}
        except json.JSONDecodeError:
            pass
    return {"devices": [], "count": 0}


async def _list_usb_devices_powershell(params: dict) -> Any:
    """Method 2: List USB devices via wmic."""
    success, output = await _run_cmd(["wmic", "path", "Win32_USBControllerDevice", "get", "Dependent"]) 
    if success and output:
        devices = [line.strip() for line in output.splitlines()[1:] if line.strip()]
        return {"devices": devices, "count": len(devices)}
    return {"devices": [], "count": 0}


async def _get_audio_devices_powershell_action(params: dict) -> Any:
    """List audio devices via WMI."""
    success, output = await _run_ps(
        "Get-WmiObject Win32_SoundDevice | Select-Object Name, Status | ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"devices": data, "count": len(data)}
        except json.JSONDecodeError:
            pass
    return {"devices": [], "count": 0}


async def _list_printers_action(params: dict) -> Any:
    """Method 1: List printers via PowerShell Get-Printer."""
    success, output = await _run_ps(
        "Get-Printer | Select-Object Name, DriverName, PrinterStatus | ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"printers": data, "count": len(data)}
        except json.JSONDecodeError:
            pass
    return {"printers": [], "count": 0}


async def _list_printers_powershell(params: dict) -> Any:
    """Method 2: List printers via wmic."""
    success, output = await _run_cmd(["wmic", "printer", "get", "name,drivernames,status"])
    if success and output:
        printers = [line.strip() for line in output.splitlines()[1:] if line.strip()]
        return {"printers": printers, "count": len(printers)}
    return {"printers": [], "count": 0}


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL (Outlook COM)
# ══════════════════════════════════════════════════════════════════════════════

async def _send_email_outlook(params: dict) -> Any:
    """Method 1: Send email via Outlook COM."""
    import win32com.client
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = params.get("to", "")
        mail.Subject = params.get("subject", "")
        mail.Body = params.get("body", "")
        mail.Send()
        return {"sent": True, "to": params.get("to", "")}
    except Exception:
        raise RuntimeError("Outlook not available or not configured")


async def _send_email_powershell(params: dict) -> Any:
    """Method 2: Send email via PowerShell (open Outlook compose window)."""
    to = params.get("to", "")
    subject = params.get("subject", "")
    body = params.get("body", "")
    ps = (
        f"$o = New-Object -ComObject Outlook.Application; "
        f"$m = $o.CreateItem(0); "
        f"$m.To='{to}'; $m.Subject='{subject}'; "
        f"$m.Body='{body}'; $m.Display()"
    )
    success, output = await _run_ps(ps)
    if not success:
        raise RuntimeError(f"PowerShell email failed: {output}")
    return {"displayed": True, "to": to}


# ══════════════════════════════════════════════════════════════════════════════
# REMINDER (in-memory)
# ══════════════════════════════════════════════════════════════════════════════

async def _set_reminder_action(params: dict) -> Any:
    """Set a reminder (returns confirmation — actual scheduling is backend responsibility)."""
    msg = params.get("message", "")
    minutes = params.get("minutes", 5)
    return {"reminder": msg, "minutes": minutes, "scheduled": True}


# ══════════════════════════════════════════════════════════════════════════════
# INTERNET TEST
# ══════════════════════════════════════════════════════════════════════════════

async def _test_internet_ping(params: dict) -> Any:
    """Method 1: Test internet via ping."""
    import socket
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return {"connected": True}
    except (socket.timeout, OSError):
        return {"connected": False}


async def _test_internet_powershell(params: dict) -> Any:
    """Method 2: Test internet via PowerShell Test-Connection."""
    success, output = await _run_ps(
        "Test-Connection -ComputerName 8.8.8.8 -Count 1 -Quiet | "
        "ForEach-Object { if($_){'Connected to internet'}else{'No internet connection'} }"
    )
    if success and output:
        return {"connected": "internet" in output.lower()}
    return {"connected": False}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION HANDLER (main entry point)
# ══════════════════════════════════════════════════════════════════════════════

# Action → (methods list, verifier)
ACTION_MAP: dict[str, tuple[list, Any]] = {
    # Audio
    "set_volume":       ([_set_volume_pycaw, _set_volume_powershell], Verifiers.volume_set),
    "get_volume":       ([_get_volume_pycaw, _get_volume_powershell], None),
    "volume_up":        ([_volume_up_pycaw, _volume_up_powershell], Verifiers.volume_set),
    "volume_down":      ([_volume_down_pycaw, _volume_down_powershell], Verifiers.volume_set),
    "mute":             ([_mute_pycaw, _mute_powershell], None),
    "unmute":           ([_unmute_powershell, _unmute_pycaw], None),

    # Power
    "shutdown":         ([_shutdown_exitwin32, _shutdown_cmd, _shutdown_powershell], None),
    "restart":          ([_reboot_exitwin32, _reboot_cmd, _reboot_powershell], None),
    "sleep":            ([_sleep_set_suspend, _sleep_powershell], None),
    "hibernate":        ([_hibernate_set_suspend, _hibernate_powershell], None),
    "lock":             ([_lock_win32, _lock_rundll32], None),
    "cancel_shutdown":  ([_cancel_shutdown, _cancel_shutdown_powershell], None),

    # Display
    "set_brightness":   ([_set_brightness_sbc, _set_brightness_wmi], Verifiers.brightness_set),
    "get_brightness":   ([_get_brightness_sbc, _get_brightness_wmi], None),
    "change_resolution": ([_change_resolution_win32api, _change_resolution_powershell], None),
    "get_displays":     ([_get_displays_win32api, _get_displays_powershell], None),

    # Network
    "get_ip_config":    ([_get_ip_config, _get_ip_config_powershell], None),
    "get_network_info": ([_get_network_info], None),
    "toggle_wifi":      ([_toggle_wifi_netsh, _toggle_wifi_powershell], None),
    "flush_dns":        ([_flush_dns, _flush_dns_cmd], None),
    "get_wifi_password": ([_get_wifi_password], None),

    # Environment
    "get_env":          ([_get_env_var, _get_env_powershell], Verifiers.result_has_key),
    "set_system_env":   ([_set_system_env], None),
    "set_user_env":     ([_set_user_env, _set_user_env_powershell], None),
    "list_env":         ([_list_env_vars, _get_env_powershell], None),

    # Hardware & System
    "get_system_info":  ([_get_system_info, _get_system_info_powershell], None),
    "get_ram_usage":    ([_get_ram_usage, _get_ram_powershell], None),
    "get_disk_usage":   ([_get_disk_usage, _get_disk_powershell], None),
    "get_uptime":       ([_get_uptime, _get_uptime_powershell], None),
    "get_cpu_temp":     ([_get_cpu_temp], None),
    "get_hardware_info": ([_get_hardware_info], None),
    "get_battery":      ([_get_battery_info, _get_battery_powershell], None),
    "connect_wifi":     ([_connect_wifi_action, _connect_wifi_netsh], None),
    "disconnect_wifi":  ([_disconnect_wifi_action], None),
    "add_firewall_rule": ([_add_firewall_rule_action], None),
    "remove_firewall_rule": ([_remove_firewall_rule_action], None),
    "get_public_ip":    ([_get_public_ip_action], None),
    # --- Phase 7 additions ---
    "logoff":              ([_logoff_action], None),
    "get_audio_devices":   ([_get_audio_devices_action], None),
    "set_default_device":  ([_set_default_device_action], None),
    "rotate_display":      ([_rotate_display_action], None),
    "enable_adapter":      ([_enable_adapter_action], None),
    "disable_adapter":     ([_disable_adapter_action], None),
    "list_wifi_networks":  ([_list_wifi_networks_action], None),
    "get_user_env":        ([_get_user_env_action], None),
    "get_system_env":      ([_get_system_env_action], None),
    "get_os_info":         ([_get_os_info_action, _get_os_info_powershell], None),
    "watch_process":       ([_watch_process_action], None),
    "watch_usb":           ([_watch_usb_action], None),
    "watch_file_events":   ([_watch_file_events_action], None),
    # --- Architecture-compliant missing actions ---
    "get_installed_updates": ([_get_installed_updates_action], None),
    "delete_system_env":     ([_delete_system_env_action], None),
    # --- time/date ---
    "get_time":    ([_get_time_python, _get_time_powershell], None),
    "get_date":    ([_get_date_python, _get_date_powershell], None),
    # --- run_powershell ---
    "run_powershell": ([_run_powershell_action, _run_powershell_cmd], None),
    # --- hardware devices ---
    "list_usb_devices":   ([_list_usb_devices_action, _list_usb_devices_powershell], None),
    "list_audio_devices": ([_get_audio_devices_powershell_action], None),
    "list_printers":      ([_list_printers_action, _list_printers_powershell], None),
    # --- email (Outlook COM) ---
    "send_email":  ([_send_email_outlook, _send_email_powershell], None),
    # --- reminder ---
    "set_reminder": ([_set_reminder_action], None),
    # --- internet test ---
    "test_internet": ([_test_internet_ping, _test_internet_powershell], None),
}


# ── Public Handler ───────────────────────────────────────────────────────────

_chain = FallbackChain()


async def handler(action: str, params: dict[str, Any]) -> Result:
    """L8 System layer handler — routes actions to their fallback chains.

    This is registered with the CommandBus and called for every
    system-level command.
    """
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown system action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"system.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("system", action),
        escalation_fn=create_escalation_fn("system", action),
    )

    suggested = None
    if not success and error:
        suggested = f"Try running as Administrator or SYSTEM. Error: {error[:120]}"

    return Result(
        command_id=params.get("id", ""),
        success=success,
        data=data,
        error=error if not success else None,
        verified=verifier is not None and success,
        method_used=method_used,
        suggested_action=suggested,
    )
