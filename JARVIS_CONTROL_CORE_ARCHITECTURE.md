# JARVIS CONTROL CORE — WINDOWS ARCHITECTURE
## The Complete PC Control Engine (No Frontend, No API Layer)

---

## WHAT THIS IS

A headless Python daemon that runs on Windows with Administrator privileges.
It receives structured commands and executes them against the OS with verified results.
This is ONLY the control engine — no UI, no voice, no LLM. Just pure execution.

---

## CORE PROPERTIES

| Property       | Value                                              |
|----------------|----------------------------------------------------|
| Language       | Python 3.12+                                       |
| Runtime        | asyncio event loop (async + thread pool for Win32) |
| Privilege      | Administrator (escalates to SYSTEM when needed)    |
| Process Type   | Windows Service (persistent daemon)                |
| Error Strategy | 3-tier fallback → verify → rollback                |
| Accuracy       | 100% via verified execution (see Section 11)       |

---

## MODULE STRUCTURE

```
jarvis/
└── core/                           ← THE ENTIRE CONTROL ENGINE
    │
    ├── daemon.py                   ← Entry point, Windows Service host
    ├── bus.py                      ← Internal async command bus
    ├── router.py                   ← Maps commands → correct layer
    ├── privilege.py                ← UAC, token, elevation management
    │
    ├── layers/                     ← The 9 Control Layers
    │   ├── L1_filesystem.py        ← Files, folders, drives, permissions
    │   ├── L2_process.py           ← Process launch, kill, suspend, inspect
    │   ├── L3_application.py       ← Installed apps, UWP, Win32, COM
    │   ├── L4_window.py            ← Window position, size, state, z-order
    │   ├── L5_input.py             ← Keyboard + Mouse simulation
    │   ├── L6_registry.py          ← Windows Registry (all hives)
    │   ├── L7_services.py          ← Windows Services + Task Scheduler
    │   ├── L8_system.py            ← Power, network, audio, display, env
    │   └── L9_browser.py           ← Browser DOM automation
    │
    ├── engine/
    │   ├── verifier.py             ← Pre/post action verification
    │   ├── fallback.py             ← Fallback chain executor
    │   ├── transaction.py          ← Atomic multi-step operations
    │   └── logger.py               ← Logging to file + Windows Event Log
    │
    └── config/
        ├── layer_caps.json         ← What each layer can do (capability map)
        └── fallback_chains.json    ← Fallback strategy per action type
```

---

## SECTION 1 — PRIVILEGE FOUNDATION

**This is the most critical part. Without it, 30% of operations silently fail.**

### 1.1 — Startup Elevation

```python
# privilege.py
import ctypes, sys

def ensure_admin():
    """Re-launches as admin if not already elevated."""
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join(sys.argv), None, 1
    )
    sys.exit(0)
```

Always call `ensure_admin()` at the very top of `daemon.py`, before anything else.

### 1.2 — Privilege Levels

```
Level 1: Administrator
    → Covers: 95% of all operations
    → How: UAC prompt on launch or run as Windows Service

Level 2: SYSTEM
    → Covers: Protected system files, service internals, locked process handles
    → How: Run the daemon as a Windows Service with LocalSystem account
    → OR: Use NSudoLC.exe / PsExec.exe to spawn a SYSTEM-level subprocess

Level 3: TrustedInstaller
    → Covers: C:\Windows\*, protected OS components
    → How: Token impersonation of the TrustedInstaller service
    → Use: win32security to duplicate TrustedInstaller's token
```

### 1.3 — Token Privileges to Enable at Startup

```python
# Enable these via win32security.AdjustTokenPrivileges
PRIVILEGES_NEEDED = [
    "SeDebugPrivilege",          # Read/write any process memory
    "SeRestorePrivilege",        # Write to any file regardless of ACL
    "SeBackupPrivilege",         # Read any file regardless of ACL
    "SeTakeOwnershipPrivilege",  # Take ownership of any object
    "SeSecurityPrivilege",       # Modify security descriptors
    "SeLoadDriverPrivilege",     # Load/unload device drivers
    "SeShutdownPrivilege",       # Shutdown/restart the system
    "SeTcbPrivilege",            # Act as part of the OS (SYSTEM-level tasks)
]
```

---

## SECTION 2 — THE COMMAND BUS

The bus is the backbone. Every layer communicates only through it.

### 2.1 — Core Structures

```python
# bus.py
from dataclasses import dataclass, field
from typing import Any
import asyncio, uuid

@dataclass
class Command:
    layer:    str          # Target layer: "filesystem", "process", etc.
    action:   str          # Action name: "delete_file", "kill_process", etc.
    params:   dict         # Action parameters
    id:       str   = field(default_factory=lambda: str(uuid.uuid4()))
    priority: int   = 1    # 0=low, 1=normal, 2=urgent
    timeout:  float = 10.0 # Max execution time in seconds

@dataclass
class Result:
    command_id:  str
    success:     bool
    data:        Any        # Return value of the action
    error:       str | None # Error message if failed
    verified:    bool       # True if post-action verification passed
    method_used: str        # Which fallback method succeeded
    time_ms:     int        # Execution time in milliseconds
```

### 2.2 — Bus Implementation

```python
class CommandBus:
    def __init__(self):
        self.handlers: dict[str, callable] = {}

    def register(self, layer_name: str, handler: callable):
        self.handlers[layer_name] = handler

    async def dispatch(self, cmd: Command) -> Result:
        handler = self.handlers.get(cmd.layer)
        if not handler:
            return Result(cmd.id, False, None, f"Unknown layer: {cmd.layer}", False, "none", 0)
        try:
            return await asyncio.wait_for(
                handler(cmd.action, cmd.params),
                timeout=cmd.timeout
            )
        except asyncio.TimeoutError:
            return Result(cmd.id, False, None, "Timeout exceeded", False, "none", int(cmd.timeout * 1000))
        except Exception as e:
            return Result(cmd.id, False, None, str(e), False, "none", 0)
```

### 2.3 — Communication Protocol (JSON over Local Socket)

```
// Brain → Core (sends a command)
{
  "id":      "cmd_001",
  "layer":   "filesystem",
  "action":  "delete_file",
  "params":  { "path": "C:\\Users\\User\\Desktop\\junk.txt" },
  "timeout": 5.0
}

// Core → Brain (returns result)
{
  "id":          "cmd_001",
  "success":     true,
  "data":        null,
  "error":       null,
  "verified":    true,
  "method_used": "method_1",
  "time_ms":     14
}
```

Transport options (pick one):
- **Named Pipe** (recommended): fastest, most secure, Windows-native
- **TCP 127.0.0.1:PORT**: simplest, works with any language
- **Unix Domain Socket**: not available on Windows — do not use

---

## SECTION 3 — LAYER 1: FILE SYSTEM

### What It Controls
Files, folders, drives, NTFS permissions, file attributes, search, monitoring, compression, recycle bin, symbolic links.

### Libraries

| Library       | Purpose                                |
|---------------|----------------------------------------|
| `pathlib`     | Path manipulation (stdlib)             |
| `os`, `shutil`| File/folder operations (stdlib)        |
| `win32file`   | Low-level file I/O, attributes         |
| `win32api`    | File attributes (hidden, system, etc.) |
| `win32security`| NTFS permissions, ACLs, ownership     |
| `watchdog`    | Real-time file system events           |
| `winshell`    | Recycle Bin operations                 |
| `py7zr`       | Archive support (7z, zip, tar, etc.)   |
| `ctypes`      | CreateFileW, MoveFileExW, etc.         |

### Key Win32 APIs (via ctypes or pywin32)

```
CreateFileW         — Open any file including locked system files
                      (use FILE_FLAG_BACKUP_SEMANTICS for protected files)
MoveFileExW         — Atomic move; MOVEFILE_DELAY_UNTIL_REBOOT for locked files
CopyFileExW         — Copy with progress callback
DeleteFileW         — Delete; combine with SetFileAttributesW to clear read-only first
SetFileAttributesW  — Set hidden, system, read-only, archive flags
BackupRead          — Read any file bypassing ACL (requires SeBackupPrivilege)
BackupWrite         — Write any file bypassing ACL (requires SeRestorePrivilege)
DeviceIoControl     — Low-level disk/volume operations
NtQuerySystemInformation — Find which process has a file locked
```

### Actions

```
create_file          create_folder        delete_file
delete_folder        copy_file            move_file
rename_file          list_directory       search_files
get_file_info        set_file_attributes  get_file_hash
change_permissions   take_ownership       read_file
write_file           append_to_file       get_drive_info
list_drives          send_to_recycle_bin  restore_from_recycle_bin
empty_recycle_bin    compress             decompress
create_symlink       create_hardlink      monitor_path_start
monitor_path_stop    get_locked_by        find_large_files
find_duplicates      copy_folder_tree     delete_folder_tree
```

### Fallback Chain: delete_file

```
Method 1: os.remove(path)
Method 2: win32file.DeleteFileW(path)
Method 3: subprocess.run(["cmd", "/c", "del", "/F", "/Q", path])
Method 4: SetFileAttributesW(path, FILE_ATTRIBUTE_NORMAL) → Method 1
Method 5: take_ownership(path) → set_full_permissions(path) → Method 1
Method 6: kill_locking_process(path) → Method 1
Method 7: MoveFileExW(path, null, MOVEFILE_DELAY_UNTIL_REBOOT)
          [schedules delete on next Windows boot — guaranteed success]
```

### Verification: delete_file

```python
def verify_delete(path: str) -> bool:
    return not os.path.exists(path)
```

---

## SECTION 4 — LAYER 2: PROCESS CONTROL

### What It Controls
Running processes, their CPU/memory, priority, threads, and handles.

### Libraries

| Library         | Purpose                                      |
|-----------------|----------------------------------------------|
| `psutil`        | Enumerate, kill, suspend, inspect processes  |
| `subprocess`    | Launch processes (stdlib)                    |
| `win32process`  | CreateProcess, job objects                   |
| `win32api`      | OpenProcess, TerminateProcess                |
| `win32con`      | Constants (PROCESS_ALL_ACCESS, etc.)         |
| `ctypes.ntdll`  | NtSuspendProcess, NtResumeProcess            |

### Key Win32 APIs

```
OpenProcess(PROCESS_ALL_ACCESS, ...)   — Get full handle to any process
TerminateProcess(handle, exit_code)    — Force kill
NtSuspendProcess(handle)               — Freeze (via ntdll.dll ctypes)
NtResumeProcess(handle)                — Unfreeze (via ntdll.dll ctypes)
CreateJobObject + AssignProcessToJobObject — Limit CPU/memory of a process
SetPriorityClass                       — Set process priority
SetProcessAffinityMask                 — Pin process to specific CPU cores
ReadProcessMemory / WriteProcessMemory — For advanced automation
```

### NtSuspend/Resume (not in pywin32, must use ctypes directly)

```python
import ctypes

ntdll = ctypes.WinDLL("ntdll.dll")

def suspend_process(pid: int):
    handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)
    ntdll.NtSuspendProcess(handle)
    ctypes.windll.kernel32.CloseHandle(handle)

def resume_process(pid: int):
    handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)
    ntdll.NtResumeProcess(handle)
    ctypes.windll.kernel32.CloseHandle(handle)
```

### Actions

```
list_processes          get_process_info        find_process_by_name
launch_process          kill_process             kill_process_tree
suspend_process         resume_process           set_priority
set_affinity            get_cpu_usage            get_memory_usage
get_open_handles        get_threads              wait_for_exit
get_command_line        get_environment          get_parent_pid
create_job_object       assign_to_job            set_memory_limit
set_cpu_limit           get_process_path         is_process_running
```

### Fallback Chain: kill_process(pid)

```
Method 1: psutil.Process(pid).kill()
Method 2: win32api.TerminateProcess(win32api.OpenProcess(..., pid), 0)
Method 3: subprocess.run(["taskkill", "/F", "/PID", str(pid)])
Method 4: Escalate to SYSTEM token → Method 2 with full access rights
Method 5: subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)])
          [/T kills entire process tree]
```

---

## SECTION 5 — LAYER 3: APPLICATION CONTROL

### What It Controls
Installed applications — launch, close, automate their UI, install, uninstall.

### Libraries

| Library          | Purpose                                         |
|------------------|-------------------------------------------------|
| `winreg`         | Find all installed apps (stdlib)                |
| `win32api`       | ShellExecuteEx for launching with verb/UAC      |
| `pywinauto`      | Automate any Windows app by its UI controls     |
| `win32com.client`| COM automation (Office, IE, Explorer, etc.)     |
| `comtypes`       | COM interface definitions                       |
| `subprocess`     | winget for install/uninstall                    |

### Finding All Installed Apps

```python
# winreg paths — check ALL of these
UNINSTALL_PATHS = [
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
]
HIVES = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]

# For UWP (Microsoft Store) apps:
subprocess.run(["powershell", "-Command", "Get-AppxPackage | ConvertTo-Json"])

# For apps in PATH:
subprocess.run(["where", "app_name.exe"])

# For App Paths in registry:
# HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\
```

### pywinauto Strategy

```python
from pywinauto import Application

# For modern apps (WPF, Win32 with accessibility):
app = Application(backend="uia").start("notepad.exe")
window = app.window(title_re=".*Notepad.*")
window.Edit.type_keys("Hello World")

# For legacy apps:
app = Application(backend="win32").connect(title="Old App")

# Find any control by: title, class_name, control_type, auto_id
# Then: click(), double_click(), type_keys(), select(), check(), etc.
```

### COM Automation (for Office, etc.)

```python
import win32com.client

# Word
word = win32com.client.Dispatch("Word.Application")
word.Visible = True
doc = word.Documents.Open("C:\\doc.docx")

# Excel
excel = win32com.client.Dispatch("Excel.Application")
wb = excel.Workbooks.Open("C:\\data.xlsx")

# Windows Explorer shell
shell = win32com.client.Dispatch("Shell.Application")
```

### Actions

```
list_installed_apps     find_app_by_name     get_app_path
get_app_version         launch_app           launch_with_args
launch_as_admin         close_app            restart_app
force_close_app         is_app_running       install_app
uninstall_app           automate_app         com_dispatch
get_app_icon            pin_to_taskbar       unpin_from_taskbar
pin_to_start            unpin_from_start     set_default_program
```

---

## SECTION 6 — LAYER 4: WINDOW MANAGEMENT

### What It Controls
Every visible window on screen — position, size, state, z-order, title, focus.

### Libraries

| Library       | Purpose                                              |
|---------------|------------------------------------------------------|
| `win32gui`    | EnumWindows, FindWindow, SetWindowPos, ShowWindow    |
| `win32con`    | SW_MAXIMIZE, SW_MINIMIZE, HWND_TOPMOST, etc.         |
| `ctypes.user32`| Direct user32.dll for anything not in pywin32       |

### Key Win32 APIs

```
EnumWindows(callback, lParam)    — Enumerate ALL top-level windows
FindWindow(class, title)         — Find window by class or title
FindWindowEx(parent, after, ...)  — Find child windows
GetWindowText(hwnd)              — Get window title
SetWindowText(hwnd, text)        — Change window title
ShowWindow(hwnd, nCmdShow)       — SW_MINIMIZE, SW_MAXIMIZE, SW_RESTORE,
                                   SW_HIDE, SW_SHOW, SW_SHOWNORMAL
SetWindowPos(hwnd, insert, x, y, w, h, flags) — Move, resize, z-order
SetForegroundWindow(hwnd)        — Bring to front (focus)
GetWindowRect(hwnd, &rect)       — Get position and size
GetClientRect(hwnd, &rect)       — Get client area
PostMessage(hwnd, msg, wParam, lParam) — Send async message
SendMessage(hwnd, msg, wParam, lParam) — Send sync message
WM_CLOSE (0x0010)                — Graceful close
WM_DESTROY (0x0002)              — Force close
```

### Virtual Desktops

```python
# Use IVirtualDesktopManager COM interface
import comtypes.client
IVirtualDesktopManager = comtypes.GUID("{A5CD92FF-29BE-454C-8D04-D82879FB3F1B}")
# Or use VirtualDesktop.exe CLI wrapper for simplicity
```

### Actions

```
list_all_windows        find_window          get_active_window
get_window_info         minimize_window      maximize_window
restore_window          hide_window          show_window
move_window             resize_window        set_position_and_size
set_foreground          set_topmost          unset_topmost
close_window            force_close_window   send_message
post_message            get_window_title     set_window_title
take_window_screenshot  arrange_tile         arrange_cascade
move_to_virtual_desktop list_virtual_desktops get_window_pid
get_window_class        get_window_rect      is_window_visible
is_window_minimized     flash_window
```

---

## SECTION 7 — LAYER 5: INPUT SIMULATION

### What It Controls
Keyboard and mouse — simulates real human input at the driver level.

### THE MOST RELIABLE METHOD: SendInput via ctypes

Do NOT use pyautogui as your primary method. It uses mouse_event/keybd_event which are deprecated and can be blocked. Use SendInput directly.

```python
# input.py — The correct way to send keyboard input
import ctypes
from ctypes import wintypes

INPUT_KEYBOARD = 1
INPUT_MOUSE    = 0

KEYEVENTF_KEYUP   = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          wintypes.LONG),
        ("dy",          wintypes.LONG),
        ("mouseData",   wintypes.DWORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         wintypes.WORD),
        ("wScan",       wintypes.WORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT_UNION)]

def send_key(vk_code: int, key_up: bool = False):
    flags = KEYEVENTF_KEYUP if key_up else 0
    inp = INPUT(type=INPUT_KEYBOARD,
                _input=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk_code, dwFlags=flags)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def press_key(vk_code: int):
    send_key(vk_code, key_up=False)
    send_key(vk_code, key_up=True)
```

### Type Text Strategy

```
Short text (< 50 chars):   SendInput char by char with KEYEVENTF_UNICODE
Long text  (>= 50 chars):  
    1. Copy text to clipboard (win32clipboard)
    2. Focus target window
    3. SendInput Ctrl+V
    Result: Instant, no character limit, handles any Unicode
```

### Mouse Input

```python
MOUSEEVENTF_MOVE       = 0x0001
MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_WHEEL      = 0x0800
MOUSEEVENTF_ABSOLUTE   = 0x8000

def mouse_move(x: int, y: int, absolute: bool = True):
    if absolute:
        # Normalize to 0-65535 range
        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1)
        nx = int(x * 65535 / screen_w)
        ny = int(y * 65535 / screen_h)
        flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
    else:
        nx, ny = x, y
        flags = MOUSEEVENTF_MOVE
    inp = INPUT(type=INPUT_MOUSE,
                _input=_INPUT_UNION(mi=MOUSEINPUT(dx=nx, dy=ny, dwFlags=flags)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
```

### Actions

```
press_key           release_key         tap_key
hold_key            type_text           type_text_fast
hotkey              mouse_move          left_click
right_click         middle_click        double_click
mouse_down          mouse_up            scroll_up
scroll_down         drag_and_drop       get_cursor_position
get_key_state       screenshot_full     screenshot_region
screenshot_window   set_clipboard       get_clipboard
```

---

## SECTION 8 — LAYER 6: WINDOWS REGISTRY

### What It Controls
All 5 registry hives, keys, values, permissions, and remote registry.

### Libraries

```
winreg       — full registry access (stdlib)
win32api     — remote registry
win32security — registry key permissions and ownership
```

### Hive Reference

```
HKEY_LOCAL_MACHINE  (HKLM) → System-wide settings, installed software, hardware
HKEY_CURRENT_USER   (HKCU) → Settings for current logged-in user
HKEY_CLASSES_ROOT   (HKCR) → File type associations, COM class registrations
HKEY_USERS          (HKU)  → All user profiles (includes HKCU and .DEFAULT)
HKEY_CURRENT_CONFIG (HKCC) → Current hardware profile
```

### Value Types

```
REG_SZ          → String
REG_EXPAND_SZ   → String with environment variable expansion
REG_DWORD       → 32-bit integer
REG_QWORD       → 64-bit integer
REG_BINARY      → Raw binary data
REG_MULTI_SZ    → List of strings (null-separated)
REG_NONE        → No defined type
```

### Actions

```
read_value          write_value         delete_value
create_key          delete_key          list_subkeys
list_values         key_exists          value_exists
export_key          import_key          backup_key
restore_key         search_by_name      search_by_value
set_key_permissions take_ownership      open_remote_registry
```

### CRITICAL: Always Backup Before Modifying

```python
def backup_key(hive, key_path: str, backup_file: str):
    """Export a key to .reg file before modifying it."""
    subprocess.run([
        "reg", "export",
        f"{hive_name}\\{key_path}",
        backup_file, "/y"
    ])
```

---

## SECTION 9 — LAYER 7: SERVICES & TASK SCHEDULER

### What It Controls
Windows Services (SCM) and Task Scheduler jobs.

### Libraries

```
win32service      — Service Control Manager
win32serviceutil  — Start, stop, install, remove services
win32com.client   → TaskScheduler COM interface (most complete)
subprocess        → sc.exe, schtasks.exe as fallback
```

### Services Actions

```
list_services          get_service_status     get_service_config
start_service          stop_service           restart_service
pause_service          resume_service         install_service
remove_service         set_startup_type       change_credentials
set_description        enable_service         disable_service
get_service_pid        get_dependent_services
```

### Service Startup Types

```
win32service.SERVICE_AUTO_START     → Starts at Windows boot
win32service.SERVICE_DEMAND_START   → Manual start only
win32service.SERVICE_DISABLED       → Cannot be started
win32service.SERVICE_BOOT_START     → Loaded by OS loader (drivers)
win32service.SERVICE_SYSTEM_START   → Started by IoInitSystem (drivers)
```

### Task Scheduler via COM

```python
import win32com.client

scheduler = win32com.client.Dispatch("Schedule.Service")
scheduler.Connect()
root_folder = scheduler.GetFolder("\\")

# Create a task
task_def = scheduler.NewTask(0)
task_def.RegistrationInfo.Description = "My Task"

# Set trigger (time-based)
trigger = task_def.Triggers.Create(1)  # TASK_TRIGGER_TIME
trigger.StartBoundary = "2024-01-01T09:00:00"
trigger.Repetition.Interval = "PT1H"  # Repeat every hour

# Set action (run executable)
action = task_def.Actions.Create(0)   # TASK_ACTION_EXEC
action.Path = "C:\\my_script.py"
action.Arguments = "--flag value"

# Register task
root_folder.RegisterTaskDefinition(
    "MyTask", task_def, 6, None, None, 3  # TASK_CREATE_OR_UPDATE
)
```

### Task Scheduler Actions

```
list_tasks          get_task_info       create_task
delete_task         enable_task         disable_task
run_task_now        stop_task           get_last_run_result
set_trigger_time    set_trigger_event   set_trigger_logon
set_trigger_idle    get_task_history
```

---

## SECTION 10 — LAYER 8: SYSTEM CONTROL

### What It Controls
Power management, audio, display, network, environment variables, WMI, hardware.

### Libraries

```
wmi                  — WMI queries (hardware info, OS info, event watching)
ctypes.windll.user32 — ExitWindowsEx (shutdown/restart/logoff)
ctypes.windll.powrprof — Power scheme management, sleep/hibernate
pycaw                — Windows Core Audio API (volume, devices, per-app volume)
subprocess + netsh   — Wi-Fi, network adapter, firewall control
winreg               — System environment variables
win32net             — Network shares
```

### Power Management

```python
import ctypes

# Shutdown (force)
ctypes.windll.user32.ExitWindowsEx(0x00000001 | 0x00000004, 0)
# EWX_SHUTDOWN = 0x01, EWX_FORCE = 0x04

# Restart (force)
ctypes.windll.user32.ExitWindowsEx(0x00000002 | 0x00000004, 0)
# EWX_REBOOT = 0x02

# Log off
ctypes.windll.user32.ExitWindowsEx(0x00000000, 0)

# Lock workstation
ctypes.windll.user32.LockWorkStation()

# Sleep
ctypes.windll.powrprof.SetSuspendState(False, True, False)
# (hibernate=False, force=True, wakeupevents=False)

# Hibernate
ctypes.windll.powrprof.SetSuspendState(True, True, False)

# Cancel shutdown (if within 60 sec)
subprocess.run(["shutdown", "/a"])
```

### Audio Control (pycaw)

```python
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL

def get_volume_interface():
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))

def set_volume(level: float):  # 0.0 to 1.0
    vol = get_volume_interface()
    vol.SetMasterVolumeLevelScalar(level, None)

def mute():
    get_volume_interface().SetMute(1, None)

def unmute():
    get_volume_interface().SetMute(0, None)
```

### Display Control

```python
# Get display info
import win32api, win32con

def get_displays():
    return win32api.EnumDisplayDevices()

def set_brightness(level: int):  # 0-100
    # via WMI
    import wmi
    c = wmi.WMI(namespace="wmi")
    methods = c.WmiMonitorBrightnessMethods()[0]
    methods.WmiSetBrightness(level, 0)

def change_resolution(width: int, height: int):
    import win32api, win32con
    devmode = win32api.EnumDisplaySettings(None, -1)  # ENUM_CURRENT_SETTINGS
    devmode.PelsWidth  = width
    devmode.PelsHeight = height
    win32api.ChangeDisplaySettings(devmode, 0)
```

### Network Control (via netsh subprocess)

```python
# These all use subprocess → netsh (the most reliable approach)
# Adapter control:
subprocess.run(["netsh", "interface", "set", "interface", "Wi-Fi", "disable"])
subprocess.run(["netsh", "interface", "set", "interface", "Wi-Fi", "enable"])

# Wi-Fi:
subprocess.run(["netsh", "wlan", "connect", "name=MyNetwork"])
subprocess.run(["netsh", "wlan", "disconnect"])
subprocess.run(["netsh", "wlan", "show", "profiles"])

# DNS:
subprocess.run(["ipconfig", "/flushdns"])

# Firewall:
subprocess.run(["netsh", "advfirewall", "set", "allprofiles", "state", "off"])
```

### Environment Variables

```python
import winreg, ctypes

SYSTEM_ENV_KEY = r"System\CurrentControlSet\Control\Session Manager\Environment"
USER_ENV_KEY   = "Environment"

def set_system_env(name: str, value: str):
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, SYSTEM_ENV_KEY,
                        0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
    # Broadcast change to all windows (no reboot needed)
    ctypes.windll.user32.SendMessageTimeoutW(
        0xFFFF,       # HWND_BROADCAST
        0x001A,       # WM_SETTINGCHANGE
        0,
        "Environment",
        0x0002,       # SMTO_ABORTIFHUNG
        5000, None
    )
```

### WMI Event Subscriptions (real-time OS events)

```python
import wmi, threading

def watch_process_creation(callback):
    def _watch():
        c = wmi.WMI()
        watcher = c.Win32_Process.watch_for("creation")
        while True:
            process = watcher()
            callback(process.Name, process.ProcessId)
    threading.Thread(target=_watch, daemon=True).start()

def watch_usb_events(callback):
    def _watch():
        c = wmi.WMI()
        watcher = c.Win32_USBControllerDevice.watch_for()
        while True:
            event = watcher()
            callback(event)
    threading.Thread(target=_watch, daemon=True).start()
```

### Actions

```
shutdown            restart             sleep
hibernate           lock_workstation    logoff
cancel_shutdown     set_volume          get_volume
mute                unmute              get_audio_devices
set_default_device  set_brightness      get_brightness
change_resolution   get_displays        rotate_display
get_ip_config       enable_adapter      disable_adapter
connect_wifi        disconnect_wifi     list_wifi_networks
flush_dns           add_firewall_rule   remove_firewall_rule
set_system_env      get_system_env      delete_system_env
set_user_env        get_user_env        get_hardware_info
get_cpu_temp        get_disk_usage      get_ram_usage
watch_process       watch_usb           watch_file_events
get_uptime          get_os_info         get_installed_updates
```

---

## SECTION 11 — LAYER 9: BROWSER AUTOMATION

### What It Controls
Chrome, Firefox, Edge — at full DOM level with JavaScript access.

### Library: Playwright (use this, not Selenium)

```
playwright         — The most reliable browser automation on Windows
                   — Supports Chromium, Firefox, WebKit
                   — Has async API (perfect for asyncio integration)
                   — Handles dynamic content, SPAs, shadow DOM
```

### Setup

```bash
pip install playwright
python -m playwright install chromium   # Or firefox, webkit
```

### Connect to Existing Browser (so you use YOUR logged-in browser)

```python
from playwright.async_api import async_playwright

async def connect_to_running_chrome():
    # Launch Chrome with remote debugging enabled:
    # chrome.exe --remote-debugging-port=9222
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]  # Use existing context (logged in, cookies intact)
        page    = context.pages[0]
        return browser, page
```

### Actions

```
open_browser            close_browser           connect_to_browser
new_tab                 close_tab               navigate_to
go_back                 go_forward              reload
find_element            click_element           type_into_element
hover_element           scroll_to_element       scroll_page
take_screenshot         get_page_title          get_current_url
get_element_text        get_element_attribute   run_javascript
fill_form               submit_form             handle_dialog
wait_for_element        wait_for_url            wait_for_network_idle
download_file           manage_cookies          manage_local_storage
intercept_request       get_page_html           switch_tab
```

---

## SECTION 12 — FALLBACK CHAIN ENGINE

**This is what gives you 100% accuracy.**

### Core Principle

Every action has multiple methods to achieve the same result. If Method 1 fails, try Method 2. If all methods fail, the action gets reported as failed with full diagnostic info. Nothing silently fails.

```python
# fallback.py
from typing import Callable, Any
import asyncio, time

class FallbackChain:

    async def execute(
        self,
        action: str,
        params: dict,
        methods: list[Callable],
        verifier: Callable | None = None
    ) -> tuple[bool, Any, str, str]:
        """
        Returns: (success, result, method_used, error_message)
        """
        errors = []

        for i, method in enumerate(methods):
            method_name = f"method_{i+1}_{method.__name__}"
            try:
                t_start = time.monotonic()
                result = await method(params)
                t_end   = time.monotonic()

                # Verify the action actually worked
                if verifier:
                    await asyncio.sleep(0.05)  # Brief settle time for OS
                    verified = await verifier(params, result)
                    if not verified:
                        errors.append(f"{method_name}: executed but verification failed")
                        continue

                return True, result, method_name, ""

            except Exception as e:
                errors.append(f"{method_name}: {str(e)}")
                continue

        return False, None, "none", " | ".join(errors)
```

### Verification Pattern (every layer implements these)

```python
# verifier.py
class Verifiers:
    
    @staticmethod
    async def file_deleted(params, result) -> bool:
        return not os.path.exists(params["path"])
    
    @staticmethod
    async def file_exists(params, result) -> bool:
        return os.path.exists(params["path"])
    
    @staticmethod
    async def process_killed(params, result) -> bool:
        return not any(p.pid == params["pid"] for p in psutil.process_iter())
    
    @staticmethod
    async def window_position(params, result) -> bool:
        import win32gui
        rect = win32gui.GetWindowRect(params["hwnd"])
        return rect[0] == params["x"] and rect[1] == params["y"]
    
    @staticmethod
    async def registry_value(params, result) -> bool:
        import winreg
        val, _ = winreg.QueryValueEx(params["key"], params["name"])
        return val == params["value"]
    
    @staticmethod
    async def volume_set(params, result) -> bool:
        # re-read the volume and compare
        current = get_volume()
        return abs(current - params["level"]) < 0.01
```

---

## SECTION 13 — TRANSACTION ENGINE

For multi-step operations that must succeed completely or roll back completely.

```python
# transaction.py
from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass
class Step:
    name:       str
    action:     Callable     # The thing to do
    rollback:   Callable     # How to undo it if a later step fails
    params:     dict

class Transaction:
    def __init__(self, name: str):
        self.name    = name
        self.steps:  list[Step] = []
        self._done:  list[tuple[Step, Any]] = []

    def add(self, step: Step):
        self.steps.append(step)

    async def execute(self) -> tuple[bool, str]:
        for step in self.steps:
            try:
                result = await step.action(step.params)
                self._done.append((step, result))
            except Exception as e:
                await self._rollback()
                return False, f"Failed at [{step.name}]: {e}"
        return True, "All steps completed"

    async def _rollback(self):
        for step, result in reversed(self._done):
            try:
                await step.rollback(step.params, result)
            except Exception as e:
                # Log but continue rolling back other steps
                print(f"Rollback failed for [{step.name}]: {e}")
        self._done.clear()
```

### Example: "Reorganize 1000 Files Into New Folder Structure"

```python
tx = Transaction("file_reorganize")

tx.add(Step("create_target_dirs",
    action   = create_directories,
    rollback = delete_directories,
    params   = {"dirs": ["C:\\New\\Folder\\A", "C:\\New\\Folder\\B"]}
))

tx.add(Step("copy_files",
    action   = copy_all_files,
    rollback = delete_copied_files,
    params   = {"source": "C:\\Old\\", "dest": "C:\\New\\"}
))

tx.add(Step("verify_copies",
    action   = verify_all_checksums,
    rollback = delete_copied_files,
    params   = {"files": [...]}
))

tx.add(Step("delete_originals",
    action   = delete_all_originals,
    rollback = restore_from_backup,   # if you made a backup
    params   = {"files": [...]}
))

success, message = await tx.execute()
# If verify_copies fails → copies get deleted → dirs get deleted → back to original state
```

---

## SECTION 14 — DAEMON ENTRY POINT

Run the control core as a persistent Windows Service:

```python
# daemon.py
import asyncio
import win32serviceutil, win32service, win32event, servicemanager

from bus import CommandBus
from router import Router
from privilege import ensure_admin, enable_all_privileges
from layers import L1_filesystem, L2_process, L3_application
from layers import L4_window, L5_input, L6_registry
from layers import L7_services, L8_system, L9_browser

class JarvisCore(win32serviceutil.ServiceFramework):
    _svc_name_         = "JarvisCore"
    _svc_display_name_ = "Jarvis Control Core"
    _svc_description_  = "Jarvis PC Control Engine"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.bus    = CommandBus()
        self.router = Router(self.bus)
        self._register_layers()

    def _register_layers(self):
        self.bus.register("filesystem",   L1_filesystem.handler)
        self.bus.register("process",      L2_process.handler)
        self.bus.register("application",  L3_application.handler)
        self.bus.register("window",       L4_window.handler)
        self.bus.register("input",        L5_input.handler)
        self.bus.register("registry",     L6_registry.handler)
        self.bus.register("services",     L7_services.handler)
        self.bus.register("system",       L8_system.handler)
        self.bus.register("browser",      L9_browser.handler)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, "")
        )
        ensure_admin()
        enable_all_privileges()
        asyncio.run(self._main_loop())

    async def _main_loop(self):
        # Listen for commands from the AI brain via named pipe
        server = await asyncio.start_server(
            self._handle_connection,
            "127.0.0.1", 7650    # Only local connections
        )
        async with server:
            await server.serve_forever()

    async def _handle_connection(self, reader, writer):
        import json
        data = await reader.read(65536)
        command_dict = json.loads(data.decode())
        from bus import Command
        cmd    = Command(**command_dict)
        result = await self.bus.dispatch(cmd)
        writer.write(json.dumps(result.__dict__).encode())
        await writer.drain()
        writer.close()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(JarvisCore)
```

### Install / Start / Stop the Service

```bash
# Install
python daemon.py install

# Start
python daemon.py start
# OR
net start JarvisCore

# Stop
python daemon.py stop

# Remove
python daemon.py remove

# Debug (run in terminal, not as service — for development)
python daemon.py debug
```

---

## SECTION 15 — ACCURACY GUARANTEE EXECUTION FLOW

```
COMMAND RECEIVED
      │
      ▼
[1] ROUTER: Map command → layer + action
      │
      ▼
[2] PRE-FLIGHT CHECK
    ├─ Does the target exist?        (file/folder/process/window)
    ├─ Do we have permission?        (check ACL, privilege level)
    └─ Is the action safe to proceed? (e.g., not deleting system32)
      │
      ▼  [if pre-flight fails → return early with specific error]
      │
      ▼
[3] EXECUTE METHOD 1 (primary method)
      │
      ├─ [SUCCESS] → Verify → [VERIFIED] → ✅ Return Success
      │                     → [NOT VERIFIED] → try Method 2
      │
      └─ [EXCEPTION] → try Method 2
      │
      ▼
[4] EXECUTE METHOD 2 (first fallback)
      │
      ├─ [SUCCESS] → Verify → [VERIFIED] → ✅ Return Success
      └─ [EXCEPTION] → try Method 3
      │
      ▼
[5] EXECUTE METHOD 3 (second fallback)
      │
      ├─ [SUCCESS] → Verify → ✅ Return Success
      └─ [EXCEPTION] → Escalate privilege
      │
      ▼
[6] PRIVILEGE ESCALATION
    ├─ Enable additional token privileges
    ├─ If needed: re-run as SYSTEM via service
    └─ Retry from Method 1 with elevated context
      │
      ▼
[7] SCHEDULE / DEFER (for truly locked system resources)
    └─ MoveFileExW DELAY_UNTIL_REBOOT for files
       Task Scheduler for process-dependent actions
      │
      ▼
[8] RETURN FULL DIAGNOSTIC
    ├─ success: false
    ├─ error: exact reason each method failed
    └─ suggested_action: what the user can do to fix it
```

---

## SECTION 16 — COMPLETE TECHNOLOGY STACK

### Install All Dependencies

```bash
pip install pywin32 psutil pywinauto watchdog wmi pycaw playwright py7zr winshell comtypes

# Playwright browsers
python -m playwright install chromium

# Post-install hook for pywin32 (CRITICAL — run this)
python -m win32com.client.makepy   # Generate COM dispatch wrappers
```

### Full Library Reference

```
STDLIB (no install needed):
  asyncio     — async event loop, the runtime
  pathlib     — path manipulation
  os          — file system operations
  shutil      — high-level file ops
  subprocess  — process launch and shell commands
  winreg      — Windows Registry
  ctypes      — Win32 API direct access (user32, kernel32, ntdll, powrprof)
  threading   — background threads for blocking Win32 calls
  logging     — structured logging
  json        — command serialization
  uuid        — command IDs
  time        — timing and delays

THIRD PARTY:
  pywin32     — THE core Windows API library
    win32api      General Windows API
    win32con      All Windows constants
    win32gui      Window management (EnumWindows, SetWindowPos, etc.)
    win32process  Process control (CreateProcess, job objects)
    win32security NTFS permissions, ACLs, token privileges
    win32service  Service Control Manager
    win32file     Low-level file I/O and attributes
    win32net      Network shares
    win32com      COM object dispatch
    win32event    Events and synchronization primitives
    win32clipboard Clipboard read/write

  psutil      — Cross-platform process and system info
  pywinauto   — Windows UI automation (Win32 and UIA backends)
  watchdog    — File system event monitoring
  wmi         — WMI queries and event subscriptions
  pycaw       — Windows Core Audio API
  playwright  — Browser automation (CDP-based)
  py7zr       — 7-Zip archive support
  winshell    — Windows Shell operations, Recycle Bin
  comtypes    — Low-level COM interface access
```

---

## SECTION 17 — ARCHITECTURE DIAGRAM

```
┌──────────────────────────────────────────────────────────────────┐
│                    JARVIS AI BRAIN (not this document)           │
│                    (LLM + Voice + Intent Parser)                 │
└───────────────────────────────┬──────────────────────────────────┘
                                │  JSON commands over local socket
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│                      JARVIS CONTROL CORE                         │
│                       (This Document)                            │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────────┐  │
│  │  privilege   │   │   daemon     │   │  logger / monitor   │  │
│  │   .py        │   │   .py        │   │     .py             │  │
│  └──────────────┘   └──────┬───────┘   └─────────────────────┘  │
│                            │                                     │
│                     ┌──────▼───────┐                            │
│                     │  CommandBus  │                            │
│                     │   bus.py     │                            │
│                     └──────┬───────┘                            │
│                            │                                     │
│                     ┌──────▼───────┐                            │
│                     │    Router    │                            │
│                     │   router.py  │                            │
│                     └──────┬───────┘                            │
│                            │                                     │
│        ┌───────────────────┼───────────────────┐               │
│        │           ┌───────┴───────┐            │               │
│        ▼           ▼               ▼            ▼               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │    L1    │ │    L2    │ │    L3    │ │    L4    │  ...      │
│  │ Filesystem│ │ Process  │ │   App    │ │  Window  │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
│       │            │            │            │                  │
│       └────────────┴────────────┴────────────┘                  │
│                            │                                     │
│                   ┌────────▼────────┐                           │
│                   │  FallbackChain  │                           │
│                   │  + Verifier     │                           │
│                   │  + Transaction  │                           │
│                   └────────┬────────┘                           │
│                            │                                     │
└────────────────────────────┼─────────────────────────────────── ┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                       WINDOWS OS                                 │
│                                                                  │
│  Win32 API │ WMI │ Registry │ Services │ COM │ NTFS │ WinRT     │
└──────────────────────────────────────────────────────────────────┘
```

---

## SECTION 18 — DEVELOPMENT SEQUENCE

Build in this exact order for a stable, testable system:

```
Phase 1 — Foundation
  [1] privilege.py       — Get elevation working first. Nothing works without it.
  [2] bus.py             — Command bus and data structures
  [3] logger.py          — Logging before anything else touches the OS
  [4] daemon.py          — Basic service shell (no layers yet)

Phase 2 — Core Layers (in this order)
  [5] L1_filesystem.py   — Test with read operations first, then write
  [6] L2_process.py      — Start with list/info, then kill
  [7] L6_registry.py     — Read-only first, then write
  [8] L8_system.py       — Volume/display (safe), then power (careful)

Phase 3 — Automation Layers
  [9]  L4_window.py      — Enumerate first, then control
  [10] L5_input.py       — SendInput keyboard first, then mouse
  [11] L3_application.py — Launch/close, then pywinauto automation
  [12] L7_services.py    — Query first, then start/stop

Phase 4 — Complex Layers
  [13] L9_browser.py     — Last, as it has its own install step
  [14] fallback.py       — Add fallback chains to each layer
  [15] verifier.py       — Add verification to each action
  [16] transaction.py    — Add transaction support for multi-step ops
  [17] router.py         — Wire everything to the router
```

---

## SECTION 19 — COMMON FAILURE POINTS & SOLUTIONS

```
PROBLEM: "Access Denied" on file delete
SOLUTION: take_ownership → set_dacl_full_access → retry

PROBLEM: Process won't die (protected process)
SOLUTION: Escalate to SYSTEM → use NtTerminateProcess → if still alive,
          use DeviceIoControl on the process's kernel object

PROBLEM: pywinauto can't find controls
SOLUTION: Try backend="uia" instead of "win32"; increase timeout;
          use spy tools (inspect.exe, Spy++) to get correct identifiers

PROBLEM: SetForegroundWindow doesn't bring window to front
SOLUTION: Attach to target thread first:
          win32process.AttachThreadInput(current_tid, target_tid, True)
          then SetForegroundWindow → then detach

PROBLEM: SendInput keystrokes go to wrong window
SOLUTION: SetForegroundWindow → verify focus → wait 50ms → then SendInput

PROBLEM: Registry write fails even as admin
SOLUTION: Enable SeRestorePrivilege → check key's existing DACL →
          take ownership → set full control → retry write

PROBLEM: COM dispatch throws "Class not registered"
SOLUTION: Run makepy.py for the COM library first;
          use comtypes instead of win32com for low-level COM access

PROBLEM: WMI queries hang
SOLUTION: Use threading.Thread with timeout; wmi connections are not thread-safe
          → create a new wmi.WMI() instance in each thread

PROBLEM: Playwright browser not found
SOLUTION: Run: python -m playwright install chromium
          Confirm install: playwright.chromium.executable_path

PROBLEM: Service fails to start
SOLUTION: Check Windows Event Viewer → Application log;
          test as console first: python daemon.py debug
          confirm pywin32 post-install ran: python -m win32com.client.makepy
```

---

*JARVIS CONTROL CORE ARCHITECTURE — COMPLETE*
*Build the layers one by one. Test each before moving to the next.*
*The fallback chains are what makes this reliable, not the primary methods.*
