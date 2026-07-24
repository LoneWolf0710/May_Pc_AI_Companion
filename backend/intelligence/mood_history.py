"""Mood History — persistent mood tracking across conversations.

Stores mood analysis results in SQLite for long-term trend analysis.
Provides mood summaries, dominant mood detection, and emotional timeline.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger("may.intelligence.mood_history")

DB_PATH = os.path.join(os.path.expanduser("~"), ".may", "mood_history.db")


@dataclass
class MoodEntry:
    """A single mood observation."""
    timestamp: float
    mood: str
    confidence: float
    message_preview: str  # First 100 chars of the user message
    may_mood: str  # May's response mood
    response_style: str
    conversation_id: str = ""  # Optional: group entries by conversation


@dataclass
class MoodTrend:
    """Aggregated mood trend over a time window."""
    period: str  # "1h", "6h", "24h", "7d"
    dominant_mood: str
    mood_distribution: dict[str, float]  # mood -> percentage
    average_confidence: float
    average_energy: float  # 0-1, higher = more intense emotions
    total_entries: int
    mood_shifts: int  # Number of mood transitions


class MoodHistory:
    """Persistent mood tracking with SQLite backend.

    Stores every mood analysis result and provides trend analysis.
    """

    def __init__(self, db_path: str = DB_PATH):
        self._db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        """Create tables if they don't exist."""
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mood_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    mood TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    message_preview TEXT NOT NULL,
                    may_mood TEXT NOT NULL,
                    response_style TEXT NOT NULL,
                    conversation_id TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_mood_timestamp
                ON mood_entries(timestamp)
            """)
            conn.commit()
        finally:
            conn.close()

    def record(self, entry: MoodEntry):
        """Record a mood entry."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """INSERT INTO mood_entries
                   (timestamp, mood, confidence, message_preview, may_mood, response_style, conversation_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (entry.timestamp, entry.mood, entry.confidence,
                 entry.message_preview, entry.may_mood, entry.response_style,
                 entry.conversation_id),
            )
            conn.commit()
            logger.debug("Recorded mood: %s (conf=%.2f)", entry.mood, entry.confidence)
        finally:
            conn.close()

    def get_recent(self, count: int = 20) -> list[dict]:
        """Get the most recent mood entries."""
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                """SELECT timestamp, mood, confidence, message_preview,
                          may_mood, response_style, conversation_id
                   FROM mood_entries ORDER BY timestamp DESC LIMIT ?""",
                (count,),
            ).fetchall()
            return [
                {
                    "timestamp": r[0],
                    "mood": r[1],
                    "confidence": r[2],
                    "message_preview": r[3],
                    "may_mood": r[4],
                    "response_style": r[5],
                    "conversation_id": r[6],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_trend(self, period: str = "24h") -> MoodTrend:
        """Get mood trend for a time window.

        Supported periods: "1h", "6h", "24h", "7d"
        """
        seconds = {"1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}.get(period, 86400)
        cutoff = time.time() - seconds

        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                """SELECT mood, confidence FROM mood_entries
                   WHERE timestamp > ? ORDER BY timestamp""",
                (cutoff,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return MoodTrend(
                period=period,
                dominant_mood="neutral",
                mood_distribution={},
                average_confidence=0.5,
                average_energy=0.5,
                total_entries=0,
                mood_shifts=0,
            )

        # Count mood occurrences
        mood_counts: dict[str, int] = {}
        total_confidence = 0.0
        mood_shifts = 0
        prev_mood = None

        for mood, confidence in rows:
            mood_counts[mood] = mood_counts.get(mood, 0) + 1
            total_confidence += confidence
            if prev_mood and mood != prev_mood:
                mood_shifts += 1
            prev_mood = mood

        total = len(rows)
        dominant = max(mood_counts, key=mood_counts.get)
        distribution = {m: c / total for m, c in mood_counts.items()}

        # Energy: high-energy moods (excited, angry, frustrated) vs low-energy (calm, sad, neutral)
        high_energy_moods = {"excited", "angry", "frustrated"}
        low_energy_moods = {"calm", "sad", "neutral"}
        high_count = sum(1 for m, _ in rows if m in high_energy_moods)
        low_count = sum(1 for m, _ in rows if m in low_energy_moods)
        energy = (high_count * 1.0 + low_count * 0.0 + (total - high_count - low_count) * 0.5) / max(1, total)

        return MoodTrend(
            period=period,
            dominant_mood=dominant,
            mood_distribution=distribution,
            average_confidence=total_confidence / max(1, total),
            average_energy=energy,
            total_entries=total,
            mood_shifts=mood_shifts,
        )

    def get_timeline(self, hours: int = 24) -> list[dict]:
        """Get mood timeline for charting — aggregated by 15-minute buckets."""
        cutoff = time.time() - (hours * 3600)
        bucket_size = 900  # 15 minutes

        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                """SELECT timestamp, mood, confidence FROM mood_entries
                   WHERE timestamp > ? ORDER BY timestamp""",
                (cutoff,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return []

        # Group into buckets
        buckets: dict[int, list[tuple[str, float]]] = {}
        for ts, mood, conf in rows:
            bucket_key = int(ts // bucket_size) * bucket_size
            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append((mood, conf))

        timeline = []
        for bucket_ts in sorted(buckets.keys()):
            entries = buckets[bucket_ts]
            mood_counts = {}
            for mood, _ in entries:
                mood_counts[mood] = mood_counts.get(mood, 0) + 1
            dominant = max(mood_counts, key=mood_counts.get)
            avg_conf = sum(c for _, c in entries) / len(entries)
            timeline.append({
                "timestamp": bucket_ts,
                "dominant_mood": dominant,
                "mood_count": len(entries),
                "average_confidence": avg_conf,
            })

        return timeline

    def get_stats(self) -> dict:
        """Get overall mood history statistics."""
        conn = sqlite3.connect(self._db_path)
        try:
            total = conn.execute("SELECT COUNT(*) FROM mood_entries").fetchone()[0]
            first = conn.execute("SELECT MIN(timestamp) FROM mood_entries").fetchone()[0]
            last = conn.execute("SELECT MAX(timestamp) FROM mood_entries").fetchone()[0]

            # Most common mood
            row = conn.execute(
                """SELECT mood, COUNT(*) as cnt FROM mood_entries
                   GROUP BY mood ORDER BY cnt DESC LIMIT 1"""
            ).fetchone()
            most_common = row[0] if row else "neutral"
            most_common_count = row[1] if row else 0
        finally:
            conn.close()

        return {
            "total_entries": total,
            "first_entry_age_hours": round((time.time() - first) / 3600, 1) if first else 0,
            "last_entry_age_hours": round((time.time() - last) / 3600, 1) if last else 0,
            "most_common_mood": most_common,
            "most_common_count": most_common_count,
        }

    def clear_old(self, days: int = 30):
        """Remove entries older than N days."""
        cutoff = time.time() - (days * 86400)
        conn = sqlite3.connect(self._db_path)
        try:
            result = conn.execute("DELETE FROM mood_entries WHERE timestamp < ?", (cutoff,))
            conn.commit()
            return result.rowcount
        finally:
            conn.close()
