"""Meeting Mode — capture system audio, transcribe, and summarize.

Per MAY_V3_ARCHITECTURE.md Section 5.13:

When the user says "I'm joining a meeting", May:
1. Starts capturing system audio via WASAPI loopback (Windows)
2. Transcribes audio chunks with faster-whisper (reuses existing STT)
3. On stop: summarizes transcript and extracts action items via LLM
4. Saves meeting notes to ~/may/meetings/YYYY-MM-DD_HHMMSS.md

Usage:
    mode = MeetingMode()
    await mode.start()
    # ... meeting happens ...
    summary = await mode.stop()
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger("may.intelligence.meeting_mode")


# ── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class MeetingSummary:
    """Summary of a captured meeting."""
    title: str
    date: str
    duration_sec: float
    transcript_length: int
    summary: str = ""
    action_items: list[str] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    saved_path: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "date": self.date,
            "duration_sec": round(self.duration_sec, 1),
            "duration_display": _format_duration(self.duration_sec),
            "transcript_length": self.transcript_length,
            "summary": self.summary,
            "action_items": self.action_items,
            "key_points": self.key_points,
            "participants": self.participants,
            "saved_path": self.saved_path,
        }


@dataclass
class MeetingState:
    """Current meeting recording state."""
    active: bool = False
    started_at: float = 0
    paused: bool = False
    audio_chunks: list[bytes] = field(default_factory=list)
    transcript_segments: list[dict] = field(default_factory=list)
    total_audio_sec: float = 0


# ── Meeting Mode ────────────────────────────────────────────────────────────

class MeetingMode:
    """Capture system audio during meetings, transcribe, and summarize.

    Uses WASAPI loopback to capture what the speakers are playing
    (i.e., the other people in the meeting). Falls back to microphone
    capture if loopback isn't available.

    All audio processing is done locally — no cloud APIs needed.
    """

    MEETINGS_DIR = os.path.join(os.path.expanduser("~"), "may", "meetings")
    # Capture a chunk every N seconds for transcription
    CHUNK_INTERVAL_SEC = 30
    # Max recording duration (safety cap)
    MAX_DURATION_SEC = 4 * 3600  # 4 hours

    def __init__(self):
        self._state = MeetingState()
        self._capture_task: asyncio.Task | None = None
        self._transcript_text: str = ""

    @property
    def active(self) -> bool:
        return self._state.active

    async def start(self, title: str | None = None) -> dict:
        """Start capturing meeting audio.

        Args:
            title: Optional meeting title. Auto-generated from timestamp if not provided.

        Returns:
            Status dict with meeting info.
        """
        if self._state.active:
            return {"error": "Meeting already in progress", "started_at": self._state.started_at}

        now = datetime.now()
        if not title:
            title = f"Meeting {now.strftime('%Y-%m-%d %H:%M')}"

        self._state = MeetingState(
            active=True,
            started_at=time.time(),
        )
        self._transcript_text = ""

        # Start background capture loop
        self._capture_task = asyncio.create_task(self._capture_loop())

        logger.info("Meeting mode started: %s", title)
        return {
            "status": "started",
            "title": title,
            "started_at": self._state.started_at,
            "message": f"Recording meeting: {title}~",
        }

    async def stop(self) -> dict:
        """Stop recording and generate summary.

        Returns:
            MeetingSummary as a dict, or error.
        """
        if not self._state.active:
            return {"error": "No meeting in progress"}

        self._state.active = False
        duration = time.time() - self._state.started_at

        # Cancel capture task
        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
            self._capture_task = None

        # Transcribe any remaining audio
        await self._transcribe_remaining()

        # Build summary
        summary = await self._generate_summary(duration)

        # Save to file
        saved_path = self._save_meeting(summary)

        # Reset state
        self._state = MeetingState()

        logger.info("Meeting stopped. Duration: %.0fs, Transcript: %d chars",
                     duration, len(self._transcript_text))
        return summary.to_dict()

    async def get_status(self) -> dict:
        """Get current meeting status."""
        if not self._state.active:
            return {"active": False}

        duration = time.time() - self._state.started_at
        return {
            "active": True,
            "duration_sec": round(duration, 1),
            "duration_display": _format_duration(duration),
            "transcript_segments": len(self._state.transcript_segments),
            "audio_chunks": len(self._state.audio_chunks),
            "paused": self._state.paused,
        }

    def set_stt(self, stt):
        """Set the STT instance to use (reuses the global one from main.py)."""
        self._stt = stt

    async def _capture_loop(self):
        """Background loop that captures and transcribes audio in chunks."""
        stt = getattr(self, '_stt', None)
        if stt is None:
            from voice.stt import SpeechToText
            stt = SpeechToText()
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, stt.load_model)

        try:
            while self._state.active:
                # Wait for chunk interval
                await asyncio.sleep(self.CHUNK_INTERVAL_SEC)
                if not self._state.active:
                    break

                # Capture system audio (WASAPI loopback)
                audio_data = await self._capture_system_audio()
                if audio_data is None or len(audio_data) == 0:
                    continue

                self._state.audio_chunks.append(audio_data)
                self._state.total_audio_sec += self.CHUNK_INTERVAL_SEC

                # Transcribe the chunk
                loop = asyncio.get_running_loop()
                try:
                    result = await loop.run_in_executor(
                        None, stt.transcribe_audio, audio_data
                    )
                    text = result.get("text", "").strip()
                    if text:
                        self._state.transcript_segments.append({
                            "text": text,
                            "timestamp": time.time(),
                            "offset_sec": self._state.total_audio_sec,
                        })
                        self._transcript_text += text + "\n"
                        logger.debug("Meeting transcript chunk: %s", text[:80])
                except Exception as e:
                    logger.warning("Meeting transcription error: %s", e)

        except asyncio.CancelledError:
            pass

    async def _capture_system_audio(self) -> Optional[bytes]:
        """Capture system audio via WASAPI loopback on Windows.

        Falls back to no-op if audio capture isn't available.
        Returns raw audio data (int16 PCM, 16kHz mono).
        """
        try:
            import numpy as np
            import sounddevice as sd

            # Try WASAPI loopback first (captures system audio)
            try:
                devices = sd.query_devices()
                loopback_device = None
                for dev in devices:
                    if "loopback" in dev["name"].lower() and dev["max_input_channels"] > 0:
                        loopback_device = dev["name"]
                        break

                if loopback_device:
                    # Capture N seconds of system audio
                    duration = self.CHUNK_INTERVAL_SEC
                    sample_rate = 16000
                    frames = sd.rec(
                        int(duration * sample_rate),
                        samplerate=sample_rate,
                        channels=1,
                        dtype="int16",
                        device=loopback_device,
                    )
                    sd.wait()
                    return frames.tobytes()
            except Exception as loopback_err:
                logger.debug("WASAPI loopback not available: %s", loopback_err)

            # Fallback: capture from default microphone
            try:
                duration = self.CHUNK_INTERVAL_SEC
                sample_rate = 16000
                frames = sd.rec(
                    int(duration * sample_rate),
                    samplerate=sample_rate,
                    channels=1,
                    dtype="int16",
                )
                sd.wait()
                return frames.tobytes()
            except Exception as mic_err:
                logger.debug("Microphone capture not available: %s", mic_err)

            return None

        except ImportError:
            logger.debug("sounddevice/numpy not available for meeting capture")
            return None

    async def _transcribe_remaining(self):
        """Transcribe any remaining unprocessed audio."""
        # The capture loop handles all transcription incrementally.
        # This is called on stop() for any future batch-processing needs.
        pass

    async def _generate_summary(self, duration: float) -> MeetingSummary:
        """Generate a meeting summary using the LLM."""
        now = datetime.now()
        title = f"Meeting {now.strftime('%Y-%m-%d %H:%M')}"
        summary = MeetingSummary(
            title=title,
            date=now.strftime("%Y-%m-%d %H:%M"),
            duration_sec=duration,
            transcript_length=len(self._transcript_text),
        )

        if not self._transcript_text.strip():
            summary.summary = "No speech was captured during this meeting."
            return summary

        # Use LLM to summarize and extract action items
        try:
            import json as _json
            import httpx

            prompt = f"""Analyze this meeting transcript and provide:

1. A brief SUMMARY (3-5 sentences)
2. ACTION ITEMS (numbered list of tasks mentioned)
3. KEY POINTS (bullet points of main topics)
4. PARTICIPANTS (if names are mentioned)

Meeting Duration: {_format_duration(duration)}
Transcript:
{self._transcript_text[:8000]}

Respond in this exact JSON format:
{{
  "summary": "...",
  "action_items": ["item 1", "item 2"],
  "key_points": ["point 1", "point 2"],
  "participants": ["name 1", "name 2"]
}}"""

            # Try to get a summary from the LLM (best-effort)
            # Uses the Ollama API directly — falls back to raw transcript on failure
            backend_url = os.environ.get("MAY_BACKEND_URL", "http://localhost:8080")
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{backend_url}/chat",
                    json={
                        "message": prompt,
                        "history": [],
                        "provider": "ollama",
                        "model": "qwen3:4b",
                    },
                )
                if resp.status_code == 200:
                    # The /chat endpoint streams text, so we get the full response
                    content = resp.text
                    # Try to extract JSON from response
                    content = content.strip()
                    if content.startswith("```"):
                        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                    parsed = _json.loads(content)
                    summary.summary = parsed.get("summary", "")
                    summary.action_items = parsed.get("action_items", [])
                    summary.key_points = parsed.get("key_points", [])
                    summary.participants = parsed.get("participants", [])
        except Exception as e:
            logger.warning("LLM summarization failed: %s — using raw transcript", e)
            # Fallback: use first few paragraphs as summary
            lines = self._transcript_text.strip().split("\n")
            summary.summary = " ".join(lines[:5])[:500]

        return summary

    def _save_meeting(self, summary: MeetingSummary) -> str:
        """Save meeting notes to ~/may/meetings/."""
        os.makedirs(self.MEETINGS_DIR, exist_ok=True)

        filename = datetime.now().strftime("%Y-%m-%d_%H%M%S") + ".md"
        filepath = os.path.join(self.MEETINGS_DIR, filename)

        content = f"""# {summary.title}

**Date:** {summary.date}
**Duration:** {_format_duration(summary.duration_sec)}

---

## Summary

{summary.summary or "_No summary generated._"}

## Action Items

{chr(10).join(f"- [ ] {item}" for item in summary.action_items) or "- _None identified._"}

## Key Points

{chr(10).join(f"- {point}" for point in summary.key_points) or "- _None identified._"}

## Participants

{chr(10).join(f"- {p}" for p in summary.participants) or "- _Not identified._"}

---

## Full Transcript

{self._transcript_text or "_No transcript captured._"}
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        summary.saved_path = filepath
        logger.info("Meeting saved: %s", filepath)
        return filepath


# ── Helpers ─────────────────────────────────────────────────────────────────

def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"
