"""Internet Learning — May learns from web searches with user approval.

From MAY_FINAL_ARCHITECTURE.md P5:
  Internet learning (user-gated) — May learns from web searches, user approves knowledge.

Design:
  1. User asks a question that needs web research
  2. May searches the web via the existing web_search tool
  3. Extracts key facts from search results
  4. Presents facts to user for approval
  5. User approves → facts stored in long-term memory (VectorStore + FactStore)
  6. User rejects → facts discarded

This module manages the learning pipeline:
  - extract_knowledge(): Parse search results into structured knowledge
  - approve_knowledge(): Store approved knowledge in memory
  - get_pending_knowledge(): Show pending knowledge for user approval
  - get_learned_knowledge(): Show recently learned knowledge
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("may.intelligence.internet_learning")

# Persistence
_LEARNING_DIR = Path(os.path.expanduser("~")) / ".may" / "learning"
_PENDING_FILE = _LEARNING_DIR / "pending.json"
_LEARNED_FILE = _LEARNING_DIR / "learned.json"

# Max pending items before auto-cleanup
_MAX_PENDING = 50
_MAX_LEARNED = 500


@dataclass
class KnowledgeItem:
    """A piece of knowledge extracted from web search results."""
    id: str = ""
    query: str = ""  # Original search query
    source: str = ""  # URL or description of source
    facts: list[str] = field(default_factory=list)  # Extracted facts
    confidence: float = 0.5  # Confidence in accuracy (0-1)
    timestamp: float = 0
    approved: bool = False
    rejected: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "query": self.query,
            "source": self.source,
            "facts": self.facts,
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp,
            "approved": self.approved,
            "rejected": self.rejected,
        }

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeItem:
        return cls(
            id=data.get("id", ""),
            query=data.get("query", ""),
            source=data.get("source", ""),
            facts=data.get("facts", []),
            confidence=data.get("confidence", 0.5),
            timestamp=data.get("timestamp", 0),
            approved=data.get("approved", False),
            rejected=data.get("rejected", False),
        )


class InternetLearner:
    """Manages May's internet learning pipeline.

    Extracts knowledge from web search results, presents it to the user
    for approval, and stores approved knowledge in long-term memory.

    Usage:
        learner = InternetLearner()

        # After a web search, extract knowledge
        item = learner.extract_knowledge(query, search_results)

        # User approves
        learner.approve_knowledge(item.id, fact_store, vector_store)

        # Or user rejects
        learner.reject_knowledge(item.id)
    """

    def __init__(self):
        self._pending: list[KnowledgeItem] = []
        self._learned: list[KnowledgeItem] = []
        self._load_state()

    def _load_state(self):
        """Load pending and learned knowledge from disk."""
        try:
            if _PENDING_FILE.exists():
                data = json.loads(_PENDING_FILE.read_text(encoding="utf-8"))
                self._pending = [KnowledgeItem.from_dict(item) for item in data]
            if _LEARNED_FILE.exists():
                data = json.loads(_LEARNED_FILE.read_text(encoding="utf-8"))
                self._learned = [KnowledgeItem.from_dict(item) for item in data[-_MAX_LEARNED:]]
            logger.info("Internet learner loaded: %d pending, %d learned", len(self._pending), len(self._learned))
        except Exception as e:
            logger.debug("Failed to load internet learner state: %s", e)

    def _save_state(self):
        """Persist state to disk."""
        try:
            _LEARNING_DIR.mkdir(parents=True, exist_ok=True)
            _PENDING_FILE.write_text(
                json.dumps([item.to_dict() for item in self._pending[-_MAX_PENDING:]], indent=2),
                encoding="utf-8",
            )
            _LEARNED_FILE.write_text(
                json.dumps([item.to_dict() for item in self._learned[-_MAX_LEARNED:]], indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.debug("Failed to save internet learner state: %s", e)

    def extract_knowledge(self, query: str, search_results: list[dict]) -> KnowledgeItem:
        """Extract knowledge items from web search results.

        Args:
            query: The original search query.
            search_results: List of search result dicts with 'title', 'snippet', 'url'.

        Returns:
            KnowledgeItem with extracted facts.
        """
        import hashlib

        # Generate a unique ID
        item_id = hashlib.sha256(f"{query}:{time.time()}".encode()).hexdigest()[:12]

        facts = []
        sources = []

        for result in search_results[:5]:  # Top 5 results
            title = result.get("title", "")
            snippet = result.get("snippet", result.get("description", ""))
            url = result.get("url", "")

            if title:
                facts.append(f"Source: {title}")
            if snippet:
                # Clean up snippet
                snippet_clean = snippet.strip()
                if len(snippet_clean) > 50:  # Only substantial snippets
                    facts.append(snippet_clean)
            if url:
                sources.append(url)

        # Deduplicate facts
        seen = set()
        unique_facts = []
        for fact in facts:
            if fact not in seen:
                seen.add(fact)
                unique_facts.append(fact)

        item = KnowledgeItem(
            id=item_id,
            query=query,
            source=sources[0] if sources else "",
            facts=unique_facts[:10],  # Cap at 10 facts
            confidence=min(0.8, len(unique_facts) * 0.15),  # More facts = higher confidence
            timestamp=time.time(),
        )

        self._pending.append(item)
        self._save_state()

        logger.info("Extracted %d facts for query '%s' (id=%s)", len(item.facts), query[:50], item_id)
        return item

    def approve_knowledge(self, item_id: str, fact_store=None, vector_store=None) -> bool:
        """Approve a knowledge item and store it in long-term memory.

        Args:
            item_id: The ID of the knowledge item to approve.
            fact_store: Optional FactStore instance for structured facts.
            vector_store: Optional VectorStore instance for semantic memory.

        Returns:
            True if approved and stored, False if not found.
        """
        item = self._find_pending(item_id)
        if item is None:
            return False

        item.approved = True
        self._learned.append(item)
        self._pending = [p for p in self._pending if p.id != item_id]

        # Store in fact store (structured memory)
        if fact_store is not None:
            for i, fact in enumerate(item.facts):
                if not fact.startswith("Source:"):
                    fact_store.set_fact(
                        key=f"learned_{item_id}_{i}",
                        value=fact,
                        category="internet_learned",
                    )

        # Store in vector store (semantic memory) — best effort
        if vector_store is not None and item.facts:
            try:
                summary = f"Learned from web search '{item.query}': " + "; ".join(
                    f for f in item.facts if not f.startswith("Source:")
                )[:500]
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        vector_store.store_conversation(
                            summary=summary,
                            messages=[{"role": "user", "content": item.query}],
                            topic="internet_learned",
                        )
                    )
                except RuntimeError:
                    pass  # No event loop running — skip vector store storage
            except Exception as e:
                logger.debug("Failed to store in vector store: %s", e)

        self._save_state()
        logger.info("Approved knowledge: %d facts for '%s'", len(item.facts), item.query[:50])
        return True

    def reject_knowledge(self, item_id: str) -> bool:
        """Reject a knowledge item (discard it).

        Args:
            item_id: The ID of the knowledge item to reject.

        Returns:
            True if rejected, False if not found.
        """
        item = self._find_pending(item_id)
        if item is None:
            return False

        item.rejected = True
        self._pending = [p for p in self._pending if p.id != item_id]
        self._save_state()

        logger.info("Rejected knowledge for '%s'", item.query[:50])
        return True

    def get_pending_knowledge(self) -> list[dict]:
        """Get all pending knowledge items awaiting user approval."""
        return [item.to_dict() for item in self._pending]

    def get_learned_knowledge(self, limit: int = 20) -> list[dict]:
        """Get recently learned knowledge items."""
        return [item.to_dict() for item in self._learned[-limit:]]

    def get_stats(self) -> dict:
        """Get internet learning statistics."""
        return {
            "pending_count": len(self._pending),
            "learned_count": len(self._learned),
            "total_facts_learned": sum(len(item.facts) for item in self._learned),
            "recent_queries": [item.query for item in self._learned[-5:]],
        }

    def clear_pending(self):
        """Clear all pending knowledge items."""
        self._pending = []
        self._save_state()

    def clear_learned(self):
        """Clear all learned knowledge."""
        self._learned = []
        self._save_state()

    def _find_pending(self, item_id: str) -> KnowledgeItem | None:
        """Find a pending knowledge item by ID."""
        for item in self._pending:
            if item.id == item_id:
                return item
        return None


# Lazy singleton
_internet_learner = None


def get_internet_learner() -> InternetLearner:
    """Get the singleton InternetLearner instance."""
    global _internet_learner
    if _internet_learner is None:
        _internet_learner = InternetLearner()
    return _internet_learner
