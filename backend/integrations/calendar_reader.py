"""Calendar integration — reads .ics files for upcoming events.

Supports:
- Local .ics file reading (universal iCalendar format)
- Google Calendar (via exported .ics URL)
- Outlook (via exported .ics file)
- Any CalDAV-compatible calendar

Usage:
    reader = CalendarReader()
    events = await reader.get_upcoming(days=1)
    # Or with a specific file/URL:
    events = await reader.get_upcoming(days=1, source="/path/to/calendar.ics")
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("may.integrations.calendar")


@dataclass
class CalendarEvent:
    """A single calendar event."""
    summary: str
    start: datetime
    end: datetime | None = None
    description: str = ""
    location: str = ""
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "start": self.start.isoformat(),
            "end": self.end.isoformat() if self.end else None,
            "description": self.description[:200] if self.description else "",
            "location": self.location,
            "source": self.source,
        }

    def to_briefing_text(self) -> str:
        """Format as brief text for the morning briefing."""
        time_str = self.start.strftime("%I:%M %p").lstrip("0")
        parts = [f"{self.summary} at {time_str}"]
        if self.location:
            parts.append(f"(at {self.location})")
        return " ".join(parts)


class CalendarReader:
    """Reads calendar events from .ics files or URLs.

    Supports:
    - Local .ics files: source="/path/to/calendar.ics"
    - Remote .ics URLs: source="https://calendar.google.com/calendar/ical/..."
    - Default: checks common locations for .ics files
    """

    # Common locations to look for .ics files
    DEFAULT_PATHS = [
        os.path.expanduser("~/Documents/*.ics"),
        os.path.expanduser("~/Desktop/*.ics"),
        os.path.expanduser("~/Downloads/*.ics"),
        os.path.expanduser("~/.may/calendar.ics"),
    ]

    def __init__(self):
        self._cache_url: str | None = None
        self._cache_events: list[CalendarEvent] = []
        self._cache_time: float = 0

    async def get_upcoming(self, days: int = 1,
                           source: str | None = None) -> list[CalendarEvent]:
        """Get upcoming events within the next N days.

        Args:
            days: Number of days to look ahead
            source: Path to .ics file or URL. If None, auto-discovers.

        Returns:
            List of CalendarEvent objects, sorted by start time
        """
        # Determine source
        ics_content = None

        if source:
            ics_content = await self._fetch_ics(source)
        else:
            # Try to find a .ics file
            ics_content = await self._auto_discover()

        if not ics_content:
            return []

        # Parse the ICS content
        events = self._parse_ics(ics_content)

        # Filter to upcoming events
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days)

        upcoming = [
            e for e in events
            if e.start >= now - timedelta(hours=1)  # Include events that started <1hr ago
            and (e.start <= cutoff)
        ]

        upcoming.sort(key=lambda e: e.start)
        logger.info("Calendar: found %d events in next %d days", len(upcoming), days)
        return upcoming

    async def _fetch_ics(self, source: str) -> str | None:
        """Fetch ICS content from a file path or URL."""
        if source.startswith("http://") or source.startswith("https://"):
            try:
                import httpx
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(source)
                    resp.raise_for_status()
                    return resp.text
            except Exception as e:
                logger.warning("Failed to fetch ICS from URL: %s", e)
                return None
        else:
            # Local file
            path = os.path.expanduser(source)
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception as e:
                    logger.warning("Failed to read ICS file %s: %s", path, e)
            return None

    async def _auto_discover(self) -> str | None:
        """Auto-discover .ics files in common locations."""
        import glob
        for pattern in self.DEFAULT_PATHS:
            matches = glob.glob(pattern)
            if matches:
                # Use the most recently modified one
                matches.sort(key=os.path.getmtime, reverse=True)
                return await self._fetch_ics(matches[0])
        return None

    def _parse_ics(self, content: str) -> list[CalendarEvent]:
        """Parse ICS content into CalendarEvent objects.

        This is a lightweight parser that handles the most common ICS fields
        without requiring the 'icalendar' library.
        """
        events = []
        lines = self._unfold_ics(content)

        current_event = None
        for line in lines:
            if line == "BEGIN:VEVENT":
                current_event = CalendarEvent(
                    summary="", start=datetime.now(timezone.utc),
                )
            elif line == "END:VEVENT" and current_event:
                if current_event.summary:
                    events.append(current_event)
                current_event = None
            elif current_event:
                if line.startswith("SUMMARY:"):
                    current_event.summary = line[8:].strip()
                elif line.startswith("DTSTART"):
                    current_event.start = self._parse_ics_datetime(line)
                elif line.startswith("DTEND"):
                    current_event.end = self._parse_ics_datetime(line)
                elif line.startswith("DESCRIPTION:"):
                    desc = line[12:].strip()
                    # Unescape ICS text
                    desc = desc.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")
                    current_event.description = desc
                elif line.startswith("LOCATION:"):
                    current_event.location = line[9:].strip().replace("\\,", ",")

        return events

    def _unfold_ics(self, content: str) -> list[str]:
        """Unfold ICS lines (continuation lines start with space/tab)."""
        lines = []
        for line in content.split("\n"):
            line = line.rstrip("\r")
            if line and line[0] in (" ", "\t"):
                if lines:
                    lines[-1] += line[1:]
            else:
                lines.append(line)
        return lines

    def _parse_ics_datetime(self, line: str) -> datetime:
        """Parse an ICS DATETIME value.

        Handles formats:
        - DTSTART:20240115T090000Z
        - DTSTART;TZID=America/New_York:20240115T090000
        - DTSTART;VALUE=DATE:20240115
        """
        # Extract the datetime part (after the colon)
        parts = line.split(":", 1)
        if len(parts) < 2:
            return datetime.now(timezone.utc)

        dt_str = parts[1].strip()

        # Check for timezone info
        tz_info = None
        if line.startswith("DTSTART;TZID="):
            # Has a timezone ID — treat as local time
            tz_info = None  # Will use local timezone
        elif dt_str.endswith("Z"):
            tz_info = timezone.utc
            dt_str = dt_str[:-1]

        try:
            if len(dt_str) == 8:
                # DATE only: 20240115
                return datetime.strptime(dt_str, "%Y%m%d").replace(tzinfo=tz_info or timezone.utc)
            else:
                # DATETIME: 20240115T090000
                return datetime.strptime(dt_str, "%Y%m%dT%H%M%S").replace(tzinfo=tz_info or timezone.utc)
        except ValueError:
            logger.debug("Failed to parse ICS datetime: %s", dt_str)
            return datetime.now(timezone.utc)
