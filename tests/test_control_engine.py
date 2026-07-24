"""Comprehensive Control Core Engine Tests.

Tests the full control engine stack:
  1. FallbackChain -- method execution, verification, escalation, defer, diagnostics
  2. CommandBus -- dispatch, routing, timeout, error handling
  3. Router -- validation, layer aliases, safety checks
  4. Verifiers -- all 9 layers' verifier functions
  5. core_bridge -- TOOL_CORE_MAP consistency, execute_tool_via_core
  6. L8_system ACTION_MAP -- handler routing, method fallback
  7. config_loader -- layer_caps.json, fallback_chains.json
"""

import asyncio
import os
import sys
import time
import json
import tempfile

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


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: FallbackChain Core Logic
# ══════════════════════════════════════════════════════════════════════════════

async def test_fallback_chain():
    _section("TEST 1: FallbackChain Core Logic")
    from core.engine.fallback import FallbackChain

    chain = FallbackChain()

    # 1.1 -- First method succeeds
    async def method_ok(params):
        return {"result": "ok"}

    success, data, method, error = await chain.execute(
        action="test.first_ok", params={}, methods=[method_ok],
    )
    if success and data == {"result": "ok"} and method == "method_1_method_ok":
        _ok("1.1 First method succeeds", f"method={method}")
    else:
        _fail("1.1 First method succeeds", f"success={success} method={method} error={error}")

    # 1.2 -- First fails, second succeeds (fallback)
    async def method_fail(params):
        raise RuntimeError("Method 1 failed")

    async def method_ok2(params):
        return {"result": "fallback"}

    success, data, method, error = await chain.execute(
        action="test.fallback", params={}, methods=[method_fail, method_ok2],
    )
    if success and data == {"result": "fallback"} and method == "method_2_method_ok2":
        _ok("1.2 Fallback to second method", f"method={method}")
    else:
        _fail("1.2 Fallback to second method", f"success={success} method={method} error={error}")

    # 1.3 -- All methods fail  -> diagnostic
    async def method_fail2(params):
        raise ValueError("Method 2 failed too")

    success, data, method, error = await chain.execute(
        action="test.all_fail", params={}, methods=[method_fail, method_fail2],
    )
    if not success and method == "none" and "RuntimeError" in error and "ValueError" in error:
        _ok("1.3 All methods fail  -> diagnostic", f"errors contain both types")
    else:
        _fail("1.3 All methods fail  -> diagnostic", f"success={success} error={error}")

    # 1.4 -- Verifier passes  -> success
    async def verifier_ok(params, result):
        return True

    success, data, method, error = await chain.execute(
        action="test.verify_pass", params={}, methods=[method_ok], verifier=verifier_ok,
    )
    if success:
        _ok("1.4 Verifier passes  -> success")
    else:
        _fail("1.4 Verifier passes  -> success", f"error={error}")

    # 1.5 -- Verifier fails  -> tries next method
    call_log = []

    async def method_logged(params):
        call_log.append("m1")
        return {"result": "m1"}

    async def method_logged2(params):
        call_log.append("m2")
        return {"result": "m2"}

    async def verifier_fail(params, result):
        return False    # Test 1.5a: verifier fails on method1, succeeds on method2
    call_log.clear()
    verifier_seq = [False, True]  # Fail first, accept second
    verifier_idx = [0]
    async def verifier_selective(params, result):
        idx = min(verifier_idx[0], len(verifier_seq) - 1)
        verifier_idx[0] += 1
        return verifier_seq[idx]
    success, data, method, error = await chain.execute(
        action="test.verify_fail", params={},
        methods=[method_logged, method_logged2], verifier=verifier_selective,
    )
    if success and data == {"result": "m2"} and call_log == ["m1", "m2"]:
        _ok("1.5 Verifier fails on m1 -> tries m2", f"calls={call_log}")
    else:
        _fail("1.5 Verifier fails on m1 -> tries m2", f"success={success} data={data} calls={call_log}")
    # Test 1.5b: verifier always fails -> all methods exhausted
    call_log.clear()
    success, data, method, error = await chain.execute(
        action="test.verify_all_fail", params={},
        methods=[method_logged, method_logged2], verifier=verifier_fail,
    )
    if not success and call_log == ["m1", "m2"]:
        _ok("1.5b Verifier always fails -> all methods exhausted", f"calls={call_log}")
    else:
        _fail("1.5b Verifier always fails -> all exhausted", f"success={success} calls={call_log}")

    # 1.6 -- Pre-flight check fails  -> short circuit
    async def preflight_fail(params):
        return "Target does not exist: /foo/bar"

    success, data, method, error = await chain.execute(
        action="test.preflight", params={},
        methods=[method_ok], preflight_fn=preflight_fail,
    )
    if not success and "Pre-flight failed" in error:
        _ok("1.6 Pre-flight check fails  -> short circuit", f"error={error}")
    else:
        _fail("1.6 Pre-flight check fails  -> short circuit", f"success={success} error={error}")

    # 1.7 -- Pre-flight raises exception  -> continues anyway
    async def preflight_raises(params):
        raise OSError("Something weird")

    success, data, method, error = await chain.execute(
        action="test.preflight_raises", params={},
        methods=[method_ok], preflight_fn=preflight_raises,
    )
    if success:
        _ok("1.7 Pre-flight raises  -> continues anyway")
    else:
        _fail("1.7 Pre-flight raises  -> continues anyway", f"error={error}")

    # 1.8 -- Privilege escalation  -> retry succeeds
    async def method_need_admin(params):
        raise PermissionError("Access denied")

    escalated = []

    async def escalation_fn():
        escalated.append(True)
        return True

    success, data, method, error = await chain.execute(
        action="test.escalation", params={},
        methods=[method_need_admin], escalation_fn=escalation_fn,
    )
    # After escalation, it retries method_need_admin which still fails
    if not success and len(escalated) == 1:
        _ok("1.8 Escalation called when all methods fail", f"escalated={len(escalated)} times")
    else:
        _fail("1.8 Escalation called when all methods fail", f"success={success} escalated={len(escalated)}")

    # 1.9 -- Escalation succeeds  -> retry works
    retry_count = []

    async def method_fail_then_ok(params):
        retry_count.append(1)
        if len(retry_count) <= 1:
            raise PermissionError("Need admin")
        return {"result": "escalated_ok"}

    async def escalation_ok():
        return True

    success, data, method, error = await chain.execute(
        action="test.escalation_retry", params={},
        methods=[method_fail_then_ok], escalation_fn=escalation_ok,
    )
    if success and data == {"result": "escalated_ok"} and "escalated_" in method:
        _ok("1.9 Escalation + retry succeeds", f"method={method}")
    else:
        _fail("1.9 Escalation + retry succeeds", f"success={success} method={method}")

    # 1.10 -- Deferred execution as last resort
    deferred_called = []

    async def defer_fn(params):
        deferred_called.append(True)
        return {"deferred": True}

    success, data, method, error = await chain.execute(
        action="test.defer", params={},
        methods=[method_fail], defer_fn=defer_fn,
    )
    if success and data == {"deferred": True} and method == "method_deferred":
        _ok("1.10 Deferred execution as last resort")
    else:
        _fail("1.10 Deferred execution as last resort", f"success={success} method={method}")

    # 1.11 -- Escalation fails  -> defer still works
    async def escalation_fail():
        return False

    success, data, method, error = await chain.execute(
        action="test.escalation_defer", params={},
        methods=[method_fail], escalation_fn=escalation_fail, defer_fn=defer_fn,
    )
    if success and method == "method_deferred":
        _ok("1.11 Escalation fails  -> defer works")
    else:
        _fail("1.11 Escalation fails  -> defer works", f"success={success} method={method}")

    # 1.12 -- Empty methods list  -> diagnostic
    success, data, method, error = await chain.execute(
        action="test.empty", params={}, methods=[],
    )
    if not success and method == "none":
        _ok("1.12 Empty methods list  -> diagnostic")
    else:
        _fail("1.12 Empty methods list  -> diagnostic", f"success={success}")    # 1.13a -- Verifier crashes on m1, succeeds on m2
    async def verifier_crash_selective(params, result):
        if result and result.get("result") == "ok":
            raise RuntimeError("Verifier crash on m1")
        return True  # Accept m2
    success, data, method, error = await chain.execute(
        action="test.verifier_crash", params={},
        methods=[method_ok, method_ok2], verifier=verifier_crash_selective,
    )
    if success and method == "method_2_method_ok2":
        _ok("1.13a Verifier crashes on m1 -> tries m2", f"method={method}")
    else:
        _fail("1.13a Verifier crashes on m1 -> tries m2", f"success={success} method={method}")
    # 1.13b -- Verifier always crashes -> all methods exhausted
    async def verifier_raises(params, result):
        raise RuntimeError("Verifier crash")
    success, data, method, error = await chain.execute(
        action="test.verifier_crash_all", params={},
        methods=[method_ok, method_ok2], verifier=verifier_raises,
    )
    if not success and method == "none":
        _ok("1.13b Verifier always crashes -> all exhausted", f"error={error[:60]}")
    else:
        _fail("1.13b Verifier always crashes -> all exhausted", f"success={success} method={method}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: CommandBus
# ══════════════════════════════════════════════════════════════════════════════

async def test_command_bus():
    _section("TEST 2: CommandBus")
    from core.bus import CommandBus, Command, Result

    bus = CommandBus()

    # 2.1 -- Register and dispatch
    async def test_handler(action, params):
        return Result(command_id="test", success=True, data={"action": action})

    bus.register("test_layer", test_handler)

    cmd = Command(layer="test_layer", action="do_something", params={"key": "val"})
    result = await bus.dispatch(cmd)

    if result.success and result.data["action"] == "do_something":
        _ok("2.1 Register and dispatch", f"method={result.method_used}")
    else:
        _fail("2.1 Register and dispatch", f"success={result.success} error={result.error}")

    # 2.2 -- Unknown layer
    cmd2 = Command(layer="nonexistent", action="x")
    result2 = await bus.dispatch(cmd2)
    if not result2.success and "Unknown layer" in (result2.error or ""):
        _ok("2.2 Unknown layer  -> error")
    else:
        _fail("2.2 Unknown layer  -> error", f"error={result2.error}")

    # 2.3 -- Handler raises exception
    async def bad_handler(action, params):
        raise ValueError("Handler crashed")

    bus.register("bad_layer", bad_handler)
    cmd3 = Command(layer="bad_layer", action="crash")
    result3 = await bus.dispatch(cmd3)
    if not result3.success and "ValueError" in (result3.error or ""):
        _ok("2.3 Handler exception  -> error result")
    else:
        _fail("2.3 Handler exception  -> error result", f"error={result3.error}")

    # 2.4 -- Timeout
    async def slow_handler(action, params):
        await asyncio.sleep(5)
        return Result(command_id="test", success=True)

    bus.register("slow_layer", slow_handler)
    cmd4 = Command(layer="slow_layer", action="slow", timeout=0.1)
    result4 = await bus.dispatch(cmd4)
    if not result4.success and "Timeout" in (result4.error or ""):
        _ok("2.4 Timeout protection", f"time={result4.time_ms}ms")
    else:
        _fail("2.4 Timeout protection", f"success={result4.success} error={result4.error}")

    # 2.5 -- dispatch_json parses JSON correctly
    json_str = json.dumps({"layer": "test_layer", "action": "do_something", "params": {"a": 1}})
    result5 = await bus.dispatch_json(json_str)
    if result5.success:
        _ok("2.5 dispatch_json parses JSON")
    else:
        _fail("2.5 dispatch_json parses JSON", f"error={result5.error}")

    # 2.6 -- dispatch_json invalid JSON
    result6 = await bus.dispatch_json("not json at all")
    if not result6.success and "Invalid" in (result6.error or ""):
        _ok("2.6 dispatch_json invalid JSON  -> error")
    else:
        _fail("2.6 dispatch_json invalid JSON  -> error", f"error={result6.error}")

    # 2.7 -- Layer aliases
    async def alias_handler(action, params):
        return Result(command_id="test", success=True, data={"alias": True})

    bus.register("filesystem", alias_handler)
    cmd7 = Command(layer="file", action="list")
    result7 = await bus.dispatch(cmd7)
    if result7.success:
        _ok("2.7 Layer alias 'file'  -> 'filesystem'")
    else:
        _fail("2.7 Layer alias 'file'  -> 'filesystem'", f"error={result7.error}")

    # 2.8 -- List layers
    layers = bus.list_layers()
    if "test_layer" in layers and "filesystem" in layers:
        _ok("2.8 list_layers", f"layers={layers}")
    else:
        _fail("2.8 list_layers", f"layers={layers}")

    # 2.9 -- Unregister
    bus.unregister("test_layer")
    if "test_layer" not in bus.list_layers():
        _ok("2.9 Unregister layer")
    else:
        _fail("2.9 Unregister layer", f"layers={bus.list_layers()}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: Router
# ══════════════════════════════════════════════════════════════════════════════

async def test_router():
    _section("TEST 3: Router")
    from core.bus import CommandBus, Command, Result
    from core.router import Router, LAYER_ALIASES, VALID_LAYERS, DESTRUCTIVE_ACTIONS

    bus = CommandBus()
    router = Router(bus)

    # 3.1 -- Normalize layer aliases
    tests = [
        ("file", "filesystem"), ("files", "filesystem"),
        ("proc", "process"), ("procs", "process"),
        ("win", "window"), ("wins", "window"),
        ("keyboard", "input"), ("mouse", "input"),
        ("reg", "registry"), ("svc", "services"),
        ("sys", "system"), ("web", "browser"),
    ]
    all_ok = True
    for alias, expected in tests:
        got = router.normalize_layer(alias)
        if got != expected:
            _fail(f"3.1 Alias '{alias}'  -> '{expected}'", f"got '{got}'")
            all_ok = False
    if all_ok:
        _ok("3.1 All layer aliases resolve correctly", f"tested {len(tests)} aliases")

    # 3.2 -- Validate command: missing action
    cmd = Command(layer="filesystem", action="")
    error = router.validate_command(cmd)
    if error and "Missing" in error:
        _ok("3.2 Validate: missing action")
    else:
        _fail("3.2 Validate: missing action", f"error={error}")

    # 3.3 -- Validate command: invalid layer
    cmd = Command(layer="bogus", action="test")
    error = router.validate_command(cmd)
    if error and "Unknown layer" in error:
        _ok("3.3 Validate: unknown layer")
    else:
        _fail("3.3 Validate: unknown layer", f"error={error}")

    # 3.4 -- Validate: timeout too large
    cmd = Command(layer="system", action="test", timeout=999)
    error = router.validate_command(cmd)
    if error and "too large" in error.lower():
        _ok("3.4 Validate: timeout too large")
    else:
        _fail("3.4 Validate: timeout too large", f"error={error}")

    # 3.5 -- Validate: invalid timeout
    cmd = Command(layer="system", action="test", timeout=-1)
    error = router.validate_command(cmd)
    if error and "Invalid" in error:
        _ok("3.5 Validate: invalid timeout")
    else:
        _fail("3.5 Validate: invalid timeout", f"error={error}")

    # 3.6 -- Safety check: destructive actions
    for layer, actions in DESTRUCTIVE_ACTIONS.items():
        for action in list(actions)[:3]:
            safety = router.check_safety(layer, action)
            if not safety["destructive"]:
                _fail(f"3.6 Safety: {layer}.{action} not flagged destructive")
                break
        else:
            continue
        break
    else:
        _ok("3.6 Destructive actions correctly flagged", f"layers={list(DESTRUCTIVE_ACTIONS.keys())}")

    # 3.7 -- Route valid command
    async def route_handler(action, params):
        return Result(command_id="r", success=True, data={"routed": action})

    router.register_layer("filesystem", route_handler)
    cmd = Command(layer="filesystem", action="read_file", params={"path": "/test"})
    result = await router.route(cmd)
    if result.success and result.data["routed"] == "read_file":
        _ok("3.7 Route valid command")
    else:
        _fail("3.7 Route valid command", f"success={result.success} error={result.error}")

    # 3.8 -- Route with alias
    cmd = Command(layer="file", action="read_file", params={"path": "/test"})
    result = await router.route(cmd)
    if result.success:
        _ok("3.8 Route with layer alias 'file'")
    else:
        _fail("3.8 Route with layer alias 'file'", f"error={result.error}")

    # 3.9 -- All VALID_LAYERS are defined (15 layers)
    expected = {
        "filesystem", "process", "application", "window", "input",
        "registry", "services", "system", "browser",
        "network", "media", "developer", "cloud", "automation", "advanced",
    }
    if VALID_LAYERS == expected:
        _ok("3.9 All 15 VALID_LAYERS defined", f"{len(VALID_LAYERS)} layers")
    else:
        _fail("3.9 VALID_LAYERS mismatch", f"got={VALID_LAYERS} expected={expected}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: Verifiers
# ══════════════════════════════════════════════════════════════════════════════

async def test_verifiers():
    _section("TEST 4: Verifiers")
    from core.engine.verifier import Verifiers, VERIFIER_MAP, get_verifier

    # 4.1 -- Create a temp file and verify file_created
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"test content")
        tmp_path = f.name

    try:
        verified = await Verifiers.file_created({"path": tmp_path}, None)
        if verified:
            _ok("4.1 file_created verifier (exists)")
        else:
            _fail("4.1 file_created verifier (exists)")

        # 4.2 -- Verify file_deleted (file still exists  -> should fail)
        verified = await Verifiers.file_deleted({"path": tmp_path}, None)
        if not verified:
            _ok("4.2 file_deleted verifier (file still exists  -> false)")
        else:
            _fail("4.2 file_deleted verifier should be false when file exists")

        # 4.3 -- Delete and verify
        os.unlink(tmp_path)
        verified = await Verifiers.file_deleted({"path": tmp_path}, None)
        if verified:
            _ok("4.3 file_deleted verifier (file gone  -> true)")
        else:
            _fail("4.3 file_deleted verifier (file gone  -> true)")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # 4.4 -- Verify folder_created
    tmp_dir = tempfile.mkdtemp()
    try:
        verified = await Verifiers.folder_created({"path": tmp_dir}, None)
        if verified:
            _ok("4.4 folder_created verifier")
        else:
            _fail("4.4 folder_created verifier")
        os.rmdir(tmp_dir)
    except Exception:
        pass

    # 4.5 -- Generic verifiers
    r = await Verifiers.always_true({}, None)
    if r:
        _ok("4.5 always_true")

    r = await Verifiers.result_not_none({}, {"data": 1})
    if r:
        _ok("4.6 result_not_none (non-None)")

    r = await Verifiers.result_not_none({}, None)
    if not r:
        _ok("4.7 result_not_none (None  -> false)")

    r = await Verifiers.result_no_error({}, {"key": "val"})
    if r:
        _ok("4.8 result_no_error (no error key)")

    r = await Verifiers.result_no_error({}, {"error": "fail"})
    if not r:
        _ok("4.9 result_no_error (has error  -> false)")

    r = await Verifiers.result_has_key({}, {"a": 1})
    if r:
        _ok("4.10 result_has_key (has key)")

    r = await Verifiers.result_has_key({}, {})
    if not r:
        _ok("4.11 result_has_key (empty dict  -> false)")

    # 4.12 -- VERIFIER_MAP coverage
    if len(VERIFIER_MAP) >= 260:
        _ok("4.12 VERIFIER_MAP coverage", f"{len(VERIFIER_MAP)} entries (-260 expected)")
    else:
        _fail("4.12 VERIFIER_MAP coverage", f"only {len(VERIFIER_MAP)} entries (expected -260)")

    # 4.13 -- get_verifier lookup
    v = get_verifier("filesystem", "delete_file")
    if v == Verifiers.file_deleted:
        _ok("4.13 get_verifier('filesystem.delete_file')")
    else:
        _fail("4.13 get_verifier('filesystem.delete_file')", f"got={v}")

    # 4.14 -- get_verifier unknown
    v = get_verifier("nonexistent", "action")
    if v is None:
        _ok("4.14 get_verifier unknown  -> None")
    else:
        _fail("4.14 get_verifier unknown  -> None", f"got={v}")

    # 4.15 -- Volume verifier (pycaw-based)
    r = await Verifiers.volume_set({"level": 50}, {"level": 50})
    if r:
        _ok("4.15 volume_set verifier (pycaw)")
    else:
        _fail("4.15 volume_set verifier", "returned False -- pycaw may not be available")

    # 4.16 -- system_info_result
    r = await Verifiers.system_info_result({}, {"os": "Windows 11"})
    if r:
        _ok("4.16 system_info_result")
    else:
        _fail("4.16 system_info_result")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: Config Loader
# ══════════════════════════════════════════════════════════════════════════════

async def test_config_loader():
    _section("TEST 5: Config Loader")
    from core.engine.config_loader import (
        get_layer_caps, get_layer_actions, is_action_supported,
        get_fallback_chains, get_fallback_strategy, reload_configs,
    )

    # 5.1 -- Layer caps load
    caps = get_layer_caps()
    if caps and len(caps) >= 9:
        _ok("5.1 Layer caps loaded", f"{len(caps)} layers")
    else:
        _fail("5.1 Layer caps loaded", f"layers={len(caps) if caps else 0}")

    # 5.2 -- Get layer actions
    actions = get_layer_actions("system")
    if actions and len(actions) > 10:
        _ok("5.2 system layer actions", f"{len(actions)} actions")
    else:
        _fail("5.2 system layer actions", f"count={len(actions) if actions else 0}")

    # 5.3 -- is_action_supported
    if is_action_supported("system", "set_volume"):
        _ok("5.3 is_action_supported('system', 'set_volume')")
    else:
        _fail("5.3 is_action_supported('system', 'set_volume')")

    if not is_action_supported("system", "nonexistent_action_xyz"):
        _ok("5.4 is_action_supported unknown  -> False")
    else:
        _fail("5.4 is_action_supported unknown  -> False")

    # 5.5 -- Fallback chains
    chains = get_fallback_chains()
    if chains and len(chains) >= 5:
        _ok("5.5 Fallback chains loaded", f"{len(chains)} layers in chains")
    else:
        _fail("5.5 Fallback chains loaded", f"count={len(chains) if chains else 0}")

    # 5.6 -- Get fallback strategy for a specific action
    strategy = get_fallback_strategy("system", "set_volume")
    if strategy and "methods" in strategy:
        _ok("5.6 Fallback strategy for system.set_volume", f"methods={len(strategy['methods'])}")
    else:
        _fail("5.6 Fallback strategy for system.set_volume", f"strategy={strategy}")

    # 5.7 -- Reload configs
    reload_configs()
    caps2 = get_layer_caps()
    if caps2:
        _ok("5.7 reload_configs works")
    else:
        _fail("5.7 reload_configs works")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: L8_system ACTION_MAP and Handler
# ══════════════════════════════════════════════════════════════════════════════

async def test_l8_system():
    _section("TEST 6: L8_system ACTION_MAP")
    try:
        from core.layers.L8_system import ACTION_MAP, handler
    except ImportError as e:
        _fail("6.0 Import L8_system", f"ImportError: {e}")
        return

    # 6.1 -- ACTION_MAP has expected entries
    expected_actions = [
        "set_volume", "get_volume", "volume_up", "volume_down", "mute", "unmute",
        "shutdown", "restart", "sleep", "lock", "cancel_shutdown",
        "set_brightness", "get_brightness",
        "get_system_info", "get_ram_usage", "get_disk_usage", "get_battery",
        "get_network_info", "flush_dns", "get_wifi_password",
        "get_time", "get_date", "run_powershell",
    ]
    missing = [a for a in expected_actions if a not in ACTION_MAP]
    if not missing:
        _ok("6.1 ACTION_MAP has all expected entries", f"{len(ACTION_MAP)} actions total")
    else:
        _fail("6.1 ACTION_MAP missing entries", f"missing={missing}")

    # 6.2 -- Every entry has (methods_list, verifier)
    bad_entries = []
    for name, entry in ACTION_MAP.items():
        if not isinstance(entry, tuple) or len(entry) != 2:
            bad_entries.append(name)
            continue
        methods, verifier = entry
        if not isinstance(methods, list) or len(methods) == 0:
            bad_entries.append(f"{name}(no methods)")
    if not bad_entries:
        _ok("6.2 All ACTION_MAP entries have (methods, verifier)", f"{len(ACTION_MAP)} entries valid")
    else:
        _fail("6.2 ACTION_MAP entries malformed", f"bad={bad_entries[:5]}")

    # 6.3 -- Methods with 2+ fallbacks
    multi_fallback = [name for name, (methods, _) in ACTION_MAP.items() if len(methods) >= 2]
    if len(multi_fallback) >= 20:
        _ok("6.3 Actions with -2 fallback methods", f"{len(multi_fallback)} actions")
    else:
        _fail("6.3 Actions with -2 fallback methods", f"only {len(multi_fallback)}")

    # 6.4 -- Handler: unknown action
    from core.bus import Result
    result = await handler("nonexistent_action_xyz", {})
    if not result.success and "Unknown" in (result.error or ""):
        _ok("6.4 Handler: unknown action  -> error")
    else:
        _fail("6.4 Handler: unknown action  -> error", f"error={result.error}")

    # 6.5 -- Handler: get_time (should succeed via Python fallback)
    result = await handler("get_time", {})
    if result.success and result.data and "time" in result.data:
        _ok("6.5 Handler: get_time", f"data={result.data}")
    else:
        _fail("6.5 Handler: get_time", f"success={result.success} error={result.error}")

    # 6.6 -- Handler: get_date
    result = await handler("get_date", {})
    if result.success and result.data and "date" in result.data:
        _ok("6.6 Handler: get_date", f"data={result.data}")
    else:
        _fail("6.6 Handler: get_date", f"success={result.success} error={result.error}")

    # 6.7 -- Handler: get_system_info
    result = await handler("get_system_info", {})
    if result.success and result.data:
        _ok("6.7 Handler: get_system_info", f"keys={list(result.data.keys())[:5]}")
    else:
        _fail("6.7 Handler: get_system_info", f"success={result.success} error={result.error}")

    # 6.8 -- Handler: get_ram_usage
    result = await handler("get_ram_usage", {})
    if result.success and result.data and "percent" in result.data:
        _ok("6.8 Handler: get_ram_usage", f"percent={result.data['percent']}")
    else:
        _fail("6.8 Handler: get_ram_usage", f"success={result.success} error={result.error}")

    # 6.9 -- Handler: get_battery
    result = await handler("get_battery", {})
    if result.success:
        _ok("6.9 Handler: get_battery", f"data={result.data}")
    else:
        _fail("6.9 Handler: get_battery", f"error={result.error}")

    # 6.10 -- Handler: get_volume (pycaw)
    result = await handler("get_volume", {})
    if result.success:
        _ok("6.10 Handler: get_volume", f"data={result.data}")
    else:
        _fail("6.10 Handler: get_volume", f"error={result.error}")

    # 6.11 -- Handler: list_env
    result = await handler("list_env", {})
    if result.success:
        _ok("6.11 Handler: list_env", f"count={result.data.get('count', '?')}")
    else:
        _fail("6.11 Handler: list_env", f"error={result.error}")

    # 6.12 -- Handler: get_disk_usage
    result = await handler("get_disk_usage", {})
    if result.success and result.data and "disks" in result.data:
        _ok("6.12 Handler: get_disk_usage", f"disks={len(result.data['disks'])}")
    else:
        _fail("6.12 Handler: get_disk_usage", f"success={result.success} error={result.error}")

    # 6.13 -- Handler: get_uptime
    result = await handler("get_uptime", {})
    if result.success and result.data:
        _ok("6.13 Handler: get_uptime", f"hours={result.data.get('hours')}")
    else:
        _fail("6.13 Handler: get_uptime", f"error={result.error}")

    # 6.14 -- Handler: get_os_info
    result = await handler("get_os_info", {})
    if result.success:
        _ok("6.14 Handler: get_os_info")
    else:
        _fail("6.14 Handler: get_os_info", f"error={result.error}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 7: core_bridge TOOL_CORE_MAP
# ══════════════════════════════════════════════════════════════════════════════

async def test_core_bridge():
    _section("TEST 7: core_bridge")
    try:
        from backend.llm.core_bridge import TOOL_CORE_MAP, execute_tool_via_core
    except ImportError:
        try:
            from llm.core_bridge import TOOL_CORE_MAP, execute_tool_via_core
        except ImportError as e:
            _fail("7.0 Import core_bridge", f"ImportError: {e}")
            return

    # 7.1 -- TOOL_CORE_MAP is populated
    if TOOL_CORE_MAP and len(TOOL_CORE_MAP) > 50:
        _ok("7.1 TOOL_CORE_MAP populated", f"{len(TOOL_CORE_MAP)} tools mapped")
    else:
        _fail("7.1 TOOL_CORE_MAP populated", f"count={len(TOOL_CORE_MAP) if TOOL_CORE_MAP else 0}")

    # 7.2 -- All tools from tools.py are in TOOL_CORE_MAP
    try:
        from llm.tools import TOOLS
    except ImportError:
        from backend.llm.tools import TOOLS
    tool_names = {t["name"] for t in TOOLS}
    mapped_names = set(TOOL_CORE_MAP.keys())
    missing = tool_names - mapped_names
    extra = mapped_names - tool_names
    if not missing:
        _ok("7.2 All tools.py tools in TOOL_CORE_MAP", f"tools={len(tool_names)} mapped={len(mapped_names)}")
    else:
        _fail("7.2 Missing from TOOL_CORE_MAP", f"missing={list(missing)[:10]}")
    if extra:
        print(f"  --  Extra in TOOL_CORE_MAP (not in tools.py): {list(extra)[:5]}")

    # 7.3 -- TOOL_CORE_MAP entries have correct structure
    bad = []
    for name, entry in TOOL_CORE_MAP.items():
        if not isinstance(entry, tuple) or len(entry) != 4:
            bad.append(name)
    if not bad:
        _ok("7.3 All TOOL_CORE_MAP entries are 4-tuples")
    else:
        _fail("7.3 Malformed TOOL_CORE_MAP entries", f"bad={bad[:5]}")

    # 7.4 -- execute_tool_via_core with a direct tool (get_time)
    try:
        result = await execute_tool_via_core("get_time", {})
        if result:
            _ok("7.4 execute_tool_via_core('get_time')", f"result={result[:80]}")
        else:
            _fail("7.4 execute_tool_via_core('get_time')", "empty result")
    except Exception as e:
        _fail("7.4 execute_tool_via_core('get_time')", f"exception: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 8: Cross-Layer Handler Consistency
# ══════════════════════════════════════════════════════════════════════════════

async def test_cross_layer():
    _section("TEST 8: Cross-Layer Handler Consistency")

    layer_modules = [
        ("filesystem", "L1_filesystem"),
        ("process", "L2_process"),
        ("application", "L3_application"),
        ("window", "L4_window"),
        ("input", "L5_input"),
        ("registry", "L6_registry"),
        ("services", "L7_services"),
        ("system", "L8_system"),
        ("browser", "L9_browser"),
        ("network", "L10_network"),
        ("media", "L11_media"),
        ("developer", "L12_developer"),
        ("cloud", "L13_cloud"),
        ("automation", "L14_automation"),
        ("advanced", "L15_advanced"),
    ]

    for layer_name, module_name in layer_modules:
        try:
            import importlib
            mod = importlib.import_module(f"core.layers.{module_name}")

            # Check ACTION_MAP exists
            action_map = getattr(mod, "ACTION_MAP", None)
            handler_fn = getattr(mod, "handler", None)

            if action_map and handler_fn:
                # Check every entry has (methods, verifier) tuple
                bad = []
                for name, entry in action_map.items():
                    if not isinstance(entry, tuple) or len(entry) != 2:
                        bad.append(name)
                    elif not isinstance(entry[0], list) or len(entry[0]) == 0:
                        bad.append(f"{name}(no_methods)")

                if not bad:
                    _ok(f"8.{layer_name} ACTION_MAP valid", f"{len(action_map)} actions")
                else:
                    _fail(f"8.{layer_name} ACTION_MAP invalid", f"bad={bad[:5]}")
            else:
                if not action_map:
                    _fail(f"8.{layer_name} missing ACTION_MAP")
                if not handler_fn:
                    _fail(f"8.{layer_name} missing handler()")

        except ImportError as e:
            _fail(f"8.{layer_name} import", f"ImportError: {e}")
        except Exception as e:
            _fail(f"8.{layer_name}", f"Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 9: Client (daemon connectivity)
# ══════════════════════════════════════════════════════════════════════════════

async def test_client():
    _section("TEST 9: Client (daemon connectivity)")
    from core.client import is_daemon_running, is_daemon_running_sync

    # 9.1 -- Check daemon status (async)
    running = await is_daemon_running()
    if running:
        _ok("9.1 Daemon is running (async check)")
    else:
        print("  --  Daemon not running -- TCP tests skipped")

    # 9.2 -- Check daemon status (sync)
    running_sync = is_daemon_running_sync()
    if running_sync == running:
        _ok("9.2 Sync check matches async check", f"running={running}")
    else:
        _fail("9.2 Sync/async mismatch", f"async={running} sync={running_sync}")

    # 9.3 -- Send command to daemon (if running)
    if running:
        from core.client import send_command
        result = await send_command("system", "get_time", {})
        if result.success:
            _ok("9.3 send_command system.get_time", f"data={result.data}")
        else:
            _fail("9.3 send_command system.get_time", f"error={result.error}")

        # 9.4 -- Send system_info
        result = await send_command("system", "get_system_info", {})
        if result.success:
            _ok("9.4 send_command system.get_system_info", f"keys={list(result.data.keys())[:5]}")
        else:
            _fail("9.4 send_command system.get_system_info", f"error={result.error}")

        # 9.5 -- Send get_volume
        result = await send_command("system", "get_volume", {})
        if result.success:
            _ok("9.5 send_command system.get_volume", f"data={result.data}")
        else:
            _fail("9.5 send_command system.get_volume", f"error={result.error}")

        # 9.6 -- Send with bad layer
        result = await send_command("nonexistent", "action", {})
        if not result.success:
            _ok("9.6 Bad layer  -> error from daemon", f"error={result.error}")
        else:
            _fail("9.6 Bad layer  -> error", f"success={result.success}")

    else:
        print("  --  Daemon not running -- skipping TCP command tests")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 10: BusServer (TCP listener)
# ══════════════════════════════════════════════════════════════════════════════

async def test_bus_server():
    _section("TEST 10: BusServer")
    from core.bus import CommandBus, BusServer, Command, Result

    # Check if port is already in use
    from core.client import is_daemon_running
    if await is_daemon_running():
        print("  --  Port 7650 in use -- BusServer tests skipped (daemon running)")
        return

    bus = CommandBus()
    async def echo_handler(action, params):
        return Result(command_id="test", success=True, data={"echo": action, "params": params})

    bus.register("echo", echo_handler)

    server = BusServer(bus, port=7651)  # Use different port
    try:
        await server.start()
        await asyncio.sleep(0.1)

        # 10.1 -- Connect and send command
        reader, writer = await asyncio.open_connection("127.0.0.1", 7651)
        cmd = Command(layer="echo", action="ping", params={"hello": "world"})
        writer.write(cmd.to_json().encode())
        await writer.drain()

        data = await asyncio.wait_for(reader.read(4096), timeout=2.0)
        writer.close()
        await writer.wait_closed()

        result_data = json.loads(data.decode())
        if result_data.get("success") and result_data["data"]["echo"] == "ping":
            _ok("10.1 BusServer TCP round-trip", f"data={result_data['data']}")
        else:
            _fail("10.1 BusServer TCP round-trip", f"response={result_data}")

        # 10.2 -- Send invalid JSON
        reader, writer = await asyncio.open_connection("127.0.0.1", 7651)
        writer.write(b"not json\n")
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), timeout=2.0)
        writer.close()
        await writer.wait_closed()

        result_data = json.loads(data.decode())
        if not result_data.get("success") and "Invalid" in result_data.get("error", ""):
            _ok("10.2 BusServer invalid JSON  -> error")
        else:
            _fail("10.2 BusServer invalid JSON  -> error", f"response={result_data}")

    except Exception as e:
        _fail("10.0 BusServer", f"exception: {e}")
    finally:
        await server.stop()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    print("=" * 60)
    print("  May Control Core Engine - Comprehensive Test Suite")
    print("=" * 60)

    await test_fallback_chain()
    await test_command_bus()
    await test_router()
    await test_verifiers()
    await test_config_loader()
    await test_l8_system()
    await test_core_bridge()
    await test_cross_layer()
    await test_client()
    await test_bus_server()

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
