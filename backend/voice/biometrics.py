"""
Voice Biometrics — Speaker verification using resemblyzer.

Provides enrollment (save speaker embedding) and verification (compare new audio against saved).
Uses cosine similarity on 256-dim embeddings with configurable threshold.
"""

import json
import os
import logging
import threading
from pathlib import Path
from typing import Optional

# Lazy numpy import to avoid module-level crash if numpy is unavailable
def _get_np():
    try:
        import numpy
        return numpy
    except ImportError:
        raise ImportError("numpy not installed. Run: pip install numpy")

logger = logging.getLogger("may.biometrics")

# Default storage path
_BIOMETRICS_DIR = Path.home() / ".may"
_PROFILE_FILE = _BIOMETRICS_DIR / "voice_profile.json"


class VoiceBiometrics:
    """Speaker verification using resemblyzer embeddings."""

    def __init__(self, threshold: float = 0.75):
        self._threshold = threshold
        self._encoder = None
        self._lock = threading.Lock()
        self._profile: Optional[dict] = None  # {"embedding": list[float], "name": str, "enrolled_at": str}
        self._enabled = False
        self._load_profile()

    def _load_profile(self):
        """Load saved voice profile from disk."""
        try:
            if _PROFILE_FILE.exists():
                with open(_PROFILE_FILE, "r") as f:
                    self._profile = json.load(f)
                self._enabled = True
                logger.info("Loaded voice profile for '%s'", self._profile.get("name", "unknown"))
        except Exception as e:
            logger.warning("Failed to load voice profile: %s", e)
            self._profile = None

    def _save_profile(self):
        """Save voice profile to disk."""
        try:
            _BIOMETRICS_DIR.mkdir(parents=True, exist_ok=True)
            with open(_PROFILE_FILE, "w") as f:
                json.dump(self._profile, f, indent=2)
        except Exception as e:
            logger.error("Failed to save voice profile: %s", e)

    def _ensure_encoder(self):
        """Lazy-load the resemblyzer VoiceEncoder."""
        if self._encoder is not None:
            return
        with self._lock:
            if self._encoder is not None:
                return
            try:
                from resemblyzer import VoiceEncoder
                logger.info("Loading resemblyzer VoiceEncoder...")
                self._encoder = VoiceEncoder()
                logger.info("VoiceEncoder loaded")
            except ImportError:
                raise ImportError(
                    "resemblyzer not installed. Run: pip install resemblyzer"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to load VoiceEncoder: {e}")

    def _extract_embedding(self, audio_samples) -> "np.ndarray":
        """Extract a 256-dim speaker embedding from float32 audio samples (16kHz mono).

        Args:
            audio_samples: Float32 audio array, 16kHz mono.

        Returns:
            256-dim numpy array (L2-normalized).
        """
        np = _get_np()
        self._ensure_encoder()

        # Ensure correct format: float32, mono, 16kHz
        if audio_samples.ndim > 1:
            audio_samples = audio_samples.mean(axis=1)

        # Minimum audio length: 0.5s for reliable embedding
        min_samples = 8000  # 0.5s at 16kHz
        if len(audio_samples) < min_samples:
            raise ValueError(
                f"Audio too short for biometrics ({len(audio_samples)/16000:.1f}s). "
                f"Need at least {min_samples/16000:.1f}s."
            )

        # resemblyzer handles resampling internally if needed
        from resemblyzer import preprocess_wav
        wav = preprocess_wav(audio_samples, source_sr=16000)
        embedding = self._encoder.embed_utterance(wav)
        return embedding

    @staticmethod
    def _cosine_similarity(a, b) -> float:
        """Compute cosine similarity between two vectors."""
        np = _get_np()
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def enroll(self, audio_samples, name: str = "user") -> dict:
        """Enroll a new speaker from audio samples.

        Args:
            audio_samples: Float32 audio array, 16kHz mono.
            name: Speaker name/label.

        Returns:
            {"status": "ok", "name": str, "threshold": float}
        """
        from datetime import datetime
        embedding = self._extract_embedding(audio_samples)
        self._profile = {
            "embedding": embedding.tolist(),
            "name": name,
            "enrolled_at": datetime.now().isoformat(),
            "threshold": self._threshold,
        }
        self._enabled = True
        self._save_profile()
        logger.info("Enrolled speaker '%s' (embedding dim=%d)", name, len(embedding))
        return {
            "status": "ok",
            "name": name,
            "threshold": self._threshold,
            "enrolled_at": self._profile["enrolled_at"],
        }

    def verify(self, audio_samples) -> dict:
        """Verify if the speaker matches the enrolled profile.

        Args:
            audio_samples: Float32 audio array, 16kHz mono.

        Returns:
            {"match": bool, "similarity": float, "threshold": float, "name": str}
        """
        if not self._enabled or self._profile is None:
            return {
                "match": False,
                "similarity": 0.0,
                "threshold": self._threshold,
                "name": "",
                "error": "No voice profile enrolled",
            }

        try:
            np = _get_np()
            embedding = self._extract_embedding(audio_samples)
            saved_embedding = np.array(self._profile["embedding"])
            similarity = self._cosine_similarity(embedding, saved_embedding)
            is_match = similarity > self._threshold
            return {
                "match": is_match,
                "similarity": round(similarity, 4),
                "threshold": self._threshold,
                "name": self._profile.get("name", ""),
                "enrolled": True,
            }
        except ValueError as e:
            return {
                "match": False,
                "similarity": 0.0,
                "threshold": self._threshold,
                "name": self._profile.get("name", ""),
                "error": str(e),
            }

    def get_status(self) -> dict:
        """Get biometrics enrollment status."""
        return {
            "enabled": self._enabled,
            "enrolled": self._profile is not None,
            "name": self._profile.get("name", "") if self._profile else "",
            "threshold": self._threshold,
            "enrolled_at": self._profile.get("enrolled_at", "") if self._profile else "",
        }

    def set_threshold(self, threshold: float):
        """Update the similarity threshold (0.0 - 1.0)."""
        self._threshold = max(0.0, min(1.0, threshold))
        if self._profile:
            self._profile["threshold"] = self._threshold
            self._save_profile()

    def delete_profile(self) -> dict:
        """Delete the saved voice profile."""
        self._profile = None
        self._enabled = False
        try:
            if _PROFILE_FILE.exists():
                _PROFILE_FILE.unlink()
        except Exception as e:
            logger.warning("Failed to delete profile file: %s", e)
        return {"status": "ok", "message": "Voice profile deleted"}

    def toggle(self) -> dict:
        """Toggle biometrics on/off (without deleting profile)."""
        self._enabled = not self._enabled
        return {"enabled": self._enabled, "enrolled": self._profile is not None}
