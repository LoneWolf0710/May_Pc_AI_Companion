"""Ghost Mode — autonomous overnight task execution.

Per MAY_V3_ARCHITECTURE.md Section 5.9:

When the user says "while I sleep, do X", May queues the task.
When the user is idle for 5+ minutes, May executes queued tasks.
On wake (first mouse movement), May reports what was completed.

Usage:
    ghost = GhostMode()
    ghost.queue_task("Research Q3 earnings", steps=[
        {"tool": "web_search", "args": {"query": "Apple Q3 2025 earnings"}},
        {"tool": "write_file", "args": {"path": "report.md", "content": "..."}},
    ])
    ghost.start()  # starts the idle detection loop
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger("may.intelligence.ghost_mode")

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".may", "ghost_mode.json")


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class GhostTask:
    """A task queued for autonomous execution."""
    id: str
    description: str
    steps: list[dict] = field(default_factory=list)
    created_at: float = 0
    started_at: float = 0
    completed_at: float = 0
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    error: str = ""
    priority: int = 0  # Higher = execute first

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "steps": self.steps,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "priority": self.priority,
            "created_display": datetime.fromtimestamp(self.created_at).strftime("%H:%M") if self.created_at else "",
        }


# ── Ghost Mode ──────────────────────────────────────────────────────────────

class GhostMode:
    """Autonomous overnight task execution.

    Runs in the background. When user is idle for 5+ minutes,
    executes queued tasks sequentially. Notifies user on completion.

    Features:
    - Task queue with priority ordering
    - Idle detection (5 min threshold)
    - Completion notification (toast + stored result)
    - Task cancellation
    - Config persistence across restarts
    """

    IDLE_THRESHOLD_SEC = 300  # 5 minutes of inactivity
    CHECK_INTERVAL_SEC = 30   # Check every 30 seconds
    MAX_CONCURRENT = 1        # Execute one task at a time

    def __init__(self):
        self._queue: list[GhostTask] = []
        self._completed: list[GhostTask] = []
        self._active = False
        self._loop_task: asyncio.Task | None = None
        self._last_input_time: float = time.time()
        self._executor: Callable | None = None  # Set by main.py
        self._task_counter = 0

        # Load persisted state
        self._load_state()

    def set_executor(self, executor: Callable):
        """Set the tool executor function (from jarvis.py execute_tool)."""
        self._executor = executor

    def set_jarvis_chat(self, chat_fn: Callable):
        """H6 FIX: Set the jarvis_chat function (avoids fragile import path)."""
        self._jarvis_chat = chat_fn

    @property
    def enabled(self) -> bool:
        return self._active

    def start(self):
        """Start the ghost mode idle detection loop."""
        if self._active:
            return
        self._active = True
        self._last_input_time = time.time()
        self._loop_task = asyncio.create_task(self._ghost_loop())
        logger.info("Ghost mode started (idle threshold: %ds)", self.IDLE_THRESHOLD_SEC)

    async def stop(self):
        """Stop the ghost mode loop."""
        self._active = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
        logger.info("Ghost mode stopped")

    def queue_task(
        self,
        description: str,
        steps: list[dict] | None = None,
        priority: int = 0,
    ) -> dict:
        """Add a task to the ghost queue.

        Args:
            description: What the task does (natural language).
            steps: Optional list of tool call steps [{"tool": "...", "args": {...}}].
            priority: Higher priority tasks execute first.

        Returns:
            Task info dict.
        """
        self._task_counter += 1
        task = GhostTask(
            id=f"ghost_{self._task_counter}",
            description=description,
            steps=steps or [],
            created_at=time.time(),
            priority=priority,
        )
        self._queue.append(task)
        # Sort by priority (descending)
        self._queue.sort(key=lambda t: t.priority, reverse=True)
        self._save_state()

        logger.info("Ghost task queued: %s (id=%s, queue=%d)",
                     description, task.id, len(self._queue))
        return task.to_dict()

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        for i, task in enumerate(self._queue):
            if task.id == task_id:
                task.status = TaskStatus.CANCELLED
                self._completed.append(self._queue.pop(i))
                self._save_state()
                logger.info("Ghost task cancelled: %s", task_id)
                return True
        return False

    def cancel_all(self) -> int:
        """Cancel all pending tasks."""
        count = len(self._queue)
        for task in self._queue:
            task.status = TaskStatus.CANCELLED
            self._completed.append(task)
        self._queue.clear()
        self._save_state()
        return count

    def record_input(self):
        """Record user input activity (call on each user message/input)."""
        self._last_input_time = time.time()

    def get_status(self) -> dict:
        """Get ghost mode status."""
        return {
            "active": self._active,
            "idle_threshold_sec": self.IDLE_THRESHOLD_SEC,
            "time_since_input_sec": round(time.time() - self._last_input_time, 1),
            "is_idle": self._is_user_idle(),
            "queue": [t.to_dict() for t in self._queue],
            "queue_count": len(self._queue),
            "completed": [t.to_dict() for t in self._completed[-10:]],  # Last 10
            "completed_count": len(self._completed),
        }

    def get_task(self, task_id: str) -> dict | None:
        """Get a specific task by ID."""
        for task in self._queue + self._completed:
            if task.id == task_id:
                return task.to_dict()
        return None

    def _is_user_idle(self) -> bool:
        """Check if user has been idle for more than threshold."""
        return (time.time() - self._last_input_time) > self.IDLE_THRESHOLD_SEC

    async def _ghost_loop(self):
        """Main loop — waits for user idle, then executes queued tasks."""
        while self._active:
            try:
                await asyncio.sleep(self.CHECK_INTERVAL_SEC)
                if not self._active:
                    break

                # Only execute when user is idle
                if not self._is_user_idle():
                    continue

                if not self._queue:
                    continue

                logger.info("User idle, executing %d ghost tasks...", len(self._queue))

                # Execute tasks one at a time
                while self._queue and self._active:
                    # Check if user came back
                    if not self._is_user_idle():
                        logger.info("User active again — pausing ghost tasks")
                        break

                    task = self._queue.pop(0)
                    task.status = TaskStatus.RUNNING
                    task.started_at = time.time()

                    try:
                        result = await self._execute_task(task)
                        task.result = result
                        task.status = TaskStatus.COMPLETED
                        logger.info("Ghost task completed: %s", task.description)
                    except Exception as e:
                        task.error = str(e)
                        task.status = TaskStatus.FAILED
                        logger.error("Ghost task failed: %s — %s", task.description, e)

                    task.completed_at = time.time()
                    self._completed.append(task)
                    self._save_state()

                # Notify user if tasks completed
                completed_count = sum(
                    1 for t in self._completed
                    if t.status == TaskStatus.COMPLETED
                    and t.completed_at > time.time() - 600  # Last 10 minutes
                )
                if completed_count > 0:
                    self._notify_completion(completed_count)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Ghost mode loop error: %s", e)
                await asyncio.sleep(10)

    async def _execute_task(self, task: GhostTask) -> str:
        """Execute a single ghost task.

        If steps are provided, executes them sequentially via the tool executor.
        Otherwise, sends the description to the LLM for autonomous execution.
        """
        if task.steps:
            # Execute pre-defined steps
            results = []
            for step in task.steps:
                tool_name = step.get("tool", "")
                tool_args = step.get("args", {})
                if not tool_name:
                    continue

                if self._executor:
                    try:
                        result = await self._executor(tool_name, tool_args)
                        results.append(f"✓ {tool_name}: {result[:200]}")
                    except Exception as e:
                        results.append(f"✗ {tool_name}: {str(e)[:200]}")
                else:
                    results.append(f"⚠ {tool_name}: executor not configured")

            return "\n".join(results)
        else:
            # Autonomous mode — send description to LLM
            return await self._autonomous_execute(task.description)

    async def _autonomous_execute(self, description: str) -> str:
        """Execute a task autonomously using the LLM brain."""
        try:
            # H6 FIX: Use injected function reference instead of fragile import
            jarvis_chat_fn = getattr(self, '_jarvis_chat', None)
            if jarvis_chat_fn is None:
                # Lazy fallback — import once, store for future use
                from llm.jarvis import jarvis_chat as _jc
                self._jarvis_chat = _jc
                jarvis_chat_fn = _jc

            result_parts = []
            # Create a ghost-mode prompt
            ghost_message = f"[GHOST MODE — Execute this task while user is away]\n\nTask: {description}\n\nExecute all necessary steps. Be thorough. Report what you did when finished."

            async for chunk in jarvis_chat_fn(
                message=ghost_message,
                history=[],
                provider="ollama",
                model="qwen3:4b",
            ):
                # Strip tool execution status lines from the result
                clean = chunk
                if chunk.startswith("\n\n🔧"):
                    continue  # Skip tool status markers
                result_parts.append(clean)

            raw = "".join(result_parts).strip()
            # Clean up any remaining tool JSON artifacts
            import re
            raw = re.sub(r'```json\s*\{[^}]*\}\s*```', '', raw).strip()
            return raw if raw else "Task completed (no output)"
        except Exception as e:
            return f"Autonomous execution failed: {str(e)}"

    def _notify_completion(self, count: int):
        """Send a notification that ghost tasks completed."""
        try:
            from system.notifications import send_toast
            send_toast(
                "Ghost Mode Complete~",
                f"{count} task(s) completed while you were away. Check your desktop!",
            )
        except Exception as e:
            logger.debug("Failed to send ghost completion notification: %s", e)

    def _save_state(self):
        """Persist ghost mode state to disk."""
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        try:
            data = {
                "queue": [t.to_dict() for t in self._queue],
                "completed_count": len(self._completed),
                "last_saved": time.time(),
            }
            with open(CONFIG_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug("Failed to save ghost state: %s", e)

    def _load_state(self):
        """Load persisted ghost mode state."""
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
            # Restore pending tasks and track max counter to avoid ID collisions
            max_counter = self._task_counter
            for t_data in data.get("queue", []):
                task = GhostTask(
                    id=t_data.get("id", f"ghost_{self._task_counter}"),
                    description=t_data.get("description", ""),
                    steps=t_data.get("steps", []),
                    created_at=t_data.get("created_at", 0),
                    priority=t_data.get("priority", 0),
                    status=TaskStatus.PENDING,
                )
                self._queue.append(task)
                # Extract counter from id (e.g. "ghost_5" → 5)
                try:
                    counter_val = int(task.id.split("_")[-1])
                    max_counter = max(max_counter, counter_val)
                except (ValueError, IndexError):
                    pass
            self._task_counter = max_counter
            if self._queue:
                logger.info("Loaded %d pending ghost tasks from disk", len(self._queue))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
