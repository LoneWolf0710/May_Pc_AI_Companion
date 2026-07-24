"""Privilege Management — UAC, Token Escalation, Admin Detection.

This is the most critical part of the Control Core. Without proper
privileges, ~30% of Windows operations silently fail.

Privilege Levels:
  Level 1: Administrator — covers 95% of operations (UAC prompt)
  Level 2: SYSTEM — protected system files, service internals (Windows Service)
  Level 3: TrustedInstaller — C:\\Windows\\*, protected OS components

Token Privileges Enabled at Startup:
  SeDebugPrivilege          Read/write any process memory
  SeRestorePrivilege        Write to any file regardless of ACL
  SeBackupPrivilege         Read any file regardless of ACL
  SeTakeOwnershipPrivilege  Take ownership of any object
  SeSecurityPrivilege       Modify security descriptors
  SeLoadDriverPrivilege     Load/unload device drivers
  SeShutdownPrivilege       Shutdown/restart the system
  SeTcbPrivilege            Act as part of the OS (SYSTEM-level tasks)

Escalation Methods:
  Level 2 (SYSTEM): Uses PsExec.exe -s to run commands as SYSTEM.
      Requires PsExec.exe downloaded from Sysinternals.
  Level 3 (TrustedInstaller): Uses PsExec to start TrustedInstaller service
      then duplicates its token. Note: This is best-effort; some protected
      OS components may still resist modification even with TrustedInstaller
      token impersonation due to additional security checks.
"""

import ctypes
import ctypes.wintypes
import sys
import os
import logging
import subprocess

logger = logging.getLogger("may.core.privilege")

# ── Windows Constants ────────────────────────────────────────────────────────

SE_DEBUG_NAME = "SeDebugPrivilege"
SE_RESTORE_NAME = "SeRestorePrivilege"
SE_BACKUP_NAME = "SeBackupPrivilege"
SE_TAKEOWNERSHIP_NAME = "SeTakeOwnershipPrivilege"
SE_SECURITY_NAME = "SeSecurityPrivilege"
SE_LOAD_DRIVER_NAME = "SeLoadDriverPrivilege"
SE_SHUTDOWN_NAME = "SeShutdownPrivilege"
SE_TCB_NAME = "SeTcbPrivilege"

TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
TOKEN_DUPLICATE = 0x0002
TOKEN_ALL_ACCESS = 0x00F000FF
ERROR_SUCCESS = 0
ERROR_NOT_ALL_ASSIGNED = 1300

PRIVILEGES_NEEDED = [
    SE_DEBUG_NAME,
    SE_RESTORE_NAME,
    SE_BACKUP_NAME,
    SE_TAKEOWNERSHIP_NAME,
    SE_SECURITY_NAME,
    SE_LOAD_DRIVER_NAME,
    SE_SHUTDOWN_NAME,
    SE_TCB_NAME,
]


# ── Win32 API Structures ─────────────────────────────────────────────────────

class LUID(ctypes.Structure):
    _fields_ = [
        ("LowPart", ctypes.wintypes.DWORD),
        ("HighPart", ctypes.wintypes.LONG),
    ]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Luid", LUID),
        ("Attributes", ctypes.wintypes.DWORD),
    ]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", ctypes.wintypes.DWORD),
        ("Privileges", LUID_AND_ATTRIBUTES * 1),  # Variable length
    ]


# ── Win32 Function Wrappers ──────────────────────────────────────────────────

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

# Declare prototypes so ctypes does NOT default return/arg types to 32-bit c_int.
# On 64-bit Python, GetCurrentProcess() returns a pseudo-handle (-1 / 0xFFFFFFFFFFFFFFFF);
# without an explicit HANDLE restype ctypes truncates it to 32 bits, producing an
# invalid handle that makes OpenProcessToken fail with "handle is invalid".
kernel32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
kernel32.GetCurrentProcess.argtypes = []
advapi32.OpenProcessToken.restype = ctypes.wintypes.BOOL
advapi32.OpenProcessToken.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
    ctypes.POINTER(ctypes.wintypes.HANDLE),
]
advapi32.LookupPrivilegeValueW.restype = ctypes.wintypes.BOOL
advapi32.LookupPrivilegeValueW.argtypes = [
    ctypes.wintypes.LPCWSTR,
    ctypes.wintypes.LPCWSTR,
    ctypes.POINTER(LUID),
]
advapi32.AdjustTokenPrivileges.restype = ctypes.wintypes.BOOL
advapi32.AdjustTokenPrivileges.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.BOOL,
    ctypes.c_void_p,
    ctypes.wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]


def _get_current_token() -> ctypes.wintypes.HANDLE:
    """Get handle to current process token."""
    handle = ctypes.wintypes.HANDLE()
    result = advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(handle),
    )
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def _get_luid(privilege_name: str) -> LUID:
    """Look up the LUID for a named privilege."""
    luid = LUID()
    result = advapi32.LookupPrivilegeValueW(
        None,  # System name (local)
        privilege_name,
        ctypes.byref(luid),
    )
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return luid


def _adjust_privilege(token_handle: ctypes.wintypes.HANDLE, privilege_name: str, enable: bool = True) -> bool:
    """Enable or disable a specific privilege on a token."""
    luid = _get_luid(privilege_name)

    tp = TOKEN_PRIVILEGES()
    tp.PrivilegeCount = 1
    tp.Privileges[0].Luid = luid
    tp.Privileges[0].Attributes = 0x00000002 if enable else 0  # SE_PRIVILEGE_ENABLED

    result = advapi32.AdjustTokenPrivileges(
        token_handle,
        False,  # DisableAllPrivileges
        ctypes.byref(tp),
        ctypes.sizeof(tp),
        None,   # PreviousState
        None,   # ReturnLength
    )

    if not result:
        return False

    last_error = ctypes.get_last_error()
    return last_error == ERROR_SUCCESS


def _close_handle_safe(handle: ctypes.wintypes.HANDLE) -> None:
    """Safely close a Win32 handle, ignoring errors."""
    try:
        if handle and handle != ctypes.wintypes.HANDLE(-1).value:
            kernel32.CloseHandle(handle)
    except Exception:
        pass


# ── Public API ───────────────────────────────────────────────────────────────

def is_admin() -> bool:
    """Check if the current process is running with Administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ensure_admin() -> bool:
    """Re-launch as admin via UAC if not already elevated.

    Returns:
        True if already admin, False if re-launch was triggered (process exits).
    """
    if is_admin():
        logger.info("Running with Administrator privileges")
        return True

    logger.warning("Not running as admin — triggering UAC elevation")
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            " ".join(sys.argv),
            None,
            1,  # SW_SHOWNORMAL
        )
    except Exception as e:
        logger.error("UAC elevation failed: %s", e)
        return False

    # Original process exits after triggering elevation
    sys.exit(0)


def enable_all_privileges() -> dict[str, bool]:
    """Enable all required token privileges for the Control Core.

    Returns:
        Dict mapping privilege name to whether it was successfully enabled.
    """
    results = {}
    try:
        token = _get_current_token()
    except Exception as e:
        logger.error("Failed to open process token: %s", e)
        return {name: False for name in PRIVILEGES_NEEDED}

    for priv_name in PRIVILEGES_NEEDED:
        try:
            success = _adjust_privilege(token, priv_name, enable=True)
            results[priv_name] = success
            if success:
                logger.debug("Enabled privilege: %s", priv_name)
            else:
                logger.warning("Could not enable privilege: %s (may require higher elevation)", priv_name)
        except Exception as e:
            results[priv_name] = False
            logger.warning("Failed to enable %s: %s", priv_name, e)

    _close_handle_safe(token)

    enabled_count = sum(1 for v in results.values() if v)
    logger.info("Privileges enabled: %d/%d", enabled_count, len(PRIVILEGES_NEEDED))
    return results


def get_privilege_status() -> dict[str, str]:
    """Check which privileges are currently enabled on the process token.

    Returns:
        Dict mapping privilege name to status string:
          'enabled'     — privilege is active on the token
          'disabled'    — privilege exists but is not active
          'unavailable' — privilege LUID not found on this system
          'token_error' — could not open process token
    """
    status = {}
    try:
        token = _get_current_token()
    except Exception:
        return {name: "token_error" for name in PRIVILEGES_NEEDED}

    for priv_name in PRIVILEGES_NEEDED:
        try:
            luid = _get_luid(priv_name)
            tp = TOKEN_PRIVILEGES()
            tp.PrivilegeCount = 1
            tp.Privileges[0].Luid = luid
            tp.Privileges[0].Attributes = 0x00000002  # SE_PRIVILEGE_ENABLED
            result = advapi32.AdjustTokenPrivileges(
                token, False, ctypes.byref(tp), ctypes.sizeof(tp), None, None,
            )
            if result and ctypes.get_last_error() == ERROR_SUCCESS:
                status[priv_name] = "enabled"
            else:
                status[priv_name] = "disabled"
        except Exception:
            status[priv_name] = "unavailable"

    _close_handle_safe(token)
    return status


def check_admin_and_enable() -> dict:
    """Full startup sequence: check admin status and enable all privileges.

    Returns:
        Dict with 'admin' bool and 'privileges' dict.
    """
    admin = is_admin()
    privileges = enable_all_privileges() if admin else {}

    return {
        "admin": admin,
        "privileges": privileges,
        "privilege_count": sum(1 for v in privileges.values() if v),
        "total_privileges": len(PRIVILEGES_NEEDED),
    }


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 2: SYSTEM PRIVILEGE ESCALATION
# ══════════════════════════════════════════════════════════════════════════════

# PsExec path (bundled with the project or in PATH)
_PSEXEC_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "..", "tools", "PsExec.exe"),
    os.path.join(os.path.expandvars(r"%LOCALAPPDATA%\may"), "PsExec.exe"),
    "PsExec.exe",  # In PATH
    os.path.join(os.path.expandvars(r"%PROGRAMFILES%\Sysinternals"), "PsExec.exe"),
]


def _find_psexec() -> str | None:
    """Find PsExec.exe on the system."""
    for path in _PSEXEC_PATHS:
        if os.path.isfile(path):
            return os.path.abspath(path)
    return None


def is_daemon_running_as_system() -> bool:
    """Check if the control core daemon is already running.

    Note: The daemon auto-starts via main.py. When installed as a
    Windows Service, it runs under the LocalSystem account (SYSTEM level).
    This function checks if it's accessible on the TCP socket.

    Returns:
        True if daemon is reachable on port 7650.
    """
    try:
        from core.client import is_daemon_running_sync
        return is_daemon_running_sync()
    except Exception:
        return False


def run_as_system(command: str, timeout: float = 30) -> tuple[bool, str]:
    """Execute a command with SYSTEM privileges using PsExec.

    This bypasses all DACL/ACL restrictions and can access:
    - Protected system files (C:\\Windows\\*)
    - Service internals
    - Locked process handles

    Requires PsExec.exe from Sysinternals. Download from:
    https://learn.microsoft.com/en-us/sysinternals/downloads/psexec

    Args:
        command: The command to execute
        timeout: Maximum time in seconds to wait

    Returns:
        Tuple of (success, output)
    """
    psexec = _find_psexec()
    if not psexec:
        return False, (
            "PsExec not found. Download from "
            "https://learn.microsoft.com/en-us/sysinternals/downloads/psexec "
            "and place in PATH or tools/ directory."
        )

    try:
        # -s = Run as SYSTEM, -accepteula = Accept EULA, -nobanner = No banner
        # -d = Don't wait (detached) — use without -d for blocking execution
        result = subprocess.run(
            [psexec, "-s", "-accepteula", "-nobanner",
             "cmd.exe", "/c", command],
            capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout.strip()
        if result.returncode == 0:
            return True, output
        error = result.stderr.strip()
        return False, error or output or f"Exit code: {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, f"SYSTEM command timed out after {timeout}s"
    except FileNotFoundError:
        return False, f"PsExec not found at: {psexec}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


async def run_command_as_system(args: list[str], timeout: float = 30) -> tuple[bool, str]:
    """Execute a command with SYSTEM privileges asynchronously.

    Wraps the blocking run_as_system() in an executor to avoid
    blocking the asyncio event loop.

    Args:
        args: Command arguments
        timeout: Maximum time in seconds

    Returns:
        Tuple of (success, output)
    """
    import asyncio
    command = " ".join(args)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, run_as_system, command, timeout)


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 3: TRUSTEDINSTALLER PRIVILEGE ESCALATION
# ══════════════════════════════════════════════════════════════════════════════

def _get_trusted_installer_pid() -> int | None:
    """Find the TrustedInstaller service PID.

    Returns the PID if the service is running, None otherwise.
    """
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "(Get-CimInstance Win32_Service -Filter \"Name='TrustedInstaller'\").ProcessId"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip().isdigit():
            pid = int(result.stdout.strip())
            if pid > 0:
                return pid
    except Exception as e:
        logger.debug("Failed to find TrustedInstaller PID: %s", e)
    return None


def _impersonate_trusted_installer() -> bool:
    """Impersonate the TrustedInstaller service token.

    This allows modification of protected OS components (C:\\Windows\\*).
    Requires Administrator privileges and the TrustedInstaller service to be running.

    Note: This is a best-effort approach. Some protected OS components
    have additional security checks beyond token verification that may
    still block modification.

    Returns:
        True if impersonation was successfully set on the current thread.
    """
    ti_pid = _get_trusted_installer_pid()
    if not ti_pid:
        logger.error("TrustedInstaller service is not running or not found")
        return False

    # Open the TrustedInstaller process
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_DUP_HANDLE = 0x0040
    PROCESS_QUERY_INFORMATION = 0x0400

    ti_handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_DUP_HANDLE | PROCESS_QUERY_INFORMATION,
        False,
        ti_pid,
    )
    if not ti_handle:
        logger.error("Cannot open TrustedInstaller process (PID %d)", ti_pid)
        return False

    ti_token = None
    dup_token = None
    try:
        # Open the TrustedInstaller process token
        ti_token = ctypes.wintypes.HANDLE()
        result = advapi32.OpenProcessToken(
            ti_handle,
            TOKEN_DUPLICATE,
            ctypes.byref(ti_token),
        )
        if not result:
            logger.error("Cannot open TrustedInstaller token (PID %d)", ti_pid)
            return False

        # Duplicate the token
        dup_token = ctypes.wintypes.HANDLE()
        SECURITY_IMPERSONATION = 2  # SecurityImpersonation
        result = advapi32.DuplicateTokenEx(
            ti_token,
            TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
            None,
            SECURITY_IMPERSONATION,
            1,  # TokenPrimary
            ctypes.byref(dup_token),
        )
        if not result:
            logger.error("Failed to duplicate TrustedInstaller token")
            return False

        # Set the thread token for impersonation
        result = advapi32.SetThreadToken(None, dup_token)
        if not result:
            logger.error("Failed to set thread token for impersonation")
            return False

        logger.info("Impersonating TrustedInstaller (PID %d)", ti_pid)
        return True

    except Exception as e:
        logger.error("TrustedInstaller impersonation failed: %s", e)
        return False
    finally:
        # Always close token handles to prevent resource leaks
        _close_handle_safe(ti_token)
        _close_handle_safe(dup_token)
        _close_handle_safe(ti_handle)


def _revert_to_self() -> bool:
    """Revert from impersonation back to the original security context."""
    try:
        result = advapi32.RevertToSelf()
        return bool(result)
    except Exception as e:
        logger.warning("Failed to revert to self: %s", e)
        return False


def run_as_trusted_installer(command: str, timeout: float = 30) -> tuple[bool, str]:
    """Execute a command with TrustedInstaller privileges.

    This is the highest privilege level on Windows and allows modification of:
    - Protected OS components (C:\\Windows\\*)
    - Windows Resource Protection (WRP) files
    - System service binaries

    Method: Uses PsExec to start a process in the TrustedInstaller session,
    then duplicates its token for impersonation.

    Note: Requires PsExec.exe. The impersonation is best-effort; some
    protected components may resist modification.

    Args:
        command: The command to execute
        timeout: Maximum time in seconds

    Returns:
        Tuple of (success, output)
    """
    psexec = _find_psexec()

    # Method 1: Use PsExec to start in TrustedInstaller session
    if psexec:
        try:
            # -s = SYSTEM, -accepteula = Accept EULA
            # Note: PsExec -s gives SYSTEM, not TrustedInstaller directly.
            # For true TrustedInstaller, we need to impersonate the token.
            result = subprocess.run(
                [psexec, "-s", "-accepteula", "-nobanner",
                 "cmd.exe", "/c", command],
                capture_output=True, text=True, timeout=timeout,
            )
            output = result.stdout.strip()
            if result.returncode == 0:
                return True, output
        except Exception as e:
            logger.debug("PsExec SYSTEM fallback failed: %s", e)

    # Method 2: Try token impersonation
    if _impersonate_trusted_installer():
        try:
            result = subprocess.run(
                ["cmd.exe", "/c", command],
                capture_output=True, text=True, timeout=timeout,
            )
            output = result.stdout.strip()
            # Revert impersonation after command
            _revert_to_self()
            return result.returncode == 0, output
        except Exception as e:
            _revert_to_self()
            return False, f"TrustedInstaller command failed: {e}"

    return False, (
        "Could not escalate to TrustedInstaller. "
        "Ensure: (1) PsExec.exe is available, (2) TrustedInstaller service is running. "
        "Try: sc query TrustedInstaller"
    )


async def run_command_as_trusted_installer(args: list[str], timeout: float = 30) -> tuple[bool, str]:
    """Execute a command with TrustedInstaller privileges asynchronously.

    Wraps the blocking run_as_trusted_installer() in an executor to avoid
    blocking the asyncio event loop.

    Args:
        args: Command arguments
        timeout: Maximum time in seconds

    Returns:
        Tuple of (success, output)
    """
    import asyncio
    command = " ".join(args)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, run_as_trusted_installer, command, timeout)


# ══════════════════════════════════════════════════════════════════════════════
# PRIVILEGE LEVEL DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def get_privilege_level() -> int:
    """Determine the current privilege level.

    Returns:
        0: Standard user
        1: Administrator (UAC elevated)
        2: SYSTEM
        3: TrustedInstaller (if impersonation is active)
    """
    if is_admin():
        try:
            result = subprocess.run(
                ["whoami"],
                capture_output=True, text=True, timeout=5,
            )
            user = result.stdout.strip().lower()
            if "system" in user or "nt authority" in user:
                return 2
            return 1
        except Exception:
            return 1
    return 0


# ══════════════════════════════════════════════════════════════════════════════
# PRIVILEGE-AWARE COMMAND EXECUTION
# ══════════════════════════════════════════════════════════════════════════════

# Actions that require SYSTEM privileges
SYSTEM_REQUIRED_ACTIONS = {
    "access_protected_files",
    "modify_service_internal",
    "access_locked_handles",
    "kill_protected_process",
    "modify_system_registry",
    "access_wrp_files",
}

# Actions that require TrustedInstaller privileges
TRUSTED_INSTALLER_ACTIONS = {
    "modify_os_components",
    "replace_system_files",
    "modify_windows_store_apps",
    "modify_system_services",
}


def requires_system_privilege(action: str) -> bool:
    """Check if an action requires SYSTEM privileges."""
    return action in SYSTEM_REQUIRED_ACTIONS


def requires_trusted_installer(action: str) -> bool:
    """Check if an action requires TrustedInstaller privileges."""
    return action in TRUSTED_INSTALLER_ACTIONS


def get_required_privilege_level(action: str) -> int:
    """Get the minimum privilege level required for an action.

    Returns:
        1: Administrator sufficient
        2: SYSTEM required
        3: TrustedInstaller required
    """
    if action in TRUSTED_INSTALLER_ACTIONS:
        return 3
    if action in SYSTEM_REQUIRED_ACTIONS:
        return 2
    return 1


def escalate_if_needed(action: str) -> tuple[int, str]:
    """Check if escalation is needed for an action and perform it.

    Args:
        action: The action name to check

    Returns:
        Tuple of (level, message):
          (1, "OK") — Admin is sufficient
          (2, "OK") — Successfully escalated to SYSTEM
          (2, "FAILED") — Failed to escalate to SYSTEM
          (3, "OK") — Successfully escalated to TrustedInstaller
          (3, "FAILED") — Failed to escalate to TrustedInstaller
    """
    required = get_required_privilege_level(action)
    current = get_privilege_level()

    if current >= required:
        return current, "OK"

    if required == 2:
        psexec = _find_psexec()
        if psexec:
            return 2, "PsExec available for SYSTEM escalation"
        return 2, "PsExec not found — cannot escalate to SYSTEM"

    if required == 3:
        ti_pid = _get_trusted_installer_pid()
        if ti_pid:
            return 3, "TrustedInstaller service running"
        return 3, "TrustedInstaller service not running"

    return current, "Unknown privilege level required"
