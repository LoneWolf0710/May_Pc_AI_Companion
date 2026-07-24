"""Conditioned Reflexes — Embedding-based learned responses for May.

From MAY_FINAL_ARCHITECTURE.md Part 2:
    Conditioned Reflexes (Learned from Repetition, <5ms)
    Embedding-based matching using sentence-transformers centroids.
    Learns from 3+ repeated brain responses. Fires in <5ms without LLM.

How new reflexes form:
    1. User says "open Chrome" → Brain processes → Opens Chrome (full LLM call)
    2. User says "open Chrome" → Brain processes → Opens Chrome (full LLM call)
    3. User says "open Chrome" → Brain processes → Opens Chrome (full LLM call)
    4. Pattern recognized (3+ repetitions) → Creates CONDITIONED REFLEX via embedding centroid
    5. User says "open Chrome" → Reflex arc fires → Opens Chrome (5ms, no LLM)

This module uses the same sentence-transformers model (all-MiniLM-L6-v2) that
vector_store.py already uses, so there's no additional VRAM cost.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from intelligence.tuner_cache import get_gene

logger = logging.getLogger("may.intelligence.conditioned_reflexes")

# Lazy imports — heavy ML dependencies
_model = None
_SentenceTransformer = None


def _ensure_model():
    """Lazy-load sentence-transformers model (shared with vector_store.py)."""
    global _model, _SentenceTransformer
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _SentenceTransformer = SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for conditioned reflexes. "
                "Install with: pip install sentence-transformers"
            )
    return _model


# ── Configuration ───────────────────────────────────────────────────────────
# P5: Default values — overridden by auto-tuner genes at runtime via tuner_cache
DEFAULT_SIMILARITY_THRESHOLD = 0.82
DEFAULT_MIN_EXAMPLES_TO_LEARN = 3
DEFAULT_MAX_REFLEXES = 200
LEARNING_RATE = 0.1          # How fast the centroid moves toward new examples
PERSISTENCE_DIR = Path.home() / ".may" / "reflexes"


@dataclass
class Reflex:
    """A single conditioned reflex — maps similar inputs to a tool call."""
    id: str = ""
    centroid: list[float] = field(default_factory=list)  # Embedding centroid (384-dim)
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    confidence: float = 0.0
    use_count: int = 0
    example_count: int = 0
    examples: list[str] = field(default_factory=list)  # Original training examples
    created_at: float = 0.0
    last_used: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "confidence": round(self.confidence, 3),
            "use_count": self.use_count,
            "example_count": self.example_count,
            "examples": self.examples[:5],
            "created_at": self.created_at,
            "last_used": self.last_used,
        }


@dataclass
class ReflexMatch:
    """Result of a reflex check."""
    matched: bool = False
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    confidence: float = 0.0
    reflex_id: str = ""


class ConditionedReflexes:
    """Embedding-based learned reflexes.

    Maintains a list of learned reflexes (embedding centroid + action).
    Checks incoming messages against learned reflexes via cosine similarity.
    Learns new reflexes after 3+ repetitions of the same action.

    Usage:
        reflexes = ConditionedReflexes()

        # Check if a message matches a learned reflex
        result = reflexes.check("open chrome")
        if result.matched:
            # Execute directly — skip the LLM!
            return execute_tool(result.tool_name, result.tool_args)

        # After LLM executes the tool, record what happened
        reflexes.record_example("open chrome", "open_app", {"app_name": "chrome"})
    """

    def __init__(self):
        self._reflexes: list[Reflex] = []
        self._pending_examples: dict[str, list[dict]] = {}  # hash → [{text, tool, args}]
        self._record_count: int = 0  # Counter for throttling stale cleanup
        self._load_persistence()

    def check(self, message: str) -> ReflexMatch:
        """Check if a message matches any learned reflex.

        Uses cosine similarity between the message embedding and each
        reflex centroid. Returns the best match above the threshold.

        Performance: <5ms for up to 200 reflexes (embedding ~2ms + cosine ~0.1ms each).
        """
        if not self._reflexes or not message.strip():
            return ReflexMatch()

        try:
            model = _ensure_model()
        except ImportError:
            return ReflexMatch()

        try:
            # Embed the query message
            query_embedding = model.encode(message, normalize_embeddings=True)

            # P5: Read threshold from auto-tuner gene
            threshold = get_gene("reflex_threshold", default=DEFAULT_SIMILARITY_THRESHOLD)

            best_match = ReflexMatch()
            best_similarity = 0.0

            for reflex in self._reflexes:
                if not reflex.centroid:
                    continue
                centroid = np.array(reflex.centroid, dtype=np.float32)
                similarity = float(np.dot(query_embedding, centroid))

                if similarity > threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = ReflexMatch(
                        matched=True,
                        tool_name=reflex.tool_name,
                        tool_args=dict(reflex.tool_args),
                        confidence=similarity,
                        reflex_id=reflex.id,
                    )

            if best_match.matched:
                # Update usage stats
                for reflex in self._reflexes:
                    if reflex.id == best_match.reflex_id:
                        reflex.use_count += 1
                        reflex.last_used = time.time()
                        reflex.confidence = best_similarity
                        break
                logger.info(
                    "Reflex match: %s (%.3f) → %s",
                    message[:40], best_similarity, best_match.tool_name,
                )

            return best_match

        except Exception as e:
            logger.debug("Reflex check failed: %s", e)
            return ReflexMatch()

    def record_example(
        self,
        message: str,
        tool_name: str,
        tool_args: dict | None = None,
    ):
        """Record that a tool was executed for a given message.

        After MIN_EXAMPLE_TO_LEARN repetitions with the same tool/args,
        a new conditioned reflex is created.

        Args:
            message: The user's message that triggered the tool.
            tool_name: The tool that was executed.
            tool_args: The arguments passed to the tool.
        """
        if not message.strip() or not tool_name:
            return

        tool_args = tool_args or {}

        now = time.time()
        self._record_count += 1

        # P4: Cleanup stale pending entries every 50 calls (older than 24h)
        if self._record_count % 50 == 0 and self._pending_examples:
            stale_keys = [
                k for k, v in self._pending_examples.items()
                if v and (now - v[-1].get("timestamp", 0)) > 86400
            ]
            for k in stale_keys:
                del self._pending_examples[k]

        # Create a key from the tool name + sorted args (same tool+args = same reflex)
        key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"

        if key not in self._pending_examples:
            self._pending_examples[key] = []

        examples = self._pending_examples[key]

        # Check for duplicate messages (don't count same exact text twice)
        existing_texts = {ex["text"] for ex in examples}
        if message.strip() in existing_texts:
            return

        examples.append({
            "text": message.strip(),
            "tool_name": tool_name,
            "tool_args": tool_args,
            "timestamp": now,
        })

        # P5: Read min_examples from auto-tuner gene
        min_examples = int(get_gene("reflex_min_examples", default=DEFAULT_MIN_EXAMPLES_TO_LEARN))

        # Check if we should create a new reflex
        if len(examples) >= min_examples:
            self._learn_reflex(key, examples)

    def _learn_reflex(self, key: str, examples: list[dict]):
        """Create a new conditioned reflex from accumulated examples.

        Computes the centroid (average embedding) of all examples and stores
        the reflex for future matching.
        """
        try:
            model = _ensure_model()
        except ImportError:
            return

        # Check if we already have a reflex for this key
        tool_name = examples[0]["tool_name"]
        tool_args = examples[0]["tool_args"]

        for existing in self._reflexes:
            if existing.tool_name == tool_name and existing.tool_args == tool_args:
                # Already have this reflex — update centroid with new examples
                self._update_centroid(existing, examples, model)
                return

        # Compute embedding centroid
        texts = [ex["text"] for ex in examples]
        embeddings = model.encode(texts, normalize_embeddings=True)
        centroid = embeddings.mean(axis=0)
        # Re-normalize the centroid
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm

        # Create new reflex
        reflex = Reflex(
            id=f"reflex_{int(time.time() * 1000)}",
            centroid=centroid.tolist(),
            tool_name=tool_name,
            tool_args=tool_args,
            confidence=DEFAULT_SIMILARITY_THRESHOLD,
            use_count=0,
            example_count=len(examples),
            examples=texts,
            created_at=time.time(),
            last_used=0,
        )

        self._reflexes.append(reflex)

        # P5: Read max_count from auto-tuner gene
        max_count = int(get_gene("reflex_max_count", default=DEFAULT_MAX_REFLEXES))

        # Evict oldest reflexes if we exceed the limit
        if len(self._reflexes) > max_count:
            self._reflexes.sort(key=lambda r: r.last_used or r.created_at)
            self._reflexes = self._reflexes[-max_count:]

        logger.info(
            "New conditioned reflex learned: '%s' → %s(%s) [%d examples]",
            texts[0][:40], tool_name, json.dumps(tool_args)[:40], len(examples),
        )

        # Persist to disk
        self._save_persistence()

        # Clear pending examples for this key
        self._pending_examples.pop(key, None)

    def _update_centroid(self, reflex: Reflex, examples: list[dict], model):
        """Update an existing reflex centroid with new examples (online learning)."""
        try:
            new_texts = [ex["text"] for ex in examples if ex["text"] not in reflex.examples]
            if not new_texts:
                return

            new_embeddings = model.encode(new_texts, normalize_embeddings=True)
            new_centroid = new_embeddings.mean(axis=0)

            # Blend: old centroid + learning_rate * new centroid
            old_centroid = np.array(reflex.centroid, dtype=np.float32)
            blended = old_centroid * (1 - LEARNING_RATE) + new_centroid * LEARNING_RATE
            # Re-normalize
            norm = np.linalg.norm(blended)
            if norm > 0:
                blended = blended / norm

            reflex.centroid = blended.tolist()
            reflex.example_count += len(new_texts)
            reflex.examples.extend(new_texts)
            reflex.examples = reflex.examples[:20]  # Cap stored examples

            logger.debug(
                "Updated reflex centroid: %s [%d examples total]",
                reflex.tool_name, reflex.example_count,
            )
            self._save_persistence()

        except Exception as e:
            logger.debug("Centroid update failed: %s", e)

    def get_reflexes(self) -> list[dict]:
        """Get all stored reflexes as dicts."""
        return [r.to_dict() for r in self._reflexes]

    def clear(self):
        """Clear all reflexes and pending examples."""
        self._reflexes.clear()
        self._pending_examples.clear()
        self._save_persistence()
        logger.info("All conditioned reflexes cleared")

    def _save_persistence(self):
        """Save reflexes to disk."""
        try:
            PERSISTENCE_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "reflexes": [
                    {
                        "id": r.id,
                        "centroid": r.centroid,
                        "tool_name": r.tool_name,
                        "tool_args": r.tool_args,
                        "confidence": r.confidence,
                        "use_count": r.use_count,
                        "example_count": r.example_count,
                        "examples": r.examples,
                        "created_at": r.created_at,
                        "last_used": r.last_used,
                    }
                    for r in self._reflexes
                ],
                "saved_at": time.time(),
            }
            path = PERSISTENCE_DIR / "conditioned_reflexes.json"
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.debug("Saved %d reflexes to disk", len(self._reflexes))
        except Exception as e:
            logger.debug("Failed to save reflexes: %s", e)

    def _load_persistence(self):
        """Load reflexes from disk."""
        path = PERSISTENCE_DIR / "conditioned_reflexes.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for r in data.get("reflexes", []):
                reflex = Reflex(
                    id=r.get("id", ""),
                    centroid=r.get("centroid", []),
                    tool_name=r.get("tool_name", ""),
                    tool_args=r.get("tool_args", {}),
                    confidence=r.get("confidence", 0),
                    use_count=r.get("use_count", 0),
                    example_count=r.get("example_count", 0),
                    examples=r.get("examples", []),
                    created_at=r.get("created_at", 0),
                    last_used=r.get("last_used", 0),
                )
                if reflex.centroid and reflex.tool_name:
                    self._reflexes.append(reflex)
            logger.info("Loaded %d conditioned reflexes from disk", len(self._reflexes))
        except Exception as e:
            logger.debug("Failed to load reflexes: %s", e)

    def get_stats(self) -> dict:
        """Get reflex statistics."""
        total_uses = sum(r.use_count for r in self._reflexes)
        return {
            "total_reflexes": len(self._reflexes),
            "total_uses": total_uses,
            "pending_groups": len(self._pending_examples),
            "pending_examples": sum(len(v) for v in self._pending_examples.values()),
            "threshold": get_gene("reflex_threshold", default=DEFAULT_SIMILARITY_THRESHOLD),
            "min_examples": int(get_gene("reflex_min_examples", default=DEFAULT_MIN_EXAMPLES_TO_LEARN)),
        }


# ── Singleton ────────────────────────────────────────────────────────────────

_instance: ConditionedReflexes | None = None


def get_conditioned_reflexes() -> ConditionedReflexes:
    """Get or create the singleton conditioned reflexes instance."""
    global _instance
    if _instance is None:
        _instance = ConditionedReflexes()
    return _instance
