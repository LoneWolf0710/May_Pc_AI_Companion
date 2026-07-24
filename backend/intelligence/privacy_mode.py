"""Privacy Mode — pauses all intelligence and keeps an audit log.

Per JARVIS_V2_ARCHITECTURE.md Section 4.7:

When privacy mode is active:
- Shadow learner stops recording actions
- Frustration detector stops monitoring input
- Screen watcher stops capturing/analyzing screens
- Wake word detection is suspended
- Audit log records every pause/resume event with timestamp and reason

The audit log is stored in SQLite and viewable via the API.
It records WHO toggled privacy and WHEN — creating accountability
for privacy-sensitive environments.

All data stays local. No telemetry, no cloud.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("may.intelligence.privacy")


@dataclass
class AuditEntry:
    """A single audit log entry."""
    timestamp: float
    action: str       # "privacy_enabled" or "privacy_disabled"
    reason: str       # User-provided or "manual toggle"
    modules_paused: list[str] = field(default_factory=list)
    duration_sec: float = 0  # How long privacy was active (filled on disable)


class PrivacyMode:
    """Manages privacy mode across all intelligence modules.

    Usage:
        privacy = PrivacyMode()
        privacy.enable(reason="User activated privacy mode")
        # All intelligence modules are now paused
        privacy.disable()
        # All modules resume, audit log records the session duration
    """

    db_path = os.path.join(os.path.expanduser("~"), ".may", "privacy_audit.db")

    # Names of intelligence modules that get paused
    MANAGED_MODULES = [
        "shadow_learner",
        "frustration_detector",
        "screen_watcher",
        "wake_word",
    ]

    def __init__(self):
        self._active = False
        self._enable_time: float = 0
        self._modules: dict[str, Any] = {}  # name -> module instance
        self._ensure_db()

    def _ensure_db(self):
        """Create the audit log database if it doesn't exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                action TEXT NOT NULL,
                reason TEXT DEFAULT '',
                modules_paused TEXT DEFAULT '[]',
                duration_sec REAL DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def register_module(self, name: str, module: Any):
        """Register an intelligence module to be controlled by privacy mode.

        Args:
            name: Module identifier (must be in MANAGED_MODULES)
            module: Module instance with pause() and resume() methods
        """
        self._modules[name] = module
        logger.debug("Registered module '%s' for privacy mode", name)

    def enable(self, reason: str = "manual toggle") -> dict:
        """Enable privacy mode — pause all intelligence modules.

        Args:
            reason: Why privacy mode was activated

        Returns:
            dict with status, modules paused, and timestamp
        """
        if self._active:
            return {"status": "already_active", "active": True}

        self._active = True
        self._enable_time = time.time()
        paused = []

        # Pause all registered modules
        for name, module in self._modules.items():
            try:
                if hasattr(module, "pause"):
                    module.pause()
                    paused.append(name)
                    logger.info("Privacy: paused %s", name)
            except Exception as e:
                logger.warning("Failed to pause %s: %s", name, e)

        # Log the event
        self._log_audit("privacy_enabled", reason, paused, 0)

        logger.info("Privacy mode ENABLED (paused %d modules, reason: %s)",
                     len(paused), reason)

        return {
            "status": "enabled",
            "active": True,
            "modules_paused": paused,
            "timestamp": self._enable_time,
        }

    def disable(self, reason: str = "manual toggle") -> dict:
        """Disable privacy mode — resume all intelligence modules.

        Args:
            reason: Why privacy mode was deactivated

        Returns:
            dict with status, duration, and timestamp
        """
        if not self._active:
            return {"status": "already_inactive", "active": False}

        duration = time.time() - self._enable_time
        resumed = []

        # Resume all registered modules
        for name, module in self._modules.items():
            try:
                if hasattr(module, "resume"):
                    module.resume()
                    resumed.append(name)
                    logger.info("Privacy: resumed %s", name)
            except Exception as e:
                logger.warning("Failed to resume %s: %s", name, e)

        # Log the event
        self._log_audit("privacy_disabled", reason, resumed, duration)

        self._active = False
        self._enable_time = 0

        logger.info("Privacy mode DISABLED (resumed %d modules, duration=%.0fs)",
                     len(resumed), duration)

        return {
            "status": "disabled",
            "active": False,
            "modules_resumed": resumed,
            "duration_sec": round(duration, 1),
        }

    def toggle(self, reason: str = "manual toggle") -> dict:
        """Toggle privacy mode on/off."""
        if self._active:
            return self.disable(reason)
        return self.enable(reason)

    def _log_audit(self, action: str, reason: str, modules: list[str], duration: float):
        """Write an entry to the audit log."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO audit_log (timestamp, action, reason, modules_paused, duration_sec) "
                "VALUES (?, ?, ?, ?, ?)",
                (time.time(), action, reason, json.dumps(modules), duration),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Failed to write audit log: %s", e)

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        """Get recent audit log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of audit entries, most recent first
        """
        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                "SELECT timestamp, action, reason, modules_paused, duration_sec "
                "FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()

            entries = []
            for ts, action, reason, modules_json, duration in rows:
                entries.append({
                    "timestamp": ts,
                    "action": action,
                    "reason": reason,
                    "modules_paused": json.loads(modules_json) if modules_json else [],
                    "duration_sec": duration,
                })
            return entries
        except Exception as e:
            logger.warning("Failed to read audit log: %s", e)
            return []

    def get_status(self) -> dict:
        """Get current privacy mode status."""
        duration = 0
        if self._active and self._enable_time > 0:
            duration = round(time.time() - self._enable_time, 1)

        return {
            "active": self._active,
            "duration_sec": duration,
            "registered_modules": list(self._modules.keys()),
            "total_audit_entries": self._count_entries(),
        }

    def _count_entries(self) -> int:
        """Count total audit log entries."""
        try:
            conn = sqlite3.connect(self.db_path)
            count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0
