"""
Streaming Speech-to-Text — processes audio in 100ms chunks.

Replaces the fixed 5-second recording approach with real-time streaming:
1. Browser captures 100ms PCM chunks via AudioWorkletNode
2. Chunks are base64-encoded and sent to /voice/stream-chunks
3. Backend accumulates chunks and transcribes on voice activity boundaries
4. Uses Silero VAD to detect speech start/end (optional, falls back to silence detection)

Architecture spec: Tier 1 voice — 100ms chunks, <1s end-to-end latency.
"""

from __future__ import annotations

import asyncio
import io
import logging
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Callable

logger = logging.getLogger("may.voice.streaming_stt")

# Constants
STREAM_SAMPLE_RATE = 16000
STREAM_CHANNELS = 1
CHUNK_DURATION_MS = 100  # 100ms per chunk
CHUNK_SAMPLES = int(STREAM_SAMPLE_RATE * CHUNK_DURATION_MS / 1000)  # 1600 samples
SILENCE_THRESHOLD = 0.01  # RMS threshold for silence detection
SILENCE_TIMEOUT_MS = 800  # Stop transcribing after 800ms of silence
MAX_SPEECH_SECONDS = 30  # Maximum speech segment before forced transcription


class StreamState(str, Enum):
    """Current state of the streaming STT pipeline."""
    IDLE = "idle"          # No active stream
    LISTENING = "listening"  # Actively capturing audio
    SPEAKING = "speaking"    # Voice detected, accumulating speech
    TRANSCRIBING = "transcribing"  # Speech ended, transcribing buffer


@dataclass
class StreamChunk:
    """A single audio chunk from the browser."""
    audio_b64: str       # Base64-encoded PCM int16 audio
    timestamp: float     # Time.time() when chunk was received
    chunk_index: int     # Sequential chunk number


@dataclass
class StreamSession:
    """Manages a single streaming STT session."""
    session_id: str
    state: StreamState = StreamState.IDLE
    chunks: list[StreamChunk] = field(default_factory=list)
    audio_buffer: bytearray = field(default_factory=bytearray)
    speech_start_time: float = 0.0
    last_voice_time: float = 0.0
    total_speech_duration: float = 0.0
    created_at: float = field(default_factory=time.time)
    partial_text: str = ""  # Running transcript from incremental transcription

    def reset(self):
        """Reset the session for reuse."""
        self.chunks.clear()
        self.audio_buffer.clear()
        self.speech_start_time = 0.0
        self.last_voice_time = 0.0
        self.total_speech_duration = 0.0
        self.partial_text = ""


class StreamingSTT:
    """Streaming speech-to-text with 100ms chunk processing.

    Uses Silero VAD (when available) for ML-based voice activity detection
    instead of simple RMS thresholding.

    Usage:
        stt = StreamingSTT()

        # Process a chunk from browser
        result = await stt.process_chunk(session, chunk_b64, chunk_index)

        # Force finalize (end of speech)
        result = await stt.finalize(session)
    """

    def __init__(self):
        self._stt_instance = None  # Will be set via set_stt() from main.py
        self._sessions: dict[str, StreamSession] = {}
        self._silence_threshold = SILENCE_THRESHOLD
        self._silence_timeout_ms = SILENCE_TIMEOUT_MS
        # P5: Silero VAD instance (lazy-loaded)
        self._vad = None  # Initialized on first use via _ensure_vad()

    def _ensure_vad(self):
        """P5: Lazily initialize Silero VAD for ML-based voice detection."""
        if self._vad is None:
            try:
                from voice.vad import get_vad
                self._vad = get_vad()
                if self._vad.is_available():
                    logger.info("Streaming STT: Silero VAD enabled")
                else:
                    logger.info("Streaming STT: Silero VAD not available, using RMS fallback")
                    self._vad = None
            except Exception as e:
                logger.debug("VAD not available: %s", e)

    def set_stt(self, stt_instance):
        """Set the underlying faster-whisper STT instance for transcription."""
        self._stt_instance = stt_instance
        self._ensure_vad()

    def create_session(self, session_id: str | None = None) -> StreamSession:
        """Create a new streaming session."""
        if session_id is None:
            session_id = f"stream_{int(time.time() * 1000)}"
        session = StreamSession(session_id=session_id, state=StreamState.LISTENING)
        self._sessions[session_id] = session
        # P5: Reset VAD state for new session
        if self._vad is not None:
            self._vad.reset()
        logger.info("Created streaming session: %s", session_id)
        return session

    def get_session(self, session_id: str) -> StreamSession | None:
        """Get an existing session by ID."""
        return self._sessions.get(session_id)

    async def process_chunk(
        self,
        session: StreamSession,
        audio_b64: str,
        chunk_index: int,
    ) -> dict:
        """Process a single 100ms audio chunk.

        Args:
            session: Active streaming session
            audio_b64: Base64-encoded PCM int16 audio (16kHz mono)
            chunk_index: Sequential chunk number

        Returns:
            dict with 'state', 'partial_text', 'speech_duration'
        """
        import base64

        chunk = StreamChunk(
            audio_b64=audio_b64,
            timestamp=time.time(),
            chunk_index=chunk_index,
        )
        session.chunks.append(chunk)

        # Decode base64 PCM int16 → bytes → append to buffer
        try:
            pcm_bytes = base64.b64decode(audio_b64)
            session.audio_buffer.extend(pcm_bytes)
        except Exception as e:
            logger.warning("Failed to decode chunk %d: %s", chunk_index, e)
            return {
                "state": session.state.value,
                "partial_text": session.partial_text,
                "speech_duration": session.total_speech_duration,
            }

        # P5: Use Silero VAD if available, otherwise fall back to RMS
        if self._vad is not None and self._vad.is_available():
            vad_result = self._vad.process_chunk(pcm_bytes)
            is_voice = vad_result["is_speech"]
        else:
            # Fallback: simple RMS-based detection
            rms = self._compute_rms(pcm_bytes)
            is_voice = rms > self._silence_threshold

        if is_voice:
            # Voice detected
            if session.state == StreamState.LISTENING:
                session.state = StreamState.SPEAKING
                session.speech_start_time = time.time()
                logger.info("Voice detected — starting speech accumulation")

            session.last_voice_time = time.time()
            session.total_speech_duration += CHUNK_DURATION_MS / 1000.0

            # Force finalize if speech exceeds max duration
            if session.total_speech_duration >= MAX_SPEECH_SECONDS:
                logger.info("Max speech duration reached — transcribing")
                return await self._transcribe_buffer(session, force=True)

        else:
            # Silence
            if session.state == StreamState.SPEAKING:
                silence_elapsed_ms = (time.time() - session.last_voice_time) * 1000
                if silence_elapsed_ms >= self._silence_timeout_ms:
                    # Speech ended — transcribe the buffer
                    logger.info(
                        "Silence detected after %.1fs of speech — transcribing",
                        session.total_speech_duration,
                    )
                    return await self._transcribe_buffer(session, force=True)

        return {
            "state": session.state.value,
            "partial_text": session.partial_text,
            "speech_duration": session.total_speech_duration,
        }

    async def finalize(self, session: StreamSession) -> dict:
        """Force-finalize the session — transcribe whatever we have.

        Called when the user releases the mic button.
        """
        if session.state == StreamState.IDLE:
            return {"text": "", "language": None, "duration": 0}

        return await self._transcribe_buffer(session, force=True)

    async def cancel_session(self, session: StreamSession) -> None:
        """Cancel an active session without transcribing."""
        session.state = StreamState.IDLE
        logger.info("Cancelled streaming session: %s", session.session_id)

    async def _transcribe_buffer(
        self,
        session: StreamSession,
        force: bool = False,
    ) -> dict:
        """Transcribe the accumulated audio buffer."""
        if not self._stt_instance:
            logger.error("No STT instance configured")
            session.state = StreamState.IDLE
            return {"text": "", "language": None, "duration": 0}

        session.state = StreamState.TRANSCRIBING

        # Convert buffer to numpy float32
        import numpy as np

        pcm_bytes = bytes(session.audio_buffer)
        if len(pcm_bytes) < 320:  # Less than 10ms of audio
            session.state = StreamState.IDLE
            return {"text": "", "language": None, "duration": 0}

        # int16 PCM → float32 normalized
        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        t0 = time.time()
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._stt_instance.transcribe_audio(samples),
            )
        except Exception as e:
            logger.error("Streaming transcription failed: %s", e)
            session.state = StreamState.IDLE
            return {"text": "", "language": None, "duration": 0, "error": str(e)}

        elapsed = time.time() - t0
        text = result.get("text", "").strip()

        # P5: Apply stt_confidence_threshold — discard transcriptions that
        # are likely noise (very short text relative to speech duration).
        # Higher threshold = stricter filtering = fewer false positives.
        if text and session.total_speech_duration > 0.5:
            try:
                from intelligence.tuner_cache import get_gene
                conf_threshold = float(get_gene("stt_confidence_threshold", default=0.5))
                # Heuristic: chars-per-second ratio. Normal speech ~8-15 chars/sec.
                # Below threshold * 4 chars/sec = likely noise.
                chars_per_sec = len(text) / session.total_speech_duration
                min_cps = conf_threshold * 4.0  # e.g., 0.5 * 4 = 2.0 chars/sec
                if chars_per_sec < min_cps:
                    logger.info(
                        "STT confidence too low (%.1f chars/sec < %.1f threshold) — discarding: '%s'",
                        chars_per_sec, min_cps, text[:40],
                    )
                    text = ""
            except Exception:
                pass  # If tuner_cache unavailable, accept all transcriptions

        logger.info(
            "Streaming transcription: %.1fs speech → %.3fs processing, text=%s",
            session.total_speech_duration,
            elapsed,
            text[:80] if text else "(empty)",
        )

        # Clean up
        session.state = StreamState.IDLE
        session.partial_text = text

        return {
            "text": text,
            "language": result.get("language"),
            "duration": session.total_speech_duration,
            "processing_time": elapsed,
        }

    def _compute_rms(self, pcm_bytes: bytes) -> float:
        """Compute RMS energy of PCM int16 audio chunk using numpy for performance."""
        import numpy as np

        if len(pcm_bytes) < 2:
            return 0.0

        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        rms = float(np.sqrt(np.mean(samples ** 2)))

        # Normalize to 0.0-1.0 range (int16 max = 32768)
        return rms / 32768.0

    def get_active_sessions(self) -> list[str]:
        """Return IDs of all active sessions."""
        return [
            sid for sid, s in self._sessions.items()
            if s.state not in (StreamState.IDLE, StreamState.TRANSCRIBING)
        ]

    def cleanup_old_sessions(self, max_age_seconds: float = 300) -> int:
        """Remove sessions older than max_age_seconds."""
        now = time.time()
        old_ids = [
            sid for sid, s in self._sessions.items()
            if now - s.created_at > max_age_seconds
        ]
        for sid in old_ids:
            del self._sessions[sid]
        if old_ids:
            logger.info("Cleaned up %d old streaming sessions", len(old_ids))
        return len(old_ids)


# ── Singleton ────────────────────────────────────────────────────────────
_streaming_stt: StreamingSTT | None = None


def get_streaming_stt() -> StreamingSTT:
    """Get or create the singleton StreamingSTT instance."""
    global _streaming_stt
    if _streaming_stt is None:
        _streaming_stt = StreamingSTT()
    return _streaming_stt
