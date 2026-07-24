"""Layer 1: File System — Files, folders, drives, permissions, recycle bin.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 3:

Controls: Files, folders, drives, NTFS permissions, file attributes,
search, monitoring, compression, recycle bin, symbolic links.

Libraries: pathlib, os, shutil, win32file, win32api, win32security

Fallback chains try 3-7 methods per action for ~99% success rate.
"""

from __future__ import annotations

import os
import shutil
import hashlib
import subprocess
from pathlib import Path
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.engine.verifier import Verifiers
from core.layers._utils import run_ps, run_cmd, run_cmd_sync, create_escalation_fn, create_preflight_fn
from core.layers.everything_search import is_everything_available, everything_search_paths

import logging
logger = logging.getLogger("may.core.layers.L1_filesystem")


# ══════════════════════════════════════════════════════════════════════════════
# DELETE FILE — 7-method fallback chain
# ══════════════════════════════════════════════════════════════════════════════

async def _delete_pathlib(params: dict) -> Any:
    """Method 1: os.remove via pathlib."""
    path = Path(params["path"])
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(str(path))
    return {"deleted": str(path)}


async def _delete_win32file(params: dict) -> Any:
    """Method 2: win32file.DeleteFileW."""
    import win32file
    win32file.DeleteFileW(params["path"])
    return {"deleted": params["path"]}


async def _delete_cmd_del(params: dict) -> Any:
    """Method 3: cmd /c del /F /Q."""
    path = params["path"]
    success, output = await run_cmd(["cmd", "/c", "del", "/F", "/Q", path])
    if not success:
        raise RuntimeError(output)
    return {"deleted": path}


async def _delete_clear_attrs(params: dict) -> Any:
    """Method 4: Clear read-only/system attrs, then delete."""
    path = params["path"]
    # Clear attributes first
    success, _ = await run_cmd(["attrib", "-R", "-S", "-H", path])
    os.chmod(path, 0o777) if os.path.exists(path) else None
    Path(path).unlink(missing_ok=True)
    return {"deleted": path}


async def _delete_take_ownership(params: dict) -> Any:
    """Method 5: Take ownership, set full permissions, then delete."""
    path = params["path"]
    # Take ownership via PowerShell
    await run_ps(f'Takeown /F "{path}" /A /R /D Y')
    await run_ps(f'icacls "{path}" /grant administrators:F /T')
    # Now try delete
    Path(path).unlink(missing_ok=True)
    return {"deleted": path}


async def _delete_kill_locking(params: dict) -> Any:
    """Method 6: Kill locking process, then delete."""
    import psutil
    path = params["path"]
    filename = Path(path).name.lower()
    # Find and kill processes that have this file open
    killed = 0
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            files = proc.open_files()
            for f in files:
                if filename in f.path.lower():
                    proc.kill()
                    killed += 1
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    # Now try delete
    Path(path).unlink(missing_ok=True)
    return {"deleted": path, "killed_locking": killed}


async def _delete_delay_reboot(params: dict) -> Any:
    """Method 7: Schedule delete on next reboot via MoveFileExW (guaranteed success)."""
    import ctypes
    import ctypes.wintypes
    path = params["path"]
    # MoveFileExW with MOVEFILE_DELAY_UNTIL_REBOOT = 0x00000004
    # This schedules the file to be moved/deleted when Windows restarts
    result = ctypes.windll.kernel32.MoveFileExW(
        path, None, 0x00000004  # MOVEFILE_DELAY_UNTIL_REBOOT
    )
    if not result:
        error = ctypes.get_last_error()
        raise RuntimeError(f"MoveFileExW failed with error {error}")
    return {"deleted": path, "method": "scheduled_reboot", "note": "File will be deleted on next Windows restart"}


# ══════════════════════════════════════════════════════════════════════════════
# CREATE FILE — 3-method fallback chain
# ══════════════════════════════════════════════════════════════════════════════

async def _create_pathlib(params: dict) -> Any:
    """Method 1: pathlib write."""
    path = Path(params["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    content = params.get("content", "")
    path.write_text(content, encoding="utf-8")
    return {"path": str(path), "size": len(content)}


async def _create_builtin(params: dict) -> Any:
    """Method 2: open() builtin."""
    path = Path(params["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    content = params.get("content", "")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"path": str(path), "size": len(content)}


async def _create_powershell(params: dict) -> Any:
    """Method 3: PowerShell Set-Content."""
    path = params["path"]
    content = params.get("content", "")
    # Use base64 for safe content transfer
    import base64
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    parent = str(Path(path).parent)
    await run_ps(f'if (!(Test-Path "{parent}")) {{ New-Item -ItemType Directory -Path "{parent}" -Force }}')
    success, output = await run_ps(
        f'[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("{encoded}")) | '
        f'Set-Content -Path "{path}" -Encoding UTF8 -Force'
    )
    if not success:
        raise RuntimeError(output)
    return {"path": path, "size": len(content)}


# ══════════════════════════════════════════════════════════════════════════════
# READ FILE
# ══════════════════════════════════════════════════════════════════════════════

async def _read_pathlib(params: dict) -> Any:
    """Method 1: pathlib read."""
    path = Path(params["path"])
    content = path.read_text(encoding="utf-8")
    max_chars = params.get("max_chars", 50000)
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n... (truncated, {len(content)} total chars)"
    return {"content": content, "size": len(content)}


async def _read_powershell(params: dict) -> Any:
    """Method 2: PowerShell Get-Content."""
    path = params["path"]
    success, output = await run_ps(f'Get-Content -Path "{path}" -Raw')
    if not success:
        raise RuntimeError(output)
    return {"content": output, "size": len(output)}


# ══════════════════════════════════════════════════════════════════════════════
# COPY FILE — 3-method fallback
# ══════════════════════════════════════════════════════════════════════════════

async def _copy_shutil(params: dict) -> Any:
    """Method 1: shutil.copy2."""
    src, dst = params["source"], params["destination"]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {"source": src, "destination": dst}


async def _copy_win32file(params: dict) -> Any:
    """Method 2: win32file.CopyFileW."""
    import win32file
    src, dst = params["source"], params["destination"]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    win32file.CopyFileW(src, dst, False)
    return {"source": src, "destination": dst}


async def _copy_cmd(params: dict) -> Any:
    """Method 3: cmd /c copy."""
    src, dst = params["source"], params["destination"]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    success, output = await run_cmd(["cmd", "/c", "copy", "/Y", src, dst])
    if not success:
        raise RuntimeError(output)
    return {"source": src, "destination": dst}


# ══════════════════════════════════════════════════════════════════════════════
# MOVE FILE — 3-method fallback
# ══════════════════════════════════════════════════════════════════════════════

async def _move_pathlib(params: dict) -> Any:
    """Method 1: pathlib rename."""
    src, dst = params["source"], params["destination"]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(src).rename(dst)
    return {"source": src, "destination": dst}


async def _move_shutil(params: dict) -> Any:
    """Method 2: shutil.move."""
    src, dst = params["source"], params["destination"]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    shutil.move(src, dst)
    return {"source": src, "destination": dst}


async def _move_win32file(params: dict) -> Any:
    """Method 3: win32file.MoveFileW."""
    import win32file
    src, dst = params["source"], params["destination"]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    win32file.MoveFileW(src, dst)
    return {"source": src, "destination": dst}


# ══════════════════════════════════════════════════════════════════════════════
# LIST DIRECTORY
# ══════════════════════════════════════════════════════════════════════════════

async def _list_pathlib(params: dict) -> Any:
    """List directory contents via pathlib."""
    path = Path(params.get("path", "."))
    if not path.exists():
        return {"error": f"Directory not found: {path}"}
    items = []
    for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        info = {"name": item.name, "is_dir": item.is_dir()}
        if item.is_file():
            size = item.stat().st_size
            info["size"] = size
            info["size_human"] = _human_size(size)
        items.append(info)
        if len(items) >= params.get("max_items", 100):
            break
    return {"path": str(path), "count": len(items), "items": items}


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH FILES
# ══════════════════════════════════════════════════════════════════════════════

async def _search_files_everything(params: dict) -> Any:
    """Strategy 1: Search via Everything by voidtools (es.exe).

    Everything indexes the NTFS MFT and returns results in < 1ms.
    Falls through to pathlib glob if Everything is not installed.
    """
    if not is_everything_available():
        raise RuntimeError("Everything not installed")
    directory = params.get("path")
    pattern = params.get("pattern", "*")
    max_results = params.get("max_results", 50)
    matches = await everything_search_paths(
        query=pattern,
        path=directory,
        max_results=max_results,
        timeout=5.0,
    )
    return {"matches": matches, "count": len(matches), "method": "everything"}


async def _search_files(params: dict) -> Any:
    """Strategy 2: Search via pathlib recursive glob.

    Adds max_depth (default 5) to prevent rglob from traversing extremely
    deep directory trees which can be very slow on large drives.
    """
    directory = params.get("path", ".")
    pattern = params.get("pattern", "*")
    max_depth = params.get("max_depth", 5)
    path = Path(directory)
    if not path.exists():
        return {"error": f"Directory not found: {directory}"}
    matches = []
    def _depth_limited_rglob(p: Path, pat: str, depth: int):
        if depth > max_depth:
            return
        try:
            for item in p.iterdir():
                if item.is_file() and item.match(pat):
                    matches.append(str(item))
                    if len(matches) >= params.get("max_results", 50):
                        return
                elif item.is_dir() and len(matches) < params.get("max_results", 50):
                    _depth_limited_rglob(item, pat, depth + 1)
        except (PermissionError, OSError):
            pass
    _depth_limited_rglob(path, pattern, 0)
    return {"matches": matches, "count": len(matches)}


# ══════════════════════════════════════════════════════════════════════════════
# FILE INFO
# ══════════════════════════════════════════════════════════════════════════════

async def _get_file_info(params: dict) -> Any:
    """Get detailed file information."""
    from datetime import datetime
    path = Path(params["path"])
    if not path.exists():
        return {"error": f"File not found: {path}"}
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "name": path.name,
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
        "size": stat.st_size,
        "size_human": _human_size(stat.st_size),
        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "extension": path.suffix,
    }


# ══════════════════════════════════════════════════════════════════════════════
# FILE HASH
# ══════════════════════════════════════════════════════════════════════════════

async def _get_file_hash(params: dict) -> Any:
    """Get file hash (MD5, SHA1, SHA256)."""
    path = Path(params["path"])
    algo = params.get("algorithm", "sha256").lower()
    hash_func = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_func.update(chunk)
    return {"hash": hash_func.hexdigest(), "algorithm": algo}


# ══════════════════════════════════════════════════════════════════════════════
# APPEND TO FILE
# ══════════════════════════════════════════════════════════════════════════════

async def _append_file(params: dict) -> Any:
    """Append content to a file."""
    path = Path(params["path"])
    content = params.get("content", "")
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)
    return {"appended": len(content), "path": str(path)}


# ══════════════════════════════════════════════════════════════════════════════
# DRIVE INFO
# ══════════════════════════════════════════════════════════════════════════════

async def _get_drives(params: dict) -> Any:
    """List all drives with usage info."""
    import psutil
    drives = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            drives.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": round(usage.total / (1024**3), 1),
                "used_gb": round(usage.used / (1024**3), 1),
                "free_gb": round(usage.free / (1024**3), 1),
                "percent": usage.percent,
            })
        except PermissionError:
            continue
    return {"drives": drives}


# ══════════════════════════════════════════════════════════════════════════════
# RECYCLE BIN
# ══════════════════════════════════════════════════════════════════════════════

async def _send_to_recycle_bin(params: dict) -> Any:
    """Send file to recycle bin using send2trash."""
    try:
        from send2trash import send2trash
        send2trash(params["path"])
        return {"sent_to_recycle": params["path"]}
    except ImportError:
        # Fallback: use PowerShell
        success, output = await run_ps(
            f'(New-Object -ComObject Shell.Application).NameSpace(10).MoveHere("{params["path"]}")'
        )
        if not success:
            raise RuntimeError("send2trash not installed and PowerShell fallback failed")
        return {"sent_to_recycle": params["path"]}


async def _empty_recycle_bin(params: dict) -> Any:
    """Empty the recycle bin."""
    success, output = await run_ps("Clear-RecycleBin -Force -ErrorAction SilentlyContinue; 'Recycle bin emptied'")
    return {"emptied": True}


# ══════════════════════════════════════════════════════════════════════════════
# SYMLINK / HARDLINK
# ══════════════════════════════════════════════════════════════════════════════

async def _create_symlink(params: dict) -> Any:
    """Create a symbolic link."""
    target = params["target"]
    link = params["link"]
    Path(link).parent.mkdir(parents=True, exist_ok=True)
    success, output = await run_cmd(["cmd", "/c", "mklink", "/D", link, target])
    if not success:
        # Try PowerShell
        success, output = await run_ps(f'New-Item -ItemType SymbolicLink -Path "{link}" -Target "{target}"')
    return {"link": link, "target": target}


# ══════════════════════════════════════════════════════════════════════════════
# FOLDER SIZE
# ══════════════════════════════════════════════════════════════════════════════

async def _get_folder_size(params: dict) -> Any:
    """Get total size of a folder.

    Uses a depth-limited walk (max 10 levels) and file count cap (100k)
    to prevent hanging on extremely large directories.
    """
    path = Path(params["path"])
    if not path.exists():
        return {"error": f"Directory not found: {path}"}
    total = 0
    file_count = 0
    max_files = params.get("max_files", 100_000)
    max_depth = params.get("max_depth", 10)
    def _walk(p: Path, depth: int):
        nonlocal total, file_count
        if depth > max_depth or file_count >= max_files:
            return
        try:
            for item in p.iterdir():
                if file_count >= max_files:
                    return
                try:
                    if item.is_file():
                        total += item.stat().st_size
                        file_count += 1
                    elif item.is_dir():
                        _walk(item, depth + 1)
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
    _walk(path, 0)
    truncated = file_count >= max_files
    result = {"path": str(path), "size": total, "size_human": _human_size(total), "file_count": file_count}
    if truncated:
        result["truncated"] = True
        result["note"] = f"Reached {max_files} file limit — size may be incomplete"
    return result


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


# ══════════════════════════════════════════════════════════════════════════════
# TAKE OWNERSHIP
# ══════════════════════════════════════════════════════════════════════════════

async def _take_ownership_action(params: dict) -> Any:
    """Take ownership of a file or folder."""
    path = params["path"]
    await run_ps(f'Takeown /F "{path}" /A /R /D Y')
    await run_ps(f'icacls "{path}" /grant administrators:F /T')
    return {"owned": path}


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE PERMISSIONS
# ══════════════════════════════════════════════════════════════════════════════

async def _change_permissions_action(params: dict) -> Any:
    """Change file/folder permissions via icacls."""
    path = params["path"]
    permission = params.get("permission", "F")  # F=Full, R=Read, M=Modify
    user = params.get("user", "administrators")
    success, output = await run_ps(f'icacls "{path}" /grant {user}:{permission} /T')
    if not success:
        raise RuntimeError(output)
    return {"path": path, "permission": permission, "user": user}


# ══════════════════════════════════════════════════════════════════════════════
# MONITOR PATH
# ══════════════════════════════════════════════════════════════════════════════

_watchers = {}  # path -> watchdog observer

async def _monitor_path_action(params: dict) -> Any:
    """Start or stop monitoring a directory for changes."""
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    import threading
    
    path = params.get("path", ".")
    action = params.get("action", "start")  # start, stop
    
    if action == "stop":
        observer = _watchers.pop(path, None)
        if observer:
            observer.stop()
            observer.join(timeout=2)
            return {"stopped": path}
        return {"error": "No watcher for this path"}
    
    class ChangeHandler(FileSystemEventHandler):
        def __init__(self):
            self.events = []
        def on_any_event(self, event):
            self.events.append({"type": event.event_type, "src": event.src_path})
    
    handler = ChangeHandler()
    observer = Observer()
    observer.schedule(handler, path, recursive=True)
    observer.start()
    _watchers[path] = observer
    return {"monitoring": path}


# ══════════════════════════════════════════════════════════════════════════════
# FIND LARGE FILES
# ══════════════════════════════════════════════════════════════════════════════

async def _find_large_files_action(params: dict) -> Any:
    """Find files larger than a threshold."""
    directory = params.get("path", ".")
    min_size_mb = params.get("min_size_mb", 100)
    min_bytes = min_size_mb * 1024 * 1024
    path = Path(directory)
    if not path.exists():
        return {"error": f"Directory not found: {directory}"}
    large = []
    for f in path.rglob("*"):
        if f.is_file():
            try:
                size = f.stat().st_size
                if size >= min_bytes:
                    large.append({"path": str(f), "size_mb": round(size / (1024*1024), 1)})
            except (PermissionError, OSError):
                continue
    large.sort(key=lambda x: x["size_mb"], reverse=True)
    return {"files": large[:50], "count": len(large)}


# ══════════════════════════════════════════════════════════════════════════════
# FIND DUPLICATES
# ══════════════════════════════════════════════════════════════════════════════

async def _find_duplicates_action(params: dict) -> Any:
    """Find duplicate files by hash."""
    directory = params.get("path", ".")
    path = Path(directory)
    if not path.exists():
        return {"error": f"Directory not found: {directory}"}
    hashes = {}  # hash -> [paths]
    for f in path.rglob("*"):
        if f.is_file():
            try:
                h = hashlib.md5()
                with open(f, "rb") as fh:
                    for chunk in iter(lambda: fh.read(8192), b""):
                        h.update(chunk)
                digest = h.hexdigest()
                hashes.setdefault(digest, []).append(str(f))
            except (PermissionError, OSError):
                continue
    dupes = {h: paths for h, paths in hashes.items() if len(paths) > 1}
    return {"duplicate_groups": len(dupes), "groups": list(dupes.values())[:20]}


# ══════════════════════════════════════════════════════════════════════════════
# COMPRESS / DECOMPRESS
# ══════════════════════════════════════════════════════════════════════════════

async def _compress_file_action(params: dict) -> Any:
    """Compress files/folders using py7zr."""
    import py7zr
    source = params["path"]
    archive = params.get("archive", source + ".7z")
    with py7zr.SevenZipFile(archive, "w") as sz:
        sz.writeall(source, Path(source).name)
    return {"compressed": source, "archive": archive}


async def _decompress_file_action(params: dict) -> Any:
    """Decompress a 7z archive."""
    import py7zr
    archive = params["path"]
    dest = params.get("dest", ".")
    with py7zr.SevenZipFile(archive, "r") as sz:
        sz.extractall(dest)
    return {"extracted": archive, "dest": dest}


# ══════════════════════════════════════════════════════════════════════════════
# CREATE HARDLINK
# ══════════════════════════════════════════════════════════════════════════════

async def _create_hardlink_action(params: dict) -> Any:
    """Create a hard link."""
    target = params["target"]
    link = params["link"]
    Path(link).parent.mkdir(parents=True, exist_ok=True)
    os.link(target, link)
    return {"link": link, "target": target}


# ══════════════════════════════════════════════════════════════════════════════
# CREATE FOLDER
# ══════════════════════════════════════════════════════════════════════════════

async def _create_folder_action(params: dict) -> Any:
    """Create a directory (and parents) using pathlib or PowerShell."""
    path = Path(params["path"])
    path.mkdir(parents=True, exist_ok=True)
    return {"created": str(path)}


async def _create_folder_powershell(params: dict) -> Any:
    """Method 2: PowerShell New-Item."""
    path = params["path"]
    success, output = await run_ps(f'New-Item -ItemType Directory -Path "{path}" -Force | Select-Object -ExpandProperty FullName')
    if not success:
        raise RuntimeError(output)
    return {"created": path}


# ══════════════════════════════════════════════════════════════════════════════
# SET FILE ATTRIBUTES
# ══════════════════════════════════════════════════════════════════════════════

async def _set_file_attributes_action(params: dict) -> Any:
    """Set file attributes (hidden, readonly, system, archive)."""
    path = params["path"]
    attrs = params.get("attributes", [])  # e.g. ["hidden", "readonly"]
    attr_map = {
        "hidden": 0x02,
        "readonly": 0x01,
        "system": 0x04,
        "archive": 0x20,
        "normal": 0x80,
    }
    flags = 0
    for attr in attrs:
        flags |= attr_map.get(attr.lower(), 0)
    if flags:
        import win32file
        # First clear existing attributes, then set new ones
        win32file.SetFileAttributesW(path, flags)
    else:
        # Use attrib command as fallback
        success, output = await run_cmd(["attrib", "+H" if "hidden" in attrs else "-H",
                                          "+R" if "readonly" in attrs else "-R",
                                          "+S" if "system" in attrs else "-S", path])
    return {"path": path, "attributes": attrs}


# ══════════════════════════════════════════════════════════════════════════════
# GET DRIVE INFO (single drive)
# ══════════════════════════════════════════════════════════════════════════════

async def _get_drive_info_action(params: dict) -> Any:
    """Get detailed info about a specific drive."""
    import psutil
    drive = params.get("drive", "C:\\")
    if not drive.endswith("\\"):
        drive += "\\"
    try:
        usage = psutil.disk_usage(drive)
        import win32api
        try:
            vol_name, vol_serial, max_comp, flags, fs = win32api.GetVolumeInformation(drive)
        except Exception:
            vol_name, fs = "", ""
        return {
            "drive": drive,
            "label": vol_name,
            "filesystem": fs,
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "percent": usage.percent,
        }
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# RESTORE FROM RECYCLE BIN
# ══════════════════════════════════════════════════════════════════════════════

async def _restore_from_recycle_bin_action(params: dict) -> Any:
    """Restore a file from the recycle bin using winshell."""
    try:
        import winshell
        winshell.undelete(params["filename"])
        return {"restored": params["filename"]}
    except ImportError:
        # Fallback: use PowerShell COM
        filename = params["filename"]
        ps_cmd = '$shell = New-Object -ComObject Shell.Application; '
        ps_cmd += '$recycle = $shell.NameSpace(10); '
        ps_cmd += '$recycle.Items() | Where-Object {$_.Name -like "*' + filename + '*"} | '
        ps_cmd += 'ForEach-Object { $_.InvokeVerb("undelete") }'
        success, output = await run_ps(ps_cmd)
        return {"restored": filename, "method": "powershell"}


# ══════════════════════════════════════════════════════════════════════════════
# GET LOCKED BY (which process has file open)
# ══════════════════════════════════════════════════════════════════════════════

async def _get_locked_by_action(params: dict) -> Any:
    """Find which process has a file locked."""
    path = params["path"]
    # Method 1: PowerShell + handle.exe approach
    success, output = await run_ps(
        f'Get-Process | Where-Object {{ $_.Modules -like "*{Path.basename(path)}*" }} | '
        f'Select-Object Id, ProcessName, Path | ConvertTo-Json'
    )
    if success and output.strip():
        import json
        try:
            procs = json.loads(output)
            if not isinstance(procs, list):
                procs = [procs]
            return {"file": path, "locked_by": procs}
        except json.JSONDecodeError:
            pass
    # Method 2: Try handle.exe if available
    success, output = await run_cmd(["handle.exe", Path(path).name])
    if success and output:
        return {"file": path, "handle_output": output[:2000]}
    return {"file": path, "locked_by": [], "note": "File may not be locked or handle.exe not in PATH"}


# ══════════════════════════════════════════════════════════════════════════════
# COPY FOLDER TREE
# ══════════════════════════════════════════════════════════════════════════════

async def _copy_folder_tree_action(params: dict) -> Any:
    """Copy an entire directory tree."""
    src = params["source"]
    dst = params["destination"]
    shutil.copytree(src, dst, dirs_exist_ok=True)
    return {"source": src, "destination": dst}


# ══════════════════════════════════════════════════════════════════════════════
# DELETE FOLDER TREE
# ══════════════════════════════════════════════════════════════════════════════

async def _delete_folder_tree_action(params: dict) -> Any:
    """Delete an entire directory tree."""
    path = Path(params["path"])
    if path.exists():
        shutil.rmtree(str(path))
    return {"deleted": str(path)}


# ══════════════════════════════════════════════════════════════════════════════
# POWERSHELL / CMD FALLBACK METHODS
# ══════════════════════════════════════════════════════════════════════════════

async def _list_directory_powershell(params: dict) -> Any:
    """Method 2: List directory via PowerShell."""
    path = params.get("path", ".")
    max_items = params.get("max_items", 100)
    ps = (f"Get-ChildItem '{path}' -ErrorAction SilentlyContinue | "
          f"Sort-Object {{ $_.PSIsContainer }}, Name | "
          f"Select-Object -First {max_items} Name, Length, PSIsContainer | "
          f"ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            items = [{"name": d.get("Name"), "is_dir": d.get("PSIsContainer", False),
                      "size": d.get("Length", 0)} for d in data]
            return {"path": path, "count": len(items), "items": items}
        except json.JSONDecodeError:
            pass
    return {"path": path, "count": 0, "items": []}


async def _search_files_powershell(params: dict) -> Any:
    """Method 2: Search files via PowerShell."""
    directory = params.get("path", ".")
    pattern = params.get("pattern", "*")
    max_results = params.get("max_results", 50)
    ps = (f"Get-ChildItem '{directory}' -Filter '{pattern}' -Recurse -File -ErrorAction SilentlyContinue | "
          f"Select-Object -First {max_results} FullName | ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            matches = [d.get("FullName", "") for d in data]
            return {"matches": matches, "count": len(matches)}
        except json.JSONDecodeError:
            pass
    return {"matches": [], "count": 0}


async def _get_file_info_powershell(params: dict) -> Any:
    """Method 2: Get file info via PowerShell."""
    path = params["path"]
    ps = (f"Get-Item '{path}' -ErrorAction Stop | "
          f"Select-Object FullName, Length, CreationTime, LastWriteTime, Extension, PSIsContainer | "
          f"ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            return {
                "path": data.get("FullName"),
                "is_file": not data.get("PSIsContainer", False),
                "is_dir": data.get("PSIsContainer", False),
                "size": data.get("Length", 0),
                "created": data.get("CreationTime"),
                "modified": data.get("LastWriteTime"),
                "extension": data.get("Extension"),
            }
        except json.JSONDecodeError:
            pass
    raise RuntimeError(f"File not found: {path}")


async def _get_file_hash_powershell(params: dict) -> Any:
    """Method 2: Get file hash via PowerShell."""
    path = params["path"]
    algo = params.get("algorithm", "sha256").upper()
    ps_map = {"MD5": "MD5", "SHA1": "SHA1", "SHA256": "SHA256"}
    ps_algo = ps_map.get(algo, "SHA256")
    ps = (f"Get-FileHash '{path}' -Algorithm {ps_algo} | "
          f"Select-Object Hash, Algorithm | ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            return {"hash": data.get("Hash", "").lower(), "algorithm": algo.lower()}
        except json.JSONDecodeError:
            pass
    raise RuntimeError(f"Could not hash file: {path}")


async def _append_file_powershell(params: dict) -> Any:
    """Method 2: Append to file via PowerShell."""
    path = params["path"]
    content = params.get("content", "")
    import base64
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    ps = (f"$text = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{encoded}')); "
          f"Add-Content -Path '{path}' -Value $text -Encoding UTF8")
    success, output = await run_ps(ps)
    if not success:
        raise RuntimeError(output)
    return {"appended": len(content), "path": path}


async def _list_drives_powershell(params: dict) -> Any:
    """Method 2: List drives via PowerShell."""
    ps = ("Get-PSDrive -PSProvider FileSystem | "
          "Select-Object Name, @{N='Used';E={$_.Used}}, @{N='Free';E={$_.Free}} | "
          "ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            drives = [{"device": f"{d.get('Name')}:\\",
                       "total_gb": round((d.get('Used', 0) + d.get('Free', 0)) / (1024**3), 1),
                       "free_gb": round(d.get('Free', 0) / (1024**3), 1)}
                      for d in data]
            return {"drives": drives}
        except json.JSONDecodeError:
            pass
    return {"drives": []}


async def _get_folder_size_powershell(params: dict) -> Any:
    """Method 2: Get folder size via PowerShell."""
    path = params["path"]
    ps = (f"$files = Get-ChildItem '{path}' -Recurse -File -ErrorAction SilentlyContinue; "
          f"$total = ($files | Measure-Object -Property Length -Sum).Sum; "
          f"@{{path='{path}'; size=$total}} | ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            total = data.get("size", 0)
            return {"path": path, "size": total, "size_human": _human_size(total)}
        except json.JSONDecodeError:
            pass
    return {"path": path, "size": 0, "size_human": "0 B"}


async def _empty_recycle_bin_powershell(params: dict) -> Any:
    """Method 2: Empty recycle bin via cmd."""
    success, output = await run_cmd(["cmd", "/c", "rd", "/s", "/q", "C:\\$Recycle.Bin"])
    return {"emptied": True}


async def _create_symlink_cmd(params: dict) -> Any:
    """Method 2: Create symlink via mklink."""
    target = params["target"]
    link = params["link"]
    success, output = await run_cmd(["cmd", "/c", "mklink", link, target])
    if not success:
        raise RuntimeError(output)
    return {"link": link, "target": target}


async def _set_attributes_powershell(params: dict) -> Any:
    """Method 2: Set file attributes via PowerShell."""
    path = params["path"]
    attrs = params.get("attributes", [])
    attr_map = {"hidden": "Hidden", "readonly": "ReadOnly", "system": "System", "archive": "Archive"}
    ps_cmds = []
    for attr in attrs:
        ps_attr = attr_map.get(attr.lower())
        if ps_attr:
            ps_cmds.append(f"Set-ItemProperty -Path '{path}' -Name Attributes -Value '{ps_attr}' -Force")
    if ps_cmds:
        success, output = await run_ps(";".join(ps_cmds))
    return {"path": path, "attributes": attrs}


async def _change_permissions_powershell(params: dict) -> Any:
    """Method 2: Change permissions via PowerShell."""
    path = params["path"]
    permission = params.get("permission", "F")
    user = params.get("user", "administrators")
    ps = (f"icacls '{path}' /grant {user}:{permission} /T /Q")
    success, output = await run_cmd(["icacls", path, f"/grant", f"{user}:{permission}", "/T"])
    if not success:
        raise RuntimeError(output)
    return {"path": path, "permission": permission, "user": user}


async def _get_drive_info_powershell(params: dict) -> Any:
    """Method 2: Get drive info via PowerShell."""
    drive = params.get("drive", "C:\\")
    if not drive.endswith("\\"):
        drive += "\\"
    ps = (f"$vol = Get-Volume -DriveLetter '{drive[0]}' -ErrorAction SilentlyContinue; "
          f"if ($vol) {{ @{{drive='{drive}'; total_gb=[math]::Round($vol.Size/1GB,1); free_gb=[math]::Round($vol.SizeRemaining/1GB,1)}} | ConvertTo-Json -Compress }}")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"drive": drive, "error": "Could not get drive info"}


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH CONTENT (grep-style)
# ══════════════════════════════════════════════════════════════════════════════

async def _search_content_pathlib(params: dict) -> Any:
    """Method 1: Search file content via pathlib + regex."""
    import re as _re
    directory = params.get("directory", ".")
    pattern = params.get("pattern", "")
    file_filter = params.get("file_filter", "*")
    regex = _re.compile(pattern, _re.IGNORECASE)
    matches = []
    for f in Path(directory).rglob(file_filter):
        if f.is_file():
            try:
                with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if regex.search(line):
                            matches.append({"file": str(f), "line": i, "text": line.strip()[:120]})
                            if len(matches) >= 50:
                                break
            except (PermissionError, OSError):
                continue
            if len(matches) >= 50:
                break
    return {"matches": matches, "count": len(matches)}


async def _search_content_powershell(params: dict) -> Any:
    """Method 2: Search file content via PowerShell Select-String."""
    directory = params.get("directory", ".")
    pattern = params.get("pattern", "")
    file_filter = params.get("file_filter", "*")
    ps = (f"Get-ChildItem '{directory}' -Filter '{file_filter}' -Recurse -File -ErrorAction SilentlyContinue | "
          f"Select-String -Pattern '{pattern}' -CaseSensitive:$false | "
          f"Select-Object -First 50 | ForEach-Object {{ @{{file=$_.Path; line=$_.LineNumber; text=$_.Line.Trim().Substring(0, [math]::Min(120, $_.Line.Trim().Length))}} }} | ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"matches": data, "count": len(data)}
        except json.JSONDecodeError:
            pass
    return {"matches": [], "count": 0}


# ══════════════════════════════════════════════════════════════════════════════
# FIND AND REPLACE
# ══════════════════════════════════════════════════════════════════════════════

async def _find_and_replace_pathlib(params: dict) -> Any:
    """Method 1: Find and replace via pathlib."""
    path = Path(params.get("path", ""))
    if not path.exists():
        raise RuntimeError(f"File not found: {path}")
    find_text = params.get("find_text", "")
    replace_text = params.get("replace_text", "")
    content = path.read_text(encoding="utf-8")
    count = content.count(find_text)
    new_content = content.replace(find_text, replace_text)
    path.write_text(new_content, encoding="utf-8")
    return {"replaced": count, "path": str(path)}


async def _find_and_replace_powershell(params: dict) -> Any:
    """Method 2: Find and replace via PowerShell."""
    path = params.get("path", "")
    find_text = params.get("find_text", "")
    replace_text = params.get("replace_text", "")
    import base64
    find_b64 = base64.b64encode(find_text.encode("utf-8")).decode("ascii")
    replace_b64 = base64.b64encode(replace_text.encode("utf-8")).decode("ascii")
    ps = (f"$content = [System.IO.File]::ReadAllText('{path}'); "
          f"$find = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{find_b64}')); "
          f"$replace = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{replace_b64}')); "
          f"$count = ([regex]::Matches($content, [regex]::Escape($find))).Count; "
          f"$content = $content.Replace($find, $replace); "
          f"[System.IO.File]::WriteAllText('{path}', $content); "
          f"Write-Output $count")
    success, output = await run_ps(ps)
    if success and output:
        return {"replaced": int(output), "path": path}
    raise RuntimeError(f"PowerShell replace failed: {output}")


# ══════════════════════════════════════════════════════════════════════════════
# BATCH RENAME
# ══════════════════════════════════════════════════════════════════════════════

async def _batch_rename_pathlib(params: dict) -> Any:
    """Method 1: Batch rename via pathlib."""
    directory = params.get("directory", ".")
    find_str = params.get("find", "")
    replace_str = params.get("replace", "")
    renamed = 0
    for item in Path(directory).iterdir():
        if find_str in item.name:
            item.rename(item.parent / item.name.replace(find_str, replace_str))
            renamed += 1
    return {"renamed": renamed}


async def _batch_rename_powershell(params: dict) -> Any:
    """Method 2: Batch rename via PowerShell."""
    directory = params.get("directory", ".")
    find_str = params.get("find", "")
    replace_str = params.get("replace", "")
    ps = (f"Get-ChildItem '{directory}' | Where-Object {{ $_.Name -like '*{find_str}*' }} | "
          f"ForEach-Object {{ $new = $_.Name -replace '{find_str}', '{replace_str}'; "
          f"Rename-Item $_.FullName -NewName $new }}")
    success, output = await run_ps(ps)
    return {"success": success, "directory": directory}


# ══════════════════════════════════════════════════════════════════════════════
# BATCH DELETE
# ══════════════════════════════════════════════════════════════════════════════

async def _batch_delete_pathlib(params: dict) -> Any:
    """Method 1: Batch delete via pathlib."""
    directory = params.get("directory", ".")
    pattern = params.get("pattern", "*")
    deleted = 0
    for item in Path(directory).glob(pattern):
        if item.is_file():
            item.unlink()
            deleted += 1
        elif item.is_dir():
            shutil.rmtree(str(item))
            deleted += 1
    return {"deleted": deleted}


async def _batch_delete_powershell(params: dict) -> Any:
    """Method 2: Batch delete via PowerShell."""
    directory = params.get("directory", ".")
    pattern = params.get("pattern", "*")
    ps = (f"$items = Get-ChildItem '{directory}' -Filter '{pattern}'; "
          f"$count = $items.Count; "
          f"$items | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue; "
          f"Write-Output $count")
    success, output = await run_ps(ps)
    count = int(output) if success and output.strip().isdigit() else 0
    return {"deleted": count}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION HANDLER
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    "delete_file":    ([_delete_pathlib, _delete_win32file, _delete_cmd_del, _delete_clear_attrs, _delete_take_ownership, _delete_kill_locking, _delete_delay_reboot], Verifiers.file_deleted),
    "delete_folder":  ([_delete_pathlib, _delete_cmd_del, _delete_clear_attrs], Verifiers.file_deleted),
    "create_file":    ([_create_pathlib, _create_builtin, _create_powershell], Verifiers.file_created),
    "read_file":      ([_read_pathlib, _read_powershell], Verifiers.file_exists),
    "write_file":     ([_create_pathlib, _create_builtin, _create_powershell], Verifiers.file_created),
    "copy_file":      ([_copy_shutil, _copy_win32file, _copy_cmd], Verifiers.file_copied),
    "move_file":      ([_move_pathlib, _move_shutil, _move_win32file], Verifiers.file_moved),
    "rename_file":    ([_move_pathlib, _move_shutil], Verifiers.file_moved),
    "list_directory": ([_list_pathlib, _list_directory_powershell], None),
    "search_files":   ([_search_files_everything, _search_files, _search_files_powershell], None),
    "get_file_info":  ([_get_file_info, _get_file_info_powershell], None),
    "get_file_hash":  ([_get_file_hash, _get_file_hash_powershell], None),
    "append_to_file": ([_append_file, _append_file_powershell], None),
    "list_drives":    ([_get_drives, _list_drives_powershell], None),
    "send_to_recycle_bin": ([_send_to_recycle_bin], Verifiers.file_deleted),
    "empty_recycle_bin":   ([_empty_recycle_bin, _empty_recycle_bin_powershell], None),
    "create_symlink": ([_create_symlink, _create_symlink_cmd], None),
    "get_folder_size": ([_get_folder_size, _get_folder_size_powershell], None),
    "take_ownership":  ([_take_ownership_action], None),
    "change_permissions": ([_change_permissions_action, _change_permissions_powershell], None),
    "monitor_path":    ([_monitor_path_action], None),
    "find_large_files": ([_find_large_files_action], None),
    "find_duplicates": ([_find_duplicates_action], None),
    "compress_file":   ([_compress_file_action], None),
    "decompress_file": ([_decompress_file_action], None),
    "create_hardlink": ([_create_hardlink_action], None),
    # --- Phase 7 additions ---
    "create_folder":    ([_create_folder_action, _create_folder_powershell], Verifiers.file_created),
    "set_file_attributes": ([_set_file_attributes_action, _set_attributes_powershell], None),
    "get_drive_info":   ([_get_drive_info_action, _get_drive_info_powershell], None),
    "restore_from_recycle_bin": ([_restore_from_recycle_bin_action], None),
    "get_locked_by":    ([_get_locked_by_action], None),
    "copy_folder_tree": ([_copy_folder_tree_action], None),
    "delete_folder_tree": ([_delete_folder_tree_action], Verifiers.folder_deleted),
    # Aliases for monitor_path
    "monitor_path_start": ([_monitor_path_action], None),
    "monitor_path_stop":  ([_monitor_path_action], None),
    # --- search_content (grep-style content search) ---
    "search_content":  ([_search_content_pathlib, _search_content_powershell], None),
    # --- find_and_replace ---
    "find_and_replace": ([_find_and_replace_pathlib, _find_and_replace_powershell], None),
    # --- batch operations ---
    "batch_rename":    ([_batch_rename_pathlib, _batch_rename_powershell], None),
    "batch_delete":    ([_batch_delete_pathlib, _batch_delete_powershell], Verifiers.file_deleted),
}


async def handler(action: str, params: dict[str, Any]) -> Result:
    """L1 Filesystem layer handler."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown filesystem action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"filesystem.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("filesystem", action),
        escalation_fn=create_escalation_fn("filesystem", action),
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
