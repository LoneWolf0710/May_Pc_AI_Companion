"""Vector store for episodic memory using LanceDB + sentence-transformers.

Provides semantic search over past conversations so May can recall
relevant context from weeks ago — not just recent messages.

Architecture:
  - LanceDB: local, zero-config vector database (no server needed)
  - sentence-transformers: all-MiniLM-L6-v2 for fast embeddings (384-dim)
  - SQLite fallback: if LanceDB unavailable, stores summaries in SQLite
"""

import sqlite3
import json
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("may.vector_store")

# Lazy imports — these are heavy and only needed when actually using vectors
_lancedb = None
SentenceTransformer = None
_model = None


def _ensure_lancedb():
    """Lazy-load lancedb and sentence-transformers on first use."""
    global _lancedb, SentenceTransformer, _model
    if _lancedb is None:
        try:
            import lancedb as ldb
            _lancedb = ldb
        except ImportError:
            raise ImportError(
                "lancedb is required for vector memory. "
                "Install with: pip install lancedb"
            )
    if SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer as ST
            SentenceTransformer = ST
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for embeddings. "
                "Install with: pip install sentence-transformers"
            )
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")


EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension


def _default_db_path() -> Path:
    """Resolve the memory.lance path. In bundled mode, use %LOCALAPPDATA%\\May\\data\\."""
    import sys as _sys
    if getattr(_sys, "frozen", False):
        base = Path(__import__("os").environ.get("LOCALAPPDATA", Path.home())) / "May" / "data"
    else:
        base = Path(__file__).resolve().parent.parent / "data"
    return base / "memory.lance"


class VectorStore:
    """Manages episodic memory via vector similarity search.

    Falls back to SQLite-based text search if LanceDB is not installed,
    so the app still works without the ML dependencies.
    """

    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.table_name = "conversations"
        self._db = None
        self._table = None
        self._use_fallback = None  # None = not yet determined

        # Fallback SQLite for when LanceDB isn't installed
        self._sqlite_path = self.db_path.with_suffix(".sqlite")
        self._init_sqlite_fallback()

    def _open_or_create_table(self):
        """Open existing table or create a new one."""
        import pyarrow as pa

        try:
            return self._db.open_table(self.table_name)
        except ValueError:
            # Table doesn't exist yet — create it with PyArrow schema
            schema = pa.schema([
                ("id", pa.string()),
                ("summary", pa.string()),
                ("messages_json", pa.string()),
                ("topic", pa.string()),
                ("timestamp", pa.string()),
                ("vector", pa.list_(pa.float32(), list_size=EMBEDDING_DIM)),
            ])
            return self._db.create_table(self.table_name, schema=schema)

    def _init_sqlite_fallback(self):
        """Initialize SQLite fallback table for text search."""
        with sqlite3.connect(self._sqlite_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    messages_json TEXT,
                    topic TEXT DEFAULT 'general',
                    timestamp TEXT NOT NULL
                )
            """)

    def _ensure_db(self):
        """Lazily connect to LanceDB on first use."""
        if self._use_fallback is not None:
            return  # Already determined
        try:
            import lancedb as ldb
            self._db = ldb.connect(str(self.db_path))
            self._table = self._open_or_create_table()
            self._use_fallback = False
        except ImportError:
            self._use_fallback = True
        except Exception as e:
            logger.warning("LanceDB connection failed, using SQLite fallback: %s", e)
            self._use_fallback = True

    def _embed(self, text: str) -> list[float]:
        """Generate embedding for a text string."""
        _ensure_lancedb()
        embedding = _model.encode(text)
        return embedding.tolist()

    def _message_id(self, summary: str, timestamp: str) -> str:
        """Generate a deterministic ID for a conversation."""
        content = f"{summary}:{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def store_conversation(
        self,
        summary: str,
        messages: list[dict],
        topic: str = "general",
    ) -> str:
        """Store a summarized conversation with embeddings.

        Returns the conversation ID.
        """
        self._ensure_db()
        timestamp = datetime.now().isoformat()
        conv_id = self._message_id(summary, timestamp)
        messages_json = json.dumps(messages, default=str)

        if self._use_fallback:
            with sqlite3.connect(self._sqlite_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO conversations "
                    "(id, summary, messages_json, topic, timestamp) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (conv_id, summary, messages_json, topic, timestamp),
                )
            return conv_id

        # LanceDB vector storage
        vector = self._embed(summary)
        self._table.add([{
            "id": conv_id,
            "summary": summary,
            "messages_json": messages_json,
            "topic": topic,
            "timestamp": timestamp,
            "vector": vector,
        }])
        return conv_id

    async def search(
        self,
        query: str,
        n_results: int = 5,
        time_filter_days: Optional[int] = None,
    ) -> list[dict]:
        """Search episodic memory by semantic similarity.

        Args:
            query: The search query (natural language)
            n_results: Maximum results to return
            time_filter_days: Only return results from the last N days

        Returns:
            List of matching conversations with scores
        """
        self._ensure_db()

        # P5: Read memory_search_top_k from auto-tuner gene
        try:
            from intelligence.tuner_cache import get_gene
            n_results = int(get_gene("memory_search_top_k", default=n_results))
        except Exception:
            pass

        if self._use_fallback:
            return self._sqlite_search(query, n_results, time_filter_days)

        # Vector search with LanceDB
        query_vector = self._embed(query)
        results = (
            self._table.search(query_vector)
            .limit(n_results * 2)  # Over-fetch for time filtering
            .to_list()
        )

        # Apply time filter if specified
        if time_filter_days:
            cutoff = (datetime.now() - timedelta(days=time_filter_days)).isoformat()
            results = [r for r in results if r.get("timestamp", "") >= cutoff]

        # Format results
        return [
            {
                "id": r.get("id", ""),
                "summary": r.get("summary", ""),
                "topic": r.get("topic", "general"),
                "timestamp": r.get("timestamp", ""),
                "score": r.get("_distance", 0),
            }
            for r in results[:n_results]
        ]

    def _sqlite_search(
        self,
        query: str,
        n_results: int,
        time_filter_days: Optional[int],
    ) -> list[dict]:
        """Fallback text search using SQLite LIKE."""
        # Escape LIKE wildcards in user query to prevent injection
        safe_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with sqlite3.connect(self._sqlite_path) as conn:
            if time_filter_days:
                cutoff = (
                    datetime.now() - timedelta(days=time_filter_days)
                ).isoformat()
                cursor = conn.execute(
                    "SELECT id, summary, topic, timestamp "
                    "FROM conversations "
                    "WHERE summary LIKE ? ESCAPE '\\' AND timestamp >= ? "
                    "ORDER BY timestamp DESC LIMIT ?",
                    (f"%{safe_query}%", cutoff, n_results),
                )
            else:
                cursor = conn.execute(
                    "SELECT id, summary, topic, timestamp "
                    "FROM conversations "
                    "WHERE summary LIKE ? ESCAPE '\\' "
                    "ORDER BY timestamp DESC LIMIT ?",
                    (f"%{safe_query}%", n_results),
                )
            return [
                {"id": r[0], "summary": r[1], "topic": r[2], "timestamp": r[3], "score": 0}
                for r in cursor.fetchall()
            ]

    async def get_recent(self, n: int = 10) -> list[dict]:
        """Get the N most recent conversation summaries."""
        self._ensure_db()
        if self._use_fallback:
            with sqlite3.connect(self._sqlite_path) as conn:
                cursor = conn.execute(
                    "SELECT id, summary, topic, timestamp "
                    "FROM conversations ORDER BY timestamp DESC LIMIT ?",
                    (n,),
                )
                return [
                    {"id": r[0], "summary": r[1], "topic": r[2], "timestamp": r[3]}
                    for r in cursor.fetchall()
                ]

        try:
            results = (
                self._table.search()
                .limit(n)
                .to_list()
            )
            results.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
            return [
                {
                    "id": r.get("id", ""),
                    "summary": r.get("summary", ""),
                    "topic": r.get("topic", "general"),
                    "timestamp": r.get("timestamp", ""),
                }
                for r in results[:n]
            ]
        except Exception as e:
            logger.warning("Failed to get recent conversations: %s", e)
            return []

    async def prune_old(self, days_old: int = 90) -> int:
        """Remove memories older than N days. Returns count removed."""
        self._ensure_db()
        cutoff = (datetime.now() - timedelta(days=days_old)).isoformat()

        if self._use_fallback:
            with sqlite3.connect(self._sqlite_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM conversations WHERE timestamp < ?",
                    (cutoff,),
                )
                return cursor.rowcount

        try:
            all_records = self._table.search().to_list()
            old_ids = [
                r["id"]
                for r in all_records
                if r.get("timestamp", "") < cutoff
            ]
            if old_ids:
                # LanceDB delete takes a raw SQL WHERE clause.
                # IDs are internally generated SHA256 hashes, not user input,
                # so string formatting is safe here.
                formatted_ids = ", ".join(repr(i) for i in old_ids)
                self._table.delete(f"id IN ({formatted_ids})")
            return len(old_ids)
        except Exception as e:
            logger.warning("Failed to prune old conversations: %s", e)
            return 0

    async def get_stats(self) -> dict:
        """Get memory statistics."""
        self._ensure_db()
        if self._use_fallback:
            with sqlite3.connect(self._sqlite_path) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM conversations"
                ).fetchone()[0]
                oldest = conn.execute(
                    "SELECT MIN(timestamp) FROM conversations"
                ).fetchone()[0]
                newest = conn.execute(
                    "SELECT MAX(timestamp) FROM conversations"
                ).fetchone()[0]
                return {
                    "total_conversations": count,
                    "oldest": oldest,
                    "newest": newest,
                    "backend": "sqlite",
                }

        try:
            count = len(self._table.search().to_list())
            return {
                "total_conversations": count,
                "backend": "lancedb",
                "embedding_model": "all-MiniLM-L6-v2",
                "embedding_dim": EMBEDDING_DIM,
            }
        except Exception as e:
            logger.warning("Failed to get memory stats: %s", e)
            return {"total_conversations": 0, "backend": "lancedb", "error": str(e)}
