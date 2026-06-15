"""
Full PC control module for Windows.
Handles EVERYTHING: volume, brightness, apps, files, windows, processes,
media, keyboard, mouse, network, system ops, settings, search, services,
registry, startup programs, disk, environment variables, power management,
devices, package management, and PowerShell command execution.
"""

import subprocess
import os
import shutil
import json
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger("may.system")


class SystemControl:
    """Full PC control on Windows — May controls everything."""

    # ── Volume Control ──────────────────────────────────────
    @staticmethod
    def set_volume(level: int) -> str:
        """Set system volume (0-100)."""
        level = max(0, min(100, level))
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            return f"Volume set to {level}%"
        except (ImportError, AttributeError, Exception):
            # Fallback: use PowerShell to set volume via nircmd or SendKeys
            try:
                subprocess.run(
                    ["powershell", "-Command",
                     f"$wsh = New-Object -ComObject WScript.Shell; "
                     f"for ($i=0; $i -lt {level // 2}; $i++) {{ $wsh.SendKeys([char]175) }}"],
                    capture_output=True, timeout=5,
                )
                return f"Volume set to ~{level}% (approximate, via SendKeys)"
            except Exception:
                return f"Volume control unavailable. Try installing pycaw: pip install pycaw comtypes"

    @staticmethod
    def get_volume() -> int:
        """Get current system volume (0-100)."""
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            return int(volume.GetMasterVolumeLevelScalar() * 100)
        except (ImportError, AttributeError, Exception):
            return -1

    @staticmethod
    def mute() -> str:
        """Mute system audio."""
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMute(1, None)
            return "Audio muted"
        except (ImportError, AttributeError, Exception):
            return "Mute requires pycaw"

    @staticmethod
    def unmute() -> str:
        """Unmute system audio."""
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMute(0, None)
            return "Audio unmuted"
        except (ImportError, AttributeError, Exception):
            return "Unmute requires pycaw"

    # ── Brightness Control ──────────────────────────────────
    @staticmethod
    def set_brightness(level: int) -> str:
        """Set screen brightness (0-100)."""
        level = max(0, min(100, level))
        try:
            import screen_brightness_control as sbc
            sbc.set_brightness(level)
            return f"Brightness set to {level}%"
        except ImportError:
            return "Brightness control requires screen_brightness_control"

    @staticmethod
    def get_brightness() -> int:
        """Get current screen brightness."""
        try:
            import screen_brightness_control as sbc
            return sbc.get_brightness()[0]
        except ImportError:
            return -1

    # ── App Launching ───────────────────────────────────────
    @staticmethod
    def open_app(app_name: str) -> str:
        """Open an application by name. Tries multiple strategies for unknown apps."""
        common_apps = {
            "chrome": "chrome", "firefox": "firefox", "edge": "msedge",
            "vs code": "code", "code": "code", "notepad": "notepad",
            "explorer": "explorer", "file explorer": "explorer",
            "calculator": "calc", "spotify": "spotify", "discord": "discord",
            "terminal": "wt", "powershell": "powershell", "cmd": "cmd",
            "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
            "paint": "mspaint", "snipping tool": "SnippingTool",
            "task manager": "taskmgr", "settings": "ms-settings",
            "photos": "ms-photos", "mail": "outlookmail",
            "calendar": "outlookcal",
            "camera": "microsoft.windows.camera:",
            "maps": "bingmaps", "store": "ms-windows-store:",
            "xbox": "xbox:", "one note": "onenote:", "onenote": "onenote:",
            "teams": "ms-teams:", "zoom": "zoom", "obs": "obs64",
            "steam": "steam", "epic": "com.epicgames.launcher",
            "blender": "blender", "photoshop": "photoshop",
            "premiere": "premiere", "after effects": "afterfx",
            "audacity": "audacity", "gimp": "gimp",
            "vlc": "vlc", "media player": "wmplayer",
            "wordpad": "write", "snip": "SnippingTool",
            "vpn": "ms-settings:network-vpn",
            "recycle bin": "shell:RecycleBinFolder",
            "downloads": "shell:Downloads",
            "documents": "shell:Personal",
            "pictures": "shell:My Pictures",
            "music": "shell:My Music",
            "videos": "shell:My Videos",
            "desktop": "shell:Desktop",
            "control panel": "control",
            "device manager": "devmgmt.msc",
            "disk management": "diskmgmt.msc",
            "event viewer": "eventvwr.msc",
            "services": "services.msc",
            "registry": "regedit",
            "resource monitor": "resmon",
            "performance monitor": "perfmon",
            "command prompt": "cmd", "powershell 7": "pwsh",
            "windows terminal": "wt",
            "notepad++": "notepad++", "sublime": "subl",
            "atom": "atom", "vim": "vim", "nano": "nano",
            "git bash": "git-bash",
            # Lenovo / OEM apps
            "lenovo vantage": "LenovoVantage",
            "lenovo legion": "LegionZone",
            "lenovo hotkeys": "LenovoHotkeys",
            # Common Windows Store / UWP apps
            "snip & sketch": "ms-screenclip:",
            "snip and sketch": "ms-screenclip:",
            "your phone": "ms-yourphone:",
            "alarm": "ms-clock:",
            "alarms": "ms-clock:",
            "clock": "ms-clock:",
            "weather": "msnweather:",
            "news": "ms-news:",
            "notepad (new)": "Microsoft.WindowsNotepad:",
            "terminal new": "WindowsTerminal:",
        }

        key = app_name.lower().strip()
        exe = common_apps.get(key)

        # Strategy 1: Known app from dictionary (no shell=True so we can detect missing exe)
        if exe:
            try:
                subprocess.Popen(
                    [exe],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return f"Opening {app_name}"
            except FileNotFoundError:
                pass

        # Strategy 2: PowerShell Start-Process (handles exe names, Store apps, UWP apps)
        try:
            ps_cmd = f"Start-Process -FilePath '{app_name}' -ErrorAction Stop"
            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return f"Opening {app_name}"
        except Exception:
            pass

        # Strategy 3: Try Get-Command to find the exe, then launch it
        try:
            ps_cmd = (
                f"$cmd = Get-Command '{app_name}' -ErrorAction SilentlyContinue; "
                f"if ($cmd) {{ Start-Process -FilePath $cmd.Source -ErrorAction Stop; 'found' }}"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=10,
            )
            if "found" in result.stdout:
                return f"Opening {app_name}"
        except Exception:
            pass

        # Strategy 4: Direct subprocess as last resort
        try:
            subprocess.Popen(
                [app_name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return f"Opening {app_name}"
        except FileNotFoundError:
            return f"Could not find {app_name}. Try searching with winget or checking the exact app name."

    # ── File Operations ─────────────────────────────────────
    @staticmethod
    def read_file(file_path: str) -> str:
        """Read contents of a file."""
        path = Path(file_path)
        if not path.exists():
            return f"File not found: {file_path}"
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Cannot read binary file: {file_path}"

    @staticmethod
    def write_file(file_path: str, content: str) -> str:
        """Write content to a file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Written to {file_path}"

    @staticmethod
    def list_directory(dir_path: str = ".") -> str:
        """List contents of a directory."""
        path = Path(dir_path)
        if not path.exists():
            return f"Directory not found: {dir_path}"
        items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        lines = []
        for item in items[:50]:
            prefix = "[DIR] " if item.is_dir() else ""
            size = ""
            if item.is_file():
                size_bytes = item.stat().st_size
                if size_bytes > 1024 * 1024:
                    size = f" ({size_bytes // (1024*1024)} MB)"
                elif size_bytes > 1024:
                    size = f" ({size_bytes // 1024} KB)"
            lines.append(f"{prefix}{item.name}{size}")
        return "\n".join(lines) if lines else "Empty directory"

    @staticmethod
    def move_file(source: str, destination: str) -> str:
        """Move or rename a file."""
        src = Path(source)
        dst = Path(destination)
        if not src.exists():
            return f"File not found: {source}"
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            return f"Moved {src.name} to {dst}"
        except Exception as e:
            return f"Move failed: {e}"

    @staticmethod
    def copy_file(source: str, destination: str) -> str:
        """Copy a file."""
        src = Path(source)
        dst = Path(destination)
        if not src.exists():
            return f"File not found: {source}"
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            return f"Copied {src.name} to {dst}"
        except Exception as e:
            return f"Copy failed: {e}"

    @staticmethod
    def delete_file(file_path: str) -> str:
        """Delete a file (moves to recycle bin if possible)."""
        path = Path(file_path)
        if not path.exists():
            return f"File not found: {file_path}"
        try:
            from send2trash import send2trash
            send2trash(str(path))
            return f"Deleted {path.name} (moved to recycle bin)"
        except ImportError:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(str(path))
            return f"Deleted {path.name}"

    @staticmethod
    def open_folder(folder_path: str) -> str:
        """Open a folder in File Explorer."""
        path = Path(folder_path).resolve()
        if not path.exists():
            return f"Folder not found: {folder_path}"
        subprocess.Popen(["explorer", str(path)])
        return f"Opened {path.name}"

    @staticmethod
    def search_files(directory: str, pattern: str) -> str:
        """Search for files matching a pattern."""
        path = Path(directory)
        if not path.exists():
            return f"Directory not found: {directory}"
        matches = list(path.rglob(pattern))
        if not matches:
            return f"No files matching '{pattern}' in {directory}"
        lines = []
        for m in matches[:30]:
            lines.append(str(m))
        return f"Found {len(matches)} files:\n" + "\n".join(lines)

    @staticmethod
    def get_file_info(file_path: str) -> str:
        """Get detailed info about a file."""
        path = Path(file_path)
        if not path.exists():
            return f"File not found: {file_path}"
        stat = path.stat()
        info = [
            f"Path: {path.resolve()}",
            f"Type: {'Directory' if path.is_dir() else 'File'}",
            f"Size: {stat.st_size:,} bytes ({stat.st_size / 1024:.1f} KB)",
            f"Created: {datetime.fromtimestamp(stat.st_ctime)}",
            f"Modified: {datetime.fromtimestamp(stat.st_mtime)}",
            f"Accessed: {datetime.fromtimestamp(stat.st_atime)}",
        ]
        if path.is_file():
            info.append(f"Extension: {path.suffix}")
        return "\n".join(info)

    # ── Clipboard ───────────────────────────────────────────
    @staticmethod
    def copy_to_clipboard(text: str) -> str:
        """Copy text to Windows clipboard."""
        try:
            # Use base64 to safely pass text through PowerShell
            import base64
            encoded = base64.b64encode(text.encode('utf-8')).decode('ascii')
            ps_script = (
                f"[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{encoded}')) | "
                f"Set-Clipboard"
            )
            process = subprocess.Popen(
                ["powershell", "-Command", ps_script],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            process.communicate()
            return f"Copied to clipboard: {text[:50]}{'...' if len(text) > 50 else ''}"
        except Exception:
            return "Clipboard copy failed"

    @staticmethod
    def get_clipboard() -> str:
        """Get text from Windows clipboard."""
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5,
            )
            text = result.stdout.strip()
            return f"Clipboard: {text[:500]}" if text else "Clipboard is empty"
        except Exception:
            return "Could not read clipboard"

    # ── Window Management ───────────────────────────────────
    @staticmethod
    def list_windows() -> str:
        """List all open windows with titles."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
                 "Select-Object ProcessName, MainWindowTitle | "
                 "Format-Table -AutoSize -Wrap"],
                capture_output=True, text=True, timeout=10,
            )
            output = result.stdout.strip()
            if output:
                return f"Open windows:\n{output}"
            return "No visible windows found"
        except Exception as e:
            return f"Could not list windows: {e}"

    @staticmethod
    def focus_window(title: str) -> str:
        """Focus/bring a window to front by partial title match."""
        try:
            ps_script = (
                f"$wshell = New-Object -ComObject WScript.Shell; "
                f"$proc = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{title}*'}} | Select-Object -First 1; "
                f"if ($proc) {{ $wshell.AppActivate($proc.Id); 'Focused: ' + $proc.MainWindowTitle }} "
                f"else {{ 'Window not found: {title}' }}"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() or f"Could not find window: {title}"
        except Exception as e:
            return f"Focus failed: {e}"

    @staticmethod
    def minimize_window(title: str) -> str:
        """Minimize a window by partial title match."""
        try:
            ps_script = (
                f"$proc = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{title}*'}} | Select-Object -First 1; "
                f"if ($proc) {{ "
                f"  Add-Type @' using System; using System.Runtime.InteropServices; "
                f"  public class Win {{ "
                f"    [DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr h, int c); "
                f"  }} '@; "
                f"  [Win]::ShowWindow($proc.MainWindowHandle, 6); 'Minimized: ' + $proc.MainWindowTitle "
                f"}} else {{ 'Window not found: {title}' }}"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() or f"Could not find window: {title}"
        except Exception as e:
            return f"Minimize failed: {e}"

    @staticmethod
    def maximize_window(title: str) -> str:
        """Maximize a window by partial title match."""
        try:
            ps_script = (
                f"$proc = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{title}*'}} | Select-Object -First 1; "
                f"if ($proc) {{ "
                f"  Add-Type -AssemblyName Microsoft.VisualBasic; "
                f"  [Microsoft.VisualBasic.Interaction]::AppActivate($proc.Id); "
                f"  'Maximized: ' + $proc.MainWindowTitle "
                f"}} else {{ 'Window not found: {title}' }}"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() or f"Could not find window: {title}"
        except Exception as e:
            return f"Maximize failed: {e}"

    @staticmethod
    def close_window(title: str) -> str:
        """Close a window by partial title match. Tries graceful close first."""
        try:
            ps_script = (
                f"$proc = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{title}*'}} | Select-Object -First 1; "
                f"if ($proc) {{ $proc.CloseMainWindow(); Start-Sleep -Milliseconds 500; "
                f"  if (!$proc.HasExited) {{ Stop-Process -Id $proc.Id -Force }}; 'Closed: ' + $proc.MainWindowTitle }} "
                f"else {{ 'Window not found: {title}' }}"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() or f"Could not find window: {title}"
        except Exception as e:
            return f"Close failed: {e}"

    # ── Process Management ──────────────────────────────────
    @staticmethod
    def list_processes(sort_by: str = "cpu") -> str:
        """List top processes by CPU or memory usage."""
        try:
            import psutil
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                procs.append(p.info)
            if sort_by == "memory":
                procs.sort(key=lambda x: x.get("memory_percent", 0), reverse=True)
            else:
                procs.sort(key=lambda x: x.get("cpu_percent", 0), reverse=True)

            lines = ["PID    Name                          CPU%    RAM%"]
            for p in procs[:20]:
                pid = str(p.get("pid", "?")).ljust(7)
                name = str(p.get("name", "?"))[:30].ljust(30)
                cpu = f"{p.get('cpu_percent', 0):5.1f}"
                mem = f"{p.get('memory_percent', 0):5.1f}"
                lines.append(f"{pid}{name}{cpu}  {mem}")
            return "\n".join(lines)
        except ImportError:
            return "Process listing requires psutil"
        except Exception:
            return "Could not access some processes"

    @staticmethod
    def get_process_info(name: str) -> str:
        """Get detailed info about a process."""
        try:
            import psutil
            found = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent",
                                           "memory_info", "status", "create_time", "exe"]):
                info = p.info
                if name.lower() in info.get("name", "").lower():
                    mem_mb = info.get("memory_info", None)
                    mem_str = f"{mem_mb.rss / 1024 / 1024:.1f} MB" if mem_mb else "N/A"
                    created = datetime.fromtimestamp(info.get("create_time", 0)).strftime("%Y-%m-%d %H:%M")
                    found.append(
                        f"PID: {info['pid']}\n"
                        f"Name: {info['name']}\n"
                        f"Status: {info.get('status', 'N/A')}\n"
                        f"CPU: {info.get('cpu_percent', 0):.1f}%\n"
                        f"Memory: {mem_str}\n"
                        f"Path: {info.get('exe', 'N/A')}\n"
                        f"Started: {created}"
                    )
            if found:
                return "\n---\n".join(found[:3])
            return f"No process found matching '{name}'"
        except ImportError:
            return "Process info requires psutil"

    @staticmethod
    def kill_process(name: str) -> str:
        """Kill a process by name."""
        try:
            import psutil
            killed = []
            for p in psutil.process_iter(["name"]):
                if name.lower() in p.info["name"].lower():
                    p.kill()
                    killed.append(p.info["name"])
            if killed:
                return f"Killed {len(killed)} process(es): {', '.join(set(killed))}"
            return f"No process found matching '{name}'"
        except ImportError:
            return "Process killing requires psutil"

    # ── Media Control ───────────────────────────────────────
    @staticmethod
    def media_play_pause() -> str:
        """Toggle media play/pause."""
        subprocess.run(
            ["powershell", "-Command",
             "$wshell = New-Object -ComObject WScript.Shell; $wshell.SendKeys([char]0xB3)"],
            capture_output=True,
        )
        return "Play/Pause toggled"

    @staticmethod
    def media_next() -> str:
        """Skip to next track."""
        subprocess.run(
            ["powershell", "-Command",
             "$wshell = New-Object -ComObject WScript.Shell; $wshell.SendKeys([char]0xB0)"],
            capture_output=True,
        )
        return "Next track"

    @staticmethod
    def media_previous() -> str:
        """Go to previous track."""
        subprocess.run(
            ["powershell", "-Command",
             "$wshell = New-Object -ComObject WScript.Shell; $wshell.SendKeys([char]0xB1)"],
            capture_output=True,
        )
        return "Previous track"

    @staticmethod
    def media_stop() -> str:
        """Stop media playback."""
        subprocess.run(
            ["powershell", "-Command",
             "$wshell = New-Object -ComObject WScript.Shell; $wshell.SendKeys([char]0xB2)"],
            capture_output=True,
        )
        return "Media stopped"

    # ── Mouse Control ───────────────────────────────────────
    @staticmethod
    def mouse_click(x: int, y: int, button: str = "left") -> str:
        """Click at screen coordinates."""
        btn = "left" if button == "left" else "right" if button == "right" else "middle"
        ps_script = (
            f"Add-Type -AssemblyName System.Windows.Forms; "
            f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({x}, {y}); "
            f"$signature = '[DllImport(\"user32.dll\")] public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, int dwExtraInfo)'; "
            f"$type = Add-Type -MemberDefinition $signature -Name Mouse -Namespace Win32Functions -PassThru; "
            f"if ('{btn}' -eq 'left') {{ "
            f"  $type::mouse_event(0x02, 0, 0, 0, 0); $type::mouse_event(0x04, 0, 0, 0, 0) "
            f"}} elseif ('{btn}' -eq 'right') {{ "
            f"  $type::mouse_event(0x08, 0, 0, 0, 0); $type::mouse_event(0x10, 0, 0, 0, 0) "
            f"}} else {{ "
            f"  $type::mouse_event(0x20, 0, 0, 0, 0); $type::mouse_event(0x40, 0, 0, 0, 0) "
            f"}}"
        )
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True, timeout=10)
        return f"Clicked {btn} at ({x}, {y})"

    @staticmethod
    def mouse_move(x: int, y: int) -> str:
        """Move mouse to screen coordinates."""
        ps_script = (
            f"Add-Type -AssemblyName System.Windows.Forms; "
            f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({x}, {y})"
        )
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True, timeout=10)
        return f"Mouse moved to ({x}, {y})"

    @staticmethod
    def mouse_scroll(clicks: int) -> str:
        """Scroll the mouse wheel. Positive = up, negative = down."""
        delta = clicks * 120
        ps_script = (
            f"Add-Type -AssemblyName System.Windows.Forms; "
            f"$signature = '[DllImport(\"user32.dll\")] public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, int dwExtraInfo)'; "
            f"$type = Add-Type -MemberDefinition $signature -Name Mouse -Namespace Win32Functions -PassThru; "
            f"$type::mouse_event(0x0800, 0, 0, {delta}, 0)"
        )
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True, timeout=10)
        direction = "up" if clicks > 0 else "down"
        return f"Scrolled {direction} {abs(clicks)} notches"

    @staticmethod
    def mouse_drag(x1: int, y1: int, x2: int, y2: int) -> str:
        """Drag from (x1,y1) to (x2,y2)."""
        ps_script = (
            f"Add-Type -AssemblyName System.Windows.Forms; "
            f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({x1}, {y1}); "
            f"$signature = '[DllImport(\"user32.dll\")] public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, int dwExtraInfo)'; "
            f"$type = Add-Type -MemberDefinition $signature -Name Mouse -Namespace Win32Functions -PassThru; "
            f"$type::mouse_event(0x02, 0, 0, 0, 0); "
            f"Start-Sleep -Milliseconds 100; "
            f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({x2}, {y2}); "
            f"Start-Sleep -Milliseconds 100; "
            f"$type::mouse_event(0x04, 0, 0, 0, 0)"
        )
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True, timeout=10)
        return f"Dragged from ({x1},{y1}) to ({x2},{y2})"

    @staticmethod
    def get_mouse_position() -> str:
        """Get current mouse position."""
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$pos = [System.Windows.Forms.Cursor]::Position; "
            "'Mouse position: (' + $pos.X + ', ' + $pos.Y + ')'"
        )
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() or "Could not get mouse position"

    # ── Keyboard Shortcuts ──────────────────────────────────
    @staticmethod
    def send_keys(keys: str) -> str:
        """Send keyboard shortcut (e.g. 'ctrl+c', 'alt+tab', 'win+d')."""
        try:
            key_map = {
                "ctrl": "^", "alt": "%", "shift": "+",
                "enter": "{ENTER}", "tab": "{TAB}", "esc": "{ESC}",
                "delete": "{DELETE}", "backspace": "{BACKSPACE}",
                "space": " ", "up": "{UP}", "down": "{DOWN}",
                "left": "{LEFT}", "right": "{RIGHT}",
                "home": "{HOME}", "end": "{END}",
                "pageup": "{PGUP}", "pagedown": "{PGDN}",
                "f1": "{F1}", "f2": "{F2}", "f3": "{F3}", "f4": "{F4}",
                "f5": "{F5}", "f6": "{F6}", "f7": "{F7}", "f8": "{F8}",
                "f9": "{F9}", "f10": "{F10}", "f11": "{F11}", "f12": "{F12}",
                "win": "^({ESC})", "printscreen": "{PRTSC}",
                "insert": "{INSERT}", "capslock": "{CAPSLOCK}",
                "numlock": "{NUMLOCK}", "scrolllock": "{SCROLLLOCK}",
            }

            parts = keys.lower().split("+")
            sendkeys_str = ""
            for part in parts:
                part = part.strip()
                if part in key_map:
                    sendkeys_str += key_map[part]
                else:
                    sendkeys_str += part

            ps_script = (
                f"$wshell = New-Object -ComObject WScript.Shell; "
                f"$wshell.SendKeys('{sendkeys_str}')"
            )
            subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
            return f"Sent keys: {keys}"
        except Exception as e:
            return f"Key send failed: {e}"

    @staticmethod
    def type_text(text: str) -> str:
        """Type text into the active window."""
        # Escape special characters for SendKeys
        escaped = (
            text.replace("{", "{{").replace("}", "}}")
            .replace("+", "{+}").replace("^", "{^}").replace("%", "{%}")
            .replace("~", "{~}").replace("(", "{(}").replace(")", "{)}")
            .replace("[", "{[}").replace("]", "{]}")
        )
        ps_script = (
            f"$wshell = New-Object -ComObject WScript.Shell; "
            f"$wshell.SendKeys('{escaped}')"
        )
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
        return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"

    # ── Network Control ─────────────────────────────────────
    @staticmethod
    def toggle_wifi(enable: bool) -> str:
        """Enable or disable WiFi (requires Admin)."""
        action = "Enable" if enable else "Disable"
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 f"{action}-NetAdapter -Name 'Wi-Fi' -Confirm:$false"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return f"WiFi {'enabled' if enable else 'disabled'}"
            result = subprocess.run(
                ["powershell", "-Command",
                 f"{action}-NetAdapter -Name 'WLAN' -Confirm:$false"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return f"WiFi {'enabled' if enable else 'disabled'}"
            return f"WiFi toggle failed (try running as Admin). Error: {result.stderr[:100]}"
        except Exception as e:
            return f"WiFi toggle failed: {e}"

    @staticmethod
    def toggle_bluetooth(enable: bool) -> str:
        """Enable or disable Bluetooth."""
        action = "Enable" if enable else "Disable"
        try:
            subprocess.Popen(["powershell", "-Command",
                             "Start-Process 'ms-settings:bluetooth'"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Opened Bluetooth settings to {'enable' if enable else 'disable'} Bluetooth"
        except Exception as e:
            return f"Bluetooth toggle failed: {e}"

    @staticmethod
    def get_network_info() -> str:
        """Get network information (IP, WiFi, adapters)."""
        try:
            ps_script = (
                "$adapters = Get-NetAdapter | Where-Object {$_.Status -eq 'Up'}; "
                "$ip = Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -like '*Wi-Fi*' -or $_.InterfaceAlias -like '*Ethernet*'}; "
                "$wifi = netsh wlan show interfaces 2>&1; "
                "$output = 'Active Adapters:\\n'; "
                "foreach ($a in $adapters) { $output += $a.Name + ' - ' + $a.LinkSpeed + '\\n' }; "
                "$output += '\\nIP Addresses:\\n'; "
                "foreach ($i in $ip) { $output += $i.InterfaceAlias + ': ' + $i.IPAddress + '\\n' }; "
                "$output += '\\nWiFi:\\n' + ($wifi | Select-String 'SSID|Signal|Speed' | ForEach-Object { $_.ToString().Trim() } | Out-String); "
                "$output"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=15,
            )
            return result.stdout.strip() or "Could not get network info"
        except Exception as e:
            return f"Network info failed: {e}"

    @staticmethod
    def get_wifi_password(ssid: str = "") -> str:
        """Get WiFi password for a saved network."""
        try:
            ps_script = (
                f"$profiles = netsh wlan show profiles | Select-String 'All User Profile\\s+:\\s+(.+$)' | "
                f"ForEach-Object {{ $_.Matches.Groups[1].Value.Trim() }}; "
                f"$output = ''; "
                f"foreach ($p in $profiles) {{ "
                f"  $detail = netsh wlan show profile name=\"$p\" key=clear 2>&1; "
                f"  $key = ($detail | Select-String 'Key Content\\s+:\\s+(.+$)').Matches.Groups[1].Value.Trim(); "
                f"  $output += \"$p : $key\\n\" "
                f"}}; "
                f"$output"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=15,
            )
            return result.stdout.strip() or "Could not retrieve WiFi passwords"
        except Exception as e:
            return f"WiFi password retrieval failed: {e}"

    @staticmethod
    def get_public_ip() -> str:
        """Get public IP address."""
        try:
            import httpx
            resp = httpx.get("https://api.ipify.org?format=json", timeout=10)
            return f"Public IP: {resp.json()['ip']}"
        except Exception:
            return "Could not get public IP"

    # ── Service Management ──────────────────────────────────
    @staticmethod
    def list_services(filter_str: str = "") -> str:
        """List Windows services, optionally filtered."""
        try:
            ps_script = (
                f"Get-Service | Where-Object {{ $_.Status -eq 'Running' }} | "
                f"Select-Object Name, DisplayName, Status | "
                f"Format-Table -AutoSize -Wrap"
            )
            if filter_str:
                ps_script = (
                    f"Get-Service | Where-Object {{ $_.Name -like '*{filter_str}*' -or $_.DisplayName -like '*{filter_str}*' }} | "
                    f"Select-Object Name, DisplayName, Status | "
                    f"Format-Table -AutoSize -Wrap"
                )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=15,
            )
            output = result.stdout.strip()
            return output[:2000] if output else "No services found"
        except Exception as e:
            return f"Service listing failed: {e}"

    @staticmethod
    def start_service(name: str) -> str:
        """Start a Windows service."""
        try:
            result = subprocess.run(
                ["powershell", "-Command", f"Start-Service -Name '{name}' -PassThru | Select-Object Name, Status"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return f"Started service: {name}"
            return f"Failed to start {name}: {result.stderr[:200]}"
        except Exception as e:
            return f"Start service failed: {e}"

    @staticmethod
    def stop_service(name: str) -> str:
        """Stop a Windows service."""
        try:
            result = subprocess.run(
                ["powershell", "-Command", f"Stop-Service -Name '{name}' -Force -PassThru | Select-Object Name, Status"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return f"Stopped service: {name}"
            return f"Failed to stop {name}: {result.stderr[:200]}"
        except Exception as e:
            return f"Stop service failed: {e}"

    @staticmethod
    def restart_service(name: str) -> str:
        """Restart a Windows service."""
        try:
            result = subprocess.run(
                ["powershell", "-Command", f"Restart-Service -Name '{name}' -Force -PassThru | Select-Object Name, Status"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return f"Restarted service: {name}"
            return f"Failed to restart {name}: {result.stderr[:200]}"
        except Exception as e:
            return f"Restart service failed: {e}"

    # ── Registry ────────────────────────────────────────────
    @staticmethod
    def read_registry(path: str, name: str = "") -> str:
        """Read a registry value."""
        try:
            ps_script = f"Get-ItemProperty -Path '{path}'"
            if name:
                ps_script += f" -Name '{name}'"
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()[:2000]
            return f"Registry read failed: {result.stderr[:200]}"
        except Exception as e:
            return f"Registry read failed: {e}"

    @staticmethod
    def write_registry(path: str, name: str, value: str, type_name: str = "String") -> str:
        """Write a registry value."""
        try:
            ps_script = (
                f"New-ItemProperty -Path '{path}' -Name '{name}' -Value '{value}' "
                f"-PropertyType '{type_name}' -Force | Out-Null; 'Registry updated'"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return f"Set {name} = {value} in {path}"
            return f"Registry write failed: {result.stderr[:200]}"
        except Exception as e:
            return f"Registry write failed: {e}"

    # ── Startup Programs ────────────────────────────────────
    @staticmethod
    def list_startup_programs() -> str:
        """List programs that run at startup."""
        try:
            ps_script = (
                "Get-CimInstance Win32_StartupCommand | "
                "Select-Object Name, Command, Location | "
                "Format-Table -AutoSize -Wrap"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=15,
            )
            output = result.stdout.strip()
            return f"Startup programs:\n{output}" if output else "No startup programs found"
        except Exception as e:
            return f"Startup listing failed: {e}"

    @staticmethod
    def add_startup_program(name: str, command: str) -> str:
        """Add a program to startup."""
        try:
            startup_folder = os.path.join(
                os.environ["APPDATA"],
                r"Microsoft\Windows\Start Menu\Programs\Startup"
            )
            bat_path = os.path.join(startup_folder, f"{name}.bat")
            with open(bat_path, "w") as f:
                f.write(f"@echo off\n{command}\n")
            return f"Added '{name}' to startup"
        except Exception as e:
            return f"Failed to add startup program: {e}"

    @staticmethod
    def remove_startup_program(name: str) -> str:
        """Remove a program from startup."""
        try:
            startup_folder = os.path.join(
                os.environ["APPDATA"],
                r"Microsoft\Windows\Start Menu\Programs\Startup"
            )
            bat_path = os.path.join(startup_folder, f"{name}.bat")
            if os.path.exists(bat_path):
                os.remove(bat_path)
                return f"Removed '{name}' from startup"
            # Also try .lnk shortcut
            lnk_path = os.path.join(startup_folder, f"{name}.lnk")
            if os.path.exists(lnk_path):
                os.remove(lnk_path)
                return f"Removed '{name}' from startup"
            return f"'{name}' not found in startup"
        except Exception as e:
            return f"Failed to remove startup program: {e}"

    # ── Disk Management ─────────────────────────────────────
    @staticmethod
    def get_disk_info() -> str:
        """Get disk usage information."""
        try:
            import psutil
            disks = []
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append(
                        f"{part.device} ({part.mountpoint})\n"
                        f"  Total: {usage.total // (1024**3)} GB\n"
                        f"  Used: {usage.used // (1024**3)} GB ({usage.percent}%)\n"
                        f"  Free: {usage.free // (1024**3)} GB"
                    )
                except PermissionError:
                    continue
            return "\n\n".join(disks) if disks else "No disk info available"
        except ImportError:
            return "Disk info requires psutil"

    @staticmethod
    def get_large_files(directory: str, min_size_mb: int = 100) -> str:
        """Find large files in a directory."""
        path = Path(directory)
        if not path.exists():
            return f"Directory not found: {directory}"
        large_files = []
        try:
            for f in path.rglob("*"):
                if f.is_file():
                    size_mb = f.stat().st_size / (1024 * 1024)
                    if size_mb >= min_size_mb:
                        large_files.append((str(f), size_mb))
            large_files.sort(key=lambda x: x[1], reverse=True)
            if not large_files:
                return f"No files larger than {min_size_mb}MB found"
            lines = [f"{f[1]:.1f} MB  {f[0]}" for f in large_files[:20]]
            return f"Large files:\n" + "\n".join(lines)
        except PermissionError:
            return "Permission denied accessing some files"

    @staticmethod
    def get_folder_size(directory: str) -> str:
        """Get total size of a folder."""
        path = Path(directory)
        if not path.exists():
            return f"Directory not found: {directory}"
        try:
            total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            if total > 1024 * 1024 * 1024:
                return f"Folder size: {total / (1024**3):.2f} GB"
            return f"Folder size: {total / (1024**2):.1f} MB"
        except Exception as e:
            return f"Could not calculate folder size: {e}"

    # ── Environment Variables ───────────────────────────────
    @staticmethod
    def get_env_var(name: str) -> str:
        """Get an environment variable."""
        value = os.environ.get(name)
        if value is not None:
            return f"{name} = {value}"
        return f"Environment variable '{name}' not set"

    @staticmethod
    def set_env_var(name: str, value: str, target: str = "User") -> str:
        """Set an environment variable (User or Machine level)."""
        try:
            ps_script = (
                f"[System.Environment]::SetEnvironmentVariable('{name}', '{value}', '{target}'); "
                f"'Set {name} = {value} for {target}'"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            # Also set for current session
            os.environ[name] = value
            return result.stdout.strip() or f"Set {name} = {value}"
        except Exception as e:
            return f"Failed to set env var: {e}"

    @staticmethod
    def list_env_vars(filter_str: str = "") -> str:
        """List environment variables."""
        try:
            env_vars = dict(os.environ)
            if filter_str:
                env_vars = {k: v for k, v in env_vars.items() if filter_str.lower() in k.lower()}
            lines = [f"{k} = {v[:100]}" for k, v in sorted(env_vars.items())]
            output = "\n".join(lines[:50])
            return f"Environment variables ({len(env_vars)} total):\n{output}"
        except Exception as e:
            return f"Failed to list env vars: {e}"

    # ── Power Management ────────────────────────────────────
    @staticmethod
    def get_battery_info() -> str:
        """Get battery information."""
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery is None:
                return "No battery detected (desktop PC)"
            status = "Charging" if battery.power_plugged else "Discharging"
            return (
                f"Battery: {battery.percent}%\n"
                f"Status: {status}\n"
                f"Time left: {battery.secsleft // 3600}h {(battery.secsleft % 3600) // 60}m"
            ) if battery.secsleft > 0 else (
                f"Battery: {battery.percent}%\nStatus: {status}"
            )
        except ImportError:
            return "Battery info requires psutil"

    @staticmethod
    def get_power_plan() -> str:
        """Get current power plan."""
        try:
            result = subprocess.run(
                ["powercfg", "/getactivescheme"],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() or "Could not get power plan"
        except Exception as e:
            return f"Power plan query failed: {e}"

    @staticmethod
    def set_power_plan(plan: str) -> str:
        """Set power plan (balanced, powersaver, highperformance)."""
        plans = {
            "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",
            "powersaver": "a1841308-3541-4fab-bc81-f71556f20b4a",
            "highperformance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
            "ultimate": "e9a42b02-d5df-448d-aa00-03f14749eb61",
        }
        plan_lower = plan.lower().strip()
        guid = plans.get(plan_lower)
        if guid:
            try:
                subprocess.run(["powercfg", "/setactive", guid], capture_output=True, timeout=10)
                return f"Power plan set to: {plan}"
            except Exception as e:
                return f"Failed to set power plan: {e}"
        return f"Unknown power plan: {plan}. Options: balanced, powersaver, highperformance, ultimate"

    # ── Device Management ───────────────────────────────────
    @staticmethod
    def list_usb_devices() -> str:
        """List connected USB devices."""
        try:
            ps_script = (
                "Get-PnpDevice | Where-Object { $_.InstanceId -like 'USB\\*' -and $_.Status -eq 'OK' } | "
                "Select-Object FriendlyName, InstanceId | "
                "Format-Table -AutoSize -Wrap"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=15,
            )
            output = result.stdout.strip()
            return f"USB devices:\n{output}" if output else "No USB devices found"
        except Exception as e:
            return f"USB listing failed: {e}"

    @staticmethod
    def list_displays() -> str:
        """List connected displays."""
        try:
            ps_script = (
                "Get-CimInstance Win32_DesktopMonitor | "
                "Select-Object Name, ScreenWidth, ScreenHeight | "
                "Format-Table -AutoSize"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() or "No display info available"
        except Exception as e:
            return f"Display listing failed: {e}"

    @staticmethod
    def list_printers() -> str:
        """List installed printers."""
        try:
            ps_script = (
                "Get-Printer | Select-Object Name, DriverName, PrinterStatus | "
                "Format-Table -AutoSize -Wrap"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            output = result.stdout.strip()
            return f"Printers:\n{output}" if output else "No printers found"
        except Exception as e:
            return f"Printer listing failed: {e}"

    @staticmethod
    def list_audio_devices() -> str:
        """List audio input/output devices."""
        try:
            ps_script = (
                "Get-AudioDevice -List 2>$null | "
                "Select-Object Name, Type, Default | "
                "Format-Table -AutoSize -Wrap"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            if result.stdout.strip():
                return result.stdout.strip()
            # Fallback
            ps_script = (
                "Get-WmiObject Win32_SoundDevice | "
                "Select-Object Name, Status | "
                "Format-Table -AutoSize"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() or "No audio devices found"
        except Exception as e:
            return f"Audio device listing failed: {e}"

    # ── Package Management (Winget/Choco) ──────────────────
    @staticmethod
    def winget_search(query: str) -> str:
        """Search for packages using winget."""
        try:
            result = subprocess.run(
                ["winget", "search", query],
                capture_output=True, text=True, timeout=30,
            )
            output = result.stdout.strip()
            return output[:2000] if output else f"No packages found for '{query}'"
        except FileNotFoundError:
            return "Winget is not installed"
        except Exception as e:
            return f"Winget search failed: {e}"

    @staticmethod
    def winget_install(package: str) -> str:
        """Install a package using winget."""
        try:
            result = subprocess.run(
                ["winget", "install", package, "--accept-package-agreements", "--accept-source-agreements"],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                return f"Installed {package}"
            return f"Install result: {result.stdout[-500:]}"
        except FileNotFoundError:
            return "Winget is not installed"
        except Exception as e:
            return f"Winget install failed: {e}"

    @staticmethod
    def winget_uninstall(package: str) -> str:
        """Uninstall a package using winget."""
        try:
            result = subprocess.run(
                ["winget", "uninstall", package, "--accept-source-agreements"],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                return f"Uninstalled {package}"
            return f"Uninstall result: {result.stdout[-500:]}"
        except FileNotFoundError:
            return "Winget is not installed"
        except Exception as e:
            return f"Winget uninstall failed: {e}"

    @staticmethod
    def winget_list_installed() -> str:
        """List installed packages via winget."""
        try:
            result = subprocess.run(
                ["winget", "list"],
                capture_output=True, text=True, timeout=30,
            )
            output = result.stdout.strip()
            return output[:3000] if output else "No installed packages found"
        except FileNotFoundError:
            return "Winget is not installed"
        except Exception as e:
            return f"Winget list failed: {e}"

    # ── Windows Features ────────────────────────────────────
    @staticmethod
    def list_windows_features() -> str:
        """List optional Windows features."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WindowsOptionalFeature -Online | Where-Object {$_.State -eq 'Enabled'} | "
                 "Select-Object FeatureName, State | Format-Table -AutoSize"],
                capture_output=True, text=True, timeout=30,
            )
            output = result.stdout.strip()
            return output[:3000] if output else "No features found"
        except Exception as e:
            return f"Feature listing failed: {e}"

    # ── Scheduled Tasks ─────────────────────────────────────
    @staticmethod
    def list_scheduled_tasks() -> str:
        """List scheduled tasks."""
        try:
            ps_script = (
                "Get-ScheduledTask | Where-Object {$_.State -ne 'Disabled'} | "
                "Select-Object TaskName, TaskPath, State | "
                "Format-Table -AutoSize -Wrap"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=15,
            )
            output = result.stdout.strip()
            return output[:3000] if output else "No scheduled tasks found"
        except Exception as e:
            return f"Task listing failed: {e}"

    # ── Screenshot ──────────────────────────────────────────
    @staticmethod
    def take_screenshot() -> str:
        """Take a screenshot and save to desktop."""
        desktop = Path.home() / "Desktop"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = desktop / f"screenshot_{timestamp}.png"
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            screenshot.save(str(filename))
            return f"Screenshot saved to {filename}"
        except ImportError:
            ps_script = (
                f"Add-Type -AssemblyName System.Windows.Forms;"
                f"$screen = [System.Windows.Forms.Screen]::PrimaryScreen;"
                f"$bitmap = New-Object System.Drawing.Bitmap($screen.Bounds.Width, $screen.Bounds.Height);"
                f"$graphics = [System.Drawing.Graphics]::FromImage($bitmap);"
                f"$graphics.CopyFromScreen($screen.Bounds.Location, [System.Drawing.Point]::Empty, $screen.Bounds.Size);"
                f"$bitmap.Save('{filename}');"
                f"$graphics.Dispose(); $bitmap.Dispose()"
            )
            subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, timeout=10,
            )
            return f"Screenshot saved to {filename}"

    # ── System Info ─────────────────────────────────────────
    @staticmethod
    def get_system_info() -> str:
        """Get comprehensive system information."""
        try:
            import platform
            import psutil
            info = []
            info.append(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
            info.append(f"Machine: {platform.machine()}")
            info.append(f"Processor: {platform.processor()[:60]}")
            info.append(f"CPU cores: {psutil.cpu_count()} ({psutil.cpu_count(logical=False)} physical)")
            info.append(f"CPU usage: {psutil.cpu_percent(interval=1)}%")
            ram = psutil.virtual_memory()
            info.append(f"RAM: {ram.total // (1024**3)} GB ({ram.percent}% used, {ram.available // (1024**3)} GB free)")
            disk = psutil.disk_usage('\\')
            info.append(f"Disk C:: {disk.total // (1024**3)} GB ({disk.percent}% used)")
            boot = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot
            hours = int(uptime.total_seconds() // 3600)
            mins = int((uptime.total_seconds() % 3600) // 60)
            info.append(f"Uptime: {hours}h {mins}m")
            info.append(f"Username: {os.environ.get('USERNAME', 'N/A')}")
            info.append(f"Computer: {os.environ.get('COMPUTERNAME', 'N/A')}")
            return "\n".join(info)
        except ImportError:
            import platform
            return f"OS: {platform.system()} {platform.release()}\nMachine: {platform.machine()}"

    @staticmethod
    def get_system_stats() -> dict:
        """Get real-time system stats."""
        stats = {"ram_percent": 0.0, "gpu_percent": None, "cpu_percent": None}
        try:
            import psutil
            stats["ram_percent"] = round(psutil.virtual_memory().percent, 1)
            stats["cpu_percent"] = round(psutil.cpu_percent(interval=0.5), 1)
        except ImportError:
            pass
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                gpu_str = result.stdout.strip()
                if gpu_str:
                    stats["gpu_percent"] = round(float(gpu_str.split("\n")[0].strip()), 1)
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, IndexError):
            pass
        return stats

    # ── Weather ─────────────────────────────────────────────
    @staticmethod
    async def get_weather(location: str = "") -> str:
        """Get weather information."""
        import httpx
        try:
            query = location or "auto:ip"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://wttr.in/{query}",
                    params={"format": "%C %t %h %w"},
                )
                return response.text.strip()
        except Exception as e:
            return f"Weather error: {e}"

    # ── Web & Search ────────────────────────────────────────
    @staticmethod
    def open_url(url: str) -> str:
        """Open a URL in the default browser."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        subprocess.Popen(["start", url], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened {url}"

    @staticmethod
    def web_search(query: str) -> str:
        """Search the web using the default browser."""
        import urllib.parse
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}"
        subprocess.Popen(["start", url], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Searching for: {query}"

    # ── Settings ────────────────────────────────────────────
    @staticmethod
    def open_settings(page: str = "") -> str:
        """Open Windows Settings (optionally a specific page)."""
        settings_pages = {
            "display": "ms-settings:display", "sound": "ms-settings:sound",
            "network": "ms-settings:network", "wifi": "ms-settings:network-wifi",
            "bluetooth": "ms-settings:bluetooth",
            "personalization": "ms-settings:personalization",
            "wallpaper": "ms-settings:personalization-background",
            "themes": "ms-settings:themes", "apps": "ms-settings:appsfeatures",
            "storage": "ms-settings:storagesense", "battery": "ms-settings:batterysaver",
            "power": "ms-settings:powersleep", "notifications": "ms-settings:notifications",
            "focus": "ms-settings:quiethours", "privacy": "ms-settings:privacy",
            "camera": "ms-settings:privacy-webcam",
            "mic": "ms-settings:privacy-microphone",
            "location": "ms-settings:privacy-location",
            "firewall": "ms-settings:windowsfirewall",
            "update": "ms-settings:windowsupdate", "about": "ms-settings:about",
            "system": "ms-settings:system", "time": "ms-settings:dateandtime",
            "region": "ms-settings:regionformatting",
            "accessibility": "ms-settings:easeofaccess",
            "mouse": "ms-settings:mouse", "keyboard": "ms-settings:keyboard",
        }
        key = page.lower().strip()
        uri = settings_pages.get(key, "ms-settings:")
        subprocess.Popen(["start", uri], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened Settings: {page or 'General'}"

    # ── System Operations ───────────────────────────────────
    @staticmethod
    def shutdown(delay: int = 0) -> str:
        """Shutdown the PC."""
        subprocess.run(["shutdown", "/s", "/t", str(delay)])
        if delay > 0:
            return f"Shutting down in {delay} seconds~"
        return "Shutting down now~"

    @staticmethod
    def restart(delay: int = 0) -> str:
        """Restart the PC."""
        subprocess.run(["shutdown", "/r", "/t", str(delay)])
        if delay > 0:
            return f"Restarting in {delay} seconds~"
        return "Restarting now~"

    @staticmethod
    def sleep_pc() -> str:
        """Put the PC to sleep."""
        subprocess.run(["powershell", "-Command",
                        "Add-Type -AssemblyName System.Windows.Forms; "
                        "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"])
        return "Going to sleep~"

    @staticmethod
    def lock_pc() -> str:
        """Lock the workstation."""
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
        return "PC locked"

    @staticmethod
    def cancel_shutdown() -> str:
        """Cancel a pending shutdown."""
        subprocess.run(["shutdown", "/a"])
        return "Shutdown cancelled"

    # ── PowerShell / CMD Execution ──────────────────────────
    @staticmethod
    def run_powershell(command: str) -> str:
        """Execute a PowerShell command and return output."""
        try:
            result = subprocess.run(
                ["powershell", "-Command", command],
                capture_output=True, text=True, timeout=30,
            )
            output = result.stdout.strip()
            if result.returncode != 0 and result.stderr.strip():
                return f"Error: {result.stderr.strip()[:500]}"
            return output[:2000] if output else "Command executed (no output)"
        except subprocess.TimeoutExpired:
            return "Command timed out (30s limit)"
        except Exception as e:
            return f"Command failed: {e}"

    @staticmethod
    def run_cmd(command: str) -> str:
        """Execute a CMD command and return output."""
        try:
            result = subprocess.run(
                command, shell=True,
                capture_output=True, text=True, timeout=30,
            )
            output = result.stdout.strip()
            if result.returncode != 0 and result.stderr.strip():
                return f"Error: {result.stderr.strip()[:500]}"
            return output[:2000] if output else "Command executed (no output)"
        except subprocess.TimeoutExpired:
            return "Command timed out (30s limit)"
        except Exception as e:
            return f"Command failed: {e}"
