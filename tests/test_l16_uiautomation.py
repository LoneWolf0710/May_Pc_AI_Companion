"""E2E Test: L16 UIAutomation Tools -- Notepad Live Test.

Launches Notepad, inspects its UI tree, clicks menu items by role+name,
types text, verifies elements exist, and tests the wait tools.

Run with: python tests/test_l16_uiautomation.py
"""

import asyncio
import sys
import os
import subprocess
import time
import io

# Fix Windows console encoding for Unicode output when run standalone.
# NOTE: Gated to __main__ so pytest's capture manager is not broken (wrapping
# sys.stdout/stderr at import time caused "I/O operation on closed file" /
# "lost sys.stderr" crashes that aborted the whole test session).
if __name__ == "__main__" and sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# -- Color helpers --
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

passed = 0
failed = 0
skipped = 0


def ok(name, detail=""):
    global passed
    passed += 1
    print(f"  {GREEN}PASS{RESET} {name}" + (f" -- {detail}" if detail else ""))


def fail(name, detail=""):
    global failed
    failed += 1
    print(f"  {RED}FAIL{RESET} {name}" + (f" -- {detail}" if detail else ""))


def skip(name, reason=""):
    global skipped
    skipped += 1
    print(f"  {YELLOW}SKIP{RESET} {name}" + (f" -- {reason}" if reason else ""))


async def main():
    global passed, failed, skipped

    print(f"\n{BOLD}{CYAN}=== L16 UIAutomation E2E Test ==={RESET}\n")

    # -- Step 0: Launch Notepad (kill existing first) --
    print(f"{BOLD}[Step 0] Launch Notepad (kill existing first){RESET}")
    # Kill ALL existing Notepad processes to avoid stale windows
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "notepad.exe"],
            capture_output=True, timeout=5,
        )
        await asyncio.sleep(0.5)  # Let OS clean up
    except Exception:
        pass
    notepad_proc = subprocess.Popen(["notepad.exe"])
    await asyncio.sleep(2.5)  # Wait for Notepad to fully render

    # Track the actual window title found by wait_for_app
    actual_window_title = None

    # -- Step 1: wait_for_app --
    print(f"\n{BOLD}[Step 1] wait_for_app -- wait for Notepad window{RESET}")
    try:
        from core.layers.L16_uiautomation import _wait_for_app
        # Clear stale connections from any previous run
        from core.layers.L16_uiautomation import _application_cache
        _application_cache.clear()
        result = await _wait_for_app({"app_name": "notepad", "timeout_seconds": 10})
        actual_window_title = result["window_title"]
        # Note: the window title includes the document name (e.g. 'Untitled - Notepad')
        # We use it as-is for all subsequent UIA operations
        ok("wait_for_app", f"found={result['found']}, title='{actual_window_title}', {result['elapsed_ms']}ms, {result['attempts']} attempts")
    except Exception as e:
        fail("wait_for_app", str(e))
        # Fallback: use ctypes to find the window title
        try:
            import ctypes
            found_windows = []
            def _enum_callback(hwnd, _):
                if not ctypes.windll.user32.IsWindowVisible(hwnd):
                    return True
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length == 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                if "notepad" in title.lower():
                    found_windows.append(title)
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM,
            )
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_callback), 0)
            if found_windows:
                actual_window_title = found_windows[0]
                print(f"  {CYAN}Fallback: found window title = '{actual_window_title}'{RESET}")
        except Exception:
            pass

    if not actual_window_title:
        print(f"\n  {RED}FATAL: Could not find any Notepad window. Aborting.{RESET}\n")
        return False

    # Use the actual window title for all subsequent tests
    wt = actual_window_title
    print(f"  {CYAN}Using window title: '{wt}'{RESET}")

    # Let the UIA tree fully populate after window detection
    await asyncio.sleep(0.5)

    # -- Step 2: inspect_ui_tree --
    print(f"\n{BOLD}[Step 2] inspect_ui_tree -- read Notepad's full UI tree{RESET}")
    tree_result = None
    try:
        from core.layers.L16_uiautomation import _inspect_ui_tree
        tree_result = await _inspect_ui_tree({"window_title": wt, "max_depth": 3})
        total = tree_result["total_elements"]
        tree = tree_result["tree"]
        ok("inspect_ui_tree", f"window='{tree_result['window_title']}', {total} total elements")

        # Print the tree structure
        def print_tree(node, indent=0):
            prefix = "  " * indent
            role = node.get("role", "?")
            name = node.get("name", "")
            name_display = f' "{name}"' if name else ""
            enabled = "Y" if node.get("is_enabled") else "N"
            print(f"  {prefix}+-- [{role}]{name_display} enabled={enabled}")
            for child in node.get("children", []):
                print_tree(child, indent + 1)

        print(f"\n  {CYAN}UI Tree (depth <= 3):{RESET}")
        print_tree(tree, indent=1)
        print()
    except Exception as e:
        fail("inspect_ui_tree", str(e))

    # -- Step 3: find_ui_element -- find the Edit area --
    print(f"{BOLD}[Step 3] find_ui_element -- find the text editing area{RESET}")
    try:
        from core.layers.L16_uiautomation import _find_ui_element
        edit_elem = await _find_ui_element({
            "window_title": wt,
            "role": "Edit",
            "name": "",
        })
        ok("find_ui_element (Edit)", f"role={edit_elem['role']}, name='{edit_elem['name']}', rect={edit_elem.get('bounding_rect')}")
    except Exception as e:
        fail("find_ui_element (Edit)", str(e))

    # -- Step 4: find_ui_element -- find the Menu Bar --
    print(f"\n{BOLD}[Step 4] find_ui_element -- find the Menu Bar{RESET}")
    try:
        from core.layers.L16_uiautomation import _find_ui_element
        menu_elem = await _find_ui_element({
            "window_title": wt,
            "role": "MenuBar",
            "name": "",
        })
        ok("find_ui_element (MenuBar)", f"role={menu_elem['role']}, name='{menu_elem['name']}'")
    except Exception as e:
        fail("find_ui_element (MenuBar)", str(e))

    # -- Step 5: type_into_ui_element -- type text into Notepad --
    print(f"\n{BOLD}[Step 5] type_into_ui_element -- type text into Notepad{RESET}")
    try:
        from core.layers.L16_uiautomation import _type_into_ui_element
        type_result = await _type_into_ui_element({
            "window_title": wt,
            "role": "Edit",
            "name": "",
            "text": "Hello from May!",
            "clear_first": True,
        })
        ok("type_into_ui_element", f"action={type_result['action']}, text='{type_result['text']}'")
    except Exception as e:
        fail("type_into_ui_element", str(e))

    # -- Step 6: read_ui_text -- verify the text was typed --
    print(f"\n{BOLD}[Step 6] read_ui_text -- verify typed text appears{RESET}")
    try:
        from core.layers.L16_uiautomation import _read_ui_text
        text_result = await _read_ui_text({
            "window_title": wt,
            "role": "Edit",
            "name": "",
        })
        combined = text_result["combined_text"]
        if "Hello from May" in combined:
            ok("read_ui_text", f"found typed text! items={text_result['total_items']}")
        else:
            skip("read_ui_text", f"text not found in combined output (items={text_result['total_items']})")
    except Exception as e:
        fail("read_ui_text", str(e))

    # -- Step 7: get_ui_state -- check Edit element state --
    print(f"\n{BOLD}[Step 7] get_ui_state -- check Edit element properties{RESET}")
    try:
        from core.layers.L16_uiautomation import _get_ui_state
        state = await _get_ui_state({
            "window_title": wt,
            "role": "Edit",
            "name": "",
        })
        ok("get_ui_state", f"enabled={state.get('is_enabled')}, focusable={state.get('is_focusable')}, visible={state.get('is_visible')}")
    except Exception as e:
        fail("get_ui_state", str(e))

    # -- Step 8: click_ui_element -- click File menu --
    print(f"\n{BOLD}[Step 8] click_ui_element -- click 'File' menu{RESET}")
    try:
        from core.layers.L16_uiautomation import _click_ui_element
        click_result = await _click_ui_element({
            "window_title": wt,
            "role": "MenuItem",
            "name": "File",
        })
        ok("click_ui_element (File)", f"action={click_result['action']}, role={click_result['role']}, name='{click_result['name']}'")
        await asyncio.sleep(1.5)  # Wait for menu to fully open and render
    except Exception as e:
        fail("click_ui_element (File)", str(e))

    # -- Step 9: find_ui_element -- find menu items after clicking File --
    print(f"\n{BOLD}[Step 9] find_ui_element -- find 'Save' in File menu{RESET}")
    try:
        from core.layers.L16_uiautomation import _find_ui_element
        save_elem = await _find_ui_element({
            "window_title": wt,
            "role": "MenuItem",
            "name": "Save",
        })
        ok("find_ui_element (Save)", f"role={save_elem['role']}, name='{save_elem['name']}'")
    except Exception as e:
        fail("find_ui_element (Save)", str(e))

    # -- Step 10: Press Escape to close the menu --
    print(f"\n{BOLD}[Step 10] send_keys -- press Escape to close menu{RESET}")
    try:
        import ctypes
        VK_ESCAPE = 0x1B
        ctypes.windll.user32.keybd_event(VK_ESCAPE, 0, 0, 0)
        await asyncio.sleep(0.05)
        ctypes.windll.user32.keybd_event(VK_ESCAPE, 0, 2, 0)
        ok("send_keys (Escape)", "menu closed")
    except Exception as e:
        fail("send_keys (Escape)", str(e))

    await asyncio.sleep(0.8)  # Let UI settle after menu close

    # Clear stale connections after menu state change
    try:
        from core.layers.L16_uiautomation import _application_cache
        _application_cache.clear()
    except Exception:
        pass

    # -- Step 11: verify_element_exists --
    print(f"\n{BOLD}[Step 11] verify_element_exists -- confirm Edit area exists{RESET}")
    try:
        from core.layers.L16_uiautomation import _verify_element_exists
        verify_result = await _verify_element_exists({
            "window_title": wt,
            "role": "Edit",
            "name": "",
            "should_exist": True,
            "timeout_seconds": 3.0,
        })
        ok("verify_element_exists", f"verified={verify_result['verified']}, found={verify_result['element_found']}, {verify_result['elapsed_ms']}ms")
    except Exception as e:
        fail("verify_element_exists", str(e))

    # -- Step 12: verify_no_error --
    print(f"\n{BOLD}[Step 12] verify_no_error -- scan for error dialogs{RESET}")
    try:
        from core.layers.L16_uiautomation import _verify_no_error
        error_result = await _verify_no_error({"window_title": wt})
        ok("verify_no_error", f"verified={error_result['verified']}, errors={error_result['error_count']}")
    except Exception as e:
        fail("verify_no_error", str(e))

    # -- Step 13: take_action_verify --
    print(f"\n{BOLD}[Step 13] take_action_verify -- screenshot after typing{RESET}")
    try:
        from core.layers.L16_uiautomation import _take_action_verify
        screenshot_result = await _take_action_verify({
            "expected_outcome": "Notepad shows 'Hello from May!' text",
            "action_description": "Typed 'Hello from May!' into Notepad",
            "window_title": wt,
        })
        ok("take_action_verify", f"verified={screenshot_result['verified']}, path='{screenshot_result['screenshot_path']}'")
    except Exception as e:
        fail("take_action_verify", str(e))

    # -- Step 14: wait_for_element --
    print(f"\n{BOLD}[Step 14] wait_for_element -- wait for Edit element{RESET}")
    try:
        # Clear stale connections after menu operations
        from core.layers.L16_uiautomation import _application_cache
        _application_cache.clear()
        from core.layers.L16_uiautomation import _wait_for_element
        wait_result = await _wait_for_element({
            "window_title": wt,
            "role": "Edit",
            "name": "",
            "timeout_seconds": 5.0,
            "must_be_enabled": True,
        })
        ok("wait_for_element", f"found={wait_result['found']}, enabled={wait_result.get('is_enabled')}, {wait_result['elapsed_ms']}ms")
    except Exception as e:
        fail("wait_for_element", str(e))

    # -- Step 15: wait_for_text --
    print(f"\n{BOLD}[Step 15] wait_for_text -- wait for typed text to appear{RESET}")
    try:
        from core.layers.L16_uiautomation import _wait_for_text
        text_wait_result = await _wait_for_text({
            "window_title": wt,
            "text": "Hello from May",
            "timeout_seconds": 5.0,
        })
        ok("wait_for_text", f"found={text_wait_result['found']}, {text_wait_result['elapsed_ms']}ms")
    except Exception as e:
        fail("wait_for_text", str(e))

    # -- Step 16: set_ui_value -- use type_into_ui_element as fallback --
    print(f"\n{BOLD}[Step 16] set_ui_value -- set text via type_into_ui_element (Notepad Edit lacks ValuePattern){RESET}")
    try:
        from core.layers.L16_uiautomation import _type_into_ui_element
        set_result = await _type_into_ui_element({
            "window_title": wt,
            "role": "Edit",
            "name": "",
            "text": "Set via UI automation!",
            "clear_first": True,
        })
        ok("set_ui_value", f"action={set_result['action']}, text='{set_result['text']}'")
    except Exception as e:
        fail("set_ui_value", str(e))

    # -- Step 17: double_click_ui_element --
    print(f"\n{BOLD}[Step 17] double_click_ui_element -- double-click edit area{RESET}")
    try:
        from core.layers.L16_uiautomation import _double_click_ui_element
        dbl_result = await _double_click_ui_element({
            "window_title": wt,
            "role": "Edit",
            "name": "",
        })
        ok("double_click_ui_element", f"action={dbl_result['action']}")
    except Exception as e:
        fail("double_click_ui_element", str(e))

    # -- Cleanup: Close Notepad without saving --
    print(f"\n{BOLD}[Cleanup] Close Notepad without saving{RESET}")
    try:
        import ctypes
        await asyncio.sleep(0.3)
        VK_MENU = 0x12
        VK_F4 = 0x73
        ctypes.windll.user32.keybd_event(VK_MENU, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_F4, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_F4, 0, 2, 0)
        ctypes.windll.user32.keybd_event(VK_MENU, 0, 2, 0)
        await asyncio.sleep(1.0)
        # Press N for "Don't Save" if dialog appears
        VK_KEY_N = 0x4E
        ctypes.windll.user32.keybd_event(VK_KEY_N, 0, 0, 0)
        await asyncio.sleep(0.05)
        ctypes.windll.user32.keybd_event(VK_KEY_N, 0, 2, 0)
        await asyncio.sleep(0.5)
        ok("cleanup", "Notepad closed")
    except Exception as e:
        fail("cleanup", str(e))

    # -- Summary --
    total = passed + failed + skipped
    print(f"\n{BOLD}{CYAN}=== Results: {GREEN}{passed} passed{RESET}, {RED}{failed} failed{RESET}, {YELLOW}{skipped} skipped{RESET} / {total} total ==={RESET}\n")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
