"""Plugin system for May — allows extending capabilities at runtime.

Plugins register new tools into the LLM's tool registry. The Jarvis brain
sees plugin tools alongside built-in tools. Plugin tool calls are routed
to the plugin's execute() method.

Usage:
    from plugins import get_plugin_manager
    manager = get_plugin_manager()
    manager.load_plugin("spotify")
    # New tools are now available to the LLM
"""

from __future__ import annotations

import importlib
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("may.plugins")

# Plugin storage directory
PLUGINS_DIR = os.path.join(os.path.expanduser("~"), ".may", "plugins")
PLUGIN_CONFIG = os.path.join(PLUGINS_DIR, "installed.json")


class BasePlugin:
    """Base class for May plugins.

    Subclass this to create a plugin. Define:
    - name: str — unique plugin identifier
    - version: str — semver version
    - description: str — human-readable description
    - tools: list[dict] — tool JSON schemas (same format as tools.py TOOLS)
    - execute(tool_name, params) -> str — handle a tool call
    """
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    tools: list[dict] = []

    def execute(self, tool_name: str, params: dict) -> str:
        """Execute a tool call. Override in subclass.

        Args:
            tool_name: The tool name from the tools list
            params: The parameters from the LLM

        Returns:
            A string result for the LLM
        """
        raise NotImplementedError(f"Plugin {self.name} did not implement execute()")

    def get_tools(self) -> list[dict]:
        """Return tool definitions for the LLM."""
        return self.tools

    def on_load(self):
        """Called when the plugin is loaded. Override for initialization."""
        pass

    def on_unload(self):
        """Called when the plugin is unloaded. Override for cleanup."""
        pass

    def get_info(self) -> dict:
        """Get plugin info as a dict."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "tool_count": len(self.tools),
            "tools": [t["name"] for t in self.tools],
        }


class PluginManager:
    """Manages plugin loading, unloading, and tool execution."""

    def __init__(self):
        self._plugins: dict[str, BasePlugin] = {}
        self._tool_to_plugin: dict[str, str] = {}  # tool_name -> plugin_name
        self._loaded_config: list[str] = []
        os.makedirs(PLUGINS_DIR, exist_ok=True)

    @property
    def plugin_count(self) -> int:
        return len(self._plugins)

    @property
    def total_plugin_tools(self) -> int:
        return sum(len(p.get_tools()) for p in self._plugins.values())

    def get_all_plugin_tools(self) -> list[dict]:
        """Get all tool definitions from all loaded plugins."""
        tools = []
        for plugin in self._plugins.values():
            tools.extend(plugin.get_tools())
        return tools

    def is_plugin_tool(self, tool_name: str) -> bool:
        """Check if a tool name belongs to a plugin."""
        return tool_name in self._tool_to_plugin

    def get_plugin_for_tool(self, tool_name: str) -> BasePlugin | None:
        """Get the plugin that owns a tool."""
        plugin_name = self._tool_to_plugin.get(tool_name)
        if plugin_name:
            return self._plugins.get(plugin_name)
        return None

    async def execute_plugin_tool(self, tool_name: str, params: dict) -> str:
        """Execute a tool call routed to a plugin.

        Returns:
            String result for the LLM
        """
        plugin = self.get_plugin_for_tool(tool_name)
        if plugin is None:
            return f"Unknown plugin tool: {tool_name}"

        try:
            # Try async execute first, fall back to sync
            import asyncio
            import inspect

            result = plugin.execute(tool_name, params)
            if asyncio.iscoroutine(result):
                result = await result
            return str(result) if result is not None else "Done"
        except Exception as e:
            logger.error("Plugin '%s' tool '%s' failed: %s", plugin.name, tool_name, e)
            return f"Plugin error: {str(e)[:200]}"

    def load_plugin(self, plugin_name: str) -> BasePlugin | None:
        """Load a plugin by name.

        Looks for a module in ~/.may/plugins/{name}/ or in backend/plugins/.
        Registers all tools into the tool registry.

        Returns:
            The loaded plugin, or None on failure
        """
        if plugin_name in self._plugins:
            logger.info("Plugin '%s' already loaded", plugin_name)
            return self._plugins[plugin_name]

        # Try to import the plugin module
        plugin_module = None

        # 1. Try user plugins dir (~/.may/plugins/{name}.py)
        user_plugin_path = os.path.join(PLUGINS_DIR, f"{plugin_name}.py")
        if os.path.exists(user_plugin_path):
            try:
                spec = importlib.util.spec_from_file_location(
                    f"plugins.user.{plugin_name}", user_plugin_path
                )
                plugin_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(plugin_module)
            except Exception as e:
                logger.error("Failed to load user plugin '%s': %s", plugin_name, e)

        # 2. Try built-in plugins (backend/plugins/{name}.py)
        if plugin_module is None:
            builtin_path = os.path.join(os.path.dirname(__file__), f"{plugin_name}.py")
            if os.path.exists(builtin_path):
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"plugins.builtin.{plugin_name}", builtin_path
                    )
                    plugin_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(plugin_module)
                except Exception as e:
                    logger.error("Failed to load built-in plugin '%s': %s", plugin_name, e)

        # 3. Try package import
        if plugin_module is None:
            try:
                plugin_module = importlib.import_module(f"plugins.{plugin_name}")
            except ImportError:
                logger.error("Plugin module 'plugins.%s' not found", plugin_name)

        if plugin_module is None:
            logger.error("Plugin '%s' not found in any location", plugin_name)
            return None

        # Find the BasePlugin subclass in the module
        plugin_instance = None
        for attr_name in dir(plugin_module):
            attr = getattr(plugin_module, attr_name)
            if (isinstance(attr, type)
                and issubclass(attr, BasePlugin)
                and attr is not BasePlugin
                and hasattr(attr, 'name')
                and attr.name):
                plugin_instance = attr()
                break

        if plugin_instance is None:
            logger.error("No BasePlugin subclass found in plugin '%s'", plugin_name)
            return None

        # Register the plugin
        self._plugins[plugin_instance.name] = plugin_instance
        for tool in plugin_instance.get_tools():
            tool_name = tool.get("name", "")
            if tool_name:
                self._tool_to_plugin[tool_name] = plugin_instance.name

        # Call on_load hook
        try:
            plugin_instance.on_load()
        except Exception as e:
            logger.warning("Plugin '%s' on_load() failed: %s", plugin_instance.name, e)

        # Persist to installed list
        self._save_installed()

        logger.info(
            "Loaded plugin '%s' v%s (%d tools: %s)",
            plugin_instance.name,
            plugin_instance.version,
            len(plugin_instance.tools),
            ", ".join(t["name"] for t in plugin_instance.tools),
        )
        return plugin_instance

    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin by name."""
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            return False

        # Call on_unload hook
        try:
            plugin.on_unload()
        except Exception as e:
            logger.warning("Plugin '%s' on_unload() failed: %s", plugin_name, e)

        # Remove tool mappings
        for tool in plugin.get_tools():
            tool_name = tool.get("name", "")
            self._tool_to_plugin.pop(tool_name, None)

        # Remove from loaded dict
        del self._plugins[plugin_name]

        # Update persisted list
        self._save_installed()

        logger.info("Unloaded plugin '%s'", plugin_name)
        return True

    def list_plugins(self) -> list[dict]:
        """List all loaded plugins."""
        return [p.get_info() for p in self._plugins.values()]

    def get_plugin(self, name: str) -> BasePlugin | None:
        return self._plugins.get(name)

    def has_plugin(self, name: str) -> bool:
        return name in self._plugins

    def _save_installed(self):
        """Persist the list of installed plugins."""
        installed = list(self._plugins.keys())
        try:
            os.makedirs(os.path.dirname(PLUGIN_CONFIG), exist_ok=True)
            with open(PLUGIN_CONFIG, "w") as f:
                json.dump({"installed": installed}, f, indent=2)
        except Exception as e:
            logger.error("Failed to save plugin config: %s", e)

    def load_installed(self):
        """Load all previously installed plugins from config."""
        try:
            with open(PLUGIN_CONFIG) as f:
                data = json.load(f)
                installed = data.get("installed", [])
                for name in installed:
                    if name not in self._plugins:
                        self.load_plugin(name)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def get_status(self) -> dict:
        """Get plugin system status."""
        return {
            "plugin_count": self.plugin_count,
            "total_tools": self.total_plugin_tools,
            "plugins": self.list_plugins(),
            "plugins_dir": PLUGINS_DIR,
        }


# ── Lazy singleton ───────────────────────────────────────────────────────
_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get or create the plugin manager singleton."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager
