"""Layer 3: Application Control — Launch, close, discover, automate.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 5:

7-Strategy Launch:    1. Everything search (es.exe — instant filesystem search)
  2. Shell URIs (Settings, UWP apps, folders)
  3. Known app registry with multi-path resolution + aliases
  4. Fuzzy match — resolves typos/abbreviations via Levenshtein + abbreviation matching
  5. os.startfile() (Windows shell resolution)
  6. PowerShell Start-Process
  7. .exe extension retry
  8. Start Menu shortcut search
  9. Common install directory search

Libraries: winreg, win32api, pywinauto, win32com.client, subprocess
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.engine.verifier import Verifiers
from core.layers._utils import run_ps, run_cmd, create_escalation_fn, create_preflight_fn
from core.layers.fuzzy_match import fuzzy_best

# Duplicate launch prevention: track recently launched apps
_recently_launched: dict[str, float] = {}
_LAUNCH_COOLDOWN = 2.0  # seconds — don't re-launch same app within this window


def _is_already_launched(app_name: str) -> bool:
    """Check if an app was launched recently (within cooldown window)."""
    now = time.time()
    last_launch = _recently_launched.get(app_name.lower())
    if last_launch and (now - last_launch) < _LAUNCH_COOLDOWN:
        return True
    return False


def _record_launch(app_name: str):
    """Record that an app was just launched."""
    _recently_launched[app_name.lower()] = time.time()
    # Cleanup old entries
    now = time.time()
    expired = [k for k, v in _recently_launched.items() if (now - v) > 60]
    for k in expired:
        del _recently_launched[k]
from core.layers.everything_search import is_everything_available, everything_find_app

import logging
import subprocess as _subprocess
logger = logging.getLogger("may.core.layers.L3_application")


# ── Dynamic App Discovery ────────────────────────────────────────────────────
# Instead of relying solely on hardcoded paths, query the OS for app locations.

_app_path_cache: dict[str, str | None] = {}


def _find_app_path(name: str) -> str | None:
    """Find an app's exe path by querying the OS.

    Strategy order:
    1. Check cache
    2. where.exe (PATH lookup)
    3. Windows App Paths registry (HKLM/HKCU SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths)
    4. Start Menu .lnk shortcut scan
    5. Return None (caller falls back to KNOWN_APPS)

    Caches results to avoid repeated OS queries.
    """
    name_lower = name.lower().strip()
    if name_lower in _app_path_cache:
        return _app_path_cache[name_lower]

    result = _find_app_path_uncached(name_lower)
    _app_path_cache[name_lower] = result
    return result


def _find_app_path_uncached(name: str) -> str | None:
    """Uncached app path lookup — called by _find_app_path."""
    # 1. where.exe (fast PATH lookup)
    exe_name = name if name.endswith(".exe") else f"{name}.exe"
    try:
        r = _subprocess.run(
            ["where", exe_name],
            capture_output=True, text=True, timeout=3, creationflags=getattr(_subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if r.returncode == 0 and r.stdout.strip():
            first = r.stdout.strip().splitlines()[0].strip()
            if os.path.isfile(first):
                logger.debug("App '%s' found via where.exe: %s", name, first)
                return first
    except Exception:
        pass

    # 2. Windows App Paths registry
    try:
        import winreg
        app_paths_key = name if name.endswith(".exe") else f"{name}.exe"
        for hive_name, hive in [("HKLM", winreg.HKEY_LOCAL_MACHINE), ("HKCU", winreg.HKEY_CURRENT_USER)]:
            try:
                key = winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{app_paths_key}")
                try:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val and os.path.isfile(os.path.expandvars(val)):
                        logger.debug("App '%s' found via App Paths registry (%s): %s", name, hive_name, val)
                        return os.path.expandvars(val)
                except FileNotFoundError:
                    pass
                finally:
                    winreg.CloseKey(key)
            except OSError:
                pass
    except ImportError:
        pass

    # 3. Start Menu .lnk scan
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        appdata = os.environ.get("APPDATA", "")
        programdata = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        for base in [
            os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(programdata, "Microsoft", "Windows", "Start Menu", "Programs"),
        ]:
            if not os.path.isdir(base):
                continue
            for root, dirs, files in os.walk(base):
                for f in files:
                    if not f.lower().endswith(".lnk"):
                        continue
                    shortcut_name = f[:-4].lower()  # remove .lnk
                    if name in shortcut_name or shortcut_name.startswith(name):
                        try:
                            shortcut = shell.CreateShortCut(os.path.join(root, f))
                            target = shortcut.Targetpath
                            if target and os.path.isfile(target):
                                logger.debug("App '%s' found via Start Menu shortcut: %s", name, target)
                                return target
                        except Exception:
                            pass
    except ImportError:
        pass

    return None


# ── Known App Registry ───────────────────────────────────────────────────────

KNOWN_APPS: dict[str, list[str]] = {
    # Browsers
    "chrome": [os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
               r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
    "google chrome": ["chrome"],
    "firefox": [r"C:\Program Files\Mozilla Firefox\firefox.exe"],
    "edge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
    "brave": [os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe")],
    "opera": [r"C:\Program Files\Opera\launcher.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\launcher.exe"),
              r"C:\Program Files (x86)\Opera\launcher.exe"],
    "opera browser": ["opera"],
    # Communication
    "discord": [os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Discord\Discord.exe")],
    "slack": [os.path.expandvars(r"%LOCALAPPDATA%\slack\slack.exe")],
    "telegram": [os.path.expandvars(r"%LOCALAPPDATA%\Telegram Desktop\Telegram.exe"),
                 r"C:\Program Files\Telegram Desktop\Telegram.exe"],
    "zoom": [r"C:\Program Files\Zoom\bin\Zoom.exe"],
    # Dev
    "vscode": [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe")],
    "visual studio code": ["vscode"],
    "vs code": ["vscode"],
    "notepad++": [r"C:\Program Files\Notepad++\notepad++.exe"],
    "npp": ["notepad++"],
    # Gaming
    "steam": [r"C:\Program Files (x86)\Steam\steam.exe",
              r"D:\Steam\steam.exe"],
    "epic": [r"C:\Program Files (x86)\Epic Games\Launcher\Portal\Binaries\Win32\EpicGamesLauncher.exe"],
    "gog": [r"C:\Program Files (x86)\GOG Galaxy\GalaxyClient.exe",
             os.path.expandvars(r"%LOCALAPPDATA%\GOG Galaxy\GalaxyClient.exe")],
    "ea": [r"C:\Program Files\Electronic Arts\EA Desktop\EADesktop.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Electronic Arts\EA Desktop\EADesktop.exe")],
    "ea app": ["ea"],
    "origin": ["ea"],
    "ubisoft": [r"C:\Program Files (x86)\Ubisoft\Ubisoft Game Launcher\upc.exe"],
    "ubisoft connect": ["ubisoft"],
    "battle.net": [r"C:\Program Files (x86)\Battle.net\Battle.net.exe"],
    "blizzard": ["battle.net"],

    "ryujinx": [os.path.expandvars(r"%LOCALAPPDATA%\Ryujinx\Ryujinx.exe"),
                r"C:\Program Files\Ryujinx\Ryujinx.exe"],
    "horizon zero dawn": [r"C:\Program Files\Epic Games\HorizonZeroDawn\HorizonZeroDawn.exe",
                          r"C:\Program Files (x86)\Steam\steamapps\common\Horizon Zero Dawn\HorizonZeroDawn.exe"],
    "horizon": ["horizon zero dawn"],

    "riot": [os.path.expandvars(r"%LOCALAPPDATA%\Riot Client\RiotClientServices.exe")],
    "league of legends": ["riot"],
    "valorant": ["riot"],
    "roblox": [os.path.expandvars(r"%LOCALAPPDATA%\Roblox\Versions\RobloxPlayerBeta.exe")],
    "minecraft": [r"C:\Program Files (x86)\Minecraft Launcher\MinecraftLauncher.exe",
                   os.path.expandvars(r"%LOCALAPPDATA%\Programs\minecraft-launcher\MinecraftLauncher.exe")],
    "geforce now": [os.path.expandvars(r"%LOCALAPPDATA%\NVIDIA\GeForceNOW\GeForceNOW.exe")],
    "nvidia geforce now": ["geforce now"],
    "nvidia geforce experience": [r"C:\Program Files\NVIDIA Corporation\NVIDIA GeForce Experience\GFExperience.exe"],

    # UWP/Store Apps (launched via shell URI or AppxPackage)
    "whatsapp": ["shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"],
    "lenovo vantage": ["shell:AppsFolder\\E046963F.LenovoCompanion_k1h2ywk1493x8!App"],
    "pc manager": ["shell:AppsFolder\\Microsoft.MicrosoftPCManager_8wekyb3d8bbwe!App"],
    "neverness to everness": ["neverness"],
    # Adobe
    "photoshop": [r"C:\Program Files\Adobe\Adobe Photoshop 2025\Photoshop.exe",
                   r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
                   r"C:\Program Files\Adobe\Adobe Photoshop CC 2019\Photoshop.exe"],
    "adobe photoshop": ["photoshop"],
    "illustrator": [r"C:\Program Files\Adobe\Adobe Illustrator 2025\Support Files\Contents\Windows\Illustrator.exe",
                     r"C:\Program Files\Adobe\Adobe Illustrator 2024\Support Files\Contents\Windows\Illustrator.exe"],
    "adobe illustrator": ["illustrator"],
    "premiere pro": [r"C:\Program Files\Adobe\Adobe Premiere Pro 2025\Premiere.exe",
                      r"C:\Program Files\Adobe\Adobe Premiere Pro 2024\Premiere.exe"],
    "adobe premiere": ["premiere pro"],
    "after effects": [r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe",
                       r"C:\Program Files\Adobe\Adobe After Effects 2024\Support Files\AfterFX.exe"],
    "adobe after effects": ["after effects"],
    "lightroom": [r"C:\Program Files\Adobe\Adobe Lightroom\Lightroom.exe",
                   os.path.expandvars(r"%LOCALAPPDATA%\Adobe\Lightroom\Lightroom.exe")],
    "adobe lightroom": ["lightroom"],
    "acrobat": [r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe",
                 r"C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe"],
    "adobe acrobat": ["acrobat"],
    "xd": [r"C:\Program Files\Adobe\Adobe XD\XD.exe"],
    "adobe xd": ["xd"],
    "indesign": [r"C:\Program Files\Adobe\Adobe InDesign 2025\InDesign.exe",
                  r"C:\Program Files\Adobe\Adobe InDesign 2024\InDesign.exe"],
    "adobe indesign": ["indesign"],
    # Media
    "spotify": [os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")],
    "vlc": [r"C:\Program Files\VideoLAN\VLC\vlc.exe"],
    "obs": [r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"],
    "audacity": [r"C:\Program Files\Audacity\audacity.exe"],
    "blender": [r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
                 r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe"],
    "gimp": [r"C:\Program Files\GIMP 2\bin\gimp-2.10.exe"],
    "handbrake": [r"C:\Program Files\HandBrake\HandBrake.exe"],
    "mpv": ["mpv"],
    "foobar2000": [r"C:\Program Files (x86)\foobar2000\foobar2000.exe"],
    "aimp": [r"C:\Program Files\AIMP\AIMP.exe"],
    # Productivity
    "word": [r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"],
    "excel": [r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE"],
    "powerpoint": [r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE"],
    "microsoft powerpoint": ["powerpoint"],
    "outlook": [r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE"],
    "onenote": [r"C:\Program Files\Microsoft Office\root\Office16\ONENOTE.EXE"],
    "teams": [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Teams\current\Teams.exe"),
               os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Teams\current\squirrel.exe")],
    "google drive": [os.path.expandvars(r"%LOCALAPPDATA%\Google\DriveFileStreamer\GoogleDriveFS.exe")],
    "dropbox": [os.path.expandvars(r"%LOCALAPPDATA%\Dropbox\Update\DropboxUpdate.exe")],
    "onedrive": [r"C:\Program Files\Microsoft OneDrive\OneDrive.exe"],
    "notion": [os.path.expandvars(r"%LOCALAPPDATA%\Notion\Notion.exe")],
    "todoist": [os.path.expandvars(r"%LOCALAPPDATA%\Programs\todoist\Todoist.exe")],
    "obsidian": [os.path.expandvars(r"%LOCALAPPDATA%\Programs\obsidian\Obsidian.exe")],
    "logseq": [os.path.expandvars(r"%LOCALAPPDATA%\Programs\logseq\Logseq.exe")],
    # Dev
    "git": [r"C:\Program Files\Git\cmd\git.exe"],
    "github desktop": [os.path.expandvars(r"%LOCALAPPDATA%\GitHubDesktop\GitHubDesktop.exe")],
    "gitkraken": [os.path.expandvars(r"%LOCALAPPDATA%\gitkraken\gitkraken.exe")],
    "sublime": [r"C:\Program Files\Sublime Text\sublime_text.exe",
                 r"C:\Program Files\Sublime Text 3\sublime_text.exe"],
    "sublime text": ["sublime"],
    "intellij": [r"C:\Program Files\JetBrains\IntelliJ IDEA 2024.2\bin\idea64.exe",
                 r"C:\Program Files\JetBrains\IntelliJ IDEA 2023.3\bin\idea64.exe"],
    "intellij idea": ["intellij"],
    "pycharm": [r"C:\Program Files\JetBrains\PyCharm 2024.2\bin\pycharm64.exe",
                 r"C:\Program Files\JetBrains\PyCharm 2023.3\bin\pycharm64.exe"],
    "webstorm": [r"C:\Program Files\JetBrains\WebStorm 2024.2\bin\webstorm64.exe"],
    "android studio": [r"C:\Program Files\Android\Android Studio\bin\studio64.exe"],
    "docker": [r"C:\Program Files\Docker\Docker\Docker Desktop.exe"],
    "docker desktop": ["docker"],
    "npm": ["npm"],
    "node": ["node"],
    "python": ["python"],
    "pip": ["pip"],
    # System
    "notepad": [r"C:\Windows\System32\notepad.exe", "notepad"],
    "calc": [r"C:\Windows\System32\calc.exe", "calc"],
    "calculator": ["calc"],
    "paint": [r"C:\Windows\System32\mspaint.exe", "mspaint"],
    "cmd": [r"C:\Windows\System32\cmd.exe", "cmd"],
    "powershell": [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "powershell"],
    "terminal": [r"C:\Users\RED\AppData\Local\Microsoft\WindowsApps\wt.exe", "wt"],
    "explorer": [r"C:\Windows\explorer.exe", "explorer"],
    "file explorer": ["explorer"],
    "windows explorer": ["explorer"],
}

SHELL_URIS: dict[str, str] = {
    "settings": "ms-settings:",
    "display settings": "ms-settings:display",
    "sound settings": "ms-settings:sound",
    "network settings": "ms-settings:network",
    "bluetooth settings": "ms-settings:bluetooth",
    "recycle bin": "shell:RecycleBinFolder",
    "downloads": "shell:Downloads",
    "documents": "shell:Personal",
    "desktop": "shell:Desktop",
    "this pc": "shell:MyComputerFolder",
    "my computer": "shell:MyComputerFolder",
    "my pc": "shell:MyComputerFolder",
    "pc": "shell:MyComputerFolder",
    "file explorer": "shell:MyComputerFolder",
    "store": "ms-windows-store:",
    "microsoft store": "ms-windows-store:",
    "windows store": "ms-windows-store:",
    "app store": "ms-windows-store:",
    # UWP/Store Apps
    "whatsapp": "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
    "lenovo vantage": "shell:AppsFolder\\E046963F.LenovoCompanion_k1h2ywk1493x8!App",
    "pc manager": "shell:AppsFolder\\Microsoft.MicrosoftPCManager_8wekyb3d8bbwe!App",
    "neverness to everness": "shell:AppsFolder\\neverness",
    "calculator": "calculator:",
    # "notepad" removed — notepad: URI only works if UWP Notepad is installed.
    # Use known registry with actual exe path instead.
    "paint": "mspaint:",
    "snipping tool": "snippingtool:",
}


# ══════════════════════════════════════════════════════════════════════════════
# LAUNCH — 7 strategies
# ══════════════════════════════════════════════════════════════════════════════

async def _launch_shell_uri(params: dict) -> Any:
    """Strategy 1: Shell URIs (Settings, UWP apps, folders).

    Catches Windows popup errors (e.g. "Get an app to open this link") when
    the UWP app isn't installed, and raises RuntimeError to fall back.
    """
    name = params["app_name"].lower().strip()
    uri = SHELL_URIS.get(name)
    if not uri:
        raise RuntimeError(f"No shell URI for '{name}'")
    try:
        os.startfile(uri)
    except OSError as e:
        # Windows shows popup "Get an app to open this link" — the URI failed
        raise RuntimeError(f"Shell URI '{uri}' failed: {e}") from e
    # Brief delay then check if app actually appeared (catch Windows popup failures)
    await asyncio.sleep(0.5)
    # Try to find exe_path for verification
    exe_path = _find_app_path(name)
    if not exe_path and name in KNOWN_APPS:
        known = KNOWN_APPS[name]
        paths = known if isinstance(known, list) else [known]
        for path in paths:
            resolved = os.path.expandvars(path)
            if os.path.isfile(resolved):
                exe_path = resolved
                break
    return {"app": name, "method": "shell_uri", "pid": None, "exe_path": exe_path}


async def _launch_known_registry(params: dict) -> Any:
    """Strategy 2: Known app registry with multi-path resolution."""
    name = params["app_name"].lower().strip()
    entry = KNOWN_APPS.get(name)
    if not entry:
        raise RuntimeError(f"App '{name}' not in known registry")

    # Resolve aliases
    visited = set()
    paths_to_try = list(entry) if isinstance(entry, list) else [entry]
    resolved = []
    for raw in paths_to_try:
        if raw in KNOWN_APPS and raw not in visited:
            visited.add(raw)
            alias = KNOWN_APPS[raw]
            paths_to_try.extend(alias if isinstance(alias, list) else [alias])
        else:
            resolved.append(raw)

    for path in resolved:
        resolved_path = os.path.expandvars(path)
        if os.path.isfile(resolved_path):
            # Special handling for Discord Update.exe
            if "Update.exe" in resolved_path:
                try:
                    proc = subprocess.Popen([resolved_path, "--processStart", f"{name.capitalize()}.exe"],
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    # Wait briefly for the actual process to start
                    await asyncio.sleep(0.5)
                    return {"app": name, "method": "known_registry", "pid": proc.pid, "exe_path": resolved_path}
                except Exception:
                    pass
            else:
                proc = subprocess.Popen([resolved_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                await asyncio.sleep(0.3)
                return {"app": name, "method": "known_registry", "pid": proc.pid, "exe_path": resolved_path}

    # Try bare commands (no path separator) — e.g. notepad, calc, cmd, explorer,
    # which live on the system PATH / are resolved by the Windows shell. These are
    # stored as single-element lists like ["notepad"], so we must scan the resolved
    # list, not just the str case. Uses cmd /c without shell=True to avoid injection.
    for cand in resolved:
        if os.sep not in cand and "/" not in cand and not os.path.isabs(cand):
            try:
                proc = subprocess.Popen(
                    ["cmd", "/c", cand],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                await asyncio.sleep(0.3)
                return {"app": name, "method": "known_registry_command",
                        "pid": proc.pid, "exe_path": None}
            except (OSError, ValueError):
                continue

    raise RuntimeError(f"All known paths for '{name}' not found")


async def _launch_dynamic_registry(params: dict) -> Any:
    """Strategy 2b: Dynamic app discovery via OS queries.

    Queries where.exe, App Paths registry, and Start Menu shortcuts
    to find apps not in the hardcoded KNOWN_APPS dict.
    """
    name = params["app_name"].lower().strip()
    exe_path = _find_app_path(name)
    if not exe_path:
        raise RuntimeError(f"Dynamic discovery found no path for '{name}'")
    try:
        proc = subprocess.Popen([exe_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.sleep(0.3)
        return {"app": name, "method": "dynamic_registry", "pid": proc.pid, "exe_path": exe_path}
    except Exception as e:
        raise RuntimeError(f"Failed to launch '{exe_path}': {e}")


async def _launch_fuzzy(params: dict) -> Any:
    """Strategy 3: Fuzzy match against known apps (typos, abbreviations)."""
    name = params["app_name"].lower().strip()
    # Skip fuzzy if exact match already failed (strategy 2 handles exact)
    # Only fire if the name looks like a partial/misspelled input
    result = fuzzy_best(name, KNOWN_APPS.keys(), threshold=0.60)
    if result is None:
        raise RuntimeError(f"No fuzzy match for '{name}'")
    logger.info(
        "Fuzzy match: '%s' → '%s' (confidence: %.2f, method: %s)",
        name, result.candidate, result.confidence, result.method,
    )
    # Re-dispatch through the known registry with the resolved name
    params_copy = dict(params)
    params_copy["app_name"] = result.candidate
    return await _launch_known_registry(params_copy)


async def _launch_startfile(params: dict) -> Any:
    """Strategy 4: os.startfile()."""
    name = params["app_name"]
    try:
        os.startfile(name)
        await asyncio.sleep(0.5)
        # Try to find the PID of the launched process
        pid = _find_pid_by_name(name)
        return {"app": name, "method": "startfile", "pid": pid, "exe_path": None}
    except Exception as e:
        raise RuntimeError(f"startfile failed: {e}")


def _find_pid_by_name(name: str) -> int | None:
    """Try to find PID of recently launched process by name."""
    try:
        import psutil
        name_lower = name.lower().strip()
        if name_lower.endswith(".exe"):
            name_lower = name_lower[:-4]
        for p in psutil.process_iter(["pid", "name", "exe"]):
            try:
                p_name = p.info["name"].lower() if p.info["name"] else ""
                p_exe = p.info["exe"].lower() if p.info["exe"] else ""
                if name_lower in p_name or (p_exe and name_lower in os.path.basename(p_exe)):
                    return p.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass
    return None


async def _launch_powershell(params: dict) -> Any:
    """Strategy 5: PowerShell Start-Process."""
    name = params["app_name"].replace("'", "").replace(";", "")
    success, output = await run_ps(f"Start-Process '{name}' -ErrorAction Stop -PassThru")
    if not success:
        raise RuntimeError(output)
    # Parse PID from output if available
    pid = None
    try:
        import json
        data = json.loads(output) if output.strip().startswith("{") else None
        if data and isinstance(data, dict):
            pid = data.get("Id")
    except Exception:
        pass
    return {"app": name, "method": "powershell", "pid": pid, "exe_path": None}


async def _launch_exe_retry(params: dict) -> Any:
    """Strategy 6: Try with .exe extension."""
    name = params["app_name"]
    if name.endswith(".exe"):
        raise RuntimeError("Already tried .exe")
    try:
        os.startfile(name + ".exe")
        await asyncio.sleep(0.5)
        pid = _find_pid_by_name(name)
        return {"app": name, "method": "exe_retry", "pid": pid, "exe_path": None}
    except Exception as e:
        raise RuntimeError(f"exe_retry failed: {e}")


async def _launch_start_menu(params: dict) -> Any:
    """Strategy 7: Search Start Menu shortcuts."""
    name = params["app_name"].lower().strip()
    start_menu_dirs = []
    appdata = os.environ.get("APPDATA", "")
    programdata = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    for d in [
        Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]:
        if d.exists():
            start_menu_dirs.append(d)

    count = 0
    for start_menu in start_menu_dirs:
        for shortcut in start_menu.rglob("*.lnk"):
            count += 1
            if count > 500:
                break
            if name in shortcut.stem.lower():
                ps_script = (
                    f"$shell = New-Object -ComObject WScript.Shell; "
                    f"$sc = $shell.CreateShortcut('{shortcut}'); "
                    f"$proc = Start-Process $sc.TargetPath -PassThru; "
                    f"$proc.Id"
                )
                success, output = await run_ps(ps_script)
                pid = int(output.strip()) if success and output.strip().isdigit() else None
                return {"app": name, "method": "start_menu", "shortcut": str(shortcut), "pid": pid, "exe_path": None}

    raise RuntimeError("No matching shortcuts found in Start Menu")


async def _launch_everything_search(params: dict) -> Any:
    """Strategy 1: Find app via Everything by voidtools.

    Searches the entire NTFS filesystem in < 1ms for executables
    matching the app name. Only fires if Everything is installed.
    If Everything's IPC is unavailable (DB not loaded), returns quickly.

    Quick-check: Skips Everything for known UWP/Store apps (WhatsApp,
    Calculator, Store, etc.) that must be launched via shell_uri.
    """
    if not is_everything_available():
        raise RuntimeError("Everything not installed")
    name = params["app_name"].lower().strip()
    # Skip Everything for known UWP/Store apps — they need shell_uri
    if name in SHELL_URIS:
        raise RuntimeError(f"UWP app '{name}' — use shell_uri method")
    try:
        results = await everything_find_app(name, max_results=5)
    except Exception as e:
        logger.warning("Everything search failed for '%s': %s", name, e)
        raise RuntimeError(f"Everything search error: {e}")
    if not results:
        raise RuntimeError(f"Everything found no executables for '{name}'")
    # Launch the first (best) result
    exe_path = results[0]
    if os.path.isfile(exe_path):
        proc = subprocess.Popen([exe_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.sleep(0.3)
        return {"app": name, "method": "everything_search", "path": exe_path, "pid": proc.pid, "exe_path": exe_path}
    raise RuntimeError(f"Everything result not a file: {exe_path}")


async def _launch_registry_search(params: dict) -> Any:
    """Strategy 8b: Search Windows registry for app install location.

    Reads the Uninstall registry keys to find apps by display name.
    Works for apps installed via MSI, winget, or manual installer.
    """
    import winreg
    name = params["app_name"].lower().strip()
    uninstall_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, path in uninstall_paths:
        try:
            key = winreg.OpenKey(hive, path)
        except OSError:
            continue
        try:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                except OSError:
                    break
                try:
                    display_name = winreg.QueryValueEx(subkey, "DisplayName")[0].lower()
                    if name in display_name or display_name.startswith(name):
                        # Try DisplayIcon first (fastest — direct exe path)
                        try:
                            icon_path = winreg.QueryValueEx(subkey, "DisplayIcon")[0]
                            if icon_path.lower().endswith(".exe") and os.path.isfile(icon_path):
                                proc = subprocess.Popen([icon_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                await asyncio.sleep(0.3)
                                return {"app": name, "method": "registry_search", "path": icon_path, "display_name": display_name, "pid": proc.pid, "exe_path": icon_path}
                        except (FileNotFoundError, OSError):
                            pass
                        install_loc = None
                        try:
                            install_loc = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                        except FileNotFoundError:
                            pass
                        if install_loc and os.path.isdir(install_loc):
                            # Search for .exe files matching the app name
                            for exe in Path(install_loc).rglob("*.exe"):
                                if name in exe.stem.lower():
                                    proc = subprocess.Popen([str(exe)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                    await asyncio.sleep(0.3)
                                    return {"app": name, "method": "registry_search", "path": str(exe), "display_name": display_name, "pid": proc.pid, "exe_path": str(exe)}
                            # Try any .exe in the directory (first match)
                            for exe in Path(install_loc).glob("*.exe"):
                                proc = subprocess.Popen([str(exe)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                await asyncio.sleep(0.3)
                                return {"app": name, "method": "registry_search", "path": str(exe), "display_name": display_name, "pid": proc.pid, "exe_path": str(exe)}
                except FileNotFoundError:
                    pass
                finally:
                    try:
                        winreg.CloseKey(subkey)
                    except OSError:
                        pass
                i += 1
        finally:
            try:
                winreg.CloseKey(key)
            except OSError:
                pass
    raise RuntimeError(f"App '{name}' not found in registry")


async def _launch_install_dirs(params: dict) -> Any:
    """Strategy 9: Search common install directories."""
    name = params["app_name"].lower().strip()
    for env_var in ["PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"]:
        base = os.environ.get(env_var, "")
        if not base:
            continue
        search_dir = Path(base)
        if not search_dir.exists():
            continue
        for item in search_dir.iterdir():
            if item.is_dir() and name in item.name.lower():
                for exe in item.rglob("*.exe"):
                    if name in exe.stem.lower() or item.name.lower() in exe.stem.lower():
                        proc = subprocess.Popen([str(exe)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        await asyncio.sleep(0.3)
                        return {"app": name, "method": "install_dirs", "path": str(exe), "pid": proc.pid, "exe_path": str(exe)}

    raise RuntimeError(f"Could not find '{name}' in install directories")


# ══════════════════════════════════════════════════════════════════════════════
# CLOSE APP
# ══════════════════════════════════════════════════════════════════════════════

# System processes that should never be force-closed by the user.
# Protects against accidental "close pc" / "close file explorer" commands.
_SYSTEM_PROTECTED_PROCESSES = {"explorer", "svchost", "csrss", "wininit", "smss", "lsass", "services", "pc"}


async def _close_graceful(params: dict) -> Any:
    """Close app gracefully via terminate() (sends WM_CLOSE)."""
    import psutil
    name = params["app_name"].lower().strip()
    if name in _SYSTEM_PROTECTED_PROCESSES:
        raise RuntimeError(f"'{name}' is a system process and cannot be closed")
    
    # Try to get exact exe name from known apps
    exact_name = None
    known = KNOWN_APPS.get(name)
    if known:
        paths = known if isinstance(known, list) else [known]
        for raw in paths:
            resolved = os.path.expandvars(raw)
            if os.path.isfile(resolved):
                exact_name = os.path.basename(resolved).lower()
                break
    
    closed = 0
    killed_pids = []
    for p in psutil.process_iter(["pid", "name", "exe"]):
        try:
            p_name = p.info["name"].lower() if p.info["name"] else ""
            p_exe = p.info["exe"].lower() if p.info["exe"] else ""
            
            # Match: exact name, or exact exe basename, or if we have exact_name from known apps
            matched = False
            if exact_name:
                matched = (p_name == exact_name) or (os.path.basename(p_exe) == exact_name)
            else:
                # Fallback: exact name match or exe basename match
                matched = (p_name == name) or (p_exe and os.path.basename(p_exe) == name)
            
            if matched:
                p.terminate()
                closed += 1
                killed_pids.append(p.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception:
            pass
    
    if closed:
        return {"closed": closed, "pids": killed_pids, "exe_name": exact_name or name}
    raise RuntimeError(f"No running process matching '{name}'")


async def _close_taskkill(params: dict) -> Any:
    """Close app via taskkill (graceful — sends WM_CLOSE)."""
    name = params["app_name"]
    if name.lower().strip() in _SYSTEM_PROTECTED_PROCESSES:
        raise RuntimeError(f"'{name}' is a system process and cannot be closed")
    # Known UWP/Store apps don't run as <name>.exe — skip straight to the UWP
    # handler instead of failing taskkill on a non-existent image name.
    if name.lower().strip() in _UWP_APP_PACKAGES:
        raise RuntimeError(f"'{name}' is a UWP app — use uwp close method")
    # Don't append .exe if the name already ends with it
    exe_name = name if name.lower().endswith(".exe") else f"{name}.exe"
    success, output = await run_cmd(["taskkill", "/IM", exe_name])
    # taskkill returns 0 on success, non-zero on failure
    if not success:
        raise RuntimeError(f"taskkill failed for '{exe_name}': {output[:200]}")
    # Get PIDs that were killed by parsing output
    killed_pids = []
    for line in output.splitlines():
        if "PID" in line and ":" in line:
            try:
                pid = int(line.split(":")[-1].strip())
                killed_pids.append(pid)
            except ValueError:
                pass
    return {"closed": True, "method": "taskkill", "pids": killed_pids, "exe_name": exe_name}


async def _close_force(params: dict) -> Any:
    """Force close via taskkill /F."""
    name = params["app_name"]
    if name.lower().strip() in _SYSTEM_PROTECTED_PROCESSES:
        raise RuntimeError(f"'{name}' is a system process and cannot be closed")
    # UWP apps handled by _close_uwp_app; taskkill /F on <name>.exe won't match.
    if name.lower().strip() in _UWP_APP_PACKAGES:
        raise RuntimeError(f"'{name}' is a UWP app — use uwp close method")
    # Don't append .exe if the name already ends with it
    exe_name = name if name.lower().endswith(".exe") else f"{name}.exe"
    success, output = await run_cmd(["taskkill", "/F", "/IM", exe_name])
    # taskkill /F returns 0 on success, non-zero when process not found
    if not success:
        raise RuntimeError(f"taskkill /F failed for '{exe_name}': {output[:200]}")
    killed_pids = []
    for line in output.splitlines():
        if "PID" in line and ":" in line:
            try:
                pid = int(line.split(":")[-1].strip())
                killed_pids.append(pid)
            except ValueError:
                pass
    return {"closed": True, "method": "taskkill_force", "pids": killed_pids, "exe_name": exe_name}


# Maps friendly app names to UWP package names for closing
_UWP_APP_PACKAGES: dict[str, str] = {
    "microsoft store": "*WindowsStore*",
    "store": "*WindowsStore*",
    "windows store": "*WindowsStore*",
    "app store": "*WindowsStore*",
    "photos": "*Photos*",
    "calculator": "*Calculator*",
    "maps": "*Maps*",
    "mail": "*WindowsCommunications*",
    "calendar": "*WindowsCommunications*",
    "weather": "*Weather*",
    "alarms": "*WindowsAlarms*",
    "camera": "*WindowsCamera*",
    "notepad": "*WindowsNotepad*",
    "paint": "*Paint*",
    "terminal": "*WindowsTerminal*",
    "settings": "*ImmersiveControlPanel*",
    "xbox": "*Xbox*",
    "alarms & clock": "*WindowsAlarms*",
    "whatsapp": "*WhatsApp*",
    "lenovo vantage": "*LenovoCompanion*",
    "pc manager": "*MicrosoftPCManager*",
    "neverness to everness": "*neverness*",
}


async def _close_uwp_app(params: dict) -> Any:
    """Close UWP/Store apps via PowerShell Stop-Process or window close."""
    name = params["app_name"].lower().strip()
    package = _UWP_APP_PACKAGES.get(name)
    if not package:
        # Try partial match
        for key, val in _UWP_APP_PACKAGES.items():
            if key in name or name in key:
                package = val
                break
    if not package:
        raise RuntimeError(f"No UWP package mapping for '{name}'")
    # Try Stop-Process first and get PIDs
    success, output = await run_ps(
        f"$procs = Get-Process {package} -ErrorAction SilentlyContinue; "
        f"$procs | ForEach-Object {{ $_.Id }}; "
        f"$procs | Stop-Process -Force -ErrorAction SilentlyContinue"
    )
    killed_pids = []
    if success and output:
        for line in output.splitlines():
            line = line.strip()
            if line.isdigit():
                killed_pids.append(int(line))
    # If no process found, try closing the window via its title
    if not killed_pids:
        title_pattern = name.title()
        await run_ps(
            f"Get-Process | Where-Object {{$_.MainWindowTitle -like '*{title_pattern}*'}} | "
            f"ForEach-Object {{ $_.CloseMainWindow() | Out-Null }}"
        )
    return {"closed": True, "method": "uwp", "pids": killed_pids, "exe_name": package}


# ══════════════════════════════════════════════════════════════════════════════
# LAUNCH WITH ARGS
# ══════════════════════════════════════════════════════════════════════════════

async def _launch_with_args(params: dict) -> Any:
    """Launch an app with arguments."""
    name = params["app_name"]
    args = params.get("args", "")
    # Try known registry first
    entry = KNOWN_APPS.get(name.lower().strip())
    if entry:
        paths = entry if isinstance(entry, list) else [entry]
        for raw in paths:
            resolved = os.path.expandvars(raw)
            if os.path.isfile(resolved):
                cmd = [resolved] + (args.split() if args else [])
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return {"app": name, "args": args}
    # Fallback: Start-Process
    safe = name.replace("'", "")
    ps = f"Start-Process '{safe}'"
    if args:
        ps += f" -ArgumentList '{args}'"
    success, output = await run_ps(ps)
    return {"app": name, "args": args}


# ══════════════════════════════════════════════════════════════════════════════
# LAUNCH AS ADMIN
# ══════════════════════════════════════════════════════════════════════════════

async def _launch_as_admin(params: dict) -> Any:
    """Launch app with elevated (admin) privileges."""
    name = params["app_name"]
    entry = KNOWN_APPS.get(name.lower().strip())
    exe = None
    if entry:
        paths = entry if isinstance(entry, list) else [entry]
        for raw in paths:
            resolved = os.path.expandvars(raw)
            if os.path.isfile(resolved):
                exe = resolved
                break
    if not exe:
        exe = name
    # Use PowerShell Start-Process -Verb RunAs
    safe = exe.replace("'", "")
    success, output = await run_ps(f"Start-Process '{safe}' -Verb RunAs -ErrorAction Stop")
    if not success:
        raise RuntimeError(output)
    return {"app": name, "elevated": True}


# ══════════════════════════════════════════════════════════════════════════════
# RESTART APP
# ══════════════════════════════════════════════════════════════════════════════

async def _restart_app(params: dict) -> Any:
    """Restart an application (close then re-launch)."""
    import asyncio as _aio
    import psutil
    name = params["app_name"].lower().strip()
    # Close
    closed = 0
    for p in psutil.process_iter(["name"]):
        if name in p.info["name"].lower():
            try:
                p.kill()
                closed += 1
            except Exception:
                pass
    # Wait briefly (async — don't block the event loop)
    await _aio.sleep(0.5)
    # Re-launch
    result = await _launch_known_registry(params)
    return {"app": name, "closed": closed, "relaunched": True}


# ══════════════════════════════════════════════════════════════════════════════
# IS APP RUNNING
# ══════════════════════════════════════════════════════════════════════════════

async def _is_app_running(params: dict) -> Any:
    """Check if an application is currently running."""
    import psutil
    name = params["app_name"].lower().strip()
    found = []
    for p in psutil.process_iter(["pid", "name"]):
        if name in p.info["name"].lower():
            found.append({"pid": p.info["pid"], "name": p.info["name"]})
    return {"running": len(found) > 0, "instances": found}


# ══════════════════════════════════════════════════════════════════════════════
# INSTALL / UNINSTALL APP (winget)
# ══════════════════════════════════════════════════════════════════════════════

async def _install_app(params: dict) -> Any:
    """Install an app via winget."""
    package = params["package"]
    success, output = await run_cmd(
        ["winget", "install", package, "--accept-package-agreements", "--accept-source-agreements"],
        timeout=120,
    )
    if not success:
        raise RuntimeError(output)
    return {"installed": package}


async def _uninstall_app(params: dict) -> Any:
    """Uninstall an app via winget."""
    package = params["package"]
    success, output = await run_cmd(
        ["winget", "uninstall", package, "--accept-source-agreements"],
        timeout=120,
    )
    if not success:
        raise RuntimeError(output)
    return {"uninstalled": package}


# ══════════════════════════════════════════════════════════════════════════════
# AUTOMATE APP (pywinauto)
# ══════════════════════════════════════════════════════════════════════════════

async def _automate_app(params: dict) -> Any:
    """Automate an app via pywinauto (click, type, etc.)."""
    from pywinauto import Application
    title = params.get("title", "")
    action = params.get("action", "connect")  # connect, click, type, close
    text = params.get("text", "")
    control = params.get("control", "")
    
    if action == "connect":
        app = Application(backend="uia").connect(title_re=f".*{title}.*")
        win = app.window(title_re=f".*{title}.*")
        return {"connected": title, "class": str(win.class_name())}
    elif action == "click":
        app = Application(backend="uia").connect(title_re=f".*{title}.*")
        win = app.window(title_re=f".*{title}.*")
        win.child_window(title=control).click()
        return {"clicked": control}
    elif action == "type":
        app = Application(backend="uia").connect(title_re=f".*{title}.*")
        win = app.window(title_re=f".*{title}.*")
        if control:
            win.child_window(title=control).type_keys(text, with_spaces=True)
        else:
            win.type_keys(text, with_spaces=True)
        return {"typed": text}
    elif action == "close":
        app = Application(backend="uia").connect(title_re=f".*{title}.*")
        win = app.window(title_re=f".*{title}.*")
        win.close()
        return {"closed": title}
    raise RuntimeError(f"Unknown automate action: {action}")


# ══════════════════════════════════════════════════════════════════════════════
# COM DISPATCH
# ══════════════════════════════════════════════════════════════════════════════

async def _com_dispatch(params: dict) -> Any:
    """Create a COM dispatch object (for Office, IE, Explorer, etc.)."""
    prog_id = params["prog_id"]  # e.g. "Word.Application", "Excel.Application"
    method = params.get("method", "open")
    target = params.get("target", "")
    
    import win32com.client
    obj = win32com.client.Dispatch(prog_id)
    
    if method == "open" and target:
        if hasattr(obj, "Documents"):
            obj.Documents.Open(target)
        elif hasattr(obj, "Workbooks"):
            obj.Workbooks.Open(target)
    elif method == "visible":
        obj.Visible = True
    elif method == "quit":
        if hasattr(obj, "Quit"):
            obj.Quit()
    
    return {"prog_id": prog_id, "method": method}


# ══════════════════════════════════════════════════════════════════════════════
# PIN TO TASKBAR / START
# ══════════════════════════════════════════════════════════════════════════════

async def _pin_to_taskbar(params: dict) -> Any:
    """Pin an app to the taskbar via Shell."""
    name = params["app_name"].lower().strip()
    entry = KNOWN_APPS.get(name)
    exe_path = None
    if entry:
        paths = entry if isinstance(entry, list) else [entry]
        for raw in paths:
            resolved = os.path.expandvars(raw)
            if os.path.isfile(resolved):
                exe_path = resolved
                break
    if not exe_path:
        raise RuntimeError(f"Could not find executable for '{name}'")
    # Use Shell COM to pin
    ps = f"(New-Object -ComObject Shell.Application).NameSpace(1).InvokeVerb('pintotaskbar')"
    success, output = await run_ps(ps)
    return {"pinned": name, "path": exe_path}


async def _pin_to_start(params: dict) -> Any:
    """Pin an app to Start Menu via PowerShell."""
    name = params["app_name"]
    ps = f"$shell = New-Object -ComObject Shell.Application; $shell.NameSpace(0).InvokeVerb('pintostartscreen')"
    success, output = await run_ps(ps)
    return {"pinned": name}


# ══════════════════════════════════════════════════════════════════════════════
# SET DEFAULT PROGRAM
# ══════════════════════════════════════════════════════════════════════════════

async def _set_default_program(params: dict) -> Any:
    """Set a program as default for a file extension."""
    extension = params["extension"]  # e.g. ".txt"
    app_name = params["app_name"]
    # Use assoc command
    success, output = await run_cmd(["cmd", "/c", "assoc", f"{extension}={app_name}"])
    return {"extension": extension, "default": app_name}


# ══════════════════════════════════════════════════════════════════════════════
# FIND APP BY NAME
# ══════════════════════════════════════════════════════════════════════════════

async def _find_app_by_name(params: dict) -> Any:
    """Search for an installed app by name.

    Uses the local uninstall registry first (instant, no network), then falls
    back to ``winget list`` if nothing matches. This avoids the hard timeouts
    that occur when winget is slow to cold-start or has no network access.
    """
    import winreg

    query = params.get("name", "").strip().lower()
    if not query:
        raise RuntimeError("No search query provided (use 'name')")

    uninstall_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    matches = []
    for hive, path in uninstall_paths:
        try:
            key = winreg.OpenKey(hive, path)
        except OSError:
            continue
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, i)
            except OSError:
                break
            i += 1
            try:
                subkey = winreg.OpenKey(key, subkey_name)
            except OSError:
                continue
            try:
                try:
                    display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                except FileNotFoundError:
                    continue
                if query in display_name.lower():
                    install_loc = None
                    try:
                        install_loc = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                    except FileNotFoundError:
                        pass
                    matches.append({
                        "name": display_name,
                        "install_location": install_loc,
                        "source": "registry",
                    })
            finally:
                winreg.CloseKey(subkey)
        winreg.CloseKey(key)

    if matches:
        return {"results": matches[:20], "count": len(matches)}

    # Fallback: winget (slower, may require network)
    try:
        success, output = await run_cmd(
            ["winget", "list", "--name", params.get("name", "")], timeout=10
        )
        if success:
            return {"results": output[:3000], "source": "winget"}
    except asyncio.TimeoutError:
        pass
    raise RuntimeError(f"No app found matching '{params.get('name', '')}'")


# ══════════════════════════════════════════════════════════════════════════════
# GET APP PATH
# ══════════════════════════════════════════════════════════════════════════════

async def _get_app_path_action(params: dict) -> Any:
    """Get the installation path of an app from registry."""
    import winreg
    name = params["app_name"].lower().strip()
    uninstall_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, path in uninstall_paths:
        try:
            key = winreg.OpenKey(hive, path)
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    try:
                        display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        if name in display_name.lower():
                            install_loc = None
                            try:
                                install_loc = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                            except FileNotFoundError:
                                pass
                            display_ver = None
                            try:
                                display_ver = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                            except FileNotFoundError:
                                pass
                            winreg.CloseKey(subkey)
                            winreg.CloseKey(key)
                            return {"name": display_name, "install_location": install_loc, "version": display_ver}
                    except FileNotFoundError:
                        pass
                    winreg.CloseKey(subkey)
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except OSError:
            continue
    # Also check App Paths
    try:
        app_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}.exe")
        path_val = winreg.QueryValueEx(app_key, "")[0]
        winreg.CloseKey(app_key)
        return {"name": name, "executable": path_val}
    except OSError:
        pass
    return {"error": f"App '{name}' not found in registry"}


# ══════════════════════════════════════════════════════════════════════════════
# GET APP VERSION
# ══════════════════════════════════════════════════════════════════════════════

async def _get_app_version_action(params: dict) -> Any:
    """Get version of an installed app from registry."""
    import winreg
    name = params["app_name"].lower().strip()
    uninstall_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, path in uninstall_paths:
        try:
            key = winreg.OpenKey(hive, path)
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    try:
                        display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        if name in display_name.lower():
                            version = None
                            try:
                                version = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                            except FileNotFoundError:
                                pass
                            winreg.CloseKey(subkey)
                            winreg.CloseKey(key)
                            return {"name": display_name, "version": version}
                    except FileNotFoundError:
                        pass
                    winreg.CloseKey(subkey)
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except OSError:
            continue
    return {"error": f"App '{name}' not found"}


# ══════════════════════════════════════════════════════════════════════════════
# GET APP ICON
# ══════════════════════════════════════════════════════════════════════════════

async def _get_app_icon_action(params: dict) -> Any:
    """Extract an app's icon to a file."""
    import ctypes
    import ctypes.wintypes as wt
    path = params["path"]  # Path to .exe or .ico
    output = params.get("output", path + ".ico")
    # Extract icon using Shell32
    large_icon = wt.HICON()
    small_icon = wt.HICON()
    ctypes.windll.shell32.ExtractIconExW(path, 0, ctypes.byref(large_icon), ctypes.byref(small_icon), 1)
    try:
        # Save to file using PowerShell
        success, ps_out = await run_ps(
            f'Add-Type -AssemblyName System.Drawing; '
            f'$icon = [System.Drawing.Icon]::ExtractAssociatedIcon("{path}"); '
            f'$bitmap = $icon.ToBitmap(); '
            f'$bitmap.Save("{output}"); '
            f'"Saved to {output}"'
        )
        return {"icon": output}
    finally:
        # Free icon handles to prevent resource leak
        try:
            if large_icon.value:
                ctypes.windll.user32.DestroyIcon(large_icon)
            if small_icon.value:
                ctypes.windll.user32.DestroyIcon(small_icon)
        except Exception:
            pass
    return {"error": "Could not extract icon"}


# ══════════════════════════════════════════════════════════════════════════════
# UNPIN FROM TASKBAR / START
# ══════════════════════════════════════════════════════════════════════════════

async def _unpin_from_taskbar_action(params: dict) -> Any:
    """Unpin an app from the taskbar."""
    app_name = params["app_name"]
    ps = ("$shell = New-Object -ComObject Shell.Application; "
          f"$shell.Namespace(1).Items() | Where-Object {{$_.Name -like '*{app_name}*'}} | "
          "ForEach-Object { $_.InvokeVerb('unpinfromtaskbar') }")
    success, output = await run_ps(ps)
    return {"unpinned": app_name}


async def _unpin_from_start_action(params: dict) -> Any:
    """Unpin an app from the Start menu."""
    app_name = params["app_name"]
    ps = ("$shell = New-Object -ComObject Shell.Application; "
          f"$shell.Namespace(0).Items() | Where-Object {{$_.Name -like '*{app_name}*'}} | "
          "ForEach-Object { $_.InvokeVerb('unpinfromstart') }")
    success, output = await run_ps(ps)
    return {"unpinned": app_name}


# ══════════════════════════════════════════════════════════════════════════════
# LIST INSTALLED APPS
# ══════════════════════════════════════════════════════════════════════════════

async def _list_winget(params: dict) -> Any:
    """List installed apps via winget."""
    success, output = await run_cmd(["winget", "list"], timeout=30)
    if success:
        return {"apps": output[:5000]}
    raise RuntimeError(output)


async def _list_registry(params: dict) -> Any:
    """List installed apps via registry."""
    import winreg
    apps = []
    paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, path in paths:
        try:
            key = winreg.OpenKey(hive, path)
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    try:
                        name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        apps.append({"name": name})
                    except FileNotFoundError:
                        pass
                    winreg.CloseKey(subkey)
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except OSError:
            continue
    return {"apps": apps[:200], "count": len(apps)}


# ══════════════════════════════════════════════════════════════════════════════
# OPEN FILE WITH (specific app)
# ══════════════════════════════════════════════════════════════════════════════

async def _open_file_with_powershell(params: dict) -> Any:
    """Method 1: Open file with app via PowerShell Start-Process."""
    path = params.get("path", "")
    app = params.get("app", "")
    if app:
        success, output = await run_ps(f"Start-Process '{app}' '{path}'")
        if not success:
            raise RuntimeError(output)
        return {"opened": path, "with": app}
    raise RuntimeError("No app specified")


async def _open_file_with_startfile(params: dict) -> Any:
    """Method 2: Open file via os.startfile (uses Windows default)."""
    path = params.get("path", "")
    app = params.get("app", "")
    if app:
        import subprocess as _subprocess
        _subprocess.Popen([app, path], stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL)
        return {"opened": path, "with": app}
    os.startfile(path)
    return {"opened": path, "with": "default"}


# ══════════════════════════════════════════════════════════════════════════════
# OPEN SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

async def _open_settings_shell(params: dict) -> Any:
    """Method 1: Open Windows Settings via shell URI."""
    page = params.get("page", "")
    settings_map = {
        "display": "ms-settings:display", "sound": "ms-settings:sound",
        "network": "ms-settings:network", "bluetooth": "ms-settings:bluetooth",
        "privacy": "ms-settings:privacy", "update": "ms-settings:windowsupdate",
    }
    uri = settings_map.get(page.lower().strip(), "ms-settings:") if page else "ms-settings:"
    os.startfile(uri)
    return {"opened": page or "General"}


async def _open_settings_powershell(params: dict) -> Any:
    """Method 2: Open Windows Settings via PowerShell."""
    page = params.get("page", "")
    settings_map = {
        "display": "ms-settings:display", "sound": "ms-settings:sound",
        "network": "ms-settings:network", "bluetooth": "ms-settings:bluetooth",
        "privacy": "ms-settings:privacy", "update": "ms-settings:windowsupdate",
    }
    uri = settings_map.get(page.lower().strip(), "ms-settings:") if page else "ms-settings:"
    success, output = await run_ps(f"Start-Process '{uri}'")
    if not success:
        raise RuntimeError(output)
    return {"opened": page or "General"}


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH PACKAGES (winget search — searches available packages, not installed)
# ══════════════════════════════════════════════════════════════════════════════

async def _search_packages_winget(params: dict) -> Any:
    """Method 1: Search available packages via winget search."""
    query = params.get("query", "")
    if not query:
        raise RuntimeError("No query provided")
    success, output = await run_cmd(
        ["winget", "search", query],
        timeout=30,
    )
    if success:
        return {"results": output[:5000], "query": query}
    raise RuntimeError(output)


async def _search_packages_powershell(params: dict) -> Any:
    """Method 2: Search packages via PowerShell winget invocation."""
    query = params.get("query", "")
    if not query:
        raise RuntimeError("No query provided")
    success, output = await run_ps(f"winget search '{query}'")
    if success and output:
        return {"results": output[:5000], "query": query}
    raise RuntimeError(output or "winget search failed")


# ══════════════════════════════════════════════════════════════════════════════
# ACTION HANDLER
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

LAUNCH_METHODS = [
    _launch_everything_search, _launch_shell_uri, _launch_known_registry,
    _launch_dynamic_registry,  # OS queries: where.exe + App Paths + Start Menu
    _launch_fuzzy,
    _launch_startfile, _launch_powershell, _launch_exe_retry,
    _launch_start_menu, _launch_registry_search, _launch_install_dirs,
]

ACTION_MAP: dict[str, tuple[list, Any]] = {
    "launch_app":         (LAUNCH_METHODS, Verifiers.process_launched),
    "launch_with_args":   ([_launch_with_args], Verifiers.process_launched),
    "launch_as_admin":    ([_launch_as_admin], Verifiers.process_launched),
    "close_app":          ([_close_graceful, _close_taskkill, _close_uwp_app, _close_force], Verifiers.process_killed),
    "restart_app":        ([_restart_app], Verifiers.process_launched),
    "is_app_running":     ([_is_app_running], None),
    "install_app":        ([_install_app], None),
    "uninstall_app":      ([_uninstall_app], None),
    "automate_app":       ([_automate_app], None),
    "com_dispatch":       ([_com_dispatch], None),
    "pin_to_taskbar":     ([_pin_to_taskbar], None),
    "pin_to_start":       ([_pin_to_start], None),
    "set_default_program": ([_set_default_program], None),
    "find_app_by_name":   ([_find_app_by_name], None),
    "list_installed_apps": ([_list_winget, _list_registry], None),
    # --- Phase 7 additions ---
    "get_app_path":      ([_get_app_path_action], None),
    "get_app_version":   ([_get_app_version_action], None),
    "force_close_app":   ([_close_force], Verifiers.process_killed),
    "get_app_icon":      ([_get_app_icon_action], None),
    "unpin_from_taskbar": ([_unpin_from_taskbar_action], None),
    "unpin_from_start":   ([_unpin_from_start_action], None),
    # --- open_file_with ---
    "open_file_with":   ([_open_file_with_powershell, _open_file_with_startfile], None),
    # --- open_settings ---
    "open_settings":    ([_open_settings_shell, _open_settings_powershell], None),
    # --- search_packages (winget search for available packages) ---
    "search_packages":  ([_search_packages_winget, _search_packages_powershell], None),
}


async def handler(action: str, params: dict[str, Any]) -> Result:
    """L3 Application layer handler."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown application action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    # Duplicate launch prevention for launch_app actions
    if action in ("launch_app", "launch_with_args", "launch_as_admin"):
        app_name = params.get("app_name", "").lower().strip()
        if app_name and _is_already_launched(app_name):
            return Result(
                command_id=params.get("id", ""),
                success=True,
                data={"app": app_name, "method": "skipped_duplicate", "message": "Already launched recently"},
                method_used="duplicate_guard",
            )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"application.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("application", action),
        escalation_fn=create_escalation_fn("application", action),
        method_timeout=8.0,
    )

    # Record successful launch
    if success and action in ("launch_app", "launch_with_args", "launch_as_admin"):
        app_name = params.get("app_name", "").lower().strip()
        if app_name:
            _record_launch(app_name)

    suggested = None
    if not success and error:
        suggested = f"Try running as Administrator. Error: {error[:120]}"

    return Result(
        command_id=params.get("id", ""),
        success=success,
        data=data,
        error=error if not success else None,
        verified=verifier is not None and success,
        method_used=method_used,
        suggested_action=suggested,
    )
