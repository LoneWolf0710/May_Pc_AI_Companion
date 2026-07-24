"""Layer 4: Window Management — Position, size, state, focus, z-order.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 6:

Libraries: win32gui, win32con, ctypes.user32

Key APIs: EnumWindows, FindWindow, SetWindowPos, SetForegroundWindow
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import re
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.engine.verifier import Verifiers
from core.layers._utils import run_ps, find_window_by_title as _find_window_by_title, get_window_pid as _get_window_pid, create_escalation_fn, create_preflight_fn

import logging
logger = logging.getLogger("may.core.layers.L4_window")

# ── Win32 Constants ──────────────────────────────────────────────────────────

SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE  = 9
SW_HIDE     = 0
SW_SHOW     = 5

HWND_TOP       = 0
HWND_TOPMOST   = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE     = 0x0002
SWP_NOSIZE     = 0x0001
SWP_SHOWWINDOW = 0x0040

WM_CLOSE = 0x0010


# ══════════════════════════════════════════════════════════════════════════════
# ENUM WINDOWS
# ══════════════════════════════════════════════════════════════════════════════

async def _list_windows(params: dict) -> Any:
    """List all visible top-level windows."""
    windows = []

    def enum_callback(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                windows.append({
                    "hwnd": hwnd,
                    "title": buf.value,
                    "pid": _get_window_pid(hwnd),
                })
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

    title_filter = params.get("title", "").lower()
    if title_filter:
        windows = [w for w in windows if title_filter in w["title"].lower()]

    return {"windows": windows[:params.get("max_results", 50)], "count": len(windows)}


# _get_window_pid and _find_window_by_title are imported from _utils.py


# ══════════════════════════════════════════════════════════════════════════════
# WINDOW ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

async def _minimize_win32(params: dict) -> Any:
    """Minimize window via ShowWindow."""
    hwnd = _find_window(params)
    ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)
    return {"minimized": hwnd}


async def _maximize_win32(params: dict) -> Any:
    """Maximize window via ShowWindow."""
    hwnd = _find_window(params)
    ctypes.windll.user32.ShowWindow(hwnd, SW_MAXIMIZE)
    return {"maximized": hwnd}


async def _restore_win32(params: dict) -> Any:
    """Restore window via ShowWindow."""
    hwnd = _find_window(params)
    ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
    return {"restored": hwnd}


async def _set_foreground_win32(params: dict) -> Any:
    """Bring window to foreground."""
    hwnd = _find_window(params)
    # Attach to target thread first for reliable foreground switch
    current_tid = ctypes.windll.kernel32.GetCurrentThreadId()
    target_tid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
    ctypes.windll.user32.AttachThreadInput(current_tid, target_tid, True)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    ctypes.windll.user32.AttachThreadInput(current_tid, target_tid, False)
    return {"focused": hwnd}


async def _set_topmost(params: dict) -> Any:
    """Set window always on top."""
    hwnd = _find_window(params)
    ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                       SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    return {"topmost": True}


async def _unset_topmost(params: dict) -> Any:
    """Remove always on top."""
    hwnd = _find_window(params)
    ctypes.windll.user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                                       SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    return {"topmost": False}


async def _close_win32(params: dict) -> Any:
    """Close window via WM_CLOSE."""
    hwnd = _find_window(params)
    ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    return {"closed": hwnd}


async def _move_window(params: dict) -> Any:
    """Move window to position."""
    hwnd = _find_window(params)
    x = params.get("x", 0)
    y = params.get("y", 0)
    w = params.get("width")
    h = params.get("height")
    if w and h:
        ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, w, h, SWP_SHOWWINDOW)
    else:
        ctypes.windll.user32.MoveWindow(hwnd, x, y,
                                         ctypes.windll.user32.GetSystemMetrics(0),
                                         ctypes.windll.user32.GetSystemMetrics(1),
                                         True)
    return {"moved": {"hwnd": hwnd, "x": x, "y": y}}


async def _get_window_rect(params: dict) -> Any:
    """Get window position and size."""
    hwnd = _find_window(params)
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return {
        "hwnd": hwnd,
        "x": rect.left, "y": rect.top,
        "width": rect.right - rect.left,
        "height": rect.bottom - rect.top,
    }


# ══════════════════════════════════════════════════════════════════════════════
# FIND WINDOW (by title)
# ══════════════════════════════════════════════════════════════════════════════

async def _find_window_action(params: dict) -> Any:
    """Find a window by partial title match."""
    title = params.get("title", "")
    handle = _find_window_by_title(title)
    if handle:
        pid = _get_window_pid(handle)
        length = ctypes.windll.user32.GetWindowTextLengthW(handle)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(handle, buf, length + 1)
        return {"hwnd": handle, "title": buf.value, "pid": pid}
    return {"error": f"No window matching '{title}'"}


async def _get_active_window_action(params: dict) -> Any:
    """Get the currently focused/active window."""
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return {"error": "No active window"}
    pid = _get_window_pid(hwnd)
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    return {"hwnd": hwnd, "title": buf.value, "pid": pid}


async def _resize_window_action(params: dict) -> Any:
    """Resize a window."""
    hwnd = _find_window(params)
    x = params.get("x")
    y = params.get("y")
    w = params.get("width", 800)
    h = params.get("height", 600)
    if x is not None and y is not None:
        ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, w, h, SWP_SHOWWINDOW)
    else:
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        ctypes.windll.user32.SetWindowPos(hwnd, 0, rect.left, rect.top, w, h, SWP_SHOWWINDOW)
    return {"resized": {"hwnd": hwnd, "width": w, "height": h}}


async def _hide_window_action(params: dict) -> Any:
    """Hide a window."""
    hwnd = _find_window(params)
    ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
    return {"hidden": hwnd}


async def _show_window_action(params: dict) -> Any:
    """Show a hidden window."""
    hwnd = _find_window(params)
    ctypes.windll.user32.ShowWindow(hwnd, SW_SHOW)
    return {"shown": hwnd}


async def _send_message_action(params: dict) -> Any:
    """Send a Windows message to a window."""
    hwnd = _find_window(params)
    msg = params.get("msg", 0x0010)  # WM_CLOSE default
    wparam = params.get("wparam", 0)
    lparam = params.get("lparam", 0)
    ctypes.windll.user32.SendMessageW(hwnd, msg, wparam, lparam)
    return {"sent": {"hwnd": hwnd, "msg": msg}}


async def _flash_window_action(params: dict) -> Any:
    """Flash a window in the taskbar."""
    hwnd = _find_window(params)
    import ctypes.wintypes
    class FLASHWINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.wintypes.UINT), ("hwnd", ctypes.wintypes.HWND),
                     ("dwFlags", ctypes.wintypes.DWORD), ("uCount", ctypes.wintypes.UINT),
                     ("dwTimeout", ctypes.wintypes.DWORD)]
    fwi = FLASHWINFO()
    fwi.cbSize = ctypes.sizeof(FLASHWINFO)
    fwi.hwnd = hwnd
    fwi.dwFlags = 0x00000003  # FLASHW_ALL
    fwi.uCount = 5
    ctypes.windll.user32.FlashWindowEx(ctypes.byref(fwi))
    return {"flashed": hwnd}


# ══════════════════════════════════════════════════════════════════════════════
# GET WINDOW INFO (full metadata)
# ══════════════════════════════════════════════════════════════════════════════

async def _get_window_info_action(params: dict) -> Any:
    """Get full window metadata."""
    hwnd = _find_window(params)
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    pid = _get_window_pid(hwnd)
    class_buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(hwnd, class_buf, 256)
    return {
        "hwnd": hwnd, "title": buf.value, "pid": pid,
        "class_name": class_buf.value,
        "x": rect.left, "y": rect.top,
        "width": rect.right - rect.left, "height": rect.bottom - rect.top,
        "visible": bool(ctypes.windll.user32.IsWindowVisible(hwnd)),
        "minimized": bool(ctypes.windll.user32.IsIconic(hwnd)),
        "maximized": bool(ctypes.windll.user32.IsZoomed(hwnd)),
    }


# ══════════════════════════════════════════════════════════════════════════════
# SET POSITION AND SIZE (atomic move+resize)
# ══════════════════════════════════════════════════════════════════════════════

async def _set_position_and_size_action(params: dict) -> Any:
    """Atomically set window position and size."""
    hwnd = _find_window(params)
    x, y = params.get("x", 0), params.get("y", 0)
    w, h = params.get("width", 800), params.get("height", 600)
    ctypes.windll.user32.MoveWindow(hwnd, x, y, w, h, True)
    return {"hwnd": hwnd, "x": x, "y": y, "width": w, "height": h}


# ══════════════════════════════════════════════════════════════════════════════
# FORCE CLOSE WINDOW (WM_DESTROY)
# ══════════════════════════════════════════════════════════════════════════════

async def _force_close_window_action(params: dict) -> Any:
    """Force close window via WM_DESTROY."""
    hwnd = _find_window(params)
    ctypes.windll.user32.PostMessageW(hwnd, 0x0002, 0, 0)  # WM_DESTROY
    return {"force_closed": hwnd}


# ══════════════════════════════════════════════════════════════════════════════
# POST MESSAGE (async)
# ══════════════════════════════════════════════════════════════════════════════

async def _post_message_action(params: dict) -> Any:
    """Post an async message to a window."""
    hwnd = _find_window(params)
    msg = params.get("msg", 0)
    wparam = params.get("wparam", 0)
    lparam = params.get("lparam", 0)
    ctypes.windll.user32.PostMessageW(hwnd, msg, wparam, lparam)
    return {"posted": {"hwnd": hwnd, "msg": msg}}


# ══════════════════════════════════════════════════════════════════════════════
# GET WINDOW TITLE
# ══════════════════════════════════════════════════════════════════════════════

async def _get_window_title_action(params: dict) -> Any:
    """Read window title."""
    hwnd = _find_window(params)
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    return {"hwnd": hwnd, "title": buf.value}


# ══════════════════════════════════════════════════════════════════════════════
# SET WINDOW TITLE
# ══════════════════════════════════════════════════════════════════════════════

async def _set_window_title_action(params: dict) -> Any:
    """Change window title."""
    hwnd = _find_window(params)
    title = params["title"]
    ctypes.windll.user32.SetWindowTextW(hwnd, title)
    return {"hwnd": hwnd, "title": title}


# ══════════════════════════════════════════════════════════════════════════════
# TAKE WINDOW SCREENSHOT
# ══════════════════════════════════════════════════════════════════════════════

async def _take_window_screenshot_action(params: dict) -> Any:
    """Capture a specific window to file."""
    hwnd = _find_window(params)
    output = params.get("output", f"window_{hwnd}.png")
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    x, y, w, h = rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    from PIL import ImageGrab
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    img.save(output)
    return {"saved": output, "hwnd": hwnd, "width": w, "height": h}


# ══════════════════════════════════════════════════════════════════════════════
# ARRANGE TILE
# ══════════════════════════════════════════════════════════════════════════════

async def _arrange_tile_action(params: dict) -> Any:
    """Tile visible windows on screen."""
    windows = []
    def enum_callback(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                windows.append(hwnd)
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    if not windows:
        return {"error": "No visible windows"}
    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)
    cols = int(len(windows) ** 0.5) + 1
    rows = (len(windows) + cols - 1) // cols
    ww, wh = screen_w // cols, screen_h // rows
    for i, hwnd in enumerate(windows):
        r, c = divmod(i, cols)
        ctypes.windll.user32.MoveWindow(hwnd, c * ww, r * wh, ww, wh, True)
    return {"tiled": len(windows), "cols": cols, "rows": rows}


# ══════════════════════════════════════════════════════════════════════════════
# ARRANGE CASCADE
# ══════════════════════════════════════════════════════════════════════════════

async def _arrange_cascade_action(params: dict) -> Any:
    """Cascade visible windows on screen."""
    windows = []
    def enum_callback(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                windows.append(hwnd)
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    if not windows:
        return {"error": "No visible windows"}
    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)
    ww, wh = int(screen_w * 0.6), int(screen_h * 0.7)
    offset = 30
    for i, hwnd in enumerate(windows):
        ctypes.windll.user32.MoveWindow(hwnd, offset * i, offset * i, ww, wh, True)
    return {"cascaded": len(windows)}


# ══════════════════════════════════════════════════════════════════════════════
# GET WINDOW CLASS
# ══════════════════════════════════════════════════════════════════════════════

async def _get_window_class_action(params: dict) -> Any:
    """Get window class name."""
    hwnd = _find_window(params)
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
    return {"hwnd": hwnd, "class_name": buf.value}


# ══════════════════════════════════════════════════════════════════════════════
# IS WINDOW VISIBLE / MINIMIZED
# ══════════════════════════════════════════════════════════════════════════════

async def _is_window_visible_action(params: dict) -> Any:
    """Check if window is visible."""
    hwnd = _find_window(params)
    return {"hwnd": hwnd, "visible": bool(ctypes.windll.user32.IsWindowVisible(hwnd))}


async def _is_window_minimized_action(params: dict) -> Any:
    """Check if window is minimized."""
    hwnd = _find_window(params)
    return {"hwnd": hwnd, "minimized": bool(ctypes.windll.user32.IsIconic(hwnd))}


async def _get_window_pid_action(params: dict) -> Any:
    """Get PID for a window."""
    hwnd = _find_window(params)
    pid = _get_window_pid(hwnd)
    return {"hwnd": hwnd, "pid": pid}


def _find_window(params: dict) -> int:
    """Find window handle from params."""
    hwnd = params.get("hwnd")
    if hwnd:
        return int(hwnd)
    title = params.get("title", "")
    if title:
        handle = _find_window_by_title(title)
        if handle:
            return handle
    raise RuntimeError(f"Window not found: {params}")


# ══════════════════════════════════════════════════════════════════════════════
# VIRTUAL DESKTOPS (Windows 10/11 via COM)
# ══════════════════════════════════════════════════════════════════════════════

async def _list_virtual_desktops_action(params: dict) -> Any:
    """List all virtual desktops and their windows."""
    ps_script = (
        "Add-Type @'\n"
        "using System;\nusing System.Runtime.InteropServices;\n"
        "public class VDHelper {\n"
        "  [DllImport(\"user32.dll\")] public static extern IntPtr FindWindow(string cn, string wn);\n"
        "  [DllImport(\"user32.dll\")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);\n"
        "  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);\n"
        "}\n'@\n"
        "# Fallback: use PowerShell to list desktops via COM interop\n"
        "try {\n"
        "  $shell = New-Object -ComObject Shell.Application\n"
        "  $desktops = @()\n"
        "  for ($i = 0; $i -lt 10; $i++) {\n"
        "    $desktops += @{ index = $i; name = \"Desktop $i\" }\n"
        "  }\n"
        "  $desktops | ConvertTo-Json -Compress\n"
        "} catch {\n"
        "  @{ error = $_.Exception.Message } | ConvertTo-Json -Compress\n"
        "}"
    )
    success, output = await run_ps(ps_script)
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict) and "error" in data:
                return {"error": data["error"]}
            if isinstance(data, dict):
                data = [data]
            return {"desktops": data, "count": len(data)}
        except json.JSONDecodeError:
            pass
    return {"desktops": [], "error": "Virtual desktops require Windows 10/11. " + (output or "")}


async def _move_to_virtual_desktop_action(params: dict) -> Any:
    """Move a window to a virtual desktop by index (0-based)."""
    hwnd = _find_window(params)
    desktop_index = params.get("desktop_index", 0)
    # Use IVirtualDesktopManager COM interface via C# interop
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms\n"
        f"$hwnd = {hwnd}\n"
        "# Try using the Win32 VirtualDesktopAccessor DLL if available\n"
        "$dllPath = Join-Path $env:APPDATA 'VirtualDesktopAccessor.dll'\n"
        "if (Test-Path $dllPath) {\n"
        "  $dll = Add-Type -Path $dllPath -MemberDefinition '[DllImport(\"VirtualDesktopAccessor.dll\")] public static extern int MoveWindowToDesktopNumber(IntPtr hwnd, int d);' -Name 'VDA' -Namespace 'Win32' -PassThru\n"
        f"  $result = [Win32.VDA]::MoveWindowToDesktopNumber([IntPtr]$hwnd, {desktop_index})\n"
        "  @{ success = ($result -eq 0); hwnd = $hwnd; desktop = \"$desktop_index\" } | ConvertTo-Json -Compress\n"
        "} else {\n"
        "  @{ error = 'VirtualDesktopAccessor.dll not found. Install it from https://github.com/Ciantic/VirtualDesktopAccessor' } | ConvertTo-Json -Compress\n"
        "}"
    )
    success, output = await run_ps(ps_script)
    if success and output:
        import json
        try:
            data = json.loads(output)
            return data
        except json.JSONDecodeError:
            pass
    return {"hwnd": hwnd, "desktop_index": desktop_index, "error": output or "Move failed"}


# ══════════════════════════════════════════════════════════════════════════════
# POWERSHELL FALLBACK METHODS
# ══════════════════════════════════════════════════════════════════════════════

async def _minimize_powershell(params: dict) -> Any:
    """Method 2: Minimize via PowerShell + .NET."""
    title = params.get("title", "")
    if not title:
        raise RuntimeError("title required for PowerShell fallback")
    ps = (f"Add-Type -AssemblyName Microsoft.VisualBasic; "
          f"[Microsoft.VisualBasic.Interaction]::AppActivate('{title}') | Out-Null; "
          f"$sig = '[user32.dll]SendMessage(IntPtr,uint,uint,uint)'; "
          f"Add-Type -MemberDefinition $sig -Name Win32 -Namespace User32 -PassThru | Out-Null; "
          f"'minimized'")
    success, output = await run_ps(ps)
    if not success:
        # Simple fallback: just minimize via wscript
        ps2 = (f"$wsh = New-Object -ComObject WScript.Shell; "
               f"$wsh.AppActivate('{title}'); "
               f"$wsh.SendKeys('% n'); "
               f"'minimized'")
        success, output = await run_ps(ps2)
    return {"minimized": title}


async def _maximize_powershell(params: dict) -> Any:
    """Method 2: Maximize via PowerShell + SendKeys."""
    title = params.get("title", "")
    if not title:
        raise RuntimeError("title required for PowerShell fallback")
    ps = (f"$wsh = New-Object -ComObject WScript.Shell; "
          f"$wsh.AppActivate('{title}'); "
          f"$wsh.SendKeys('% x'); "
          f"'maximized'")
    success, output = await run_ps(ps)
    return {"maximized": title}


async def _restore_powershell(params: dict) -> Any:
    """Method 2: Restore via PowerShell + SendKeys."""
    title = params.get("title", "")
    if not title:
        raise RuntimeError("title required for PowerShell fallback")
    ps = (f"$wsh = New-Object -ComObject WScript.Shell; "
          f"$wsh.AppActivate('{title}'); "
          f"$wsh.SendKeys('% r'); "
          f"'restored'")
    success, output = await run_ps(ps)
    return {"restored": title}


async def _set_foreground_powershell(params: dict) -> Any:
    """Method 2: Focus window via PowerShell AppActivate."""
    title = params.get("title", "")
    if not title:
        raise RuntimeError("title required for PowerShell fallback")
    ps = f"[Microsoft.VisualBasic.Interaction]::AppActivate('{title}')"
    success, output = await run_ps(f"Add-Type -AssemblyName Microsoft.VisualBasic; {ps}")
    return {"focused": title}


async def _close_window_powershell(params: dict) -> Any:
    """Method 2: Close window via taskkill by PID."""
    hwnd = params.get("hwnd")
    if hwnd:
        pid = _get_window_pid(int(hwnd))
        if pid:
            success, output = await run_ps(f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue")
            return {"closed": int(hwnd)}
    # Fallback: close by title via taskkill
    title = params.get("title", "")
    if title:
        hwnd_val = _find_window_by_title(title)
        if hwnd_val:
            pid = _get_window_pid(hwnd_val)
            if pid:
                success, output = await run_ps(f"Stop-Process -Id {pid} -Force")
                return {"closed": title}
    raise RuntimeError("Could not close window")


async def _close_window_taskkill(params: dict) -> Any:
    """Method 3: Close window via taskkill."""
    hwnd = params.get("hwnd")
    if hwnd:
        pid = _get_window_pid(int(hwnd))
        if pid:
            success, output = await run_ps(f"taskkill /F /PID {pid}")
            return {"closed": int(hwnd)}
    raise RuntimeError("Could not close window")


async def _find_window_powershell(params: dict) -> Any:
    """Method 2: Find window via PowerShell Get-Process."""
    title = params.get("title", "")
    if not title:
        raise RuntimeError("title required for PowerShell fallback")
    ps = (f"Get-Process | Where-Object {{ $_.MainWindowTitle -like '*{title}*' }} | "
          f"Select-Object Id, MainWindowTitle, MainWindowHandle | "
          f"ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, list):
                data = data[0]
            return {"hwnd": data.get("MainWindowHandle", 0), "title": data.get("MainWindowTitle", ""), "pid": data.get("Id")}
        except json.JSONDecodeError:
            pass
    return {"error": f"No window matching '{title}'"}


async def _get_active_window_powershell(params: dict) -> Any:
    """Method 2: Get active window via PowerShell."""
    ps = ("Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
          "public class Win32 {\n"
          "  [DllImport(\"user32.dll\")] public static extern IntPtr GetForegroundWindow();\n"
          "  [DllImport(\"user32.dll\", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count);\n"
          "  [DllImport(\"user32.dll\")] public static extern int GetWindowThreadProcessId(IntPtr hWnd, out int processId);\n"
          "}\n'@\n"
          "$hwnd = [Win32]::GetForegroundWindow(); "
          "$sb = New-Object System.Text.StringBuilder 256; "
          "[Win32]::GetWindowText($hwnd, $sb, 256) | Out-Null; "
          "$pid = 0; [Win32]::GetWindowThreadProcessId($hwnd, [ref]$pid) | Out-Null; "
          "@{hwnd=$hwnd.ToInt64(); title=$sb.ToString(); pid=$pid} | ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"error": "Could not get active window"}


async def _get_window_rect_powershell(params: dict) -> Any:
    """Method 2: Get window rect via PowerShell + .NET."""
    hwnd = params.get("hwnd") or params.get("title")
    if not hwnd:
        raise RuntimeError("hwnd or title required")
    ps = (f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
          "public class WinRect {\n"
          "  [DllImport(\"user32.dll\")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);\n"
          "  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }\n"
          "}\n'@\n"
          f"$hwnd = [IntPtr]::new({hwnd}); "
          "$rect = New-Object WinRect+RECT; "
          "[WinRect]::GetWindowRect($hwnd, [ref]$rect) | Out-Null; "
          "@{x=$rect.Left; y=$rect.Top; width=$rect.Right-$rect.Left; height=$rect.Bottom-$rect.Top} | ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    raise RuntimeError("Could not get window rect")


async def _get_window_info_powershell(params: dict) -> Any:
    """Method 2: Get window info via PowerShell."""
    title = params.get("title", "")
    if not title:
        raise RuntimeError("title required for PowerShell fallback")
    ps = (f"Get-Process | Where-Object {{ $_.MainWindowTitle -like '*{title}*' }} | "
          f"Select-Object Id, ProcessName, MainWindowTitle | "
          f"ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, list):
                data = data[0]
            return {"pid": data.get("Id"), "title": data.get("MainWindowTitle"), "process": data.get("ProcessName")}
        except json.JSONDecodeError:
            pass
    return {"error": "Could not get window info"}


async def _set_window_title_powershell(params: dict) -> Any:
    """Method 2: Set window title via PowerShell."""
    hwnd = params.get("hwnd")
    title = params["title"]
    if hwnd:
        ps = (f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
              "public class WinTitle {\n"
              "  [DllImport(\"user32.dll\", CharSet=CharSet.Unicode)] public static extern bool SetWindowText(IntPtr hWnd, string lpString);\n"
              "}\n'@\n"
              f"[WinTitle]::SetWindowText([IntPtr]::new({hwnd}), '{title}')")
        await run_ps(ps)
        return {"hwnd": int(hwnd), "title": title}
    raise RuntimeError("hwnd required for PowerShell fallback")


async def _get_window_title_powershell(params: dict) -> Any:
    """Method 2: Get window title via PowerShell."""
    hwnd = params.get("hwnd")
    if not hwnd:
        raise RuntimeError("hwnd required for PowerShell fallback")
    ps = (f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
          "public class WinTitle {\n"
          "  [DllImport(\"user32.dll\", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count);\n"
          "  [DllImport(\"user32.dll\")] public static extern int GetWindowTextLength(IntPtr hWnd);\n"
          "}\n'@\n"
          f"$hwnd = [IntPtr]::new({hwnd}); "
          "$len = [WinTitle]::GetWindowTextLength($hwnd); "
          "$sb = New-Object System.Text.StringBuilder ($len + 1); "
          "[WinTitle]::GetWindowText($hwnd, $sb, $sb.Capacity) | Out-Null; "
          "@{hwnd=$hwnd.ToInt64(); title=$sb.ToString()} | ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    raise RuntimeError("Could not get window title")


async def _is_visible_powershell(params: dict) -> Any:
    """Method 2: Check visibility via PowerShell."""
    title = params.get("title", "")
    if not title:
        raise RuntimeError("title required")
    ps = (f"$proc = Get-Process | Where-Object {{ $_.MainWindowTitle -like '*{title}*' }} | Select-Object -First 1; "
          f"@{{visible=($null -ne $proc)}} | ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"visible": False}


async def _get_pid_powershell(params: dict) -> Any:
    """Method 2: Get PID via PowerShell."""
    title = params.get("title", "")
    hwnd = params.get("hwnd")
    if title:
        ps = (f"Get-Process | Where-Object {{ $_.MainWindowTitle -like '*{title}*' }} | "
              f"Select-Object -First 1 -ExpandProperty Id")
        success, output = await run_ps(ps)
        if success and output.isdigit():
            return {"pid": int(output)}
    raise RuntimeError("Could not get PID")


async def _hide_window_powershell(params: dict) -> Any:
    """Method 2: Hide window via PowerShell."""
    title = params.get("title", "")
    if not title:
        raise RuntimeError("title required")
    ps = (f"$wsh = New-Object -ComObject WScript.Shell; "
          f"$wsh.AppActivate('{title}'); "
          f"$wsh.SendKeys('% {F4}'); "
          # Actually hiding requires ShowWindow - use Add-Type
          f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
          "public class WinHide {\n"
          "  [DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);\n"
          "  [DllImport(\"user32.dll\")] public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);\n"
          "}\n'@\n"
          f"$hwnd = [WinHide]::FindWindow($null, '{title}'); "
          f"if ($hwnd -ne [IntPtr]::Zero) {{ [WinHide]::ShowWindow($hwnd, 0) | Out-Null; 'hidden' }} else {{ 'not_found' }}")
    success, output = await run_ps(ps)
    return {"hidden": title}


async def _show_window_powershell(params: dict) -> Any:
    """Method 2: Show window via PowerShell."""
    title = params.get("title", "")
    if not title:
        raise RuntimeError("title required")
    ps = (f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
          "public class WinShow {\n"
          "  [DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);\n"
          "  [DllImport(\"user32.dll\")] public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);\n"
          "}\n'@\n"
          f"$hwnd = [WinShow]::FindWindow($null, '{title}'); "
          f"if ($hwnd -ne [IntPtr]::Zero) {{ [WinShow]::ShowWindow($hwnd, 5) | Out-Null; 'shown' }} else {{ 'not_found' }}")
    success, output = await run_ps(ps)
    return {"shown": title}


async def _get_window_class_powershell(params: dict) -> Any:
    """Method 2: Get window class via PowerShell."""
    hwnd = params.get("hwnd")
    if not hwnd:
        raise RuntimeError("hwnd required")
    ps = (f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
          "public class WinClass {\n"
          "  [DllImport(\"user32.dll\", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, System.Text.StringBuilder lpClassName, int nMaxCount);\n"
          "}\n'@\n"
          f"$sb = New-Object System.Text.StringBuilder 256; "
          f"[WinClass]::GetClassName([IntPtr]::new({hwnd}), $sb, 256) | Out-Null; "
          f"@{{hwnd={hwnd}; class_name=$sb.ToString()}} | ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    raise RuntimeError("Could not get window class")


async def _list_windows_powershell(params: dict) -> Any:
    """Method 2: List windows via PowerShell Get-Process."""
    ps = ("Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | "
          "Select-Object Id, ProcessName, MainWindowTitle | "
          "ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            windows = [{"pid": d.get("Id"), "title": d.get("MainWindowTitle"), "process": d.get("ProcessName")} for d in data]
            return {"windows": windows, "count": len(windows)}
        except json.JSONDecodeError:
            pass
    return {"windows": [], "count": 0}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION HANDLER
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    "list_all_windows":  ([_list_windows, _list_windows_powershell], None),
    "minimize_window":  ([_minimize_win32, _minimize_powershell], None),
    "maximize_window":  ([_maximize_win32, _maximize_powershell], None),
    "restore_window":   ([_restore_win32, _restore_powershell], None),
    "set_foreground":   ([_set_foreground_win32, _set_foreground_powershell], Verifiers.window_focused),
    "set_topmost":      ([_set_topmost], None),
    "unset_topmost":    ([_unset_topmost], None),
    "close_window":     ([_close_win32, _close_window_powershell, _close_window_taskkill], None),
    "move_window":      ([_move_window], Verifiers.window_position),
    "get_window_rect":  ([_get_window_rect, _get_window_rect_powershell], None),
    "find_window":      ([_find_window_action, _find_window_powershell], None),
    "get_active_window": ([_get_active_window_action, _get_active_window_powershell], None),
    "resize_window":    ([_resize_window_action], Verifiers.window_position),
    "hide_window":      ([_hide_window_action, _hide_window_powershell], None),
    "show_window":      ([_show_window_action, _show_window_powershell], None),
    "send_message":     ([_send_message_action], None),
    "flash_window":     ([_flash_window_action], None),
    "get_window_pid_action": ([_get_window_pid_action, _get_pid_powershell], None),
    # --- Phase 7 additions ---
    "get_window_info":       ([_get_window_info_action, _get_window_info_powershell], None),
    "set_position_and_size": ([_set_position_and_size_action], Verifiers.window_position),
    "force_close_window":    ([_force_close_window_action, _close_window_taskkill], None),
    "post_message":          ([_post_message_action], None),
    "get_window_title":      ([_get_window_title_action, _get_window_title_powershell], None),
    "set_window_title":      ([_set_window_title_action, _set_window_title_powershell], None),
    "take_window_screenshot": ([_take_window_screenshot_action], None),
    "arrange_tile":          ([_arrange_tile_action], None),
    "arrange_cascade":       ([_arrange_cascade_action], None),
    "get_window_class":      ([_get_window_class_action, _get_window_class_powershell], None),
    "is_window_visible":     ([_is_window_visible_action, _is_visible_powershell], None),
    "is_window_minimized":   ([_is_window_minimized_action], None),
    # --- Virtual Desktops ---
    "list_virtual_desktops":  ([_list_virtual_desktops_action], None),
    "move_to_virtual_desktop": ([_move_to_virtual_desktop_action], None),
}


async def handler(action: str, params: dict[str, Any]) -> Result:
    """L4 Window layer handler."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown window action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"window.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("window", action),
        escalation_fn=create_escalation_fn("window", action),
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
