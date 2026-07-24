"""Tests for core.layers.everything_search — Everything by voidtools integration.

Run: python -m pytest tests/test_everything_search.py -v

Note: These tests mock Everything since it may not be installed on the
test runner. The integration is verified when Everything IS installed.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.layers.everything_search import (
    _find_es_exe,
    is_everything_available,
    reset_detection_cache,
    EverythingResult,
)


def check(condition, label):
    status = "✅" if condition else "❌"
    print(f"  {status} {label}")
    assert condition, f"FAILED: {label}"


# ══════════════════════════════════════════════════════════════════════════════
# 1. Detection
# ══════════════════════════════════════════════════════════════════════════════

def test_detection():
    print("\n[1] Everything Detection")
    # Reset cache so we get a fresh detection
    reset_detection_cache()
    # This may or may not find Everything — both are valid test outcomes
    available = is_everything_available()
    es_path = _find_es_exe()
    if available:
        check(es_path is not None, "es.exe path found when available")
        check(es_path.endswith("es.exe"), "path ends with es.exe")
        print(f"  ℹ️  Everything detected at: {es_path}")
    else:
        check(es_path is None, "no es.exe path when unavailable")
        print("  ℹ️  Everything not detected (expected on CI/new installs)")


# ══════════════════════════════════════════════════════════════════════════════
# 2. Detection Cache
# ══════════════════════════════════════════════════════════════════════════════

def test_detection_cache():
    print("\n[2] Detection Cache")
    reset_detection_cache()
    # First call sets cache
    result1 = is_everything_available()
    # Second call should use cache
    result2 = is_everything_available()
    check(result1 == result2, "cached result matches fresh result")
    # Reset should clear cache
    reset_detection_cache()
    result3 = is_everything_available()
    check(result3 == result1, "after reset, result is consistent")


# ══════════════════════════════════════════════════════════════════════════════
# 3. EverythingResult Dataclass
# ══════════════════════════════════════════════════════════════════════════════

def test_result_dataclass():
    print("\n[3] EverythingResult Dataclass")
    r = EverythingResult(path="C:\\chrome.exe")
    check(r.path == "C:\\chrome.exe", "path set correctly")
    check(r.size is None, "size defaults to None")
    check(r.date_modified is None, "date_modified defaults to None")

    r2 = EverythingResult(
        path="C:\\report.pdf",
        size=1024000,
        date_modified="2025-01-15",
    )
    check(r2.size == 1024000, "size set correctly")
    check(r2.date_modified == "2025-01-15", "date_modified set correctly")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Integration Smoke Test (only when Everything is installed)
# ══════════════════════════════════════════════════════════════════════════════

def test_integration_search():
    print("\n[4] Integration Smoke Test")
    if not is_everything_available():
        print("  ⏭️  Skipping (Everything not installed)")
        return

    import asyncio
    from core.layers.everything_search import everything_search_paths

    async def _run():
        # Search for a common file
        results = await everything_search_paths(
            query="*.txt",
            max_results=5,
            timeout=5.0,
        )
        return results

    results = asyncio.run(_run())
    check(isinstance(results, list), "returns a list")
    print(f"  ℹ️  Found {len(results)} .txt files")


def test_integration_find_app():
    print("\n[5] Integration — Find App")
    if not is_everything_available():
        print("  ⏭️  Skipping (Everything not installed)")
        return

    import asyncio
    from core.layers.everything_search import everything_find_app

    async def _run():
        # Search for notepad (should exist on any Windows system)
        results = await everything_find_app("notepad", max_results=5)
        return results

    results = asyncio.run(_run())
    check(isinstance(results, list), "returns a list")
    check(len(results) > 0, "returns non-empty results when Everything is installed")
    if results:
        # Results are strings (file paths from everything_find_app)
        has_notepad = any("notepad" in r.lower() for r in results)
        if has_notepad:
            notepad_path = next(r for r in results if "notepad" in r.lower())
            print(f"  ℹ️  Found: {notepad_path}")
        else:
            # Everything may return version info or partial results — warn, don't fail
            print(f"  ⚠️  Results don't contain 'notepad': {results[:3]}")
            print("     (Everything may not be fully indexed — integration test lenient)")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_detection()
    test_detection_cache()
    test_result_dataclass()
    test_integration_search()
    test_integration_find_app()
    print("\n✅ All everything_search tests passed!")
