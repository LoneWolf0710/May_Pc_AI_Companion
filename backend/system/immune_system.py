"""Immune System — Adaptive Action Verification.

Per MAY_FINAL_ARCHITECTURE.md Part 5 (Immune System):

    class ImmuneSystem:
        async def verify_action(self, action) -> Verification:
            risk_tier = self._classify_risk(action)
            # CRITICAL always requires confirmation — no exceptions
            # DESTRUCTIVE requires confirmation outside TAKEOVER mode
            # Behavioral anomaly check

This module combines:
1. Risk tier classification (from risk_classifier.py)
2. Behavioral profile anomaly scoring (from behavioral_profile.py)
3. Control mode awareness (from control_modes.py)
4. OWASP mapping for documentation (from owasp_mapping.py)
5. Endocrine system emotional context (from endocrine.py)

Provides a single verify_action() entry point that the jarvis brain
calls before every tool execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("may.system.immune_system")


@dataclass
class Verification:
    """Result of an action verification check."""
    allowed: bool
    needs_confirmation: bool = False
    reason: str = ""
    risk_tier: str = "safe"
    behavioral_score: float = 1.0
    emotional_context: str = ""
    owasp_categories: list[dict] | None = None


class ImmuneSystem:
    """Adaptive action verification combining risk tiers, behavioral profiles, control modes, and emotional context.

    Architecture spec (Part 5):
    - CRITICAL always requires confirmation — no exceptions
    - DESTRUCTIVE requires confirmation outside TAKEOVER mode
    - Behavioral anomaly check with adaptive threshold
    - OWASP mapping for each action
    - Endocrine emotional context modulates caution levels
    """

    def __init__(self):
        self._behavioral_profile = None
        self._control_modes = None
        self._endocrine_system = None
        self._threshold = 0.3  # Below this score = anomalous

    def set_behavioral_profile(self, profile):
        """Register the behavioral profile for anomaly detection."""
        self._behavioral_profile = profile

    def set_control_modes(self, modes):
        """Register control modes for mode-aware verification."""
        self._control_modes = modes

    def set_endocrine_system(self, endocrine):
        """Register the endocrine system for emotional context in verification."""
        self._endocrine_system = endocrine

    def set_threshold(self, threshold: float):
        """Set the behavioral anomaly threshold (0.0 - 1.0)."""
        self._threshold = max(0.0, min(1.0, threshold))

    # Low-risk input actions that should NEVER be blocked by emotional context
    # or behavioral anomaly detection. These are trivially reversible.
    _EXEMPT_TOOLS = frozenset({
        "type_text", "send_keys", "hotkey", "type_text_fast",
        "clipboard_set", "clipboard_paste", "clipboard_copy", "clipboard_get",
        "press_key", "release_key", "tap_key", "hold_key",
        "mouse_move", "left_click", "right_click", "double_click",
        "scroll", "scroll_up", "scroll_down", "middle_click",
        "drag_and_drop", "get_key_state", "get_cursor_position",
        "set_volume", "volume_up", "volume_down", "set_mute",
        "set_brightness", "focus_window", "minimize_window", "maximize_window",
    })

    def _get_emotional_context(self, risk_tier: str, tool_name: str = "") -> tuple[bool, str]:
        """Read hormone levels and return (should_confirm, reason) for emotional risk modulation.

        Emotional rules (from endocrine.py hormone levels):
        - High cortisol (>0.6): Stress → be more conservative. DESTRUCTIVE actions
          require confirmation. MODERATE actions are exempted for low-risk input tools
          (type_text, send_keys, clipboard, etc.) since these are trivially reversible.
        - High adrenaline (>0.7): Alertness → user may be rushing. Add a caution
          note but don't block (adrenaline alone isn't enough to override).
        - Low serotonin (<0.3) + high cortisol (>0.5): Low well-being + stress
          → protective mode. DESTRUCTIVE actions always need confirmation even
          in automation mode.
        - High dopamine (>0.7): Satisfaction → user is in a productive flow.
          Slightly relax — allow MODERATE actions freely.
        """
        if self._endocrine_system is None:
            return False, ""

        # Exempt low-risk input actions from emotional blocking entirely.
        # Typing text, pressing keys, clicking are trivially reversible.
        if tool_name in self._EXEMPT_TOOLS:
            return False, ""

        cortisol = self._endocrine_system.get_hormone("cortisol")
        dopamine = self._endocrine_system.get_hormone("dopamine")
        serotonin = self._endocrine_system.get_hormone("serotonin")
        adrenaline = self._endocrine_system.get_hormone("adrenaline")

        # Rule 1: Protective mode — low well-being + stress → block DESTRUCTIVE even in automation
        if serotonin < 0.3 and cortisol > 0.5:
            if risk_tier in ("DESTRUCTIVE", "CRITICAL"):
                return True, f"Protective mode: low well-being (serotonin={serotonin:.2f}) + stress (cortisol={cortisol:.2f}) — need confirmation"

        # Rule 2: High stress → conservative for DESTRUCTIVE actions only
        # MODERATE actions (write_file, set_volume, etc.) are trivially reversible
        # and should not be blocked by emotional state — only DESTRUCTIVE needs confirmation
        if cortisol > 0.6 and risk_tier == "DESTRUCTIVE":
            return True, f"Stress elevated (cortisol={cortisol:.2f}) — recommending confirmation for {risk_tier} action"

        # Rule 3: High adrenaline → user may be rushing — add caution for DESTRUCTIVE
        if adrenaline > 0.7 and risk_tier == "DESTRUCTIVE":
            return True, f"High alertness (adrenaline={adrenaline:.2f}) — user may be rushing, recommending confirmation"

        # Rule 4: High dopamine → satisfaction/flow — relax for MODERATE
        # (This doesn't trigger confirmation; it's noted in context for downstream use)
        # No action needed here — the Verification.emotional_context field carries the info.

        return False, ""

    def _build_emotional_context_string(self) -> str:
        """Build a concise emotional context string for the Verification result."""
        if self._endocrine_system is None:
            return ""

        state = self._endocrine_system.get_emotional_state()
        if state == "neutral":
            return ""
        cortisol = self._endocrine_system.get_hormone("cortisol")
        dopamine = self._endocrine_system.get_hormone("dopamine")
        parts = [f"emotional_state={state}"]
        if cortisol > 0.5:
            parts.append(f"stress={cortisol:.2f}")
        if dopamine > 0.6:
            parts.append(f"satisfaction={dopamine:.2f}")
        return " ".join(parts)

    async def verify_action(
        self,
        tool_name: str,
        params: dict | None = None,
        control_mode: str | None = None,
    ) -> Verification:
        """Verify whether a tool action should be allowed.

        This is the main entry point called by jarvis.py before every tool execution.

        Args:
            tool_name: The tool/action name
            params: Optional tool parameters
            control_mode: Override control mode (else reads from ControlModes)

        Returns:
            Verification with allowed/needs_confirmation/reason
        """
        # 1. Classify risk tier
        from system.risk_classifier import classify_action, RiskTier
        risk_tier = classify_action(tool_name, params)

        # 2. Get control mode
        if control_mode is None and self._control_modes is not None:
            try:
                control_mode = self._control_modes.get_status().get("active_mode", "normal")
            except Exception:
                control_mode = "normal"
        control_mode = control_mode or "normal"

        # 3. CRITICAL always requires confirmation — no exceptions
        if risk_tier == RiskTier.CRITICAL:
            owasp = self._get_owasp_categories(risk_tier)
            return Verification(
                allowed=False,
                needs_confirmation=True,
                reason="CRITICAL action requires explicit confirmation regardless of mode",
                risk_tier=risk_tier,
                behavioral_score=0.0,
                emotional_context=self._build_emotional_context_string(),
                owasp_categories=owasp,
            )

        # 4. DESTRUCTIVE requires confirmation outside automation/takeover modes
        if risk_tier == RiskTier.DESTRUCTIVE:
            if control_mode not in ("automation", "takeover"):
                owasp = self._get_owasp_categories(risk_tier)
                return Verification(
                    allowed=False,
                    needs_confirmation=True,
                    reason=f"DESTRUCTIVE action requires confirmation in {control_mode} mode",
                    risk_tier=risk_tier,
                    behavioral_score=0.0,
                    emotional_context=self._build_emotional_context_string(),
                    owasp_categories=owasp,
                )

        # 5. Behavioral anomaly check (for MODERATE and above)
        # Exempt low-risk input tools — trivially reversible, should never be blocked.
        behavioral_score = 1.0
        if self._behavioral_profile is not None and risk_tier in (RiskTier.MODERATE, RiskTier.DESTRUCTIVE) and tool_name not in self._EXEMPT_TOOLS:
            try:
                behavioral_score = self._behavioral_profile.score_action(tool_name, params)
                if behavioral_score < self._threshold:
                    owasp = self._get_owasp_categories(risk_tier)
                    return Verification(
                        allowed=False,
                        needs_confirmation=True,
                        reason=f"Anomalous behavior detected (score: {behavioral_score:.2f}, threshold: {self._threshold:.2f})",
                        risk_tier=risk_tier,
                        behavioral_score=behavioral_score,
                        emotional_context=self._build_emotional_context_string(),
                        owasp_categories=owasp,
                    )
            except Exception as e:
                logger.debug("Behavioral scoring failed: %s", e)

        # 6. Endocrine emotional context check (for MODERATE+ actions)
        # This runs AFTER behavioral check but BEFORE final "allowed" result.
        # It can upgrade a pass to confirmation-recommended based on stress/adrenaline.
        # Low-risk input tools (type_text, send_keys, etc.) are exempted.
        if risk_tier in ("MODERATE", "DESTRUCTIVE"):
            should_confirm, emotion_reason = self._get_emotional_context(risk_tier, tool_name)
            if should_confirm:
                owasp = self._get_owasp_categories(risk_tier)
                return Verification(
                    allowed=False,
                    needs_confirmation=True,
                    reason=emotion_reason,
                    risk_tier=risk_tier,
                    behavioral_score=behavioral_score,
                    emotional_context=self._build_emotional_context_string(),
                    owasp_categories=owasp,
                )

        # 7. Record action in behavioral profile (best-effort)
        if self._behavioral_profile is not None:
            try:
                self._behavioral_profile.record_action(tool_name, params)
            except Exception:
                pass

        # 8. All checks passed — action is allowed
        owasp = self._get_owasp_categories(risk_tier)
        return Verification(
            allowed=True,
            risk_tier=risk_tier,
            behavioral_score=behavioral_score,
            emotional_context=self._build_emotional_context_string(),
            owasp_categories=owasp,
        )

    def _get_owasp_categories(self, risk_tier: str) -> list[dict]:
        """Get relevant OWASP categories for a risk tier."""
        try:
            from system.owasp_mapping import check_action_owasp
            return check_action_owasp("action", risk_tier)
        except Exception:
            return []

    def get_status(self) -> dict:
        """Get immune system status."""
        status = {
            "threshold": self._threshold,
            "behavioral_profile": self._behavioral_profile is not None,
            "control_modes": self._control_modes is not None,
            "endocrine_system": self._endocrine_system is not None,
        }
        if self._endocrine_system is not None:
            try:
                status["emotional_state"] = self._endocrine_system.get_emotional_state()
            except Exception:
                status["emotional_state"] = "unknown"
        return status
