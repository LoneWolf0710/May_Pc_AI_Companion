# May v3 — Unified Architecture (Best of Both)

> May's proven 3-process architecture + JARVIS V2's intelligence features
> Built on what works. Not a rewrite — an evolution.

---

## 1. What This Is

May v3 takes the **working foundation** from May (Tauri desktop, FastAPI brain, Control Core daemon, multi-provider LLM, voice, memory) and adds the **intelligence features** from JARVIS V2 that were never built (shadow learning, screen watching, frustration detection, privacy mode, wake word, plugin system).

**Philosophy:** Don't throw away working code. Layer new capabilities on top.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MAY v3 — 4 PROCESSES                                │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  PROCESS 1: TAURI (Rust + React + TypeScript)                       │   │
│  │  Glassmorphism UI │ Chat Panel │ Avatar │ Voice Monitor │ Settings   │   │
│  │  Floating Orb HUD │ System Tray │ Model Selector                     │   │
│  └──────────────────────────────┬───────────────────────────────────────┘   │
│                                 │ HTTP (localhost:8080)                      │
│  ┌──────────────────────────────▼───────────────────────────────────────┐   │
│  │  PROCESS 2: FASTAPI BRAIN (Python)                                    │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────┐   │   │
│  │  │  LLM Providers  │  │  Jarvis Brain   │  │   Voice System     │   │   │
│  │  │  Ollama/OpenAI/  │  │  Tool calling   │  │  STT (whisper)     │   │   │
│  │  │  Anthropic/      │  │  Streaming      │  │  TTS (browser)     │   │   │
│  │  │  Gemini/OpenRouter│ │  Multi-provider │  │  Model selector    │   │   │
│  │  └─────────────────┘  └─────────────────┘  └────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────┐   │   │
│  │  │   Memory        │  │  Notifications  │  │   NEW: Intelligence│   │   │
│  │  │  LanceDB vector │  │  Toast + remind │  │  Shadow learner    │   │   │
│  │  │  SQLite facts   │  │  Background     │  │  Screen watcher    │   │   │
│  │  │  Auto-extract   │  │  checker        │  │  Frustration det.  │   │   │
│  │  └─────────────────┘  └─────────────────┘  └────────────────────┘   │   │
│  └──────────────────────────────┬───────────────────────────────────────┘   │
│                                 │ TCP (127.0.0.1:7650)                       │
│  ┌──────────────────────────────▼───────────────────────────────────────┐   │
│  │  PROCESS 3: CONTROL CORE DAEMON (Python)                              │   │
│  │                                                                      │   │
│  │  CommandBus → Router → 9 Control Layers → FallbackChain → Verifier   │   │
│  │                                                                      │   │
│  │  L1 Filesystem  │ L2 Process    │ L3 Application                     │   │
│  │  L4 Window      │ L5 Input      │ L6 Registry                        │   │
│  │  L7 Services    │ L8 System     │ L9 Browser                         │   │
│  │                                                                      │   │
│  │  + Transaction Engine (atomic multi-step ops with rollback)          │   │
│  │  + Privilege Management (Admin → SYSTEM → TrustedInstaller)          │   │
│  │  + Fallback Chains (7-strategy retry per action)                     │   │
│  │  + Post-Action Verification (execute → verify → confirm)             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PROCESS 4: WAKE WORD LISTENER (Python — NEW)                       │   │
│  │  openwakeword on mic │ "Hey May" detection → triggers STT          │   │
│  │  Lightweight, <2% CPU, runs independently                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  All processes communicate via TCP/HTTP. No shared state. Crash-isolated.  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Directory Structure

```
may/
├── knowledge.md                    # Project knowledge base (read first every session)
├── MAY_V3_ARCHITECTURE.md          # THIS FILE — unified architecture
│
├── src/                            # PROCESS 1: Tauri Frontend
│   ├── App.tsx                     # Main app — floating card, state, chat, streaming
│   ├── config.ts                   # Shared constants (BACKEND_URL)
│   ├── main.tsx                    # React entry point
│   ├── components/
│   │   ├── Avatar.tsx              # Glass sphere + orbital ring animations
│   │   ├── ChatPanel.tsx           # Chat bubbles + input + voice + model selector
│   │   ├── FloatingOrb.tsx         # Mini desktop widget
│   │   ├── ModelSelector.tsx       # Multi-provider dropdown with search
│   │   ├── QuickActions.tsx        # Command palette
│   │   ├── SettingsModal.tsx       # API keys + STT model selector + NEW settings
│   │   ├── StatusHUD.tsx           # Clock, GPU/RAM bars, model info
│   │   └── VoiceMonitor.tsx        # Floating side panel — amplitude, countdown
│   ├── hooks/
│   │   ├── useMicMonitor.ts        # Browser mic capture via getUserMedia
│   │   ├── useSpeechRecognition.ts # Backend STT flag
│   │   └── useSpeechSynthesis.ts   # Browser TTS
│   └── styles/
│       └── globals.css             # Surfaced Dark theme, glass-sphere CSS
│
├── src-tauri/                      # Tauri v2 (Rust)
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── capabilities/default.json
│   └── src/
│       ├── main.rs
│       └── lib.rs                  # IPC commands (greet, start_backend)
│
├── backend/                        # PROCESS 2: FastAPI Brain
│   ├── main.py                     # FastAPI server — all endpoints
│   ├── requirements.txt
│   ├── llm/
│   │   ├── jarvis.py               # May's brain — tool calling, streaming, multi-provider
│   │   ├── providers.py            # 6 providers + tool-aware streaming
│   │   ├── ollama_client.py        # Ollama streaming + think tag filter
│   │   ├── tools.py                # 100+ tool definitions (JSON schemas)
│   │   └── core_bridge.py          # Tool → daemon TCP mapping (param/result transformers)
│   ├── voice/
│   │   ├── stt.py                  # faster-whisper (GPU auto-detect → CPU fallback)
│   │   ├── tts.py                  # TTS module
│   │   └── recorder.py             # Audio recording
│   ├── memory/
│   │   ├── vector_store.py         # LanceDB 0.33.0 + sentence-transformers
│   │   └── fact_store.py           # SQLite CRUD + reminders
│   ├── system/
│   │   ├── notifications.py        # Toast notifications (winotify) + reminder checker
│   │   └── fallback.py             # System fallback helpers
│   └── intelligence/               # ← NEW: Intelligence Layer (from JARVIS V2)
│       ├── shadow_learner.py       # Tracks repeated patterns, suggests automations
│       ├── screen_watcher.py       # Low-res screenshots every 8s, detects events
│       ├── frustration_detector.py # Keyboard/mouse stress detection
│       └── briefing_engine.py      # Morning briefing (calendar, weather, news)
│
├── core/                           # PROCESS 3: Control Core Daemon
│   ├── daemon.py                   # Entry point (Windows Service / debug mode)
│   ├── bus.py                      # CommandBus + BusServer (TCP 127.0.0.1:7650)
│   ├── router.py                   # Layer normalization, aliases, safety checks
│   ├── privilege.py                # Admin/SYSTEM/TrustedInstaller escalation
│   ├── client.py                   # TCP client for FastAPI → daemon communication
│   ├── config/
│   │   ├── layer_caps.json         # Capability map per layer
│   │   └── fallback_chains.json    # Fallback strategy per action type
│   ├── engine/
│   │   ├── fallback.py             # FallbackChain — multi-method retry per action
│   │   ├── verifier.py             # Pre/post action verification
│   │   ├── transaction.py          # Atomic multi-step with rollback
│   │   ├── logger.py               # Structured logging
│   │   └── config_loader.py        # Load layer configs
│   └── layers/
│       ├── L1_filesystem.py        # Files, folders, drives, permissions
│       ├── L2_process.py           # Process launch, kill, suspend, inspect
│       ├── L3_application.py       # App launch, close, automate, install
│       ├── L4_window.py            # Window position, size, state, z-order
│       ├── L5_input.py             # Keyboard + Mouse (SendInput)
│       ├── L6_registry.py          # Windows Registry (all hives)
│       ├── L7_services.py          # Windows Services + Task Scheduler
│       ├── L8_system.py            # Power, network, audio, display, env
│       ├── L9_browser.py           # Browser DOM automation (Playwright)
│       └── _utils.py               # Shared layer utilities
│
├── wake/                           # PROCESS 4: Wake Word Listener (NEW)
│   ├── listener.py                 # openwakeword microphone listener
│   ├── trainer.py                  # Custom wake word training
│   └── sounds/
│       ├── wake.wav                # Wake detection chime
│       └── done.wav                # Task complete chime
│
└── config/
    ├── may.yaml                    # Master config (personality, voice, intelligence, privacy)
    └── personality.yaml            # Personality profiles (shikimori, formal, debug)
```

---

## 4. What We Keep From May (Proven Architecture)

### 4.1 — 3-Process Model
May's separation of concerns is architecturally superior to JARVIS V2's single-process design:
- **Tauri (Rust)** — UI performance, small footprint
- **FastAPI (Python)** — AI/ML ecosystem access
- **Daemon (Python)** — OS-level control with admin privileges

JARVIS V2's single Python process with 12 threads is fragile. May's approach gives crash isolation, language optimization per layer, and independent restartability.

### 4.2 — Multi-Provider LLM System
6 providers with unified streaming interface — something JARVIS V2 never detailed:
- Ollama (local, free)
- OpenAI (GPT-4o, o1)
- Anthropic (Claude)
- Google Gemini
- OpenRouter (100+ models, free tiers)
- Ollama Cloud

### 4.3 — Voice System
Server-side STT with GPU auto-detection, model selector, browser mic capture via getUserMedia — battle-tested through 8+ sessions of bug fixes.

### 4.4 — Memory System
LanceDB 0.33.0 vectors + SQLite structured facts + auto-extraction from conversations.

### 4.5 — Control Core with 100+ Tools
9-layer daemon with TCP bus, privilege escalation (Admin → SYSTEM → TrustedInstaller), and a core bridge that maps every LLM tool call to a daemon command.

---

## 5. What We Take From JARVIS V2 (New Features)

### 5.1 — Shadow Learning Mode
> "I've noticed you open Spotify, VS Code, then Discord every morning around 9am. Want me to automate that?"

**Implementation in `backend/intelligence/shadow_learner.py`:**

```python
class ShadowLearner:
    """Learns user patterns from repeated actions. Runs in background."""
    
    threshold = 3  # repetitions before suggesting
    
    def __init__(self, db_path: str = "shadow_patterns.db"):
        self.db_path = db_path
        self.event_log: list[ActionEvent] = []
        
    def record_event(self, action_type: str, target: str, timestamp: float):
        """Record every tool call and system action."""
        self.event_log.append(ActionEvent(action_type, target, timestamp))
        self._persist_event(action_type, target, timestamp)
        self._analyze_patterns()
    
    def _analyze_patterns(self):
        """Sliding window n-gram frequency analysis."""
        sequences = self._find_repeated_sequences(window=5)
        for seq in sequences:
            if seq.count >= self.threshold and not seq.suggested:
                self._suggest_automation(seq)
    
    def _suggest_automation(self, pattern: ActionPattern):
        """Emit suggestion to the LLM for proactive response."""
        event_bus.emit("pattern_detected", {
            "actions": pattern.actions,
            "count": pattern.count,
            "time_range": pattern.time_range,
        })
```

**Data stored:** 100% local SQLite. Never leaves the machine.

**Integration point:** Every tool call in `jarvis.py` also calls `shadow_learner.record_event()`. After 3+ repetitions, May suggests an automation.

### 5.2 — Proactive Screen Monitoring
> "You've been on that page for 5 minutes — need help?"

**Implementation in `backend/intelligence/screen_watcher.py`:**

```python
class ScreenWatcher:
    """Takes low-res screenshots periodically and detects user state."""
    
    interval_sec = 8
    resolution = (400, 300)  # Very low res, fast to process
    
    def __init__(self):
        self.active = False
        self.last_hash = 0
        self._rules: list[ProactiveRule] = [
            ProactiveRule("error_dialog", "Looks like an error — want me to search the fix?"),
            ProactiveRule("same_page_5min", "You've been here a while, need help?"),
            ProactiveRule("large_text_block", "That looks long — want a summary?"),
            ProactiveRule("email_compose", "Want me to help write that?"),
            ProactiveRule("calendar_today", "You have a meeting coming up."),
            ProactiveRule("low_battery", "Battery is getting low — want me to save your work?"),
        ]
    
    async def watch_loop(self):
        while self.active:
            screen = await self._capture_lowres()
            screen_hash = hash(screen)
            if screen_hash != self.last_hash:
                self.last_hash = screen_hash
                context = await self._analyze_screen(screen)
                suggestion = self._check_rules(context)
                if suggestion:
                    event_bus.emit("proactive_suggestion", suggestion)
            await asyncio.sleep(self.interval_sec)
    
    def _should_skip(self) -> bool:
        """Smart throttling — don't interrupt during typing, fullscreen video, gaming."""
        # Check if user is actively typing (high input rate)
        # Check if a fullscreen app is active
        # Check if a game is detected
        return False
```

**Smart throttling:** Will NOT interrupt during active typing, fullscreen video, or gaming.

### 5.3 — Frustration Detector
> "Looks like a rough moment — want me to handle what's blocking you?"

**Implementation in `backend/intelligence/frustration_detector.py`:**

```python
class FrustrationDetector:
    """Detects user stress purely from keyboard and mouse behavior. No camera."""
    
    SIGNALS = {
        "rapid_backspace":    {"threshold": 8, "window": 1},     # 8+ backspace/sec
        "ctrl_z_spam":        {"threshold": 5, "window": 10},    # 5+ undo in 10sec
        "mouse_thrashing":    {"threshold": 0.7, "window": 5},   # velocity variance
        "rapid_app_switch":   {"threshold": 6, "window": 30},    # 6+ alt-tab in 30sec
        "rage_click":         {"threshold": 4, "window": 3},     # 4+ clicks same region
        "long_pause":         {"threshold": 90, "window": 90},   # 90sec no input
        "repeat_same_action": {"threshold": 3, "window": 60},    # same action 3+ times
    }
    
    def calculate_score(self) -> int:
        """Returns 0-100 frustration score."""
        score = 0
        for signal_name, config in self.SIGNALS.items():
            if self._detect_signal(signal_name, config):
                score += self.SIGNAL_WEIGHTS[signal_name]
        return min(100, score)
    
    def get_response(self, context: str) -> str:
        """Context-aware response based on what app the user is in."""
        if context == "code_editor":
            return "Want me to search that error or explain this section?"
        if context == "browser":
            return "Want me to take over and find what you need?"
        if context == "document":
            return "Want me to rewrite that paragraph?"
        return "Looks like a rough moment — want me to handle what's blocking you?"
```

**Cooldown:** Once triggered, won't fire again for 5 minutes to avoid spam.

### 5.4 — Wake Word Detection
> "Hey May" → starts listening

**Implementation in `wake/listener.py`:**

```python
class WakeWordListener:
    """Runs as a separate process. Lightweight, <2% CPU."""
    
    def __init__(self, wake_phrase: str = "hey_may"):
        self.wake_phrase = wake_phrase
        self.hotkey = "ctrl+space"  # Manual fallback
        self.on_wake = None  # Callback
    
    async def listen_loop(self):
        """Continuous mic monitoring via openwakeword."""
        model = openwakeword.Model(wakeword_models=["hey_may"])
        while True:
            audio = await self._capture_chunk()
            prediction = model.predict(audio)
            if prediction["hey_may"] > 0.5:
                self.on_wake()
    
    def setup_hotkey(self):
        """Ctrl+Space always works as manual override."""
        keyboard.add_hotkey("ctrl+space", lambda: self.on_wake())
```

**Integration:** When wake word detected → signals FastAPI brain → starts STT → processes command → TTS response.

### 5.5 — Privacy Mode
> "Privacy mode on" → everything stops. Silent.

**Implementation in `backend/intelligence/privacy.py`:**

```python
class PrivacyMode:
    """One command kills everything."""
    
    def __init__(self):
        self.active = False
        self.audit_log: list[AuditEntry] = []
    
    def activate(self):
        self.active = True
        # Pause all intelligence modules
        shadow_learner.pause()
        screen_watcher.pause()
        frustration_detector.pause()
        wake_word_listener.pause()
        # Release microphone
        release_mic()
        # Log the event
        self.audit_log.append(AuditEntry(
            timestamp=time.time(),
            action="privacy_mode_activated",
            detail="All monitoring paused. Microphone released."
        ))
        return "Privacy mode active. I'm completely silent."
    
    def deactivate(self):
        self.active = False
        shadow_learner.resume()
        screen_watcher.resume()
        frustration_detector.resume()
        wake_word_listener.resume()
        return "Privacy mode off. I'm back~"
    
    def log_action(self, action: str, detail: str):
        """Plain English audit log."""
        self.audit_log.append(AuditEntry(
            timestamp=time.time(),
            action=action,
            detail=detail
        ))
```

**Audit log:** `~/may/audit_log.txt` — plain text, always readable, never encrypted.

### 5.6 — Morning Briefing Engine
> "Good morning. It's Tuesday. You have 3 meetings today..."

**Implementation in `backend/intelligence/briefing_engine.py`:**

```python
class BriefingEngine:
    """Generates a morning briefing from multiple sources."""
    
    sources = {
        "calendar": CalendarSource(),   # Google Calendar API
        "weather": WeatherSource(),     # wttr.in (free, no key)
        "news": NewsSource(),           # RSS feeds
        "stock": StockSource(),         # Yahoo Finance (free)
        "email": EmailSource(),         # Gmail IMAP
    }
    
    async def generate_briefing(self) -> str:
        parts = []
        
        # Date & day
        now = datetime.now()
        parts.append(f"Good morning. It's {now.strftime('%A, %B %d')}.")
        
        # Calendar
        meetings = await self.sources["calendar"].get_today()
        if meetings:
            parts.append(f"You have {len(meetings)} meetings today.")
        
        # Weather
        weather = await self.sources["weather"].get_current()
        parts.append(f"Weather is {weather}.")
        
        # News (top 2 headlines)
        news = await self.sources["news"].get_headlines(2)
        if news:
            parts.append(f"Top news: {', '.join(news)}.")
        
        # Overnight tasks
        # Check if any ghost mode tasks completed overnight
        
        return " ".join(parts)
```

### 5.7 — Fallback Chain Engine + Verification Pattern (JARVIS V2 Sections 12 & 15)

May already has `core/engine/fallback.py` but it's not wired into layer handlers. JARVIS V2's spec makes this explicit — **this is what gives 100% accuracy**.

#### Full Execution Pipeline (JARVIS V2 Section 15):

```
COMMAND RECEIVED
      │
      ▼
[1] ROUTER: Map command → layer + action
      │
      ▼
[2] PRE-FLIGHT CHECK
    ├─ Does the target exist?        (file/folder/process/window)
    ├─ Do we have permission?        (check ACL, privilege level)
    └─ Is the action safe to proceed? (e.g., not deleting system32)
      │
      ▼  [if pre-flight fails → return early with specific error]
      │
      ▼
[3] EXECUTE METHOD 1 (primary method)
      │
      ├─ [SUCCESS] → Verify → [VERIFIED] → ✅ Return Success
      │                     → [NOT VERIFIED] → try Method 2
      │
      └─ [EXCEPTION] → try Method 2
      │
      ▼
[4] EXECUTE METHOD 2 (first fallback)
      │
      ├─ [SUCCESS] → Verify → [VERIFIED] → ✅ Return Success
      └─ [EXCEPTION] → try Method 3
      │
      ▼
[5] EXECUTE METHOD 3 (second fallback)
      │
      ├─ [SUCCESS] → Verify → ✅ Return Success
      └─ [EXCEPTION] → Escalate privilege
      │
      ▼
[6] PRIVILEGE ESCALATION
    ├─ Enable additional token privileges
    ├─ If needed: re-run as SYSTEM via service
    └─ Retry from Method 1 with elevated context
      │
      ▼
[7] SCHEDULE / DEFER (for truly locked system resources)
    └─ MoveFileExW DELAY_UNTIL_REBOOT for files
       Task Scheduler for process-dependent actions
      │
      ▼
[8] RETURN FULL DIAGNOSTIC
    ├─ success: false
    ├─ error: exact reason each method failed
    └─ suggested_action: what the user can do to fix it
```

#### FallbackChain Implementation:

```python
class FallbackChain:
    """Multi-method retry with verification — the core of 100% accuracy."""
    
    async def execute(
        self,
        action: str,
        params: dict,
        methods: list[Callable],
        verifier: Callable | None = None,
    ) -> tuple[bool, Any, str, str]:
        """
        Returns: (success, result, method_used, error_message)
        """
        errors = []
        
        for i, method in enumerate(methods):
            method_name = f"method_{i+1}_{method.__name__}"
            try:
                t_start = time.monotonic()
                result = await method(params)
                t_end = time.monotonic()
                
                # Verify the action actually worked
                if verifier:
                    await asyncio.sleep(0.05)  # Brief settle time for OS
                    verified = await verifier(params, result)
                    if not verified:
                        errors.append(f"{method_name}: executed but verification failed")
                        continue
                
                return True, result, method_name, ""
            
            except Exception as e:
                errors.append(f"{method_name}: {str(e)}")
                continue
        
        return False, None, "none", " | ".join(errors)
```

#### Example: delete_file with 7-method fallback (JARVIS V2 Section 3):

```python
async def handle_delete_file(params: dict) -> Result:
    return await fallback.execute(
        action="delete_file",
        params=params,
        methods=[
            lambda p: os.remove(p["path"]),
            lambda p: win32file_delete(p["path"]),
            lambda p: subprocess.run(["cmd", "/c", "del", "/F", "/Q", p["path"]]),
            lambda p: set_attributes_normal(p["path"]) or os.remove(p["path"]),
            lambda p: take_ownership_and_delete(p["path"]),
            lambda p: kill_locking_process(p["path"]) or os.remove(p["path"]),
            lambda p: move_file_ex_reboot(p["path"]),  # Guaranteed on next boot
        ],
        verifier=lambda p, _: not os.path.exists(p["path"]),
    )
```

#### Post-Action Verification Functions (JARVIS V2 Section 12):

```python
class Verifiers:
    @staticmethod
    async def file_deleted(params, result) -> bool:
        return not os.path.exists(params["path"])
    
    @staticmethod
    async def file_exists(params, result) -> bool:
        return os.path.exists(params["path"])
    
    @staticmethod
    async def process_killed(params, result) -> bool:
        return not any(p.pid == params["pid"] for p in psutil.process_iter())
    
    @staticmethod
    async def window_position(params, result) -> bool:
        import win32gui
        rect = win32gui.GetWindowRect(params["hwnd"])
        return rect[0] == params["x"] and rect[1] == params["y"]
    
    @staticmethod
    async def registry_value(params, result) -> bool:
        import winreg
        val, _ = winreg.QueryValueEx(params["key"], params["name"])
        return val == params["value"]
    
    @staticmethod
    async def volume_set(params, result) -> bool:
        current = get_volume()
        return abs(current - params["level"]) < 0.01
    
    @staticmethod
    async def service_running(params, result) -> bool:
        status = get_service_status(params["name"])
        return status == "RUNNING"
```

### 5.8 — Parallel Multi-Agent Executor
> "While that file downloads, search for the best settings, open Notepad, and remind me in 10 minutes."

**Implementation in `backend/intelligence/parallel_executor.py`:**

```python
class ParallelExecutor:
    """Runs multiple independent tasks simultaneously."""
    max_agents = 6
    
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=self.max_agents)
        self.active_tasks: dict[str, Future] = {}
    
    async def execute_parallel(self, tasks: list[Task]):
        """Execute multiple tasks concurrently."""
        futures = {
            task.id: self.pool.submit(self._run_task, task)
            for task in tasks
        }
        for tid, future in futures.items():
            self.active_tasks[tid] = future
            future.add_done_callback(
                lambda f, id=tid: self._on_task_done(id, f)
            )
    
    def _on_task_done(self, task_id: str, future: Future):
        """Handle task completion — notify HUD, chain results."""
        result = future.result()
        event_bus.emit("agent_done", {"id": task_id, "result": result})
        del self.active_tasks[task_id]
```

**HUD shows live status panel** with each agent's progress when parallel mode is active.

### 5.9 — Ghost Mode (Autonomous Overnight Tasks)
> "While I sleep, research Apple, Google, Microsoft Q3 earnings, compile a report, and have it open when I wake up."

**Implementation in `backend/intelligence/ghost_mode.py`:**

```python
class GhostMode:
    """Autonomous overnight task execution."""
    
    def __init__(self):
        self.queue: list[GhostTask] = []
        self.active = False
    
    async def run_ghost_loop(self):
        """Main loop — waits for user idle, then executes queued tasks."""
        while self.active:
            if self._user_idle() and self.queue:
                for task in self.queue:
                    await orchestrator.execute_plan(task.steps)
                self.queue.clear()
                # Notify user on wake
                event_bus.emit("ghost_complete", {
                    "message": "Your tasks are complete~"
                })
            await asyncio.sleep(30)
    
    def _user_idle(self) -> bool:
        """Check if user has been idle for 5+ minutes."""
        return (time.time() - last_input_time) > 300
    
    def queue_task(self, task: GhostTask):
        """Add a task to the overnight queue."""
        self.queue.append(task)
```

**On wake (first mouse movement):** May says "Good morning. Your report is ready on your desktop."

### 5.10 — Voice Biometric Auth
> Only responds to YOUR voice. Strangers or recordings are rejected.

**Implementation in `wake/voice_auth.py`:**

```python
class VoiceAuth:
    """Voice biometric authentication using resemblyzer."""
    threshold = 0.82  # Cosine similarity cutoff
    
    def __init__(self):
        self.encoder = VoiceEncoder()
        self.owner_embedding = None
    
    def enroll(self, audio_samples: list[np.ndarray]):
        """User says 3 phrases during setup."""
        embeddings = [self.encoder.embed_utterance(s) for s in audio_samples]
        self.owner_embedding = np.mean(embeddings, axis=0)
        self._save_enrollment()
    
    def verify(self, audio: np.ndarray) -> bool:
        """Check if the speaker is the enrolled owner."""
        if self.owner_embedding is None:
            return True  # No enrollment = anyone can use
        embedding = self.encoder.embed_utterance(audio)
        return cosine_similarity(embedding, self.owner_embedding) > self.threshold
```

**Setup:** On first run, May says "Please say these 3 phrases to register your voice."
**Bypass:** Ctrl+Space hotkey always works regardless.

### 5.11 — Voice Personality Modes
> "Hey May, switch to debug mode"

```python
PERSONALITY_MODES = {
    "shikimori": {
        "tts_voice": "en-US-GuyNeural",
        "response_length": "short",
        "tone": "cool, calm, caring",
        "tilde_frequency": 0.3,
    },
    "formal": {
        "tts_voice": "en-US-GuyNeural",
        "response_length": "concise",
        "tone": "professional, precise",
        "tilde_frequency": 0.0,
    },
    "debug": {
        "tts_voice": "en-US-GuyNeural",
        "response_length": "verbose",
        "tone": "narrates every action",
        "tilde_frequency": 0.1,
    },
    "silent": {
        "tts_voice": None,
        "response_length": "short",
        "tone": "text-only, no TTS",
        "tilde_frequency": 0.3,
    },
}
```

### 5.12 — Contextual Awareness
> Every AI prompt includes live context for situationally aware responses.

```python
async def build_context() -> dict:
    """Gather live context for every LLM prompt."""
    return {
        "time_of_day":    get_time_of_day(),         # morning/afternoon/evening/night
        "day_of_week":    datetime.now().strftime("%A"),
        "active_app":     await get_active_app(),     # "Visual Studio Code"
        "active_file":    await get_active_file(),     # "main.py"
        "user_state":     get_user_state(),           # working/idle/gaming
        "battery":        await get_battery_percent(), # "67%"
        "pending_tasks":  ghost_queue.count(),
        "active_agents":  parallel_executor.active_count(),
    }
```

**Injected into system prompt:** Gives May situational awareness like "You're in VS Code — should I open a terminal too?"

### 5.13 — Meeting Mode
> "Hey May, I'm joining a meeting — take notes"

```python
class MeetingMode:
    """Capture system audio, transcribe, summarize."""
    
    async def start(self):
        """Begin capturing system audio."""
        self.audio_stream = await capture_system_audio()
        self.transcript = []
    
    async def stop(self) -> MeetingSummary:
        """Stop capture, transcribe, generate summary."""
        audio = await self.audio_stream.collect()
        transcript = await stt.transcribe(audio)
        summary = await llm.summarize(transcript)
        action_items = await llm.extract_actions(transcript)
        # Save to ~/may/meetings/YYYY-MM-DD.md
        save_meeting(summary, action_items)
        return MeetingSummary(summary, action_items)
```

### 5.14 — Smart Home Control
> "Dim the lights to 40%"

**Integrations:** Home Assistant (local, free, 1000+ devices), MQTT, Philips Hue, SmartThings.

```python
class SmartHomeController:
    def __init__(self, ha_url: str, ha_token: str):
        self.ha_client = HomeAssistantClient(ha_url, ha_token)
    
    async def execute(self, action: str, entity: str, params: dict = {}):
        return await self.ha_client.call_service(
            domain=entity.split(".")[0],
            service=action,
            entity_id=entity,
            **params,
        )
```

### 5.15 — Health & Wellness Reminders
> "Time to drink some water~"

```python
WELLNESS_RULES = [
    Rule("water",   interval_min=45,  msg="Time to drink some water."),
    Rule("posture", interval_min=30,  msg="Check your posture."),
    Rule("break",   interval_min=90,  msg="90 minutes in — take a 5-minute break."),
    Rule("eyes",    interval_min=20,  msg="Look away from the screen for 20 seconds."),
]
```

**Silenceable:** "May, skip wellness reminders for today."

### 5.16 — Remote Control from Phone
> Phone opens http://192.168.x.x:7777 — minimal web UI.

```python
@app.post("/command")
async def receive_command(cmd: str):
    await orchestrator.process_text_command(cmd)

@app.get("/screenshot")
async def get_screenshot():
    return StreamingResponse(capture_screen_jpeg_stream())
```

**LAN only.** Never exposed to the internet.

### 5.17 — Explain My Screen
> "What am I looking at?"

Captures screenshot → sends to vision model → describes what's on screen.
Works with any app — code, spreadsheets, PDFs, games.

### 5.18 — Self-Diagnostic Mode
> "Run diagnostics"

```python
async def run_diagnostics() -> str:
    return f"""Running systems check...
    CPU at {cpu_percent}% — {'normal' if cpu < 80 else 'high'}.
    RAM: {ram_used}GB of {ram_total}GB — {'normal' if ram < 80 else 'high'}.
    Wake word: {'active' if wake_active else 'inactive'}.
    Voice auth: {'enrolled' if voice_enrolled else 'not enrolled'}.
    Shadow learner: {patterns_count} patterns recorded.
    Ghost queue: {ghost_count} tasks.
    Plugins loaded: {plugin_count}.
    All systems nominal."""
```

### 5.19 — Security Monitor
> Watches for suspicious activity and alerts immediately.

```python
SECURITY_RULES = [
    "Unknown USB device connected",
    "New app installed without user request",
    "Microphone accessed by non-May app",
    "Suspicious background network connections",
    "Screen capture attempt by unknown process",
]
```

Alerts: "Alert: a USB storage device was connected. Do you recognize it?"

### 5.20 — "Faster" Execution Mode
> When repeating a known sequence, May asks: "I've done this before. Run it at full speed?"

- **Full speed:** No mouse animation delay, no pauses between steps.
- **Normal speed:** Human-paced with visual feedback so you can follow along.

### 5.21 — Plugin System

```python
class BasePlugin:
    """Base class for May plugins."""
    name: str
    version: str
    tools: list[dict]  # Tool schemas
    
    def execute(self, tool_name: str, params: dict) -> str:
        raise NotImplementedError

class SpotifyPlugin(BasePlugin):
    name = "spotify"
    version = "1.0"
    tools = [
        {"name": "play_song", "params": {"query": "str"}},
        {"name": "pause", "params": {}},
        {"name": "next_track", "params": {}},
    ]
```

**Plugin Manager** registers new tools into the AI's tool registry at runtime. No restart needed.
**Voice installation:** "Hey May, install the Spotify skill" → downloads plugin, registers tools.

---

## 6. Execution Flow (End-to-End)

### 6.1 — Text Command
```
User types "open discord and play some music"
  → Frontend sends POST /chat {message, provider, model}
  → FastAPI → jarvis_chat() → LLM with 100+ tool definitions
  → LLM returns: tool_calls [{open_app, discord}, {play_song, music}]
  → core_bridge.execute_tool_via_core("open_app", {app_name: "discord"})
    → TCP → Daemon → L3_application.handler("launch_app", {app_name: "discord"})
      → FallbackChain: Start-Process → os.startfile → registry search → Start Menu
      → Verifier: is_app_running("discord") == True
      → Result(success=True, method_used="method_1_start_process")
  → core_bridge.execute_tool_via_core("play_song", {query: "music"})
    → Plugin handler (SpotifyPlugin)
  → LLM generates natural response: "Discord's open~ Playing some music for you."
  → Streamed back to frontend via StreamingResponse
```

### 6.2 — Voice Command (with Wake Word)
```
Microphone captures "Hey May" → Wake word listener detects it
  → Chime plays
  → FastAPI /voice/transcribe-audio (5 second capture)
  → faster-whisper transcription (GPU: 0.3s, CPU: 2s)
  → Text sent to /chat → same flow as above
  → TTS speaks response via browser SpeechSynthesis
```

### 6.3 — Proactive Action (Intelligence Layer)
```
Shadow learner detects: user opened Chrome → Gmail → Inbox 3 mornings in a row
  → event_bus.emit("pattern_detected", {actions: ["chrome", "gmail", "inbox"], count: 3})
  → FastAPI brain receives event
  → LLM generates suggestion: "I've noticed you open Chrome, Gmail, then check your inbox every morning. Want me to automate that?"
  → Toast notification or chat message
  → User says "yes" → creates a scheduled macro
```

### 6.4 — Frustration Response
```
Frustration detector: rapid_backspace (10/sec) + ctrl_z_spam (5 in 10sec)
  → Score: 75/100
  → Context: active app is VS Code
  → Response: "Want me to search that error or explain this section?"
  → Shown as proactive suggestion (toast or chat)
```

---

## 7. Thread/Process Architecture

```
PROCESS 1 — Tauri (Rust):
  Main Thread:     Tauri event loop + React UI
  Web Worker:      Vite dev server (dev mode)

PROCESS 2 — FastAPI Brain (Python):
  Main Thread:     uvicorn event loop (async)
  Thread-1:        STT model pre-load (background)
  Thread-2:        Daemon health check (30s interval)
  Thread-3:        Shadow learner background analysis
  Thread-4:        Screen watcher (8s interval)
  Thread-5:        Frustration detector (input monitor)
  Thread-6:        Reminder checker (background)

PROCESS 3 — Control Core Daemon (Python):
  Main Thread:     asyncio event loop
  TCP Listener:    BusServer on 127.0.0.1:7650
  Worker Pool:     Layer handlers execute in async tasks

PROCESS 4 — Wake Word Listener (Python):
  Main Thread:     openwakeword microphone listener
  Thread-1:        Hotkey listener (pynput)

All processes communicate via TCP/HTTP. Zero shared mutable state.
```

---

## 8. Configuration

```yaml
# config/may.yaml
may:
  name: "May"
  wake_word: "hey_may"
  hotkey: "ctrl+space"
  personality: "shikimori"      # shikimori / formal / debug / silent

ai:
  mode: "auto"                  # local / cloud / auto
  local:
    provider: "ollama"
    model: "qwen3:4b"
    endpoint: "http://localhost:11434"
  cloud:
    provider: "openrouter"      # or openai, anthropic, gemini
    model: "auto"

voice:
  stt_mode: "local"             # local (faster-whisper) / browser (dead in Tauri)
  tts_mode: "browser"           # browser (SpeechSynthesis) / edge / elevenlabs
  stt_model: "auto"             # auto / large-v3-turbo (GPU) / small (CPU)
  silence_threshold_ms: 1500

intelligence:
  shadow_learning: true
  screen_watching: true
  screen_watch_interval_sec: 8
  frustration_detection: true
  frustration_cooldown_sec: 300
  briefing_enabled: false       # Enable when calendar/weather APIs are set up
  briefing_time: "08:30"

privacy:
  audit_log_enabled: true
  audit_log_path: "~/may/audit_log.txt"
  privacy_hotkey: "ctrl+shift+p"

wellness:
  water_reminder_min: 45
  break_reminder_min: 90
  eye_reminder_min: 20
  enabled: true

ui:
  theme: "surfaced_dark"
  accent_color: "#06B6D4"       # Electric Cyan
  always_on_top: true
  orb_animations: true

system:
  start_with_windows: true
  confirm_destructive: true
  max_history_turns: 20
```

---

## 9. Development Phases

### Phase 11: Fallback Chains + Verification (Week 1)
- [ ] Wire `FallbackChain` into all 9 layer handlers
- [ ] Add `Verifier` functions for every action
- [ ] Test: delete file with locked handle → verify retry works
- [ ] Test: kill protected process → verify SYSTEM escalation works

### Phase 12: Intelligence Layer (Week 2-3)
- [ ] Implement `ShadowLearner` with SQLite storage
- [ ] Implement `FrustrationDetector` with keyboard/mouse hooks
- [ ] Implement `ScreenWatcher` with low-res capture + rule engine
- [ ] Wire all three into `jarvis.py` for proactive suggestions
- [ ] Test: open Chrome 3 mornings → May suggests automation

### Phase 13: Wake Word + Privacy (Week 3-4)
- [ ] Implement `WakeWordListener` with openwakeword
- [ ] Implement `PrivacyMode` with audit log
- [ ] Wire wake word → STT → chat pipeline
- [ ] Test: "Hey May" → starts listening → responds by voice

### Phase 14: Briefing + Integrations (Week 4-5)
- [ ] Implement `BriefingEngine` with calendar/weather/news sources
- [ ] Add Google Calendar API integration
- [ ] Add wttr.in weather (free, no key)
- [ ] Test: morning briefing generates correctly

### Phase 15: Plugin System (Week 5-6)
- [ ] Implement `BasePlugin` class
- [ ] Implement `PluginManager` (register tools at runtime)
- [ ] Create Spotify plugin as reference implementation
- [ ] Voice plugin installation flow

### Phase 16: Polish + Boot Startup (Week 6)
- [ ] Windows boot startup (Task Scheduler)
- [ ] System tray icon
- [ ] Performance tuning (CPU/memory profiling)
- [ ] Integration testing (all features end-to-end)

---

## 10. Technology Stack

| Layer | Technology | Source |
|:---|:---|:---|
| **Desktop Framework** | Tauri v2 (Rust + React) | May ✅ |
| **Frontend** | React 18 + TypeScript + Tailwind + Framer Motion | May ✅ |
| **Avatar** | CSS glass sphere + Framer Motion orbital rings | May ✅ |
| **Backend** | Python FastAPI | May ✅ |
| **LLM Runtime** | Ollama (local) + 6 cloud providers | May ✅ |
| **Tool Calling** | Native (Ollama/OpenAI) + text-based fallback | May ✅ |
| **Voice STT** | faster-whisper (GPU auto-detect → CPU fallback) | May ✅ |
| **Voice TTS** | Browser SpeechSynthesis API | May ✅ |
| **Wake Word** | openwakeword (custom "Hey May") | JARVIS V2 ✨ |
| **Memory Vectors** | LanceDB 0.33.0 + sentence-transformers | May ✅ |
| **Memory Facts** | SQLite | May ✅ |
| **System Control** | 9-layer daemon with 100+ tools | May ✅ |
| **Fallback Engine** | FallbackChain with verification | JARVIS V2 ✨ |
| **Privilege Mgmt** | Admin → SYSTEM (PsExec) → TrustedInstaller | May ✅ |
| **Shadow Learning** | SQLite + sliding window n-gram analysis | JARVIS V2 ✨ |
| **Screen Watch** | Low-res capture + rule engine | JARVIS V2 ✨ |
| **Frustration Det.** | Keyboard/mouse input analysis | JARVIS V2 ✨ |
| **Privacy Mode** | Kill switches + audit log | JARVIS V2 ✨ |
| **Morning Briefing** | Calendar + Weather + News + Email | JARVIS V2 ✨ |
| **Plugin System** | BasePlugin + runtime tool registration | JARVIS V2 ✨ |
| **Notifications** | winotify (Windows 10/11 native) | May ✅ |

---

## 11. Key Design Decisions

1. **3-process model over single-process** — May's architecture is crash-isolated. JARVIS V2's single process with 12 threads is fragile.
2. **Multi-provider LLM over single-provider** — May supports 6 providers. JARVIS V2 only detailed OpenAI.
3. **TCP bus over named pipe** — May chose TCP. Both work. TCP is simpler to debug.
4. **Browser mic capture over Python sounddevice** — Python records silence on Windows. Browser getUserMedia works. May discovered this the hard way.
5. **GPU auto-detect with CPU fallback** — Don't assume CUDA is available. May's STT works on any hardware.
6. **Shadow learning stays local** — All pattern data in SQLite. Never leaves the machine.
7. **Screen watcher at 400x300** — Low resolution = fast processing. No need for full screenshots.
8. **Frustration detector uses input only** — No camera. No microphone analysis. Pure keyboard/mouse behavior. Privacy-respecting.
9. **Privacy mode is absolute** — One command kills everything. No exceptions. Audit log proves it.
10. **Plugin system is optional** — Core features work without plugins. Plugins extend, not replace.

---

*May v3 Architecture — Built on what works. Evolved with what's next.*
*Last updated: Session 11*
