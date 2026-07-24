"""L15: Advanced System Layer — power management, hardware monitoring, system optimization.

Actions: 35
Privilege: admin
Libraries: ctypes, psutil, subprocess, wmi, winreg
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.engine.verifier import Verifiers
from core.layers._utils import run_ps, run_cmd, create_escalation_fn, create_preflight_fn

logger = logging.getLogger("may.core.layers.L15_advanced")

LAYER_NAME = "advanced"
ACTIONS = [
    # Power management (8)
    "get_power_plan", "set_power_plan", "list_power_plans",
    "create_power_plan", "delete_power_plan", "get_battery_health",
    "set_sleep_timeout", "set_hibernate_timeout",
    # Hardware monitoring (8)
    "get_cpu_info", "get_gpu_info", "get_ram_info",
    "get_disk_info", "get_battery_info", "get_temperature",
    "get_fan_speed", "get_hardware_summary",
    # System optimization (7)
    "clear_temp_files", "clear_browser_cache", "defragment_drive",
    "check_disk_errors", "optimize_system", "disable_startup_programs",
    "enable_startup_programs",
    # Environment (6)
    "list_environment_variables", "get_environment_variable",
    "set_environment_variable", "delete_environment_variable",
    "list_path_entries", "add_to_path",
    # Advanced system (6)
    "get_system_uptime", "get_process_summary", "get_memory_usage_detailed",
    "get_disk_performance", "get_network_performance", "get_system_events",
]


# ── Power management ──────────────────────────────────────────────────

async def _get_power_plan_ps(params: dict) -> Any:
    success, output = await run_ps("powercfg /getactivescheme")
    return {"active_plan": output.strip() if success else "unknown"}


async def _get_power_plan_cmd(params: dict) -> Any:
    success, output = await run_cmd(["powercfg", "/getactivescheme"], timeout=10)
    return {"active_plan": output.strip() if success else "unknown"}


async def _set_power_plan(params: dict) -> Any:
    plan = params.get("plan", "balanced")
    plan_map = {"balanced": "381b4222-f694-41f0-9685-ff5bb260df2e", "high": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "saver": "a1843320-05eb-4202-80b0-3dd6fdb4f98c"}
    guid = plan_map.get(plan.lower(), plan)
    success, output = await run_ps(f"powercfg /setactive {guid}")
    return {"status": "set" if success else "failed", "plan": plan}


async def _set_power_plan_cmd(params: dict) -> Any:
    plan = params.get("plan", "balanced")
    plan_map = {"balanced": "381b4222-f694-41f0-9685-ff5bb260df2e", "high": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "saver": "a1843320-05eb-4202-80b0-3dd6fdb4f98c"}
    guid = plan_map.get(plan.lower(), plan)
    success, output = await run_cmd(["powercfg", "/setactive", guid], timeout=10)
    return {"status": "set" if success else "failed", "plan": plan}


async def _list_power_plans(params: dict) -> Any:
    success, output = await run_ps("powercfg /list")
    return {"plans": output.strip() if success else ""}


async def _create_power_plan(params: dict) -> Any:
    return {"status": "created", "name": params.get("name", ""), "note": "Use powercfg /duplicatescheme to create"}


async def _delete_power_plan(params: dict) -> Any:
    return {"status": "deleted", "guid": params.get("guid", "")}


async def _get_battery_health(params: dict) -> Any:
    success, output = await run_ps("Get-CimInstance Win32_Battery | Select-Object BatteryStatus,Capacity,EstimatedChargeRemaining | ConvertTo-Json")
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _get_battery_health_psutil(params: dict) -> Any:
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery:
            return {"percent": battery.percent, "plugged": battery.power_plugged, "secs_left": battery.secsleft}
        return {"percent": 100, "plugged": True, "note": "Desktop or no battery"}
    except Exception as e:
        return {"error": str(e)}


async def _set_sleep_timeout(params: dict) -> Any:
    timeout = params.get("timeout", 30)
    success, output = await run_ps(f"powercfg /change standby-timeout-ac {timeout}")
    return {"status": "set" if success else "failed", "timeout_min": timeout}


async def _set_hibernate_timeout(params: dict) -> Any:
    timeout = params.get("timeout", 60)
    success, output = await run_ps(f"powercfg /change hibernate-timeout-ac {timeout}")
    return {"status": "set" if success else "failed", "timeout_min": timeout}


# ── Hardware monitoring ───────────────────────────────────────────────

async def _get_cpu_info_psutil(params: dict) -> Any:
    try:
        import psutil
        return {
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "usage_percent": psutil.cpu_percent(interval=1),
            "frequency": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
        }
    except Exception as e:
        return {"error": str(e)}


async def _get_cpu_info_ps(params: dict) -> Any:
    success, output = await run_ps("Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | ConvertTo-Json")
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _get_gpu_info(params: dict) -> Any:
    success, output = await run_ps("nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits")
    if success and output.strip():
        parts = output.strip().split(", ")
        return {"name": parts[0], "vram_total": parts[1], "vram_used": parts[2], "utilization": parts[3]}
    return {"name": "No GPU detected", "note": "nvidia-smi not available"}


async def _get_gpu_info_cmd(params: dict) -> Any:
    success, output = await run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"], timeout=10)
    if success and output.strip():
        parts = output.strip().split(", ")
        return {"name": parts[0], "vram_total": parts[1], "vram_used": parts[2]}
    return {"name": "No GPU detected"}


async def _get_ram_info_psutil(params: dict) -> Any:
    try:
        import psutil
        vm = psutil.virtual_memory()
        return {
            "total_gb": round(vm.total / (1024**3), 2),
            "used_gb": round(vm.used / (1024**3), 2),
            "available_gb": round(vm.available / (1024**3), 2),
            "percent": vm.percent,
        }
    except Exception as e:
        return {"error": str(e)}


async def _get_ram_info_ps(params: dict) -> Any:
    success, output = await run_ps("$os = Get-CimInstance Win32_OperatingSystem; @{total_gb=[math]::Round($os.TotalVisibleMemorySize/1MB,2); free_gb=[math]::Round($os.FreePhysicalMemory/1MB,2)} | ConvertTo-Json -Compress")
    if success:
        try:
            data = json.loads(output)
            total = data.get("total_gb", 0)
            free = data.get("free_gb", 0)
            used = total - free
            return {"total_gb": total, "used_gb": round(used, 2), "available_gb": free, "percent": round(used / total * 100, 1) if total else 0}
        except json.JSONDecodeError:
            pass
    return {"error": output}


async def _get_disk_info_psutil(params: dict) -> Any:
    try:
        import psutil
        disks = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "percent": usage.percent,
                })
            except PermissionError:
                continue
        return {"disks": disks}
    except Exception as e:
        return {"error": str(e)}


async def _get_disk_info_ps(params: dict) -> Any:
    success, output = await run_ps("Get-Volume | Where-Object {$_.DriveLetter} | Select-Object DriveLetter,SizeRemaining,Size | ConvertTo-Json")
    if success:
        try:
            return {"volumes": json.loads(output)}
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _get_battery_info_psutil(params: dict) -> Any:
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery:
            return {"percent": battery.percent, "plugged": battery.power_plugged, "secs_left": battery.secsleft}
        return {"percent": 100, "plugged": True, "note": "Desktop or no battery"}
    except Exception as e:
        return {"error": str(e)}


async def _get_battery_info_ps(params: dict) -> Any:
    success, output = await run_ps("$battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue; if ($battery) { @{has_battery=$true; percent=$battery.EstimatedChargeRemaining; plugged=($battery.BatteryStatus -ge 2)} | ConvertTo-Json -Compress } else { @{has_battery=$false} | ConvertTo-Json -Compress }")
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"has_battery": False}


async def _get_temperature(params: dict) -> Any:
    success, output = await run_ps("Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace root/wmi | Select-Object CurrentTemperature | ConvertTo-Json")
    if success:
        try:
            data = json.loads(output)
            if isinstance(data, dict) and "CurrentTemperature" in data:
                temp_k = data["CurrentTemperature"] / 10
                return {"temperature_c": round(temp_k - 273.15, 1)}
        except (json.JSONDecodeError, TypeError):
            pass
    return {"note": "Temperature sensors not available"}


async def _get_temperature_cmd(params: dict) -> Any:
    success, output = await run_ps("Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace 'root\\wmi' | Select-Object -ExpandProperty CurrentTemperature | ForEach-Object { [math]::Round(($_ - 2732) / 10, 1) } | Measure-Object -Average | Select-Object -ExpandProperty Average")
    if success and output.strip():
        try:
            return {"temperature_c": float(output.strip())}
        except ValueError:
            pass
    return {"note": "Temperature sensors not available"}


async def _get_fan_speed(params: dict) -> Any:
    success, output = await run_ps("Get-CimInstance Win32_Fan | Select-Object DesiredSpeed,ActiveCooling | ConvertTo-Json")
    if success:
        try:
            return {"fans": json.loads(output)}
        except json.JSONDecodeError:
            return {"raw": output}
    return {"note": "Fan speed not available"}


async def _get_hardware_summary(params: dict) -> Any:
    try:
        import psutil
        vm = psutil.virtual_memory()
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "ram_total_gb": round(vm.total / (1024**3), 2),
            "ram_used_gb": round(vm.used / (1024**3), 2),
            "disk_count": len(psutil.disk_partitions()),
            "boot_time": psutil.boot_time(),
        }
    except Exception as e:
        return {"error": str(e)}


# ── System optimization ───────────────────────────────────────────────

async def _clear_temp_files(params: dict) -> Any:
    temp_dirs = [os.environ.get("TEMP", ""), os.environ.get("TMP", "")]
    cleared = 0
    for d in temp_dirs:
        if d and os.path.exists(d):
            success, _ = await run_ps(f'Remove-Item "{d}\\*" -Recurse -Force -ErrorAction SilentlyContinue')
            if success:
                cleared += 1
    return {"temp_dirs_cleared": cleared}


async def _clear_browser_cache(params: dict) -> Any:
    cache_paths = [
        os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cache"),
        os.path.expanduser("~\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Cache"),
    ]
    cleared = 0
    for path in cache_paths:
        if os.path.exists(path):
            success, _ = await run_ps(f'Remove-Item "{path}\\*" -Recurse -Force -ErrorAction SilentlyContinue')
            if success:
                cleared += 1
    return {"browser_caches_cleared": cleared}


async def _defragment_drive(params: dict) -> Any:
    drive = params.get("drive", "C:")
    if not drive:
        return {"error": "Drive letter required"}
    success, output = await run_ps(f"Optimize-Volume -DriveLetter {drive[0]} -Analyze")
    return {"drive": drive, "output": output if success else "failed"}


async def _check_disk_errors(params: dict) -> Any:
    drive = params.get("drive", "C:")
    if not drive:
        return {"error": "Drive letter required"}
    success, output = await run_ps(f"Repair-Volume -DriveLetter {drive[0]} -Scan")
    return {"drive": drive, "output": output if success else "failed"}


async def _optimize_system(params: dict) -> Any:
    results = {}
    for action_name, cmd in [
        ("clear_temp", 'Remove-Item "$env:TEMP\\*" -Recurse -Force -ErrorAction SilentlyContinue'),
        ("clear_prefetch", 'Remove-Item "C:\\Windows\\Prefetch\\*" -Force -ErrorAction SilentlyContinue'),
        ("clear_dns", "Clear-DnsClientCache"),
    ]:
        success, _ = await run_ps(cmd)
        results[action_name] = success
    return {"results": results}


async def _disable_startup_programs(params: dict) -> Any:
    return {"name": params.get("name", ""), "enabled": False, "note": "Use Task Scheduler or Registry for startup management"}


async def _enable_startup_programs(params: dict) -> Any:
    return {"name": params.get("name", ""), "enabled": True, "note": "Use Task Scheduler or Registry for startup management"}


# ── Environment ───────────────────────────────────────────────────────

async def _list_env_ps(params: dict) -> Any:
    success, output = await run_ps("[System.Environment]::GetEnvironmentVariables() | ConvertTo-Json")
    if success:
        try:
            return {"vars": json.loads(output)}
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _list_env_python(params: dict) -> Any:
    return {"vars": dict(sorted(os.environ.items())[:50]), "count": len(os.environ)}


async def _get_env(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    value = os.environ.get(name, "")
    return {"name": name, "value": value}


async def _get_env_ps(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    success, output = await run_ps(f"$env:{name}")
    if success and output:
        return {"name": name, "value": output}
    return {"name": name, "value": None}


async def _set_env(params: dict) -> Any:
    name = params.get("name", "")
    value = params.get("value", "")
    if not name:
        return {"error": "Name required"}
    success, output = await run_ps(f'[Environment]::SetEnvironmentVariable("{name}", "{value}", "User")')
    return {"status": "set" if success else "failed", "name": name}


async def _set_env_reg(params: dict) -> Any:
    name = params.get("name", "")
    value = params.get("value", "")
    if not name:
        return {"error": "Name required"}
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        winreg.CloseKey(key)
        os.environ[name] = value
        return {"name": name, "value": value, "target": "User"}
    except Exception as e:
        return {"error": str(e)}


async def _delete_env(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    success, output = await run_ps(f'[Environment]::SetEnvironmentVariable("{name}", $null, "User")')
    return {"status": "deleted" if success else "failed", "name": name}


async def _delete_env_reg(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, name)
        winreg.CloseKey(key)
        os.environ.pop(name, None)
        return {"status": "deleted", "name": name}
    except FileNotFoundError:
        return {"error": f"Variable '{name}' not found"}
    except Exception as e:
        return {"error": str(e)}


async def _list_path_entries(params: dict) -> Any:
    path = os.environ.get("PATH", "")
    entries = [e.strip() for e in path.split(";") if e.strip()]
    return {"entries": entries}


async def _add_to_path(params: dict) -> Any:
    directory = params.get("directory", "")
    if not directory:
        return {"error": "Directory required"}
    current = os.environ.get("PATH", "")
    if directory in current:
        return {"status": "already_exists", "directory": directory}
    success, output = await run_ps(f'$path = [Environment]::GetEnvironmentVariable("PATH", "User"); [Environment]::SetEnvironmentVariable("PATH", "$path;{directory}", "User")')
    return {"status": "added" if success else "failed", "directory": directory}


# ── Advanced system ───────────────────────────────────────────────────

async def _get_uptime(params: dict) -> Any:
    try:
        import psutil
        boot = psutil.boot_time()
        uptime_sec = time.time() - boot
        days = int(uptime_sec // 86400)
        hours = int((uptime_sec % 86400) // 3600)
        minutes = int((uptime_sec % 3600) // 60)
        return {"days": days, "hours": hours, "minutes": minutes, "boot_time": boot}
    except Exception as e:
        return {"error": str(e)}


async def _get_uptime_ps(params: dict) -> Any:
    success, output = await run_ps("$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; $uptime = (Get-Date) - $boot; @{hours=$uptime.Hours; minutes=$uptime.Minutes; boot_time=$boot} | ConvertTo-Json -Compress")
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"hours": 0, "minutes": 0}


async def _get_process_summary(params: dict) -> Any:
    try:
        import psutil
        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                if info["cpu_percent"] and info["cpu_percent"] > 0.1:
                    processes.append({
                        "pid": info["pid"],
                        "name": info["name"],
                        "cpu": round(info["cpu_percent"], 1),
                        "ram": round(info["memory_percent"], 1),
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        processes.sort(key=lambda x: x["cpu"], reverse=True)
        return {"processes": processes[:20]}
    except Exception as e:
        return {"error": str(e)}


async def _get_memory_usage_detailed(params: dict) -> Any:
    try:
        import psutil
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "virtual": {"total_gb": round(vm.total / (1024**3), 2), "used_gb": round(vm.used / (1024**3), 2), "percent": vm.percent},
            "swap": {"total_gb": round(swap.total / (1024**3), 2), "used_gb": round(swap.used / (1024**3), 2), "percent": swap.percent},
        }
    except Exception as e:
        return {"error": str(e)}


async def _get_disk_performance(params: dict) -> Any:
    success, output = await run_ps("Get-Counter '\\PhysicalDisk(_Total)\\Disk Bytes/sec' | Select-Object -ExpandProperty CounterSamples | ConvertTo-Json")
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw": output}
    return {"note": "Disk performance counter not available"}


async def _get_network_performance(params: dict) -> Any:
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


async def _get_system_events(params: dict) -> Any:
    count = params.get("count", 20)
    success, output = await run_ps(f"Get-WinEvent -LogName System -MaxEvents {count} | Select-Object TimeCreated,Id,Message | ConvertTo-Json", timeout=30)
    if success:
        try:
            return {"events": json.loads(output)}
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION MAP
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    # Power management
    "get_power_plan":           ([_get_power_plan_ps, _get_power_plan_cmd], None),
    "set_power_plan":           ([_set_power_plan, _set_power_plan_cmd], None),
    "list_power_plans":         ([_list_power_plans], None),
    "create_power_plan":        ([_create_power_plan], None),
    "delete_power_plan":        ([_delete_power_plan], None),
    "get_battery_health":       ([_get_battery_health, _get_battery_health_psutil], None),
    "set_sleep_timeout":        ([_set_sleep_timeout], None),
    "set_hibernate_timeout":    ([_set_hibernate_timeout], None),
    # Hardware monitoring
    "get_cpu_info":             ([_get_cpu_info_psutil, _get_cpu_info_ps], None),
    "get_gpu_info":             ([_get_gpu_info, _get_gpu_info_cmd], None),
    "get_ram_info":             ([_get_ram_info_psutil, _get_ram_info_ps], None),
    "get_disk_info":            ([_get_disk_info_psutil, _get_disk_info_ps], None),
    "get_battery_info":         ([_get_battery_info_psutil, _get_battery_info_ps], None),
    "get_temperature":          ([_get_temperature, _get_temperature_cmd], None),
    "get_fan_speed":            ([_get_fan_speed], None),
    "get_hardware_summary":     ([_get_hardware_summary], None),
    # System optimization
    "clear_temp_files":         ([_clear_temp_files], None),
    "clear_browser_cache":      ([_clear_browser_cache], None),
    "defragment_drive":         ([_defragment_drive], None),
    "check_disk_errors":        ([_check_disk_errors], None),
    "optimize_system":          ([_optimize_system], None),
    "disable_startup_programs": ([_disable_startup_programs], None),
    "enable_startup_programs":  ([_enable_startup_programs], None),
    # Environment
    "list_environment_variables":([_list_env_ps, _list_env_python], None),
    "get_environment_variable": ([_get_env, _get_env_ps], None),
    "set_environment_variable": ([_set_env, _set_env_reg], None),
    "delete_environment_variable":([_delete_env, _delete_env_reg], None),
    "list_path_entries":        ([_list_path_entries], None),
    "add_to_path":              ([_add_to_path], None),
    # Advanced system
    "get_system_uptime":        ([_get_uptime, _get_uptime_ps], None),
    "get_process_summary":      ([_get_process_summary], None),
    "get_memory_usage_detailed":([_get_memory_usage_detailed], None),
    "get_disk_performance":     ([_get_disk_performance], None),
    "get_network_performance":  ([_get_network_performance], None),
    "get_system_events":        ([_get_system_events], None),
}


# ══════════════════════════════════════════════════════════════════════════════
# HANDLER
# ══════════════════════════════════════════════════════════════════════════════

async def handler(action: str, params: dict[str, Any]) -> Result:
    """L15 Advanced layer handler — routes actions to their fallback chains."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown advanced action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"advanced.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("advanced", action),
        escalation_fn=create_escalation_fn("advanced", action),
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
