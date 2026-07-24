"""Emotional Tone Analyzer — detects user mood from message text.

Analyzes user messages for emotional signals and returns a mood classification
that the frontend uses to adjust the avatar's expression and May's personality.

Tier 1: Keyword/pattern matching (fast, no LLM needed)
Tier 2: LLM-based analysis (optional, for nuanced detection)

The mood output maps directly to the frontend's MayMood type:
- neutral, happy, cool, concerned, surprised
Plus extended moods for richer avatar expression:
- frustrated, excited, calm, sad
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("may.intelligence.tone_analyzer")


class UserMood(str, Enum):
    """Detected user mood — maps to avatar expression."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    CALM = "calm"
    ANGRY = "angry"
    ANXIOUS = "anxious"
    GRATEFUL = "grateful"
    CURIOUS = "curious"


@dataclass
class ToneResult:
    """Result of tone analysis."""
    mood: UserMood
    confidence: float  # 0.0 - 1.0
    signals: list[str]  # What triggered this mood detection
    suggested_may_mood: str  # May's response mood (maps to MayMood in frontend)
    response_style: str  # Personality adjustment hint
    timestamp: float = field(default_factory=time.time)


# ── Keyword Patterns ──────────────────────────────────────────────────────

MOOD_PATTERNS: dict[UserMood, list[str]] = {
    UserMood.HAPPY: [
        r"\b(haha|hehe|lol|lmao|rofl)\b",
        r"\b(happy|glad|great|awesome|amazing|perfect|wonderful|fantastic)\b",
        r"\b(thanks?|thx|ty|thank you|tysm)\b",
        r"\b(nice|cool|sweet|brilliant|excellent)\b",
        r"[!]{2,}",  # Multiple exclamation marks
        r"[😊😄😃🎉❤️✨💕🌟👍]",
    ],
    UserMood.SAD: [
        r"\b(sad|upset|depressed|miserable|unhappy|lonely)\b",
        r"\b(miss you|miss them|miss it)\b",
        r"\b(cry|crying|tears|heartbroken)\b",
        r"\b(not okay|not doing well|feeling down)\b",
        r"[😢😭💔😞]",
    ],
    UserMood.FRUSTRATED: [
        r"\b(ugh|argh|damn|dammit|crap|stupid|useless)\b",
        r"\b(not working|broken|doesn't work|won't work|failed)\b",
        r"\b(keep failing|keeps crashing|error again)\b",
        r"\b(why won't|how do I|I can't figure)\b",
        r"\b(tired of|sick of|fed up)\b",
        r"[😤😤🏻 frustrated emoji]",
    ],
    UserMood.EXCITED: [
        r"\b(omg|oh my god|no way|wow|whoa|holy)\b",
        r"\b(excited|pumped|hyped|can't wait|stoked)\b",
        r"\b(it worked|it's working|finally|yesss|yes!)\b",
        r"\b(just got|just finished|just completed)\b",
        r"[🔥⚡🚀🎉🎊]",
    ],
    UserMood.ANGRY: [
        r"\b(hate|angry|furious|pissed|livid|raging)\b",
        r"\b(worst|terrible|awful|horrible|hate this)\b",
        r"\b(wtf|wth|are you kidding|unacceptable)\b",
        r"[😡🤬💢]",
    ],
    UserMood.ANXIOUS: [
        r"\b(worried|anxious|nervous|stressed|panic)\b",
        r"\b(what if|hope it|scared|afraid|fear)\b",
        r"\b(deadline|due soon|rushing|hurry|urgent)\b",
        r"[😰😨😟]",
    ],
    UserMood.GRATEFUL: [
        r"\b(thank|thanks|thx|appreciate|grateful)\b",
        r"\b(you're the best|you helped|saved me)\b",
        r"\b(couldn't have done|thanks to you)\b",
    ],
    UserMood.CURIOUS: [
        r"\b(how|what|why|when|where|who)\b.*\?",
        r"\b(wonder|curious|interesting|tell me|explain)\b",
        r"\b(what is|what are|how does|how do)\b",
    ],
    UserMood.CALM: [
        r"\b(ok|okay|alright|sure|fine|sounds good)\b",
        r"\b(noted|understood|got it|makes sense)\b",
        r"\b(chill|relaxed|mellow|peaceful)\b",
    ],
}

# ── May's Response Style Adjustments ──────────────────────────────────────
# Maps user mood → how May should adjust her personality

RESPONSE_STYLES: dict[UserMood, dict] = {
    UserMood.NEUTRAL: {
        "may_mood": "neutral",
        "style": "default",
        "prefix_chance": 0.3,
        "empathy_level": "normal",
    },
    UserMood.HAPPY: {
        "may_mood": "happy",
        "style": "enthusiastic",
        "prefix_chance": 0.5,
        "empathy_level": "match_energy",
    },
    UserMood.SAD: {
        "may_mood": "concerned",
        "style": "gentle",
        "prefix_chance": 0.7,
        "empathy_level": "high",
    },
    UserMood.FRUSTRATED: {
        "may_mood": "concerned",
        "style": "solution_focused",
        "prefix_chance": 0.8,
        "empathy_level": "validate_then_solve",
    },
    UserMood.EXCITED: {
        "may_mood": "happy",
        "style": "mirror_excitement",
        "prefix_chance": 0.6,
        "empathy_level": "match_energy",
    },
    UserMood.ANGRY: {
        "may_mood": "concerned",
        "style": "calm_and_helpful",
        "prefix_chance": 0.9,
        "empathy_level": "de_escalate",
    },
    UserMood.ANXIOUS: {
        "may_mood": "concerned",
        "style": "reassuring",
        "prefix_chance": 0.7,
        "empathy_level": "high",
    },
    UserMood.GRATEFUL: {
        "may_mood": "happy",
        "style": "warm",
        "prefix_chance": 0.4,
        "empathy_level": "accept_grace",
    },
    UserMood.CURIOUS: {
        "may_mood": "cool",
        "style": "informative",
        "prefix_chance": 0.3,
        "empathy_level": "normal",
    },
    UserMood.CALM: {
        "may_mood": "cool",
        "style": "default",
        "prefix_chance": 0.2,
        "empathy_level": "normal",
    },
}

# Greeting patterns (shouldn't trigger sad/excited just because someone says "hey")
GREETING_PATTERN = re.compile(
    r"^(hey|hi|hello|yo|sup|good morning|good evening|good night|howdy|how are you|what's up)[\s!.~]*$",
    re.IGNORECASE,
)


class ToneAnalyzer:
    """Analyzes user messages for emotional tone.

    Stateless — each message is analyzed independently.
    Keeps a short history (last 5 messages) for trend detection.
    """

    def __init__(self):
        self._history: list[tuple[str, UserMood]] = []
        self._max_history = 5

    def analyze(self, message: str) -> ToneResult:
        """Analyze a user message and return mood classification."""
        msg_lower = message.lower().strip()
        signals: list[str] = []
        scores: dict[UserMood, float] = {mood: 0.0 for mood in UserMood}

        # Skip very short messages
        if len(msg_lower) < 2:
            return ToneResult(
                mood=UserMood.NEUTRAL,
                confidence=0.5,
                signals=["short_message"],
                **self._get_style(UserMood.NEUTRAL),
            )

        # Skip pure greetings
        if GREETING_PATTERN.match(msg_lower):
            return ToneResult(
                mood=UserMood.CALM,
                confidence=0.8,
                signals=["greeting"],
                **self._get_style(UserMood.CALM),
            )

        # Tier 1: Keyword/pattern matching
        for mood, patterns in MOOD_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, msg_lower)
                if matches:
                    score = min(1.0, len(matches) * 0.3 + 0.2)
                    scores[mood] = max(scores[mood], score)
                    signals.append(f"{mood.value}:{pattern if isinstance(pattern, str) else pattern.pattern}")

        # Check for ALL CAPS (shouting = anger/excitement)
        words = msg_lower.split()
        caps_ratio = sum(1 for w in message.split() if w.isupper() and len(w) > 1) / max(1, len(words))
        if caps_ratio > 0.5 and len(words) > 1:
            scores[UserMood.ANGRY] += 0.3
            scores[UserMood.EXCITED] += 0.1
            signals.append("all_caps_shouting")

        # Check for exclamation density (excitement or frustration)
        excl_count = message.count("!")
        if excl_count >= 3:
            scores[UserMood.EXCITED] += 0.2
            signals.append(f"exclamation_density:{excl_count}")

        # Check for question marks (curiosity)
        if message.count("?") >= 2:
            scores[UserMood.CURIOUS] += 0.2
            signals.append("multiple_questions")

        # Check for profanity indicators (frustration/anger)
        profanity_indicators = ["damn", "hell", "shit", "fuck", "wtf", "bruh"]
        for word in profanity_indicators:
            if word in msg_lower:
                scores[UserMood.FRUSTRATED] += 0.3
                scores[UserMood.ANGRY] += 0.2
                signals.append(f"profanity:{word}")

        # Trend detection: if last 2+ messages were frustrated, boost frustration
        if len(self._history) >= 2:
            recent_moods = [m for _, m in self._history[-2:]]
            if recent_moods.count(UserMood.FRUSTRATED) >= 2:
                scores[UserMood.FRUSTRATED] += 0.3
                signals.append("frustration_trend")

        # Pick the highest scoring mood
        best_mood = max(scores, key=lambda m: scores[m])
        best_score = scores[best_mood]

        # If no strong signal, default to neutral
        if best_score < 0.2:
            best_mood = UserMood.NEUTRAL
            best_score = 0.5
            signals.append("no_strong_signal")

        # Confidence is the score, capped at 0.95 (never 100% certain)
        confidence = min(0.95, best_score)

        # Store in history
        self._history.append((message, best_mood))
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        result = ToneResult(
            mood=best_mood,
            confidence=confidence,
            signals=signals,
            **self._get_style(best_mood),
        )

        logger.debug("Tone analysis: mood=%s conf=%.2f signals=%s",
                     best_mood.value, confidence, signals)

        return result

    def _get_style(self, mood: UserMood) -> dict:
        """Get May's response style for a given user mood."""
        style = RESPONSE_STYLES.get(mood, RESPONSE_STYLES[UserMood.NEUTRAL])
        return {
            "suggested_may_mood": style["may_mood"],
            "response_style": style["style"],
        }

    def get_conversation_energy(self) -> float:
        """Get the overall energy level of the conversation (0.0 = calm, 1.0 = intense)."""
        if not self._history:
            return 0.5
        high_energy = {UserMood.EXCITED, UserMood.ANGRY, UserMood.FRUSTRATED}
        low_energy = {UserMood.CALM, UserMood.SAD, UserMood.NEUTRAL}
        recent = [m for _, m in self._history[-5:]]
        high_count = sum(1 for m in recent if m in high_energy)
        low_count = sum(1 for m in recent if m in low_energy)
        return (high_count * 1.0 + low_count * 0.0 + (len(recent) - high_count - low_count) * 0.5) / max(1, len(recent))

    def reset(self):
        """Clear conversation history."""
        self._history.clear()
