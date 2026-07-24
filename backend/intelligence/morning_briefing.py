"""Morning Briefing — aggregates weather, news, calendar, reminders, and smart home into a daily briefing.

Per JARVIS_V2_ARCHITECTURE.md Section 4.8:

When May starts up (or user requests), she delivers a morning briefing:
- Current weather + forecast
- Top news headlines
- Upcoming calendar events
- Pending reminders
- Smart home status (lights, thermostat, etc.)

All data is fetched concurrently for speed. The briefing is formatted
as a natural-language message that May delivers in her Shikimori voice.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("may.intelligence.morning_briefing")


@dataclass
class MorningBriefing:
    """A complete morning briefing with all sections."""
    weather_text: str = ""
    news_text: str = ""
    calendar_text: str = ""
    reminders_text: str = ""
    smart_home_text: str = ""
    generated_at: float = 0
    generation_time_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "weather": self.weather_text,
            "news": self.news_text,
            "calendar": self.calendar_text,
            "reminders": self.reminders_text,
            "smart_home": self.smart_home_text,
            "generated_at": self.generated_at,
            "generation_time_ms": self.generation_time_ms,
        }

    def to_full_briefing(self) -> str:
        """Format the complete briefing as a natural-language message.

        This is what May says to the user.
        """
        sections = []

        if self.weather_text:
            sections.append(self.weather_text)

        if self.news_text:
            sections.append(self.news_text)

        if self.calendar_text:
            sections.append(self.calendar_text)

        if self.reminders_text:
            sections.append(self.reminders_text)

        if self.smart_home_text:
            sections.append(self.smart_home_text)

        if not sections:
            return "Good morning~ Nothing new to report right now."

        # Add a May-style greeting
        greeting = "Good morning~"
        return f"{greeting}\n\n" + "\n\n".join(sections)


class MorningBriefingGenerator:
    """Generates morning briefings by aggregating all data sources.

    Usage:
        generator = MorningBriefingGenerator()
        briefing = await generator.generate()
        print(briefing.to_full_briefing())
    """

    def __init__(self):
        self._last_briefing: MorningBriefing | None = None
        self._last_gen_time: float = 0
        self._cache_ttl = 1800  # 30 minutes

    async def generate(self, fact_store=None, force: bool = False) -> MorningBriefing:
        """Generate a complete morning briefing.

        Fetches all data sources concurrently for speed.

        Args:
            fact_store: FactStore instance for retrieving reminders
            force: Force regeneration even if cached

        Returns:
            MorningBriefing with all sections populated
        """
        now = time.time()

        # Check cache
        if not force and self._last_briefing and (now - self._last_gen_time) < self._cache_ttl:
            return self._last_briefing

        start_time = time.monotonic()

        briefing = MorningBriefing(generated_at=now)

        # Fetch all data sources concurrently
        tasks = {
            "weather": self._fetch_weather(),
            "news": self._fetch_news(),
            "calendar": self._fetch_calendar(),
            "reminders": self._fetch_reminders(fact_store),
            "smart_home": self._fetch_smart_home(),
        }

        results = await asyncio.gather(
            *tasks.values(),
            return_exceptions=True,
        )

        # Map results back to briefing sections
        keys = list(tasks.keys())
        for i, key in enumerate(keys):
            result = results[i]
            if isinstance(result, Exception):
                logger.warning("Failed to fetch %s for briefing: %s", key, result)
                continue
            if result:
                setattr(briefing, f"{key}_text", result)

        elapsed = int((time.monotonic() - start_time) * 1000)
        briefing.generation_time_ms = elapsed

        # Cache
        self._last_briefing = briefing
        self._last_gen_time = now

        logger.info("Morning briefing generated in %dms", elapsed)
        return briefing

    async def _fetch_weather(self) -> str:
        """Fetch weather data for the briefing."""
        try:
            from integrations import get_weather_client
            from settings import get_setting
            city = get_setting("city", "") or None
            client = get_weather_client(city=city)
            forecast = await client.get_forecast()
            return forecast.to_briefing_text()
        except Exception as e:
            logger.debug("Weather fetch failed: %s", e)
            return ""

    async def _fetch_news(self) -> str:
        """Fetch top news headlines."""
        try:
            from integrations import get_news_client
            client = get_news_client()
            digest = await client.get_headlines("technology", max_items=5)
            return digest.to_briefing_text(max_items=3)
        except Exception as e:
            logger.debug("News fetch failed: %s", e)
            return ""

    async def _fetch_calendar(self) -> str:
        """Fetch upcoming calendar events."""
        try:
            from integrations import get_calendar_reader
            reader = get_calendar_reader()
            events = await reader.get_upcoming(days=1)
            if not events:
                return ""
            lines = ["Upcoming today:"]
            for event in events[:5]:
                lines.append(f"  - {event.to_briefing_text()}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug("Calendar fetch failed: %s", e)
            return ""

    async def _fetch_reminders(self, fact_store=None) -> str:
        """Fetch pending reminders."""
        try:
            if fact_store is None:
                from memory.fact_store import FactStore
                fact_store = FactStore()
            reminders = fact_store.get_pending_reminders()
            if not reminders:
                return ""
            lines = [f"You have {len(reminders)} pending reminder(s):"]
            for r in reminders[:3]:
                msg = r.get("message", r.get("text", "something"))
                remind_at = r.get("remind_at", "")
                if remind_at:
                    lines.append(f"  - {msg} (due: {remind_at})")
                else:
                    lines.append(f"  - {msg}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug("Reminders fetch failed: %s", e)
            return ""

    async def _fetch_smart_home(self) -> str:
        """Fetch smart home status."""
        try:
            from integrations import get_smart_home_client
            client = get_smart_home_client()
            if not client.enabled:
                return ""
            devices = await client.get_entities(domain="light")
            if not devices:
                return ""
            on_count = sum(1 for d in devices if d.state == "on")
            total = len(devices)
            if on_count > 0:
                on_names = [d.friendly_name or d.entity_id for d in devices if d.state == "on"]
                return f"Smart home: {on_count}/{total} lights on ({', '.join(on_names[:3])})"
            return f"Smart home: all {total} lights off"
        except Exception as e:
            logger.debug("Smart home fetch failed: %s", e)
            return ""
