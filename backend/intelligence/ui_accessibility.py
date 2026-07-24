"""UIAccessibility Reader — Tier 2 of May's 3-Tier Screen Understanding.

Uses the Windows UI Automation API (via `uiautomation` library) to read the
accessibility tree of the active window. This is the SAME API that screen
readers (Narrator, NVDA) use — it works for all modern Windows apps that
expose accessibility info (Chrome, VS Code, Office, etc.).

Key properties:
  - Zero VRAM (pure Windows API, no ML models)
  - ~100ms per read (fast enough for on-change triggering)
  - Provides structured data: buttons, inputs, menus, text, links

From MAY_FINAL_ARCHITECTURE.md Part 3:
  TIER 2: STRUCTURED ANALYSIS (On change, ~100ms)
    OPTION A (preferred — zero VRAM):
      Windows UIAccessibility API reads the accessibility tree
      → Buttons, inputs, menus, text as structured data
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@contextmanager
def _com_initialize():
    """Initialize COM on the current thread for uiautomation API calls.

    The uiautomation library requires COM to be initialized on each thread
    before calling its APIs. This context manager handles CoInitialize/CoUninitialize
    cleanly without the noisy debug output from UIAutomationInitializerInThread.

    Safe to call from any thread — CoInitialize is ref-counted.
    If pythoncom is not available (unlikely since uiautomation depends on it),
    this is a silent no-op.
    """
    try:
        import pythoncom
    except ImportError:
        yield  # pythoncom not available — hope we're on the main thread
        return

    pythoncom.CoInitialize()
    try:
        yield
    finally:
        pythoncom.CoUninitialize()

logger = logging.getLogger("may.intelligence.ui_accessibility")

# Lazy import — uiautomation is Windows-only
_auto = None


def _ensure_uiautomation():
    """Lazy-load the uiautomation library (Windows-only)."""
    global _auto
    if _auto is None:
        try:
            import uiautomation as auto
            _auto = auto
        except ImportError:
            raise ImportError(
                "uiautomation is required for Tier 2 screen reading. "
                "Install with: pip install uiautomation"
            )
    return _auto


# ── Interactive control types (the ones May cares about) ─────────────────

INTERACTIVE_CONTROL_TYPES = frozenset({
    "ButtonControl",
    "EditControl",
    "HyperlinkControl",
    "MenuItemControl",
    "ComboBoxControl",
    "CheckBoxControl",
    "RadioButtonControl",
    "TabControl",
    "DataGridControl",
    "ListControl",
    "ListItemControl",
    "TreeControl",
    "TreeItemControl",
    "ToolBarControl",
    "StatusBarControl",
    "SliderControl",
    "SpinnerControl",
    "ProgressBarControl",
    "DocumentControl",
    "CustomControl",
})

# Error-indicator keywords in element names
_ERROR_KEYWORDS = frozenset([
    "error", "exception", "fault", "failed", "crash",
    "cannot", "unable", "access denied", "not found",
    "not working", "has stopped", "problem", "fatal",
    "warning", "alert", "critical",
])

# Modal/dialog indicator keywords
_MODAL_KEYWORDS = frozenset([
    "dialog", "popup", "modal", "alert", "confirm",
    "save", "discard", "cancel", "open", "browse",
])

# Permission/security keywords
_PERMISSION_KEYWORDS = frozenset([
    "permission", "access", "authorize", "grant", "denied",
    "elevated", "admin", "uac", "security", "credential",
    "password", "login", "sign in",
])


@dataclass
class UIElement:
    """A single UI element from the accessibility tree."""
    name: str = ""
    control_type: str = ""
    automation_id: str = ""
    is_enabled: bool = True
    is_visible: bool = True
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)  # left, top, right, bottom
    children_count: int = 0
    depth: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "control_type": self.control_type,
            "automation_id": self.automation_id,
            "is_enabled": self.is_enabled,
            "is_visible": self.is_visible,
            "bounds": list(self.bounds),
            "children_count": self.children_count,
            "depth": self.depth,
        }


@dataclass
class UIScreenData:
    """Structured data about the current screen from UIAccessibility."""
    window_title: str = ""
    window_class: str = ""
    window_pid: int = 0
    elements: list[UIElement] = field(default_factory=list)
    element_count: int = 0
    interactive_count: int = 0
    error_text: str = ""
    is_modal: bool = False
    control_type: str = ""
    read_time_ms: float = 0
    # Extracted text content (all visible text joined)
    visible_text: str = ""

    def to_dict(self) -> dict:
        return {
            "window_title": self.window_title,
            "window_class": self.window_class,
            "window_pid": self.window_pid,
            "element_count": self.element_count,
            "interactive_count": self.interactive_count,
            "error_text": self.error_text,
            "is_modal": self.is_modal,
            "control_type": self.control_type,
            "read_time_ms": round(self.read_time_ms, 1),
            "visible_text": self.visible_text[:1000],
            "elements": [e.to_dict() for e in self.elements[:50]],  # Cap at 50 elements
        }


class UIAccessibilityReader:
    """Reads the Windows accessibility tree — zero VRAM, zero CPU overhead.

    Uses the same API that screen readers (Narrator, NVDA) use.
    Works for all Windows apps that expose accessibility info
    (which is most modern apps including Chrome, VS Code, Office, etc.).

    Usage:
        reader = UIAccessibilityReader()
        data = reader.get_screen_data()
        print(data.window_title, data.element_count, data.error_text)
    """

    def __init__(self, max_depth: int = 4, timeout_sec: float = 2.0):
        """
        Args:
            max_depth: Maximum tree depth to traverse (prevents deep recursion).
            timeout_sec: Maximum time to spend reading the tree.
        """
        self._max_depth = max_depth
        self._timeout_sec = timeout_sec
        self._last_read: UIScreenData | None = None
        self._available: bool | None = None  # None = not yet checked

    def is_available(self) -> bool:
        """Check if uiautomation is available on this system."""
        if self._available is not None:
            return self._available
        try:
            _ensure_uiautomation()
            self._available = True
        except (ImportError, OSError):
            self._available = False
        return self._available

    def get_screen_data(self) -> UIScreenData:
        """Read the accessibility tree of the currently focused window.

        Returns a UIScreenData with structured information about the screen.
        Falls back gracefully if uiautomation is not available.

        Thread-safe: Wraps uiautomation calls with _com_initialize()
        to ensure COM is initialized on thread pool threads.
        """
        if not self.is_available():
            return UIScreenData()

        auto = _ensure_uiautomation()
        start_time = time.monotonic()

        # Initialize COM on this thread — required for uiautomation API calls
        # from thread pool threads (asyncio.run_in_executor). Safe to call from
        # the main thread too (CoInitialize is ref-counted).
        with _com_initialize():
            try:
                # Get the focused window (the top-level ancestor)
                focused_control = auto.GetFocusedControl()
                if focused_control is None:
                    logger.debug("No focused control found")
                    return UIScreenData(read_time_ms=(time.monotonic() - start_time) * 1000)

                # Walk up to find the window ancestor
                window = focused_control
                while window is not None:
                    if hasattr(window, 'ControlTypeName') and window.ControlTypeName == "WindowControl":
                        break
                    try:
                        window = window.GetParentControl()
                    except Exception:
                        window = None

                if window is None:
                    window = focused_control  # Fallback to the focused control itself

                # Build the screen data
                data = UIScreenData()
                data.window_title = self._safe_get_attr(window, "Name", "")
                data.window_class = self._safe_get_attr(window, "ClassName", "")
                data.window_pid = self._safe_get_attr(window, "ProcessId", 0)
                data.control_type = self._safe_get_attr(window, "ControlTypeName", "")

                # Traverse children
                self._traverse_element(window, data, depth=0, start_time=start_time)

                data.element_count = len(data.elements)
                data.interactive_count = sum(
                    1 for e in data.elements
                    if e.control_type in INTERACTIVE_CONTROL_TYPES
                )

                # Build visible text from all element names
                text_parts = []
                for elem in data.elements:
                    if elem.name and elem.control_type not in ("PaneControl",):
                        text_parts.append(elem.name)
                data.visible_text = " | ".join(text_parts[:100])  # Cap at 100 elements

                # Check for error dialogs and modals
                self._detect_errors_and_modals(data)

                data.read_time_ms = (time.monotonic() - start_time) * 1000
                self._last_read = data

                logger.debug(
                    "UIAccessibility read: %d elements (%d interactive) in %.0fms — %s",
                    data.element_count, data.interactive_count, data.read_time_ms,
                    data.window_title[:50],
                )

                return data

            except Exception as e:
                logger.debug("UIAccessibility read failed: %s", e)
                return UIScreenData(read_time_ms=(time.monotonic() - start_time) * 1000)

    def find_element(self, name: str, control_type: str | None = None) -> bool:
        """Find and click a UI element by name.

        Searches the focused window for an element matching the given name
        and optionally control type, then clicks it.

        Thread-safe: Wraps uiautomation calls with UIAutomationInitializerInThread
        for COM initialization on thread pool threads.

        Args:
            name: The Name property of the element to find.
            control_type: Optional ControlTypeName to narrow the search.

        Returns:
            True if the element was found and clicked, False otherwise.
        """
        if not self.is_available():
            return False

        auto = _ensure_uiautomation()

        with _com_initialize():
            try:
                focused_control = auto.GetFocusedControl()
                if focused_control is None:
                    return False

                # Walk up to the window
                window = focused_control
                while window is not None:
                    if hasattr(window, 'ControlTypeName') and window.ControlTypeName == "WindowControl":
                        break
                    try:
                        window = window.GetParentControl()
                    except Exception:
                        window = None

                if window is None:
                    return False

                # Try multiple control types to find the element
                search_types = [control_type] if control_type else [
                    "TextControl", "ButtonControl", "HyperlinkControl",
                    "EditControl", "MenuItemControl", "CustomControl",
                ]

                for ctrl_type in search_types:
                    try:
                        search_fn = getattr(auto, ctrl_type, None)
                        if search_fn is None:
                            continue
                        element = search_fn(Name=name, searchFromControl=window)
                        if element.Exists(maxSearchSeconds=2):
                            element.Click()
                            logger.info("Clicked UI element: %s (%s)", name, ctrl_type)
                            return True
                    except Exception:
                        continue

                # Fallback: search by AutomationId
                try:
                    element = window.TextControl(Name=name)
                    if element.Exists(maxSearchSeconds=2):
                        element.Click()
                        logger.info("Clicked UI element by text: %s", name)
                        return True
                except Exception:
                    pass

                logger.debug("UI element not found: %s", name)
                return False

            except Exception as e:
                logger.debug("find_element failed: %s", e)
                return False

    def get_last_read(self) -> UIScreenData | None:
        """Get the most recently read screen data without re-reading."""
        return self._last_read

    def _traverse_element(
        self,
        element,
        data: UIScreenData,
        depth: int,
        start_time: float,
    ):
        """Recursively traverse UI element tree.

        Stops at max_depth or timeout to prevent hanging on complex UIs.
        """
        if depth > self._max_depth:
            return
        if (time.monotonic() - start_time) > self._timeout_sec:
            return

        try:
            children = element.GetChildren()
        except Exception:
            return

        for child in children:
            try:
                name = self._safe_get_attr(child, "Name", "")
                ctrl_type = self._safe_get_attr(child, "ControlTypeName", "")
                automation_id = self._safe_get_attr(child, "AutomationId", "")
                is_enabled = self._safe_get_attr(child, "IsEnabled", True)
                is_visible = self._safe_get_attr(child, "IsVisible", True)

                # Get bounding rectangle
                bounds = (0, 0, 0, 0)
                try:
                    rect = child.BoundingRectangle
                    if rect and hasattr(rect, 'left'):
                        bounds = (rect.left, rect.top, rect.right, rect.bottom)
                except Exception:
                    pass

                # Count children of this element
                children_count = 0
                try:
                    children_count = len(child.GetChildren())
                except Exception:
                    pass

                ui_elem = UIElement(
                    name=name,
                    control_type=ctrl_type,
                    automation_id=automation_id,
                    is_enabled=is_enabled,
                    is_visible=is_visible,
                    bounds=bounds,
                    children_count=children_count,
                    depth=depth,
                )

                # Only include interactive elements and text elements
                if ((ctrl_type in INTERACTIVE_CONTROL_TYPES
                        or ctrl_type in ("TextControl", "PaneControl"))
                        and name):
                    data.elements.append(ui_elem)

                # Recurse into children
                self._traverse_element(child, data, depth + 1, start_time)

            except Exception:
                continue  # Skip broken elements

    def _detect_errors_and_modals(self, data: UIScreenData):
        """Analyze screen data for error dialogs, modals, and permission prompts."""
        for elem in data.elements:
            name_lower = elem.name.lower()

            # Detect error text
            if not data.error_text:
                for kw in _ERROR_KEYWORDS:
                    if kw in name_lower:
                        data.error_text = elem.name
                        data.is_modal = True
                        break

            # Detect modal dialogs
            ctrl_lower = elem.control_type.lower()
            if not data.is_modal:
                for kw in _MODAL_KEYWORDS:
                    if kw in name_lower or kw in ctrl_lower:
                        data.is_modal = True
                        break

            # Detect permission prompts
            if not data.error_text:
                for kw in _PERMISSION_KEYWORDS:
                    if kw in name_lower:
                        data.error_text = elem.name
                        break

    @staticmethod
    def _safe_get_attr(obj, attr: str, default: Any = None) -> Any:
        """Safely get an attribute from a UIAutomation control."""
        try:
            return getattr(obj, attr, default)
        except Exception:
            return default
