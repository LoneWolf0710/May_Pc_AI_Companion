"""Unit tests for _try_fast_path() -- skip LLM for simple commands.

Tests all 13 pattern categories:
1. open_app (single word + aliases)
2. close_app (single word + system process guard)
3. volume_up
4. volume_down
5. set_mute
6. set_volume (with level)
7. get_time
8. get_date
9. battery_info
10. screenshot
11. get_system_info
12. test_internet
13. get_weather

Plus edge cases:
- Multi-word app aliases (file explorer, google chrome, etc.)
- Case insensitivity
- Whitespace handling
- Confirmation bypass (messages like "yes" skip fast-path)
- System process guard (close explorer/svchost blocked)
- Unknown messages return None (need LLM)
"""

import sys
import os

# Add backend to path
_project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_backend = os.path.join(_project_root, "backend")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from llm.jarvis import _try_fast_path, _is_confirmation

_passed = 0
_failed = 0


def check(condition: bool, name: str, details: str = ""):
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  [PASS] {name}")
    else:
        _failed += 1
        msg = f"  [FAIL] {name}"
        if details:
            msg += f" -- {details}"
        print(msg)


def test_open_app_single_word():
    print("\n[1] open_app -- single word")
    # Basic open
    r = _try_fast_path("open notepad")
    check(r is not None and r[0] == "open_app" and r[1]["app_name"] == "notepad", "open notepad")

    r = _try_fast_path("launch chrome")
    check(r is not None and r[0] == "open_app" and r[1]["app_name"] == "chrome", "launch chrome")

    r = _try_fast_path("start spotify")
    check(r is not None and r[0] == "open_app" and r[1]["app_name"] == "spotify", "start spotify")

    r = _try_fast_path("run code")
    check(r is not None and r[0] == "open_app" and r[1]["app_name"] == "code", "run code")

    # Case insensitive
    r = _try_fast_path("Open Notepad")
    check(r is not None and r[1]["app_name"] == "notepad", "Open Notepad (case)")

    r = _try_fast_path("OPEN STORE")
    check(r is not None and r[1]["app_name"] == "store", "OPEN STORE (case)")

    # With whitespace
    r = _try_fast_path("  open notepad  ")
    check(r is not None and r[1]["app_name"] == "notepad", "open notepad (whitespace)")


def test_open_app_aliases():
    print("\n[2] open_app -- multi-word aliases")
    r = _try_fast_path("open file explorer")
    check(r is not None and r[1]["app_name"] == "explorer", "open file explorer -> explorer", str(r))

    r = _try_fast_path("open windows explorer")
    check(r is not None and r[1]["app_name"] == "explorer", "open windows explorer -> explorer", str(r))

    r = _try_fast_path("open google chrome")
    check(r is not None and r[1]["app_name"] == "chrome", "open google chrome -> chrome", str(r))

    r = _try_fast_path("open visual studio code")
    check(r is not None and r[1]["app_name"] == "vscode", "open visual studio code -> vscode", str(r))

    r = _try_fast_path("open vs code")
    check(r is not None and r[1]["app_name"] == "vscode", "open vs code -> vscode", str(r))

    r = _try_fast_path("open microsoft store")
    check(r is not None and r[1]["app_name"] == "store", "open microsoft store -> store", str(r))

    r = _try_fast_path("open windows store")
    check(r is not None and r[1]["app_name"] == "store", "open windows store -> store", str(r))

    r = _try_fast_path("open this pc")
    check(r is not None and r[1]["app_name"] == "this pc", "open this pc -> this pc", str(r))


def test_open_app_unknown_multiword():
    print("\n[3] open_app -- unknown multi-word (should fail, no alias match)")
    r = _try_fast_path("open visual studio 2022")
    check(r is None, "open visual studio 2022 -> None (no alias)", str(r))

    r = _try_fast_path("open my custom app")
    check(r is None, "open my custom app -> None (no alias)", str(r))


def test_close_app():
    print("\n[4] close_app -- basic")
    r = _try_fast_path("close notepad")
    check(r is not None and r[0] == "close_app" and r[1]["app_name"] == "notepad", "close notepad")

    r = _try_fast_path("quit chrome")
    check(r is not None and r[0] == "close_app" and r[1]["app_name"] == "chrome", "quit chrome")

    r = _try_fast_path("kill spotify")
    check(r is not None and r[0] == "close_app" and r[1]["app_name"] == "spotify", "kill spotify")

    r = _try_fast_path("exit vim")
    check(r is not None and r[0] == "close_app" and r[1]["app_name"] == "vim", "exit vim")


def test_close_system_processes():
    print("\n[5] close_app -- system process guard")
    _blocked = ["pc", "computer", "this pc", "explorer", "svchost",
                "csrss", "wininit", "smss", "lsass", "services"]
    for name in _blocked:
        r = _try_fast_path(f"close {name}")
        check(r is None, f"close {name} -> None (blocked)", str(r))

    # Also test kill and quit variants
    r = _try_fast_path("kill explorer")
    check(r is None, "kill explorer -> None (blocked)", str(r))

    r = _try_fast_path("quit svchost")
    check(r is None, "quit svchost -> None (blocked)", str(r))


def test_volume_up():
    print("\n[6] volume_up")
    for phrase in ["volume up", "vol up", "louder", "volume+"]:
        r = _try_fast_path(phrase)
        check(r is not None and r[0] == "volume_up", f"volume_up: '{phrase}'", str(r))


def test_volume_down():
    print("\n[7] volume_down")
    for phrase in ["volume down", "vol down", "quieter", "softer", "volume-"]:
        r = _try_fast_path(phrase)
        check(r is not None and r[0] == "volume_down", f"volume_down: '{phrase}'", str(r))


def test_mute_unmute():
    print("\n[8] set_mute")
    r = _try_fast_path("mute")
    check(r is not None and r[0] == "set_mute" and r[1]["muted"] is True, "mute")

    r = _try_fast_path("mute volume")
    check(r is not None and r[0] == "set_mute" and r[1]["muted"] is True, "mute volume")

    r = _try_fast_path("silence")
    check(r is not None and r[0] == "set_mute" and r[1]["muted"] is True, "silence")

    r = _try_fast_path("unmute")
    check(r is not None and r[0] == "set_mute" and r[1]["muted"] is False, "unmute")

    r = _try_fast_path("unmute volume")
    check(r is not None and r[0] == "set_mute" and r[1]["muted"] is False, "unmute volume")


def test_set_volume():
    print("\n[9] set_volume")
    r = _try_fast_path("volume 50")
    check(r is not None and r[0] == "set_volume" and r[1]["level"] == 50, "volume 50")

    r = _try_fast_path("volume to 80")
    check(r is not None and r[0] == "set_volume" and r[1]["level"] == 80, "volume to 80")

    r = _try_fast_path("set volume 100")
    check(r is not None and r[0] == "set_volume" and r[1]["level"] == 100, "set volume 100")

    r = _try_fast_path("set volume to 0")
    check(r is not None and r[0] == "set_volume" and r[1]["level"] == 0, "set volume to 0")

    # Edge: 101 should not match (out of range 0-100)
    r = _try_fast_path("volume 101")
    check(r is None, "volume 101 -> None (out of range)", str(r))


def test_time():
    print("\n[10] get_time")
    for phrase in ["what time", "time", "what time is it", "current time", "tell me the time"]:
        r = _try_fast_path(phrase)
        check(r is not None and r[0] == "get_time", f"get_time: '{phrase}'", str(r))


def test_date():
    print("\n[11] get_date")
    for phrase in ["what day", "date", "what date is it", "what day is it", "today"]:
        r = _try_fast_path(phrase)
        check(r is not None and r[0] == "get_date", f"get_date: '{phrase}'", str(r))


def test_battery():
    print("\n[12] battery_info")
    for phrase in ["battery", "battery status", "how much battery", "battery level", "power"]:
        r = _try_fast_path(phrase)
        check(r is not None and r[0] == "battery_info", f"battery: '{phrase}'", str(r))


def test_screenshot():
    print("\n[13] screenshot")
    for phrase in ["screenshot", "take screenshot", "capture screen", "screen capture", "take a screenshot"]:
        r = _try_fast_path(phrase)
        check(r is not None and r[0] == "screenshot", f"screenshot: '{phrase}'", str(r))


def test_system_info():
    print("\n[14] get_system_info")
    for phrase in ["system info", "system status", "pc info", "computer info", "specs"]:
        r = _try_fast_path(phrase)
        check(r is not None and r[0] == "get_system_info", f"system_info: '{phrase}'", str(r))


def test_internet():
    print("\n[15] test_internet")
    for phrase in ["internet status", "test internet", "internet", "am i online"]:
        r = _try_fast_path(phrase)
        check(r is not None and r[0] == "test_internet", f"internet: '{phrase}'", str(r))


def test_weather():
    print("\n[16] get_weather")
    for phrase in ["weather", "weather outside", "current weather"]:
        r = _try_fast_path(phrase)
        check(r is not None and r[0] == "get_weather", f"weather: '{phrase}'", str(r))


def test_no_match():
    print("\n[17] No match -- needs LLM")
    _need_llm = [
        "hello how are you",
        "what is the capital of france",
        "open notepad and write hello",  # multi-step
        "tell me a joke",
        "what's 2+2",
        "search for cats on google",
        "remind me to drink water",
        "play some music",
    ]
    for msg in _need_llm:
        r = _try_fast_path(msg)
        check(r is None, f"LLM needed: '{msg}'", str(r))


def test_confirmation_bypass():
    print("\n[18] Confirmation bypass -- 'yes' etc. should not match fast-path")
    _confirmations = ["yes", "confirm", "yeah", "yep", "y", "ok", "okay", "do it", "go ahead", "sure"]
    for msg in _confirmations:
        is_conf = _is_confirmation(msg)
        check(is_conf, f"_is_confirmation('{msg}') = True")
        # fast-path should NOT match for confirmations (jarvis_chat checks _is_confirmation first)
        # But _try_fast_path itself doesn't check -- that's done in jarvis_chat


def test_whitespace_case():
    print("\n[19] Whitespace and case handling")
    r = _try_fast_path("  Open  Notepad  ")
    check(r is not None and r[1]["app_name"] == "notepad", "whitespace+case: '  Open  Notepad  '")

    r = _try_fast_path("VOLUME UP")
    check(r is not None and r[0] == "volume_up", "case: VOLUME UP")

    r = _try_fast_path("MUTE")
    check(r is not None and r[0] == "set_mute", "case: MUTE")

    r = _try_fast_path("BATTERY")
    check(r is not None and r[0] == "battery_info", "case: BATTERY")


def main():
    global _passed, _failed
    _passed = 0
    _failed = 0

    print("=" * 60)
    print("_try_fast_path() Unit Tests")
    print("=" * 60)

    test_open_app_single_word()
    test_open_app_aliases()
    test_open_app_unknown_multiword()
    test_close_app()
    test_close_system_processes()
    test_volume_up()
    test_volume_down()
    test_mute_unmute()
    test_set_volume()
    test_time()
    test_date()
    test_battery()
    test_screenshot()
    test_system_info()
    test_internet()
    test_weather()
    test_no_match()
    test_confirmation_bypass()
    test_whitespace_case()

    print("\n" + "=" * 60)
    total = _passed + _failed
    print(f"Results: {_passed}/{total} passed, {_failed} failed")
    if _failed == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"{_failed} TEST(S) FAILED")
    print("=" * 60)

    return _failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
