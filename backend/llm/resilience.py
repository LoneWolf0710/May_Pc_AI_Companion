"""May AI Resilience Layer — Retry, Fallback, Health, Queuing, Degradation.

P0: Auto-retry with exponential backoff on LLM failures
P1: Provider fallback chain (Ollama → cloud) when primary fails
P2: Health monitoring with service status checks
P3: Request queuing + timeout handling
P4: Graceful degradation (partial success > total failure)
"""

import asyncio
import logging
import time
import threading
from typing import AsyncGenerator, Any

logger = logging.getLogger("may.llm.resilience")

# ── P0: Retry with exponential backoff ────────────────────────────────────

MAX_RETRIES = 2  # Retry up to 2 times (3 total attempts)
BASE_DELAY = 0.5  # Initial delay in seconds
MAX_DELAY = 4.0   # Maximum delay cap
RATE_LIMIT_DELAY = 10.0  # Longer base delay for 429 rate limits
RETRYABLE_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def is_retryable_error(exc: Exception) -> bool:
    """Check if an exception is transient and worth retrying."""
    import httpx
    if isinstance(exc, RETRYABLE_ERRORS):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        # Retry on rate limit (429), server errors (5xx), but NOT client errors (4xx except 429)
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


def is_rate_limit_error(exc: Exception) -> bool:
    """Check if an exception is a rate limit (429) error."""
    import httpx
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


def _retry_delay(attempt: int, rate_limited: bool = False) -> float:
    """Calculate exponential backoff delay with jitter.

    Args:
        attempt: Current retry attempt (0-based).
        rate_limited: If True, use longer delays for 429 rate limits.
    """
    import random
    base = RATE_LIMIT_DELAY if rate_limited else BASE_DELAY
    cap = RATE_LIMIT_DELAY * 3 if rate_limited else MAX_DELAY
    delay = min(base * (2 ** attempt), cap)
    jitter = random.uniform(0, delay * 0.3)  # 30% jitter
    return delay + jitter


# ── P1: Provider fallback chain ───────────────────────────────────────────

# Default fallback order: try the user's selected provider first,
# then fall back through alternatives.
FALLBACK_CHAINS: dict[str, list[dict]] = {
    "ollama": [
        {"provider": "openrouter", "model": "qwen/qwen3-coder:free", "label": "OpenRouter (Qwen3 Coder Free)"},
    ],
    "openrouter": [
        {"provider": "ollama", "model": "qwen3:4b", "label": "Ollama (local)"},
    ],
    "openai": [
        {"provider": "openrouter", "model": "openai/gpt-4o-mini", "label": "OpenRouter (GPT-4o Mini)"},
    ],
    "anthropic": [
        {"provider": "openrouter", "model": "anthropic/claude-3.5-haiku", "label": "OpenRouter (Claude 3.5 Haiku)"},
    ],
    "gemini": [
        {"provider": "openrouter", "model": "google/gemini-2.0-flash", "label": "OpenRouter (Gemini 2.0 Flash)"},
    ],
    "google_ai_studio": [
        {"provider": "gemini", "model": "gemini-2.0-flash", "label": "Google Gemini (2.0 Flash)"},
        {"provider": "openrouter", "model": "google/gemini-2.0-flash", "label": "OpenRouter (Gemini 2.0 Flash)"},
    ],
    "ollama_cloud": [
        {"provider": "openrouter", "model": "qwen/qwen3-coder:free", "label": "OpenRouter (Qwen3 Coder Free)"},
    ],
}


def get_fallback_chain(provider: str) -> list[dict]:
    """Get the fallback chain for a provider."""
    return FALLBACK_CHAINS.get(provider, [])


# ── P2: Health monitoring ─────────────────────────────────────────────────

class HealthMonitor:
    """Tracks service health and provides status for /health/detailed."""

    def __init__(self):
        self._services: dict[str, dict] = {}
        self._lock = threading.Lock()
        # Register built-in services
        self.register("backend", "FastAPI Backend", critical=True)
        self.register("ollama", "Ollama LLM", critical=True)
        self.register("control_core", "Control Core Daemon", critical=False)
        self.register("stt", "Speech-to-Text (faster-whisper)", critical=False)
        self.register("memory", "Memory Store (LanceDB + SQLite)", critical=False)
        self.register("intelligence", "Intelligence Layer", critical=False)

    def register(self, name: str, display_name: str, critical: bool = False):
        """Register a service for health monitoring."""
        with self._lock:
            self._services[name] = {
                "name": name,
                "display_name": display_name,
                "critical": critical,
                "status": "unknown",
                "latency_ms": None,
                "last_check": None,
                "error": None,
            }

    def update(self, name: str, status: str, latency_ms: float = None, error: str = None):
        """Update a service's health status."""
        with self._lock:
            if name not in self._services:
                return
            self._services[name]["status"] = status
            self._services[name]["latency_ms"] = latency_ms
            self._services[name]["last_check"] = time.time()
            self._services[name]["error"] = error

    def get_status(self) -> dict:
        """Get full health status."""
        with self._lock:
            services = dict(self._services)
        healthy = sum(1 for s in services.values() if s["status"] == "healthy")
        total = len(services)
        return {
            "overall": "healthy" if healthy == total else "degraded" if healthy > 0 else "unhealthy",
            "healthy_count": healthy,
            "total_count": total,
            "services": services,
        }

    async def check_all(self):
        """Run health checks on all registered services."""
        import httpx
        import os as _os

        # Check backend (self) — use configurable URL
        backend_url = _os.environ.get("MAY_BACKEND_URL", "http://localhost:8080")
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{backend_url}/health")
                if r.status_code == 200:
                    self.update("backend", "healthy", (time.time() - t0) * 1000)
                else:
                    self.update("backend", "degraded", error=f"HTTP {r.status_code}")
        except Exception as e:
            self.update("backend", "unhealthy", error=str(e)[:100])

        # Check Ollama
        t0 = time.time()
        try:
            from llm.ollama_client import is_ollama_running
            ok = await is_ollama_running()
            if ok:
                self.update("ollama", "healthy", (time.time() - t0) * 1000)
            else:
                self.update("ollama", "unhealthy", error="Ollama not reachable")
        except Exception as e:
            self.update("ollama", "unhealthy", error=str(e)[:100])

        # Check Control Core daemon
        t0 = time.time()
        try:
            from core.client import is_daemon_running_sync
            ok = is_daemon_running_sync()
            if ok:
                self.update("control_core", "healthy", (time.time() - t0) * 1000)
            else:
                self.update("control_core", "unhealthy", error="Daemon not running")
        except ImportError:
            self.update("control_core", "unknown", error="core module not available")
        except Exception as e:
            self.update("control_core", "unhealthy", error=str(e)[:100])

        # Check memory store
        t0 = time.time()
        try:
            from memory.fact_store import FactStore
            fs = FactStore()
            fs.get_all_facts()  # Quick sanity check
            self.update("memory", "healthy", (time.time() - t0) * 1000)
        except Exception as e:
            self.update("memory", "unhealthy", error=str(e)[:100])

        # Check intelligence layer
        t0 = time.time()
        try:
            # Just check if the modules loaded — don't re-import heavy modules
            import importlib
            spec = importlib.util.find_spec("intelligence.shadow_learner")
            if spec:
                self.update("intelligence", "healthy", (time.time() - t0) * 1000)
            else:
                self.update("intelligence", "unknown", error="Intelligence module not found")
        except Exception as e:
            self.update("intelligence", "unknown", error=str(e)[:100])

        # Check STT (Speech-to-Text)
        t0 = time.time()
        try:
            import importlib
            spec = importlib.util.find_spec("voice.stt")
            if spec:
                self.update("stt", "healthy", (time.time() - t0) * 1000)
            else:
                self.update("stt", "unknown", error="STT module not found")
        except Exception as e:
            self.update("stt", "unknown", error=str(e)[:100])


# Singleton
_health_monitor = None
_health_lock = threading.Lock()


def get_health_monitor() -> HealthMonitor:
    """Get or create the singleton health monitor."""
    global _health_monitor
    if _health_monitor is None:
        with _health_lock:
            if _health_monitor is None:
                _health_monitor = HealthMonitor()
    return _health_monitor


# P3: Request queuing deferred — streaming endpoints don't work well
# with semaphore-based queues. Implement if non-streaming endpoints need it.


# ── P4: Graceful degradation helpers ──────────────────────────────────────

def format_partial_results(tool_results: list[str]) -> str:
    """Format partial tool execution results when some tools failed.

    Instead of failing completely, show which tools succeeded and which failed.
    """
    if not tool_results:
        return ""

    lines = []
    for r in tool_results:
        if r.startswith("Error:"):
            lines.append(f"⚠️ {r}")
        else:
            lines.append(f"✓ {r}")
    return "\n".join(lines)



