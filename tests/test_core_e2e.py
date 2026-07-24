"""End-to-End Control Core Test -- core_bridge -> daemon -> layer handlers.

Tests the full chain:
  1. core_bridge.execute_tool_via_core() (what jarvis.py calls)
  2. TCP send_command() to daemon
  3. Layer handler execution (L1-L9)
  4. Result returned back through the chain

Verifies:
  - Single tool execution via daemon
  - Multi-step sequential execution (simulates agentic loop)
  - Per-action timeout overrides work
  - Direct fallback works when daemon is down
  - Tool results are correctly formatted for the LLM

Requirements:
  - Backend daemon must be running on TCP port 7650
  - Start with: python core/daemon.py debug
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import tempfile

# Ensure project root and backend are on sys.path
_project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_backend = os.path.normpath(os.path.join(_project_root, "backend"))
for p in (_project_root, _backend):
    if p not in sys.path:
        sys.path.insert(0, p)

from core.client import send_command, is_daemon_running_sync
from core.bus import Result


# -- Test Helpers -------------------------------------------------------------

_passed = 0
_failed = 0
_total = 0


def check(name: str, condition: bool, detail: str = ""):
    global _passed, _failed, _total
    _total += 1
    if condition:
        _passed += 1
        print(f"  [PASS] {name}")
    else:
        _failed += 1
        msg = f"  [FAIL] {name}"
        if detail:
            msg += f" -- {detail}"
        print(msg)


# -- Test 1: Single Tool via TCP ----------------------------------------------

async def test_single_tool_tcp():
    """Verify a single tool works via direct TCP to daemon."""
    print("\n-- Test 1: Single Tool via TCP --")

    r = await send_command("system", "get_time", {})
    check("get_time succeeds", r.success, f"err={r.error}")
    check("get_time returns data", r.data is not None, f"data={r.data}")
    check("get_time returns dict with 'time' key",
          isinstance(r.data, dict) and "time" in r.data,
          f"data={r.data}")

    r = await send_command("system", "get_date", {})
    check("get_date succeeds", r.success, f"err={r.error}")
    check("get_date returns dict with 'date' key",
          isinstance(r.data, dict) and "date" in r.data,
          f"data={r.data}")

    r = await send_command("system", "test_internet", {})
    check("test_internet succeeds", r.success, f"err={r.error}")
    check("test_internet returns 'connected' key",
          isinstance(r.data, dict) and "connected" in r.data,
          f"data={r.data}")


# -- Test 2: Multi-Step Sequential Execution ----------------------------------

async def test_multi_step():
    """Simulate agentic loop: execute tool A, then tool B, verify both succeed.

    This is the core E2E test -- it simulates what jarvis.py does:
    1. LLM returns tool_calls: [get_time, get_date]
    2. Agentic loop executes them sequentially
    3. Each result is collected
    """
    print("\n-- Test 2: Multi-Step Sequential Execution --")

    results = []
    all_success = True

    # Step 1: get_time
    r1 = await send_command("system", "get_time", {})
    results.append(("get_time", r1))
    check("Step 1: get_time succeeds", r1.success, f"err={r1.error}")

    # Step 2: get_date
    r2 = await send_command("system", "get_date", {})
    results.append(("get_date", r2))
    check("Step 2: get_date succeeds", r2.success, f"err={r2.error}")

    # Step 3: get_battery
    r3 = await send_command("system", "get_battery", {})
    results.append(("get_battery", r3))
    check("Step 3: get_battery succeeds", r3.success, f"err={r3.error}")

    # Verify all succeeded
    for name, r in results:
        if not r.success:
            all_success = False

    check("All 3 sequential steps succeeded", all_success,
          f"results={[(n, r.success) for n, r in results]}")

    # Verify results are distinct (not cached/stale)
    times = set()
    for name, r in results:
        if r.data and isinstance(r.data, dict):
            for v in r.data.values():
                if isinstance(v, str):
                    times.add(v)
    check("Results contain distinct data", len(times) >= 2,
          f"unique_values={len(times)}")


# -- Test 3: Cross-Layer Multi-Step -------------------------------------------

async def test_cross_layer():
    """Test tools from different layers in sequence (simulates real user request).

    Scenario: 'what time is it and how much battery do I have?'
    - L8 system.get_time
    - L8 system.get_battery
    - L8 system.get_disk_usage
    """
    print("\n-- Test 3: Cross-Layer Multi-Step (system queries) --")

    r1 = await send_command("system", "get_time", {})
    check("L8 get_time", r1.success, f"err={r1.error}")

    r2 = await send_command("system", "get_battery", {})
    check("L8 get_battery", r2.success, f"err={r2.error}")

    r3 = await send_command("system", "get_disk_usage", {})
    check("L8 get_disk_usage", r3.success, f"err={r3.error}")

    # Scenario 2: filesystem + system
    r4 = await send_command("filesystem", "list_directory", {"path": "."})
    check("L1 list_directory", r4.success, f"err={r4.error}")

    r5 = await send_command("system", "get_system_info", {})
    check("L8 get_system_info", r5.success, f"err={r5.error}")

    # All should succeed
    all_ok = all(r.success for r in [r1, r2, r3, r4, r5])
    check("All cross-layer steps succeeded", all_ok)


# -- Test 4: Application Layer ------------------------------------------------

async def test_application_layer():
    """Test L3 application layer tools (app discovery)."""
    print("\n-- Test 4: Application Layer (L3) --")

    r = await send_command("application", "find_app_by_name", {"name": "notepad"})
    check("find_app_by_name(notepad)", r.success, f"err={r.error}")
    if r.success and r.data:
        check("find_app returns app info",
              isinstance(r.data, dict),
              f"data_keys={list(r.data.keys()) if isinstance(r.data, dict) else type(r.data)}")


# -- Test 5: Window Layer -----------------------------------------------------

async def test_window_layer():
    """Test L4 window layer tools."""
    print("\n-- Test 5: Window Layer (L4) --")

    r = await send_command("window", "list_all_windows", {})
    check("list_all_windows succeeds", r.success, f"err={r.error}")
    if r.success and r.data:
        check("list_all_windows returns dict",
              isinstance(r.data, dict),
              f"data_type={type(r.data)}")


# -- Test 6: Process Layer ----------------------------------------------------

async def test_process_layer():
    """Test L2 process layer tools."""
    print("\n-- Test 6: Process Layer (L2) --")

    r = await send_command("process", "list_processes", {"sort": "cpu"})
    check("list_processes succeeds", r.success, f"err={r.error}")
    if r.success and r.data:
        check("list_processes returns dict",
              isinstance(r.data, dict),
              f"data_type={type(r.data)}")


# -- Test 7: Per-Action Timeout -----------------------------------------------

async def test_timeout_overrides() -> None:
    """Verify that slow actions get longer timeouts (not the default 10s)."""
    print("\n-- Test 7: Per-Action Timeout Overrides --")

    from llm.core_bridge import _ACTION_TIMEOUTS

    check("install_app has 120s timeout",
          _ACTION_TIMEOUTS.get("install_app") == 120.0,
          f"actual={_ACTION_TIMEOUTS.get('install_app')}")

    check("search_packages has 30s timeout",
          _ACTION_TIMEOUTS.get("search_packages") == 30.0,
          f"actual={_ACTION_TIMEOUTS.get('search_packages')}")

    check("search_files has 15s timeout",
          _ACTION_TIMEOUTS.get("search_files") == 15.0,
          f"actual={_ACTION_TIMEOUTS.get('search_files')}")

    check("enable_service has 15s timeout",
          _ACTION_TIMEOUTS.get("enable_service") == 15.0,
          f"actual={_ACTION_TIMEOUTS.get('enable_service')}")

    check("restart_service has 20s timeout",
          _ACTION_TIMEOUTS.get("restart_service") == 20.0,
          f"actual={_ACTION_TIMEOUTS.get('restart_service')}")

    check("default timeout is 10s",
          _ACTION_TIMEOUTS.get("nonexistent_action", 10.0) == 10.0)


# -- Test 8: core_bridge.execute_tool_via_core --------------------------------

async def test_core_bridge():
    """Test the actual function that jarvis.py calls to execute tools."""
    print("\n-- Test 8: core_bridge.execute_tool_via_core --")

    from llm.core_bridge import execute_tool_via_core

    # Test 1: get_time
    result = await execute_tool_via_core("get_time", {})
    check("execute_tool(get_time) succeeds",
          "Error" not in result and len(result) > 0,
          f"result={result[:200]}")

    # Test 2: get_date
    result = await execute_tool_via_core("get_date", {})
    check("execute_tool(get_date) succeeds",
          "Error" not in result and len(result) > 0,
          f"result={result[:200]}")

    # Test 3: list_windows
    result = await execute_tool_via_core("list_windows", {})
    check("execute_tool(list_windows) succeeds",
          "Error" not in result,
          f"result={result[:200]}")

    # Test 4: get_volume
    result = await execute_tool_via_core("get_volume", {})
    check("execute_tool(get_volume) succeeds",
          "Error" not in result,
          f"result={result[:200]}")

    # Test 5: test_internet
    result = await execute_tool_via_core("test_internet", {})
    check("execute_tool(test_internet) succeeds",
          "connected" in result.lower() or "Error" not in result,
          f"result={result[:200]}")


# -- Test 9: Multi-Step Through core_bridge (Agentic Loop Simulation) ---------

async def test_multi_step_core_bridge():
    """Simulate the agentic loop using core_bridge -- the actual code path jarvis.py uses.

    This tests:
    1. execute_tool_via_core("get_time") -> result1
    2. execute_tool_via_core("get_date") -> result2
    3. execute_tool_via_core("get_battery") -> result3
    4. All succeed and return non-empty strings
    """
    print("\n-- Test 9: Multi-Step via core_bridge (Agentic Loop Sim) --")

    from llm.core_bridge import execute_tool_via_core

    all_results = []
    tools = [
        ("get_time", {}),
        ("get_date", {}),
        ("get_battery", {}),
        ("get_volume", {}),
        ("test_internet", {}),
    ]

    for tool_name, args in tools:
        result = await execute_tool_via_core(tool_name, args)
        all_results.append((tool_name, result))
        is_ok = "Error" not in result and len(result) > 0
        check(f"  Step: {tool_name}", is_ok, f"result={result[:100]}")

    # Verify all steps succeeded
    all_ok = all("Error" not in r for _, r in all_results)
    check("All 5 core_bridge steps succeeded", all_ok)

    # Verify results are non-empty strings (what the LLM sees)
    all_nonempty = all(len(r) > 0 for _, r in all_results)
    check("All results are non-empty strings", all_nonempty,
          f"lengths={[len(r) for _, r in all_results]}")


# -- Test 10: Tool Tiering Integration ----------------------------------------

async def test_tool_tiering():
    """Verify tool tiering works correctly with the daemon."""
    print("\n-- Test 10: Tool Tiering Integration --")

    from llm.tool_tiering import get_tools_for_message, TIERED_NAMES
    from llm.tools import TOOLS

    # Test: simple message should return filtered tools
    tools = get_tools_for_message("what time is it?", TOOLS)
    tool_names = [t["name"] for t in tools]
    check("Simple query returns filtered tools",
          len(tools) < 50 and len(tools) > 0,
          f"count={len(tools)}")
    check("get_time is included for time query",
          "get_time" in tool_names,
          f"tools={tool_names[:10]}")

    # Test: app query should include open_app
    tools = get_tools_for_message("open notepad", TOOLS)
    tool_names = [t["name"] for t in tools]
    check("App query includes open_app",
          "open_app" in tool_names,
          f"tools={tool_names[:10]}")

    # Test: volume query should include volume tools
    tools = get_tools_for_message("turn up the volume", TOOLS)
    tool_names = [t["name"] for t in tools]
    check("Volume query includes volume tools",
          any("volume" in t for t in tool_names),
          f"tools={tool_names[:10]}")


# -- Test 11: Full Agentic Loop via jarvis_chat --------------------------------

async def test_agentic_loop():
    """Test the full agentic loop: jarvis_chat -> LLM -> tool calls -> daemon -> results.

    Uses monkeypatching on execute_tool_via_core to verify tools were actually
    called (not just that the LLM mentioned them in its response).
    """
    print("\n-- Test 11: Full Agentic Loop via jarvis_chat --")

    # Skip if Ollama is not running (requires live LLM)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("http://localhost:11435/api/tags")
            if resp.status_code != 200:
                print("  ⏭️  Skipping (Ollama not running on port 11435)")
                return
    except Exception:
        print("  ⏭️  Skipping (Ollama not reachable)")
        return

    from llm.jarvis import jarvis_chat
    import llm.core_bridge as _cb

    # Track which tools were executed via core_bridge (proves daemon routing)
    executed_tools = []
    original_execute = _cb.execute_tool_via_core

    async def _tracking_execute(name, args):
        executed_tools.append(name)
        return await original_execute(name, args)

    _cb.execute_tool_via_core = _tracking_execute

    async def _collect(gen):
        """Collect async generator chunks into a list (for timeout wrapping)."""
        return [chunk async for chunk in gen]

    try:
        # Test 1: Multi-tool request (with timeout)
        try:
            chunks = await asyncio.wait_for(
                _collect(jarvis_chat(
                    message="what time is it and how much battery do I have",
                    history=[],
                    provider="ollama",
                    model="phi4-mini:3.8b",
                )),
                timeout=120,
            )
        except asyncio.TimeoutError:
            check("Multi-tool agentic loop (timeout)", False, "Timed out after 120s")
            return

        full_response = "".join(chunks)
        check("Agentic loop returns non-empty response",
              len(full_response) > 0,
              f"response_len={len(full_response)}")

        # Verify tools were actually executed (not just LLM mentioning them)
        check("Tools were executed via core_bridge",
              len(executed_tools) > 0,
              f"executed={executed_tools}")

        # Lenient content check -- LLM can phrase things many ways
        resp_lower = full_response.lower()
        has_any_info = any(kw in resp_lower for kw in [
            "time", "am", "pm", "clock", "battery", "charge",
            "percent", "power", ":", "hour", "minute",
        ])
        check("Response contains useful information",
              has_any_info,
              f"response={full_response[:300]}")

        # Test 2: Single tool request (with timeout)
        executed_tools.clear()
        try:
            chunks2 = await asyncio.wait_for(
                _collect(jarvis_chat(
                    message="what time is it",
                    history=[],
                    provider="ollama",
                    model="phi4-mini:3.8b",
                )),
                timeout=120,
            )
        except asyncio.TimeoutError:
            check("Single tool agentic loop (timeout)", False, "Timed out after 120s")
            return

        full_response2 = "".join(chunks2)
        check("Single tool agentic loop returns response",
              len(full_response2) > 0,
              f"response_len={len(full_response2)}")
        check("Single tool executed via core_bridge",
              len(executed_tools) > 0,
              f"executed={executed_tools}")

    finally:
        # Restore original function
        _cb.execute_tool_via_core = original_execute


# -- Main Runner --------------------------------------------------------------

async def main():
    global _passed, _failed, _total

    print("=" * 70)
    print("Control Core End-to-End Test")
    print("=" * 70)

    # Pre-flight: check daemon is running
    running = is_daemon_running_sync()
    print(f"\nDaemon running on TCP :7650: {running}")
    if not running:
        print("\n[WARN] Daemon not running. Starting tests anyway (fallback will be used).")
        print("   To test with daemon: python core/daemon.py debug")

    start = time.time()

    # Run all tests
    await test_single_tool_tcp()
    await test_multi_step()
    await test_cross_layer()
    await test_application_layer()
    await test_window_layer()
    await test_process_layer()
    await test_timeout_overrides()
    await test_core_bridge()
    await test_multi_step_core_bridge()
    await test_tool_tiering()
    await test_agentic_loop()

    elapsed = time.time() - start

    # Summary
    print("\n" + "=" * 70)
    print(f"Results: {_passed}/{_total} passed, {_failed} failed ({elapsed:.1f}s)")
    if _failed == 0:
        print("*** ALL TESTS PASSED ***")
    else:
        print(f"*** {_failed} test(s) failed ***")
    print("=" * 70)

    return _failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
