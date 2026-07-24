"""Everything by voidtools — instant file search via SDK DLL (ctypes IPC).

Everything indexes the entire NTFS filesystem in ~1 second and returns
search results in < 1ms by querying its in-memory MFT index.

This module provides THREE backends in priority order:
  1. ctypes SDK (Everything*.dll) — Direct IPC, ~0.1ms, structured results
  2. HTTP API (localhost:80) — JSON responses, no subprocess
  3. es.exe CLI — Fallback subprocess call

Everything MUST be running in the background for any method to work.

Usage:
    from core.layers.everything_search import everything_search, is_everything_available
    if is_everything_available():
        results = await everything_search("chrome.exe", path="C:\\\\Program Files", max_results=10)
"""

from __future__ import annotations

import asyncio
import ctypes
import ctypes.wintypes
import datetime
import logging
import os
import re
import shutil
import struct
import subprocess
import time
from dataclasses import dataclass
from enum import IntFlag
from typing import Any

logger = logging.getLogger("may.core.layers.everything_search")


# ══════════════════════════════════════════════════════════════════════════════
# Everything SDK Constants (from Everything SDK header)
# ══════════════════════════════════════════════════════════════════════════════

class EverythingRequest(IntFlag):
    """SDK request flags — controls what data is returned per result."""
    FILE_NAME = 0x00000001
    PATH = 0x00000002
    FULL_PATH_AND_FILE_NAME = 0x00000004
    EXTENSION = 0x00000008
    SIZE = 0x00000010
    DATE_CREATED = 0x00000020
    DATE_MODIFIED = 0x00000040
    DATE_ACCESSED = 0x00000080
    ATTRIBUTES = 0x00000100
    FILE_LIST_FILE_NAME = 0x00000200
    RUN_COUNT = 0x00000400
    DATE_RUN = 0x00000800
    DATE_RECENTLY_CHANGED = 0x00001000
    HIGHLIGHTED_FILE_NAME = 0x00002000
    HIGHLIGHTED_PATH = 0x00004000
    HIGHLIGHTED_FULL_PATH_AND_FILE_NAME = 0x00008000


class EverythingSort(IntFlag):
    """SDK sort modes."""
    NAME_ASCENDING = 1
    NAME_DESCENDING = 2
    PATH_ASCENDING = 3
    PATH_DESCENDING = 4
    SIZE_ASCENDING = 5
    SIZE_DESCENDING = 6
    EXTENSION_ASCENDING = 7
    EXTENSION_DESCENDING = 8
    DATE_CREATED_ASCENDING = 9
    DATE_CREATED_DESCENDING = 10
    DATE_MODIFIED_ASCENDING = 11
    DATE_MODIFIED_DESCENDING = 12
    DATE_ACCESSED_ASCENDING = 13
    DATE_ACCESSED_DESCENDING = 14
    ATTRIBUTES_ASCENDING = 15
    ATTRIBUTES_DESCENDING = 16
    FILE_LIST_FILE_NAME_ASCENDING = 17
    FILE_LIST_FILE_NAME_DESCENDING = 18
    RUN_COUNT_ASCENDING = 19
    RUN_COUNT_DESCENDING = 20
    DATE_RECENTLY_CHANGED_ASCENDING = 21
    DATE_RECENTLY_CHANGED_DESCENDING = 22
    DATE_RUN_ASCENDING = 23
    DATE_RUN_DESCENDING = 24


# Windows FILETIME conversion constants
_WINDOWS_TICKS = int(1e7)  # 10,000,000 ticks per second
_WINDOWS_EPOCH = datetime.datetime(1601, 1, 1)
_POSIX_EPOCH = datetime.datetime(1970, 1, 1)
_EPOCH_DIFF = (_POSIX_EPOCH - _WINDOWS_EPOCH).total_seconds()
_WINDOWS_TICKS_TO_POSIX = _EPOCH_DIFF * _WINDOWS_TICKS


def _filetime_to_datetime(filetime: int) -> str | None:
    """Convert Windows FILETIME (64-bit int) to ISO datetime string."""
    if filetime == 0:
        return None
    try:
        microsecs = (filetime - _WINDOWS_TICKS_TO_POSIX) / _WINDOWS_TICKS
        return datetime.datetime.fromtimestamp(microsecs).isoformat()
    except (ValueError, OSError):
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Everything SDK DLL Loader
# ══════════════════════════════════════════════════════════════════════════════

_sdk_dll = None
_sdk_checked = False
_sdk_method = None  # 'dll', 'es', 'http', or None
_DB_NOT_LOADED = object()  # Sentinel: SDK loaded but DB not ready

# Regex to validate Windows paths returned by es.exe
_ES_PATH_RE = re.compile(r'^[A-Za-z]:\\|^\\\\')


def _find_sdk_dll() -> ctypes.WinDLL | None:
    """Find and load Everything SDK DLL (Everything.dll or Everything64.dll).

    The SDK DLL communicates with the Everything process via IPC.
    Everything must be running in the background.

    Note: Not thread-safe — safe only in asyncio (single thread).
    """
    global _sdk_dll, _sdk_checked, _sdk_method

    if _sdk_checked:
        return _sdk_dll

    _sdk_checked = True

    # Try to find the DLL via registry install location
    dll_names = ["Everything64.dll", "Everything32.dll", "Everything.dll"]
    search_dirs = []

    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for subkey in [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Everything",
                r"SOFTWARE\voidtools\Everything",
            ]:
                try:
                    key = winreg.OpenKey(hive, subkey)
                    install_dir = winreg.QueryValueEx(key, "InstallLocation")[0]
                    winreg.CloseKey(key)
                    search_dirs.append(os.path.join(install_dir, "SDK", "DLL"))
                    search_dirs.append(install_dir)
                except (OSError, FileNotFoundError):
                    continue
    except ImportError:
        pass

    # Add common locations
    search_dirs.extend([
        r"C:\Program Files\Everything\SDK\DLL",
        r"C:\Program Files\Everything",
        r"C:\Program Files (x86)\Everything\SDK\DLL",
        os.path.expandvars(r"%LOCALAPPDATA%\Everything\SDK\DLL"),
    ])

    # Also search the module's own directory (where Everything64.dll might be copied)
    module_dir = os.path.dirname(os.path.abspath(__file__))
    if module_dir not in search_dirs:
        search_dirs.append(module_dir)

    # Search the project root (2 levels up from core/layers/)
    project_root = os.path.dirname(os.path.dirname(module_dir))
    if project_root not in search_dirs:
        search_dirs.append(project_root)
        # Also check SDK subdirectory in project root
        search_dirs.append(os.path.join(project_root, "Everything-SDK", "dll"))

    for dll_name in dll_names:
        for search_dir in search_dirs:
            dll_path = os.path.join(search_dir, dll_name)
            if os.path.isfile(dll_path):
                try:
                    dll = ctypes.WinDLL(dll_path)
                    # Quick sanity check — can we call a basic function?
                    dll.Everything_GetNumResults()
                    _setup_sdk_functions(dll)
                    _sdk_dll = dll
                    _sdk_method = "dll"
                    logger.info("Everything SDK DLL loaded: %s", dll_path)
                    return _sdk_dll
                except Exception as e:
                    logger.debug("Failed to load %s: %s", dll_path, e)
                    continue

    logger.debug("Everything SDK DLL not found — will try es.exe/HTTP fallback")
    return None


def _setup_sdk_functions(dll: ctypes.WinDLL) -> None:
    """Configure argument and return types for SDK DLL functions.

    Each function setup is wrapped in try/except so a single missing
    function (e.g. in an older SDK DLL version) doesn't prevent the
    entire DLL from loading.
    """
    def _safe_setup(func_name: str, argtypes=None, restype=None):
        try:
            fn = getattr(dll, func_name)
            if argtypes is not None:
                fn.argtypes = argtypes
            if restype is not None:
                fn.restype = restype
        except (AttributeError, OSError):
            pass  # Function doesn't exist in this DLL version

    # Search state
    _safe_setup("Everything_SetSearchW", [ctypes.c_wchar_p], None)
    _safe_setup("Everything_SetMatchPath", [ctypes.c_bool])
    _safe_setup("Everything_SetMatchCase", [ctypes.c_bool])
    _safe_setup("Everything_SetMatchWholeWord", [ctypes.c_bool])
    _safe_setup("Everything_SetRegex", [ctypes.c_bool])
    _safe_setup("Everything_SetMax", [ctypes.c_int])
    _safe_setup("Everything_SetOffset", [ctypes.c_int])
    _safe_setup("Everything_SetSort", [ctypes.c_int])
    _safe_setup("Everything_SetRequestFlags", [ctypes.c_int])

    # Query execution
    _safe_setup("Everything_QueryW", [ctypes.c_bool], ctypes.c_bool)

    # Result counts
    _safe_setup("Everything_GetNumResults", restype=ctypes.c_int)
    _safe_setup("Everything_GetTotResults", restype=ctypes.c_int)
    _safe_setup("Everything_GetNumFileResults", restype=ctypes.c_int)
    _safe_setup("Everything_GetNumFolderResults", restype=ctypes.c_int)

    # Result reading
    _safe_setup("Everything_IsFileResult", [ctypes.c_int], ctypes.c_bool)
    _safe_setup("Everything_IsFolderResult", [ctypes.c_int], ctypes.c_bool)
    _safe_setup("Everything_GetResultFullPathNameW",
               [ctypes.c_int, ctypes.c_wchar_p, ctypes.c_int], ctypes.c_int)
    _safe_setup("Everything_GetResultFileNameW", [ctypes.c_int], ctypes.c_wchar_p)
    _safe_setup("Everything_GetResultSize",
               [ctypes.c_int, ctypes.POINTER(ctypes.c_ulonglong)])
    _safe_setup("Everything_GetResultDateModified",
               [ctypes.c_int, ctypes.POINTER(ctypes.c_ulonglong)])
    _safe_setup("Everything_GetResultDateCreated",
               [ctypes.c_int, ctypes.POINTER(ctypes.c_ulonglong)])
    _safe_setup("Everything_GetResultRunCount", [ctypes.c_int], ctypes.c_int)
    _safe_setup("Everything_GetResultExtension", [ctypes.c_int], ctypes.c_wchar_p)

    # DB status
    _safe_setup("Everything_IsDBLoaded", restype=ctypes.c_bool)
    _safe_setup("Everything_IsFastSort", restype=ctypes.c_bool)
    _safe_setup("Everything_IsFileInfoIndexed", restype=ctypes.c_bool)


# ══════════════════════════════════════════════════════════════════════════════
# Everything Installation Detection
# ══════════════════════════════════════════════════════════════════════════════

_es_path_cache: str | None = None
_es_checked = False

_COMMON_ES_PATHS = [
    r"C:\Program Files\Everything\es.exe",
    r"C:\Program Files (x86)\Everything\es.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Everything\es.exe"),
    os.path.expandvars(r"%PROGRAMDATA%\Everything\es.exe"),
    # Project-local es.exe (copied from Everything SDK)
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "es.exe"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "es-exe", "es.exe"),
]

_ES_REGISTRY_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Everything"


def _find_es_exe() -> str | None:
    """Find es.exe on the system. Checks PATH, registry, and common locations."""
    global _es_path_cache, _es_checked
    if _es_checked:
        return _es_path_cache
    _es_checked = True

    path_result = shutil.which("es.exe")
    if path_result:
        _es_path_cache = path_result
        return _es_path_cache

    for candidate in _COMMON_ES_PATHS:
        if os.path.isfile(candidate):
            _es_path_cache = candidate
            return _es_path_cache

    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                key = winreg.OpenKey(hive, _ES_REGISTRY_KEY)
                install_dir = winreg.QueryValueEx(key, "InstallLocation")[0]
                winreg.CloseKey(key)
                candidate = os.path.join(install_dir, "es.exe")
                if os.path.isfile(candidate):
                    _es_path_cache = candidate
                    return _es_path_cache
            except (OSError, FileNotFoundError):
                continue
    except ImportError:
        pass

    return None


def is_everything_available() -> bool:
    """Check if Everything by voidtools is available (SDK DLL or es.exe)."""
    if _find_sdk_dll() is not None:
        return True
    return _find_es_exe() is not None


def get_backend() -> str:
    """Return which backend is available: 'dll', 'es', 'http', or 'none'."""
    if _find_sdk_dll() is not None:
        return "dll"
    if _find_es_exe() is not None:
        return "es"
    return "none"


def get_es_path() -> str | None:
    """Get the path to es.exe, or None if not available."""
    return _find_es_exe()


def reset_detection_cache():
    """Reset all detection caches."""
    global _sdk_dll, _sdk_checked, _sdk_method, _es_path_cache, _es_checked
    _sdk_dll = None
    _sdk_checked = False
    _sdk_method = None
    _es_path_cache = None
    _es_checked = False


# ══════════════════════════════════════════════════════════════════════════════
# Sort Mode Mapping
# ══════════════════════════════════════════════════════════════════════════════

_SORT_MAP = {
    "name": (EverythingSort.NAME_ASCENDING, EverythingSort.NAME_DESCENDING),
    "path": (EverythingSort.PATH_ASCENDING, EverythingSort.PATH_DESCENDING),
    "size": (EverythingSort.SIZE_ASCENDING, EverythingSort.SIZE_DESCENDING),
    "extension": (EverythingSort.EXTENSION_ASCENDING, EverythingSort.EXTENSION_DESCENDING),
    "date_created": (EverythingSort.DATE_CREATED_ASCENDING, EverythingSort.DATE_CREATED_DESCENDING),
    "date_modified": (EverythingSort.DATE_MODIFIED_ASCENDING, EverythingSort.DATE_MODIFIED_DESCENDING),
    "date_accessed": (EverythingSort.DATE_ACCESSED_ASCENDING, EverythingSort.DATE_ACCESSED_DESCENDING),
    "run_count": (EverythingSort.RUN_COUNT_ASCENDING, EverythingSort.RUN_COUNT_DESCENDING),
    "date_recently_changed": (EverythingSort.DATE_RECENTLY_CHANGED_ASCENDING, EverythingSort.DATE_RECENTLY_CHANGED_DESCENDING),
}


# ══════════════════════════════════════════════════════════════════════════════
# Search Result Dataclass
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EverythingResult:
    """A single search result from Everything."""
    path: str
    name: str | None = None
    size: int | None = None
    date_modified: str | None = None
    date_created: str | None = None
    extension: str | None = None
    run_count: int | None = None


# ══════════════════════════════════════════════════════════════════════════════
# Backend 1: ctypes SDK (Direct IPC — fastest, ~0.1ms)
# ══════════════════════════════════════════════════════════════════════════════

def _sdk_search(
    query: str,
    path: str | None = None,
    max_results: int = 50,
    files_only: bool = False,
    folders_only: bool = False,
    sort_by: str | None = None,
    sort_descending: bool = False,
    include_size: bool = False,
    include_date_modified: bool = False,
    include_date_created: bool = False,
    include_run_count: bool = False,
) -> list[EverythingResult]:
    """Search via Everything SDK DLL — direct IPC, no subprocess."""
    dll = _find_sdk_dll()
    if dll is None:
        return []

    # _setup_sdk_functions already called during _find_sdk_dll load

    # Build the search query
    search = query
    if path:
        search = f"path:{path}\\ {query}"

    # Configure search state
    dll.Everything_SetSearchW(search)
    dll.Everything_SetMatchPath(bool(path))
    dll.Everything_SetMax(max_results)
    dll.Everything_SetOffset(0)

    # Sort
    if sort_by and sort_by in _SORT_MAP:
        ascending, descending = _SORT_MAP[sort_by]
        dll.Everything_SetSort(descending if sort_descending else ascending)

    # Request flags — request all the data we need
    flags = (
        EverythingRequest.FULL_PATH_AND_FILE_NAME
        | EverythingRequest.FILE_NAME
        | EverythingRequest.PATH
        | EverythingRequest.EXTENSION
    )
    if include_size:
        flags |= EverythingRequest.SIZE
    if include_date_modified:
        flags |= EverythingRequest.DATE_MODIFIED
    if include_date_created:
        flags |= EverythingRequest.DATE_CREATED
    if include_run_count:
        flags |= EverythingRequest.RUN_COUNT

    dll.Everything_SetRequestFlags(int(flags))

    # Execute the query (blocking but ~0.1ms)
    dll.Everything_QueryW(True)

    # Check if DB is loaded (everything must be running and have indexed)
    # Retry up to 3 times with 1s delay — Everything may still be indexing
    for _attempt in range(3):
        if dll.Everything_IsDBLoaded():
            break
        if _attempt == 0:
            logger.info("Everything DB not loaded yet — waiting for indexing...")
        # NOTE: Blocking sleep in sync function called from async context.
        # Acceptable because SDK DLL is inherently synchronous (~0.1ms query)
        # and the DB load wait is bounded to 3s total.
        time.sleep(1.0)
    else:
        # Still not loaded after 3 retries — signal for fallback
        logger.warning("Everything DB not loaded after retries — trying es.exe/HTTP fallbacks")
        return _DB_NOT_LOADED  # type: ignore[return-value]

    # Read results
    num_results = dll.Everything_GetNumResults()
    results = []
    filename_buf = ctypes.create_unicode_buffer(260)
    size_buf = ctypes.c_ulonglong(0)
    date_mod_buf = ctypes.c_ulonglong(0)
    date_created_buf = ctypes.c_ulonglong(0)

    for i in range(min(num_results, max_results)):
        try:
            # Get full path
            dll.Everything_GetResultFullPathNameW(i, filename_buf, 260)
            full_path = filename_buf.value

            if not full_path:
                continue

            # Apply file/folder filter in-memory
            is_file = dll.Everything_IsFileResult(i)
            if files_only and not is_file:
                continue
            if folders_only and is_file:
                continue

            result = EverythingResult(path=full_path)

            # Get file name
            name_ptr = dll.Everything_GetResultFileNameW(i)
            if name_ptr:
                result.name = name_ptr

            # Get extension (optional SDK function — older Everything DLLs don't
            # export Everything_GetResultExtension; derive from the filename instead
            # of calling a missing function 564 times per search).
            if not result.extension and full_path:
                ext = os.path.splitext(full_path)[1]
                if ext:
                    result.extension = ext.lstrip(".")
            # Try SDK extension function only if not already derived from path
            if not result.extension:
                try:
                    ext_ptr = dll.Everything_GetResultExtension(i)
                    if ext_ptr:
                        result.extension = ext_ptr
                except (AttributeError, OSError):
                    pass

            # Get size
            if include_size:
                dll.Everything_GetResultSize(i, ctypes.byref(size_buf))
                result.size = size_buf.value

            # Get date modified
            if include_date_modified:
                dll.Everything_GetResultDateModified(i, ctypes.byref(date_mod_buf))
                result.date_modified = _filetime_to_datetime(date_mod_buf.value)

            # Get date created
            if include_date_created:
                dll.Everything_GetResultDateCreated(i, ctypes.byref(date_created_buf))
                result.date_created = _filetime_to_datetime(date_created_buf.value)

            # Get run count
            if include_run_count:
                result.run_count = dll.Everything_GetResultRunCount(i)

            results.append(result)

        except Exception as e:
            logger.debug("Error reading result %d: %s", i, e)
            continue

    return results


# ══════════════════════════════════════════════════════════════════════════════
# Backend 2: HTTP API (JSON — no subprocess, ~1ms)
# ══════════════════════════════════════════════════════════════════════════════

async def _http_search(
    query: str,
    path: str | None = None,
    max_results: int = 50,
    files_only: bool = False,
    folders_only: bool = False,
    include_size: bool = False,
    include_date_modified: bool = False,
    port: int = 80,
) -> list[EverythingResult]:
    """Search via Everything HTTP server (JSON API)."""
    import httpx

    params = {
        "search": query,
        "json": 1,
        "count": max_results,
    }
    if path:
        params["path"] = 1
    if include_size:
        params["size_column"] = 1
    if include_date_modified:
        params["date_modified_column"] = 1

    url = f"http://localhost:{port}/"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            # Everything HTTP JSON returns a flat list or {"results": [...]}  
            items = data if isinstance(data, list) else data.get("results", [])
            results = []
            for item in items:
                name = item.get("name", "")
                path_part = item.get("path", "")
                full_path = f"{path_part}\\{name}" if path_part else name

                result = EverythingResult(
                    path=full_path,
                    name=name,
                )
                if include_size and "size" in item:
                    result.size = item["size"]
                if include_date_modified and "date_modified" in item:
                    result.date_modified = item["date_modified"]
                results.append(result)
            return results

    except Exception as e:
        logger.debug("HTTP search failed: %s", e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Backend 3: es.exe CLI (subprocess — slowest, ~50-200ms)
# ══════════════════════════════════════════════════════════════════════════════

async def _es_search(
    query: str,
    path: str | None = None,
    max_results: int = 50,
    files_only: bool = False,
    folders_only: bool = False,
    sort_by: str | None = None,
    sort_descending: bool = False,
    include_size: bool = False,
    include_date_modified: bool = False,
    include_date_created: bool = False,
    include_run_count: bool = False,
    timeout: float = 5.0,
) -> list[EverythingResult]:
    """Search via es.exe subprocess — fallback when SDK DLL not available."""
    es_path = _find_es_exe()
    if not es_path:
        return []

    cmd = [es_path]
    if path:
        cmd.extend(["-path", path])
    cmd.extend(["-n", str(max_results)])
    if files_only:
        cmd.append("/a-d")
    elif folders_only:
        cmd.append("/ad")
    if sort_by:
        # es.exe sort names use hyphens, not underscores
        es_sort = sort_by.replace("_", "-")
        if sort_descending:
            es_sort += "-descending"
        cmd.extend(["-sort", es_sort])
    if include_size:
        cmd.append("-size")
    if include_date_modified:
        cmd.append("-date-modified")
    cmd.append(query)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace").strip()

        if not output:
            return []

        # es.exe returns one path per line (no size/date metadata).
        # CRITICAL: When es.exe finds NO results, it prints help text
        # starting with "ES <version>". We detect this and return empty.
        # Valid results always look like Windows paths (C:\\... or \\\\server\\\...).
        results = []
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            # es.exe help text always starts with version header
            if line.startswith("ES "):
                break
            # Only accept lines that look like valid Windows paths
            if _ES_PATH_RE.match(line):
                results.append(EverythingResult(path=line))
        return results

    except Exception as e:
        logger.debug("es.exe search failed: %s", e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Public API — Auto-selects best backend
# ══════════════════════════════════════════════════════════════════════════════

async def everything_search(
    query: str,
    path: str | None = None,
    max_results: int = 50,
    files_only: bool = False,
    folders_only: bool = False,
    sort_by: str | None = None,
    sort_descending: bool = False,
    include_size: bool = False,
    include_date_modified: bool = False,
    include_date_created: bool = False,
    include_run_count: bool = False,
    timeout: float = 5.0,
) -> list[EverythingResult]:
    """Search for files/folders using Everything.

    Auto-selects the best available backend:
      1. ctypes SDK DLL (fastest, ~0.1ms)
      2. HTTP API (fast, ~1ms)
      3. es.exe CLI (fallback, ~50ms)

    Args:
        query: Search term (supports Everything search syntax)
        path: Restrict search to this directory
        max_results: Maximum results (default 50)
        files_only: Only return files
        folders_only: Only return folders
        sort_by: 'name', 'path', 'size', 'date_modified', 'run_count', etc.
        sort_descending: Sort descending
        include_size: Include file sizes
        include_date_modified: Include modification dates
        include_date_created: Include creation dates
        include_run_count: Include run counts (for app discovery)
        timeout: Timeout for async backends (es.exe, HTTP)

    Returns:
        List of EverythingResult objects, empty list on error.
    """
    # Try SDK DLL first (synchronous but ~0.1ms — blocks event loop less
    # than the async overhead of subprocess/HTTP would add)
    if _find_sdk_dll() is not None:
        try:
            results = _sdk_search(
                query, path, max_results, files_only, folders_only,
                sort_by, sort_descending, include_size,
                include_date_modified, include_date_created, include_run_count,
            )
            if results is _DB_NOT_LOADED:
                logger.info("SDK: DB not loaded — trying es.exe/HTTP fallbacks")
                # Don't return yet — fall through to HTTP/es.exe below
            elif results:
                return results  # Got results from SDK, done
            else:
                # SDK returned empty list = DB loaded but no matches found
                # Still try es.exe as a second opinion (it may have different indexing)
                pass
        except Exception as e:
            logger.warning("SDK search failed, falling back: %s", e)

    # Try HTTP API
    try:
        results = await _http_search(
            query, path, max_results, files_only, folders_only,
            include_size, include_date_modified,
        )
        if results:
            return results
    except Exception:
        pass

    # Fallback to es.exe (also serves as second opinion when SDK found nothing)
    es_results = await _es_search(
        query, path, max_results, files_only, folders_only,
        sort_by, sort_descending, include_size, include_date_modified, timeout,
    )
    return es_results


async def everything_search_paths(
    query: str,
    path: str | None = None,
    max_results: int = 50,
    files_only: bool = False,
    folders_only: bool = False,
    timeout: float = 5.0,
) -> list[str]:
    """Simplified search returning just paths as strings.

    Primary interface used by L1_filesystem and L3_application.
    """
    results = await everything_search(
        query=query,
        path=path,
        max_results=max_results,
        files_only=files_only,
        folders_only=folders_only,
        timeout=timeout,
    )
    return [r.path for r in results]


async def everything_find_app(
    app_name: str,
    max_results: int = 10,
    timeout: float = 15.0,
) -> list[str]:
    """Find an application executable using Everything.

    Searches for .exe files matching the app name, sorted by run count
    (most-used first) when the SDK DLL is available.

    Args:
        app_name: Name of the app (e.g. "chrome", "firefox", "vscode")
        max_results: Maximum results
        timeout: Timeout for async backends

    Returns:
        List of executable paths, best matches first.
    """
    # Try multiple search strategies for multi-word app names
    queries = [
        f"{app_name}.exe",           # exact with .exe
        app_name.replace(" ", ""),   # no spaces: "horizonzerodawn"
        app_name.replace(" ", ""),   # camelCase: "HorizonZeroDawn"
        app_name,                     # original name
    ]
    
    for query in queries:
        results = await everything_search(
            query=query,
            max_results=max_results * 3,
            files_only=True,
            sort_by="run_count",
            sort_descending=True,
            include_run_count=True,
            timeout=timeout,
        )
        exe_results = [r for r in results if r.path.lower().endswith(".exe")]
        if exe_results:
            return [r.path for r in exe_results[:max_results]]

    return []
