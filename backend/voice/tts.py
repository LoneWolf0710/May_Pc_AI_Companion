"""Text-to-speech — Browser SpeechSynthesis API (frontend).

TTS is now handled by the browser using the SpeechSynthesis API.
This approach was chosen because:

1. Instant, no server roundtrip needed
2. No heavy ML dependencies (Kokoro, Piper, etc.)
3. Works reliably on Windows without audio device configuration
4. Natural-sounding voices available (Google, Microsoft, etc.)

The frontend hook is at: src/hooks/useSpeechSynthesis.ts

This backend module is kept for potential future use with higher-quality
TTS models (Kokoro, Piper, etc.) when the user wants better voice quality.
"""


class TextToSpeech:
    """Placeholder for server-side TTS. Currently unused — browser handles TTS."""

    def __init__(self):
        self.is_speaking = False

    async def initialize(self) -> bool:
        return False  # Not implemented — browser TTS is used instead

    async def synthesize(self, text: str) -> bytes:
        return b""  # Not implemented

    def get_amplitude(self) -> float:
        return 0.0  # Not implemented
