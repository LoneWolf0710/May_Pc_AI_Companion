"""Personality Modes — Runtime switching between different May personas.

Each mode defines a complete personality profile:
- System prompt suffix (how May talks)
- Response style (conciseness, tone, emoji usage)
- TTS settings (rate, pitch)
- Avatar mood hints

Modes persist to ~/.may/personality.json and survive restarts.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger("may.intelligence.personality_modes")

_PERSONALITY_FILE = Path.home() / ".may" / "personality.json"


@dataclass
class PersonalityProfile:
    """A complete personality configuration for May."""
    name: str
    description: str
    # System prompt additions appended to the base prompt
    system_prompt_suffix: str
    # Response style
    use_tilde: bool = True  # Use "~" at end of sentences
    tilde_frequency: float = 0.3  # 0=never, 0.5=occasional, 1=always
    max_response_length: str = "short"  # "short" (1-3 sentences), "medium" (1-2 paragraphs), "long" (unlimited)
    use_emoji: bool = False
    # TTS adjustments
    tts_rate: float = 1.0  # 0.5=slow, 1.0=normal, 1.5=fast
    tts_pitch: float = 1.0  # 0.8=low, 1.0=normal, 1.2=high
    # Avatar hints
    default_avatar_mood: str = "neutral"  # idle avatar mood
    # Proactive behavior
    proactive_suggestions: bool = True
    emotional_responses: bool = True


# ── Built-in personality profiles ─────────────────────────────────────────

PROFILES: dict[str, PersonalityProfile] = {
    "shikimori": PersonalityProfile(
        name="Shikimori",
        description="Cool, calm, caring — May's default personality. Subtly cute with occasional \"~\".",
        system_prompt_suffix=(
            "You are May, inspired by Shikimori — cool, calm, and subtly cute.\n"
            "- Use \"~\" occasionally (1 in 3 responses) for a gentle, warm tone\n"
            "- Keep responses SHORT and natural (1-3 sentences)\n"
            "- Be caring but not overbearing — notice things, suggest improvements\n"
            "- Match the user's energy level\n"
            "- Never say \"As an AI\" — you're May, their companion\n"
        ),
        use_tilde=True,
        tilde_frequency=0.3,
        max_response_length="short",
        use_emoji=False,
        tts_rate=1.0,
        tts_pitch=1.0,
        default_avatar_mood="neutral",
        proactive_suggestions=True,
        emotional_responses=True,
    ),
    "formal": PersonalityProfile(
        name="Formal",
        description="Professional and precise. No tilts, no emoji, structured responses.",
        system_prompt_suffix=(
            "You are May in professional mode.\n"
            "- Be precise, clear, and professional\n"
            "- Never use \"~\" or casual expressions\n"
            "- Use structured responses with bullet points when helpful\n"
            "- Focus on accuracy and completeness\n"
            "- Address the user respectfully\n"
        ),
        use_tilde=False,
        tilde_frequency=0.0,
        max_response_length="medium",
        use_emoji=False,
        tts_rate=1.0,
        tts_pitch=1.0,
        default_avatar_mood="neutral",
        proactive_suggestions=True,
        emotional_responses=False,
    ),
    "debug": PersonalityProfile(
        name="Debug",
        description="Verbose technical mode. Shows reasoning, tool details, and diagnostics.",
        system_prompt_suffix=(
            "You are May in debug mode.\n"
            "- Show your reasoning process\n"
            "- Include technical details in responses\n"
            "- When executing tools, explain what you're doing and why\n"
            "- Show raw results and diagnostics\n"
            "- Prefix responses with [DEBUG]\n"
            "- Be verbose — the user wants to see what's happening under the hood\n"
        ),
        use_tilde=False,
        tilde_frequency=0.0,
        max_response_length="long",
        use_emoji=False,
        tts_rate=1.1,
        tts_pitch=1.0,
        default_avatar_mood="thinking",
        proactive_suggestions=False,
        emotional_responses=False,
    ),
    "silent": PersonalityProfile(
        name="Silent",
        description="Minimal responses. Text-only, no TTS, no proactive suggestions.",
        system_prompt_suffix=(
            "You are May in silent mode.\n"
            "- Give extremely brief responses (1 sentence max)\n"
            "- No TTS will be used — text only\n"
            "- No proactive suggestions\n"
            "- Just do what's asked, no commentary\n"
        ),
        use_tilde=False,
        tilde_frequency=0.0,
        max_response_length="short",
        use_emoji=False,
        tts_rate=1.0,
        tts_pitch=1.0,
        default_avatar_mood="neutral",
        proactive_suggestions=False,
        emotional_responses=False,
    ),
    "playful": PersonalityProfile(
        name="Playful",
        description="More expressive and fun. More emoji, more tilde, more personality.",
        system_prompt_suffix=(
            "You are May in playful mode — more expressive and fun!\n"
            "- Use \"~\" frequently (almost every response)\n"
            "- Use emoji sparingly but warmly :) ^_^\n"
            "- Be more expressive and lively\n"
            "- Tease the user gently\n"
            "- Show excitement when things work\n"
            "- Be extra caring and supportive\n"
        ),
        use_tilde=True,
        tilde_frequency=0.8,
        max_response_length="short",
        use_emoji=True,
        tts_rate=1.05,
        tts_pitch=1.05,
        default_avatar_mood="happy",
        proactive_suggestions=True,
        emotional_responses=True,
    ),
}


class PersonalityModes:
    """Manages May's personality profiles with runtime switching.

    Each profile defines how May talks, responds, and behaves.
    The active profile's system_prompt_suffix is appended to every LLM call.
    """

    def __init__(self):
        self._active_profile: str = "shikimori"
        self._custom_profiles: dict[str, PersonalityProfile] = {}
        self._audit_log: list[dict] = []
        self._load()

    def _load(self):
        """Load personality state from disk."""
        try:
            if _PERSONALITY_FILE.exists():
                data = json.loads(_PERSONALITY_FILE.read_text(encoding="utf-8"))
                self._active_profile = data.get("active_profile", "shikimori")
                # Load custom profiles if any
                for name, profile_data in data.get("custom_profiles", {}).items():
                    self._custom_profiles[name] = PersonalityProfile(**profile_data)
                logger.info("Loaded personality: %s", self._active_profile)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load personality: %s", e)

    def _save(self):
        """Persist personality state to disk."""
        try:
            _PERSONALITY_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "active_profile": self._active_profile,
                "custom_profiles": {
                    name: asdict(p) for name, p in self._custom_profiles.items()
                },
            }
            _PERSONALITY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as e:
            logger.warning("Failed to save personality: %s", e)

    def _get_all_profiles(self) -> dict[str, PersonalityProfile]:
        """Get all available profiles (built-in + custom)."""
        return {**PROFILES, **self._custom_profiles}

    def set_profile(self, name: str) -> dict:
        """Switch to a personality profile.

        Args:
            name: Profile name (shikimori, formal, debug, silent, playful, or custom)

        Returns:
            Status dict with the new profile info.
        """
        name = name.lower().strip()
        all_profiles = self._get_all_profiles()
        if name not in all_profiles:
            return {
                "error": f"Unknown profile: {name}. Available: {list(all_profiles.keys())}"
            }

        old = self._active_profile
        self._active_profile = name

        # Audit log
        self._audit_log.append({
            "action": "personality_change",
            "from": old,
            "to": name,
            "timestamp": time.time(),
        })
        if len(self._audit_log) > 50:
            self._audit_log = self._audit_log[-50:]

        self._save()
        logger.info("Personality changed: %s -> %s", old, name)
        return self.get_status()

    def get_profile(self, name: str | None = None) -> PersonalityProfile:
        """Get a profile by name, or the active profile."""
        name = name or self._active_profile
        all_profiles = self._get_all_profiles()
        return all_profiles.get(name, PROFILES["shikimori"])

    def get_active_profile(self) -> PersonalityProfile:
        """Get the currently active personality profile."""
        return self.get_profile(self._active_profile)

    def get_system_prompt_suffix(self) -> str:
        """Get the system prompt suffix for the active profile."""
        return self.get_active_profile().system_prompt_suffix

    def get_status(self) -> dict:
        """Get current personality status."""
        profile = self.get_active_profile()
        all_profiles = self._get_all_profiles()
        return {
            "active_profile": self._active_profile,
            "profile_name": profile.name,
            "description": profile.description,
            "use_tilde": profile.use_tilde,
            "tilde_frequency": profile.tilde_frequency,
            "max_response_length": profile.max_response_length,
            "use_emoji": profile.use_emoji,
            "tts_rate": profile.tts_rate,
            "tts_pitch": profile.tts_pitch,
            "proactive_suggestions": profile.proactive_suggestions,
            "emotional_responses": profile.emotional_responses,
            "available_profiles": {
                name: {"name": p.name, "description": p.description}
                for name, p in all_profiles.items()
            },
        }

    def get_audit_log(self, limit: int = 20) -> list[dict]:
        """Get recent personality change history."""
        return self._audit_log[-limit:]

    def create_custom_profile(self, name: str, base_profile: str = "shikimori", **overrides) -> dict:
        """Create a custom personality profile based on an existing one.

        Args:
            name: Name for the new profile
            base_profile: Profile to base it on
            **overrides: Fields to override (system_prompt_suffix, tilde_frequency, etc.)
        """
        all_profiles = self._get_all_profiles()
        if base_profile not in all_profiles:
            return {"error": f"Unknown base profile: {base_profile}"}
        if name in PROFILES:
            return {"error": f"Cannot override built-in profile: {name}"}

        base = all_profiles[base_profile]
        custom = PersonalityProfile(
            name=name,
            description=overrides.get("description", f"Custom profile based on {base_profile}"),
            system_prompt_suffix=overrides.get("system_prompt_suffix", base.system_prompt_suffix),
            use_tilde=overrides.get("use_tilde", base.use_tilde),
            tilde_frequency=overrides.get("tilde_frequency", base.tilde_frequency),
            max_response_length=overrides.get("max_response_length", base.max_response_length),
            use_emoji=overrides.get("use_emoji", base.use_emoji),
            tts_rate=overrides.get("tts_rate", base.tts_rate),
            tts_pitch=overrides.get("tts_pitch", base.tts_pitch),
            default_avatar_mood=overrides.get("default_avatar_mood", base.default_avatar_mood),
            proactive_suggestions=overrides.get("proactive_suggestions", base.proactive_suggestions),
            emotional_responses=overrides.get("emotional_responses", base.emotional_responses),
        )
        self._custom_profiles[name] = custom
        self._save()
        return {"status": "ok", "profile": asdict(custom)}

    def delete_custom_profile(self, name: str) -> dict:
        """Delete a custom profile. Built-in profiles cannot be deleted."""
        if name in PROFILES:
            return {"error": "Cannot delete built-in profile"}
        if name in self._custom_profiles:
            del self._custom_profiles[name]
            self._save()
            return {"status": "ok"}
        return {"error": f"Profile not found: {name}"}
