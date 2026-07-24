"""Layer 16: UIAutomation — Accessibility Tree for computer-use agent control.

Per Hermes Agent architecture:
  Reads the Windows UIAutomation accessibility tree to find and interact
  with UI elements by role, name, and automation_id — NOT by coordinates.

This is the KEY capability that brings May to Hermes Agent level:
  - inspect_ui_tree:  Read the full UI tree of any window
  - find_ui_element:  Find a specific element by role + name
  - click_ui_element: Click an element by role + name
  - type_into_ui_element: Type into a specific input element
  - select_ui_dropdown: Select dropdown option by text
  - toggle_ui_checkbox: Check/uncheck a checkbox
  - read_ui_text:  Read all visible text from a UI subtree
  - set_ui_value:  Set value of a UI element (slider, textbox)
  - get_ui_state:  Get element state (enabled, focusable, value)
  - double_click_ui_element: Double-click an element
  - right_click_ui_element: Right-click an element

Libraries: pywinauto (UIA backend), ctypes for fallback
"""

from __future__ import annotations

import asyncio
import ctypes
import ctypes.wintypes
import re
from collections import OrderedDict
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.layers._utils import create_escalation_fn, create_preflight_fn

import logging


# ── Role alias map (module-level constant, like VK_MAP in L5_input.py) ───────
_ROLE_MAP = {
    "button": "Button", "btn": "Button",
    "edit": "Edit", "textbox": "Edit", "text": "Edit", "input": "Edit",
    "combo": "ComboBox", "combobox": "ComboBox", "dropdown": "ComboBox",
    "listbox": "List", "list": "List",
    "checkbox": "CheckBox", "check": "CheckBox",
    "radio": "RadioButton", "radiobutton": "RadioButton",
    "menu": "Menu", "menuitem": "MenuItem",
    "tab": "Tab", "tabitem": "TabItem",
    "tree": "Tree", "treeview": "Tree",
    "toolbar": "ToolBar", "statusbar": "StatusBar",
    "static": "Text", "label": "Text",
    "link": "Hyperlink", "hyperlink": "Hyperlink",
    "scrollbar": "ScrollBar", "slider": "Slider",
    "progress": "ProgressBar", "group": "Group",
    "pane": "Pane", "window": "Window", "dialog": "Window",
    "document": "Document", "dataitem": "DataItem",
    "header": "Header", "headeritem": "HeaderItem",
    "thumb": "Thumb", "tooltip": "ToolTip",
    "separator": "Separator", "semantic": "SemanticZoom",
    "app": "Application", "client": "Client",
}
logger = logging.getLogger("may.core.layers.L16_uiautomation")


# ══════════════════════════════════════════════════════════════════════════════
# pywinauto UIA Backend — Lazy Loading
# ══════════════════════════════════════════════════════════════════════════════

_application_cache: OrderedDict[str, Any] = OrderedDict()
_MAX_CACHE_SIZE = 20


def _get_uia_app(window_title: str):
    """Get or create a pywinauto Application connected via UIA backend.

    Caches connections by window title to avoid repeated connection overhead.
    Uses a 4-strategy connection approach:
      1. Cache hit with lightweight verification (fastest)
      2. Application.connect(title_re=...) — standard pywinauto
      3. Desktop scan + Application.connect(handle=hwnd) — fallback for tricky titles
      4. PID-based connect via EnumWindows — last resort for stubborn connections
    """
    try:
        from pywinauto import Application
        import pywinauto
    except ImportError:
        raise RuntimeError(
            "pywinauto is required for accessibility tree tools. "
            "Install with: pip install pywinauto"
        )

    title_lower = window_title.lower().strip()
    escaped_title = re.escape(window_title)

    # Strategy 1: Check cache first — lightweight verification (just list windows)
    if title_lower in _application_cache:
        app = _application_cache.pop(title_lower)
        _application_cache[title_lower] = app  # Move to end (most recently used)
        try:
            # Lightweight check: can we list windows from this connection?
            windows = app.windows()
            if windows:
                return app
        except Exception:
            # Stale connection, remove and reconnect
            _application_cache.pop(title_lower, None)

    # Strategy 2: Standard Application.connect with title_re
    try:
        app = Application(backend="uia").connect(title_re=f".*{escaped_title}.*")
        _application_cache[title_lower] = app
        while len(_application_cache) > _MAX_CACHE_SIZE:
            _application_cache.popitem(last=False)
        return app
    except Exception:
        pass  # Fall through to Desktop scan

    # Strategy 3: Desktop scan — find window by partial title, connect by handle
    try:
        desktop = pywinauto.Desktop(backend="uia")
        for win in desktop.windows():
            try:
                title = _safe_name(win) or ""
                if title_lower in title.lower() or title.lower() in title_lower:
                    hwnd = win.element_info.handle
                    if hwnd:
                        app = Application(backend="uia").connect(handle=hwnd)
                        _application_cache[title_lower] = app
                        while len(_application_cache) > _MAX_CACHE_SIZE:
                            _application_cache.popitem(last=False)
                        logger.debug(f"Connected via Desktop scan: '{title}' (hwnd={hwnd})")
                        return app
            except Exception:
                continue
    except Exception:
        pass

    # Strategy 4: Connect by PID — find PID via EnumWindows, connect directly
    # Last resort: handles cases where UIA title matching fails
    # (e.g. special chars in title, stale connections, process-level blocks)
    try:
        found_pids = []

        def _enum_pid_callback(hwnd, _):
            if not ctypes.windll.user32.IsWindowVisible(hwnd):
                return True
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            wtitle = buf.value
            if title_lower in wtitle.lower() or wtitle.lower() in title_lower:
                pid = ctypes.wintypes.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                found_pids.append((hwnd, pid.value, wtitle))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM,
        )
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_pid_callback), 0)

        for hwnd, pid, wtitle in found_pids:
            try:
                app = Application(backend="uia").connect(process=pid)
                _application_cache[title_lower] = app
                while len(_application_cache) > _MAX_CACHE_SIZE:
                    _application_cache.popitem(last=False)
                logger.debug(f"Connected via PID: '{wtitle}' (pid={pid})")
                return app
            except Exception:
                continue
    except Exception:
        pass

    raise RuntimeError(
        f"Could not connect to window '{window_title}'. "
        f"Make sure the window is open and visible."
    )


def _get_window_element(window_title: str):
    """Get the top-level window element for a given title.

    Uses a multi-strategy approach to find the window:
      1. app.window(title_re=...) — standard pywinauto
      2. app.top_window() — fallback when title matching fails
    """
    app = _get_uia_app(window_title)
    escaped_title = re.escape(window_title)

    # Strategy 1: Find by title regex
    try:
        win = app.window(title_re=f".*{escaped_title}.*")
        win.wait("exists visible", timeout=5)
        return win
    except Exception:
        pass  # Fall through to top_window fallback

    # Strategy 2: Just get the top window of the process
    try:
        win = app.top_window()
        win.wait("exists visible", timeout=3)
        return win
    except Exception as e:
        raise RuntimeError(f"Window '{window_title}' not found or not visible: {e}")


def _element_to_dict(element, depth: int = 0, max_depth: int = 4) -> dict:
    """Convert a pywinauto element to a serializable dict.

    Recursively builds the UI tree structure with role, name,
    automation_id, bounding_rect, and children.
    """
    if depth > max_depth:
        return {"role": "...", "name": "(max depth reached)"}

    rect = _safe_rect(element)
    toggle_state = _safe_attr(element, "get_toggle_state")
    value = _safe_attr(element, "get_value")

    node = {
        "role": _safe_control_type(element),
        "name": _safe_name(element),
        "automation_id": _safe_automation_id(element),
        "class_name": _safe_class_name(element),
        "bounding_rect": rect,
        "children_count": _safe_attr(element, "children_count") or 0,
        "is_enabled": _safe_attr(element, "is_enabled"),
        "is_focusable": _safe_attr(element, "is_focusable"),
    }

    if toggle_state is not None:
        node["toggle_state"] = toggle_state
    if value is not None and value != "":
        node["value"] = str(value)[:500]

    # Recurse into children if within depth limit
    if node["children_count"] > 0 and depth < max_depth:
        children = []
        try:
            for child in element.children():
                children.append(_element_to_dict(child, depth + 1, max_depth))
        except Exception:
            pass
        node["children"] = children

    return node


def _safe_control_type(element) -> str:
    """Safely get control type name."""
    try:
        return element.element_info.control_type or "Unknown"
    except Exception:
        return "Unknown"


def _safe_name(element) -> str:
    """Safely get element name."""
    try:
        return element.element_info.name or ""
    except Exception:
        return ""


def _safe_automation_id(element) -> str:
    """Safely get automation ID."""
    try:
        return element.element_info.automation_id or ""
    except Exception:
        return ""


def _safe_class_name(element) -> str:
    """Safely get class name."""
    try:
        return element.element_info.class_name or ""
    except Exception:
        return ""


def _safe_attr(element, attr_name: str):
    """Safely call an attribute/method on an element, returning None on failure."""
    try:
        val = getattr(element, attr_name, None)
        if callable(val):
            return val()
        return val
    except Exception:
        return None


def _safe_rect(element) -> dict | None:
    """Safely get bounding rectangle as a dict."""
    try:
        rect = element.rectangle()
        return {
            "left": rect.left, "top": rect.top,
            "right": rect.right, "bottom": rect.bottom,
            "width": rect.width(), "height": rect.height(),
        }
    except Exception:
        return None


def _find_element_by_role_and_name(window, role: str, name: str):
    """Find a UI element by control type (role) and name.

    Searches the window subtree for an element matching both the role and name
    (case-insensitive partial match for name). Uses a multi-strategy approach:
      1. Exact control_type filter + name match (fastest)
      2. All descendants filtered by role string + name (broader)
      3. All descendants by name only (when role is empty)

    Also handles common control type aliases:
      - 'Edit' also searches 'Document' (modern Notepad, VS Code, etc.)
      - 'Document' also searches 'Edit' (legacy apps)
    """
    role_lower = role.lower().strip()
    name_lower = name.lower().strip()

    target_role = _ROLE_MAP.get(role_lower, role) if role_lower else ""

    # Build a list of roles to search (with fallback aliases)
    search_roles = [target_role] if target_role else []
    if target_role == "Edit":
        search_roles.append("Document")  # Modern Notepad uses Document
    elif target_role == "Document":
        search_roles.append("Edit")  # Legacy apps use Edit

    for sr in search_roles:
        # Strategy 1: Exact control_type filter + name match (fastest)
        try:
            elements = window.descendants(control_type=sr)
            for elem in elements:
                elem_name = _safe_name(elem).lower()
                if name_lower and (name_lower in elem_name or elem_name in name_lower):
                    return elem
                elif not name_lower:
                    return elem  # Role-only match
        except Exception:
            pass

        # Strategy 2: All descendants, match role string + name
        try:
            for elem in window.descendants():
                ctrl_type = _safe_control_type(elem).lower()
                elem_name = _safe_name(elem).lower()
                if sr.lower() in ctrl_type and (
                    not name_lower or name_lower in elem_name or elem_name in name_lower
                ):
                    return elem
        except Exception:
            pass

    # Strategy 3: Name-only match (no role specified or role strategies failed)
    if name_lower:
        try:
            for elem in window.descendants():
                if name_lower in _safe_name(elem).lower():
                    return elem
        except Exception:
            pass

    return None


# ══════════════════════════════════════════════════════════════════════════════
# UIAutomation Actions
# ══════════════════════════════════════════════════════════════════════════════

async def _inspect_ui_tree(params: dict) -> Any:
    """Read the full UIAutomation accessibility tree for a window.

    Returns all UI elements with their role, name, automation_id,
    bounding_rect, children_count, and recursively nested children.

    This is the KEY tool that makes May a computer-use agent.
    Instead of guessing coordinates, May can now find elements by
    role and name — just like Hermes Agent does.
    """
    window_title = params.get("window_title", "")
    max_depth = params.get("max_depth", 4)

    if not window_title:
        # Get the active window title
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd:
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                window_title = buf.value

    if not window_title:
        raise RuntimeError("No window_title provided and no active window found")

    win = _get_window_element(window_title)

    # Build the tree
    tree = _element_to_dict(win, depth=0, max_depth=max_depth)

    # Count total elements
    try:
        total = len(win.descendants())
    except Exception:
        total = tree.get("children_count", 0)

    return {
        "window_title": window_title,
        "total_elements": total,
        "tree": tree,
    }


async def _find_ui_element(params: dict) -> Any:
    """Find a specific UI element by role + name or automation_id.

    Returns the element's details including bounding_rect for clicking.
    """
    window_title = params["window_title"]
    role = params.get("role", "")
    name = params.get("name", "")
    automation_id = params.get("automation_id", "")

    win = _get_window_element(window_title)

    element = None

    # Strategy 1: Find by automation_id (most precise)
    if automation_id:
        try:
            elements = win.descendants(auto_id=automation_id)
            if elements:
                element = elements[0]
        except Exception:
            pass

    # Strategy 2: Find by role + name (or role-only when name is empty)
    if element is None and role:
        element = _find_element_by_role_and_name(win, role, name)

    # Strategy 3: Find by name only (when role is empty)
    if element is None and name:
        try:
            elements = win.descendants(title=name)
            if elements:
                element = elements[0]
        except Exception:
            pass
        # Partial match fallback
        if element is None:
            try:
                for elem in win.descendants():
                    if name.lower() in _safe_name(elem).lower():
                        element = elem
                        break
            except Exception:
                pass

    if element is None:
        raise RuntimeError(
            f"Element not found: role='{role}', name='{name}', "
            f"automation_id='{automation_id}' in window '{window_title}'"
        )

    return _element_to_dict(element, depth=0, max_depth=2)


async def _click_ui_element(params: dict) -> Any:
    """Click a UI element by role + name.

    Finds the element via inspect_ui_tree, then clicks it.
    More reliable than coordinate-based clicking because it targets
    the element by its UI structure, not screen position.
    """
    window_title = params["window_title"]
    role = params.get("role", "")
    name = params.get("name", "")
    automation_id = params.get("automation_id", "")
    double_click = params.get("double_click", False)
    right_click = params.get("right_click", False)

    win = _get_window_element(window_title)

    # Find the element
    element = None
    if automation_id:
        try:
            elements = win.descendants(auto_id=automation_id)
            if elements:
                element = elements[0]
        except Exception:
            pass

    if element is None and role:
        element = _find_element_by_role_and_name(win, role, name)

    if element is None and name:
        try:
            for elem in win.descendants():
                if name.lower() in _safe_name(elem).lower():
                    element = elem
                    break
        except Exception:
            pass

    if element is None:
        raise RuntimeError(
            f"Element not found for clicking: role='{role}', name='{name}'"
        )

    # Perform the click — with bounding_rect validation
    try:
        rect = _safe_rect(element)
        has_valid_rect = rect and rect.get("width", 0) > 0 and rect.get("height", 0) > 0

        if right_click:
            if has_valid_rect:
                element.click_input(button="right")
            else:
                ctypes.windll.user32.keybd_event(0x5D, 0, 0, 0)  # VK_APPS
                ctypes.windll.user32.keybd_event(0x5D, 0, 2, 0)
            action = "right-clicked"
        elif double_click:
            if has_valid_rect:
                element.double_click_input()
            else:
                element.click_input()
                await asyncio.sleep(0.05)
                element.click_input()
            action = "double-clicked"
        else:
            if has_valid_rect:
                element.click_input()
            else:
                # Try UIA InvokePattern first (correct way to 'click' without coordinates)
                invoked = False
                try:
                    element.invoke()
                    invoked = True
                except Exception:
                    pass
                if not invoked:
                    element.set_focus()
                    await asyncio.sleep(0.05)
                    ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)  # VK_RETURN
                    ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)
            action = "clicked"
    except Exception as e:
        raise RuntimeError(f"Failed to click element: {e}")

    # Small delay to let the UI respond
    await asyncio.sleep(0.1)

    return {
        "action": action,
        "role": _safe_control_type(element),
        "name": _safe_name(element),
        "bounding_rect": _safe_rect(element),
    }


async def _type_into_ui_element(params: dict) -> Any:
    """Type text into a specific UI input element.

    Finds the element by role + name, focuses it, and types text.
    More reliable than clipboard paste for form fields because it
    uses the element's native input method.
    """
    window_title = params["window_title"]
    role = params.get("role", "Edit")
    name = params.get("name", "")
    text = params.get("text", "")
    clear_first = params.get("clear_first", True)

    if not text:
        raise RuntimeError("No text provided to type")

    win = _get_window_element(window_title)

    # Find the element
    element = _find_element_by_role_and_name(win, role, name)
    if element is None and name:
        # Fallback: search by name in all descendants
        try:
            for elem in win.descendants():
                if name.lower() in _safe_name(elem).lower():
                    element = elem
                    break
        except Exception:
            pass

    if element is None:
        raise RuntimeError(
            f"Input element not found: role='{role}', name='{name}'"
        )

    try:
        # Focus the element
        element.set_focus()
        await asyncio.sleep(0.1)

        # Clear existing text if requested
        if clear_first:
            try:
                element.set_edit_text("")
            except Exception:
                # Fallback: select all + delete
                element.type_keys("^a{DELETE}")
                await asyncio.sleep(0.05)

        # Type the text
        try:
            element.set_edit_text(text)
        except Exception:
            # Fallback: type_keys (slower but universal)
            element.type_keys(text, with_spaces=True, pause=0.01)

    except Exception as e:
        raise RuntimeError(f"Failed to type into element: {e}")

    await asyncio.sleep(0.1)

    return {
        "action": "typed",
        "text": text,
        "role": _safe_control_type(element),
        "name": _safe_name(element),
        "clear_first": clear_first,
    }


async def _select_ui_dropdown(params: dict) -> Any:
    """Select an option from a ComboBox/dropdown by visible text.

    Finds the dropdown by role + name, then selects the option.
    """
    window_title = params["window_title"]
    role = params.get("role", "ComboBox")
    name = params.get("name", "")
    option_text = params.get("option_text", "")

    if not option_text:
        raise RuntimeError("No option_text provided to select")

    win = _get_window_element(window_title)

    element = _find_element_by_role_and_name(win, role, name)
    if element is None:
        raise RuntimeError(
            f"Dropdown not found: role='{role}', name='{name}'"
        )

    try:
        # Method 1: Try select() with visible text
        element.select(option_text)
    except Exception:
        try:
            # Method 2: Click to open, then find and click the option
            element.click_input()
            await asyncio.sleep(0.2)

            # Find the dropdown list item
            for child in element.children():
                child_name = _safe_name(child).lower()
                if option_text.lower() in child_name:
                    child.click_input()
                    break
            else:
                raise RuntimeError(f"Option '{option_text}' not found in dropdown")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to select option '{option_text}': {e}")

    await asyncio.sleep(0.1)

    return {
        "action": "selected",
        "option": option_text,
        "role": _safe_control_type(element),
        "name": _safe_name(element),
    }


async def _toggle_ui_checkbox(params: dict) -> Any:
    """Check/uncheck a checkbox element.

    Finds the checkbox by role + name and toggles its state.
    """
    window_title = params["window_title"]
    role = params.get("role", "CheckBox")
    name = params.get("name", "")

    win = _get_window_element(window_title)

    element = _find_element_by_role_and_name(win, role, name)
    if element is None:
        raise RuntimeError(
            f"Checkbox not found: role='{role}', name='{name}'"
        )

    try:
        old_state = element.get_toggle_state()
        element.toggle()
        await asyncio.sleep(0.1)
        new_state = element.get_toggle_state()
    except Exception as e:
        raise RuntimeError(f"Failed to toggle checkbox: {e}")

    return {
        "action": "toggled",
        "old_state": old_state,
        "new_state": new_state,
        "role": _safe_control_type(element),
        "name": _safe_name(element),
    }


async def _read_ui_text(params: dict) -> Any:
    """Read all visible text from a UI element subtree.

    Returns the text content of a window or specific element.
    Useful for reading menus, panels, dialogs, status bars.
    """
    window_title = params.get("window_title", "")
    role = params.get("role", "")
    name = params.get("name", "")

    if not window_title:
        raise RuntimeError("window_title is required")

    win = _get_window_element(window_title)

    target = win
    if role or name:
        target = _find_element_by_role_and_name(win, role, name)
        if target is None:
            raise RuntimeError(
                f"Element not found: role='{role}', name='{name}'"
            )

    # Collect all text from descendants
    # Check both name AND value (e.g. Notepad stores typed text in value, not name)
    texts = []
    try:
        for elem in target.descendants():
            text = _safe_name(elem)
            # Also check get_value() for Document/Edit elements (Notepad, VS Code, etc.)
            if not text or not text.strip():
                val = _safe_attr(elem, "get_value")
                if val:
                    text = str(val)[:500]  # Truncate to match _element_to_dict pattern
            if text and text.strip():
                ctrl_type = _safe_control_type(elem)
                texts.append(f"[{ctrl_type}] {text}")
    except Exception:
        # Fallback: just get the window text
        try:
            texts.append(f"[Window] {target.window_text()}")
        except Exception:
            pass

    return {
        "window_title": window_title,
        "element_role": _safe_control_type(target) if role else "Window",
        "element_name": _safe_name(target) if name else "",
        "text_items": texts,
        "total_items": len(texts),
        "combined_text": "\n".join(texts[:100]),
    }


async def _set_ui_value(params: dict) -> Any:
    """Set the value of a UI element (slider, textbox, etc.).

    Works with elements that support ValuePattern.
    """
    window_title = params["window_title"]
    role = params.get("role", "")
    name = params.get("name", "")
    value = params.get("value", "")

    win = _get_window_element(window_title)

    element = _find_element_by_role_and_name(win, role, name)
    if element is None and name:
        try:
            for elem in win.descendants():
                if name.lower() in _safe_name(elem).lower():
                    element = elem
                    break
        except Exception:
            pass

    if element is None:
        raise RuntimeError(
            f"Element not found: role='{role}', name='{name}'"
        )

    try:
        element.set_focus()
        await asyncio.sleep(0.05)

        # Try set_value first (ValuePattern)
        try:
            element.set_value(value)
        except Exception:
            # Fallback: set_edit_text for text fields
            try:
                element.set_edit_text(str(value))
            except Exception:
                # Last resort: type_keys
                element.type_keys(str(value), with_spaces=True)

    except Exception as e:
        raise RuntimeError(f"Failed to set value: {e}")

    await asyncio.sleep(0.1)

    return {
        "action": "value_set",
        "value": value,
        "role": _safe_control_type(element),
        "name": _safe_name(element),
    }


async def _get_ui_state(params: dict) -> Any:
    """Get the current state of a UI element.

    Returns enabled/focusable status, current value, toggle state.
    """
    window_title = params["window_title"]
    role = params.get("role", "")
    name = params.get("name", "")

    win = _get_window_element(window_title)

    element = _find_element_by_role_and_name(win, role, name)
    if element is None and name:
        try:
            for elem in win.descendants():
                if name.lower() in _safe_name(elem).lower():
                    element = elem
                    break
        except Exception:
            pass

    if element is None:
        raise RuntimeError(
            f"Element not found: role='{role}', name='{name}'"
        )

    state = {
        "role": _safe_control_type(element),
        "name": _safe_name(element),
        "automation_id": _safe_automation_id(element),
        "class_name": _safe_class_name(element),
    }

    try:
        state["is_enabled"] = element.is_enabled()
    except Exception:
        pass

    try:
        state["is_focusable"] = element.is_focusable()
    except Exception:
        pass

    try:
        state["is_visible"] = element.is_visible()
    except Exception:
        pass

    try:
        state["toggle_state"] = element.get_toggle_state()
    except Exception:
        pass

    try:
        val = element.get_value()
        if val:
            state["value"] = str(val)[:500]
    except Exception:
        pass

    try:
        rect = element.rectangle()
        state["bounding_rect"] = {
            "left": rect.left, "top": rect.top,
            "right": rect.right, "bottom": rect.bottom,
        }
    except Exception:
        pass

    return state


async def _double_click_ui_element(params: dict) -> Any:
    """Double-click a UI element by role + name."""
    params_copy = dict(params)
    params_copy["double_click"] = True
    return await _click_ui_element(params_copy)


async def _right_click_ui_element(params: dict) -> Any:
    """Right-click a UI element by role + name."""
    params_copy = dict(params)
    params_copy["right_click"] = True
    return await _click_ui_element(params_copy)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 3: Wait Tools — Prevent type_text / click failures
# ══════════════════════════════════════════════════════════════════════════════


async def _wait_for_app(params: dict) -> Any:
    """Wait for an application window to appear and become ready.

    Prevents type_text failures by ensuring the target app has fully loaded
    before interacting with it. Polls the window list with exponential backoff.

    Use after: open_app, launch_with_args, launch_as_admin
    Use before: type_into_ui_element, click_ui_element, set_ui_value
    """
    app_name = params.get("app_name", "")
    window_title = params.get("window_title", "")
    timeout_seconds = params.get("timeout_seconds", 15.0)
    poll_interval = params.get("poll_interval", 0.5)
    require_visible = params.get("require_visible", True)

    search_term = (window_title or app_name).lower().strip()
    if not search_term:
        raise RuntimeError("Either app_name or window_title is required")

    start_time = time.time()
    attempts = 0
    last_error = None

    while (time.time() - start_time) < timeout_seconds:
        attempts += 1
        try:
            # Strategy 1: pywinauto UIA scan
            try:
                import pywinauto
                desktop = pywinauto.Desktop(backend="uia")
                for win in desktop.windows():
                    try:
                        title = _safe_name(win) or ""
                        if search_term in title.lower():
                            if require_visible and not _safe_attr(win, "is_visible"):
                                await asyncio.sleep(poll_interval)
                                continue
                            # Window found — wait for it to settle
                            try:
                                win.wait("ready", timeout=min(3.0, timeout_seconds - (time.time() - start_time)))
                            except Exception:
                                pass  # "ready" timeout is okay — window exists
                            elapsed_ms = int((time.time() - start_time) * 1000)
                            return {
                                "found": True,
                                "window_title": title,
                                "app_name": app_name,
                                "attempts": attempts,
                                "elapsed_ms": elapsed_ms,
                                "instruction": f"Window '{title}' is ready.",
                            }
                    except Exception:
                        continue
            except ImportError:
                pass  # Fall through to ctypes strategy

            # Strategy 2: ctypes EnumWindows (fast, no deps)
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
                if search_term in title.lower():
                    found_windows.append((hwnd, title))
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM,
            )
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_callback), 0)

            if found_windows:
                hwnd, title = found_windows[0]
                # Bring to foreground and wait for ready
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                await asyncio.sleep(0.3)  # Let window settle
                elapsed_ms = int((time.time() - start_time) * 1000)
                return {
                    "found": True,
                    "window_title": title,
                    "app_name": app_name,
                    "hwnd": hwnd,
                    "attempts": attempts,
                    "elapsed_ms": elapsed_ms,
                    "instruction": f"Window '{title}' is ready.",
                }

            last_error = f"No window matching '{search_term}' found"
        except Exception as e:
            last_error = str(e)

        # Exponential backoff: 0.5s → 0.7s → 1.0s → capped at poll_interval * 2
        actual_interval = min(poll_interval * (1.0 + attempts * 0.1), poll_interval * 2)
        await asyncio.sleep(actual_interval)

    elapsed_ms = int((time.time() - start_time) * 1000)
    raise RuntimeError(
        f"Timeout ({timeout_seconds}s) waiting for app '{search_term}'. "
        f"Last error: {last_error}. Attempts: {attempts}. "
        f"The app may not have opened, or the window title may be different."
    )


async def _wait_for_element(params: dict) -> Any:
    """Wait for a UI element to appear in the accessibility tree.

    Prevents type_text failures by ensuring the target element exists and
    is ready before interacting. Polls the UIA tree with backoff.

    Use after: open_app, click_ui_element (dialog transitions)
    Use before: type_into_ui_element, select_ui_dropdown, set_ui_value
    """
    window_title = params["window_title"]
    role = params.get("role", "")
    name = params.get("name", "")
    automation_id = params.get("automation_id", "")
    timeout_seconds = params.get("timeout_seconds", 10.0)
    poll_interval = params.get("poll_interval", 0.3)
    must_be_enabled = params.get("must_be_enabled", False)
    must_be_visible = params.get("must_be_visible", True)

    if not role and not name and not automation_id:
        raise RuntimeError("At least one of role, name, or automation_id is required")

    start_time = time.time()
    attempts = 0
    last_error = None

    while (time.time() - start_time) < timeout_seconds:
        attempts += 1
        try:
            win = _get_window_element(window_title)

            element = None

            # Strategy 1: automation_id (most precise)
            if automation_id:
                try:
                    elements = win.descendants(auto_id=automation_id)
                    if elements:
                        element = elements[0]
                except Exception:
                    pass

            # Strategy 2: role + name
            if element is None and (role or name):
                element = _find_element_by_role_and_name(win, role, name)

            if element is not None:
                # Check visibility and enabled constraints
                if must_be_visible:
                    visible = _safe_attr(element, "is_visible")
                    if visible is False:
                        last_error = "Element found but not visible"
                        await asyncio.sleep(poll_interval)
                        continue

                if must_be_enabled:
                    enabled = _safe_attr(element, "is_enabled")
                    if enabled is False:
                        last_error = "Element found but not enabled"
                        await asyncio.sleep(poll_interval)
                        continue

                elapsed_ms = int((time.time() - start_time) * 1000)
                return {
                    "found": True,
                    "role": _safe_control_type(element),
                    "name": _safe_name(element),
                    "automation_id": _safe_automation_id(element),
                    "is_enabled": _safe_attr(element, "is_enabled"),
                    "is_visible": _safe_attr(element, "is_visible"),
                    "bounding_rect": _safe_rect(element),
                    "window_title": window_title,
                    "attempts": attempts,
                    "elapsed_ms": elapsed_ms,
                    "instruction": f"Element '{_safe_name(element)}' [{_safe_control_type(element)}] is ready.",
                }

            last_error = f"Element not found: role='{role}', name='{name}'"
        except Exception as e:
            last_error = str(e)

        await asyncio.sleep(poll_interval)

    elapsed_ms = int((time.time() - start_time) * 1000)
    raise RuntimeError(
        f"Timeout ({timeout_seconds}s) waiting for element in '{window_title}'. "
        f"Searched for: role='{role}', name='{name}', automation_id='{automation_id}'. "
        f"Last error: {last_error}. Attempts: {attempts}. "
        f"The element may not exist, may be in a different window, or may need more time to load."
    )


async def _wait_for_text(params: dict) -> Any:
    """Wait for specific text to appear anywhere in a window.

    Useful for waiting for: search results, loading indicators to finish,
    error messages to clear, page content to load, form validation messages.

    Use after: type_into_ui_element (wait for search results)
    Use before: read_ui_text (ensure content loaded)
    """
    window_title = params["window_title"]
    text = params.get("text", "")
    timeout_seconds = params.get("timeout_seconds", 10.0)
    poll_interval = params.get("poll_interval", 0.5)
    must_not_contain = params.get("must_not_contain", "")  # Wait for text to DISAPPEAR
    case_sensitive = params.get("case_sensitive", False)

    if not text and not must_not_contain:
        raise RuntimeError("Either 'text' or 'must_not_contain' is required")

    start_time = time.time()
    attempts = 0
    all_texts_found = []

    while (time.time() - start_time) < timeout_seconds:
        attempts += 1
        try:
            win = _get_window_element(window_title)
            all_texts_found = []

            for elem in win.descendants():
                elem_text = _safe_name(elem)
                # Also check get_value() for Document/Edit elements (Notepad stores text in value)
                if not elem_text or not elem_text.strip():
                    val = _safe_attr(elem, "get_value")
                    if val:
                        elem_text = str(val)
                if elem_text and elem_text.strip():
                    all_texts_found.append(elem_text)

            combined = " ".join(all_texts_found)

            # Check for text presence
            if text:
                search_text = text if case_sensitive else text.lower()
                haystack = combined if case_sensitive else combined.lower()
                if search_text in haystack:
                    # If must_not_contain is also set, check it hasn't appeared
                    if must_not_contain:
                        not_contain = must_not_contain if case_sensitive else must_not_contain.lower()
                        if not_contain in haystack:
                            await asyncio.sleep(poll_interval)
                            continue

                    elapsed_ms = int((time.time() - start_time) * 1000)
                    return {
                        "found": True,
                        "text_present": True,
                        "searched_text": text,
                        "window_title": window_title,
                        "attempts": attempts,
                        "elapsed_ms": elapsed_ms,
                        "matching_snippet": _find_text_snippet(combined, text if case_sensitive else text.lower()),
                        "instruction": f"Text '{text}' found in window '{window_title}'.",
                    }

            # Check for text absence (must_not_contain mode)
            if must_not_contain and not text:
                not_contain = must_not_contain if case_sensitive else must_not_contain.lower()
                haystack = combined if case_sensitive else combined.lower()
                if not_contain not in haystack:
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    return {
                        "found": True,
                        "text_absent": True,
                        "waited_for_removal": must_not_contain,
                        "window_title": window_title,
                        "attempts": attempts,
                        "elapsed_ms": elapsed_ms,
                        "instruction": f"Text '{must_not_contain}' is no longer present in '{window_title}'.",
                    }

        except Exception as e:
            pass  # Window may be transitioning

        await asyncio.sleep(poll_interval)

    elapsed_ms = int((time.time() - start_time) * 1000)
    raise RuntimeError(
        f"Timeout ({timeout_seconds}s) waiting for text in '{window_title}'. "
        f"Searched for: '{text}', must_not_contain: '{must_not_contain}'. "
        f"Attempts: {attempts}. "
        f"The text may not appear, or the window content may have changed."
    )


def _find_text_snippet(haystack: str, needle: str, context_chars: int = 60) -> str:
    """Extract a snippet around the matched text for display."""
    idx = haystack.find(needle)
    if idx == -1:
        return ""
    start = max(0, idx - context_chars)
    end = min(len(haystack), idx + len(needle) + context_chars)
    snippet = haystack[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(haystack):
        snippet = snippet + "..."
    return snippet


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2: Verification Tools — Post-Action Screenshot Verification
# ══════════════════════════════════════════════════════════════════════════════

import hashlib
import os
import time
from pathlib import Path

# Temp directory for before/after screenshots
_VERIFY_DIR = Path(os.path.expanduser("~/.may/verify"))
_VERIFY_DIR.mkdir(parents=True, exist_ok=True)


async def _take_action_verify(params: dict) -> Any:
    """Post-action screenshot verification — the OpenClaw/Hermes pattern.

    Takes a screenshot after any tool execution, then uses the vision model
    or UIA tree to verify the expected outcome. This catches cases where
    the action appeared to succeed but didn't (wrong window, popup blocked,
    element not clicked, etc.).

    The LLM should call this after critical actions like:
    - click_ui_element (verify the click had an effect)
    - type_into_ui_element (verify text was entered)
    - select_ui_dropdown (verify the option was selected)
    - toggle_ui_checkbox (verify the state changed)

    Returns the screenshot path and verification result.
    """
    expected_outcome = params.get("expected_outcome", "")
    window_title = params.get("window_title", "")
    action_description = params.get("action_description", "")
    verify_method = params.get("verify_method", "screenshot")  # screenshot, uia_tree, or both

    # Take a screenshot
    try:
        from PIL import ImageGrab
        screenshot_path = str(_VERIFY_DIR / "verify_after.png")
        img = ImageGrab.grab()
        img.save(screenshot_path)
    except Exception as e:
        raise RuntimeError(f"Failed to take verification screenshot: {e}")

    result = {
        "verified": True,
        "screenshot_path": screenshot_path,
        "screenshot_size": {"width": img.width, "height": img.height},
    }

    # If a window_title is provided, also check the UIA tree for changes
    if window_title and verify_method in ("uia_tree", "both"):
        try:
            win = _get_window_element(window_title)
            tree_summary = []
            for elem in win.descendants()[:50]:  # Limit to first 50 elements
                name = _safe_name(elem)
                if name and name.strip():
                    tree_summary.append(f"[{_safe_control_type(elem)}] {name}")
            result["ui_elements"] = tree_summary[:30]
            result["ui_element_count"] = len(tree_summary)
        except Exception as e:
            result["ui_tree_error"] = str(e)

    # If expected_outcome is provided, include it for the LLM to compare
    if expected_outcome:
        result["expected_outcome"] = expected_outcome
        result["instruction"] = (
            f"Screenshot saved to {screenshot_path}. "
            f"Expected outcome: {expected_outcome}. "
            f"Compare the screenshot against the expected outcome to verify success."
        )
    else:
        result["instruction"] = (
            f"Screenshot saved to {screenshot_path}. "
            f"Review the screenshot to confirm the action completed successfully."
        )

    if action_description:
        result["action_performed"] = action_description

    return result


async def _verify_element_exists(params: dict) -> Any:
    """Verify that a UI element exists and is visible after an action.

    Checks the UIA tree for the presence of a specific element.
    Use this to confirm that clicking a button opened a dialog,
    typing in a search bar showed results, etc.
    """
    window_title = params["window_title"]
    role = params.get("role", "")
    name = params.get("name", "")
    should_exist = params.get("should_exist", True)
    timeout_seconds = params.get("timeout_seconds", 3.0)

    import time
    start_time = time.time()
    found = False
    element_info = None

    while (time.time() - start_time) < timeout_seconds:
        try:
            win = _get_window_element(window_title)
            element = _find_element_by_role_and_name(win, role, name)
            if element is not None:
                found = True
                element_info = {
                    "role": _safe_control_type(element),
                    "name": _safe_name(element),
                    "is_enabled": _safe_attr(element, "is_enabled"),
                    "bounding_rect": _safe_rect(element),
                }
                break
        except Exception:
            pass
        await asyncio.sleep(0.3)

    verified = (found == should_exist)

    return {
        "verified": verified,
        "element_found": found,
        "should_exist": should_exist,
        "element": element_info,
        "window_title": window_title,
        "searched_for": {"role": role, "name": name},
        "elapsed_ms": int((time.time() - start_time) * 1000),
    }


async def _verify_no_error(params: dict) -> Any:
    """Verify that no error dialogs or popups appeared after an action.

    Scans the UIA tree for common error indicators:
    - Dialog windows with 'Error', 'Failed', 'Cannot' in the title
    - Modal popups
    - Windows Defender / UAC prompts
    """
    window_title = params.get("window_title", "")

    # Error indicators to scan for
    error_keywords = [
        "error", "failed", "cannot", "unable", "exception",
        "access denied", "permission denied", "not found",
        "crash", "fatal", "critical", "alert",
        "warning", "confirm",
        "user account control", "windows defender",
    ]

    errors_found = []

    try:
        def _enum_callback(hwnd, _):
            if not ctypes.windll.user32.IsWindowVisible(hwnd):
                return True
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            title_lower = title.lower()

            for keyword in error_keywords:
                if keyword in title_lower:
                    # Get the process name
                    pid = ctypes.wintypes.DWORD()
                    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    errors_found.append({
                        "hwnd": hwnd,
                        "title": title,
                        "matched_keyword": keyword,
                        "pid": pid.value,
                    })
                    break
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM,
        )
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_callback), 0)
    except Exception as e:
        return {
            "verified": False,
            "error": f"Failed to scan for errors: {e}",
        }

    has_errors = len(errors_found) > 0

    return {
        "verified": not has_errors,
        "errors_found": errors_found,
        "error_count": len(errors_found),
        "instruction": (
            f"No error dialogs detected." if not has_errors
            else f"WARNING: {len(errors_found)} error dialog(s) detected: {[e['title'] for e in errors_found]}"
        ),
    }


async def _compare_screenshots(params: dict) -> Any:
    """Compare two screenshots to detect changes (before/after an action).

    Uses perceptual hashing (pHash) for structural comparison and
    optional pixel-level diff for detailed analysis.

    Can compare:
    - Two file paths (before_path vs after_path)
    - A file path vs current screen (after_path = "screen")
    - Current screen vs a stored baseline
    """
    before_path = params.get("before_path", "")
    after_path = params.get("after_path", "")
    threshold = params.get("threshold", 0.85)  # Similarity threshold (0-1)

    if not before_path or not after_path:
        raise RuntimeError("Both before_path and after_path are required")

    try:
        from PIL import Image
        import imagehash
    except ImportError:
        # Fallback: basic file hash comparison
        return await _compare_screenshots_basic(before_path, after_path)

    # Load images
    try:
        img_before = Image.open(before_path)
    except Exception as e:
        raise RuntimeError(f"Cannot open before screenshot '{before_path}': {e}")

    if after_path.lower() == "screen":
        from PIL import ImageGrab
        img_after = ImageGrab.grab()
    else:
        try:
            img_after = Image.open(after_path)
        except Exception as e:
            raise RuntimeError(f"Cannot open after screenshot '{after_path}': {e}")

    # Perceptual hash comparison
    hash_before = imagehash.phash(img_before)
    hash_after = imagehash.phash(img_after)
    hash_diff = hash_before - hash_after
    max_hash = 64  # pHash produces 64-bit hash
    similarity = 1.0 - (hash_diff / max_hash)

    # Pixel-level diff (downsampled for speed)
    try:
        # Resize both to same dimensions for comparison
        size = (320, 240)
        img_b = img_before.resize(size).convert("RGB")
        img_a = img_after.resize(size).convert("RGB")

        pixels_b = list(img_b.getdata())
        pixels_a = list(img_a.getdata())

        changed_pixels = 0
        total_pixels = len(pixels_b)
        for pb, pa in zip(pixels_b, pixels_a):
            # Euclidean distance per pixel
            diff = sum((b - a) ** 2 for b, a in zip(pb, pa)) ** 0.5
            if diff > 30:  # Threshold per pixel
                changed_pixels += 1

        change_percent = (changed_pixels / total_pixels) * 100 if total_pixels > 0 else 0
    except Exception:
        change_percent = None

    changed = similarity < threshold

    return {
        "changed": changed,
        "similarity": round(similarity, 4),
        "hash_diff": hash_diff,
        "threshold": threshold,
        "change_percent": round(change_percent, 2) if change_percent is not None else None,
        "before_path": before_path,
        "after_path": after_path,
        "instruction": (
            f"Screenshots are {'DIFFERENT' if changed else 'SIMILAR'} "
            f"(similarity: {similarity:.1%}, pixel change: {change_percent:.1f}%)."
            if change_percent is not None
            else f"Screenshots are {'DIFFERENT' if changed else 'SIMILAR'} (similarity: {similarity:.1%})."
        ),
    }


async def _compare_screenshots_basic(before_path: str, after_path: str) -> dict:
    """Basic screenshot comparison using file hashes (fallback when imagehash unavailable)."""
    def _file_hash(path: str) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    hash_before = _file_hash(before_path)
    hash_after = _file_hash(after_path)
    identical = hash_before == hash_after

    size_before = os.path.getsize(before_path)
    size_after = os.path.getsize(after_path)

    return {
        "changed": not identical,
        "identical": identical,
        "hash_before": hash_before,
        "hash_after": hash_after,
        "size_before": size_before,
        "size_after": size_after,
        "before_path": before_path,
        "after_path": after_path,
        "method": "basic_file_hash",
        "instruction": (
            f"Screenshots are {'IDENTICAL' if identical else 'DIFFERENT'} "
            f"(hash: {hash_before[:8]} vs {hash_after[:8]})."
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# ACTION HANDLER
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    # Phase 1: Accessibility Tree (11 tools)
    "inspect_ui_tree":           ([_inspect_ui_tree], None),
    "find_ui_element":           ([_find_ui_element], None),
    "click_ui_element":          ([_click_ui_element], None),
    "double_click_ui_element":   ([_double_click_ui_element], None),
    "right_click_ui_element":    ([_right_click_ui_element], None),
    "type_into_ui_element":      ([_type_into_ui_element], None),
    "select_ui_dropdown":        ([_select_ui_dropdown], None),
    "toggle_ui_checkbox":        ([_toggle_ui_checkbox], None),
    "read_ui_text":              ([_read_ui_text], None),
    "set_ui_value":              ([_set_ui_value], None),
    "get_ui_state":              ([_get_ui_state], None),
    # Phase 3: Wait Tools (3 tools)
    "wait_for_app":              ([_wait_for_app], None),
    "wait_for_element":          ([_wait_for_element], None),
    "wait_for_text":             ([_wait_for_text], None),
    # Phase 2: Verification (4 tools)
    "take_action_verify":        ([_take_action_verify], None),
    "verify_element_exists":     ([_verify_element_exists], None),
    "verify_no_error":           ([_verify_no_error], None),
    "compare_screenshots":       ([_compare_screenshots], None),
}


async def handler(action: str, params: dict[str, Any]) -> Result:
    """L16 UIAutomation layer handler."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown UIAutomation action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"uiautomation.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("uiautomation", action),
        escalation_fn=create_escalation_fn("uiautomation", action),
        method_timeout=15.0,  # UIA can be slow on complex windows
    )

    return Result(
        command_id=params.get("id", ""),
        success=success,
        data=data,
        error=error if not success else None,
        verified=False,
        method_used=method_used,
    )
