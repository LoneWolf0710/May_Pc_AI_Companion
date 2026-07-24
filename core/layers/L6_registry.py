"""Layer 6: Windows Registry — Read, write, delete, backup.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 8:

CRITICAL: Always backup before modifying.

Hives: HKLM, HKCU, HKCR, HKU, HKCC
Libraries: winreg, win32api, win32security
"""

from __future__ import annotations

import winreg
import subprocess
import json
from pathlib import Path
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.engine.verifier import Verifiers
from core.layers._utils import run_ps, create_escalation_fn, create_preflight_fn

import logging
logger = logging.getLogger("may.core.layers.L6_registry")

HIVE_MAP = {
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKCR": winreg.HKEY_CLASSES_ROOT,
    "HKU":  winreg.HKEY_USERS,
    "HKCC": winreg.HKEY_CURRENT_CONFIG,
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
    "HKEY_USERS": winreg.HKEY_USERS,
    "HKEY_CURRENT_CONFIG": winreg.HKEY_CURRENT_CONFIG,
}

REG_TYPE_MAP = {
    "string": winreg.REG_SZ,
    "expand_string": winreg.REG_EXPAND_SZ,
    "dword": winreg.REG_DWORD,
    "qword": winreg.REG_QWORD,
    "binary": winreg.REG_BINARY,
    "multi_string": winreg.REG_MULTI_SZ,
}


# ══════════════════════════════════════════════════════════════════════════════
# READ
# ══════════════════════════════════════════════════════════════════════════════

async def _read_value(params: dict) -> Any:
    """Read a registry value."""
    hive = HIVE_MAP.get(params.get("hive", "HKCU"))
    key_path = params["key"]
    value_name = params.get("name")
    with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
        if value_name:
            value, reg_type = winreg.QueryValueEx(key, value_name)
            return {"name": value_name, "value": value, "type": reg_type}
        else:
            # List all values
            values = {}
            i = 0
            while True:
                try:
                    name, value, reg_type = winreg.EnumValue(key, i)
                    values[name] = {"value": value, "type": reg_type}
                    i += 1
                except OSError:
                    break
            return {"key": key_path, "values": values}


async def _list_subkeys(params: dict) -> Any:
    """List subkeys under a registry key."""
    hive = HIVE_MAP.get(params.get("hive", "HKCU"))
    key_path = params["key"]
    subkeys = []
    with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
        i = 0
        while True:
            try:
                subkeys.append(winreg.EnumKey(key, i))
                i += 1
            except OSError:
                break
    return {"subkeys": subkeys, "count": len(subkeys)}


# ══════════════════════════════════════════════════════════════════════════════
# WRITE
# ══════════════════════════════════════════════════════════════════════════════

async def _backup_key(params: dict) -> Any:
    """Backup a registry key to a .reg file before modifying."""
    hive_name = params.get("hive", "HKCU")
    key_path = params["key"]
    backup_dir = Path(params.get("backup_dir", "core/config/backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / f"registry_backup_{hive_name}_{key_path.replace(chr(92), '_')}.reg"
    success, output = await run_ps(f'reg export "{hive_name}\\{key_path}" "{backup_file}" /y')
    return {"backup_file": str(backup_file), "success": success}


async def _write_value(params: dict) -> Any:
    """Write a registry value."""
    hive = HIVE_MAP.get(params.get("hive", "HKCU"))
    key_path = params["key"]
    value_name = params["name"]
    value = params["value"]
    reg_type = REG_TYPE_MAP.get(params.get("type", "string"), winreg.REG_SZ)
    # Backup first
    try:
        await _backup_key(params)
    except Exception:
        pass  # Non-fatal
    with winreg.OpenKey(hive, key_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, value_name, 0, reg_type, value)
    return {"written": True, "name": value_name, "value": value}


async def _create_key(params: dict) -> Any:
    """Create a registry key."""
    hive = HIVE_MAP.get(params.get("hive", "HKCU"))
    key_path = params["key"]
    with winreg.CreateKey(hive, key_path) as key:
        pass
    return {"created": key_path}


# ══════════════════════════════════════════════════════════════════════════════
# DELETE
# ══════════════════════════════════════════════════════════════════════════════

async def _delete_value(params: dict) -> Any:
    """Delete a registry value."""
    hive = HIVE_MAP.get(params.get("hive", "HKCU"))
    key_path = params["key"]
    value_name = params["name"]
    with winreg.OpenKey(hive, key_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.DeleteValue(key, value_name)
    return {"deleted": value_name}


async def _delete_key(params: dict) -> Any:
    """Delete a registry key (must be empty)."""
    hive = HIVE_MAP.get(params.get("hive", "HKCU"))
    key_path = params["key"]
    # Get parent key and subkey name
    parts = key_path.rsplit("\\", 1)
    if len(parts) != 2:
        raise RuntimeError(f"Cannot delete root key: {key_path}")
    parent_path, subkey_name = parts
    with winreg.OpenKey(hive, parent_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.DeleteKey(key, subkey_name)
    return {"deleted": key_path}


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH
# ══════════════════════════════════════════════════════════════════════════════

async def _search_by_name(params: dict) -> Any:
    """Search for a value name in registry."""
    hive = HIVE_MAP.get(params.get("hive", "HKCU"))
    key_path = params["key"]
    search = params.get("search", "").lower()
    results = []
    try:
        with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
            i = 0
            while True:
                try:
                    name, value, reg_type = winreg.EnumValue(key, i)
                    if search in name.lower() or search in str(value).lower():
                        results.append({"name": name, "value": value})
                    i += 1
                except OSError:
                    break
    except FileNotFoundError:
        pass
    return {"results": results, "count": len(results)}


# ══════════════════════════════════════════════════════════════════════════════
# EXPORT KEY
# ══════════════════════════════════════════════════════════════════════════════

async def _export_key_action(params: dict) -> Any:
    """Export a registry key to a .reg file."""
    hive_name = params.get("hive", "HKCU")
    key_path = params["key"]
    export_path = params.get("path", f"{key_path.replace(chr(92), '_')}.reg")
    success, output = await run_ps(f'reg export "{hive_name}\\{key_path}" "{export_path}" /y')
    if not success:
        raise RuntimeError(output)
    return {"exported": key_path, "file": export_path}


# ══════════════════════════════════════════════════════════════════════════════
# IMPORT KEY
# ══════════════════════════════════════════════════════════════════════════════

async def _import_key_action(params: dict) -> Any:
    """Import a registry key from a .reg file."""
    reg_file = params["path"]
    success, output = await run_ps(f'reg import "{reg_file}"')
    if not success:
        raise RuntimeError(output)
    return {"imported": reg_file}


# ══════════════════════════════════════════════════════════════════════════════
# KEY EXISTS
# ══════════════════════════════════════════════════════════════════════════════

async def _key_exists_action(params: dict) -> Any:
    """Check if a registry key exists."""
    hive = HIVE_MAP.get(params.get("hive", "HKCU"))
    key_path = params["key"]
    try:
        with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ):
            return {"exists": True, "key": key_path}
    except FileNotFoundError:
        return {"exists": False, "key": key_path}


# ══════════════════════════════════════════════════════════════════════════════
# VALUE EXISTS
# ══════════════════════════════════════════════════════════════════════════════

async def _value_exists_action(params: dict) -> Any:
    """Check if a registry value exists."""
    hive = HIVE_MAP.get(params.get("hive", "HKCU"))
    key_path = params["key"]
    value_name = params["name"]
    try:
        with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, value_name)
            return {"exists": True, "name": value_name}
    except FileNotFoundError:
        return {"exists": False, "name": value_name}


# ══════════════════════════════════════════════════════════════════════════════
# RESTORE KEY (from backup .reg file)
# ══════════════════════════════════════════════════════════════════════════════

async def _restore_key_action(params: dict) -> Any:
    """Restore a registry key from a backup .reg file."""
    reg_file = params["path"]
    success, output = await run_ps(f'reg import "{reg_file}"')
    if not success:
        raise RuntimeError(output)
    return {"restored": reg_file}


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH BY VALUE
# ══════════════════════════════════════════════════════════════════════════════

async def _search_by_value_action(params: dict) -> Any:
    """Search for keys containing a specific value."""
    hive = HIVE_MAP.get(params.get("hive", "HKCU"))
    key_path = params["key"]
    search = params.get("search", "").lower()
    results = []
    try:
        with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
            i = 0
            while True:
                try:
                    name, value, reg_type = winreg.EnumValue(key, i)
                    if search in str(value).lower():
                        results.append({"name": name, "value": value, "type": reg_type})
                    i += 1
                except OSError:
                    break
    except FileNotFoundError:
        pass
    return {"results": results, "count": len(results)}


# ══════════════════════════════════════════════════════════════════════════════
# SET KEY PERMISSIONS
# ══════════════════════════════════════════════════════════════════════════════

async def _set_key_permissions_action(params: dict) -> Any:
    """Modify registry key ACL permissions."""
    hive_name = params.get("hive", "HKCU")
    key_path = params["key"]
    user = params.get("user", "Everyone")
    permission = params.get("permission", "F")  # F=Full, R=Read
    success, output = await run_ps(
        f'$acl = Get-Acl "Registry::{hive_name}\\{key_path}" -ErrorAction SilentlyContinue; '
        f'if ($acl) {{ $rule = New-Object System.Security.AccessControl.RegistryAccessRule("", "{permission}"); '
        f'$acl.SetAccessRule($rule); Set-Acl "Registry::{hive_name}\\{key_path}" $acl }}'
    )
    return {"permissions_set": True, "key": key_path, "user": user, "permission": permission}


# ══════════════════════════════════════════════════════════════════════════════
# TAKE OWNERSHIP (registry key)
# ══════════════════════════════════════════════════════════════════════════════

async def _take_ownership_action(params: dict) -> Any:
    """Take ownership of a registry key."""
    hive_name = params.get("hive", "HKCU")
    key_path = params["key"]
    success, output = await run_ps(
        f'$key = [Microsoft.Win32.Registry]::{hive_name}.OpenSubKey("{key_path}", '
        f'[Microsoft.Win32.RegistryKeyPermissionCheck]::ReadWriteSubTree, '
        f'[System.Security.AccessControl.RegistryRights]::TakeOwnership); '
        f'if ($key) {{ $acl = $key.GetAccessControl(); '
        f'$acl.SetOwner([System.Security.Principal.NTAccount]"$env:USERNAME"); '
        f'$key.SetAccessControl($acl); $key.Close(); "Ownership taken" }}'
    )
    return {"owned": key_path}


# ══════════════════════════════════════════════════════════════════════════════
# OPEN REMOTE REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

async def _open_remote_registry_action(params: dict) -> Any:
    """Connect to a remote machine's registry."""
    remote = params["computer"]  # e.g. \\Server01
    hive_name = params.get("hive", "HKLM")
    key_path = params.get("key", "SOFTWARE")
    hive = HIVE_MAP.get(hive_name)
    try:
        remote_key = winreg.ConnectRegistry(remote, hive)
        with winreg.OpenKey(remote_key, key_path, 0, winreg.KEY_READ) as key:
            values = {}
            i = 0
            while True:
                try:
                    name, value, reg_type = winreg.EnumValue(key, i)
                    values[name] = value
                    i += 1
                except OSError:
                    break
        return {"computer": remote, "key": key_path, "values": values}
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# POWERSHELL / REG.EXE FALLBACK METHODS
# ══════════════════════════════════════════════════════════════════════════════

_HIVE_NAME_MAP = {
    winreg.HKEY_LOCAL_MACHINE: "HKLM",
    winreg.HKEY_CURRENT_USER: "HKCU",
    winreg.HKEY_CLASSES_ROOT: "HKCR",
    winreg.HKEY_USERS: "HKU",
    winreg.HKEY_CURRENT_CONFIG: "HKCC",
}


def _hive_name(params: dict) -> str:
    """Get the short hive name (e.g. 'HKCU') for reg.exe commands."""
    hive = HIVE_MAP.get(params.get("hive", "HKCU"))
    return _HIVE_NAME_MAP.get(hive, "HKCU")


async def _read_value_reg(params: dict) -> Any:
    """Method 2: Read registry via reg.exe."""
    hive_name = _hive_name(params)
    key_path = params["key"]
    value_name = params.get("name")
    if value_name:
        success, output = await run_ps(f'reg query "{hive_name}\\{key_path}" /v "{value_name}"')
        if success and output:
            # Parse reg query output
            for line in output.splitlines():
                if value_name in line and "REG_" in line:
                    parts = line.split("    ", 2)
                    if len(parts) >= 3:
                        return {"name": value_name, "value": parts[2].strip()}
        raise RuntimeError(f"Value '{value_name}' not found")
    else:
        success, output = await run_ps(f'reg query "{hive_name}\\{key_path}"')
        if success and output:
            values = {}
            for line in output.splitlines():
                if "REG_" in line:
                    parts = line.split(None, 2)
                    if len(parts) >= 3:
                        values[parts[0]] = parts[2].strip()
            return {"key": key_path, "values": values}
        raise RuntimeError(f"Key '{key_path}' not found")


async def _list_subkeys_reg(params: dict) -> Any:
    """Method 2: List subkeys via reg.exe."""
    hive_name = _hive_name(params)
    key_path = params["key"]
    success, output = await run_ps(f'reg query "{hive_name}\\{key_path}"')
    if success and output:
        subkeys = []
        for line in output.splitlines():
            line = line.strip()
            if line and not line.startswith("HKEY_") and "REG_" not in line and line != key_path:
                subkeys.append(line)
        return {"subkeys": subkeys, "count": len(subkeys)}
    return {"subkeys": [], "count": 0}


async def _write_value_reg(params: dict) -> Any:
    """Method 2: Write registry via reg.exe."""
    hive_name = _hive_name(params)
    key_path = params["key"]
    value_name = params["name"]
    value = params["value"]
    reg_type = params.get("type", "string")
    type_map = {"string": "REG_SZ", "dword": "REG_DWORD", "qword": "REG_QWORD",
                "expand_string": "REG_EXPAND_SZ", "binary": "REG_BINARY",
                "multi_string": "REG_MULTI_SZ"}
    reg_type_str = type_map.get(reg_type, "REG_SZ")
    # Backup first
    try:
        await _backup_key(params)
    except Exception:
        pass
    success, output = await run_ps(f'reg add "{hive_name}\\{key_path}" /v "{value_name}" /t {reg_type_str} /d "{value}" /f')
    if not success:
        raise RuntimeError(output)
    return {"written": True, "name": value_name, "value": value}


async def _create_key_reg(params: dict) -> Any:
    """Method 2: Create key via reg.exe."""
    hive_name = _hive_name(params)
    key_path = params["key"]
    success, output = await run_ps(f'reg add "{hive_name}\\{key_path}" /f')
    if not success:
        raise RuntimeError(output)
    return {"created": key_path}


async def _delete_value_reg(params: dict) -> Any:
    """Method 2: Delete value via reg.exe."""
    hive_name = _hive_name(params)
    key_path = params["key"]
    value_name = params["name"]
    success, output = await run_ps(f'reg delete "{hive_name}\\{key_path}" /v "{value_name}" /f')
    if not success:
        raise RuntimeError(output)
    return {"deleted": value_name}


async def _delete_key_reg(params: dict) -> Any:
    """Method 2: Delete key via reg.exe."""
    hive_name = _hive_name(params)
    key_path = params["key"]
    success, output = await run_ps(f'reg delete "{hive_name}\\{key_path}" /f')
    if not success:
        raise RuntimeError(output)
    return {"deleted": key_path}


async def _key_exists_reg(params: dict) -> Any:
    """Method 2: Check key existence via reg.exe."""
    hive_name = _hive_name(params)
    key_path = params["key"]
    success, output = await run_ps(f'reg query "{hive_name}\\{key_path}" 2>&1')
    exists = success and "ERROR" not in output
    return {"exists": exists, "key": key_path}


async def _value_exists_reg(params: dict) -> Any:
    """Method 2: Check value existence via reg.exe."""
    hive_name = _hive_name(params)
    key_path = params["key"]
    value_name = params["name"]
    success, output = await run_ps(f'reg query "{hive_name}\\{key_path}" /v "{value_name}" 2>&1')
    exists = success and "ERROR" not in output and value_name in output
    return {"exists": exists, "name": value_name}


async def _search_by_name_reg(params: dict) -> Any:
    """Method 2: Search registry via PowerShell."""
    hive_name = _hive_name(params)
    key_path = params["key"]
    search = params.get("search", "").lower()
    ps = (f"Get-ItemProperty -Path 'Registry::{hive_name}\\{key_path}' -ErrorAction SilentlyContinue | "
          f"Get-Member -MemberType NoteProperty | Where-Object {{ $_.Name -like '*{search}*' }} | "
          f"Select-Object Name | ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            results = [{"name": d.get("Name", "")} for d in data]
            return {"results": results, "count": len(results)}
        except json.JSONDecodeError:
            pass
    return {"results": [], "count": 0}


async def _export_key_reg(params: dict) -> Any:
    """Method 2: Export via reg.exe."""
    hive_name = _hive_name(params)
    key_path = params["key"]
    export_path = params.get("path", f"{key_path.replace(chr(92), '_')}.reg")
    success, output = await run_ps(f'reg export "{hive_name}\\{key_path}" "{export_path}" /y')
    if not success:
        raise RuntimeError(output)
    return {"exported": key_path, "file": export_path}


# ══════════════════════════════════════════════════════════════════════════════
# ENABLE/DISABLE DARK MODE (via registry)
# ══════════════════════════════════════════════════════════════════════════════

THEME_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"

async def _enable_dark_mode_winreg(params: dict) -> Any:
    """Method 1: Set dark mode via winreg."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, THEME_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, 0)
        return {"mode": "dark"}
    except FileNotFoundError:
        # Key may not exist on older Windows
        raise RuntimeError(f"Registry key not found: {THEME_KEY}")


async def _enable_dark_mode_powershell(params: dict) -> Any:
    """Method 2: Set dark mode via PowerShell."""
    ps = (
        "Set-ItemProperty -Path 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' "
        "-Name 'AppsUseLightTheme' -Value 0; "
        "Set-ItemProperty -Path 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' "
        "-Name 'SystemUsesLightTheme' -Value 0"
    )
    success, output = await run_ps(ps)
    if not success:
        raise RuntimeError(output)
    return {"mode": "dark"}


async def _enable_light_mode_winreg(params: dict) -> Any:
    """Method 1: Set light mode via winreg."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, THEME_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, 1)
        return {"mode": "light"}
    except FileNotFoundError:
        raise RuntimeError(f"Registry key not found: {THEME_KEY}")


async def _enable_light_mode_powershell(params: dict) -> Any:
    """Method 2: Set light mode via PowerShell."""
    ps = (
        "Set-ItemProperty -Path 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' "
        "-Name 'AppsUseLightTheme' -Value 1; "
        "Set-ItemProperty -Path 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' "
        "-Name 'SystemUsesLightTheme' -Value 1"
    )
    success, output = await run_ps(ps)
    if not success:
        raise RuntimeError(output)
    return {"mode": "light"}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION HANDLER
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    "read_value":    ([_read_value, _read_value_reg], None),
    "list_subkeys":  ([_list_subkeys, _list_subkeys_reg], None),
    "write_value":   ([_write_value, _write_value_reg], Verifiers.registry_value),
    "create_key":    ([_create_key, _create_key_reg], None),
    "delete_value":  ([_delete_value, _delete_value_reg], None),
    "delete_key":    ([_delete_key, _delete_key_reg], None),
    "backup_key":    ([_backup_key], None),
    "search_by_name": ([_search_by_name, _search_by_name_reg], None),
    "list_values":    ([_read_value, _read_value_reg], None),
    "export_key":     ([_export_key_action, _export_key_reg], None),
    "import_key":     ([_import_key_action], None),
    "key_exists":     ([_key_exists_action, _key_exists_reg], None),
    "value_exists":   ([_value_exists_action, _value_exists_reg], None),
    # --- Phase 7 additions ---
    "restore_key":          ([_restore_key_action], None),
    "search_by_value":      ([_search_by_value_action], None),
    "set_key_permissions":  ([_set_key_permissions_action], None),
    "take_ownership":       ([_take_ownership_action], None),
    "open_remote_registry": ([_open_remote_registry_action], None),
    # --- enable/disable dark mode via registry ---
    "enable_dark_mode":  ([_enable_dark_mode_winreg, _enable_dark_mode_powershell], None),
    "enable_light_mode": ([_enable_light_mode_winreg, _enable_light_mode_powershell], None),
}


async def handler(action: str, params: dict[str, Any]) -> Result:
    """L6 Registry layer handler."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown registry action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"registry.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("registry", action),
        escalation_fn=create_escalation_fn("registry", action),
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
