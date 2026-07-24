# MAY AI — Complete System Architecture
### The definitive reference for building May from current state to fully working system

---

## DESIGN PHILOSOPHY

One process. No daemons. No IPC overhead.
All intelligence (LLM, voice, memory) and all control (layers, fallbacks, verifier)
live inside a single FastAPI process. The JARVIS control patterns are imported as a
Python package, not called over a socket.

Reliability comes from fallback chains, not from architectural complexity.

---

## FOLDER STRUCTURE (Complete)

```
C:\AI\may\
│
├── knowledge.md                        # Session state tracker (keep updated)
├── package.json                        # Tauri/Vite frontend config
├── vite.config.ts
│
├── src-tauri/                          # Tauri Rust layer (minimal, don't touch much)
│   ├── tauri.conf.json
│   └── src/main.rs
│
├── src/                                # React frontend
│   ├── App.tsx                         # Main app, voice toggle, message handler
│   ├── config.ts                       # BACKEND_URL constant
│   ├── components/
│   │   ├── ChatPanel.tsx               # Message display
│   │   ├── VoiceMonitor.tsx            # Mic frequency bars + countdown
│   │   ├── Avatar.tsx                  # Glass sphere animation
│   │   └── SettingsModal.tsx           # API keys + STT model selector
│   └── hooks/
│       ├── useMicMonitor.ts            # getUserMedia + MediaRecorder
│       └── useSpeechRecognition.ts     # STT flag + browser fallback (dead)
│
└── backend/                            # ← EVERYTHING IMPORTANT IS HERE
    │
    ├── main.py                         # FastAPI entry point (start here)
    ├── config.py                       # All shared constants (ports, paths, etc.)
    ├── startup.py                      # Admin check + Task Scheduler registration
    ├── tray.py                         # System tray icon (pystray)
    │
    ├── control/                        # ← PC CONTROL ENGINE
    │   ├── __init__.py
    │   ├── bus.py                      # Command + Result dataclasses
    │   ├── privilege.py                # Admin check + Win32 token privileges
    │   ├── router.py                   # Command → Layer dispatcher
    │   ├── fallback.py                 # Fallback chain executor
    │   ├── verifier.py                 # Post-action confirmation
    │   ├── safety.py                   # Destructive command guard
    │   └── layers/
    │       ├── __init__.py
    │       ├── L1_filesystem.py        # Files, folders, drives, permissions
    │       ├── L2_process.py           # Processes: launch, kill, suspend
    │       ├── L3_application.py       # Installed apps: open, close, automate
    │       ├── L4_window.py            # Windows: move, resize, focus, z-order
    │       ├── L5_input.py             # Keyboard + Mouse simulation
    │       ├── L6_registry.py          # Windows Registry: read, write, delete
    │       ├── L7_services.py          # Windows Services + Task Scheduler
    │       ├── L8_system.py            # Volume, brightness, power, network, audio
    │       └── L9_browser.py           # Browser automation (Playwright)
    │
    ├── llm/                            # ← AI BRAIN
    │   ├── __init__.py
    │   ├── provider.py                 # Ollama, OpenAI, Anthropic, Gemini routing
    │   ├── intent.py                   # is_pc_command() + extract_command_json()
    │   ├── tools.py                    # Native tool call definitions (for cloud LLMs)
    │   └── system_prompt.py            # May's personality + tool instructions
    │
    ├── voice/                          # ← VOICE I/O
    │   ├── __init__.py
    │   ├── stt.py                      # faster-whisper (GPU auto-detect → CPU)
    │   └── tts.py                      # TTS (edge-tts for offline, pyttsx3 fallback)
    │
    └── memory/                         # ← LONG-TERM MEMORY
        ├── __init__.py
        ├── episodic.py                 # LanceDB — semantic/vector search
        └── structured.py              # SQLite — facts, preferences, reminders
```

---

## ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         WINDOWS STARTUP                                  │
│   Task Scheduler (ONLOGON, Run as Admin) → launches main.py              │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────┐
│                     main.py  (FastAPI Process)                           │
│                                                                          │
│  startup.py ──→ ensure_admin() + enable_privileges() + register_tray()  │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                   REQUEST PIPELINE                               │    │
│  │                                                                  │    │
│  │  WebSocket / HTTP                                                │    │
│  │       ↓                                                          │    │
│  │  [Voice] ──→ voice/stt.py ──→ text                              │    │
│  │  [Text]  ──────────────────→ text                               │    │
│  │                   ↓                                              │    │
│  │           llm/intent.py                                         │    │
│  │          is_pc_command(text)?                                   │    │
│  │             ↙            ↘                                      │    │
│  │         YES               NO                                    │    │
│  │          ↓                 ↓                                    │    │
│  │  control/router.py    llm/provider.py                           │    │
│  │          ↓             (Ollama/OpenAI/etc.)                     │    │
│  │  Layer (L1–L9)             ↓                                    │    │
│  │          ↓           memory lookup                              │    │
│  │  fallback.py               ↓                                    │    │
│  │  (try 5–7 methods)    response text                             │    │
│  │          ↓                 ↓                                    │    │
│  │  verifier.py         voice/tts.py (if voice mode)              │    │
│  │          ↓                 ↓                                    │    │
│  │  Result ───────────────→ WebSocket response to frontend        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
          ┌───────────────────────┼────────────────────┐
          ↓                       ↓                    ↓
    ┌───────────┐         ┌──────────────┐     ┌──────────────┐
    │ WINDOWS   │         │ TAURI WINDOW │     │ SYSTEM TRAY  │
    │ OS / APIs │         │ (React UI)   │     │ (pystray)    │
    └───────────┘         └──────────────┘     └──────────────┘
```

---

## MODULE REFERENCE

### `main.py` — FastAPI Entry Point

The first file to run. Does five things in order:

```python
# main.py
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from startup import ensure_admin, enable_privileges, register_startup
from tray import launch_tray
from control.router import ControlRouter
from llm.intent import is_pc_command, extract_command_json
from llm.provider import stream_response
from voice.stt import SpeechToText
from memory.episodic import EpisodicMemory
from memory.structured import StructuredMemory

router = ControlRouter()
stt    = SpeechToText()
epimem = EpisodicMemory()
strmem = StructuredMemory()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──
    ensure_admin()          # 1. Re-launch as admin if needed
    enable_privileges()     # 2. Enable Win32 token privileges
    register_startup()      # 3. Register in Task Scheduler
    launch_tray()           # 4. System tray icon
    await epimem.init()     # 5. Init LanceDB
    strmem.init()           # 6. Init SQLite
    yield
    # ── SHUTDOWN ──
    # cleanup if needed

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])

@app.websocket("/ws")
async def ws_handler(ws: WebSocket):
    await ws.accept()
    while True:
        data = await ws.receive_json()
        text = data.get("text", "")
        mode = data.get("mode", "text")   # "text" or "voice"

        if is_pc_command(text):
            result = await handle_pc_command(text, ws)
        else:
            await handle_conversation(text, mode, ws)

@app.post("/voice/transcribe-audio")
async def transcribe(request: Request):
    audio_bytes = await request.body()
    text = await stt.transcribe(audio_bytes)
    return {"text": text}
```

---

### `startup.py` — Admin + Task Scheduler

```python
# startup.py
import ctypes, sys, os, subprocess

TASK_NAME = "MayAI"

def ensure_admin():
    """Re-launch with admin rights if not already elevated."""
    if ctypes.windll.shell32.IsUserAnAdmin():
        return
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit(0)

def enable_privileges():
    """Enable Win32 token privileges needed for full PC control."""
    import win32security, win32api, win32con
    PRIVS = [
        "SeDebugPrivilege",        # Read/write any process memory
        "SeRestorePrivilege",      # Write any file regardless of ACL
        "SeBackupPrivilege",       # Read any file regardless of ACL
        "SeTakeOwnershipPrivilege",# Take ownership of any object
        "SeSecurityPrivilege",     # Modify security descriptors
        "SeShutdownPrivilege",     # Shutdown/restart the system
    ]
    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(),
        win32con.TOKEN_ADJUST_PRIVILEGES | win32con.TOKEN_QUERY
    )
    for name in PRIVS:
        try:
            priv_id = win32security.LookupPrivilegeValue(None, name)
            win32security.AdjustTokenPrivileges(
                token, False, [(priv_id, win32con.SE_PRIVILEGE_ENABLED)]
            )
        except Exception:
            pass  # Not available on this account — continue

def register_startup():
    """Register May in Task Scheduler to run at Windows logon."""
    python  = sys.executable
    script  = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))
    cmd = [
        "schtasks", "/Create", "/F",
        "/TN", TASK_NAME,
        "/TR", f'"{python}" "{script}"',
        "/SC", "ONLOGON",
        "/RL", "HIGHEST",    # Run with highest privileges (no UAC prompt)
        "/DELAY", "0000:30", # 30-second delay after login (let desktop settle)
    ]
    subprocess.run(cmd, capture_output=True)

def unregister_startup():
    subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                   capture_output=True)
```

---

### `tray.py` — System Tray Icon

```python
# tray.py
import threading
import pystray
from PIL import Image, ImageDraw

_icon = None

def launch_tray():
    """Start the system tray icon in a background thread."""
    global _icon

    # Draw a simple cyan circle (matches May's accent color)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([8, 8, 56, 56], fill=(6, 182, 212))   # #06B6D4 cyan

    menu = pystray.Menu(
        pystray.MenuItem("Open May",  lambda: open_may_window()),
        pystray.MenuItem("Mute/Unmute", lambda: toggle_mute()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Restart",   lambda: restart_may()),
        pystray.MenuItem("Exit",      lambda: _icon.stop()),
    )

    _icon = pystray.Icon("May", img, "May AI", menu)
    threading.Thread(target=_icon.run, daemon=True).start()
```

---

### `control/bus.py` — Command & Result

Every single operation in the system is a `Command`. Every result is a `Result`.
Nothing bypasses these two dataclasses.

```python
# control/bus.py
from dataclasses import dataclass, field
from typing import Any
import uuid

@dataclass
class Command:
    layer:   str           # "filesystem", "process", "application", "window",
                           # "input", "registry", "services", "system", "browser"
    action:  str           # "delete_file", "kill_process", "open_app", etc.
    params:  dict          # Layer-specific parameters
    id:      str = field(default_factory=lambda: str(uuid.uuid4()))
    timeout: float = 10.0  # Max seconds before giving up

@dataclass
class Result:
    command_id:  str
    success:     bool
    data:        Any        # Return value (file list, process info, etc.)
    error:       str | None # Error message if all methods failed
    verified:    bool       # True if post-action check confirmed success
    method_used: str        # "method_1", "method_3", etc. — for debugging
    time_ms:     int        # Total execution time
```

---

### `control/privilege.py` — Privilege Management

Already covered in startup.py. This module also handles the rarer
SYSTEM-level escalation needed for protected processes:

```python
# control/privilege.py

def get_system_token():
    """
    Returns a SYSTEM-level token by impersonating the SYSTEM process.
    Use only when admin-level operations fail on protected resources.
    Requires SeDebugPrivilege (enabled at startup).
    """
    import win32security, win32api, win32process, win32con
    # Find a SYSTEM process (e.g., winlogon.exe)
    import psutil
    for proc in psutil.process_iter(["pid", "name"]):
        if proc.info["name"] == "winlogon.exe":
            handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION, False, proc.info["pid"]
            )
            token = win32security.OpenProcessToken(
                handle, win32con.TOKEN_DUPLICATE | win32con.TOKEN_QUERY
            )
            system_token = win32security.DuplicateTokenEx(
                token,
                win32con.MAXIMUM_ALLOWED,
                None,
                win32security.SecurityImpersonation,
                win32security.TokenPrimary
            )
            return system_token
    raise RuntimeError("Could not obtain SYSTEM token")
```

---

### `control/fallback.py` — Fallback Chain Executor

The engine that makes May reliable. Every layer method calls this.

```python
# control/fallback.py
import asyncio, time
from typing import Callable, Awaitable
from .bus import Result

async def run_with_fallback(
    command_id:  str,
    methods:     list[tuple[str, Callable]],  # [("method_1", fn), ...]
    verifier:    Callable | None = None,
    timeout:     float = 10.0
) -> Result:
    """
    Try each method in order. Stop at the first one that succeeds
    AND passes verification. Return a full Result with diagnostics.
    """
    start = time.monotonic()
    errors = {}

    for method_name, method_fn in methods:
        try:
            # Support both sync and async methods
            if asyncio.iscoroutinefunction(method_fn):
                data = await asyncio.wait_for(method_fn(), timeout=timeout)
            else:
                loop = asyncio.get_event_loop()
                data = await asyncio.wait_for(
                    loop.run_in_executor(None, method_fn), timeout=timeout
                )

            time_ms = int((time.monotonic() - start) * 1000)

            # Run verifier if provided
            verified = True
            if verifier:
                verified = verifier() if not asyncio.iscoroutinefunction(verifier) \
                           else await verifier()

            if verified:
                return Result(command_id, True, data, None, True, method_name, time_ms)
            else:
                errors[method_name] = "Verifier failed — action appeared to succeed but result not confirmed"

        except asyncio.TimeoutError:
            errors[method_name] = f"Timed out after {timeout}s"
        except Exception as e:
            errors[method_name] = str(e)

    time_ms = int((time.monotonic() - start) * 1000)
    error_summary = " | ".join(f"{k}: {v}" for k, v in errors.items())
    return Result(command_id, False, None, error_summary, False, "all_failed", time_ms)
```

---

### `control/router.py` — Layer Dispatcher

```python
# control/router.py
from .bus import Command, Result
from .layers import (
    L1_filesystem, L2_process, L3_application, L4_window,
    L5_input, L6_registry, L7_services, L8_system, L9_browser
)

LAYERS = {
    "filesystem":  L1_filesystem,
    "process":     L2_process,
    "application": L3_application,
    "window":      L4_window,
    "input":       L5_input,
    "registry":    L6_registry,
    "services":    L7_services,
    "system":      L8_system,
    "browser":     L9_browser,
}

class ControlRouter:
    async def execute(self, cmd: Command) -> Result:
        layer = LAYERS.get(cmd.layer)
        if not layer:
            return Result(
                cmd.id, False, None,
                f"Unknown layer '{cmd.layer}'. Valid: {list(LAYERS.keys())}",
                False, "none", 0
            )
        return await layer.execute(cmd.action, cmd.params, cmd.id, cmd.timeout)
```

---

### `control/safety.py` — Destructive Command Guard

```python
# control/safety.py
import re

# These patterns in LLM-generated PowerShell mean "stop and ask the user"
DANGEROUS_PATTERNS = [
    r"Remove-Item\s+.*-Recurse",
    r"Format-Volume",
    r"rm\s+-rf",
    r"del\s+/[Ss]",
    r"rd\s+/[Ss]",
    r"Clear-Disk",
    r"Initialize-Disk",
    r"Stop-Service\s+.*wuauserv",   # Windows Update
    r"Disable-WindowsOptionalFeature",
]

# These actions always require user confirmation before executing
DESTRUCTIVE_ACTIONS = {
    "filesystem": ["delete_file", "delete_folder", "delete_folder_tree", "empty_recycle_bin"],
    "process":    ["kill_process", "kill_process_tree"],
    "registry":   ["delete_key", "delete_value"],
    "system":     ["shutdown", "restart", "hibernate"],
    "services":   ["stop_service", "delete_service", "disable_service"],
}

def is_dangerous_powershell(code: str) -> bool:
    return any(re.search(p, code, re.IGNORECASE) for p in DANGEROUS_PATTERNS)

def needs_confirmation(layer: str, action: str) -> bool:
    return action in DESTRUCTIVE_ACTIONS.get(layer, [])
```

---

### `control/verifier.py` — Post-Action Verification

```python
# control/verifier.py
import os
import psutil

def verify_file_deleted(path: str) -> bool:
    return not os.path.exists(path)

def verify_file_exists(path: str) -> bool:
    return os.path.exists(path)

def verify_process_running(name_or_pid) -> bool:
    if isinstance(name_or_pid, int):
        return psutil.pid_exists(name_or_pid)
    return any(p.name().lower() == name_or_pid.lower()
               for p in psutil.process_iter(["name"]))

def verify_process_dead(pid: int) -> bool:
    return not psutil.pid_exists(pid)

def verify_volume_set(target: int) -> bool:
    # Check pycaw or nircmd for actual system volume
    # Returns True if within ±2% of target
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = interface.QueryInterface(IAudioEndpointVolume)
    current = round(volume.GetMasterVolumeLevelScalar() * 100)
    return abs(current - target) <= 2
```

---

### Layer Pattern — How Every Layer Is Structured

Every layer (L1–L9) follows the exact same pattern:

```python
# control/layers/L1_filesystem.py  (example pattern — all layers follow this)
from ..bus import Result
from ..fallback import run_with_fallback
import os, shutil, subprocess, ctypes

async def execute(action: str, params: dict, cmd_id: str, timeout: float) -> Result:
    handler = _ACTIONS.get(action)
    if not handler:
        return Result(cmd_id, False, None, f"Unknown action: {action}", False, "none", 0)
    return await handler(params, cmd_id, timeout)

async def _delete_file(params: dict, cmd_id: str, timeout: float) -> Result:
    path = params["path"]

    # Define all fallback methods for this action
    methods = [
        ("os.remove",       lambda: os.remove(path)),
        ("win32file",       lambda: _win32_delete(path)),
        ("cmd_del",         lambda: subprocess.run(["cmd","/c","del","/F","/Q",path], check=True)),
        ("clear_readonly",  lambda: (_clear_readonly(path), os.remove(path))),
        ("take_ownership",  lambda: (_take_ownership(path), os.remove(path))),
        ("kill_lock_retry", lambda: (_kill_locking_process(path), os.remove(path))),
        ("schedule_reboot", lambda: _schedule_delete_on_reboot(path)),
    ]

    # Verifier: file should not exist after delete
    def verify():
        return not os.path.exists(path)

    return await run_with_fallback(cmd_id, methods, verifier=verify, timeout=timeout)

# ── Helper functions ──────────────────────────────────────────────────────────

def _win32_delete(path: str):
    import win32file
    win32file.DeleteFileW(path)

def _clear_readonly(path: str):
    import win32api, win32con
    attrs = win32api.GetFileAttributes(path)
    win32api.SetFileAttributes(path, attrs & ~win32con.FILE_ATTRIBUTE_READONLY)

def _take_ownership(path: str):
    import win32security, win32api, win32con, ntsecuritycon
    # Take ownership, then grant full control
    sd = win32security.GetFileSecurity(path, win32security.DACL_SECURITY_INFORMATION)
    current_user = win32security.LookupAccountName(None, win32api.GetUserName())[0]
    win32security.SetFileSecurity(
        path,
        win32security.OWNER_SECURITY_INFORMATION,
        win32security.CreateSecurityDescriptor()
    )
    dacl = win32security.ACL()
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, ntsecuritycon.FILE_ALL_ACCESS, current_user)
    sd.SetSecurityDescriptorDacl(True, dacl, False)
    win32security.SetFileSecurity(path, win32security.DACL_SECURITY_INFORMATION, sd)

def _kill_locking_process(path: str):
    """Find and kill the process locking this file."""
    import psutil
    for proc in psutil.process_iter(["pid", "open_files"]):
        try:
            if any(f.path == path for f in (proc.info["open_files"] or [])):
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

def _schedule_delete_on_reboot(path: str):
    """Schedule the file for deletion on next Windows boot. Always succeeds."""
    MOVEFILE_DELAY_UNTIL_REBOOT = 0x4
    ctypes.windll.kernel32.MoveFileExW(path, None, MOVEFILE_DELAY_UNTIL_REBOOT)

# ── Action registry ──────────────────────────────────────────────────────────
_ACTIONS = {
    "delete_file":   _delete_file,
    # ... add all other filesystem actions here
}
```

---

### `llm/intent.py` — Command Intent Classification

```python
# llm/intent.py
import re, json

# Strong patterns → definitely a PC command, no LLM call needed
FAST_PATTERNS = [
    r'\b(open|launch|start|run)\s+\w+',
    r'\b(close|kill|quit|exit)\s+\w+',
    r'\b(delete|remove|trash)\s+.+',
    r'\b(create|make|new)\s+(file|folder|directory)',
    r'\bset\s+volume\s+to\b',
    r'\b(volume|brightness)\s*(up|down|to|set)\b',
    r'\b(shutdown|restart|sleep|hibernate|lock)\s*(the\s+pc|computer|system)?\b',
    r'\b(minimize|maximize|resize|move)\s+\w+',
    r'\btake\s+a?\s*screenshot\b',
    r'\btype\s+.+\s+in\b',
    r'\bopen\s+.+\s+in\s+\w+',
    r'\binstall\s+\w+',
    r'\bmute\b',
]

def is_pc_command(text: str) -> bool:
    """Fast regex check — no LLM call needed for obvious commands."""
    return any(re.search(p, text.lower()) for p in FAST_PATTERNS)

def extract_command_json(llm_response: str) -> dict | None:
    """
    Extract a structured command from LLM response.
    LLM should output JSON like:
    {"layer": "filesystem", "action": "delete_file", "params": {"path": "..."}}
    """
    # Try clean JSON first
    try:
        return json.loads(llm_response.strip())
    except json.JSONDecodeError:
        pass

    # Try extracting JSON block from mixed text
    match = re.search(r'\{[^{}]*"layer"[^{}]*\}', llm_response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None
```

---

### PC Command Execution Flow (in `main.py`)

```python
# main.py — how PC commands are handled end-to-end

async def handle_pc_command(text: str, ws: WebSocket) -> None:
    from control.safety import needs_confirmation, is_dangerous_powershell
    from llm.intent import extract_command_json
    from llm.provider import get_command_json   # LLM call that returns JSON command

    # Step 1: Ask LLM to convert natural language → structured command
    raw = await get_command_json(text)  # Returns {"layer":..., "action":..., "params":...}
    cmd_dict = extract_command_json(raw)

    if not cmd_dict:
        # LLM couldn't structure it → PowerShell fallback
        await handle_powershell_fallback(text, ws)
        return

    layer  = cmd_dict.get("layer", "")
    action = cmd_dict.get("action", "")
    params = cmd_dict.get("params", {})

    # Step 2: Safety check for destructive operations
    if needs_confirmation(layer, action):
        await ws.send_json({
            "type": "confirm",
            "message": f"This will {action.replace('_',' ')} — are you sure?",
            "command": cmd_dict
        })
        return  # Wait for user confirmation in a follow-up message

    # Step 3: Execute through the control router
    from control.bus import Command
    cmd    = Command(layer=layer, action=action, params=params)
    result = await router.execute(cmd)

    # Step 4: Respond
    if result.success:
        response = f"Done. {action.replace('_',' ').capitalize()} completed successfully."
    else:
        response = f"I couldn't do that. {result.error}"

    await ws.send_json({"type": "message", "text": response, "result": vars(result)})
```

---

## DATA FLOW SUMMARY

### Voice Command Path
```
User speaks
    ↓
Browser captures → webm blob
    ↓
POST /voice/transcribe-audio
    ↓
voice/stt.py (faster-whisper) → text
    ↓
WebSocket message with {text, mode: "voice"}
    ↓
is_pc_command(text)?
    ↙ YES                    ↘ NO
LLM → JSON command         LLM → conversation response
    ↓                           ↓
control/router.py          memory lookup (LanceDB)
    ↓                           ↓
Layer (L1–L9)              response text
    ↓                           ↓
fallback chain             voice/tts.py
    ↓                           ↓
verifier                   audio output
    ↓
Result → WebSocket
```

### Startup Sequence
```
Windows boots
    ↓
Task Scheduler fires (30s after logon)
    ↓
python main.py (already Admin — Task Scheduler ran with HIGHEST privilege)
    ↓
ensure_admin()           — already admin, passes immediately
enable_privileges()      — grants Win32 token privileges
register_startup()       — confirms task still exists in scheduler
launch_tray()            — system tray icon appears in notification area
FastAPI starts on :8080  — backend ready
    ↓
Tauri app starts (or stays minimized if already running)
    ↓
May is ready — listening for voice/text
```

---

## LAYER CAPABILITY REFERENCE

| Layer | Controls | Key Libraries |
|-------|----------|---------------|
| L1 Filesystem | Files, folders, drives, permissions, recycle bin | pathlib, os, shutil, win32file, win32security, watchdog |
| L2 Process | Launch, kill, suspend, resume, inspect | psutil, subprocess, win32process, ctypes.ntdll |
| L3 Application | Installed apps, UWP, Win32, COM automation | winreg, win32com, pywinauto, comtypes |
| L4 Window | Position, size, state, z-order, focus | win32gui, win32con, ctypes.user32 |
| L5 Input | Keyboard simulation, mouse control, clipboard | win32api, ctypes.user32, pyperclip |
| L6 Registry | All registry hives: read, write, delete | winreg, win32security |
| L7 Services | Windows Services, Task Scheduler | win32service, win32serviceutil, subprocess (schtasks) |
| L8 System | Volume, brightness, power, network, audio, display | pycaw, screen_brightness_control, ctypes, subprocess |
| L9 Browser | DOM automation, clicks, form fill, scraping | playwright, requests |

---

## TECH STACK (Complete Install List)

```bash
# Core Windows control
pip install pywin32 psutil pywinauto watchdog wmi pycaw playwright py7zr winshell comtypes

# System tray
pip install pystray Pillow

# Voice
pip install faster-whisper edge-tts

# Memory
pip install lancedb sentence-transformers

# Screen brightness
pip install screen_brightness_control

# Notifications
pip install winotify

# Backend
pip install fastapi uvicorn python-multipart

# Post-install (CRITICAL — run after pywin32)
python -m win32com.client.makepy

# Playwright browser
python -m playwright install chromium
```

---

## BUILD SEQUENCE

Build in this exact order. Test each phase before moving on.

```
PHASE 1 — Foundation (1–2 days)
  [1] startup.py         — ensure_admin() + enable_privileges() + register_startup()
  [2] control/bus.py     — Command + Result dataclasses
  [3] control/fallback.py— The fallback chain executor
  [4] control/verifier.py— Post-action verification helpers
  [5] tray.py            — System tray icon
  [6] main.py skeleton   — FastAPI + lifespan + WebSocket shell

PHASE 2 — Core Layers (3–5 days)
  [7]  L1_filesystem.py  — Start with read ops (list, read), then write, then delete
  [8]  L2_process.py     — list_processes first, then kill (careful)
  [9]  L8_system.py      — Volume + brightness (safe), then power (very careful)
  [10] L3_application.py — open_app with 7-strategy fallback (you already have this)

PHASE 3 — Automation Layers (3–4 days)
  [11] L4_window.py      — Enumerate windows first, then control
  [12] L5_input.py       — Keyboard first, then mouse
  [13] L6_registry.py    — Read-only first, then write
  [14] L7_services.py    — Query only first, then start/stop

PHASE 4 — Intelligence Layer (2–3 days)
  [15] llm/intent.py     — Upgrade is_pc_command() + extract_command_json()
  [16] llm/tools.py      — Native tool calls for OpenAI/Anthropic (structured output)
  [17] control/router.py — Wire all layers to the router
  [18] control/safety.py — Add confirmation flow for destructive actions

PHASE 5 — Complex Layers (2 days)
  [19] L9_browser.py     — Playwright automation (has its own install step)

PHASE 6 — Startup & Polish (1 day)
  [20] Task Scheduler registration test
  [21] Tray icon + menu actions
  [22] Graceful shutdown / restart from tray
```

---

## KNOWN ISSUES IN CURRENT PROJECT — HOW EACH IS FIXED

| Issue | Root Cause | Fix In Architecture |
|-------|-----------|---------------------|
| WiFi/BT toggle needs Admin | No privilege escalation | startup.py enable_privileges() |
| Volume fallback is approximate | Single pycaw call | L8_system fallback chain (nircmd, SendInput, WMI) |
| type_text window focus fragile | Guesses most-recent window | L5_input: type_text accepts hwnd param, L4_window returns handle |
| search_files no depth limit | Unbounded rglob | L1_filesystem: max_depth param on search |
| LLM PowerShell can be dangerous | No safety check | safety.py is_dangerous_powershell() |
| Boot startup not implemented | Phase 7 not done | startup.py register_startup() |
| System tray not implemented | Phase 7 not done | tray.py |

---

## ONE RULE

Every operation that touches the OS goes through:

```
Command → Router → Layer → Fallback Chain → Verifier → Result
```

Nothing bypasses this pipeline. No direct `os.remove()` calls in `main.py`.
No ad-hoc `subprocess.run()` calls outside the layers.
Everything is logged, everything is verifiable, everything has a fallback.

---

*MAY COMPLETE ARCHITECTURE — v1.0*
*Single process. 9 layers. Fallback chains. Verified results.*
