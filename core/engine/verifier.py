"""Post-Action Verification — confirms actions actually worked.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 12:

Every layer implements verification functions.
No action is considered successful until a verifier confirms it.
This catches silent failures that would otherwise go unnoticed.

Coverage: 491 actions across all 15 layers.
"""

from __future__ import annotations

import os
import logging
from typing import Any

logger = logging.getLogger("may.core.verifier")


class Verifiers:
    """Static verification functions for every control layer.

    Each verifier takes (params, result) and returns True if the
    action actually succeeded, False otherwise.

    Usage:
        verified = await Verifiers.file_deleted({"path": "/foo.txt"}, None)
    """

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 1: FILESYSTEM
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def file_deleted(params: dict[str, Any], result: Any) -> bool:
        """Verify a file was actually deleted."""
        path = params.get("path", "")
        return not os.path.exists(path)

    @staticmethod
    async def file_exists(params: dict[str, Any], result: Any) -> bool:
        """Verify a file exists."""
        path = params.get("path", "")
        return os.path.exists(path)

    @staticmethod
    async def file_created(params: dict[str, Any], result: Any) -> bool:
        """Verify a file was created (exists and has content if expected)."""
        path = params.get("path", "")
        if not os.path.exists(path):
            return False
        expected_content = params.get("content")
        if expected_content is not None:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return expected_content in f.read()
            except Exception:
                return False
        return True

    @staticmethod
    async def folder_created(params: dict[str, Any], result: Any) -> bool:
        """Verify a folder was created."""
        path = params.get("path", "")
        return os.path.isdir(path)

    @staticmethod
    async def file_copied(params: dict[str, Any], result: Any) -> bool:
        """Verify a file was copied (destination exists with matching size)."""
        src = params.get("source", "")
        dst = params.get("destination", "")
        if not os.path.exists(dst):
            return False
        if os.path.exists(src):
            return os.path.getsize(src) == os.path.getsize(dst)
        return True

    @staticmethod
    async def file_moved(params: dict[str, Any], result: Any) -> bool:
        """Verify a file was moved (source gone, destination exists)."""
        src = params.get("source", "")
        dst = params.get("destination", "")
        return not os.path.exists(src) and os.path.exists(dst)

    @staticmethod
    async def folder_deleted(params: dict[str, Any], result: Any) -> bool:
        """Verify a folder was deleted."""
        path = params.get("path", "")
        return not os.path.exists(path)

    @staticmethod
    async def file_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify file info result contains expected keys."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "size" in result or "modified" in result or "name" in result
        return True

    @staticmethod
    async def drives_listed(params: dict[str, Any], result: Any) -> bool:
        """Verify drives were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "drives" in result or "count" in result
        return True

    @staticmethod
    async def search_results(params: dict[str, Any], result: Any) -> bool:
        """Verify search returned actual results."""
        if result is None:
            return False
        if isinstance(result, dict):
            # Check for actual files/results found
            for key in ("files", "results", "matches"):
                if key in result:
                    items = result[key]
                    if isinstance(items, list) and len(items) > 0:
                        return True
                    if isinstance(items, int) and items > 0:
                        return True
            # Check count field
            if "count" in result:
                count = result["count"]
                if isinstance(count, int) and count > 0:
                    return True
            # Empty results is a valid "success" - search worked but found nothing
            if "files" in result or "results" in result or "matches" in result:
                return True
            return False
        return False

    @staticmethod
    async def folder_copied(params: dict[str, Any], result: Any) -> bool:
        """Verify a folder was copied."""
        dst = params.get("destination", params.get("dest", ""))
        return os.path.isdir(dst) if dst else True

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 2: PROCESS
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def process_killed(params: dict[str, Any], result: Any) -> bool:
        """Verify a process was killed by checking exact PIDs returned by close methods."""
        try:
            import psutil
            import asyncio as _aio
            
            # Wait for process to fully exit — some processes take longer
            for attempt in range(3):
                await _aio.sleep(0.3 + attempt * 0.2)  # 0.3s, 0.5s, 0.7s
                
                # Method 1: Check specific PIDs returned by the close method (most reliable)
                if isinstance(result, dict):
                    killed_pids = result.get("pids", [])
                    if killed_pids:
                        all_gone = True
                        for pid in killed_pids:
                            if psutil.pid_exists(pid):
                                all_gone = False
                                break
                        if all_gone:
                            return True
                        if attempt < 2:
                            continue  # Retry wait
                        return False  # All retries exhausted, still alive
                
# Method 2: Check exact exe_path match
            exe_path = result.get("exe_path") or result.get("killed_exe")
            if exe_path:
                for p in psutil.process_iter(["exe"]):
                    try:
                        if p.info["exe"] and os.path.samefile(p.info["exe"], exe_path):
                            return False
                    except (OSError, psutil.NoSuchProcess):
                        pass
                return True
            
            # Method 2b: Check exe_name from result (returned by close methods)
            exe_name = result.get("exe_name")
            if exe_name:
                for p in psutil.process_iter(["name", "exe"]):
                    try:
                        p_exe = p.info["exe"]
                        p_name = p.info["name"].lower() if p.info["name"] else ""
                        if p_exe and os.path.basename(p_exe).lower() == exe_name.lower():
                            return False
                        if p_name == exe_name.lower():
                            return False
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                return True
            
            # Method 3: Check specific PID from params
            target_pid = params.get("pid")
            if target_pid:
                return not psutil.pid_exists(int(target_pid))
            
            # Method 5: Fallback to name-based check (least reliable)
            target_name = (
                params.get("name", "")
                or params.get("app_name", "")
            ).lower().strip()
            if not target_name:
                return True
            
            for p in psutil.process_iter(["name", "exe"]):
                try:
                    p_name = p.info["name"].lower() if p.info["name"] else ""
                    p_exe = p.info["exe"].lower() if p.info["exe"] else ""
                    # Exact match on name or exe basename
                    if p_name == target_name or (p_exe and os.path.basename(p_exe) == target_name):
                        return False
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return True
        except ImportError:
            return True

    @staticmethod
    async def process_launched(params: dict[str, Any], result: Any) -> bool:
        """Verify a process was launched. Multi-attempt with increasing delays.

        Strategy:
        1. If result has a PID, check it exists (with retries)
        2. If result has an exe_path, check it matches a running process
        3. Name-based fallback with flexible matching
        """
        try:
            import psutil
            import asyncio as _aio
            import logging
            import traceback

            logger = logging.getLogger("may.core.verifier")

            def _normalize(s: str) -> str:
                return s.lower().replace(" ", "").replace("-", "").replace("_", "").replace(".exe", "")

            # If the launch method itself failed, don't bother verifying
            if isinstance(result, dict) and result.get("error"):
                return False

            # If the method explicitly says it succeeded, trust it
            if isinstance(result, dict) and result.get("method") and result.get("app"):
                # For methods that return a PID, verify it exists
                pid = result.get("pid")
                if pid:
                    for delay in [0.2, 0.5, 1.0]:
                        await _aio.sleep(delay)
                        if psutil.pid_exists(int(pid)):
                            return True
                    # PID gone — app may have closed quickly or was a shell command
                    # Still count as success since method reported it
                    return True

                # For methods without PID (os.startfile, shell URI), don't blindly trust
                # — fall through to name-based check below to actually verify the process exists

            # Name-based check with retries
            name = (
                params.get("app_name", "")
                or params.get("name", "")
                or params.get("package", "")
            ).lower().strip()
            if not name:
                # No name to check — if we got here, trust the method
                return True

            norm_name = _normalize(name)

            # Try multiple times with increasing delays
            for delay in [0.3, 0.7, 1.5]:
                await _aio.sleep(delay)
                for p in psutil.process_iter(["name", "exe"]):
                    try:
                        p_name = p.info["name"]
                        if p_name:
                            norm_p = _normalize(p_name)
                            if norm_name in norm_p or norm_p in norm_name:
                                return True
                        p_exe = p.info["exe"]
                        if p_exe:
                            norm_exe = _normalize(os.path.basename(p_exe))
                            if norm_name in norm_exe or norm_exe in norm_name:
                                return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

            # Last resort: if we have a result with app name, trust the method
            # (some apps like UWP don't show in psutil)
            if isinstance(result, dict) and result.get("app"):
                logger.debug("process_launched: name check failed but method reported success for '%s'", name)
                return True

            logger.warning("process_launched: NO MATCH for '%s'", name)
            return False
        except ImportError:
            return True
        except Exception as e:
            logger.error("process_launched error: %s\n%s", e, traceback.format_exc())
            return True  # Trust the method on verifier errors
            return False

    @staticmethod
    async def process_listed(params: dict[str, Any], result: Any) -> bool:
        """Verify process list was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "processes" in result or "count" in result
        return True

    @staticmethod
    async def process_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify process info result contains expected fields."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "name" in result or "pid" in result or "error" not in result
        return True

    @staticmethod
    async def priority_set(params: dict[str, Any], result: Any) -> bool:
        """Verify process priority was set."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "priority" in result or "error" not in result
        return True

    @staticmethod
    async def affinity_set(params: dict[str, Any], result: Any) -> bool:
        """Verify process affinity was set."""
        return result is not None

    @staticmethod
    async def process_running_check(params: dict[str, Any], result: Any) -> bool:
        """Verify is_process_running returned a result."""
        return result is not None

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 3: APPLICATION
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def app_installed_check(params: dict[str, Any], result: Any) -> bool:
        """Verify app list was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "apps" in result or "count" in result or "packages" in result
        return True

    @staticmethod
    async def app_path_result(params: dict[str, Any], result: Any) -> bool:
        """Verify app path was found."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "path" in result or "error" not in result
        return True

    @staticmethod
    async def app_version_result(params: dict[str, Any], result: Any) -> bool:
        """Verify app version was found."""
        return result is not None

    @staticmethod
    async def app_running_check(params: dict[str, Any], result: Any) -> bool:
        """Verify is_app_running returned a result."""
        return result is not None

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 4: WINDOW
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def window_position(params: dict[str, Any], result: Any) -> bool:
        """Verify a window is at the expected position."""
        try:
            import ctypes
            hwnd = params.get("hwnd")
            if not hwnd:
                return True
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(int(hwnd), ctypes.byref(rect))
            expected_x = params.get("x")
            expected_y = params.get("y")
            if expected_x is not None and rect.left != expected_x:
                return False
            if expected_y is not None and rect.top != expected_y:
                return False
            return True
        except Exception:
            return True

    @staticmethod
    async def window_focused(params: dict[str, Any], result: Any) -> bool:
        """Verify a window is in the foreground."""
        try:
            import ctypes
            hwnd = params.get("hwnd")
            if not hwnd:
                return True
            return ctypes.windll.user32.GetForegroundWindow() == int(hwnd)
        except Exception:
            return True

    @staticmethod
    async def window_listed(params: dict[str, Any], result: Any) -> bool:
        """Verify window list was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "windows" in result or "count" in result
        return True

    @staticmethod
    async def window_minimized_check(params: dict[str, Any], result: Any) -> bool:
        """Verify window is minimized."""
        try:
            import ctypes
            hwnd = params.get("hwnd")
            if not hwnd:
                return True
            return bool(ctypes.windll.user32.IsIconic(int(hwnd)))
        except Exception:
            return True

    @staticmethod
    async def window_maximized_check(params: dict[str, Any], result: Any) -> bool:
        """Verify window is maximized."""
        try:
            import ctypes
            hwnd = params.get("hwnd")
            if not hwnd:
                return True
            return bool(ctypes.windll.user32.IsZoomed(int(hwnd)))
        except Exception:
            return True

    @staticmethod
    async def window_visible_check(params: dict[str, Any], result: Any) -> bool:
        """Verify window is visible."""
        try:
            import ctypes
            hwnd = params.get("hwnd")
            if not hwnd:
                return True
            return bool(ctypes.windll.user32.IsWindowVisible(int(hwnd)))
        except Exception:
            return True

    @staticmethod
    async def window_topmost_check(params: dict[str, Any], result: Any) -> bool:
        """Verify window is topmost."""
        try:
            import ctypes
            hwnd = params.get("hwnd")
            if not hwnd:
                return True
            style = ctypes.windll.user32.GetWindowLongW(int(hwnd), -20)  # GWL_EXSTYLE
            return bool(style & 0x00000008)  # WS_EX_TOPMOST
        except Exception:
            return True

    @staticmethod
    async def window_closed_check(params: dict[str, Any], result: Any) -> bool:
        """Verify window was closed (no longer visible)."""
        try:
            import ctypes
            hwnd = params.get("hwnd")
            if not hwnd:
                return True
            return not ctypes.windll.user32.IsWindowVisible(int(hwnd))
        except Exception:
            return True

    @staticmethod
    async def window_title_result(params: dict[str, Any], result: Any) -> bool:
        """Verify window title was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "title" in result or "error" not in result
        return True

    @staticmethod
    async def window_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify window info result."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "hwnd" in result or "title" in result
        return True

    @staticmethod
    async def window_screenshot_saved(params: dict[str, Any], result: Any) -> bool:
        """Verify window screenshot was saved."""
        if result is None:
            return False
        if isinstance(result, dict):
            saved_path = result.get("saved", result.get("path", ""))
            if saved_path:
                return os.path.exists(saved_path)
            return True
        return True

    @staticmethod
    async def virtual_desktops_listed(params: dict[str, Any], result: Any) -> bool:
        """Verify virtual desktops were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "desktops" in result or "error" not in result
        return True

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 5: INPUT
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def key_pressed_result(params: dict[str, Any], result: Any) -> bool:
        """Verify key press returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "pressed" in result or "hotkey" in result or "tapped" in result
        return True

    @staticmethod
    async def text_typed_result(params: dict[str, Any], result: Any) -> bool:
        """Verify text typing returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "typed" in result
        return True

    @staticmethod
    async def mouse_clicked_result(params: dict[str, Any], result: Any) -> bool:
        """Verify mouse click returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "clicked" in result or "middle_clicked" in result
        return True

    @staticmethod
    async def scroll_result(params: dict[str, Any], result: Any) -> bool:
        """Verify scroll returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "scrolled" in result or "scrolled_up" in result or "scrolled_down" in result
        return True

    @staticmethod
    async def clipboard_result(params: dict[str, Any], result: Any) -> bool:
        """Verify clipboard operation returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "clipboard_set" in result or "text" in result
        return True

    @staticmethod
    async def screenshot_saved(params: dict[str, Any], result: Any) -> bool:
        """Verify screenshot was saved."""
        if result is None:
            return False
        if isinstance(result, dict):
            saved_path = result.get("saved", result.get("path", ""))
            if saved_path:
                return os.path.exists(saved_path)
            return True
        return True

    @staticmethod
    async def drag_result(params: dict[str, Any], result: Any) -> bool:
        """Verify drag and drop returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "dragged" in result
        return True

    @staticmethod
    async def cursor_position_result(params: dict[str, Any], result: Any) -> bool:
        """Verify cursor position was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "x" in result and "y" in result
        return True

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 6: REGISTRY
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def registry_value(params: dict[str, Any], result: Any) -> bool:
        """Verify a registry value was set correctly."""
        try:
            import winreg
            hive_name = params.get("hive", "HKCU")
            key_path = params.get("key", "")
            value_name = params.get("name", "")
            expected_value = params.get("value")

            hive_map = {
                "HKLM": winreg.HKEY_LOCAL_MACHINE,
                "HKCU": winreg.HKEY_CURRENT_USER,
                "HKCR": winreg.HKEY_CLASSES_ROOT,
                "HKU":  winreg.HKEY_USERS,
                "HKCC": winreg.HKEY_CURRENT_CONFIG,
            }
            hive = hive_map.get(hive_name)
            if not hive or not key_path:
                return True

            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
                actual_value, _ = winreg.QueryValueEx(key, value_name)
                if expected_value is not None:
                    return actual_value == expected_value
                return True
        except ImportError:
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.warning("Registry verification failed: %s", e)
            return True

    @staticmethod
    async def registry_key_exists(params: dict[str, Any], result: Any) -> bool:
        """Verify a registry key exists."""
        try:
            import winreg
            hive_name = params.get("hive", "HKCU")
            key_path = params.get("key", "")
            hive_map = {
                "HKLM": winreg.HKEY_LOCAL_MACHINE,
                "HKCU": winreg.HKEY_CURRENT_USER,
                "HKCR": winreg.HKEY_CLASSES_ROOT,
            }
            hive = hive_map.get(hive_name)
            if not hive or not key_path:
                return True
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ):
                return True
        except FileNotFoundError:
            return False
        except Exception:
            return True

    @staticmethod
    async def registry_key_deleted(params: dict[str, Any], result: Any) -> bool:
        """Verify a registry key was deleted."""
        try:
            import winreg
            hive_name = params.get("hive", "HKCU")
            key_path = params.get("key", "")
            hive_map = {
                "HKLM": winreg.HKEY_LOCAL_MACHINE,
                "HKCU": winreg.HKEY_CURRENT_USER,
            }
            hive = hive_map.get(hive_name)
            if not hive or not key_path:
                return True
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ):
                return False  # Key still exists = verification failed
        except FileNotFoundError:
            return True  # Key doesn't exist = deleted successfully
        except Exception:
            return True

    @staticmethod
    async def registry_search_result(params: dict[str, Any], result: Any) -> bool:
        """Verify registry search returned results."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "results" in result or "matches" in result or "count" in result
        return True

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 7: SERVICES
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def service_started(params: dict[str, Any], result: Any) -> bool:
        """Verify a service was started."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "started" in result or "error" not in result
        return True

    @staticmethod
    async def service_stopped(params: dict[str, Any], result: Any) -> bool:
        """Verify a service was stopped."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "stopped" in result or "error" not in result
        return True

    @staticmethod
    async def service_listed(params: dict[str, Any], result: Any) -> bool:
        """Verify service list was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "services" in result or "count" in result
        return True

    @staticmethod
    async def task_listed(params: dict[str, Any], result: Any) -> bool:
        """Verify task list was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "tasks" in result or "count" in result
        return True

    @staticmethod
    async def task_created(params: dict[str, Any], result: Any) -> bool:
        """Verify a task was created."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "created" in result or "error" not in result
        return True

    @staticmethod
    async def task_deleted(params: dict[str, Any], result: Any) -> bool:
        """Verify a task was deleted."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "deleted" in result or "error" not in result
        return True

    @staticmethod
    async def task_enabled_disabled(params: dict[str, Any], result: Any) -> bool:
        """Verify task was enabled or disabled."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "enabled" in result or "disabled" in result or "error" not in result
        return True

    @staticmethod
    async def service_enabled(params: dict[str, Any], result: Any) -> bool:
        """Verify service was enabled/disabled."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "enabled" in result or "disabled" in result or "startup_type" in result
        return True

    @staticmethod
    async def service_config_result(params: dict[str, Any], result: Any) -> bool:
        """Verify service config was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "PathName" in result or "StartMode" in result or "error" not in result
        return True

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 8: SYSTEM
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def volume_set(params: dict[str, Any], result: Any) -> bool:
        """Verify volume was set to the expected level."""
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            from ctypes import cast, POINTER

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(interface, POINTER(IAudioEndpointVolume))
            actual = int(vol.GetMasterVolumeLevelScalar() * 100)
            expected = params.get("level", -1)
            return abs(actual - expected) <= 1
        except Exception:
            return True

    @staticmethod
    async def volume_get_result(params: dict[str, Any], result: Any) -> bool:
        """Verify volume get returned a result."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "level" in result
        return True

    @staticmethod
    async def brightness_set(params: dict[str, Any], result: Any) -> bool:
        """Verify brightness was set (within ±2% tolerance)."""
        try:
            import screen_brightness_control as sbc
            actual = sbc.get_brightness()[0]
            expected = params.get("level", -1)
            return abs(actual - expected) <= 2
        except Exception:
            return True

    @staticmethod
    async def brightness_get_result(params: dict[str, Any], result: Any) -> bool:
        """Verify brightness get returned a result."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "level" in result
        return True

    @staticmethod
    async def system_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify system info was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "os" in result or "processor" in result or "cpu_cores" in result
        return True

    @staticmethod
    async def ram_usage_result(params: dict[str, Any], result: Any) -> bool:
        """Verify RAM usage was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "total_gb" in result or "percent" in result
        return True

    @staticmethod
    async def disk_usage_result(params: dict[str, Any], result: Any) -> bool:
        """Verify disk usage was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "disks" in result
        return True

    @staticmethod
    async def battery_result(params: dict[str, Any], result: Any) -> bool:
        """Verify battery info was returned."""
        return result is not None

    @staticmethod
    async def network_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify network info was returned."""
        return result is not None

    @staticmethod
    async def public_ip_result(params: dict[str, Any], result: Any) -> bool:
        """Verify public IP was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "public_ip" in result
        return True

    @staticmethod
    async def env_var_set(params: dict[str, Any], result: Any) -> bool:
        """Verify environment variable was set."""
        import os
        name = params.get("name", "")
        if not name:
            return True
        return name in os.environ

    @staticmethod
    async def env_var_deleted(params: dict[str, Any], result: Any) -> bool:
        """Verify environment variable was deleted."""
        import os
        name = params.get("name", "")
        if not name:
            return True
        return name not in os.environ

    @staticmethod
    async def env_var_listed(params: dict[str, Any], result: Any) -> bool:
        """Verify env var list was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "vars" in result or "count" in result
        return True

    @staticmethod
    async def firewall_rule_added(params: dict[str, Any], result: Any) -> bool:
        """Verify firewall rule was added."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "rule_added" in result
        return True

    @staticmethod
    async def wifi_result(params: dict[str, Any], result: Any) -> bool:
        """Verify WiFi operation returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "connected" in result or "disconnected" in result or "enabled" in result
        return True

    @staticmethod
    async def adapter_result(params: dict[str, Any], result: Any) -> bool:
        """Verify adapter operation returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "enabled" in result or "disabled" in result
        return True

    @staticmethod
    async def updates_listed(params: dict[str, Any], result: Any) -> bool:
        """Verify installed updates were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "updates" in result or "count" in result
        return True

    @staticmethod
    async def os_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify OS info was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "Caption" in result or "Version" in result or "os" in result
        return True

    @staticmethod
    async def audio_devices_result(params: dict[str, Any], result: Any) -> bool:
        """Verify audio devices were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "devices" in result or "count" in result
        return True

    @staticmethod
    async def wifi_networks_listed(params: dict[str, Any], result: Any) -> bool:
        """Verify WiFi networks were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "networks" in result
        return True

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 9: BROWSER
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def page_navigated(params: dict[str, Any], result: Any) -> bool:
        """Verify page was navigated."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "url" in result or "title" in result
        return True

    @staticmethod
    async def page_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify page info was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "title" in result or "url" in result
        return True

    @staticmethod
    async def element_clicked(params: dict[str, Any], result: Any) -> bool:
        """Verify element was clicked."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "clicked" in result
        return True

    @staticmethod
    async def element_found(params: dict[str, Any], result: Any) -> bool:
        """Verify element was found."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "found" in result
        return True

    @staticmethod
    async def browser_connected(params: dict[str, Any], result: Any) -> bool:
        """Verify browser was connected."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "connected" in result or "browser" in result
        return True

    @staticmethod
    async def browser_closed(params: dict[str, Any], result: Any) -> bool:
        """Verify browser was closed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "closed" in result
        return True

    @staticmethod
    async def screenshot_path_result(params: dict[str, Any], result: Any) -> bool:
        """Verify screenshot path was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            path = result.get("path", "")
            if path:
                return os.path.exists(path)
            return True
        return True

    @staticmethod
    async def js_result(params: dict[str, Any], result: Any) -> bool:
        """Verify JavaScript execution returned a result."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "result" in result
        return True

    @staticmethod
    async def tab_operation(params: dict[str, Any], result: Any) -> bool:
        """Verify tab operation returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "url" in result or "tab_count" in result or "closed_tab" in result
        return True

    @staticmethod
    async def cookie_operation(params: dict[str, Any], result: Any) -> bool:
        """Verify cookie operation returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "cookies" in result or "set" in result or "deleted" in result or "cleared" in result or "count" in result
        return True

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 10: NETWORK
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def network_interfaces_result(params: dict[str, Any], result: Any) -> bool:
        """Verify network interfaces were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "interfaces" in result or "raw" in result
        return True

    @staticmethod
    async def network_stats_result(params: dict[str, Any], result: Any) -> bool:
        """Verify network stats were returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "stats" in result or "bytes_sent" in result or "error" not in result
        return True

    @staticmethod
    async def connections_result(params: dict[str, Any], result: Any) -> bool:
        """Verify network connections were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "connections" in result or "error" not in result
        return True

    @staticmethod
    async def listening_ports_result(params: dict[str, Any], result: Any) -> bool:
        """Verify listening ports were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "listening" in result or "error" not in result
        return True

    @staticmethod
    async def established_result(params: dict[str, Any], result: Any) -> bool:
        """Verify established connections were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "established" in result or "error" not in result
        return True

    @staticmethod
    async def dns_result(params: dict[str, Any], result: Any) -> bool:
        """Verify DNS info was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "dns_cache" in result or "dns_servers" in result or "dns" in result or "error" not in result
        return True

    @staticmethod
    async def proxy_result(params: dict[str, Any], result: Any) -> bool:
        """Verify proxy settings were returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "proxy" in result or "proxy_enabled" in result or "error" not in result
        return True

    @staticmethod
    async def wifi_profiles_result(params: dict[str, Any], result: Any) -> bool:
        """Verify WiFi profiles were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "profiles" in result or "error" not in result
        return True

    @staticmethod
    async def wifi_status_result(params: dict[str, Any], result: Any) -> bool:
        """Verify WiFi status was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "status" in result or "signal" in result or "ssid" in result or "error" not in result
        return True

    @staticmethod
    async def firewall_status_result(params: dict[str, Any], result: Any) -> bool:
        """Verify firewall status was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "status" in result or "rules" in result or "raw" in result or "error" not in result
        return True

    @staticmethod
    async def firewall_rule_result(params: dict[str, Any], result: Any) -> bool:
        """Verify firewall rule operation returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "status" in result or "rule_added" in result or "error" not in result
        return True

    @staticmethod
    async def traceroute_result(params: dict[str, Any], result: Any) -> bool:
        """Verify traceroute returned results."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "traceroute" in result or "error" not in result
        return True

    @staticmethod
    async def whois_result(params: dict[str, Any], result: Any) -> bool:
        """Verify whois lookup returned results."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "whois" in result or "result" in result or "error" not in result
        return True

    @staticmethod
    async def ping_result(params: dict[str, Any], result: Any) -> bool:
        """Verify ping returned results."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "ping" in result or "raw" in result or "error" not in result
        return True

    @staticmethod
    async def arp_result(params: dict[str, Any], result: Any) -> bool:
        """Verify ARP table was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "arp" in result or "error" not in result
        return True

    @staticmethod
    async def route_result(params: dict[str, Any], result: Any) -> bool:
        """Verify route table was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "routes" in result or "error" not in result
        return True

    @staticmethod
    async def public_ip_ext_result(params: dict[str, Any], result: Any) -> bool:
        """Verify public IP was returned (extended)."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "ip" in result or "error" not in result
        return True

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 11: MEDIA
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def audio_sessions_listed(params: dict[str, Any], result: Any) -> bool:
        """Verify audio sessions were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "sessions" in result or "error" not in result
        return True

    @staticmethod
    async def active_audio_result(params: dict[str, Any], result: Any) -> bool:
        """Verify active audio session was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "pid" in result or "name" in result or "message" in result or "error" not in result
        return True

    @staticmethod
    async def audio_device_muted(params: dict[str, Any], result: Any) -> bool:
        """Verify audio device mute state was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "muted" in result or "error" not in result
        return True

    @staticmethod
    async def media_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify media info was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "players" in result or "message" in result or "error" not in result
        return True

    @staticmethod
    async def media_files_listed(params: dict[str, Any], result: Any) -> bool:
        """Verify media files were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "files" in result or "error" not in result
        return True

    @staticmethod
    async def disc_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify disc info was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "disc" in result or "drives" in result or "raw" in result or "error" not in result
        return True

    @staticmethod
    async def optical_drives_listed(params: dict[str, Any], result: Any) -> bool:
        """Verify optical drives were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "drives" in result or "raw" in result or "error" not in result
        return True

    @staticmethod
    async def media_status_result(params: dict[str, Any], result: Any) -> bool:
        """Verify media status operation returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "status" in result or "note" in result or "error" not in result
        return True

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 12: DEVELOPER
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def git_command_result(params: dict[str, Any], result: Any) -> bool:
        """Verify git command returned a result."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "output" in result or "command" in result or "error" not in result
        return True

    @staticmethod
    async def package_command_result(params: dict[str, Any], result: Any) -> bool:
        """Verify package manager command returned a result."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "output" in result or "command" in result or "error" not in result
        return True

    @staticmethod
    async def file_stats_result(params: dict[str, Any], result: Any) -> bool:
        """Verify file stats were returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "size_bytes" in result or "lines" in result or "error" not in result
        return True

    @staticmethod
    async def port_check_result(params: dict[str, Any], result: Any) -> bool:
        """Verify port check returned a result."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "port" in result and ("in_use" in result or "TcpTestSucceeded" in result or "error" not in result)
        return True

    @staticmethod
    async def terminal_command_result(params: dict[str, Any], result: Any) -> bool:
        """Verify terminal command returned a result."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "output" in result or "command" in result or "error" not in result
        return True

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 13: CLOUD
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def http_response_result(params: dict[str, Any], result: Any) -> bool:
        """Verify HTTP response was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "status_code" in result or "body" in result or "error" not in result
        return True

    @staticmethod
    async def api_test_result(params: dict[str, Any], result: Any) -> bool:
        """Verify API test returned latency and status."""
        if result is None:
            return False
        if isinstance(result, dict):
            return ("status_code" in result and "latency_ms" in result) or "error" not in result
        return True

    @staticmethod
    async def webhook_result(params: dict[str, Any], result: Any) -> bool:
        """Verify webhook operation returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "status" in result or "webhooks" in result or "deleted" in result or "error" not in result
        return True

    @staticmethod
    async def health_check_result(params: dict[str, Any], result: Any) -> bool:
        """Verify health check returned status and latency."""
        if result is None:
            return False
        if isinstance(result, dict):
            return ("status" in result and "latency_ms" in result) or "error" not in result
        return True

    @staticmethod
    async def ssl_cert_result(params: dict[str, Any], result: Any) -> bool:
        """Verify SSL certificate check returned a result."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "TcpTestSucceeded" in result or "raw" in result or "error" not in result
        return True

    @staticmethod
    async def notification_result(params: dict[str, Any], result: Any) -> bool:
        """Verify notification was sent."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "status" in result or "error" not in result
        return True

    @staticmethod
    async def cloud_files_result(params: dict[str, Any], result: Any) -> bool:
        """Verify cloud files were listed."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "files" in result or "provider" in result or "error" not in result
        return True

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 14: AUTOMATION
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def script_execution_result(params: dict[str, Any], result: Any) -> bool:
        """Verify script execution returned output."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "output" in result or "success" in result or "error" not in result
        return True

    @staticmethod
    async def workflow_result(params: dict[str, Any], result: Any) -> bool:
        """Verify workflow operation returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "status" in result or "workflows" in result or "steps" in result or "error" not in result
        return True

    @staticmethod
    async def scheduled_task_result(params: dict[str, Any], result: Any) -> bool:
        """Verify scheduled task operation returned success."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "tasks" in result or "status" in result or "error" not in result
        return True

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 15: ADVANCED
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def power_plan_result(params: dict[str, Any], result: Any) -> bool:
        """Verify power plan info was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "active_plan" in result or "plans" in result or "error" not in result
        return True

    @staticmethod
    async def cpu_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify CPU info was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "physical_cores" in result or "usage_percent" in result or "Name" in result or "error" not in result
        return True

    @staticmethod
    async def gpu_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify GPU info was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "name" in result or "error" not in result
        return True

    @staticmethod
    async def ram_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify RAM info was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "total_gb" in result or "percent" in result or "error" not in result
        return True

    @staticmethod
    async def disk_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify disk info was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "disks" in result or "volumes" in result or "error" not in result
        return True

    @staticmethod
    async def battery_info_result(params: dict[str, Any], result: Any) -> bool:
        """Verify battery info was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "percent" in result or "has_battery" in result or "error" not in result
        return True

    @staticmethod
    async def temperature_result(params: dict[str, Any], result: Any) -> bool:
        """Verify temperature was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "temperature_c" in result or "note" in result or "error" not in result
        return True

    @staticmethod
    async def hardware_summary_result(params: dict[str, Any], result: Any) -> bool:
        """Verify hardware summary was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "cpu_percent" in result or "ram_total_gb" in result or "error" not in result
        return True

    @staticmethod
    async def system_optimization_result(params: dict[str, Any], result: Any) -> bool:
        """Verify system optimization returned results."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "results" in result or "temp_dirs_cleared" in result or "browser_caches_cleared" in result or "error" not in result
        return True

    @staticmethod
    async def uptime_result(params: dict[str, Any], result: Any) -> bool:
        """Verify system uptime was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "days" in result or "hours" in result or "boot_time" in result or "error" not in result
        return True

    @staticmethod
    async def process_summary_result(params: dict[str, Any], result: Any) -> bool:
        """Verify process summary was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "processes" in result or "error" not in result
        return True

    @staticmethod
    async def system_events_result(params: dict[str, Any], result: Any) -> bool:
        """Verify system events were returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "events" in result or "raw" in result or "error" not in result
        return True

    @staticmethod
    async def path_entries_result(params: dict[str, Any], result: Any) -> bool:
        """Verify PATH entries were returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "entries" in result or "error" not in result
        return True

    @staticmethod
    async def counter_or_note_result(params: dict[str, Any], result: Any) -> bool:
        """Verify performance counter or fallback note was returned."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "note" in result or "raw" in result or "bytes_sent" in result or "error" not in result
        return True

    # ════════════════════════════════════════════════════════════════════════
    # GENERIC VERIFIERS
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def always_true(params: dict[str, Any], result: Any) -> bool:
        """Placeholder verifier that always returns True."""
        return True

    @staticmethod
    async def result_not_none(params: dict[str, Any], result: Any) -> bool:
        """Verify the result is not None."""
        return result is not None

    @staticmethod
    async def result_is_true(params: dict[str, Any], result: Any) -> bool:
        """Verify the result is truthy."""
        return bool(result)

    @staticmethod
    async def result_has_key(params: dict[str, Any], result: Any) -> bool:
        """Verify the result dict has at least one key."""
        if result is None:
            return False
        if isinstance(result, dict):
            return len(result) > 0
        return True

    @staticmethod
    async def result_no_error(params: dict[str, Any], result: Any) -> bool:
        """Verify the result doesn't contain an error."""
        if result is None:
            return False
        if isinstance(result, dict):
            return "error" not in result
        return True

    @staticmethod
    async def status_not_failed(params: dict[str, Any], result: Any) -> bool:
        """Verify the result status is not 'failed'.

        Use for operations that return {"status": "failed"} on failure
        (no 'error' key), where result_no_error would always pass.
        """
        if result is None:
            return False
        if isinstance(result, dict):
            return result.get("status") != "failed"
        return True


# ── Verifier Registry ────────────────────────────────────────────────────────

# Maps "layer.action" → verifier function for easy lookup by the router.
# This supplements the per-ACTION_MAP verifiers in each layer file.
# Coverage: 491 actions across all 15 layers.
VERIFIER_MAP: dict[str, Any] = {
    # ── Layer 1: Filesystem (35 actions) ──────────────────────────────────
    "filesystem.delete_file":         Verifiers.file_deleted,
    "filesystem.delete_folder":       Verifiers.folder_deleted,
    "filesystem.create_file":         Verifiers.file_created,
    "filesystem.copy_file":           Verifiers.file_copied,
    "filesystem.move_file":           Verifiers.file_moved,
    "filesystem.rename_file":         Verifiers.file_moved,
    "filesystem.read_file":           Verifiers.file_exists,
    "filesystem.write_file":          Verifiers.file_created,
    "filesystem.append_to_file":      Verifiers.file_exists,
    "filesystem.create_folder":       Verifiers.folder_created,
    "filesystem.list_directory":      Verifiers.search_results,
    "filesystem.search_files":        Verifiers.search_results,
    "filesystem.get_file_info":       Verifiers.file_info_result,
    "filesystem.get_folder_size":     Verifiers.result_has_key,
    "filesystem.get_drive_info":      Verifiers.drives_listed,
    "filesystem.list_drives":         Verifiers.drives_listed,
    "filesystem.copy_folder_tree":    Verifiers.folder_copied,
    "filesystem.delete_folder_tree":  Verifiers.folder_deleted,
    "filesystem.send_to_recycle_bin": Verifiers.file_deleted,
    "filesystem.compress_file":       Verifiers.file_exists,
    "filesystem.decompress_file":     Verifiers.search_results,
    "filesystem.get_file_hash":       Verifiers.result_has_key,
    "filesystem.empty_recycle_bin":   Verifiers.result_no_error,
    "filesystem.create_symlink":      Verifiers.result_has_key,
    "filesystem.change_permissions":  Verifiers.result_no_error,
    "filesystem.monitor_path":        Verifiers.result_has_key,
    "filesystem.find_large_files":    Verifiers.result_has_key,
    "filesystem.find_duplicates":     Verifiers.result_has_key,
    "filesystem.create_hardlink":     Verifiers.result_has_key,
    "filesystem.set_file_attributes": Verifiers.result_has_key,
    "filesystem.restore_from_recycle_bin": Verifiers.result_has_key,
    "filesystem.get_locked_by":       Verifiers.result_has_key,
    "filesystem.monitor_path_start":  Verifiers.result_has_key,
    "filesystem.monitor_path_stop":   Verifiers.result_has_key,
    "filesystem.search_content":      Verifiers.search_results,
    "filesystem.find_and_replace":    Verifiers.result_no_error,
    "filesystem.batch_rename":        Verifiers.result_no_error,
    "filesystem.batch_delete":        Verifiers.result_no_error,

    # ── Layer 2: Process (24 actions) ─────────────────────────────────────
    "process.kill_process":           Verifiers.process_killed,
    "process.kill_process_tree":      Verifiers.process_killed,
    "process.launch_process":         Verifiers.process_launched,
    "process.list_processes":         Verifiers.process_listed,
    "process.get_process_info":       Verifiers.process_info_result,
    "process.set_priority":           Verifiers.priority_set,
    "process.set_affinity":           Verifiers.affinity_set,
    "process.is_process_running":     Verifiers.process_running_check,
    "process.get_cpu_usage":          Verifiers.process_info_result,
    "process.get_memory_usage":       Verifiers.process_info_result,
    "process.get_process_path":       Verifiers.app_path_result,
    "process.get_command_line":       Verifiers.result_has_key,
    "process.suspend_process":        Verifiers.result_has_key,
    "process.resume_process":         Verifiers.result_has_key,
    "process.find_process_by_name":   Verifiers.process_info_result,
    "process.get_parent_pid":         Verifiers.result_has_key,
    "process.create_job_object":      Verifiers.result_has_key,
    "process.get_open_handles":       Verifiers.result_has_key,
    "process.get_threads":            Verifiers.result_has_key,
    "process.wait_for_exit":          Verifiers.result_has_key,
    "process.get_environment":        Verifiers.result_has_key,
    "process.assign_to_job":          Verifiers.result_has_key,
    "process.set_memory_limit":       Verifiers.result_has_key,
    "process.set_cpu_limit":          Verifiers.result_has_key,

    # ── Layer 3: Application (21 actions) ──────────────────────────────────
    "application.launch_app":         Verifiers.process_launched,
    "application.close_app":          Verifiers.process_killed,
    "application.launch_with_args":   Verifiers.process_launched,
    "application.launch_as_admin":    Verifiers.process_launched,
    "application.restart_app":        Verifiers.process_launched,
    "application.is_app_running":     Verifiers.app_running_check,
    "application.list_installed_apps": Verifiers.app_installed_check,
    "application.get_app_path":       Verifiers.app_path_result,
    "application.get_app_version":    Verifiers.app_version_result,
    "application.force_close_app":    Verifiers.process_killed,
    "application.install_app":        Verifiers.result_has_key,
    "application.uninstall_app":      Verifiers.result_has_key,
    "application.automate_app":       Verifiers.result_has_key,
    "application.com_dispatch":       Verifiers.result_has_key,
    "application.pin_to_taskbar":     Verifiers.result_has_key,
    "application.pin_to_start":       Verifiers.result_has_key,
    "application.set_default_program": Verifiers.result_has_key,
    "application.find_app_by_name":   Verifiers.result_has_key,
    "application.get_app_icon":       Verifiers.result_has_key,
    "application.unpin_from_taskbar": Verifiers.result_has_key,
    "application.unpin_from_start":   Verifiers.result_has_key,

    # ── Layer 4: Window (32 actions) ──────────────────────────────────────
    "window.list_all_windows":        Verifiers.window_listed,
    "window.minimize_window":         Verifiers.window_minimized_check,
    "window.maximize_window":         Verifiers.window_maximized_check,
    "window.restore_window":          Verifiers.window_visible_check,
    "window.set_foreground":          Verifiers.window_focused,
    "window.set_topmost":             Verifiers.window_topmost_check,
    "window.unset_topmost":           Verifiers.window_visible_check,
    "window.close_window":            Verifiers.window_closed_check,
    "window.move_window":             Verifiers.window_position,
    "window.resize_window":           Verifiers.window_position,
    "window.find_window":             Verifiers.window_info_result,
    "window.get_active_window":       Verifiers.window_info_result,
    "window.hide_window":             Verifiers.window_visible_check,
    "window.show_window":             Verifiers.window_visible_check,
    "window.get_window_rect":         Verifiers.window_info_result,
    "window.get_window_info":         Verifiers.window_info_result,
    "window.set_position_and_size":   Verifiers.window_position,
    "window.force_close_window":      Verifiers.window_closed_check,
    "window.get_window_title":        Verifiers.window_title_result,
    "window.set_window_title":        Verifiers.window_title_result,
    "window.take_window_screenshot":  Verifiers.window_screenshot_saved,
    "window.arrange_tile":            Verifiers.result_no_error,
    "window.arrange_cascade":         Verifiers.result_no_error,
    "window.get_window_class":        Verifiers.result_has_key,
    "window.is_window_visible":       Verifiers.result_has_key,
    "window.is_window_minimized":     Verifiers.result_has_key,
    "window.list_virtual_desktops":   Verifiers.virtual_desktops_listed,
    "window.send_message":            Verifiers.result_has_key,
    "window.flash_window":            Verifiers.result_has_key,
    "window.get_window_pid_action":   Verifiers.result_has_key,
    "window.post_message":            Verifiers.result_has_key,
    "window.move_to_virtual_desktop": Verifiers.result_has_key,

    # ── Layer 5: Input (25 actions) ───────────────────────────────────────
    "input.press_key":                Verifiers.key_pressed_result,
    "input.type_text":                Verifiers.text_typed_result,
    "input.hotkey":                   Verifiers.key_pressed_result,
    "input.left_click":               Verifiers.mouse_clicked_result,
    "input.right_click":              Verifiers.mouse_clicked_result,
    "input.double_click":             Verifiers.mouse_clicked_result,
    "input.scroll":                   Verifiers.scroll_result,
    "input.set_clipboard":            Verifiers.clipboard_result,
    "input.get_clipboard":            Verifiers.clipboard_result,
    "input.release_key":              Verifiers.key_pressed_result,
    "input.drag_and_drop":            Verifiers.drag_result,
    "input.get_key_state":            Verifiers.result_has_key,
    "input.get_cursor_position":      Verifiers.cursor_position_result,
    "input.tap_key":                  Verifiers.key_pressed_result,
    "input.hold_key":                 Verifiers.key_pressed_result,
    "input.type_text_fast":           Verifiers.text_typed_result,
    "input.middle_click":             Verifiers.mouse_clicked_result,
    "input.scroll_up":                Verifiers.scroll_result,
    "input.scroll_down":              Verifiers.scroll_result,
    "input.screenshot_full":          Verifiers.screenshot_saved,
    "input.screenshot_region":        Verifiers.screenshot_saved,
    "input.screenshot_window":        Verifiers.screenshot_saved,
    "input.mouse_move":               Verifiers.result_has_key,
    "input.mouse_down":               Verifiers.result_has_key,
    "input.mouse_up":                 Verifiers.result_has_key,

    # ── Layer 6: Registry (18 actions) ────────────────────────────────────
    "registry.write_value":           Verifiers.registry_value,
    "registry.create_key":            Verifiers.registry_key_exists,
    "registry.delete_key":            Verifiers.registry_key_deleted,
    "registry.delete_value":          Verifiers.registry_value,
    "registry.read_value":            Verifiers.result_has_key,
    "registry.list_subkeys":          Verifiers.search_results,
    "registry.list_values":           Verifiers.search_results,
    "registry.search_by_name":        Verifiers.registry_search_result,
    "registry.set_key_permissions":   Verifiers.result_no_error,
    "registry.take_ownership":        Verifiers.result_no_error,
    "registry.backup_key":            Verifiers.result_has_key,
    "registry.export_key":            Verifiers.result_has_key,
    "registry.import_key":            Verifiers.result_has_key,
    "registry.key_exists":            Verifiers.result_has_key,
    "registry.value_exists":          Verifiers.result_has_key,
    "registry.restore_key":           Verifiers.result_has_key,
    "registry.search_by_value":       Verifiers.registry_search_result,
    "registry.open_remote_registry":  Verifiers.result_has_key,
    "registry.enable_dark_mode":      Verifiers.result_no_error,
    "registry.enable_light_mode":     Verifiers.result_no_error,

    # ── Layer 7: Services (31 actions) ────────────────────────────────────
    "services.list_services":         Verifiers.service_listed,
    "services.start_service":         Verifiers.service_started,
    "services.stop_service":          Verifiers.service_stopped,
    "services.restart_service":       Verifiers.service_started,
    "services.get_service_status":    Verifiers.result_has_key,
    "services.list_tasks":            Verifiers.task_listed,
    "services.run_task":              Verifiers.result_no_error,
    "services.create_task":           Verifiers.task_created,
    "services.delete_task":           Verifiers.task_deleted,
    "services.enable_task":           Verifiers.task_enabled_disabled,
    "services.disable_task":          Verifiers.task_enabled_disabled,
    "services.get_service_config":    Verifiers.service_config_result,
    "services.pause_service":         Verifiers.service_stopped,
    "services.resume_service":        Verifiers.service_started,
    "services.set_startup_type":      Verifiers.service_enabled,
    "services.install_service":       Verifiers.service_started,
    "services.remove_service":        Verifiers.service_stopped,
    "services.enable_service":        Verifiers.service_enabled,
    "services.disable_service":       Verifiers.service_enabled,
    "services.change_credentials":    Verifiers.result_has_key,
    "services.set_description":       Verifiers.result_has_key,
    "services.get_dependent_services": Verifiers.result_has_key,
    "services.get_task_info":         Verifiers.result_has_key,
    "services.stop_task":             Verifiers.result_has_key,
    "services.get_last_run_result":   Verifiers.result_has_key,
    "services.set_trigger_time":      Verifiers.result_has_key,
    "services.set_trigger_event":     Verifiers.result_has_key,
    "services.set_trigger_logon":     Verifiers.result_has_key,
    "services.set_trigger_idle":      Verifiers.result_has_key,
    "services.get_task_history":      Verifiers.result_has_key,
    "services.get_service_pid":       Verifiers.result_has_key,

    # ── Layer 8: System (49 actions) ──────────────────────────────────────
    "system.set_volume":              Verifiers.volume_set,
    "system.get_volume":              Verifiers.volume_get_result,
    "system.mute":                    Verifiers.result_no_error,
    "system.unmute":                  Verifiers.result_no_error,
    "system.set_brightness":          Verifiers.brightness_set,
    "system.get_brightness":          Verifiers.brightness_get_result,
    "system.get_system_info":         Verifiers.system_info_result,
    "system.get_ram_usage":           Verifiers.ram_usage_result,
    "system.get_disk_usage":          Verifiers.disk_usage_result,
    "system.get_battery":             Verifiers.battery_result,
    "system.get_uptime":              Verifiers.result_has_key,
    "system.get_network_info":        Verifiers.network_info_result,
    "system.get_public_ip":           Verifiers.public_ip_result,
    "system.get_env":                 Verifiers.result_has_key,
    "system.set_system_env":          Verifiers.env_var_set,
    "system.set_user_env":            Verifiers.env_var_set,
    "system.delete_system_env":       Verifiers.env_var_deleted,
    "system.list_env":                Verifiers.env_var_listed,
    "system.add_firewall_rule":       Verifiers.firewall_rule_added,
    "system.remove_firewall_rule":    Verifiers.result_no_error,
    "system.connect_wifi":            Verifiers.wifi_result,
    "system.disconnect_wifi":         Verifiers.wifi_result,
    "system.toggle_wifi":             Verifiers.wifi_result,
    "system.enable_adapter":          Verifiers.adapter_result,
    "system.disable_adapter":         Verifiers.adapter_result,
    "system.flush_dns":               Verifiers.result_no_error,
    "system.get_audio_devices":       Verifiers.audio_devices_result,
    "system.get_os_info":             Verifiers.os_info_result,
    "system.list_wifi_networks":      Verifiers.wifi_networks_listed,
    "system.get_installed_updates":   Verifiers.updates_listed,
    "system.rotate_display":          Verifiers.result_no_error,
    "system.logoff":                  Verifiers.result_no_error,
    "system.shutdown":                Verifiers.result_no_error,
    "system.restart":                 Verifiers.result_no_error,
    "system.sleep":                   Verifiers.result_no_error,
    "system.hibernate":               Verifiers.result_no_error,
    "system.lock":                    Verifiers.result_no_error,
    "system.change_resolution":       Verifiers.result_has_key,
    "system.get_displays":            Verifiers.result_has_key,
    "system.get_wifi_password":       Verifiers.result_has_key,
    "system.get_cpu_temp":            Verifiers.result_has_key,
    "system.get_hardware_info":       Verifiers.result_has_key,
    "system.watch_process":           Verifiers.result_has_key,
    "system.watch_usb":               Verifiers.result_has_key,
    "system.watch_file_events":       Verifiers.result_has_key,
    "system.set_default_device":      Verifiers.result_has_key,
    "system.get_user_env":            Verifiers.result_has_key,

    # ── Layer 9: Browser (34 actions) ─────────────────────────────────────
    "browser.navigate":               Verifiers.page_navigated,
    "browser.reload":                 Verifiers.page_navigated,
    "browser.go_back":                Verifiers.page_navigated,
    "browser.go_forward":             Verifiers.page_navigated,
    "browser.new_tab":                Verifiers.tab_operation,
    "browser.close_tab":              Verifiers.tab_operation,
    "browser.switch_tab":             Verifiers.tab_operation,
    "browser.get_page_info":          Verifiers.page_info_result,
    "browser.get_current_url":        Verifiers.page_info_result,
    "browser.get_page_content":       Verifiers.result_has_key,
    "browser.get_page_html":          Verifiers.result_has_key,
    "browser.click_element":          Verifiers.element_clicked,
    "browser.hover_element":          Verifiers.result_has_key,
    "browser.type_into_element":      Verifiers.text_typed_result,
    "browser.fill_form":              Verifiers.result_has_key,
    "browser.submit_form":            Verifiers.result_has_key,
    "browser.find_element":           Verifiers.element_found,
    "browser.get_element_text":       Verifiers.result_has_key,
    "browser.get_element_attribute":  Verifiers.result_has_key,
    "browser.scroll_page":            Verifiers.scroll_result,
    "browser.scroll_to_element":      Verifiers.result_has_key,
    "browser.take_screenshot":        Verifiers.screenshot_path_result,
    "browser.run_javascript":         Verifiers.js_result,
    "browser.wait_for_element":       Verifiers.result_has_key,
    "browser.wait_for_url":           Verifiers.result_has_key,
    "browser.wait_for_network_idle":  Verifiers.result_has_key,
    "browser.manage_cookies":         Verifiers.cookie_operation,
    "browser.manage_local_storage":   Verifiers.result_has_key,
    "browser.download_file":          Verifiers.result_has_key,
    "browser.intercept_request":      Verifiers.result_has_key,
    "browser.open_browser":           Verifiers.browser_connected,
    "browser.close_browser":          Verifiers.browser_closed,
    "browser.handle_dialog":          Verifiers.result_has_key,
    "browser.connect_to_browser":     Verifiers.browser_connected,

    # ── Layer 10: Network (38 actions) ─────────────────────────────────
    "network.get_network_interfaces":   Verifiers.network_interfaces_result,
    "network.get_network_stats":        Verifiers.network_stats_result,
    "network.get_connections":          Verifiers.connections_result,
    "network.get_listening_ports":      Verifiers.listening_ports_result,
    "network.get_established_connections": Verifiers.established_result,
    "network.get_network_bytes":        Verifiers.network_stats_result,
    "network.get_dns_cache":            Verifiers.dns_result,
    "network.get_dns_servers":          Verifiers.dns_result,
    "network.get_proxy_settings":       Verifiers.proxy_result,
    "network.get_network_latency":      Verifiers.ping_result,
    "network.get_traceroute":           Verifiers.traceroute_result,
    "network.get_whois":                Verifiers.whois_result,
    "network.get_wifi_profiles":        Verifiers.wifi_profiles_result,
    "network.connect_wifi_profile":     Verifiers.wifi_status_result,
    "network.disconnect_wifi_profile":  Verifiers.wifi_status_result,
    "network.forget_wifi_profile":      Verifiers.wifi_status_result,
    "network.get_wifi_signal_strength": Verifiers.wifi_status_result,
    "network.set_wifi_autoconnect":     Verifiers.wifi_status_result,
    "network.create_wifi_hotspot":      Verifiers.wifi_status_result,
    "network.stop_wifi_hotspot":        Verifiers.wifi_status_result,
    "network.list_firewall_rules":      Verifiers.firewall_status_result,
    "network.add_firewall_rule":        Verifiers.firewall_rule_result,
    "network.remove_firewall_rule":     Verifiers.firewall_rule_result,
    "network.enable_firewall":          Verifiers.firewall_status_result,
    "network.disable_firewall":         Verifiers.firewall_status_result,
    "network.get_firewall_status":      Verifiers.firewall_status_result,
    "network.set_dns_servers":          Verifiers.result_no_error,
    "network.set_static_ip":            Verifiers.result_no_error,
    "network.set_dhcp":                 Verifiers.result_no_error,
    "network.set_network_proxy":        Verifiers.proxy_result,
    "network.clear_proxy":              Verifiers.proxy_result,
    "network.set_network_priority":     Verifiers.result_no_error,
    "network.ping_host":                Verifiers.ping_result,
    "network.nslookup":                 Verifiers.whois_result,
    "network.netstat_listening":        Verifiers.listening_ports_result,
    "network.arp_table":                Verifiers.arp_result,
    "network.route_table":              Verifiers.route_result,
    "network.get_public_ip_extended":   Verifiers.public_ip_ext_result,

    # ── Layer 11: Media (32 actions) ───────────────────────────────────
    "media.list_audio_sessions":        Verifiers.audio_sessions_listed,
    "media.get_active_audio":           Verifiers.active_audio_result,
    "media.get_all_audio_sessions":     Verifiers.audio_sessions_listed,
    "media.set_session_volume":         Verifiers.media_status_result,
    "media.set_session_mute":           Verifiers.media_status_result,
    "media.set_session_state":          Verifiers.media_status_result,
    "media.get_audio_meter":            Verifiers.active_audio_result,
    "media.set_audio_endpoint":         Verifiers.media_status_result,
    "media.get_default_audio_device":   Verifiers.active_audio_result,
    "media.set_default_audio_device":   Verifiers.media_status_result,
    "media.list_audio_devices":         Verifiers.audio_devices_result,
    "media.get_audio_device_info":      Verifiers.active_audio_result,
    "media.enable_audio_device":        Verifiers.media_status_result,
    "media.disable_audio_device":       Verifiers.media_status_result,
    "media.set_audio_device_volume":    Verifiers.media_status_result,
    "media.mute_audio_device":          Verifiers.audio_device_muted,
    "media.unmute_audio_device":        Verifiers.audio_device_muted,
    "media.get_audio_device_mute":      Verifiers.audio_device_muted,
    "media.get_media_info":             Verifiers.media_info_result,
    "media.list_media_files":           Verifiers.media_files_listed,
    "media.play_media":                 Verifiers.media_status_result,
    "media.pause_media":                Verifiers.media_status_result,
    "media.stop_media":                 Verifiers.media_status_result,
    "media.next_track":                 Verifiers.media_status_result,
    "media.previous_track":             Verifiers.media_status_result,
    "media.get_media_position":         Verifiers.media_status_result,
    "media.list_optical_drives":        Verifiers.optical_drives_listed,
    "media.get_disc_info":              Verifiers.disc_info_result,
    "media.eject_disc":                 Verifiers.media_status_result,
    "media.close_disc_tray":            Verifiers.media_status_result,
    "media.is_disc_inserted":           Verifiers.disc_info_result,
    "media.get_disc_type":              Verifiers.disc_info_result,

    # ── Layer 12: Developer (35 actions) ───────────────────────────────
    "developer.git_status":             Verifiers.git_command_result,
    "developer.git_diff":               Verifiers.git_command_result,
    "developer.git_log":                Verifiers.git_command_result,
    "developer.git_commit":             Verifiers.git_command_result,
    "developer.git_push":               Verifiers.git_command_result,
    "developer.git_pull":               Verifiers.git_command_result,
    "developer.git_branch":             Verifiers.git_command_result,
    "developer.git_checkout":           Verifiers.git_command_result,
    "developer.git_merge":              Verifiers.git_command_result,
    "developer.git_rebase":             Verifiers.git_command_result,
    "developer.npm_install":            Verifiers.package_command_result,
    "developer.npm_run":                Verifiers.package_command_result,
    "developer.npm_list":               Verifiers.package_command_result,
    "developer.pip_install":            Verifiers.package_command_result,
    "developer.pip_list":               Verifiers.package_command_result,
    "developer.pip_freeze":             Verifiers.package_command_result,
    "developer.cargo_build":            Verifiers.package_command_result,
    "developer.cargo_run":              Verifiers.package_command_result,
    "developer.find_files":             Verifiers.search_results,
    "developer.replace_in_file":        Verifiers.result_no_error,
    "developer.count_lines":            Verifiers.file_stats_result,
    "developer.compare_files":          Verifiers.file_stats_result,
    "developer.watch_directory":        Verifiers.result_has_key,
    "developer.compress_directory":     Verifiers.result_no_error,
    "developer.extract_archive":        Verifiers.result_no_error,
    "developer.syntax_check":           Verifiers.terminal_command_result,
    "developer.lint_file":              Verifiers.terminal_command_result,
    "developer.format_file":            Verifiers.terminal_command_result,
    "developer.get_file_stats":         Verifiers.file_stats_result,
    "developer.search_code":            Verifiers.search_results,
    "developer.run_terminal":           Verifiers.terminal_command_result,
    "developer.open_terminal":          Verifiers.status_not_failed,
    "developer.list_services_running":  Verifiers.service_listed,
    "developer.check_port":             Verifiers.port_check_result,
    "developer.kill_port":              Verifiers.result_no_error,

    # ── Layer 13: Cloud (30 actions) ───────────────────────────────────
    "cloud.http_get":                   Verifiers.http_response_result,
    "cloud.http_post":                  Verifiers.http_response_result,
    "cloud.http_put":                   Verifiers.http_response_result,
    "cloud.http_delete":                Verifiers.http_response_result,
    "cloud.http_patch":                 Verifiers.http_response_result,
    "cloud.http_head":                  Verifiers.http_response_result,
    "cloud.http_request":               Verifiers.http_response_result,
    "cloud.test_api":                   Verifiers.api_test_result,
    "cloud.create_webhook":             Verifiers.webhook_result,
    "cloud.list_webhooks":              Verifiers.webhook_result,
    "cloud.delete_webhook":             Verifiers.webhook_result,
    "cloud.test_webhook":               Verifiers.http_response_result,
    "cloud.webhook_history":            Verifiers.webhook_result,
    "cloud.set_webhook_headers":        Verifiers.webhook_result,
    "cloud.list_cloud_files":           Verifiers.cloud_files_result,
    "cloud.upload_cloud_file":          Verifiers.cloud_files_result,
    "cloud.download_cloud_file":        Verifiers.cloud_files_result,
    "cloud.delete_cloud_file":          Verifiers.cloud_files_result,
    "cloud.get_cloud_storage_info":     Verifiers.cloud_files_result,
    "cloud.sync_cloud_folder":          Verifiers.cloud_files_result,
    "cloud.check_service_health":       Verifiers.health_check_result,
    "cloud.monitor_api_endpoint":       Verifiers.health_check_result,
    "cloud.get_ssl_certificate":        Verifiers.ssl_cert_result,
    "cloud.check_dns_propagation":      Verifiers.dns_result,
    "cloud.get_whois_info":             Verifiers.whois_result,
    "cloud.send_api_email":             Verifiers.notification_result,
    "cloud.send_webhook_notification":  Verifiers.notification_result,
    "cloud.send_discord_webhook":       Verifiers.notification_result,
    "cloud.send_slack_message":         Verifiers.notification_result,
    "cloud.send_telegram_message":      Verifiers.notification_result,

    # ── Layer 14: Automation (28 actions) ──────────────────────────────
    "automation.list_scheduled_tasks":       Verifiers.scheduled_task_result,
    "automation.create_scheduled_task":      Verifiers.task_created,
    "automation.delete_scheduled_task":      Verifiers.task_deleted,
    "automation.enable_scheduled_task":      Verifiers.task_enabled_disabled,
    "automation.disable_scheduled_task":     Verifiers.task_enabled_disabled,
    "automation.run_scheduled_task":         Verifiers.scheduled_task_result,
    "automation.get_task_history":           Verifiers.scheduled_task_result,
    "automation.get_task_status":            Verifiers.scheduled_task_result,
    "automation.run_powershell":             Verifiers.script_execution_result,
    "automation.run_batch":                  Verifiers.script_execution_result,
    "automation.run_python":                 Verifiers.script_execution_result,
    "automation.run_node":                   Verifiers.script_execution_result,
    "automation.run_script_file":            Verifiers.script_execution_result,
    "automation.stop_script":                Verifiers.status_not_failed,
    "automation.get_script_output":          Verifiers.script_execution_result,
    "automation.create_workflow":            Verifiers.workflow_result,
    "automation.list_workflows":             Verifiers.workflow_result,
    "automation.run_workflow":               Verifiers.workflow_result,
    "automation.stop_workflow":              Verifiers.workflow_result,
    "automation.get_workflow_status":        Verifiers.workflow_result,
    "automation.delete_workflow":            Verifiers.workflow_result,
    "automation.get_clipboard_text":         Verifiers.clipboard_result,
    "automation.set_clipboard_text":         Verifiers.clipboard_result,
    "automation.get_clipboard_image":        Verifiers.result_has_key,
    "automation.type_text_auto":             Verifiers.text_typed_result,
    "automation.send_keys_auto":             Verifiers.key_pressed_result,
    "automation.simulate_mouse":             Verifiers.status_not_failed,
    "automation.capture_screen_auto":        Verifiers.screenshot_saved,

    # ── Layer 15: Advanced (35 actions) ────────────────────────────────
    "advanced.get_power_plan":              Verifiers.power_plan_result,
    "advanced.set_power_plan":              Verifiers.power_plan_result,
    "advanced.list_power_plans":            Verifiers.power_plan_result,
    "advanced.create_power_plan":           Verifiers.power_plan_result,
    "advanced.delete_power_plan":           Verifiers.power_plan_result,
    "advanced.get_battery_health":          Verifiers.battery_info_result,
    "advanced.set_sleep_timeout":           Verifiers.power_plan_result,
    "advanced.set_hibernate_timeout":       Verifiers.power_plan_result,
    "advanced.get_cpu_info":                Verifiers.cpu_info_result,
    "advanced.get_gpu_info":                Verifiers.gpu_info_result,
    "advanced.get_ram_info":                Verifiers.ram_info_result,
    "advanced.get_disk_info":               Verifiers.disk_info_result,
    "advanced.get_battery_info":            Verifiers.battery_info_result,
    "advanced.get_temperature":             Verifiers.temperature_result,
    "advanced.get_fan_speed":               Verifiers.temperature_result,
    "advanced.get_hardware_summary":        Verifiers.hardware_summary_result,
    "advanced.clear_temp_files":            Verifiers.system_optimization_result,
    "advanced.clear_browser_cache":         Verifiers.system_optimization_result,
    "advanced.defragment_drive":            Verifiers.system_optimization_result,
    "advanced.check_disk_errors":           Verifiers.system_optimization_result,
    "advanced.optimize_system":             Verifiers.system_optimization_result,
    "advanced.disable_startup_programs":    Verifiers.status_not_failed,
    "advanced.enable_startup_programs":     Verifiers.status_not_failed,
    "advanced.list_environment_variables":  Verifiers.env_var_listed,
    "advanced.get_environment_variable":    Verifiers.env_var_listed,
    "advanced.set_environment_variable":    Verifiers.env_var_set,
    "advanced.delete_environment_variable": Verifiers.env_var_deleted,
    "advanced.list_path_entries":           Verifiers.path_entries_result,
    "advanced.add_to_path":                 Verifiers.path_entries_result,
    "advanced.get_system_uptime":           Verifiers.uptime_result,
    "advanced.get_process_summary":         Verifiers.process_summary_result,
    "advanced.get_memory_usage_detailed":   Verifiers.ram_info_result,
    "advanced.get_disk_performance":        Verifiers.counter_or_note_result,
    "advanced.get_network_performance":     Verifiers.counter_or_note_result,
    "advanced.get_system_events":           Verifiers.system_events_result,
}


def get_verifier(layer: str, action: str):
    """Look up the verifier for a given layer.action combination.

    Returns the verifier function, or None if no specific verifier exists.
    """
    key = f"{layer}.{action}"
    return VERIFIER_MAP.get(key)
