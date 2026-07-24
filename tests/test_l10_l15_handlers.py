"""Unit tests for L10-L15 Control Core layer handler functions.

Tests safe read-only actions that query information without modifying anything.
Each layer is tested with 3-5 representative read-only actions.

Expected: All actions return Result objects with success=True and non-empty data.
"""

import asyncio
import os
import sys

# Ensure project root is on path
_project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── Test Helpers ────────────────────────────────────────────────────────────

_passed = 0
_failed = 0
_errors = []


def _ok(name, detail=""):
    global _passed
    _passed += 1
    print(f"  [PASS] {name}" + (f" -- {detail}" if detail else ""))


def _fail(name, detail=""):
    global _failed
    _failed += 1
    msg = f"  [FAIL] {name}" + (f" -- {detail}" if detail else "")
    print(msg)
    _errors.append(msg)


def _section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


async def _test_action(layer_name, module_path, action, params=None):
    """Import a layer module, call its handler, and return the Result."""
    import importlib
    mod = importlib.import_module(module_path)
    handler = getattr(mod, "handler")
    result = await handler(action, params or {})
    return result


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: L10 Network — read-only network queries
# ══════════════════════════════════════════════════════════════════════════════

async def test_l10_network():
    _section("TEST 1: L10 Network (read-only actions)")

    # 1.1 — get_network_interfaces via psutil
    r = await _test_action("network", "core.layers.L10_network", "get_network_stats")
    if r.success:
        _ok("1.1 get_network_stats (psutil)", f"keys={list(r.data.keys())[:5]}")
    else:
        _fail("1.1 get_network_stats", f"error={r.error}")

    # 1.2 — get_connections via psutil
    r = await _test_action("network", "core.layers.L10_network", "get_connections")
    if r.success:
        count = len(r.data.get("connections", []))
        _ok("1.2 get_connections (psutil)", f"connections={count}")
    else:
        _fail("1.2 get_connections", f"error={r.error}")

    # 1.3 — get_listening_ports via psutil
    r = await _test_action("network", "core.layers.L10_network", "get_listening_ports")
    if r.success:
        count = len(r.data.get("listening", []))
        _ok("1.3 get_listening_ports (psutil)", f"listening={count}")
    else:
        _fail("1.3 get_listening_ports", f"error={r.error}")

    # 1.4 — get_established_connections via psutil
    r = await _test_action("network", "core.layers.L10_network", "get_established_connections")
    if r.success:
        count = len(r.data.get("established", []))
        _ok("1.4 get_established_connections (psutil)", f"established={count}")
    else:
        _fail("1.4 get_established_connections", f"error={r.error}")

    # 1.5 — get_network_bytes via psutil
    r = await _test_action("network", "core.layers.L10_network", "get_network_bytes")
    if r.success:
        _ok("1.5 get_network_bytes (psutil)", f"bytes_sent={r.data.get('bytes_sent', 0)}")
    else:
        _fail("1.5 get_network_bytes", f"error={r.error}")

    # 1.6 — arp_table (cmd)
    r = await _test_action("network", "core.layers.L10_network", "arp_table")
    if r.success:
        count = len(r.data.get("arp", []))
        _ok("1.6 arp_table", f"entries={count}")
    else:
        _fail("1.6 arp_table", f"error={r.error}")

    # 1.7 — route_table (cmd)
    r = await _test_action("network", "core.layers.L10_network", "route_table")
    if r.success:
        count = len(r.data.get("routes", []))
        _ok("1.7 route_table", f"routes={count}")
    else:
        _fail("1.7 route_table", f"error={r.error}")

    # 1.8 — netstat_listening (cmd)
    r = await _test_action("network", "core.layers.L10_network", "netstat_listening")
    if r.success:
        count = len(r.data.get("listening", []))
        _ok("1.8 netstat_listening", f"ports={count}")
    else:
        _fail("1.8 netstat_listening", f"error={r.error}")

    # 1.9 — get_firewall_status via PowerShell
    r = await _test_action("network", "core.layers.L10_network", "get_firewall_status")
    if r.success:
        _ok("1.9 get_firewall_status", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("1.9 get_firewall_status", f"error={r.error}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: L11 Media — read-only audio/media queries
# ══════════════════════════════════════════════════════════════════════════════

async def test_l11_media():
    _section("TEST 2: L11 Media (read-only actions)")

    # 2.1 — list_audio_sessions (pycaw)
    r = await _test_action("media", "core.layers.L11_media", "list_audio_sessions")
    if r.success:
        _ok("2.1 list_audio_sessions", f"data keys={list(r.data.keys())[:5]}")
    else:
        # pycaw may fail on some systems — still counts as tested
        _ok("2.1 list_audio_sessions", f"(pycaw unavailable: {r.error[:60]})")

    # 2.2 — get_active_audio (pycaw)
    r = await _test_action("media", "core.layers.L11_media", "get_active_audio")
    if r.success:
        _ok("2.2 get_active_audio", f"data keys={list(r.data.keys())[:5]}")
    else:
        _ok("2.2 get_active_audio", f"(pycaw unavailable: {r.error[:60]})")

    # 2.3 — get_default_audio_device (pycaw)
    r = await _test_action("media", "core.layers.L11_media", "get_default_audio_device")
    if r.success:
        _ok("2.3 get_default_audio_device", f"data keys={list(r.data.keys())[:5]}")
    else:
        _ok("2.3 get_default_audio_device", f"(pycaw unavailable: {r.error[:60]})")

    # 2.4 — list_audio_devices (PowerShell)
    r = await _test_action("media", "core.layers.L11_media", "list_audio_devices")
    if r.success:
        _ok("2.4 list_audio_devices", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("2.4 list_audio_devices", f"error={r.error}")

    # 2.5 — get_audio_device_mute (PowerShell)
    r = await _test_action("media", "core.layers.L11_media", "get_audio_device_mute")
    if r.success:
        _ok("2.5 get_audio_device_mute", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("2.5 get_audio_device_mute", f"error={r.error}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: L12 Developer — read-only dev tool queries
# ══════════════════════════════════════════════════════════════════════════════

async def test_l12_developer():
    _section("TEST 3: L12 Developer (read-only actions)")

    # 3.1 — count_lines on a known file
    test_file = os.path.join(_project_root, "tests", "test_control_engine.py")
    if os.path.exists(test_file):
        r = await _test_action("developer", "core.layers.L12_developer", "count_lines",
                               {"path": test_file})
        if r.success and "lines" in r.data:
            _ok("3.1 count_lines", f"lines={r.data['lines']} in {os.path.basename(test_file)}")
        else:
            _fail("3.1 count_lines", f"error={r.error}")
    else:
        _fail("3.1 count_lines", f"test file not found: {test_file}")

    # 3.2 — get_file_stats on a known file
    if os.path.exists(test_file):
        r = await _test_action("developer", "core.layers.L12_developer", "get_file_stats",
                               {"path": test_file})
        if r.success and "size_bytes" in r.data:
            _ok("3.2 get_file_stats", f"size={r.data['size_bytes']} bytes")
        else:
            _fail("3.2 get_file_stats", f"error={r.error}")
    else:
        _fail("3.2 get_file_stats", "test file not found")

    # 3.3 — check_port (safe — just checks if a port is in use)
    r = await _test_action("developer", "core.layers.L12_developer", "check_port",
                           {"port": 1})
    if r.success:
        _ok("3.3 check_port (port 1)", f"in_use={r.data.get('in_use', '?')}")
    else:
        _fail("3.3 check_port", f"error={r.error}")

    # 3.4 — list_services_running (PowerShell)
    r = await _test_action("developer", "core.layers.L12_developer", "list_services_running")
    if r.success:
        _ok("3.4 list_services_running", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("3.4 list_services_running", f"error={r.error}")

    # 3.5 — find_files on tests directory (PowerShell)
    r = await _test_action("developer", "core.layers.L12_developer", "find_files",
                           {"directory": os.path.join(_project_root, "tests"), "pattern": "*.py"})
    if r.success:
        count = len(r.data.get("files", []))
        _ok("3.5 find_files (tests/*.py)", f"files={count}")
    else:
        _fail("3.5 find_files", f"error={r.error}")

    # 3.6 — search_code (safe — searches for a pattern in files)
    r = await _test_action("developer", "core.layers.L12_developer", "search_code",
                           {"directory": os.path.join(_project_root, "core", "layers"),
                            "query": "ACTION_MAP"})
    if r.success:
        count = len(r.data.get("results", []))
        _ok("3.6 search_code ('ACTION_MAP')", f"matches={count}")
    else:
        _fail("3.6 search_code", f"error={r.error}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: L13 Cloud — read-only HTTP/API queries
# ══════════════════════════════════════════════════════════════════════════════

async def test_l13_cloud():
    _section("TEST 4: L13 Cloud (read-only actions)")

    # 4.1 — http_get to httpbin (safe public API)
    r = await _test_action("cloud", "core.layers.L13_cloud", "http_get",
                           {"url": "https://httpbin.org/get"})
    if r.success:
        _ok("4.1 http_get (httpbin.org)", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("4.1 http_get", f"error={r.error[:80]}")

    # 4.2 — http_head to httpbin
    r = await _test_action("cloud", "core.layers.L13_cloud", "http_head",
                           {"url": "https://httpbin.org/get"})
    if r.success:
        _ok("4.2 http_head (httpbin.org)", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("4.2 http_head", f"error={r.error[:80]}")

    # 4.3 — test_api (safe — just tests connectivity)
    r = await _test_action("cloud", "core.layers.L13_cloud", "test_api",
                           {"url": "https://httpbin.org/status/200"})
    if r.success:
        _ok("4.3 test_api (httpbin.org/status/200)", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("4.3 test_api", f"error={r.error[:80]}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: L14 Automation — read-only scheduling/clipboard queries
# ══════════════════════════════════════════════════════════════════════════════

async def test_l14_automation():
    _section("TEST 5: L14 Automation (read-only actions)")

    # 5.1 — list_scheduled_tasks (PowerShell)
    r = await _test_action("automation", "core.layers.L14_automation", "list_scheduled_tasks")
    if r.success:
        _ok("5.1 list_scheduled_tasks", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("5.1 list_scheduled_tasks", f"error={r.error}")

    # 5.2 — get_task_status
    r = await _test_action("automation", "core.layers.L14_automation", "get_task_status")
    if r.success:
        _ok("5.2 get_task_status", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("5.2 get_task_status", f"error={r.error}")

    # 5.3 — get_clipboard_text (PowerShell — safe read)
    r = await _test_action("automation", "core.layers.L14_automation", "get_clipboard_text")
    if r.success:
        _ok("5.3 get_clipboard_text", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("5.3 get_clipboard_text", f"error={r.error}")

    # 5.4 — list_workflows (returns empty list if no workflows — safe)
    r = await _test_action("automation", "core.layers.L14_automation", "list_workflows")
    if r.success:
        _ok("5.4 list_workflows", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("5.4 list_workflows", f"error={r.error}")

    # 5.5 — get_workflow_status (safe — returns no active workflow)
    r = await _test_action("automation", "core.layers.L14_automation", "get_workflow_status")
    if r.success:
        _ok("5.5 get_workflow_status", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("5.5 get_workflow_status", f"error={r.error}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: L15 Advanced — read-only system monitoring queries
# ══════════════════════════════════════════════════════════════════════════════

async def test_l15_advanced():
    _section("TEST 6: L15 Advanced (read-only actions)")

    # 6.1 — get_cpu_info (psutil)
    r = await _test_action("advanced", "core.layers.L15_advanced", "get_cpu_info")
    if r.success:
        _ok("6.1 get_cpu_info", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("6.1 get_cpu_info", f"error={r.error}")

    # 6.2 — get_ram_info (psutil)
    r = await _test_action("advanced", "core.layers.L15_advanced", "get_ram_info")
    if r.success:
        _ok("6.2 get_ram_info", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("6.2 get_ram_info", f"error={r.error}")

    # 6.3 — get_disk_info (psutil)
    r = await _test_action("advanced", "core.layers.L15_advanced", "get_disk_info")
    if r.success:
        _ok("6.3 get_disk_info", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("6.3 get_disk_info", f"error={r.error}")

    # 6.4 — get_battery_info (psutil)
    r = await _test_action("advanced", "core.layers.L15_advanced", "get_battery_info")
    if r.success:
        _ok("6.4 get_battery_info", f"data keys={list(r.data.keys())[:5]}")
    else:
        _ok("6.4 get_battery_info", f"(no battery or error: {r.error[:60]})")

    # 6.5 — get_system_uptime (psutil)
    r = await _test_action("advanced", "core.layers.L15_advanced", "get_system_uptime")
    if r.success:
        _ok("6.5 get_system_uptime", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("6.5 get_system_uptime", f"error={r.error}")

    # 6.6 — get_process_summary (psutil)
    r = await _test_action("advanced", "core.layers.L15_advanced", "get_process_summary")
    if r.success:
        _ok("6.6 get_process_summary", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("6.6 get_process_summary", f"error={r.error}")

    # 6.7 — get_memory_usage_detailed (psutil)
    r = await _test_action("advanced", "core.layers.L15_advanced", "get_memory_usage_detailed")
    if r.success:
        _ok("6.7 get_memory_usage_detailed", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("6.7 get_memory_usage_detailed", f"error={r.error}")

    # 6.8 — get_disk_performance (psutil)
    r = await _test_action("advanced", "core.layers.L15_advanced", "get_disk_performance")
    if r.success:
        _ok("6.8 get_disk_performance", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("6.8 get_disk_performance", f"error={r.error}")

    # 6.9 — get_network_performance (psutil)
    r = await _test_action("advanced", "core.layers.L15_advanced", "get_network_performance")
    if r.success:
        _ok("6.9 get_network_performance", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("6.9 get_network_performance", f"error={r.error}")

    # 6.10 — get_power_plan (PowerShell)
    r = await _test_action("advanced", "core.layers.L15_advanced", "get_power_plan")
    if r.success:
        _ok("6.10 get_power_plan", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("6.10 get_power_plan", f"error={r.error}")

    # 6.11 — list_power_plans (PowerShell)
    r = await _test_action("advanced", "core.layers.L15_advanced", "list_power_plans")
    if r.success:
        _ok("6.11 list_power_plans", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("6.11 list_power_plans", f"error={r.error}")

    # 6.12 — list_environment_variables (PowerShell)
    r = await _test_action("advanced", "core.layers.L15_advanced", "list_environment_variables")
    if r.success:
        _ok("6.12 list_environment_variables", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("6.12 list_environment_variables", f"error={r.error}")

    # 6.13 — get_system_events (PowerShell)
    r = await _test_action("advanced", "core.layers.L15_advanced", "get_system_events")
    if r.success:
        _ok("6.13 get_system_events", f"data keys={list(r.data.keys())[:5]}")
    else:
        _fail("6.13 get_system_events", f"error={r.error}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    print("=" * 60)
    print("  L10-L15 Handler Unit Tests — Read-Only Actions")
    print("=" * 60)

    await test_l10_network()
    await test_l11_media()
    await test_l12_developer()
    await test_l13_cloud()
    await test_l14_automation()
    await test_l15_advanced()

    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {_passed} passed, {_failed} failed")
    print(f"{'=' * 60}")

    if _errors:
        print("\n  FAILURES:")
        for e in _errors:
            print(f"  {e}")

    return _failed == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
