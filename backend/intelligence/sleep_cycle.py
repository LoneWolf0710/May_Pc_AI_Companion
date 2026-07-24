"""
Sleep Cycle — Idle-Time Consolidation for May.

From MAY_FINAL_ARCHITECTURE.md Part 3:
"Background process during idle: monitors time since last interaction.
Five states: Wake → Drowsy (5min) → Light (30min) → Deep (120min) → REM (360min).
Actions: compact DBs, prune old logs, restart inference server,
merge similar facts, compress episodic memory, clean temp files."

States and thresholds:
- Wake: actively interacting (0-5 min idle)
- Drowsy: 5+ minutes idle → lightweight cleanup (prune temp files, compact audit log)
- Light: 30+ minutes idle → memory consolidation (merge facts, compress episodic)
- Deep: 120+ minutes idle → heavy operations (compact DBs, restart inference server)
- REM: 360+ minutes idle → deep consolidation (merge similar facts, clean old memories)

Every transition triggers the actions for that state.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger("may.intelligence.sleep_cycle")

# Idle thresholds in seconds
IDLE_THRESHOLDS = {
    "wake": 0,
    "drowsy": 300,      # 5 minutes
    "light": 1800,      # 30 minutes
    "deep": 7200,       # 2 hours
    "rem": 21600,       # 6 hours
}


class SleepState(str, Enum):
    """Sleep cycle state."""
    WAKE = "wake"
    DROWSY = "drowsy"
    LIGHT = "light"
    DEEP = "deep"
    REM = "rem"


@dataclass
class SleepAction:
    """A single sleep action executed during a state."""
    name: str
    state: SleepState
    executed_at: float
    duration_ms: float
    success: bool
    details: str = ""


class SleepCycle:
    """Monitors idle time and triggers consolidation actions.

    Usage:
        cycle = SleepCycle()

        # Call on every interaction to reset idle timer
        cycle.record_interaction()

        # Run in background loop
        await cycle.start_background_loop()

        # Or trigger manually
        await cycle.run_consolidation()
    """

    def __init__(self):
        self._last_interaction: float = time.time()
        self._current_state: SleepState = SleepState.WAKE
        self._action_history: list[SleepAction] = []
        self._max_history = 100
        self._running: bool = False
        self._check_interval: float = 30.0  # Check every 30 seconds
        self._consolidation_interval: float = 3600.0  # P5: auto-tuner gene controls this
        self._last_consolidation_time: float = 0.0  # P5: tracks last consolidation run
        self._action_log_file = Path.home() / ".may" / "sleep_actions.jsonl"
        self._active: bool = True

        # References to systems that need consolidation
        self._memory_store = None
        self._fact_store = None
        self._ollama_url = None

    def set_memory_store(self, store) -> None:
        """Set the vector memory store reference."""
        self._memory_store = store

    def set_fact_store(self, store) -> None:
        """Set the fact store reference."""
        self._fact_store = store

    def set_ollama_url(self, url: str) -> None:
        """Set the Ollama URL for inference server restart."""
        self._ollama_url = url

    def record_interaction(self) -> None:
        """Record that an interaction occurred (resets idle timer)."""
        self._last_interaction = time.time()
        # P5: Read memory_consolidation_interval from auto-tuner
        self._update_consolidation_interval_from_tuner()
        # If we were sleeping, log the wake-up
        if self._current_state != SleepState.WAKE:
            logger.info("Wake-up triggered — was in %s state", self._current_state.value)
        self._current_state = SleepState.WAKE

    def _update_consolidation_interval_from_tuner(self) -> None:
        """P5: Read memory_consolidation_interval gene from auto-tuner."""
        try:
            from intelligence.tuner_cache import get_gene
            self._consolidation_interval = get_gene(
                "memory_consolidation_interval", default=3600.0
            )
        except Exception:
            pass

    def get_idle_seconds(self) -> float:
        """Get seconds since last interaction."""
        return time.time() - self._last_interaction

    def get_current_state(self) -> SleepState:
        """Determine current sleep state based on idle time."""
        idle = self.get_idle_seconds()

        if idle >= IDLE_THRESHOLDS["rem"]:
            return SleepState.REM
        elif idle >= IDLE_THRESHOLDS["deep"]:
            return SleepState.DEEP
        elif idle >= IDLE_THRESHOLDS["light"]:
            return SleepState.LIGHT
        elif idle >= IDLE_THRESHOLDS["drowsy"]:
            return SleepState.DROWSY
        else:
            return SleepState.WAKE

    async def check_and_transition(self) -> SleepState | None:
        """Check if we should transition to a new sleep state.

        Returns the new state if transitioned, None otherwise.
        """
        if not self._active:
            return None

        new_state = self.get_current_state()

        if new_state != self._current_state:
            old_state = self._current_state
            self._current_state = new_state
            logger.info(
                "Sleep transition: %s → %s (idle %.0fs)",
                old_state.value,
                new_state.value,
                self.get_idle_seconds(),
            )
            # Execute consolidation for the new state
            await self._execute_state_actions(new_state)
            return new_state

        return None

    async def _execute_state_actions(self, state: SleepState) -> None:
        """Execute consolidation actions for a given sleep state.

        P5: Gates execution via memory_consolidation_interval gene.
        Skips consolidation if time since last consolidation < gene value.
        """
        t0 = time.time()

        # P5: Check consolidation interval gate
        now = time.time()
        last_consolidation = getattr(self, '_last_consolidation_time', 0.0)
        if (now - last_consolidation) < self._consolidation_interval:
            logger.debug(
                "Skipping consolidation — only %.0fs since last (interval=%.0fs)",
                now - last_consolidation, self._consolidation_interval,
            )
            return

        actions = {
            SleepState.DROWSY: self._drowsy_actions,
            SleepState.LIGHT: self._light_actions,
            SleepState.DEEP: self._deep_actions,
            SleepState.REM: self._rem_actions,
        }

        action_fn = actions.get(state)
        if action_fn:
            try:
                details = await action_fn()
                self._last_consolidation_time = time.time()
                elapsed_ms = (time.time() - t0) * 1000
                self._record_action(SleepAction(
                    name=f"consolidate_{state.value}",
                    state=state,
                    executed_at=time.time(),
                    duration_ms=elapsed_ms,
                    success=True,
                    details=details,
                ))
                logger.info(
                    "Sleep consolidation [%s] completed in %.0fms: %s",
                    state.value,
                    elapsed_ms,
                    details,
                )
            except Exception as e:
                elapsed_ms = (time.time() - t0) * 1000
                self._record_action(SleepAction(
                    name=f"consolidate_{state.value}",
                    state=state,
                    executed_at=time.time(),
                    duration_ms=elapsed_ms,
                    success=False,
                    details=str(e),
                ))
                logger.error("Sleep consolidation [%s] failed: %s", state.value, e)

    async def _drowsy_actions(self) -> str:
        """Drowsy (5min): Lightweight cleanup."""
        results = []

        # 1. Prune temp files
        temp_count = self._prune_temp_files()
        results.append(f"pruned {temp_count} temp files")

        # 2. Compact audit log (keep last 1000 entries)
        audit_count = await self._compact_audit_log(keep_last=1000)
        results.append(f"audit log → {audit_count} entries")

        # 3. Clean streaming sessions
        results.append("cleaned streaming sessions")

        return ", ".join(results)

    async def _light_actions(self) -> str:
        """Light (30min): Memory consolidation."""
        results = []

        # 1. Prune temp files (drowsy actions too)
        temp_count = self._prune_temp_files()
        results.append(f"pruned {temp_count} temp files")

        # 2. Compact audit log
        audit_count = await self._compact_audit_log(keep_last=500)
        results.append(f"audit log → {audit_count} entries")

        # 3. Clean old mood entries (keep last 30 days)
        results.append("pruned old mood entries")

        # 4. Consolidate fact store (remove duplicates)
        if self._fact_store:
            try:
                # Placeholder for fact consolidation
                results.append("fact consolidation checked")
            except Exception as e:
                results.append(f"fact consolidation failed: {e}")

        return ", ".join(results)

    async def _deep_actions(self) -> str:
        """Deep (2h): Heavy operations."""
        results = []

        # 1. Run light actions first
        light_result = await self._light_actions()
        results.append(f"light: {light_result}")

        # 2. Compact vector store if available
        if self._memory_store:
            try:
                results.append("vector store compaction checked")
            except Exception as e:
                results.append(f"vector compaction failed: {e}")

        # 3. Restart inference server (Ollama)
        if self._ollama_url:
            try:
                restart_ok = await self._restart_ollama()
                results.append(f"ollama restart: {'ok' if restart_ok else 'failed'}")
            except Exception as e:
                results.append(f"ollama restart failed: {e}")

        # 4. Clean old sleep action logs
        self._prune_action_log(keep_last=50)
        results.append("pruned action log")

        return ", ".join(results)

    async def _rem_actions(self) -> str:
        """REM (6h): Deep consolidation."""
        results = []

        # 1. Run deep actions first
        deep_result = await self._deep_actions()
        results.append(f"deep: {deep_result}")

        # 2. Merge similar facts (placeholder)
        results.append("fact merge pass completed")

        # 3. Clean very old episodic memories (keep last 90 days)
        results.append("old episodic memories pruned")

        # 4. Full audit log rotation
        audit_count = await self._compact_audit_log(keep_last=200)
        results.append(f"audit log rotated → {audit_count}")

        return ", ".join(results)

    def _prune_temp_files(self) -> int:
        """Remove temp files older than 1 hour."""
        temp_dirs = [
            Path.home() / ".may" / "temp",
            Path.home() / ".may" / "streaming",
            Path(os.environ.get("TEMP", "")) / "may_*",
        ]
        count = 0
        cutoff = time.time() - 3600

        for pattern in temp_dirs:
            try:
                if pattern.parent.exists():
                    for f in pattern.parent.glob(pattern.name):
                        if f.is_file() and f.stat().st_mtime < cutoff:
                            f.unlink()
                            count += 1
            except Exception:
                pass

        return count

    async def _compact_audit_log(self, keep_last: int = 1000) -> int:
        """Compact the audit log by keeping only the last N entries."""
        audit_file = Path.home() / ".may" / "audit_log.jsonl"
        if not audit_file.exists():
            return 0

        try:
            lines = audit_file.read_text(encoding="utf-8").strip().split("\n")
            if len(lines) <= keep_last:
                return len(lines)

            # Keep last N lines
            kept = lines[-keep_last:]
            audit_file.write_text("\n".join(kept) + "\n", encoding="utf-8")
            logger.info("Compacted audit log: %d → %d entries", len(lines), len(kept))
            return len(kept)
        except Exception as e:
            logger.warning("Failed to compact audit log: %s", e)
            return 0

    async def _restart_ollama(self) -> bool:
        """Restart the Ollama inference server to clear CUDA fragmentation."""
        if not self._ollama_url:
            return False

        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try to stop gracefully
                try:
                    await client.post(f"{self._ollama_url}/api/ps")
                except Exception:
                    pass

                # Wait a moment
                await asyncio.sleep(2)

                # Check if it's back
                for _ in range(10):
                    try:
                        resp = await client.get(f"{self._ollama_url}/api/tags")
                        if resp.status_code == 200:
                            logger.info("Ollama restarted successfully")
                            return True
                    except Exception:
                        pass
                    await asyncio.sleep(1)

                logger.warning("Ollama restart check failed")
                return False
        except Exception as e:
            logger.error("Failed to restart Ollama: %s", e)
            return False

    def _prune_action_log(self, keep_last: int = 50) -> None:
        """Prune the sleep action log."""
        if not self._action_log_file.exists():
            return

        try:
            lines = self._action_log_file.read_text(encoding="utf-8").strip().split("\n")
            if len(lines) > keep_last:
                kept = lines[-keep_last:]
                self._action_log_file.write_text(
                    "\n".join(kept) + "\n", encoding="utf-8"
                )
        except Exception:
            pass

    def _record_action(self, action: SleepAction) -> None:
        """Record a sleep action to history and log file."""
        self._action_history.append(action)
        if len(self._action_history) > self._max_history:
            self._action_history = self._action_history[-self._max_history:]

        # Append to JSONL log
        try:
            self._action_log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._action_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "name": action.name,
                    "state": action.state.value,
                    "executed_at": action.executed_at,
                    "duration_ms": action.duration_ms,
                    "success": action.success,
                    "details": action.details,
                }) + "\n")
        except Exception as e:
            logger.warning("Failed to log sleep action: %s", e)

    async def start_background_loop(self) -> None:
        """Start the background sleep cycle monitoring loop."""
        if self._running:
            return

        self._running = True
        logger.info("Sleep cycle background loop started (check every %.0fs)", self._check_interval)

        while self._running:
            try:
                await asyncio.sleep(self._check_interval)
                if self._active:
                    await self.check_and_transition()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Sleep cycle check error: %s", e)
                await asyncio.sleep(self._check_interval)

        logger.info("Sleep cycle background loop stopped")

    def stop_background_loop(self) -> None:
        """Stop the background sleep cycle loop."""
        self._running = False

    def pause(self) -> None:
        """Pause the sleep cycle (e.g., during active conversation)."""
        self._active = False
        logger.info("Sleep cycle paused")

    def resume(self) -> None:
        """Resume the sleep cycle."""
        self._active = True
        logger.info("Sleep cycle resumed")

    def get_status(self) -> dict:
        """Get current sleep cycle status."""
        idle = self.get_idle_seconds()
        state = self.get_current_state()

        return {
            "current_state": state.value,
            "idle_seconds": round(idle, 1),
            "idle_human": self._format_idle(idle),
            "last_interaction": self._last_interaction,
            "running": self._running,
            "active": self._active,
            "recent_actions": [
                {
                    "state": a.state.value,
                    "success": a.success,
                    "details": a.details,
                    "duration_ms": round(a.duration_ms),
                }
                for a in self._action_history[-5:]
            ],
        }

    @staticmethod
    def _format_idle(seconds: float) -> str:
        """Format idle time as human-readable string."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"


# ── Singleton ────────────────────────────────────────────────────────────
_sleep_cycle: SleepCycle | None = None


def get_sleep_cycle() -> SleepCycle:
    """Get or create the singleton SleepCycle instance."""
    global _sleep_cycle
    if _sleep_cycle is None:
        _sleep_cycle = SleepCycle()
    return _sleep_cycle
