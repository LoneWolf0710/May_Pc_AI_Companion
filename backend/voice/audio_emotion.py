"""
Audio-Based Emotion Detection — extracts vocal features for emotion inference.

From MAY_FINAL_ARCHITECTURE.md Part 3:
"Tier 1: Text-based tone analyzer (keyword matching)
 Tier 2: Audio-based analysis (pitch, energy, tempo)"

Extracts from voice waveform:
- Pitch (F0): Fundamental frequency — high pitch = excitement/stress, low = calm/sadness
- Energy (RMS): Loudness — high energy = frustration/excitement, low = calm/sadness
- Tempo: Speech rate — fast = urgency/excitement, slow = sadness/calm
- Pitch variability: Monotone = calm/sad, variable = excited/stressed

All computations use numpy only (no librosa dependency) for fast startup.
"""

from __future__ import annotations

import logging
import math
import struct
import time
from dataclasses import dataclass

logger = logging.getLogger("may.voice.audio_emotion")

# Feature thresholds (tuned for 16kHz mono audio)
PITCH_HIGH_THRESHOLD = 200.0   # Hz — above this suggests excitement/stress
PITCH_LOW_THRESHOLD = 100.0    # Hz — below this suggests calm/sadness
ENERGY_HIGH_THRESHOLD = 0.15   # RMS normalized — high energy
ENERGY_LOW_THRESHOLD = 0.03    # RMS normalized — low energy
TEMPO_FAST_THRESHOLD = 4.0     # syllables/sec estimate — fast speech
TEMPO_SLOW_THRESHOLD = 2.0     # syllables/sec estimate — slow speech


@dataclass
class AudioFeatures:
    """Extracted audio features from a voice segment."""
    pitch_mean: float       # Mean fundamental frequency (Hz)
    pitch_std: float        # Pitch variability (Hz)
    energy_mean: float      # Mean RMS energy (0.0-1.0)
    energy_std: float       # Energy variability
    tempo_estimate: float   # Estimated speech rate (syllables/sec)
    duration: float         # Audio duration in seconds

    def to_dict(self) -> dict:
        return {
            "pitch_mean": round(self.pitch_mean, 1),
            "pitch_std": round(self.pitch_std, 1),
            "energy_mean": round(self.energy_mean, 4),
            "energy_std": round(self.energy_std, 4),
            "tempo_estimate": round(self.tempo_estimate, 2),
            "duration": round(self.duration, 2),
        }


@dataclass
class AudioEmotionResult:
    """Result of audio-based emotion analysis."""
    emotion: str            # Detected emotion label
    confidence: float       # 0.0-1.0
    features: AudioFeatures # Extracted features
    signals: list[str]      # What signals contributed

    def to_dict(self) -> dict:
        return {
            "emotion": self.emotion,
            "confidence": round(self.confidence, 3),
            "features": self.features.to_dict(),
            "signals": self.signals,
        }


class AudioEmotionAnalyzer:
    """Analyzes audio features to detect emotion from voice.

    Usage:
        analyzer = AudioEmotionAnalyzer()

        # From float32 samples
        result = analyzer.analyze_samples(samples, sample_rate=16000)

        # From raw PCM int16 bytes
        result = analyzer.analyze_pcm(pcm_bytes)
    """

    def analyze_samples(
        self,
        samples,
        sample_rate: int = 16000,
    ) -> AudioEmotionResult:
        """Analyze emotion from numpy float32 audio samples.

        Args:
            samples: numpy float32 array (mono, 16kHz)
            sample_rate: Sample rate in Hz

        Returns:
            AudioEmotionResult with emotion, confidence, features, signals
        """
        import numpy as np

        if samples is None or len(samples) == 0:
            return self._empty_result()

        if samples.dtype != np.float32:
            samples = samples.astype(np.float32)

        duration = len(samples) / sample_rate

        # Extract features
        features = self._extract_features(samples, sample_rate)

        # Classify emotion from features
        emotion, confidence, signals = self._classify_emotion(features)

        return AudioEmotionResult(
            emotion=emotion,
            confidence=confidence,
            features=features,
            signals=signals,
        )

    def analyze_pcm(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 16000,
    ) -> AudioEmotionResult:
        """Analyze emotion from raw PCM int16 bytes."""
        import numpy as np

        if len(pcm_bytes) < 2:
            return self._empty_result()

        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        return self.analyze_samples(samples, sample_rate)

    def _extract_features(self, samples, sample_rate: int) -> AudioFeatures:
        """Extract pitch, energy, and tempo features."""
        import numpy as np

        duration = len(samples) / sample_rate

        # ── Energy (RMS) ──
        # Compute RMS in short frames (25ms windows, 10ms hop)
        frame_size = int(sample_rate * 0.025)
        hop_size = int(sample_rate * 0.010)

        energies = []
        for i in range(0, len(samples) - frame_size, hop_size):
            frame = samples[i:i + frame_size]
            rms = float(np.sqrt(np.mean(frame ** 2)))
            energies.append(rms)

        energy_mean = float(np.mean(energies)) if energies else 0.0
        energy_std = float(np.std(energies)) if energies else 0.0

        # ── Pitch (F0) via autocorrelation ──
        pitches = self._estimate_pitch_autocorrelation(samples, sample_rate)

        if pitches:
            pitch_mean = float(np.mean(pitches))
            pitch_std = float(np.std(pitches))
        else:
            pitch_mean = 0.0
            pitch_std = 0.0

        # ── Tempo estimate ──
        # Estimate from energy envelope — count energy peaks (syllable proxies)
        tempo = self._estimate_tempo(energies, sample_rate, hop_size)

        return AudioFeatures(
            pitch_mean=pitch_mean,
            pitch_std=pitch_std,
            energy_mean=energy_mean,
            energy_std=energy_std,
            tempo_estimate=tempo,
            duration=duration,
        )

    def _estimate_pitch_autocorrelation(self, samples, sample_rate: int) -> list[float]:
        """Estimate F0 using autocorrelation method."""
        import numpy as np

        # Frame parameters
        frame_size = int(sample_rate * 0.030)  # 30ms frames
        hop_size = int(sample_rate * 0.010)     # 10ms hop

        # Pitch bounds
        min_lag = int(sample_rate / 500)   # Max 500 Hz
        max_lag = int(sample_rate / 50)    # Min 50 Hz

        pitches = []
        for i in range(0, len(samples) - frame_size, hop_size):
            frame = samples[i:i + frame_size]

            # Autocorrelation
            corr = np.correlate(frame, frame, mode='full')
            corr = corr[len(corr) // 2:]

            # Find peak in valid pitch range
            if max_lag > len(corr):
                continue

            search_corr = corr[min_lag:max_lag]
            if len(search_corr) == 0:
                continue

            peak_idx = np.argmax(search_corr)
            peak_val = search_corr[peak_idx]

            # Only accept if correlation is strong enough
            if peak_val > 0.3 * corr[0]:  # Normalized threshold
                f0 = sample_rate / (peak_idx + min_lag)
                pitches.append(f0)

        return pitches

    def _estimate_tempo(
        self,
        energies: list[float],
        sample_rate: int,
        hop_size: int,
    ) -> float:
        """Estimate speech tempo from energy envelope."""
        if len(energies) < 10:
            return 0.0

        import numpy as np

        energy_arr = np.array(energies)

        # Smooth the energy envelope
        kernel_size = max(3, len(energies) // 20)
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel = np.ones(kernel_size) / kernel_size
        smoothed = np.convolve(energy_arr, kernel, mode='same')

        # Find peaks (syllable proxies)
        threshold = np.mean(smoothed) * 0.6
        peaks = []
        for i in range(1, len(smoothed) - 1):
            if smoothed[i] > threshold and smoothed[i] > smoothed[i-1] and smoothed[i] > smoothed[i+1]:
                peaks.append(i)

        # Merge peaks that are too close (< 50ms apart)
        min_peak_distance = int(0.05 * sample_rate / hop_size)
        merged_peaks = []
        for p in peaks:
            if not merged_peaks or p - merged_peaks[-1] >= min_peak_distance:
                merged_peaks.append(p)

        # Calculate tempo (peaks per second)
        if len(merged_peaks) < 2:
            return 0.0

        total_time = len(energies) * hop_size / sample_rate
        tempo = len(merged_peaks) / total_time

        return tempo

    def _classify_emotion(self, features: AudioFeatures) -> tuple[str, float, list[str]]:
        """Classify emotion from extracted audio features.

        Returns: (emotion, confidence, signals)
        """
        signals = []
        scores = {
            "neutral": 0.3,  # Default baseline
            "happy": 0.0,
            "sad": 0.0,
            "angry": 0.0,
            "excited": 0.0,
            "calm": 0.0,
            "anxious": 0.0,
        }

        # ── Pitch-based signals ──
        if features.pitch_mean > PITCH_HIGH_THRESHOLD:
            scores["excited"] += 0.2
            scores["anxious"] += 0.1
            scores["angry"] += 0.1
            signals.append(f"high_pitch:{features.pitch_mean:.0f}Hz")
        elif features.pitch_mean < PITCH_LOW_THRESHOLD and features.pitch_mean > 0:
            scores["sad"] += 0.15
            scores["calm"] += 0.1
            signals.append(f"low_pitch:{features.pitch_mean:.0f}Hz")

        # Pitch variability — variable = emotional, monotone = calm/sad
        if features.pitch_std > 40:
            scores["excited"] += 0.15
            scores["angry"] += 0.1
            signals.append(f"variable_pitch:{features.pitch_std:.0f}Hz")
        elif features.pitch_std < 10 and features.pitch_std > 0:
            scores["calm"] += 0.15
            scores["sad"] += 0.1
            signals.append("monotone_pitch")

        # ── Energy-based signals ──
        if features.energy_mean > ENERGY_HIGH_THRESHOLD:
            scores["angry"] += 0.2
            scores["excited"] += 0.15
            scores["happy"] += 0.05
            signals.append(f"high_energy:{features.energy_mean:.3f}")
        elif features.energy_mean < ENERGY_LOW_THRESHOLD:
            scores["sad"] += 0.15
            scores["calm"] += 0.1
            signals.append(f"low_energy:{features.energy_mean:.3f}")

        # High energy variability = emotional swings
        if features.energy_std > 0.1:
            scores["angry"] += 0.1
            scores["excited"] += 0.05
            signals.append(f"variable_energy:{features.energy_std:.3f}")

        # ── Tempo-based signals ──
        if features.tempo_estimate > TEMPO_FAST_THRESHOLD:
            scores["excited"] += 0.15
            scores["angry"] += 0.1
            scores["anxious"] += 0.1
            signals.append(f"fast_tempo:{features.tempo_estimate:.1f}syl/s")
        elif features.tempo_estimate < TEMPO_SLOW_THRESHOLD and features.tempo_estimate > 0:
            scores["sad"] += 0.15
            scores["calm"] += 0.1
            signals.append(f"slow_tempo:{features.tempo_estimate:.1f}syl/s")

        # ── Combined signal boosts ──
        # High pitch + high energy + fast tempo = definitely excited
        if (features.pitch_mean > PITCH_HIGH_THRESHOLD and
            features.energy_mean > ENERGY_HIGH_THRESHOLD and
            features.tempo_estimate > TEMPO_FAST_THRESHOLD):
            scores["excited"] += 0.2
            signals.append("combined_excitement")

        # Low pitch + low energy + slow tempo = definitely sad
        if (features.pitch_mean < PITCH_LOW_THRESHOLD and features.pitch_mean > 0 and
            features.energy_mean < ENERGY_LOW_THRESHOLD and
            features.tempo_estimate < TEMPO_SLOW_THRESHOLD and features.tempo_estimate > 0):
            scores["sad"] += 0.2
            signals.append("combined_sadness")

        # High pitch + high energy + fast tempo + variable = angry (not just excited)
        if (features.pitch_mean > PITCH_HIGH_THRESHOLD and
            features.energy_mean > ENERGY_HIGH_THRESHOLD and
            features.energy_std > 0.1):
            scores["angry"] += 0.15
            signals.append("combined_anger")

        # Pick the highest scoring emotion
        best_emotion = max(scores, key=lambda e: scores[e])
        best_score = scores[best_emotion]

        # Normalize confidence to 0.0-0.95
        confidence = min(0.95, best_score / 1.0)

        if not signals:
            signals.append("no_voice_features")

        return best_emotion, confidence, signals

    def _empty_result(self) -> AudioEmotionResult:
        """Return an empty result for no audio."""
        return AudioEmotionResult(
            emotion="neutral",
            confidence=0.0,
            features=AudioFeatures(
                pitch_mean=0, pitch_std=0,
                energy_mean=0, energy_std=0,
                tempo_estimate=0, duration=0,
            ),
            signals=["no_audio"],
        )
