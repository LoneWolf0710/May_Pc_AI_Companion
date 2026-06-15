"""
LLM-powered PC Controller for May.

When the command parser doesn't match a user message, this module sends the
message to the LLM with a special "PC Controller" system prompt that instructs
it to generate a PowerShell command. The command is then executed and results
are returned to the user.

This gives May INFINITE PC control capability — any natural language request
can be translated into a system command.
"""

import re
import json
import logging

logger = logging.getLogger("may.pc_controller")


PC_CONTROLLER_PROMPT = """You are a Windows PC command translator. Given a user's natural language request, output a JSON object with a PowerShell command to fulfill it.

Rules:
- Output ONLY valid JSON, no markdown, no explanation
- The JSON must have exactly these fields:
  {
    "action": "short description of what this does",
    "command": "the PowerShell command to execute",
    "needs_confirm": true/false (true for destructive actions like delete, shutdown, format, etc.)
  }
- Use PowerShell commands (not cmd)
- Keep commands safe — never format drives, delete System32, etc.
- For app launching, use Start-Process or just the app name
- For file operations, use PowerShell cmdlets
- For system queries, use Get-* cmdlets
- If the request is just casual conversation (hello, how are you, etc.), output:
  {"action": "chat", "command": "", "needs_confirm": false}

Examples:
User: "what's my IP address"
{"action": "Get public IP", "command": "(Invoke-WebRequest -Uri 'https://api.ipify.org' -UseBasicParsing).Content", "needs_confirm": false}

User: "how much RAM do I have"
{"action": "Get RAM info", "command": "Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory | ForEach-Object { [math]::Round($_.TotalPhysicalMemory / 1GB, 2).ToString() + ' GB' }", "needs_confirm": false}

User: "open YouTube in Chrome"
{"action": "Open YouTube in Chrome", "command": "Start-Process 'chrome' -ArgumentList 'https://www.youtube.com'", "needs_confirm": false}

User: "what processes are using the most CPU"
{"action": "List top CPU processes", "command": "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, CPU, @{N='RAM(MB)';E={[math]::Round($_.WorkingSet64/1MB,1)}} | Format-Table -AutoSize", "needs_confirm": false}

User: "delete all temp files"
{"action": "Clean temp files", "command": "Remove-Item -Path $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue", "needs_confirm": true}

User: "set my wallpaper to a blue color"
{"action": "Set wallpaper", "command": "Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public class Wallpaper { [DllImport(\"user32.dll\")] public static extern int SystemParametersInfo(int a, int b, string c, int d); }'; [Wallpaper]::SystemParametersInfo(0x0014, 0, (Get-ItemProperty 'HKCU:\\Control Panel\\Desktop').WallPaper, 0x0003)", "needs_confirm": false}

User: "install notepad++"
{"action": "Install Notepad++", "command": "winget install Notepad++.Notepad++ --accept-package-agreements --accept-source-agreements", "needs_confirm": true}
"""


def parse_llm_response(response: str) -> dict | None:
    """Parse the LLM's JSON response into a command object."""
    try:
        # Try to extract JSON from the response
        # The LLM might wrap it in ```json ... ``` or just return raw JSON
        text = response.strip()

        # Remove markdown code blocks if present
        if text.startswith("```"):
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

        # Find JSON object in the text
        match = re.search(r'\{[^{}]*"command"[^{}]*\}', text, re.DOTALL)
        if match:
            text = match.group(0)

        data = json.loads(text)

        if "command" in data:
            return {
                "action": data.get("action", "Execute command"),
                "command": data.get("command", ""),
                "needs_confirm": data.get("needs_confirm", False),
            }
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to parse LLM PC control response: {e}")

    return None


def is_pc_command(message: str) -> bool:
    """Heuristic check if a message looks like a PC control request
    (as opposed to a conversational message).
    
    IMPORTANT: This is intentionally conservative. We only return True
    for messages that are clearly PC commands. Ambiguous messages should
    fall through to the LLM for normal conversation.
    """
    msg = message.lower().strip()

    # Strong indicators — these are clearly PC commands
    strong_patterns = [
        "open ", "launch ", "start ", "close ", "kill ", "quit ",
        "volume up", "volume down", "set volume", "volume to",
        "brightness", "screenshot", "take screenshot",
        "shut down", "shutdown", "restart", "reboot",
        "lock screen", "lock pc",
        "wifi on", "wifi off", "bluetooth on", "bluetooth off",
        "turn on wifi", "turn off wifi", "enable wifi", "disable wifi",
        "list processes", "list windows", "list services",
        "kill process", "run command", "powershell", "execute ",
        "system info", "computer info", "about this pc",
        "disk info", "disk usage", "disk space",
        "battery info", "battery status", "power plan",
        "search for ", "google ", "open url",
        "remind me in", "set reminder",
        "copy to clipboard", "paste from clipboard",
        "open settings", "open folder",
        "winget install", "winget search", "winget uninstall",
        "install package", "install app",
        "usb devices", "list printers", "list displays",
        "network info", "ip address", "my ip",
        "wifi password",
        "regedit", "registry",
        "startup programs", "scheduled tasks",
        "environment variable", "env var", "get env",
        "file info", "folder size", "search files",
        "large files", "big files",
        "audio devices", "sound devices",
        "service start", "service stop", "service restart",
        "start service", "stop service", "restart service",
        "power plan", "power settings",
        "maximize ", "minimize ", "focus ", "switch to ",
        "window",
        "alt+tab", "alt tab", "ctrl+c", "ctrl+v", "ctrl+z",
        "ctrl+s", "ctrl+a", "show desktop",
        "mouse position", "cursor position",
        "click at", "click ",
        "scroll", "drag",
        "type ", "press ",
        "installed packages", "list installed", "my apps",
        "check disk", "defrag", "clean temp",
    ]

    for pattern in strong_patterns:
        if pattern in msg:
            return True

    return False
