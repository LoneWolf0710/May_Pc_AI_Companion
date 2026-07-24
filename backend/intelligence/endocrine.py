"""
Endocrine System — Immutable Emotional State for May.

From MAY_FINAL_ARCHITECTURE.md Part 3:
"Incident memories get tagged with emotional weight. Sleep cycles consolidate
emotional memories first. Mood is NOT a string in a prompt — it's an immutable
hormone state that affects inference parameters."

Hormones:
- cortisol: stress level (0.0-1.0), decays slowly
- dopamine: satisfaction/reward (0.0-1.0), decays moderately
- serotonin: baseline well-being (0.0-1.0), decays slowly
- adrenaline: alertness/urgency (0.0-1.0), decays fast
- oxytocin: social bonding/trust (0.0-1.0), decays slowly
- endorphin: pain/pleasure balance (0.0-1.0), decays moderately

Each hormone has:
- A current value (0.0-1.0)
- A baseline (natural resting level, typically 0.3-0.5)
- A decay rate (how fast it returns to baseline per hour)
- An update method that clamps to [0.0, 1.0]

The hormone state is IMMUTABLE to prompt injection — it's computed from
actual interaction signals, not from what the user says about mood.
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("may.intelligence.endocrine")

# File path for persistence
_HORMONE_FILE = Path.home() / ".may" / "hormones.json"

# Decay rates (fraction per hour that returns to baseline)
DECAY_RATES = {
    "cortisol": 0.15,    # Stress decays slowly — lingers after incidents
    "dopamine": 0.25,    # Satisfaction decays moderately
    "serotonin": 0.08,   # Well-being is very stable
    "adrenaline": 0.60,  # Alertness fades quickly
    "oxytocin": 0.10,    # Social bonding is persistent
    "endorphin": 0.30,   # Pain relief fades moderately fast
}

BASELINES = {
    "cortisol": 0.3,     # Normal stress baseline
    "dopamine": 0.4,     # Moderate satisfaction baseline
    "serotonin": 0.6,    # Good well-being baseline
    "adrenaline": 0.2,   # Low alertness baseline
    "oxytocin": 0.3,     # Moderate social baseline
    "endorphin": 0.3,    # Low endorphin baseline
}


@dataclass
class Hormone:
    """A single hormone with value, baseline, and decay."""
    name: str
    value: float
    baseline: float
    decay_rate: float  # fraction per hour
    last_updated: float = field(default_factory=time.time)

    def update(self, new_value: float) -> None:
        """Set a new value, clamped to [0.0, 1.0]."""
        self.value = max(0.0, min(1.0, new_value))
        self.last_updated = time.time()

    def apply_decay(self) -> None:
        """Apply natural decay toward baseline based on elapsed time."""
        now = time.time()
        elapsed_hours = (now - self.last_updated) / 3600.0

        if elapsed_hours <= 0:
            return

        # Exponential decay toward baseline
        # value(t) = baseline + (value - baseline) * exp(-decay_rate * t)
        diff = self.value - self.baseline
        decay_factor = math.exp(-self.decay_rate * elapsed_hours)
        self.value = self.baseline + diff * decay_factor
        self.value = max(0.0, min(1.0, self.value))
        self.last_updated = now

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "name": self.name,
            "value": round(self.value, 4),
            "baseline": self.baseline,
            "decay_rate": self.decay_rate,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Hormone:
        """Deserialize from dict."""
        return cls(
            name=data["name"],
            value=data["value"],
            baseline=data.get("baseline", BASELINES.get(data["name"], 0.3)),
            decay_rate=data.get("decay_rate", DECAY_RATES.get(data["name"], 0.2)),
            last_updated=data.get("last_updated", time.time()),
        )


class EndocrineSystem:
    """Manages May's immutable emotional hormone state.

    Hormones decay naturally over time and are updated by interaction signals.
    The state is NOT influenced by user text — only by actual behavior patterns
    (tool executions, errors, conversation energy, frustration signals, etc.).
    """

    def __init__(self):
        self._hormones: dict[str, Hormone] = {}
        self._last_save: float = 0.0  # Debounce timestamp for _save_state
        self._init_hormones()
        self._load_state()

    def _init_hormones(self) -> None:
        """Initialize all hormones at their baselines."""
        for name in DECAY_RATES:
            self._hormones[name] = Hormone(
                name=name,
                value=BASELINES[name],
                baseline=BASELINES[name],
                decay_rate=DECAY_RATES[name],
            )

    def _load_state(self) -> None:
        """Load persisted hormone state from disk."""
        if not _HORMONE_FILE.exists():
            return

        try:
            data = json.loads(_HORMONE_FILE.read_text(encoding="utf-8"))
            for h_data in data.get("hormones", []):
                name = h_data.get("name", "")
                if name in self._hormones:
                    self._hormones[name] = Hormone.from_dict(h_data)
            logger.info("Loaded hormone state from %s", _HORMONE_FILE)
        except Exception as e:
            logger.warning("Failed to load hormone state: %s", e)

    def _save_state(self) -> None:
        """Persist hormone state to disk. Debounced — at most once per 5 seconds."""
        now = time.time()
        if now - self._last_save < 5.0:
            return
        self._last_save = now
        try:
            _HORMONE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "hormones": [h.to_dict() for h in self._hormones.values()],
                "saved_at": now,
            }
            _HORMONE_FILE.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.warning("Failed to save hormone state: %s", e)

    def decay_all(self) -> None:
        """Apply natural decay to all hormones toward their baselines."""
        for hormone in self._hormones.values():
            hormone.apply_decay()

    def update_from_tool_execution(
        self,
        tool_name: str,
        success: bool,
        risk_tier: str = "SAFE",
        latency_ms: float = 0.0,
    ) -> None:
        """Update hormones based on a tool execution event.

        This is the PRIMARY input mechanism — hormones reflect what actually
        happened, not what the user said.
        """
        self.decay_all()  # Apply decay first

        if success:
            # Successful action → slight dopamine boost
            self._hormones["dopamine"].update(
                self._hormones["dopamine"].value + 0.05
            )

            # Low-risk successful action → serotonin boost (baseline well-being)
            if risk_tier == "SAFE":
                self._hormones["serotonin"].update(
                    self._hormones["serotonin"].value + 0.02
                )
        else:
            # Failed action → cortisol boost (stress)
            self._hormones["cortisol"].update(
                self._hormones["cortisol"].value + 0.10
            )
            # Dopamine decrease (frustration)
            self._hormones["dopamine"].update(
                self._hormones["dopamine"].value - 0.05
            )

        # High-risk actions → adrenaline boost (alertness)
        if risk_tier in ("DESTRUCTIVE", "CRITICAL"):
            self._hormones["adrenaline"].update(
                self._hormones["adrenaline"].value + 0.15
            )

        # Very slow actions (>5s) → cortisol boost (patience wears thin)
        if latency_ms > 5000:
            self._hormones["cortisol"].update(
                self._hormones["cortisol"].value + 0.03
            )

        self._save_state()

    def update_from_conversation(
        self,
        user_energy: float,
        frustration_score: float,
        mood: str = "neutral",
    ) -> None:
        """Update hormones from conversation analysis signals.

        Args:
            user_energy: 0.0 (calm) to 1.0 (intense)
            frustration_score: 0.0 (calm) to 1.0 (very frustrated)
            mood: User's detected mood string
        """
        self.decay_all()

        # Frustration → cortisol
        if frustration_score > 0.5:
            self._hormones["cortisol"].update(
                self._hormones["cortisol"].value + frustration_score * 0.15
            )

        # High energy → adrenaline
        if user_energy > 0.7:
            self._hormones["adrenaline"].update(
                self._hormones["adrenaline"].value + (user_energy - 0.7) * 0.2
            )

        # Positive mood → dopamine + serotonin
        positive_moods = {"happy", "excited", "grateful", "calm"}
        if mood in positive_moods:
            self._hormones["dopamine"].update(
                self._hormones["dopamine"].value + 0.05
            )
            self._hormones["serotonin"].update(
                self._hormones["serotonin"].value + 0.03
            )

        # Negative mood → cortisol
        negative_moods = {"frustrated", "angry", "anxious", "sad"}
        if mood in negative_moods:
            self._hormones["cortisol"].update(
                self._hormones["cortisol"].value + 0.08
            )

        self._save_state()

    def update_from_interaction(self, interaction_type: str) -> None:
        """Update hormones from specific interaction events.

        interaction_type: 'tool_success', 'tool_failure', 'user_thanks',
                         'user_frustration', 'long_session', 'idle', 'wake_word'
        """
        self.decay_all()

        if interaction_type == "tool_success":
            self._hormones["dopamine"].update(
                self._hormones["dopamine"].value + 0.03
            )
        elif interaction_type == "tool_failure":
            self._hormones["cortisol"].update(
                self._hormones["cortisol"].value + 0.08
            )
        elif interaction_type == "user_thanks":
            self._hormones["oxytocin"].update(
                self._hormones["oxytocin"].value + 0.10
            )
            self._hormones["dopamine"].update(
                self._hormones["dopamine"].value + 0.05
            )
        elif interaction_type == "user_frustration":
            self._hormones["cortisol"].update(
                self._hormones["cortisol"].value + 0.12
            )
            self._hormones["oxytocin"].update(
                self._hormones["oxytocin"].value - 0.03
            )
        elif interaction_type == "long_session":
            # Extended session → endorphin boost (flow state)
            self._hormones["endorphin"].update(
                self._hormones["endorphin"].value + 0.05
            )
            self._hormones["adrenaline"].update(
                self._hormones["adrenaline"].value - 0.05
            )
        elif interaction_type == "idle":
            # Idle time → gradual return to baseline
            self._hormones["adrenaline"].update(
                self._hormones["adrenaline"].value - 0.05
            )
        elif interaction_type == "wake_word":
            self._hormones["adrenaline"].update(
                self._hormones["adrenaline"].value + 0.10
            )
            self._hormones["oxytocin"].update(
                self._hormones["oxytocin"].value + 0.05
            )

        self._save_state()

    def get_hormone(self, name: str) -> float:
        """Get the current value of a hormone (0.0-1.0)."""
        if name in self._hormones:
            return self._hormones[name].value
        return 0.3  # default

    def get_all(self) -> dict[str, float]:
        """Get all hormone values."""
        return {name: round(h.value, 4) for name, h in self._hormones.items()}

    def get_dominant_hormone(self) -> str:
        """Get the hormone with the highest value above its baseline."""
        max_name = "serotonin"
        max_excess = -1.0
        for name, h in self._hormones.items():
            excess = h.value - h.baseline
            if excess > max_excess:
                max_excess = excess
                max_name = name
        return max_name

    def get_emotional_state(self) -> str:
        """Derive a human-readable emotional state from hormone levels.

        Maps hormone combinations to emotional descriptors.
        """
        c = self._hormones["cortisol"].value
        d = self._hormones["dopamine"].value
        s = self._hormones["serotonin"].value
        a = self._hormones["adrenaline"].value
        o = self._hormones["oxytocin"].value

        if c > 0.7:
            return "stressed"
        elif a > 0.7:
            return "alert"
        elif d > 0.7 and a > 0.5:
            return "excited"
        elif d > 0.6 and s > 0.5:
            return "happy"
        elif o > 0.6:
            return "connected"
        elif c > 0.5:
            return "anxious"
        elif s > 0.6:
            return "calm"
        elif a < 0.2 and s < 0.4:
            return "tired"
        else:
            return "neutral"

    def get_context_for_llm(self) -> str:
        """Get a concise hormone context string for LLM injection.

        This is injected into the system prompt so May's personality
        adapts to her current emotional state — but it's computed from
        REAL signals, not from user text.
        """
        state = self.get_emotional_state()
        c = self._hormones["cortisol"].value
        d = self._hormones["dopamine"].value

        # Only inject if significantly different from baseline
        if state == "neutral":
            return ""

        parts = [f"emotional_state={state}"]
        if c > 0.5:
            parts.append(f"stress={c:.2f}")
        if d > 0.6:
            parts.append(f"satisfaction={d:.2f}")

        return " ".join(parts)

    def reset_to_baselines(self) -> None:
        """Reset all hormones to baselines."""
        self._init_hormones()
        self._save_state()
        logger.info("Reset all hormones to baselines")

    def get_stats(self) -> dict:
        """Get hormone statistics."""
        return {
            "hormones": {name: h.to_dict() for name, h in self._hormones.items()},
            "emotional_state": self.get_emotional_state(),
            "dominant": self.get_dominant_hormone(),
            "llm_context": self.get_context_for_llm(),
        }
