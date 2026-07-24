"""
Live integration test for type_text across multiple apps.

Tests:
1. Notepad — simple text editor (baseline)
2. VS Code — Electron app (may intercept Ctrl+V)
3. Chrome — Browser address bar or text field
4. PowerShell window — terminal input
5. Windows Terminal — modern terminal

Each test:
- Opens the app via open_app
- Waits for it to load
- Types text via type_text with window_title
- Verifies the text was typed by Ctrl+A → Ctrl+C → Get-Clipboard
- Reports which strategy was used

Run: python -m pytest tests/test_type_text_live.py -v -s
"""

import asyncio
import sys
import os
import time
import subprocess
import logging

# Add project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("test_type_text_live")


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

async def open_app(app_name: str) -> bool:
    """Open an app using the core bus daemon."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("http://localhost:7650", json={
                "layer": "application",
                "action": "open_app",
                "params": {"app_name": app_name}
            })
            if resp.status_code == 200:
                data = resp.json()
                success = data.get("success", False)
                logger.info("open_app(%s) → success=%s", app_name, success)
                return success
            else:
                logger.error("open_app(%s) HTTP %d: %s", app_name, resp.status_code, resp.text[:200])
                return False
    except Exception as e:
        logger.error("open_app(%s) failed: %s", app_name, e)
        return False


async def close_app(app_name: str) -> bool:
    """Close an app using the core bus daemon."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("http://localhost:7650", json={
                "layer": "application",
                "action": "close_app",
                "params": {"app_name": app_name}
            })
            return resp.status_code == 200 and resp.json().get("success", False)
    except Exception:
        return False


async def type_text(text: str, window_title: str = "") -> dict:
    """Type text using the type_text action."""
    import httpx
    params = {"text": text}
    if window_title:
        params["window_title"] = window_title
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post("http://localhost:7650", json={
                "layer": "input",
                "action": "type_text",
                "params": params
            })
            if resp.status_code == 200:
                data = resp.json()
                logger.info("type_text → %s", data.get("data", {}))
                return data
            else:
                logger.error("type_text HTTP %d: %s", resp.status_code, resp.text[:200])
                return {"success": False, "error": resp.text}
    except Exception as e:
        logger.error("type_text failed: %s", e)
        return {"success": False, "error": str(e)}


async def select_all_and_copy(window_title: str) -> str:
    """Select all text and copy to clipboard, then return clipboard contents."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Focus window first
            if window_title:
                await client.post("http://localhost:7650", json={
                    "layer": "input",
                    "action": "press_key",
                    "params": {"key": "ctrl"}
                })
                await asyncio.sleep(0.05)

            # Ctrl+A (select all)
            await client.post("http://localhost:7650", json={
                "layer": "input",
                "action": "hotkey",
                "params": {"combo": "ctrl+a"}
            })
            await asyncio.sleep(0.1)

            # Ctrl+C (copy)
            await client.post("http://localhost:7650", json={
                "layer": "input",
                "action": "hotkey",
                "params": {"combo": "ctrl+c"}
            })
            await asyncio.sleep(0.1)

            # Get clipboard
            resp = await client.post("http://localhost:7650", json={
                "layer": "input",
                "action": "get_clipboard",
                "params": {}
            })
            if resp.status_code == 200:
                data = resp.json()
                text = data.get("data", {}).get("text", "")
                return text.strip()
    except Exception as e:
        logger.error("select_all_and_copy failed: %s", e)
    return ""


async def get_foreground_window() -> str:
    """Get the current foreground window title via PowerShell."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "(Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
             "Sort-Object StartTime -Descending | Select-Object -First 1).MainWindowTitle"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return ""


async def wait_for_window(title: str, timeout: float = 10.0) -> bool:
    """Wait for a window with the given title to appear."""
    import httpx
    start = time.time()
    while time.time() - start < timeout:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.post("http://localhost:7650", json={
                    "layer": "application",
                    "action": "list_windows",
                    "params": {}
                })
                if resp.status_code == 200:
                    windows = resp.json().get("data", {}).get("windows", [])
                    for w in windows:
                        wtitle = w.get("title", "").lower()
                        if title.lower() in wtitle:
                            return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return False


async def kill_app_processes(app_name: str):
    """Force kill an app process by name."""
    try:
        subprocess.run(
            ["powershell", "-Command",
             f"Stop-Process -Name '{app_name}' -Force -ErrorAction SilentlyContinue"],
            capture_output=True, timeout=5
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# TEST RESULTS TRACKER
# ══════════════════════════════════════════════════════════════════════════════

results = []


def record(app: str, method: str, expected: str, actual: str, success: bool, notes: str = ""):
    """Record a test result."""
    results.append({
        "app": app,
        "method": method,
        "expected": expected,
        "actual": actual,
        "success": success,
        "notes": notes,
    })
    status = "✅ PASS" if success else "❌ FAIL"
    logger.info("%s %s: expected=%r actual=%r %s", status, app, expected, actual, notes)


# ══════════════════════════════════════════════════════════════════════════════
# LIVE TEST FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

async def test_notepad():
    """Test typing into Notepad."""
    test_text = "Hello from May! 🌸 Testing Notepad type_text."
    app = "notepad"
    logger.info("═══ Testing %s ═══", app.upper())

    # Close any existing Notepad
    await kill_app_processes("Notepad")
    await asyncio.sleep(0.5)

    # Open Notepad
    ok = await open_app(app)
    if not ok:
        record(app, "open_app", "success=True", "success=False", False, "Failed to open app")
        return

    # Wait for Notepad window
    found = await wait_for_window("Notepad", timeout=8.0)
    if not found:
        record(app, "wait_for_window", "found=True", "found=False", False, "Notepad window not found")
        return

    await asyncio.sleep(1.0)  # Extra settle time for Notepad

    # Type text with window_title
    result = await type_text(test_text, window_title="Notepad")
    success = result.get("success", False)
    data = result.get("data", {})
    typed = data.get("typed", 0)
    method = data.get("method", "unknown")

    if not success:
        record(app, method, f"typed={len(test_text)}", f"typed={typed}", False,
               f"Error: {result.get('error', 'unknown')}")
        return

    # Verify by selecting all + copying
    await asyncio.sleep(0.3)
    # First press Ctrl+End to go to end of document
    import httpx
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post("http://localhost:7650", json={
            "layer": "input", "action": "hotkey",
            "params": {"combo": "ctrl+end"}
        })
    await asyncio.sleep(0.2)

    clipboard = await select_all_and_copy("Notepad")
    matched = test_text in clipboard if clipboard else False
    record(app, method, test_text, clipboard[:100] if clipboard else "(empty)", matched,
           f"typed={typed} chars")

    # Clean up
    await close_app(app)


async def test_vscode():
    """Test typing into VS Code (new file)."""
    test_text = "Hello from May! 🌸 Testing VS Code type_text."
    app = "code"
    logger.info("═══ Testing %s ═══", app.upper())

    # Close any existing VS Code (careful — may have unsaved work)
    # Instead, just open a new instance
    ok = await open_app(app)
    if not ok:
        record(app, "open_app", "success=True", "success=False", False, "Failed to open VS Code")
        return

    found = await wait_for_window("Visual Studio Code", timeout=15.0)
    if not found:
        record(app, "wait_for_window", "found=True", "found=False", False, "VS Code window not found")
        return

    await asyncio.sleep(2.0)  # VS Code is slow to fully load

    # Create new file first (Ctrl+N)
    import httpx
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post("http://localhost:7650", json={
            "layer": "input", "action": "hotkey",
            "params": {"combo": "ctrl+n"}
        })
    await asyncio.sleep(1.0)

    # Type text with window_title
    result = await type_text(test_text, window_title="Visual Studio Code")
    success = result.get("success", False)
    data = result.get("data", {})
    typed = data.get("typed", 0)
    method = data.get("method", "unknown")

    if not success:
        record(app, method, f"typed={len(test_text)}", f"typed={typed}", False,
               f"Error: {result.get('error', 'unknown')}")
        return

    # Verify
    await asyncio.sleep(0.3)
    clipboard = await select_all_and_copy("Visual Studio Code")
    matched = test_text in clipboard if clipboard else False
    record(app, method, test_text, clipboard[:100] if clipboard else "(empty)", matched,
           f"typed={typed} chars")

    # Close without saving
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post("http://localhost:7650", json={
            "layer": "input", "action": "hotkey",
            "params": {"combo": "ctrl+w"}
        })
        await asyncio.sleep(0.2)
        await client.post("http://localhost:7650", json={
            "layer": "input", "action": "press_key",
            "params": {"key": "n"}
        })
    await asyncio.sleep(0.5)


async def test_chrome():
    """Test typing into Chrome address bar."""
    test_text = "hello from may"
    app = "chrome"
    logger.info("═══ Testing %s ═══", app.upper())

    ok = await open_app(app)
    if not ok:
        record(app, "open_app", "success=True", "success=False", False, "Failed to open Chrome")
        return

    found = await wait_for_window("Chrome", timeout=10.0)
    if not found:
        record(app, "wait_for_window", "found=True", "found=False", False, "Chrome window not found")
        return

    await asyncio.sleep(1.5)

    # Focus address bar (Ctrl+L)
    import httpx
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post("http://localhost:7650", json={
            "layer": "input", "action": "hotkey",
            "params": {"combo": "ctrl+l"}
        })
    await asyncio.sleep(0.3)

    # Type into address bar
    result = await type_text(test_text, window_title="Chrome")
    success = result.get("success", False)
    data = result.get("data", {})
    typed = data.get("typed", 0)
    method = data.get("method", "unknown")

    if not success:
        record(app, method, f"typed={len(test_text)}", f"typed={typed}", False,
               f"Error: {result.get('error', 'unknown')}")
        return

    # Verify by selecting all + copying
    await asyncio.sleep(0.3)
    clipboard = await select_all_and_copy("Chrome")
    matched = test_text.lower() in clipboard.lower() if clipboard else False
    record(app, method, test_text, clipboard[:100] if clipboard else "(empty)", matched,
           f"typed={typed} chars")

    # Press Escape to dismiss address bar
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post("http://localhost:7650", json={
            "layer": "input", "action": "press_key",
            "params": {"key": "esc"}
        })


async def test_powershell():
    """Test typing into a PowerShell window."""
    test_text = "echo 'Hello from May! Testing PowerShell type_text'"
    app = "PowerShell"
    logger.info("═══ Testing %s ═══", app.upper())

    # Open PowerShell
    ok = await open_app("powershell")
    if not ok:
        record(app, "open_app", "success=True", "success=False", False, "Failed to open PowerShell")
        return

    found = await wait_for_window("PowerShell", timeout=8.0)
    if not found:
        record(app, "wait_for_window", "found=True", "found=False", False, "PowerShell window not found")
        return

    await asyncio.sleep(1.5)

    # Type text
    result = await type_text(test_text, window_title="PowerShell")
    success = result.get("success", False)
    data = result.get("data", {})
    typed = data.get("typed", 0)
    method = data.get("method", "unknown")

    if not success:
        record(app, method, f"typed={len(test_text)}", f"typed={typed}", False,
               f"Error: {result.get('error', 'unknown')}")
        return

    # Don't press Enter — just verify the text is visible
    # Select all + copy to verify
    await asyncio.sleep(0.3)
    clipboard = await select_all_and_copy("PowerShell")
    matched = test_text in clipboard if clipboard else False
    record(app, method, test_text, clipboard[:100] if clipboard else "(empty)", matched,
           f"typed={typed} chars")

    # Press Escape then Ctrl+C to cancel the command line
    import httpx
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post("http://localhost:7650", json={
            "layer": "input", "action": "hotkey",
            "params": {"combo": "ctrl+c"}
        })
    await asyncio.sleep(0.3)

    # Close PowerShell
    await close_app(app)


async def test_windows_terminal():
    """Test typing into Windows Terminal."""
    test_text = "echo 'Hello from May! Testing Windows Terminal type_text'"
    app = "wt"
    logger.info("═══ Testing %s ═══", app.upper())

    ok = await open_app("wt")
    if not ok:
        # Try alternative name
        ok = await open_app("terminal")
    if not ok:
        record(app, "open_app", "success=True", "success=False", False, "Failed to open Windows Terminal")
        return

    found = await wait_for_window("Terminal", timeout=8.0)
    if not found:
        record(app, "wait_for_window", "found=True", "found=False", False, "Windows Terminal window not found")
        return

    await asyncio.sleep(1.5)

    # Type text
    result = await type_text(test_text, window_title="Terminal")
    success = result.get("success", False)
    data = result.get("data", {})
    typed = data.get("typed", 0)
    method = data.get("method", "unknown")

    if not success:
        record(app, method, f"typed={len(test_text)}", f"typed={typed}", False,
               f"Error: {result.get('error', 'unknown')}")
        return

    # Verify
    await asyncio.sleep(0.3)
    clipboard = await select_all_and_copy("Terminal")
    matched = test_text in clipboard if clipboard else False
    record(app, method, test_text, clipboard[:100] if clipboard else "(empty)", matched,
           f"typed={typed} chars")

    # Cancel command line
    import httpx
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post("http://localhost:7650", json={
            "layer": "input", "action": "hotkey",
            "params": {"combo": "ctrl+c"}
        })
    await asyncio.sleep(0.3)


async def test_notepad_long_text():
    """Test typing long text (>50 chars) into Notepad — should use clipboard paste."""
    test_text = "This is a longer text that exceeds the 50-character threshold, so it should be typed using the clipboard paste strategy instead of SendInput char-by-char. 🌸"
    app = "notepad"
    logger.info("═══ Testing %s (LONG TEXT) ═══", app.upper())

    await kill_app_processes("Notepad")
    await asyncio.sleep(0.5)

    ok = await open_app(app)
    if not ok:
        record(app + " (long)", "open_app", "success=True", "success=False", False, "Failed to open")
        return

    found = await wait_for_window("Notepad", timeout=8.0)
    if not found:
        record(app + " (long)", "wait_for_window", "found=True", "found=False", False, "Notepad not found")
        return

    await asyncio.sleep(1.0)

    result = await type_text(test_text, window_title="Notepad")
    success = result.get("success", False)
    data = result.get("data", {})
    typed = data.get("typed", 0)
    method = data.get("method", "unknown")

    if not success:
        record(app + " (long)", method, f"typed={len(test_text)}", f"typed={typed}", False,
               f"Error: {result.get('error', 'unknown')}")
        return

    await asyncio.sleep(0.3)
    import httpx
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post("http://localhost:7650", json={
            "layer": "input", "action": "hotkey",
            "params": {"combo": "ctrl+end"}
        })
    await asyncio.sleep(0.2)
    clipboard = await select_all_and_copy("Notepad")
    matched = test_text in clipboard if clipboard else False
    record(app + " (long)", method, test_text[:60] + "...",
           clipboard[:100] if clipboard else "(empty)", matched,
           f"typed={typed} chars, expected clipboard_paste")

    await close_app(app)


async def test_unicode_text():
    """Test typing Unicode/emoji text into Notepad."""
    test_text = "Unicode test: 你好世界 🌸✨🎉 café résumé über"
    app = "notepad (unicode)"
    logger.info("═══ Testing %s ═══", app.upper())

    await kill_app_processes("Notepad")
    await asyncio.sleep(0.5)

    ok = await open_app("notepad")
    if not ok:
        record(app, "open_app", "success=True", "success=False", False, "Failed to open")
        return

    found = await wait_for_window("Notepad", timeout=8.0)
    if not found:
        record(app, "wait_for_window", "found=True", "found=False", False, "Notepad not found")
        return

    await asyncio.sleep(1.0)

    result = await type_text(test_text, window_title="Notepad")
    success = result.get("success", False)
    data = result.get("data", {})
    typed = data.get("typed", 0)
    method = data.get("method", "unknown")

    await asyncio.sleep(0.3)
    import httpx
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post("http://localhost:7650", json={
            "layer": "input", "action": "hotkey",
            "params": {"combo": "ctrl+end"}
        })
    await asyncio.sleep(0.2)
    clipboard = await select_all_and_copy("Notepad")
    matched = test_text in clipboard if clipboard else False
    record(app, method, test_text[:40] + "...",
           clipboard[:100] if clipboard else "(empty)", matched,
           f"typed={typed} chars")

    await close_app(app)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    """Run all live type_text tests."""
    logger.info("Starting live type_text tests...")

    tests = [
        test_notepad,
        test_notepad_long_text,
        test_unicode_text,
        test_vscode,
        test_chrome,
        test_powershell,
        test_windows_terminal,
    ]

    for test_fn in tests:
        try:
            await test_fn()
        except Exception as e:
            logger.error("Test %s crashed: %s", test_fn.__name__, e)
            record(test_fn.__name__, "crash", "success", "exception", False, str(e))
        await asyncio.sleep(1.0)  # Pause between tests

    # Print summary
    logger.info("")
    logger.info("═" * 80)
    logger.info("RESULTS SUMMARY")
    logger.info("═" * 80)
    passed = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if not r["success"])
    logger.info("Total: %d | Passed: %d | Failed: %d", len(results), passed, failed)
    logger.info("")

    for r in results:
        status = "✅" if r["success"] else "❌"
        logger.info("%s %-25s method=%-25s expected=%r", status, r["app"], r["method"], r["expected"][:50])
        if r["notes"]:
            logger.info("   Notes: %s", r["notes"])

    logger.info("═" * 80)
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
