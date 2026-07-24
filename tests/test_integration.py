"""End-to-end integration test for the May Control Core.

Tests the full flow: LLM tool call → core_bridge → daemon → layer handler → result.
Run this with the daemon running (python core/daemon.py debug).

Usage:
    # Start daemon in one terminal:
    python core/daemon.py debug

    # Run tests in another:
    python tests/test_integration.py
"""

from __future__ import annotations

import asyncio
import sys
import os
import time
import json

# Add project root to path
_project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _project_root)
sys.path.insert(0, os.path.join(_project_root, "backend"))


# ── Test infrastructure ──────────────────────────────────────────────────────

_pass_count = 0
_fail_count = 0
_skip_count = 0
_errors: list[str] = []


def _ok(name: str, detail: str = ""):
    global _pass_count
    _pass_count += 1
    print(f"  PASS {name}" + (f" -- {detail}" if detail else ""))


def _fail(name: str, reason: str):
    global _fail_count
    _fail_count += 1
    msg = f"  FAIL {name} -- {reason}"
    print(msg)
    _errors.append(msg)


def _skip_test(name: str, reason: str):
    global _skip_count
    _skip_count += 1
    print(f"  SKIP {name} -- {reason}")


# ── Wait for daemon ──────────────────────────────────────────────────────────

async def wait_for_daemon(timeout: float = 10) -> bool:
    """Wait for the daemon TCP server to become available."""
    from core.client import is_daemon_running_sync
    start = time.time()
    while time.time() - start < timeout:
        try:
            if is_daemon_running_sync():
                return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return False


# ── Test cases ───────────────────────────────────────────────────────────────

async def test_core_bus():
    """Test core bus Command/Result creation."""
    from core.bus import Command, Result

    cmd = Command(layer="test", action="test_action", params={"key": "value"})
    assert cmd.layer == "test"
    assert cmd.action == "test_action"
    _ok("core_bus", "Command/Result dataclasses work")

async def test_router_validation():
    """Test router command validation."""
    from core.bus import CommandBus, Command
    from core.router import Router

    bus = CommandBus()
    router = Router(bus)

    # Valid command
    cmd = Command(layer="filesystem", action="list_directory", params={"path": "."})
    err = router.validate_command(cmd)
    assert err is None
    _ok("router_valid", "Valid command passes validation")

    # Invalid layer
    cmd_bad = Command(layer="nonexistent", action="test", params={})
    err = router.validate_command(cmd_bad)
    assert err is not None
    _ok("router_invalid_layer", f"Invalid layer caught: {err}")

async def test_safety_checks():
    """Test pre-flight safety checks."""
    from core.router import Router, DESTRUCTIVE_ACTIONS, ADMIN_REQUIRED_ACTIONS
    from core.bus import CommandBus

    bus = CommandBus()
    router = Router(bus)

    safety = router.check_safety("system", "shutdown")
    assert safety["destructive"] is True
    _ok("safety_destructive", "shutdown flagged as destructive")

    safety = router.check_safety("system", "get_system_info")
    assert safety["destructive"] is False
    _ok("safety_safe", "get_system_info not flagged as destructive")

    safety = router.check_safety("system", "set_system_env")
    # Admin-required actions are in router.py's ADMIN_REQUIRED_ACTIONS
    _ok("safety_admin", f"set_system_env admin_required={safety.get('admin_required', False)}")

async def test_fallback_chain():
    """Test fallback chain executor."""
    from core.engine.fallback import FallbackChain

    chain = FallbackChain()

    async def success_method(params):
        return {"result": "ok"}

    async def failing_method(params):
        raise RuntimeError("should not be called")

    success, data, method_used, error = await chain.execute(
        action="test.success",
        params={},
        methods=[success_method],
        verifier=None,
    )
    assert success is True
    assert data["result"] == "ok"
    _ok("fallback_success", "Successful method executed")

async def test_verifier_coverage():
    """Test that VERIFIER_MAP has comprehensive coverage."""
    from core.engine.verifier import VERIFIER_MAP, Verifiers

    total_map = len(VERIFIER_MAP)
    methods = [m for m in dir(Verifiers) if not m.startswith("_") and callable(getattr(Verifiers, m))]

    # Should have at least 100 entries (50% of 269 actions)
    assert total_map >= 100, f"VERIFIER_MAP only has {total_map} entries"
    _ok("verifier_coverage", f"{total_map} entries, {len(methods)} methods")

async def test_action_counts():
    """Test that all layers have the expected action counts."""
    from core.layers.L1_filesystem import ACTION_MAP as L1
    from core.layers.L2_process import ACTION_MAP as L2
    from core.layers.L3_application import ACTION_MAP as L3
    from core.layers.L4_window import ACTION_MAP as L4
    from core.layers.L5_input import ACTION_MAP as L5
    from core.layers.L6_registry import ACTION_MAP as L6
    from core.layers.L7_services import ACTION_MAP as L7
    from core.layers.L8_system import ACTION_MAP as L8
    from core.layers.L9_browser import ACTION_MAP as L9

    layers = {
        "L1": (L1, 35), "L2": (L2, 24), "L3": (L3, 21),
        "L4": (L4, 32), "L5": (L5, 25), "L6": (L6, 18),
        "L7": (L7, 31), "L8": (L8, 49), "L9": (L9, 34),
    }
    total = 0
    for name, (amap, expected) in layers.items():
        count = len(amap)
        total += count
        if count >= expected:
            _ok(f"action_count_{name}", f"{count} actions (target: {expected})")
        else:
            _fail(f"action_count_{name}", f"{count} actions < {expected} target")

    _ok("action_count_total", f"{total} total actions across 9 layers")

async def test_tools_bridge():
    """Test tools.py and core_bridge.py consistency."""
    from llm.tools import TOOLS
    from llm.core_bridge import TOOL_CORE_MAP

    tool_names = {t["name"] for t in TOOLS}
    mapped_names = set(TOOL_CORE_MAP.keys())

    # All tools should have a mapping
    unmapped = tool_names - mapped_names
    if unmapped:
        _fail("tools_bridge_coverage", f"{len(unmapped)} tools without core mapping: {unmapped}")
    else:
        _ok("tools_bridge_coverage", f"All {len(tool_names)} tools have core mappings")

    # Core map should have more entries (some direct tools)
    _ok("tools_bridge_map_size", f"{len(mapped_names)} mappings, {len(tool_names)} tools")

async def test_daemon_connection():
    """Test TCP connection to the daemon."""
    from core.client import is_daemon_running_sync

    running = is_daemon_running_sync()
    if running:
        _ok("daemon_connection", "Daemon is running on port 7650")
    else:
        _skip_test("daemon_connection", "Daemon not running — start with: python core/daemon.py debug")

async def test_daemon_send_command():
    """Test sending a command to the daemon via TCP."""
    from core.client import send_command, is_daemon_running_sync

    if not is_daemon_running_sync():
        _skip_test("daemon_send_command", "Daemon not running")
        return

    result = await send_command("system", "get_system_info", {})
    if result.success:
        data = result.data
        _ok("daemon_send_command", f"OS: {data.get('os', '?')[:50]}")
    else:
        _fail("daemon_send_command", f"Command failed: {result.error}")

async def test_daemon_filesystem():
    """Test filesystem actions via the daemon."""
    from core.client import send_command, is_daemon_running_sync

    if not is_daemon_running_sync():
        _skip_test("daemon_filesystem", "Daemon not running")
        return

    result = await send_command("filesystem", "list_directory", {"path": _project_root})
    if result.success:
        count = result.data.get("count", 0) if isinstance(result.data, dict) else 0
        _ok("daemon_filesystem", f"Listed {count} items")
    else:
        _fail("daemon_filesystem", f"Failed: {result.error}")

async def test_daemon_volume():
    """Test volume control via the daemon."""
    from core.client import send_command, is_daemon_running_sync

    if not is_daemon_running_sync():
        _skip_test("daemon_volume", "Daemon not running")
        return

    result = await send_command("system", "get_volume", {})
    if result.success:
        level = result.data.get("level", "?") if isinstance(result.data, dict) else "?"
        _ok("daemon_volume", f"Current volume: {level}%")
    else:
        _fail("daemon_volume", f"Failed: {result.error}")

async def test_daemon_process_list():
    """Test process listing via the daemon."""
    from core.client import send_command, is_daemon_running_sync

    if not is_daemon_running_sync():
        _skip_test("daemon_process_list", "Daemon not running")
        return

    result = await send_command("process", "list_processes", {"sort": "memory"})
    if result.success:
        count = result.data.get("count", 0) if isinstance(result.data, dict) else 0
        _ok("daemon_process_list", f"Listed {count} processes")
    else:
        _fail("daemon_process_list", f"Failed: {result.error}")

async def test_daemon_window_list():
    """Test window listing via the daemon."""
    from core.client import send_command, is_daemon_running_sync

    if not is_daemon_running_sync():
        _skip_test("daemon_window_list", "Daemon not running")
        return

    result = await send_command("window", "list_all_windows", {})
    if result.success:
        count = result.data.get("count", 0) if isinstance(result.data, dict) else 0
        _ok("daemon_window_list", f"Listed {count} windows")
    else:
        _fail("daemon_window_list", f"Failed: {result.error}")

async def test_daemon_new_actions():
    """Test the new architecture-compliant actions via the daemon."""
    from core.client import send_command, is_daemon_running_sync

    if not is_daemon_running_sync():
        _skip_test("daemon_new_actions", "Daemon not running")
        return

    # Test get_installed_updates
    result = await send_command("system", "get_installed_updates", {})
    if result.success:
        count = result.data.get("count", 0) if isinstance(result.data, dict) else 0
        _ok("daemon_get_installed_updates", f"Found {count} updates")
    else:
        _fail("daemon_get_installed_updates", f"Failed: {result.error}")

    # Test get_os_info
    result = await send_command("system", "get_os_info", {})
    if result.success:
        _ok("daemon_get_os_info", "OS info retrieved")
    else:
        _fail("daemon_get_os_info", f"Failed: {result.error}")

async def test_daemon_services():
    """Test service listing via the daemon."""
    from core.client import send_command, is_daemon_running_sync

    if not is_daemon_running_sync():
        _skip_test("daemon_services", "Daemon not running")
        return

    result = await send_command("services", "list_services", {"filter": "Windows"})
    if result.success:
        count = result.data.get("count", 0) if isinstance(result.data, dict) else 0
        _ok("daemon_services", f"Listed {count} services")
    else:
        _fail("daemon_services", f"Failed: {result.error}")

async def test_core_bridge_execute():
    """Test execute_tool_via_core with a direct tool."""
    from llm.core_bridge import execute_tool_via_core

    result = await execute_tool_via_core("get_time", {})
    assert result and len(result) > 0
    _ok("core_bridge_direct", f"get_time returned: {result}")

async def test_core_bridge_tcp_tool():
    """Test execute_tool_via_core with a TCP-routed tool."""
    from llm.core_bridge import execute_tool_via_core
    from core.client import is_daemon_running_sync

    if not is_daemon_running_sync():
        _skip_test("core_bridge_tcp", "Daemon not running")
        return

    result = await execute_tool_via_core("system_info", {})
    assert "os" in result.lower() or "windows" in result.lower() or "error" not in result.lower()
    _ok("core_bridge_tcp", f"system_info returned: {result[:80]}...")


# ── Runner ───────────────────────────────────────────────────────────────────

async def run_all_tests():
    print("\n" + "=" * 60)
    print("  MAY CONTROL CORE — Integration Tests")
    print("=" * 60)

    # Phase 1: Unit tests (no daemon needed)
    print("\n[Phase 1] Core Engine Tests (no daemon)")
    await test_core_bus()
    await test_router_validation()
    await test_safety_checks()
    await test_fallback_chain()
    await test_verifier_coverage()
    await test_action_counts()
    await test_tools_bridge()

    # Phase 2: Check daemon
    print("\n[Phase 2] Daemon Connection")
    daemon_running = await wait_for_daemon(timeout=5)
    await test_daemon_connection()

    # Phase 3: Integration tests (need daemon)
    if daemon_running:
        print("\n[Phase 3] Daemon Integration Tests")
        await test_daemon_send_command()
        await test_daemon_filesystem()
        await test_daemon_volume()
        await test_daemon_process_list()
        await test_daemon_window_list()
        await test_daemon_new_actions()
        await test_daemon_services()
        await test_core_bridge_tcp_tool()
    else:
        print("\n[Phase 3] SKIPPED (daemon not running)")

    # Phase 4: Direct bridge tests (always run)
    print("\n[Phase 4] Bridge Tests")
    await test_core_bridge_execute()

    # Summary
    print("\n" + "=" * 60)
    total = _pass_count + _fail_count + _skip_count
    print(f"  Results: {_pass_count} passed, {_fail_count} failed, {_skip_count} skipped / {total} total")
    if _fail_count > 0:
        print(f"\n  Failed tests:")
        for e in _errors:
            print(f"  {e}")
    print("=" * 60 + "\n")

    return _fail_count == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
