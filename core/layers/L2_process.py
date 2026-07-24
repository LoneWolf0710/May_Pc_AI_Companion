"""Layer 2: Process Control — Launch, kill, suspend, inspect.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 4:

Libraries: psutil, subprocess, win32process, win32api, win32con, ctypes.ntdll

Fallback chains try 5 methods per action.
"""

from __future__ import annotations

import os
import asyncio
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.engine.verifier import Verifiers
from core.layers._utils import run_ps, run_cmd, create_escalation_fn, create_preflight_fn

import logging
logger = logging.getLogger("may.core.layers.L2_process")


# ══════════════════════════════════════════════════════════════════════════════
# LIST / INFO
# ══════════════════════════════════════════════════════════════════════════════

async def _list_psutil(params: dict) -> Any:
    """List running processes via psutil."""
    import psutil
    sort_by = params.get("sort", "cpu")
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "memory_info"]):
        try:
            info = p.info
            mem_mb = info.get("memory_info")
            procs.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu_percent": info.get("cpu_percent", 0),
                "memory_percent": round(info.get("memory_percent", 0), 1),
                "memory_mb": round(mem_mb.rss / 1024 / 1024, 1) if mem_mb else 0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    key = "memory_percent" if sort_by == "memory" else "cpu_percent"
    procs.sort(key=lambda x: x.get(key, 0), reverse=True)
    return {"processes": procs[:params.get("max_results", 50)], "count": len(procs)}


async def _get_info_psutil(params: dict) -> Any:
    """Get detailed info about a process."""
    import psutil
    name = params.get("name", "")
    pid = params.get("pid")
    found = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "memory_info", "status", "exe"]):
        try:
            info = p.info
            if pid and info["pid"] == pid:
                found.append(_format_proc_info(info))
            elif name and name.lower() in info.get("name", "").lower():
                found.append(_format_proc_info(info))
            if len(found) >= 5:
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {"processes": found}


def _format_proc_info(info: dict) -> dict:
    from datetime import datetime
    mem = info.get("memory_info")
    return {
        "pid": info["pid"],
        "name": info["name"],
        "status": info.get("status"),
        "cpu_percent": info.get("cpu_percent", 0),
        "memory_mb": round(mem.rss / 1024 / 1024, 1) if mem else 0,
        "exe": info.get("exe"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# KILL PROCESS — 5-method fallback
# ══════════════════════════════════════════════════════════════════════════════

async def _kill_psutil(params: dict) -> Any:
    """Method 1: psutil.Process.kill()."""
    import psutil
    pid = params.get("pid")
    name = params.get("name", "")
    killed = 0
    if pid:
        psutil.Process(pid).kill()
        killed = 1
    elif name:
        for p in psutil.process_iter(["name"]):
            if name.lower() in p.info["name"].lower():
                p.kill()
                killed += 1
    return {"killed": killed}


async def _kill_win32api(params: dict) -> Any:
    """Method 2: win32api.TerminateProcess."""
    import win32api
    pid = params.get("pid")
    if not pid:
        raise RuntimeError("PID required for win32api kill")
    handle = win32api.OpenProcess(0x1F0FFF, False, pid)
    win32api.TerminateProcess(handle, 0)
    return {"killed": 1}


async def _kill_taskkill(params: dict) -> Any:
    """Method 3: taskkill /F /PID."""
    pid = params.get("pid")
    name = params.get("name", "")
    if pid:
        success, output = await run_cmd(["taskkill", "/F", "/PID", str(pid)])
    elif name:
        success, output = await run_cmd(["taskkill", "/F", "/IM", f"{name}.exe"])
    else:
        raise RuntimeError("PID or name required")
    return {"killed": 1}


async def _kill_taskkill_tree(params: dict) -> Any:
    """Method 4: taskkill /F /T (kills entire process tree)."""
    pid = params.get("pid")
    name = params.get("name", "")
    if pid:
        success, output = await run_cmd(["taskkill", "/F", "/T", "/PID", str(pid)])
    elif name:
        success, output = await run_cmd(["taskkill", "/F", "/T", "/IM", f"{name}.exe"])
    else:
        raise RuntimeError("PID or name required")
    return {"killed": 1}


async def _kill_max_access(params: dict) -> Any:
    """Method 5: Open with maximum access rights then TerminateProcess.

    After privilege escalation (SeDebugPrivilege), this opens the process
    with PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION for maximum
    compatibility with protected processes.
    """
    import ctypes
    pid = params.get("pid")
    if not pid:
        raise RuntimeError("PID required for max-access kill")
    PROCESS_TERMINATE = 0x0001
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid)
    )
    if not handle:
        raise RuntimeError(f"Cannot open process {pid} with max access")
    try:
        result = ctypes.windll.kernel32.TerminateProcess(handle, 1)
        if not result:
            raise RuntimeError(f"TerminateProcess failed for {pid}")
        return {"killed": 1, "method": "max_access"}
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


# ══════════════════════════════════════════════════════════════════════════════
# LAUNCH PROCESS — 3-method fallback
# ══════════════════════════════════════════════════════════════════════════════

async def _launch_subprocess(params: dict) -> Any:
    """Method 1: subprocess.Popen."""
    cmd = params.get("command") or params.get("cmd")
    if not cmd:
        raise RuntimeError("command parameter required")
    proc = subprocess.Popen(
        cmd, shell=params.get("shell", False),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return {"pid": proc.pid, "command": cmd}


async def _launch_powershell(params: dict) -> Any:
    """Method 2: PowerShell Start-Process."""
    cmd = params.get("command") or params.get("cmd")
    if not cmd:
        raise RuntimeError("command parameter required")
    success, output = await run_ps(f"Start-Process '{cmd}' -PassThru | Select-Object -ExpandProperty Id")
    pid = int(output) if output.isdigit() else None
    return {"pid": pid, "command": cmd}


async def _launch_shell(params: dict) -> Any:
    """Method 3: subprocess.run with cmd /c start (safe, no os.system)."""
    import subprocess as _sub
    cmd = params.get("command") or params.get("cmd")
    if not cmd:
        raise RuntimeError("command parameter required")
    _sub.Popen(["cmd", "/c", "start", "", cmd],
               stdout=_sub.DEVNULL, stderr=_sub.DEVNULL)
    return {"command": cmd}


# ══════════════════════════════════════════════════════════════════════════════
# SUSPEND / RESUME
# ══════════════════════════════════════════════════════════════════════════════

async def _suspend_ctypes(params: dict) -> Any:
    """Suspend process via NtSuspendProcess."""
    import ctypes
    pid = params["pid"]
    ntdll = ctypes.WinDLL("ntdll.dll")
    handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)
    ntdll.NtSuspendProcess(handle)
    ctypes.windll.kernel32.CloseHandle(handle)
    return {"suspended": pid}


async def _resume_ctypes(params: dict) -> Any:
    """Resume process via NtResumeProcess."""
    import ctypes
    pid = params["pid"]
    ntdll = ctypes.WinDLL("ntdll.dll")
    handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)
    ntdll.NtResumeProcess(handle)
    ctypes.windll.kernel32.CloseHandle(handle)
    return {"resumed": pid}


# ══════════════════════════════════════════════════════════════════════════════
# SET PRIORITY
# ══════════════════════════════════════════════════════════════════════════════

async def _set_priority_action(params: dict) -> Any:
    """Set process priority."""
    import psutil
    pid = params["pid"]
    priority_name = params.get("priority", "normal")
    priority_map = {
        "low": psutil.BELOW_NORMAL_PRIORITY_CLASS,
        "normal": psutil.NORMAL_PRIORITY_CLASS,
        "high": psutil.HIGH_PRIORITY_CLASS,
        "realtime": psutil.REALTIME_PRIORITY_CLASS,
        "idle": psutil.IDLE_PRIORITY_CLASS,
    }
    p = psutil.Process(pid)
    p.nice(priority_map.get(priority_name, psutil.NORMAL_PRIORITY_CLASS))
    return {"pid": pid, "priority": priority_name}


# ══════════════════════════════════════════════════════════════════════════════
# SET AFFINITY
# ══════════════════════════════════════════════════════════════════════════════

async def _set_affinity_action(params: dict) -> Any:
    """Set process CPU affinity (list of core indices)."""
    import psutil
    pid = params["pid"]
    cores = params.get("cores", [0])  # e.g. [0, 1] for cores 0 and 1
    p = psutil.Process(pid)
    p.cpu_affinity(cores)
    return {"pid": pid, "cores": cores}


# ══════════════════════════════════════════════════════════════════════════════
# GET COMMAND LINE
# ══════════════════════════════════════════════════════════════════════════════

async def _get_command_line_action(params: dict) -> Any:
    """Get the command line of a process."""
    import psutil
    pid = params.get("pid")
    name = params.get("name", "")
    if not pid and name:
        for p in psutil.process_iter(["pid", "name"]):
            if name.lower() in p.info["name"].lower():
                pid = p.info["pid"]
                break
    if not pid:
        return {"error": "Process not found"}
    p = psutil.Process(pid)
    return {"pid": pid, "cmdline": p.cmdline()}


# ══════════════════════════════════════════════════════════════════════════════
# GET PARENT PID
# ══════════════════════════════════════════════════════════════════════════════

async def _get_parent_pid_action(params: dict) -> Any:
    """Get the parent process ID."""
    import psutil
    pid = params["pid"]
    p = psutil.Process(pid)
    parent = p.parent()
    return {"pid": pid, "parent_pid": parent.pid if parent else None, "parent_name": parent.name() if parent else None}


# ══════════════════════════════════════════════════════════════════════════════
# IS PROCESS RUNNING
# ══════════════════════════════════════════════════════════════════════════════

async def _is_process_running_action(params: dict) -> Any:
    """Check if a process is running."""
    import psutil
    pid = params.get("pid")
    name = params.get("name", "")
    if pid:
        return {"running": psutil.pid_exists(pid), "pid": pid}
    if name:
        for p in psutil.process_iter(["pid", "name"]):
            if name.lower() in p.info["name"].lower():
                return {"running": True, "pid": p.info["pid"], "name": p.info["name"]}
        return {"running": False, "name": name}
    return {"error": "Provide pid or name"}


# ══════════════════════════════════════════════════════════════════════════════
# CREATE JOB OBJECT
# ══════════════════════════════════════════════════════════════════════════════

async def _create_job_action(params: dict) -> Any:
    """Create a job object and assign processes to it for resource limits."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    job_handle = kernel32.CreateJobObjectW(None, None)
    pid = params.get("pid")
    if pid:
        h = kernel32.OpenProcess(0x1F0FFF, False, pid)
        kernel32.AssignProcessToJobObject(job_handle, h)
        kernel32.CloseHandle(h)
    return {"job_handle": job_handle, "pid": pid}


# ══════════════════════════════════════════════════════════════════════════════
# GET CPU USAGE
# ══════════════════════════════════════════════════════════════════════════════

async def _get_cpu_usage_action(params: dict) -> Any:
    """Get per-process CPU usage percentage."""
    import psutil
    pid = params.get("pid")
    name = params.get("name", "")
    interval = params.get("interval", 0.5)
    if not pid and name:
        for p in psutil.process_iter(["pid", "name"]):
            if name.lower() in p.info["name"].lower():
                pid = p.info["pid"]
                break
    if not pid:
        return {"error": "Process not found"}
    p = psutil.Process(pid)
    cpu = p.cpu_percent(interval=interval)
    return {"pid": pid, "name": p.name(), "cpu_percent": cpu}


# ══════════════════════════════════════════════════════════════════════════════
# GET MEMORY USAGE
# ══════════════════════════════════════════════════════════════════════════════

async def _get_memory_usage_action(params: dict) -> Any:
    """Get per-process memory usage (RSS, VMS, percent)."""
    import psutil
    pid = params.get("pid")
    name = params.get("name", "")
    if not pid and name:
        for p in psutil.process_iter(["pid", "name"]):
            if name.lower() in p.info["name"].lower():
                pid = p.info["pid"]
                break
    if not pid:
        return {"error": "Process not found"}
    p = psutil.Process(pid)
    mem = p.memory_info()
    return {
        "pid": pid, "name": p.name(),
        "rss_mb": round(mem.rss / (1024**2), 1),
        "vms_mb": round(mem.vms / (1024**2), 1),
        "percent": p.memory_percent(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# GET PROCESS PATH
# ══════════════════════════════════════════════════════════════════════════════

async def _get_process_path_action(params: dict) -> Any:
    """Get the executable path of a process."""
    import psutil
    pid = params.get("pid")
    name = params.get("name", "")
    if not pid and name:
        for p in psutil.process_iter(["pid", "name"]):
            if name.lower() in p.info["name"].lower():
                pid = p.info["pid"]
                break
    if not pid:
        return {"error": "Process not found"}
    p = psutil.Process(pid)
    return {"pid": pid, "name": p.name(), "path": p.exe()}


# ══════════════════════════════════════════════════════════════════════════════
# GET OPEN HANDLES
# ══════════════════════════════════════════════════════════════════════════════

async def _get_open_handles_action(params: dict) -> Any:
    """Get files opened by a process."""
    import psutil
    pid = params["pid"]
    p = psutil.Process(pid)
    try:
        files = p.open_files()
        handles = [{"path": f.path, "fd": f.fd} for f in files]
        return {"pid": pid, "handles": handles[:100], "count": len(handles)}
    except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
        return {"pid": pid, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# GET THREADS
# ══════════════════════════════════════════════════════════════════════════════

async def _get_threads_action(params: dict) -> Any:
    """Get threads of a process."""
    import psutil
    pid = params["pid"]
    p = psutil.Process(pid)
    threads = p.threads()
    result = [{"id": t.id, "user_time": t.user_time, "system_time": t.system_time} for t in threads]
    return {"pid": pid, "threads": result, "count": len(result)}


# ══════════════════════════════════════════════════════════════════════════════
# WAIT FOR EXIT
# ══════════════════════════════════════════════════════════════════════════════

async def _wait_for_exit_action(params: dict) -> Any:
    """Wait for a process to exit."""
    import psutil
    pid = params["pid"]
    timeout = params.get("timeout", 30)
    p = psutil.Process(pid)
    try:
        p.wait(timeout=timeout)
        return {"pid": pid, "exited": True, "code": p.returncode}
    except psutil.TimeoutExpired:
        return {"pid": pid, "exited": False, "timeout": timeout}


# ══════════════════════════════════════════════════════════════════════════════
# GET ENVIRONMENT
# ══════════════════════════════════════════════════════════════════════════════

async def _get_environment_action(params: dict) -> Any:
    """Get environment variables of a process."""
    import psutil
    pid = params.get("pid")
    name = params.get("name", "")
    if not pid and name:
        for p in psutil.process_iter(["pid", "name"]):
            if name.lower() in p.info["name"].lower():
                pid = p.info["pid"]
                break
    if not pid:
        return {"error": "Process not found"}
    p = psutil.Process(pid)
    env = p.environ()
    return {"pid": pid, "env": dict(list(env.items())[:100]), "count": len(env)}


# ══════════════════════════════════════════════════════════════════════════════
# ASSIGN TO JOB
# ══════════════════════════════════════════════════════════════════════════════

async def _assign_to_job_action(params: dict) -> Any:
    """Assign a process to a job object."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    pid = params["pid"]
    job_handle = params.get("job_handle")
    if not job_handle:
        # Create a new job
        job_handle = kernel32.CreateJobObjectW(None, None)
    h = kernel32.OpenProcess(0x1F0FFF, False, pid)
    kernel32.AssignProcessToJobObject(job_handle, h)
    kernel32.CloseHandle(h)
    return {"pid": pid, "job_handle": job_handle}


# ══════════════════════════════════════════════════════════════════════════════
# SET MEMORY LIMIT
# ══════════════════════════════════════════════════════════════════════════════

async def _set_memory_limit_action(params: dict) -> Any:
    """Set memory limit for a process via job object."""
    import ctypes, ctypes.wintypes as wt
    kernel32 = ctypes.windll.kernel32
    pid = params["pid"]
    limit_mb = params.get("limit_mb", 1024)
    limit_bytes = limit_mb * 1024 * 1024

    # Proper JOBOBJECT_BASIC_LIMIT_INFORMATION structure
    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wt.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wt.LARGE_INTEGER),
            ("LimitFlags", wt.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wt.DWORD),
            ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
            ("PriorityClass", wt.DWORD),
            ("SchedulingClass", wt.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    job_handle = kernel32.CreateJobObjectW(None, None)
    limit_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    limit_info.JobMemoryLimit = limit_bytes
    limit_info.BasicLimitInformation.LimitFlags = 0x10  # JOB_OBJECT_LIMIT_JOB_MEMORY
    job_info_class = 9  # JobObjectExtendedLimitInformation
    kernel32.SetInformationJobObject(
        job_handle, job_info_class,
        ctypes.byref(limit_info), ctypes.sizeof(limit_info)
    )
    h = kernel32.OpenProcess(0x1F0FFF, False, pid)
    kernel32.AssignProcessToJobObject(job_handle, h)
    kernel32.CloseHandle(h)
    return {"pid": pid, "limit_mb": limit_mb, "job_handle": job_handle}


# ══════════════════════════════════════════════════════════════════════════════
# SET CPU LIMIT
# ══════════════════════════════════════════════════════════════════════════════

async def _set_cpu_limit_action(params: dict) -> Any:
    """Set CPU rate limit for a process via job object."""
    import ctypes, ctypes.wintypes as wt
    kernel32 = ctypes.windll.kernel32
    pid = params["pid"]
    percent = params.get("percent", 50)  # 1-100%
    rate = percent * 100  # In 100ths of a percent
    job_handle = kernel32.CreateJobObjectW(None, None)
    class JOBOBJECT_CPU_RATE_CONTROL(ctypes.Structure):
        _fields_ = [
            ("ControlFlags", wt.DWORD),
            ("CpuRate", wt.DWORD),
        ]
    cpu_info = JOBOBJECT_CPU_RATE_CONTROL()
    cpu_info.ControlFlags = 0x1  # JOB_OBJECT_CPU_RATE_CONTROL_ENABLE
    cpu_info.CpuRate = rate
    kernel32.SetInformationJobObject(
        job_handle, 3,  # JobObjectCpuRateInformation
        ctypes.byref(cpu_info), ctypes.sizeof(cpu_info)
    )
    h = kernel32.OpenProcess(0x1F0FFF, False, pid)
    kernel32.AssignProcessToJobObject(job_handle, h)
    kernel32.CloseHandle(h)
    return {"pid": pid, "cpu_percent": percent, "job_handle": job_handle}


# ══════════════════════════════════════════════════════════════════════════════
# POWERSHELL / WMI FALLBACK METHODS
# ══════════════════════════════════════════════════════════════════════════════

async def _list_ps_powershell(params: dict) -> Any:
    """Method 2: List processes via PowerShell."""
    ps = ("Get-Process | Select-Object Id, ProcessName, CPU, WorkingSet64 | "
          "Sort-Object CPU -Descending | "
          "Select-Object -First 50 | ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            procs = [{"pid": d.get("Id"), "name": d.get("ProcessName"),
                      "cpu_percent": d.get("CPU", 0),
                      "memory_mb": round((d.get("WorkingSet64", 0)) / (1024*1024), 1)}
                     for d in data]
            return {"processes": procs, "count": len(procs)}
        except json.JSONDecodeError:
            pass
    return {"processes": [], "count": 0}


async def _list_tasklist(params: dict) -> Any:
    """Method 3: List processes via tasklist."""
    success, output = await run_cmd(["tasklist", "/FO", "CSV"]) 
    if success and output:
        lines = output.strip().splitlines()
        procs = []
        for line in lines[1:]:
            parts = line.strip('"').split('","')
            if len(parts) >= 5:
                procs.append({"name": parts[0], "pid": int(parts[1]) if parts[1].isdigit() else 0})
        return {"processes": procs[:50], "count": len(procs)}
    return {"processes": [], "count": 0}


async def _get_info_powershell(params: dict) -> Any:
    """Method 2: Get process info via PowerShell."""
    name = params.get("name", "")
    pid = params.get("pid")
    if pid:
        ps = f"Get-Process -Id {pid} | Select-Object Id, ProcessName, CPU, WorkingSet64, Path | ConvertTo-Json -Compress"
    elif name:
        ps = f"Get-Process -Name '{name}' | Select-Object Id, ProcessName, CPU, WorkingSet64, Path | ConvertTo-Json -Compress"
    else:
        raise RuntimeError("pid or name required")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            procs = [{"pid": d.get("Id"), "name": d.get("ProcessName"),
                      "cpu_percent": d.get("CPU", 0),
                      "path": d.get("Path"),
                      "memory_mb": round((d.get("WorkingSet64", 0)) / (1024*1024), 1)}
                     for d in data[:5]]
            return {"processes": procs}
        except json.JSONDecodeError:
            pass
    return {"processes": []}


async def _suspend_powershell(params: dict) -> Any:
    """Method 2: Suspend via PowerShell."""
    pid = params["pid"]
    success, output = await run_ps(f"$p = Get-Process -Id {pid}; $p.Suspend() 2>$null; if ($LASTEXITCODE -ne 0) {{ 'failed' }} else {{ 'suspended' }}")
    if not success or "failed" in (output or ""):
        # Fallback: use taskkill /suspend not available, use PowerShell debugging
        raise RuntimeError("PowerShell cannot suspend process directly")
    return {"suspended": pid}


async def _resume_powershell(params: dict) -> Any:
    """Method 2: Resume via PowerShell."""
    pid = params["pid"]
    success, output = await run_ps(f"$p = Get-Process -Id {pid}; $p.Resume() 2>$null")
    if not success:
        raise RuntimeError("PowerShell cannot resume process directly")
    return {"resumed": pid}


async def _set_priority_powershell(params: dict) -> Any:
    """Method 2: Set priority via PowerShell."""
    pid = params["pid"]
    priority_name = params.get("priority", "normal")
    ps_map = {"low": "BelowNormal", "normal": "Normal", "high": "High",
              "realtime": "RealTime", "idle": "Idle"}
    ps_priority = ps_map.get(priority_name, "Normal")
    success, output = await run_ps(f"Get-Process -Id {pid} | ForEach-Object {{ $_.PriorityClass = '{ps_priority}' }}")
    if not success:
        raise RuntimeError(output)
    return {"pid": pid, "priority": priority_name}


async def _is_running_powershell(params: dict) -> Any:
    """Method 2: Check process via PowerShell."""
    pid = params.get("pid")
    name = params.get("name", "")
    if pid:
        success, output = await run_ps(f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id")
        running = success and output.strip().isdigit()
        return {"running": running, "pid": pid}
    elif name:
        success, output = await run_ps(f"Get-Process -Name '{name}' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Id")
        running = success and output.strip().isdigit()
        return {"running": running, "name": name, "pid": int(output) if running else None}
    return {"error": "Provide pid or name"}


async def _get_cmdline_powershell(params: dict) -> Any:
    """Method 2: Get command line via PowerShell/WMI."""
    pid = params.get("pid")
    name = params.get("name", "")
    if pid:
        ps = f"Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\" | Select-Object CommandLine | ConvertTo-Json -Compress"
    elif name:
        ps = f"Get-CimInstance Win32_Process | Where-Object {{ $_.Name -like '*{name}*' }} | Select-Object -First 1 CommandLine | ConvertTo-Json -Compress"
    else:
        return {"error": "Provide pid or name"}
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            return {"pid": pid, "cmdline": data.get("CommandLine", "")}
        except json.JSONDecodeError:
            pass
    return {"pid": pid, "cmdline": ""}


async def _get_parent_powershell(params: dict) -> Any:
    """Method 2: Get parent PID via WMI."""
    pid = params["pid"]
    ps = (f"Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\" | "
          f"Select-Object ParentProcessId, Name | ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            parent_pid = data.get("ParentProcessId")
            return {"pid": pid, "parent_pid": parent_pid}
        except json.JSONDecodeError:
            pass
    return {"pid": pid, "parent_pid": None}


async def _get_path_powershell(params: dict) -> Any:
    """Method 2: Get process path via PowerShell."""
    pid = params.get("pid")
    name = params.get("name", "")
    if pid:
        ps = f"Get-Process -Id {pid} | Select-Object -ExpandProperty Path"
    elif name:
        ps = f"Get-Process -Name '{name}' | Select-Object -First 1 -ExpandProperty Path"
    else:
        return {"error": "Provide pid or name"}
    success, output = await run_ps(ps)
    if success and output:
        return {"pid": pid, "path": output}
    return {"pid": pid, "path": ""}


async def _get_cpu_powershell(params: dict) -> Any:
    """Method 2: Get CPU usage via PowerShell."""
    pid = params.get("pid")
    name = params.get("name", "")
    if pid:
        ps = f"Get-Process -Id {pid} | Select-Object CPU | ConvertTo-Json -Compress"
    elif name:
        ps = f"Get-Process -Name '{name}' | Select-Object -First 1 CPU | ConvertTo-Json -Compress"
    else:
        return {"error": "Provide pid or name"}
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            return {"pid": pid, "cpu_percent": data.get("CPU", 0)}
        except json.JSONDecodeError:
            pass
    return {"pid": pid, "cpu_percent": 0}


async def _get_memory_powershell(params: dict) -> Any:
    """Method 2: Get memory usage via PowerShell."""
    pid = params.get("pid")
    name = params.get("name", "")
    if pid:
        ps = f"Get-Process -Id {pid} | Select-Object WorkingSet64 | ConvertTo-Json -Compress"
    elif name:
        ps = f"Get-Process -Name '{name}' | Select-Object -First 1 WorkingSet64 | ConvertTo-Json -Compress"
    else:
        return {"error": "Provide pid or name"}
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            rss = data.get("WorkingSet64", 0)
            return {"pid": pid, "rss_mb": round(rss / (1024**2), 1)}
        except json.JSONDecodeError:
            pass
    return {"pid": pid, "rss_mb": 0}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION HANDLER
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    "list_processes":  ([_list_psutil, _list_ps_powershell, _list_tasklist], None),
    "get_process_info": ([_get_info_psutil, _get_info_powershell], None),
    "find_process_by_name": ([_get_info_psutil, _get_info_powershell], None),
    "kill_process":    ([_kill_psutil, _kill_win32api, _kill_taskkill, _kill_taskkill_tree, _kill_max_access], Verifiers.process_killed),
    "kill_process_tree": ([_kill_taskkill_tree, _kill_psutil], Verifiers.process_killed),
    "launch_process":  ([_launch_subprocess, _launch_powershell, _launch_shell], Verifiers.process_launched),
    "suspend_process": ([_suspend_ctypes, _suspend_powershell], None),
    "resume_process":  ([_resume_ctypes, _resume_powershell], None),
    "set_priority":    ([_set_priority_action, _set_priority_powershell], None),
    "set_affinity":    ([_set_affinity_action], None),
    "get_command_line": ([_get_command_line_action, _get_cmdline_powershell], None),
    "get_parent_pid":  ([_get_parent_pid_action, _get_parent_powershell], None),
    "is_process_running": ([_is_process_running_action, _is_running_powershell], None),
    "create_job_object": ([_create_job_action], None),
    # --- Phase 7 additions ---
    "get_cpu_usage":    ([_get_cpu_usage_action, _get_cpu_powershell], None),
    "get_memory_usage": ([_get_memory_usage_action, _get_memory_powershell], None),
    "get_process_path": ([_get_process_path_action, _get_path_powershell], None),
    "get_open_handles": ([_get_open_handles_action], None),
    "get_threads":      ([_get_threads_action], None),
    "wait_for_exit":    ([_wait_for_exit_action], None),
    "get_environment":  ([_get_environment_action], None),
    "assign_to_job":    ([_assign_to_job_action], None),
    "set_memory_limit": ([_set_memory_limit_action], None),
    "set_cpu_limit":    ([_set_cpu_limit_action], None),
}


async def handler(action: str, params: dict[str, Any]) -> Result:
    """L2 Process layer handler."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown process action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"process.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("process", action),
        escalation_fn=create_escalation_fn("process", action),
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
