op# JARVIS AI v2 — Complete Architecture (Ultimate Edition)

> The most complete personal AI desktop assistant ever built in Python.
> Always-on. Fully offline-capable. Cinematic UI. Genuinely intelligent.

---

## 1. What Makes This Different From Everything Else

| Feature | PyGPT | Claude Cowork | ChatGPT Agent | JARVIS v2 |
|---------|-------|--------------|---------------|-----------|
| Always-on wake word | No | No | No | Yes |
| Fully offline capable | No | No | No | Yes |
| Shadow learning | No | No | No | Yes |
| Proactive monitoring | No | No | No | Yes |
| Parallel agents | No | No | No | Yes |
| Ghost mode tasks | No | No | No | Yes |
| Frustration detection | No | No | No | Yes |
| Animated orb HUD | No | No | No | Yes |
| Plugin voice install | No | No | No | Yes |
| Voice biometrics | No | No | No | Yes |
| Morning briefing | No | No | No | Yes |
| Smart home control | No | No | No | Yes |
| Full privacy mode | No | Partial | No | Yes |
| Standalone .exe | No | Yes | Yes | Yes |

---

## 2. Complete System Architecture Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              JARVIS v2 PROCESS                              │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         INTELLIGENCE LAYER                           │  │
│  │  Shadow Learner | Screen Watcher | Frustration Detector | Briefing   │  │
│  └───────────────────────────┬──────────────────────────────────────────┘  │
│                               │ proactive triggers                         │
│  ┌────────────────┐    ┌──────▼───────┐    ┌─────────────────────────┐    │
│  │  Voice Layer   │───▶│ Orchestrator │───▶│    PC Control Engine    │    │
│  │ Wake + STT/TTS │    │  + Parallel  │    │ Mouse/KB/Screen/System  │    │
│  │ Voice Biometry │    │  Agent Pool  │    │ Browser/Files/Apps      │    │
│  └────────────────┘    └──────────────┘    └─────────────────────────┘    │
│                                │                                           │
│  ┌─────────────────────────────▼──────────────────────────────────────┐   │
│  │                          AI CORE                                    │   │
│  │  Model Router | Local (Ollama) | Cloud (OpenAI/Claude/Gemini)       │   │
│  │  Tool Registry (70+ tools) | Context Manager | Memory Store        │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                        INTEGRATION LAYER                            │  │
│  │  Smart Home | Calendar | Email | Weather | News | Remote Access     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                          UI LAYER                                   │  │
│  │  Animated Orb HUD | System Tray | Settings | Privacy Indicator      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                       PLUGIN SYSTEM                                 │  │
│  │  Plugin Manager | Plugin Store | Voice Install | Sandboxed Runner   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Complete Directory Structure

```
jarvis/
│
├── main.py
├── build.py
├── requirements.txt
│
├── config/
│   ├── config.yaml
│   ├── settings_manager.py
│   └── personality_profiles.yaml
│
├── core/
│   ├── orchestrator.py
│   ├── context_manager.py
│   ├── command_parser.py
│   ├── memory_store.py
│   ├── event_bus.py
│   └── startup_manager.py
│
├── ai/
│   ├── model_router.py
│   ├── local_model.py
│   ├── cloud_openai.py
│   ├── cloud_anthropic.py
│   ├── cloud_gemini.py
│   ├── tool_registry.py
│   └── system_prompt.py
│
├── voice/
│   ├── wake_word.py
│   ├── voice_auth.py            ← Voice biometric (speaker ID)
│   ├── custom_wake_word.py      ← Train your own wake phrase
│   ├── stt.py
│   ├── tts.py
│   └── voice_cloning.py
│
├── control/
│   ├── mouse_controller.py
│   ├── keyboard_controller.py
│   ├── screen_analyzer.py
│   ├── window_manager.py
│   ├── app_controller.py
│   ├── file_controller.py
│   ├── browser_controller.py
│   ├── system_controller.py
│   └── clipboard_controller.py
│
├── intelligence/               ← UNIQUE — no other project has this
│   ├── shadow_learner.py
│   ├── screen_watcher.py
│   ├── frustration_detector.py
│   ├── briefing_engine.py
│   ├── context_awareness.py
│   └── pattern_store.py
│
├── agents/
│   ├── parallel_executor.py
│   ├── ghost_mode.py
│   ├── task_planner.py
│   └── agent_monitor.py
│
├── integrations/
│   ├── smart_home.py
│   ├── calendar_sync.py
│   ├── email_manager.py
│   ├── weather.py
│   ├── news_feed.py
│   ├── finance_tracker.py
│   ├── music_controller.py
│   └── remote_access.py
│
├── privacy/
│   ├── privacy_mode.py
│   ├── audit_log.py
│   └── data_vault.py
│
├── plugins/
│   ├── plugin_manager.py
│   ├── plugin_sandbox.py
│   ├── plugin_store.py
│   └── base_plugin.py
│
├── ui/
│   ├── animated_hud.py
│   ├── tray_icon.py
│   ├── settings_window.py
│   ├── privacy_indicator.py
│   └── assets/
│       ├── jarvis.ico
│       ├── orb_idle.gif
│       ├── orb_listening.gif
│       ├── orb_speaking.gif
│       └── sounds/
│           ├── startup.wav
│           ├── wake.wav
│           └── done.wav
│
└── utils/
    ├── logger.py
    ├── crypto.py
    ├── hotkey_listener.py
    └── scheduler.py
```

---

## 4. All Unique Modules — Full Specification

---

### 4.1 Shadow Learning Mode

Runs silently at ~1% CPU. Watches what you do and learns your patterns.

Monitors:
- Apps you open at what times
- Repeated action sequences (open Chrome → Gmail → inbox every morning)
- Files you always open together
- Copy-paste patterns

After 3+ repetitions of a pattern:
```
Jarvis: "I've noticed you open Spotify, VS Code, then Discord
         every morning around 9am. Want me to automate that?"
```

```python
class ShadowLearner:
    threshold = 3   # repetitions before suggesting

    def record_event(self, action_type, target, timestamp):
        self.event_log.append((action_type, target, timestamp))
        self._analyze_patterns()

    def _analyze_patterns(self):
        # Sliding window n-gram frequency analysis
        sequences = self._find_repeated_sequences(window=5)
        for seq in sequences:
            if seq.count >= self.threshold and not seq.suggested:
                event_bus.emit("pattern_detected", seq)

    def to_macro(self, pattern) -> ScheduledMacro:
        # Convert pattern to executable scheduled macro
        pass
```

All pattern data stays 100% local in SQLite. Never leaves the machine.

---

### 4.2 Proactive Screen Monitoring

Takes a low-res screenshot every 8 seconds (configurable). Local AI checks for:

| Signal | Jarvis Says |
|--------|------------|
| Error dialog open | "Looks like an error — want me to search the fix?" |
| Same page > 5 min | "You've been here a while, need help?" |
| Large block of text | "That looks long — want a summary?" |
| Email compose open | "Want me to help write that?" |
| Calendar showing today | "You have a meeting in 20 minutes" |
| Low battery warning | "Battery at 15%, want me to save your work?" |

Smart throttling: will not interrupt during active typing, fullscreen video, or gaming.

```python
class ScreenWatcher:
    interval_sec = 8

    def watch_loop(self):
        while self.active:
            screen = capture_screen_lowres()   # 400x300, very fast
            if hash(screen) != self.last_hash:
                self.last_hash = hash(screen)
                context = local_vision.describe(screen)
                suggestion = self._check_rules(context)
                if suggestion:
                    event_bus.emit("proactive_suggestion", suggestion)
            time.sleep(self.interval_sec)
```

---

### 4.3 Frustration Detector

No camera. Detects stress purely from keyboard and mouse behavior:

```python
SIGNALS = {
    "rapid_backspace":    backspace_rate > 8/sec,
    "ctrl_z_spam":        undo_count > 5 in 10sec,
    "mouse_thrashing":    mouse_velocity_variance > threshold,
    "rapid_app_switch":   alt_tab_count > 6 in 30sec,
    "rage_click":         click_same_region > 4 in 3sec,
    "long_pause":         no_input_duration > 90sec,
    "repeat_same_action": identical_action_count > 3,
}
```

When score reaches 60+, Jarvis responds based on context:
- In code editor: "Want me to search that error or explain this section?"
- In browser: "Want me to take over and find what you need?"
- In document: "Want me to rewrite that paragraph?"
- General: "Looks like a rough moment — want me to handle what's blocking you?"

Cooldown prevents spam suggestions after triggering once.

---

### 4.4 Parallel Multi-Agent Executor

Runs multiple independent tasks simultaneously:

```
User: "While that file downloads, search for the best settings,
       open Notepad, and remind me in 10 minutes."

Agent-1: monitor_download()           → Thread-1
Agent-2: web_search("best settings")  → Thread-2
Agent-3: open_app("notepad")          → Thread-3
Agent-4: schedule_reminder(10_min)    → Scheduler

All four start at the same time.
When Agent-2 finishes, results paste into Agent-3's Notepad window.
```

HUD shows a live status panel with each agent's progress when parallel mode is active.

```python
class ParallelExecutor:
    max_agents = 6

    def execute_parallel(self, tasks: list[Task]):
        futures = {
            task.id: self.pool.submit(self._run_task, task)
            for task in tasks
        }
        for tid, future in futures.items():
            future.add_done_callback(
                lambda f, id=tid: event_bus.emit("agent_done", id)
            )
```

---

### 4.5 Ghost Mode

Autonomous overnight task execution:

```
User: "While I sleep, research Apple, Google, Microsoft Q3 earnings,
       compile a report, and have it open when I wake up."

Jarvis: "Understood. Sleep well."

Waits for idle > 5 min, then:
  1. Searches each company's earnings (3 web searches)
  2. Reads and summarizes each page
  3. Opens Word, types formatted report
  4. Saves to Desktop as "Earnings_Report.docx"

On wake (first mouse movement):
  Jarvis: "Good morning. Your earnings report is ready on your desktop."
  Brings Word to foreground.
```

```python
class GhostMode:
    def run_ghost_loop(self):
        while True:
            if self._user_idle() and self.queue:
                for task in self.queue:
                    orchestrator.execute_plan(task.steps)
                self.queue.clear()
            time.sleep(30)

    def _user_idle(self):
        return (time.time() - last_input_time) > 300   # 5 min
```

---

### 4.6 Animated Jarvis HUD

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│              [  animated arc reactor orb  ]         │
│                                                     │
│  ─────────────────────────────────────────────────  │
│  You: "open chrome and search for python tutorials" │
│  ▓▓▓▓▓▓▓▓░░░░░░░░░░░ Working...                    │
│  Jarvis: Done. Chrome is open on YouTube results.   │
│  ─────────────────────────────────────────────────  │
│  [    Type or speak a command...              ] [▶]  │
│  Mic: Listening    Privacy: Off    Agents: 3 active  │
└─────────────────────────────────────────────────────┘
   Frameless | Dark glass | Always-on-top | Draggable
```

Orb states (PyQt6 QPropertyAnimation):
- Idle: slow breathing pulse, dim blue
- Wake word: quick flash + chime
- Listening: fast rotating arc, bright cyan
- Processing: spinning particles
- Speaking: waveform synced to audio
- Ghost mode active: dim purple pulse
- Privacy mode: all gray, padlock icon
- Error: brief red flash

Colors: Background #080C14 at 88% opacity | Accent #00D4FF
Fonts: Orbitron (display titles) | Inter (body text)

---

### 4.7 Plugin System

Voice installation:
```
User: "Hey Jarvis, install the Spotify skill"
Jarvis: "Downloading... done. You can now say play, pause,
         next track, and set volume."
```

Plugin structure anyone can write:
```python
class SpotifyPlugin(BasePlugin):
    name = "spotify"
    version = "1.0"

    tools = [
        {"name": "play_song",  "params": {"query": "str"}},
        {"name": "pause",      "params": {}},
        {"name": "next_track", "params": {}},
    ]

    def execute(self, tool_name, params):
        if tool_name == "play_song":
            spotify.search_and_play(params["query"])
```

Plugin Manager registers new tools into the AI's tool registry at runtime. No restart needed.

---

### 4.8 Full Privacy Mode

One command kills everything:
```
User: "Hey Jarvis, privacy mode on"
→ Wake word listener:    PAUSED
→ Screen watcher:        PAUSED
→ Frustration detector:  PAUSED
→ Microphone:            RELEASED
→ HUD:                   Shows red padlock
Jarvis: "Privacy mode active. I'm completely silent."
```

Full audit log in plain English:
```
[09:12:33] Heard wake word. Started recording.
[09:12:37] User said: "open chrome"
[09:12:37] Launched: chrome.exe
[09:12:40] Spoke: "Chrome is open."
[09:14:01] Screen watcher: suggested help. User declined.
[09:20:00] Privacy mode activated by user.
[09:35:00] Privacy mode deactivated by user.
```

Stored at ~/Jarvis/audit_log.txt — plain text, always readable, never encrypted.

---

### 4.9 Voice Biometric Auth

Jarvis only responds to your voice. Strangers or recordings are rejected.

```python
from resemblyzer import VoiceEncoder

class VoiceAuth:
    threshold = 0.82    # Cosine similarity cutoff

    def enroll(self, audio_samples):
        # User says 3 phrases during setup
        embeddings = [self.encoder.embed_utterance(s) for s in samples]
        self.owner_embedding = np.mean(embeddings, axis=0)

    def verify(self, audio) -> bool:
        embedding = self.encoder.embed_utterance(audio)
        return cosine_similarity(embedding, self.owner_embedding) > self.threshold
```

Setup: on first run Jarvis says "Please say these 3 phrases to register your voice."
Bypass: Ctrl+Space hotkey always works regardless.

---

### 4.10 Custom Wake Word + Voice Cloning

Train your own wake phrase with openwakeword (your name, a custom word, anything).

Voice cloning options:
- ElevenLabs voice cloning (upload 1 min of audio, get custom TTS voice)
- Piper local TTS with fine-tuned voice model
- Clone any voice or invent a new one entirely

```
"Hey Jarvis, switch to FRIDAY voice"  → switches TTS model
"Hey Jarvis, use my custom voice"     → uses your cloned voice
```

---

## 5. New Jarvis-Like Features

---

### 5.1 Voice Personality Modes

```
"Hey Jarvis, switch to FRIDAY mode"   → casual, warm, witty
"Hey Jarvis, switch to formal mode"   → professional, concise
"Hey Jarvis, switch to silent mode"   → text-only, no TTS
"Hey Jarvis, switch to debug mode"    → narrates every action
```

Each mode changes TTS voice, response length, verbosity, and sound effects.

---

### 5.2 Smart Home Control

```
"Dim the lights to 40%"
"Turn off everything in the living room"
"Set the thermostat to 22 degrees"
"Lock the front door"
```

Integrates with:
- Home Assistant (local network, free, 1000+ devices)
- MQTT direct device control
- Philips Hue direct bridge API
- SmartThings (Samsung ecosystem)

```python
class SmartHomeController:
    def execute(self, action, entity, params={}):
        self.ha_client.call_service(
            domain=entity.split(".")[0],
            service=action,
            entity_id=entity,
            **params
        )
```

---

### 5.3 Morning Briefing Engine

Every morning at your configured time or first login:

```
Jarvis: "Good morning. It's Tuesday November 14th. You have 3
         meetings today — first at 10am with the design team.
         Weather is 18 degrees and clear. Apple stock is up 2.1%.
         Top news: [2 headlines]. Your most urgent email is from
         Alex sent last night. Your overnight task is complete —
         the report is on your desktop."
```

Sources: Google Calendar, OpenWeatherMap, NewsAPI/RSS, yfinance, Gmail IMAP.

---

### 5.4 Contextual Awareness

Every AI prompt includes live context:

```python
context = {
    "time_of_day":        "morning",
    "day_of_week":        "Tuesday",
    "active_app":         "Visual Studio Code",
    "active_file":        "main.py",
    "user_state":         "working",
    "next_meeting":       "10am standup",
    "battery":            "67%",
    "pending_ghosts":     1,
    "active_agents":      0,
}
```

Gives situationally aware responses:
"You're in VS Code — should I open a terminal too?"

---

### 5.5 Meeting Mode

```
"Hey Jarvis, I'm joining a meeting — take notes"
```

- Captures system audio
- Transcribes everything (Whisper)
- Generates summary + action items on "Meeting over"
- Saves to ~/Jarvis/meetings/2025-11-14.md
- Can email summary: "Send the notes to everyone on the invite"

---

### 5.6 Health and Wellness Reminders

```python
WELLNESS_RULES = [
    Rule("water",   interval=45,  msg="Time to drink some water."),
    Rule("posture", interval=30,  msg="Check your posture."),
    Rule("break",   interval=90,  msg="90 minutes in — take a 5-minute break."),
    Rule("eyes",    interval=20,  msg="Look away from the screen for 20 seconds."),
]
```

Silenceable: "Jarvis, skip wellness reminders for today."

---

### 5.7 Remote Control from Phone

FastAPI server on local Wi-Fi only (never internet-exposed).

Phone opens http://192.168.x.x:7777 — minimal web UI.
Type or tap a command → Jarvis executes it on PC.
See a thumbnail of your screen in real-time.

```python
@app.post("/command")
async def receive_command(cmd: str):
    orchestrator.process_text_command(cmd)

@app.get("/screenshot")
async def get_screenshot():
    return StreamingResponse(capture_screen_jpeg_stream())
```

---

### 5.8 Explain My Screen

```
User: "Jarvis, what am I looking at?"

Jarvis: "You're looking at a Python NameError on line 47.
         The variable 'result' was used before being assigned.
         Want me to fix it?"
```

Works with any app — code, spreadsheets, PDFs, games, anything on screen.

---

### 5.9 Self-Diagnostic Mode

```
User: "Jarvis, run diagnostics"

Jarvis: "Running systems check...
         CPU at 34% — normal.
         RAM: 6.2GB of 16GB — normal.
         Wake word: active.
         Voice auth: enrolled.
         Shadow learner: 47 patterns recorded.
         Ghost queue: empty.
         Plugins loaded: 3.
         All systems nominal."
```

---

### 5.10 Security Monitor

Watches for:
- Unknown USB device connected
- New app installed without user request
- Microphone accessed by non-Jarvis app
- Suspicious background network connections
- Screen capture attempt by unknown process

Alerts immediately:
"Alert: a USB storage device was connected. Do you recognize it?"

---

### 5.11 "Faster" Execution Mode

When repeating a known sequence, Jarvis asks:
"I've done this before. Run it at full speed?"

Full speed: no mouse animation delay, no pauses between steps.
Normal speed: human-paced with visual feedback so you can follow along.

---

## 6. Complete Tool Registry — 70+ Tools

Mouse and Keyboard (10):
move_mouse, click, double_click, right_click, drag,
scroll, type_text, press_key, hotkey, hold_key

Screen and Vision (8):
take_screenshot, find_text_on_screen, find_image_on_screen,
read_screen_text, get_pixel_color, wait_for_element,
explain_screen, detect_active_app

Window Management (7):
focus_window, minimize_window, maximize_window, close_window,
resize_window, list_windows, move_window

Applications (5):
open_app, close_app, list_running_apps, is_app_running, restart_app

File System (10):
read_file, write_file, append_file, delete_file, move_file,
copy_file, list_directory, create_folder, open_file, search_files

Browser (7):
open_url, search_web, get_page_text, click_browser_element,
fill_input, scroll_page, get_page_title

System (10):
set_volume, get_volume, set_brightness, get_battery,
shutdown, restart, sleep, run_command, get_system_info, send_notification

AI Internal (8):
respond, remember, recall, ask_clarification,
chain_task, spawn_agent, schedule_task, enter_ghost_mode

Intelligence (6):
get_context, trigger_briefing, list_learned_patterns,
suggest_automation, detect_frustration_state, explain_screen

Integrations (9):
get_weather, get_news, get_calendar_events, read_email,
send_email, play_music, smart_home_action, get_stock_price, get_crypto_price

---

## 7. Thread Architecture

```
Main Thread:        PyQt6 UI event loop
Thread-2:           openwakeword microphone listener
Thread-3:           Global hotkey listener (pynput)
Thread-4:           Orchestrator / AI loop
Thread-5:           TTS audio playback
Thread-6:           pystray system tray
Thread-7:           Shadow learner (background)
Thread-8:           Screen watcher (8-second loop)
Thread-9:           Frustration detector (input monitor)
Thread-10:          Ghost mode task runner
Thread-11:          APScheduler (briefings, wellness, reminders)
Thread-12:          FastAPI remote access server
Agent Pool 1-6:     Parallel executor (dynamic, on demand)

All communicate via queue.Queue() — zero shared mutable state.
```

---

## 8. Full Config File

```yaml
jarvis:
  name: "Jarvis"
  wake_word: "hey_jarvis"
  hotkey: "ctrl+space"
  personality: "jarvis"          # jarvis / friday / formal / silent / debug
  voice_auth_enabled: true

ai:
  mode: "auto"                   # local / cloud / auto
  local:
    provider: "ollama"
    model: "llama3.1:8b"
    vision_model: "llava:13b"
    endpoint: "http://localhost:11434"
  cloud:
    provider: "openai"
    model: "gpt-4o"
    api_key: ""                  # encrypted at rest

voice:
  stt_mode: "local"
  tts_mode: "edge"
  tts_voice: "en-US-GuyNeural"
  elevenlabs_key: ""
  cloned_voice_id: ""
  silence_threshold_ms: 1500

intelligence:
  shadow_learning: true
  screen_watching: true
  screen_watch_interval_sec: 8
  frustration_detection: true
  briefing_time: "08:30"
  briefing_enabled: true

integrations:
  smart_home:
    enabled: false
    ha_url: "http://homeassistant.local:8123"
    ha_token: ""
  calendar:
    provider: "google"
    credentials_path: ""
  email:
    provider: "gmail"
    email: ""
    password: ""                 # App password, encrypted
  weather:
    api_key: ""
    city: "London"
  finance:
    watchlist: ["AAPL", "GOOGL", "BTC-USD"]

privacy:
  audit_log_enabled: true
  audit_log_path: "~/Jarvis/audit_log.txt"
  privacy_hotkey: "ctrl+shift+p"

wellness:
  water_reminder_min: 45
  break_reminder_min: 90
  eye_reminder_min: 20
  enabled: true

remote_access:
  enabled: false
  port: 7777
  local_only: true               # NEVER expose to internet

ui:
  theme: "dark_glass"
  accent_color: "#00D4FF"
  always_on_top: true
  hud_opacity: 0.88
  orb_animations: true
  sound_effects: true

system:
  start_with_windows: true
  confirm_destructive: true
  max_history_turns: 20
```

---

## 9. MCU Jarvis vs This Project

| Jarvis in Iron Man | This Project |
|-------------------|--------------|
| "Good morning, Mr. Stark" | Morning briefing on login |
| Only Tony can activate it | Voice biometric authentication |
| Knows Tony's schedule | Calendar integration in briefing |
| Monitors the lab | Proactive screen watching |
| Controls lights and environment | Smart home integration |
| Manages multiple tasks simultaneously | Parallel agent executor |
| Works while Tony sleeps | Ghost mode overnight execution |
| Has personality and humor | Personality mode system |
| "All systems nominal" | Self-diagnostic mode |
| Warns about threats | Security monitor |
| Learns Tony's preferences | Shadow learner |
| Speaks and displays on HUD | TTS + animated orb HUD |
| Anticipates needs | Contextual awareness layer |
| Runs in Iron Man suit | Runs on your PC, phone-accessible |

---

## 10. Build Command

```bash
python -m nuitka \
  --standalone \
  --onefile \
  --windows-disable-console \
  --windows-icon-from-ico=ui/assets/jarvis.ico \
  --include-data-dir=config=config \
  --include-data-dir=ui/assets=ui/assets \
  --include-data-dir=plugins=plugins \
  --include-package=openwakeword \
  --include-package=faster_whisper \
  --include-package=resemblyzer \
  --include-package=PyQt6 \
  --include-package=playwright \
  --include-package=uvicorn \
  --output-filename=Jarvis.exe \
  main.py
```

Output: single Jarvis.exe, approximately 180MB.
No Python required on target machine.
Runs silently on Windows startup.

---

## 11. Development Phases

| Phase | What to Build | Time |
|-------|--------------|------|
| 1 | Config + logging + event bus | 1 day |
| 2 | Cloud AI + text HUD + 30 core tools | 2 days |
| 3 | Precision mouse/KB/screen engine | 3 days |
| 4 | Wake word + STT + TTS + voice auth | 2 days |
| 5 | Animated orb HUD | 2 days |
| 6 | Shadow learner + screen watcher + frustration | 3 days |
| 7 | Parallel agents + ghost mode | 2 days |
| 8 | Morning briefing + calendar/weather/email | 2 days |
| 9 | Plugin system | 2 days |
| 10 | Privacy mode + audit log + voice cloning | 1 day |
| 11 | Smart home + remote access + security monitor | 2 days |
| 12 | Packaging + startup + polish | 2 days |

Total: approximately 26 days for complete v1

---

*Architecture v2.0 — Python 3.11+ / Windows 10 and 11*
*All intelligence runs locally. Cloud AI is optional and swappable.*
