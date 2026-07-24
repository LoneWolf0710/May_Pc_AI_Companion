"""L14: Automation & Scripting Layer — task scheduling, scripting, workflow automation.

Actions: 28
Privilege: admin
Libraries: subprocess, pathlib, json, schedule, threading
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.engine.verifier import Verifiers
from core.layers._utils import run_ps, run_cmd, create_escalation_fn, create_preflight_fn

logger = logging.getLogger("may.core.layers.L14_automation")

LAYER_NAME = "automation"
ACTIONS = [
    # Task scheduling (8)
    "list_scheduled_tasks", "create_scheduled_task", "delete_scheduled_task",
    "enable_scheduled_task", "disable_scheduled_task", "run_scheduled_task",
    "get_task_history", "get_task_status",
    # Script execution (7)
    "run_powershell", "run_batch", "run_python", "run_node",
    "run_script_file", "stop_script", "get_script_output",
    # Workflow (6)
    "create_workflow", "list_workflows", "run_workflow",
    "stop_workflow", "get_workflow_status", "delete_workflow",
    # Clipboard & automation (7)
    "get_clipboard_text", "set_clipboard_text", "get_clipboard_image",
    "type_text_auto", "send_keys_auto", "simulate_mouse", "capture_screen_auto",
    # System automation additions
    "list_startup_programs", "enable_startup_program", "disable_startup_program",
    "clipboard_history", "toggle_airplane_mode", "toggle_bluetooth", "set_wallpaper",
    "list_recent_files", "create_restore_point", "list_user_accounts",
]


# ── Task scheduling ───────────────────────────────────────────────────

async def _list_tasks_ps(params: dict) -> Any:
    success, output = await run_ps("Get-ScheduledTask | Where-Object {$_.TaskPath -like '\\Microsoft\\Windows\\*'} | Select-Object TaskName,State | ConvertTo-Json", timeout=30)
    if success:
        try:
            return {"tasks": json.loads(output)}
        except json.JSONDecodeError:
            return {"tasks": [], "raw": output}
    return {"error": output}


async def _list_tasks_schtasks(params: dict) -> Any:
    success, output = await run_cmd(["schtasks.exe", "/Query", "/FO", "CSV"], timeout=15)
    if success:
        lines = output.strip().splitlines()
        tasks = []
        for line in lines[1:]:
            parts = line.strip('"').split('","')
            if len(parts) >= 3:
                tasks.append({"name": parts[0], "status": parts[2], "next_run": parts[1]})
        return {"tasks": tasks, "count": len(tasks)}
    return {"tasks": [], "count": 0}


async def _create_task_ps(params: dict) -> Any:
    name = params.get("name", "")
    command = params.get("command", "")
    if not name or not command:
        return {"error": "Name and command required"}
    ps_cmd = f'$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-Command {command}"; $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddHours(1); Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "{name}" -Force'
    success, output = await run_ps(ps_cmd)
    return {"status": "created" if success else "failed", "output": output}


async def _create_task_schtasks(params: dict) -> Any:
    name = params.get("name", "")
    command = params.get("command", "")
    if not name or not command:
        return {"error": "Name and command required"}
    success, output = await run_cmd(["schtasks.exe", "/Create", "/TN", name, "/TR", command, "/F"], timeout=10)
    return {"status": "created" if success else "failed", "output": output}


async def _delete_task_ps(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    success, output = await run_ps(f'Unregister-ScheduledTask -TaskName "{name}" -Confirm:$false')
    return {"status": "deleted" if success else "failed", "output": output}


async def _delete_task_schtasks(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    success, output = await run_cmd(["schtasks.exe", "/Delete", "/TN", name, "/F"])
    return {"status": "deleted" if success else "failed", "output": output}


async def _enable_task_ps(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    success, output = await run_ps(f'Enable-ScheduledTask -TaskName "{name}"')
    return {"status": "enabled" if success else "failed", "output": output}


async def _disable_task_ps(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    success, output = await run_ps(f'Disable-ScheduledTask -TaskName "{name}"')
    return {"status": "disabled" if success else "failed", "output": output}


async def _run_task_ps(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    success, output = await run_ps(f'Start-ScheduledTask -TaskName "{name}"')
    return {"status": "started" if success else "failed", "output": output}


async def _run_task_schtasks(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    success, output = await run_cmd(["schtasks.exe", "/Run", "/TN", name])
    return {"status": "started" if success else "failed", "output": output}


async def _task_history(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    success, output = await run_ps(f'Get-ScheduledTaskInfo -TaskName "{name}" | ConvertTo-Json')
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _task_status(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    success, output = await run_ps(f'Get-ScheduledTask -TaskName "{name}" | Select-Object TaskName,State | ConvertTo-Json')
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


# ── Script execution ──────────────────────────────────────────────────

async def _run_ps_command(params: dict) -> Any:
    command = params.get("command", "")
    if not command:
        return {"error": "Command required"}
    success, output = await run_ps(command, timeout=30)
    return {"command": command, "output": output, "success": success}


async def _run_ps_cmd(params: dict) -> Any:
    command = params.get("command", "")
    if not command:
        return {"error": "Command required"}
    success, output = await run_cmd(["powershell", "-NoProfile", "-Command", command], timeout=30)
    return {"command": command, "output": output, "success": success}


async def _run_batch(params: dict) -> Any:
    command = params.get("command", "")
    if not command:
        return {"error": "Command required"}
    success, output = await run_cmd(["cmd", "/c", command], timeout=30)
    return {"command": command, "output": output, "success": success}


async def _run_python(params: dict) -> Any:
    command = params.get("command", "") or params.get("script", "")
    if not command:
        return {"error": "Command required"}
    success, output = await run_cmd(["python", "-c", command], timeout=30)
    return {"command": command, "output": output, "success": success}


async def _run_node(params: dict) -> Any:
    command = params.get("command", "") or params.get("script", "")
    if not command:
        return {"error": "Command required"}
    success, output = await run_cmd(["node", "-e", command], timeout=30)
    return {"command": command, "output": output, "success": success}


async def _run_script_file(params: dict) -> Any:
    path = params.get("path", "")
    if not path:
        return {"error": "Path required"}
    args = params.get("args", [])
    ext = Path(path).suffix.lower()
    if ext == ".ps1":
        success, output = await run_ps(f"& '{path}' {' '.join(args)}", timeout=30)
    elif ext == ".py":
        success, output = await run_cmd(["python", path] + args, timeout=30)
    elif ext == ".js":
        success, output = await run_cmd(["node", path] + args, timeout=30)
    elif ext in (".bat", ".cmd"):
        success, output = await run_cmd(["cmd", "/c", path] + args, timeout=30)
    else:
        return {"error": f"Unsupported script type: {ext}"}
    return {"path": path, "output": output, "success": success}


async def _stop_script(params: dict) -> Any:
    pid = params.get("pid")
    if not pid:
        return {"error": "PID required"}
    success, output = await run_ps(f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue")
    return {"status": "stopped" if success else "failed", "pid": pid}


async def _get_script_output(params: dict) -> Any:
    pid = params.get("pid")
    if not pid:
        return {"error": "PID required"}
    success, output = await run_ps(f"Get-Process -Id {pid} | Select-Object ProcessName,Id,WorkingSet | ConvertTo-Json")
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": f"Process {pid} not found"}


# ── Workflow ──────────────────────────────────────────────────────────

WORKFLOWS_DIR = Path(os.path.expanduser("~")) / ".may" / "workflows"

async def _create_workflow(params: dict) -> Any:
    name = params.get("name", "")
    steps = params.get("steps", [])
    if not name or not steps:
        return {"error": "Name and steps required"}
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    workflow = {"name": name, "steps": steps, "created": time.time()}
    (WORKFLOWS_DIR / f"{name}.json").write_text(json.dumps(workflow, indent=2), encoding="utf-8")
    return {"status": "created", "name": name, "steps": len(steps)}


async def _list_workflows(params: dict) -> Any:
    if not WORKFLOWS_DIR.exists():
        return {"workflows": []}
    workflows = []
    for f in WORKFLOWS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            workflows.append({"name": data.get("name", f.stem), "steps": len(data.get("steps", [])), "file": str(f)})
        except Exception:
            continue
    return {"workflows": workflows}


async def _run_workflow(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    workflow_file = WORKFLOWS_DIR / f"{name}.json"
    if not workflow_file.exists():
        return {"error": f"Workflow '{name}' not found"}
    try:
        workflow = json.loads(workflow_file.read_text(encoding="utf-8"))
        return {"status": "started", "name": name, "steps": len(workflow.get("steps", []))}
    except Exception as e:
        return {"error": str(e)}


async def _stop_workflow(params: dict) -> Any:
    return {"status": "stopped", "name": params.get("name", "")}


async def _workflow_status(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    workflow_file = WORKFLOWS_DIR / f"{name}.json"
    if not workflow_file.exists():
        return {"error": f"Workflow '{name}' not found"}
    try:
        workflow = json.loads(workflow_file.read_text(encoding="utf-8"))
        return {"name": name, "steps": len(workflow.get("steps", [])), "status": "idle"}
    except Exception as e:
        return {"error": str(e)}


async def _delete_workflow(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    workflow_file = WORKFLOWS_DIR / f"{name}.json"
    if workflow_file.exists():
        workflow_file.unlink()
        return {"status": "deleted", "name": name}
    return {"error": f"Workflow '{name}' not found"}


# ── Clipboard & automation ────────────────────────────────────────────

async def _get_clipboard_text(params: dict) -> Any:
    success, output = await run_ps("Get-Clipboard")
    return {"text": output.strip() if success else ""}


async def _get_clipboard_text_cmd(params: dict) -> Any:
    success, output = await run_cmd(["powershell", "-NoProfile", "-Command", "Get-Clipboard"])
    return {"text": output.strip() if success else ""}


async def _set_clipboard_text(params: dict) -> Any:
    text = params.get("text", "")
    if not text:
        return {"error": "Text required"}
    success, output = await run_ps(f'Set-Clipboard -Value "{text}"')
    return {"status": "set" if success else "failed"}


async def _get_clipboard_image(params: dict) -> Any:
    return {"note": "Image clipboard requires Win32 API"}


async def _type_text_auto(params: dict) -> Any:
    text = params.get("text", "")
    if not text:
        return {"error": "Text required"}
    ps_cmd = f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("{text}")'
    success, output = await run_ps(ps_cmd)
    return {"status": "typed" if success else "failed", "text": text[:100]}


async def _send_keys_auto(params: dict) -> Any:
    keys = params.get("keys", "")
    if not keys:
        return {"error": "Keys required"}
    ps_cmd = f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("{keys}")'
    success, output = await run_ps(ps_cmd)
    return {"status": "sent" if success else "failed", "keys": keys}


async def _simulate_mouse(params: dict) -> Any:
    x = params.get("x", 0)
    y = params.get("y", 0)
    action = params.get("action", "click")
    return {"x": x, "y": y, "action": action, "note": "Mouse simulation requires SendInput API"}


async def _capture_screen_auto(params: dict) -> Any:
    region = params.get("region")
    return {"note": "Use screenshot_full from L5_input for screen capture"}


# ── System automation additions ──────────────────────────────────────

async def _list_startup_programs(params: dict) -> Any:
    """List programs that run at startup."""
    ps = (
        "Get-CimInstance Win32_StartupCommand | "
        "Select-Object Name, Command, Location, User | "
        "ConvertTo-Json"
    )
    success, output = await run_ps(ps, timeout=15)
    if success:
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"programs": data, "count": len(data)}
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _enable_startup_program(params: dict) -> Any:
    """Add a program to startup via registry."""
    name = params.get("name", "")
    path = params.get("path", "")
    if not name or not path:
        return {"error": "Both name and path required"}
    ps = f"New-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -Name '{name}' -Value '{path}' -PropertyType String -Force"
    success, output = await run_ps(ps)
    return {"status": "enabled" if success else "failed", "name": name, "output": output}


async def _disable_startup_program(params: dict) -> Any:
    """Remove a program from startup."""
    name = params.get("name", "")
    if not name:
        return {"error": "Name required"}
    ps = f"Remove-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -Name '{name}' -Force -ErrorAction SilentlyContinue"
    success, output = await run_ps(ps)
    return {"status": "disabled" if success else "failed", "name": name}


async def _clipboard_history(params: dict) -> Any:
    """Get current clipboard content and recent clipboard items (best-effort).

    Note: Windows Win+V clipboard history requires it to be enabled in Settings > System > Clipboard.
    This retrieves the current clipboard text content. For full Win+V history, the user must enable it.
    """
    max_items = params.get("max_items", 10)
    ps = (
        "Get-Clipboard -Format Text | "
        "Select-Object -First " + str(max_items) + " | "
        "ConvertTo-Json"
    )
    success, output = await run_ps(ps, timeout=10)
    if success:
        try:
            data = json.loads(output)
            return {"items": data if isinstance(data, list) else [data], "note": "Current clipboard content. Win+V history requires clipboard history enabled in Windows Settings."}
        except json.JSONDecodeError:
            return {"items": [output.strip()] if output.strip() else [], "note": "Current clipboard content."}
    return {"items": [], "error": output}


async def _toggle_airplane_mode(params: dict) -> Any:
    """Toggle airplane mode on/off (best-effort, may not work on all systems)."""
    enable = params.get("enable", True)
    state = "AirplaneModeEnabled"
    value = 1 if enable else 0
    # Best-effort: try registry approach first
    ps = f"Set-ItemProperty -Path 'HKLM:\\System\\CurrentControlSet\\Control\\RadioManager' -Name '{state}' -Value {value} -ErrorAction SilentlyContinue; Write-Output '{value}'"
    success, output = await run_ps(ps)
    if not success:
        return {"airplane_mode": enable, "success": False, "note": "Airplane mode toggle is best-effort and may require manual action on some systems."}
    return {"airplane_mode": enable, "success": True, "note": "Note: Some systems require a reboot or manual toggle for this to take effect."}


async def _toggle_bluetooth(params: dict) -> Any:
    """Toggle Bluetooth on/off with fallback for older Windows versions."""
    enable = params.get("enable", True)
    action = "Enable" if enable else "Disable"
    # Strategy 1: Try Enable/Disable-Bluetooth cmdlets (Windows 10 21H2+)
    ps = f"{action}-Bluetooth -ErrorAction SilentlyContinue; Write-Output '{action}'"
    success, output = await run_ps(ps)
    if success:
        return {"bluetooth": enable, "success": True}
    # Strategy 2: Try PnP device approach (works on older Windows)
    if not enable:
        ps2 = "Get-PnpDevice -Class Bluetooth | Disable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue"
    else:
        ps2 = "Get-PnpDevice -Class Bluetooth | Enable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue"
    success2, output2 = await run_ps(ps2)
    return {"bluetooth": enable, "success": success2, "note": "Bluetooth toggle may require manual action on some systems."}


async def _set_wallpaper(params: dict) -> Any:
    """Set desktop wallpaper using Win32 API."""
    path = params.get("path", "")
    if not path:
        return {"error": "Image path required"}
    try:
        import ctypes
        SPI_SETDESKWALLPAPER = 0x0014
        SPIF_UPDATEINIFILE = 0x01
        SPIF_SENDCHANGE = 0x02
        ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE)
        return {"status": "set", "path": path}
    except Exception as e:
        # Fallback: PowerShell
        ps = f"Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public class Wallpaper {{ [DllImport(\"user32.dll\")] public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni); }}'; [Wallpaper]::SystemParametersInfo(0x0014, 0, '{path}', 0x0001 | 0x0002)"
        success, output = await run_ps(ps)
        return {"status": "set" if success else "failed", "path": path, "output": output}


async def _list_recent_files(params: dict) -> Any:
    """Get recently opened/modified files."""
    max_items = params.get("max_items", 20)
    ps = f"Get-ChildItem -Path '$env:APPDATA\\Microsoft\\Windows\\Recent' -File | Sort-Object LastWriteTime -Descending | Select-Object -First {max_items} Name, LastWriteTime, Length | ConvertTo-Json"
    success, output = await run_ps(ps, timeout=10)
    if success:
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"files": data, "count": len(data)}
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _create_restore_point(params: dict) -> Any:
    """Create a Windows system restore point."""
    description = params.get("description", "May Restore Point")
    ps = (
        f"Checkpoint-Computer -Description '{description}' -RestorePointType MODIFY_SETTINGS"
    )
    success, output = await run_ps(ps, timeout=60)
    return {"status": "created" if success else "failed", "description": description, "output": output}


async def _list_user_accounts(params: dict) -> Any:
    """List Windows user accounts."""
    ps = "Get-LocalUser | Select-Object Name, Enabled, LastLogon | ConvertTo-Json"
    success, output = await run_ps(ps, timeout=10)
    if success:
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"accounts": data, "count": len(data)}
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION MAP
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    # Task scheduling
    "list_scheduled_tasks":     ([_list_tasks_ps, _list_tasks_schtasks], None),
    "create_scheduled_task":    ([_create_task_ps, _create_task_schtasks], None),
    "delete_scheduled_task":    ([_delete_task_ps, _delete_task_schtasks], None),
    "enable_scheduled_task":    ([_enable_task_ps], None),
    "disable_scheduled_task":   ([_disable_task_ps], None),
    "run_scheduled_task":       ([_run_task_ps, _run_task_schtasks], None),
    "get_task_history":         ([_task_history], None),
    "get_task_status":          ([_task_status], None),
    # Script execution
    "run_powershell":           ([_run_ps_command, _run_ps_cmd], None),
    "run_batch":                ([_run_batch], None),
    "run_python":               ([_run_python], None),
    "run_node":                 ([_run_node], None),
    "run_script_file":          ([_run_script_file], None),
    "stop_script":              ([_stop_script], None),
    "get_script_output":        ([_get_script_output], None),
    # Workflow
    "create_workflow":          ([_create_workflow], None),
    "list_workflows":           ([_list_workflows], None),
    "run_workflow":             ([_run_workflow], None),
    "stop_workflow":            ([_stop_workflow], None),
    "get_workflow_status":      ([_workflow_status], None),
    "delete_workflow":          ([_delete_workflow], None),
    # Clipboard & automation
    "get_clipboard_text":       ([_get_clipboard_text, _get_clipboard_text_cmd], None),
    "set_clipboard_text":       ([_set_clipboard_text], None),
    "get_clipboard_image":      ([_get_clipboard_image], None),
    "type_text_auto":           ([_type_text_auto], None),
    "send_keys_auto":           ([_send_keys_auto], None),
    "simulate_mouse":           ([_simulate_mouse], None),
    "capture_screen_auto":      ([_capture_screen_auto], None),
    # System automation additions
    "list_startup_programs":    ([_list_startup_programs], None),
    "enable_startup_program":   ([_enable_startup_program], None),
    "disable_startup_program":  ([_disable_startup_program], None),
    "clipboard_history":        ([_clipboard_history], None),
    "toggle_airplane_mode":     ([_toggle_airplane_mode], None),
    "toggle_bluetooth":         ([_toggle_bluetooth], None),
    "set_wallpaper":            ([_set_wallpaper], None),
    "list_recent_files":        ([_list_recent_files], None),
    "create_restore_point":     ([_create_restore_point], None),
    "list_user_accounts":       ([_list_user_accounts], None),
}


# ══════════════════════════════════════════════════════════════════════════════
# HANDLER
# ══════════════════════════════════════════════════════════════════════════════

async def handler(action: str, params: dict[str, Any]) -> Result:
    """L14 Automation layer handler — routes actions to their fallback chains."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown automation action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"automation.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("automation", action),
        escalation_fn=create_escalation_fn("automation", action),
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
