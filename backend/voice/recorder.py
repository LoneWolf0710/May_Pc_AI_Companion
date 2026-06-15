"""
Streaming voice recorder — records audio from mic and streams amplitude
data back to the frontend in real-time while recording.

Provides:
- POST /voice/record: Records audio for N seconds, returns transcription
- GET /voice/record/status: SSE stream of amplitude during recording
"""

import asyncio
import io
import json
import logging
import queue
import struct
import threading
import time
import wave

import numpy as np
import sounddevice as sd
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger("may.voice.recorder")

router = APIRouter(prefix="/voice", tags=["voice"])

SAMPLE_RATE = 16000
CHANNELS = 1

# Shared state for amplitude broadcasting
_amplitude_queue: queue.Queue = queue.Queue()
_is_recording = False
_recording_result: dict | None = None


def _audio_callback(indata, frames, time_info, status):
    """Called by sounddevice for each audio block during recording."""
    if status:
        logger.debug("Audio status: %s", status)
    audio = indata[:, 0] if indata.ndim > 1 else indata
    rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
    peak = float(np.abs(audio).max())
    # Broadcast amplitude to any connected SSE clients
    try:
        _amplitude_queue.put_nowait({"amplitude": min(1.0, rms * 5), "peak": min(1.0, peak * 3)})
    except queue.Full:
        pass


def _record_audio(duration: float) -> tuple[np.ndarray, float]:
    """Record audio for N seconds. Returns (audio_data, peak_amplitude)."""
    global _is_recording
    _is_recording = True

    recording = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
    )

    # Stream amplitude data while recording
    elapsed = 0.0
    while elapsed < duration:
        time.sleep(0.1)
        elapsed += 0.1
        try:
            _amplitude_queue.put_nowait({"elapsed": round(elapsed, 1), "duration": duration})
        except queue.Full:
            pass

    sd.wait()
    _is_recording = False

    peak = float(np.abs(recording).max())
    audio = recording[:, 0] if recording.ndim > 1 else recording
    return audio, peak


def _transcribe_audio(audio: np.ndarray) -> str:
    """Transcribe audio using faster-whisper."""
    from faster_whisper import WhisperModel

    model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
    segments, info = model.transcribe(audio, beam_size=5, language="en", vad_filter=True)
    text = " ".join(segment.text.strip() for segment in segments).strip()
    logger.info("Transcribed: '%s' (lang=%.2f)", text, info.language_probability)
    return text


@router.get("/record/amplitude")
async def record_amplitude_stream():
    """SSE stream of real-time amplitude data during recording."""

    async def event_generator():
        while _is_recording or not _amplitude_queue.empty():
            try:
                data = _amplitude_queue.get(timeout=0.2)
                yield f"data: {json.dumps(data)}\n\n"
            except queue.Empty:
                if _is_recording:
                    yield f"data: {json.dumps({'amplitude': 0})}\n\n"
                else:
                    break
        # Send final completion signal
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/record")
async def record_and_transcribe(duration: float = 5.0):
    """Record audio from mic and transcribe it.

    While recording, the frontend can subscribe to /voice/record/amplitude
    for real-time amplitude data via SSE.
    """
    duration = max(1.0, min(30.0, duration))

    # Clear any stale amplitude data
    while not _amplitude_queue.empty():
        try:
            _amplitude_queue.get_nowait()
        except queue.Empty:
            break

    # Record in a thread to not block the event loop
    loop = asyncio.get_event_loop()
    audio, peak = await loop.run_in_executor(None, _record_audio, duration)

    if peak < 0.005:
        return {"text": "", "amplitude": peak, "error": "No audio detected"}

    # Transcribe in a thread
    text = await loop.run_in_executor(None, _transcribe_audio, audio)

    return {"text": text, "amplitude": peak}
