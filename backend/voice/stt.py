"""
Speech-to-text module using sounddevice + faster-whisper.

Provides server-side STT as a fallback when browser webkitSpeechRecognition
doesn't work (e.g., in Tauri WebView2 on Windows).

Records audio via sounddevice and transcribes using faster-whisper (tiny model).
All heavy imports (numpy, sounddevice, faster-whisper) are deferred to load_model()
so the server starts fast.
"""

import logging
import time

logger = logging.getLogger("may.stt")

# Constants
SAMPLE_RATE = 16000
CHANNELS = 1
WHISPER_MODEL_SIZE_GPU = "large-v3-turbo"
WHISPER_MODEL_SIZE_CPU = "small"


class SpeechToText:
    """Server-side STT using sounddevice + faster-whisper."""

    def __init__(self, whisper_model: str | None = None):
        self._whisper_model = None
        self._device = None
        self._whisper_model_size = whisper_model

    def _detect_device(self) -> tuple[str, str, str]:
        """Detect best device, model, and compute type.
        
        Returns: (device, model_size, compute_type)
        """
        if self._whisper_model_size:
            # User forced a specific model
            return "cpu", self._whisper_model_size, "int8"
        
        try:
            import ctranslate2
            types = ctranslate2.get_supported_compute_types("cuda")
            if "float16" in types:
                logger.info("GPU detected — using large-v3-turbo with float16")
                return "cuda", WHISPER_MODEL_SIZE_GPU, "float16"
        except Exception:
            pass
        
        logger.info("No GPU — using small model with int8 on CPU")
        return "cpu", WHISPER_MODEL_SIZE_CPU, "int8"

    def load_model(self):
        """Lazy-load faster-whisper model with GPU→CPU fallback.
        
        Tests GPU with a dummy transcription to catch errors like missing cublas.
        """
        if self._whisper_model is not None:
            return

        import numpy as np
        from faster_whisper import WhisperModel

        device, model_size, compute_type = self._detect_device()
        for attempt_device, attempt_model, attempt_compute in [
            (device, model_size, compute_type),
            ("cpu", WHISPER_MODEL_SIZE_CPU, "int8"),
        ]:
            try:
                logger.info("Loading faster-whisper %s on %s (%s)...", attempt_model, attempt_device, attempt_compute)
                kwargs = {"device": attempt_device, "compute_type": attempt_compute}
                if attempt_device == "cpu":
                    kwargs["cpu_threads"] = 4
                    kwargs["num_workers"] = 2
                model = WhisperModel(attempt_model, **kwargs)
                # Test the model with a dummy transcription to catch runtime errors
                test_audio = np.zeros(16000, dtype=np.float32)
                list(model.transcribe(test_audio, beam_size=1))
                self._whisper_model = model
                self._device = attempt_device
                self._whisper_model_size = attempt_model
                logger.info("faster-whisper loaded and verified on %s", attempt_device)
                return
            except Exception as e:
                logger.warning("Failed on %s: %s — trying CPU fallback", attempt_device, e)
                if attempt_device == "cpu":
                    raise RuntimeError(f"Failed to load Whisper model on CPU: {e}")

        raise RuntimeError("Failed to load any Whisper model")

    def transcribe_audio(self, audio_samples) -> dict:
        """Transcribe float32 audio samples using faster-whisper.

        Args:
            audio_samples: numpy float32 array at 16kHz mono

        Returns:
            dict with 'text', 'language', 'duration' keys
        """
        import numpy as np

        self.load_model()

        if audio_samples is None or len(audio_samples) == 0:
            return {"text": "", "language": None, "duration": 0}

        # Ensure float32
        if audio_samples.dtype != np.float32:
            audio_samples = audio_samples.astype(np.float32)

        duration = len(audio_samples) / SAMPLE_RATE
        logger.info("Transcribing %.1fs of audio...", duration)

        t0 = time.time()
        segments, info = self._whisper_model.transcribe(
            audio_samples,
            beam_size=1,
            language="en",
            vad_filter=False,
            condition_on_previous_text=False,
            initial_prompt="The following is a transcription of English speech.",
        )
        text = " ".join(seg.text.strip() for seg in segments)
        elapsed = time.time() - t0

        logger.info(
            "Transcribed in %.1fs (lang=%s): %s",
            elapsed,
            info.language,
            text[:100] if text else "(empty)",
        )

        return {
            "text": text.strip(),
            "language": info.language,
            "duration": duration,
        }

    def cleanup(self):
        """Release resources."""
        self._whisper_model = None
