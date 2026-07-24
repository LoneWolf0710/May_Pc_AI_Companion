"""Tuner Cache — Shared gene value reader with in-memory caching.

Modules that read auto-tuner gene values (ollama_client, jarvis, conditioned_reflexes,
tool_tiering, vector_store, screen_watcher) all need to read from the same JSON state
file. Reading from disk on every LLM call adds ~1-5ms of latency.

This module provides a module-level cache with a 30-second TTL so that:
1. Gene values are read from disk at most once every 30 seconds
2. All modules share the same cached values (no duplicate reads)
3. The cache is thread-safe and asyncio-safe (reads are atomic)

Usage:
    from intelligence.tuner_cache import get_gene

    temperature = get_gene("temperature", default=0.7)
    num_ctx = get_gene("num_ctx", default=131072)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger("may.intelligence.tuner_cache")

# ── Cache configuration ──────────────────────────────────────────────────

_STATE_FILE = Path(os.path.expanduser("~")) / ".may" / "auto_tuner_state.json"
_CACHE_TTL = 30.0  # Re-read from disk at most once every 30 seconds

# In-memory cache
_cache: dict[str, float] = {}
_cache_timestamp: float = 0.0
_cache_lock = threading.Lock()


def _load_from_disk() -> dict[str, float]:
    """Read gene values from the auto-tuner state file.

    Returns a dict mapping gene name → current value.
    """
    if not _STATE_FILE.exists():
        return {}
    try:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        genes = {}
        for g in data.get("genes", []):
            name = g.get("name", "")
            value = g.get("value")
            if name and value is not None:
                genes[name] = float(value)
        return genes
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def _refresh_cache():
    """Reload gene values from disk into the in-memory cache."""
    global _cache, _cache_timestamp
    _cache = _load_from_disk()
    _cache_timestamp = time.time()


def get_gene(name: str, default: float = 0.0) -> float:
    """Get a gene value by name, with 30-second disk caching.

    This is the main entry point for all modules. It's fast (~0.01ms)
    because it reads from the in-memory cache, which is refreshed
    from disk at most once every 30 seconds.

    Args:
        name: Gene name (e.g. "temperature", "num_ctx", "reflex_threshold")
        default: Value to return if the gene is not found or the file is missing

    Returns:
        The current gene value, or the default if not found.
    """
    global _cache, _cache_timestamp

    now = time.time()

    # Fast path: cache is still valid
    if _cache and (now - _cache_timestamp) < _CACHE_TTL:
        return _cache.get(name, default)

    # Slow path: refresh from disk (once per 30s, thread-safe)
    with _cache_lock:
        # Double-check after acquiring lock (another thread may have refreshed)
        if _cache and (time.time() - _cache_timestamp) < _CACHE_TTL:
            return _cache.get(name, default)
        _refresh_cache()
        return _cache.get(name, default)


def get_genes() -> dict[str, float]:
    """Get all gene values as a dict. Useful for debugging/logging.

    Returns a snapshot of the current cached gene values.
    """
    global _cache, _cache_timestamp

    now = time.time()
    if not _cache or (now - _cache_timestamp) >= _CACHE_TTL:
        with _cache_lock:
            if not _cache or (time.time() - _cache_timestamp) >= _CACHE_TTL:
                _refresh_cache()
    return dict(_cache)  # Return a copy


def invalidate_cache():
    """Force a cache refresh on the next get_gene() call.

    Call this after auto-tuner mutations are applied so modules
    see the updated values immediately.
    """
    global _cache_timestamp
    _cache_timestamp = 0.0
    logger.debug("Tuner cache invalidated — will refresh on next read")
