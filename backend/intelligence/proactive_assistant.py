"""Proactive assistance module — health/wellness reminders and contextual suggestions.

Monitors user activity and provides proactive suggestions based on:
- Time-based wellness reminders (water, posture, breaks, eye rest)
- Context-aware suggestions based on active app and time of day
- Work session tracking (detects long sessions, suggests breaks)

All suggestions are delivered via the notification system or chat.

Usage:
    assistant = ProactiveAssistant()
    assistant.start()
    # ... later ...
    suggestions = await assistant.check()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("may.intelligence.proactive")

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".may", "proactive.json")


@dataclass
class WellnessRule:
    """A single wellness reminder rule."""
    name: str
    interval_seconds: int       # Seconds between reminders
    message: str                # Reminder message
    enabled: bool = True
    last_triggered: float = 0   # Timestamp of last trigger
    cooldown_seconds: int = 60  # Minimum gap between same reminders

    def should_trigger(self) -> bool:
        """Check if this rule should fire now."""
        if not self.enabled:
            return False
        now = time.time()
        if now - self.last_triggered < self.interval_seconds:
            return False
        return True

    def mark_triggered(self):
        """Mark this rule as triggered."""
        self.last_triggered = time.time()


# Default wellness rules
DEFAULT_RULES = [
    WellnessRule(
        name="water",
        interval_seconds=45 * 60,  # 45 minutes
        message="Time to drink some water~ Stay hydrated~",
        cooldown_seconds=120,
    ),
    WellnessRule(
        name="posture",
        interval_seconds=30 * 60,  # 30 minutes
        message="Check your posture~ Sit up straight and relax your shoulders.",
        cooldown_seconds=120,
    ),
    WellnessRule(
        name="break",
        interval_seconds=90 * 60,  # 90 minutes
        message="90 minutes in — take a 5-minute break. Stretch, walk around~",
        cooldown_seconds=300,
    ),
    WellnessRule(
        name="eyes",
        interval_seconds=20 * 60,  # 20 minutes (20-20-20 rule)
        message="Look away from the screen for 20 seconds. Focus on something far away~",
        cooldown_seconds=120,
    ),
]


@dataclass
class ProactiveConfig:
    """Configuration for proactive assistance."""
    wellness_enabled: bool = True
    work_hours_start: int = 9     # 9 AM
    work_hours_end: int = 22      # 10 PM
    quiet_hours_start: int = 23   # 11 PM
    quiet_hours_end: int = 7      # 7 AM
    rules: dict[str, bool] = field(default_factory=dict)  # rule_name -> enabled

    def save(self):
        """Save config to disk."""
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump({
                "wellness_enabled": self.wellness_enabled,
                "work_hours_start": self.work_hours_start,
                "work_hours_end": self.work_hours_end,
                "quiet_hours_start": self.quiet_hours_start,
                "quiet_hours_end": self.quiet_hours_end,
                "rules": self.rules,
            }, f, indent=2)

    @classmethod
    def load(cls) -> "ProactiveConfig":
        """Load config from disk."""
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
                return cls(
                    wellness_enabled=data.get("wellness_enabled", True),
                    work_hours_start=data.get("work_hours_start", 9),
                    work_hours_end=data.get("work_hours_end", 22),
                    quiet_hours_start=data.get("quiet_hours_start", 23),
                    quiet_hours_end=data.get("quiet_hours_end", 7),
                    rules=data.get("rules", {}),
                )
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()


@dataclass
class WorkSession:
    """Tracks the current work session."""
    started_at: float = 0
    last_input_at: float = 0
    total_active_seconds: float = 0
    break_count: int = 0

    def update_input(self):
        """Record user input activity."""
        now = time.time()
        if self.last_input_at > 0:
            self.total_active_seconds += now - self.last_input_at
        self.last_input_at = now
        if self.started_at == 0:
            self.started_at = now

    def is_idle(self, idle_threshold: int = 300) -> bool:
        """Check if user has been idle for more than threshold seconds."""
        if self.last_input_at == 0:
            return True
        return (time.time() - self.last_input_at) > idle_threshold

    def session_duration(self) -> float:
        """How long the current session has been going (seconds)."""
        if self.started_at == 0:
            return 0
        return time.time() - self.started_at

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "session_minutes": round(self.session_duration() / 60, 1),
            "active_minutes": round(self.total_active_seconds / 60, 1),
            "break_count": self.break_count,
            "is_idle": self.is_idle(),
        }


class ProactiveAssistant:
    """Proactive wellness and context assistant.

    Runs in the background and generates suggestions based on:
    - Time-based wellness reminders
    - Work session tracking
    - Context-aware suggestions (time of day, active patterns)
    """

    def __init__(self):
        self._config = ProactiveConfig.load()
        self._rules = list(DEFAULT_RULES)
        self._session = WorkSession()
        self._suggestions: list[dict] = []
        self._active = False
        self._check_task: asyncio.Task | None = None

        # Apply saved rule states
        for rule in self._rules:
            if rule.name in self._config.rules:
                rule.enabled = self._config.rules[rule.name]

    @property
    def enabled(self) -> bool:
        return self._config.wellness_enabled

    def enable(self):
        """Enable proactive assistance."""
        self._config.wellness_enabled = True
        self._config.save()
        logger.info("Proactive assistance enabled")

    def disable(self):
        """Disable proactive assistance."""
        self._config.wellness_enabled = False
        self._config.save()
        self._stop_check_loop()
        logger.info("Proactive assistance disabled")

    def toggle(self) -> bool:
        """Toggle proactive assistance on/off."""
        if self.enabled:
            self.disable()
        else:
            self.enable()
        return self.enabled

    def set_rule_enabled(self, rule_name: str, enabled: bool):
        """Enable or disable a specific wellness rule."""
        for rule in self._rules:
            if rule.name == rule_name:
                rule.enabled = enabled
                self._config.rules[rule_name] = enabled
                self._config.save()
                logger.info("Rule '%s' %s", rule_name, "enabled" if enabled else "disabled")
                return
        logger.warning("Unknown rule: %s", rule_name)

    def get_status(self) -> dict:
        """Get proactive assistant status."""
        return {
            "enabled": self.enabled,
            "session": self._session.to_dict(),
            "rules": [
                {
                    "name": r.name,
                    "enabled": r.enabled,
                    "interval_minutes": r.interval_seconds // 60,
                    "message": r.message,
                    "last_triggered": r.last_triggered,
                }
                for r in self._rules
            ],
            "pending_suggestions": len(self._suggestions),
            "config": {
                "work_hours": f"{self._config.work_hours_start}:00 - {self._config.work_hours_end}:00",
                "quiet_hours": f"{self._config.quiet_hours_start}:00 - {self._config.quiet_hours_end}:00",
            },
        }

    def record_activity(self):
        """Record user input activity (call on each user message/input)."""
        self._session.update_input()

    def _is_quiet_hours(self) -> bool:
        """Check if we're in quiet hours (no reminders)."""
        from datetime import datetime
        hour = datetime.now().hour
        start = self._config.quiet_hours_start
        end = self._config.quiet_hours_end
        if start > end:  # Crosses midnight
            return hour >= start or hour < end
        return start <= hour < end

    def _is_work_hours(self) -> bool:
        """Check if we're in work hours."""
        from datetime import datetime
        hour = datetime.now().hour
        return self._config.work_hours_start <= hour < self._config.work_hours_end

    async def check(self) -> list[dict]:
        """Check all rules and return pending suggestions.

        Returns:
            List of suggestion dicts with 'type', 'message', 'priority' keys
        """
        if not self.enabled or self._is_quiet_hours():
            return []

        suggestions = []

        # Check wellness rules
        for rule in self._rules:
            if rule.should_trigger():
                rule.mark_triggered()
                suggestions.append({
                    "type": "wellness",
                    "rule": rule.name,
                    "message": rule.message,
                    "priority": "normal",
                })

        # Check work session
        if self._session.session_duration() > 0:
            duration_min = self._session.session_duration() / 60

            # Long session without break (> 2 hours)
            if duration_min > 120 and self._session.break_count == 0:
                suggestions.append({
                    "type": "break",
                    "message": f"You've been working for {int(duration_min)} minutes straight. Take a break~",
                    "priority": "high",
                })

            # Very long session (> 4 hours)
            if duration_min > 240:
                suggestions.append({
                    "type": "break",
                    "message": f"Almost {int(duration_min / 60)} hours now. You should really rest your eyes and stretch~",
                    "priority": "high",
                })

        # Time-based suggestions
        from datetime import datetime
        now = datetime.now()

        # Late night reminder
        if now.hour >= 1 and now.hour < 4 and not self._session.is_idle():
            suggestions.append({
                "type": "context",
                "message": "It's pretty late~ Consider wrapping up and getting some sleep.",
                "priority": "normal",
            })

        # Morning greeting (first activity after 6 AM)
        if 6 <= now.hour <= 9 and self._session.session_duration() < 300:
            suggestions.append({
                "type": "context",
                "message": "Good morning~ Ready to start the day?",
                "priority": "low",
            })

        self._suggestions.extend(suggestions)
        return suggestions

    def get_pending_suggestions(self) -> list[dict]:
        """Get and clear pending suggestions."""
        suggestions = list(self._suggestions)
        self._suggestions.clear()
        return suggestions

    def acknowledge_suggestion(self, suggestion_type: str):
        """User acknowledged a suggestion."""
        if suggestion_type == "break":
            self._session.break_count += 1
            self._session.started_at = time.time()
            self._session.total_active_seconds = 0

    def _stop_check_loop(self):
        """Stop the background check loop."""
        if self._check_task and not self._check_task.done():
            self._check_task.cancel()
            self._check_task = None

    async def start(self):
        """Start the proactive check loop (runs in background)."""
        if not self.enabled:
            return
        self._active = True
        self._check_task = asyncio.create_task(self._check_loop())
        logger.info("Proactive assistant started")

    async def stop(self):
        """Stop the proactive check loop."""
        self._active = False
        self._stop_check_loop()
        logger.info("Proactive assistant stopped")

    async def _check_loop(self):
        """Background loop that checks for suggestions every 60 seconds."""
        while self._active:
            try:
                await asyncio.sleep(60)
                if not self._active:
                    break
                suggestions = await self.check()
                if suggestions:
                    logger.info("Proactive: %d suggestions generated", len(suggestions))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Proactive check loop error: %s", e)
