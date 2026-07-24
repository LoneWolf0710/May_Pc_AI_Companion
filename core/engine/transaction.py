"""Transaction Engine — atomic multi-step operations with rollback.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 13:

For multi-step operations that must succeed completely or
roll back completely. If any step fails, all previous steps
are undone in reverse order.

Example:
  tx = Transaction("file_reorganize")
  tx.add(Step("create_dirs", create_dirs_fn, rollback_delete_dirs, params))
  tx.add(Step("copy_files", copy_files_fn, rollback_delete_copies, params))
  success, message = await tx.execute()
  # If copy_files fails → copies deleted → dirs deleted → original state restored
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Any, Awaitable

logger = logging.getLogger("may.core.transaction")


# ── Type Aliases ─────────────────────────────────────────────────────────────

ActionFn = Callable[[dict[str, Any]], Awaitable[Any]]
RollbackFn = Callable[[dict[str, Any], Any], Awaitable[None]]


# ── Step ─────────────────────────────────────────────────────────────────────

@dataclass
class Step:
    """A single step in a transaction.

    Attributes:
        name:     Human-readable step name (for logging).
        action:   Async function to execute this step.
        rollback: Async function to undo this step. Takes (params, result).
        params:   Parameters for the action.
    """
    name:     str
    action:   ActionFn
    rollback: RollbackFn
    params:   dict[str, Any] = field(default_factory=dict)


# ── Transaction ──────────────────────────────────────────────────────────────

class Transaction:
    """Executes a series of steps atomically — all succeed or all roll back.

    Usage:
        tx = Transaction("file_reorganize")

        tx.add(Step(
            name="create_dirs",
            action=create_directories,
            rollback=delete_directories,
            params={"dirs": ["C:\\New\\A", "C:\\New\\B"]},
        ))

        tx.add(Step(
            name="copy_files",
            action=copy_all_files,
            rollback=delete_copied_files,
            params={"source": "C:\\Old\\", "dest": "C:\\New\\"},
        ))

        tx.add(Step(
            name="verify_copies",
            action=verify_checksums,
            rollback=delete_copied_files,
            params={"files": [...]},
        ))

        success, message = await tx.execute()
        # If verify_copies fails:
        #   → delete_copied_files (rollback step 2)
        #   → delete_directories (rollback step 1)
        #   → Original state restored
    """

    def __init__(self, name: str):
        self.name = name
        self.steps: list[Step] = []
        self._done: list[tuple[Step, Any]] = []  # (step, result) for rollback

    def add(self, step: Step) -> Transaction:
        """Add a step to the transaction. Returns self for chaining."""
        self.steps.append(step)
        return self

    async def execute(self) -> tuple[bool, str]:
        """Execute all steps in order.

        If any step fails, roll back all completed steps in reverse order.

        Returns:
            Tuple of (success, message).
        """
        logger.info(
            "Transaction '%s' starting with %d steps",
            self.name, len(self.steps),
        )

        for i, step in enumerate(self.steps):
            logger.info(
                "Transaction '%s' — step %d/%d: %s",
                self.name, i + 1, len(self.steps), step.name,
            )

            try:
                result = await step.action(step.params)
                self._done.append((step, result))
                logger.info(
                    "Transaction '%s' — step %s succeeded",
                    self.name, step.name,
                )

            except Exception as e:
                logger.error(
                    "Transaction '%s' — step %s failed: %s",
                    self.name, step.name, e,
                )
                # Roll back all completed steps
                await self._rollback()
                return False, f"Failed at step [{step.name}]: {type(e).__name__}: {e}"

        logger.info(
            "Transaction '%s' — all %d steps completed successfully",
            self.name, len(self.steps),
        )
        return True, f"All {len(self.steps)} steps completed successfully"

    async def _rollback(self):
        """Roll back all completed steps in reverse order."""
        if not self._done:
            logger.info("Transaction '%s' — nothing to roll back", self.name)
            return

        logger.info(
            "Transaction '%s' — rolling back %d completed steps",
            self.name, len(self._done),
        )

        # Reverse order: undo most recent first
        for step, result in reversed(self._done):
            try:
                await step.rollback(step.params, result)
                logger.info(
                    "Transaction '%s' — rollback of '%s' succeeded",
                    self.name, step.name,
                )
            except Exception as e:
                # Log but continue rolling back — don't let one failure stop the rest
                logger.error(
                    "Transaction '%s' — rollback of '%s' failed: %s",
                    self.name, step.name, e,
                )

        self._done.clear()

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def completed_count(self) -> int:
        return len(self._done)

    def __repr__(self) -> str:
        return (
            f"Transaction('{self.name}', "
            f"steps={self.step_count}, completed={self.completed_count})"
        )
