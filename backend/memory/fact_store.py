"""Structured fact store using SQLite for user preferences and pinned memories."""

import sqlite3
import json
from datetime import datetime
from pathlib import Path


class FactStore:
    """Manages structured user facts and preferences in SQLite."""

    def __init__(self, db_path: str = "../data/facts.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    confidence REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    remind_at TIMESTAMP NOT NULL,
                    completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def set_fact(self, key: str, value: str, category: str = "general") -> None:
        """Store or update a user fact."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO facts (key, value, category, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   category = excluded.category,
                   updated_at = CURRENT_TIMESTAMP""",
                (key, value, category),
            )

    def get_fact(self, key: str) -> str | None:
        """Retrieve a user fact by key."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT value FROM facts WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_facts_by_category(self, category: str) -> list[dict]:
        """Get all facts in a category."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT key, value, category, updated_at FROM facts WHERE category = ?",
                (category,),
            )
            return [
                {"key": r[0], "value": r[1], "category": r[2], "updated_at": r[3]}
                for r in cursor.fetchall()
            ]

    def get_all_facts(self) -> list[dict]:
        """Get all stored facts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT key, value, category, updated_at FROM facts"
            )
            return [
                {"key": r[0], "value": r[1], "category": r[2], "updated_at": r[3]}
                for r in cursor.fetchall()
            ]

    def delete_fact(self, key: str) -> bool:
        """Delete a fact. Returns True if deleted."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM facts WHERE key = ?", (key,))
            return cursor.rowcount > 0

    def add_reminder(self, message: str, remind_at: str) -> int:
        """Add a reminder. Returns the reminder ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO reminders (message, remind_at) VALUES (?, ?)",
                (message, remind_at),
            )
            return cursor.lastrowid or 0

    def get_pending_reminders(self) -> list[dict]:
        """Get all pending (uncompleted) reminders."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """SELECT id, message, remind_at, created_at
                   FROM reminders
                   WHERE completed = FALSE AND remind_at <= ?
                   ORDER BY remind_at""",
                (now,),
            )
            return [
                {"id": r[0], "message": r[1], "remind_at": r[2], "created_at": r[3]}
                for r in cursor.fetchall()
            ]

    def complete_reminder(self, reminder_id: int) -> bool:
        """Mark a reminder as completed."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE reminders SET completed = TRUE WHERE id = ?",
                (reminder_id,),
            )
            return cursor.rowcount > 0
