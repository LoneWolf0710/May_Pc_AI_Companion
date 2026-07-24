"""Frustration Detector — detects user stress from keyboard/mouse behavior.

Per JARVIS_V2_ARCHITECTURE.md Section 4.3:

No camera. Detects stress purely from keyboard and mouse behavior.
When score reaches 60+, May responds based on context:
- In code editor: "Want me to search that error or explain this section?"
- In browser: "Want me to take over and find what you need?"
- In document: "Want me to rewrite that paragraph?"
- General: "Looks like a rough moment — want me to handle what's blocking you?"

Cooldown prevents spam suggestions after triggering once.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("may.intelligence.frustration_detector")


# ── Signal Definitions ───────────────────────────────────────────────────────

SIGNALS = {
    "rapid_backspace":    {"threshold": 8,  "window": 1,   "weight": 15},  # 8+ backspace/sec
    "ctrl_z_spam":        {"threshold": 5,  "window": 10,  "weight": 15},  # 5+ undo in 10sec
    "mouse_thrashing":    {"threshold": 0.7, "window": 5,  "weight": 10},  # velocity variance > 0.7
    "rapid_app_switch":   {"threshold": 6,  "window": 30,  "weight": 15},  # 6+ alt-tab in 30sec
    "rage_click":         {"threshold": 4,  "window": 3,   "weight": 20},  # 4+ clicks same region in 3sec
    "long_pause":         {"threshold": 90, "window": 90,  "weight": 10},  # 90sec no input
    "repeat_same_action": {"threshold": 3,  "window": 60,  "weight": 15},  # same action 3+ times in 60sec
}


# ── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class InputEvent:
    """A single keyboard/mouse input event."""
    event_type: str      # "key_press", "mouse_click", "mouse_move", "mouse_scroll"
    key: str = ""        # Key name (for keyboard events)
    x: int = 0           # X coordinate (for mouse events)
    y: int = 0           # Y coordinate (for mouse events)
    timestamp: float = 0.0


# ── Frustration Detector ────────────────────────────────────────────────────

class FrustrationDetector:
    """Detects user stress purely from keyboard and mouse behavior. No camera.

    Usage:
        detector = FrustrationDetector()
        detector.record_input(InputEvent("key_press", key="backspace", timestamp=time.time()))
        score = detector.calculate_score()
        if score >= 60:
            response = detector.get_response("code_editor")
    """

    def __init__(self, cooldown_sec: float = 300):
        self._events: deque[InputEvent] = deque(maxlen=10000)
        self._last_trigger_time: float = 0
        self._cooldown_sec = cooldown_sec
        self._active = True

    def record_input(self, event: InputEvent):
        """Record a keyboard or mouse input event."""
        if not self._active:
            return

        if event.timestamp == 0:
            event.timestamp = time.time()

        self._events.append(event)

    def record_key_press(self, key: str, timestamp: float | None = None):
        """Convenience method to record a key press."""
        self.record_input(InputEvent(
            event_type="key_press",
            key=key,
            timestamp=timestamp or time.time(),
        ))

    def record_mouse_click(self, x: int, y: int, timestamp: float | None = None):
        """Convenience method to record a mouse click."""
        self.record_input(InputEvent(
            event_type="mouse_click",
            x=x, y=y,
            timestamp=timestamp or time.time(),
        ))

    def record_mouse_move(self, x: int, y: int, timestamp: float | None = None):
        """Convenience method to record mouse movement."""
        self.record_input(InputEvent(
            event_type="mouse_move",
            x=x, y=y,
            timestamp=timestamp or time.time(),
        ))

    def calculate_score(self) -> int:
        """Returns 0-100 frustration score based on input signals."""
        now = time.time()
        score = 0

        # ── Rapid backspace ──────────────────────────────────────────────
        recent_backspace = sum(
            1 for e in self._events
            if e.event_type == "key_press" and e.key == "backspace"
            and (now - e.timestamp) <= SIGNALS["rapid_backspace"]["window"]
        )
        if recent_backspace >= SIGNALS["rapid_backspace"]["threshold"]:
            score += SIGNALS["rapid_backspace"]["weight"]

        # ── Ctrl+Z spam ─────────────────────────────────────────────────
        recent_ctrl_z = sum(
            1 for e in self._events
            if e.event_type == "key_press" and e.key.lower() in ("ctrl+z", "undo")
            and (now - e.timestamp) <= SIGNALS["ctrl_z_spam"]["window"]
        )
        if recent_ctrl_z >= SIGNALS["ctrl_z_spam"]["threshold"]:
            score += SIGNALS["ctrl_z_spam"]["weight"]

        # ── Mouse thrashing ──────────────────────────────────────────────
        mouse_moves = [
            e for e in self._events
            if e.event_type == "mouse_move"
            and (now - e.timestamp) <= SIGNALS["mouse_thrashing"]["window"]
        ]
        if len(mouse_moves) > 5:
            # Calculate velocity variance
            velocities = []
            for i in range(1, len(mouse_moves)):
                dx = mouse_moves[i].x - mouse_moves[i-1].x
                dy = mouse_moves[i].y - mouse_moves[i-1].y
                dt = mouse_moves[i].timestamp - mouse_moves[i-1].timestamp
                if dt > 0:
                    velocity = (dx**2 + dy**2)**0.5 / dt
                    velocities.append(velocity)
            if velocities:
                mean_v = sum(velocities) / len(velocities)
                variance = sum((v - mean_v)**2 for v in velocities) / len(velocities)
                # Normalize variance (threshold 0.7 is in arbitrary units)
                if variance > 1000000:  # High velocity variance
                    score += SIGNALS["mouse_thrashing"]["weight"]

        # ── Rapid app switching (alt-tab) ────────────────────────────────
        recent_alt_tab = sum(
            1 for e in self._events
            if e.event_type == "key_press" and e.key.lower() in ("alt+tab", "alt+tab+shift")
            and (now - e.timestamp) <= SIGNALS["rapid_app_switch"]["window"]
        )
        if recent_alt_tab >= SIGNALS["rapid_app_switch"]["threshold"]:
            score += SIGNALS["rapid_app_switch"]["weight"]

        # ── Rage clicking (same region) ──────────────────────────────────
        recent_clicks = [
            e for e in self._events
            if e.event_type == "mouse_click"
            and (now - e.timestamp) <= SIGNALS["rage_click"]["window"]
        ]
        if len(recent_clicks) >= SIGNALS["rage_click"]["threshold"]:
            # Check if clicks are in similar region (within 50px radius)
            for click in recent_clicks:
                same_region_count = sum(
                    1 for c in recent_clicks
                    if abs(c.x - click.x) < 50 and abs(c.y - click.y) < 50
                )
                if same_region_count >= SIGNALS["rage_click"]["threshold"]:
                    score += SIGNALS["rage_click"]["weight"]
                    break

        # ── Long pause ───────────────────────────────────────────────────
        if self._events:
            last_event_time = self._events[-1].timestamp
            pause_duration = now - last_event_time
            if pause_duration >= SIGNALS["long_pause"]["threshold"]:
                score += SIGNALS["long_pause"]["weight"]

        # ── Repeat same action ───────────────────────────────────────────
        recent_actions = [
            f"{e.event_type}:{e.key}" if e.event_type == "key_press" else e.event_type
            for e in self._events
            if (now - e.timestamp) <= SIGNALS["repeat_same_action"]["window"]
        ]
        if recent_actions:
            action_counts = Counter(recent_actions)
            most_common_count = action_counts.most_common(1)[0][1]
            if most_common_count >= SIGNALS["repeat_same_action"]["threshold"]:
                score += SIGNALS["repeat_same_action"]["weight"]

        return min(100, score)

    def should_trigger(self) -> bool:
        """Check if frustration detection should trigger a response.

        Returns True if score >= 60 and cooldown has elapsed.
        """
        score = self.calculate_score()
        now = time.time()

        if score < 60:
            return False

        # Check cooldown
        if (now - self._last_trigger_time) < self._cooldown_sec:
            return False

        self._last_trigger_time = now
        return True

    def get_response(self, context: str = "general") -> str:
        """Context-aware response based on what app the user is in.

        Args:
            context: One of "code_editor", "browser", "document", "general"
        """
        responses = {
            "code_editor": "Want me to search that error or explain this section?",
            "browser": "Want me to take over and find what you need?",
            "document": "Want me to rewrite that paragraph?",
            "general": "Looks like a rough moment — want me to handle what's blocking you?",
        }
        return responses.get(context, responses["general"])

    def get_stats(self) -> dict:
        """Get frustration detector statistics."""
        return {
            "events_tracked": len(self._events),
            "current_score": self.calculate_score(),
            "last_trigger": self._last_trigger_time,
            "cooldown_remaining": max(0, self._cooldown_sec - (time.time() - self._last_trigger_time)),
            "active": self._active,
        }

    def pause(self):
        """Pause the frustration detector (for privacy mode)."""
        self._active = False
        logger.info("Frustration detector paused")

    def resume(self):
        """Resume the frustration detector."""
        self._active = True
        logger.info("Frustration detector resumed")
