"""End-to-end test: send tool commands through daemon TCP and verify results."""

import asyncio
import sys
import os

# Ensure imports resolve
_project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.client import send_command, is_daemon_running


async def test():
    print("=== END-TO-END TEST SUITE ===")
    print()
    passed = 0
    failed = 0
    total = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed, total
        total += 1
        if condition:
            passed += 1
            print(f"  PASS: {name}")
        else:
            failed += 1
            print(f"  FAIL: {name} {detail}")

    # ── Infrastructure ──────────────────────────────────────────────
    running = await is_daemon_running()
    check("Daemon running on port 7650", running)
    if not running:
        print("\nCannot continue — daemon not running")
        return

    # ── L1 Filesystem ──────────────────────────────────────────────
    r = await send_command("filesystem", "list_directory", {"path": "."})
    check("[L1] list_directory", r.success and r.data, f"err={r.error}")

    abs_path = os.path.join(os.getcwd(), "backend", "requirements.txt")
    r = await send_command("filesystem", "read_file", {"path": abs_path})
    check("[L1] read_file", r.success and r.data, f"err={r.error}")

    # ── L2 Process ─────────────────────────────────────────────────
    r = await send_command("process", "list_processes", {"sort": "cpu"})
    check("[L2] list_processes", r.success and r.data, f"err={r.error}")

    # ── L4 Window ──────────────────────────────────────────────────
    r = await send_command("window", "list_all_windows", {})
    check("[L4] list_all_windows", r.success and r.data, f"err={r.error}")

    # ── L5 Input ───────────────────────────────────────────────────
    r = await send_command("input", "get_cursor_position", {})
    check("[L5] get_cursor_position", r.success and r.data, f"err={r.error}")

    # ── L8 System — Audio ──────────────────────────────────────────
    r = await send_command("system", "get_volume", {})
    check("[L8] get_volume", r.success, f"err={r.error}")

    # ── L8 System — Info ───────────────────────────────────────────
    r = await send_command("system", "get_system_info", {})
    check("[L8] get_system_info", r.success and r.data, f"err={r.error}")

    # ── L8 System — Network ────────────────────────────────────────
    r = await send_command("system", "test_internet", {})
    check("[L8] test_internet", r.success, f"err={r.error}")

    # ── L8 System — Time/Date ──────────────────────────────────────
    r = await send_command("system", "get_time", {})
    check("[L8] get_time", r.success and r.data, f"err={r.error}")

    r = await send_command("system", "get_date", {})
    check("[L8] get_date", r.success and r.data, f"err={r.error}")

    # ── L8 System — PowerShell ─────────────────────────────────────
    r = await send_command("system", "run_powershell", {"command": "Write-Output E2E_TEST_OK"})
    check("[L8] run_powershell", r.success and "E2E_TEST_OK" in str(r.data), f"err={r.error} data={str(r.data)[:80]}")

    # ── L8 System — Battery ────────────────────────────────────────
    r = await send_command("system", "get_battery", {})
    check("[L8] get_battery", r.success, f"err={r.error}")

    # ── L8 System — Disk ───────────────────────────────────────────
    r = await send_command("system", "get_disk_usage", {})
    check("[L8] get_disk_usage", r.success and r.data, f"err={r.error}")

    # ── L8 System — Env vars ───────────────────────────────────────
    r = await send_command("system", "get_env", {"name": "PATH"})
    check("[L8] get_env PATH", r.success, f"err={r.error}")

    # ── Fallback chain — repeat call ───────────────────────────────
    r = await send_command("system", "get_battery", {})
    check("[L8] get_battery (re-test)", r.success, f"err={r.error}")

    # ── Error handling ─────────────────────────────────────────────
    r = await send_command("system", "totally_fake_action", {})
    check("Unknown action returns error", not r.success and r.error)

    # ── Summary ────────────────────────────────────────────────────
    print()
    print(f"=== RESULTS: {passed}/{total} passed, {failed} failed ===")
    if failed == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"{failed} test(s) FAILED")
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(test())
    sys.exit(0 if ok else 1)
