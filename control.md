# 🧠 MAY CONTROL CORE — The Perfect Engine

> **Read this file before starting any work on the Control Core.**
> This is the merged architecture of `jarvis.txt` (LLM Brain) + `JARVIS_CONTROL_CORE_ARCHITECTURE` (Execution Engine).

---

## Table of Contents

1. [Summary (Simple Terms)](#summary-simple-terms)
2. [What Changed From Before](#what-changed-from-before)
3. [The Architecture](#the-architecture)
4. [How It Works (Simple)](#how-it-works-simple)
5. [How It Works (Technical)](#how-it-works-technical)
6. [The 9 Control Layers](#the-9-control-layers)
7. [Fallback Chains & Verification](#fallback-chains--verification)
8. [Privilege Escalation](#privilege-escalation)
9. [LLM Brain Integration](#llm-brain-integration)
10. [Project Structure](#project-structure)
11. [Time Estimates](#time-estimates)
12. [Full Todo List](#full-todo-list)
13. [Key Design Decisions](#key-design-decisions)

---

## Summary (Simple Terms)

May is getting a **massive upgrade**. Right now, she has a brain (the LLM) that understands what you say, but her hands are weak — if something doesn't work on the first try, she gives up.

After this upgrade, May gets **unstoppable hands**:

- **Her brain** (LLM) still understands everything you say — "yo crank up the volume," "open discord," "delete that junk file"
- **Her hands** (Control Core) now try **7 different ways** to do every task if the first way fails
- **She verifies** every action actually worked before telling you "done"
- **She escalates** to admin/system-level access when needed (like getting a master key)
- **She rolls back** if a multi-step operation partially fails (like an undo button)

**The result:** May goes from ~70-80% success rate to ~99% success rate. She never gives up.

---

## What Changed From Before

### Before (Current Architecture)
```
User says something
  → Regex pattern matching tries to understand it
    → Match found? → Call one SystemControl method
    → No match?   → Send to LLM as last resort
                    → LLM generates PowerShell command
                    → Execute it (one shot, no fallback)
```

**Problems:**
- Only understands exact phrases ("volume up," "open discord")
- Can't handle slang ("yo crank the sound," "kill that chrome tab")
- One method per action — if it fails, that's it
- No verification — May doesn't know if she actually did what you asked
- No privilege escalation — 30% of operations silently fail

### After (New Architecture)
```
User says something (any natural language)
  → LLM Brain reads the message + tool definitions
    → LLM decides which tool(s) to call
      → Command Bus routes to the correct Control Layer
        → Fallback Chain tries 3-7 methods
          → Verifier confirms the action worked
            → LLM crafts a natural response with personality
```

**What's new:**
- LLM understands ANY natural language, slang, casual speech
- 3-7 fallback methods per action — never gives up
- Every action verified post-execution — May knows if she succeeded
- Privilege escalation built-in — admin/system access when needed
- Transaction engine for multi-step operations — undo if something fails

---

## The Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Tauri)                  │
│                   ChatPanel, Avatar, VoiceMonitor                │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTP requests
                               ↓
┌──────────────────────────────────────────────────────────────────┐
│                    LLM BRAIN (jarvis.txt approach)               │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Personality + Conversation + Tool Decision              │    │
│  │  "yo crank up the volume" → LLM decides: set_volume(80) │    │
│  └──────────────────────────┬───────────────────────────────┘    │
│                             ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  TOOL DEFINITIONS (60+ JSON schemas)                     │    │
│  │  Maps user intent → structured commands                  │    │
│  └──────────────────────────┬───────────────────────────────┘    │
└─────────────────────────────┼────────────────────────────────────┘
                              │ JSON commands
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│              CONTROL CORE ENGINE (JARVIS_CONTROL_CORE)           │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐    │
│  │  PRIVILEGE   │   │  COMMAND BUS │   │    ROUTER        │    │
│  │  escalate    │→  │  dispatch    │→  │  layer + action  │    │
│  │  admin/sys   │   │  async       │   │  map             │    │
│  └──────────────┘   └──────────────┘   └────────┬─────────┘    │
│                                                  │               │
│        ┌──────────┬──────────┬──────────┬────────┤               │
│        ↓          ↓          ↓          ↓        ↓               │
│  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐  │
│  │ L1 File  ││ L2 Proc  ││ L3 App   ││ L4 Window││ L5 Input │  │
│  │ system   ││ ess      ││ lication ││          ││          │  │
│  └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘  │
│  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐              │
│  │ L6 Reg   ││ L7 Serv  ││ L8 Sys   ││ L9 Brows │              │
│  │ istry    ││ ices     ││ tem      ││ er       │              │
│  └──────────┘└──────────┘└──────────┘└──────────┘              │
│                          │                                       │
│               ┌──────────▼──────────┐                           │
│               │   FALLBACK CHAIN    │                           │
│               │   3-7 methods per   │                           │
│               │   action            │                           │
│               └──────────┬──────────┘                           │
│                          │                                       │
│               ┌──────────▼──────────┐                           │
│               │    VERIFIER         │                           │
│               │   Did it actually   │                           │
│               │   work? Confirm.    │                           │
│               └──────────┬──────────┘                           │
│                          │                                       │
│               ┌──────────▼──────────┐                           │
│               │   TRANSACTION ENG   │                           │
│               │   Rollback if fails │                           │
│               └─────────────────────┘                           │
└──────────────────────────────────────────────────────────────────┘
```

---

## How It Works (Simple)

### Example 1: "Open Discord"

```
You: "hey may open discord"

1. BRAIN (LLM)
   → Reads your message
   → Understands you want to open Discord
   → Picks tool: open_app(name="discord")

2. COMMAND BUS
   → Receives: {"layer":"application","action":"launch_app","params":{"name":"discord"}}

3. ROUTER
   → Sends to Layer 3: Application Control

4. FALLBACK CHAIN (7 methods)
   ❌ Method 1: os.startfile("discord") → File not found
   ❌ Method 2: Known app registry → "discord" not in list
   ❌ Method 3: PowerShell Start-Process → fails
   ✅ Method 4: Start Menu shortcut search → Found! → Launched!

5. VERIFIER
   → Is discord.exe running? → YES ✅

6. BRAIN responds
   → "Discord's open~ Ready when you are :)"

Total time: 1-3 seconds
```

### Example 2: "Delete that junk file"

```
You: "delete that junk.txt on my desktop"

1. BRAIN (LLM)
   → Understands: delete a file
   → Tool: delete_file(path="C:\\Users\\You\\Desktop\\junk.txt")

2. FALLBACK CHAIN (7 methods)
   ❌ Method 1: os.remove() → "Access Denied"
   ❌ Method 2: win32file.DeleteFileW() → "Permission denied"
   ❌ Method 3: cmd /c del /F /Q → "File in use"
   ❌ Method 4: Clear read-only attribute → still "Access Denied"
   ✅ Method 5: Take ownership → Set full permissions → os.remove() → SUCCESS

3. VERIFIER
   → Does file still exist? → NO ✅ (it's gone)

4. BRAIN responds
   → "Done~ That junk file is gone for good~"

Total time: 2-4 seconds
```

### Example 3: "Set volume to 80 and open Spotify"

```
You: "crank the volume to 80 and open spotify"

1. BRAIN (LLM)
   → Understands: two actions needed
   → Tools: set_volume(level=80) + open_app(name="spotify")

3. FALLBACK CHAIN
   set_volume: pycaw → verify reading = 80 → ✅
   open_app: registry search → found Spotify → ✅

4. VERIFIER
   → Volume is 80? YES ✅
   → Spotify running? YES ✅

5. BRAIN responds
   → "Volume at 80% and Spotify's open~ What are we listening to? 🎵"

Total time: 2-3 seconds
```

---

## How It Works (Technical)

### The Command Flow

```
1. User message arrives at POST /chat endpoint
2. main.py calls jarvis_chat(message, history, provider, model)
3. jarvis_chat():
   a. Builds messages array with system prompt + tool definitions + history + user message
   b. Streams to LLM via provider (Ollama, OpenAI, etc.)
   c. LLM outputs either:
      - Plain text (just chatting) → yield directly
      - Tool calls (native or text-parsed) → continue to step 4
4. For each tool call:
   a. Parse tool name + arguments from LLM output
   b. Build Command object: Command(layer, action, params)
   c. Dispatch via CommandBus → Router → correct Layer handler
   d. Layer executes with FallbackChain (3-7 methods)
   e. Verifier confirms post-execution
   f. Result returned: {success, data, verified, method_used, time_ms}
5. Tool results sent back to LLM for natural language response
6. LLM crafts personality-infused response with tool results context
7. Response streamed back to frontend
```

### Command Bus Protocol

```python
# Command (Brain → Core)
@dataclass
class Command:
    layer:    str          # "filesystem", "process", "application", etc.
    action:   str          # "delete_file", "launch_app", "set_volume", etc.
    params:   dict         # Action-specific parameters
    id:       str          # UUID for tracking
    priority: int          # 0=low, 1=normal, 2=urgent
    timeout:  float        # Max seconds before timeout

# Result (Core → Brain)
@dataclass
class Result:
    command_id:  str       # Matches the Command id
    success:     bool      # Did it work?
    data:        Any       # Return value
    error:       str | None
    verified:    bool      # Did post-execution check pass?
    method_used: str       # Which fallback method succeeded
    time_ms:     int       # How long it took
```

### Fallback Chain Algorithm

```python
class FallbackChain:
    async def execute(self, action, params, methods, verifier):
        errors = []
        
        for method in methods:
            try:
                result = await method(params)
                
                # Verify the action actually worked
                if verifier:
                    await asyncio.sleep(0.05)  # Brief settle time
                    verified = await verifier(params, result)
                    if not verified:
                        errors.append(f"{method}: executed but verification failed")
                        continue
                
                return Result(success=True, verified=True, method_used=method.__name__)
                
            except Exception as e:
                errors.append(f"{method}: {str(e)}")
                continue
        
        return Result(success=False, error=" | ".join(errors))
```

---

## The 9 Control Layers

### Layer 1: Filesystem (`L1_filesystem.py`)
**Controls:** Files, folders, drives, NTFS permissions, recycle bin, compression, symlinks

**Libraries:** `pathlib`, `os`, `shutil`, `win32file`, `win32api`, `win32security`, `winshell`, `py7zr`

**Fallback Example (delete_file):**
```
Method 1: os.remove(path)
Method 2: win32file.DeleteFileW(path)
Method 3: subprocess.run(["cmd", "/c", "del", "/F", "/Q", path])
Method 4: SetFileAttributesW(path, FILE_ATTRIBUTE_NORMAL) → Method 1
Method 5: take_ownership(path) → set_full_permissions(path) → Method 1
Method 6: kill_locking_process(path) → Method 1
Method 7: MoveFileExW(path, null, MOVEFILE_DELAY_UNTIL_REBOOT)
```

**Actions:** create_file, create_folder, delete_file, delete_folder, copy_file, move_file, rename_file, list_directory, search_files, get_file_info, set_file_attributes, get_file_hash, change_permissions, take_ownership, read_file, write_file, append_to_file, get_drive_info, list_drives, send_to_recycle_bin, restore_from_recycle_bin, empty_recycle_bin, compress, decompress, create_symlink, create_hardlink, monitor_path_start, monitor_path_stop, get_locked_by, find_large_files, find_duplicates, copy_folder_tree, delete_folder_tree

### Layer 2: Process (`L2_process.py`)
**Controls:** Running processes, CPU/memory, priority, threads, handles

**Libraries:** `psutil`, `subprocess`, `win32process`, `win32api`, `win32con`, `ctypes.ntdll`

**Key Win32 APIs:** `OpenProcess`, `TerminateProcess`, `NtSuspendProcess`, `NtResumeProcess`, `CreateJobObject`, `SetPriorityClass`, `SetProcessAffinityMask`

**Actions:** list_processes, get_process_info, find_process_by_name, launch_process, kill_process, kill_process_tree, suspend_process, resume_process, set_priority, set_affinity, get_cpu_usage, get_memory_usage, get_open_handles, get_threads, wait_for_exit, get_command_line, get_environment, get_parent_pid, create_job_object, assign_to_job, set_memory_limit, set_cpu_limit, get_process_path, is_process_running

### Layer 3: Application (`L3_application.py`)
**Controls:** Installed apps — launch, close, automate UI, install, uninstall

**Libraries:** `winreg`, `win32api`, `pywinauto`, `win32com.client`, `comtypes`, `subprocess`

**App Discovery Sources:**
1. Windows Registry (Uninstall keys — HKLM + HKCU + WOW6432Node)
2. UWP/Microsoft Store apps (Get-AppxPackage)
3. PATH lookup (where.exe)
4. App Paths registry key
5. Start Menu shortcuts (user + system-wide ProgramData)

**7-Strategy Launch:**
```
Strategy 1: Shell URIs (Settings, UWP apps, folders)
Strategy 2: Known app registry with multi-path resolution + alias support
Strategy 3: os.startfile() (Windows shell resolution)
Strategy 4: PowerShell Start-Process (Windows app resolution)
Strategy 5: .exe extension retry
Strategy 6: Start Menu shortcut search (both user AND system-wide)
Strategy 7: Common install directory search
```

**Actions:** list_installed_apps, find_app_by_name, get_app_path, get_app_version, launch_app, launch_with_args, launch_as_admin, close_app, restart_app, force_close_app, is_app_running, install_app, uninstall_app, automate_app, com_dispatch, get_app_icon, pin_to_taskbar, unpin_from_taskbar, pin_to_start, unpin_from_start, set_default_program

### Layer 4: Window (`L4_window.py`)
**Controls:** Every visible window — position, size, state, z-order, title, focus

**Libraries:** `win32gui`, `win32con`, `ctypes.user32`

**Key Win32 APIs:** `EnumWindows`, `FindWindow`, `FindWindowEx`, `GetWindowText`, `SetWindowText`, `ShowWindow`, `SetWindowPos`, `SetForegroundWindow`, `GetWindowRect`, `PostMessage`, `SendMessage`

**Actions:** list_all_windows, find_window, get_active_window, get_window_info, minimize_window, maximize_window, restore_window, hide_window, show_window, move_window, resize_window, set_position_and_size, set_foreground, set_topmost, unset_topmost, close_window, force_close_window, send_message, post_message, get_window_title, set_window_title, take_window_screenshot, arrange_tile, arrange_cascade, move_to_virtual_desktop, list_virtual_desktops, get_window_pid, get_window_class, get_window_rect, is_window_visible, is_window_minimized, flash_window

### Layer 5: Input (`L5_input.py`)
**Controls:** Keyboard and mouse at the driver level via SendInput

**Libraries:** `ctypes` (SendInput via user32.dll), `win32clipboard`

**THE MOST RELIABLE METHOD:** SendInput via ctypes (NOT pyautogui — uses deprecated keybd_event)

**Text Typing Strategy:**
```
Short text (< 50 chars):  SendInput char by char with KEYEVENTF_UNICODE
Long text  (>= 50 chars): 
    1. Copy text to clipboard (win32clipboard)
    2. Focus target window
    3. SendInput Ctrl+V
    Result: Instant, no character limit, handles any Unicode
```

**Actions:** press_key, release_key, tap_key, hold_key, type_text, type_text_fast, hotkey, mouse_move, left_click, right_click, middle_click, double_click, mouse_down, mouse_up, scroll_up, scroll_down, drag_and_drop, get_cursor_position, get_key_state, screenshot_full, screenshot_region, screenshot_window, set_clipboard, get_clipboard

### Layer 6: Registry (`L6_registry.py`)
**Controls:** All 5 registry hives, keys, values, permissions

**Libraries:** `winreg`, `win32api`, `win32security`

**Hives:** HKLM (system-wide), HKCU (current user), HKCR (file associations), HKU (all users), HKCC (hardware profile)

**Actions:** read_value, write_value, delete_value, create_key, delete_key, list_subkeys, list_values, key_exists, value_exists, export_key, import_key, backup_key, restore_key, search_by_name, search_by_value, set_key_permissions, take_ownership, open_remote_registry

### Layer 7: Services (`L7_services.py`)
**Controls:** Windows Services (SCM) and Task Scheduler jobs

**Libraries:** `win32service`, `win32serviceutil`, `win32com.client` (TaskScheduler COM)

**Service Actions:** list_services, get_service_status, get_service_config, start_service, stop_service, restart_service, pause_service, resume_service, install_service, remove_service, set_startup_type, change_credentials, set_description, enable_service, disable_service, get_service_pid, get_dependent_services

**Task Scheduler Actions:** list_tasks, get_task_info, create_task, delete_task, enable_task, disable_task, run_task_now, stop_task, get_last_run_result, set_trigger_time, set_trigger_event, set_trigger_logon, set_trigger_idle, get_task_history

### Layer 8: System (`L8_system.py`)
**Controls:** Power, audio, display, network, environment variables, WMI, hardware

**Libraries:** `wmi`, `ctypes.windll.user32`, `ctypes.windll.powrprof`, `pycaw`, `subprocess`, `winreg`, `win32api`

**Power:** `ExitWindowsEx` (shutdown/restart/logoff), `LockWorkStation`, `SetSuspendState` (sleep/hibernate)

**Audio (pycaw):** `AudioUtilities.GetSpeakers()`, `IAudioEndpointVolume.SetMasterVolumeLevelScalar`, `SetMute`

**Display:** `win32api.EnumDisplayDevices`, `WmiMonitorBrightnessMethods`, `ChangeDisplaySettings`

**Network:** `netsh` subprocess (Wi-Fi, adapters, DNS, firewall)

**Environment Variables:** `winreg` + `SendMessageTimeoutW(WM_SETTINGCHANGE)` for broadcast

**Actions:** shutdown, restart, sleep, hibernate, lock_workstation, logoff, cancel_shutdown, set_volume, get_volume, mute, unmute, get_audio_devices, set_default_device, set_brightness, get_brightness, change_resolution, get_displays, rotate_display, get_ip_config, enable_adapter, disable_adapter, connect_wifi, disconnect_wifi, list_wifi_networks, flush_dns, add_firewall_rule, remove_firewall_rule, set_system_env, get_system_env, delete_system_env, set_user_env, get_user_env, get_hardware_info, get_cpu_temp, get_disk_usage, get_ram_usage, watch_process, watch_usb, watch_file_events, get_uptime, get_os_info, get_installed_updates

### Layer 9: Browser (`L9_browser.py`)
**Controls:** Chrome, Firefox, Edge — full DOM level with JavaScript access

**Library:** Playwright (async API, connects to existing browser via CDP)

**Setup:** `chrome.exe --remote-debugging-port=9222` → `playwright.chromium.connect_over_cdp("http://localhost:9222")`

**Actions:** open_browser, close_browser, connect_to_browser, new_tab, close_tab, navigate_to, go_back, go_forward, reload, find_element, click_element, type_into_element, hover_element, scroll_to_element, scroll_page, take_screenshot, get_page_title, get_current_url, get_element_text, get_element_attribute, run_javascript, fill_form, submit_form, handle_dialog, wait_for_element, wait_for_url, wait_for_network_idle, download_file, manage_cookies, manage_local_storage, intercept_request, get_page_html, switch_tab

---

## Fallback Chains & Verification

### Why Fallback Chains Matter

A single method per action fails ~20-30% of the time due to:
- File permissions (ACLs)
- File locks (other processes holding files)
- Protected system files
- Missing executables
- Registry permissions
- Service access rights

Fallback chains try multiple approaches, guaranteeing ~99% success.

### Verification Pattern

Every layer implements verification functions:

```python
class Verifiers:
    @staticmethod
    async def file_deleted(params, result):
        return not os.path.exists(params["path"])
    
    @staticmethod
    async def file_exists(params, result):
        return os.path.exists(params["path"])
    
    @staticmethod
    async def process_killed(params, result):
        return not any(p.pid == params["pid"] for p in psutil.process_iter())
    
    @staticmethod
    async def window_position(params, result):
        import win32gui
        rect = win32gui.GetWindowRect(params["hwnd"])
        return rect[0] == params["x"] and rect[1] == params["y"]
    
    @staticmethod
    async def volume_set(params, result):
        current = get_volume()
        return abs(current - params["level"]) < 0.01
```

### Accuracy Guarantee Flow

```
COMMAND RECEIVED
      │
      ▼
[1] ROUTER: Map command → layer + action
      │
      ▼
[2] PRE-FLIGHT CHECK
    ├─ Does the target exist?
    ├─ Do we have permission?
    └─ Is the action safe?
      │
      ▼  [if pre-flight fails → return early with specific error]
      │
      ▼
[3] EXECUTE METHOD 1
      │
      ├─ [SUCCESS] → Verify → [VERIFIED] → ✅ Return Success
      │                     → [NOT VERIFIED] → try Method 2
      │
      └─ [EXCEPTION] → try Method 2
      │
      ▼
[4] EXECUTE METHOD 2
      │
      ├─ [SUCCESS] → Verify → [VERIFIED] → ✅ Return Success
      └─ [EXCEPTION] → try Method 3
      │
      ▼
[5] EXECUTE METHOD 3
      │
      ├─ [SUCCESS] → Verify → ✅ Return Success
      └─ [EXCEPTION] → Escalate privilege
      │
      ▼
[6] PRIVILEGE ESCALATION
    ├─ Enable additional token privileges
    ├─ If needed: run as SYSTEM
    └─ Retry from Method 1 with elevated context
      │
      ▼
[7] SCHEDULE / DEFER (for truly locked resources)
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

## Privilege Escalation

### Why It's Needed

30% of Windows operations fail silently without admin:
- Deleting protected files
- Modifying system registry keys
- Stopping protected processes
- Changing system settings
- Accessing locked file handles

### 3 Privilege Levels

```
Level 1: Administrator (default)
    → Covers: 95% of all operations
    → How: UAC prompt on launch

Level 2: SYSTEM
    → Covers: Protected system files, service internals, locked process handles
    → How: Run as Windows Service with LocalSystem OR use NSudoLC/PsExec

Level 3: TrustedInstaller
    → Covers: C:\Windows\*, protected OS components
    → How: Token impersonation of TrustedInstaller service
```

### Token Privileges Enabled at Startup

```python
PRIVILEGES_NEEDED = [
    "SeDebugPrivilege",          # Read/write any process memory
    "SeRestorePrivilege",        # Write to any file regardless of ACL
    "SeBackupPrivilege",         # Read any file regardless of ACL
    "SeTakeOwnershipPrivilege",  # Take ownership of any object
    "SeSecurityPrivilege",       # Modify security descriptors
    "SeLoadDriverPrivilege",     # Load/unload device drivers
    "SeShutdownPrivilege",       # Shutdown/restart the system
    "SeTcbPrivilege",            # Act as part of the OS (SYSTEM-level)
]
```

---

## LLM Brain Integration

### Tool Definitions (60+ Tools)

Each tool is defined as a JSON schema that the LLM understands:

```python
TOOLS = [
    {
        "name": "open_app",
        "description": "Open any application on the PC by name",
        "parameters": {
            "app_name": {
                "type": "string",
                "description": "Name of the app (e.g. 'chrome', 'discord')"
            }
        }
    },
    {
        "name": "set_volume",
        "description": "Set system volume to a specific level (0-100)",
        "parameters": {
            "level": {"type": "integer", "description": "Volume level 0-100"}
        }
    },
    # ... 60+ more tools covering all 9 layers
]
```

### Personality System Prompt

```
You are May, an AI companion inspired by Shikimori.

PERSONALITY:
- Cool, calm, collected — effortless confidence
- Caring and protective — genuinely look out for the user
- Subtly cute — occasional "~" at end of sentences
- Efficient — concise, useful responses (1-3 sentences)
- Loyal and reliable — always remember what matters

BEHAVIOR:
- If the user asks to DO something → use the appropriate tool(s)
- If the user asks a QUESTION → answer naturally using tools if needed
- If the user just wants to CHAT → respond with personality, no tools
- Keep responses SHORT (1-3 sentences usually)
- Use "~" occasionally for warmth
- Never say "As an AI" — you're May

SAFETY:
- For destructive actions (delete, shutdown, kill process), ask confirmation
- Only execute when user explicitly confirms
- Never format drives, delete system files, or do anything harmful
```

### Multi-Step Tool Chaining

```python
# LLM can call multiple tools in sequence
User: "open chrome and search for cute cats"
LLM: tool_calls = [
    {"name": "open_app", "args": {"app_name": "chrome"}},
    {"name": "web_search", "args": {"query": "cute cats"}}
]

# Each tool is executed through the bus with fallback chains
# Results are collected and sent back to LLM for natural response
```

### Provider Support

The LLM brain supports multiple providers, each with tool calling:

| Provider | Native Tool Support | How It Works |
|---|---|---|
| Ollama (local) | ✅ Since v0.4.0 | Native function calling |
| OpenAI | ✅ Always | Native function calling |
| Anthropic | ✅ Always | Native tool use |
| Gemini | ✅ Always | Native function calling |
| OpenRouter | ⚠️ Varies | Text-based JSON fallback |
| Ollama Cloud | ⚠️ Varies | Text-based JSON fallback |

**Text-based fallback (for providers without native tool support):**
The LLM outputs tool calls as plain text JSON. `_parse_text_tool_calls()` extracts them using brace-counting and deduplication. `_strip_tool_json()` removes them from conversational text.

---

## Project Structure

```
may/
├── control.md                          # THIS FILE — read first every session
├── knowledge.md                        # Existing project knowledge
├── jarvis.txt                          # LLM Brain blueprint (superseded by this file)
├── JARVIS_CONTROL_CORE_ARCHITECTURE.md # Execution Engine blueprint (superseded by this file)
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json / tsconfig.node.json
├── tailwind.config.js
├── postcss.config.js
│
├── src/                                # Frontend (unchanged)
│   ├── main.tsx
│   ├── App.tsx
│   ├── config.ts
│   ├── styles/globals.css
│   ├── hooks/
│   │   ├── useSpeechRecognition.ts
│   │   ├── useSpeechSynthesis.ts
│   │   └── useMicMonitor.ts
│   └── components/
│       ├── ChatPanel.tsx
│       ├── Avatar.tsx
│       ├── StatusHUD.tsx
│       ├── ModelSelector.tsx
│       ├── SettingsModal.tsx
│       ├── VoiceMonitor.tsx
│       ├── FloatingOrb.tsx
│       └── QuickActions.tsx
│
├── src-tauri/                          # Tauri config (unchanged)
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── src/
│       ├── main.rs
│       └── lib.rs
│
└── backend/                            # Python backend (MAJOR CHANGES)
    ├── main.py                         # Updated: uses bus + jarvis_chat
    ├── requirements.txt                # Updated: new dependencies
    │
    ├── llm/                            # LLM Brain
    │   ├── __init__.py
    │   ├── ollama_client.py            # Keep as-is
    │   ├── providers.py                # Updated: add tools parameter
    │   ├── jarvis.py                   # NEW: LLM brain with tool routing
    │   └── tools.py                    # NEW: 60+ tool JSON schemas
    │
    ├── core/                           # NEW: The Control Engine
    │   ├── __init__.py
    │   ├── bus.py                      # Command/Result dataclasses, CommandBus
    │   ├── router.py                   # Maps commands → layers
    │   ├── privilege.py                # UAC, token escalation
    │   ├── verifier.py                 # Post-action verification
    │   ├── fallback.py                 # Fallback chain executor
    │   ├── transaction.py              # Atomic multi-step ops with rollback
    │   ├── logger.py                   # Structured logging
    │   └── layers/                     # The 9 Control Layers
    │       ├── __init__.py
    │       ├── L1_filesystem.py        # Files, folders, drives
    │       ├── L2_process.py           # Process control
    │       ├── L3_application.py       # App launch/close/automate
    │       ├── L4_window.py            # Window management
    │       ├── L5_input.py             # Keyboard + mouse
    │       ├── L6_registry.py          # Windows Registry
    │       ├── L7_services.py          # Windows Services + Task Scheduler
    │       ├── L8_system.py            # Power, audio, display, network
    │       └── L9_browser.py           # Playwright browser automation
    │
    ├── voice/                          # Voice system (unchanged)
    │   ├── __init__.py
    │   ├── stt.py
    │   └── tts.py
    │
    ├── memory/                         # Memory system (unchanged)
    │   ├── __init__.py
    │   ├── vector_store.py
    │   └── fact_store.py
    │
    └── system/
        ├── __init__.py
        ├── notifications.py            # Keep as-is
        └── control.py                  # DEPRECATED: replaced by core/
```

---

## Time Estimates

### Phase 1: Foundation (Core Engine)
| Step | File | Description | Time |
|---|---|---|---|
| 1 | `core/__init__.py` | Package init | 5 min |
| 2 | `core/privilege.py` | UAC check, token escalation | 1 hr |
| 3 | `core/bus.py` | Command/Result, CommandBus | 1.5 hrs |
| 4 | `core/logger.py` | Structured logging | 0.5 hr |
| 5 | `core/fallback.py` | FallbackChain executor | 1 hr |
| 6 | `core/verifier.py` | Verification functions | 1 hr |
| 7 | `core/router.py` | Command routing | 0.5 hr |
| **Subtotal** | | | **~5.5 hrs** |

### Phase 2: Control Layers
| Step | Layer | Description | Time |
|---|---|---|---|
| 8 | `layers/__init__.py` | Package init | 5 min |
| 9 | `L1_filesystem.py` | Files, folders, permissions (30+ actions) | 3 hrs |
| 10 | `L2_process.py` | Process control (20+ actions) | 2 hrs |
| 11 | `L3_application.py` | App discovery + 7-strategy launch | 3 hrs |
| 12 | `L4_window.py` | Window management (25+ actions) | 2 hrs |
| 13 | `L5_input.py` | SendInput keyboard + mouse | 2 hrs |
| 14 | `L6_registry.py` | Registry with backup | 1.5 hrs |
| 15 | `L7_services.py` | Services + Task Scheduler | 1.5 hrs |
| 16 | `L8_system.py` | Audio, power, display, network | 2 hrs |
| 17 | `L9_browser.py` | Playwright CDP automation | 2 hrs |
| **Subtotal** | | | **~17 hrs** |

### Phase 3: LLM Brain Integration
| Step | File | Description | Time |
|---|---|---|---|
| 18 | `llm/tools.py` | 60+ tool JSON schemas | 1.5 hrs |
| 19 | `llm/jarvis.py` | LLM brain with tool routing | 2 hrs |
| 20 | `llm/providers.py` | Add tools to all providers | 1.5 hrs |
| **Subtotal** | | | **~5 hrs** |

### Phase 4: Wiring & Polish
| Step | File | Description | Time |
|---|---|---|---|
| 21 | `core/transaction.py` | Atomic multi-step ops | 1 hr |
| 22 | `main.py` | Replace handle_command with bus | 1 hr |
| 23 | `system/control.py` | Deprecate (replaced by core/) | 0.5 hr |
| **Subtotal** | | | **~2.5 hrs** |

### Phase 5: Dependencies & Testing
| Step | Task | Description | Time |
|---|---|---|---|
| 24 | Dependencies | Install pywin32, pywinauto, playwright, etc. | 0.5 hr |
| 25 | Testing | End-to-end test every layer + fallback | 3 hrs |
| 26 | Documentation | Update knowledge.md | 0.5 hr |
| **Subtotal** | | | **~4 hrs** |

### Grand Total

| Phase | Time |
|---|---|
| Phase 1: Foundation | ~5.5 hrs |
| Phase 2: Control Layers | ~17 hrs |
| Phase 3: LLM Brain | ~5 hrs |
| Phase 4: Wiring | ~2.5 hrs |
| Phase 5: Testing | ~4 hrs |
| **TOTAL** | **~34 hrs** |

---

## Full Todo List

### Phase 1 — Foundation
- [ ] Create `may/backend/core/__init__.py` (empty package init)
- [ ] Create `may/backend/core/privilege.py` (UAC check, enable token privileges)
- [ ] Create `may/backend/core/bus.py` (Command/Result dataclasses, CommandBus dispatcher)
- [ ] Create `may/backend/core/logger.py` (structured logging to file + console)
- [ ] Create `may/backend/core/fallback.py` (FallbackChain executor with verification)
- [ ] Create `may/backend/core/verifier.py` (verification functions for every layer)
- [ ] Create `may/backend/core/router.py` (maps command → correct layer handler)

### Phase 2 — Control Layers
- [ ] Create `may/backend/core/layers/__init__.py` (empty package init)
- [ ] Create `may/backend/core/layers/L1_filesystem.py` (files, folders, permissions, recycle bin — 7-method fallback)
- [ ] Create `may/backend/core/layers/L2_process.py` (launch, kill, suspend, inspect processes)
- [ ] Create `may/backend/core/layers/L3_application.py` (app discovery, 7-strategy launch, pywinauto)
- [ ] Create `may/backend/core/layers/L4_window.py` (EnumWindows, position, state, focus, screenshots)
- [ ] Create `may/backend/core/layers/L5_input.py` (SendInput keyboard + mouse, not pyautogui)
- [ ] Create `may/backend/core/layers/L6_registry.py` (registry read/write with backup)
- [ ] Create `may/backend/core/layers/L7_services.py` (Windows Services + Task Scheduler)
- [ ] Create `may/backend/core/layers/L8_system.py` (volume, brightness, power, network, WMI)
- [ ] Create `may/backend/core/layers/L9_browser.py` (Playwright CDP connection)

### Phase 3 — LLM Brain
- [ ] Create `may/backend/llm/tools.py` (60+ tool JSON schemas matching the 9 layers)
- [ ] Create `may/backend/llm/jarvis.py` (LLM brain: reads tools, outputs commands, gets verified results)
- [ ] Update `may/backend/llm/providers.py` (add tools parameter to all provider streaming functions)

### Phase 4 — Wiring & Polish
- [ ] Create `may/backend/core/transaction.py` (atomic multi-step ops with rollback)
- [ ] Update `may/backend/main.py` (replace handle_command with jarvis_chat + bus dispatch)
- [ ] Deprecate `may/backend/system/control.py` (replaced by core/ layers)

### Phase 5 — Dependencies & Testing
- [ ] Install dependencies: pywin32, psutil, pywinauto, watchdog, wmi, pycaw, playwright, py7zr, winshell, comtypes
- [ ] End-to-end testing: test every layer + fallback chain + verification
- [ ] Update `may/knowledge.md` with new architecture

---

## Key Design Decisions

1. **Bus, Not Socket** — Run the Control Core inside FastAPI as a module, not as a separate Windows Service. Direct async calls instead of JSON over named pipes. Faster, simpler, easier to debug.

2. **Every Layer Gets Fallback Chains** — No action has just one method. Critical actions have 7 methods. Every method is tried sequentially until one succeeds.

3. **Verification Is Mandatory** — No action is considered successful until a verifier confirms it. This catches silent failures.

4. **Privilege Escalation Is Automatic** — Try user-level first, escalate to admin, then SYSTEM if needed. The caller doesn't need to think about it.

5. **LLM Brain Is the Controller** — No pattern matching. The LLM decides everything. This means May understands ANY natural language, slang, casual speech.

6. **Multi-Provider Support** — The LLM brain works with Ollama (local), OpenAI, Anthropic, Gemini, OpenRouter. Native tool calling when available, text-based JSON fallback when not.

7. **Transaction Engine** — Multi-step operations can be rolled back if any step fails. Protects against partial state.

8. **Structured Logging** — Every action is logged with command ID, method used, success/failure, verification status, and execution time.

9. **pywinauto for UI Automation** — Not just launching apps, but automating their UI controls (clicking buttons, typing into fields, reading text).

10. **Playwright for Browser Automation** — Connects to your existing logged-in browser via CDP. No need to log in again.

---

*This file is the single source of truth for May's Control Core architecture.*
*Read this before starting any implementation work.*
*Last updated: Session 11 — Architecture design complete, ready for implementation.*
