"""MemoryInjector — Rich context injection for every LLM prompt.

Architecture spec (Part 6):
    class MemoryInjector:
        async def build_context(self, user_message, screen_ctx) -> str:
            # 1. Semantic memory search
            # 2. User facts (name, preferences, habits)
            # 3. Recent conversation summaries
            # 4. Current screen context
            # 5. Emotional state
            # 6. Time context
            # 7. Shadow learner patterns

This module builds a context block that gets prepended to the system prompt,
giving May situational awareness across all 7 sources.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from memory.vector_store import VectorStore
    from memory.fact_store import FactStore
    from memory.skill_store import SkillStore

logger = logging.getLogger("may.memory.injector")


class MemoryInjector:
    """Builds rich context for every LLM call.

    Combines 7 data sources into a single context block:
    1. Semantic memory (past conversations via vector search)
    2. User facts (name, preferences, habits from SQLite)
    3. Recent conversations (last 3 summaries)
    4. Screen context (active app, visible text)
    5. Emotional state (from tone analyzer)
    6. Time context (day of week, time of day)
    7. Shadow learner patterns (repeated actions)
    8. Skills (learned procedures)

    The injected context gives May situational awareness so she truly
    "knows" the user and their environment.
    """

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        fact_store: FactStore | None = None,
        skill_store: SkillStore | None = None,
    ):
        self._vector_store = vector_store
        self._fact_store = fact_store
        self._skill_store = skill_store
        self._shadow_learner = None  # Set via set_shadow_learner()
        self._tone_analyzer = None   # Set via set_tone_analyzer()

    def set_shadow_learner(self, learner):
        """Register the shadow learner for pattern injection."""
        self._shadow_learner = learner

    def set_tone_analyzer(self, analyzer):
        """Register the tone analyzer for emotional state injection."""
        self._tone_analyzer = analyzer

    async def build_context(
        self,
        user_message: str,
        screen_ctx: dict[str, Any] | None = None,
        active_app: str = "",
    ) -> str:
        """Build a context block for injection into the LLM system prompt.

        Args:
            user_message: The user's current message
            screen_ctx: Optional screen context dict. Can be:
                - Simple dict with 'active_app', 'text_on_screen' keys
                - Tier 2 UIAccessibility dict with 'window_title', 'elements',
                  'visible_text', 'error_text', 'is_modal', etc.
            active_app: Name of the currently active application

        Returns:
            A formatted context string to prepend to the system prompt
        """
        sections = []

        # 1. Semantic memory search — relevant past conversations
        if self._vector_store:
            try:
                memories = await self._vector_store.search(user_message, n_results=3)
                if memories:
                    mem_lines = []
                    for m in memories:
                        summary = m.get("summary", "")[:200]
                        if summary:
                            mem_lines.append(f"  - {summary}")
                    if mem_lines:
                        sections.append(
                            "[CONVERSATION MEMORY]\nRelevant past conversations:\n"
                            + "\n".join(mem_lines)
                        )
            except Exception as e:
                logger.debug("Memory search failed: %s", e)

        # 2. User facts — name, preferences, habits
        if self._fact_store:
            try:
                facts = self._fact_store.get_all_facts()
                if facts:
                    fact_lines = []
                    for f in facts[:10]:  # Top 10 most relevant
                        key = f.get("key", "")
                        value = f.get("value", "")
                        if key and value:
                            # Skip auto-generated facts for cleaner context
                            if not key.startswith("auto_"):
                                fact_lines.append(f"  {key}: {value}")
                    if fact_lines:
                        sections.append(
                            "[USER PROFILE]\n"
                            + "\n".join(fact_lines)
                        )
            except Exception as e:
                logger.debug("Fact store read failed: %s", e)

        # 3. Recent conversation summaries
        if self._vector_store:
            try:
                recent = await self._vector_store.get_recent(3)
                if recent:
                    recent_lines = []
                    for r in recent:
                        summary = r.get("summary", "")[:150]
                        if summary:
                            recent_lines.append(f"  - {summary}")
                    if recent_lines:
                        sections.append(
                            "[RECENT CONVERSATIONS]\n"
                            + "\n".join(recent_lines)
                        )
            except Exception as e:
                logger.debug("Recent memory read failed: %s", e)

        # 4. Screen context — P4: Enhanced with Tier 2 UIAccessibility data
        _active = active_app or (screen_ctx or {}).get("active_app", "")
        _screen_text = (screen_ctx or {}).get("text_on_screen", "") or (screen_ctx or {}).get("visible_text", "")
        _window_title = (screen_ctx or {}).get("window_title", "")
        _error_text = (screen_ctx or {}).get("error_text", "")
        _is_modal = (screen_ctx or {}).get("is_modal", False)
        _element_count = (screen_ctx or {}).get("element_count", 0)
        _interactive_count = (screen_ctx or {}).get("interactive_count", 0)

        if _active or _window_title or _screen_text or _error_text:
            screen_lines = []
            if _window_title and _window_title != _active:
                screen_lines.append(f"Window: {_window_title}")
            if _active:
                screen_lines.append(f"Active app: {_active}")
            if _element_count:
                screen_lines.append(f"UI elements: {_element_count} ({_interactive_count} interactive)")
            if _error_text:
                screen_lines.append(f"Error detected: {_error_text}")
            if _is_modal:
                screen_lines.append("Modal dialog: visible")
            if _screen_text:
                # Cap at 400 chars for Tier 2 full text, 300 for legacy
                max_len = 400 if _element_count else 300
                screen_lines.append(f"Visible text: {_screen_text[:max_len]}")
            sections.append(
                "[SCREEN CONTEXT]\n" + "\n".join(screen_lines)
            )

        # 5. Emotional state
        if self._tone_analyzer:
            try:
                energy = self._tone_analyzer.get_conversation_energy()
                energy_label = "high" if energy > 0.7 else "low" if energy < 0.3 else "medium"
                sections.append(
                    f"[EMOTIONAL STATE]\nConversation energy: {energy_label} ({energy:.2f})"
                )
            except Exception:
                pass

        # 6. Time context
        now = datetime.now()
        day_name = now.strftime("%A")
        time_str = now.strftime("%I:%M %p")
        hour = now.hour
        if hour < 6:
            period = "late night"
        elif hour < 12:
            period = "morning"
        elif hour < 17:
            period = "afternoon"
        elif hour < 21:
            period = "evening"
        else:
            period = "night"
        sections.append(
            f"[TIME CONTEXT]\nCurrent time: {day_name}, {time_str} ({period})"
        )

        # 7. Shadow learner patterns
        if self._shadow_learner:
            try:
                patterns = self._shadow_learner.get_relevant_patterns(
                    active_app=_active, timestamp=time.time()
                )
                if patterns:
                    pattern_lines = [f"  - {p}" for p in patterns[:5]]
                    sections.append(
                        "[DETECTED PATTERNS]\n"
                        + "\n".join(pattern_lines)
                    )
            except Exception as e:
                logger.debug("Shadow learner pattern read failed: %s", e)

        # 8. Relevant skills
        if self._skill_store:
            try:
                skills = self._skill_store.find_relevant(user_message, top_k=2)
                if skills:
                    skill_lines = []
                    for s in skills:
                        steps_desc = " → ".join(
                            step.tool_name for step in s.steps
                        )
                        skill_lines.append(
                            f"  - {s.name}: {steps_desc} (used {s.use_count}x)"
                        )
                    if skill_lines:
                        sections.append(
                            "[LEARNED SKILLS]\n"
                            + "\n".join(skill_lines)
                        )
            except Exception as e:
                logger.debug("Skill store search failed: %s", e)

        if not sections:
            return ""

        return "\n\n".join(sections) + "\n\n---\n"

    def get_status(self) -> dict:
        """Get injector status."""
        return {
            "vector_store": self._vector_store is not None,
            "fact_store": self._fact_store is not None,
            "skill_store": self._skill_store is not None,
            "shadow_learner": self._shadow_learner is not None,
            "tone_analyzer": self._tone_analyzer is not None,
        }
