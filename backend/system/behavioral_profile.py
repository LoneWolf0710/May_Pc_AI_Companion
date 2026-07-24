"""Behavioral Profile — Adaptive Normal Behavior Learning.

Per MAY_FINAL_ARCHITECTURE.md Part 5 (Immune System):

Tracks the user's "normal" behavior patterns and flags anomalies.
Every tool execution is scored against the learned profile.
If an action seems anomalous, it's flagged for review.

Mitigates OWASP A03 (Memory & Context Poisoning) by ensuring
behavioral profiles can't be manipulated to accept destructive actions.

Storage: ~/.may/behavioral_profile.json
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger("may.system.behavioral_profile")

_PROFILE_FILE = Path.home() / ".may" / "behavioral_profile.json"

# Minimum observations before profile is considered reliable
_MIN_OBSERVATIONS = 10

# How much weight to give recent vs historical observations
_RECENCY_WEIGHT = 0.7  # 70% recent, 30% historical


class BehavioralProfile:
    """Learns the user's normal behavior patterns.

    Tracks:
    - Which tools are used and how often
    - What time of day actions typically occur
    - What parameters are typically passed
    - Sequences of actions (e.g., open_app → type_text)

    Provides a score (0.0 - 1.0) for each new action:
    - 1.0 = perfectly normal (seen many times)
    - 0.5 = somewhat unusual (new tool or unusual params)
    - 0.0 = highly anomalous (never seen before, unusual context)
    """

    def __init__(self):
        self._tool_counts: dict[str, int] = defaultdict(int)
        self._tool_hour_counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self._tool_param_patterns: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._action_sequences: dict[str, int] = defaultdict(int)  # "A→B" → count
        self._total_actions: int = 0
        self._last_actions: list[str] = []  # Last 10 action names for sequence tracking
        self._profile_modified: bool = False
        self._load()

    def _load(self):
        """Load profile from disk."""
        if not _PROFILE_FILE.exists():
            return
        try:
            data = json.loads(_PROFILE_FILE.read_text(encoding="utf-8"))
            self._tool_counts = defaultdict(int, data.get("tool_counts", {}))
            self._total_actions = data.get("total_actions", 0)
            self._last_actions = data.get("last_actions", [])
            # Rebuild hour counts
            for tool, hours in data.get("tool_hour_counts", {}).items():
                self._tool_hour_counts[tool] = defaultdict(int, {int(h): c for h, c in hours.items()})
            # Rebuild param patterns
            for tool, params in data.get("tool_param_patterns", {}).items():
                self._tool_param_patterns[tool] = defaultdict(int, params)
            # Rebuild sequences
            self._action_sequences = defaultdict(int, data.get("action_sequences", {}))
            logger.info("Loaded behavioral profile: %d actions, %d tools", self._total_actions, len(self._tool_counts))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load behavioral profile: %s", e)

    def _save(self):
        """Persist profile to disk."""
        try:
            _PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "tool_counts": dict(self._tool_counts),
                "total_actions": self._total_actions,
                "last_actions": self._last_actions,
                "tool_hour_counts": {
                    tool: {str(h): c for h, c in hours.items()}
                    for tool, hours in self._tool_hour_counts.items()
                },
                "tool_param_patterns": {
                    tool: dict(params)
                    for tool, params in self._tool_param_patterns.items()
                },
                "action_sequences": dict(self._action_sequences),
                "updated_at": time.time(),
            }
            _PROFILE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self._profile_modified = False
        except OSError as e:
            logger.warning("Failed to save behavioral profile: %s", e)

    def record_action(self, tool_name: str, params: dict | None = None):
        """Record a tool execution for behavioral learning.

        Args:
            tool_name: The tool/action that was executed
            params: Optional parameters passed to the tool
        """
        self._total_actions += 1
        self._tool_counts[tool_name] += 1

        # Track by hour of day
        hour = int(time.strftime("%H"))
        self._tool_hour_counts[tool_name][hour] += 1

        # Track parameter patterns (top-level keys only)
        if params:
            for key in sorted(params.keys()):
                self._tool_param_patterns[tool_name][key] += 1

        # Track action sequences
        if self._last_actions:
            last_action = self._last_actions[-1]
            sequence = f"{last_action}→{tool_name}"
            self._action_sequences[sequence] += 1

        # Update recent actions (keep last 10)
        self._last_actions.append(tool_name)
        if len(self._last_actions) > 10:
            self._last_actions = self._last_actions[-10:]

        self._profile_modified = True
        # Auto-save every 20 actions
        if self._total_actions % 20 == 0:
            self._save()

    def score_action(self, tool_name: str, params: dict | None = None) -> float:
        """Score how 'normal' an action is based on learned behavior.

        Args:
            tool_name: The tool/action being considered
            params: Optional parameters

        Returns:
            Score from 0.0 (highly anomalous) to 1.0 (perfectly normal)
        """
        if self._total_actions < _MIN_OBSERVATIONS:
            return 0.5  # Not enough data — neutral score

        scores = []

        # 1. Tool frequency score
        tool_count = self._tool_counts.get(tool_name, 0)
        if tool_count > 0:
            # Normalize: 100+ uses = 1.0, 1 use = ~0.3
            freq_score = min(1.0, 0.3 + (tool_count / 100) * 0.7)
        else:
            freq_score = 0.1  # Never seen this tool before
        scores.append(freq_score)

        # 2. Time-of-day score
        hour = int(time.strftime("%H"))
        hour_count = self._tool_hour_counts.get(tool_name, {}).get(hour, 0)
        total_tool = self._tool_counts.get(tool_name, 1)
        if total_tool > 0:
            time_score = min(1.0, hour_count / max(1, total_tool) * 3)
        else:
            time_score = 0.5
        scores.append(time_score)

        # 3. Parameter pattern score
        if params:
            known_params = set(self._tool_param_patterns.get(tool_name, {}).keys())
            provided_params = set(params.keys())
            if known_params:
                overlap = len(provided_params & known_params) / max(1, len(provided_params))
                param_score = 0.5 + overlap * 0.5
            else:
                param_score = 0.5  # No history for this tool's params
        else:
            param_score = 0.8  # No params is usually normal
        scores.append(param_score)

        # 4. Sequence score
        if self._last_actions:
            last_action = self._last_actions[-1]
            sequence = f"{last_action}→{tool_name}"
            seq_count = self._action_sequences.get(sequence, 0)
            if seq_count > 0:
                seq_score = min(1.0, 0.5 + seq_count / 20)
            else:
                seq_score = 0.4  # New sequence
        else:
            seq_score = 0.5
        scores.append(seq_score)

        # Weighted average
        weights = [0.35, 0.2, 0.2, 0.25]  # Tool frequency most important
        return sum(s * w for s, w in zip(scores, weights))

    def get_profile_summary(self) -> dict:
        """Get a summary of the learned behavioral profile."""
        top_tools = sorted(self._tool_counts.items(), key=lambda x: -x[1])[:10]
        return {
            "total_actions": self._total_actions,
            "unique_tools": len(self._tool_counts),
            "top_tools": [{"tool": t, "count": c} for t, c in top_tools],
            "reliable": self._total_actions >= _MIN_OBSERVATIONS,
        }

    def save(self):
        """Force save to disk."""
        if self._profile_modified:
            self._save()
