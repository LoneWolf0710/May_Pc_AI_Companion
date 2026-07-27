"""May AI Companion — Python Backend Server.

FastAPI server that handles:
- Chat with Ollama (streaming, with model routing)
- System control (volume, brightness, apps, files)
- Voice processing (STT + TTS)
- Memory (facts + vector store)
"""

from contextlib import asynccontextmanager
import json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
from datetime import datetime
import os as _os
import sys as _sys
import time

# Add project root (may/) to sys.path so 'from core.*' imports work
_project_root = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), ".."))
if _project_root not in _sys.path:
    _sys.path.insert(0, _project_root)

from llm.ollama_client import (
    is_ollama_running,
    has_available_models,
    PRIMARY_MODEL,
    extract_facts,
)
from llm.ollama_config import check_ollama_config, set_ollama_env_vars, get_ollama_config_summary
from settings import get_setting
from llm.providers import (
    PROVIDERS,
    set_api_key,
    delete_api_key,
    get_all_key_status,
    refresh_openrouter_free_models,
    refresh_ollama_cloud_models,
    refresh_ollama_local_models,
    get_free_models_status,
    get_ollama_local_status,
    get_ollama_cloud_status,
    close_http_clients,
)
from llm.jarvis import jarvis_chat
from llm.tool_tiering import invalidate_tool_cache
from system.notifications import ReminderChecker, send_toast, check_and_send_reminders
from memory.fact_store import FactStore
from memory.vector_store import VectorStore
from memory.skill_store import SkillStore
from memory.memory_injector import MemoryInjector
# pc_controller removed — all PC control routed through daemon via core_bridge
from voice.stt import SpeechToText
from voice.streaming_stt import get_streaming_stt
from voice.audio_emotion import AudioEmotionAnalyzer
import logging
import subprocess as _subprocess
import threading as _threading
import asyncio
logger = logging.getLogger("may.main")

# P6: Personality Modes + Security Monitor (lazy-initialized)
personality_modes = None
security_monitor = None


# ── Auto-start the Control Core daemon ────────────────────────────────────
def _start_core_daemon():
    """Start the Control Core daemon if not already running.

    After launching the subprocess, waits up to 10 seconds for the daemon
    to become TCP-reachable on port 7650 before returning.
    """
    try:
        from core.client import is_daemon_running_sync
        if is_daemon_running_sync():
            logger.info("Control Core daemon already running")
            return True
    except Exception as e:
        logger.debug("Could not check daemon status: %s", e)

    try:
        daemon_script = _os.path.join(_os.path.dirname(__file__), "..", "core", "daemon.py")
        if not _os.path.exists(daemon_script):
            logger.warning("Control Core daemon script not found at %s", daemon_script)
            return False

        # Start daemon as a detached process (debug mode = run as console app)
        # Log daemon output to ~/.may/control_core.log for crash diagnostics
        import os as _os_mod
        _log_dir = _os_mod.path.join(_os_mod.path.expanduser("~"), ".may")
        _os_mod.makedirs(_log_dir, exist_ok=True)
        _daemon_log = _os_mod.path.join(_log_dir, "control_core.log")
        _daemon_log_fh = open(_daemon_log, "a", encoding="utf-8")
        try:
            _subprocess.Popen(
                [_sys.executable, daemon_script, "debug"],
                creationflags=(_subprocess.CREATE_NO_WINDOW if hasattr(_subprocess, 'CREATE_NO_WINDOW') else 0),
                stdout=_daemon_log_fh,
                stderr=_daemon_log_fh,
            )
        finally:
            _daemon_log_fh.close()  # Popen inherits the fd; safe to close parent handle
        logger.info("Control Core daemon started — waiting for readiness...")

        # Readiness probe: poll TCP port 7650 up to 10s (20 x 0.5s)
        import socket as _socket
        for _attempt in range(20):
            time.sleep(0.5)
            sock = None
            try:
                sock = _socket.create_connection(("127.0.0.1", 7650), timeout=1)
                logger.info("Control Core daemon ready on port 7650")
                return True
            except (ConnectionRefusedError, OSError):
                continue
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
        logger.warning("Control Core daemon did not become ready within 10s — proceeding anyway")
        return True  # Still return True; health check will restart if needed
    except Exception as e:
        logger.warning("Failed to start Control Core daemon: %s", e)
        return False


# ── Global instances ───────────────────────────────────────────────────────
# SystemControl removed — all tools routed through Control Core daemon via core_bridge
fact_store = FactStore()
vector_store = VectorStore()
skill_store = SkillStore()
memory_injector = MemoryInjector(vector_store=vector_store, fact_store=fact_store, skill_store=skill_store)
reminder_checker = ReminderChecker(fact_store)

# Daemon health check (auto-restart if it crashes)
_daemon_health_stop = _threading.Event()


def _daemon_health_loop():
    """Periodically check if daemon is running and restart if crashed."""
    try:
        from core.client import is_daemon_running_sync
    except ImportError:
        return

    # Wait for daemon to initialize before first health check
    _daemon_health_stop.wait(15)  # Initial delay for daemon startup
    while not _daemon_health_stop.is_set():
        _daemon_health_stop.wait(30)  # Check every 30 seconds
        if _daemon_health_stop.is_set():
            break
        try:
            if not is_daemon_running_sync():
                logger.warning("Daemon health check: daemon not running, restarting...")
                _start_core_daemon()
        except Exception as e:
            logger.debug("Daemon health check error: %s", e)    # Intelligence layer (lazy-initialized)
shadow_learner = None
frustration_detector = None
screen_watcher = None
wake_word_detector = None
privacy_mode = None
proactive_assistant = None
meeting_mode = None
ghost_mode = None
tone_analyzer = None
from intelligence.control_modes import ControlModes as _ControlModesEager
control_modes = _ControlModesEager()  # Eager init — available before background thread completes
mood_history = None
endocrine_system = None
sleep_cycle = None
audio_emotion = None


def _load_intelligence():
    """Load intelligence modules in background (heavy imports).

    Note: Screen watcher is started separately in the lifespan handler
    (asyncio.create_task) since this runs in a background thread.
    """
    global shadow_learner, frustration_detector, screen_watcher, wake_word_detector, privacy_mode, meeting_mode, ghost_mode, tone_analyzer, control_modes, memory_injector, behavioral_profile, immune_system, personality_modes, security_monitor, endocrine_system, sleep_cycle
    try:
        from intelligence.shadow_learner import ShadowLearner
        from intelligence.frustration_detector import FrustrationDetector
        from intelligence.screen_watcher import ScreenWatcher
        from intelligence.wake_word import WakeWordDetector
        from intelligence.privacy_mode import PrivacyMode
        from intelligence.meeting_mode import MeetingMode
        from intelligence.ghost_mode import GhostMode
        from intelligence.tone_analyzer import ToneAnalyzer
        # control_modes already initialized eagerly at module level (line ~172)
        from intelligence.mood_history import MoodHistory
        shadow_learner = ShadowLearner()
        frustration_detector = FrustrationDetector()
        screen_watcher = ScreenWatcher()
        wake_word_detector = WakeWordDetector()
        privacy_mode = PrivacyMode()
        meeting_mode = MeetingMode()
        ghost_mode = GhostMode()
        tone_analyzer = ToneAnalyzer()
        # control_modes reused from module-level init (not re-instantiated)
        mood_history = MoodHistory()
        # Pass the global STT instance to meeting mode (avoids double-loading)
        meeting_mode.set_stt(get_stt())
        from intelligence.proactive_assistant import ProactiveAssistant
        proactive_assistant = ProactiveAssistant()
        # Register shadow learner with jarvis.py (avoids circular import)
        from llm.jarvis import set_shadow_learner, set_control_modes
        set_shadow_learner(shadow_learner)
        set_control_modes(control_modes)
        # P6: Wire personality modes into jarvis.py
        from llm.jarvis import set_personality_modes
        set_personality_modes(personality_modes)
        # P5: Wire skill store into shadow learner for auto-skill creation
        shadow_learner.set_skill_store(skill_store)
        # Wire memory injector into jarvis.py for context injection
        from llm.jarvis import set_memory_injector, set_skill_store
        set_memory_injector(memory_injector)
        set_skill_store(skill_store)
        # Wire shadow learner + tone analyzer into memory injector
        memory_injector.set_shadow_learner(shadow_learner)
        memory_injector.set_tone_analyzer(tone_analyzer)
        # Wire immune system + behavioral profile for adaptive verification
        from system.behavioral_profile import BehavioralProfile
        from system.immune_system import ImmuneSystem
        behavioral_profile = BehavioralProfile()
        immune_system = ImmuneSystem()
        immune_system.set_behavioral_profile(behavioral_profile)
        immune_system.set_control_modes(control_modes)
        from llm.jarvis import set_immune_system
        set_immune_system(immune_system)
        # Initialize tracing
        from system.tracing import init_tracing
        init_tracing()
        # Register all modules with privacy mode
        privacy_mode.register_module("shadow_learner", shadow_learner)
        privacy_mode.register_module("frustration_detector", frustration_detector)
        privacy_mode.register_module("screen_watcher", screen_watcher)
        privacy_mode.register_module("wake_word", wake_word_detector)
        # Wire ghost mode to tool executor AND jarvis_chat
        from llm.jarvis import execute_tool
        ghost_mode.set_executor(execute_tool)
        from llm.jarvis import jarvis_chat as _jarvis_chat_fn
        ghost_mode.set_jarvis_chat(_jarvis_chat_fn)
        # P6: Wire workflow engine to tool executor
        from intelligence.workflows import get_workflow_engine
        _wf_engine = get_workflow_engine()
        _wf_engine.set_executor(execute_tool)
        # P7: Wire LLM chat function for async-safe NL fallback
        _wf_engine.set_chat_fn(_jarvis_chat_fn)
        # Register control modes with privacy mode
        privacy_mode.register_module("control_modes", control_modes)
        # P6: Personality modes
        from intelligence.personality_modes import PersonalityModes
        personality_modes = PersonalityModes()
        # P6: Security monitor
        from intelligence.security_monitor import SecurityMonitor
        security_monitor = SecurityMonitor()
        # P4: Conditioned reflexes (embedding-based learned responses)
        from intelligence.conditioned_reflexes import get_conditioned_reflexes
        conditioned_reflexes = get_conditioned_reflexes()
        from llm.jarvis import set_conditioned_reflexes, set_screen_watcher_for_context
        set_conditioned_reflexes(conditioned_reflexes)
        set_screen_watcher_for_context(screen_watcher)
        logger.info("P4: Conditioned reflexes and Tier 2 screen context wired into jarvis")
        # P4: Register OCR reader with screen watcher
        from intelligence.ocr_reader import OCRReader
        screen_watcher._ocr_reader = OCRReader()
        logger.info("P4: PaddleOCR reader registered with screen watcher")
        # P3: Endocrine system (immutable emotional state)
        from intelligence.endocrine import EndocrineSystem
        endocrine_system = EndocrineSystem()
        # Wire endocrine into immune system for emotional context
        immune_system.set_endocrine_system(endocrine_system)
        # P3: Sleep cycle (idle-time consolidation)
        from intelligence.sleep_cycle import get_sleep_cycle as _get_sleep
        sleep_cycle = _get_sleep()
        sleep_cycle.set_ollama_url("http://localhost:11435")
        logger.info("Intelligence layer loaded (shadow learner, frustration detector, screen watcher, wake word, privacy mode, proactive assistant, meeting mode, ghost mode, tone analyzer, control modes, mood history, endocrine, sleep cycle, personality modes, security monitor)")
    except Exception as e:
        logger.error("Failed to load intelligence layer: %s", e)


# Voice system (lazy-initialized)
# M2 FIX: Lock protects stt/_stt_forced_model from concurrent read/write
# (e.g., /voice/model POST while /voice/transcribe-audio POST is reading)
stt: SpeechToText | None = None
_stt_forced_model: bool = False
_stt_lock = asyncio.Lock()


def get_stt() -> SpeechToText:
    global stt
    if stt is None:
        stt = SpeechToText()
    return stt


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler: startup & shutdown logic (replaces deprecated on_event)."""
    # ── Startup ────────────────────────────────────────────────────────────
    # Check Ollama env var configuration — auto-set if missing, then warn only if still missing
    try:
        ollama_cfg = check_ollama_config()
        if ollama_cfg["status"] != "optimal":
            # Auto-set missing env vars via setx (persistent) + os.environ (immediate)
            try:
                set_result = set_ollama_env_vars()
                if set_result["status"] == "ok":
                    logger.info("Ollama env vars auto-configured. Restart Ollama service for full effect.")
                else:
                    logger.info("Ollama env vars partially configured: %s", set_result.get("message", ""))
            except Exception as se:
                logger.debug("Auto-set Ollama env vars failed (non-critical): %s", se)
            # Re-check after auto-set — only warn if still missing
            ollama_cfg = check_ollama_config()
            if ollama_cfg["status"] != "optimal":
                logger.warning("Ollama config suboptimal (%s). Missing: %s", ollama_cfg["status"], ollama_cfg["missing_vars"])
        else:
            logger.info("Ollama config: optimal")
    except Exception as e:
        logger.debug("Ollama config check failed: %s", e)

    # Start the Control Core daemon (with readiness wait — blocks up to 10s)
    _threading.Thread(target=_start_core_daemon, daemon=True).start()

    # Pre-load STT model in a subprocess so torch native crashes
    # (STATUS_STACK_BUFFER_OVERRUN in torch_python.dll) don't kill the backend.
    def _preload_stt():
        import subprocess as _sp, sys as _sys, os as _os_mod, textwrap as _tw
        preload_script = _tw.dedent("""\
            import sys, os
            os.environ['CUDA_VISIBLE_DEVICES'] = ''
            try:
                from voice.stt import SpeechToText
                stt = SpeechToText()
                stt.load_model()
            except Exception:
                pass
        """)
        try:
            logger.info("Pre-loading STT model in subprocess...")
            _sp.run(
                [_sys.executable, "-c", preload_script],
                timeout=60,
                creationflags=(_sp.CREATE_NO_WINDOW if hasattr(_sp, 'CREATE_NO_WINDOW') else 0),
                stdout=_sp.DEVNULL,
                stderr=_sp.DEVNULL,
            )
            logger.info("STT model pre-load subprocess finished")
        except _sp.TimeoutExpired:
            logger.warning("STT pre-load subprocess timed out (60s)")
        except Exception as e:
            logger.error("STT pre-load subprocess failed: %s", e)

    _threading.Thread(target=_preload_stt, daemon=True).start()

    # Start the background reminder checker
    await reminder_checker.start()

    # Start daemon health check (auto-restart if daemon crashes)
    _threading.Thread(target=_daemon_health_loop, daemon=True).start()

    # Start intelligence layer in background
    _threading.Thread(target=_load_intelligence, daemon=True).start()

    # Start screen watcher, proactive assistant, and ghost mode once modules are loaded
    import asyncio as _asyncio
    async def _start_screen_watcher():
        try:
            # Poll until intelligence modules are loaded by background thread (max 15s)
            for _ in range(30):
                await _asyncio.sleep(0.5)
                if screen_watcher is not None:
                    break
            if screen_watcher:
                await screen_watcher.start()
                logger.info("Screen watcher started")
            else:
                logger.warning("Screen watcher failed to load after 15s")
            if proactive_assistant:
                await proactive_assistant.start()
                logger.info("Proactive assistant started")
            if ghost_mode:
                ghost_mode.start()
                logger.info("Ghost mode started")
            if security_monitor:
                await security_monitor.start()
                logger.info("Security monitor started")
        except Exception as e:
            logger.debug("Screen watcher/proactive assistant start failed: %s", e)
    _asyncio.create_task(_start_screen_watcher())

    # Refresh OpenRouter free models from API (background, non-blocking)
    async def _refresh_free_models():
        try:
            result = await refresh_openrouter_free_models(force=True)
            logger.info("OpenRouter free models: %s (%d models)", result.get("source", "unknown"), result.get("free_count", 0))
        except Exception as e:
            logger.debug("OpenRouter free models refresh failed: %s", e)
    _asyncio.create_task(_refresh_free_models())

    # Refresh Ollama Cloud models from API (background, non-blocking)
    async def _refresh_ollama_cloud():
        try:
            result = await refresh_ollama_cloud_models(force=True)
            logger.info("Ollama Cloud models: %s (%d models)", result.get("source", "unknown"), result.get("model_count", 0))
        except Exception as e:
            logger.debug("Ollama Cloud models refresh failed: %s", e)
    _asyncio.create_task(_refresh_ollama_cloud())

    # Refresh local Ollama models from localhost:11434 (background, non-blocking)
    async def _refresh_ollama_local():
        try:
            result = await refresh_ollama_local_models(force=True)
            logger.info("Ollama local models: %s (%d models)", result.get("source", "unknown"), result.get("model_count", 0))
        except Exception as e:
            logger.debug("Ollama local models refresh failed: %s", e)
    _asyncio.create_task(_refresh_ollama_local())

    # P3: Start sleep cycle background loop
    async def _start_sleep_cycle():
        try:
            # Poll until intelligence modules are loaded
            for _ in range(30):
                await _asyncio.sleep(0.5)
                if sleep_cycle is not None:
                    break
            if sleep_cycle:
                await sleep_cycle.start_background_loop()
        except Exception as e:
            logger.debug("Sleep cycle failed to start: %s", e)
    _asyncio.create_task(_start_sleep_cycle())

    # P2: Background health check loop (every 60s)
    async def _health_check_loop():
        try:
            from llm.resilience import get_health_monitor
            monitor = get_health_monitor()
            while True:
                await _asyncio.sleep(60)
                try:
                    await monitor.check_all()
                except Exception as e:
                    logger.debug("Health check error: %s", e)
        except Exception as e:
            logger.debug("Health check loop failed to start: %s", e)
    _asyncio.create_task(_health_check_loop())

    # P7: Start workflow schedule loop (checks scheduled workflows every 30s)
    async def _start_workflow_schedule():
        # Poll until intelligence modules are loaded
        for _ in range(30):
            await _asyncio.sleep(0.5)
        try:
            from intelligence.workflows import get_workflow_engine
            wf_engine = get_workflow_engine()
            await wf_engine.start_schedule_loop()
            logger.info("Workflow schedule loop started")
        except Exception as e:
            logger.debug("Workflow schedule loop failed to start: %s", e)
    _asyncio.create_task(_start_workflow_schedule())

    # P5: Start auto-tuner background loop
    async def _start_auto_tuner():
        try:
            # Poll until intelligence modules are loaded
            for _ in range(30):
                await _asyncio.sleep(0.5)
            tuner = _get_auto_tuner()  # Use the same singleton as API endpoints
            await tuner.start_background_loop()
            logger.info("Auto-tuner started (interval=%ds)", tuner.CYCLE_INTERVAL_SEC)
        except Exception as e:
            logger.debug("Auto-tuner failed to start: %s", e)
    _asyncio.create_task(_start_auto_tuner())

    yield  # ── Server is running ───────────────────────────────────────────────

    # ── Shutdown ───────────────────────────────────────────────────────────
    _daemon_health_stop.set()
    await reminder_checker.stop()
    # Stop intelligence modules
    if screen_watcher:
        try:
            await screen_watcher.stop()
        except Exception:
            pass
    if proactive_assistant:
        try:
            await proactive_assistant.stop()
        except Exception:
            pass
    if ghost_mode:
        try:
            await ghost_mode.stop()
        except Exception:
            pass
    # Stop sleep cycle
    if sleep_cycle:
        sleep_cycle.stop_background_loop()
    # P6: Stop security monitor
    if security_monitor:
        try:
            await security_monitor.stop()
        except Exception:
            pass
    # P7: Stop workflow schedule loop
    try:
        from intelligence.workflows import get_workflow_engine
        get_workflow_engine().stop_schedule_loop()
    except Exception:
        pass
    # Close persistent HTTP connection pools
    try:
        await close_http_clients()
    except Exception:
        pass


# ── App creation (must come after lifespan and all globals) ─────────────────
app = FastAPI(title="May AI Backend", version="0.2.0", lifespan=lifespan)

# CORS — allow Tauri frontend and dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



# ── Settings endpoints ────────────────────────────────────────────────────

@app.get("/settings")
async def get_app_settings():
    """Get all app settings (default model, city, etc.)."""
    return get_settings()


@app.post("/settings")
async def set_app_settings(request: Request):
    """Update app settings. Only known keys are accepted."""
    data = await request.json()
    updated = update_settings(data)
    return {"status": "ok", **updated}


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


async def _convert_webm_to_float32(audio_bytes: bytes):
    """Convert webm/opus audio bytes to float32 numpy array (16kHz mono).

    Shared helper for /voice/transcribe-audio, /voice/biometrics/enroll, and /voice/biometrics/verify.
    Handles ffmpeg conversion, temp file cleanup, and returns (samples, amplitude).
    Raises ValueError if audio is empty or silent.
    """
    import numpy as _np
    import subprocess
    import tempfile
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
            samples = _np.frombuffer(raw, dtype=_np.int16).astype(_np.float32) / 32768.0
    finally:
        if webm_path and _os.path.exists(webm_path):
            _os.unlink(webm_path)
        if wav_path and _os.path.exists(wav_path):
            _os.unlink(wav_path)

    amp = float(_np.abs(samples).max())
    if amp < 0.001:
        raise ValueError("No speech detected in audio")
    return samples, amp


# NOTE: /voice/transcribe-audio is defined below with rate limiting (SEC5)


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
    # M2 FIX: Acquire lock to prevent race with concurrent transcribe requests
    async with _stt_lock:
        _stt_forced_model = request.model is not None
        if request.model:
            # Force a specific model
            stt = SpeechToText(whisper_model=request.model)
        else:
            # Reset to auto-detect
            stt = SpeechToText()
    # Run model loading in executor to avoid blocking the event loop
    loop = _asyncio.get_running_loop()
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


async def _build_health_response(run_checks: bool = False) -> dict:
    """Build detailed health response. Optionally run fresh checks (slower ~3s)."""
    from llm.resilience import get_health_monitor
    monitor = get_health_monitor()
    if run_checks:
        await monitor.check_all()
    status = monitor.get_status()
    status["free_models"] = get_free_models_status()
    status["ollama_cloud"] = get_ollama_cloud_status()
    return status


@app.get("/health/detailed")
async def health_detailed():
    """Detailed health check — returns cached results from background 60s loop."""
    return await _build_health_response(run_checks=False)


@app.post("/health/detailed/refresh")
async def health_detailed_refresh():
    """Force a fresh health check on all services (slower, ~3s)."""
    return await _build_health_response(run_checks=True)


@app.post("/chat")
async def chat(request: ChatRequest):
    """Stream chat response from May — now uses Jarvis brain.

    Every message goes through the LLM with tool definitions.
    The LLM decides what to do: call tools, chat, or both.
    """
    # Check if Ollama is running (for local provider)
    provider = request.provider or "ollama"
    model = request.model or PRIMARY_MODEL

    # Try fast path BEFORE Ollama check — fast path works without LLM
    from llm.jarvis import _try_fast_path
    fast = _try_fast_path(request.message)
    if fast is not None:
        # Fast path matched — execute directly without LLM
        tool_name, tool_args = fast
        logger.info("Chat fast-path: %s(%s)", tool_name, tool_args)

        import os as _os_f
        import asyncio as _aio_f
        from llm.jarvis import execute_tool, _update_pronoun_state

        status_messages = []

        from llm.jarvis import _parse_app_and_tab_intent
        if tool_name == "__compound_open_and_type":
            raw_app = tool_args["app_name"]
            text = tool_args["text"]
            real_app, wants_tab, shortcut = _parse_app_and_tab_intent(raw_app)
            await execute_tool("open_app", {"app_name": real_app})
            _update_pronoun_state("open_app", {"app_name": real_app})
            status_messages.append(f"*Opening {real_app}...*")
            await _aio_f.sleep(1.0)
            if wants_tab:
                status_messages.append(f"*Opening new tab in {real_app}...*")
                await execute_tool("send_keys", {"keys": shortcut})
                await _aio_f.sleep(0.5)
            status_messages.append(f"*Typing into {real_app}...*")
            await execute_tool("type_text", {"text": text, "window_title": real_app})
            _update_pronoun_state("type_text", {"text": text, "window_title": real_app})
        elif tool_name == "__compound_generate_and_type":
            raw_app = tool_args["app_name"]
            full_prompt = tool_args.get("full_prompt", request.message)
            real_app, wants_tab, shortcut = _parse_app_and_tab_intent(raw_app)
            await execute_tool("open_app", {"app_name": real_app})
            _update_pronoun_state("open_app", {"app_name": real_app})
            status_messages.append(f"*Opening {real_app}...*")
            await _aio_f.sleep(1.0)
            if wants_tab:
                status_messages.append(f"*Opening new tab in {real_app}...*")
                await execute_tool("send_keys", {"keys": shortcut})
                await _aio_f.sleep(0.5)
            status_messages.append(f"*Generating content for {real_app}...*")
            gen_prompt = f"Write the requested content for: '{full_prompt}'. Output ONLY the body of the document/essay/poem/code. Do NOT include intro conversational text like 'Here is the essay' or 'Sure'."
            generated_text = ""
            try:
                from llm.providers import stream_chat_with_tools
                async for event in stream_chat_with_tools(
                    provider=provider,
                    model=model,
                    messages=[{"role": "user", "content": gen_prompt}],
                    system_prompt="You are a document generator. Output ONLY the document text directly. No commentary.",
                    tools=None,
                    max_tokens=2048,
                ):
                    if event["type"] == "text":
                        generated_text += event["content"]
            except Exception as e:
                logger.error("Failed to generate content in main.py: %s", e)
                generated_text = f"Content for: {full_prompt}"

            import re as _re_main_g
            generated_text = _re_main_g.sub(r"<think>.*?</think>", "", generated_text, flags=_re_main_g.DOTALL).strip()
            status_messages.append(f"*Typing into {real_app}...*")
            await execute_tool("type_text", {"text": generated_text, "window_title": real_app})
            _update_pronoun_state("type_text", {"text": generated_text, "window_title": real_app})
            status_messages.append(f"Done~ Typed into {real_app}!")
        elif tool_name == "__compound_create_write_open":
            file_path = tool_args["path"]
            content = tool_args["content"]
            app_name = tool_args.get("app_name", "notepad")
            await execute_tool("write_file", {"path": file_path, "content": content})
            status_messages.append(f"*Created {_os_f.basename(file_path)}*")
            await _aio_f.sleep(0.5)
            await execute_tool("open_app", {"app_name": app_name})
            status_messages.append(f"*Opened in {app_name}*")
        elif tool_name == "__compound_create_and_open":
            file_path = tool_args["path"]
            app_name = tool_args["app_name"]
            await execute_tool("write_file", {"path": file_path, "content": ""})
            status_messages.append(f"*Created {_os_f.basename(file_path)}*")
            await _aio_f.sleep(0.5)
            await execute_tool("open_app", {"app_name": app_name})
            status_messages.append(f"*Opened in {app_name}*")
        else:
            result = await execute_tool(tool_name, tool_args)
            _update_pronoun_state(tool_name, tool_args)
            status_messages.append(f"Done~ {tool_name.replace('_', ' ')}: {result[:200]}")

        async def _fast_stream():
            for msg in status_messages:
                yield msg + "\n"

        return StreamingResponse(_fast_stream(), media_type="text/plain")

    if provider == "ollama" and not await is_ollama_running():
        async def error_stream():
            yield "Ollama isn't running right now~ Start it with `ollama serve` and try again."
        return StreamingResponse(error_stream(), media_type="text/plain")

    # Build conversation history
    history = []
    for msg_item in request.history[-20:]:
        history.append({
            "role": msg_item.get("role", "user"),
            "content": msg_item.get("content", "")
        })

    # Use Jarvis brain for everything
    provider_name = PROVIDERS.get(provider, {}).get("name", provider)

    async def generate():
        full_response = ""
        # Record user activity for ghost mode idle detection
        if ghost_mode:
            ghost_mode.record_input()
        # Analyze tone and record to mood history
        if tone_analyzer and mood_history:
            try:
                from intelligence.mood_history import MoodEntry
                tone_result = tone_analyzer.analyze(request.message)
                mood_history.record(MoodEntry(
                    timestamp=time.time(),
                    mood=tone_result.mood.value,
                    confidence=tone_result.confidence,
                    message_preview=request.message[:100],
                    may_mood=tone_result.suggested_may_mood,
                    response_style=tone_result.response_style,
                ))
            except Exception:
                pass
        try:
            async for chunk in jarvis_chat(
                message=request.message,
                history=history,
                provider=provider,
                model=model,
            ):
                # Strip the 🔧 tool status lines from final response (they're for user feedback)
                full_response += chunk
                yield chunk
        except ValueError as e:
            yield f"\n\n({str(e)})"
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 402:
                yield f"\n\n(Your {provider_name} account has insufficient credits or balance~ Top up your balance and try again.)"
            elif status == 401:
                yield f"\n\n(Invalid API key for {provider_name}~ Check your key in Settings.)"
            elif status == 429:
                yield f"\n\n({provider_name} rate limit exceeded~ Wait a moment and try again.)"
            elif status == 404:
                yield f"\n\n(Model not found on {provider_name}~ Try a different model.)"
            else:
                yield f"\n\n({provider_name} returned an error (HTTP {status})~ Check your settings and try again.)"
        except ConnectionError:
            yield f"\n\n(My backend can't reach {provider_name}~ Check your connection and API key.)"
        except TimeoutError:
            yield "\n\n(I'm thinking too hard on this one~ Try again in a moment.)"
        except Exception as e:
            yield f"\n\n(Something went wrong: {str(e)[:200]})"

        # P3: Feed conversation signals to endocrine system
        if endocrine_system and tone_analyzer:
            try:
                energy = tone_analyzer.get_conversation_energy()
                tone_result = tone_analyzer.analyze(request.message)
                endocrine_system.update_from_conversation(
                    user_energy=energy,
                    frustration_score=0.8 if tone_result.mood.value in ("frustrated", "angry") else 0.2,
                    mood=tone_result.mood.value,
                )
            except Exception:
                pass
        # P3: Reset sleep cycle idle timer on every chat interaction
        if sleep_cycle:
            try:
                sleep_cycle.record_interaction()
            except Exception:
                pass
        # P7: Check chat-triggered workflows
        try:
            from intelligence.workflows import get_workflow_engine
            wf_engine = get_workflow_engine()
            chat_triggered = wf_engine.get_chat_triggered_workflows(request.message)
            for wf in chat_triggered:
                logger.info("Chat-triggered workflow: %s", wf.name)
                asyncio.create_task(wf_engine.execute(wf.id))
        except Exception:
            pass
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
                pass

    return StreamingResponse(generate(), media_type="text/plain")


async def handle_command(lower_msg: str, original_msg: str) -> str | None:
    """DEPRECATED — This function is superseded by the Control Core daemon.

    All system commands are now routed through llm/core_bridge.py → daemon TCP.
    This stub exists only for backward compatibility. Returns None to let
    the Jarvis brain handle all commands via tool definitions.
    """
    return None


# try_pc_control and _execute_pc_command removed — superseded by core_bridge + daemon


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
    """Return OpenRouter models (paid + dynamically fetched free models)."""
    has_key = get_all_key_status().get("openrouter", False)
    models = [
        {"provider": "openrouter", "provider_name": "OpenRouter", **m, "available": has_key}
        for m in PROVIDERS["openrouter"]["models"]
    ]
    free_count = sum(1 for m in PROVIDERS["openrouter"]["models"] if ":free" in m["id"])
    return {"models": models, "free_count": free_count, "status": get_free_models_status()}


@app.get("/models/ollama")
async def list_ollama_local_models():
    """Return locally installed Ollama models (auto-discovered from localhost:11434)."""
    models = [
        {"provider": "ollama", "provider_name": "Ollama (Local)", **m, "available": True}
        for m in PROVIDERS["ollama"]["models"]
    ]
    return {"models": models, "count": len(models), "status": get_ollama_local_status()}


@app.get("/models/ollama-cloud")
async def list_ollama_cloud_models():
    """Return Ollama Cloud models (hardcoded + dynamically fetched)."""
    has_key = get_all_key_status().get("ollama_cloud", False)
    models = [
        {"provider": "ollama_cloud", "provider_name": "Ollama Cloud", **m, "available": has_key}
        for m in PROVIDERS["ollama_cloud"]["models"]
    ]
    return {"models": models, "count": len(models), "status": get_ollama_cloud_status()}


@app.post("/models/refresh")
async def refresh_models():
    """Force-refresh all dynamic model lists (OpenRouter free + Ollama Cloud + Ollama Local)."""
    openrouter_result = await refresh_openrouter_free_models(force=True)
    ollama_cloud_result = await refresh_ollama_cloud_models(force=True)
    ollama_local_result = await refresh_ollama_local_models(force=True)
    return {
        "status": "ok",
        "openrouter": openrouter_result,
        "ollama_cloud": ollama_cloud_result,
        "ollama_local": ollama_local_result,
    }


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


# ── Skill Store (Procedural Memory) endpoints ───────────────────────────


class SkillStoreRequest(BaseModel):
    name: str
    description: str = ""
    steps: list[dict] = []
    trigger_phrases: list[str] = []
    tags: list[str] = []
    confidence: float = 0.5


@app.get("/skills")
async def list_skills():
    """List all stored skills."""
    skills = skill_store.list_all()
    return {"skills": [s.to_dict() for s in skills], "count": len(skills)}


@app.post("/skills")
async def create_skill(request: SkillStoreRequest):
    """Store a new skill."""
    skill = skill_store.store(
        name=request.name,
        description=request.description,
        steps=request.steps,
        trigger_phrases=request.trigger_phrases,
        tags=request.tags,
        confidence=request.confidence,
    )
    return {"status": "ok", **skill.to_dict()}


@app.get("/skills/search")
async def search_skills(q: str, top_k: int = 3):
    """Search skills relevant to a query."""
    skills = skill_store.find_relevant(q, top_k=top_k)
    return {"skills": [s.to_dict() for s in skills], "count": len(skills)}


@app.get("/skills/stats")
async def skill_stats():
    """Get skill store statistics."""
    stats = skill_store.get_stats()
    return {
        "total_skills": stats["total_skills"],
        "total_uses": stats["total_uses"],
        "avg_confidence": stats["avg_confidence"],
    }


@app.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    """Get a single skill by ID."""
    skill = skill_store.get(skill_id)
    if skill:
        return skill.to_dict()
    return {"error": "Skill not found"}


@app.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str):
    """Delete a skill by ID."""
    success = skill_store.delete(skill_id)
    return {"status": "ok" if success else "not_found"}


@app.post("/skills/execute")
async def execute_skill(request: Request):
    """Execute a stored skill by running its steps sequentially."""
    data = await request.json()
    skill_id = data.get("skill_id", "")
    if not skill_id:
        return {"error": "skill_id required"}
    skill = skill_store.get(skill_id)
    if not skill:
        return {"error": "Skill not found"}
    # Execute each step via the tool executor
    from llm.jarvis import execute_tool
    results = []
    for step in skill.steps:
        try:
            result = await execute_tool(step.tool_name, step.params)
            results.append({"tool": step.tool_name, "result": result[:200], "ok": True})
        except Exception as e:
            results.append({"tool": step.tool_name, "result": str(e)[:200], "ok": False})
    # Record usage
    skill_store.record_use(skill_id)
    return {"status": "ok", "skill": skill.name, "results": results}


@app.get("/memory/injector")
async def memory_injector_status():
    """Get memory injector status."""
    return memory_injector.get_status()


@app.get("/system/stats")
async def system_stats():
    """Get real-time system stats (RAM and GPU usage)."""
    try:
        import psutil
        stats = {
            "ram_percent": round(psutil.virtual_memory().percent, 1),
            "cpu_percent": round(psutil.cpu_percent(interval=0.5), 1),
        }
        try:
            result = _subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                stats["gpu_percent"] = round(float(result.stdout.strip().split("\n")[0]), 1)
        except Exception:
            pass
        return stats
    except ImportError:
        return {"ram_percent": 0, "cpu_percent": 0}


# ── Wake Word Detection endpoints ──────────────────────────────────────


class WakeWordCheckRequest(BaseModel):
    audio: str  # base64-encoded PCM int16 audio chunk (16kHz mono, 80ms)


@app.get("/voice/wake-word")
async def get_wake_word_status():
    """Get current wake word detection status."""
    if wake_word_detector:
        return wake_word_detector.get_status()
    return {"enabled": False, "loaded": False, "model": "none"}


@app.post("/voice/wake-word")
async def set_wake_word_config(request: Request):
    """Enable/disable wake word detection and configure it."""
    data = await request.json()
    if not wake_word_detector:
        return {"error": "Wake word detector not loaded"}

    enabled = data.get("enabled")
    model = data.get("model")
    threshold = data.get("threshold")

    if enabled is True:
        wake_word_detector.enable(model_name=model, threshold=threshold)
    elif enabled is False:
        wake_word_detector.disable()
    else:
        if model:
            wake_word_detector._state.model_name = model
        if threshold is not None:
            wake_word_detector.set_threshold(threshold)

    return wake_word_detector.get_status()


@app.post("/voice/wake-word/check")
async def check_wake_word(request: WakeWordCheckRequest):
    """Check an audio chunk for wake word detection.

    Frontend sends base64-encoded PCM int16 audio chunks (16kHz mono, ~80ms each)
    while in 'wake word mode'. Returns whether the wake word was detected.
    """
    import base64

    if not wake_word_detector or not wake_word_detector.enabled:
        return {"detected": False, "confidence": 0, "enabled": False}

    try:
        pcm_bytes = base64.b64decode(request.audio)
        result = wake_word_detector.check_chunk(pcm_bytes)
        result["enabled"] = True
        return result
    except Exception as e:
        logger.debug("Wake word check error: %s", e)
        return {"detected": False, "confidence": 0, "enabled": True, "error": str(e)[:100]}


# ── Privacy Mode endpoints ───────────────────────────────────────────────


class PrivacyRequest(BaseModel):
    reason: str = "manual toggle"


@app.get("/privacy")
async def get_privacy_status():
    """Get current privacy mode status."""
    if privacy_mode:
        return privacy_mode.get_status()
    return {"active": False, "registered_modules": []}


@app.post("/privacy/toggle")
async def toggle_privacy(request: PrivacyRequest):
    """Toggle privacy mode on/off. Pauses/resumes all intelligence modules."""
    if not privacy_mode:
        return {"error": "Privacy mode not loaded"}
    return privacy_mode.toggle(reason=request.reason)


@app.post("/privacy/enable")
async def enable_privacy(request: PrivacyRequest):
    """Enable privacy mode."""
    if not privacy_mode:
        return {"error": "Privacy mode not loaded"}
    return privacy_mode.enable(reason=request.reason)


@app.post("/privacy/disable")
async def disable_privacy(request: PrivacyRequest):
    """Disable privacy mode."""
    if not privacy_mode:
        return {"error": "Privacy mode not loaded"}
    return privacy_mode.disable(reason=request.reason)


@app.get("/privacy/audit")
async def get_privacy_audit_log(limit: int = 50):
    """Get the privacy audit log."""
    if privacy_mode:
        return {"entries": privacy_mode.get_audit_log(limit)}
    return {"entries": []}


# ── Morning Briefing + Integrations endpoints ──────────────────────────
_briefing_generator = None  # Lazy-initialized in the endpoint


class SmartHomeConfigRequest(BaseModel):
    ha_url: str
    ha_token: str


class CalendarSourceRequest(BaseModel):
    source: str | None = None  # Path to .ics file or URL
    days: int = 1


@app.get("/briefing")
async def get_morning_briefing():
    """Generate a morning briefing with weather, news, calendar, reminders, smart home."""
    global _briefing_generator
    if _briefing_generator is None:
        from intelligence.morning_briefing import MorningBriefingGenerator
        _briefing_generator = MorningBriefingGenerator()
    briefing = await _briefing_generator.generate(fact_store=fact_store)
    return {
        "text": briefing.to_full_briefing(),
        "sections": briefing.to_dict(),
    }


@app.get("/weather")
async def get_weather(city: str | None = None, lat: float | None = None, lon: float | None = None):
    """Get current weather. Uses saved city from settings if none provided."""
    from integrations.weather import WeatherClient
    # Use explicit params > saved city setting > IP geolocation
    if not city and lat is None and lon is None:
        saved_city = get_setting("city", "")
        if saved_city:
            city = saved_city
    client = WeatherClient(lat=lat, lon=lon, city=city or None)
    forecast = await client.get_forecast()
    return forecast.to_dict()


@app.get("/news")
async def get_news(category: str = "technology", max_items: int = 5):
    """Get top news headlines. Categories: technology, general, science, business."""
    from integrations.news import NewsClient
    client = NewsClient()
    digest = await client.get_headlines(category=category, max_items=max_items)
    return digest.to_dict()


@app.get("/calendar")
async def get_calendar_events(source: str | None = None, days: int = 1):
    """Get upcoming calendar events from .ics file or URL."""
    from integrations.calendar_reader import CalendarReader
    reader = CalendarReader()
    events = await reader.get_upcoming(days=days, source=source)
    return {
        "events": [e.to_dict() for e in events],
        "count": len(events),
    }


@app.get("/smart-home")
async def get_smart_home_status():
    """Get smart home device status."""
    from integrations.smart_home import SmartHomeClient
    client = SmartHomeClient()
    status = client.get_status()
    if client.enabled:
        devices = await client.get_entities()
        status["devices"] = [d.to_dict() for d in devices[:20]]
        status["device_count"] = len(devices)
    return status


@app.post("/smart-home/configure")
async def configure_smart_home(request: SmartHomeConfigRequest):
    """Configure Home Assistant connection."""
    from integrations.smart_home import SmartHomeClient
    client = SmartHomeClient()
    client.configure(request.ha_url, request.ha_token)
    connected = await client.test_connection()
    return {"status": "ok" if connected else "connection_failed", **client.get_status()}


@app.post("/smart-home/toggle")
async def toggle_smart_device(request: Request):
    """Toggle a smart home device on/off."""
    data = await request.json()
    entity_id = data.get("entity_id", "")
    if not entity_id:
        return {"error": "entity_id required"}
    from integrations.smart_home import SmartHomeClient
    client = SmartHomeClient()
    success = await client.toggle_entity(entity_id)
    return {"status": "ok" if success else "failed", "entity_id": entity_id}


@app.get("/calendar/sources")
async def get_calendar_sources():
    """List available .ics calendar files in common locations."""
    import glob as _glob
    import os
    patterns = [
        os.path.expanduser("~/Documents/*.ics"),
        os.path.expanduser("~/Desktop/*.ics"),
        os.path.expanduser("~/Downloads/*.ics"),
        os.path.expanduser("~/.may/calendar.ics"),
    ]
    found = []
    for pattern in patterns:
        for path in _glob.glob(pattern):
            found.append({"path": path, "name": _os.path.basename(path)})
    return {"sources": found}


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


# ── Email endpoints ───────────────────────────────────────────────────────


class EmailConfigRequest(BaseModel):
    provider: str | None = None  # 'gmail', 'outlook', 'yahoo' or None for custom
    email_address: str = ""
    password: str = ""
    imap_host: str = ""
    smtp_host: str = ""
    imap_port: int = 993
    smtp_port: int = 587


class SendEmailRequest(BaseModel):
    to: str
    subject: str
    body: str
    cc: str = ""


@app.get("/email")
async def get_email_status():
    """Get email integration status."""
    from integrations import get_email_client
    client = get_email_client()
    return client.get_status()


@app.post("/email/configure")
async def configure_email(request: EmailConfigRequest):
    """Configure email connection."""
    from integrations import get_email_client
    client = get_email_client()
    kwargs = {}
    if request.email_address:
        kwargs["email_address"] = request.email_address
    if request.password:
        kwargs["password"] = request.password
    if request.imap_host:
        kwargs["imap_host"] = request.imap_host
    if request.smtp_host:
        kwargs["smtp_host"] = request.smtp_host
    if request.imap_port:
        kwargs["imap_port"] = request.imap_port
    if request.smtp_port:
        kwargs["smtp_port"] = request.smtp_port
    client.configure(provider=request.provider, **kwargs)
    return client.get_status()


@app.get("/email/unread")
async def get_unread_emails(max_items: int = 10):
    """Get unread emails from the inbox."""
    from integrations import get_email_client
    client = get_email_client()
    emails = await client.get_unread(max_items=max_items)
    return {"emails": [e.to_dict() for e in emails], "count": len(emails)}


@app.get("/email/unread/count")
async def get_unread_count():
    """Get the count of unread emails."""
    from integrations import get_email_client
    client = get_email_client()
    count = await client.get_unread_count()
    return {"count": count}


@app.get("/email/search")
async def search_emails(q: str, max_items: int = 10):
    """Search emails by subject text."""
    from integrations import get_email_client
    client = get_email_client()
    emails = await client.search_emails(query=q, max_items=max_items)
    return {"emails": [e.to_dict() for e in emails], "count": len(emails)}


@app.get("/email/recent")
async def get_recent_emails(max_items: int = 5):
    """Get the most recent emails."""
    from integrations import get_email_client
    client = get_email_client()
    emails = await client.get_recent(max_items=max_items)
    return {"emails": [e.to_dict() for e in emails], "count": len(emails)}


@app.get("/email/{uid}")
async def read_email(uid: str):
    """Read a specific email by UID."""
    from integrations import get_email_client
    client = get_email_client()
    email_msg = await client.read_email(uid)
    if email_msg:
        return email_msg.to_dict()
    return {"error": "Email not found"}


@app.post("/email/send")
async def send_email(request: SendEmailRequest):
    """Send an email."""
    from integrations import get_email_client
    client = get_email_client()
    success = await client.send_email(
        to=request.to, subject=request.subject,
        body=request.body, cc=request.cc,
    )
    return {"status": "ok" if success else "failed"}


# ── Wellness / Proactive endpoints ────────────────────────────────────────


@app.get("/wellness")
async def get_wellness_status():
    """Get proactive wellness assistant status."""
    if proactive_assistant:
        return proactive_assistant.get_status()
    return {"enabled": False, "rules": []}


@app.get("/wellness/suggestions")
async def get_wellness_suggestions():
    """Check for pending wellness suggestions."""
    if proactive_assistant:
        suggestions = await proactive_assistant.check()
        return {"suggestions": suggestions, "count": len(suggestions)}
    return {"suggestions": [], "count": 0}


@app.post("/wellness/toggle")
async def toggle_wellness():
    """Toggle wellness reminders on/off."""
    if proactive_assistant:
        enabled = proactive_assistant.toggle()
        return {"enabled": enabled}
    return {"error": "Proactive assistant not loaded"}


@app.post("/wellness/rule")
async def set_wellness_rule(request: Request):
    """Enable or disable a specific wellness rule."""
    data = await request.json()
    rule = data.get("rule", "")
    enabled = data.get("enabled", True)
    if proactive_assistant:
        proactive_assistant.set_rule_enabled(rule, enabled)
        return {"status": "ok", "rule": rule, "enabled": enabled}
    return {"error": "Proactive assistant not loaded"}


@app.post("/wellness/acknowledge")
async def acknowledge_suggestion(request: Request):
    """Acknowledge a wellness suggestion (e.g., take a break)."""
    data = await request.json()
    suggestion_type = data.get("type", "break")
    if proactive_assistant:
        proactive_assistant.acknowledge_suggestion(suggestion_type)
        return {"status": "ok"}
    return {"error": "Proactive assistant not loaded"}


# ── Plugin System endpoints ───────────────────────────────────────────────
_plugin_manager = None  # Lazy-initialized


def _get_plugin_manager():
    global _plugin_manager
    if _plugin_manager is None:
        from plugins import get_plugin_manager
        _plugin_manager = get_plugin_manager()
        # Wire into jarvis.py so plugin tools are available to the LLM
        from llm.jarvis import set_plugin_manager
        set_plugin_manager(_plugin_manager)
        # Load previously installed plugins
        _plugin_manager.load_installed()
    return _plugin_manager


@app.get("/plugins")
async def get_plugins():
    """List all loaded plugins and their tools."""
    pm = _get_plugin_manager()
    return pm.get_status()


@app.post("/plugins/load")
async def load_plugin(request: Request):
    """Load a plugin by name."""
    data = await request.json()
    plugin_name = data.get("name", "")
    if not plugin_name:
        return {"error": "Plugin name required"}
    pm = _get_plugin_manager()
    plugin = pm.load_plugin(plugin_name)
    if plugin:
        invalidate_tool_cache()  # Rebuild tool tiering cache after plugin load
        return {"status": "ok", **plugin.get_info()}
    return {"error": f"Failed to load plugin '{plugin_name}'"}


@app.post("/plugins/unload")
async def unload_plugin(request: Request):
    """Unload a plugin by name."""
    data = await request.json()
    plugin_name = data.get("name", "")
    if not plugin_name:
        return {"error": "Plugin name required"}
    pm = _get_plugin_manager()
    success = pm.unload_plugin(plugin_name)
    if success:
        invalidate_tool_cache()  # Rebuild tool tiering cache after plugin unload
    return {"status": "ok" if success else "not_found"}


@app.get("/plugins/tools")
async def get_plugin_tools():
    """Get all tools registered by plugins."""
    pm = _get_plugin_manager()
    tools = pm.get_all_plugin_tools()
    return {"tools": tools, "count": len(tools)}


# ── Meeting Mode endpoints ───────────────────────────────────────────────


class MeetingStartRequest(BaseModel):
    title: str | None = None


@app.get("/meeting/status")
async def get_meeting_status():
    """Get current meeting recording status."""
    if meeting_mode:
        return await meeting_mode.get_status()
    return {"active": False}


@app.post("/meeting/start")
async def start_meeting(request: MeetingStartRequest):
    """Start recording a meeting. Captures system audio for transcription."""
    if not meeting_mode:
        return {"error": "Meeting mode not loaded"}
    return await meeting_mode.start(title=request.title)


@app.post("/meeting/stop")
async def stop_meeting():
    """Stop recording and generate summary with action items."""
    if not meeting_mode:
        return {"error": "Meeting mode not loaded"}
    return await meeting_mode.stop()


@app.get("/meeting/list")
async def list_meetings():
    """List saved meeting notes."""
    import glob as _glob
    meetings_dir = _os.path.join(_os.path.expanduser("~"), "may", "meetings")
    files = sorted(_glob.glob(_os.path.join(meetings_dir, "*.md")), reverse=True)
    meetings = []
    for f in files[:20]:  # Last 20
        name = _os.path.basename(f).replace(".md", "")
        size = _os.path.getsize(f)
        meetings.append({"name": name, "file": f, "size": size})
    return {"meetings": meetings, "count": len(meetings)}


# ── Ghost Mode endpoints ─────────────────────────────────────────────────


class GhostTaskRequest(BaseModel):
    description: str
    priority: int = 0
    steps: list[dict] | None = None


class GhostCancelRequest(BaseModel):
    task_id: str


@app.get("/ghost/status")
async def get_ghost_status():
    """Get Ghost Mode status — queued tasks, idle detection."""
    if ghost_mode:
        return ghost_mode.get_status()
    return {"active": False, "queue": [], "completed": []}


@app.post("/ghost/queue")
async def queue_ghost_task(request: GhostTaskRequest):
    """Queue a task for autonomous execution when user is idle."""
    if not ghost_mode:
        return {"error": "Ghost mode not loaded"}
    return ghost_mode.queue_task(
        description=request.description,
        steps=request.steps,
        priority=request.priority,
    )


@app.post("/ghost/cancel")
async def cancel_ghost_task(request: GhostCancelRequest):
    """Cancel a queued ghost task."""
    if not ghost_mode:
        return {"error": "Ghost mode not loaded"}
    success = ghost_mode.cancel_task(request.task_id)
    return {"status": "ok" if success else "not_found"}


@app.post("/ghost/cancel-all")
async def cancel_all_ghost_tasks():
    """Cancel all queued ghost tasks."""
    if not ghost_mode:
        return {"error": "Ghost mode not loaded"}
    count = ghost_mode.cancel_all()
    return {"status": "ok", "cancelled": count}


@app.get("/ghost/task/{task_id}")
async def get_ghost_task(task_id: str):
    """Get a specific ghost task by ID."""
    if not ghost_mode:
        return {"error": "Ghost mode not loaded"}
    task = ghost_mode.get_task(task_id)
    if task:
        return task
    return {"error": "Task not found"}


# ── Voice Biometrics endpoints ───────────────────────────────────────────
_biometrics = None  # Lazy-initialized


def _get_biometrics():
    global _biometrics
    if _biometrics is None:
        from voice.biometrics import VoiceBiometrics
        _biometrics = VoiceBiometrics()
    return _biometrics


class BiometricsEnrollRequest(BaseModel):
    name: str = "user"


class BiometricsVerifyRequest(BaseModel):
    pass  # Audio sent as raw body


class BiometricsThresholdRequest(BaseModel):
    threshold: float = 0.75


@app.get("/voice/biometrics")
async def get_biometrics_status():
    """Get voice biometrics enrollment status."""
    return _get_biometrics().get_status()


@app.post("/voice/biometrics/enroll")
async def enroll_voice(request: Request):
    """Enroll a voice profile. Send binary audio data (webm/opus)."""
    import asyncio as _asyncio

    bio = _get_biometrics()
    audio_bytes = await request.body()
    if not audio_bytes or len(audio_bytes) < 100:
        return {"error": "No audio data received"}

    # Parse query params for name
    name = request.query_params.get("name", "user")

    try:
        samples, _amp = await _convert_webm_to_float32(audio_bytes)
    except ValueError as e:
        return {"error": str(e)}

    loop = _asyncio.get_running_loop()
    result = await loop.run_in_executor(None, bio.enroll, samples, name)
    return result


@app.post("/voice/biometrics/verify")
async def verify_voice(request: Request):
    """Verify voice against enrolled profile. Send binary audio data."""
    import asyncio as _asyncio

    bio = _get_biometrics()
    audio_bytes = await request.body()
    if not audio_bytes or len(audio_bytes) < 100:
        return {"error": "No audio data received"}

    try:
        samples, _amp = await _convert_webm_to_float32(audio_bytes)
    except ValueError as e:
        return {"error": str(e)}

    loop = _asyncio.get_running_loop()
    result = await loop.run_in_executor(None, bio.verify, samples)
    return result


@app.post("/voice/biometrics/threshold")
async def set_biometrics_threshold(request: BiometricsThresholdRequest):
    """Update the biometrics similarity threshold."""
    bio = _get_biometrics()
    bio.set_threshold(request.threshold)
    return {"status": "ok", "threshold": bio._threshold}


@app.post("/voice/biometrics/delete")
async def delete_voice_profile():
    """Delete the saved voice profile."""
    return _get_biometrics().delete_profile()


@app.post("/voice/biometrics/toggle")
async def toggle_biometrics():
    """Toggle biometrics on/off without deleting profile."""
    return _get_biometrics().toggle()


# ── Tone Analyzer endpoints ──────────────────────────────────────────────


class ToneAnalyzeRequest(BaseModel):
    message: str


@app.post("/tone/analyze")
async def analyze_tone(request: ToneAnalyzeRequest):
    """Analyze the emotional tone of a user message.

    Returns mood classification, confidence, and suggested May response style.
    Used by the frontend to adjust avatar expression and personality.
    """
    if not tone_analyzer:
        return {"mood": "neutral", "confidence": 0.5, "signals": ["not_loaded"], "suggested_may_mood": "neutral", "response_style": "default"}
    result = tone_analyzer.analyze(request.message)
    return {
        "mood": result.mood.value,
        "confidence": result.confidence,
        "signals": result.signals,
        "suggested_may_mood": result.suggested_may_mood,
        "response_style": result.response_style,
    }


@app.get("/tone/energy")
async def get_conversation_energy():
    """Get the overall energy level of the current conversation."""
    if not tone_analyzer:
        return {"energy": 0.5}
    return {"energy": tone_analyzer.get_conversation_energy()}


@app.post("/tone/reset")
async def reset_tone():
    """Reset tone analyzer history."""
    if tone_analyzer:
        tone_analyzer.reset()
    return {"status": "ok"}


# ── Mood History endpoints ──────────────────────────────────────────────


class MoodRecordRequest(BaseModel):
    mood: str
    confidence: float = 0.5
    message_preview: str = ""
    may_mood: str = "neutral"
    response_style: str = "default"


@app.get("/mood/recent")
async def get_recent_moods(count: int = 20):
    """Get recent mood entries."""
    if not mood_history:
        return {"entries": [], "count": 0}
    entries = mood_history.get_recent(count)
    return {"entries": entries, "count": len(entries)}


@app.get("/mood/trend")
async def get_mood_trend(period: str = "24h"):
    """Get mood trend for a time window (1h, 6h, 24h, 7d)."""
    if not mood_history:
        return {"period": period, "dominant_mood": "neutral", "total_entries": 0}
    trend = mood_history.get_trend(period)
    return {
        "period": trend.period,
        "dominant_mood": trend.dominant_mood,
        "mood_distribution": trend.mood_distribution,
        "average_confidence": trend.average_confidence,
        "average_energy": trend.average_energy,
        "total_entries": trend.total_entries,
        "mood_shifts": trend.mood_shifts,
    }


@app.get("/mood/timeline")
async def get_mood_timeline(hours: int = 24):
    """Get mood timeline for charting — aggregated by 15-minute buckets."""
    if not mood_history:
        return {"timeline": [], "hours": hours}
    timeline = mood_history.get_timeline(hours)
    return {"timeline": timeline, "hours": hours}


@app.get("/mood/stats")
async def get_mood_stats():
    """Get overall mood history statistics."""
    if not mood_history:
        return {"total_entries": 0}
    return mood_history.get_stats()


@app.post("/mood/record")
async def record_mood(request: MoodRecordRequest):
    """Record a mood entry."""
    if not mood_history:
        return {"error": "Mood history not loaded"}
    from intelligence.mood_history import MoodEntry
    entry = MoodEntry(
        timestamp=time.time(),
        mood=request.mood,
        confidence=request.confidence,
        message_preview=request.message_preview[:100],
        may_mood=request.may_mood,
        response_style=request.response_style,
    )
    mood_history.record(entry)
    return {"status": "ok"}


@app.post("/mood/clear")
async def clear_old_mood_data(days: int = 30):
    """Remove mood entries older than N days."""
    if not mood_history:
        return {"error": "Mood history not loaded"}
    removed = mood_history.clear_old(days)
    return {"status": "ok", "removed": removed}


# ── P3 Endocrine / Sleep / Streaming STT / Audio Emotion endpoints ────


class StreamChunkRequest(BaseModel):
    session_id: str | None = None
    audio: str  # base64-encoded PCM int16 audio (100ms chunk)
    chunk_index: int = 0


@app.post("/voice/stream/start")
async def stream_stt_start():
    """Start a new streaming STT session."""
    stt_instance = get_stt()
    streaming = get_streaming_stt()
    streaming.set_stt(stt_instance)
    session = streaming.create_session()
    return {"session_id": session.session_id, "state": session.state.value}


@app.post("/voice/stream/chunk")
async def stream_stt_chunk(request: StreamChunkRequest):
    """Process a 100ms audio chunk for streaming STT."""
    streaming = get_streaming_stt()
    session = streaming.get_session(request.session_id) if request.session_id else None
    if not session:
        # Auto-create session if none exists
        session = streaming.create_session(request.session_id)
    result = await streaming.process_chunk(session, request.audio, request.chunk_index)
    return result


@app.post("/voice/stream/finalize")
async def stream_stt_finalize(request: Request):
    """Finalize a streaming STT session — transcribe accumulated audio."""
    data = await request.json()
    session_id = data.get("session_id", "")
    streaming = get_streaming_stt()
    session = streaming.get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    result = await streaming.finalize(session)
    return result


@app.post("/voice/stream/cancel")
async def stream_stt_cancel(request: Request):
    """Cancel a streaming STT session."""
    data = await request.json()
    session_id = data.get("session_id", "")
    streaming = get_streaming_stt()
    session = streaming.get_session(session_id)
    if session:
        await streaming.cancel_session(session)
    return {"status": "ok"}


# ── P5: Silero VAD endpoints ───────────────────────────────────────────

@app.get("/voice/vad")
async def get_vad_status():
    """Get Silero VAD status — model availability, speech detection state."""
    try:
        from voice.vad import get_vad
        vad = get_vad()
        return vad.get_state()
    except Exception as e:
        return {"available": False, "error": str(e)[:200]}


@app.get("/endocrine")
async def get_endocrine_status():
    """Get endocrine system hormone levels and emotional state."""
    if endocrine_system:
        return endocrine_system.get_stats()
    return {"hormones": {}, "emotional_state": "neutral"}


@app.post("/endocrine/update")
async def update_endocrine(request: Request):
    """Manually update endocrine hormones (for testing)."""
    data = await request.json()
    if not endocrine_system:
        return {"error": "Endocrine system not loaded"}
    interaction = data.get("interaction", "tool_success")
    endocrine_system.update_from_interaction(interaction)
    return endocrine_system.get_stats()


@app.post("/endocrine/reset")
async def reset_endocrine():
    """Reset all hormones to baselines."""
    if endocrine_system:
        endocrine_system.reset_to_baselines()
    return {"status": "ok"}


@app.get("/sleep")
async def get_sleep_status():
    """Get sleep cycle status."""
    if sleep_cycle:
        return sleep_cycle.get_status()
    return {"current_state": "wake", "active": False}


@app.post("/sleep/consolidate")
async def force_sleep_consolidation():
    """Force a sleep consolidation cycle (for testing)."""
    if not sleep_cycle:
        return {"error": "Sleep cycle not loaded"}
    # Set idle time to deep sleep threshold for testing
    old_interaction = sleep_cycle._last_interaction
    sleep_cycle._last_interaction = time.time() - 7200  # 2 hours ago
    state = await sleep_cycle.check_and_transition()
    sleep_cycle._last_interaction = old_interaction  # Restore
    return {"state": state.value if state else "none", "status": "ok"}


@app.post("/sleep/interaction")
async def record_sleep_interaction():
    """Record user interaction to reset sleep idle timer."""
    if sleep_cycle:
        sleep_cycle.record_interaction()
    return {"status": "ok"}


@app.post("/audio/emotion")
async def analyze_audio_emotion(request: Request):
    """Analyze emotion from voice audio. Send webm/opus audio as body."""
    audio_bytes = await request.body()
    if not audio_bytes or len(audio_bytes) < 100:
        return {"error": "No audio data"}

    try:
        samples, _amp = await _convert_webm_to_float32(audio_bytes)
    except ValueError as e:
        return {"error": str(e)}

    analyzer = AudioEmotionAnalyzer()
    import asyncio as _asyncio
    loop = _asyncio.get_running_loop()
    result = await loop.run_in_executor(None, analyzer.analyze_samples, samples)
    return result.to_dict()


# ── P2 Security endpoints ───────────────────────────────────────────────
behavioral_profile = None
immune_system = None


@app.get("/security")
async def get_security_status():
    """Get overall security status — encryption, audit log, risk tiers."""
    result = {}

    # Secure storage status
    try:
        from system.secure_storage import get_key_status
        result["storage"] = get_key_status()
    except ImportError:
        result["storage"] = {"encryption": "unavailable", "encryption_secure": False}

    # Audit log stats
    try:
        from system.audit_log import get_stats as _audit_stats
        result["audit_log"] = _audit_stats()
    except ImportError:
        result["audit_log"] = {"total_entries": 0}

    # Risk classifier summary
    try:
        from system.risk_classifier import get_risk_summary
        result["risk_tiers"] = get_risk_summary()
    except ImportError:
        result["risk_tiers"] = {}

    return result


@app.get("/security/audit-log")
async def get_audit_log(
    limit: int = 100,
    action: str = "",
    risk: str = "",
    since: float = 0,
):
    """Get tamper-evident audit log entries with optional filters."""
    try:
        from system.audit_log import get_entries
        entries = get_entries(limit=limit, action_filter=action, risk_filter=risk, since=since)
        return {"entries": entries, "count": len(entries)}
    except ImportError:
        return {"entries": [], "count": 0, "error": "Audit log module not available"}


@app.get("/security/audit-log/verify")
async def verify_audit_log():
    """Verify the integrity of the entire audit log hash chain."""
    try:
        from system.audit_log import verify_integrity
        is_valid, violations = verify_integrity()
        return {"valid": is_valid, "violations": violations}
    except ImportError:
        return {"valid": True, "violations": [], "error": "Audit log module not available"}


@app.post("/security/audit-log/clear")
async def clear_audit_log(request: Request):
    """Clear the audit log. Optionally keep last N entries for continuity."""
    try:
        from system.audit_log import clear_log
        keep_n = 0
        try:
            data = await request.json()
            keep_n = data.get("keep_last_n", 0) if isinstance(data, dict) else 0
        except Exception:
            pass  # No body or invalid JSON — use default keep_n=0
        result = clear_log(keep_last_n=keep_n)
        return result
    except ImportError:
        return {"error": "Audit log module not available"}


@app.get("/security/risk-tiers")
async def get_risk_tiers():
    """Get all action risk tier classifications."""
    try:
        from system.risk_classifier import get_risk_summary
        return get_risk_summary()
    except ImportError:
        return {"error": "Risk classifier not available"}


@app.get("/security/owasp")
async def get_owasp_mapping():
    """Get OWASP Top 10 for Agentic Applications mapping."""
    try:
        from system.owasp_mapping import get_owasp_summary
        return get_owasp_summary()
    except ImportError:
        return {"error": "OWASP mapping not available"}


@app.get("/security/behavioral-profile")
async def get_behavioral_profile():
    """Get behavioral profile summary."""
    if behavioral_profile:
        return behavioral_profile.get_profile_summary()
    return {"total_actions": 0, "reliable": False}


@app.get("/security/immune-system")
async def get_immune_system_status():
    """Get immune system status."""
    if immune_system:
        return immune_system.get_status()
    return {"threshold": 0.3, "behavioral_profile": False, "control_modes": False}


@app.get("/tracing")
async def get_tracing_status():
    """Get OpenTelemetry tracing status."""
    from system.tracing import get_trace_stats
    return get_trace_stats()


@app.post("/security/migrate-keys")
async def migrate_api_keys():
    """Migrate all API keys from legacy plaintext to DPAPI-encrypted storage."""
    try:
        from system.secure_storage import migrate_all_from_plaintext
        result = migrate_all_from_plaintext()
        return {"status": "ok", **result}
    except ImportError:
        return {"error": "Secure storage module not available"}


# ── Control Modes endpoints ───────────────────────────────────────────────


class ControlModeRequest(BaseModel):
    mode: str  # "normal", "focus", "silent", "automation"
    reason: str = ""


@app.get("/modes")
async def get_control_modes():
    """Get current control mode status and settings."""
    if control_modes:
        return control_modes.get_status()
    return {"active_mode": "normal", "enabled": True, "settings": {}, "available_modes": ["normal", "focus", "silent", "automation"]}


@app.post("/modes/set")
async def set_control_mode(request: ControlModeRequest):
    """Switch to a control mode."""
    if not control_modes:
        return {"error": "Control modes not loaded"}
    return control_modes.set_mode(request.mode, reason=request.reason)


@app.get("/modes/audit")
async def get_mode_audit_log(limit: int = 20):
    """Get mode change history."""
    if control_modes:
        return {"entries": control_modes.get_audit_log(limit)}
    return {"entries": []}


# ── Screen Watcher Proactive endpoints ──────────────────────────────────


@app.get("/screen/suggestions")
async def get_screen_suggestions():
    """Get pending screen watcher suggestions (Tier 1/2/3).

    Returns suggestions from the screen watcher's proactive rules, including
    UIAutomation-detected errors, visual changes, and other monitored events.
    """
    if not screen_watcher:
        return {"suggestions": [], "count": 0}
    suggestions = screen_watcher.get_suggestions()
    return {
        "suggestions": suggestions,
        "count": len(suggestions),
    }


@app.post("/screen/suggestions/acknowledge")
async def acknowledge_screen_suggestion(request: Request):
    """Acknowledge a screen watcher suggestion (mark as shown)."""
    data = await request.json()
    suggestion_rule = data.get("rule", "")
    if not screen_watcher:
        return {"error": "Screen watcher not loaded"}
    suggestions = screen_watcher.get_suggestions()
    for s in suggestions:
        if s.get("rule") == suggestion_rule:
            screen_watcher.mark_shown(s)
            return {"status": "ok"}
    return {"error": "Suggestion not found"}


@app.get("/screen/stats")
async def get_screen_watcher_stats():
    """Get screen watcher statistics including Tier 2/3 status."""
    if not screen_watcher:
        return {"active": False, "rules_active": 0, "suggestions_pending": 0}
    return screen_watcher.get_stats()


@app.get("/screen/context")
async def get_screen_context():
    """Get the latest Tier 2 UIAccessibility screen context.

    Returns structured data about the current screen: window title,
    UI elements, visible text, error detection, modal status.
    Zero VRAM — uses Windows UIAutomation API.
    """
    if not screen_watcher:
        return {"error": "Screen watcher not loaded"}
    data = screen_watcher.get_last_screen_data()
    return {"screen_data": data or {}, "available": data is not None}


@app.post("/screen/context/read")
async def force_screen_context_read():
    """Force an immediate Tier 2 UIAccessibility screen read.

    Returns fresh structured data without waiting for the next watch cycle.
    """
    if not screen_watcher:
        return {"error": "Screen watcher not loaded"}
    try:
        data = await screen_watcher.read_screen_now()
        return {"screen_data": data or {}, "available": data is not None}
    except Exception as e:
        return {"error": str(e)[:200]}


# ── P4: Conditioned Reflexes endpoints ──────────────────────────────────


def _get_conditioned_reflexes():
    """Lazy getter for conditioned reflexes singleton."""
    from intelligence.conditioned_reflexes import get_conditioned_reflexes
    return get_conditioned_reflexes()


@app.get("/reflexes")
async def get_reflexes():
    """Get all learned conditioned reflexes."""
    reflexes = _get_conditioned_reflexes()
    return {"reflexes": reflexes.get_reflexes(), "stats": reflexes.get_stats()}


@app.get("/reflexes/stats")
async def get_reflexes_stats():
    """Get conditioned reflexes statistics."""
    reflexes = _get_conditioned_reflexes()
    return reflexes.get_stats()


@app.post("/reflexes/clear")
async def clear_reflexes():
    """Clear all learned conditioned reflexes."""
    reflexes = _get_conditioned_reflexes()
    reflexes.clear()
    return {"status": "ok"}


@app.get("/ui-accessibility")
async def get_ui_accessibility_status():
    """Get Tier 2 UIAccessibility reader status."""
    try:
        from intelligence.ui_accessibility import UIAccessibilityReader
        reader = UIAccessibilityReader()
        return {
            "available": reader.is_available(),
            "last_read": reader.get_last_read().to_dict() if reader.get_last_read() else None,
        }
    except ImportError:
        return {"available": False, "error": "uiautomation not installed"}


@app.post("/ui-accessibility/read")
async def force_ui_accessibility_read():
    """Force an immediate UIAccessibility screen read."""
    try:
        from intelligence.ui_accessibility import UIAccessibilityReader
        import asyncio as _asyncio
        reader = UIAccessibilityReader()
        if not reader.is_available():
            return {"error": "uiautomation not installed"}
        loop = _asyncio.get_running_loop()
        data = await loop.run_in_executor(None, reader.get_screen_data)
        return {"screen_data": data.to_dict()}
    except ImportError:
        return {"error": "uiautomation not installed"}
    except Exception as e:
        return {"error": str(e)[:200]}


# ── P4: OCR Fallback endpoints ───────────────────────────────────────────

@app.get("/ocr")
async def get_ocr_status():
    """Get PaddleOCR reader status."""
    try:
        from intelligence.ocr_reader import OCRReader
        reader = OCRReader()
        return {
            "available": reader.is_available(),
            "last_result": reader.get_last_result().to_dict() if reader.get_last_result() else None,
        }
    except ImportError:
        return {"available": False, "error": "PaddleOCR not installed"}


@app.post("/ocr/read")
async def force_ocr_read():
    """Force an immediate OCR screen read via PaddleOCR."""
    try:
        from intelligence.ocr_reader import OCRReader
        import asyncio as _asyncio
        reader = OCRReader()
        if not reader.is_available():
            return {"error": "PaddleOCR not installed (pip install paddleocr paddlepaddle)"}

        # Take a screenshot via the daemon
        from core.client import send_command
        import os as _os_mod
        result = await send_command("input", "screenshot_full", {
            "output_path": "_may_ocr_api_temp.png",
        })
        if not result.success or not isinstance(result.data, dict):
            return {"error": "Failed to capture screenshot"}

        screenshot_path = result.data.get("path", "")
        try:
            loop = _asyncio.get_running_loop()
            ocr_result = await loop.run_in_executor(
                None, reader.read_screenshot, screenshot_path
            )
            return {"ocr_result": ocr_result.to_dict()}
        finally:
            try:
                _os_mod.unlink(screenshot_path)
            except OSError:
                pass
    except ImportError:
        return {"error": "PaddleOCR not installed"}
    except Exception as e:
        return {"error": str(e)[:200]}


# ── P5: Auto-Tuner endpoints ────────────────────────────────────────────
_auto_tuner = None  # Lazy-initialized


def _get_auto_tuner():
    """Lazy getter for auto-tuner singleton."""
    global _auto_tuner
    if _auto_tuner is None:
        from intelligence.auto_tuner import AutoTuner
        _auto_tuner = AutoTuner()
    return _auto_tuner


@app.get("/auto-tuner")
async def get_auto_tuner_status():
    """Get auto-tuner status — genes, fitness, history."""
    return _get_auto_tuner().get_status()


@app.get("/auto-tuner/genes")
async def get_auto_tuner_genes():
    """Get all tunable genes with current values."""
    return {"genes": _get_auto_tuner().get_genes()}


@app.post("/auto-tuner/evolve")
async def run_auto_tuner_evolve():
    """Manually trigger one evolution cycle."""
    return await _get_auto_tuner().evolve()


@app.post("/auto-tuner/gene")
async def set_auto_tuner_gene(request: Request):
    """Manually set a gene value."""
    data = await request.json()
    name = data.get("name", "")
    value = data.get("value", 0)
    success = _get_auto_tuner().set_gene(name, value)
    return {"status": "ok" if success else "not_found", "gene": name, "value": value}


@app.post("/auto-tuner/reset")
async def reset_auto_tuner():
    """Reset all genes to defaults."""
    _get_auto_tuner().reset_to_defaults()
    return {"status": "ok"}


@app.post("/auto-tuner/history/clear")
async def clear_auto_tuner_history():
    """Clear fitness history."""
    _get_auto_tuner().clear_history()
    return {"status": "ok"}


# ── P5: Internet Learning endpoints ──────────────────────────────────────
_internet_learner = None  # Lazy-initialized


def _get_internet_learner():
    """Lazy getter for internet learner singleton."""
    global _internet_learner
    if _internet_learner is None:
        from intelligence.internet_learning import get_internet_learner
        _internet_learner = get_internet_learner()
    return _internet_learner


@app.get("/learning")
async def get_learning_status():
    """Get internet learning status — pending and learned items."""
    return _get_internet_learner().get_stats()


@app.get("/learning/pending")
async def get_pending_knowledge():
    """Get pending knowledge items awaiting user approval."""
    return {"items": _get_internet_learner().get_pending_knowledge()}


@app.get("/learning/recent")
async def get_recent_learned():
    """Get recently learned knowledge items."""
    return {"items": _get_internet_learner().get_learned_knowledge()}


@app.post("/learning/extract")
async def extract_knowledge(request: Request):
    """Extract knowledge from search results (called after web_search)."""
    data = await request.json()
    query = data.get("query", "")
    results = data.get("results", [])
    if not query or not results:
        return {"error": "query and results required"}
    item = _get_internet_learner().extract_knowledge(query, results)
    return {"item": item.to_dict()}


@app.post("/learning/approve")
async def approve_knowledge(request: Request):
    """Approve a pending knowledge item and store in long-term memory."""
    data = await request.json()
    item_id = data.get("id", "")
    if not item_id:
        return {"error": "id required"}
    success = _get_internet_learner().approve_knowledge(
        item_id, fact_store=fact_store, vector_store=vector_store
    )
    return {"status": "ok" if success else "not_found"}


@app.post("/learning/reject")
async def reject_knowledge(request: Request):
    """Reject a pending knowledge item."""
    data = await request.json()
    item_id = data.get("id", "")
    if not item_id:
        return {"error": "id required"}
    success = _get_internet_learner().reject_knowledge(item_id)
    return {"status": "ok" if success else "not_found"}


@app.post("/learning/clear")
async def clear_learning():
    """Clear all pending knowledge items."""
    _get_internet_learner().clear_pending()
    return {"status": "ok"}


@app.post("/speculative/chat")
async def speculative_chat(request: ChatRequest):
    """Stream chat using speculative decoding (draft + verify). Only supports Ollama."""
    from llm.ollama_client import speculative_generate
    provider = request.provider or "ollama"
    model = request.model or PRIMARY_MODEL

    # Speculative decoding only works with local Ollama models
    if provider != "ollama":
        async def error_stream():
            yield f"Speculative decoding only supports Ollama. Use /chat with provider '{provider}' instead."
        return StreamingResponse(error_stream(), media_type="text/plain")

    if not await is_ollama_running():
        async def error_stream():
            yield "Ollama isn't running right now~ Start it with `ollama serve` and try again."
        return StreamingResponse(error_stream(), media_type="text/plain")

    messages = [{"role": "user", "content": request.message}]
    for msg_item in request.history[-10:]:
        role = "user" if msg_item.get("role") == "user" else "assistant"
        messages.insert(-1, {"role": role, "content": msg_item.get("content", "")})

    return StreamingResponse(
        speculative_generate(messages=messages, model=model),
        media_type="text/plain",
    )


# ── Remote Control endpoints ─────────────────────────────────────────────
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response

_remote_control = None  # Lazy-initialized


def _get_remote():
    global _remote_control
    if _remote_control is None:
        from remote.control import get_remote_control
        _remote_control = get_remote_control()
    return _remote_control


@app.get("/remote", response_class=HTMLResponse)
async def remote_ui():
    """Serve the mobile-friendly remote control web UI."""
    template_path = _os.path.join(_os.path.dirname(__file__), "remote", "template.html")
    if _os.path.exists(template_path):
        with open(template_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Remote UI template not found</h1>", status_code=500)


@app.get("/remote/info")
async def remote_info():
    """Get remote control connection info (local IP, port, QR code, PIN)."""
    rc = _get_remote()
    port = 8080
    info = rc.get_connection_info(port)
    info["qr_svg"] = rc.generate_qr_svg(info["url"])
    pin = rc.get_pin()
    info["pin"] = pin
    info["auth_enabled"] = pin is not None
    return info


@app.get("/remote/qr")
async def remote_qr():
    """Generate a QR code PNG for the remote control URL."""
    rc = _get_remote()
    info = rc.get_connection_info(8080)
    qr_png = rc.generate_qr(info["url"])
    if qr_png:
        return Response(content=qr_png, media_type="image/png")
    return HTMLResponse(content="<h1>QR library not installed</h1><p>pip install qrcode[pil]</p>", status_code=500)


@app.get("/remote/status")
async def remote_status():
    """Get remote control status."""
    return _get_remote().get_status()


@app.get("/remote/pin")
async def remote_get_pin():
    """Get the current remote control PIN."""
    rc = _get_remote()
    pin = rc.get_pin()
    if pin is None:
        return {"pin": None, "auth_disabled": True}
    return {"pin": pin, "auth_disabled": False}


@app.post("/remote/pin/verify")
async def remote_verify_pin(request: Request):
    """Verify a PIN for remote access."""
    data = await request.json()
    pin = data.get("pin", "")
    rc = _get_remote()
    return {"valid": rc.verify_pin(pin)}


@app.post("/remote/pin/regenerate")
async def remote_regenerate_pin():
    """Regenerate the remote control PIN."""
    rc = _get_remote()
    new_pin = rc.regenerate_pin()
    return {"pin": new_pin}


# ── Rate limiter for voice transcription (SEC5) ─────────────────────────
_voice_rate_limits: dict[str, list[float]] = {}  # ip -> list of timestamps
_last_rate_cleanup: float = 0.0  # timestamp of last stale IP cleanup
_VOICE_RATE_MAX = 15  # Max requests per minute
_VOICE_RATE_WINDOW = 60.0  # 1-minute window


def _check_voice_rate_limit(client_ip: str) -> bool:
    """Check if the client is within the voice transcription rate limit.

    Returns True if the request is allowed, False if rate limited.
    Auto-cleans stale IPs every 100 checks to prevent memory leak.
    """
    now = time.time()
    # Periodic cleanup: evict IPs with no recent requests (every 5 minutes)
    global _last_rate_cleanup
    if now - _last_rate_cleanup > 300:
        _last_rate_cleanup = now
        stale_ips = [
            ip for ip, ts_list in _voice_rate_limits.items()
            if not ts_list or now - max(ts_list) > _VOICE_RATE_WINDOW * 2
        ]
        for ip in stale_ips:
            del _voice_rate_limits[ip]

    # Clean old entries for this IP
    if client_ip in _voice_rate_limits:
        _voice_rate_limits[client_ip] = [
            t for t in _voice_rate_limits[client_ip] if now - t < _VOICE_RATE_WINDOW
        ]
    else:
        _voice_rate_limits[client_ip] = []

    if len(_voice_rate_limits[client_ip]) >= _VOICE_RATE_MAX:
        return False

    _voice_rate_limits[client_ip].append(now)
    return True


@app.post("/voice/transcribe-audio")
async def voice_transcribe_audio(request: Request):
    """Transcribe audio captured by the browser's getUserMedia.
    
    Accepts binary audio data (webm/opus from MediaRecorder) and transcribes
    it using faster-whisper. This bypasses the Python PortAudio issue where
    sd.rec() records silence on Windows.

    Rate limited to 15 requests per minute per IP.
    """
    import asyncio as _asyncio

    # SEC5: Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not _check_voice_rate_limit(client_ip):
        return {"text": "", "error": "Rate limit exceeded. Please wait a moment and try again."}

    _stt = get_stt()
    audio_bytes = await request.body()

    if not audio_bytes or len(audio_bytes) < 100:
        return {"text": "", "error": "No audio data received"}

    try:
        samples, amp = await _convert_webm_to_float32(audio_bytes)
    except ValueError as e:
        return {"text": "", "error": str(e)}

    # Transcribe with faster-whisper
    loop = _asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _stt.transcribe_audio, samples)
    result["amplitude"] = amp
    return result


@app.websocket("/ws/remote")
async def websocket_remote(ws: WebSocket):
    """WebSocket endpoint for remote control -- real-time chat.

    Accepts JSON messages with optional provider/model fields:
    {"content": "...", "provider": "ollama", "model": "qwen3:4b"}
    """
    rc = _get_remote()
    await ws.accept()
    # SEC3: Verify PIN if auth is enabled
    try:
        pin = await ws.receive_text()
        msg_data = json.loads(pin) if pin.startswith('{') else {"pin": pin}
        if not rc.verify_pin(msg_data.get("pin", "")):
            await ws.send_text(json.dumps({"type": "error", "content": "Invalid PIN"}))
            await ws.close()
            return
        await ws.send_text(json.dumps({"type": "authenticated", "content": "Connected"}))
    except Exception:
        await ws.close()
        return
    rc.add_connection(ws)
    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                msg = {"type": "message", "content": data}

            content = msg.get("content", "")
            if not content:
                continue

            # Record the remote message
            rc.record_message("user", content)

            # P4: Respect user-selected provider/model from frontend
            r_provider = msg.get("provider", "ollama")
            r_model = msg.get("model", PRIMARY_MODEL)

            # Send to Jarvis brain and stream response
            try:
                response_text = ""
                async for chunk in jarvis_chat(
                    message=content,
                    history=[],
                    provider=r_provider,
                    model=r_model,
                ):
                    response_text += chunk
                rc.record_message("may", response_text)
                await ws.send_text(json.dumps({
                    "type": "response",
                    "content": response_text,
                }))
            except Exception as e:
                error_msg = f"Error: {str(e)[:200]}"
                await ws.send_text(json.dumps({
                    "type": "response",
                    "content": error_msg,
                }))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("WebSocket error: %s", e)
    finally:
        rc.remove_connection(ws)


# ── P6: Personality Mode endpoints ─────────────────────────────────────

class PersonalityRequest(BaseModel):
    name: str


@app.get("/personality")
async def get_personality():
    """Get current personality mode status and available profiles."""
    if personality_modes:
        return personality_modes.get_status()
    return {"active_profile": "shikimori", "available_profiles": {}}


@app.post("/personality/set")
async def set_personality(request: PersonalityRequest):
    """Switch to a personality profile (shikimori, formal, debug, silent, playful)."""
    if not personality_modes:
        return {"error": "Personality modes not loaded"}
    return personality_modes.set_profile(request.name)


@app.get("/personality/audit")
async def get_personality_audit(limit: int = 20):
    """Get personality change history."""
    if personality_modes:
        return {"entries": personality_modes.get_audit_log(limit)}
    return {"entries": []}


@app.post("/personality/custom")
async def create_custom_personality(request: Request):
    """Create a custom personality profile."""
    if not personality_modes:
        return {"error": "Personality modes not loaded"}
    data = await request.json()
    return personality_modes.create_custom_profile(
        data.get("name", ""),
        base_profile=data.get("base", "shikimori"),
        **{k: v for k, v in data.items() if k not in ("name", "base")},
    )


# ── P6: Security Monitor endpoints ──────────────────────────────────────

@app.get("/security-monitor")
async def get_security_monitor_status():
    """Get security monitor status."""
    if security_monitor:
        return security_monitor.get_status()
    return {"active": False, "alerts": 0}


@app.get("/security-monitor/alerts")
async def get_security_alerts(
    category: str = "",
    severity: str = "",
    limit: int = 50,
):
    """Get security monitoring alerts."""
    if not security_monitor:
        return {"alerts": [], "count": 0}
    alerts = security_monitor.get_alerts(
        category=category, severity=severity, limit=limit,
    )
    return {"alerts": alerts, "count": len(alerts)}


@app.post("/security-monitor/acknowledge")
async def acknowledge_security_alert(request: Request):
    """Acknowledge a security alert by index (0 = most recent)."""
    if not security_monitor:
        return {"error": "Security monitor not loaded"}
    data = await request.json()
    success = security_monitor.acknowledge_alert(data.get("index", 0))
    return {"status": "ok" if success else "not_found"}


@app.post("/security-monitor/config")
async def update_security_monitor_config(request: Request):
    """Update security monitor configuration."""
    if not security_monitor:
        return {"error": "Security monitor not loaded"}
    data = await request.json()
    return security_monitor.update_config(**data)


# ── P5: Llama-Server (True Speculative Decoding) endpoints ─────────────

@app.get("/llama-server")
async def get_llama_server_status():
    """Get llama-server status — running, models, config."""
    from llm.llama_server import get_status
    return get_status()


@app.get("/llama-server/health")
async def llama_server_health():
    """Check llama-server health (live check)."""
    from llm.llama_server import check_llama_server_health
    return await check_llama_server_health()


class LlamaServerConfigRequest(BaseModel):
    enabled: bool | None = None
    target_model: str | None = None
    draft_model: str | None = None
    port: int | None = None
    n_ctx: int | None = None
    n_gpu_layers: int | None = None
    draft_n_max: int | None = None


@app.post("/llama-server/config")
async def update_llama_server_config(request: LlamaServerConfigRequest):
    """Update llama-server configuration."""
    from llm.llama_server import update_config
    kwargs = {k: v for k, v in request.model_dump().items() if v is not None}
    return update_config(**kwargs)


@app.post("/llama-server/start")
async def start_llama_server(request: LlamaServerConfigRequest | None = None):
    """Start llama-server with speculative decoding enabled."""
    from llm.llama_server import start_llama_server as _start
    kwargs = {}
    if request:
        kwargs = {k: v for k, v in request.model_dump().items() if v is not None}
    return await _start(**kwargs)


@app.post("/llama-server/stop")
async def stop_llama_server():
    """Stop the running llama-server."""
    from llm.llama_server import stop_llama_server as _stop
    return await _stop()


if __name__ == "__main__":
    import uvicorn
    # Bind to localhost by default for security; use MAY_LISTEN_ALL=true for LAN access
    import os as _os_listen
    _listen_all = _os_listen.environ.get("MAY_LISTEN_ALL", "false").lower() == "true"
    _host = "0.0.0.0" if _listen_all else "127.0.0.1"
    uvicorn.run(app, host=_host, port=8080)


# ── P6: Automated Workflows endpoints ──────────────────────────────────
_workflow_engine = None  # Lazy-initialized


def _get_workflow_engine():
    """Lazy getter for workflow engine singleton."""
    global _workflow_engine
    if _workflow_engine is None:
        from intelligence.workflows import get_workflow_engine
        _workflow_engine = get_workflow_engine()
    return _workflow_engine


@app.get("/workflows")
async def list_workflows():
    """List all automated workflows."""
    engine = _get_workflow_engine()
    wfs = engine.list_all()
    return {"workflows": [wf.to_dict() for wf in wfs], "count": len(wfs)}


@app.get("/workflows/stats")
async def get_workflow_stats():
    """Get workflow engine statistics."""
    return _get_workflow_engine().get_stats()


@app.post("/workflows")
async def create_workflow(request: Request):
    """Create a new automated workflow."""
    data = await request.json()
    engine = _get_workflow_engine()
    wf = engine.create(
        name=data.get("name", "Untitled"),
        description=data.get("description", ""),
        steps=data.get("steps", []),
        trigger=data.get("trigger", "manual"),
        trigger_config=data.get("trigger_config", {}),
    )
    return {"status": "ok", **wf.to_dict()}


@app.post("/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str):
    """Execute a workflow's steps sequentially."""
    engine = _get_workflow_engine()
    if not engine._executor:
        from llm.jarvis import execute_tool
        engine.set_executor(execute_tool)
    return await engine.execute(workflow_id)


@app.post("/workflows/{workflow_id}/toggle")
async def toggle_workflow(workflow_id: str):
    """Toggle a workflow enabled/disabled."""
    engine = _get_workflow_engine()
    success = engine.toggle(workflow_id)
    return {"status": "ok" if success else "not_found"}


@app.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete a workflow."""
    engine = _get_workflow_engine()
    success = engine.delete(workflow_id)
    return {"status": "ok" if success else "not_found"}


@app.get("/workflows/{workflow_id}")
async def get_workflow_detail(workflow_id: str):
    """Get a single workflow by ID."""
    engine = _get_workflow_engine()
    wf = engine.get(workflow_id)
    if wf:
        return wf.to_dict()
    return {"error": "Workflow not found"}


@app.post("/workflows/preview")
async def preview_workflow_steps(request: Request):
    """Preview what steps would be generated from a natural language description."""
    data = await request.json()
    description = data.get("description", "")
    if not description:
        return {"steps": [], "count": 0}
    engine = _get_workflow_engine()
    steps = engine.preview_steps(description)
    return {"steps": steps, "count": len(steps)}
