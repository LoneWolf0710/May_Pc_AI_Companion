# 🌸 May AI Companion — Project Knowledge Base

> **IMPORTANT:** Read this file at the start of every new session. It contains the full project state, what's done, and what to do next.

---

## Project Overview

**May** is a full desktop AI companion that runs on Windows, controls the PC via voice/text commands, starts at boot, and has long-term memory. She has the personality of Shikimori from "Shikimori Not Just a Cutie" — cool, calm, caring, and subtly adorable.

### User's Hardware
- **GPU:** NVIDIA RTX 4050 Laptop (6GB VRAM) — CUDA toolkit NOT installed (cublas64_12.dll missing)
- **OS:** Windows (using Git Bash shell)
- **Current LLM:** phi4-mini:3.8b via Ollama (port 11435) + qwen3:0.6b router (port 11434)
- **Voice style:** Cool & calm (Shikimori-like)
- **Project path:** `C:\AI\may\`

### User Requirements
1. **Voice commands** — Talk to May, she replies by voice. Type to her, she replies by text.
2. **System control** — Open apps, volume, brightness, files, web search, weather, reminders
3. **Long-term memory** — Remembers everything from weeks ago (episodic + structured)
4. **Boot startup** — Runs on Windows startup, lives in system tray
5. **Fast responses** — < 2 second end-to-end (voice to voice)
6. **Animated avatar** — Responsive, expressive geometric sphere with state animations
7. **Shikimori personality** — Cool, calm, caring; uses "~" occasionally; proactive care
8. **Multi-provider models** — Support local Ollama + online API models (OpenAI, Anthropic, Gemini, OpenRouter, Ollama Cloud)

---

## Tech Stack

| Layer | Technology | Status |
|:---|:---|:---|
| **Desktop Framework** | Tauri v2 (Rust + Web frontend) | ✅ Configured |
| **Frontend** | React 18 + TypeScript + Tailwind CSS + Framer Motion | ✅ Working |
| **Avatar Animation** | SVG expressive face + state machine (7 expressions) + Framer Motion orbital rings + particles | ✅ ENHANCED |
| **Backend** | Python FastAPI (sidecar process) | ✅ Working |
| **LLM Runtime** | Ollama (phi4-mini:3.8b main + qwen3:0.6b router) + Multi-provider API support | ✅ FULLY IMPLEMENTED |
| **Multi-Provider LLM** | Ollama, OpenAI, Anthropic, Gemini, Google AI Studio, OpenRouter, Ollama Cloud | ✅ FULLY IMPLEMENTED |
| **API Key Management** | DPAPI-encrypted storage + legacy JSON fallback + Settings modal | ✅ FULLY IMPLEMENTED |
| **Speech-to-Text** | Server-side: faster-whisper (GPU auto-detect → CPU fallback) + STT model selector in Settings | ✅ FULLY IMPLEMENTED |
| **Text-to-Speech** | Browser SpeechSynthesis API | ✅ FULLY IMPLEMENTED |
| **Long-Term Memory** | LanceDB 0.33.0 (vector) + SQLite (structured) | ✅ FULLY IMPLEMENTED & TESTED |
| **Embeddings** | all-MiniLM-L6-v2 (sentence-transformers 5.5.1) | ✅ Integrated & Tested |
| **System Control** | pycaw, screen_brightness_control, subprocess, psutil | ✅ FULL PC CONTROL |
| **PC Control** | 60+ methods, LLM-powered PowerShell fallback, 7-strategy app launcher | ✅ FULLY IMPLEMENTED |
| **Toast Notifications** | winotify (Windows 10/11 native) | ✅ FULLY IMPLEMENTED |
| **Background Tasks** | asyncio reminder checker | ✅ FULLY IMPLEMENTED |
| **Tool Call Execution** | Text-based JSON parsing for prompt-based LLM fallback | ✅ FULLY IMPLEMENTED |
| **Intelligence Layer** | Shadow learner + frustration detector + screen watcher + mood history + Tier 4 vision | ✅ FULLY IMPLEMENTED & TESTED |
| **Wake Word Detection** | openwakeword-based, chunk API, cooldown, lazy model loading | ✅ IMPLEMENTED (needs tflite-runtime on Windows) |
| **Wake Word Audio Pipeline** | Browser PCM capture → base64 → /voice/wake-word/check, 80ms chunks, auto-resample | ✅ FULLY IMPLEMENTED |
| **Privacy Mode** | Pause all intelligence modules, SQLite audit logging, toggle/enable/disable | ✅ FULLY IMPLEMENTED & TESTED |
| **Control Core Daemon** | 15-layer daemon with TCP bus (:7650), 467 actions, 100% verifier coverage | ✅ FULLY IMPLEMENTED |
| **Jarvis Brain** | LLM tool routing (native + text-based fallback), personality system, tool definitions | ✅ FULLY IMPLEMENTED |
| **Natural Language Engine** | Enhanced system prompt (NL patterns, content generation, app sequences), pronoun resolution (15+ patterns with regex word boundaries), 50+ fast-path patterns with keyboard shortcuts (gated by word count), politeness stripping | ✅ FULLY IMPLEMENTED |
| **Reliable type_text** | Multi-strategy window focus (SetForegroundWindow + Alt key trick + BringWindowToTop), multi-strategy paste (Ctrl+V + Shift+Insert + PowerShell SendKeys), focus return tracking, error logging | ✅ FULLY IMPLEMENTED |
| **Weather Integration** | Open-Meteo API (free, no key), IP geolocation, 3-day forecast, WMO weather codes | ✅ FULLY IMPLEMENTED & TESTED |
| **News Integration** | RSS feed reader (feedparser), 4 categories, dedup, 10-min cache | ✅ FULLY IMPLEMENTED & TESTED |
| **Calendar Integration** | ICS file parser, auto-discovery, URL/file support | ✅ FULLY IMPLEMENTED & TESTED |
| **Smart Home Integration** | Home Assistant REST API client, device listing, toggle, config | ✅ IMPLEMENTED (needs HA setup) |
| **Morning Briefing (Backend)** | Aggregator: weather + news + calendar + reminders + smart home, 2.8s generation | ✅ FULLY IMPLEMENTED & TESTED |
| **Morning Briefing (Frontend)** | Weather cards, news cards, calendar, reminders, expand/collapse, quick actions | ✅ FULLY IMPLEMENTED |
| **Email Monitoring** | IMAP/SMTP client, Gmail/Outlook/Yahoo presets, unread/search/read/send | ✅ FULLY IMPLEMENTED |
| **Proactive Wellness** | 4 wellness rules, work session tracking, quiet hours, time-based suggestions | ✅ FULLY IMPLEMENTED |
| **Proactive Suggestions** | Screen watcher suggestions → floating UI cards with severity icons, dismiss/act actions | ✅ FULLY IMPLEMENTED |
| **Plugin System** | BasePlugin + PluginManager, runtime tool registration, Spotify reference plugin | ✅ FULLY IMPLEMENTED |
| **Tool Tiering** | Intent-based tool filtering (17 CORE + 16 domain tiers), keyword classification, plugin-safe | ✅ FULLY IMPLEMENTED & TESTED |
| **Dynamic Free Models** | OpenRouter free models fetched live from API at startup, 3-tier fallback (API → cache file → hardcoded), auto-refresh hourly | ✅ FULLY IMPLEMENTED |
| **Resilience Layer** | Auto-retry (exponential backoff), provider fallback chains, health monitoring (60s background loop), graceful degradation | ✅ FULLY IMPLEMENTED |
| **Explain My Screen** | On-demand screenshot → base64 → vision API (OpenAI/OpenRouter/Gemini) → natural language description | ✅ FULLY IMPLEMENTED |
| **Screen Watcher Tier 4** | Background vision analysis every 2min — screenshot → base64 → vision API → description + error detection | ✅ FULLY IMPLEMENTED |
| **Barge-in Detection** | Stops TTS when user speaks — amplitude analysis with consecutive frame debounce | ✅ FULLY IMPLEMENTED |
| **Mood History** | SQLite-backed mood tracking — tone analysis auto-recorded per chat, timeline/trend/stats APIs | ✅ FULLY IMPLEMENTED |
| **Proactive Suggestions** | Frontend floating notification cards — polls screen watcher suggestions, severity-coded, dismiss/act | ✅ FULLY IMPLEMENTED |
| **UWP App Closing** | PowerShell Stop-Process for Microsoft Store + other UWP apps with friendly name mapping | ✅ FULLY IMPLEMENTED |
| **System Process Protection** | _SYSTEM_PROTECTED_PROCESSES guard prevents close_app from killing explorer, svchost, csrss, etc. | ✅ FULLY IMPLEMENTED |
| **Ollama Cloud Dynamic Models** | Live model fetch from /api/tags at startup, 3-tier fallback (API → cache → hardcoded), auto-refresh | ✅ FULLY IMPLEMENTED |
| **DPAPI Encrypted Storage** | Hardware-backed API key encryption via Windows DPAPI, base64 fallback on non-Windows | ✅ FULLY IMPLEMENTED |
| **Hash-Chain Audit Log** | SHA-256 tamper-evident chain for all tool executions, verify_integrity(), JSONL format | ✅ FULLY IMPLEMENTED |
| **Audit Log Auto-Rotation** | Archives to .old when log exceeds 10MB, configurable threshold | ✅ FULLY IMPLEMENTED |
| **Action Risk Classifier** | SAFE/MODERATE/DESTRUCTIVE/CRITICAL tiers for ~150 tools, context-aware upgrades | ✅ FULLY IMPLEMENTED |
| **Tier 2: UIAccessibility** | Zero-VRAM Windows UIAutomation API — buttons, inputs, menus, error detection | ✅ FULLY IMPLEMENTED |
| **Conditioned Reflexes** | Embedding-based learned responses (sentence-transformers), learns from 3+ reps, <5ms | ✅ FULLY IMPLEMENTED |
| **Proper imagehash** | Perceptual hash (pHash) for screen change detection, fallback to basic PIL hash | ✅ FULLY IMPLEMENTED |
| **Tier 2 → MemoryInjector** | Structured screen data (elements, errors, modals) injected into every LLM prompt | ✅ FULLY IMPLEMENTED |
| **Reflex Fast-Path** | Learned reflexes checked between regex fast-path and LLM call in jarvis.py | ✅ FULLY IMPLEMENTED |
| **EasyOCR Fallback** | Lightweight OCR for apps without accessibility support (~500MB) | ✅ FULLY IMPLEMENTED |
| **Control Core Daemon** | 15-layer daemon with TCP bus (:7650), 467 actions, 100% verifier coverage | ✅ FULLY IMPLEMENTED |
| **Auto-Tuner** | 15 tunable genes, security exclusions, JSONL audit trail, rollback on >5% regression | ✅ FULLY IMPLEMENTED |
| **Auto-Tuner Gene Wiring** | All 15 genes wired into runtime via tuner_cache.py (30s TTL) | ✅ FULLY IMPLEMENTED |
| **Silero VAD** | Always-on voice activity detection — lazy-loaded Silero model (~2MB, <1ms inference), RMS fallback, hysteresis, session reset | ✅ FULLY IMPLEMENTED |
| **Internet Learning** | User-gated web knowledge acquisition, extract→approve→store pipeline | ✅ FULLY IMPLEMENTED |
| **Speculative Decoding** | Auto-selects true (llama-server batch verify) or approx (dual Ollama prefix) mode | ✅ FULLY IMPLEMENTED |
| **True Speculative Decoding** | llama-server with draft model: draft→batch verify→accept/reject (~25-40% speedup) | ✅ FULLY IMPLEMENTED |
| **Vitest Frontend Tests** | 33 tests (AutoTunerPanel 14 + InternetLearning 16 + 3 setup): Vitest + jsdom + @testing-library/react + jest-dom | ✅ FULLY IMPLEMENTED |
| **Rive Avatar Wrapper** | Smart wrapper checking for `/avatar.riv`, dynamic Rive runtime import, state machine mapping, SVG fallback | ✅ FULLY IMPLEMENTED |
| **Skill Acquisition** | shadow_learner → SkillStore auto-creation pipeline (3+ reps), jarvis_chat skill matching shortcut (confidence≥0.6), 4 skill tools, SkillsPanel UI | ✅ FULLY IMPLEMENTED |
| **Parallel Multi-Agent Executor** | asyncio.gather for independent tool calls in agentic loop, sequential tools run one-by-one | ✅ FULLY IMPLEMENTED |
| **Mood History Frontend** | MoodTimeline.tsx — 3-tab UI (chart/recent/stats), period selector, trend indicators, auto-refresh | ✅ FULLY IMPLEMENTED |
| **Personality Modes** | 5 profiles (Shikimori/Formal/Debug/Silent/Playful), runtime switching, system prompt injection, persistence | ✅ FULLY IMPLEMENTED |
| **Security Monitor** | USB device tracking (Get-CimInstance), microphone access detection, suspicious app monitoring, configurable | ✅ FULLY IMPLEMENTED |
| **Auto-generate tools.py** | Standalone script to extract tool definitions from layer ACTION_MAPs (single source of truth) | ✅ FULLY IMPLEMENTED |
| **Personality Quick-Selector** | StatusHUD dropdown with 🌸/💼/🐛/🤫/✨ icons, dynamic profiles from API, purple accent for non-default | ✅ FULLY IMPLEMENTED |
| **Llama-Server UI Config** | SettingsModal: target/draft model inputs, start/stop/config buttons, proper HTTP calls per action | ✅ FULLY IMPLEMENTED |
| **Expanded App Registry** | ~45 new apps: Adobe suite, game launchers (GOG/EA/Ubisoft/Battle.net/Riot), media (Blender/GIMP/Audacity), dev (Git/Docker/IntelliJ/PyCharm), productivity (OneDrive/Notion/Obsidian) | ✅ FULLY IMPLEMENTED |
| **Control Mode Eager Init** | control_modes initialized at module level — available immediately, not after background thread | ✅ FULLY IMPLEMENTED |
| **Daemon Crash Recovery** | Command history ring buffer (100 entries) in CommandBus, crash context logging on fatal errors, get_history/get_crash_context APIs, _total_failures counter in BusServer | ✅ FULLY IMPLEMENTED |
| **Continuous Conversation** | Auto-restart mic after May responds (backend STT path), persistent toggle with localStorage, 1.2s delay for TTS completion | ✅ FULLY IMPLEMENTED |
| **Code Assistant** | Syntax-highlighted code blocks in chat — placeholder-based tokenization prevents double-highlighting of keywords inside comments/strings. copy-to-clipboard, line numbers, traffic-light header, RenderedMessage markdown parser (inline code/bold/italic) | ✅ FULLY IMPLEMENTED |
| **Automated Workflows** | WorkflowEngine: CRUD, NL parsing (30+ keyword patterns), preview_steps + async LLM fallback, scheduled executor (30s background loop), chat-triggered workflows, trigger UI (manual/scheduled/chat). Persistence at ~/.may/workflows.json. 8 API endpoints. WorkflowsPanel with error toasts, trigger config, preview UI | ✅ FULLY IMPLEMENTED |
| **Fuzzy App Matching** | Pure Python fuzzy name resolution (6 strategies: exact, prefix, abbreviation, substring, Levenshtein, token overlap). Configurable threshold. Integrated into L3 launch chain + jarvis fast-path | ✅ FULLY IMPLEMENTED |
| **Everything Search** | 3-tier backend: ctypes SDK DLL (~0.1ms), HTTP API (~1ms), es.exe CLI (~50ms). Auto-detection, structured results with size/date/run-count. Integrated into L1 search + L3 app launch | ✅ FULLY IMPLEMENTED |

---

## Voice System — Architecture & Key Details

### How Voice Works (End-to-End Flow)
1. User clicks mic button → `handleVoiceToggle()` in App.tsx
2. `useBackendSTT` is always `true` (browser webkitSpeechRecognition doesn't work in Tauri WebView2)
3. `useMicMonitor` starts `getUserMedia` + `MediaRecorder` to capture audio in the browser
4. After 5 seconds, `getRecordedBlob()` stops the recorder and returns a webm Blob
5. Frontend sends the blob to `POST /voice/transcribe-audio` on the backend
6. Backend converts webm → wav via ffmpeg, transcribes with faster-whisper
7. Backend returns `{text, amplitude, language, duration}`
8. Frontend calls `handleSendMessageRef.current(text)` to send the transcript as a chat message
9. May responds via the selected LLM provider (Ollama, OpenAI, etc.)

### Key Files
| File | Purpose |
|:---|:---|
| `src/hooks/useMicMonitor.ts` | Browser mic capture via getUserMedia + MediaRecorder + amplitude visualization |
| `src/hooks/useSpeechRecognition.ts` | `useBackendSTT` flag (always true), browser STT fallback code (dead but kept) |
| `src/components/VoiceMonitor.tsx` | Floating side panel with frequency bars, amplitude meter, countdown timer, transcript |
| `src/App.tsx` | `handleVoiceToggle()` — orchestrates the full voice flow |
| `src/components/SettingsModal.tsx` | API key management + **STT model selector** (auto/GPU/CPU model buttons) |
| `backend/main.py` | `/voice/transcribe-audio` + `/voice/model` endpoints, provider routing, system commands |
| `backend/voice/stt.py` | `SpeechToText` class — faster-whisper with GPU auto-detection + CPU fallback + model switching |

### Dual Ollama Instance Routing
| Port | Model | Purpose |
|:---|:---|:---|
| 11434 | qwen3:0.6b | Router — intent classification, simple replies |
| 11435 | phi4-mini:3.8b | Main — complex reasoning, tool calling |

`get_ollama_url(model)` routes to the correct port based on model name.

---

## Color Palette (Surfaced Dark Theme)

| Role | Color | Hex |
|:---|:---|:---|
| Background | Deep Charcoal | `#0D0D0D` |
| Surface | Midnight Slate | `#1A1A1A` |
| Surface Elevated | Dark Zinc | `#252525` |
| Border | Subtle Line | `#2E2E2E` |
| Accent Primary | Electric Cyan | `#06B6D4` |
| Accent Secondary | Soft Purple | `#818cf8` |
| Success | Mint Green | `#34d399` |
| Warning | Amber | `#F59E0B` |
| Danger | Red | `#EF4444` |
| Text Primary | Off-White | `#E5E5E5` |
| Text Secondary | Warm Gray | `#A0A0A0` |
| Text Muted | Dark Gray | `#666666` |

---

## Project Structure (Key Files)

```
C:\AI\may\
├── knowledge.md              # THIS FILE — read first every session
├── package.json
├── vite.config.ts
├── src/
│   ├── App.tsx               # Main app — state, modals, 3-panel layout
│   ├── config.ts             # BACKEND_URL = "http://localhost:8080"
│   └── components/
│       ├── ChatPanel.tsx     # Chat + voice toggle + action buttons (🎙️👻📱🧬🌐🧠🎭⚡🔄)
│       ├── Avatar.tsx        # SVG expressive face + state machine
│       ├── MoodTimeline.tsx  # Mood history chart/recent/stats tabs
│       ├── SettingsModal.tsx # API keys + STT model selector
│       ├── SkillsPanel.tsx   # Learned skills viewer/executor
│       ├── CodeBlock.tsx     # Syntax-highlighted code blocks + RenderedMessage
│       └── WorkflowsPanel.tsx # Automated workflows CRUD + NL preview
├── backend/
│   ├── main.py               # FastAPI server (80+ endpoints)
│   ├── llm/
│   │   ├── ollama_client.py  # Dual-port Ollama + speculative_generate (true + approx)
│   │   ├── llama_server.py   # llama-server lifecycle manager (start/stop/health/config)
│   │   ├── providers.py      # 7 providers + persistent HTTP pools
│   │   ├── jarvis.py         # Personality + LLM tool calling + agentic loop + parallel executor
│   │   ├── core_bridge.py    # jarvis → Control Core TCP daemon bridge
│   │   ├── resilience.py     # Auto-retry, fallback chains, health monitoring
│   │   ├── tools.py          # 178 tool JSON schemas
│   │   └── tool_tiering.py   # Intent-based tool filtering (20-40 relevant tools)
│   ├── intelligence/
│   │   ├── personality_modes.py  # 5 profiles, runtime switching, system prompt injection
│   │   ├── security_monitor.py   # USB/microphone/app monitoring, configurable
│   │   ├── shadow_learner.py     # Pattern detection → skill auto-creation
│   │   ├── screen_watcher.py     # 8s loop, Tier 4 vision, proactive rules
│   │   ├── mood_history.py       # SQLite mood tracking, timeline/trend/stats
│   │   ├── endocrine.py          # 6 hormones with exponential decay
│   │   ├── sleep_cycle.py        # 5-state idle consolidation
││       ├── workflows.py          # NL parsing (30+ patterns), scheduled executor, async LLM fallback, CRUD, preview_steps
│   │   └── ...                   # 15+ more intelligence modules
│   ├── memory/
│   │   ├── vector_store.py   # LanceDB + sentence-transformers
│   │   ├── fact_store.py     # SQLite CRUD + reminders
│   │   ├── skill_store.py    # Procedural memory (JSON-based)
│   │   └── memory_injector.py # 8-source context injection
│   ├── system/
│   │   ├── secure_storage.py # DPAPI encrypted API keys
│   │   ├── audit_log.py      # SHA-256 hash-chain + auto-rotation (>10MB)
│   │   ├── risk_classifier.py # 4 risk tiers for ~150 tools
│   │   └── immune_system.py  # Risk + behavioral + OWASP + endocrine emotional context
│   └── voice/
│       ├── stt.py            # faster-whisper with GPU auto-detection
│       ├── vad.py            # Silero VAD (<1ms inference)
│       └── streaming_stt.py  # 100ms chunk processing
├── core/                         # Control Core daemon — 15 layers, 467 actions
│   ├── bus.py                    # TCP CommandBus + crash recovery ring buffer
│   ├── daemon.py                 # Windows Service + debug mode
│   ├── layers/                   # L1-L15 (filesystem → advanced system)
│   │   ├── fuzzy_match.py        # 6-strategy fuzzy app name resolution (~380 lines)
│   │   ├── everything_search.py  # 3-tier Everything search (SDK/HTTP/es.exe, ~400 lines)
│   │   ├── L1_filesystem.py      # 35 file operations + Everything search integration
│   │   ├── L3_application.py     # 21 app operations + fuzzy matching + Everything
│   │   └── ...                   # L2-L15 layers (15 total, 467 actions)
│   └── engine/                   # Fallback chains, verifiers, transactions
├── tests/                        # Python test suite
│   ├── test_fuzzy_match.py       # 14 fuzzy matching tests
│   └── test_everything_search.py # 5 Everything integration tests
└── tools/
    └── generate_tools.py         # Auto-generate tools.py from layer ACTION_MAPs
```

---

## Session History

### Session 1-9: Foundation
Project setup, core LLM chat, voice system, avatar, multi-provider models, system control, memory, voice transcription, PC control.

### Session 10-13: Control Core + Intelligence
Tool execution overhaul, Control Core 15-layer architecture, intelligence layer (shadow learner, frustration detector, screen watcher), wake word, privacy mode.

### Session 14-18: Integrations + Plugins
Morning briefing, weather/news/calendar/smart home, email monitoring, proactive wellness, plugin system, meeting mode, ghost mode.

### Session 20-21: Avatar + Voice Biometrics + Remote Control
SVG expressive face, voice biometrics (resemblyzer), LAN remote control with WebSocket chat + PIN auth.

### Session 22-26: Testing + Bug Fixes
E2E testing, tool tiering (90% token reduction), dynamic OpenRouter free models, resilience layer (retry/fallback/health), PC control bug fixes.

### Session 28-31: Vision + Cloud + Gemini
Explain my screen, Tier 4 vision, Ollama Cloud dynamic models, Gemini native function calling, token optimization (fast-path), unit tests.

### Session 32: Week 3 Features
Barge-in detection, mood history tracking, vision Tier 4 integration, proactive suggestions frontend.

### Session 33: P2 Security
DPAPI encrypted storage, hash-chain audit log, action risk classifier (4 tiers), immune system, OWASP mapping, 6 security endpoints.

### Session 36: P4 See the Screen
Tier 2 UIAccessibility, imagehash perceptual hash, conditioned reflexes, reflex fast-path, screen data injection into LLM prompts, EasyOCR fallback.

### Session 37-38: P4 Completion + P5 Implementation
Auto-tuner (15 genes wired), internet learning, L10-L15 control layers (467 actions total), speculative decoding (approx), auto-tuner frontend panel, internet learning frontend, Silero VAD, gene wiring, Vitest tests.

### Session 39: P5 Rive Avatar + Skills
RiveAvatar wrapper (SVG fallback), SkillsPanel frontend, shadow_learner → skill store pipeline, 4 skill tools, Rive runtime integration.

### Session 40: P6 — Personality, Security Monitor, Parallel Executor, Audit Rotation
- ✅ **Personality Modes** (`backend/intelligence/personality_modes.py`) — 5 built-in profiles (Shikimori/Formal/Debug/Silent/Playful), runtime switching via `POST /personality/set`, system prompt injection into jarvis.py `_build_dynamic_prompt()`, custom profile creation, audit log, persistence at `~/.may/personality.json`. Wired into jarvis.py via `set_personality_modes()`.
- ✅ **Security Monitor** (`backend/intelligence/security_monitor.py`) — USB device tracking (WMI), microphone access detection, suspicious app monitoring, configurable poll interval, alerts with severity levels, acknowledge/dismiss. Starts only when at least one monitoring category is enabled. API: `/security-monitor`, `/security-monitor/alerts`, `/security-monitor/acknowledge`, `/security-monitor/config`.
- ✅ **Parallel Multi-Agent Executor** (`backend/llm/jarvis.py`) — `_classify_tool()` separates tools into `_SEQUENTIAL_TOOLS` (type_text, open_app, close_app, write_file, etc.) and parallel batch. Independent tools (get_time, screenshot, list_processes) run via `asyncio.gather()`. Sequential tools run one-by-one with dedup, window targeting, and delay-after-open logic.
- ✅ **Mood History Frontend** (`src/components/MoodTimeline.tsx`) — 3-tab UI (chart/recent/stats), 4 period buttons (1h/6h/24h/7d), mood distribution visualization, trend indicator (↑ Improving / → Stable / ↓ Declining), mood emojis + color coding, auto-refresh every 15s. Uses `BACKEND_URL` for all API calls.
- ✅ **Audit Log Auto-Rotation** (`backend/system/audit_log.py`) — Checks file size on every `log_action()` call. When `~/.may/audit_log.jsonl` exceeds 10MB, archives to `audit_log.jsonl.old` and starts fresh. Configurable via `_ROTATION_MAX_SIZE_MB`.
- ✅ **Auto-generate tools.py** (`tools/generate_tools.py`) — Standalone script that reads all 15 layer files, extracts ACTION_MAPs, generates tool JSON schemas matching the format in `tools.py`. Fallback dictionary for common tools without action map entries.
- ✅ **Wiring** — Personality modes wired into `main.py` (endpoints + startup + jarvis.py setter). Security monitor started in lifespan. MoodTimeline added as 🎭 button in ChatPanel + modal overlay in App.tsx. Python AST 6/6 pass, TypeScript clean.

### Session 41: True Speculative Decoding via llama-server (P5 completion)
- ✅ **llama-server Lifecycle Manager** (`backend/llm/llama_server.py`) — Full process management: start/stop/health check. Resolves GGUF model paths from: absolute path, relative path, or Ollama model name (traverses Ollama manifest → blob hash → GGUF file). Finds llama-server executable via `MAY_LLAMA_SERVER_PATH` env var, PATH, or common Windows install locations. Config persistence at `~/.may/llama_server.json`. Runs on port 8081 (avoids conflict with FastAPI on 8080). Builds command with `-m target.gguf -md draft.gguf --spec-type draft-simple --draft-n-max N`.
- ✅ **Auto-Mode Selection** (`backend/llm/ollama_client.py`) — `speculative_generate()` now auto-selects at runtime: if llama-server is running → true batch-verified speculative decoding (25-40% speedup); otherwise → software approximation prefix mode (10-20% speedup). Two internal functions: `_speculative_generate_true()` (calls llama-server's `/v1/chat/completions` OpenAI-compatible endpoint) and `_speculative_generate_approx()` (draft prefix → main continuation via dual Ollama).
- ✅ **API Endpoints** (`backend/main.py`) — 5 new endpoints: `GET /llama-server` (status), `GET /llama-server/health` (live check), `POST /llama-server/config` (update settings), `POST /llama-server/start` (launch with optional model overrides), `POST /llama-server/stop` (graceful shutdown). Uses `LlamaServerConfigRequest` Pydantic model for optional field updates.
- ✅ **Validation** — Python AST 3/3 pass (llama_server.py, ollama_client.py, main.py). Code review approved.

### Session 44: Bug Fixes + Live E2E Verification + Model Auto-Discovery
- ✅ **Endocrine → ImmuneSystem Integration** (`backend/system/immune_system.py`) — Wired `endocrine_system` into `verify_action()` with 4 hormone-based risk rules: (1) High cortisol >0.6 → conservative mode, MODERATE+ actions require confirmation; (2) Low serotonin <0.3 + high cortisol >0.5 → protective mode, DESTRUCTIVE always requires confirmation even in automation; (3) High adrenaline >0.7 → user may be rushing, DESTRUCTIVE requires confirmation; (4) High dopamine >0.7 → flow state noted in `Verification.emotional_context` for downstream use. Removed dead code (`set_endocrine_system` was stored but unused). Step 6 in verify_action() applies emotional context after behavioral check but before final allow.
- ✅ **Live E2E Test Results** — Backend (`python main.py`) starts cleanly on port 8080, all 159 endpoints registered. Frontend (`npm run dev`) compiles in 772ms with 0 errors on port 1420. All key endpoints verified live: `/health`, `/models`, `/models/ollama`, `/personality`, `/modes`. Chat tested with `phi4-mini:3.8b` — streaming response confirmed.
- ✅ **Model Auto-Discovery Verified** — Backend fetches Ollama models from both ports (11434 router + 11435 main) via `refresh_ollama_local_models()` at startup. Discovered 6 models (may-main, may-router, qwen3:0.6b, phi4-mini:3.8b, qwen3:4b, gemma2:2b). `get_all_key_status()` correctly returns `available: true` for Ollama (`requires_key: false`). Frontend polls `GET /models` every 30s and displays all models in ModelSelector grouped by provider.
- ✅ **Validation** — Python AST 62/62 pass, TypeScript clean 0 errors, ImmuneSystem method verified working.

### Session 43: Control Mode Wiring + App Registry + Daemon Crash Recovery
- ✅ **Control Mode Eager Init** (`backend/main.py`) — `control_modes` initialized at module level (`_ControlModesEager()`) so jarvis.py can read actual mode immediately. Removed redundant instantiation from `_load_intelligence()`. Fixed SyntaxError from redundant `global` declarations.
- ✅ **Expanded App Registry** (`core/layers/L3_application.py`) — ~45 new apps: Gaming (GOG, EA, Ubisoft, Battle.net, Riot, Roblox, Minecraft, GeForce NOW), Adobe (Photoshop, Illustrator, Premiere Pro, After Effects, Lightroom, Acrobat, XD, InDesign), Media (Audacity, Blender, GIMP, HandBrake, foobar2000, AIMP), Productivity (PowerPoint, Outlook, OneNote, Google Drive, Dropbox, OneDrive, Notion, Todoist, Obsidian, Logseq), Dev (Git, GitHub Desktop, GitKraken, Sublime Text, IntelliJ IDEA, PyCharm, WebStorm, Android Studio, Docker, npm, node, python, pip). Fixed git path (bin→cmd), removed duplicate keys, fixed geforce now typo.
- ✅ **Daemon Crash Recovery** (`core/bus.py`) — Command history ring buffer (collections.deque, max 100) recording every dispatch with timestamp/layer/action/params/success/error/method/timing. Crash context tracking (last_command updated before each dispatch). `get_history(limit)` and `get_crash_context()` methods for post-mortem diagnosis. `BusServer._serve_with_guard()` now logs crash context (last command, recent failures, registered layers) on fatal crash. `_total_failures` counter in BusServer.
- ✅ **Validation** — Python AST 62/62 pass, TypeScript clean 0 errors, code review approved.

### Session 45: P6/P7 — Continuous Conversation, Code Assistant, Automated Workflows
- ✅ **Continuous Conversation** (`src/App.tsx`) — `continuousMode` state with localStorage persistence. Auto-restart useEffect: when mayState=idle, continuousMode=true, useBackendSTT=true → 1.2s delay → trigger voice toggle. Toggle handler flips mode + saves to localStorage. Voice toggle disables continuous mode when manually stopped. 🔄 toggle button in ChatPanel with active styling (cyan glow).
- ✅ **Code Assistant — Syntax-Highlighted Chat** (`src/components/CodeBlock.tsx`) — `CodeBlock` component: syntax highlighting (keywords purple, strings green, numbers orange, comments gray, functions blue, decorators pink), line numbers, copy-to-clipboard with ✓ feedback, traffic-light header. `RenderedMessage` component: splits content on ``` fenced code blocks, renders CodeBlock for code, inline markdown (backticks/bold/italic) for text. Integrated into ChatPanel via `RenderedMessage` replacing raw text. CSS in `globals.css` (.code-keyword, .code-string, .code-number, .code-comment, .code-function, .code-builtin, .code-decorator).
- ✅ **Automated Workflows — Backend** (`backend/intelligence/workflows.py`) — `WorkflowEngine`: CRUD (create/get/list/delete/toggle), persistence at `~/.may/workflows.json`, singleton pattern. `parse_description()`: NL parser with 30+ keyword patterns. `preview_steps()` + `preview_steps_async()` with LLM fallback. Scheduled executor (30s background loop). Chat-triggered workflow matching. `_parse_percent()` helper. `_match_segment_to_step()`: regex matcher with optional capture. Updated `create()` to accept `description_input` and auto-parse into steps.
- ✅ **Automated Workflows — API** (`backend/main.py`) — 8 endpoints: `GET /workflows`, `GET /workflows/stats`, `POST /workflows`, `POST /workflows/{id}/run`, `POST /workflows/{id}/toggle`, `DELETE /workflows/{id}`, `GET /workflows/{id}`, `POST /workflows/preview`. Workflow engine wired in `_load_intelligence()` via `set_executor(execute_tool)` + `set_chat_fn(_jarvis_chat_fn)`. Schedule loop started in lifespan. Chat-triggered workflows checked in `/chat` endpoint. Shutdown handler stops schedule loop.
- ✅ **Automated Workflows — Frontend** (`src/components/WorkflowsPanel.tsx`) — Full CRUD panel: workflow list with status dots, step preview on expand, run/toggle/delete buttons, stats bar, create form with name input + description textarea + trigger selector (manual/scheduled/chat) + config inputs + Preview Steps button + Create button. Error toasts for all async operations. Preview shows parsed tool_name + description list before creation.
- ✅ **Validation** — Python AST 72/72 pass, TypeScript 0 errors, Vitest 33/33 pass, code review approved.

### Session 42: P6 UI Polish + wmic Fix
- ✅ **Personality Quick-Selector** (`src/components/StatusHUD.tsx`) — New dropdown selector in the status bar next to the control mode button. Shows current personality emoji + name (🌸 Shikimori / 💼 Formal / 🐛 Debug / 🤫 Silent / ✨ Playful). Hover dropdown for quick switching. Purple accent color when non-default mode is active. Dynamically built from API `available_profiles` (not hardcoded). Fallback emoji for custom profiles.
- ✅ **Personality State Wiring** (`src/App.tsx`) — `personalityMode` state polls `/personality` every 15s, `personalityProfiles` state holds available profiles from API (with hardcoded defaults as initial fallback). `handleSetPersonality` POSTs to `/personality/set`. Props wired to StatusHUD.
- ✅ **SettingsModal Personality Section** (`src/components/SettingsModal.tsx`) — Personality Modes section with profile selector buttons (same dynamic profiles from API). Purple accent styling for active profile.
- ✅ **SettingsModal Llama-Server Fix** (`src/components/SettingsModal.tsx`) — Replaced stub `handleLlamaServerAction` with proper per-action HTTP calls: `POST /llama-server/start` (with optional target/draft model config body), `POST /llama-server/stop`, `POST /llama-server/config`. Added editable target/draft model path input fields with placeholders from server config. Added "save config" button when server is running.
- ✅ **wmic Deprecation Fix** (`backend/intelligence/security_monitor.py`) — Replaced deprecated `wmic path Win32_USBControllerDevice get` with PowerShell `Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPClass -eq 'USB' } | Select-Object DeviceID, Name | ConvertTo-Json`. JSON-based parsing instead of line-based. Ensures USB device tracking works on Windows 11 where wmic is removed.
- ✅ **Validation** — Python AST clean, TypeScript compiles 0 errors, code review approved.

---

### Session 47: Fuzzy App Matching + Everything Search Integration
- ✅ **Fuzzy App Matching** (`core/layers/fuzzy_match.py`, ~380 lines) — Pure Python fuzzy app name resolution with 6 matching strategies:
  - Exact match (normalization-aware)
  - Prefix matching (notep→notepad, 0.70-0.95 confidence)
  - Abbreviation matching (vscode→visual studio code via token-initial subsequence, chrm→chrome via consonant skeleton)
  - Substring containment (fire→firefox)
  - Levenshtein edit distance (chrme→chrome, 1 edit)
  - Token overlap (google browser→google chrome)
  - `fuzzy_resolve()` returns ranked list, `fuzzy_best()` returns top-1
  - Configurable threshold (default 0.60)
  - Integrated as Strategy 3 in L3_application.py 8-strategy launch chain
  - Integrated into jarvis.py fast-path for multi-word app names
- ✅ **Everything Search Integration** (`core/layers/everything_search.py`, ~400 lines) — 3-tier backend:
  - **ctypes SDK DLL** (fastest, ~0.1ms) — Direct IPC via Everything64.dll, structured results with size/date/run-count
  - **HTTP API** (fast, ~1ms) — JSON via httpx from Everything's built-in HTTP server
  - **es.exe CLI** (fallback, ~50ms) — subprocess call
  - Auto-detection via registry, common paths, PATH, and module directory
  - `everything_search()`, `everything_search_paths()`, `everything_find_app()` APIs
  - EverythingRequest/EverythingSort IntFlag enums from SDK header
  - Integrated as Strategy 1 in L1_filesystem.py search_files
  - Integrated as Strategy 8 in L3_application.py app launch chain
  - Everything is installed and es.exe backend is active on this system
- ✅ **Tests** — 19 Python tests (14 fuzzy + 5 Everything), all passing. Vitest 33/33. AST validation clean.
- ✅ **Validation** — Python AST clean, code review approved.

### Session 48: Phase 8 — L10-L15 Domain-Specific Verifiers
- ✅ **L10-L15 Domain Verifiers** (`core/engine/verifier.py`) — Replaced ~150 generic `result_has_key` entries with ~30 domain-specific verifier methods across 6 layers:
  - **L10 Network** (38 actions): `network_interfaces_result`, `network_stats_result`, `connections_result`, `listening_ports_result`, `established_result`, `dns_result`, `proxy_result`, `wifi_profiles_result`, `wifi_status_result`, `firewall_status_result`, `firewall_rule_result`, `traceroute_result`, `whois_result`, `ping_result`, `arp_result`, `route_result`, `public_ip_ext_result`
  - **L11 Media** (32 actions): `audio_sessions_listed`, `active_audio_result`, `audio_device_muted`, `media_info_result`, `media_files_listed`, `disc_info_result`, `optical_drives_listed`, `media_status_result`
  - **L12 Developer** (35 actions): `git_command_result`, `package_command_result`, `file_stats_result`, `port_check_result`, `terminal_command_result`
  - **L13 Cloud** (30 actions): `http_response_result`, `api_test_result`, `webhook_result`, `health_check_result`, `ssl_cert_result`, `notification_result`, `cloud_files_result`
  - **L14 Automation** (28 actions): `script_execution_result`, `workflow_result`, `scheduled_task_result`
  - **L15 Advanced** (35 actions): `power_plan_result`, `cpu_info_result`, `gpu_info_result`, `ram_info_result`, `disk_info_result`, `battery_info_result`, `temperature_result`, `hardware_summary_result`, `system_optimization_result`, `uptime_result`, `process_summary_result`, `system_events_result`, `path_entries_result`, `performance_counter_result`
  - Semantic fixes: `open_terminal` → `result_no_error`, `syntax_check/lint_file/format_file` → `terminal_command_result`, `stop_script/simulate_mouse` → `result_no_error`, `disable/enable_startup_programs` → `result_no_error`
- ✅ **Validation** — Python AST clean (verifier.py + all 15 layer files), control engine tests 10/10 pass.
- ✅ **Code Review** — Approved with semantic fixes applied.

### Session 49: Natural Language Handling + In-App Controls Perfected
- ✅ **Enhanced System Prompt** (`backend/llm/jarvis.py`) — Expanded from ~800 tokens to ~1200 tokens with:
  - **NL Understanding section**: Users speak naturally — parse intent, not exact words. Added 10+ phrasings for common commands.
  - **Content Generation templates**: Lists, emails, code, notes, pros/cons, summaries. Auto-detects content type and routes to type_text (<200 chars) or write_file (>200 chars).
  - **App-Specific Sequences**: After opening Notepad → save=Ctrl+S, after browser → search=web_search, after any app → close=close_app.
  - **Quick Commands reference**: time/date/battery/screenshot, volume/brightness, open/close, lock/sleep/shutdown.
  - **Multi-step examples**: "open chrome, search for cats, then screenshot" → 3 tools in ONE response.
- ✅ **Improved Pronoun Resolution** (`backend/llm/jarvis.py`) — Expanded from 3 patterns to 15+ with regex word boundaries:
  - **App references**: "in it/there/that", "close it/that/this", "open it/that/this", "restart it/that", "maximize/minimize it/that/this"
  - **File references**: "save it/that/this", "open it/that/this" (when no app open)
  - **Search references**: "search that", "search for that", "look that up", "look it up"
  - **Natural speech**: "turn it on/off" → open/close app
  - **Word boundary regex** (`\b`) prevents false positives like "unit" matching "in it"
- ✅ **Expanded Fast-Path Patterns** (`backend/llm/jarvis.py`) — From ~30 to 50+ patterns:
  - **Politeness stripping**: "please ", "can you ", "could you ", "would you ", "hey may, " → stripped before matching
  - **Natural phrasing**: "crank the volume", "make it louder", "it's too bright", "got the time", "am i online"
  - **Keyboard shortcuts** (gated by `_word_count <= 5` to prevent false positives): undo, redo, select all, copy, paste, cut, save, new file, find, print, refresh, new tab, close tab, alt-tab, alt-f4, show desktop
  - **App aliases**: file explorer, open files → explorer
  - **Brightness set**: "brightness to 80" → set_brightness(level=80)
- ✅ **Smart _update_pronoun_state** (`backend/llm/jarvis.py`) — Tracks more tool types:
  - open_app, launch_with_args, launch_as_admin → set _last_opened_app
  - close_app, force_close_app → clear _last_opened_app
  - write_file → set _last_created_file
  - web_search → set _last_searched_query
  - type_text with window_title → update _last_opened_app (only when differs)
- ✅ **Tool Name Fixes** — `mute`/`unmute` (not `set_mute`), `lock_pc`, `system_info`, `send_keys` for keyboard shortcuts
- ✅ **Empty Message Guard** — Returns None after politeness stripping if message is empty
- ✅ **Validation** — Python AST OK, 51/51 tests pass (compound, smart routing, fast path), code review approved

---

## What Needs to Be Done Next

### Phase 9 Remaining
- **Rive Animated Avatar** — Create full animated avatar in Rive Editor (312-byte stub exists, SVG fallback active)
- **Windows 11 SDK** — Install via Visual Studio Installer to enable `cargo check` and Tauri EXE build
- **Git commit all changes** — 100+ untracked files need staging and committing
- **type_text reliability** — Improve window focus for apps other than Notepad (Steam, Discord, Opera)
- **More fast-path patterns** — Add patterns for specific apps user uses frequently

### Future
- **Conditional triggers** — "when I open Chrome..." event-based triggers via screen watcher integration
- **Everything SDK DLL activation** — Copy Everything64.dll to project dir to enable fastest backend (currently es.exe active)
- **Voice-triggered NL** — Natural language via voice with better punctuation handling

---

## Key Design Decisions

1. **Local-first, cloud-optional** — Local Ollama as default, online providers available via API keys
2. **Tauri over Electron** — Smaller footprint (critical since LLMs eat RAM)
3. **Python sidecar** — FastAPI backend for AI/ML ecosystem access
4. **Streaming everything** — LLM tokens stream to TTS for fast response (< 2s target)
5. **Hybrid memory** — LanceDB for semantic search, SQLite for exact facts
6. **Dual Ollama ports** — Router (11434) for simple tasks, Main (11435) for complex reasoning
7. **Tool tiering** — Send ~20-40 relevant tools per request instead of all 178
8. **Speculative decoding auto-mode** — True (llama-server) or approx (dual Ollama prefix) based on availability
9. **Agentic loop parallelization** — Independent tools via asyncio.gather, sequential tools one-by-one
10. **Personality prompt injection** — Profile suffix prepended to dynamic system prompt
11. **Security monitor lazy start** — Only runs background loop when monitoring is enabled
12. **Audit log rotation** — Archives at 10MB to prevent unbounded growth
13. **GGUF model resolution** — Resolves Ollama model names to GGUF blob paths via manifest traversal
14. **Fuzzy app matching** — 6-strategy resolution chain handles typos, abbreviations, and partial names
15. **Everything search 3-tier** — SDK DLL → HTTP API → es.exe fallback for instant file search

---

## Known Issues

1. **Windows SDK missing** — `cargo check` fails. Need Windows 11 SDK via Visual Studio Installer.
2. **Tauri Rust build fails** — Needs Windows 11 SDK.
3. **CUDA toolkit missing** — cublas64_12.dll not found. Install CUDA 12.x for GPU acceleration.
4. **tflite-runtime not on Windows** — Wake word detection needs this dependency.
5. **llama-server requires GGUF files** — User must download GGUF models separately (not Ollama format).
6. **type_text window focus is fragile** — Finds most recently started window, not necessarily the target.
7. **Everything SDK DLL not in project dir** — Only es.exe backend active; copy Everything64.dll to enable fastest backend.

---

## Startup Commands

```bash
# Terminal 1 — Python backend
cd C:\AI\may\backend
python main.py
# Starts FastAPI on http://localhost:8080

# Terminal 2 — Frontend dev server
cd C:\AI\may
npm run dev
# Starts Vite on http://localhost:1420

# Terminal 3 — Ollama (should already be running)
ollama serve
# Router on :11434 (qwen3:0.6b), Main on :11435 (phi4-mini:3.8b)

# Optional — llama-server for true speculative decoding
# Download from https://github.com/ggml-org/llama.cpp/releases
# Start via POST /llama-server/start or manually:
llama-server -m phi4-mini.gguf -md qwen3-0.6b.gguf --port 8081 --spec-type draft-simple

# Optional — Everything by voidtools for instant file search
# Download from https://www.voidtools.com/
# Requires es.exe in PATH or Everything64.dll in project dir
```

---

## Architecture Documents

| Document | Purpose |
|:---|:---|
| `knowledge.md` | THIS FILE — project state, what's done, what to do next |
| `MAY_V3_ARCHITECTURE.md` | Unified architecture — best of May + JARVIS V2 (21 new features) |
| `MAY_FINAL_ARCHITECTURE.md` | Definitive architecture spec (12-week plan, 7 brain regions, 3-tier reflexes) |
| `FINAL_DESIGN.md` | UI design spec (Warm Dusk palette, 3-panel layout, 6-layer orb) |
| `STEP_BY_STEP.md` | Implementation roadmap tracker (P1-P5 phases) |
| `JARVIS_V2_ARCHITECTURE.md` | Original JARVIS V2 spec — intelligence features, privacy, integrations |
| `JARVIS_CONTROL_CORE_ARCHITECTURE.md` | Control Core spec — 15-layer daemon, bus, router, fallback chains |

---

*Last updated: Session 51 — L17 Content Tools + L12/L14 additions + L16 E2E fix. L17: 14 new tools (calculate, unit_convert, timer, cancel_timer, speed_test, hash_string, base64_encode/decode, create_qr_code, json_format, csv_to_json, json_to_csv, compare_images). L12: git_clone, run_code, docker_list/start/stop, database_query, port_scan. L14: startup programs, clipboard_history, airplane/bluetooth toggle, set_wallpaper, recent_files, restore_point, user_accounts. L16: time.sleep→asyncio.sleep, set_ui_value→type_into_ui_element fallback. Total: 230+ tools, 17 layers, 9/9 files AST OK, code review approved.*
