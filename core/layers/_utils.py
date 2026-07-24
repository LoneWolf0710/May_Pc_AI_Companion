"""Shared async utilities for all control layers.

Provides common helper functions for running PowerShell, CMD,
and synchronous subprocess commands without blocking the event loop.
"""

from __future__ import annotations

import asyncio
import subprocess
import logging
from typing import Any

logger = logging.getLogger("may.core.layers.utils")


async def run_ps(command: str, timeout: float = 15) -> tuple[bool, str]:
    """Run a PowerShell command asynchronously. Returns (success, output)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-Command", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode == 0:
            return True, output
        error = stderr.decode("utf-8", errors="replace").strip()
        return False, error or output
    except asyncio.TimeoutError:
        return False, f"PowerShell command timed out after {timeout}s"
    except FileNotFoundError:
        return False, "PowerShell not found"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


async def run_cmd(args: list[str], timeout: float = 15) -> tuple[bool, str]:
    """Run a command asynchronously. Returns (success, output)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode == 0:
            return True, output
        error = stderr.decode("utf-8", errors="replace").strip()
        return False, error or output
    except asyncio.TimeoutError:
        return False, f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return False, f"Command not found: {args[0]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def run_cmd_sync(args: list[str], timeout: float = 10) -> tuple[bool, str]:
    """Run a command synchronously (for blocking Win32 calls)."""
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout.strip()
        if result.returncode == 0:
            return True, output
        error = result.stderr.strip()
        return False, error or output
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return False, f"Command not found: {args[0]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ── Shared Win32 window helpers ──────────────────────────────────────────────
# Used by L4_window and L5_input to avoid code duplication.

def find_window_by_title(title: str) -> int | None:
    """Find a top-level visible window by partial title match.

    Returns the first matching hwnd, or None if not found.
    Uses Win32 EnumWindows — works from any layer without circular imports.
    """
    import ctypes
    import ctypes.wintypes

    title_lower = title.lower()
    found = []

    def enum_callback(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                if title_lower in buf.value.lower():
                    found.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM,
    )
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    return found[0] if found else None


def get_window_pid(hwnd: int) -> int:
    """Get the PID owning a window handle."""
    import ctypes
    import ctypes.wintypes

    pid = ctypes.wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


# ── Shared privilege escalation for FallbackChain ───────────────────────────
# Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 15 Step 6:
# "If all methods fail → Escalate privilege → Retry from Method 1"
#
# All 9 layers pass `escalation_fn` to FallbackChain.execute() so that
# when normal methods exhaust, the system retries with SYSTEM privileges.

def create_escalation_fn(layer: str, action: str):
    """Factory: returns an async escalation_fn suitable for FallbackChain.

    The returned coroutine:
      1. Checks if the daemon is already running as SYSTEM.
      2. If not, attempts to restart the daemon as SYSTEM via PsExec.
      3. Returns True if escalation succeeded (chain will retry methods).

    Args:
        layer:  Layer name (e.g. 'filesystem') for logging.
        action: Action name (e.g. 'delete_file') for logging.
    """
    async def _escalate() -> bool:
        try:
            from core.privilege import is_daemon_running_as_system, _find_psexec

            # Already SYSTEM — nothing to do
            if is_daemon_running_as_system():
                logger.info(
                    "Escalation: already running as SYSTEM for %s.%s",
                    layer, action,
                )
                return True

            # Try to find PsExec
            psexec = _find_psexec()
            if not psexec:
                logger.warning(
                    "Escalation: PsExec not found, cannot escalate %s.%s",
                    layer, action,
                )
                return False

            # Restart the daemon as SYSTEM via PsExec -s
            import subprocess
            daemon_script = str(
                __import__("pathlib").Path(__file__).resolve().parent.parent / "daemon.py"
            )
            subprocess.Popen(
                [psexec, "-s", "-d", "-accepteula",
                 "python", daemon_script, "debug"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info(
                "Escalation: started SYSTEM daemon via PsExec for %s.%s",
                layer, action,
            )
            # Brief wait for the new daemon to bind the port
            await asyncio.sleep(1.0)
            return True

        except Exception as e:
            logger.error(
                "Escalation failed for %s.%s: %s", layer, action, e,
            )
            return False

    return _escalate


def create_preflight_fn(layer: str, action: str):
    """Factory: returns an async preflight_fn suitable for FallbackChain.

    Performs basic pre-flight checks before execution:
      - Does the target file/folder exist? (for destructive actions)
      - Permission sanity check
    """
    async def _preflight(params: dict) -> str | None:
        """Returns None if ok, or an error string if the check fails."""
        # Check target existence for destructive file operations
        destructive_actions = {
            "delete_file", "delete_folder", "delete_folder_tree",
            "move_file", "rename_file",
        }
        if action in destructive_actions:
            target = params.get("path") or params.get("source")
            if target:
                import os
                if not os.path.exists(target):
                    return f"Target does not exist: {target}"

        # Check source existence for copy operations
        copy_actions = {"copy_file", "copy_folder_tree"}
        if action in copy_actions:
            source = params.get("source")
            if source:
                import os
                if not os.path.exists(source):
                    return f"Source does not exist: {source}"

        return None  # All checks passed

    return _preflight

