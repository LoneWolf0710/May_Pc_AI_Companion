"""Fallback Chain Executor — what gives the Control Core ~99% accuracy.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 12 & 15:

Every action has multiple methods to achieve the same result.
If Method 1 fails, try Method 2. If all methods fail, return
a full diagnostic with what each method tried.

Execution flow (per Section 15):
  [1] ROUTER: Map command → layer + action
  [2] PRE-FLIGHT CHECK: target exists? permission? safe?
  [3] EXECUTE METHOD 1 → Verify → Return
  [4] EXECUTE METHOD 2 → Verify → Return
  [5] EXECUTE METHOD 3 → Verify → Return
  [6] PRIVILEGE ESCALATION → Retry from Method 1
  [7] SCHEDULE / DEFER (MoveFileExW DELAY_UNTIL_REBOOT)
  [8] RETURN FULL DIAGNOSTIC
"""

from __future__ import annotations

import asyncio
import time
import logging
from typing import Callable, Any, Awaitable

logger = logging.getLogger("may.core.fallback")


# ── Type Aliases ─────────────────────────────────────────────────────────────

# A method in a fallback chain: async function that takes params and returns a result
FallbackMethod = Callable[[dict[str, Any]], Awaitable[Any]]

# A verifier: async function that takes (params, result) and returns bool
Verifier = Callable[[dict[str, Any], Any], Awaitable[bool]]

# A pre-flight check: async function that takes params and returns None (ok) or error string
PreflightCheck = Callable[[dict[str, Any]], Awaitable[str | None]]

# An escalation function: async function that escalates privileges, returns True if ok
EscalationFn = Callable[[], Awaitable[bool]]

# A deferred/schedule function: async function for last-resort execution (e.g. MoveFileExW)
DeferredFn = Callable[[dict[str, Any]], Awaitable[Any]]


# ── Fallback Chain ───────────────────────────────────────────────────────────

class FallbackChain:
    """Executes a chain of fallback methods until one succeeds and verifies.

    Follows the accuracy guarantee flow from Section 15:
      1. Pre-flight checks (target exists, permission, safety)
      2. Try each method with verification
      3. Privilege escalation if all methods fail
      4. Deferred/scheduled execution as last resort
      5. Full diagnostic return

    Usage:
        chain = FallbackChain()
        success, result, method, error = await chain.execute(
            action="delete_file",
            params={"path": "/some/file.txt"},
            methods=[method_1, method_2, method_3],
            verifier=verify_file_deleted,
        )
    """

    async def execute(
        self,
        action: str,
        params: dict[str, Any],
        methods: list[FallbackMethod],
        verifier: Verifier | None = None,
        preflight_fn: PreflightCheck | None = None,
        escalation_fn: EscalationFn | None = None,
        defer_fn: DeferredFn | None = None,
        method_timeout: float = 5.0,
    ) -> tuple[bool, Any, str, str]:
        """Execute the fallback chain with full Section 15 accuracy guarantee.

        Args:
            action:       Human-readable action name (for logging).
            params:       Parameters to pass to each method.
            methods:      Ordered list of methods to try.
            verifier:     Optional post-execution verification function.
            preflight_fn: Optional pre-flight check function. Returns None if ok,
                          or an error string if the check fails.
            escalation_fn: Optional privilege escalation function. Called when all
                           methods fail. Returns True if escalation succeeded.
            defer_fn:     Optional deferred/scheduled execution function. Called as
                          a last resort after escalation fails.
            method_timeout: Timeout in seconds for each individual method.

        Returns:
            Tuple of (success, result, method_used, error_message).
        """
        errors: list[str] = []

        # ── [2] PRE-FLIGHT CHECK ──────────────────────────────────────────
        if preflight_fn:
            try:
                preflight_error = await preflight_fn(params)
                if preflight_error:
                    logger.warning("Pre-flight check failed for %s: %s", action, preflight_error)
                    return False, None, "none", f"Pre-flight failed: {preflight_error}"
            except Exception as e:
                logger.warning("Pre-flight check raised for %s: %s — continuing anyway", action, e)

        # ── [3-5] EXECUTE METHODS ─────────────────────────────────────────
        success, result, method, error = await self._try_methods(
            action, params, methods, verifier, errors, method_timeout,
        )
        if success:
            return success, result, method, error

        # ── [6] PRIVILEGE ESCALATION ──────────────────────────────────────
        if escalation_fn:
            logger.info(
                "All %d methods failed for %s — attempting privilege escalation",
                len(methods), action,
            )
            try:
                escalated = await escalation_fn()
            except Exception as e:
                logger.error("Privilege escalation failed for %s: %s", action, e)
                escalated = False

            if escalated:
                success, result, method, error = await self._try_methods(
                    action, params, methods, verifier, errors,
                )
                if success:
                    method = f"escalated_{method}"
                    return success, result, method, error

        # ── [7] DEFERRED / SCHEDULED EXECUTION ────────────────────────────
        if defer_fn:
            logger.info(
                "Escalation failed for %s — attempting deferred execution",
                action,
            )
            try:
                result = await defer_fn(params)
                logger.info("Deferred execution scheduled for %s", action)
                return True, result, "method_deferred", ""
            except Exception as e:
                error_msg = f"deferred: {type(e).__name__}: {e}"
                errors.append(error_msg)
                logger.error("Deferred execution failed for %s: %s", action, e)

        # ── [8] FULL DIAGNOSTIC ───────────────────────────────────────────
        full_error = " | ".join(errors)
        logger.error(
            "Fallback chain exhausted for %s — all %d methods failed",
            action, len(methods),
        )
        return False, None, "none", full_error

    async def _try_methods(
        self,
        action: str,
        params: dict[str, Any],
        methods: list[FallbackMethod],
        verifier: Verifier | None,
        errors: list[str],
        method_timeout: float = 5.0,
    ) -> tuple[bool, Any, str, str]:
        """Try each method in order, verifying on success."""
        # Resolve verifier once before the loop
        if not verifier:
            try:
                from core.engine.verifier import get_verifier
                # Use rsplit to handle action names that may contain dots
                # e.g. "filesystem.delete_file" → ["filesystem", "delete_file"]
                layer_action = action.rsplit(".", 1)
                if len(layer_action) == 2:
                    verifier = get_verifier(layer_action[0], layer_action[1])
                else:
                    logger.debug("Cannot auto-resolve verifier for '%s' — no layer prefix found", action)
            except Exception as e:
                logger.debug("Verifier auto-resolution failed for '%s': %s", action, e)

        for i, method in enumerate(methods):
            method_name = f"method_{i + 1}_{method.__name__}"
            verified = False  # reset per method; only meaningful when a verifier runs
            try:
                t_start = time.monotonic()
                result = await asyncio.wait_for(method(params), timeout=method_timeout)
                t_end = time.monotonic()
                elapsed_ms = int((t_end - t_start) * 1000)

                logger.debug(
                    "Method %s executed for %s in %dms",
                    method_name, action, elapsed_ms,
                )

                # If the method itself reports an error, skip to next
                if isinstance(result, dict) and result.get("error"):
                    errors.append(f"{method_name}: {result['error']}")
                    continue

                if verifier:
                    # Settle time for OS to complete the action
                    await asyncio.sleep(0.3)
                    try:
                        verified = await verifier(params, result)
                    except Exception as ve:
                        logger.warning(
                            "Verifier raised exception for %s.%s: %s",
                            action, method_name, ve,
                        )
                        verified = False

                    if not verified:
                        error_msg = f"{method_name}: executed but verification failed"
                        errors.append(error_msg)
                        logger.warning(
                            "Verification failed for %s.%s — trying next method",
                            action, method_name,
                        )
                        continue

                # Success!
                logger.info(
                    "Fallback chain succeeded for %s: %s (verified=%s, %dms)",
                    action, method_name,
                    verified if verifier is not None else "n/a",
                    elapsed_ms,
                )
                return True, result, method_name, ""

            except asyncio.TimeoutError:
                error_msg = f"{method_name}: timeout after {method_timeout}s"
                errors.append(error_msg)
                logger.warning("Method %s timed out for %s after %ss", method_name, action, method_timeout)
                continue
            except Exception as e:
                error_msg = f"{method_name}: {type(e).__name__}: {e}"
                errors.append(error_msg)
                logger.warning(
                    "Method %s failed for %s: %s",
                    method_name, action, e,
                )
                continue

        return False, None, "none", " | ".join(errors)
