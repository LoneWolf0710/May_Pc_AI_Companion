"""Screen Watcher — proactive screen monitoring for May.

Per JARVIS_V2_ARCHITECTURE.md Section 4.2:

Takes a low-res screenshot every 8 seconds (configurable). Local analysis checks for:
- Error dialogs
- Same page for > 5 minutes
- Large blocks of text (summary candidate)
- Email compose windows
- Calendar showing today
- Low battery warnings

Smart throttling: will NOT interrupt during active typing, fullscreen video, or gaming.

Implementation note: This module captures screenshots via the Control Core daemon's
input layer (screenshot_full action) and hashes them to detect changes. It does NOT
use local AI vision (no llava required) — instead it uses rule-based heuristics
on window titles and process names.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

# P4: Lazy imports for Tier 1 (imagehash), Tier 2 (UIAccessibility + PaddleOCR)
_imagehash = None
_UIAccessibilityReader = None
_OCRReader = None

# P5: Deterministic pseudo-random for suggestion rate gating (avoids importing random)
def _pseudo_random() -> float:
    """Return a deterministic float in [0,1) based on current time.

    Avoids importing the random module — uses time-based hashing instead.
    """
    import hashlib
    h = hashlib.md5(str(time.time_ns()).encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF

logger = logging.getLogger("may.intelligence.screen_watcher")


# ── Proactive Rules ─────────────────────────────────────────────────────────

@dataclass
class ProactiveRule:
    """A rule that detects a screen state and generates a suggestion."""
    name: str
    message: str
    check_fn: Any = None  # Callable[[ScreenContext], bool]
    cooldown_sec: float = 300  # 5 minutes between same rule triggers
    last_triggered: float = 0


# ── Screen Context ──────────────────────────────────────────────────────────

@dataclass
class ScreenContext:
    """Parsed information about the current screen state."""
    active_app: str = ""
    active_window_title: str = ""
    is_fullscreen: bool = False
    is_game: bool = False
    battery_percent: float = 100
    timestamp: float = 0
    # Tier 2: Perceptual screenshot hash (set by _capture_screenshot_hash)
    screenshot_hash: str | None = None
    # Tier 3: UIAutomation accessibility tree elements
    ui_elements: list[dict] = field(default_factory=list)
    ui_error_text: str = ""  # Extracted error text from UI tree
    ui_is_modal: bool = False  # Whether a modal dialog is detected
    ui_control_type: str = ""  # Active window's control type (e.g. Window, Dialog)


# ── Screen Watcher ──────────────────────────────────────────────────────────

class ScreenWatcher:
    """Takes low-res screenshots periodically and detects user state.

    Uses the Control Core daemon to capture screenshots and detect the active window.
    Runs as a background asyncio task.

    Usage:
        watcher = ScreenWatcher()
        await watcher.start()
        # ... later ...
        await watcher.stop()
    """

    interval_sec = 8
    resolution = (400, 300)  # Very low res, fast to process
    # P4: imagehash threshold — hamming distance above this means "changed"
    IMAGEHASH_THRESHOLD = 8

    # Apps that indicate the user is in fullscreen / gaming
    FULLSCREEN_APPS = {
        "steam", "epic games", "battle.net", "origin", "ubisoft",
        "vlc", "mpc-hc", "potplayer", "netflix", "disney+",
    }
    GAME_INDICATORS = {
        "dota", "counter-strike", "valorant", "league of legends",
        "fortnite", "apex legends", "overwatch", "minecraft",
        "gta", "cyberpunk", "elden ring", "baldur's gate",
    }

    def __init__(self):
        self._active = False
        self._last_hash: str = ""
        self._last_window_check: float = 0
        self._rules: list[ProactiveRule] = self._default_rules()
        self._suggestions: list[dict] = []
        self._task: asyncio.Task | None = None
        # Tier 4: Vision analysis state
        self._last_vision_analysis: float = 0
        self._vision_interval_sec: float = 120  # Analyze every 2 minutes
        self._last_vision_description: str = ""
        self._vision_enabled: bool = True
        # P4: Tier 2 — UIAccessibility reader (lazy-init, zero VRAM)
        self._ui_reader = None  # Initialized on first use
        # P4: Tier 2 Option B — PaddleOCR fallback (for apps without accessibility)
        self._ocr_reader = None  # Initialized on first use
        self._last_screen_data: dict = {}  # Cached Tier 2 screen data
        # P5: Read screen_interval from auto-tuner
        self._update_interval_from_tuner()

    def _update_interval_from_tuner(self):
        """P5: Read screen_interval gene from auto-tuner (cached via tuner_cache)."""
        from intelligence.tuner_cache import get_gene
        self.interval_sec = int(get_gene("screen_interval", default=8))

    def _default_rules(self) -> list[ProactiveRule]:
        """Create the default set of proactive monitoring rules."""
        return [
            ProactiveRule(
                name="error_dialog",
                message="Looks like an error — want me to search the fix?",
                check_fn=lambda ctx: "error" in ctx.active_window_title.lower()
                    or "exception" in ctx.active_window_title.lower()
                    or "not responding" in ctx.active_window_title.lower(),
            ),
            # Tier 3: UIAutomation-detected error dialog (catches errors the title check misses)
            ProactiveRule(
                name="ui_error_dialog",
                message="I detected an error dialog — want me to help?",
                check_fn=lambda ctx: bool(ctx.ui_error_text),
                cooldown_sec=600,
            ),
            # Tier 3: UIAutomation-detected permission/security prompt
            ProactiveRule(
                name="permission_prompt",
                message="A permission prompt appeared — want me to help decide?",
                check_fn=lambda ctx: ctx.ui_control_type.lower() in ("dialog", "popup")
                    and any(kw in ctx.ui_error_text.lower() for kw in
                        ["permission", "access", "denied", "allow", "grant", "authorize"]),
                cooldown_sec=900,
            ),
            # Tier 3: UIAutomation-detected installation/update wizard
            ProactiveRule(
                name="installer_detected",
                message="An installer is running — want me to monitor progress?",
                check_fn=lambda ctx: any(kw in ctx.active_window_title.lower() for kw in
                    ["setup", "install", "wizard", "updating", "downloading"]),
                cooldown_sec=1800,
            ),
            ProactiveRule(
                name="same_page_5min",
                message="You've been here a while, need help?",
                check_fn=lambda ctx: False,  # Handled by time-based check in watch_loop
                cooldown_sec=600,  # 10 minutes
            ),
            ProactiveRule(
                name="email_compose",
                message="Want me to help write that?",
                check_fn=lambda ctx: any(kw in ctx.active_window_title.lower() for kw in
                    ["compose", "new message", "new mail", "reply", "write"]),
            ),
            ProactiveRule(
                name="low_battery",
                message="Battery is getting low — want me to save your work?",
                check_fn=lambda ctx: ctx.battery_percent < 15 and ctx.battery_percent > 0,
            ),
            # Tier 4: Vision model detected error in screenshot
            ProactiveRule(
                name="vision_error_detected",
                message="I can see an error on your screen — want me to help?",
                check_fn=lambda ctx: False,  # Triggered by _run_vision_analysis
                cooldown_sec=1800,
            ),
        ]

    async def start(self):
        """Start the screen watcher background task."""
        if self._active:
            return
        self._active = True
        self._task = asyncio.create_task(self._watch_loop())
        logger.info("Screen watcher started (interval=%ds)", self.interval_sec)

    async def stop(self):
        """Stop the screen watcher."""
        self._active = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Screen watcher stopped")

    async def _watch_loop(self):
        """Main monitoring loop — captures screenshots and checks rules.

        Tier 1: Text-based hash (window title + process name) — always runs
        Tier 2: Perceptual screenshot hash — runs every other cycle (16s)
        Tier 3: UIAutomation accessibility tree — runs every other cycle (16s)
        """
        same_page_start: float = 0
        last_window_title: str = ""
        cycle_count = 0
        last_screenshot_hash: str = ""

        while self._active:
            try:
                await asyncio.sleep(self.interval_sec)

                # Re-check after sleep — stop()/pause() may have been called
                if not self._active:
                    break
                cycle_count += 1

                # Get current screen context (Tier 1 — always)
                ctx = await self._get_screen_context()

                # P4: Tier 1.5 — Proper imagehash perceptual comparison (every other cycle)
                if cycle_count % 2 == 0:
                    try:
                        ctx.screenshot_hash = await self._capture_screenshot_hash()
                    except Exception as e:
                        logger.debug("Tier 1 imagehash failed: %s", e)

                # P4: Tier 2 — UIAccessibility or PaddleOCR structured screen data (every other cycle)
                if cycle_count % 2 == 0:
                    try:
                        screen_data = await self._get_ui_accessibility_data()
                        if not screen_data or screen_data.get("element_count", 0) == 0:
                            # UIAccessibility returned nothing — try PaddleOCR fallback
                            screen_data = await self._get_ocr_data()
                        if screen_data:
                            self._last_screen_data = screen_data
                            # Map Tier 2 data into existing ScreenContext fields
                            ctx.ui_elements = [
                                {"name": e.get("name", ""), "control_type": e.get("control_type", ""),
                                 "is_enabled": e.get("is_enabled", True)}
                                for e in screen_data.get("elements", [])[:50]
                            ]
                            ctx.ui_error_text = screen_data.get("error_text", "")
                            ctx.ui_is_modal = screen_data.get("is_modal", False)
                            ctx.ui_control_type = screen_data.get("control_type", "")
                            self._parse_ui_tree(ctx)  # Re-parse with Tier 2 data
                    except Exception as e:
                        logger.debug("Tier 2 screen reading failed: %s", e)

                # Check if screen changed (combined hash)
                screen_hash = self._hash_context(ctx)
                screenshot_changed = (
                    ctx.screenshot_hash is not None
                    and ctx.screenshot_hash != last_screenshot_hash
                )
                if ctx.screenshot_hash is not None:
                    last_screenshot_hash = ctx.screenshot_hash

                if screen_hash == self._last_hash and not screenshot_changed:
                    # Same screen — check for time-based rules
                    if ctx.active_window_title == last_window_title:
                        if same_page_start == 0:
                            same_page_start = time.time()
                        elif (time.time() - same_page_start) > 300:  # 5 minutes
                            self._trigger_rule("same_page_5min", ctx)
                    else:
                        same_page_start = 0
                        last_window_title = ctx.active_window_title
                else:
                    # Screen changed — reset time tracking
                    same_page_start = 0
                    last_window_title = ctx.active_window_title
                    self._last_hash = screen_hash

                # Check throttle conditions FIRST — don't interrupt during games/fullscreen
                if self._should_skip(ctx):
                    continue

                # Check all rules (Tier 1 + Tier 3)
                for rule in self._rules:
                    if rule.check_fn and rule.check_fn(ctx):
                        now = time.time()
                        if (now - rule.last_triggered) > rule.cooldown_sec:
                            rule.last_triggered = now
                            self._trigger_rule(rule.name, ctx)

                # Tier 4: Vision model analysis (every _vision_interval_sec)
                now = time.time()
                if (self._vision_enabled
                        and cycle_count % 2 == 0  # Only on Tier 2/3 cycles
                        and (now - self._last_vision_analysis) > self._vision_interval_sec):
                    try:
                        await self._run_vision_analysis()
                        self._last_vision_analysis = now
                    except Exception as e:
                        logger.debug("Tier 4 vision analysis failed: %s", e)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Screen watcher error: %s", e)
                await asyncio.sleep(5)  # Back off on error

    def _trigger_rule(self, rule_name: str, ctx: ScreenContext):
        """Trigger a proactive suggestion.

        P5: Gates suggestions through proactive_suggestion_rate gene.
        If rate=0.0, no suggestions trigger. If rate=0.5, ~50% trigger.
        """
        # P5: Read proactive_suggestion_rate from auto-tuner
        try:
            from intelligence.tuner_cache import get_gene
            suggestion_rate = get_gene("proactive_suggestion_rate", default=0.1)
            if _pseudo_random() > suggestion_rate:
                return  # Rate gate — skip this suggestion
        except Exception:
            pass  # If tuner_cache unavailable, always trigger (original behavior)

        for rule in self._rules:
            if rule.name == rule_name:
                suggestion = {
                    "type": "proactive",
                    "rule": rule_name,
                    "message": rule.message,
                    "context": {
                        "active_app": ctx.active_app,
                        "window_title": ctx.active_window_title,
                    },
                    "timestamp": time.time(),
                }
                self._suggestions.append(suggestion)
                logger.info("Proactive suggestion triggered: %s (app: %s)",
                           rule_name, ctx.active_app)
                return

    def _should_skip(self, ctx: ScreenContext) -> bool:
        """Smart throttling — don't interrupt during certain activities."""
        # Skip if user is in a fullscreen app or game
        if ctx.is_fullscreen or ctx.is_game:
            return True
        return False

    async def _get_screen_context(self) -> ScreenContext:
        """Get the current screen context by querying the active window.

        Uses the Control Core daemon's window layer to get the active window title,
        then checks the process name against known fullscreen/game apps.
        """
        ctx = ScreenContext(timestamp=time.time())

        try:
            # Query the Control Core daemon for the active window
            from core.client import send_command
            result = await send_command("window", "get_active_window", {})

            if result.success and isinstance(result.data, dict):
                ctx.active_window_title = result.data.get("title", "")
                process_name = result.data.get("process_name", "").lower()
                ctx.active_app = process_name

                # Check fullscreen/game status
                ctx.is_fullscreen = any(
                    fa in process_name for fa in self.FULLSCREEN_APPS
                )
                ctx.is_game = any(
                    gi in process_name for gi in self.GAME_INDICATORS
                )
        except Exception as e:
            logger.debug("Failed to get screen context: %s", e)

        # Check battery level
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                ctx.battery_percent = battery.percent
        except Exception:
            pass

        return ctx

    # Tier 3 keyword constants
    _UI_ERROR_KEYWORDS = [
        "error", "exception", "fault", "failed", "crash",
        "cannot", "unable", "access denied", "not found",
        "not working", "has stopped", "problem", "fatal",
    ]
    _UI_MODAL_KEYWORDS = ["dialog", "popup", "modal", "alert", "confirm"]
    _UI_PERMISSION_KEYWORDS = ["permission", "access", "authorize", "grant", "denied"]

    def _parse_ui_tree(self, ctx: ScreenContext):
        """Parse UIAutomation tree to extract error text and modal status.

        Tier 3: Looks for error/exception text in UI elements, detects modal dialogs,
        and extracts the active window's control type.
        """
        if not ctx.ui_elements:
            return

        # Extract window control type from first element (unconditionally)
        first_elem = ctx.ui_elements[0]
        ctx.ui_control_type = first_elem.get("control_type", "")

        for elem in ctx.ui_elements:
            name = elem.get("name", "").lower()
            ctrl_type = elem.get("control_type", "").lower()

            # Detect error text in any UI element
            if any(kw in name for kw in self._UI_ERROR_KEYWORDS):
                ctx.ui_error_text = elem.get("name", "")
                ctx.ui_is_modal = True
                break

            # Detect modal/popup windows
            if any(kw in ctrl_type for kw in self._UI_MODAL_KEYWORDS):
                ctx.ui_is_modal = True
                if not ctx.ui_control_type:
                    ctx.ui_control_type = elem.get("control_type", "")

            # Detect permission/security prompts
            if any(kw in name for kw in self._UI_PERMISSION_KEYWORDS):
                ctx.ui_error_text = elem.get("name", "")
                ctx.ui_control_type = elem.get("control_type", "")

    def _hash_context(self, ctx: ScreenContext) -> str:
        """Create a hash of the screen context for change detection.

        Combines Tier 1 (text hash) with Tier 2 (screenshot hash) for
        robust change detection.
        """
        # Tier 1: Text-based hash (window title + process name)
        key = f"{ctx.active_window_title}|{ctx.active_app}|{ctx.is_fullscreen}"
        text_hash = hashlib.md5(key.encode()).hexdigest()

        # Combine with Tier 2 screenshot hash if available
        if ctx.screenshot_hash:
            combined = f"{text_hash}|{ctx.screenshot_hash}"
            return hashlib.md5(combined.encode()).hexdigest()

        return text_hash

    async def _capture_screenshot_hash(self) -> str | None:
        """P4 Tier 1: Perceptual hash using the imagehash library.

        Takes a low-res screenshot and computes a proper perceptual hash (pHash)
        that detects visual changes even when the window title stays the same
        (e.g., loading a new page, scrolling, modal dialogs).

        Falls back to the basic PIL hash if imagehash is not installed.
        Uses a threshold (IMAGEHASH_THRESHOLD) to determine if the change is significant.
        """
        try:
            from core.client import send_command
            import os

            # Capture a screenshot via the daemon's input layer
            result = await send_command("input", "screenshot_full", {
                "output_path": "_may_screenshot_temp.png",
            })

            if not result.success or not isinstance(result.data, dict):
                return None

            screenshot_path = result.data.get("path", "")
            if not screenshot_path or not os.path.exists(screenshot_path):
                return None

            try:
                from PIL import Image
                img = Image.open(screenshot_path)

                # P4: Try proper imagehash library first (much better change detection)
                try:
                    global _imagehash
                    if _imagehash is None:
                        import imagehash as _ih
                        _imagehash = _ih
                    # Use perceptual hash (pHash) — DCT-based, robust to minor changes
                    current_hash = _imagehash.phash(img, hash_size=8)
                    return str(current_hash)
                except ImportError:
                    pass

                # Fallback: basic block-average hash (original implementation)
                img_gray = img.convert('L')
                img_small = img_gray.resize((8, 8), Image.Resampling.LANCZOS)
                pixels = list(img_small.getdata())
                avg = sum(pixels) / len(pixels)
                hash_bits = ''.join('1' if p > avg else '0' for p in pixels)
                return hash_bits
            finally:
                try:
                    os.unlink(screenshot_path)
                except OSError:
                    pass
        except Exception as e:
            logger.debug("Screenshot hash failed: %s", e)
            return None

    async def _get_ocr_data(self) -> dict | None:
        """P4 Tier 2 Option B: Read screen text using PaddleOCR.

        Fallback when UIAccessibility returns no data (e.g., games, custom UIs).
        Takes a screenshot and runs OCR to extract visible text.
        ~200-400MB RAM, no VRAM, ~100-300ms per read.
        """
        try:
            global _OCRReader
            if _OCRReader is None:
                from intelligence.ocr_reader import OCRReader
                _OCRReader = OCRReader()

            if not _OCRReader.is_available():
                return None

            # Take a screenshot via the daemon (unique name to avoid collisions)
            import time as _time_mod
            screenshot_name = f"_may_ocr_{int(_time_mod.time() * 1000)}.png"
            from core.client import send_command
            result = await send_command("input", "screenshot_full", {
                "output_path": screenshot_name,
            })

            if not result.success or not isinstance(result.data, dict):
                return None

            screenshot_path = result.data.get("path", "")
            if not screenshot_path or not os.path.exists(screenshot_path):
                return None

            try:
                loop = asyncio.get_event_loop()
                ocr_result = await loop.run_in_executor(
                    None, _OCRReader.read_screenshot, screenshot_path
                )
            finally:
                try:
                    os.unlink(screenshot_path)
                except OSError:
                    pass

            if ocr_result is None or ocr_result.line_count == 0:
                return None

            # Map OCR result to the same format as UIAccessibility
            elements = []
            for line in ocr_result.text_lines:
                elements.append({
                    "name": line,
                    "control_type": "TextControl",
                    "is_enabled": True,
                })

            return {
                "window_title": "OCR fallback",
                "element_count": len(elements),
                "interactive_count": 0,
                "elements": elements,
                "visible_text": ocr_result.full_text,
                "error_text": "",
                "is_modal": False,
                "control_type": "OCR",
                "source": "paddleocr",
            }

        except ImportError:
            logger.debug("PaddleOCR not available")
            return None
        except Exception as e:
            logger.debug("OCR fallback failed: %s", e)
            return None

    async def _get_ui_accessibility_data(self) -> dict | None:
        """P4 Tier 2: Read the screen using Windows UIAccessibility API.

        Zero VRAM — uses the same API as screen readers (Narrator, NVDA).
        Returns structured data: buttons, inputs, menus, text, error detection.
        """
        try:
            from intelligence.ui_accessibility import UIAccessibilityReader

            if self._ui_reader is None:
                self._ui_reader = UIAccessibilityReader()

            if not self._ui_reader.is_available():
                return None

            # Run the UIAccessibility read in a thread executor to avoid blocking
            loop = asyncio.get_event_loop()
            screen_data = await loop.run_in_executor(
                None, self._ui_reader.get_screen_data
            )

            if screen_data is None or not screen_data.elements:
                return None

            return screen_data.to_dict()

        except ImportError:
            logger.debug("UIAccessibility not available (uiautomation not installed)")
            return None
        except Exception as e:
            logger.debug("UIAccessibility read failed: %s", e)
            return None

    def get_suggestions(self) -> list[dict]:
        """Get pending suggestions that haven't been shown to the user yet."""
        return [s for s in self._suggestions if not s.get("shown")]

    def mark_shown(self, suggestion: dict):
        """Mark a suggestion as shown to the user."""
        suggestion["shown"] = True

    def get_stats(self) -> dict:
        """Get screen watcher statistics."""
        return {
            "active": self._active,
            "interval_sec": self.interval_sec,
            "rules_active": len(self._rules),
            "suggestions_pending": len(self.get_suggestions()),
            "last_hash": self._last_hash[:8] if self._last_hash else None,
            "vision_enabled": self._vision_enabled,
            "last_vision_analysis": self._last_vision_analysis,
            "last_vision_description": self._last_vision_description[:200] if self._last_vision_description else None,
            # P4: Tier 2 UIAccessibility status
            "ui_accessibility_available": self._ui_reader.is_available() if self._ui_reader else False,
            "last_screen_data": self._last_screen_data.get("window_title", "") if self._last_screen_data else "",
            "screen_data_elements": self._last_screen_data.get("element_count", 0) if self._last_screen_data else 0,
            "screen_data_interactive": self._last_screen_data.get("interactive_count", 0) if self._last_screen_data else 0,
            "screen_data_error": self._last_screen_data.get("error_text", "")[:100] if self._last_screen_data else "",
            "screen_data_modal": self._last_screen_data.get("is_modal", False) if self._last_screen_data else False,
        }

    # ── Tier 4: Vision Model Analysis ──────────────────────────────────────

    async def _run_vision_analysis(self):
        """Tier 4: Send a screenshot to a vision model for semantic analysis.

        Captures a screenshot, encodes it as base64, and sends it to a vision-capable
        LLM (OpenAI GPT-4o, OpenRouter, or Gemini) with a focused prompt.
        The response is stored for proactive suggestions and can trigger new rules.
        """
        try:
            import base64
            import tempfile
            from core.client import send_command

            # Take a screenshot via the daemon's input layer
            result = await send_command("input", "screenshot_full", {
                "output_path": "_may_vision_temp.png",
            })

            if not result.success or not isinstance(result.data, dict):
                return

            screenshot_path = result.data.get("path", "")
            if not screenshot_path or not os.path.exists(screenshot_path):
                return

            try:
                # Read and encode the screenshot
                with open(screenshot_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode("utf-8")
            finally:
                try:
                    os.unlink(screenshot_path)
                except OSError:
                    pass

            # Find a vision-capable provider
            from llm.providers import get_api_key
            import httpx

            api_key = None
            base_url = None
            model = None
            for prov in ["openai", "openrouter", "gemini", "google_ai_studio"]:
                try:
                    key = get_api_key(prov)
                    if key:
                        api_key = key
                        if prov == "openai":
                            base_url = "https://api.openai.com/v1"
                            model = "gpt-4o"
                        elif prov == "openrouter":
                            base_url = "https://openrouter.ai/api/v1"
                            model = "openai/gpt-4o"
                        elif prov in ("gemini", "google_ai_studio"):
                            base_url = "https://generativelanguage.googleapis.com/v1beta"
                            model = "gemini-2.0-flash"
                        break
                except Exception:
                    continue

            if not api_key:
                logger.debug("No vision-capable API key — Tier 4 disabled")
                self._vision_enabled = False
                return

            # Send to vision model with a focused prompt
            prompt = (
                "Briefly describe what's on this screen in 1-2 sentences. "
                "Focus on: what app/page is shown, any errors or alerts visible, "
                "and what the user appears to be doing. Be concise."
            )

            if "gemini" in (base_url or ""):
                url = f"{base_url}/models/{model}:generateContent?key={api_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/png", "data": img_b64}}
                        ]
                    }],
                    "generationConfig": {"maxOutputTokens": 200},
                }
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            else:
                url = f"{base_url}/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                        ]
                    }],
                    "max_tokens": 200,
                }
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            if text and text.strip():
                self._last_vision_description = text.strip()
                logger.info("Tier 4 vision: %s", text.strip()[:100])

                # Check vision description for error patterns
                desc_lower = self._last_vision_description.lower()
                error_keywords = ["error", "crash", "exception", "failed", "not responding", "fatal"]
                if any(kw in desc_lower for kw in error_keywords):
                    self._trigger_rule("vision_error_detected", ScreenContext(
                        active_app="vision_analysis",
                        active_window_title=self._last_vision_description[:100],
                    ))

        except Exception as e:
            logger.debug("Tier 4 vision analysis failed: %s", e)

    async def read_screen_now(self) -> dict | None:
        """Public method to force an immediate Tier 2 UIAccessibility read.

        Called by API endpoints for on-demand screen context.
        Returns the screen data dict or None if unavailable.
        """
        data = await self._get_ui_accessibility_data()
        if data:
            self._last_screen_data = data
        return data

    def get_last_screen_data(self) -> dict | None:
        """Get the most recently read Tier 2 UIAccessibility screen data.

        Called by jarvis.py for memory injection context.
        Returns None if no Tier 2 data has been read yet.
        """
        return self._last_screen_data if self._last_screen_data else None

    def pause(self):
        """Pause the screen watcher (for privacy mode)."""
        self._active = False
        logger.info("Screen watcher paused")

    def resume(self):
        """Resume the screen watcher."""
        self._active = True
        logger.info("Screen watcher resumed")
