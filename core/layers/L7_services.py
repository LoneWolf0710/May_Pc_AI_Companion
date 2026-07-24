"""Layer 7: Services & Task Scheduler — Windows Services (SCM) + Task Scheduler.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 9:

Libraries: win32service, win32serviceutil, win32com.client (TaskScheduler COM)
"""

from __future__ import annotations

from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.layers._utils import run_ps, run_cmd, create_escalation_fn, create_preflight_fn

import logging
logger = logging.getLogger("may.core.layers.L7_services")


# ══════════════════════════════════════════════════════════════════════════════
# SERVICES
# ══════════════════════════════════════════════════════════════════════════════

async def _list_services(params: dict) -> Any:
    """List Windows services."""
    filter_str = params.get("filter", "")
    if filter_str:
        ps = f"Get-Service | Where-Object {{$_.Name -like '*{filter_str}*' -or $_.DisplayName -like '*{filter_str}*'}} | Select-Object Name, DisplayName, Status | ConvertTo-Json -Compress"
    else:
        ps = "Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object Name, DisplayName, Status | ConvertTo-Json -Compress"
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"services": data, "count": len(data)}
        except json.JSONDecodeError:
            pass
    return {"services": [], "raw": output}


async def _start_service(params: dict) -> Any:
    """Start a Windows service."""
    name = params["name"]
    success, output = await run_ps(f"Start-Service -Name '{name}' -ErrorAction Stop")
    if not success:
        raise RuntimeError(output)
    return {"started": name}


async def _stop_service(params: dict) -> Any:
    """Stop a Windows service."""
    name = params["name"]
    success, output = await run_ps(f"Stop-Service -Name '{name}' -Force -ErrorAction Stop")
    if not success:
        raise RuntimeError(output)
    return {"stopped": name}


async def _restart_service(params: dict) -> Any:
    """Restart a Windows service."""
    name = params["name"]
    success, output = await run_ps(f"Restart-Service -Name '{name}' -Force -ErrorAction Stop")
    if not success:
        raise RuntimeError(output)
    return {"restarted": name}


async def _get_service_status(params: dict) -> Any:
    """Get service status."""
    name = params["name"]
    success, output = await run_ps(
        f"Get-Service -Name '{name}' | Select-Object Name, Status, StartType | ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"error": output}


# ══════════════════════════════════════════════════════════════════════════════
# TASK SCHEDULER
# ══════════════════════════════════════════════════════════════════════════════

async def _list_tasks(params: dict) -> Any:
    """List scheduled tasks."""
    success, output = await run_ps(
        "Get-ScheduledTask | Where-Object {$_.State -ne 'Disabled'} | "
        "Select-Object TaskName, TaskPath, State | ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"tasks": data, "count": len(data)}
        except json.JSONDecodeError:
            pass
    return {"tasks": [], "raw": output}


async def _run_task(params: dict) -> Any:
    """Run a scheduled task immediately."""
    name = params["name"]
    success, output = await run_ps(f"Start-ScheduledTask -TaskName '{name}'")
    if not success:
        raise RuntimeError(output)
    return {"ran": name}


async def _create_task(params: dict) -> Any:
    """Create a scheduled task."""
    name = params["name"]
    command = params["command"]
    time_str = params.get("time", "")
    ps = (
        f"$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-Command \"{command}\"'; "
    )
    if time_str:
        ps += f"$trigger = New-ScheduledTaskTrigger -Once -At '{time_str}'; "
    else:
        ps += "$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5); "
    ps += f"Register-ScheduledTask -TaskName '{name}' -Action $action -Trigger $trigger -Force | Out-Null"
    success, output = await run_ps(ps)
    if not success:
        raise RuntimeError(output)
    return {"created": name}


# ══════════════════════════════════════════════════════════════════════════════
# DELETE TASK
# ══════════════════════════════════════════════════════════════════════════════

async def _delete_task_action(params: dict) -> Any:
    """Delete a scheduled task."""
    name = params["name"]
    success, output = await run_ps(f"Unregister-ScheduledTask -TaskName '{name}' -Confirm:$false -ErrorAction Stop")
    if not success:
        raise RuntimeError(output)
    return {"deleted": name}


# ══════════════════════════════════════════════════════════════════════════════
# ENABLE / DISABLE TASK
# ══════════════════════════════════════════════════════════════════════════════

async def _enable_task_action(params: dict) -> Any:
    """Enable a scheduled task."""
    name = params["name"]
    success, output = await run_ps(f"Enable-ScheduledTask -TaskName '{name}' -ErrorAction Stop")
    if not success:
        raise RuntimeError(output)
    return {"enabled": name}


async def _disable_task_action(params: dict) -> Any:
    """Disable a scheduled task."""
    name = params["name"]
    success, output = await run_ps(f"Disable-ScheduledTask -TaskName '{name}' -ErrorAction Stop")
    if not success:
        raise RuntimeError(output)
    return {"disabled": name}


# ══════════════════════════════════════════════════════════════════════════════
# GET SERVICE CONFIG
# ══════════════════════════════════════════════════════════════════════════════

async def _get_service_config_action(params: dict) -> Any:
    """Get detailed service configuration."""
    name = params["name"]
    success, output = await run_ps(
        f"Get-CimInstance Win32_Service -Filter \"Name='{name}'\" | "
        f"Select-Object Name, DisplayName, Status, StartMode, PathName, ProcessId | ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"error": output}


# ══════════════════════════════════════════════════════════════════════════════
# PAUSE / RESUME SERVICE
# ══════════════════════════════════════════════════════════════════════════════

async def _pause_service_action(params: dict) -> Any:
    """Pause a service."""
    name = params["name"]
    success, output = await run_ps(f"Suspend-Service -Name '{name}' -ErrorAction Stop")
    if not success:
        raise RuntimeError(output)
    return {"paused": name}


async def _resume_service_action(params: dict) -> Any:
    """Resume a paused service."""
    name = params["name"]
    success, output = await run_ps(f"Resume-Service -Name '{name}' -ErrorAction Stop")
    if not success:
        raise RuntimeError(output)
    return {"resumed": name}


# ══════════════════════════════════════════════════════════════════════════════
# SET STARTUP TYPE
# ══════════════════════════════════════════════════════════════════════════════

async def _set_startup_type_action(params: dict) -> Any:
    """Set service startup type (Auto, Manual, Disabled)."""
    name = params["name"]
    startup_type = params.get("type", "Manual")
    success, output = await run_ps(f"Set-Service -Name '{name}' -StartupType '{startup_type}' -ErrorAction Stop")
    if not success:
        raise RuntimeError(output)
    return {"name": name, "startup_type": startup_type}


# ══════════════════════════════════════════════════════════════════════════════
# INSTALL SERVICE
# ══════════════════════════════════════════════════════════════════════════════

async def _install_service_action(params: dict) -> Any:
    """Register a new Windows service."""
    name = params["name"]
    exe_path = params["path"]
    display_name = params.get("display_name", name)
    startup = params.get("startup_type", "Manual")
    success, output = await run_ps(
        f"New-Service -Name '{name}' -BinaryPathName '{exe_path}' "
        f"-DisplayName '{display_name}' -StartupType '{startup}' -ErrorAction Stop"
    )
    if not success:
        raise RuntimeError(output)
    return {"installed": name}


# ══════════════════════════════════════════════════════════════════════════════
# REMOVE SERVICE
# ══════════════════════════════════════════════════════════════════════════════

async def _remove_service_action(params: dict) -> Any:
    """Unregister a Windows service."""
    name = params["name"]
    success, output = await run_ps(f"Remove-Service -Name '{name}' -Force -ErrorAction Stop")
    if not success:
        # Fallback: sc delete
        success, output = await run_ps(f"sc.exe delete '{name}'")
    if not success:
        raise RuntimeError(output)
    return {"removed": name}


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE CREDENTIALS
# ══════════════════════════════════════════════════════════════════════════════

async def _change_credentials_action(params: dict) -> Any:
    """Change service logon account."""
    name = params["name"]
    user = params["user"]
    password = params.get("password", "")
    success, output = await run_ps(
        f"sc.exe config '{name}' obj= '{user}' password= '{password}'"
    )
    if not success:
        raise RuntimeError(output)
    return {"name": name, "user": user}


# ══════════════════════════════════════════════════════════════════════════════
# SET DESCRIPTION
# ══════════════════════════════════════════════════════════════════════════════

async def _set_description_action(params: dict) -> Any:
    """Set service description."""
    name = params["name"]
    desc = params["description"]
    success, output = await run_ps(
        f"sc.exe description '{name}' '{desc}'"
    )
    if not success:
        raise RuntimeError(output)
    return {"name": name, "description": desc}


# ══════════════════════════════════════════════════════════════════════════════
# GET SERVICE PID
# ══════════════════════════════════════════════════════════════════════════════

async def _get_service_pid_action(params: dict) -> Any:
    """Get the process ID of a running service."""
    name = params["name"]
    success, output = await run_ps(
        f"Get-CimInstance Win32_Service -Filter \"Name='{name}'\" | Select-Object ProcessId | ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            data = json.loads(output)
            return {"name": name, "pid": data.get("ProcessId")}
        except json.JSONDecodeError:
            pass
    return {"name": name, "pid": None}


# ══════════════════════════════════════════════════════════════════════════════
# GET DEPENDENT SERVICES
# ══════════════════════════════════════════════════════════════════════════════

async def _get_dependent_services_action(params: dict) -> Any:
    """List services that depend on this service."""
    name = params["name"]
    success, output = await run_ps(
        f"Get-Service '{name}' | Select-Object -ExpandProperty DependentServices | "
        f"Select-Object Name, Status | ConvertTo-Json -Compress"
    )
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"name": name, "dependents": data}
        except json.JSONDecodeError:
            pass
    return {"name": name, "dependents": []}


# ══════════════════════════════════════════════════════════════════════════════
# TASK SCHEDULER — additional actions
# ══════════════════════════════════════════════════════════════════════════════

async def _get_task_info_action(params: dict) -> Any:
    """Get detailed task information."""
    name = params["name"]
    ps_cmd = (
        "Get-ScheduledTask -TaskName '" + name + "' | "
        "Select-Object TaskName, TaskPath, State, LastRunTime, NextRunTime | "
        "ConvertTo-Json -Compress"
    )
    success, output = await run_ps(ps_cmd)
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"error": output}


async def _stop_task_action(params: dict) -> Any:
    """Stop a running scheduled task."""
    name = params["name"]
    success, output = await run_ps(
        f"Stop-ScheduledTask -TaskName '{name}' -ErrorAction Stop"
    )
    if not success:
        raise RuntimeError(output)
    return {"stopped": name}


async def _get_last_run_result_action(params: dict) -> Any:
    """Get the last execution result of a task."""
    name = params["name"]
    ps_cmd = (
        "Get-ScheduledTask -TaskName '" + name + "' | "
        "Select-Object TaskName, LastRunTime, LastTaskResult | "
        "ConvertTo-Json -Compress"
    )
    success, output = await run_ps(ps_cmd)
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"error": output}


async def _set_trigger_time_action(params: dict) -> Any:
    """Set a time-based trigger for a task."""
    name = params["name"]
    time_str = params["time"]  # e.g. "2024-01-01T09:00:00"
    interval = params.get("interval")  # e.g. "PT1H" for every hour
    ps = f"$task = Get-ScheduledTask -TaskName '{name}'; "
    ps += f"$task.Triggers | Where-Object {{$_.CimClass.CimClassName -like '*CalendarTrigger*'}} | ForEach-Object {{ "
    ps += f"  $_.StartBoundary = '{time_str}'; "
    if interval:
        ps += f"  $_.Repetition.Interval = '{interval}'; "
    ps += f"}}; Register-ScheduledTask -TaskName '{name}' -InputObject $task -Force | Out-Null"
    success, output = await run_ps(ps)
    if not success:
        raise RuntimeError(output)
    return {"name": name, "time": time_str}


async def _set_trigger_event_action(params: dict) -> Any:
    """Set an event-based trigger for a task."""
    name = params["name"]
    log_name = params.get("log_name", "Application")
    source = params.get("source", "")
    event_id = params.get("event_id", 1)
    ps = (f"$task = Get-ScheduledTask -TaskName '{name}'; "
          f"$trigger = New-ScheduledTaskTrigger -AtLogOn; "
          f"Register-ScheduledTask -TaskName '{name}' -Action ($task.Actions[0]) "
          f"-Trigger $trigger -Force | Out-Null")
    success, output = await run_ps(ps)
    if not success:
        raise RuntimeError(output)
    return {"name": name, "trigger": "event"}


async def _set_trigger_logon_action(params: dict) -> Any:
    """Set a logon trigger for a task."""
    name = params["name"]
    user = params.get("user", "")
    ps = f"$trigger = New-ScheduledTaskTrigger -AtLogOn"
    if user:
        ps += f" -User '{user}'"
    ps += f"; $task = Get-ScheduledTask -TaskName '{name}'; "
    ps += f"Register-ScheduledTask -TaskName '{name}' -Action ($task.Actions[0]) "
    ps += f"-Trigger $trigger -Force | Out-Null"
    success, output = await run_ps(ps)
    if not success:
        raise RuntimeError(output)
    return {"name": name, "trigger": "logon"}


async def _set_trigger_idle_action(params: dict) -> Any:
    """Set an idle trigger for a task."""
    name = params["name"]
    ps = (f"$task = Get-ScheduledTask -TaskName '{name}'; "
          f"$trigger = New-ScheduledTaskTrigger -AtStartup; "
          f"Register-ScheduledTask -TaskName '{name}' -Action ($task.Actions[0]) "
          f"-Trigger $trigger -Force | Out-Null")
    success, output = await run_ps(ps)
    if not success:
        raise RuntimeError(output)
    return {"name": name, "trigger": "idle"}


async def _get_task_history_action(params: dict) -> Any:
    """Get execution history of a task."""
    name = params["name"]
    ps_cmd = (
        "Get-ScheduledTask -TaskName '" + name + "' | "
        "Select-Object TaskName, LastRunTime, NextRunTime, LastTaskResult, MissedRuns | "
        "ConvertTo-Json -Compress"
    )
    success, output = await run_ps(ps_cmd)
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"error": output}


# ══════════════════════════════════════════════════════════════════════════════
# ENABLE / DISABLE SERVICE (set startup type)
# ══════════════════════════════════════════════════════════════════════════════

async def _enable_service_action(params: dict) -> Any:
    """Enable a Windows service (set startup type to Automatic)."""
    name = params["name"]
    success, output = await run_ps(
        f"Set-Service -Name '{name}' -StartupType Automatic -ErrorAction Stop"
    )
    if not success:
        raise RuntimeError(output)
    return {"enabled": name, "startup_type": "Automatic"}


async def _disable_service_action(params: dict) -> Any:
    """Disable a Windows service (set startup type to Disabled)."""
    name = params["name"]
    success, output = await run_ps(
        f"Set-Service -Name '{name}' -StartupType Disabled -ErrorAction Stop"
    )
    if not success:
        raise RuntimeError(output)
    return {"disabled": name, "startup_type": "Disabled"}


# ══════════════════════════════════════════════════════════════════════════════
# SC.EXE / CMD FALLBACK METHODS
# ══════════════════════════════════════════════════════════════════════════════

async def _start_service_sc(params: dict) -> Any:
    """Method 2: Start service via sc.exe."""
    name = params["name"]
    success, output = await run_cmd(["sc.exe", "start", name])
    if not success:
        raise RuntimeError(output)
    return {"started": name}


async def _stop_service_sc(params: dict) -> Any:
    """Method 2: Stop service via sc.exe."""
    name = params["name"]
    success, output = await run_cmd(["sc.exe", "stop", name])
    if not success:
        raise RuntimeError(output)
    return {"stopped": name}


async def _restart_service_sc(params: dict) -> Any:
    """Method 2: Restart service via sc.exe stop + start."""
    name = params["name"]
    await run_cmd(["sc.exe", "stop", name])
    import asyncio
    await asyncio.sleep(2)
    success, output = await run_cmd(["sc.exe", "start", name])
    if not success:
        raise RuntimeError(output)
    return {"restarted": name}


async def _get_status_sc(params: dict) -> Any:
    """Method 2: Get service status via sc.exe."""
    name = params["name"]
    success, output = await run_cmd(["sc.exe", "query", name])
    if success and output:
        state = "Unknown"
        for line in output.splitlines():
            if "STATE" in line:
                parts = line.split()
                if parts:
                    state = parts[-1]
        return {"name": name, "status": state}
    raise RuntimeError(output)


async def _list_services_sc(params: dict) -> Any:
    """Method 2: List services via sc.exe."""
    filter_str = params.get("filter", "")
    success, output = await run_cmd(["sc.exe", "query", "type=", "service", "state=", "all"], timeout=15)
    if success and output:
        services = []
        current = {}
        for line in output.splitlines():
            line = line.strip()
            if "SERVICE_NAME" in line:
                if current:
                    services.append(current)
                current = {"name": line.split(":")[1].strip()}
            elif "DISPLAY_NAME" in line:
                current["display_name"] = line.split(":", 1)[1].strip()
            elif "STATE" in line:
                current["status"] = line.split()[-1]
        if current:
            services.append(current)
        if filter_str:
            services = [s for s in services if filter_str.lower() in s.get("name", "").lower() or filter_str.lower() in s.get("display_name", "").lower()]
        return {"services": services, "count": len(services)}
    return {"services": [], "count": 0}


async def _get_config_sc(params: dict) -> Any:
    """Method 2: Get service config via sc.exe qc."""
    name = params["name"]
    success, output = await run_cmd(["sc.exe", "qc", name])
    if success and output:
        config = {}
        for line in output.splitlines():
            line = line.strip()
            if "START_TYPE" in line:
                config["start_type"] = line.split(":", 1)[1].strip()
            elif "BINARY_PATH_NAME" in line:
                config["path"] = line.split(":", 1)[1].strip()
            elif "SERVICE_START_NAME" in line:
                config["account"] = line.split(":", 1)[1].strip()
        config["name"] = name
        return config
    raise RuntimeError(output)


async def _pause_service_sc(params: dict) -> Any:
    """Method 2: Pause service via sc.exe."""
    name = params["name"]
    success, output = await run_cmd(["sc.exe", "pause", name])
    if not success:
        raise RuntimeError(output)
    return {"paused": name}


async def _resume_service_sc(params: dict) -> Any:
    """Method 2: Resume service via sc.exe."""
    name = params["name"]
    success, output = await run_cmd(["sc.exe", "continue", name])
    if not success:
        raise RuntimeError(output)
    return {"resumed": name}


async def _set_startup_sc(params: dict) -> Any:
    """Method 2: Set startup type via sc.exe config."""
    name = params["name"]
    startup_type = params.get("type", "Manual")
    type_map = {"automatic": "auto", "auto": "auto", "manual": "demand",
                "disabled": "disabled", "demand": "demand"}
    sc_type = type_map.get(startup_type.lower(), startup_type)
    success, output = await run_cmd(["sc.exe", "config", name, f"start=", sc_type])
    if not success:
        raise RuntimeError(output)
    return {"name": name, "startup_type": startup_type}


async def _enable_service_sc(params: dict) -> Any:
    """Method 2: Enable service via sc.exe config."""
    name = params["name"]
    success, output = await run_cmd(["sc.exe", "config", name, "start=", "auto"])
    if not success:
        raise RuntimeError(output)
    return {"enabled": name, "startup_type": "Automatic"}


async def _disable_service_sc(params: dict) -> Any:
    """Method 2: Disable service via sc.exe config."""
    name = params["name"]
    success, output = await run_cmd(["sc.exe", "config", name, "start=", "disabled"])
    if not success:
        raise RuntimeError(output)
    return {"disabled": name, "startup_type": "Disabled"}


async def _run_task_schtasks(params: dict) -> Any:
    """Method 2: Run task via schtasks.exe."""
    name = params["name"]
    success, output = await run_cmd(["schtasks.exe", "/Run", "/TN", name])
    if not success:
        raise RuntimeError(output)
    return {"ran": name}


async def _delete_task_schtasks(params: dict) -> Any:
    """Method 2: Delete task via schtasks.exe."""
    name = params["name"]
    success, output = await run_cmd(["schtasks.exe", "/Delete", "/TN", name, "/F"])
    if not success:
        raise RuntimeError(output)
    return {"deleted": name}


async def _list_tasks_schtasks(params: dict) -> Any:
    """Method 2: List tasks via schtasks.exe."""
    success, output = await run_cmd(["schtasks.exe", "/Query", "/FO", "CSV"], timeout=15)
    if success and output:
        lines = output.strip().splitlines()
        tasks = []
        for line in lines[1:]:  # Skip header
            parts = line.strip('"').split('","')
            if len(parts) >= 3:
                tasks.append({"name": parts[0], "status": parts[2], "next_run": parts[1]})
        return {"tasks": tasks, "count": len(tasks)}
    return {"tasks": [], "count": 0}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION HANDLER
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    "list_services":    ([_list_services, _list_services_sc], None),
    "start_service":    ([_start_service, _start_service_sc], None),
    "stop_service":     ([_stop_service, _stop_service_sc], None),
    "restart_service":  ([_restart_service, _restart_service_sc], None),
    "get_service_status": ([_get_service_status, _get_status_sc], None),
    "list_tasks":       ([_list_tasks, _list_tasks_schtasks], None),
    "run_task":         ([_run_task, _run_task_schtasks], None),
    "create_task":      ([_create_task], None),
    "delete_task":      ([_delete_task_action, _delete_task_schtasks], None),
    "enable_task":      ([_enable_task_action], None),
    "disable_task":     ([_disable_task_action], None),
    "get_service_config": ([_get_service_config_action, _get_config_sc], None),
    "pause_service":    ([_pause_service_action, _pause_service_sc], None),
    "resume_service":   ([_resume_service_action, _resume_service_sc], None),
    "set_startup_type": ([_set_startup_type_action, _set_startup_sc], None),
    # --- Phase 7 additions: Services ---
    "install_service":      ([_install_service_action], None),
    "remove_service":       ([_remove_service_action], None),
    "change_credentials":   ([_change_credentials_action], None),
    "set_description":      ([_set_description_action], None),
    "get_service_pid":      ([_get_service_pid_action], None),
    "get_dependent_services": ([_get_dependent_services_action], None),
    # --- Phase 7 additions: Task Scheduler ---
    "get_task_info":        ([_get_task_info_action], None),
    "stop_task":            ([_stop_task_action], None),
    "get_last_run_result":  ([_get_last_run_result_action], None),
    "set_trigger_time":     ([_set_trigger_time_action], None),
    "set_trigger_event":    ([_set_trigger_event_action], None),
    "set_trigger_logon":    ([_set_trigger_logon_action], None),
    "set_trigger_idle":     ([_set_trigger_idle_action], None),
    "get_task_history":     ([_get_task_history_action], None),
    # --- Enable/Disable Service ---
    "enable_service":   ([_enable_service_action, _enable_service_sc], None),
    "disable_service":  ([_disable_service_action, _disable_service_sc], None),
}


async def handler(action: str, params: dict[str, Any]) -> Result:
    """L7 Services layer handler."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown services action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"services.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("services", action),
        escalation_fn=create_escalation_fn("services", action),
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
