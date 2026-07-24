# 🌸 May — AI Desktop Companion

**May** is a full-featured desktop AI companion that runs locally on Windows, controls your PC via voice/text commands, and has long-term memory. 

> **Repository:** [LoneWolf0710/May_Pc_AI_Companion](https://github.com/LoneWolf0710/May_Pc_AI_Companion/tree/May) (`May` branch)

---

## ✨ Features

| Feature | Description |
|:---|:---|
| 🎤 **Voice Commands** | Click the mic, speak naturally — May transcribes and responds by voice |
| 💬 **Multi-Provider Chat** | Supports Ollama (local dual-port), OpenAI, Anthropic, Gemini, Google AI Studio, OpenRouter, and Ollama Cloud |
| 🖥️ **Full PC Control** | **467 actions** across 15 Control Core layers — apps, files, processes, windows, input, registry, services, system, browser, network, media, developer tools, cloud, automation, advanced |
| 🧩 **Fuzzy App Matching** | 6-strategy name resolution — handles typos, abbreviations, and partial names with confidence scoring |
| 🔍 **Everything Search** | 3-tier instant file search via [Everything by voidtools](https://www.voidtools.com/) — ctypes SDK DLL, HTTP API, or es.exe fallback |
| 🧠 **Long-Term Memory** | LanceDB vector store for semantic search + SQLite for structured facts + procedural skill memory |
| 🎨 **Animated Avatar** | SVG expressive face with 7 expressions, state machine, blinking, particles, mood wiring, Rive `.riv` ready |
| 🧬 **Endocrine System** | 6 hormones (cortisol, dopamine, serotonin, adrenaline, oxytocin, endorphin) with exponential decay — emotionally modulates risk assessment |
| 🎭 **Personality Modes** | 5 profiles (Shikimori/Formal/Debug/Silent/Playful) with runtime switching and system prompt injection |
| 🔒 **Immune System** | Adaptive action verification: risk tiers + behavioral profile + control modes + endocrine emotional context + OWASP |
| ⚡ **GPU Acceleration** | Auto-detects NVIDIA GPU for near-instant speech transcription via faster-whisper |
| 📖 **Screen Understanding** | Tier 2 UIAccessibility (zero-VRAM), Tier 4 vision model, conditioned reflexes, proactive suggestions |
| 🔐 **DPAPI Security** | Hardware-encrypted API keys, hash-chain audit log, 4-tier risk classifier |
| 🔔 **Toast Notifications** | Windows native notifications for reminders and alerts |
| 🎙️ **Meeting Mode** | WASAPI loopback capture → transcribe → LLM summary with action items |
| 👻 **Ghost Mode** | Autonomous task queue with priority ordering and idle detection |
| 🔌 **Plugin System** | BasePlugin + PluginManager with Spotify reference plugin |
| 🧠 **Skill Acquisition** | Learns procedures from demonstration, auto-creates skills after 3+ repetitions |
| 🌐 **Integrations** | Weather (Open-Meteo), news (RSS), calendar (ICS), smart home (Home Assistant), email (IMAP/SMTP) |
| 🚀 **Desktop App** | Built with Tauri v2 — lightweight, fast, native Windows feel, system tray, autostart |

---

## 🛠️ Tech Stack

| Layer | Technology |
|:---|:---|
| **Desktop Framework** | [Tauri v2](https://tauri.app/) (Rust + Web frontend) |
| **Frontend** | React 18 + TypeScript + Tailwind CSS + Framer Motion |
| **Backend** | Python FastAPI (sidecar process) — 159+ API endpoints |
| **LLM Runtime** | [Ollama](https://ollama.ai/) (dual-port: router on 11434 + main on 11435) + 6 online providers |
| **Speech-to-Text** | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (GPU auto-detect → CPU fallback) + Silero VAD |
| **Text-to-Speech** | Browser SpeechSynthesis API + barge-in detection |
| **Long-Term Memory** | [LanceDB](https://lancedb.com/) 0.33.0 (vectors) + SQLite (facts) + JSON skills |
| **Embeddings** | [all-MiniLM-L6-v2](https://www.sbert.net/) via sentence-transformers |
| **System Control** | 15-layer Control Core daemon (467 actions) with TCP bus, fallback chains, verifiers |
| **Security** | DPAPI encryption, SHA-256 hash-chain audit log, 4-tier risk classifier, OWASP mapping |
| **Intelligence** | Shadow learner, frustration detector, screen watcher, endocrine system, personality modes, conditioned reflexes |
| **File Search** | Everything by voidtools — 3-tier backend (ctypes SDK DLL / HTTP API / es.exe CLI), auto-detection |
| **App Matching** | 6-strategy fuzzy name resolution — exact, prefix, abbreviation, substring, Levenshtein, token overlap |

---

## 🚀 Getting Started

### Prerequisites

- **Windows 10/11**
- **Python 3.11+**
- **Node.js 18+**
- **Ollama** ([ollama.ai](https://ollama.ai/)) — for local LLM
- **ffmpeg** — for voice transcription (webm → wav conversion)
- **CUDA 12.x Toolkit** (optional) — for GPU-accelerated speech transcription

### Installation

```bash
# Clone the repo
git clone https://github.com/LoneWolf0710/May_Pc_AI_Companion.git -b May
cd May_Pc_AI_Companion

# Install frontend dependencies
npm install

# Install backend dependencies
cd backend
pip install -r requirements.txt
cd ..

# Pull the main Ollama model
ollama pull phi4-mini:3.8b
```

### Running May

You'll need 3 terminals:

```bash
# Terminal 1 — Backend (FastAPI server on port 8080)
cd backend
python main.py

# Terminal 2 — Frontend (Vite dev server on port 1420)
npm run dev

# Terminal 3 — Ollama (dual instances)
# Router on port 11434 (qwen3:0.6b) — intent classification
# Main on port 11435 (phi4-mini:3.8b) — complex reasoning
ollama serve
```

Then open the app and start chatting with May!

### Building for Production

```bash
# Build the Tauri desktop app
npm run tauri build
```

---

## 📁 Project Structure

```
May_Pc_AI_Companion/
├── src/                          # React frontend
│   ├── App.tsx                   # Main app — state, chat, voice, streaming, modals
│   ├── components/
│   │   ├── Avatar.tsx            # SVG expressive face + 7-expression state machine
│   │   ├── ChatPanel.tsx         # Chat bubbles + input + action buttons (🎙️👻📱🧬🌐🧠🎭)
│   │   ├── ModelSelector.tsx     # Multi-provider model dropdown with search
│   │   ├── SettingsModal.tsx     # API keys + STT model selector + personality
│   │   ├── StatusHUD.tsx         # Real-time clock, GPU/RAM bars, personality selector
│   │   ├── MoodTimeline.tsx      # Mood history chart/recent/stats tabs
│   │   ├── SkillsPanel.tsx       # Learned skills viewer/executor
│   │   ├── MorningBriefing.tsx   # Weather + news + calendar cards
│   │   ├── AutoTunerPanel.tsx    # 15 tunable gene cards + fitness chart
│   │   ├── InternetLearning.tsx  # Pending knowledge cards + approve/reject
│   │   ├── MeetingMode.tsx       # Record + transcribe + summarize
│   │   ├── GhostMode.tsx         # Autonomous task queue
│   │   ├── ProactiveSuggestions.tsx  # Floating notification cards
│   │   ├── RemoteControl.tsx     # LAN web UI + WebSocket chat
│   │   └── RiveAvatar.tsx        # Rive state machine wrapper (SVG fallback)
│   └── hooks/
│       ├── useMicMonitor.ts      # Browser mic capture
│       ├── useSpeechSynthesis.ts # Browser TTS
│       ├── useBargeIn.ts         # Stop TTS when user speaks
│       └── useWakeWord.ts        # Wake word audio pipeline
├── src-tauri/                    # Tauri Rust desktop shell
├── backend/                      # Python FastAPI server
│   ├── main.py                   # 159+ API endpoints, streaming chat, voice
│   ├── llm/
│   │   ├── ollama_client.py      # Dual-port Ollama + speculative_generate
│   │   ├── llama_server.py       # llama-server lifecycle manager
│   │   ├── providers.py          # 7 providers + persistent HTTP pools
│   │   ├── jarvis.py             # Personality + tool calling + agentic loop + parallel executor
│   │   ├── core_bridge.py        # jarvis → Control Core TCP daemon bridge
│   │   ├── resilience.py         # Auto-retry, fallback chains, health monitoring
│   │   ├── tools.py              # 178 tool JSON schemas
│   │   └── tool_tiering.py       # Intent-based tool filtering (20-40 relevant tools)
│   ├── intelligence/
│   │   ├── personality_modes.py  # 5 profiles, runtime switching, system prompt injection
│   │   ├── endocrine.py          # 6 hormones with exponential decay
│   │   ├── screen_watcher.py     # 8s loop, Tier 4 vision, proactive rules
│   │   ├── shadow_learner.py     # Pattern detection → skill auto-creation
│   │   ├── mood_history.py       # SQLite mood tracking
│   │   └── ...                   # 15+ intelligence modules
│   ├── memory/
│   │   ├── vector_store.py       # LanceDB semantic search
│   │   ├── fact_store.py         # SQLite structured facts
│   │   ├── skill_store.py        # Procedural memory (JSON)
│   │   └── memory_injector.py    # 8-source context injection
│   ├── system/
│   │   ├── secure_storage.py     # DPAPI encrypted API keys
│   │   ├── audit_log.py          # SHA-256 hash-chain + auto-rotation
│   │   ├── risk_classifier.py    # 4 risk tiers for ~150 tools
│   │   └── immune_system.py      # Risk + behavioral + OWASP + endocrine emotional context
│   ├── integrations/             # Weather, news, calendar, email, smart home
│   ├── plugins/                  # Plugin system + Spotify reference
│   ├── voice/                    # STT, TTS, VAD, biometrics, streaming
│   └── remote/                   # LAN web UI + WebSocket chat
├── core/                         # Control Core daemon — 15 layers, 467 actions
│   ├── bus.py                    # TCP CommandBus + crash recovery ring buffer
│   ├── daemon.py                 # Windows Service + debug mode
│   ├── layers/                   # L1-L15 (filesystem → advanced system)
│   │   ├── fuzzy_match.py        # 6-strategy fuzzy app name resolution
│   │   ├── everything_search.py  # 3-tier Everything search (SDK/HTTP/es.exe)
│   │   ├── L1_filesystem.py      # 35 file operations + Everything search
│   │   ├── L3_application.py     # 21 app operations + fuzzy matching + Everything
│   │   └── ...                   # L2-L15 layers (15 total, 467 actions)
│   └── engine/                   # Fallback chains, verifiers, transactions
├── tests/                        # Python test suite
│   ├── test_fuzzy_match.py       # 14 fuzzy matching tests
│   └── test_everything_search.py # 5 Everything integration tests
└── knowledge.md                  # Full project knowledge base
```

---

## 🎙️ Voice Commands

Click the **mic button** or press the voice toggle to speak to May. Examples:

- *"What time is it?"*
- *"Open Spotify"*
- *"Set volume to 50%"*
- *"Remind me in 30 minutes to take a break"*
- *"What's the weather in Tokyo?"*
- *"Take a screenshot and tell me what I'm looking at"*
- *"Open Notepad and type hello world"*
- *"What emails do I have?"*
- *"Give me my morning briefing"*

---

## 🖥️ PC Control Examples

May can control virtually anything on your PC via **467 actions across 15 layers**:

| Layer | Actions | Examples |
|:---|:---|:---|
| **L1: Filesystem** | 35 | Read, write, copy, move, delete files; list directories; search (Everything integration) |
| **L2: Process** | 24 | List processes, kill by name/PID, memory usage |
| **L3: Application** | 21 | Open apps (45+ known apps + **8-strategy launcher** with fuzzy matching + Everything), close apps |
| **L4: Window** | 32 | List windows, focus, minimize, maximize, resize, arrange |
| **L5: Input** | 25 | Type text, send keys, mouse click, scroll, clipboard |
| **L6: Registry** | 18 | Read/write/delete registry keys |
| **L7: Services** | 31 | Start/stop/restart services, Task Scheduler |
| **L8: System** | 49 | Volume, brightness, power, display, network info |
| **L9: Browser** | 34 | Playwright CDP automation, navigate, click, extract |
| **L10: Network** | 38 | WiFi profiles, firewall rules, DNS, proxy, traceroute |
| **L11: Media** | 32 | Per-app volume, audio endpoints, media playback |
| **L12: Developer** | 35 | Git, npm/pip/cargo, code analysis |
| **L13: Cloud** | 30 | HTTP client, webhooks, cloud storage, Discord/Slack |
| **L14: Automation** | 28 | Task scheduling, PowerShell/Python/Node execution |
| **L15: Advanced** | 35 | Power plans, hardware monitoring, optimization |

---

## 🧬 Endocrine System

May has an emotional hormone state that affects her behavior:

| Hormone | What It Tracks | Risk Impact |
|:---|:---|:---|
| **Cortisol** | Stress level | High (>0.6) → conservative mode, MODERATE+ actions require confirmation |
| **Adrenaline** | Alertness/urgency | High (>0.7) → caution for DESTRUCTIVE actions |
| **Serotonin** | Baseline well-being | Low (<0.3) + high cortisol → protective mode |
| **Dopamine** | Satisfaction/reward | High (>0.7) → flow state noted in context |
| **Oxytocin** | Social bonding | Tracks trust level |
| **Endorphin** | Pain/pleasure balance | Tracks flow state |

---

## 🔧 Configuration

### API Keys

Open **Settings** (gear icon) to add API keys for online providers:

- **OpenAI** — GPT-4o, GPT-4o-mini
- **Anthropic** — Claude 3.5 Sonnet, Claude 3 Haiku
- **Google Gemini** — Gemini 2.5 Pro/Flash, Gemini 2.0 Flash
- **Google AI Studio** — Free tier models
- **OpenRouter** — 100+ models (dynamically fetched free models)
- **Ollama Cloud** — Cloud-hosted models (dynamically fetched)

### Speech Recognition

In Settings → Speech Recognition, choose your preferred model:

- **auto** — Auto-detects GPU/CPU and picks the best model
- **large-v3-turbo** — Near-perfect accuracy (requires CUDA)
- **small** — Good accuracy, fast on CPU (~2s)
- **base** / **tiny** — Smaller models for slower machines

---

## 🎨 Theming

May uses the **Surfaced Dark** color palette:

| Element | Color |
|:---|:---|
| Background | `#0D0D0D` (Deep Charcoal) |
| Surface | `#1A1A1A` (Midnight Slate) |
| Accent | `#06B6D4` (Electric Cyan) |
| Text | `#E5E5E5` (Off-White) |

---

## 📝 License

This project is for personal use.

---

## 🙏 Acknowledgments

- [Tauri](https://tauri.app/) — Desktop framework
- [Ollama](https://ollama.ai/) — Local LLM runtime
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Speech transcription
- [LanceDB](https://lancedb.com/) — Vector database
- [Shikimori](https://myanimelist.net/anime/33504) — Personality inspiration

---

*Built with ❤️ by [LoneWolf0710](https://github.com/LoneWolf0710)*

## 🧩 Fuzzy App Matching

May can resolve typos, abbreviations, and partial app names:

| Input | Resolved To | Method |
|:---|:---|:---|
| `chrm` | `chrome` | Levenshtein distance (2 edits) |
| `vscode` | `visual studio code` | Token-initial subsequence |
| `fire` | `firefox` | Prefix match |
| `npp` | `notepad++` | Exact alias match |
| `spotfy` | `spotify` | Levenshtein distance (1 edit) |

**6 matching strategies** with configurable confidence threshold (default 0.60).

---

## 🔍 Everything Search Integration

May integrates with [Everything by voidtools](https://www.voidtools.com/) for instant file search:

| Backend | Speed | Method |
|:---|:---|:---|
| **ctypes SDK DLL** | ~0.1ms | Direct IPC via Everything64.dll (fastest) |
| **HTTP API** | ~1ms | JSON via httpx from Everything's built-in HTTP server |
| **es.exe CLI** | ~50ms | Subprocess call (fallback) |

**Auto-selects the best available backend.** Falls back gracefully when Everything isn't installed.

### Requirements
- [Everything by voidtools](https://www.voidtools.com/) (free, ~2MB)
- Everything must be running in the background
- es.exe in PATH or at a known location
- SDK DLL (Everything64.dll) for fastest backend

---

*Last updated: Session 47*
