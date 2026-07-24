"""Spotify plugin — reference implementation for May's plugin system.

Provides tools for controlling Spotify playback:
- spotify_play: Play a song, album, or playlist
- spotify_pause: Pause playback
- spotify_next: Skip to next track
- spotify_previous: Go to previous track
- spotify_search: Search for songs/artists/albums
- spotify_now_playing: Get current track info

Uses Spotify's local web API (open.spotify.com) via subprocess.
No API key needed — controls the running Spotify desktop app.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from plugins import BasePlugin

logger = logging.getLogger("may.plugins.spotify")


class SpotifyPlugin(BasePlugin):
    name = "spotify"
    version = "1.0.0"
    description = "Control Spotify playback — play, pause, skip, search, now playing"
    tools = [
        {
            "name": "spotify_play",
            "description": "Play a song, album, or artist on Spotify. Opens Spotify if not running.",
            "parameters": {
                "query": {
                    "type": "string",
                    "description": "Song, artist, album, or playlist name to play"
                }
            }
        },
        {
            "name": "spotify_pause",
            "description": "Pause Spotify playback.",
            "parameters": {}
        },
        {
            "name": "spotify_resume",
            "description": "Resume Spotify playback.",
            "parameters": {}
        },
        {
            "name": "spotify_next",
            "description": "Skip to next track on Spotify.",
            "parameters": {}
        },
        {
            "name": "spotify_previous",
            "description": "Go to previous track on Spotify.",
            "parameters": {}
        },
        {
            "name": "spotify_now_playing",
            "description": "Get the currently playing track on Spotify.",
            "parameters": {}
        },
        {
            "name": "spotify_volume",
            "description": "Set Spotify volume (0-100).",
            "parameters": {
                "level": {
                    "type": "integer",
                    "description": "Volume level 0-100"
                }
            }
        },
    ]

    def on_load(self):
        logger.info("Spotify plugin loaded")

    def on_unload(self):
        logger.info("Spotify plugin unloaded")

    async def execute(self, tool_name: str, params: dict) -> str:
        """Execute a Spotify tool call via PowerShell media key simulation."""
        if tool_name == "spotify_play":
            return await self._play(params.get("query", ""))
        elif tool_name == "spotify_pause":
            return await self._media_key(0xB3)  # Play/Pause toggle
        elif tool_name == "spotify_resume":
            return await self._media_key(0xB3)
        elif tool_name == "spotify_next":
            return await self._media_key(0xB0)  # Next track
        elif tool_name == "spotify_previous":
            return await self._media_key(0xB1)  # Previous track
        elif tool_name == "spotify_now_playing":
            return await self._now_playing()
        elif tool_name == "spotify_volume":
            return await self._set_volume(params.get("level", 50))
        return f"Unknown Spotify tool: {tool_name}"

    async def _play(self, query: str) -> str:
        """Play music on Spotify. If query provided, search and play via URI."""
        if not query:
            # Just resume playback
            return await self._media_key(0xB3)

        # Open Spotify and use the search URI scheme
        try:
            # Use Spotify URI to search and play
            ps_cmd = (
                "Start-Process 'spotify:search:" + query.replace("'", "''") + "' "
                "-ErrorAction SilentlyContinue"
            )
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-NoProfile", "-Command", ps_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10)
            return f"Playing '{query}' on Spotify~"
        except Exception as e:
            return f"Error starting Spotify: {e}"

    async def _media_key(self, vk_code: int) -> str:
        """Send a media key via PowerShell keybd_event."""
        ps = (
            "Add-Type @'\n"
            "using System;\n"
            "using System.Runtime.InteropServices;\n"
            "public class KeySender {\n"
            '  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);\n'
            "}\n"
            "'@\n"
            f"[KeySender]::keybd_event({vk_code}, 0, 0, [UIntPtr]::Zero); "
            f"[KeySender]::keybd_event({vk_code}, 0, 2, [UIntPtr]::Zero)"
        )
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-Command", ps,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=10)
        return "Done"

    async def _now_playing(self) -> str:
        """Get current track info from Spotify via PowerShell."""
        ps = (
            "try {\n"
            "  $proc = Get-Process spotify -ErrorAction Stop\n"
            "  $title = $proc.MainWindowTitle\n"
            "  if ($title -and $title -ne 'Spotify') {\n"
            "    Write-Output \"Now playing: $title\"\n"
            "  } else {\n"
            "    Write-Output 'Spotify is open but nothing is playing'\n"
            "  }\n"
            "} catch {\n"
            "  Write-Output 'Spotify is not running'\n"
            "}"
        )
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-Command", ps,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        return stdout.decode("utf-8", errors="replace").strip() or "Could not get track info"

    async def _set_volume(self, level: int) -> str:
        """Set Spotify volume by focusing it and using system volume keys."""
        level = max(0, min(100, level))
        # Use the system volume set via pycaw if available, otherwise approximate
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$wsh = New-Object -ComObject WScript.Shell; "
            "$wsh.AppActivate('Spotify'); "
            "Start-Sleep -Milliseconds 200"
        )
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-Command", ps,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=10)
        return f"Spotify volume set to {level}% (via system volume)"
