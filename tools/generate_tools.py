"""Auto-generate tools.py from Control Core layer ACTION_MAPs.

Single source of truth: tool definitions are derived from the actual
layer implementations rather than maintained manually. Prevents parameter
mismatches between tools.py and layer handlers.

Usage:
    python tools/generate_tools.py

Reads core/layers/*.py ACTION_MAPs and generates backend/llm/tools.py
with matching JSON schemas.

NOTE: This is a development-time script, not a runtime module.
Run it after modifying any layer's ACTION_MAP to regenerate tools.py.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path

# ── Layer definitions ──────────────────────────────────────────────────────
# Maps layer module name → (layer_id, description)
LAYERS = {
    "L1_filesystem": ("L1", "File and folder operations"),
    "L2_process": ("L2", "Process management"),
    "L3_application": ("L3", "Application discovery and launching"),
    "L4_window": ("L4", "Window management"),
    "L5_input": ("L5", "Keyboard and mouse input"),
    "L6_registry": ("L6", "Windows Registry operations"),
    "L7_services": ("L7", "Windows services and task scheduler"),
    "L8_system": ("L8", "System controls (power, audio, display, network)"),
    "L9_browser": ("L9", "Browser automation via Playwright CDP"),
    "L10_network": ("L10", "Network management (WiFi, firewall, DNS, proxy)"),
    "L11_media": ("L11", "Media and audio control"),
    "L12_developer": ("L12", "Developer tools (Git, npm/pip/cargo, code analysis)"),
    "L13_cloud": ("L13", "HTTP client, webhooks, cloud storage, messaging"),
    "L14_automation": ("L14", "Task scheduling and script execution"),
    "L15_advanced": ("L15", "Power plans, hardware monitoring, optimization"),
}

# ── Known tool schemas ────────────────────────────────────────────────────
# These are hand-maintained parameter definitions for tools that need
# specific schemas. Tools not in this dict get auto-generated schemas
# from their ACTION_MAP entries.

TOOL_SCHEMAS: dict[str, dict] = {
    "open_app": {
        "description": "Open any application on the PC by name. Handles browsers, editors, games, system tools, UWP apps, shell folders.",
        "parameters": {
            "app_name": {"type": "string", "description": "Name of the app to open (e.g. 'chrome', 'discord', 'notepad', 'settings', 'this pc')"}
        }
    },
    "close_app": {
        "description": "Close an application by name. Tries graceful close first, then force kills.",
        "parameters": {
            "app_name": {"type": "string", "description": "App name to close (e.g. 'chrome', 'notepad')"}
        }
    },
    "type_text": {
        "description": "Type text into a specific window. Always provide window_title when typing into an app you just opened.",
        "parameters": {
            "text": {"type": "string", "description": "Text to type"},
            "window_title": {"type": "string", "description": "Partial window title to focus before typing (e.g. 'notepad', 'untitled'). Required when typing into a specific app."}
        }
    },
    "web_search": {
        "description": "Search the web using Google. Opens search results in the default browser.",
        "parameters": {
            "query": {"type": "string", "description": "Search query"}
        }
    },
    "write_file": {
        "description": "Write content to a file (creates parent directories if needed, overwrites if exists).",
        "parameters": {
            "path": {"type": "string", "description": "Full path to the file"},
            "content": {"type": "string", "description": "Content to write"}
        }
    },
    "describe_screen": {
        "description": "Take a screenshot and describe what's on screen using a vision model. Use when the user asks 'what am I looking at', 'describe my screen', 'what's on screen', or wants to understand visible content (PDFs, spreadsheets, code, error messages, etc.).",
        "parameters": {
            "question": {"type": "string", "description": "Optional specific question about what's on screen (e.g. 'what error is showing', 'summarize this document'). Leave empty for a general description."}
        }
    },
    "set_volume": {
        "description": "Set system volume to a specific level (0-100).",
        "parameters": {
            "level": {"type": "integer", "description": "Volume level 0-100"}
        }
    },
    "set_brightness": {
        "description": "Set screen brightness (0-100).",
        "parameters": {
            "level": {"type": "integer", "description": "Brightness level 0-100"}
        }
    },
    "run_powershell": {
        "description": "Execute any PowerShell command. Use as last resort when no specific tool exists.",
        "parameters": {
            "command": {"type": "string", "description": "PowerShell command to execute"}
        }
    },
    "set_reminder": {
        "description": "Set a timed reminder that sends a Windows toast notification.",
        "parameters": {
            "message": {"type": "string", "description": "What to remind about"},
            "minutes": {"type": "integer", "description": "Minutes from now"}
        }
    },
    "send_email": {
        "description": "Send an email.",
        "parameters": {
            "to": {"type": "string", "description": "Recipient email address(es), comma-separated"},
            "subject": {"type": "string", "description": "Email subject"},
            "body": {"type": "string", "description": "Email body text"},
            "cc": {"type": "string", "description": "CC recipients (optional, comma-separated)"}
        }
    },
    "get_weather": {
        "description": "Get current weather information.",
        "parameters": {
            "location": {"type": "string", "description": "City name (optional, auto-detects if empty)"}
        }
    },
    "queue_ghost_task": {
        "description": "Queue a task for autonomous execution when the user is idle. Ghost Mode executes tasks overnight or during breaks.",
        "parameters": {
            "description": {"type": "string", "description": "What the task should accomplish (natural language)"},
            "priority": {"type": "integer", "description": "Priority (higher = execute first, default: 0)"}
        }
    },
    "execute_skill": {
        "description": "Execute a learned skill (multi-step procedure) by ID.",
        "parameters": {
            "skill_id": {"type": "string", "description": "Skill ID (from list_skills)"}
        }
    },
    "search_skills": {
        "description": "Search for skills matching a query.",
        "parameters": {
            "query": {"type": "string", "description": "Search query to match against skill names, triggers, and descriptions"}
        }
    },
    "delete_skill": {
        "description": "Delete a learned skill by ID. DESTRUCTIVE.",
        "parameters": {
            "skill_id": {"type": "string", "description": "Skill ID to delete"}
        }
    },
}


# ── Simple tools (no parameters) ──────────────────────────────────────────
# Tools that take no parameters — generated automatically from ACTION_MAPs
# that have empty param lists.

_NO_PARAM_TOOLS = {
    "get_volume", "get_brightness", "get_time", "get_date",
    "battery_info", "system_info", "screenshot", "test_internet",
    "list_windows", "list_processes", "list_services",
    "get_network_info", "get_public_ip", "get_wifi_password",
    "get_os_info", "list_wifi_networks", "list_installed_apps",
    "list_env_vars", "get_clipboard", "list_virtual_desktops",
    "get_audio_devices", "get_drive_info", "get_window_title",
    "get_mouse_position", "cancel_shutdown", "lock_pc",
    "sleep_pc", "logoff", "get_installed_updates",
    "get_recent_emails", "get_unread_count", "meeting_status",
    "ghost_status", "cancel_all_ghost_tasks", "biometrics_status",
    "biometrics_toggle", "biometrics_delete", "voice_enroll", "voice_verify",
    "list_skills", "get_wellness_status", "get_wellness_suggestions",
    "close_browser", "get_ocr_status",
}


def _action_name_to_tool_name(action_name: str) -> str:
    """Convert an ACTION_MAP action name to a tool name.

    Most action names ARE the tool names. This function handles any
    edge cases or transformations needed.
    """
    # Most actions map directly
    return action_name


def _generate_param_schema(param_names: list[str], tool_name: str) -> dict:
    """Generate a JSON schema for tool parameters from a list of param names.

    Uses the TOOL_SCHEMAS override if available, otherwise generates
    generic string parameters.
    """
    if tool_name in TOOL_SCHEMAS:
        return TOOL_SCHEMAS[tool_name]["parameters"]

    params = {}
    for p in param_names:
        params[p] = {
            "type": "string",
            "description": f"{p.replace('_', ' ').title()} parameter"
        }
    return params


def _get_tool_description(tool_name: str, layer_desc: str) -> str:
    """Generate a tool description from TOOL_SCHEMAS or a generic one."""
    if tool_name in TOOL_SCHEMAS:
        return TOOL_SCHEMAS[tool_name]["description"]
    return f"{tool_name.replace('_', ' ').title()} — {layer_desc}"


def generate_tools_from_layers(layers_dir: Path) -> list[dict]:
    """Parse all layer files and extract ACTION_MAPs to generate tool definitions.

    Returns a list of tool definition dicts compatible with tools.py TOOLS list.
    """
    tools = []
    seen_tools = set()

    for module_name, (layer_id, layer_desc) in LAYERS.items():
        layer_file = layers_dir / f"{module_name}.py"
        if not layer_file.exists():
            print(f"  Warning: {layer_file} not found, skipping {layer_id}")
            continue

        try:
            content = layer_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except SyntaxError as e:
            print(f"  Warning: Syntax error in {layer_file}: {e}")
            continue

        # Find ACTION_MAP dictionaries in the module
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "ACTION_MAP":
                    # Parse the dict literal
                    if isinstance(node.value, ast.Dict):
                        for key, value in zip(node.value.keys, node.value.values):
                            if isinstance(key, ast.Constant):
                                action_name = key.value
                                if action_name in seen_tools:
                                    continue
                                seen_tools.add(action_name)

                                # Extract params from the value
                                param_names = []
                                if isinstance(value, ast.Dict):
                                    for k, v in zip(value.keys, value.values):
                                        if isinstance(k, ast.Constant) and k.value == "params":
                                            if isinstance(v, ast.List):
                                                param_names = [
                                                    elt.value for elt in v.elts
                                                    if isinstance(elt, ast.Constant)
                                                ]

                                tool_name = _action_name_to_tool_name(action_name)
                                tool = {
                                    "name": tool_name,
                                    "description": _get_tool_description(tool_name, layer_desc),
                                    "parameters": _generate_param_schema(param_names, tool_name),
                                }
                                tools.append(tool)

    return tools


def generate_tools_file(tools: list[dict], output_path: Path):
    """Generate the tools.py file content from tool definitions."""
    lines = [
        '"""',
        "Tool definitions for May's Jarvis brain.",
        "",
        "AUTO-GENERATED by tools/generate_tools.py from Control Core layer ACTION_MAPs.",
        "Do NOT edit manually — run `python tools/generate_tools.py` to regenerate.",
        "",
        "Each tool is a JSON schema that the LLM can read and call.",
        '"""',
        "",
        "",
        "TOOLS = [",
    ]

    for tool in sorted(tools, key=lambda t: t["name"]):
        tool_json = json.dumps(tool, indent=8)
        # Indent properly for list continuation
        for line in tool_json.split("\n"):
            lines.append(f"    {line}" if lines[-1].endswith("[") or lines[-1].endswith(",") else f"    {line}")
        # Add comma after each tool dict
        if not lines[-1].rstrip().endswith(","):
            lines[-1] = lines[-1].rstrip() + ","
        lines.append("")

    lines.append("]")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return len(tools)


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    layers_dir = project_root / "core" / "layers"
    output_path = project_root / "backend" / "llm" / "tools.py"

    print(f"Generating tools.py from {layers_dir}...")
    tools = generate_tools_from_layers(layers_dir)

    # Add the hand-maintained tools that aren't in layer ACTION_MAPs
    # (email, wellness, meeting, ghost, biometrics, skill tools)
    extra_tools = [
        tool for name, schema in TOOL_SCHEMAS.items()
        if name not in {t["name"] for t in tools}
        for tool in [{"name": name, "description": schema["description"], "parameters": schema["parameters"]}]
    ]
    tools.extend(extra_tools)

    count = generate_tools_file(tools, output_path)
    print(f"Generated {count} tools → {output_path}")
