"""Silero VAD — Always-on Voice Activity Detection for May.

Uses the Silero VAD model (~2MB, <1ms inference) for efficient
voice activity detection. This replaces the RMS-based silence
detection in streaming_stt.py with a proper ML-based VAD that
distinguishes speech from background noise.

Architecture spec: Part 4 — Voice Pipeline, Tier 1 VAD.

The model is loaded lazily on first use and shared across all callers.
It processes 512-sample chunks (32ms at 16kHz) and returns a speech
probability score between 0.0 and 1.0.

Usage:
    from voice.vad import get_vad, is_speech

    vad = get_vad()
    is_voice = vad.is_speech(pcm_int16_bytes)

    # Or use the convenience function
    is_voice = is_speech(pcm_int16_bytes)
"""

from __future__ import annotations

import logging
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("may.voice.vad")

# ── Constants ──────────────────────────────────────────────────────────

SAMPLE_RATE = 16000
CHUNK_SIZE_SAMPLES = 512  # 32ms at 16kHz — Silero's native chunk size
CHUNK_SIZE_BYTES = CHUNK_SIZE_SAMPLES * 2  # int16 = 2 bytes per sample

# Speech detection thresholds
SPEECH_THRESHOLD = 0.5      # Probability above this = speech
SILENCE_THRESHOLD = 0.3     # Probability below this = silence
SPEECH_FRAMES_REQUIRED = 2  # Consecutive speech frames to confirm speech start
SILENCE_FRAMES_REQUIRED = 4  # Consecutive silence frames to confirm speech end

# Cooldown to prevent rapid state toggling
STATE_TOGGLE_COOLDOWN_MS = 300


@dataclass
class VADState:
    """Current state of the VAD engine."""
    is_speaking: bool = False
    speech_probability: float = 0.0
    speech_start_time: float = 0.0
    last_speech_time: float = 0.0
    total_speech_duration: float = 0.0
    consecutive_speech_frames: int = 0
    consecutive_silence_frames: int = 0
    last_state_change: float = 0.0
    chunks_processed: int = 0


class SileroVAD:
    """Silero VAD wrapper with lazy model loading.

    The model is loaded on first use and kept in memory.
    Thread-safe — multiple callers can use the same instance.

    Usage:
        vad = SileroVAD()
        result = vad.process_chunk(pcm_int16_bytes)
        if result.is_speech:
            # Voice detected
    """

    def __init__(self):
        self._model = None
        self._load_attempted = False
        self._lock = threading.Lock()
        self._state = VADState()
        self._model_sample_rate = None

    def _ensure_model(self):
        """Lazy-load the Silero VAD model on first use."""
        if self._model is not None or self._load_attempted:
            return

        with self._lock:
            # Double-check after acquiring lock
            if self._model is not None or self._load_attempted:
                return

            self._load_attempted = True
            try:
                import torch
                # Load the Silero VAD model from torch.hub
                model, utils = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    onnx=False,
                )
                self._model = model
                self._model_sample_rate = utils[1]  # get_sample_rate
                logger.info(
                    "Silero VAD loaded (sample_rate=%d, device=%s)",
                    self._model_sample_rate,
                    "cuda" if torch.cuda.is_available() else "cpu",
                )
            except ImportError:
                logger.warning(
                    "torch not available — Silero VAD disabled. "
                    "Install with: pip install torch"
                )
            except Exception as e:
                logger.warning("Failed to load Silero VAD: %s", e)

    def is_available(self) -> bool:
        """Check if the Silero VAD model is loaded and ready."""
        self._ensure_model()
        return self._model is not None

    def process_chunk(self, pcm_int16_bytes: bytes) -> dict:
        """Process a single audio chunk and return speech detection.

        Args:
            pcm_int16_bytes: Raw PCM int16 audio (16kHz mono).
                Should be CHUNK_SIZE_BYTES (1024 bytes = 512 samples).

        Returns:
            dict with keys:
                - is_speech: bool — whether speech is detected
                - probability: float — speech probability (0.0-1.0)
                - state: str — "speech" or "silence"
                - speech_duration: float — total speech duration in seconds
        """
        self._ensure_model()

        if self._model is None:
            # Fallback to simple RMS-based detection
            return self._rms_fallback(pcm_int16_bytes)

        import torch

        try:
            # Convert int16 bytes to float32 tensor
            samples = struct.unpack(f'<{len(pcm_int16_bytes) // 2}h', pcm_int16_bytes)
            audio_tensor = torch.tensor(samples, dtype=torch.float32) / 32768.0

            # Get speech probability from Silero
            # The model expects a 1D tensor of floats
            speech_prob = self._model(audio_tensor, SAMPLE_RATE).item()

            self._state.speech_probability = speech_prob
            self._state.chunks_processed += 1

            # Determine speech/silence state with hysteresis
            now = time.time()
            chunk_duration = len(pcm_int16_bytes) / (SAMPLE_RATE * 2)  # int16 = 2 bytes

            if speech_prob >= SPEECH_THRESHOLD:
                self._state.consecutive_speech_frames += 1
                self._state.consecutive_silence_frames = 0
            else:
                self._state.consecutive_silence_frames += 1
                self._state.consecutive_speech_frames = 0

            # State transitions with debounce
            time_since_last_change = (now - self._state.last_state_change) * 1000
            if time_since_last_change < STATE_TOGGLE_COOLDOWN_MS:
                # Within cooldown — don't toggle state
                pass
            elif self._state.consecutive_speech_frames >= SPEECH_FRAMES_REQUIRED:
                if not self._state.is_speaking:
                    self._state.is_speaking = True
                    self._state.speech_start_time = now
                    self._state.last_state_change = now
                    logger.debug("VAD: Speech started")
            elif self._state.consecutive_silence_frames >= SILENCE_FRAMES_REQUIRED:
                if self._state.is_speaking:
                    # Record speech duration
                    self._state.total_speech_duration += now - self._state.speech_start_time
                    self._state.is_speaking = False
                    self._state.last_state_change = now
                    logger.debug("VAD: Speech ended (%.1fs)", self._state.total_speech_duration)

            if self._state.is_speaking:
                self._state.last_speech_time = now

            return {
                "is_speech": self._state.is_speaking,
                "probability": round(speech_prob, 4),
                "state": "speech" if self._state.is_speaking else "silence",
                "speech_duration": round(self._state.total_speech_duration, 2),
            }

        except Exception as e:
            logger.debug("Silero VAD processing failed: %s", e)
            return self._rms_fallback(pcm_int16_bytes)

    def _rms_fallback(self, pcm_int16_bytes: bytes) -> dict:
        """Simple RMS-based fallback when Silero is not available.

        Uses consecutive-frame hysteresis to prevent rapid toggling.
        """
        if len(pcm_int16_bytes) < 2:
            return {"is_speech": False, "probability": 0.0, "state": "silence", "speech_duration": 0.0}

        samples = struct.unpack(f'<{len(pcm_int16_bytes) // 2}h', pcm_int16_bytes)
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
        prob = min(1.0, rms / 5000.0)  # Normalize roughly

        self._state.speech_probability = prob
        is_speech = prob >= 0.15

        # Hysteresis: require consecutive frames to toggle state
        if is_speech:
            self._state.consecutive_speech_frames += 1
            self._state.consecutive_silence_frames = 0
        else:
            self._state.consecutive_silence_frames += 1
            self._state.consecutive_speech_frames = 0

        now = time.time()
        time_since_last_change = (now - self._state.last_state_change) * 1000
        if time_since_last_change < STATE_TOGGLE_COOLDOWN_MS:
            pass  # Within cooldown — don't toggle
        elif self._state.consecutive_speech_frames >= SPEECH_FRAMES_REQUIRED:
            if not self._state.is_speaking:
                self._state.is_speaking = True
                self._state.speech_start_time = now
                self._state.last_state_change = now
        elif self._state.consecutive_silence_frames >= SILENCE_FRAMES_REQUIRED:
            if self._state.is_speaking:
                self._state.total_speech_duration += now - self._state.speech_start_time
                self._state.is_speaking = False
                self._state.last_state_change = now

        return {
            "is_speech": self._state.is_speaking,
            "probability": round(prob, 4),
            "state": "speech" if self._state.is_speaking else "silence",
            "speech_duration": round(self._state.total_speech_duration, 2),
        }

    def reset(self):
        """Reset VAD state for a new session."""
        self._state = VADState()
        if self._model is not None:
            try:
                self._model.reset_states()
            except Exception:
                pass

    def get_state(self) -> dict:
        """Get current VAD state for API responses."""
        return {
            "available": self.is_available(),
            "model": "silero-vad" if self._model is None or self._load_attempted else "rms-fallback",
            "is_speaking": self._state.is_speaking,
            "speech_probability": round(self._state.speech_probability, 4),
            "speech_duration": round(self._state.total_speech_duration, 2),
            "chunks_processed": self._state.chunks_processed,
        }


# ── Singleton ────────────────────────────────────────────────────────────

_vad_instance: SileroVAD | None = None


def get_vad() -> SileroVAD:
    """Get or create the singleton SileroVAD instance."""
    global _vad_instance
    if _vad_instance is None:
        _vad_instance = SileroVAD()
    return _vad_instance


def is_speech(pcm_int16_bytes: bytes) -> bool:
    """Convenience function: check if a PCM chunk contains speech.

    Args:
        pcm_int16_bytes: Raw PCM int16 audio (16kHz mono)

    Returns:
        True if speech is detected
    """
    result = get_vad().process_chunk(pcm_int16_bytes)
    return result["is_speech"]
