"""Test suite for tool tiering — verifies intent classification and filtering."""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from llm.tools import TOOLS
from llm.tool_tiering import get_tools_for_message, classify_intent, TIERED_NAMES, CORE_TOOLS

# Sanity checks
assert len(TOOLS) > 100, f"Expected 171 tools, got {len(TOOLS)}"

# Verify TIERED_NAMES covers every built-in tool — catches stale tier configs
# when tools are added to TOOLS but forgotten in CORE_TOOLS/DOMAIN_TIERS
builtin_names = {t["name"] for t in TOOLS}
missing_from_tiers = builtin_names - TIERED_NAMES
assert not missing_from_tiers, (
    f"{len(missing_from_tiers)} built-in tools not in any tier: {sorted(missing_from_tiers)}. "
    f"Add them to CORE_TOOLS or a DOMAIN_TIERS entry."
)


def test_scenario(
    name: str,
    message: str,
    expected_contains: list[str],
    expected_not_contains: list[str] | None = None,
    all_tools: list[dict] | None = None,
    enable_tiering: bool = True,
):
    """Run a single test scenario."""
    tools_to_use = all_tools or TOOLS
    filtered = get_tools_for_message(message, tools_to_use, enable_tiering=enable_tiering)
    filtered_names = {t["name"] for t in filtered}
    core_names = set(CORE_TOOLS)

    passed = True
    failures = []

    # Check expected tools are present
    for tool_name in expected_contains:
        if tool_name not in filtered_names:
            failures.append(f"  MISSING expected tool: {tool_name}")
            passed = False

    # Check excluded tools are absent (if specified)
    if expected_not_contains:
        for tool_name in expected_not_contains:
            if tool_name in filtered_names:
                failures.append(f"  UNEXPECTED tool present: {tool_name}")
                passed = False

    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{'='*60}")
    print(f"{status} — {name}")
    print(f"  Message: \"{message}\"")
    print(f"  Intent tiers: {classify_intent(message)}")
    print(f"  Tools sent: {len(filtered)} / {len(tools_to_use)} total")
    print(f"  Core tools: {len(filtered_names & core_names)}")
    print(f"  Domain tools: {len(filtered_names - core_names)}")

    if failures:
        for f in failures:
            print(f)

    return passed


def main():
    print("=" * 60)
    print("TOOL TIERING TEST SUITE")
    print(f"Total tools in TOOLS: {len(TOOLS)}")
    print(f"Core tools always sent: {len(CORE_TOOLS)}")
    print(f"Tiered tool names (static): {len(TIERED_NAMES)}")

    results = []

    # ── Scenario 1: "open notepad" → app management tools ──
    # Core tools (10) + some app_management tools fit within max_tools cap (15)
    results.append(test_scenario(
        name="App Launch — 'open notepad'",
        message="open notepad",
        expected_contains=[
            "open_app", "close_app", "web_search", "type_text",
        ],
        expected_not_contains=[
            "browser_navigate", "browser_click",
            "list_services", "start_service",
            "shutdown_pc", "lock_pc",
            "queue_ghost_task",
        ],
    ))

    # ── Scenario 2: "what time is it" → only core tools ──
    results.append(test_scenario(
        name="Simple Query — 'what time is it'",
        message="what time is it",
        expected_contains=["get_time", "get_date", "open_app", "web_search"],
        expected_not_contains=[
            "launch_with_args", "read_file", "list_windows",
            "browser_navigate", "get_unread_emails", "shutdown_pc",
            "list_services", "media_play_pause",
        ],
    ))

    # ── Scenario 3: Plugin tools always included ──
    fake_plugin_tools = [
        {"name": "spotify_play", "description": "Play music on Spotify", "parameters": {}},
        {"name": "spotify_pause", "description": "Pause music on Spotify", "parameters": {}},
        {"name": "spotify_next", "description": "Next track on Spotify", "parameters": {}},
    ]
    all_tools_with_plugins = TOOLS + fake_plugin_tools

    filtered = get_tools_for_message("what time is it", all_tools_with_plugins)
    filtered_names = {t["name"] for t in filtered}
    plugin_found = all(p["name"] in filtered_names for p in fake_plugin_tools)

    status = "✅ PASS" if plugin_found else "❌ FAIL"
    results.append(plugin_found)
    print(f"\n{'='*60}")
    print(f"{status} — Plugin Tools Always Included")
    print(f"  Message: \"what time is it\" (with 3 fake plugin tools)")
    print(f"  Tools sent: {len(filtered)} / {len(all_tools_with_plugins)} total")
    print(f"  Plugin tools found: {[p['name'] for p in fake_plugin_tools if p['name'] in filtered_names]}")

    # ── Scenario 4: Multi-tier — app + filesystem + browser ──
    results.append(test_scenario(
        name="Multi-tier — 'open chrome and search for weather'",
        message="open chrome and search for weather",
        expected_contains=[
            "open_app", "launch_with_args",
            "web_search", "open_url",
            "get_weather",
        ],
        expected_not_contains=[
            "browser_navigate",  # chrome is app_management, not browser
            "list_services",
        ],
    ))

    # ── Scenario 5: Empty message → only core tools ──
    results.append(test_scenario(
        name="Edge Case — empty message",
        message="",
        expected_contains=["open_app", "web_search"],
        expected_not_contains=[
            "launch_with_args", "read_file", "browser_navigate",
            "shutdown_pc", "list_services", "media_play_pause",
        ],
    ))

    # ── Scenario 6: enable_tiering=False returns all tools ──
    results.append(test_scenario(
        name="Bypass — enable_tiering=False",
        message="what time is it",
        expected_contains=["browser_navigate", "list_services", "shutdown_pc"],
        enable_tiering=False,
    ))

    # ── Scenario 7: Volume/display tier ──
    results.append(test_scenario(
        name="Volume — 'set volume to 50%'",
        message="set volume to 50%",
        expected_contains=[
            "volume_up", "volume_down", "set_volume",  # core
            "get_volume", "mute", "unmute",             # volume_display tier
        ],
        expected_not_contains=[
            "browser_navigate", "list_services",
        ],
    ))

    # ── Scenario 8: Filesystem tier ──
    results.append(test_scenario(
        name="Filesystem — 'read the file config.json'",
        message="read the file config.json",
        expected_contains=[
            "read_file", "write_file", "list_directory",  # filesystem tier
            "open_app", "web_search",                      # core
        ],
        expected_not_contains=[
            "browser_navigate", "list_services",
            "media_play_pause",
        ],
    ))

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"RESULTS: {sum(results)}/{len(results)} passed")
    if all(results):
        print("🎉 All tests passed! Tool tiering is working correctly.")
    else:
        print("⚠️ Some tests failed. Check output above.")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
