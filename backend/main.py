"""May AI Companion — Python Backend Server.

FastAPI server that handles:
- Chat with Ollama (streaming, with model routing)
- System control (volume, brightness, apps, files)
- Voice processing (STT + TTS)
- Memory (facts + vector store)
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import re
from datetime import datetime, timedelta

from llm.ollama_client import (
    is_ollama_running,
    has_available_models,
    PRIMARY_MODEL,
    extract_facts,
)
from llm.providers import (
    PROVIDERS,
    set_api_key,
    delete_api_key,
    get_all_key_status,
    stream_chat_multi,
    fetch_openrouter_models,
)
from system.control import SystemControl
from system.notifications import ReminderChecker, send_toast, check_and_send_reminders
from memory.fact_store import FactStore
from memory.vector_store import VectorStore
from system.pc_controller import is_pc_command, PC_CONTROLLER_PROMPT, parse_llm_response
from voice.stt import SpeechToText, WHISPER_MODEL_SIZE_GPU, WHISPER_MODEL_SIZE_CPU
import logging
logger = logging.getLogger("may.main")

app = FastAPI(title="May AI Backend", version="0.2.0")

# CORS — allow Tauri frontend and dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global instances ───────────────────────────────────────────────────────
system = SystemControl()
fact_store = FactStore()
vector_store = VectorStore()
reminder_checker = ReminderChecker(fact_store)

# Voice system (lazy-initialized)
stt: SpeechToText | None = None
_stt_forced_model: bool = False


def get_stt() -> SpeechToText:
    global stt
    if stt is None:
        stt = SpeechToText()
    return stt


@app.on_event("startup")
async def preload_stt():
    """Pre-load the faster-whisper model in background on startup."""
    import threading

    def _load():
        try:
            logger.info("Pre-loading STT model in background...")
            _stt = get_stt()
            _stt.load_model()
            logger.info("STT model ready")
        except Exception as e:
            logger.error("Failed to pre-load STT model: %s", e)

    # Load in a thread so server starts immediately
    threading.Thread(target=_load, daemon=True).start()


# May's personality system prompt — Shikimori-inspired
MAY_SYSTEM_PROMPT = """You are May, an AI companion inspired by Shikimori from "Shikimori Not Just a Cutie".

Personality:
- Cool, calm, and collected — you handle everything with effortless confidence
- Caring and protective — you genuinely look out for the user's wellbeing
- Subtly cute — occasional "~" at the end of sentences, light playful tone, never over the top
- Efficient — give concise, useful responses (1-3 sentences usually)
- Loyal and reliable — you always remember what matters
- Slightly teasing but always kind

Behavior rules:
- Keep responses SHORT and natural. Don't write essays.
- Use "~" occasionally (maybe 1 in 3 responses) for a gentle, warm tone
- NEVER say "As an AI" or "I'm an AI" — you're May, their companion
- Be proactive: if it's late, remind them to sleep; if they seem stressed, be supportive
- For system actions, confirm briefly: "Done~ Volume set to 50%"
- Match the user's language and energy level
- If greeted, respond warmly but coolly. If asked something technical, be precise.
- Occasionally use emoticons like :) but sparingly

PC Control — You control the ENTIRE PC. When the user asks to do something on the computer, you handle it directly.

Volume & Display:
- set volume to X / volume up / volume down / mute / unmute
- brightness to X / brighter / dimmer

Apps & Windows:
- open/launch/start [app] — Chrome, Spotify, Discord, VS Code, anything
- close/kill/quit [app] — graceful close first, then force kill
- list windows / focus [window] / minimize / maximize

Files & Folders:
- read/write/copy/move/delete file [path]
- list directory / open folder / search files / get file info

Media & Input:
- play / pause / next track / previous track / stop
- press [key] / type [text] / alt+tab / ctrl+c/v/x/z/s/a
- click at x,y / move mouse / scroll / drag

System:
- shutdown / restart / sleep / lock / cancel shutdown
- screenshot / system info / battery info
- list processes / kill [process] / process info [name]
- list services / start/stop/restart service
- startup programs / scheduled tasks

Network:
- wifi on/off / bluetooth on/off / network info
- wifi password / public IP / IP address

Advanced:
- registry read/write / environment variables
- disk info / large files / folder size
- winget search/install/uninstall/list
- USB devices / displays / printers / audio devices
- power plan (balanced/performance/saver)
- Windows features

Web & Search:
- search for [query] / google [query] / open url

Time & Weather:
- what time / what day / weather in [city]

Reminders:
- remind me in X minutes/hours to [task]

Clipboard:
- copy to clipboard [text] / paste from clipboard

Settings:
- open settings [page] — display, sound, network, bluetooth, etc.

PowerShell:
- run command [command] / execute [command] / powershell [command]

For ANY request, you have the ability to control the PC. If someone asks you to do something on the computer, you do it."""


@app.post("/voice/transcribe-audio")
async def voice_transcribe_audio(request: Request):
    """Transcribe audio captured by the browser's getUserMedia.
    
    Accepts binary audio data (webm/opus from MediaRecorder) and transcribes
    it using faster-whisper. This bypasses the Python PortAudio issue where
    sd.rec() records silence on Windows.
    """
    import asyncio as _asyncio
    import numpy as np

    _stt = get_stt()
    audio_bytes = await request.body()

    if not audio_bytes or len(audio_bytes) < 100:
        return {"text": "", "error": "No audio data received"}

    # Convert webm/opus to wav using ffmpeg
    import subprocess
    import tempfile
    import os
    import wave

    webm_path = None
    wav_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(audio_bytes)
            webm_path = f.name
        wav_path = webm_path.replace(".webm", ".wav")
        result = subprocess.run(
            ["ffmpeg", "-i", webm_path, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path, "-y"],
            capture_output=True, timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr.decode(errors='replace')[:200]}")
        with wave.open(wav_path, "rb") as w:
            raw = w.readframes(w.getnframes())
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    finally:
        if webm_path and os.path.exists(webm_path):
            os.unlink(webm_path)
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)

    amp = float(np.abs(samples).max())
    if amp < 0.001:
        return {"text": "", "amplitude": amp, "error": "No speech detected"}

    # Transcribe with faster-whisper
    loop = _asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _stt.transcribe_audio, samples)
    result["amplitude"] = amp
    return result


@app.get("/voice/model")
async def get_stt_model():
    """Get current STT model info."""
    _stt = get_stt()
    device = getattr(_stt, '_device', None) or 'unknown'
    model = getattr(_stt, '_whisper_model_size', None) or 'not loaded'
    return {
        "device": device,
        "model": model,
        "gpu_models": ["large-v3-turbo"],
        "cpu_models": ["small", "base", "tiny"],
        "auto": not _stt_forced_model,
    }


class SttModelRequest(BaseModel):
    model: str | None = None  # None = auto-detect, or force a specific model


@app.post("/voice/model")
async def set_stt_model(request: SttModelRequest):
    """Set STT model. Pass model name to force, or None for auto-detect."""
    import asyncio as _asyncio
    global stt, _stt_forced_model
    _stt_forced_model = request.model is not None
    if request.model:
        # Force a specific model
        stt = SpeechToText(whisper_model=request.model)
    else:
        # Reset to auto-detect
        stt = SpeechToText()
    # Run model loading in executor to avoid blocking the event loop
    loop = _asyncio.get_event_loop()
    await loop.run_in_executor(None, stt.load_model)
    return {
        "device": stt._device,
        "model": stt._whisper_model_size,
        "auto": not _stt_forced_model,
    }


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    provider: str | None = None  # 'ollama', 'openai', 'anthropic', 'gemini', 'openrouter'
    model: str | None = None    # Model ID within the provider


class ReminderRequest(BaseModel):
    message: str
    remind_at: str


class ApiKeyRequest(BaseModel):
    provider: str
    key: str


@app.get("/health")
async def health():
    """Health check with Ollama status and model availability."""
    ollama_ok = await is_ollama_running()
    has_models = await has_available_models() if ollama_ok else False
    return {
        "status": "ok",
        "name": "May",
        "version": "0.2.0",
        "ollama": "connected" if ollama_ok else "disconnected",
        "model": PRIMARY_MODEL,
        "models_available": has_models,
        "mock_mode": ollama_ok and not has_models,
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """Stream chat response from May.

    Supports multi-provider routing via provider/model fields.
    Falls back gracefully if provider is unavailable.
    """
    # Check for system commands first
    msg = request.message.lower().strip()
    command_result = await handle_command(msg, request.message)
    if command_result:
        async def text_stream():
            yield command_result
        return StreamingResponse(text_stream(), media_type="text/plain")

    # If not a direct command, try LLM-powered PC control fallback
    pc_result = await try_pc_control(request.message)
    if pc_result:
        async def text_stream():
            yield pc_result
        return StreamingResponse(text_stream(), media_type="text/plain")

    # Determine provider and model
    provider = request.provider or "ollama"
    model = request.model or PRIMARY_MODEL

    # If using ollama, check it's running
    if provider == "ollama" and not await is_ollama_running():
        async def error_stream():
            yield "Ollama isn't running right now~ Start it with `ollama serve` and try again."
        return StreamingResponse(error_stream(), media_type="text/plain")

    # Build message history for the provider
    provider_messages = []
    for msg_item in request.history[-10:]:
        role = msg_item.get("role", "user")
        if role in ("user", "may"):
            provider_messages.append({
                "role": "user" if role == "user" else "assistant",
                "content": msg_item.get("content", ""),
            })
    provider_messages.append({"role": "user", "content": request.message})

    # Stream LLM response
    async def generate():
        full_response = ""
        try:
            async for chunk in stream_chat_multi(
                provider=provider,
                model=model,
                messages=provider_messages,
                system_prompt=MAY_SYSTEM_PROMPT,
            ):
                full_response += chunk
                yield chunk
        except ValueError as e:
            yield f"\n\n({str(e)})"
        except ConnectionError:
            provider_name = PROVIDERS.get(provider, {}).get("name", provider)
            yield f"\n\n(My backend can't reach {provider_name}~ Check your connection and API key.)"
        except TimeoutError:
            yield "\n\n(I'm thinking too hard on this one~ Try again in a moment.)"
        except Exception as e:
            yield f"\n\n(Something went wrong: {str(e)[:100]})"

        # Background: extract facts from conversation (non-blocking)
        if full_response and provider == "ollama":
            try:
                new_facts = await extract_facts(
                    message=request.message,
                    response=full_response,
                    existing_facts=[f["value"] for f in fact_store.get_all_facts()],
                )
                for fact in new_facts:
                    fact_store.set_fact(
                        key=f"auto_{fact[:50].replace(' ', '_')}",
                        value=fact,
                        category="auto_extracted",
                    )
            except (ConnectionError, TimeoutError, RuntimeError):
                pass  # Don't fail on fact extraction errors

    return StreamingResponse(generate(), media_type="text/plain")


async def handle_command(lower_msg: str, original_msg: str) -> str | None:
    """Check if the message is a system command and handle it.

    Supports natural language for: volume, brightness, apps, files, windows,
    processes, media, keyboard, network, system ops, settings, search, and more.
    """

    # ── Compound commands: route to LLM ──────────────────
    # Detect multi-step commands like "open notepad and write hello"
    compound_separators = [" and ", " then ", " after that "]
    for sep in compound_separators:
        if sep in lower_msg:
            return None  # Let try_pc_control handle multi-step commands

    # ── Volume ────────────────────────────────────────────
    if "set volume" in lower_msg or "volume to" in lower_msg:
        nums = re.findall(r'\d+', original_msg)
        if nums:
            return system.set_volume(int(nums[0]))
    if any(p in lower_msg for p in ["volume up", "turn up", "louder", "increase volume"]):
        current = system.get_volume()
        return system.set_volume(min(100, current + 15))
    if any(p in lower_msg for p in ["volume down", "turn down", "quieter", "decrease volume", "softer"]):
        current = system.get_volume()
        return system.set_volume(max(0, current - 15))
    if any(p in lower_msg for p in ["mute", "silence"]):
        if "unmute" not in lower_msg:
            return system.mute()
    if "unmute" in lower_msg:
        return system.unmute()

    # ── Brightness ────────────────────────────────────────
    if "brightness" in lower_msg and any(w in lower_msg for w in ["set", "to", "change"]):
        nums = re.findall(r'\d+', original_msg)
        if nums:
            return system.set_brightness(int(nums[0]))
    if any(p in lower_msg for p in ["brighter", "increase brightness"]):
        try:
            current = system.get_brightness()
            return system.set_brightness(min(100, current + 15))
        except Exception:
            return "Could not read current brightness~"
    if any(p in lower_msg for p in ["dimmer", "dim", "decrease brightness"]):
        try:
            current = system.get_brightness()
            return system.set_brightness(max(0, current - 15))
        except Exception:
            return "Could not read current brightness~"

    # ── Time & Date ───────────────────────────────────────
    if any(p in lower_msg for p in ["what time", "current time", "tell me the time"]):
        now = datetime.now()
        return f"It's {now.strftime('%I:%M %p')}~"
    if any(p in lower_msg for p in ["what day", "today's date", "what date", "what's today"]):
        now = datetime.now()
        return f"Today is {now.strftime('%A, %B %d, %Y')}~"

    # ── Weather ───────────────────────────────────────────
    if "weather" in lower_msg:
        # Check for location
        loc_match = re.search(r'weather\s+(?:in|for|at)\s+(.+)', lower_msg)
        location = loc_match.group(1) if loc_match else ""
        weather = await system.get_weather(location)
        return f"Here's the weather: {weather}~"

    # ── Open App ──────────────────────────────────────────
    # Skip if already handled by URL/search section above
    if any(lower_msg.startswith(p) for p in ["open ", "launch ", "start ", "run "]):
        if lower_msg.startswith("open url "):
            pass  # Already handled above
        else:
            for prefix in ["open ", "launch ", "start ", "run "]:
                if lower_msg.startswith(prefix):
                    app_name = original_msg[len(prefix):].strip()
                    if app_name:
                        return system.open_app(app_name)
                    return "What should I open?~"

    # ── Close App / Kill Process ──────────────────────────
    if any(p in lower_msg for p in ["close ", "kill ", "quit ", "end "]):
        for prefix in ["close ", "kill ", "quit ", "end "]:
            if prefix in lower_msg:
                target = original_msg[original_msg.lower().find(prefix) + len(prefix):].strip()
                if target:
                    # Try closing window first, then kill process
                    result = system.close_window(target)
                    if "not found" in result.lower():
                        result = system.kill_process(target)
                    return result
                return "What should I close?~"

    # ── Window Management ─────────────────────────────────
    if any(p in lower_msg for p in ["list windows", "open windows", "what's open", "show windows"]):
        return system.list_windows()
    if "minimize" in lower_msg:
        target = re.sub(r'.*minimize\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if target:
            return system.minimize_window(target)
        return "Which window should I minimize?~"
    if "maximize" in lower_msg:
        target = re.sub(r'.*maximize\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if target:
            return system.maximize_window(target)
        return "Which window should I maximize?~"
    if any(p in lower_msg for p in ["focus ", "switch to ", "bring ", "go to "]):
        for prefix in ["focus ", "switch to ", "bring ", "go to "]:
            if prefix in lower_msg:
                target = original_msg[original_msg.lower().find(prefix) + len(prefix):].strip()
                if target:
                    return system.focus_window(target)

    # ── Media Control ─────────────────────────────────────
    # Check next/previous FIRST before play/pause (more specific matches first)
    if any(p in lower_msg for p in ["next song", "next track", "skip song", "skip track", "next"]):
        return system.media_next()
    if any(p in lower_msg for p in ["previous song", "last song", "go back song", "previous track", "go back"]):
        return system.media_previous()
    if any(p in lower_msg for p in ["stop music", "stop playing", "stop media"]):
        return system.media_stop()
    if any(p in lower_msg for p in ["play", "pause", "resume"]):
        return system.media_play_pause()

    # ── Keyboard Shortcuts ────────────────────────────────
    if "press" in lower_msg:
        keys = re.sub(r'.*press\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if keys:
            return system.send_keys(keys)
    if any(p in lower_msg for p in ["alt+tab", "alt tab"]):
        return system.send_keys("alt+tab")
    if any(p in lower_msg for p in ["ctrl+c", "copy selected"]):
        return system.send_keys("ctrl+c")
    if any(p in lower_msg for p in ["ctrl+v", "paste selected"]):
        return system.send_keys("ctrl+v")
    if any(p in lower_msg for p in ["ctrl+x", "cut selected"]):
        return system.send_keys("ctrl+x")
    if any(p in lower_msg for p in ["ctrl+z", "undo"]):
        return system.send_keys("ctrl+z")
    if any(p in lower_msg for p in ["ctrl+s", "save"]):
        return system.send_keys("ctrl+s")
    if any(p in lower_msg for p in ["ctrl+a", "select all"]):
        return system.send_keys("ctrl+a")
    if any(p in lower_msg for p in ["show desktop", "minimize all"]):
        return system.send_keys("win+d")
    if any(p in lower_msg for p in ["alt+f4", "force close"]):
        return system.send_keys("alt+f4")
    if any(p in lower_msg for p in ["ctrl+shift+esc", "task manager"]):
        if "open" not in lower_msg:
            return system.send_keys("ctrl+shift+esc")

    # ── Screenshot ────────────────────────────────────────
    if any(p in lower_msg for p in ["screenshot", "take screenshot", "capture screen"]):
        return system.take_screenshot()

    # ── Clipboard ─────────────────────────────────────────
    if "paste" in lower_msg and "clipboard" in lower_msg:
        return system.get_clipboard()
    if "copy" in lower_msg and "clipboard" in lower_msg:
        idx = original_msg.lower().find("copy")
        text = original_msg[idx + 4:].strip().strip('"' '')
        if text:
            return system.copy_to_clipboard(text)
        return "What should I copy?~"

    # ── Text Input ────────────────────────────────────────
    if any(p in lower_msg for p in ["type ", "write ", "input "]):
        for prefix in ["type ", "write ", "input "]:
            if prefix in lower_msg:
                text = original_msg[original_msg.lower().find(prefix) + len(prefix):].strip()
                if text:
                    return system.type_text(text)

    # ── File Operations ───────────────────────────────────
    if lower_msg.startswith("read file ") or lower_msg.startswith("read "):
        file_path = original_msg.split(maxsplit=1)[1] if len(original_msg.split()) > 1 else ""
        if file_path:
            content = system.read_file(file_path)
            return f"Here's the content:\n\n{content}"
    if "list directory" in lower_msg or "ls" == lower_msg.strip() or "list files" in lower_msg:
        return system.list_directory(".")
    if lower_msg.startswith("open folder ") or lower_msg.startswith("open directory "):
        folder = re.sub(r'.*(?:open folder|open directory)\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if folder:
            return system.open_folder(folder)
        return "Which folder should I open?~"
    if any(p in lower_msg for p in ["move file", "rename file"]):
        parts = original_msg.split(" to ")
        if len(parts) == 2:
            src = parts[0].split(maxsplit=1)[-1].strip()
            dst = parts[1].strip()
            return system.move_file(src, dst)
        return "Usage: move file [source] to [destination]~"
    if "delete file" in lower_msg or "remove file" in lower_msg:
        file_path = re.sub(r'.*(?:delete file|remove file)\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if file_path:
            return system.delete_file(file_path)
        return "Which file should I delete?~"

    # ── Network Control ───────────────────────────────────
    if any(p in lower_msg for p in ["wifi on", "enable wifi", "turn on wifi", "turn wifi on"]):
        return system.toggle_wifi(True)
    if any(p in lower_msg for p in ["wifi off", "disable wifi", "turn off wifi", "turn wifi off"]):
        return system.toggle_wifi(False)
    if any(p in lower_msg for p in ["bluetooth on", "enable bluetooth", "bluetooth off", "disable bluetooth"]):
        enable = "on" in lower_msg or "enable" in lower_msg
        return system.toggle_bluetooth(enable)

    # ── System Operations ─────────────────────────────────
    if any(p in lower_msg for p in ["shutdown", "shut down", "turn off pc", "turn off computer"]):
        nums = re.findall(r'\d+', original_msg)
        delay = int(nums[0]) * 60 if nums else 0
        return system.shutdown(delay)
    if any(p in lower_msg for p in ["restart", "reboot"]):
        nums = re.findall(r'\d+', original_msg)
        delay = int(nums[0]) * 60 if nums else 0
        return system.restart(delay)
    if any(p in lower_msg for p in ["sleep pc", "put to sleep", "pc sleep", "hibernate"]):
        return system.sleep_pc()
    if any(p in lower_msg for p in ["lock screen", "lock pc", "lock workstation"]):
        return system.lock_pc()
    if any(p in lower_msg for p in ["cancel shutdown", "abort shutdown"]):
        return system.cancel_shutdown()

    # ── Web & Search (checked BEFORE Open App to catch 'open url') ────
    if any(p in lower_msg for p in ["search for ", "google ", "search "]):
        for prefix in ["search for ", "google ", "search "]:
            if prefix in lower_msg:
                query = original_msg[original_msg.lower().find(prefix) + len(prefix):].strip()
                if query:
                    return system.web_search(query)
    if lower_msg.startswith("open url "):
        url = original_msg[len("open url "):].strip()
        if url:
            return system.open_url(url)
    if re.match(r'^(?:go to|navigate to)\s+https?://', lower_msg):
        url = re.sub(r'^(?:go to|navigate to)\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if url:
            return system.open_url(url)

    # ── Settings ──────────────────────────────────────────
    if any(p in lower_msg for p in ["open settings", "show settings"]):
        page = re.sub(r'.*(?:open settings|show settings)\s*', '', original_msg, flags=re.IGNORECASE).strip()
        return system.open_settings(page)

    # ── Process Management ────────────────────────────────
    if any(p in lower_msg for p in ["list processes", "running processes", "what's running"]):
        return system.list_processes()
    if any(p in lower_msg for p in ["process info", "about process"]):
        target = re.sub(r'.*(?:process info|about process)\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if target:
            return system.get_process_info(target)
        return "Which process?~"

    # ── Service Management ────────────────────────────────
    if any(p in lower_msg for p in ["list services", "running services"]):
        filter_str = re.sub(r'.*(?:list services|running services)\s*', '', original_msg, flags=re.IGNORECASE).strip()
        return system.list_services(filter_str)
    if any(p in lower_msg for p in ["start service", "start the service"]):
        target = re.sub(r'.*(?:start service|start the service)\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if target:
            return system.start_service(target)
        return "Which service should I start?~"
    if any(p in lower_msg for p in ["stop service", "stop the service"]):
        target = re.sub(r'.*(?:stop service|stop the service)\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if target:
            return system.stop_service(target)
        return "Which service should I stop?~"
    if any(p in lower_msg for p in ["restart service"]):
        target = re.sub(r'.*restart service\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if target:
            return system.restart_service(target)
        return "Which service should I restart?~"

    # ── Mouse Control ─────────────────────────────────────
    if "click" in lower_msg:
        nums = re.findall(r'\d+', original_msg)
        if len(nums) >= 2:
            button = "right" if "right" in lower_msg else "middle" if "middle" in lower_msg else "left"
            return system.mouse_click(int(nums[0]), int(nums[1]), button)
    if "move mouse" in lower_msg or "move cursor" in lower_msg:
        nums = re.findall(r'\d+', original_msg)
        if len(nums) >= 2:
            return system.mouse_move(int(nums[0]), int(nums[1]))
    if "scroll" in lower_msg:
        nums = re.findall(r'[-]?\d+', original_msg)
        clicks = int(nums[0]) if nums else (-3 if "down" in lower_msg else 3)
        return system.mouse_scroll(clicks)
    if "drag" in lower_msg:
        nums = re.findall(r'\d+', original_msg)
        if len(nums) >= 4:
            return system.mouse_drag(int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3]))
    if any(p in lower_msg for p in ["mouse position", "cursor position", "where is my mouse"]):
        return system.get_mouse_position()

    # ── Network Info ──────────────────────────────────────
    if any(p in lower_msg for p in ["network info", "my ip", "ip address", "what's my ip", "what is my ip"]):
        if "public" in lower_msg or "external" in lower_msg or "what's my ip" in lower_msg:
            return system.get_public_ip()
        return system.get_network_info()
    if any(p in lower_msg for p in ["wifi password", "wifi pass", "wifi key"]):
        return system.get_wifi_password()

    # ── Registry ──────────────────────────────────────────
    if any(p in lower_msg for p in ["read registry", "get registry"]):
        path = re.sub(r'.*(?:read registry|get registry)\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if path:
            return system.read_registry(path)
        return "Which registry path?~"
    if any(p in lower_msg for p in ["write registry", "set registry"]):
        parts = re.split(r'\s+(?:to|=)\s+', original_msg, maxsplit=1)
        if len(parts) >= 2:
            path_part = parts[0].strip()
            # Try to extract registry value name from path (last backslash segment)
            path_parts = path_part.rsplit('\\', 1)
            if len(path_parts) == 2:
                return system.write_registry(path_parts[0].strip(), path_parts[1].strip(), parts[1].strip())
            return system.write_registry(path_part, "Value", parts[1].strip())
        return r"Usage: write registry [path\name] to [value]~"

    # ── Startup Programs ──────────────────────────────────
    if any(p in lower_msg for p in ["list startup", "startup programs", "what starts on boot"]):
        return system.list_startup_programs()

    # ── Disk Management ───────────────────────────────────
    if any(p in lower_msg for p in ["disk info", "disk usage", "disk space", "hard drive"]):
        return system.get_disk_info()
    if any(p in lower_msg for p in ["large files", "big files", "find big"]):
        nums = re.findall(r'\d+', original_msg)
        min_mb = int(nums[0]) if nums else 100
        return system.get_large_files(".", min_mb)
    if any(p in lower_msg for p in ["folder size", "directory size"]):
        folder = re.sub(r'.*(?:folder size|directory size)\s+', '', original_msg, flags=re.IGNORECASE).strip() or "."
        return system.get_folder_size(folder)

    # ── Environment Variables ──────────────────────────────
    if any(p in lower_msg for p in ["get env", "env var", "environment variable", "get environment"]):
        var_name = re.sub(r'.*(?:get env|env var|environment variable|get environment)\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if var_name:
            return system.get_env_var(var_name)
        return system.list_env_vars()
    if any(p in lower_msg for p in ["list env", "list environment", "all env vars"]):
        return system.list_env_vars()

    # ── Power Management ──────────────────────────────────
    if any(p in lower_msg for p in ["battery", "battery info", "battery status"]):
        return system.get_battery_info()
    if any(p in lower_msg for p in ["power plan", "power settings"]):
        if any(w in lower_msg for w in ["set", "change", "to"]):
            plan = re.sub(r'.*(?:power plan|power settings)\s*(?:to|=)?\s*', '', original_msg, flags=re.IGNORECASE).strip()
            if plan:
                return system.set_power_plan(plan)
        return system.get_power_plan()

    # ── Device Management ─────────────────────────────────
    if any(p in lower_msg for p in ["usb devices", "usb", "connected devices"]):
        return system.list_usb_devices()
    if any(p in lower_msg for p in ["displays", "monitors", "screens"]):
        return system.list_displays()
    if any(p in lower_msg for p in ["printers", "list printers"]):
        return system.list_printers()
    if any(p in lower_msg for p in ["audio devices", "sound devices", "speakers", "microphone"]):
        return system.list_audio_devices()

    # ── Package Management ────────────────────────────────
    if any(p in lower_msg for p in ["winget search", "find package", "search package"]):
        query = re.sub(r'.*(?:winget search|find package|search package)\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if query:
            return system.winget_search(query)
        return "What should I search for?~"
    if any(p in lower_msg for p in ["winget install", "install package", "install app"]):
        target = re.sub(r'.*(?:winget install|install package|install app)\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if target:
            return system.winget_install(target)
        return "What should I install?~"
    if any(p in lower_msg for p in ["winget uninstall", "uninstall package"]):
        target = re.sub(r'.*(?:winget uninstall|uninstall package)\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if target:
            return system.winget_uninstall(target)
        return "What should I uninstall?~"
    if any(p in lower_msg for p in ["installed packages", "list installed", "my apps"]):
        return system.winget_list_installed()

    # ── Scheduled Tasks ───────────────────────────────────
    if any(p in lower_msg for p in ["scheduled tasks", "tasks scheduler", "cron jobs"]):
        return system.list_scheduled_tasks()

    # ── Search Files ──────────────────────────────────────
    if any(p in lower_msg for p in ["search files", "find files", "find file"]):
        pattern = re.sub(r'.*(?:search files|find files|find file)\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if pattern:
            return system.search_files(".", pattern)
        return "What file pattern?~"
    if any(p in lower_msg for p in ["file info", "about file"]):
        target = re.sub(r'.*(?:file info|about file)\s+', '', original_msg, flags=re.IGNORECASE).strip()
        if target:
            return system.get_file_info(target)
        return "Which file?~"

    # ── System Info ───────────────────────────────────────
    if any(p in lower_msg for p in ["system info", "systeminfo", "computer info", "about this pc"]):
        return system.get_system_info()

    # ── Reminders ─────────────────────────────────────────
    if "remind me" in lower_msg or "set reminder" in lower_msg:
        minutes = 0
        if "in " in lower_msg:
            nums = re.findall(r'(\d+)\s*(min|hour|hr)', lower_msg)
            for num, unit in nums:
                if "min" in unit:
                    minutes += int(num)
                elif "hour" in unit or "hr" in unit:
                    minutes += int(num) * 60
        if minutes > 0:
            remind_at = (datetime.now() + timedelta(minutes=minutes)).isoformat()
            reminder_msg = original_msg
            rid = fact_store.add_reminder(reminder_msg, remind_at)
            return f"Reminder set! I'll remind you in {minutes} minutes~"
        return "When should I remind you? Try 'Remind me in 30 minutes to...'~"

    # ── PowerShell / CMD Execution ────────────────────────
    if any(p in lower_msg for p in ["run command ", "execute ", "powershell ", "cmd ", "run cmd "]):
        for prefix in ["run command ", "execute ", "powershell ", "cmd ", "run cmd "]:
            if prefix in lower_msg:
                cmd = original_msg[original_msg.lower().find(prefix) + len(prefix):].strip()
                if cmd:
                    return system.run_powershell(cmd)

    return None  # Not a system command — let LLM handle it


async def try_pc_control(message: str) -> str | None:
    """Use the LLM to translate a natural language request into a PC command.
    
    This is the fallback for commands the parser doesn't recognize.
    The LLM generates a PowerShell command which we then execute.
    Handles compound commands by splitting on separators.
    """
    if not is_pc_command(message):
        return None
    
    # Check for compound commands (e.g. "open notepad and write hello")
    compound_separators = [" and ", " then ", " after that "]
    parts = [message]
    for sep in compound_separators:
        if sep in message.lower():
            parts = [p.strip() for p in re.split(sep, message, flags=re.IGNORECASE) if p.strip()]
            break
    
    results = []
    for part in parts:
        result = await _execute_pc_command(part)
        if result:
            results.append(result)
    
    if results:
        return "\n".join(results)
    return None


async def _execute_pc_command(message: str) -> str | None:
    """Execute a single PC command via LLM translation."""
    try:
        pc_messages = [
            {"role": "user", "content": message},
        ]
        
        full_response = ""
        async for chunk in stream_chat_multi(
            provider="ollama",
            model=PRIMARY_MODEL,
            messages=pc_messages,
            system_prompt=PC_CONTROLLER_PROMPT,
        ):
            full_response += chunk
        
        cmd_data = parse_llm_response(full_response)
        if cmd_data and cmd_data["command"]:
            action = cmd_data["action"]
            command = cmd_data["command"]
            needs_confirm = cmd_data["needs_confirm"]
            
            # Safety: skip destructive commands without confirmation
            if needs_confirm:
                return f"⚠️ This action requires confirmation: {action}. Command: {command}. Please confirm by typing the command directly."
            
            # Execute the generated command
            result = system.run_powershell(command)
            return f"{action}: {result}"
    except Exception as e:
        logger.warning(f"PC control LLM fallback failed: {e}")
    
    return None


@app.get("/facts")
async def get_facts():
    """Get all stored user facts."""
    return {"facts": fact_store.get_all_facts()}


@app.post("/facts")
async def set_fact(request: Request):
    """Store a user fact."""
    data = await request.json()
    fact_store.set_fact(
        key=data.get("key", ""),
        value=data.get("value", ""),
        category=data.get("category", "general"),
    )
    return {"status": "ok"}


@app.get("/reminders")
async def get_reminders():
    """Get pending reminders."""
    return {"reminders": fact_store.get_pending_reminders()}


@app.post("/reminders")
async def create_reminder(request: ReminderRequest):
    """Create a new reminder."""
    rid = fact_store.add_reminder(request.message, request.remind_at)
    return {"status": "ok", "id": rid}


@app.post("/reminders/{reminder_id}/complete")
async def complete_reminder(reminder_id: int):
    """Mark a reminder as completed."""
    fact_store.complete_reminder(reminder_id)
    return {"status": "ok"}


# ── Memory (vector store) endpoints ───────────────────────────────────────


class ConversationStoreRequest(BaseModel):
    summary: str
    messages: list[dict] = []
    topic: str = "general"


# ── Provider / Model endpoints ──────────────────────────────────────────────


@app.get("/providers")
async def get_providers():
    """List all available providers with their key status."""
    key_status = get_all_key_status()
    result = []
    for provider_id, provider_info in PROVIDERS.items():
        result.append({
            "id": provider_id,
            "name": provider_info["name"],
            "requires_key": provider_info["requires_key"],
            "has_key": key_status.get(provider_id, False),
            "models": provider_info["models"],
        })
    return {"providers": result}


@app.get("/api-keys")
async def list_api_keys():
    """Get which providers have API keys configured (not the actual keys)."""
    return {"status": get_all_key_status()}


@app.post("/api-keys")
async def save_api_key(request: ApiKeyRequest):
    """Save an API key for a provider."""
    if request.provider not in PROVIDERS:
        return {"error": f"Unknown provider: {request.provider}"}
    set_api_key(request.provider, request.key)
    return {"status": "ok", "provider": request.provider}


@app.delete("/api-keys/{provider}")
async def remove_api_key(provider: str):
    """Remove an API key for a provider."""
    delete_api_key(provider)
    return {"status": "ok", "provider": provider}


@app.get("/models")
async def list_models():
    """List all available models across all providers."""
    key_status = get_all_key_status()
    models = []
    for provider_id, provider_info in PROVIDERS.items():
        has_key = key_status.get(provider_id, False)
        for m in provider_info["models"]:
            models.append({
                "provider": provider_id,
                "provider_name": provider_info["name"],
                "id": m["id"],
                "name": m["name"],
                "fast": m["fast"],
                "available": has_key,
            })
    return {"models": models}


@app.get("/models/openrouter")
async def list_openrouter_models():
    """Fetch live models from OpenRouter API + merge with hardcoded list."""
    has_key = get_all_key_status().get("openrouter", False)
    live_models = await fetch_openrouter_models()
    hardcoded = [
        {"provider": "openrouter", "provider_name": "OpenRouter", **m, "available": has_key}
        for m in PROVIDERS["openrouter"]["models"]
    ]
    hardcoded_ids = {h["id"] for h in hardcoded}
    live = [
        {
            "provider": "openrouter",
            "provider_name": "OpenRouter",
            "id": m["id"],
            "name": m["name"],
            "fast": m["fast"],
            "available": has_key,
            "live": True,
        }
        for m in live_models
        if m["id"] not in hardcoded_ids
    ]
    return {"models": hardcoded + live, "live_count": len(live)}


class MemorySearchRequest(BaseModel):
    query: str
    n_results: int = 5
    time_filter_days: int | None = None


@app.post("/memory/store")
async def store_conversation(request: ConversationStoreRequest):
    """Store a summarized conversation in episodic memory."""
    conv_id = await vector_store.store_conversation(
        summary=request.summary,
        messages=request.messages,
        topic=request.topic,
    )
    return {"status": "ok", "id": conv_id}


@app.post("/memory/search")
async def search_memory(request: MemorySearchRequest):
    """Search episodic memory by semantic similarity."""
    results = await vector_store.search(
        query=request.query,
        n_results=request.n_results,
        time_filter_days=request.time_filter_days,
    )
    return {"results": results}


@app.get("/memory/recent")
async def get_recent_memory(n: int = 10):
    """Get the N most recent conversation summaries."""
    return {"conversations": await vector_store.get_recent(n)}


@app.get("/memory/stats")
async def memory_stats():
    """Get memory system statistics."""
    return await vector_store.get_stats()


@app.post("/memory/prune")
async def prune_memory(days_old: int = 90):
    """Remove memories older than N days."""
    removed = await vector_store.prune_old(days_old)
    return {"status": "ok", "removed": removed}


@app.get("/system/stats")
async def system_stats():
    """Get real-time system stats (RAM and GPU usage)."""
    return system.get_system_stats()


# ── Reminder / Notification endpoints ──────────────────────────────────────


@app.get("/reminders/check")
async def check_reminders():
    """Manually check for due reminders and send notifications."""
    sent = await check_and_send_reminders(fact_store)
    return {"sent": sent, "count": len(sent)}


@app.post("/notifications/test")
async def test_notification():
    """Send a test toast notification."""
    success = send_toast("May says hi~", "This is a test notification from your AI companion.")
    return {"status": "ok" if success else "failed"}


@app.on_event("startup")
async def start_reminder_checker():
    """Start the background reminder checker on server startup."""
    await reminder_checker.start()


@app.on_event("shutdown")
async def stop_reminder_checker():
    """Stop the background reminder checker on server shutdown."""
    await reminder_checker.stop()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
