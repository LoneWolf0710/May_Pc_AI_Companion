"""OpenTelemetry Tracing — Lightweight signal tracing across brain regions.

Per MAY_FINAL_ARCHITECTURE.md Part 9 (Tracing):

    tracer = trace.get_tracer("may.brain")

    async def process_signal(signal):
        with tracer.start_as_current_span("thalamus.route") as span:
            span.set_attribute("signal.type", signal.type)
            result = await self._send_to(target, signal)
            span.set_attribute("latency_ms", result.latency_ms)

A bad response can now be traced through exactly which regions touched it.

This module provides a lightweight tracing implementation that works
with or without OpenTelemetry installed. When opentelemetry is not
available, it falls back to structured logging.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger("may.system.tracing")

# Try to import OpenTelemetry
_HAS_OTEL = False
tracer = None

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
    _HAS_OTEL = True
except ImportError:
    pass


def init_tracing(service_name: str = "may.brain") -> bool:
    """Initialize OpenTelemetry tracing.

    Falls back to structured logging if opentelemetry is not installed.

    Returns:
        True if OpenTelemetry was initialized, False if using fallback.
    """
    global tracer

    if _HAS_OTEL:
        try:
            provider = TracerProvider()
            processor = BatchSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)
            tracer = trace.get_tracer(service_name)
            logger.info("OpenTelemetry tracing initialized")
            return True
        except Exception as e:
            logger.warning("OpenTelemetry init failed, using fallback: %s", e)

    # Fallback: use structured logging
    tracer = _LoggingTracer()
    logger.info("Using structured logging tracer (opentelemetry not installed)")
    return False


class _LoggingTracer:
    """Fallback tracer that uses structured logging when OpenTelemetry is not available."""

    @contextmanager
    def start_as_current_span(self, name: str, attributes: dict | None = None):
        """Create a span using structured logging."""
        span = _LoggingSpan(name, attributes or {})
        try:
            yield span
        finally:
            span._finish()


class _LoggingSpan:
    """A span that logs to structured logging."""

    def __init__(self, name: str, attributes: dict):
        self.name = name
        self._start = time.time()
        self._attributes = attributes
        self._events: list[dict] = []

    def set_attribute(self, key: str, value: Any):
        """Set a span attribute."""
        self._attributes[key] = value

    def add_event(self, name: str, attributes: dict | None = None):
        """Add an event to the span."""
        self._events.append({"name": name, "attributes": attributes or {}})

    def set_status(self, status):
        """Set span status (no-op for logging tracer)."""
        pass

    def _finish(self):
        """Log the completed span."""
        duration_ms = (time.time() - self._start) * 1000
        logger.debug(
            "Span %s completed in %.1fms | attrs=%s | events=%d",
            self.name, duration_ms, self._attributes, len(self._events),
        )


# ── Convenience wrappers for May's brain regions ─────────────────────────

def trace_signal(signal_type: str, target: str = ""):
    """Trace a signal through the brain (Thalamus routing)."""
    if tracer is None:
        init_tracing()
    return tracer.start_as_current_span(
        "thalamus.route",
        attributes={"signal.type": signal_type, "target": target},
    )


def trace_region(region_name: str):
    """Trace processing in a brain region (Prefrontal, Wernicke's, etc.)."""
    if tracer is None:
        init_tracing()
    return tracer.start_as_current_span(f"region.{region_name}")


def trace_tool_execution(tool_name: str, params: dict | None = None):
    """Trace a tool execution through the Cerebellum."""
    if tracer is None:
        init_tracing()
    return tracer.start_as_current_span(
        "cerebellum.execute",
        attributes={"tool": tool_name, "params": str(params or {})[:200]},
    )


def trace_memory_operation(operation: str, query: str = ""):
    """Trace a memory operation (Hippocampus)."""
    if tracer is None:
        init_tracing()
    return tracer.start_as_current_span(
        f"hippocampus.{operation}",
        attributes={"query": query[:100]},
    )


def trace_llm_call(provider: str, model: str, tool_count: int = 0):
    """Trace an LLM API call."""
    if tracer is None:
        init_tracing()
    return tracer.start_as_current_span(
        "prefrontal.llm_call",
        attributes={"provider": provider, "model": model, "tool_count": tool_count},
    )


def trace_voice_pipeline(stage: str):
    """Trace a voice pipeline stage (VAD, STT, TTS)."""
    if tracer is None:
        init_tracing()
    return tracer.start_as_current_span(f"voice.{stage}")


def get_trace_stats() -> dict:
    """Get tracing status."""
    return {
        "backend": "opentelemetry" if _HAS_OTEL and isinstance(tracer, trace.Tracer) else "structured_logging",
        "otel_available": _HAS_OTEL,
        "initialized": tracer is not None,
    }
