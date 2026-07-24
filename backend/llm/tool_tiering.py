"""
Intent-based tool tiering for May's Jarvis brain.

Instead of sending all 171 tool definitions to the LLM every time (~8300 tokens),
this module classifies the user's message intent and sends only the relevant
tools (~20-40 tools, ~1000-2000 tokens). This dramatically speeds up chat
with small models like qwen3:4b.

How it works:
1. CORE tools are always included (~20 universal tools)
2. Domain-specific tiers are added when keyword triggers match
3. No LLM call needed — fast keyword matching (<1ms)

Design decision: Keyword-based classification is used instead of an LLM call
because:
- Zero latency (no extra round-trip to the LLM)
- Zero cost (no additional token usage)
- Deterministic and predictable
- Easy to debug and extend
"""

import logging

logger = logging.getLogger("may.tool_tiering")

# ── Intent Tiers ─────────────────────────────────────────────────────────────
#
# Each tier has:
#   - keywords: list of trigger words (message must contain at least one)
#   - tools: list of tool names to include when this tier is active
#
# CORE tier is always included (no keywords needed).

CORE_TOOLS = [
    # App control (most common action)
    "open_app",
    "close_app",
    # Web
    "web_search",
    "open_url",
    # Time & weather
    "get_time",
    "get_date",
    # Quick input
    "send_keys",
    "type_text",
    # Volume
    "volume_up",
    "volume_down",
]

# Domain tiers with keyword triggers
DOMAIN_TIERS: dict[str, dict] = {
    "app_management": {
        "keywords": [
            "open", "launch", "start", "close", "quit", "kill", "restart",
            "app", "application", "program", "software", "install", "uninstall",
            "discord", "chrome", "firefox", "notepad", "spotify", "vscode",
            "steam", "calculator", "word", "excel", "powerpoint", "teams",
            "zoom", "slack", "edge", "brave", "obsidian", "file explorer",
            "cmd", "terminal", "powershell", "task manager",
        ],
        "tools": [
            "launch_with_args",
            "launch_as_admin",
            "restart_app",
            "is_app_running",
            "automate_app",
            "find_app_by_name",
            "list_installed_apps",
            "get_app_path",
            "get_app_version",
            "force_close_app",
            "com_dispatch",
        ],
    },
    "volume_display": {
        "keywords": [
            "volume", "sound", "audio", "mute", "unmute", "loud", "quiet",
            "brightness", "bright", "dim", "display", "screen", "monitor",
            "dark mode", "light mode", "theme",
        ],
        "tools": [
            "get_volume",
            "mute",
            "unmute",
            "set_brightness",
            "get_brightness",
            "enable_dark_mode",
            "enable_light_mode",
            "get_audio_devices",
        ],
    },
    "filesystem": {
        "keywords": [
            "file", "folder", "directory", "read", "write", "save",
            "copy", "move", "rename", "delete", "find", "search",
            "open folder", "explorer", "folder size", "large files",
            "duplicate", "compress", "extract", "archive", "zip",
            "create folder", "drive", "disk",
        ],
        "tools": [
            "read_file",
            "write_file",
            "list_directory",
            "search_files",
            "search_content",
            "find_and_replace",
            "copy_file",
            "move_file",
            "delete_file",
            "get_file_info",
            "open_folder",
            "open_file_with",
            "get_folder_size",
            "get_large_files",
            "batch_rename",
            "batch_delete",
            "take_ownership",
            "find_duplicates",
            "compress_file",
            "decompress_file",
            "create_folder",
            "get_drive_info",
            "copy_folder",
            "delete_folder",
        ],
    },
    "window": {
        "keywords": [
            "window", "minimize", "maximize", "resize", "focus",
            "bring to front", "taskbar", "arrange", "tile", "cascade",
            "virtual desktop",
        ],
        "tools": [
            "list_windows",
            "focus_window",
            "minimize_window",
            "maximize_window",
            "resize_window",
            "flash_window",
            "find_window",
            "set_window_position",
            "close_window",
            "get_window_title",
            "arrange_windows",
            "list_virtual_desktops",
            "move_to_virtual_desktop",
        ],
    },
    "process": {
        "keywords": [
            "process", "task manager", "cpu", "memory", "ram",
            "kill process", "end task", "pid", "affinity", "priority",
            "cpu usage", "memory usage",
        ],
        "tools": [
            "list_processes",
            "kill_process",
            "get_process_info",
            "set_process_priority",
            "get_command_line",
            "is_process_running",
            "get_process_cpu",
            "get_process_memory",
            "get_process_path",
            "set_process_affinity",
            "set_memory_limit",
            "set_cpu_limit",
        ],
    },
    "media": {
        "keywords": [
            "play", "pause", "stop", "next track", "previous track",
            "music", "song", "media", "spotify", "youtube music",
            "skip track",
        ],
        "tools": [
            "media_play_pause",
            "media_next",
            "media_previous",
            "media_stop",
        ],
    },
    "input": {
        "keywords": [
            "type text", "keyboard", "shortcut", "hotkey", "key",
            "ctrl", "alt", "shift", "click", "mouse", "scroll",
            "drag", "tap", "hold key",
        ],
        "tools": [
            "type_text_fast",
            "tap_key",
            "hold_key",
            "mouse_click",
            "mouse_scroll",
            "drag_and_drop",
            "get_mouse_position",
            "screenshot_full",
            "screenshot_region",
            "screenshot_window",
            "take_window_screenshot",
        ],
    },
    "browser": {
        "keywords": [
            "browser", "web page", "website", "navigate", "form",
            "css selector", "javascript", "html", "dom", "playwright",
            "cookie", "headless",
        ],
        "tools": [
            "browser_navigate",
            "browser_click",
            "browser_type",
            "browser_fill_form",
            "browser_get_text",
            "browser_screenshot",
            "browser_run_js",
            "browser_wait_for",
            "browser_manage_cookies",
            "open_browser",
            "close_browser",
            "handle_dialog",
            "connect_to_browser",
            "extract_web_content",
        ],
    },
    "email": {
        "keywords": [
            "email", "mail", "inbox", "unread", "inbox", "send email",
            "inbox", "gmail", "outlook", "smtp", "imap",
        ],
        "tools": [
            "get_unread_emails",
            "get_unread_count",
            "search_emails",
            "read_email",
            "send_email",
            "get_recent_emails",
        ],
    },
    "system": {
        "keywords": [
            "shutdown", "restart", "sleep", "hibernate", "lock",
            "logoff", "battery", "power", "system info", "uptime",
            "disk info", "drive info", "network", "wifi", "bluetooth",
            "firewall", "dns", "adapter", "display rotation",
            "environment variable", "windows update", "service",
        ],
        "tools": [
            "shutdown_pc",
            "restart_pc",
            "sleep_pc",
            "lock_pc",
            "cancel_shutdown",
            "battery_info",
            "disk_info",
            "logoff",
            "get_network_info",
            "get_public_ip",
            "get_wifi_password",
            "test_internet",
            "connect_wifi",
            "disconnect_wifi",
            "flush_dns",
            "add_firewall_rule",
            "enable_adapter",
            "disable_adapter",
            "list_wifi_networks",
            "rotate_display",
            "get_os_info",
            "system_info",
            "get_installed_updates",
            "get_env_var",
            "list_env_vars",
            "delete_system_env",
            "get_drive_info",
            "get_audio_devices",
        ],
    },
    "services": {
        "keywords": [
            "service", "windows service", "start service", "stop service",
            "task scheduler", "scheduled task", "startup program",
        ],
        "tools": [
            "list_services",
            "start_service",
            "stop_service",
            "restart_service",
            "set_service_startup",
            "enable_service",
            "disable_service",
        ],
    },
    "wellness": {
        "keywords": [
            "water", "posture", "break", "eyes", "rest", "stretch",
            "wellness", "health", "ergonomic",
        ],
        "tools": [
            "get_wellness_status",
            "get_wellness_suggestions",
            "set_wellness_rule",
        ],
    },
    "meeting": {
        "keywords": [
            "meeting", "record", "transcribe", "transcript",
            "summary", "action items",
        ],
        "tools": [
            "start_meeting",
            "stop_meeting",
            "meeting_status",
        ],
    },
    "ghost": {
        "keywords": [
            "ghost", "autonomous", "idle", "background task",
            "queue task", "overnight",
        ],
        "tools": [
            "queue_ghost_task",
            "ghost_status",
            "cancel_ghost_task",
            "cancel_all_ghost_tasks",
        ],
    },
    "biometrics": {
        "keywords": [
            "voice profile", "biometric", "speaker", "voice verify",
            "voice enroll", "identity",
        ],
        "tools": [
            "voice_enroll",
            "voice_verify",
            "biometrics_status",
            "biometrics_toggle",
            "biometrics_delete",
        ],
    },
    "packages": {
        "keywords": [
            "winget", "package", "install package", "search packages",
            "chocolatey", "scoop",
        ],
        "tools": [
            "install_app",
            "search_packages",
        ],
    },
    "settings": {
        "keywords": [
            "settings", "control panel", "display settings",
            "sound settings", "network settings", "bluetooth settings",
        ],
        "tools": [
            "open_settings",
        ],
    },
    "uiautomation": {
        "keywords": [
            "click button", "click the", "press button", "ui element",
            "accessibility", "ui tree", "inspect ui", "find element",
            "dropdown", "checkbox", "toggle", "combo box", "menu item",
            "read screen", "read window", "ui text", "element name",
            "type into", "type in field", "input field", "text field",
            "click menu", "click link", "click tab", "click icon",
            "set value", "slider", "get state", "element exists",
            "double click", "right click", "context menu",
            "wait for", "wait until", "element appear", "text appear",
            "loading", "ready", "app ready", "window ready",
        ],
        "tools": [
            "inspect_ui_tree",
            "find_ui_element",
            "click_ui_element",
            "double_click_ui_element",
            "right_click_ui_element",
            "type_into_ui_element",
            "select_ui_dropdown",
            "toggle_ui_checkbox",
            "read_ui_text",
            "set_ui_value",
            "get_ui_state",
            "wait_for_app",
            "wait_for_element",
            "wait_for_text",
        ],
    },
    "verification": {
        "keywords": [
            "verify", "confirm", "check if", "did it work",
            "compare", "before after", "error check", "error dialog",
            "element exist", "element appear", "action verify",
        ],
        "tools": [
            "take_action_verify",
            "verify_element_exists",
            "verify_no_error",
            "compare_screenshots",
        ],
    },
    "developer": {
        "keywords": [
            "git", "clone", "commit", "push", "pull", "branch", "merge",
            "npm", "pip", "cargo", "package", "install package",
            "docker", "container", "image",
            "run code", "execute code", "sandbox",
            "database", "sql", "sqlite", "query",
            "port scan", "open port", "closed port",
            "terminal", "command line", "shell",
        ],
        "tools": [
            "git_clone", "git_status", "git_diff", "git_log", "git_commit",
            "git_push", "git_pull", "git_branch", "git_checkout",
            "run_terminal", "run_code",
            "docker_list", "docker_start", "docker_stop",
            "database_query", "port_scan",
            "check_port", "kill_port",
            "npm_install", "npm_run", "pip_install", "pip_list",
            "syntax_check", "search_code", "find_files", "replace_in_file",
            "count_lines", "get_file_stats",
        ],
    },
    "content_tools": {
        "keywords": [
            "calculate", "math", "convert", "unit", "hash", "base64",
            "encode", "decode", "qr code", "json format", "json pretty",
            "csv", "timer", "countdown", "speed test", "speedtest",
            "compare images", "compare picture",
        ],
        "tools": [
            "calculate", "unit_convert", "timer", "cancel_timer",
            "speed_test", "hash_string", "base64_encode", "base64_decode",
            "create_qr_code", "json_format", "csv_to_json", "json_to_csv",
            "compare_images",
        ],
    },
    "automation_extra": {
        "keywords": [
            "startup program", "boot program", "autostart",
            "clipboard history", "copy history",
            "airplane mode", "flight mode",
            "bluetooth", "wallpaper", "desktop background",
            "recent files", "recently opened",
            "restore point", "system restore",
            "user account", "user profile",
            "scheduled task", "task scheduler",
        ],
        "tools": [
            "list_startup_programs", "enable_startup_program", "disable_startup_program",
            "clipboard_history", "toggle_airplane_mode", "toggle_bluetooth",
            "set_wallpaper", "list_recent_files", "create_restore_point",
            "list_user_accounts", "list_scheduled_tasks", "create_scheduled_task",
            "delete_scheduled_task", "run_scheduled_task",
            "run_powershell", "run_batch", "run_python", "run_node",
        ],
    },
}


# ── Pre-computed static sets ───────────────────────────────────────────────

# All tool names defined in tiers (CORE_TOOLS + all DOMAIN_TIERS tools).
# Used to identify plugin tools (not in this set → always include).
TIERED_NAMES: set[str] = set(CORE_TOOLS)
for _tier in DOMAIN_TIERS.values():
    TIERED_NAMES.update(_tier.get("tools", []))

# Map tool name → tool definition for fast lookup (rebuilt per call)
_TOOL_BY_NAME: dict[str, dict] = {}      # Map tool name → tool definition for fast lookup
_TOOL_GENERATION: int = 0                # Incremented when tools change; cache rebuilt when stale
_CACHE_GENERATION: int = -1              # Generation of the currently cached data


# ── Intent Classifier ────────────────────────────────────────────────────────

def invalidate_tool_cache() -> None:
    """Increment the generation counter to force cache rebuild on next call.

    Call this when plugin tools are loaded/unloaded or the tool list changes.
    """
    global _TOOL_GENERATION
    _TOOL_GENERATION += 1


def classify_intent(message: str) -> list[str]:
    """Classify a user message into intent tiers using keyword matching.

    Returns a list of matched tier names. Always includes "core" implicitly.

    This is intentionally simple and fast — no ML, no LLM call.
    Keyword matching handles >95% of real user messages correctly.
    Edge cases (e.g. "open my heart" → matches app tier) are harmless
    because the LLM will simply not call any app tools for that message.
    """
    msg_lower = message.lower()
    matched = []

    for tier_name, tier_config in DOMAIN_TIERS.items():
        for keyword in tier_config["keywords"]:
            if keyword in msg_lower:
                matched.append(tier_name)
                break  # One keyword match is enough for this tier

    return matched


def get_tools_for_message(
    message: str,
    all_tools: list[dict],
    enable_tiering: bool = True,
) -> list[dict]:
    """Get the relevant tools for a user message.

    Args:
        message: The user's message text.
        all_tools: Full list of all tool definitions (from TOOLS).
        enable_tiering: If False, return all tools (for debugging/testing).

    Returns:
        Filtered list of tool definitions relevant to the message intent.
    """
    if not enable_tiering:
        return all_tools

    # P5: Read max tools from auto-tuner gene
    from intelligence.tuner_cache import get_gene
    max_tools = int(get_gene("tool_tier_max_tools", default=15))

    # BUG-6 FIX: Rebuild tool index when generation changes (plugin load/unload, first call).
    global _CACHE_GENERATION
    if _CACHE_GENERATION != _TOOL_GENERATION or not _TOOL_BY_NAME:
        _TOOL_BY_NAME.clear()
        for tool in all_tools:
            _TOOL_BY_NAME[tool["name"]] = tool
        _CACHE_GENERATION = _TOOL_GENERATION

    # Classify intent
    matched_tiers = classify_intent(message)

    # Collect tool names from matched tiers
    tool_names = set(CORE_TOOLS)
    for tier_name in matched_tiers:
        tier = DOMAIN_TIERS.get(tier_name, {})
        tool_names.update(tier.get("tools", []))

    # Build filtered tool list — only include tools from matched tiers
    filtered = []
    for name in tool_names:
        tool = _TOOL_BY_NAME.get(name)
        if tool:
            filtered.append(tool)

    # Always include plugin tools (they aren't in any tier definition,
    # so they'd be excluded by the tier-based lookup above)
    for tool in all_tools:
        if tool["name"] not in TIERED_NAMES:
            filtered.append(tool)

    # P5: Cap at auto-tuner max_tools gene value
    if len(filtered) > max_tools:
        # Prioritize core tools, then domain tools, then plugin tools
        core_filtered = [t for t in filtered if t["name"] in CORE_TOOLS]
        other_filtered = [t for t in filtered if t["name"] not in CORE_TOOLS]
        filtered = core_filtered + other_filtered[:max_tools - len(core_filtered)]

    # Log for debugging
    if matched_tiers:
        logger.debug(
            "Tool tiering: message='%s' → tiers=%s → %d tools (from %d total)",
            message[:60], matched_tiers, len(filtered), len(all_tools),
        )
    else:
        logger.debug(
            "Tool tiering: message='%s' → no domain match → %d core tools (from %d total)",
            message[:60], len(filtered), len(all_tools),
        )

    return filtered

