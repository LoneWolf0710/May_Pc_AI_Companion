"""Command Router — maps commands to the correct layer handler.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md:

The router sits between the Command Bus and the 9 Control Layers.
It validates the layer name and delegates to the registered handler.

Layer Registry:
  L1_filesystem   → filesystem
  L2_process      → process
  L3_application  → application
  L4_window       → window
  L5_input        → input
  L6_registry     → registry
  L7_services     → services
  L8_system       → system
  L9_browser      → browser
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from .bus import CommandBus, Command, Result

logger = logging.getLogger("may.core.router")

# All valid layer names
VALID_LAYERS = frozenset({
    "filesystem",
    "process",
    "application",
    "window",
    "input",
    "registry",
    "services",
    "system",
    "browser",
    # P5: Expanded layers (L10-L15)
    "network",
    "media",
    "developer",
    "cloud",
    "automation",
    "advanced",
    # P7: UIAutomation accessibility tree
    "uiautomation",
    # P7: Post-action verification
    "verify",
    # P8: Content & utility tools
    "content_tools",
})

# ── Pre-flight Safety Checks ────────────────────────────────────────────────
# Actions that require explicit user confirmation before execution.
# The LLM should never auto-execute these without asking.
DESTRUCTIVE_ACTIONS: dict[str, set[str]] = {
    "system":       {"shutdown", "restart", "logoff", "hibernate", "disable_adapter"},
    "filesystem":   {"delete_file", "delete_folder", "delete_folder_tree", "batch_delete"},
    "process":      {"kill_process", "kill_process_tree", "set_memory_limit", "set_cpu_limit"},
    "application":  {"force_close_app", "uninstall_app"},
    "services":     {"remove_service", "delete_task", "disable_task"},
    "window":       {"force_close_window"},
    "input":        {"screenshot_full", "screenshot_region"},
    "registry":     {"delete_value", "delete_key", "set_key_permissions", "take_ownership"},
    # P5: Expanded destructive actions
    "network":      {"disable_firewall", "remove_firewall_rule", "stop_wifi_hotspot"},
    "media":        {"disable_audio_device"},
    "developer":    {"kill_port"},
    "automation":   {"delete_scheduled_task", "stop_script", "delete_workflow"},
    "advanced":     {"defragment_drive", "check_disk_errors", "optimize_system", "delete_power_plan"},
}

# Actions that require elevated (admin) privileges
ADMIN_REQUIRED_ACTIONS: dict[str, set[str]] = {
    "system":       {"shutdown", "restart", "disable_adapter", "enable_adapter",
                      "add_firewall_rule", "remove_firewall_rule"},
    "services":     {"install_service", "remove_service", "change_credentials",
                      "set_startup_type", "enable_task", "disable_task"},
    "process":      {"set_memory_limit", "set_cpu_limit", "set_priority"},
    "registry":     {"set_key_permissions", "take_ownership"},
    "application":  {"launch_as_admin"},
    # P5: Expanded admin-required actions
    "network":      {"add_firewall_rule", "remove_firewall_rule", "enable_firewall", "disable_firewall",
                      "set_static_ip", "set_dns_servers", "create_wifi_hotspot", "stop_wifi_hotspot"},
    "advanced":     {"set_power_plan", "create_power_plan", "delete_power_plan", "defragment_drive",
                      "optimize_system", "set_environment_variable", "delete_environment_variable"},
    "automation":   {"create_scheduled_task", "delete_scheduled_task", "run_powershell"},
}

# Layer name aliases for convenience
LAYER_ALIASES: dict[str, str] = {
    "file":     "filesystem",
    "files":    "filesystem",
    "proc":     "process",
    "procs":    "process",
    "apps":     "application",
    "win":      "window",
    "wins":     "window",
    "keyboard": "input",
    "mouse":    "input",
    "reg":      "registry",
    "svc":      "services",
    "sys":      "system",
    "browser":  "browser",
    "web":      "browser",
    # P5: Expanded layer aliases
    "net":      "network",
    "firewall": "network",
    "audio":    "media",
    "video":    "media",
    "dev":      "developer",
    "git":      "developer",
    "npm":      "developer",
    "api":      "cloud",
    "webhook":  "cloud",
    "cron":     "automation",
    "script":   "automation",
    "hw":       "advanced",
    "power":    "advanced",
    "optimize": "advanced",
    # P7: UIAutomation aliases
    "uia":          "uiautomation",
    "accessibility": "uiautomation",
    "a11y":         "uiautomation",
    # P7: Verification aliases
    "verification":  "verify",
    "screenshot_verify": "verify",
    # P8: Content & utility aliases
    "content":       "content_tools",
    "tools":         "content_tools",
    "math":          "content_tools",
    "encoding":      "content_tools",
    "convert":       "content_tools",
}

# Layer handler type
LayerHandler = Callable[[str, dict[str, Any]], Awaitable[Result]]


class Router:
    """Maps incoming commands to the correct control layer.

    The router validates and normalizes the layer name, then
    delegates to the CommandBus for actual execution.

    Usage:
        router = Router(bus)
        router.register_layer("filesystem", filesystem_handler)
        result = await router.route(command)
    """

    def __init__(self, bus: CommandBus):
        self.bus = bus
        self._layer_handlers: dict[str, LayerHandler] = {}

    def register_layer(self, layer_name: str, handler: LayerHandler):
        """Register a handler for a specific layer.

        Registers both the canonical name and any aliases.
        """
        canonical = LAYER_ALIASES.get(layer_name, layer_name)
        if canonical not in VALID_LAYERS:
            logger.warning("Registering non-standard layer: %s", canonical)

        self._layer_handlers[canonical] = handler
        self.bus.register(canonical, handler)
        logger.info("Registered layer: %s", canonical)

    def normalize_layer(self, layer: str) -> str:
        """Resolve layer aliases to canonical names.

        Examples:
            "file"      → "filesystem"
            "proc"      → "process"
            "win"       → "window"
            "keyboard"  → "input"
            "sys"       → "system"
        """
        return LAYER_ALIASES.get(layer.lower().strip(), layer.lower().strip())

    def validate_command(self, cmd: Command) -> str | None:
        """Validate a command before routing.

        Returns None if valid, or an error message string.
        """
        # Normalize layer name
        cmd.layer = self.normalize_layer(cmd.layer)

        if not cmd.layer:
            return "Missing required field: 'layer'"

        if not cmd.action:
            return "Missing required field: 'action'"

        if cmd.layer not in VALID_LAYERS and cmd.layer not in self._layer_handlers:
            return (
                f"Unknown layer: '{cmd.layer}'. "
                f"Valid layers: {sorted(VALID_LAYERS)}"
            )

        if cmd.timeout <= 0:
            return f"Invalid timeout: {cmd.timeout}s (must be > 0)"

        if cmd.timeout > 300:
            return f"Timeout too large: {cmd.timeout}s (max 300s)"

        return None  # Valid

    def check_safety(self, layer: str, action: str) -> dict[str, bool]:
        """Pre-flight safety check for an action.

        Returns a dict indicating:
          - destructive: True if the action can cause data loss or system changes
          - admin_required: True if the action needs elevated privileges
        """
        destructive = action in DESTRUCTIVE_ACTIONS.get(layer, set())
        admin_required = action in ADMIN_REQUIRED_ACTIONS.get(layer, set())
        return {"destructive": destructive, "admin_required": admin_required}

    async def route(self, cmd: Command) -> Result:
        """Validate and route a command through the bus.

        Args:
            cmd: The command to route.

        Returns:
            Result from the layer handler, or an error Result.
        """
        # Normalize layer name first (without mutating cmd in-place)
        original_layer = cmd.layer
        cmd.layer = self.normalize_layer(cmd.layer)

        # Validate
        error = self.validate_command(cmd)
        if error:
            cmd.layer = original_layer  # Restore on failure
            logger.warning("Command validation failed: %s", error)
            return Result.error_result(cmd.id, error)

        # Pre-flight safety check
        safety = self.check_safety(cmd.layer, cmd.action)
        if safety.get("destructive"):
            logger.warning("DESTRUCTIVE action requested: %s.%s", cmd.layer, cmd.action)
        if safety.get("admin_required"):
            logger.info("Admin-required action: %s.%s", cmd.layer, cmd.action)

        # Dispatch through the bus
        result = await self.bus.dispatch(cmd)
        cmd.layer = original_layer  # Restore after dispatch
        return result

    def list_layers(self) -> dict[str, list[str]]:
        """Return a map of registered layers and their available actions."""
        result = {}
        for layer_name, handler in self._layer_handlers.items():
            # We don't introspect actions from the handler,
            # just report that the layer is registered
            result[layer_name] = ["registered"]
        return result
