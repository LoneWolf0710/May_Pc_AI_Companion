# 🤖 AI Agent Tools & Functions — Complete Reference

> **Purpose:** Comprehensive catalog of every tool, function, and capability across three computer-use AI agents — **OpenClaw**, **Hermes Agent**, and **May** — plus a prioritized roadmap of new tools to implement.
>
> **Date:** July 17, 2026

---

## Table of Contents

1. [Agent Architecture Comparison](#1-agent-architecture-comparison)
2. [OpenClaw — Tools & Functions](#2-openclaw--tools--functions)
3. [Hermes Agent — Tools & Functions](#3-hermes-agent--tools--functions)
4. [May — Current Tools (178 Tools)](#4-may--current-tools-178-tools)
5. [Gap Analysis — What May is Missing](#5-gap-analysis--what-may-is-missing)
6. [Proposed New Tools (55+ Tools)](#6-proposed-new-tools-55-tools)
7. [Implementation Priority Matrix](#7-implementation-priority-matrix)

---

## 1. Agent Architecture Comparison

### OpenClaw (Open Source, Local)

| Component | Technology |
|:---|:---|
| **Core** | Gateway process (long-lived daemon) |
| **Brain** | Any LLM (OpenAI, Anthropic, local) |
| **Browser Control** | Playwright (CDP) — isolated Chromium profile |
| **App Control** | Shell commands + MCP (Model Context Protocol) |
| **Perception** | Screenshots → Vision model analysis |
| **Memory** | Markdown files (SOUL.md, MEMORY.md, daily logs) |
| **Skills** | Instruction bundles (SKILL.md per domain) |
| **Proactive** | Heartbeat cron tasks, idle detection |
| **Communication** | Channel adapters (Telegram, WhatsApp, Slack) |

### Hermes Agent (Nous Research)

| Component | Technology |
|:---|:---|
| **Core** | cua-driver (background mode, non-intrusive) |
| **Brain** | Multi-provider LLM (Anthropic, OpenAI, Google, Ollama) |
| **App Control** | **Accessibility Tree** (UIAutomation/AX/AT-SPI) |
| **Perception** | UI element tree (role, name, automation_id) |
| **Memory** | Skills system (agentskills.io standard) |
| **Input** | Click, type, scroll, drag, keyboard combos |
| **Platform** | macOS (SkyLight SPI), Windows (UIAutomation), Linux (AT-SPI) |
| **Session** | Isolated sub-agents with virtual cursors |
| **Guardrails** | Command approval, dangerous key blocking, password protection |

### May (Your Project)

| Component | Technology |
|:---|:---|
| **Core** | 15-layer Control Core daemon (TCP bus :7650) |
| **Brain** | Dual Ollama (router + main) + 6 online providers |
| **App Control** | 10-strategy fallback chain + fuzzy matching + Everything search |
| **Perception** | Screenshots + Tier 4 vision + UIAccessibility (Tier 2) |
| **Memory** | LanceDB (vectors) + SQLite (facts) + JSON skills |
| **Input** | SendInput (ctypes) + clipboard paste + pywinauto |
| **Browser** | Playwright CDP (Chrome on port 9222) |
| **Security** | DPAPI encryption, risk classifier, immune system, audit log |
| **Intelligence** | Shadow learner, endocrine system, personality modes, conditioned reflexes |

---

## 2. OpenClaw — Tools & Functions

### 2.1 Browser Automation (Playwright)

| Tool | Function | Description |
|:---|:---|:---|
| `navigate` | `page.goto(url)` | Navigate to a URL |
| `click` | `page.click(selector)` | Click an element by CSS/XPath selector |
| `type` | `page.fill(selector, text)` | Type text into a form field |
| `scroll` | `page.mouse.wheel(delta)` | Scroll the page |
| `screenshot` | `page.screenshot()` | Capture page screenshot for vision analysis |
| `get_text` | `page.inner_text(selector)` | Extract text from elements |
| `evaluate` | `page.evaluate(js)` | Run JavaScript on the page |
| `wait_for` | `page.wait_for_selector(sel)` | Wait for element to appear |
| `manage_cookies` | `context.cookies()` | Get/set/delete cookies |
| `storage` | `context.storage_state()` | Save/load browser state |

### 2.2 System Control (Shell + MCP)

| Tool | Function | Description |
|:---|:---|:---|
| `shell` | `subprocess.run(cmd)` | Execute any shell command |
| `read_file` | `open(path).read()` | Read file contents |
| `write_file` | `open(path, 'w').write()` | Write file contents |
| `list_dir` | `os.listdir(path)` | List directory contents |
| `search_files` | `glob(pattern)` | Find files by pattern |
| `schedule_task` | cron/heartbeat | Schedule background tasks |

### 2.3 MCP Integrations

| Tool | Function | Description |
|:---|:---|:---|
| `mcp_tool_call` | MCP protocol | Call any MCP-compatible tool |
| `notion_*` | Notion MCP | Read/write Notion pages |
| `homeassistant_*` | HA MCP | Control smart home devices |
| `github_*` | GitHub MCP | Repository management |

### 2.4 Perception & Memory

| Tool | Function | Description |
|:---|:---|:---|
| `screenshot_analyze` | Vision model | Analyze screenshot with LLM vision |
| `memory_read` | Read MEMORY.md | Load persistent memory |
| `memory_write` | Append to MEMORY.md | Store facts and preferences |
| `skill_execute` | Run SKILL.md | Execute a learned procedure |

---

## 3. Hermes Agent — Tools & Functions

### 3.1 Accessibility Tree (Core Innovation)

| Tool | Function | Description |
|:---|:---|:---|
| `inspect_tree` | Read UIAutomation tree | Returns all UI elements with role, name, automation_id, bounding_rect |
| `find_element` | Query by role/name/automation_id | Find specific UI elements (Button, Edit, Menu, etc.) |
| `get_element_value` | Read element property | Get text/value/state of a UI element |

### 3.2 Input Actions (via cua-driver)

| Tool | Function | Description |
|:---|:---|:---|
| `click_element` | `element.Invoke()` | Click a UI element by reference |
| `type_text` | `element.Value = text` | Type into a text field element |
| `select_option` | `ComboBox.Select()` | Select dropdown option |
| `toggle_checkbox` | `CheckBox.Toggle()` | Check/uncheck a checkbox |
| `scroll_element` | `ScrollPattern.Scroll()` | Scroll within a scrollable element |
| `mouse_click` | `SendInput(MOUSEEVENTF)` | Click at screen coordinates |
| `mouse_move` | `SendInput(MOUSEEVENTF_MOVE)` | Move cursor |
| `mouse_scroll` | `SendInput(MOUSEEVENTF_WHEEL)` | Scroll wheel |
| `key_press` | `SendInput(KEYEVENTF)` | Press a key |
| `key_combo` | `SendInput(multiple)` | Key combination (Ctrl+C, etc.) |
| `drag` | `SendInput(DRAG)` | Drag from point A to B |

### 3.3 Platform-Specific Drivers

| Platform | Driver | API |
|:---|:---|:---|
| **Windows** | `cua-driver` | UIAutomation (IUIAutomation) |
| **macOS** | `cua-driver` | SkyLight SPI + AX (NSAccessibility) |
| **Linux** | `cua-driver` | AT-SPI2 (D-Bus) |

### 3.4 Safety & Guardrails

| Tool | Function | Description |
|:---|:---|:---|
| `command_approval` | HITL gate | Pause for user approval on destructive actions |
| `block_dangerous_keys` | Filter | Prevent Alt+F4, Win+L, Ctrl+Alt+Delete |
| `password_protection` | Masking | Never type passwords via automation |
| `computer_use_doctor` | Diagnostics | Check accessibility permissions and driver health |

### 3.5 Learning System

| Tool | Function | Description |
|:---|:---|:---|
| `skill_store` | Save trajectory | Store successful action sequences |
| `skill_replay` | Replay learned | Execute previously learned procedures |
| `trajectory_track` | History | Track past actions for refinement |

---

## 4. May — Current Tools (178 Tools)

### 4.1 App Control (12 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `open_app` | L3 | Open any app by name (10-strategy fallback chain) |
| `close_app` | L3 | Close app gracefully (psutil → taskkill → UWP → force) |
| `force_close_app` | L3 | Force-kill an application |
| `launch_with_args` | L3 | Launch app with command-line arguments |
| `launch_as_admin` | L3 | Launch with elevated (admin) privileges |
| `restart_app` | L3 | Kill then re-launch an application |
| `is_app_running` | L3 | Check if an app is currently running |
| `automate_app` | L3 | pywinauto automation (connect, click, type, close) |
| `com_dispatch` | L3 | COM object automation (Office apps) |
| `find_app_by_name` | L3 | Search for installed apps via winget |
| `list_installed_apps` | L3 | List all installed applications |
| `get_app_path` | L3 | Get installation path from registry |
| `get_app_version` | L3 | Get app version from registry |

**10-Strategy Launch Chain:**
1. Everything search (NTFS index, <1ms)
2. Shell URIs (UWP/Store apps)
3. Known app registry (45+ apps with exact paths)
4. Fuzzy match (6-strategy: exact, prefix, abbreviation, substring, Levenshtein, token overlap)
5. os.startfile()
6. PowerShell Start-Process
7. .exe extension retry
8. Start Menu shortcut search
9. Windows registry search (Uninstall keys)
10. Common install directory search

### 4.2 File Operations (22 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `read_file` | L1 | Read text file contents |
| `write_file` | L1 | Write content to file (creates dirs) |
| `list_directory` | L1 | List directory contents with sizes |
| `search_files` | L1 | Search files by glob pattern |
| `search_content` | L1 | Search text inside files (grep) |
| `find_and_replace` | L1 | Find and replace text in file |
| `copy_file` | L1 | Copy file to destination |
| `move_file` | L1 | Move or rename file |
| `delete_file` | L1 | Delete file (recycle bin if available) |
| `get_file_info` | L1 | Get file metadata (size, dates, type) |
| `open_folder` | L1 | Open folder in File Explorer |
| `get_folder_size` | L1 | Calculate total folder size |
| `get_large_files` | L1 | Find large files for cleanup |
| `batch_rename` | L1 | Rename files by pattern |
| `batch_delete` | L1 | Delete files by glob pattern |
| `open_file_with` | L1 | Open file with specific app |
| `take_ownership` | L1 | Take ownership of file/folder |
| `find_duplicates` | L1 | Find duplicate files by hash |
| `compress_file` | L1 | Compress to .7z archive |
| `decompress_file` | L1 | Extract .7z archive |
| `create_folder` | L1 | Create directory |
| `copy_folder` | L1 | Recursively copy folder tree |
| `delete_folder` | L1 | Recursively delete folder |
| `get_drive_info` | L1 | Get drive space info |

### 4.3 Web & Search (3 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `web_search` | L9 | Search the web (DuckDuckGo) |
| `open_url` | L9 | Open URL in default browser |
| `extract_web_content` | L9 | Fetch and extract readable text from URL |

### 4.4 Process Management (6 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `list_processes` | L2 | List top processes by CPU/memory |
| `kill_process` | L2 | Kill process by name |
| `get_process_info` | L2 | Get detailed process info |
| `set_process_priority` | L2 | Set process priority |
| `get_command_line` | L2 | Get process command line args |
| `is_process_running` | L2 | Check if process is running |
| `get_process_cpu` | L2 | Get process CPU usage |
| `get_process_memory` | L2 | Get process memory usage |
| `get_process_path` | L2 | Get executable path |
| `set_process_affinity` | L2 | Set CPU core affinity |
| `set_memory_limit` | L2 | Limit process memory |
| `set_cpu_limit` | L2 | Limit process CPU % |

### 4.5 Media Control (4 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `media_play_pause` | L11 | Toggle play/pause |
| `media_next` | L11 | Next track |
| `media_previous` | L11 | Previous track |
| `media_stop` | L11 | Stop playback |
| `get_active_audio` | L11 | Get currently playing info |
| `set_per_app_volume` | L11 | Set volume for specific app |
| `list_audio_endpoints` | L11 | List audio devices |

### 4.6 Keyboard & Mouse Input (6 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `send_keys` | L5 | Send keyboard shortcut (Ctrl+C, Alt+Tab, etc.) |
| `type_text` | L5 | Type text into focused window |
| `type_text_fast` | L5 | Type via clipboard paste (any length/Unicode) |
| `mouse_click` | L5 | Click at screen coordinates |
| `mouse_scroll` | L5 | Scroll mouse wheel |
| `drag_and_drop` | L5 | Drag from (x1,y1) to (x2,y2) |
| `tap_key` | L5 | Quick press/release single key |
| `hold_key` | L5 | Hold key for duration |
| `get_mouse_position` | L5 | Get cursor position |

**Input Methods:**
- **SendInput** via ctypes (NOT pyautogui) — most reliable, cannot be blocked
- **KEYEVENTF_UNICODE** for character input
- **Clipboard paste** for long text (>50 chars)
- **VK code map** for 30+ special keys

### 4.7 Window Management (8 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `list_windows` | L4 | List all visible windows |
| `focus_window` | L4 | Bring window to foreground |
| `minimize_window` | L4 | Minimize window |
| `maximize_window` | L4 | Maximize window |
| `resize_window` | L4 | Resize window to dimensions |
| `flash_window` | L4 | Flash window in taskbar |
| `find_window` | L4 | Find window by title |
| `set_window_position` | L4 | Set position and size |
| `close_window` | L4 | Close window by title |
| `get_window_title` | L4 | Get active window title |
| `arrange_windows` | L4 | Tile or cascade windows |
| `set_topmost` | L4 | Set always on top |
| `hide_window` | L4 | Hide window |
| `show_window` | L4 | Show hidden window |
| `get_window_info` | L4 | Get full window metadata |
| `get_window_class` | L4 | Get window class name |
| `is_window_visible` | L4 | Check visibility |
| `is_window_minimized` | L4 | Check minimized state |
| `take_window_screenshot` | L4 | Screenshot specific window |
| `list_virtual_desktops` | L4 | List virtual desktops |
| `move_to_virtual_desktop` | L4 | Move window to desktop |

**Focus Methods (3 strategies):**
1. `SetForegroundWindow` (direct)
2. Alt key trick (brief Alt press unlocks foreground)
3. `BringWindowToTop` + `SetForegroundWindow`

### 4.8 System Control (9 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `screenshot` | L8 | Take screenshot |
| `screenshot_full` | L8 | Full screen capture |
| `screenshot_region` | L8 | Capture screen region |
| `describe_screen` | L8 | Screenshot + vision model description |
| `system_info` | L8 | OS, CPU, RAM, disk, uptime |
| `battery_info` | L8 | Battery status and percentage |
| `disk_info` | L8 | Disk usage for all drives |
| `shutdown_pc` | L8 | Shut down PC |
| `restart_pc` | L8 | Restart PC |
| `sleep_pc` | L8 | Put PC to sleep |
| `lock_pc` | L8 | Lock workstation |
| `logoff` | L8 | Log off user |
| `cancel_shutdown` | L8 | Cancel pending shutdown |
| `get_os_info` | L8 | Detailed OS information |
| `get_installed_updates` | L8 | List Windows updates |
| `rotate_display` | L8 | Rotate screen orientation |
| `enable_dark_mode` | L8 | Enable dark mode |
| `enable_light_mode` | L8 | Enable light mode |
| `get_audio_devices` | L8 | List audio playback devices |

### 4.9 Network (8 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `get_network_info` | L10 | IP addresses, WiFi, adapters |
| `get_public_ip` | L10 | External IP address |
| `get_wifi_password` | L10 | Saved WiFi passwords |
| `test_internet` | L10 | Internet connectivity test |
| `connect_wifi` | L10 | Connect to WiFi network |
| `disconnect_wifi` | L10 | Disconnect from WiFi |
| `flush_dns` | L10 | Flush DNS cache |
| `add_firewall_rule` | L10 | Add firewall rule |
| `enable_adapter` | L10 | Enable network adapter |
| `disable_adapter` | L10 | Disable network adapter |
| `list_wifi_networks` | L10 | Scan available WiFi networks |

### 4.10 Browser Automation (12 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `browser_navigate` | L9 | Navigate to URL via Playwright CDP |
| `browser_click` | L9 | Click element by CSS selector |
| `browser_type` | L9 | Type into form field |
| `browser_fill_form` | L9 | Fill multiple fields at once |
| `browser_get_text` | L9 | Extract text from element |
| `browser_screenshot` | L9 | Screenshot current page |
| `browser_run_js` | L9 | Execute JavaScript on page |
| `browser_wait_for` | L9 | Wait for element to appear |
| `browser_manage_cookies` | L9 | Get/set/delete cookies |
| `open_browser` | L9 | Launch new browser instance |
| `close_browser` | L9 | Close browser instance |
| `handle_dialog` | L9 | Accept/dismiss JS dialogs |
| `connect_to_browser` | L9 | Connect via CDP |

### 4.11 Volume & Display (10 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `set_volume` | L8 | Set volume (0-100) |
| `get_volume` | L8 | Get current volume |
| `volume_up` | L8 | Increase volume 15% |
| `volume_down` | L8 | Decrease volume 15% |
| `mute` | L8 | Mute audio |
| `unmute` | L8 | Unmute audio |
| `set_brightness` | L8 | Set brightness (0-100) |
| `get_brightness` | L8 | Get current brightness |
| `enable_dark_mode` | L8 | Enable dark mode |
| `enable_light_mode` | L8 | Enable light mode |

### 4.12 Clipboard (2 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `copy_to_clipboard` | L5 | Copy text to clipboard |
| `get_clipboard` | L5 | Get text from clipboard |

### 4.13 Email (6 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `get_unread_emails` | Integration | Get unread inbox emails |
| `get_unread_count` | Integration | Count unread emails |
| `search_emails` | Integration | Search by subject |
| `read_email` | Integration | Read full email by UID |
| `send_email` | Integration | Send email |
| `get_recent_emails` | Integration | Get recent emails |

### 4.14 Services (5 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `list_services` | L7 | List Windows services |
| `start_service` | L7 | Start a service |
| `stop_service` | L7 | Stop a service |
| `restart_service` | L7 | Restart a service |
| `set_service_startup` | L7 | Set startup type |
| `enable_service` | L7 | Enable service |
| `disable_service` | L7 | Disable service |

### 4.15 Registry (6 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `read_registry` | L6 | Read registry value |
| `write_registry` | L6 | Write registry value |
| `delete_registry` | L6 | Delete registry key |
| `list_registry_keys` | L6 | List subkeys |
| `search_registry` | L6 | Search registry |
| `export_registry` | L6 | Export registry to file |

### 4.16 Reminders (1 Tool)

| Tool | Layer | Description |
|:---|:---|:---|
| `set_reminder` | Integration | Set timed reminder with toast notification |

### 4.17 Wellness (3 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `get_wellness_status` | Intelligence | Session duration, rules, suggestions |
| `get_wellness_suggestions` | Intelligence | Pending wellness suggestions |
| `set_wellness_rule` | Intelligence | Enable/disable wellness rules |

### 4.18 Meeting Mode (3 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `start_meeting` | Integration | Start recording + transcribing |
| `stop_meeting` | Integration | Stop and generate summary |
| `meeting_status` | Integration | Check recording status |

### 4.19 Ghost Mode (4 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `queue_ghost_task` | Intelligence | Queue autonomous task |
| `ghost_status` | Intelligence | Check task queue status |
| `cancel_ghost_task` | Intelligence | Cancel queued task |
| `cancel_all_ghost_tasks` | Intelligence | Cancel all tasks |

### 4.20 Voice Biometrics (5 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `voice_enroll` | Voice | Enroll voice profile |
| `voice_verify` | Voice | Verify speaker |
| `biometrics_status` | Voice | Check enrollment status |
| `biometrics_toggle` | Voice | Toggle biometrics |
| `biometrics_delete` | Voice | Delete voice profile |

### 4.21 Skills (4 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `execute_skill` | Intelligence | Execute learned procedure |
| `list_skills` | Intelligence | List all learned skills |
| `search_skills` | Intelligence | Search skills by query |
| `delete_skill` | Intelligence | Delete a skill |

### 4.22 Package Management (2 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `install_app` | L7 | Install via winget |
| `search_packages` | L7 | Search available packages |

### 4.23 Environment Variables (2 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `get_env_var` | L8 | Get env variable value |
| `list_env_vars` | L8 | List all env variables |
| `delete_system_env` | L8 | Delete env variable |

### 4.24 Weather (1 Tool)

| Tool | Layer | Description |
|:---|:---|:---|
| `get_weather` | Integration | Current weather (Open-Meteo API) |

### 4.25 Time & Date (2 Tools)

| Tool | Layer | Description |
|:---|:---|:---|
| `get_time` | L8 | Get current time |
| `get_date` | L8 | Get today's date |

### 4.26 PowerShell (1 Tool)

| Tool | Layer | Description |
|:---|:---|:---|
| `run_powershell` | L8 | Execute any PowerShell command |

### 4.27 Settings (1 Tool)

| Tool | Layer | Description |
|:---|:---|:---|
| `open_settings` | L8 | Open Windows Settings page |

---

## 5. Gap Analysis — What May is Missing

### 🔴 Critical Gaps (vs Hermes Agent)

| Gap | Hermes Approach | May Status | Impact |
|:---|:---|:---|:---|
| **Accessibility Tree Reading** | Reads UIAutomation tree for ANY app — finds buttons, menus, inputs by role/name/automation_id | ❌ Not implemented | **Cannot interact with UI elements by name.** Must use coordinates or window titles. |
| **Background Non-Intrusive Mode** | cua-driver runs in background, never steals focus | ❌ Always requires foreground focus | **Cannot operate while user is working.** |
| **Per-Element Interaction** | Click/type specific UI elements by reference | ❌ Only window-level focus + clipboard paste | **Fragile for complex apps.** |
| **Platform Accessibility Stacks** | Native UIAutomation (Win), AX (macOS), AT-SPI (Linux) | Partial (pywinauto exists but not integrated) | **pywinauto is available but not wired into the main control loop.** |
| **Structured Health Reporting** | `computer_use_doctor` checks permissions/drivers | ❌ No diagnostic tool | **Cannot self-diagnose issues.** |

### 🟡 Important Gaps (vs OpenClaw)

| Gap | OpenClaw Approach | May Status | Impact |
|:---|:---|:---|:---|
| **Post-Action Screenshot Verification** | Screenshot → vision model → verify expected outcome | ❌ No verification loop | **Actions may silently fail.** |
| **MCP Protocol** | Standard tool schema for all integrations | ❌ Custom JSON schemas | **Cannot use MCP-compatible tools.** |
| **Proactive Heartbeat** | Cron-like background task checking | Partial (Ghost Mode exists) | **Could be more proactive.** |
| **Skill Bundles** | SKILL.md instruction files per domain | Partial (skill_store exists) | **Could be more structured.** |

### 🟢 Minor Gaps

| Gap | Description |
|:---|:---|
| **Clipboard Image Support** | Can only copy/get text, not images |
| **OCR as Primary Tool** | EasyOCR exists but not exposed as LLM-callable tool |
| **Scheduled Tasks** | No Task Scheduler integration |
| **Startup Programs** | No startup program management |
| **Git Operations** | No git tools (clone, status, commit, push) |
| **Code Execution** | No sandboxed code execution |
| **HTTP Client** | No direct HTTP request tool (only via PowerShell) |
| **Timer/Stopwatch** | No countdown timer or stopwatch |
| **Calculator** | No math expression evaluator |
| **Unit Converter** | No unit conversion tool |

---

## 6. Proposed New Tools (55+ Tools)

### 🔴 Priority 1: Computer-Use Agent (Hermes-Level)

These tools bring May to parity with Hermes Agent's accessibility tree approach.

#### 6.1 Accessibility Tree Tools

| # | Tool | Parameters | Returns | Description |
|:---|:---|:---|:---|:---|
| 1 | **`inspect_ui_tree`** | `window_title?`, `max_depth?` | `{elements: [{role, name, automation_id, bounding_rect, children_count, is_enabled, is_focusable}]}` | Read the Windows UIAutomation tree for any window. Returns all UI elements with their role (Button, Edit, Menu, etc.), name, automation ID, and bounding rectangle. This is Hermes' secret sauce — enables finding UI elements by structure, not coordinates. |
| 2 | **`find_ui_element`** | `window_title`, `role?`, `name?`, `automation_id?` | `{element: {role, name, automation_id, bounding_rect, children}}` | Find a specific UI element by role + name or automation_id. Returns the element reference for clicking/typing. |
| 3 | **`click_ui_element`** | `window_title`, `role`, `name` | `{clicked: true, element: {role, name, bounding_rect}}` | Click a UI element found via inspect_ui_tree. Finds element by role+name, scrolls into view if needed, then clicks center of bounding rect. |
| 4 | **`double_click_ui_element`** | `window_title`, `role`, `name` | `{double_clicked: true}` | Double-click a UI element (for opening files, selecting words, etc.) |
| 5 | **`right_click_ui_element`** | `window_title`, `role`, `name` | `{right_clicked: true}` | Right-click a UI element (for context menus) |
| 6 | **`type_into_ui_element`** | `window_title`, `role`, `name`, `text`, `clear_first?` | `{typed: true, text: "..."}` | Type text into a specific UI input element. Clears field first if `clear_first=true`. More reliable than clipboard paste for form fields. |
| 7 | **`select_ui_dropdown`** | `window_title`, `role`, `name`, `option_text` | `{selected: true, option: "..."}` | Select an option from a ComboBox/dropdown by visible text. |
| 8 | **`toggle_ui_checkbox`** | `window_title`, `role`, `name` | `{toggled: true, new_state: true/false}` | Check/uncheck a checkbox element. |
| 9 | **`read_ui_text`** | `window_title`, `role?`, `name?` | `{text: "...", elements: [...]}` | Read all visible text from a UI element subtree. Useful for reading menus, panels, dialogs. |
| 10 | **`set_ui_value`** | `window_title`, `role`, `name`, `value` | `{set: true}` | Set the value of a UI element (slider, textbox, etc.) |
| 11 | **`get_ui_state`** | `window_title`, `role`, `name` | `{is_enabled, is_focusable, value, toggle_state}` | Get the current state of a UI element. |

#### 6.2 Post-Action Verification Tools

| # | Tool | Parameters | Returns | Description |
|:---|:---|:---|:---|:---|
| 12 | **`take_action_verify`** | `expected_outcome?`, `window_title?` | `{verified: true, screenshot_path, description, matches_expected: true}` | Take a screenshot after any tool execution, run vision model, verify the expected outcome. Catches cases where action appeared to succeed but didn't (wrong window, popup blocked, etc.). |
| 13 | **`verify_element_exists`** | `window_title`, `role`, `name` | `{exists: true, visible: true}` | Verify a UI element exists and is visible (e.g., after clicking Save, verify the "Saved" dialog appeared). |
| 14 | **`verify_no_error`** | `window_title?` | `{has_error: false, error_text: null}` | Check that no error dialogs or popups appeared after an action. |

#### 6.3 Screen Reading Tools

| # | Tool | Parameters | Returns | Description |
|:---|:---|:---|:---|:---|
| 15 | **`ocr_screen_region`** | `x`, `y`, `x2`, `y2` | `{text: "...", confidence: 0.95}` | Extract text from a screen region via EasyOCR. Useful for apps that don't support accessibility (games, remote desktop, PDF viewers). |
| 16 | **`ocr_full_screen`** | — | `{text: "...", regions: [...]}` | OCR the entire screen and return all detected text with bounding boxes. |
| 17 | **`ocr_image_file`** | `path` | `{text: "...", confidence: 0.95}` | Extract text from an image file via OCR. |

### 🟡 Priority 2: Reliability & Self-Healing

| # | Tool | Parameters | Returns | Description |
|:---|:---|:---|:---|:---|
| 18 | **`wait_for_app`** | `app_name`, `timeout?` (default 15s) | `{ready: true, window_title: "..."}` | Wait for an app to finish launching by polling for its window. Prevents type_text failures from apps not being ready. |
| 19 | **`wait_for_element`** | `window_title`, `role`, `name`, `timeout?` (default 10s) | `{found: true, element: {...}}` | Wait for a UI element to appear before clicking. Prevents "element not found" errors. |
| 20 | **`wait_for_text`** | `window_title`, `text`, `timeout?` | `{found: true}` | Wait for specific text to appear in a window (e.g., "Loading complete"). |
| 21 | **`retry_on_failure`** | `tool_name`, `tool_args`, `max_retries?` (default 3), `backoff?` | `{success: true, attempts: 2, result: {...}}` | Wrap any tool call with automatic retry (exponential backoff). Handles transient failures. |
| 22 | **`get_active_app`** | — | `{app_name: "chrome", window_title: "Gmail - Chrome", pid: 1234}` | Get the currently focused app name + window title. Context for pronoun resolution. |
| 23 | **`list_app_windows`** | `app_name` | `{windows: [{title, hwnd, pid, is_visible}]}` | List all windows for a specific app (Chrome tab 1, tab 2, etc.). |
| 24 | **`find_app_window`** | `app_name`, `title_contains?` | `{hwnd, title, pid}` | Find the specific window for an app (e.g., "Chrome - Gmail" vs "Chrome - YouTube"). |
| 25 | **`compare_screenshots`** | `path1`, `path2` | `{changed: true, difference_percent: 15.3, description: "..."}` | Compare two screenshots to detect changes (before/after action). |

### 🟢 Priority 3: System Automation

| # | Tool | Parameters | Returns | Description |
|:---|:---|:---|:---|:---|
| 26 | **`list_scheduled_tasks`** | `filter?` | `{tasks: [{name, status, next_run, trigger}]}` | List Windows Task Scheduler tasks. |
| 27 | **`create_scheduled_task`** | `name`, `command`, `trigger` (daily/weekly/once), `time?` | `{created: true, task_id: "..."}` | Create a scheduled task. |
| 28 | **`delete_scheduled_task`** | `name` | `{deleted: true}` | Delete a scheduled task. |
| 29 | **`list_startup_programs`** | — | `{programs: [{name, path, enabled}]}` | List programs that run at startup. |
| 30 | **`enable_startup_program`** | `name`, `path` | `{enabled: true}` | Add program to startup. |
| 31 | **`disable_startup_program`** | `name` | `{disabled: true}` | Remove program from startup. |
| 32 | **`list_recent_files`** | `max_items?` (default 20) | `{files: [{name, path, last_modified}]}` | Get recently opened/modified files. |
| 33 | **`clipboard_history`** | `max_items?` | `{items: [{text, timestamp}]}` | Access Windows clipboard history (Win+V). |
| 34 | **`clipboard_image_get`** | — | `{image_base64: "...", width, height}` | Get image from clipboard as base64. |
| 35 | **`clipboard_image_set`** | `path` | `{set: true}` | Set image to clipboard from file. |
| 36 | **`create_restore_point`** | `description?` | `{created: true, restore_point_id: "..."}` | Create Windows system restore point. |
| 37 | **`list_user_accounts`** | — | `{accounts: [{name, status, last_login}]}` | List Windows user accounts. |
| 38 | **`toggle_airplane_mode`** | `enable` | `{airplane_mode: true/false}` | Toggle airplane mode. |
| 39 | **`toggle_bluetooth`** | `enable` | `{bluetooth: true/false}` | Toggle Bluetooth. |
| 40 | **`set_wallpaper`** | `path` | `{set: true}` | Set desktop wallpaper. |
| 41 | **`get_running_time`** | — | `{uptime: "3d 5h 23m", boot_time: "..."}` | Get system uptime. |

### 🔵 Priority 4: Developer Tools

| # | Tool | Parameters | Returns | Description |
|:---|:---|:---|:---|:---|
| 42 | **`git_clone`** | `url`, `destination?` | `{cloned: true, path: "..."}` | Clone a git repository. |
| 43 | **`git_status`** | `path?` | `{branch, ahead, behind, modified: [...], untracked: [...]}` | Get git status. |
| 44 | **`git_diff`** | `path?`, `file?` | `{diff: "..."}` | Get git diff. |
| 45 | **`git_commit`** | `message`, `path?`, `add_all?` | `{committed: true, hash: "abc123"}` | Stage and commit changes. |
| 46 | **`git_push`** | `remote?`, `branch?` | `{pushed: true}` | Push to remote. |
| 47 | **`git_pull`** | `remote?`, `branch?` | `{pulled: true, files_changed: 5}` | Pull from remote. |
| 48 | **`run_code`** | `language` (python/js/powershell), `code`, `timeout?` | `{output: "...", error: null, exit_code: 0}` | Execute code in a sandboxed subprocess. |
| 49 | **`http_request`** | `method`, `url`, `headers?`, `body?`, `timeout?` | `{status: 200, headers: {...}, body: "..."}` | Make HTTP requests (GET/POST/PUT/DELETE). |
| 50 | **`docker_list`** | `type?` (containers/images) | `{items: [{id, name, status, image}]}` | List Docker containers/images. |
| 51 | **`docker_start`** | `name_or_id` | `{started: true}` | Start Docker container. |
| 52 | **`docker_stop`** | `name_or_id` | `{stopped: true}` | Stop Docker container. |
| 53 | **`database_query`** | `db_path`, `query` | `{columns: [...], rows: [...], row_count: 5}` | Query SQLite databases. |
| 54 | **`port_scan`** | `host`, `ports?` (default: common ports) | `{open: [80, 443], closed: [22, 8080]}` | Scan ports on a host. |

### 🟣 Priority 5: AI & Content Tools

| # | Tool | Parameters | Returns | Description |
|:---|:---|:---|:---|:---|
| 55 | **`summarize_text`** | `text`, `max_length?` | `{summary: "..."}` | Summarize long text into key points. |
| 56 | **`translate_text`** | `text`, `target_language` | `{translated: "...", source_lang: "en", target_lang: "ja"}` | Translate text between languages. |
| 57 | **`generate_pdf`** | `content`, `output_path`, `format?` (html/md) | `{generated: true, path: "..."}` | Generate PDF from HTML/markdown. |
| 58 | **`create_qr_code`** | `data`, `output_path?`, `size?` | `{generated: true, path: "..."}` | Generate QR code from text/URL. |
| 59 | **`text_to_speech_file`** | `text`, `output_path`, `voice?` | `{generated: true, path: "...", duration: 5.2}` | Generate audio file from text (edge-tts). |
| 60 | **`speech_recognition_file`** | `audio_path`, `language?` | `{text: "...", duration: 10.5, language: "en"}` | Transcribe audio file to text. |
| 61 | **`image_to_base64`** | `path` | `{base64: "...", mime_type: "image/png"}` | Convert image to base64 for LLM vision. |
| 62 | **`compare_images`** | `path1`, `path2` | `{similarity: 0.85, differences: [...]}` | Compare two images structurally. |

### ⚪ Priority 6: Quality of Life

| # | Tool | Parameters | Returns | Description |
|:---|:---|:---|:---|:---|
| 63 | **`speed_test`** | — | `{download_mbps: 50.2, upload_mbps: 10.5, ping_ms: 12}` | Internet speed test. |
| 64 | **`timer`** | `seconds`, `label?` | `{timer_id: "...", ends_at: "..."}` | Set countdown timer with notification. |
| 65 | **`stopwatch_start`** | — | `{started: true, timestamp: "..."}` | Start stopwatch. |
| 66 | **`stopwatch_stop`** | — | `{elapsed: "12.5s"}` | Stop stopwatch. |
| 67 | **`calculate`** | `expression` | `{result: 42.5, expression: "15% of 247"}` | Evaluate math expressions. |
| 68 | **`unit_convert`** | `value`, `from_unit`, `to_unit` | `{result: 1.524, from: "5 feet", to: "1.524 meters"}` | Convert between units. |
| 69 | **`base64_encode`** | `text` | `{encoded: "..."}` | Base64 encode. |
| 70 | **`base64_decode`** | `encoded` | `{decoded: "..."}` | Base64 decode. |
| 71 | **`hash_string`** | `text`, `algorithm?` (md5/sha256) | `{hash: "..."}` | Generate hash. |
| 72 | **`json_format`** | `json_string` | `{formatted: "..."}` | Pretty-print JSON. |
| 73 | **`csv_to_json`** | `csv_path` | `{json: [...]}` | Convert CSV to JSON. |
| 74 | **`json_to_csv`** | `json_path`, `output_path?` | `{csv_path: "..."}` | Convert JSON to CSV. |
| 75 | **`extract_archive`** | `path`, `dest?` | `{extracted: true, files: [...]}` | Extract ZIP/RAR/7z archives. |
| 76 | **`create_archive`** | `paths`, `output_path`, `format?` | `{archived: true, size_mb: 15.2}` | Create ZIP/7z archive. |

---

## 7. Implementation Priority Matrix

### Phase 1: Accessibility Tree (Makes May = Hermes) — ~2 weeks

```
inspect_ui_tree → find_ui_element → click_ui_element → type_into_ui_element
select_ui_dropdown → toggle_ui_checkbox → read_ui_text → set_ui_value → get_ui_state
```

**Implementation:**
- Use `pywinauto` (already installed) with UIA backend
- `inspect_ui_tree` wraps `window.descendants()` with recursive tree building
- `click_ui_element` finds element by role+name, calls `.click_input()`
- `type_into_ui_element` finds element by role+name, calls `.set_edit_text()` or `.type_keys()`
- Wire into `core/layers/L5_input.py` as new actions
- Add to `backend/llm/tools.py` as LLM-callable tools

### Phase 2: Verification Loop — ~1 week

```
take_action_verify → verify_element_exists → verify_no_error → compare_screenshots
```

**Implementation:**
- `take_action_verify` calls existing `screenshot_full` + Tier 4 vision
- `verify_element_exists` uses `inspect_ui_tree` to check element presence
- `verify_no_error` scans for error dialog windows
- Wire into the agentic loop in `jarvis.py` as post-action step

### Phase 3: Wait & Retry — ~3 days

```
wait_for_app → wait_for_element → wait_for_text → retry_on_failure
```

**Implementation:**
- `wait_for_app` polls `psutil.process_iter` + `EnumWindows` for app window
- `wait_for_element` polls `inspect_ui_tree` for element presence
- `wait_for_text` polls `win32gui.GetWindowText` for text
- `retry_on_failure` wraps any tool call with try/except + exponential backoff

### Phase 4: System Automation — ~1 week

```
list_scheduled_tasks → create_scheduled_task → list_startup_programs
enable/disable_startup_program → list_recent_files → clipboard_history
```

**Implementation:**
- Task Scheduler: `schtasks.exe /query` and `schtasks.exe /create`
- Startup: Registry `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run`
- Recent Files: `shell:recent` folder or PowerShell `Get-ChildItem`
- Clipboard History: PowerShell `Get-Clipboard -Format Text -AsHtml`

### Phase 5: Developer Tools — ~1 week

```
git_clone → git_status → git_diff → git_commit → git_push → git_pull
run_code → http_request → docker_list → docker_start/stop → database_query → port_scan
```

**Implementation:**
- Git: `subprocess.run(["git", ...])` with JSON output parsing
- Run Code: `subprocess.run(["python", "-c", code])` with timeout
- HTTP: `httpx.AsyncClient` (already used in providers.py)
- Docker: `subprocess.run(["docker", ...])`
- Database: `sqlite3` module
- Port Scan: `socket.connect_ex()`

### Phase 6: Content & QoL — ~1 week

```
summarize_text → translate_text → generate_pdf → create_qr_code
text_to_speech_file → speed_test → timer → calculate → unit_convert
```

**Implementation:**
- Summarize/Translate: Route through LLM with special prompts
- PDF: `weasyprint` or `pdfkit` (HTML to PDF)
- QR Code: `qrcode` Python library
- TTS File: `edge-tts` (free, high quality)
- Speed Test: `speedtest-cli` library
- Timer: `asyncio.sleep` + toast notification
- Calculate: `eval()` with safety sandbox or `simpleeval` library

---

## Summary

| Metric | Count |
|:---|:---|
| **May Current Tools** | 178 |
| **Proposed New Tools** | 76 |
| **Total After Implementation** | 254 |
| **Implementation Phases** | 6 |
| **Estimated Total Time** | ~6 weeks |
| **Critical Gap (Accessibility Tree)** | 11 tools, ~2 weeks |

The **single most impactful change** is implementing the **accessibility tree tools** (Phase 1). These 11 tools would bring May from "good PC control" to "Hermes-level computer-use agent" — enabling it to read and interact with ANY Windows app's UI structure by element role, name, and automation ID, rather than relying on coordinates or window titles.

---

*Last updated: July 17, 2026*
*Document created for the May AI Companion project*
