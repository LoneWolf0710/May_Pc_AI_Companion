"""Layer 16: Verification — Post-Action Screenshot Verification.

Per OpenClaw/Hermes architecture:
  After every critical tool execution, take a screenshot and verify
  the expected outcome. This catches cases where the action appeared
  to succeed but didn't (wrong window, popup blocked, element not clicked).

This is the KEY capability that gives May "insane accuracy":
  - take_action_verify: Screenshot + optional vision model analysis
  - verify_element_exists: Check if UI element appeared after action
  - verify_no_error: Scan for error dialogs/popups after action
  - compare_screenshots: Before/after screenshot comparison (pHash + pixel diff)

Libraries: PIL (screenshot), imagehash (perceptual hash), os/pathlib
"""

from __future__ import annotations

import asyncio
import ctypes
import ctypes.wintypes
import hashlib
import os
import time
from pathlib import Path
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.layers._utils import create_escalation_fn, create_preflight_fn

import logging
logger = logging.getLogger("may.core.layers.L16_verify")


# ══════════════════════════════════════════════════════════════════════════════
# Verification Helpers
# ══════════════════════════════════════════════════════════════════════════════

_VERIFY_DIR = Path(os.path.expanduser("~/.may/verify"))
_VERIFY_DIR.mkdir(parents=True, exist_ok=True)

# Error keywords to scan for in window titles
_ERROR_KEYWORDS = [
    "error", "failed", "cannot", "unable", "exception",
    "access denied", "permission denied", "not found",
    "crash", "fatal", "critical",
    "user account control", "windows defender",
]


def _take_screenshot(output_path: str | None = None) -> tuple[str, int, int]:
    """Take a full-screen screenshot. Returns (path, width, height)."""
    from PIL import ImageGrab
    path = output_path or str(_VERIFY_DIR / "verify_after.png")
    img = ImageGrab.grab()
    img.save(path)
    return path, img.width, img.height


def _take_screenshot_base64(output_path: str | None = None) -> tuple[str, str, int, int]:
    """Take a full-screen screenshot and return base64 for vision model.
    Returns (path, base64_data, width, height)."""
    import base64
    from PIL import ImageGrab
    path = output_path or str(_VERIFY_DIR / "verify_after.png")
    img = ImageGrab.grab()
    img.save(path)
    # Also encode as base64 for vision model
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return path, b64, img.width, img.height


def _file_hash(path: str) -> str:
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _scan_for_errors() -> list[dict]:
    """Scan all visible windows for error dialog indicators."""
    errors_found = []

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

        for keyword in _ERROR_KEYWORDS:
            if keyword in title_lower:
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
    return errors_found


# ══════════════════════════════════════════════════════════════════════════════
# Verification Actions
# ══════════════════════════════════════════════════════════════════════════════

async def _take_action_verify(params: dict) -> Any:
    """Post-action screenshot verification — the OpenClaw/Hermes pattern.

    Takes a screenshot after any tool execution, then returns it for
    the LLM to review. This catches cases where the action appeared
    to succeed but didn't (wrong window, popup blocked, element not clicked).

    The LLM should call this after critical actions like:
    - click_ui_element (verify the click had an effect)
    - type_into_ui_element (verify text was entered)
    - select_ui_dropdown (verify the option was selected)
    - toggle_ui_checkbox (verify the state changed)

    Returns the screenshot path and optional base64 for vision model.
    """
    expected_outcome = params.get("expected_outcome", "")
    action_description = params.get("action_description", "")
    include_base64 = params.get("include_base64", False)

    # Take screenshot
    try:
        if include_base64:
            path, b64, width, height = _take_screenshot_base64()
        else:
            path, width, height = _take_screenshot()
            b64 = None
    except Exception as e:
        raise RuntimeError(f"Failed to take verification screenshot: {e}")

    result = {
        "screenshot_path": path,
        "screenshot_size": {"width": width, "height": height},
    }

    if b64:
        result["screenshot_base64"] = b64  # For vision model analysis

    if expected_outcome:
        result["expected_outcome"] = expected_outcome
        result["instruction"] = (
            f"Screenshot saved to {path}. "
            f"Expected outcome: {expected_outcome}. "
            f"Compare the screenshot against the expected outcome to verify success."
        )
    else:
        result["instruction"] = (
            f"Screenshot saved to {path}. "
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

    Polls with timeout for slow UI updates.
    """
    window_title = params["window_title"]
    role = params.get("role", "")
    name = params.get("name", "")
    should_exist = params.get("should_exist", True)
    timeout_seconds = params.get("timeout_seconds", 3.0)

    # Use cached UIA connection + element finder from L16_uiautomation
    from core.layers.L16_uiautomation import _get_window_element, _find_element_by_role_and_name

    start_time = time.time()
    found = False
    element_info = None
    attempts = 0

    while (time.time() - start_time) < timeout_seconds:
        attempts += 1
        try:
            win = _get_window_element(window_title)
            element = _find_element_by_role_and_name(win, role, name)
            if element is not None:
                found = True
                try:
                    elem_name = element.element_info.name or ""
                except Exception:
                    elem_name = name
                element_info = {
                    "role": role,
                    "name": elem_name or name,
                    "found_after_ms": int((time.time() - start_time) * 1000),
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
        "attempts": attempts,
        "instruction": (
            f"Element {'FOUND' if found else 'NOT FOUND'} as expected — verification {'PASSED' if verified else 'FAILED'}."
        ),
    }


async def _verify_no_error(params: dict) -> Any:
    """Verify that no error dialogs or popups appeared after an action.

    Scans all visible windows for common error indicators:
    - Dialog windows with 'Error', 'Failed', 'Cannot' in the title
    - Modal popups
    - Windows Defender / UAC prompts
    """
    errors_found = _scan_for_errors()
    has_errors = len(errors_found) > 0

    return {
        "verified": not has_errors,
        "errors_found": errors_found,
        "error_count": len(errors_found),
        "instruction": (
            "No error dialogs detected." if not has_errors
            else f"WARNING: {len(errors_found)} error dialog(s) detected: "
                 f"{[e['title'] for e in errors_found]}"
        ),
    }


async def _compare_screenshots(params: dict) -> Any:
    """Compare two screenshots to detect changes (before/after an action).

    Uses perceptual hashing (pHash) for structural comparison and
    optional pixel-level diff for detailed analysis.

    Can compare:
    - Two file paths (before_path vs after_path)
    - A file path vs current screen (after_path = "screen")
    """
    before_path = params.get("before_path", "")
    after_path = params.get("after_path", "")
    threshold = params.get("threshold", 0.85)

    if not before_path or not after_path:
        raise RuntimeError("Both before_path and after_path are required")

    # Try imagehash first, fallback to basic file hash
    try:
        from PIL import Image
        import imagehash
        has_imagehash = True
    except ImportError:
        has_imagehash = False

    if not has_imagehash:
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
    hash_diff = int(hash_before - hash_after)  # Convert to int for JSON serialization
    max_hash = 64
    similarity = 1.0 - (hash_diff / max_hash)

    # Pixel-level diff (downsampled for speed)
    change_percent = None
    try:
        size = (320, 240)
        img_b = img_before.resize(size).convert("RGB")
        img_a = img_after.resize(size).convert("RGB")

        pixels_b = list(img_b.getdata())
        pixels_a = list(img_a.getdata())

        changed_pixels = 0
        total_pixels = len(pixels_b)
        for pb, pa in zip(pixels_b, pixels_a):
            diff = sum((b - a) ** 2 for b, a in zip(pb, pa)) ** 0.5
            if diff > 30:
                changed_pixels += 1

        change_percent = round((changed_pixels / total_pixels) * 100, 2) if total_pixels > 0 else 0
    except Exception:
        pass

    changed = similarity < threshold

    return {
        "changed": changed,
        "similarity": round(similarity, 4),
        "hash_diff": hash_diff,
        "threshold": threshold,
        "change_percent": change_percent,
        "before_path": before_path,
        "after_path": after_path,
        "method": "perceptual_hash",
        "instruction": (
            f"Screenshots are {'DIFFERENT' if changed else 'SIMILAR'} "
            f"(similarity: {similarity:.1%}, pixel change: {change_percent:.1f}%)."
            if change_percent is not None
            else f"Screenshots are {'DIFFERENT' if changed else 'SIMILAR'} (similarity: {similarity:.1%})."
        ),
    }


async def _compare_screenshots_basic(before_path: str, after_path: str) -> dict:
    """Basic screenshot comparison using file hashes (fallback)."""
    hash_before = _file_hash(before_path)
    hash_after = _file_hash(after_path)
    identical = hash_before == hash_after

    return {
        "changed": not identical,
        "identical": identical,
        "hash_before": hash_before,
        "hash_after": hash_after,
        "size_before": os.path.getsize(before_path),
        "size_after": os.path.getsize(after_path),
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
    "take_action_verify":    ([_take_action_verify], None),
    "verify_element_exists": ([_verify_element_exists], None),
    "verify_no_error":       ([_verify_no_error], None),
    "compare_screenshots":   ([_compare_screenshots], None),
}


async def handler(action: str, params: dict[str, Any]) -> Result:
    """L16 Verify layer handler."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown verification action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"verify.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("verify", action),
        escalation_fn=create_escalation_fn("verify", action),
        method_timeout=20.0,  # Verification can be slow (UIA polling, screenshot)
    )

    return Result(
        command_id=params.get("id", ""),
        success=success,
        data=data,
        error=error if not success else None,
        verified=False,
        method_used=method_used,
    )
