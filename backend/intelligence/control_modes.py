"""Control Modes — Focus, Automation, and Silent modes for May.

Three modes that change how May interacts with the user:

1. **Normal Mode** (default) — Full interaction, proactive suggestions, TTS enabled
2. **Focus Mode** — Suppresses proactive suggestions, reduces TTS, minimal interruptions
3. **Silent Mode** — No TTS, no proactive suggestions, text-only responses
4. **Automation Mode** — Allows ghost mode auto-execution, shadow learner suggestions

Modes are stored in ~/.may/control_modes.json and persist across restarts.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("may.intelligence.control_modes")

_MODES_FILE = Path.home() / ".may" / "control_modes.json"


@dataclass
class ModeState:
    """Current control mode state."""
    active_mode: str = "normal"  # "normal", "focus", "silent", "automation"
    enabled: bool = True
    activated_at: float = field(default_factory=time.time)
    reason: str = ""
    # Per-mode settings
    tts_enabled: bool = True
    proactive_enabled: bool = True
    auto_execute_enabled: bool = False
    notifications_enabled: bool = True
    wake_word_enabled: bool = True
    screen_watcher_enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "active_mode": self.active_mode,
            "enabled": self.enabled,
            "activated_at": self.activated_at,
            "reason": self.reason,
            "tts_enabled": self.tts_enabled,
            "proactive_enabled": self.proactive_enabled,
            "auto_execute_enabled": self.auto_execute_enabled,
            "notifications_enabled": self.notifications_enabled,
            "wake_word_enabled": self.wake_word_enabled,
            "screen_watcher_enabled": self.screen_watcher_enabled,
        }


# Architecture spec mode aliases — map spec names to internal names
_MODE_ALIASES: dict[str, str] = {
    "observe_only": "silent",      # May can see, never act
    "ask_before_action": "normal",  # Default — confirms above SAFE
    "background": "automation",     # Autonomous for SAFE/MODERATE
    "takeover": "takeover",         # Full hands-on-keyboard, new mode
}

# Mode presets — each mode overrides these settings
_MODE_PRESETS: dict[str, dict[str, Any]] = {
    "normal": {
        "tts_enabled": True,
        "proactive_enabled": True,
        "auto_execute_enabled": False,
        "notifications_enabled": True,
        "wake_word_enabled": True,
        "screen_watcher_enabled": True,
    },
    "focus": {
        "tts_enabled": False,  # No TTS distractions
        "proactive_enabled": False,  # No proactive suggestions
        "auto_execute_enabled": False,
        "notifications_enabled": False,  # No toast notifications
        "wake_word_enabled": False,  # No wake word listening
        "screen_watcher_enabled": True,  # Keep screen watcher (passive)
    },
    "silent": {
        "tts_enabled": False,
        "proactive_enabled": False,
        "auto_execute_enabled": False,
        "notifications_enabled": False,
        "wake_word_enabled": False,
        "screen_watcher_enabled": False,  # Full privacy
    },
    "automation": {
        "tts_enabled": True,
        "proactive_enabled": True,
        "auto_execute_enabled": True,  # Allow ghost mode auto-execution
        "notifications_enabled": True,
        "wake_word_enabled": True,
        "screen_watcher_enabled": True,
    },
    "takeover": {
        "tts_enabled": True,
        "proactive_enabled": True,
        "auto_execute_enabled": True,  # Full autonomous execution
        "notifications_enabled": True,
        "wake_word_enabled": True,
        "screen_watcher_enabled": True,
        # TAKEOVER has highest autonomy — all actions allowed without confirmation
    },
}


class ControlModes:
    """Manages May's control modes (Normal, Focus, Silent, Automation).

    Architecture spec (Part 5) defines 4 explicit autonomy levels:
    - OBSERVE_ONLY: May can see, never act → maps to 'silent'
    - ASK_BEFORE_ACTION: Default. Confirms anything above SAFE → maps to 'normal'
    - BACKGROUND: Autonomous for SAFE/MODERATE, asks for rest → maps to 'automation'
    - TAKEOVER: Full hands-on-keyboard, explicit session only → new mode

    Frontend uses 'normal'/'focus'/'silent'/'automation' for backward compat.
    Architecture spec names (OBSERVE_ONLY, etc.) are accepted as aliases.
    """

    def __init__(self):
        self._state = ModeState()
        self._audit_log: list[dict] = []
        self._load()

    def _load(self):
        """Load mode state from disk."""
        try:
            if _MODES_FILE.exists():
                data = json.loads(_MODES_FILE.read_text(encoding="utf-8"))
                self._state.active_mode = data.get("active_mode", "normal")
                self._state.enabled = data.get("enabled", True)
                self._state.activated_at = data.get("activated_at", time.time())
                self._state.reason = data.get("reason", "")
                self._apply_preset(self._state.active_mode)
                logger.info("Loaded control mode: %s", self._state.active_mode)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load control modes: %s", e)

    def _save(self):
        """Persist mode state to disk."""
        try:
            _MODES_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "active_mode": self._state.active_mode,
                "enabled": self._state.enabled,
                "activated_at": self._state.activated_at,
                "reason": self._state.reason,
            }
            _MODES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as e:
            logger.warning("Failed to save control modes: %s", e)

    def _apply_preset(self, mode: str):
        """Apply a mode preset to the state."""
        preset = _MODE_PRESETS.get(mode, _MODE_PRESETS["normal"])
        for key, value in preset.items():
            setattr(self._state, key, value)

    def set_mode(self, mode: str, reason: str = "") -> dict:
        """Switch to a control mode.

        Accepts both internal names (normal, focus, silent, automation, takeover)
        and architecture spec aliases (observe_only, ask_before_action, background, takeover).

        Args:
            mode: One of "normal", "focus", "silent", "automation", "takeover"
                  or spec aliases: "observe_only", "ask_before_action", "background"
            reason: Why the mode was changed

        Returns:
            Status dict with the new mode and settings.
        """
        # Resolve architecture spec aliases to internal names
        mode = _MODE_ALIASES.get(mode.lower(), mode.lower())
        if mode not in _MODE_PRESETS:
            return {"error": f"Unknown mode: {mode}. Valid: {list(_MODE_PRESETS.keys())} (or spec aliases: {list(_MODE_ALIASES.keys())})"}

        old_mode = self._state.active_mode
        self._state.active_mode = mode
        self._state.activated_at = time.time()
        self._state.reason = reason
        self._apply_preset(mode)

        # Audit log
        self._audit_log.append({
            "action": "mode_change",
            "from": old_mode,
            "to": mode,
            "reason": reason,
            "timestamp": time.time(),
        })
        # Keep last 50 entries
        if len(self._audit_log) > 50:
            self._audit_log = self._audit_log[-50:]

        self._save()
        logger.info("Control mode changed: %s -> %s (reason: %s)", old_mode, mode, reason)

        return self.get_status()

    def get_status(self) -> dict:
        """Get current mode status."""
        return {
            "active_mode": self._state.active_mode,
            "enabled": self._state.enabled,
            "settings": {
                "tts_enabled": self._state.tts_enabled,
                "proactive_enabled": self._state.proactive_enabled,
                "auto_execute_enabled": self._state.auto_execute_enabled,
                "notifications_enabled": self._state.notifications_enabled,
                "wake_word_enabled": self._state.wake_word_enabled,
                "screen_watcher_enabled": self._state.screen_watcher_enabled,
            },
            "activated_at": self._state.activated_at,
            "reason": self._state.reason,
            "available_modes": list(_MODE_PRESETS.keys()),
            "spec_aliases": _MODE_ALIASES,
        }

    def is_tts_enabled(self) -> bool:
        """Check if TTS is allowed in current mode."""
        return self._state.enabled and self._state.tts_enabled

    def is_proactive_enabled(self) -> bool:
        """Check if proactive suggestions are allowed."""
        return self._state.enabled and self._state.proactive_enabled

    def is_auto_execute_enabled(self) -> bool:
        """Check if autonomous execution is allowed."""
        return self._state.enabled and self._state.auto_execute_enabled

    def is_notifications_enabled(self) -> bool:
        """Check if notifications are allowed."""
        return self._state.enabled and self._state.notifications_enabled

    def is_wake_word_enabled(self) -> bool:
        """Check if wake word detection is allowed."""
        return self._state.enabled and self._state.wake_word_enabled

    def is_screen_watcher_enabled(self) -> bool:
        """Check if screen watcher is allowed."""
        return self._state.enabled and self._state.screen_watcher_enabled

    def get_audit_log(self, limit: int = 20) -> list[dict]:
        """Get recent mode change history."""
        return self._audit_log[-limit:]

    def to_dict(self) -> dict:
        """Serialize for API response."""
        return self.get_status()
