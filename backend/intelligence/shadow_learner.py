"""Shadow Learning Mode — learns user patterns from repeated actions.

Per JARVIS_V2_ARCHITECTURE.md Section 4.1:

Runs silently at ~1% CPU. Watches what the user does and learns patterns.
After 3+ repetitions of a pattern, suggests an automation.

Monitors:
- Apps opened at what times
- Repeated action sequences (open Chrome → Gmail → inbox every morning)
- Files always opened together
- Copy-paste patterns

All data stays 100% local in SQLite. Never leaves the machine.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("may.intelligence.shadow_learner")


# ── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class ActionEvent:
    """A single recorded user action."""
    action_type: str   # e.g. "open_app", "write_file", "web_search"
    target: str        # e.g. "chrome", "main.py", "python tutorials"
    timestamp: float   # Unix timestamp
    extra: dict = field(default_factory=dict)  # Additional context


@dataclass
class ActionPattern:
    """A repeated sequence of actions detected by the shadow learner."""
    actions: list[str]        # e.g. ["open_chrome", "open_gmail", "open_inbox"]
    count: int                # How many times this sequence was observed
    first_seen: float         # Timestamp of first occurrence
    last_seen: float          # Timestamp of most recent occurrence
    time_range: str           # e.g. "9am-9:30am"
    suggested: bool = False   # Whether we've already suggested this automation
    macro_steps: list[dict] = field(default_factory=list)  # Steps for the automation


# ── Shadow Learner ──────────────────────────────────────────────────────────

class ShadowLearner:
    """Learns user patterns from repeated actions. Runs in background.

    Usage:
        learner = ShadowLearner()
        learner.record_event("open_app", "chrome", time.time())
        learner.record_event("open_app", "gmail", time.time())
        # After 3+ repetitions, get_suggestions() returns automation proposals
    """

    threshold = 3   # Repetitions before suggesting
    window_size = 5 # Sliding window for sequence detection
    max_in_memory = 10000  # Max events kept in memory (full history in SQLite)
    db_path = os.path.join(os.path.expanduser("~"), ".may", "shadow_patterns.db")

    def __init__(self):
        self._events: list[ActionEvent] = []
        self._patterns: list[ActionPattern] = []
        self._suggestions: list[dict] = []
        self._lock = asyncio.Lock()
        self._active = True
        self._ensure_db()
        self._skill_store = None  # P5: Set via set_skill_store() — auto-creates skills from patterns

    def set_skill_store(self, store):
        """Register the SkillStore for auto-creating skills from detected patterns."""
        self._skill_store = store

    def _ensure_db(self):
        """Create the SQLite database if it doesn't exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                target TEXT NOT NULL,
                timestamp REAL NOT NULL,
                extra TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actions TEXT NOT NULL,
                count INTEGER DEFAULT 1,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                time_range TEXT DEFAULT '',
                suggested INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id INTEGER,
                message TEXT NOT NULL,
                timestamp REAL NOT NULL,
                accepted INTEGER DEFAULT 0,
                FOREIGN KEY (pattern_id) REFERENCES patterns(id)
            )
        """)
        conn.commit()
        conn.close()

    def record_event(self, action_type: str, target: str, timestamp: float | None = None, extra: dict | None = None):
        """Record every tool call and system action.

        Called from jarvis.py after every successful tool execution.
        Respects pause state for privacy mode.
        """
        if not self._active:
            return

        ts = timestamp or time.time()
        event = ActionEvent(
            action_type=action_type,
            target=target,
            timestamp=ts,
            extra=extra or {},
        )
        self._events.append(event)

        # Trim in-memory buffer to prevent unbounded growth
        if len(self._events) > self.max_in_memory:
            self._events = self._events[-self.max_in_memory:]

        # Persist to SQLite (non-blocking in production, but synchronous here for simplicity)
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO events (action_type, target, timestamp, extra) VALUES (?, ?, ?, ?)",
                (action_type, target, ts, json.dumps(extra or {})),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Failed to persist shadow event: %s", e)

        # Analyze patterns (lightweight — just check recent events)
        self._analyze_patterns_sync()

    def _analyze_patterns_sync(self):
        """Sliding window n-gram frequency analysis (synchronous version).

        Checks the last N events for repeated sequences.
        """
        if len(self._events) < self.threshold:
            return

        # Look at the last `window_size` events
        recent = self._events[-self.window_size:]

        # Build 2-gram and 3-gram sequences
        for ngram_size in (2, 3):
            if len(recent) < ngram_size:
                continue

            for i in range(len(recent) - ngram_size + 1):
                sequence = [f"{e.action_type}:{e.target}" for e in recent[i:i + ngram_size]]
                seq_key = " → ".join(sequence)

                # Count how many times this sequence appears in ALL events
                count = self._count_sequence(sequence)

                if count >= self.threshold:
                    # Check if we already have this pattern
                    existing = any(
                        p.actions == sequence and not p.suggested
                        for p in self._patterns
                    )
                    if not existing:
                        self._add_pattern(sequence, count)

    def _count_sequence(self, sequence: list[str]) -> int:
        """Count how many times a sequence appears in the recent event log."""
        count = 0
        # Only scan recent events (last 500) for performance
        recent_events = self._events[-500:]
        events = [f"{e.action_type}:{e.target}" for e in recent_events]
        for i in range(len(events) - len(sequence) + 1):
            if events[i:i + len(sequence)] == sequence:
                count += 1
        return count

    def _add_pattern(self, actions: list[str], count: int):
        """Add a new detected pattern and create a suggestion."""
        now = time.time()
        pattern = ActionPattern(
            actions=actions,
            count=count,
            first_seen=now,
            last_seen=now,
            time_range=self._get_time_range(),
            suggested=True,  # Mark as suggested immediately
        )
        self._patterns.append(pattern)

        # Generate a natural language suggestion
        action_descriptions = []
        for act in actions:
            parts = act.split(":", 1)
            if len(parts) == 2:
                action_type, target = parts
                action_descriptions.append(f"{action_type.replace('_', ' ')} {target}")
            else:
                action_descriptions.append(act.replace("_", " "))

        sequence_str = ", then ".join(action_descriptions)
        suggestion = f"I've noticed you {sequence_str} multiple times. Want me to automate that?"

        self._suggestions.append({
            "pattern": pattern,
            "message": suggestion,
            "timestamp": now,
        })

        # Persist the pattern
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO patterns (actions, count, first_seen, last_seen, time_range, suggested) "
                "VALUES (?, ?, ?, ?, ?, 1)",
                (json.dumps(actions), count, pattern.first_seen, pattern.last_seen, pattern.time_range),
            )
            pattern_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO suggestions (pattern_id, message, timestamp) VALUES (?, ?, ?)",
                (pattern_id, suggestion, now),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Failed to persist pattern: %s", e)

        logger.info("Shadow learner detected pattern: %s (count=%d)", " → ".join(actions), count)

        # P5: Auto-create a skill in SkillStore when a pattern is detected
        self._auto_create_skill_from_pattern(pattern, actions, count)

    def _get_time_range(self) -> str:
        """Get the approximate time range of recent events."""
        if not self._events:
            return ""
        from datetime import datetime
        recent = self._events[-5:]
        times = [datetime.fromtimestamp(e.timestamp) for e in recent]
        earliest = min(times).strftime("%I:%M %p")
        latest = max(times).strftime("%I:%M %p")
        return f"{earliest}-{latest}"

    def get_suggestions(self) -> list[dict]:
        """Get pending suggestions that haven't been shown to the user yet."""
        return [s for s in self._suggestions if not s.get("shown")]

    def mark_shown(self, suggestion: dict):
        """Mark a suggestion as shown to the user."""
        suggestion["shown"] = True

    def get_stats(self) -> dict:
        """Get shadow learner statistics."""
        return {
            "events_recorded": len(self._events),
            "patterns_detected": len(self._patterns),
            "suggestions_pending": len(self.get_suggestions()),
            "threshold": self.threshold,
        }

    def pause(self):
        """Pause the shadow learner (for privacy mode)."""
        self._active = False
        logger.info("Shadow learner paused")

    def resume(self):
        """Resume the shadow learner."""
        self._active = True
        logger.info("Shadow learner resumed")

    def to_macro(self, pattern: ActionPattern) -> dict:
        """Convert a detected pattern to an executable scheduled macro.

        Returns a dict with steps that can be executed by the orchestrator.
        """
        steps = []
        for action_str in pattern.actions:
            parts = action_str.split(":", 1)
            if len(parts) == 2:
                action_type, target = parts
                steps.append({
                    "tool": action_type,
                    "args": {"app_name": target} if action_type == "open_app" else {"path": target},
                })
        return {
            "name": f"Auto: {' → '.join(pattern.actions)}",
            "steps": steps,
            "pattern_count": pattern.count,
        }

    def _auto_create_skill_from_pattern(self, pattern: ActionPattern, actions: list[str], count: int):
        """P5: Auto-create a Skill in SkillStore when a pattern is detected.

        Converts a detected action pattern into a reusable skill with steps,
        trigger phrases derived from the actions, and a name based on the sequence.
        Only creates if the skill store is registered and the pattern has >= 2 steps.
        """
        if self._skill_store is None or len(actions) < 2:
            return

        # Check if a skill with the same steps already exists
        existing_skills = self._skill_store.list_all()
        existing_actions = set()
        for s in existing_skills:
            step_key = " → ".join(step.tool_name + ":" + str(step.params) for step in s.steps)
            existing_actions.add(step_key)

        new_step_key = " → ".join(actions)
        if new_step_key in existing_actions:
            return  # Skill already exists for this exact sequence

        # Build skill steps from the action pattern
        skill_steps = []
        trigger_phrases = []
        action_labels = []
        for action_str in actions:
            parts = action_str.split(":", 1)
            if len(parts) == 2:
                action_type, target = parts
                step = {"tool_name": action_type, "params": {}, "description": f"{action_type} {target}"}
                if action_type == "open_app":
                    step["params"] = {"app_name": target}
                elif action_type == "write_file":
                    step["params"] = {"path": target}
                elif action_type == "web_search":
                    step["params"] = {"query": target}
                else:
                    step["params"] = {"name": target}
                skill_steps.append(step)
                action_labels.append(f"{action_type.replace('_', ' ')} {target}")
                # Build trigger phrases from the action targets
                trigger_phrases.append(target.lower())
            else:
                skill_steps.append({"tool_name": action_str, "params": {}, "description": action_str})
                action_labels.append(action_str.replace("_", " "))

        # Generate a descriptive name
        name = f"Auto: {', then '.join(action_labels)}"
        description = ("Automatically learned from repeated user actions. "
                        f"Observed {count} times. Steps: {' → '.join(action_labels)}")
        tags = ["auto_learned", "shadow_learner"]

        # Add the first action target as a trigger phrase for matching
        if trigger_phrases:
            tags.append(trigger_phrases[0])

        try:
            self._skill_store.store(
                name=name,
                description=description,
                steps=skill_steps,
                trigger_phrases=trigger_phrases,
                tags=tags,
                confidence=min(0.8, 0.5 + count * 0.05),  # Higher confidence with more observations
            )
            logger.info("Auto-created skill from pattern: %s (%d steps)", name, len(skill_steps))
        except Exception as e:
            logger.warning("Failed to auto-create skill from pattern: %s", e)
