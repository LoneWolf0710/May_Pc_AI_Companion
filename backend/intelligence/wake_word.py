"""Wake Word Detection — hands-free 'Hey May' activation.

Per JARVIS_V2_ARCHITECTURE.md Section 4.6:

Uses openwakeword for continuous wake word detection. The browser captures
audio via getUserMedia and streams chunks to the backend. The backend runs
openwakeword on each chunk and signals when the wake word is detected.

Architecture:
  Browser mic → getUserMedia → PCM chunks → POST /voice/wake-word-check
  → openwakeword.predict() → confidence score → detected signal

When the wake word fires, the frontend switches to "listening" mode and
the user speaks their command, which goes through the normal STT flow.

All processing is local — no cloud wake word service.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("may.intelligence.wake_word")

# openwakeword needs 16kHz 16-bit PCM in 1280-sample chunks (80ms)
CHUNK_SIZE = 1280
SAMPLE_RATE = 16000


@dataclass
class WakeWordState:
    """Tracks the state of wake word detection."""
    enabled: bool = False
    model_name: str = "hey_jarvis"  # Default built-in model closest to "Hey May"
    threshold: float = 0.5
    last_detection_time: float = 0
    detection_count: int = 0
    cooldown_sec: float = 2.0  # Minimum seconds between detections
    # Rolling confidence for UI display
    last_confidence: float = 0.0


class WakeWordDetector:
    """Continuous wake word detection using openwakeword.

    Usage:
        detector = WakeWordDetector()
        detector.enable()  # or load via config

        # When audio chunk arrives from browser:
        result = detector.check_chunk(pcm_int16_bytes)
        if result["detected"]:
            # Signal frontend to switch to listening mode
    """

    def __init__(self):
        self._state = WakeWordState()
        self._model = None  # openwakeword Model instance (lazy-loaded)
        self._loaded = False
        self._load_attempted = False  # Avoid retrying failed loads

    @property
    def enabled(self) -> bool:
        return self._state.enabled

    @property
    def state(self) -> WakeWordState:
        return self._state

    def load_model(self, model_name: str | None = None):
        """Load the openwakeword model. Call once at startup.

        Args:
            model_name: Which wake word model to use. Built-in options:
                        'alexa', 'hey_jarvis', 'hey_mycroft', 'computer'.
                        If None, uses the configured model_name.
        """
        if self._loaded or self._load_attempted:
            return

        self._load_attempted = True
        name = model_name or self._state.model_name

        try:
            from openwakeword.model import Model as OwwModel

            # Try loading the specified model first
            try:
                self._model = OwwModel(wakeword_models=[name])
                self._state.model_name = name
                logger.info("openwakeword loaded model: %s", name)
            except Exception:
                # Fallback: load with default models
                logger.warning(
                    "Model '%s' not found, loading default openwakeword models", name
                )
                self._model = OwwModel()
                self._state.model_name = "default"

            self._loaded = True
            logger.info("openwakeword ready (model=%s, threshold=%.2f)",
                        self._state.model_name, self._state.threshold)

        except ImportError:
            logger.error(
                "openwakeword not installed. Run: pip install openwakeword"
            )
            self._loaded = False
        except Exception as e:
            logger.error("Failed to load openwakeword: %s", e)
            self._loaded = False

    def check_chunk(self, pcm_int16_bytes: bytes) -> dict:
        """Check an audio chunk for wake word detection.

        Args:
            pcm_int16_bytes: Raw 16-bit PCM audio bytes at 16kHz mono.
                             Should be CHUNK_SIZE * 2 bytes (1280 samples * 2 bytes each).

        Returns:
            dict with keys:
                - detected (bool): Whether the wake word was detected
                - confidence (float): Current confidence score (0.0 - 1.0)
                - model (str): Which model was used
                - timestamp (float): Detection timestamp (if detected)
        """
        if not self._loaded or self._model is None:
            return {"detected": False, "confidence": 0, "model": self._state.model_name}

        import numpy as np

        # Convert bytes to numpy int16 array
        audio = np.frombuffer(pcm_int16_bytes, dtype=np.int16)

        # openwakeword expects the chunk size to be a multiple of CHUNK_SIZE
        # Pad or truncate to exact size
        if len(audio) < CHUNK_SIZE:
            audio = np.pad(audio, (0, CHUNK_SIZE - len(audio)))
        elif len(audio) > CHUNK_SIZE:
            audio = audio[:CHUNK_SIZE]

        # Run prediction
        try:
            prediction = self._model.predict(audio.astype(np.int16))
        except Exception as e:
            logger.debug("openwakeword predict error: %s", e)
            return {"detected": False, "confidence": 0, "model": self._state.model_name}

        # Get confidence for the active model
        # prediction is a dict: {model_name: confidence_score}
        confidence = 0.0
        for key, score in prediction.items():
            if isinstance(score, (int, float)) and score > confidence:
                confidence = float(score)

        self._state.last_confidence = confidence

        # Check if detection threshold met + cooldown elapsed
        now = time.time()
        detected = False
        if confidence >= self._state.threshold:
            if (now - self._state.last_detection_time) >= self._state.cooldown_sec:
                detected = True
                self._state.last_detection_time = now
                self._state.detection_count += 1
                logger.info(
                    "Wake word detected! (confidence=%.2f, count=%d)",
                    confidence, self._state.detection_count,
                )

        return {
            "detected": detected,
            "confidence": confidence,
            "model": self._state.model_name,
            "timestamp": now if detected else 0,
        }

    def enable(self, model_name: str | None = None, threshold: float | None = None):
        """Enable wake word detection."""
        if model_name:
            self._state.model_name = model_name
        if threshold is not None:
            self._state.threshold = threshold
        self._state.enabled = True
        self.load_model()
        logger.info("Wake word detection enabled (model=%s, threshold=%.2f)",
                    self._state.model_name, self._state.threshold)

    def disable(self):
        """Disable wake word detection."""
        self._state.enabled = False
        logger.info("Wake word detection disabled")

    def get_status(self) -> dict:
        """Get current wake word status for the API/frontend."""
        return {
            "enabled": self._state.enabled,
            "loaded": self._loaded,
            "model": self._state.model_name,
            "threshold": self._state.threshold,
            "last_confidence": round(self._state.last_confidence, 3),
            "detection_count": self._state.detection_count,
            "cooldown_sec": self._state.cooldown_sec,
        }

    def pause(self):
        """Pause wake word detection (used by privacy mode)."""
        self._previous_enabled = self._state.enabled
        self._state.enabled = False
        logger.info("Wake word detection paused")

    def resume(self):
        """Resume wake word detection (used by privacy mode)."""
        self._state.enabled = getattr(self, '_previous_enabled', False)
        logger.info("Wake word detection resumed (was: %s)", self._previous_enabled)

    def set_threshold(self, threshold: float):
        """Update detection threshold (0.0 - 1.0)."""
        self._state.threshold = max(0.0, min(1.0, threshold))
        logger.info("Wake word threshold set to %.2f", self._state.threshold)
