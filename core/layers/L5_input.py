"""Layer 5: Input Simulation — Keyboard and Mouse via SendInput.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 7:

THE MOST RELIABLE METHOD: SendInput via ctypes (NOT pyautogui).
pyautogui uses deprecated keybd_event and can be blocked.

Text Typing Strategy:
  Short text (< 50 chars):  SendInput char by char with KEYEVENTF_UNICODE
  Long text  (>= 50 chars): Clipboard paste (copy text → focus window → Ctrl+V)
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.layers._utils import run_ps, find_window_by_title, create_escalation_fn, create_preflight_fn

import logging
logger = logging.getLogger("may.core.layers.L5_input")


# ── SendInput Structures ─────────────────────────────────────────────────────

INPUT_KEYBOARD = 1
INPUT_MOUSE    = 0
KEYEVENTF_KEYUP     = 0x0002
KEYEVENTF_UNICODE   = 0x0004
MOUSEEVENTF_MOVE       = 0x0001
MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP   = 0x0040
MOUSEEVENTF_WHEEL      = 0x0800
MOUSEEVENTF_ABSOLUTE   = 0x8000

VK_MAP = {
    "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    "space": 0x20, "backspace": 0x08, "delete": 0x2E,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "ctrl": 0x11, "alt": 0x12, "shift": 0x10,
    "win": 0x5B, "insert": 0x2D, "capslock": 0x14,
    "printscreen": 0x2C,
    # Media keys
    "play_pause": 0xB3, "playpause": 0xB3,
    "media_next": 0xB0, "next_track": 0xB0,
    "media_prev": 0xB1, "prev_track": 0xB1,
    "media_stop": 0xB2, "stop_media": 0xB2,
    "volume_up": 0xAF, "volume_down": 0xAE, "volume_mute": 0xAD,
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.wintypes.LONG), ("dy", ctypes.wintypes.LONG),
        ("mouseData", ctypes.wintypes.DWORD), ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.wintypes.ULONG)),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD), ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD), ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.wintypes.ULONG)),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.wintypes.DWORD), ("_input", _INPUT_UNION)]


def _send_input(inp: INPUT):
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def _send_key(vk_code: int, key_up: bool = False):
    flags = KEYEVENTF_KEYUP if key_up else 0
    inp = INPUT(type=INPUT_KEYBOARD,
                _input=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk_code, dwFlags=flags)))
    _send_input(inp)


def _tap_key(vk_code: int):
    _send_key(vk_code, key_up=False)
    _send_key(vk_code, key_up=True)


def _send_unicode_char(char: str):
    for ch in char:
        code = ord(ch)
        # Key down
        inp = INPUT(type=INPUT_KEYBOARD,
                    _input=_INPUT_UNION(ki=KEYBDINPUT(wScan=code, dwFlags=KEYEVENTF_UNICODE)))
        _send_input(inp)
        # Key up
        inp = INPUT(type=INPUT_KEYBOARD,
                    _input=_INPUT_UNION(ki=KEYBDINPUT(wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)))
        _send_input(inp)


# ══════════════════════════════════════════════════════════════════════════════
# WINDOW FOCUS HELPER (for type_text)
# ══════════════════════════════════════════════════════════════════════════════

# Window titles that belong to May itself (should never be typed into)
_MAY_WINDOW_TITLES = {"may", "tauri", "codebuff", "codebuff cli"}


async def _focus_window_for_typing(title: str) -> bool:
    """Focus a specific window by title before typing.

    Uses a multi-strategy approach:
    1. SetForegroundWindow with Alt key trick
    2. AttachThreadInput + SetForegroundWindow
    3. SetWindowPos(HWND_TOPMOST) toggle
    4. BringWindowToTop + SetForegroundWindow
    5. Falls back to _focus_recent_window_for_typing

    Returns True if a window was found and focused.
    """
    import asyncio as _aio
    from core.layers._utils import find_window_by_title

    # Poll for up to 3 seconds for slow apps (Notepad may need time to load)
    for attempt in range(15):
        hwnd = find_window_by_title(title)
        if hwnd:
            logger.info("Focusing window '%s' (hwnd=%s) for typing (attempt %d)", title, hwnd, attempt + 1)

            # Strategy 1: Direct SetForegroundWindow with retry
            for retry in range(3):
                result = ctypes.windll.user32.SetForegroundWindow(hwnd)
                if result:
                    await _aio.sleep(0.2)
                    logger.info("Focused '%s' via SetForegroundWindow", title)
                    return True
                logger.debug("SetForegroundWindow failed (attempt %d), trying Alt key trick...", retry + 1)
                # Alt key trick — brief Alt press unlocks SetForegroundWindow
                _tap_key(VK_MAP["alt"])
                await _aio.sleep(0.1)
                result = ctypes.windll.user32.SetForegroundWindow(hwnd)
                if result:
                    await _aio.sleep(0.2)
                    logger.info("Focused '%s' via Alt key trick", title)
                    return True

            # Strategy 2: AttachThreadInput — attach to foreground window's thread
            # This grants our thread the ability to call SetForegroundWindow successfully.
            try:
                fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
                fg_tid = ctypes.windll.user32.GetWindowThreadProcessId(fg_hwnd, None)
                our_tid = ctypes.windll.kernel32.GetCurrentThreadId()
                if fg_tid and our_tid and fg_tid != our_tid:
                    # Attach to the foreground thread, then detach — this gives us
                    # a brief window where SetForegroundWindow is allowed.
                    ctypes.windll.user32.AttachThreadInput(our_tid, fg_tid, True)
                    await _aio.sleep(0.05)
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    ctypes.windll.user32.AttachThreadInput(our_tid, fg_tid, False)
                    await _aio.sleep(0.2)
                    # Verify it worked
                    if ctypes.windll.user32.GetForegroundWindow() == hwnd:
                        logger.info("Focused '%s' via AttachThreadInput", title)
                        return True
            except Exception as e:
                logger.debug("AttachThreadInput failed: %s", e)

            # Strategy 3: SetWindowPos HWND_TOPMOST toggle — force window to top
            try:
                HWND_TOPMOST = -1
                HWND_NOTOPMOST = -2
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_SHOWWINDOW = 0x0040
                # Temporarily make topmost, then immediately un-topmost
                ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                await _aio.sleep(0.05)
                ctypes.windll.user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                await _aio.sleep(0.2)
                if ctypes.windll.user32.GetForegroundWindow() == hwnd:
                    logger.info("Focused '%s' via SetWindowPos TOPMOST toggle", title)
                    return True
            except Exception as e:
                logger.debug("SetWindowPos toggle failed: %s", e)

            # Strategy 4: BringWindowToTop + SetForegroundWindow
            ctypes.windll.user32.BringWindowToTop(hwnd)
            await _aio.sleep(0.05)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            await _aio.sleep(0.2)
            # Final check
            if ctypes.windll.user32.GetForegroundWindow() == hwnd:
                logger.info("Focused '%s' via BringWindowToTop", title)
                return True
            logger.info("Focused '%s' via best-effort (foreground check inconclusive)", title)
            return True  # Best effort — keystrokes might still land

        await _aio.sleep(0.2)

    # Window not found — fall back to most recent window heuristic
    logger.warning("Window '%s' not found after 3s, falling back to most recent window", title)
    return await _focus_recent_window_for_typing()


async def _focus_recent_window_for_typing() -> bool:
    """Find the most recently created visible window (excluding May) and focus it.

    This is called before type_text to ensure keystrokes go to the right window
    (e.g. Notepad after open_app launched it). Uses EnumWindows + psutil to find
    the most recently started process with a visible window.

    Polls up to 2 seconds (10 x 0.2s) for slow apps like Steam/Discord/Opera.
    Returns True if a window was focused.
    """
    import ctypes
    import ctypes.wintypes
    import asyncio as _aio

    def _enumerate_non_may_windows():
        """Enumerate visible top-level windows, excluding May's own."""
        windows = []

        def _enum_callback(hwnd, _):
            if not ctypes.windll.user32.IsWindowVisible(hwnd):
                return True
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            title_lower = title.lower()
            # Skip May's own windows
            if any(mt in title_lower for mt in _MAY_WINDOW_TITLES):
                return True
            # Get PID
            pid = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            windows.append((hwnd, pid.value, title))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM,
        )
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_callback), 0)
        return windows

    def _focus_best_window(windows):
        """Focus the most recently started process's window from the list."""
        if not windows:
            return False
        try:
            import psutil
            pid_to_start = {}
            for hwnd, pid, title in windows:
                if pid in pid_to_start:
                    continue
                try:
                    p = psutil.Process(pid)
                    pid_to_start[pid] = (p.create_time(), hwnd, title)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if pid_to_start:
                _time, best_hwnd, best_title = max(pid_to_start.values(), key=lambda x: x[0])
                logger.info("Focusing recent window: '%s' (hwnd=%s) for typing", best_title, best_hwnd)
                ctypes.windll.user32.SetForegroundWindow(best_hwnd)
                return True
        except ImportError:
            pass
        # Fallback: focus the frontmost non-May window (EnumWindows returns Z-order, front-to-back)
        front_hwnd, _, front_title = windows[0]
        logger.info("Focusing frontmost window: '%s' (hwnd=%s) for typing", front_title, front_hwnd)
        ctypes.windll.user32.SetForegroundWindow(front_hwnd)
        return True

    # Poll for up to 2 seconds for slow apps (Steam, Discord, Opera)
    for attempt in range(10):
        await _aio.sleep(0.2)
        windows = _enumerate_non_may_windows()
        if windows and _focus_best_window(windows):
            return

    # Last resort: just try whatever windows exist
    windows = _enumerate_non_may_windows()
    _focus_best_window(windows)


# ══════════════════════════════════════════════════════════════════════════════
# KEYBOARD ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

async def _press_key(params: dict) -> Any:
    """Press a single key."""
    key = params["key"].lower().strip()
    vk = VK_MAP.get(key)
    if vk is None and len(key) == 1:
        vk = ord(key.upper())
    if vk is None:
        raise RuntimeError(f"Unknown key: '{key}'")
    _tap_key(vk)
    return {"pressed": key}


async def _type_text_unicode(params: dict) -> Any:
    """Type text using SendInput char by char (short text)."""
    text = params.get("text", "")
    if not text:
        raise RuntimeError("No text provided")
    # Focus target window: specific title if provided, else most recent
    window_title = params.get("window_title", "")
    focused = False
    if window_title:
        focused = await _focus_window_for_typing(window_title)
    else:
        focused = await _focus_recent_window_for_typing()
    if not focused:
        logger.warning("Could not focus window for typing — keystrokes may go to wrong window")
    for ch in text:
        _send_unicode_char(ch)
    return {"typed": len(text)}


CF_UNICODETEXT = 13  # Win32 clipboard format for Unicode text

# ── Set proper ctypes return types for 64-bit pointer safety ──────────────
# Without these, pointer return values get truncated from 8→4 bytes on x64,
# causing access violations in GlobalAlloc/GlobalLock/RtlMoveMemory.
ctypes.windll.kernel32.GlobalAlloc.restype = ctypes.c_void_p
ctypes.windll.kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
ctypes.windll.kernel32.GlobalLock.restype = ctypes.c_void_p
ctypes.windll.kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
ctypes.windll.kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
ctypes.windll.kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
ctypes.windll.kernel32.GlobalFree.restype = ctypes.c_void_p
ctypes.windll.kernel32.RtlMoveMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
ctypes.windll.user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
ctypes.windll.user32.SetClipboardData.restype = ctypes.c_void_p


async def _type_text_clipboard(params: dict) -> Any:
    """Type text via clipboard paste with multi-strategy paste and retry.

    Strategies (in order):
    1. Ctrl+V (works in most apps)
    2. Shift+Insert (works when Ctrl+V is intercepted)
    3. PowerShell SendKeys (fallback for stubborn apps)
    """
    import asyncio as _aio
    text = params.get("text", "")
    if not text:
        raise RuntimeError("No text provided")

    # Focus target window: specific title if provided, else most recent
    window_title = params.get("window_title", "")
    focused = False
    if window_title:
        focused = await _focus_window_for_typing(window_title)
    else:
        focused = await _focus_recent_window_for_typing()

    if not focused:
        logger.warning("Could not focus any window for typing — proceeding anyway")

    # ── Step 1: Set clipboard content ──
    import ctypes as _ct
    if not _ct.windll.user32.OpenClipboard(0):
        logger.warning("Failed to open clipboard, retrying after 100ms...")
        await _aio.sleep(0.1)
        if not _ct.windll.user32.OpenClipboard(0):
            raise RuntimeError("Cannot open clipboard after retry")
    try:
        _ct.windll.user32.EmptyClipboard()
        data = text.encode("utf-16-le") + b"\x00\x00"
        h = _ct.windll.kernel32.GlobalAlloc(0x0042, len(data))
        if not h:
            raise RuntimeError("GlobalAlloc returned NULL")
        p = _ct.windll.kernel32.GlobalLock(h)
        if not p:
            _ct.windll.kernel32.GlobalFree(h)
            raise RuntimeError("GlobalLock returned NULL")
        _ct.windll.kernel32.RtlMoveMemory(p, data, len(data))
        _ct.windll.kernel32.GlobalUnlock(h)
        _ct.windll.user32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        _ct.windll.user32.CloseClipboard()

    # Brief wait for clipboard to settle
    await _aio.sleep(0.1)

    # ── Step 2: Try paste strategies ──
    _paste_strategies = [
        ("ctrl+v", lambda: (
            _send_key(VK_MAP["ctrl"], key_up=False),
            _send_key(VK_MAP["v"], key_up=False),
            _send_key(VK_MAP["v"], key_up=True),
            _send_key(VK_MAP["ctrl"], key_up=True),
        )),
        ("shift+insert", lambda: (
            _send_key(VK_MAP["shift"], key_up=False),
            _send_key(VK_MAP["insert"], key_up=False),
            _send_key(VK_MAP["insert"], key_up=True),
            _send_key(VK_MAP["shift"], key_up=True),
        )),
    ]

    for strategy_name, paste_fn in _paste_strategies:
        try:
            paste_fn()
            await _aio.sleep(0.2)  # 200ms to ensure paste completes in slow apps
            logger.info("Pasted %d chars via %s", len(text), strategy_name)
            return {"typed": len(text), "method": f"clipboard_{strategy_name.replace('+', '_')}"}
        except Exception as e:
            logger.warning("Paste via %s failed: %s", strategy_name, e)
            continue

    # ── Step 3: PowerShell SendKeys fallback ──
    try:
        ps_script = (
            "$wsh = New-Object -ComObject WScript.Shell; "
            "$wsh.SendKeys('^(v)')"  # Ctrl+V via SendKeys
        )
        success, output = await run_ps(ps_script)
        if success:
            await _aio.sleep(0.2)
            logger.info("Pasted %d chars via PowerShell SendKeys", len(text))
            return {"typed": len(text), "method": "clipboard_powershell"}
    except Exception as e:
        logger.warning("PowerShell SendKeys fallback failed: %s", e)

    # ── All strategies failed — return what we have ──
    logger.error("All paste strategies failed for %d chars", len(text))
    return {"typed": len(text), "method": "clipboard_failed"}


async def _hotkey(params: dict) -> Any:
    """Send a key combination (e.g. ctrl+c, alt+tab)."""
    combo = params.get("combo", "").lower().strip()
    parts = [p.strip() for p in combo.split("+")]
    vk_codes = []
    for part in parts:
        vk = VK_MAP.get(part)
        if vk is None and len(part) == 1:
            vk = ord(part.upper())
        if vk is None:
            raise RuntimeError(f"Unknown key in combo: '{part}'")
        vk_codes.append(vk)
    # Press all modifier keys first
    for vk in vk_codes:
        _send_key(vk, key_up=False)
    # Release in reverse order
    for vk in reversed(vk_codes):
        _send_key(vk, key_up=True)
    return {"hotkey": combo}


# ══════════════════════════════════════════════════════════════════════════════
# MOUSE ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

async def _mouse_move(params: dict) -> Any:
    """Move mouse to absolute screen coordinates."""
    x, y = params["x"], params["y"]
    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)
    nx = int(x * 65535 / screen_w)
    ny = int(y * 65535 / screen_h)
    flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
    inp = INPUT(type=INPUT_MOUSE,
                _input=_INPUT_UNION(mi=MOUSEINPUT(dx=nx, dy=ny, dwFlags=flags)))
    _send_input(inp)
    return {"moved": {"x": x, "y": y}}


async def _left_click(params: dict) -> Any:
    """Left click at coordinates."""
    x, y = params.get("x", 0), params.get("y", 0)
    await _mouse_move({"x": x, "y": y})
    inp = INPUT(type=INPUT_MOUSE, _input=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_LEFTDOWN)))
    _send_input(inp)
    inp = INPUT(type=INPUT_MOUSE, _input=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_LEFTUP)))
    _send_input(inp)
    return {"clicked": {"x": x, "y": y}}


async def _right_click(params: dict) -> Any:
    """Right click at coordinates."""
    x, y = params.get("x", 0), params.get("y", 0)
    await _mouse_move({"x": x, "y": y})
    inp = INPUT(type=INPUT_MOUSE, _input=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_RIGHTDOWN)))
    _send_input(inp)
    inp = INPUT(type=INPUT_MOUSE, _input=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_RIGHTUP)))
    _send_input(inp)
    return {"clicked": {"x": x, "y": y}}


async def _double_click(params: dict) -> Any:
    """Double click at coordinates."""
    import asyncio as _aio
    await _left_click(params)
    await _aio.sleep(0.05)
    await _left_click(params)
    return {"double_clicked": {"x": params.get("x", 0), "y": params.get("y", 0)}}


async def _scroll(params: dict) -> Any:
    """Scroll mouse wheel."""
    clicks = params.get("clicks", 3)
    delta = clicks * 120
    inp = INPUT(type=INPUT_MOUSE, _input=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_WHEEL, mouseData=delta)))
    _send_input(inp)
    return {"scrolled": clicks}


# ══════════════════════════════════════════════════════════════════════════════
# CLIPBOARD
# ══════════════════════════════════════════════════════════════════════════════

async def _set_clipboard(params: dict) -> Any:
    """Set clipboard text."""
    text = params.get("text", "")
    success, output = await run_ps(
        f"[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("
        f"'{__import__('base64').b64encode(text.encode()).decode()}')) | Set-Clipboard"
    )
    return {"clipboard_set": len(text)}


async def _get_clipboard(params: dict) -> Any:
    """Get clipboard text."""
    success, output = await run_ps("Get-Clipboard")
    return {"text": output if success else ""}


# ══════════════════════════════════════════════════════════════════════════════
# RELEASE KEY
# ══════════════════════════════════════════════════════════════════════════════

async def _release_key_action(params: dict) -> Any:
    """Release a held key."""
    key = params["key"].lower().strip()
    vk = VK_MAP.get(key)
    if vk is None and len(key) == 1:
        vk = ord(key.upper())
    if vk is None:
        raise RuntimeError(f"Unknown key: '{key}'")
    _send_key(vk, key_up=True)
    return {"released": key}


# ══════════════════════════════════════════════════════════════════════════════
# MOUSE DOWN / UP
# ══════════════════════════════════════════════════════════════════════════════

async def _mouse_down_action(params: dict) -> Any:
    """Press and hold a mouse button."""
    button = params.get("button", "left")
    flag_map = {"left": MOUSEEVENTF_LEFTDOWN, "right": MOUSEEVENTF_RIGHTDOWN, "middle": MOUSEEVENTF_MIDDLEDOWN}
    flag = flag_map.get(button, MOUSEEVENTF_LEFTDOWN)
    inp = INPUT(type=INPUT_MOUSE, _input=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=flag)))
    _send_input(inp)
    return {"mouse_down": button}


async def _mouse_up_action(params: dict) -> Any:
    """Release a mouse button."""
    button = params.get("button", "left")
    flag_map = {"left": MOUSEEVENTF_LEFTUP, "right": MOUSEEVENTF_RIGHTUP, "middle": MOUSEEVENTF_MIDDLEUP}
    flag = flag_map.get(button, MOUSEEVENTF_LEFTUP)
    inp = INPUT(type=INPUT_MOUSE, _input=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=flag)))
    _send_input(inp)
    return {"mouse_up": button}


# ══════════════════════════════════════════════════════════════════════════════
# DRAG AND DROP
# ══════════════════════════════════════════════════════════════════════════════

async def _drag_and_drop_action(params: dict) -> Any:
    """Drag from (x1,y1) to (x2,y2)."""
    import asyncio as _aio
    x1, y1 = params["x1"], params["y1"]
    x2, y2 = params["x2"], params["y2"]
    await _mouse_move({"x": x1, "y": y1})
    await _mouse_down_action({"button": "left"})
    await _aio.sleep(0.1)
    await _mouse_move({"x": x2, "y": y2})
    await _aio.sleep(0.1)
    await _mouse_up_action({"button": "left"})
    return {"dragged": {"from": {"x": x1, "y": y1}, "to": {"x": x2, "y": y2}}}


# ══════════════════════════════════════════════════════════════════════════════
# GET KEY STATE
# ══════════════════════════════════════════════════════════════════════════════

async def _get_key_state_action(params: dict) -> Any:
    """Check if a key is currently pressed."""
    key = params["key"].lower().strip()
    vk = VK_MAP.get(key)
    if vk is None and len(key) == 1:
        vk = ord(key.upper())
    if vk is None:
        raise RuntimeError(f"Unknown key: '{key}'")
    state = ctypes.windll.user32.GetKeyState(vk)
    pressed = bool(state & 0x8000)
    return {"key": key, "pressed": pressed}


# ══════════════════════════════════════════════════════════════════════════════
# GET CURSOR POSITION
# ══════════════════════════════════════════════════════════════════════════════

async def _get_cursor_position_action(params: dict) -> Any:
    """Get current mouse cursor position."""
    point = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return {"x": point.x, "y": point.y}


# ══════════════════════════════════════════════════════════════════════════════
# TAP KEY (convenience: press + release)
# ══════════════════════════════════════════════════════════════════════════════

async def _tap_key_action(params: dict) -> Any:
    """Quick press and release of a key."""
    key = params["key"].lower().strip()
    vk = VK_MAP.get(key)
    if vk is None and len(key) == 1:
        vk = ord(key.upper())
    if vk is None:
        raise RuntimeError(f"Unknown key: '{key}'")
    _tap_key(vk)
    return {"tapped": key}


# ══════════════════════════════════════════════════════════════════════════════
# HOLD KEY (press, wait, release)
# ══════════════════════════════════════════════════════════════════════════════

async def _hold_key_action(params: dict) -> Any:
    """Hold a key for a specified duration."""
    import asyncio as _aio
    key = params["key"].lower().strip()
    duration = params.get("duration", 0.5)
    vk = VK_MAP.get(key)
    if vk is None and len(key) == 1:
        vk = ord(key.upper())
    if vk is None:
        raise RuntimeError(f"Unknown key: '{key}'")
    _send_key(vk, key_up=False)
    await _aio.sleep(duration)
    _send_key(vk, key_up=True)
    return {"held": key, "duration": duration}


# ══════════════════════════════════════════════════════════════════════════════
# TYPE TEXT FAST (always clipboard-based for speed)
# ══════════════════════════════════════════════════════════════════════════════

async def _type_text_fast_action(params: dict) -> Any:
    """Type text using clipboard paste (fast, handles any length/Unicode)."""
    text = params.get("text", "")
    if not text:
        raise RuntimeError("No text provided")
    return await _type_text_clipboard(params)


# ══════════════════════════════════════════════════════════════════════════════
# MIDDLE CLICK
# ══════════════════════════════════════════════════════════════════════════════

async def _middle_click_action(params: dict) -> Any:
    """Middle mouse button click."""
    x, y = params.get("x", 0), params.get("y", 0)
    await _mouse_move({"x": x, "y": y})
    inp = INPUT(type=INPUT_MOUSE, _input=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_MIDDLEDOWN)))
    _send_input(inp)
    inp = INPUT(type=INPUT_MOUSE, _input=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_MIDDLEUP)))
    _send_input(inp)
    return {"middle_clicked": {"x": x, "y": y}}


# ══════════════════════════════════════════════════════════════════════════════
# SCROLL UP / DOWN (separate from generic scroll)
# ══════════════════════════════════════════════════════════════════════════════

async def _scroll_up_action(params: dict) -> Any:
    """Scroll wheel up."""
    clicks = params.get("clicks", 3)
    delta = clicks * 120
    inp = INPUT(type=INPUT_MOUSE, _input=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_WHEEL, mouseData=delta)))
    _send_input(inp)
    return {"scrolled_up": clicks}


async def _scroll_down_action(params: dict) -> Any:
    """Scroll wheel down."""
    clicks = params.get("clicks", 3)
    delta = -(clicks * 120)
    inp = INPUT(type=INPUT_MOUSE, _input=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_WHEEL, mouseData=delta)))
    _send_input(inp)
    return {"scrolled_down": clicks}


# ══════════════════════════════════════════════════════════════════════════════
# SCREENSHOT (full screen + region)
# ══════════════════════════════════════════════════════════════════════════════

async def _screenshot_full_action(params: dict) -> Any:
    """Capture the full screen to file."""
    from PIL import ImageGrab
    output = params.get("output", "screenshot_full.png")
    img = ImageGrab.grab()
    img.save(output)
    return {"saved": output, "width": img.width, "height": img.height}


async def _screenshot_region_action(params: dict) -> Any:
    """Capture a screen region to file."""
    from PIL import ImageGrab
    x1 = params.get("x", 0)
    y1 = params.get("y", 0)
    x2 = params.get("x2", x1 + 800)
    y2 = params.get("y2", y1 + 600)
    output = params.get("output", "screenshot_region.png")
    img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
    img.save(output)
    return {"saved": output, "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}}


# ══════════════════════════════════════════════════════════════════════════════
# SCREENSHOT WINDOW (capture a specific window by title)
# ══════════════════════════════════════════════════════════════════════════════

async def _screenshot_window_action(params: dict) -> Any:
    """Capture a specific window to file by title or hwnd."""
    import ctypes
    import ctypes.wintypes
    from PIL import ImageGrab

    title = params.get("title", "")
    hwnd_val = params.get("hwnd")
    output = params.get("output", "screenshot_window.png")

    if hwnd_val:
        hwnd = int(hwnd_val)
    elif title:
        hwnd = find_window_by_title(title)
        if not hwnd:
            raise RuntimeError(f"No window matching '{title}'")
    else:
        # Active window
        hwnd = ctypes.windll.user32.GetForegroundWindow()

    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    x, y, w, h = rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    img.save(output)
    return {"saved": output, "hwnd": hwnd, "width": w, "height": h}


# ══════════════════════════════════════════════════════════════════════════════
# POWERSHELL / SENDKEYS FALLBACK METHODS
# ══════════════════════════════════════════════════════════════════════════════

async def _press_key_powershell(params: dict) -> Any:
    """Method 2: Press key via PowerShell SendKeys."""
    key = params["key"].lower().strip()
    sendkeys_map = {"enter": "{ENTER}", "tab": "{TAB}", "esc": "{ESC}",
                    "escape": "{ESC}", "space": " ", "backspace": "{BACKSPACE}",
                    "delete": "{DELETE}", "up": "{UP}", "down": "{DOWN}",
                    "left": "{LEFT}", "right": "{RIGHT}", "home": "{HOME}",
                    "end": "{END}", "pageup": "{PGUP}", "pagedown": "{PGDN}",
                    "f1": "{F1}", "f2": "{F2}", "f3": "{F3}", "f4": "{F4}",
                    "f5": "{F5}", "f6": "{F6}", "f7": "{F7}", "f8": "{F8}",
                    "f9": "{F9}", "f10": "{F10}", "f11": "{F11}", "f12": "{F12}",
                    "insert": "{INS}", "printscreen": "{PRTSC}", "capslock": "{CAPSLOCK}"}
    sk = sendkeys_map.get(key, key.upper())
    ps = f"$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys('{sk}')"
    success, output = await run_ps(ps)
    return {"pressed": key}


async def _hotkey_powershell(params: dict) -> Any:
    """Method 2: Hotkey via PowerShell SendKeys."""
    combo = params.get("combo", "").lower().strip()
    parts = [p.strip() for p in combo.split("+")]
    # Build SendKeys combo string
    modifiers = {"ctrl": "^", "alt": "%", "shift": "+"}
    sk_combo = ""
    for part in parts:
        if part in modifiers:
            sk_combo += modifiers[part]
        elif len(part) == 1:
            sk_combo += part.upper()
        else:
            sk_combo += part.upper()
    ps = f"$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys('{sk_combo}')"
    success, output = await run_ps(ps)
    return {"hotkey": combo}


async def _left_click_powershell(params: dict) -> Any:
    """Method 2: Click via PowerShell + mouse_event."""
    x, y = params.get("x", 0), params.get("y", 0)
    # Use PowerShell Add-Type for mouse_event
    ps = (f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
          "public class Mouse {{ \n"
          "  [DllImport(\"user32.dll\")] public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, IntPtr dwExtraInfo);\n"
          "  [DllImport(\"user32.dll\")] public static extern bool SetCursorPos(int X, int Y);\n"
          "}}\n'@\n"
          f"[Mouse]::SetCursorPos({x}, {y}); Start-Sleep -Milliseconds 50; "
          f"[Mouse]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero); "
          f"Start-Sleep -Milliseconds 50; "
          f"[Mouse]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero); "
          f"'clicked'")
    success, output = await run_ps(ps)
    return {"clicked": {"x": x, "y": y}}


async def _right_click_powershell(params: dict) -> Any:
    """Method 2: Right click via PowerShell + mouse_event."""
    x, y = params.get("x", 0), params.get("y", 0)
    ps = (f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
          "public class Mouse {{ \n"
          "  [DllImport(\"user32.dll\")] public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, IntPtr dwExtraInfo);\n"
          "  [DllImport(\"user32.dll\")] public static extern bool SetCursorPos(int X, int Y);\n"
          "}}\n'@\n"
          f"[Mouse]::SetCursorPos({x}, {y}); Start-Sleep -Milliseconds 50; "
          f"[Mouse]::mouse_event(0x0008, 0, 0, 0, [IntPtr]::Zero); "
          f"Start-Sleep -Milliseconds 50; "
          f"[Mouse]::mouse_event(0x0010, 0, 0, 0, [IntPtr]::Zero); "
          f"'clicked'")
    success, output = await run_ps(ps)
    return {"clicked": {"x": x, "y": y}}


async def _scroll_powershell(params: dict) -> Any:
    """Method 2: Scroll via PowerShell + mouse_event."""
    clicks = params.get("clicks", 3)
    delta = clicks * 120
    ps = (f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
          "public class Mouse {{ \n"
          "  [DllImport(\"user32.dll\")] public static extern void mouse_event(uint dwFlags, int dx, int dy, int dwData, IntPtr dwExtraInfo);\n"
          "}}\n'@\n"
          f"[Mouse]::mouse_event(0x0800, 0, 0, {delta}, [IntPtr]::Zero); "
          f"'scrolled'")
    success, output = await run_ps(ps)
    return {"scrolled": clicks}


async def _get_cursor_pos_powershell(params: dict) -> Any:
    """Method 2: Get cursor position via PowerShell."""
    ps = ("Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
          "public class MousePos {\n"
          "  [DllImport(\"user32.dll\")] public static extern bool GetCursorPos(out POINT lpPoint);\n"
          "  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }\n"
          "}\n'@\n"
          "$pt = New-Object MousePos+POINT; "
          "[MousePos]::GetCursorPos([ref]$pt) | Out-Null; "
          "@{x=$pt.X; y=$pt.Y} | ConvertTo-Json -Compress")
    success, output = await run_ps(ps)
    if success and output:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"x": 0, "y": 0}


async def _set_clipboard_powershell(params: dict) -> Any:
    """Method 2: Set clipboard via PowerShell Set-Clipboard."""
    text = params.get("text", "")
    # Escape for PowerShell
    escaped = text.replace("'", "''").replace("`", "``")
    success, output = await run_ps(f"'{escaped}' | Set-Clipboard")
    if not success:
        # Fallback: use clip.exe
        import subprocess
        proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE)
        proc.communicate(text.encode("utf-16-le"))
    return {"clipboard_set": len(text)}


async def _get_clipboard_powershell(params: dict) -> Any:
    """Method 2: Get clipboard via PowerShell Get-Clipboard."""
    success, output = await run_ps("Get-Clipboard -Format Text -Raw")
    return {"text": output if success else ""}


async def _double_click_powershell(params: dict) -> Any:
    """Method 2: Double click via PowerShell + mouse_event."""
    x, y = params.get("x", 0), params.get("y", 0)
    ps = (f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\n"
          "public class Mouse {{ \n"
          "  [DllImport(\"user32.dll\")] public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, IntPtr dwExtraInfo);\n"
          "  [DllImport(\"user32.dll\")] public static extern bool SetCursorPos(int X, int Y);\n"
          "}}\n'@\n"
          f"[Mouse]::SetCursorPos({x}, {y}); Start-Sleep -Milliseconds 30; "
          f"[Mouse]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero); "
          f"[Mouse]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero); "
          f"Start-Sleep -Milliseconds 30; "
          f"[Mouse]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero); "
          f"[Mouse]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero); "
          f"'double_clicked'")
    success, output = await run_ps(ps)
    return {"double_clicked": {"x": x, "y": y}}


async def _screenshot_full_powershell(params: dict) -> Any:
    """Method 2: Screenshot via PowerShell."""
    output_path = params.get("output", "screenshot_full.png")
    ps = (f"Add-Type -AssemblyName System.Windows.Forms; "
          f"Add-Type -AssemblyName System.Drawing; "
          f"$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
          f"$bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height); "
          f"$g = [System.Drawing.Graphics]::FromImage($bmp); "
          f"$g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size); "
          f"$bmp.Save('{output_path}'); "
          f"'saved'")
    success, output = await run_ps(ps)
    return {"saved": output_path}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION HANDLER
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    "press_key":       ([_press_key, _press_key_powershell], None),
    "type_text":       ([_type_text_unicode, _type_text_clipboard], None),
    "hotkey":          ([_hotkey, _hotkey_powershell], None),
    "mouse_move":      ([_mouse_move], None),
    "left_click":      ([_left_click, _left_click_powershell], None),
    "right_click":     ([_right_click, _right_click_powershell], None),
    "double_click":    ([_double_click, _double_click_powershell], None),
    "scroll":          ([_scroll, _scroll_powershell], None),
    "set_clipboard":   ([_set_clipboard, _set_clipboard_powershell], None),
    "get_clipboard":   ([_get_clipboard, _get_clipboard_powershell], None),
    "release_key":     ([_release_key_action], None),
    "mouse_down":      ([_mouse_down_action], None),
    "mouse_up":        ([_mouse_up_action], None),
    "drag_and_drop":   ([_drag_and_drop_action], None),
    "get_key_state":   ([_get_key_state_action], None),
    "get_cursor_position": ([_get_cursor_position_action, _get_cursor_pos_powershell], None),
    # --- Phase 7 additions ---
    "tap_key":          ([_tap_key_action, _press_key_powershell], None),
    "hold_key":         ([_hold_key_action], None),
    "type_text_fast":   ([_type_text_fast_action, _type_text_clipboard], None),
    "middle_click":     ([_middle_click_action], None),
    "scroll_up":        ([_scroll_up_action, _scroll_powershell], None),
    "scroll_down":      ([_scroll_down_action, _scroll_powershell], None),
    "screenshot_full":  ([_screenshot_full_action, _screenshot_full_powershell], None),
    "screenshot_region": ([_screenshot_region_action], None),
    "screenshot_window": ([_screenshot_window_action], None),
}


async def handler(action: str, params: dict[str, Any]) -> Result:
    """L5 Input layer handler."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown input action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"input.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("input", action),
        escalation_fn=create_escalation_fn("input", action),
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
