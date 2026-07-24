"""
Tool definitions for May's Jarvis brain.

Each tool is a JSON schema that the LLM can read and call.
Updated to include all actions across all 9 control layers.
"""

TOOLS = [
    # ── App Control ─────────────────────────────────────────────────────────
    {
        "name": "open_app",
        "description": "Open any application on the PC by name. Handles browsers, editors, games, system tools, UWP apps, shell folders.",
        "parameters": {
            "app_name": {
                "type": "string",
                "description": "Name of the app to open (e.g. 'chrome', 'discord', 'notepad', 'settings', 'this pc')"
            }
        }
    },
    {
        "name": "close_app",
        "description": "Close an application by name. Tries graceful close first, then force kills.",
        "parameters": {
            "app_name": {"type": "string", "description": "App name to close (e.g. 'chrome', 'notepad')"}
        }
    },
    {
        "name": "launch_with_args",
        "description": "Launch an application with command-line arguments (e.g. open Chrome with a specific URL).",
        "parameters": {
            "app_name": {"type": "string", "description": "App name"},
            "args": {"type": "string", "description": "Command-line arguments"}
        }
    },
    {
        "name": "launch_as_admin",
        "description": "Launch an application with elevated (admin) privileges. DESTRUCTIVE - requires user confirmation.",
        "parameters": {
            "app_name": {"type": "string", "description": "App name to launch elevated"}
        }
    },
    {
        "name": "restart_app",
        "description": "Restart an application (kills then re-launches).",
        "parameters": {
            "app_name": {"type": "string", "description": "App name to restart"}
        }
    },
    {
        "name": "is_app_running",
        "description": "Check if an application is currently running.",
        "parameters": {
            "app_name": {"type": "string", "description": "App name to check"}
        }
    },
    {
        "name": "automate_app",
        "description": "Automate a Windows app via pywinauto (connect, click, type, close).",
        "parameters": {
            "title": {"type": "string", "description": "Window title to connect to"},
            "action": {"type": "string", "enum": ["connect", "click", "type", "close"], "description": "Automation action"},
            "control": {"type": "string", "description": "UI control name (for click/type)"},
            "text": {"type": "string", "description": "Text to type (for type action)"}
        }
    },
    {
        "name": "com_dispatch",
        "description": "Create a COM dispatch object (for Office, IE, Explorer automation).",
        "parameters": {
            "prog_id": {"type": "string", "description": "COM ProgID (e.g. 'Word.Application', 'Excel.Application')"},
            "method": {"type": "string", "enum": ["open", "visible", "quit"], "description": "Action to perform"},
            "target": {"type": "string", "description": "File to open (for open method)"}
        }
    },
    {
        "name": "find_app_by_name",
        "description": "Search for an installed app by name.",
        "parameters": {
            "name": {"type": "string", "description": "App name to search for"}
        }
    },
    {
        "name": "list_installed_apps",
        "description": "List all installed applications on the PC.",
        "parameters": {}
    },

    # ── Volume & Display ────────────────────────────────────────────────────
    {
        "name": "set_volume",
        "description": "Set system volume to a specific level (0-100).",
        "parameters": {
            "level": {"type": "integer", "description": "Volume level 0-100"}
        }
    },
    {
        "name": "get_volume",
        "description": "Get current system volume level (0-100).",
        "parameters": {}
    },
    {
        "name": "volume_up",
        "description": "Increase system volume by 15%.",
        "parameters": {}
    },
    {
        "name": "volume_down",
        "description": "Decrease system volume by 15%.",
        "parameters": {}
    },
    {
        "name": "mute",
        "description": "Mute system audio.",
        "parameters": {}
    },
    {
        "name": "unmute",
        "description": "Unmute system audio.",
        "parameters": {}
    },
    {
        "name": "set_brightness",
        "description": "Set screen brightness (0-100).",
        "parameters": {
            "level": {"type": "integer", "description": "Brightness level 0-100"}
        }
    },
    {
        "name": "get_brightness",
        "description": "Get current screen brightness level.",
        "parameters": {}
    },
    {
        "name": "enable_dark_mode",
        "description": "Enable Windows dark mode for apps and system UI.",
        "parameters": {}
    },
    {
        "name": "enable_light_mode",
        "description": "Enable Windows light mode for apps and system UI.",
        "parameters": {}
    },

    # ── File Operations ─────────────────────────────────────────────────────
    {
        "name": "read_file",
        "description": "Read the contents of a text file.",
        "parameters": {
            "path": {"type": "string", "description": "Full path to the file"}
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file (creates parent directories if needed, overwrites if exists).",
        "parameters": {
            "path": {"type": "string", "description": "Full path to the file"},
            "content": {"type": "string", "description": "Content to write"}
        }
    },
    {
        "name": "list_directory",
        "description": "List contents of a directory (files and folders with sizes).",
        "parameters": {
            "path": {"type": "string", "description": "Directory path (default: current directory)"}
        }
    },
    {
        "name": "search_files",
        "description": "Search for files matching a glob pattern recursively.",
        "parameters": {
            "directory": {"type": "string", "description": "Directory to search in"},
            "pattern": {"type": "string", "description": "File glob pattern (e.g. '*.txt')"}
        }
    },
    {
        "name": "search_content",
        "description": "Search for text inside files (grep-like). Finds lines containing the pattern.",
        "parameters": {
            "directory": {"type": "string", "description": "Directory to search in"},
            "pattern": {"type": "string", "description": "Text or regex to search for"},
            "file_filter": {"type": "string", "description": "File type filter (e.g. '*.py'). Default: all files"}
        }
    },
    {
        "name": "find_and_replace",
        "description": "Find and replace text in a file.",
        "parameters": {
            "path": {"type": "string", "description": "File path"},
            "find_text": {"type": "string", "description": "Text to find"},
            "replace_text": {"type": "string", "description": "Replacement text"}
        }
    },
    {
        "name": "copy_file",
        "description": "Copy a file from source to destination.",
        "parameters": {
            "source": {"type": "string", "description": "Source file path"},
            "destination": {"type": "string", "description": "Destination path"}
        }
    },
    {
        "name": "move_file",
        "description": "Move or rename a file.",
        "parameters": {
            "source": {"type": "string", "description": "Source file path"},
            "destination": {"type": "string", "description": "Destination path"}
        }
    },
    {
        "name": "delete_file",
        "description": "Delete a file (moves to recycle bin if send2trash is installed).",
        "parameters": {
            "path": {"type": "string", "description": "File path to delete"}
        }
    },
    {
        "name": "get_file_info",
        "description": "Get detailed info about a file (size, dates, type, extension).",
        "parameters": {
            "path": {"type": "string", "description": "File path"}
        }
    },
    {
        "name": "open_folder",
        "description": "Open a folder in Windows File Explorer.",
        "parameters": {
            "path": {"type": "string", "description": "Folder path to open"}
        }
    },
    {
        "name": "get_folder_size",
        "description": "Calculate total size of a folder.",
        "parameters": {
            "path": {"type": "string", "description": "Folder path"}
        }
    },
    {
        "name": "get_large_files",
        "description": "Find large files in a directory (useful for freeing disk space).",
        "parameters": {
            "directory": {"type": "string", "description": "Directory to search"},
            "min_size_mb": {"type": "integer", "description": "Minimum file size in MB (default: 100)"}
        }
    },
    {
        "name": "batch_rename",
        "description": "Rename files in a directory that contain a specific text pattern.",
        "parameters": {
            "directory": {"type": "string", "description": "Directory containing files"},
            "find": {"type": "string", "description": "Text to find in filenames"},
            "replace": {"type": "string", "description": "Text to replace with"}
        }
    },
    {
        "name": "batch_delete",
        "description": "Delete multiple files matching a glob pattern in a directory.",
        "parameters": {
            "directory": {"type": "string", "description": "Directory to delete from"},
            "pattern": {"type": "string", "description": "File glob pattern (e.g. '*.tmp')"}
        }
    },
    {
        "name": "open_file_with",
        "description": "Open a file with a specific application.",
        "parameters": {
            "path": {"type": "string", "description": "File path to open"},
            "app": {"type": "string", "description": "Application name (e.g. 'notepad', 'chrome')"}
        }
    },
    {
        "name": "take_ownership",
        "description": "Take ownership of a file or folder (requires admin).",
        "parameters": {
            "path": {"type": "string", "description": "File or folder path"}
        }
    },
    {
        "name": "find_duplicates",
        "description": "Find duplicate files by content hash in a directory.",
        "parameters": {
            "path": {"type": "string", "description": "Directory to search"}
        }
    },
    {
        "name": "compress_file",
        "description": "Compress a file or folder into a .7z archive.",
        "parameters": {
            "path": {"type": "string", "description": "File or folder to compress"},
            "archive": {"type": "string", "description": "Output archive path (default: path.7z)"}
        }
    },
    {
        "name": "decompress_file",
        "description": "Extract a .7z archive.",
        "parameters": {
            "path": {"type": "string", "description": "Archive path"},
            "dest": {"type": "string", "description": "Destination folder (default: current dir)"}
        }
    },

    # ── Web & Search ────────────────────────────────────────────────────────
    {
        "name": "web_search",
        "description": "Search the web using Google. Opens search results in the default browser.",
        "parameters": {
            "query": {"type": "string", "description": "Search query"}
        }
    },
    {
        "name": "open_url",
        "description": "Open a URL in the default browser.",
        "parameters": {
            "url": {"type": "string", "description": "URL to open"}
        }
    },
    {
        "name": "extract_web_content",
        "description": "Fetch a web page and extract its readable text content.",
        "parameters": {
            "url": {"type": "string", "description": "URL to fetch and read"}
        }
    },

    # ── Process Management ──────────────────────────────────────────────────
    {
        "name": "list_processes",
        "description": "List top processes by CPU or memory usage.",
        "parameters": {
            "sort_by": {"type": "string", "enum": ["cpu", "memory"], "description": "Sort by CPU or memory"}
        }
    },
    {
        "name": "kill_process",
        "description": "Kill a process by name. DESTRUCTIVE - requires user confirmation.",
        "parameters": {
            "name": {"type": "string", "description": "Process name to kill"}
        }
    },
    {
        "name": "get_process_info",
        "description": "Get detailed info about a specific process (PID, CPU, memory, status, path).",
        "parameters": {
            "name": {"type": "string", "description": "Process name to look up"}
        }
    },
    {
        "name": "set_process_priority",
        "description": "Set a process's priority (low, normal, high, realtime, idle).",
        "parameters": {
            "pid": {"type": "integer", "description": "Process ID"},
            "priority": {"type": "string", "enum": ["low", "normal", "high", "realtime", "idle"], "description": "Priority level"}
        }
    },
    {
        "name": "get_command_line",
        "description": "Get the command line arguments of a running process.",
        "parameters": {
            "name": {"type": "string", "description": "Process name"}
        }
    },
    {
        "name": "is_process_running",
        "description": "Check if a process is currently running.",
        "parameters": {
            "name": {"type": "string", "description": "Process name to check"}
        }
    },

    # ── Media Control ───────────────────────────────────────────────────────
    {
        "name": "media_play_pause",
        "description": "Toggle media play/pause (works with Spotify, YouTube, any media player).",
        "parameters": {}
    },
    {
        "name": "media_next",
        "description": "Skip to next track in media player.",
        "parameters": {}
    },
    {
        "name": "media_previous",
        "description": "Go to previous track in media player.",
        "parameters": {}
    },
    {
        "name": "media_stop",
        "description": "Stop media playback.",
        "parameters": {}
    },

    # ── Keyboard & Mouse ────────────────────────────────────────────────────
    {
        "name": "send_keys",
        "description": "Send a keyboard shortcut. Supports: ctrl, alt, shift, win, enter, tab, esc, delete, backspace, arrows, home, end, pageup, pagedown, f1-f12.",
        "parameters": {
            "keys": {"type": "string", "description": "Key combination (e.g. 'ctrl+c', 'alt+tab', 'win+d')"}
        }
    },
    {
        "name": "type_text",
        "description": "Type text into a specific window. Always provide window_title when typing into an app you just opened.",
        "parameters": {
            "text": {"type": "string", "description": "Text to type"},
            "window_title": {"type": "string", "description": "Partial window title to focus before typing (e.g. 'notepad', 'untitled'). Required when typing into a specific app."}
        }
    },
    {
        "name": "mouse_click",
        "description": "Click at screen coordinates.",
        "parameters": {
            "x": {"type": "integer", "description": "X coordinate"},
            "y": {"type": "integer", "description": "Y coordinate"},
            "button": {"type": "string", "enum": ["left", "right", "middle"], "description": "Mouse button (default: left)"}
        }
    },
    {
        "name": "mouse_scroll",
        "description": "Scroll the mouse wheel. Positive = up, negative = down.",
        "parameters": {
            "clicks": {"type": "integer", "description": "Number of scroll notches"}
        }
    },
    {
        "name": "drag_and_drop",
        "description": "Drag from (x1,y1) to (x2,y2).",
        "parameters": {
            "x1": {"type": "integer", "description": "Start X"},
            "y1": {"type": "integer", "description": "Start Y"},
            "x2": {"type": "integer", "description": "End X"},
            "y2": {"type": "integer", "description": "End Y"}
        }
    },
    {
        "name": "get_mouse_position",
        "description": "Get current mouse cursor position on screen.",
        "parameters": {}
    },

    # ── Window Management ───────────────────────────────────────────────────
    {
        "name": "list_windows",
        "description": "List all currently open windows with their titles and process names.",
        "parameters": {}
    },
    {
        "name": "focus_window",
        "description": "Bring a window to the front by partial title match.",
        "parameters": {
            "title": {"type": "string", "description": "Partial window title to match"}
        }
    },
    {
        "name": "minimize_window",
        "description": "Minimize a window by partial title match.",
        "parameters": {
            "title": {"type": "string", "description": "Partial window title to match"}
        }
    },
    {
        "name": "maximize_window",
        "description": "Maximize a window by partial title match.",
        "parameters": {
            "title": {"type": "string", "description": "Partial window title to match"}
        }
    },
    {
        "name": "resize_window",
        "description": "Resize a window to specific dimensions.",
        "parameters": {
            "title": {"type": "string", "description": "Window title"},
            "width": {"type": "integer", "description": "Width in pixels"},
            "height": {"type": "integer", "description": "Height in pixels"}
        }
    },
    {
        "name": "flash_window",
        "description": "Flash a window in the taskbar to get attention.",
        "parameters": {
            "title": {"type": "string", "description": "Window title to flash"}
        }
    },

    # ── System ──────────────────────────────────────────────────────────────
    {
        "name": "screenshot",
        "description": "Take a screenshot and save it to the desktop.",
        "parameters": {}
    },
    {
        "name": "describe_screen",
        "description": "Take a screenshot and describe what's on screen using a vision model. Use when the user asks 'what am I looking at', 'describe my screen', 'what's on screen', or wants to understand visible content (PDFs, spreadsheets, code, error messages, etc.).",
        "parameters": {
            "question": {"type": "string", "description": "Optional specific question about what's on screen (e.g. 'what error is showing', 'summarize this document'). Leave empty for a general description."}
        }
    },
    {
        "name": "system_info",
        "description": "Get comprehensive system information (OS, CPU, RAM, disk, uptime, username).",
        "parameters": {}
    },
    {
        "name": "battery_info",
        "description": "Get battery status, percentage, and estimated time remaining.",
        "parameters": {}
    },
    {
        "name": "disk_info",
        "description": "Get disk usage information for all drives.",
        "parameters": {}
    },
    {
        "name": "shutdown_pc",
        "description": "Shut down the PC after an optional delay. DESTRUCTIVE - requires user confirmation.",
        "parameters": {
            "delay": {"type": "integer", "description": "Delay in seconds before shutdown (default: 0)"}
        }
    },
    {
        "name": "restart_pc",
        "description": "Restart the PC after an optional delay. DESTRUCTIVE - requires user confirmation.",
        "parameters": {
            "delay": {"type": "integer", "description": "Delay in seconds before restart (default: 0)"}
        }
    },
    {
        "name": "sleep_pc",
        "description": "Put the PC to sleep.",
        "parameters": {}
    },
    {
        "name": "lock_pc",
        "description": "Lock the Windows workstation.",
        "parameters": {}
    },
    {
        "name": "cancel_shutdown",
        "description": "Cancel a pending shutdown or restart.",
        "parameters": {}
    },

    # ── Network ─────────────────────────────────────────────────────────────
    {
        "name": "get_network_info",
        "description": "Get network information (IP addresses, WiFi status, adapters).",
        "parameters": {}
    },
    {
        "name": "get_public_ip",
        "description": "Get the public/external IP address.",
        "parameters": {}
    },
    {
        "name": "get_wifi_password",
        "description": "Get WiFi password for all saved networks.",
        "parameters": {}
    },
    {
        "name": "test_internet",
        "description": "Test if there's an active internet connection.",
        "parameters": {}
    },
    {
        "name": "connect_wifi",
        "description": "Connect to a WiFi network by SSID.",
        "parameters": {
            "ssid": {"type": "string", "description": "Network name (SSID)"},
            "password": {"type": "string", "description": "Password (if needed)"}
        }
    },
    {
        "name": "disconnect_wifi",
        "description": "Disconnect from the current WiFi network.",
        "parameters": {}
    },
    {
        "name": "flush_dns",
        "description": "Flush the DNS cache.",
        "parameters": {}
    },
    {
        "name": "add_firewall_rule",
        "description": "Add a Windows firewall rule. DESTRUCTIVE - requires user confirmation.",
        "parameters": {
            "name": {"type": "string", "description": "Rule name"},
            "direction": {"type": "string", "enum": ["Inbound", "Outbound"], "description": "Direction"},
            "action": {"type": "string", "enum": ["Allow", "Block"], "description": "Action"},
            "protocol": {"type": "string", "description": "Protocol (TCP, UDP)"},
            "port": {"type": "string", "description": "Port number"}
        }
    },

    # ── Browser Automation ──────────────────────────────────────────────────
    {
        "name": "browser_navigate",
        "description": "Navigate to a URL in the browser (requires Chrome with --remote-debugging-port=9222).",
        "parameters": {
            "url": {"type": "string", "description": "URL to navigate to"}
        }
    },
    {
        "name": "browser_click",
        "description": "Click an element on a web page by CSS selector.",
        "parameters": {
            "selector": {"type": "string", "description": "CSS selector (e.g. '#submit', '.btn', 'a[href]')"}
        }
    },
    {
        "name": "browser_type",
        "description": "Type text into a form field on a web page.",
        "parameters": {
            "selector": {"type": "string", "description": "CSS selector of the input field"},
            "text": {"type": "string", "description": "Text to type"}
        }
    },
    {
        "name": "browser_fill_form",
        "description": "Fill multiple form fields at once.",
        "parameters": {
            "fields": {"type": "array", "items": {"type": "object", "properties": {"selector": {"type": "string"}, "value": {"type": "string"}}}, "description": "List of {selector, value} pairs"}
        }
    },
    {
        "name": "browser_get_text",
        "description": "Get text content from a web page element.",
        "parameters": {
            "selector": {"type": "string", "description": "CSS selector"}
        }
    },
    {
        "name": "browser_screenshot",
        "description": "Take a screenshot of the current web page.",
        "parameters": {
            "path": {"type": "string", "description": "Save path (optional)"}
        }
    },
    {
        "name": "browser_run_js",
        "description": "Run JavaScript on the current web page.",
        "parameters": {
            "script": {"type": "string", "description": "JavaScript code to execute"}
        }
    },
    {
        "name": "browser_wait_for",
        "description": "Wait for an element to appear on the page.",
        "parameters": {
            "selector": {"type": "string", "description": "CSS selector to wait for"},
            "timeout": {"type": "integer", "description": "Timeout in ms (default: 10000)"}
        }
    },
    {
        "name": "browser_manage_cookies",
        "description": "Get, set, or delete browser cookies.",
        "parameters": {
            "action": {"type": "string", "enum": ["get", "set", "delete", "clear"], "description": "Cookie action"},
            "name": {"type": "string", "description": "Cookie name (for set/delete)"},
            "value": {"type": "string", "description": "Cookie value (for set)"}
        }
    },

    # ── Settings ────────────────────────────────────────────────────────────
    {
        "name": "open_settings",
        "description": "Open Windows Settings to a specific page.",
        "parameters": {
            "page": {"type": "string", "description": "Settings page (display, sound, network, bluetooth, update, etc.)"}
        }
    },

    # ── Clipboard ───────────────────────────────────────────────────────────
    {
        "name": "copy_to_clipboard",
        "description": "Copy text to the Windows clipboard.",
        "parameters": {
            "text": {"type": "string", "description": "Text to copy"}
        }
    },
    {
        "name": "get_clipboard",
        "description": "Get text from the Windows clipboard.",
        "parameters": {}
    },

    # ── Reminders ───────────────────────────────────────────────────────────
    {
        "name": "set_reminder",
        "description": "Set a timed reminder that sends a Windows toast notification.",
        "parameters": {
            "message": {"type": "string", "description": "What to remind about"},
            "minutes": {"type": "integer", "description": "Minutes from now"}
        }
    },

    # ── Email ───────────────────────────────────────────────────────────────
    {
        "name": "get_unread_emails",
        "description": "Get unread emails from the inbox. Returns subject, sender, date, and snippet.",
        "parameters": {
            "max_items": {"type": "integer", "description": "Maximum emails to return (default: 10)"}
        }
    },
    {
        "name": "get_unread_count",
        "description": "Get the count of unread emails.",
        "parameters": {}
    },
    {
        "name": "search_emails",
        "description": "Search emails by subject text.",
        "parameters": {
            "query": {"type": "string", "description": "Search query (matches subject)"},
            "max_items": {"type": "integer", "description": "Maximum results (default: 10)"}
        }
    },
    {
        "name": "read_email",
        "description": "Read a specific email by UID. Returns the full email body.",
        "parameters": {
            "uid": {"type": "string", "description": "Email UID (from get_unread_emails)"}
        }
    },
    {
        "name": "send_email",
        "description": "Send an email.",
        "parameters": {
            "to": {"type": "string", "description": "Recipient email address(es), comma-separated"},
            "subject": {"type": "string", "description": "Email subject"},
            "body": {"type": "string", "description": "Email body text"},
            "cc": {"type": "string", "description": "CC recipients (optional, comma-separated)"}
        }
    },
    {
        "name": "get_recent_emails",
        "description": "Get the most recent emails (read or unread).",
        "parameters": {
            "max_items": {"type": "integer", "description": "Maximum emails to return (default: 5)"}
        }
    },

    # ── Wellness & Proactive ───────────────────────────────────────────────
    {
        "name": "get_wellness_status",
        "description": "Get proactive wellness assistant status (session duration, rules, suggestions).",
        "parameters": {}
    },
    {
        "name": "get_wellness_suggestions",
        "description": "Check for pending wellness suggestions (water, posture, breaks, eye rest).",
        "parameters": {}
    },
    {
        "name": "set_wellness_rule",
        "description": "Enable or disable a specific wellness reminder rule.",
        "parameters": {
            "rule": {"type": "string", "enum": ["water", "posture", "break", "eyes"], "description": "Wellness rule to toggle"},
            "enabled": {"type": "boolean", "description": "Enable or disable the rule"}
        }
    },

    # ── Meeting Mode ────────────────────────────────────────────────────────
    {
        "name": "start_meeting",
        "description": "Start recording a meeting. Captures system audio, transcribes, and will generate a summary with action items when stopped.",
        "parameters": {
            "title": {"type": "string", "description": "Meeting title (optional, auto-generated if not provided)"}
        }
    },
    {
        "name": "stop_meeting",
        "description": "Stop the current meeting recording. Generates a summary with action items and saves to ~/may/meetings/.",
        "parameters": {}
    },
    {
        "name": "meeting_status",
        "description": "Check if a meeting is currently being recorded.",
        "parameters": {}
    },

    # ── Ghost Mode ──────────────────────────────────────────────────────────
    {
        "name": "queue_ghost_task",
        "description": "Queue a task for autonomous execution when the user is idle. Ghost Mode executes tasks overnight or during breaks.",
        "parameters": {
            "description": {"type": "string", "description": "What the task should accomplish (natural language)"},
            "priority": {"type": "integer", "description": "Priority (higher = execute first, default: 0)"}
        }
    },
    {
        "name": "ghost_status",
        "description": "Check Ghost Mode status — queued tasks, completed tasks, idle detection.",
        "parameters": {}
    },
    {
        "name": "cancel_ghost_task",
        "description": "Cancel a queued Ghost Mode task.",
        "parameters": {
            "task_id": {"type": "string", "description": "Task ID to cancel"}
        }
    },
    {
        "name": "cancel_all_ghost_tasks",
        "description": "Cancel all queued Ghost Mode tasks.",
        "parameters": {}
    },

    # ── Voice Biometrics ──────────────────────────────────────────────
    {
        "name": "voice_enroll",
        "description": "Enroll a voice profile for speaker verification. May will only respond to your voice.",
        "parameters": {
            "name": {"type": "string", "description": "Speaker name/label (default: user)"}
        }
    },
    {
        "name": "voice_verify",
        "description": "Verify if the current speaker matches the enrolled voice profile.",
        "parameters": {}
    },
    {
        "name": "biometrics_status",
        "description": "Check voice biometrics enrollment status.",
        "parameters": {}
    },
    {
        "name": "biometrics_toggle",
        "description": "Toggle voice biometrics on/off.",
        "parameters": {}
    },
    {
        "name": "biometrics_delete",
        "description": "Delete the saved voice profile. DESTRUCTIVE.",
        "parameters": {}
    },

    # ── Package Management ──────────────────────────────────────────────────
    {
        "name": "install_app",
        "description": "Install an application using winget. DESTRUCTIVE - requires user confirmation.",
        "parameters": {
            "package": {"type": "string", "description": "Package name to install"}
        }
    },
    {
        "name": "search_packages",
        "description": "Search for installable packages using winget.",
        "parameters": {
            "query": {"type": "string", "description": "Search query"}
        }
    },

    # ── Service Management ──────────────────────────────────────────────────
    {
        "name": "list_services",
        "description": "List Windows services with their status.",
        "parameters": {
            "filter": {"type": "string", "description": "Optional filter text"}
        }
    },
    {
        "name": "start_service",
        "description": "Start a Windows service.",
        "parameters": {"name": {"type": "string", "description": "Service name"}}
    },
    {
        "name": "stop_service",
        "description": "Stop a Windows service.",
        "parameters": {"name": {"type": "string", "description": "Service name"}}
    },
    {
        "name": "restart_service",
        "description": "Restart a Windows service.",
        "parameters": {"name": {"type": "string", "description": "Service name"}}
    },
    {
        "name": "set_service_startup",
        "description": "Set a service's startup type (Auto, Manual, Disabled).",
        "parameters": {
            "name": {"type": "string", "description": "Service name"},
            "type": {"type": "string", "enum": ["Auto", "Manual", "Disabled"], "description": "Startup type"}
        }
    },

    # ── Environment Variables ───────────────────────────────────────────────
    {
        "name": "get_env_var",
        "description": "Get an environment variable's value.",
        "parameters": {
            "name": {"type": "string", "description": "Environment variable name"}
        }
    },
    {
        "name": "list_env_vars",
        "description": "List all environment variables.",
        "parameters": {
            "filter": {"type": "string", "description": "Optional filter text"}
        }
    },

    # ── Weather ─────────────────────────────────────────────────────────────
    {
        "name": "get_weather",
        "description": "Get current weather information.",
        "parameters": {
            "location": {"type": "string", "description": "City name (optional, auto-detects if empty)"}
        }
    },

    # ── Time & Date ─────────────────────────────────────────────────────────
    {
        "name": "get_time",
        "description": "Get the current time.",
        "parameters": {}
    },
    {
        "name": "get_date",
        "description": "Get today's date.",
        "parameters": {}
    },

    # ── PowerShell Fallback ─────────────────────────────────────────────────
    {
        "name": "run_powershell",
        "description": "Execute any PowerShell command. Use as last resort when no specific tool exists.",
        "parameters": {
            "command": {"type": "string", "description": "PowerShell command to execute"}
        }
    },

    # ── Phase 7: New Filesystem Actions ────────────────────────────────────
    {
        "name": "create_folder",
        "description": "Create a directory (and parent directories if needed).",
        "parameters": {
            "path": {"type": "string", "description": "Directory path to create"}
        }
    },
    {
        "name": "get_drive_info",
        "description": "Get info about all drives (total, free, used space).",
        "parameters": {}
    },
    {
        "name": "copy_folder",
        "description": "Recursively copy a folder tree to a destination.",
        "parameters": {
            "source": {"type": "string", "description": "Source folder path"},
            "destination": {"type": "string", "description": "Destination folder path"}
        }
    },
    {
        "name": "delete_folder",
        "description": "Recursively delete a folder and all its contents. DESTRUCTIVE.",
        "parameters": {
            "path": {"type": "string", "description": "Folder path to delete"}
        }
    },

    # ── Phase 7: New Process Actions ───────────────────────────────────────
    {
        "name": "get_process_cpu",
        "description": "Get CPU usage percentage for a specific process.",
        "parameters": {
            "name": {"type": "string", "description": "Process name"},
            "pid": {"type": "integer", "description": "Process ID (optional)"}
        }
    },
    {
        "name": "get_process_memory",
        "description": "Get memory usage (RSS, VMS, percent) for a specific process.",
        "parameters": {
            "name": {"type": "string", "description": "Process name"},
            "pid": {"type": "integer", "description": "Process ID (optional)"}
        }
    },
    {
        "name": "get_process_path",
        "description": "Get the executable path of a running process.",
        "parameters": {
            "name": {"type": "string", "description": "Process name"},
            "pid": {"type": "integer", "description": "Process ID (optional)"}
        }
    },
    {
        "name": "set_process_affinity",
        "description": "Set which CPU cores a process can use.",
        "parameters": {
            "pid": {"type": "integer", "description": "Process ID"},
            "cores": {"type": "array", "items": {"type": "integer"}, "description": "List of core indices (e.g. [0, 1])"}
        }
    },
    {
        "name": "set_memory_limit",
        "description": "Limit a process's memory usage via job object. Requires admin.",
        "parameters": {
            "pid": {"type": "integer", "description": "Process ID"},
            "limit_mb": {"type": "integer", "description": "Memory limit in MB"}
        }
    },
    {
        "name": "set_cpu_limit",
        "description": "Limit a process's CPU usage percentage via job object. Requires admin.",
        "parameters": {
            "pid": {"type": "integer", "description": "Process ID"},
            "percent": {"type": "integer", "description": "CPU limit 1-100%"}
        }
    },

    # ── Phase 7: New Application Actions ───────────────────────────────────
    {
        "name": "get_app_path",
        "description": "Get the installation path of an app from the Windows registry.",
        "parameters": {
            "app_name": {"type": "string", "description": "App name to look up"}
        }
    },
    {
        "name": "get_app_version",
        "description": "Get the version of an installed app.",
        "parameters": {
            "app_name": {"type": "string", "description": "App name to look up"}
        }
    },
    {
        "name": "force_close_app",
        "description": "Force-kill an application. DESTRUCTIVE.",
        "parameters": {
            "app_name": {"type": "string", "description": "App name to force-close"}
        }
    },

    # ── Phase 7: New Window Actions ────────────────────────────────────────
    {
        "name": "find_window",
        "description": "Find a window by title or class name.",
        "parameters": {
            "title": {"type": "string", "description": "Window title (partial match)"}
        }
    },
    {
        "name": "set_window_position",
        "description": "Set a window's position and size on screen.",
        "parameters": {
            "title": {"type": "string", "description": "Window title"},
            "x": {"type": "integer", "description": "X position"},
            "y": {"type": "integer", "description": "Y position"},
            "width": {"type": "integer", "description": "Width"},
            "height": {"type": "integer", "description": "Height"}
        }
    },
    {
        "name": "close_window",
        "description": "Close a window by title.",
        "parameters": {
            "title": {"type": "string", "description": "Window title to close"}
        }
    },
    {
        "name": "get_window_title",
        "description": "Get the title of the currently active window.",
        "parameters": {}
    },
    {
        "name": "take_window_screenshot",
        "description": "Take a screenshot of a specific window.",
        "parameters": {
            "title": {"type": "string", "description": "Window title"},
            "output": {"type": "string", "description": "Save path (optional)"}
        }
    },
    {
        "name": "arrange_windows",
        "description": "Arrange all visible windows in tile or cascade layout.",
        "parameters": {
            "mode": {"type": "string", "enum": ["tile", "cascade"], "description": "Arrangement mode"}
        }
    },

    # ── Phase 7: New Input Actions ─────────────────────────────────────────
    {
        "name": "tap_key",
        "description": "Quick press and release of a single key.",
        "parameters": {
            "key": {"type": "string", "description": "Key name (enter, tab, f1-f12, etc.)"}
        }
    },
    {
        "name": "hold_key",
        "description": "Hold a key for a specified duration.",
        "parameters": {
            "key": {"type": "string", "description": "Key name"},
            "duration": {"type": "number", "description": "Hold duration in seconds (default 0.5)"}
        }
    },
    {
        "name": "type_text_fast",
        "description": "Type text quickly using clipboard paste (handles any length/Unicode).",
        "parameters": {
            "text": {"type": "string", "description": "Text to type"}
        }
    },
    {
        "name": "screenshot_full",
        "description": "Capture the full screen to a PNG file.",
        "parameters": {
            "output": {"type": "string", "description": "Save path (default: screenshot_full.png)"}
        }
    },
    {
        "name": "screenshot_region",
        "description": "Capture a screen region to a PNG file.",
        "parameters": {
            "x": {"type": "integer", "description": "Left X"},
            "y": {"type": "integer", "description": "Top Y"},
            "x2": {"type": "integer", "description": "Right X"},
            "y2": {"type": "integer", "description": "Bottom Y"},
            "output": {"type": "string", "description": "Save path (optional)"}
        }
    },

    # ── Phase 7: New System Actions ────────────────────────────────────────
    {
        "name": "logoff",
        "description": "Log off the current user. DESTRUCTIVE.",
        "parameters": {}
    },
    {
        "name": "get_audio_devices",
        "description": "List all audio playback devices.",
        "parameters": {}
    },
    {
        "name": "rotate_display",
        "description": "Rotate the screen orientation.",
        "parameters": {
            "angle": {"type": "integer", "enum": [0, 90, 180, 270], "description": "Rotation angle in degrees"}
        }
    },
    {
        "name": "enable_adapter",
        "description": "Enable a network adapter.",
        "parameters": {
            "name": {"type": "string", "description": "Adapter name (default: Wi-Fi)"}
        }
    },
    {
        "name": "disable_adapter",
        "description": "Disable a network adapter. DESTRUCTIVE.",
        "parameters": {
            "name": {"type": "string", "description": "Adapter name (default: Wi-Fi)"}
        }
    },
    {
        "name": "list_wifi_networks",
        "description": "Scan and list available WiFi networks.",
        "parameters": {}
    },
    {
        "name": "get_os_info",
        "description": "Get detailed OS information (version, build, install date).",
        "parameters": {}
    },

    # ── Phase 7: New Browser Actions ───────────────────────────────────────
    {
        "name": "open_browser",
        "description": "Launch a new browser instance via Playwright.",
        "parameters": {
            "browser": {"type": "string", "enum": ["chromium", "firefox", "webkit"], "description": "Browser type (default: chromium)"},
            "url": {"type": "string", "description": "URL to open"},
            "headless": {"type": "boolean", "description": "Run headless (default: false)"}
        }
    },
    {
        "name": "close_browser",
        "description": "Close the Playwright browser instance.",
        "parameters": {}
    },
    {
        "name": "handle_dialog",
        "description": "Accept or dismiss a JavaScript dialog (alert, confirm, prompt).",
        "parameters": {
            "action": {"type": "string", "enum": ["accept", "dismiss"], "description": "Dialog action"},
            "text": {"type": "string", "description": "Text for prompt dialogs"}
        }
    },

    # ── Architecture-compliant missing actions ──────────────────────────────
    {
        "name": "list_virtual_desktops",
        "description": "List all virtual desktops (Windows 10/11).",
        "parameters": {}
    },
    {
        "name": "move_to_virtual_desktop",
        "description": "Move a window to a specific virtual desktop by index (0-based).",
        "parameters": {
            "title": {"type": "string", "description": "Window title to move"},
            "desktop_index": {"type": "integer", "description": "Virtual desktop index (0-based)"}
        }
    },
    {
        "name": "screenshot_window",
        "description": "Capture a specific window to a PNG file by title.",
        "parameters": {
            "title": {"type": "string", "description": "Window title (partial match)"},
            "output": {"type": "string", "description": "Save path (optional)"}
        }
    },
    {
        "name": "enable_service",
        "description": "Enable a Windows service (set startup to Automatic).",
        "parameters": {
            "name": {"type": "string", "description": "Service name"}
        }
    },
    {
        "name": "disable_service",
        "description": "Disable a Windows service (set startup to Disabled). DESTRUCTIVE.",
        "parameters": {
            "name": {"type": "string", "description": "Service name"}
        }
    },
    {
        "name": "get_installed_updates",
        "description": "List recently installed Windows updates.",
        "parameters": {}
    },
    {
        "name": "delete_system_env",
        "description": "Delete a system environment variable. DESTRUCTIVE - requires user confirmation.",
        "parameters": {
            "name": {"type": "string", "description": "Variable name to delete"}
        }
    },
    {
        "name": "connect_to_browser",
        "description": "Connect to an existing browser instance via Chrome DevTools Protocol.",
        "parameters": {
            "cdp_url": {"type": "string", "description": "CDP endpoint URL (default: http://localhost:9222)"}
        }
    },

    # ── P7: Verification — Post-Action Screenshot Verification ──────────────
    {
        "name": "take_action_verify",
        "description": "Take a screenshot AFTER executing a tool action to verify the outcome. This is the OpenClaw/Hermes verification pattern — catches cases where the action appeared to succeed but didn't. Call this after click_ui_element, type_into_ui_element, select_ui_dropdown, or toggle_ui_checkbox to confirm the result.",
        "parameters": {
            "expected_outcome": {"type": "string", "description": "What you expect to see on screen after the action (e.g. 'Save dialog appeared', 'text was entered in the search box'). The LLM will compare this against the screenshot."},
            "action_description": {"type": "string", "description": "Description of the action that was just performed (for logging)."},
            "include_base64": {"type": "boolean", "description": "Include base64-encoded screenshot for vision model analysis (default: false).", "default": False}
        }
    },
    {
        "name": "verify_element_exists",
        "description": "Verify that a specific UI element exists (or doesn't exist) after an action. Polls with timeout for slow UI updates. Use to confirm that clicking a button opened a dialog, typing showed results, etc.",
        "parameters": {
            "window_title": {"type": "string", "description": "Window title to search in"},
            "role": {"type": "string", "description": "Element role (Button, Edit, CheckBox, etc.)"},
            "name": {"type": "string", "description": "Element name/label"},
            "should_exist": {"type": "boolean", "description": "Expected: true if element should appear, false if it should disappear (default: true)", "default": True},
            "timeout_seconds": {"type": "number", "description": "How long to poll for the element (default: 3.0)", "default": 3.0}
        }
    },
    {
        "name": "verify_no_error",
        "description": "Verify that no error dialogs or popups appeared after an action. Scans all visible windows for common error indicators (Error, Failed, Cannot, Access Denied, UAC prompts, etc.).",
        "parameters": {}
    },
    {
        "name": "compare_screenshots",
        "description": "Compare two screenshots to detect changes (before/after an action). Uses perceptual hashing (pHash) for structural comparison and pixel-level diff. Can compare two file paths or a file vs current screen.",
        "parameters": {
            "before_path": {"type": "string", "description": "Path to the 'before' screenshot"},
            "after_path": {"type": "string", "description": "Path to the 'after' screenshot, or 'screen' for current screen"},
            "threshold": {"type": "number", "description": "Similarity threshold 0-1 (default: 0.85). Below this = changed.", "default": 0.85}
        }
    },

    # ── P7: UIAutomation — Accessibility Tree (Hermes-level computer-use) ──
    {
        "name": "inspect_ui_tree",
        "description": "Read the Windows UIAutomation accessibility tree for any window. Returns ALL UI elements with their role, name, automation_id, bounding_rect, and children. This is the KEY tool for reliable computer-use — instead of guessing coordinates, find elements by role and name.",
        "parameters": {
            "window_title": {"type": "string", "description": "Window title to inspect (partial match). Leave empty for the active/focused window."},
            "max_depth": {"type": "integer", "description": "Max tree depth to traverse (default: 4). Higher = more detail but slower.", "default": 4}
        }
    },
    {
        "name": "find_ui_element",
        "description": "Find a specific UI element by role + name or automation_id. Returns element details including bounding_rect for clicking. Use this BEFORE click_ui_element to verify the element exists.",
        "parameters": {
            "window_title": {"type": "string", "description": "Window title to search in"},
            "role": {"type": "string", "description": "UI element role: Button, Edit, CheckBox, ComboBox, Menu, MenuItem, Tab, Tree, Text, Hyperlink, Slider, etc."},
            "name": {"type": "string", "description": "Element name/label (partial match, case-insensitive)"},
            "automation_id": {"type": "string", "description": "Automation ID (exact match, most precise)"}
        }
    },
    {
        "name": "click_ui_element",
        "description": "Click a UI element by role + name. More reliable than coordinate clicking — targets the element by its UI structure. Works for buttons, links, menu items, etc.",
        "parameters": {
            "window_title": {"type": "string", "description": "Window title"},
            "role": {"type": "string", "description": "Element role (Button, MenuItem, etc.)"},
            "name": {"type": "string", "description": "Element name/label"},
            "automation_id": {"type": "string", "description": "Automation ID (optional, most precise)"}
        }
    },
    {
        "name": "double_click_ui_element",
        "description": "Double-click a UI element by role + name. Use for opening files, selecting words, etc.",
        "parameters": {
            "window_title": {"type": "string", "description": "Window title"},
            "role": {"type": "string", "description": "Element role"},
            "name": {"type": "string", "description": "Element name/label"}
        }
    },
    {
        "name": "right_click_ui_element",
        "description": "Right-click a UI element to open context menu.",
        "parameters": {
            "window_title": {"type": "string", "description": "Window title"},
            "role": {"type": "string", "description": "Element role"},
            "name": {"type": "string", "description": "Element name/label"}
        }
    },
    {
        "name": "type_into_ui_element",
        "description": "Type text into a specific UI input element (textbox, search bar, etc.). More reliable than clipboard paste — uses the element's native input method. Clears field first by default.",
        "parameters": {
            "window_title": {"type": "string", "description": "Window title"},
            "role": {"type": "string", "description": "Element role (usually 'Edit' for text fields)"},
            "name": {"type": "string", "description": "Element name/label"},
            "text": {"type": "string", "description": "Text to type"},
            "clear_first": {"type": "boolean", "description": "Clear existing text first (default: true)", "default": True}
        }
    },
    {
        "name": "select_ui_dropdown",
        "description": "Select an option from a ComboBox/dropdown by visible text.",
        "parameters": {
            "window_title": {"type": "string", "description": "Window title"},
            "role": {"type": "string", "description": "Element role (usually 'ComboBox')"},
            "name": {"type": "string", "description": "Dropdown name/label"},
            "option_text": {"type": "string", "description": "Option text to select"}
        }
    },
    {
        "name": "toggle_ui_checkbox",
        "description": "Check/uncheck a checkbox element.",
        "parameters": {
            "window_title": {"type": "string", "description": "Window title"},
            "role": {"type": "string", "description": "Element role (usually 'CheckBox')"},
            "name": {"type": "string", "description": "Checkbox name/label"}
        }
    },
    {
        "name": "read_ui_text",
        "description": "Read all visible text from a UI element subtree. Useful for reading menus, panels, dialogs, status bars, or any window content.",
        "parameters": {
            "window_title": {"type": "string", "description": "Window title"},
            "role": {"type": "string", "description": "Element role (optional, defaults to whole window)"},
            "name": {"type": "string", "description": "Element name (optional)"}
        }
    },
    {
        "name": "set_ui_value",
        "description": "Set the value of a UI element (slider, textbox, etc.). Works with elements that support ValuePattern.",
        "parameters": {
            "window_title": {"type": "string", "description": "Window title"},
            "role": {"type": "string", "description": "Element role"},
            "name": {"type": "string", "description": "Element name/label"},
            "value": {"type": "string", "description": "Value to set"}
        }
    },
    {
        "name": "get_ui_state",
        "description": "Get the current state of a UI element (enabled, focusable, value, toggle_state). Useful for checking if an element is ready for interaction.",
        "parameters": {
            "window_title": {"type": "string", "description": "Window title"},
            "role": {"type": "string", "description": "Element role"},
            "name": {"type": "string", "description": "Element name/label"}
        }
    },

    # ── P7: Wait Tools — Prevent type_text / click failures ─────────────────
    {
        "name": "wait_for_app",
        "description": "Wait for an application window to appear and become ready. Use AFTER open_app and BEFORE type_into_ui_element, click_ui_element, or any UIA interaction. Prevents failures by ensuring the app has fully loaded.",
        "parameters": {
            "app_name": {"type": "string", "description": "App name to wait for (e.g. 'chrome', 'notepad')"},
            "window_title": {"type": "string", "description": "Window title to wait for (partial match). Alternative to app_name."},
            "timeout_seconds": {"type": "number", "description": "Max seconds to wait (default: 15)", "default": 15.0}
        }
    },
    {
        "name": "wait_for_element",
        "description": "Wait for a specific UI element to appear in the accessibility tree. Use BEFORE typing into or clicking an element that may not exist yet (e.g. after a page load or dialog transition).", "parameters": {
            "window_title": {"type": "string", "description": "Window title to search in"},
            "role": {"type": "string", "description": "Element role (Button, Edit, MenuItem, etc.)"},
            "name": {"type": "string", "description": "Element name/label"},
            "automation_id": {"type": "string", "description": "Automation ID (optional)"},
            "timeout_seconds": {"type": "number", "description": "Max seconds to wait (default: 10)", "default": 10.0},
            "must_be_enabled": {"type": "boolean", "description": "Wait until element is enabled, not just visible (default: false)", "default": False}
        }
    },
    {
        "name": "wait_for_text",
        "description": "Wait for specific text to appear anywhere in a window. Use after type_into_ui_element to confirm text was entered, or to wait for search results, loading indicators, or error messages to appear/disappear.",
        "parameters": {
            "window_title": {"type": "string", "description": "Window title to search in"},
            "text": {"type": "string", "description": "Text to wait for (case-insensitive substring match)"},
            "timeout_seconds": {"type": "number", "description": "Max seconds to wait (default: 10)", "default": 10.0},
            "must_not_contain": {"type": "string", "description": "Wait for this text to DISAPPEAR (optional, use for loading indicators)"}
        }
    },

    # ── P5: Skill Acquisition — learned procedural memory ──────────────────
    {
        "name": "execute_skill",
        "description": "Execute a learned skill (multi-step procedure) by ID. Run previously learned procedures like 'open chrome then gmail'.",
        "parameters": {
            "skill_id": {"type": "string", "description": "Skill ID (from list_skills)"}
        }
    },
    {
        "name": "list_skills",
        "description": "List all learned skills with their steps, usage count, and confidence.",
        "parameters": {}
    },
    {
        "name": "search_skills",
        "description": "Search for skills matching a query.",
        "parameters": {
            "query": {"type": "string", "description": "Search query to match against skill names, triggers, and descriptions"}
        }
    },
    {
        "name": "delete_skill",
        "description": "Delete a learned skill by ID. DESTRUCTIVE.",
        "parameters": {
            "skill_id": {"type": "string", "description": "Skill ID to delete"}
        }
    },

    # ── P8: Developer Additions (L12) ─────────────────────────────────────
    {
        "name": "git_clone",
        "description": "Clone a git repository to a local directory.",
        "parameters": {
            "url": {"type": "string", "description": "Repository URL to clone"},
            "destination": {"type": "string", "description": "Local directory path (optional)"}
        }
    },
    {
        "name": "run_code",
        "description": "Execute code in a sandboxed subprocess. Supports python, javascript/node, powershell, batch.",
        "parameters": {
            "language": {"type": "string", "enum": ["python", "javascript", "node", "powershell", "batch"], "description": "Programming language"},
            "code": {"type": "string", "description": "Code to execute"}
        }
    },
    {
        "name": "docker_list",
        "description": "List Docker containers or images.",
        "parameters": {
            "type": {"type": "string", "enum": ["containers", "images"], "description": "Type to list (default: containers)"}
        }
    },
    {
        "name": "docker_start",
        "description": "Start a Docker container by name.",
        "parameters": {
            "name": {"type": "string", "description": "Container name or ID"}
        }
    },
    {
        "name": "docker_stop",
        "description": "Stop a Docker container by name.",
        "parameters": {
            "name": {"type": "string", "description": "Container name or ID"}
        }
    },
    {
        "name": "database_query",
        "description": "Query a SQLite database. Returns columns, rows, and row count for SELECT queries.",
        "parameters": {
            "db_path": {"type": "string", "description": "Path to SQLite database file"},
            "query": {"type": "string", "description": "SQL query to execute"}
        }
    },
    {
        "name": "port_scan",
        "description": "Scan common ports on a host to find open services.",
        "parameters": {
            "host": {"type": "string", "description": "Host to scan (default: 127.0.0.1)"},
            "ports": {"type": "array", "items": {"type": "integer"}, "description": "Specific ports to scan (optional)"}
        }
    },

    # ── P8: Automation Additions (L14) ────────────────────────────────────
    {
        "name": "list_startup_programs",
        "description": "List programs that run at Windows startup.",
        "parameters": {}
    },
    {
        "name": "enable_startup_program",
        "description": "Add a program to Windows startup via registry.",
        "parameters": {
            "name": {"type": "string", "description": "Program name"},
            "path": {"type": "string", "description": "Full path to the executable"}
        }
    },
    {
        "name": "disable_startup_program",
        "description": "Remove a program from Windows startup.",
        "parameters": {
            "name": {"type": "string", "description": "Program name to remove from startup"}
        }
    },
    {
        "name": "clipboard_history",
        "description": "Access Windows clipboard history (Win+V). Returns recent clipboard items.",
        "parameters": {
            "max_items": {"type": "integer", "description": "Maximum items to return (default: 10)"}
        }
    },
    {
        "name": "toggle_airplane_mode",
        "description": "Toggle Windows airplane mode on or off.",
        "parameters": {
            "enable": {"type": "boolean", "description": "True to enable, false to disable"}
        }
    },
    {
        "name": "toggle_bluetooth",
        "description": "Toggle Windows Bluetooth on or off.",
        "parameters": {
            "enable": {"type": "boolean", "description": "True to enable, false to disable"}
        }
    },
    {
        "name": "set_wallpaper",
        "description": "Set the desktop wallpaper to an image file.",
        "parameters": {
            "path": {"type": "string", "description": "Full path to the image file"}
        }
    },
    {
        "name": "list_recent_files",
        "description": "List recently opened or modified files.",
        "parameters": {
            "max_items": {"type": "integer", "description": "Maximum items to return (default: 20)"}
        }
    },
    {
        "name": "create_restore_point",
        "description": "Create a Windows system restore point.",
        "parameters": {
            "description": {"type": "string", "description": "Description for the restore point"}
        }
    },
    {
        "name": "list_user_accounts",
        "description": "List local Windows user accounts.",
        "parameters": {}
    },

    # ── P8: Content & Utility Tools (L17) ─────────────────────────────────
    {
        "name": "calculate",
        "description": "Evaluate a math expression safely. Supports: +, -, *, /, **, %, sqrt, sin, cos, tan, log, abs, min, max, pi, e. Also handles '15% of 247' and unit conversions like '5 feet in meters'.",
        "parameters": {
            "expression": {"type": "string", "description": "Math expression to evaluate (e.g. '2 + 2', 'sqrt(16)', '15% of 247')"}
        }
    },
    {
        "name": "unit_convert",
        "description": "Convert between units of measurement. Supports: length (m, ft, km, mi, cm, in, mm, yd), weight (kg, lb, g, oz), temperature (c, f, k), volume (l, gal, ml, fl_oz), data (gb, mb, tb, kb), time (h, min, s, d), area (sqm, sqft, ha, acres).",
        "parameters": {
            "value": {"type": "number", "description": "Value to convert"},
            "from_unit": {"type": "string", "description": "Source unit (e.g. 'm', 'ft', 'kg', 'c')"},
            "to_unit": {"type": "string", "description": "Target unit (e.g. 'ft', 'm', 'lb', 'f')"}
        }
    },
    {
        "name": "timer",
        "description": "Set a countdown timer. May will send a toast notification when the timer expires.",
        "parameters": {
            "seconds": {"type": "number", "description": "Duration in seconds"},
            "label": {"type": "string", "description": "Timer label (e.g. 'pasta', 'meeting break')"}
        }
    },
    {
        "name": "speed_test",
        "description": "Run an internet speed test. Measures download speed in Mbps.",
        "parameters": {}
    },
    {
        "name": "hash_string",
        "description": "Generate a hash of a string. Supports: md5, sha1, sha256, sha512, sha384, blake2b.",
        "parameters": {
            "text": {"type": "string", "description": "Text to hash"},
            "algorithm": {"type": "string", "enum": ["md5", "sha1", "sha256", "sha512"], "description": "Hash algorithm (default: sha256)"}
        }
    },
    {
        "name": "base64_encode",
        "description": "Encode a string to Base64.",
        "parameters": {
            "text": {"type": "string", "description": "Text to encode"}
        }
    },
    {
        "name": "base64_decode",
        "description": "Decode a Base64 string back to text.",
        "parameters": {
            "encoded": {"type": "string", "description": "Base64 string to decode"}
        }
    },
    {
        "name": "create_qr_code",
        "description": "Generate a QR code image from text or a URL.",
        "parameters": {
            "data": {"type": "string", "description": "Text or URL to encode in the QR code"},
            "output_path": {"type": "string", "description": "Save path (optional, defaults to ~/.may/qrcodes/qr_code.png)"},
            "size": {"type": "integer", "description": "Image size in pixels (default: 300)"}
        }
    },
    {
        "name": "json_format",
        "description": "Pretty-print or validate a JSON string.",
        "parameters": {
            "json_string": {"type": "string", "description": "JSON string to format"},
            "indent": {"type": "integer", "description": "Indentation spaces (default: 2)"}
        }
    },
    {
        "name": "csv_to_json",
        "description": "Convert a CSV file to JSON.",
        "parameters": {
            "csv_path": {"type": "string", "description": "Path to the CSV file"}
        }
    },
    {
        "name": "json_to_csv",
        "description": "Convert a JSON file (array of objects) to CSV.",
        "parameters": {
            "json_path": {"type": "string", "description": "Path to the JSON file"},
            "output_path": {"type": "string", "description": "Output CSV path (optional)"}
        }
    },
    {
        "name": "compare_images",
        "description": "Compare two images structurally using perceptual hashing.",
        "parameters": {
            "path1": {"type": "string", "description": "Path to first image"},
            "path2": {"type": "string", "description": "Path to second image"}
        }
    },
]
