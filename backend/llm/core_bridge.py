"""Core Bridge -- Maps LLM tool calls to control core TCP commands.

Every tool the LLM can call is mapped here to:
  - A (layer, action) pair for the control core
  - A param transformer that converts tool params -> core params
  - An optional result transformer that formats the core result for the LLM

Tools that don't map to any control core layer are handled as 'direct'
(they run locally via subprocess/asyncio without the daemon).

NOTE: The deprecated SystemControl class (system.control) has been removed.
All direct tools now use inline subprocess/asyncio implementations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger("may.llm.core_bridge")

# -- Import the TCP client ---------------------------------------------------
# The client lives in core/ (project root), we're in backend/llm/
# Add the project root (may/) so 'from core.client import ...' resolves correctly
_project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.client import send_command, is_daemon_running_sync
from core.bus import Result


# -- Tool -> Core Mapping ----------------------------------------------------
# Each entry: (layer, action, param_transformer, result_transformer)
#
# param_transformer(tool_args) -> core_params dict
# result_transformer(core_result_data) -> string for the LLM

def _identity_params(args: dict) -> dict:
    """Pass params through unchanged."""
    return args


def _empty_params(args: dict) -> dict:
    """No params needed."""
    return {}


def _result_to_str(data: Any) -> str:
    """Convert result data to a readable string for the LLM."""
    if data is None:
        return "Done"
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        parts = []
        for k, v in data.items():
            if k in ("raw",):
                continue
            parts.append(f"{k}: {v}")
        return ", ".join(parts) if parts else "Done"
    if isinstance(data, list):
        if len(data) == 0:
            return "Empty list"
        if isinstance(data[0], dict):
            lines = []
            for item in data[:30]:
                name = item.get("name") or item.get("title") or item.get("pid") or str(item)
                lines.append(f"  - {name}")
            suffix = f"  ... and {len(data) - 30} more" if len(data) > 30 else ""
            return "\n".join(lines) + suffix
        return "\n".join(str(x) for x in data[:20])
    return str(data)


# -- Special param transformers -----------------------------------------------

def _open_app_params(args: dict) -> dict:
    return {"app_name": args.get("app_name", "")}


def _close_app_params(args: dict) -> dict:
    return {"app_name": args.get("app_name", args.get("title", ""))}


def _search_files_params(args: dict) -> dict:
    return {"path": args.get("path", args.get("directory", ".")), "pattern": args.get("pattern", "*")}


def _list_processes_params(args: dict) -> dict:
    return {"sort": args.get("sort_by", "cpu")}


def _hotkey_params(args: dict) -> dict:
    return {"combo": args.get("keys", "")}


def _shutdown_params(args: dict) -> dict:
    return {"delay": args.get("delay", 0)}


def _restart_params(args: dict) -> dict:
    return {"delay": args.get("delay", 0)}


def _get_env_params(args: dict) -> dict:
    return {"name": args.get("name", "")}


def _list_env_params(args: dict) -> dict:
    return {"filter": args.get("filter", "")}


def _list_services_params(args: dict) -> dict:
    return {"filter": args.get("filter", "")}


# -- Result transformers -------------------------------------------------------

def _result_windows(data: Any) -> str:
    """Format window list for LLM."""
    if isinstance(data, dict) and "windows" in data:
        windows = data["windows"]
        if not windows:
            return "No visible windows"
        lines = []
        for w in windows[:30]:
            lines.append(f"  - [{w.get('pid', '?')}] {w.get('title', 'Untitled')}")
        return "\n".join(lines)
    return _result_to_str(data)


def _result_services(data: Any) -> str:
    """Format service list for LLM."""
    if isinstance(data, dict) and "services" in data:
        services = data["services"]
        if not services:
            return "No services found"
        lines = []
        for s in services[:30]:
            name = s.get("Name", s.get("name", "?"))
            status = s.get("Status", s.get("status", "?"))
            lines.append(f"  - {name}: {status}")
        return "\n".join(lines)
    return _result_to_str(data)


def _result_processes(data: Any) -> str:
    """Format process list for LLM."""
    if isinstance(data, dict) and "processes" in data:
        procs = data["processes"]
        if not procs:
            return "No processes found"
        lines = []
        for p in procs[:20]:
            name = p.get("name", "?")
            pid = p.get("pid", "?")
            cpu = p.get("cpu_percent", 0)
            mem = p.get("memory_mb", 0)
            lines.append(f"  - {name} (PID {pid}) -- CPU: {cpu}%, RAM: {mem}MB")
        return "\n".join(lines)
    return _result_to_str(data)


def _result_drives(data: Any) -> str:
    """Format drive info for LLM."""
    if isinstance(data, dict) and "drives" in data:
        drives = data["drives"]
        lines = []
        for d in drives:
            dev = d.get("device", "?")
            mount = d.get("mountpoint", "?")
            free = d.get("free_gb", 0)
            total = d.get("total_gb", 0)
            pct = d.get("percent", 0)
            lines.append(f"  - {dev} ({mount}): {free}GB free / {total}GB total ({pct}% used)")
        return "\n".join(lines) if lines else "No drives found"
    return _result_to_str(data)


def _result_system_info(data: Any) -> str:
    """Format system info for LLM."""
    if isinstance(data, dict):
        parts = []
        for key in ["os", "processor", "cpu_cores", "ram_total_gb", "ram_percent",
                      "username", "computer", "uptime_hours", "uptime_minutes"]:
            if key in data:
                val = data[key]
                label = key.replace("_", " ").title()
                parts.append(f"{label}: {val}")
        return "\n".join(parts) if parts else _result_to_str(data)
    return _result_to_str(data)


def _result_env(data: Any) -> str:
    """Format env var result for LLM."""
    if isinstance(data, dict):
        if "value" in data:
            name = data.get("name", "?")
            value = data.get("value", "Not set")
            return f"{name} = {value}"
        if "vars" in data:
            vars_dict = data["vars"]
            count = data.get("count", len(vars_dict))
            lines = [f"  {k} = {v[:100]}" for k, v in list(vars_dict.items())[:30]]
            suffix = f"\n  ... and {count - 30} more" if count > 30 else ""
            return "\n".join(lines) + suffix
    return _result_to_str(data)


# -- THE MAPPING TABLE --------------------------------------------------------
# Format: tool_name -> (layer, action, param_transformer, result_transformer)
# If layer is None -> tool is handled directly (not via TCP)

TOOL_CORE_MAP: dict[str, tuple[str | None, str | None, Callable | None, Callable | None]] = {
    # -- Filesystem (L1) ---------------------------------------------------
    "read_file":       ("filesystem", "read_file",       _identity_params, _result_to_str),
    "write_file":      ("filesystem", "write_file",      _identity_params, _result_to_str),
    "list_directory":  ("filesystem", "list_directory",  _identity_params, _result_to_str),
    "search_files":    ("filesystem", "search_files",    _search_files_params, _result_to_str),
    "copy_file":       ("filesystem", "copy_file",       _identity_params, _result_to_str),
    "move_file":       ("filesystem", "move_file",       _identity_params, _result_to_str),
    "delete_file":     ("filesystem", "delete_file",     _identity_params, _result_to_str),
    "get_file_info":   ("filesystem", "get_file_info",   _identity_params, _result_to_str),
    "get_folder_size": ("filesystem", "get_folder_size", _identity_params, _result_to_str),
    "create_folder":   ("filesystem", "create_folder",   _identity_params, _result_to_str),
    "get_drive_info":  ("filesystem", "list_drives",     _empty_params, _result_to_str),
    "copy_folder":     ("filesystem", "copy_folder_tree", _identity_params, _result_to_str),
    "delete_folder":   ("filesystem", "delete_folder_tree", _identity_params, _result_to_str),
    "open_folder":     ("application", "launch_app",     _open_app_params, _result_to_str),
    "launch_with_args":   ("application", "launch_with_args",  lambda a: {"app_name": a.get("app_name", ""), "args": a.get("args", "")}, _result_to_str),
    "launch_as_admin":    ("application", "launch_as_admin",   lambda a: {"app_name": a.get("app_name", "")}, _result_to_str),
    "restart_app":        ("application", "restart_app",       lambda a: {"app_name": a.get("app_name", "")}, _result_to_str),
    "is_app_running":     ("application", "is_app_running",    lambda a: {"app_name": a.get("app_name", "")}, _result_to_str),
    "automate_app":       ("application", "automate_app",      _identity_params, _result_to_str),
    "com_dispatch":       ("application", "com_dispatch",      _identity_params, _result_to_str),
    "find_app_by_name":   ("application", "find_app_by_name",  lambda a: {"name": a.get("name", "")}, _result_to_str),

    # -- Process (L2) --------------------------------------------------------
    "list_processes":    ("process", "list_processes",     _list_processes_params, _result_processes),
    "kill_process":      ("process", "kill_process",       _identity_params, _result_to_str),
    "get_process_info":  ("process", "get_process_info",   _identity_params, _result_processes),
    "get_top_processes": ("process", "list_processes",     lambda a: {"sort": "cpu"}, _result_processes),
    "get_process_tree":  ("process", "get_process_info",   _identity_params, _result_processes),
    "set_process_priority": ("process", "set_priority",    lambda a: {"pid": a.get("pid", 0), "priority": a.get("priority", "normal")}, _result_to_str),
    "get_command_line":   ("process", "get_command_line",  lambda a: {"name": a.get("name", "")}, _result_to_str),
    "is_process_running": ("process", "is_process_running", lambda a: {"name": a.get("name", "")}, _result_to_str),
    "get_process_cpu":    ("process", "get_cpu_usage",    lambda a: {"name": a.get("name", ""), "pid": a.get("pid")}, _result_to_str),
    "get_process_memory": ("process", "get_memory_usage",  lambda a: {"name": a.get("name", ""), "pid": a.get("pid")}, _result_to_str),
    "get_process_path":   ("process", "get_process_path",  lambda a: {"name": a.get("name", ""), "pid": a.get("pid")}, _result_to_str),
    "set_process_affinity": ("process", "set_affinity",   lambda a: {"pid": a.get("pid", 0), "cores": a.get("cores", [0])}, _result_to_str),
    "set_memory_limit":   ("process", "set_memory_limit",  lambda a: {"pid": a.get("pid", 0), "limit_mb": a.get("limit_mb", 1024)}, _result_to_str),
    "set_cpu_limit":      ("process", "set_cpu_limit",     lambda a: {"pid": a.get("pid", 0), "percent": a.get("percent", 50)}, _result_to_str),

    # -- Application (L3) ----------------------------------------------------
    "open_app":            ("application", "launch_app",         _open_app_params, _result_to_str),
    "close_app":           ("application", "close_app",          _close_app_params, _result_to_str),
    "list_installed_apps": ("application", "list_installed_apps", _empty_params, _result_to_str),
    "get_app_path":        ("application", "get_app_path",       lambda a: {"app_name": a.get("app_name", "")}, _result_to_str),
    "get_app_version":     ("application", "get_app_version",    lambda a: {"app_name": a.get("app_name", "")}, _result_to_str),
    "force_close_app":     ("application", "force_close_app",    lambda a: {"app_name": a.get("app_name", "")}, _result_to_str),

    # -- Window (L4) ---------------------------------------------------------
    "list_windows":     ("window", "list_all_windows", _empty_params, _result_windows),
    "focus_window":     ("window", "set_foreground",   lambda a: {"title": a.get("title", "")}, _result_to_str),
    "minimize_window":  ("window", "minimize_window",  lambda a: {"title": a.get("title", "")}, _result_to_str),
    "maximize_window":  ("window", "maximize_window",  lambda a: {"title": a.get("title", "")}, _result_to_str),
    "resize_window":    ("window", "resize_window",    lambda a: {"title": a.get("title", ""), "width": a.get("width", 800), "height": a.get("height", 600)}, _result_to_str),
    "flash_window":     ("window", "flash_window",     lambda a: {"title": a.get("title", "")}, _result_to_str),
    "find_window":      ("window", "find_window",      lambda a: {"title": a.get("title", "")}, _result_to_str),
    "set_window_position": ("window", "set_position_and_size", lambda a: {"title": a.get("title", ""), "x": a.get("x", 0), "y": a.get("y", 0), "width": a.get("width", 800), "height": a.get("height", 600)}, _result_to_str),
    "close_window":     ("window", "force_close_window", lambda a: {"title": a.get("title", "")}, _result_to_str),
    "get_window_title":  ("window", "get_active_window", _empty_params, _result_to_str),
    "take_window_screenshot": ("window", "take_window_screenshot", _identity_params, _result_to_str),
    "arrange_windows":  ("window", "arrange_tile",     lambda a: {"mode": a.get("mode", "tile")}, _result_to_str),

    # -- Input (L5) ----------------------------------------------------------
    "send_keys":          ("input", "hotkey",        lambda a: {"combo": a.get("keys", a.get("combo", ""))}, _result_to_str),
    "type_text":          ("input", "type_text",     lambda a: {"text": a.get("text", ""), **({"window_title": a["window_title"]} if a.get("window_title") else {})}, _result_to_str),
    "type_text_fast":     ("input", "type_text_fast", _identity_params, _result_to_str),
    "mouse_scroll":       ("input", "scroll",        _identity_params, _result_to_str),
    "copy_to_clipboard":  ("input", "set_clipboard", _identity_params, _result_to_str),
    "set_clipboard":      ("input", "set_clipboard", _identity_params, _result_to_str),
    "get_clipboard":      ("input", "get_clipboard",  _empty_params, _result_to_str),
    "drag_and_drop":      ("input", "drag_and_drop",  lambda a: {"x1": a.get("x1", 0), "y1": a.get("y1", 0), "x2": a.get("x2", 0), "y2": a.get("y2", 0)}, _result_to_str),
    "tap_key":             ("input", "tap_key",       lambda a: {"key": a.get("key", "")}, _result_to_str),
    "hold_key":            ("input", "hold_key",      lambda a: {"key": a.get("key", ""), "duration": a.get("duration", 0.5)}, _result_to_str),
    "screenshot_full":     ("input", "screenshot_full", _identity_params, _result_to_str),
    "screenshot_region":   ("input", "screenshot_region", _identity_params, _result_to_str),

    # -- Services (L7) -------------------------------------------------------
    "list_services":  ("services", "list_services", _list_services_params, _result_services),
    "start_service":  ("services", "start_service", _identity_params, _result_to_str),
    "stop_service":   ("services", "stop_service",  _identity_params, _result_to_str),
    "restart_service": ("services", "restart_service", _identity_params, _result_to_str),
    "set_service_startup": ("services", "set_startup_type", lambda a: {"name": a.get("name", ""), "type": a.get("type", "Manual")}, _result_to_str),

    # -- System (L8) ---------------------------------------------------------
    "set_volume":    ("system", "set_volume",      _identity_params, _result_to_str),
    "get_volume":    ("system", "get_volume",       _empty_params, _result_to_str),
    "mute":          ("system", "mute",             _empty_params, _result_to_str),
    "unmute":        ("system", "unmute",           _empty_params, _result_to_str),
    "set_brightness": ("system", "set_brightness", _identity_params, _result_to_str),
    "get_brightness": ("system", "get_brightness",  _empty_params, _result_to_str),
    "shutdown_pc":   ("system", "shutdown",         _shutdown_params, _result_to_str),
    "restart_pc":    ("system", "restart",          _restart_params, _result_to_str),
    "sleep_pc":      ("system", "sleep",            _empty_params, _result_to_str),
    "lock_pc":       ("system", "lock",             _empty_params, _result_to_str),
    "cancel_shutdown": ("system", "cancel_shutdown", _empty_params, _result_to_str),
    "system_info":   ("system", "get_system_info",  _empty_params, _result_system_info),
    "battery_info":  ("system", "get_battery",      _empty_params, _result_to_str),
    "disk_info":     ("system", "get_disk_usage",   _empty_params, _result_drives),
    "get_network_info": ("system", "get_network_info", _empty_params, _result_to_str),
    "get_public_ip": ("system", "get_public_ip",    _empty_params, _result_to_str),
    "get_wifi_password": ("system", "get_wifi_password", _empty_params, _result_to_str),
    "get_env_var":   ("system", "get_env",          _get_env_params, _result_env),
    "list_env_vars": ("system", "list_env",         _list_env_params, _result_env),
    "connect_wifi":  ("system", "connect_wifi",     lambda a: {"ssid": a.get("ssid", ""), "password": a.get("password", "")}, _result_to_str),
    "disconnect_wifi": ("system", "disconnect_wifi", _empty_params, _result_to_str),
    "flush_dns":     ("system", "flush_dns",        _empty_params, _result_to_str),
    "add_firewall_rule": ("system", "add_firewall_rule", _identity_params, _result_to_str),
    "logoff":        ("system", "logoff",           _empty_params, _result_to_str),
    "get_audio_devices": ("system", "get_audio_devices", _empty_params, _result_to_str),
    "rotate_display": ("system", "rotate_display",  _identity_params, _result_to_str),
    "enable_adapter": ("system", "enable_adapter",   lambda a: {"name": a.get("name", "Wi-Fi")}, _result_to_str),
    "disable_adapter": ("system", "disable_adapter", lambda a: {"name": a.get("name", "Wi-Fi")}, _result_to_str),
    "list_wifi_networks": ("system", "list_wifi_networks", _empty_params, _result_to_str),
    "get_os_info":   ("system", "get_os_info",      _empty_params, _result_to_str),

    # -- Browser (L9) --------------------------------------------------------
    "browser_navigate":  ("browser", "navigate",      _identity_params, _result_to_str),
    "browser_click":     ("browser", "click_element",  _identity_params, _result_to_str),
    "browser_type":      ("browser", "type_into_element", _identity_params, _result_to_str),
    "browser_fill_form": ("browser", "fill_form",      _identity_params, _result_to_str),
    "browser_get_text":  ("browser", "get_element_text", _identity_params, _result_to_str),
    "browser_screenshot": ("browser", "take_screenshot", _identity_params, _result_to_str),
    "browser_run_js":    ("browser", "run_javascript",  _identity_params, _result_to_str),
    "browser_wait_for":  ("browser", "wait_for_element", _identity_params, _result_to_str),
    "browser_manage_cookies": ("browser", "manage_cookies", _identity_params, _result_to_str),
    "open_browser":      ("browser", "open_browser",    _identity_params, _result_to_str),
    "close_browser":     ("browser", "close_browser",   _empty_params, _result_to_str),
    "handle_dialog":     ("browser", "handle_dialog",   _identity_params, _result_to_str),
    "connect_to_browser": ("browser", "connect_to_browser", _identity_params, _result_to_str),

    # -- Architecture-compliant new actions ------------------------------------
    "list_virtual_desktops":  ("window", "list_virtual_desktops", _empty_params, _result_to_str),
    "move_to_virtual_desktop": ("window", "move_to_virtual_desktop", lambda a: {"title": a.get("title", ""), "desktop_index": a.get("desktop_index", 0)}, _result_to_str),
    "screenshot_window":      ("input", "screenshot_window", _identity_params, _result_to_str),
    "enable_service":         ("services", "enable_service", _identity_params, _result_to_str),
    "disable_service":        ("services", "disable_service", _identity_params, _result_to_str),
    "get_installed_updates":  ("system", "get_installed_updates", _empty_params, _result_to_str),
    "delete_system_env":      ("system", "delete_system_env", lambda a: {"name": a.get("name", "")}, _result_to_str),

    "compress_file":       ("filesystem", "compress_file",  _identity_params, _result_to_str),
    "decompress_file":     ("filesystem", "decompress_file", _identity_params, _result_to_str),
    "find_duplicates":     ("filesystem", "find_duplicates", lambda a: {"path": a.get("path", ".")}, _result_to_str),
    "take_ownership":      ("filesystem", "take_ownership", _identity_params, _result_to_str),

    # -- Media -> routed through daemon input layer (media key simulation) ----
    "media_play_pause":   ("input", "hotkey", lambda a: {"combo": "play_pause"}, _result_to_str),
    "media_next":         ("input", "hotkey", lambda a: {"combo": "media_next"}, _result_to_str),
    "media_previous":     ("input", "hotkey", lambda a: {"combo": "media_prev"}, _result_to_str),
    "media_stop":         ("input", "hotkey", lambda a: {"combo": "media_stop"}, _result_to_str),

    # -- Mouse -> routed through daemon input layer ----------------------------
    "mouse_click":        ("input", "left_click", lambda a: {"x": a.get("x", 0), "y": a.get("y", 0)}, _result_to_str),
    "get_mouse_position": ("input", "get_cursor_position", _empty_params, _result_to_str),
    "screenshot":         ("input", "screenshot_full", lambda a: {"output": a.get("path", "screenshot.png")}, _result_to_str),

    # -- Volume relative -> routed through daemon system layer -----------------
    "volume_up":          ("system", "volume_up", lambda a: {"delta": a.get("delta", 15)}, _result_to_str),
    "volume_down":        ("system", "volume_down", lambda a: {"delta": a.get("delta", 15)}, _result_to_str),

    # -- Registry (L6) --------------------------------------------------------
    "enable_dark_mode":   ("registry", "enable_dark_mode",  _empty_params, _result_to_str),
    "enable_light_mode":  ("registry", "enable_light_mode", _empty_params, _result_to_str),

    # -- Browser web helpers (L9) ---------------------------------------------
    "web_search":         ("browser", "web_search",  lambda a: {"query": a.get("query", "")}, _result_to_str),
    "open_url":           ("browser", "open_url",    lambda a: {"url": a.get("url", "")}, _result_to_str),
    "extract_web_content": ("browser", "extract_web_content", lambda a: {"url": a.get("url", "")}, _result_to_str),

    # -- System helpers (L8) --------------------------------------------------
    "get_time":           ("system", "get_time",       _empty_params, _result_to_str),
    "get_date":           ("system", "get_date",       _empty_params, _result_to_str),
    "send_email":         ("system", "send_email",     _identity_params, _result_to_str),
    "set_reminder":       ("system", "set_reminder",   _identity_params, _result_to_str),
    "run_powershell":     ("system", "run_powershell", lambda a: {"command": a.get("command", "")}, _result_to_str),
    "list_usb_devices":   ("system", "list_usb_devices",   _empty_params, _result_to_str),
    "list_audio_devices": ("system", "list_audio_devices", _empty_params, _result_to_str),
    "list_printers":      ("system", "list_printers",      _empty_params, _result_to_str),
    "test_internet":      ("system", "test_internet",      _empty_params, _result_to_str),

    # -- Application helpers (L3) ---------------------------------------------
    "install_app":        ("application", "install_app",     lambda a: {"package": a.get("package", "")}, _result_to_str),
    "search_packages":    ("application", "search_packages", lambda a: {"query": a.get("query", "")}, _result_to_str),
    "open_file_with":     ("application", "open_file_with",  _identity_params, _result_to_str),
    "open_settings":      ("application", "open_settings",   _identity_params, _result_to_str),

    # -- Filesystem helpers (L1) ----------------------------------------------
    "search_content":     ("filesystem", "search_content",  _identity_params, _result_to_str),
    "find_and_replace":   ("filesystem", "find_and_replace", _identity_params, _result_to_str),
    "get_large_files":    ("filesystem", "find_large_files", lambda a: {"path": a.get("directory", "."), "min_size_mb": a.get("min_size_mb", 100)}, _result_to_str),
    "batch_rename":       ("filesystem", "batch_rename",    _identity_params, _result_to_str),
    "batch_delete":       ("filesystem", "batch_delete",    _identity_params, _result_to_str),

    # -- UIAutomation (L16) -- Accessibility Tree --------------------------
    "inspect_ui_tree":         ("uiautomation", "inspect_ui_tree",         _identity_params, _result_to_str),
    "find_ui_element":         ("uiautomation", "find_ui_element",         _identity_params, _result_to_str),
    "click_ui_element":        ("uiautomation", "click_ui_element",        _identity_params, _result_to_str),
    "double_click_ui_element": ("uiautomation", "double_click_ui_element", _identity_params, _result_to_str),
    "right_click_ui_element":  ("uiautomation", "right_click_ui_element",  _identity_params, _result_to_str),
    "type_into_ui_element":    ("uiautomation", "type_into_ui_element",    _identity_params, _result_to_str),
    "select_ui_dropdown":      ("uiautomation", "select_ui_dropdown",      _identity_params, _result_to_str),
    "toggle_ui_checkbox":      ("uiautomation", "toggle_ui_checkbox",      _identity_params, _result_to_str),
    "read_ui_text":            ("uiautomation", "read_ui_text",            _identity_params, _result_to_str),
    "set_ui_value":            ("uiautomation", "set_ui_value",            _identity_params, _result_to_str),
    "get_ui_state":            ("uiautomation", "get_ui_state",            _identity_params, _result_to_str),

    # -- Verification (L16) -- Post-Action Screenshot Verification --------
    "take_action_verify":    ("verify", "take_action_verify",    _identity_params, _result_to_str),
    "verify_element_exists": ("verify", "verify_element_exists", _identity_params, _result_to_str),
    "verify_no_error":       ("verify", "verify_no_error",       _identity_params, _result_to_str),
    "compare_screenshots":   ("verify", "compare_screenshots",   _identity_params, _result_to_str),

    # -- Wait Tools (L16) -- Prevent type_text / click failures ----------
    "wait_for_app":     ("uiautomation", "wait_for_app",     _identity_params, _result_to_str),
    "wait_for_element": ("uiautomation", "wait_for_element", _identity_params, _result_to_str),
    "wait_for_text":    ("uiautomation", "wait_for_text",    _identity_params, _result_to_str),

    # -- Skills (direct, handled by jarvis.py via skill_store) -----------
    "list_skills":       (None, None, None, None),
    "execute_skill":     (None, None, None, None),
    "delete_skill":      (None, None, None, None),
    "search_skills":     (None, None, None, None),

# -- Direct-only (external API, no daemon equivalent) ----------------------
    "get_weather":        (None, None, None, None),
    "describe_screen":    (None, None, None, None),

    # -- Email (HTTP API, handled by jarvis.py before core_bridge) ------------
    "get_unread_emails":  (None, None, None, None),
    "get_unread_count":   (None, None, None, None),
    "search_emails":      (None, None, None, None),
    "read_email":         (None, None, None, None),
    "get_recent_emails":  (None, None, None, None),

    # -- Wellness (HTTP API, handled by jarvis.py before core_bridge) ----------
    "get_wellness_status":      (None, None, None, None),
    "get_wellness_suggestions": (None, None, None, None),
    "set_wellness_rule":        (None, None, None, None),

    # -- Meeting mode (HTTP API, handled by jarvis.py before core_bridge) ------
    "start_meeting":      (None, None, None, None),
    "stop_meeting":       (None, None, None, None),
    "meeting_status":     (None, None, None, None),

    # -- Ghost mode (HTTP API, handled by jarvis.py before core_bridge) --------
    "queue_ghost_task":   (None, None, None, None),
    "ghost_status":      (None, None, None, None),
    "cancel_ghost_task":  (None, None, None, None),
    "cancel_all_ghost_tasks": (None, None, None, None),

    # -- Voice biometrics (HTTP API, handled by jarvis.py before core_bridge) --
    "voice_enroll":       (None, None, None, None),
    "voice_verify":       (None, None, None, None),
    "biometrics_status":  (None, None, None, None),
    "biometrics_toggle":  (None, None, None, None),
    "biometrics_delete":  (None, None, None, None),

    # -- L12 Developer additions --
    "git_clone":          ("developer", "git_clone",          _identity_params, _result_to_str),
    "run_code":           ("developer", "run_code",           _identity_params, _result_to_str),
    "docker_list":        ("developer", "docker_list",        _identity_params, _result_to_str),
    "docker_start":       ("developer", "docker_start",       _identity_params, _result_to_str),
    "docker_stop":        ("developer", "docker_stop",        _identity_params, _result_to_str),
    "database_query":     ("developer", "database_query",     _identity_params, _result_to_str),
    "port_scan":          ("developer", "port_scan",          _identity_params, _result_to_str),

    # -- L14 Automation additions --
    "list_startup_programs":   ("automation", "list_startup_programs",   _empty_params, _result_to_str),
    "enable_startup_program":  ("automation", "enable_startup_program",  _identity_params, _result_to_str),
    "disable_startup_program": ("automation", "disable_startup_program", _identity_params, _result_to_str),
    "clipboard_history":       ("automation", "clipboard_history",       _empty_params, _result_to_str),
    "toggle_airplane_mode":    ("automation", "toggle_airplane_mode",    _identity_params, _result_to_str),
    "toggle_bluetooth":        ("automation", "toggle_bluetooth",        _identity_params, _result_to_str),
    "set_wallpaper":           ("automation", "set_wallpaper",           _identity_params, _result_to_str),
    "list_recent_files":       ("automation", "list_recent_files",       _empty_params, _result_to_str),
    "create_restore_point":    ("automation", "create_restore_point",    _identity_params, _result_to_str),
    "list_user_accounts":      ("automation", "list_user_accounts",      _empty_params, _result_to_str),

    # -- L17 Content Tools --
    "calculate":          ("content_tools", "calculate",          _identity_params, _result_to_str),
    "unit_convert":       ("content_tools", "unit_convert",       _identity_params, _result_to_str),
    "timer":              ("content_tools", "timer",              _identity_params, _result_to_str),
    "speed_test":         ("content_tools", "speed_test",         _empty_params, _result_to_str),
    "hash_string":        ("content_tools", "hash_string",        _identity_params, _result_to_str),
    "base64_encode":      ("content_tools", "base64_encode",      _identity_params, _result_to_str),
    "base64_decode":      ("content_tools", "base64_decode",      _identity_params, _result_to_str),
    "create_qr_code":     ("content_tools", "create_qr_code",     _identity_params, _result_to_str),
    "json_format":        ("content_tools", "json_format",        _identity_params, _result_to_str),
    "csv_to_json":        ("content_tools", "csv_to_json",        _identity_params, _result_to_str),
    "json_to_csv":        ("content_tools", "json_to_csv",        _identity_params, _result_to_str),
    "compare_images":     ("content_tools", "compare_images",     _identity_params, _result_to_str),
}


# -- Direct tool handlers (for tools with no core mapping) --------------------
# Inline implementations using subprocess/asyncio -- no SystemControl dependency.

import subprocess as _subprocess


async def _run_ps_inline(command: str, timeout: float = 15) -> str:
    """Run a PowerShell command and return stdout."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-Command", command,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode("utf-8", errors="replace").strip()
    except Exception as e:
        return f"Error: {e}"


async def _handle_direct_tool(name: str, args: dict) -> str:
    """Handle tools that don't map to the control core (fallback when daemon is down).

    NOTE: Nearly all tools now route through daemon layers.
    This serves as a last-resort inline fallback for daemon-unreachable scenarios,
    using PowerShell subprocess calls to avoid requiring the daemon process.
    """

    # -- Weather (external HTTP API -- no daemon layer) ----------------------
    if name == "get_weather":
        import httpx as _httpx
        query = args.get("location", "") or "auto:ip"
        async with _httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"https://wttr.in/{query}", params={"format": "%C %t %h %w"})
            return resp.text.strip()

    # -- Media keys (PowerShell keybd_event) ---------------------------------
    media_vk_codes = {
        "media_play_pause": 179,  # 0xB3
        "media_next":       176,  # 0xB0
        "media_previous":   177,  # 0xB1
        "media_stop":       178,  # 0xB2
    }
    if name in media_vk_codes:
        vk = media_vk_codes[name]
        ps = (
            "Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
            "public class KeySender {\n"
            '  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);\n'
            "}\n'@\n"
            f"[KeySender]::keybd_event({vk}, 0, 0, [UIntPtr]::Zero); "
            f"[KeySender]::keybd_event({vk}, 0, 2, [UIntPtr]::Zero)"
        )
        await _run_ps_inline(ps)
        return f"Media action '{name}' executed via fallback"

    # -- Mouse click (PowerShell mouse_event) --------------------------------
    if name == "mouse_click":
        x, y = args.get("x", 0), args.get("y", 0)
        ps = (
            f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
            "public class Mouse {\n"
            '  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, IntPtr dwExtraInfo);\n'
            '  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);\n'
            "}\n'@\n"
            f"[Mouse]::SetCursorPos({x}, {y}); Start-Sleep -Milliseconds 50; "
            f"[Mouse]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero); "
            f"Start-Sleep -Milliseconds 50; "
            f"[Mouse]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero)"
        )
        await _run_ps_inline(ps)
        return f"Mouse click at ({x}, {y}) executed via fallback"

    # -- Screenshot (PowerShell System.Drawing) ------------------------------
    if name == "screenshot":
        output = args.get("path", "screenshot.png")
        ps = (
            f"Add-Type -AssemblyName System.Windows.Forms; "
            f"Add-Type -AssemblyName System.Drawing; "
            f"$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            f"$bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height); "
            f"$g = [System.Drawing.Graphics]::FromImage($bmp); "
            f"$g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size); "
            f"$bmp.Save('{output}')"
        )
        await _run_ps_inline(ps)
        return f"Screenshot saved to {output} via fallback"

    # -- run_powershell (just run it directly -- the irony!) ------------------
    if name == "run_powershell":
        command = args.get("command", "")
        if not command:
            return "Error: no command provided"
        output = await _run_ps_inline(command, timeout=30)
        return output or "Done"

    # -- read_file (Python open) ----------------------------------------------
    if name == "read_file":
        path = args.get("path", "")
        if not path:
            return "Error: no path provided"
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(50_000)
            return content if content else "(empty file)"
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except Exception as e:
            return f"Error reading {path}: {e}"

    # -- write_file (Python open) ---------------------------------------------
    if name == "write_file":
        path = args.get("path", "")
        content = args.get("content", "")
        if not path:
            return "Error: no path provided"
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Written {len(content)} chars to {path}"
        except Exception as e:
            return f"Error writing {path}: {e}"

    # -- list_directory (Python pathlib) --------------------------------------
    if name == "list_directory":
        from pathlib import Path as _Path
        path = args.get("path", ".")
        try:
            p = _Path(path)
            if not p.exists():
                return f"Error: directory not found: {path}"
            if not p.is_dir():
                return f"Error: not a directory: {path}"
            entries = []
            for item in sorted(p.iterdir()):
                kind = "[DIR]" if item.is_dir() else "     "
                size = "" if item.is_dir() else f"  {item.stat().st_size:>10,} bytes"
                entries.append(f"{kind} {item.name}{size}")
            if not entries:
                return f"Empty directory: {path}"
            return "\n".join(entries[:100]) + (f"\n  ... {len(entries) - 100} more" if len(entries) > 100 else "")
        except Exception as e:
            return f"Error listing {path}: {e}"

    # -- open_app / open_folder (cmd /c start) -------------------------------
    if name in ("open_app", "open_folder"):
        app = args.get("app_name", "") or args.get("path", "")
        if not app:
            return "Error: no app_name or path provided"
        try:
            proc = await asyncio.create_subprocess_exec(
                "cmd", "/c", "start", "", app,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10)
            return f"Opened {app} via fallback"
        except FileNotFoundError:
            return f"Error: not found: {app}"
        except Exception as e:
            return f"Error opening {app}: {e}"

    # -- search_files (PowerShell Get-ChildItem) -------------------------------
    if name == "search_files":
        path = args.get("path", args.get("directory", "."))
        pattern = args.get("pattern", "*")
        ps = (
            f"Get-ChildItem -Path '{path}' -Filter '{pattern}' -Recurse -ErrorAction SilentlyContinue "
            f"| Select-Object -First 50 FullName, Length, LastWriteTime "
            f"| ConvertTo-Json -Compress"
        )
        output = await _run_ps_inline(ps)
        if not output or output.startswith("Error"):
            return f"No files found matching '{pattern}' in {path}"
        try:
            import json as _json
            data = _json.loads(output)
            if isinstance(data, dict):
                data = [data]
            lines = [f"  {f.get('FullName', '?')} ({f.get('Length', 0)} bytes)" for f in data]
            return f"Found {len(data)} file(s):\n" + "\n".join(lines)
        except Exception:
            return output[:500]

    # -- get_file_info (PowerShell) -------------------------------------------
    if name == "get_file_info":
        path = args.get("path", "")
        if not path:
            return "Error: no path provided"
        ps = f"Get-Item '{path}' | Select-Object FullName, Length, LastWriteTime, CreationTime, Extension | ConvertTo-Json -Compress"
        output = await _run_ps_inline(ps)
        if not output or output.startswith("Error"):
            return f"File not found: {path}"
        return output

    # -- get_folder_size (PowerShell) -----------------------------------------
    if name == "get_folder_size":
        path = args.get("path", args.get("directory", "."))
        ps = f"(Get-ChildItem '{path}' -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum"
        output = await _run_ps_inline(ps)
        if output and output.isdigit():
            size = int(output)
            return f"Folder size: {size / (1024**3):.2f} GB ({size:,} bytes)"
        return f"Could not get size for {path}"

    # -- copy_file (PowerShell Copy-Item) -------------------------------------
    if name == "copy_file":
        source = args.get("source", "")
        destination = args.get("destination", "")
        if not source or not destination:
            return "Error: source and destination required"
        ps = f"Copy-Item '{source}' '{destination}' -Force -ErrorAction Stop"
        output = await _run_ps_inline(ps)
        return f"Copied {source} to {destination}" if not output.startswith("Error") else output

    # -- move_file (PowerShell Move-Item) -------------------------------------
    if name == "move_file":
        source = args.get("source", "")
        destination = args.get("destination", "")
        if not source or not destination:
            return "Error: source and destination required"
        ps = f"Move-Item '{source}' '{destination}' -Force -ErrorAction Stop"
        output = await _run_ps_inline(ps)
        return f"Moved {source} to {destination}" if not output.startswith("Error") else output

    # -- delete_file (PowerShell Remove-Item) ---------------------------------
    if name == "delete_file":
        path = args.get("path", "")
        if not path:
            return "Error: no path provided"
        ps = f"Remove-Item '{path}' -Force -ErrorAction Stop"
        output = await _run_ps_inline(ps)
        return f"Deleted {path}" if not output.startswith("Error") else output

    # -- create_folder (PowerShell New-Item) ----------------------------------
    if name == "create_folder":
        path = args.get("path", "")
        if not path:
            return "Error: no path provided"
        ps = f"New-Item -ItemType Directory -Path '{path}' -Force -ErrorAction Stop"
        output = await _run_ps_inline(ps)
        return f"Created folder {path}" if not output.startswith("Error") else output

    # -- kill_process (PowerShell taskkill) -----------------------------------
    if name == "kill_process":
        pid = args.get("pid")
        name_proc = args.get("name", "")
        if pid:
            ps = f"taskkill /F /PID {pid}"
        elif name_proc:
            exe = name_proc if name_proc.endswith(".exe") else f"{name_proc}.exe"
            ps = f"taskkill /F /IM {exe}"
        else:
            return "Error: pid or name required"
        output = await _run_ps_inline(ps)
        return f"Killed process" if not output.startswith("Error") else output

    # -- get_process_info (PowerShell) ----------------------------------------
    if name == "get_process_info":
        name_proc = args.get("name", "")
        pid = args.get("pid")
        if pid:
            ps = f"Get-Process -Id {pid} | Select-Object Id, ProcessName, CPU, WorkingSet64 | ConvertTo-Json -Compress"
        elif name_proc:
            ps = f"Get-Process -Name '{name_proc}' | Select-Object -First 5 Id, ProcessName, CPU, WorkingSet64 | ConvertTo-Json -Compress"
        else:
            return "Error: name or pid required"
        output = await _run_ps_inline(ps)
        return output if output else "Process not found"

    # -- list_installed_apps (PowerShell winget/registry) ---------------------
    if name == "list_installed_apps":
        ps = "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Select-Object DisplayName, DisplayVersion | Where-Object { \$_.DisplayName } | Sort-Object DisplayName | ConvertTo-Json -Compress"
        output = await _run_ps_inline(ps)
        if not output or output.startswith("Error"):
            return "No installed apps found"
        try:
            import json as _json
            data = _json.loads(output)
            if isinstance(data, dict):
                data = [data]
            lines = [f"  {a.get('DisplayName', '?')} {a.get('DisplayVersion', '')}" for a in data[:50]]
            return f"{len(data)} apps:\n" + "\n".join(lines)
        except Exception:
            return output[:500]

    # -- get_app_path (PowerShell registry) -----------------------------------
    if name == "get_app_path":
        name_proc = args.get("app_name", "")
        if not name_proc:
            return "Error: no app_name provided"
        ps = (
            f"Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*, "
            f"HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* "
            f"| Where-Object {{ \$_.DisplayName -like '*{name_proc}*' }} "
            f"| Select-Object -First 1 InstallLocation, DisplayIcon | ConvertTo-Json -Compress"
        )
        output = await _run_ps_inline(ps)
        if not output or output.startswith("Error"):
            return f"App '{name_proc}' not found in registry"
        return output

    # -- force_close_app (PowerShell taskkill /F) -----------------------------
    if name == "force_close_app":
        app = args.get("app_name", "")
        if not app:
            return "Error: no app_name provided"
        exe = app if app.lower().endswith(".exe") else f"{app}.exe"
        ps = f"taskkill /F /IM {exe}"
        output = await _run_ps_inline(ps)
        return f"Force-closed {app}" if not output.startswith("Error") else output

    # -- close_app (PowerShell taskkill with exact match) --------------------
    if name == "close_app":
        import psutil as _psutil
        app = args.get("app_name", "")
        if not app:
            return "Error: no app_name provided"
        app_lower = app.lower().strip()
        # Don't close system processes
        if app_lower in {"explorer", "svchost", "csrss", "wininit", "smss", "lsass", "services"}:
            return f"Error: '{app}' is a system process and cannot be closed"
        # Try to get exact exe name from known apps
        exact_name = None
        known_apps = {
            "chrome": "chrome.exe", "discord": "Discord.exe", "spotify": "Spotify.exe",
            "vscode": "Code.exe", "notepad": "notepad.exe", "calculator": "Calculator.exe",
            "edge": "msedge.exe", "firefox": "firefox.exe", "steam": "steam.exe",
            "slack": "slack.exe", "teams": "Teams.exe", "zoom": "Zoom.exe",
        }
        exact_name = known_apps.get(app_lower)
        
        closed_count = 0
        killed_pids = []
        for p in _psutil.process_iter(["pid", "name", "exe"]):
            try:
                p_name = p.info["name"].lower() if p.info["name"] else ""
                p_exe = p.info["exe"].lower() if p.info["exe"] else ""
                
                matched = False
                if exact_name:
                    matched = (p_name == exact_name.lower()) or (p_exe and os.path.basename(p_exe).lower() == exact_name.lower())
                else:
                    # Exact match on name or exe basename
                    matched = (p_name == app_lower) or (p_exe and os.path.basename(p_exe).lower() == app_lower)
                
                if matched:
                    p.terminate()
                    closed_count += 1
                    killed_pids.append(p.info["pid"])
            except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                pass
            except Exception:
                pass
        
        if closed_count > 0:
            await asyncio.sleep(0.3)
            still_running = False
            for p in _psutil.process_iter(["name", "exe"]):
                try:
                    p_name = p.info["name"].lower() if p.info["name"] else ""
                    p_exe = p.info["exe"].lower() if p.info["exe"] else ""
                    if exact_name:
                        matched = (p_name == exact_name.lower()) or (p_exe and os.path.basename(p_exe).lower() == exact_name.lower())
                    else:
                        matched = (p_name == app_lower) or (p_exe and os.path.basename(p_exe).lower() == app_lower)
                    if matched:
                        still_running = True
                        break
                except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                    pass
                except Exception:
                    pass
            if not still_running:
                return f"Closed {app} gracefully ({closed_count} process(es))"
        
        # Strategy 2: Force kill via taskkill /F
        exe_name = app if app.lower().endswith(".exe") else f"{app}.exe"
        if exact_name:
            exe_name = exact_name
        try:
            proc = await asyncio.create_subprocess_exec(
                "taskkill", "/F", "/IM", exe_name,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode == 0:
                return f"Force-closed {app} via taskkill"
            # Try psutil force kill
            for p in _psutil.process_iter(["name", "exe"]):
                try:
                    p_name = p.info["name"].lower() if p.info["name"] else ""
                    p_exe = p.info["exe"].lower() if p.info["exe"] else ""
                    if exact_name:
                        matched = (p_name == exact_name.lower()) or (p_exe and os.path.basename(p_exe).lower() == exact_name.lower())
                    else:
                        matched = (p_name == app_lower) or (p_exe and os.path.basename(p_exe).lower() == app_lower)
                    if matched:
                        p.kill()
                except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                    pass
                except Exception:
                    pass
            await asyncio.sleep(0.2)
            # Final check
            for p in _psutil.process_iter(["name", "exe"]):
                try:
                    p_name = p.info["name"].lower() if p.info["name"] else ""
                    p_exe = p.info["exe"].lower() if p.info["exe"] else ""
                    if exact_name:
                        matched = (p_name == exact_name.lower()) or (p_exe and os.path.basename(p_exe).lower() == exact_name.lower())
                    else:
                        matched = (p_name == app_lower) or (p_exe and os.path.basename(p_exe).lower() == app_lower)
                    if matched:
                        return f"Error: could not close '{app}' — process may require elevated privileges"
                except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                    pass
                except Exception:
                    pass
            return f"Closed {app} via force kill"
        except Exception as e:
            return f"Error closing {app}: {e}"

    # -- is_app_running (PowerShell Get-Process) ------------------------------
    if name == "is_app_running":
        name_proc = args.get("app_name", "")
        if not name_proc:
            return "Error: no app_name provided"
        ps = f"Get-Process -Name '{name_proc}' -ErrorAction SilentlyContinue | Select-Object Id, ProcessName | ConvertTo-Json -Compress"
        output = await _run_ps_inline(ps)
        if not output or output.startswith("Error") or output.strip() == "[]":
            return f"{name_proc}: not running"
        try:
            import json as _json
            data = _json.loads(output)
            if isinstance(data, dict):
                data = [data]
            lines = [f"  PID {p.get('Id', '?')}: {p.get('ProcessName', '?')}" for p in data]
            return f"{name_proc} is running ({len(data)} instance(s)):\n" + "\n".join(lines)
        except Exception:
            return output[:500]

    # -- mute / unmute (pycaw) ------------------------------------------------
    if name == "mute":
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            from ctypes import cast, POINTER
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(interface, POINTER(IAudioEndpointVolume))
            vol.SetMute(True, None)
            return "Muted"
        except Exception as e:
            return f"Error muting: {e}"

    if name == "unmute":
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            from ctypes import cast, POINTER
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(interface, POINTER(IAudioEndpointVolume))
            vol.SetMute(False, None)
            return "Unmuted"
        except Exception as e:
            return f"Error unmuting: {e}"

    # -- shutdown_pc / restart_pc / sleep_pc / lock_pc ------------------------
    if name == "shutdown_pc":
        delay = args.get("delay", 0)
        ps = f"shutdown /s /t {delay}"
        await _run_ps_inline(ps)
        return f"Shutdown scheduled in {delay} seconds"

    if name == "restart_pc":
        delay = args.get("delay", 0)
        ps = f"shutdown /r /t {delay}"
        await _run_ps_inline(ps)
        return f"Restart scheduled in {delay} seconds"

    if name == "sleep_pc":
        ps = "rundll32.exe powrprof.dll,SetSuspendState 0,1,0"
        await _run_ps_inline(ps)
        return "Sleep initiated"

    if name == "lock_pc":
        ps = "rundll32.exe user32.dll,LockWorkStation"
        await _run_ps_inline(ps)
        return "Screen locked"

    # -- cancel_shutdown ------------------------------------------------------
    if name == "cancel_shutdown":
        ps = "shutdown /a"
        await _run_ps_inline(ps)
        return "Shutdown cancelled"

    # -- get_public_ip --------------------------------------------------------
    if name == "get_public_ip":
        try:
            import httpx as _httpx
            async with _httpx.AsyncClient(timeout=5) as client:
                resp = await client.get("https://api.ipify.org?format=text")
                return f"Public IP: {resp.text.strip()}"
        except Exception as e:
            return f"Error getting public IP: {e}"

    # -- get_wifi_password ----------------------------------------------------
    if name == "get_wifi_password":
        try:
            ps = "netsh wlan show profiles"
            output = await _run_ps_inline(ps)
            if not output:
                return "No WiFi profiles found"
            lines = output.splitlines()
            profiles = []
            for line in lines:
                if "All User Profile" in line:
                    profile = line.split(":")[-1].strip()
                    profiles.append(profile)
            
            results = []
            for profile in profiles[:5]:
                ps2 = f'netsh wlan show profile name="{profile}" key=clear'
                out2 = await _run_ps_inline(ps2)
                for l in out2.splitlines():
                    if "Key Content" in l:
                        pwd = l.split(":")[-1].strip()
                        results.append(f"  {profile}: {pwd}")
                        break
            return "WiFi passwords:\n" + "\n".join(results) if results else "No passwords found"
        except Exception as e:
            return f"Error: {e}"

    # -- get_env_var / list_env_vars ------------------------------------------
    if name == "get_env_var":
        name_var = args.get("name", "")
        if not name_var:
            return "Error: no name provided"
        value = os.environ.get(name_var)
        return f"{name_var} = {value}" if value else f"{name_var} not set"

    if name == "list_env_vars":
        filter_str = args.get("filter", "").lower()
        vars_dict = {k: v for k, v in os.environ.items() if not filter_str or filter_str in k.lower()}
        lines = [f"  {k} = {v[:100]}" for k, v in list(vars_dict.items())[:30]]
        return f"{len(vars_dict)} env vars:\n" + "\n".join(lines)

    # -- connect_wifi / disconnect_wifi ---------------------------------------
    if name == "connect_wifi":
        ssid = args.get("ssid", "")
        password = args.get("password", "")
        if not ssid:
            return "Error: no ssid provided"
        ps = f'netsh wlan connect name="{ssid}"'
        if password:
            ps += f' key="{password}"'
        await _run_ps_inline(ps)
        return f"Connecting to {ssid}..."

    if name == "disconnect_wifi":
        await _run_ps_inline("netsh wlan disconnect")
        return "Disconnected from WiFi"

    # -- flush_dns ------------------------------------------------------------
    if name == "flush_dns":
        await _run_ps_inline("ipconfig /flushdns")
        return "DNS cache flushed"

    # -- add_firewall_rule ----------------------------------------------------
    if name == "add_firewall_rule":
        name_rule = args.get("name", "May Rule")
        direction = args.get("direction", "in")
        action = args.get("action", "allow")
        protocol = args.get("protocol", "TCP")
        port = args.get("port", "")
        ps = f'New-NetFirewallRule -DisplayName "{name_rule}" -Direction {direction} -Action {action} -Protocol {protocol}'
        if port:
            ps += f" -LocalPort {port}"
        await _run_ps_inline(ps)
        return f"Firewall rule '{name_rule}' added"

    # -- logoff ---------------------------------------------------------------
    if name == "logoff":
        await _run_ps_inline("shutdown /l")
        return "Logging off..."

    # -- get_audio_devices ----------------------------------------------------
    if name == "get_audio_devices":
        try:
            from pycaw.pycaw import AudioUtilities
            devices = AudioUtilities.GetAllDevices()
            lines = []
            for d in devices:
                lines.append(f"  {d.FriendlyName} ({d.Id[:50]})")
            return "Audio devices:\n" + "\n".join(lines[:20])
        except Exception as e:
            return f"Error: {e}"

    # -- rotate_display -------------------------------------------------------
    if name == "rotate_display":
        orientation = args.get("orientation", "0")
        ps = f"(Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBasicDisplayParams).InstanceName | ForEach-Object {{ (Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBrightnessMethods -Filter \"InstanceName='$_'\").WmiSetBrightness(1, {orientation}) }}"
        await _run_ps_inline(ps)
        return f"Display rotation set to {orientation}"

    # -- enable_adapter / disable_adapter -------------------------------------
    if name == "enable_adapter":
        adapter = args.get("name", "Wi-Fi")
        ps = f'Enable-NetAdapter -Name "{adapter}" -Confirm:$false'
        await _run_ps_inline(ps)
        return f"Enabled adapter: {adapter}"

    if name == "disable_adapter":
        adapter = args.get("name", "Wi-Fi")
        ps = f'Disable-NetAdapter -Name "{adapter}" -Confirm:$false'
        await _run_ps_inline(ps)
        return f"Disabled adapter: {adapter}"

    # -- list_wifi_networks ---------------------------------------------------
    if name == "list_wifi_networks":
        ps = "netsh wlan show networks mode=bssid"
        output = await _run_ps_inline(ps)
        return output if output else "No networks found"

    # -- get_os_info ----------------------------------------------------------
    if name == "get_os_info":
        import platform
        return f"OS: {platform.system()} {platform.release()} ({platform.version()})"

    # -- send_keys (PowerShell SendKeys) --------------------------------------
    if name == "send_keys":
        keys = args.get("keys", "")
        if not keys:
            return "Error: no keys provided"
        ps = f"$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys('{keys}')"
        await _run_ps_inline(ps)
        return f"Sent keys: {keys}"

    # -- type_text (PowerShell SendKeys) --------------------------------------
    if name == "type_text":
        text = args.get("text", "")
        if not text:
            return "Error: no text provided"
        escaped = text.replace("{", "{{").replace("}", "}}").replace("+", "{+}").replace("^", "{^}").replace("%", "{%}").replace("~", "{~}")
        ps = f"$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys('{escaped}')"
        await _run_ps_inline(ps)
        return f"Typed: {text[:50]}..."

    # -- get_clipboard / set_clipboard ----------------------------------------
    if name == "get_clipboard":
        ps = "Get-Clipboard"
        output = await _run_ps_inline(ps)
        return output if output else "(clipboard empty)"

    if name == "set_clipboard":
        text = args.get("text", args.get("content", ""))
        if not text:
            return "Error: no text provided"
        ps = f"Set-Clipboard -Value '{text}'"
        await _run_ps_inline(ps)
        return "Clipboard set"

    # -- web_search (PowerShell Invoke-WebRequest to duckduckgo/html) ---------
    if name == "web_search":
        query = args.get("query", "")
        if not query:
            return "Error: no query provided"
        ps = f"Invoke-WebRequest -Uri 'https://html.duckduckgo.com/html/?q={query}' -UseBasicParsing | Select-Object -ExpandProperty Content"
        output = await _run_ps_inline(ps, timeout=15)
        if not output:
            return "No results"
        import re
        snippets = re.findall(r'class="result__snippet">(.*?)</a>', output)
        if snippets:
            return "Search results:\n" + "\n".join([f"  - {s[:200]}" for s in snippets[:5]])
        return output[:500]

    # -- open_url -------------------------------------------------------------
    if name == "open_url":
        url = args.get("url", "")
        if not url:
            return "Error: no url provided"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        ps = f"Start-Process '{url}'"
        await _run_ps_inline(ps)
        return f"Opened {url}"

    # -- describe_screen (screenshot + vision API) -----------------------------
    if name == "describe_screen":
        import base64 as _b64
        import tempfile as _tmp
        question = args.get("question", "") or "Describe what you see on this screen in detail."
        screenshot_path = os.path.join(_tmp.gettempdir(), "may_screenshot.png")
        try:
            ps = (
                f"Add-Type -AssemblyName System.Windows.Forms; "
                f"Add-Type -AssemblyName System.Drawing; "
                f"$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
                f"$bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height); "
                f"$g = [System.Drawing.Graphics]::FromImage($bmp); "
                f"$g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size); "
                f"$bmp.Save('{screenshot_path}')"
            )
            await _run_ps_inline(ps, timeout=10)
        except Exception as e:
            return f"Error taking screenshot: {e}"
        try:
            with open(screenshot_path, "rb") as f:
                img_b64 = _b64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return f"Error reading screenshot: {e}"
        finally:
            try:
                os.remove(screenshot_path)
            except OSError:
                pass
        try:
            import httpx as _httpx
            from llm.providers import get_api_key
            api_key = None
            base_url = None
            model = None
            for prov in ["openai", "openrouter", "gemini", "google_ai_studio"]:
                try:
                    key = get_api_key(prov)
                    if key:
                        api_key = key
                        if prov == "openai":
                            base_url = "https://api.openai.com/v1"
                            model = "gpt-4o"
                        elif prov == "openrouter":
                            base_url = "https://openrouter.ai/api/v1"
                            model = "openai/gpt-4o"
                        elif prov in ("gemini", "google_ai_studio"):
                            base_url = "https://generativelanguage.googleapis.com/v1beta"
                            model = "gemini-2.0-flash"
                        break
                except Exception:
                    continue
            if not api_key:
                return "No vision-capable API key configured. Add an OpenAI, OpenRouter, Gemini, or Google AI Studio API key in Settings."
            if "gemini" in (base_url or ""):
                url = f"{base_url}/models/{model}:generateContent?key={api_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": question},
                            {"inline_data": {"mime_type": "image/png", "data": img_b64}}
                        ]
                    }]
                }
                async with _httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    return text or "No description available."
            else:
                url = f"{base_url}/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                        ]
                    }],
                    "max_tokens": 1024,
                }
                async with _httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return text or "No description available."
        except Exception as e:
            return f"Vision API error: {e}"

    return f"Direct handler not implemented for tool: {name}"


# -- Per-action timeout overrides (seconds) -----------------------------------
# Some actions need longer than the default 10s due to subprocess calls
# (winget install, registry searches, etc.).
_ACTION_TIMEOUTS: dict[str, float] = {
    # Application layer — winget operations are slow
    "install_app":        120.0,
    "uninstall_app":      120.0,
    "search_packages":     30.0,
    "list_installed_apps": 30.0,
    "find_app_by_name":    30.0,
    "get_app_path":        15.0,
    "get_app_version":     15.0,
    "launch_app":          15.0,
    "launch_with_args":    15.0,
    "launch_as_admin":     15.0,
    "force_close_app":     15.0,
    "close_app":           15.0,
    "restart_app":         15.0,
    # Filesystem layer — large directory operations
    "search_files":        15.0,
    "search_content":      20.0,
    "get_folder_size":     20.0,
    "find_large_files":    20.0,
    "find_duplicates":     30.0,
    # System layer — network/hardware queries
    "get_wifi_password":   15.0,
    "list_wifi_networks":  20.0,
    "get_network_info":    15.0,
    # Browser layer — Playwright operations
    "browser_navigate":    15.0,
    "browser_wait_for":    15.0,
    "extract_web_content": 20.0,
    # Services layer — subprocess + service control manager
    "enable_service":      15.0,
    "disable_service":     15.0,
    "restart_service":     20.0,
    "start_service":       15.0,
    "stop_service":        15.0,
}


async def execute_tool_via_core(name: str, args: dict) -> str:
    """Execute a tool call by routing through the control core daemon.

    Tries TCP first. Falls back to direct execution if daemon is not running
    or the tool has no core mapping.

    Returns a human-readable string result for the LLM.
    """
    mapping = TOOL_CORE_MAP.get(name)

    # -- Unknown tool --
    if mapping is None and name not in TOOL_CORE_MAP:
        return f"Unknown tool: {name}"

    # -- Direct tool (no core mapping) --
    layer, action, param_tf, result_tf = mapping
    if layer is None:
        try:
            return await _handle_direct_tool(name, args)
        except Exception as e:
            logger.error("Direct tool '%s' failed: %s", name, e)
            return f"Error: {str(e)[:200]}"

    # -- Normal core-routed tool --
    core_params = param_tf(args)

    # BUG-D FIX: Use per-action timeout for slow operations (winget, registry, etc.)
    action_timeout = _ACTION_TIMEOUTS.get(action, 10.0)
    result: Result = await send_command(layer, action, core_params, timeout=action_timeout)

    if result.success:
        base = result_tf(result.data) if result_tf else _result_to_str(result.data)
        # Append verifier status so the LLM knows if the action was confirmed
        if result.verified:
            base += " [verified]"
        elif result.verified is False and result.method_used:
            base += f" [executed via {result.method_used}, unverified]"
        return base

    # Daemon returned an error -- check if it's a connection issue (daemon down)
    # vs a legitimate action failure (e.g. file not found)
    daemon_unreachable = (
        not result.success
        and result.error
        and ("not running" in result.error.lower()
             or "unreachable" in result.error.lower()
             or "connection error" in result.error.lower()
             or "timeout" in result.error.lower()
             or "empty response" in result.error.lower())
    )

    if daemon_unreachable:
        logger.warning("Daemon unreachable for '%s', trying direct fallback", name)
        try:
            return await _handle_direct_tool(name, args)
        except Exception as e2:
            logger.error("Direct fallback also failed for '%s': %s", name, e2)
            return f"Error: daemon down and direct fallback failed for {name}"

    # Daemon processed the command but action failed -- return its error
    return f"Error: {result.error}"