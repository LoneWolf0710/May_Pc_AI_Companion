"""Risk Classifier — Action risk tier classification.

Per MAY_FINAL_ARCHITECTURE.md Part 5 (Immune System):

Every tool execution is classified into a risk tier before execution:
- SAFE: Read-only or reversible actions (get_time, screenshot, open_app)
- MODERATE: Actions with side effects but easily reversible (type_text, set_volume)
- DESTRUCTIVE: Actions that delete, kill, or send data (delete_file, kill_process, send_email)
- CRITICAL: Actions that could damage the system (format_disk, disable_service, modify_registry_system)

Risk tiers drive the confirmation flow:
- SAFE: Execute immediately, no confirmation
- MODERATE: Execute immediately, log for review
- DESTRUCTIVE: Requires user confirmation (unless in TAKEOVER mode)
- CRITICAL: ALWAYS requires confirmation, regardless of mode
"""

from __future__ import annotations

import logging

logger = logging.getLogger("may.system.risk_classifier")


class RiskTier:
    """Risk tier constants."""
    SAFE = "safe"
    MODERATE = "moderate"
    DESTRUCTIVE = "destructive"
    CRITICAL = "critical"


# ── Risk Classification Tables ──────────────────────────────────────────
# Maps tool names to their risk tiers.
# Tools not in any table default to SAFE.

# SAFE: Read-only, informational, or trivially reversible
SAFE_TOOLS = {
    # Information queries
    "get_time", "get_date", "battery_info", "get_system_info",
    "get_network_info", "test_internet", "list_processes",
    "list_windows", "find_window", "get_active_window",
    # Read-only file ops
    "read_file", "list_directory", "search_files", "get_folder_size",
    "find_duplicates",
    # Media
    "screenshot", "screenshot_full", "screenshot_region", "screenshot_window",
    "take_window_screenshot", "describe_screen",
    # App discovery
    "open_app", "open_folder",  # Open is safe — it just launches
    "close_app",  # Close is safe — easily reversible (reopen)
    # Clipboard
    "clipboard_copy", "clipboard_paste", "clipboard_get",
    # Browser
    "browser_navigate", "browser_screenshot", "browser_get_text",
    "browser_click", "browser_type", "browser_scroll",
    # Memory
    "memory_search", "memory_store", "memory_get", "memory_list",
    # Voice
    "voice_enroll", "voice_verify", "biometrics_status",
    # System info (read-only)
    "get_audio_devices", "get_display_info", "get_browser_tabs",
    "check_service_status",
    # Wake word / proactive
    "get_wellness_status", "get_wellness_suggestions",
    "get_screen_stats",
}

# MODERATE: Side effects, but easily reversible
MODERATE_TOOLS = {
    # Text input
    "type_text", "send_keys", "hotkey",
    # Volume / brightness
    "set_volume", "volume_up", "volume_down", "set_mute",
    "set_brightness",
    # Window management
    "focus_window", "minimize_window", "maximize_window",
    "resize_window", "move_window",
    # File creation (non-destructive)
    "write_file", "create_folder",
    # Run command
    "run_powershell", "run_command",
    # Network
    "set_wifi", "set_bluetooth",
    # App management (non-destructive)
    "install_app", "close_app",
    # Clipboard write
    "clipboard_set",
    # Environment variables (non-system)
    "set_environment_variable",
    # Browser control
    "browser_fill_form", "browser_select",
    "browser_accept_dialog", "browser_dismiss_dialog",
    # Control modes
    "set_control_mode",
}

# DESTRUCTIVE: Deletes data, kills processes, sends external communication
DESTRUCTIVE_TOOLS = {
    # Process control
    "kill_process", "force_close_app",
    # File deletion
    "delete_file", "delete_folder", "move_file", "copy_file",
    # External communication
    "send_email", "send_notification",
    # Service management
    "enable_service", "disable_service", "restart_service",
    "start_service", "stop_service",
    # Task scheduler
    "create_scheduled_task", "delete_scheduled_task",
    # Registry (user-level)
    "set_registry_value", "delete_registry_value",
    # System
    "set_system_volume",  # Can go to 0 or 100
    "lock_screen",
    # Firewall
    "add_firewall_rule", "remove_firewall_rule",
    # Voice
    "voice_delete",
}

# CRITICAL: Could damage the system or cause data loss
CRITICAL_TOOLS = {
    # System power
    "shutdown_pc", "restart_pc", "sleep_pc", "hibernate_pc",
    # Disk operations
    "format_disk", "partition_disk",
    # System services
    "disable_system_service", "modify_system_registry",
    # Batch operations
    "batch_delete", "batch_move",
    # Privilege escalation
    "run_as_admin", "run_as_system",
    # Environment (system-level)
    "delete_system_environment_variable",
}

# Build reverse lookup for O(1) classification
_RISK_MAP: dict[str, str] = {}
for tool in SAFE_TOOLS:
    _RISK_MAP[tool] = RiskTier.SAFE
for tool in MODERATE_TOOLS:
    _RISK_MAP[tool] = RiskTier.MODERATE
for tool in DESTRUCTIVE_TOOLS:
    _RISK_MAP[tool] = RiskTier.DESTRUCTIVE
for tool in CRITICAL_TOOLS:
    _RISK_MAP[tool] = RiskTier.CRITICAL


def classify_action(tool_name: str, params: dict | None = None) -> str:
    """Classify a tool action into a risk tier.

    Args:
        tool_name: The tool/action name
        params: Optional tool parameters for context-aware classification

    Returns:
        Risk tier string: "safe", "moderate", "destructive", or "critical"
    """
    # Direct lookup
    tier = _RISK_MAP.get(tool_name)
    if tier:
        # Context-aware upgrades
        if tier == RiskTier.MODERATE and params:
            tier = _upgrade_for_params(tool_name, params, tier)
        return tier

    # Pattern-based fallback for unknown tools
    return _classify_by_name(tool_name)


def _upgrade_for_params(tool_name: str, params: dict, current_tier: str) -> str:
    """Upgrade risk tier based on tool parameters.

    Some moderate tools become destructive with certain parameters:
    - write_file to system directories → destructive
    - type_text with very long content → stays moderate (just text)
    - set_volume to extreme values → stays moderate (reversible)
    """
    # write_file to system directories
    if tool_name == "write_file":
        path = params.get("path", "").lower()
        system_dirs = [
            "c:\\windows", "c:\\program files", "c:\\programdata",
            "\\system32", "\\drivers",
        ]
        if any(sd in path for sd in system_dirs):
            return RiskTier.DESTRUCTIVE

    # run_powershell with destructive keywords
    if tool_name == "run_powershell":
        command = params.get("command", "").lower()
        destructive_keywords = [
            "remove-item", "del ", "rmdir", "format-",
            "stop-process", "disable-", "remove-service",
            "shutdown", "restart", "set-executionpolicy",
        ]
        if any(kw in command for kw in destructive_keywords):
            return RiskTier.DESTRUCTIVE

    return current_tier


def _classify_by_name(tool_name: str) -> str:
    """Classify an unknown tool by name patterns."""
    name_lower = tool_name.lower()

    # Critical patterns
    if any(kw in name_lower for kw in ["shutdown", "restart", "format", "disable_system"]):
        return RiskTier.CRITICAL

    # Destructive patterns
    if any(kw in name_lower for kw in ["delete", "kill", "remove", "send_email", "send_notification"]):
        return RiskTier.DESTRUCTIVE

    # Moderate patterns
    if any(kw in name_lower for kw in ["set_", "write_", "create_", "run_", "send_", "focus_"]):
        return RiskTier.MODERATE

    # Default to safe
    return RiskTier.SAFE


def needs_confirmation(tool_name: str, params: dict | None = None, control_mode: str = "normal") -> bool:
    """Determine if a tool execution requires user confirmation.

    Per MAY_FINAL_ARCHITECTURE.md Part 5:
    - CRITICAL always requires confirmation — no exceptions
    - DESTRUCTIVE requires confirmation in most modes (only 'automation' bypasses)
    - MODERATE and SAFE execute without confirmation

    Args:
        tool_name: The tool/action name
        params: Optional tool parameters
        control_mode: Current control mode (normal, focus, silent, automation)

    Returns:
        True if confirmation is required
    """
    tier = classify_action(tool_name, params)

    if tier == RiskTier.CRITICAL:
        return True  # Always require confirmation

    if tier == RiskTier.DESTRUCTIVE:
        # Automation mode allows destructive actions without confirmation
        # All other modes require confirmation
        return control_mode != "automation"

    return False  # Safe and moderate never need confirmation


def get_risk_summary() -> dict:
    """Get a summary of all risk tiers and their tool counts."""
    return {
        "safe": {"count": len(SAFE_TOOLS), "tools": sorted(SAFE_TOOLS)},
        "moderate": {"count": len(MODERATE_TOOLS), "tools": sorted(MODERATE_TOOLS)},
        "destructive": {"count": len(DESTRUCTIVE_TOOLS), "tools": sorted(DESTRUCTIVE_TOOLS)},
        "critical": {"count": len(CRITICAL_TOOLS), "tools": sorted(CRITICAL_TOOLS)},
        "total_classified": len(_RISK_MAP),
        "default_tier": "safe",
    }
