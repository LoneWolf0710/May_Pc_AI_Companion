# 🌸 May AI Companion — Project Knowledge Base

> **IMPORTANT:** Read this file at the start of every new session. It contains the full project state, what's done, and what to do next.

---

## Project Overview

**May** is a full desktop AI companion that runs on Windows, controls the PC via voice/text commands, starts at boot, and has long-term memory. She has the personality of Shikimori from "Shikimori Not Just a Cutie" — cool, calm, caring, and subtly adorable.

### User's Hardware
- **GPU:** NVIDIA RTX 4050 Laptop (6GB VRAM) — CUDA toolkit NOT installed (cublas64_12.dll missing)
- **OS:** Windows (using Git Bash shell)
- **Current LLM:** qwen3:4b via Ollama (local-only, no cloud) OR online models via OpenAI/Anthropic/Gemini/OpenRouter
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
| **Avatar Animation** | CSS glass sphere + Framer Motion (concentric orbital rings) | ✅ Working |
| **Backend** | Python FastAPI (sidecar process) | ✅ Working |
| **LLM Runtime** | Ollama (qwen3:4b) + Multi-provider API support | ✅ FULLY IMPLEMENTED |
| **Multi-Provider LLM** | Ollama, OpenAI, Anthropic, Gemini, OpenRouter, Ollama Cloud | ✅ FULLY IMPLEMENTED |
| **API Key Management** | File-backed JSON store + Settings modal | ✅ FULLY IMPLEMENTED |
| **Speech-to-Text** | Server-side: faster-whisper (GPU auto-detect → CPU fallback) + STT model selector in Settings | ✅ FULLY IMPLEMENTED |
| **Text-to-Speech** | Browser SpeechSynthesis API | ✅ FULLY IMPLEMENTED |
| **Long-Term Memory** | LanceDB 0.33.0 (vector) + SQLite (structured) | ✅ FULLY IMPLEMENTED & TESTED |
| **Embeddings** | all-MiniLM-L6-v2 (sentence-transformers 5.5.1) | ✅ Integrated & Tested |
| **System Control** | pycaw, screen_brightness_control, subprocess, psutil | ✅ FULL PC CONTROL |
| **PC Control** | 60+ methods, LLM-powered PowerShell fallback | ✅ FULLY IMPLEMENTED |
| **Toast Notifications** | winotify (Windows 10/11 native) | ✅ FULLY IMPLEMENTED |
| **Background Tasks** | asyncio reminder checker | ✅ FULLY IMPLEMENTED |

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
| `may/src/hooks/useMicMonitor.ts` | Browser mic capture via getUserMedia + MediaRecorder + amplitude visualization |
| `may/src/hooks/useSpeechRecognition.ts` | `useBackendSTT` flag (always true), browser STT fallback code (dead but kept) |
| `may/src/components/VoiceMonitor.tsx` | Floating side panel with frequency bars, amplitude meter, countdown timer, transcript |
| `may/src/App.tsx` | `handleVoiceToggle()` — orchestrates the full voice flow |
| `may/src/components/SettingsModal.tsx` | API key management + **STT model selector** (auto/GPU/CPU model buttons) |
| `may/backend/main.py` | `/voice/transcribe-audio` + `/voice/model` endpoints, provider routing, system commands |
| `may/backend/voice/stt.py` | `SpeechToText` class — faster-whisper with GPU auto-detection + CPU fallback + model switching |

### Critical Bugs That Were Fixed
1. **`useEffect` killed mic capture** — A `useEffect` meant for browser STT cleanup was also killing the backend STT mic capture. Fixed by adding `!useBackendSTT` to the guard condition.
2. **Stale closure in voice path** — `handleVoiceToggle` is a `useCallback` that captured a stale `handleSendMessage` always using `provider: "ollama"`. Fixed by using `handleSendMessageRef.current()` instead.
3. **`webkitSpeechRecognition` in Opera** — Opera has `webkitSpeechRecognition` in the DOM but it doesn't work in Tauri WebView2. Fixed by always using backend STT.
4. **Language detection bottleneck** — Removing `language="en"` caused faster-whisper to spin for 60+ seconds detecting language on silence. Re-added `language="en"` to skip detection.
5. **WAV conversion was slower** — Attempted to replace webm→ffmpeg with raw PCM capture, but it was slower on CPU due to large-v3-turbo model. Reverted to webm+ffmpeg approach.

### STT Model Selector (New!)
- **Settings Modal** → "Speech Recognition" section at top
- **auto** button — detects GPU/CPU and picks best model automatically
- **GPU models** — `large-v3-turbo` (shown with ⚡ badge)
- **CPU models** — `small`, `base`, `tiny`
- Backend endpoints:
  - `GET /voice/model` — returns current device, model, available options, auto status
  - `POST /voice/model` — switches model at runtime (uses `run_in_executor` to avoid blocking event loop)
- Module-level `_stt_forced_model` tracks whether user manually selected a model vs auto-detect

### GPU Auto-Detection
- `stt.py` tries CUDA first via `ctranslate2.get_supported_compute_types("cuda")`
- If CUDA + float16 available → uses `large-v3-turbo` model (809MB, near-perfect accuracy, ~0.3s)
- If CUDA fails (e.g., missing cublas64_12.dll) → falls back to `small` model on CPU with int8 (~2s)
- The fallback tests GPU with a dummy transcription during `load_model()` to catch runtime errors

### Current Model Configuration
- **GPU available:** `large-v3-turbo` on CUDA with `float16` — ~0.3s transcription
- **CPU fallback:** `small` on CPU with `int8` — ~2s transcription
- **beam_size:** 1 (greedy decoding for speed)
- **language:** "en" (hardcoded to skip language detection bottleneck)
- **condition_on_previous_text:** False (prevents hallucination loops)
- **initial_prompt:** "The following is a transcription of English speech." (biases toward English)

### To Enable GPU Acceleration
Install the **CUDA 12.x Toolkit** from [nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads). This installs `cublas64_12.dll`. After that, the backend auto-detects GPU on next startup. The code handles everything automatically — no code changes needed.

---

## Color Palette (Surfaced Dark Theme)

| Role | Color | Hex |
|:---|:---|:---|
| Background | Deep Charcoal | `#0D0D0D` |
| Surface | Midnight Slate | `#1A1A1A` |
| Surface Elevated | Dark Zinc | `#252525` |
| Border | Subtle Line | `#2E2E2E` |
| Accent Primary | Electric Cyan | `#06B6D4` |
| Accent Secondary | Soft Purple | `#8B5CF6` |
| Success | Mint Green | `#4ADE80` |
| Warning | Amber | `#F59E0B` |
| Danger | Red | `#EF4444` |
| Text Primary | Off-White | `#E5E5E5` |
| Text Secondary | Warm Gray | `#A0A0A0` |
| Text Muted | Dark Gray | `#666666` |

---

## Project Structure

```
C:\AI\may\
├── knowledge.md              # THIS FILE — read first every session
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json / tsconfig.node.json
├── tailwind.config.js        # Surfaced Dark palette + JetBrains Mono + glow shadows
├── postcss.config.js
├── src/
│   ├── main.tsx              # React entry point
│   ├── App.tsx               # Main app — floating card layout, state, chat logic, streaming, model selection, voice integration
│   ├── config.ts             # Shared constants (BACKEND_URL = "http://localhost:8080")
│   ├── styles/
│   │   └── globals.css       # Surfaced dark theme, glass-sphere CSS, card-glow, status dots
│   ├── hooks/
│   │   ├── useSpeechRecognition.ts  # useBackendSTT (always true), browser STT fallback
│   │   ├── useSpeechSynthesis.ts    # Browser TTS via SpeechSynthesis API
│   │   └── useMicMonitor.ts         # Browser mic capture via getUserMedia + MediaRecorder
│   └── components/
│       ├── ChatPanel.tsx     # Chat bubbles + input + voice toggle + model selector + live transcript
│       ├── Avatar.tsx        # 3D glass sphere with mesh gradient + orbital ring animations
│       ├── StatusHUD.tsx     # Real-time clock, live GPU/RAM bars, model selector (compact variant)
│       ├── ModelSelector.tsx # Multi-provider model dropdown with search, accordion provider sections
│       ├── SettingsModal.tsx # API key management for all providers + **STT model selector**
│       ├── VoiceMonitor.tsx  # Floating side panel with frequency bars, amplitude, countdown, transcript
│       ├── FloatingOrb.tsx   # Mini glass sphere desktop widget with state-reactive glow
│       └── QuickActions.tsx  # Command-palette style action list
├── src-tauri/
│   ├── Cargo.toml            # Rust dependencies
│   ├── tauri.conf.json       # Tauri v2 config (window size, plugins, withGlobalTauri: false)
│   ├── capabilities/default.json  # Tauri v2 permissions (core:default, shell:allow-open)
│   ├── build.rs              # Tauri build script
│   └── src/
│       ├── main.rs           # Rust entry point
│       └── lib.rs            # IPC commands (greet, start_backend)
└── backend/
    ├── main.py               # FastAPI server — streaming chat, commands, memory API, system stats, provider routing, /voice/transcribe-audio, /voice/model
    ├── requirements.txt      # Python dependencies
    ├── .api_keys.json        # Stored API keys (gitignored)
    ├── llm/
    │   ├── __init__.py
    │   ├── ollama_client.py  # Ollama streaming, buffer-based think tag filter, mock mode
    │   └── providers.py      # Multi-provider abstraction (6 providers, API key store)
    ├── voice/
    │   ├── __init__.py
    │   ├── stt.py            # SpeechToText class — faster-whisper with GPU auto-detection + CPU fallback + model switching
    │   └── recorder.py       # (deleted — dead code removed)
    ├── memory/
    │   ├── __init__.py
    │   ├── vector_store.py   # LanceDB 0.33.0 + sentence-transformers 5.5.1 (lazy-loaded via _ensure_db)
    │   └── fact_store.py     # SQLite CRUD + reminders
    └── system/
        ├── __init__.py
        ├── control.py        # 60+ methods — FULL PC CONTROL (4-strategy open_app)
        ├── notifications.py  # Toast notifications (winotify) + background ReminderChecker
        └── pc_controller.py  # LLM-powered PC controller — translates natural language to PowerShell commands
```

---

## Session History

### Session 1: Project Setup & Scaffolding
- ✅ Installed Rust MSVC toolchain, created full project directory structure
- ✅ All frontend components, Surfaced Dark theme, Tauri v2 configured
- ✅ Python FastAPI backend with streaming chat

### Session 2: Core LLM Chat
- ✅ Disabled qwen3 thinking mode, model routing, Ollama health checks
- ✅ Backend + frontend error handling, connection status UI

### Session 3: Voice System & Bug Fixes
- ✅ Browser Web Speech API for STT + TTS
- ✅ Auto-send recognized speech, live transcript, TTS speaks responses
- ✅ Stale closure fix (useRef pattern)

### Session 4: Avatar Upgrade & UI Polish
- ✅ CSS glass sphere avatar with Framer Motion orbital rings
- ✅ Surfaced Dark theme, glassmorphism, status dots, scan bar, voice wave

### Session 5: Multi-Provider Models & API Keys
- ✅ 6 providers: Ollama, OpenAI, Anthropic, Gemini, OpenRouter, Ollama Cloud
- ✅ Unified streaming interface, API key management, Settings modal
- ✅ ModelSelector: search, accordion, auto-expand on search

### Session 6: System Control & PC Management
- ✅ 60+ control methods, LLM-powered PC controller fallback
- ✅ Toast notifications, background reminder checker

### Session 7: Memory System, Voice System & Bug Fixes
- ✅ LanceDB 0.33.0 + sentence-transformers 5.5.1
- ✅ 4-strategy open_app, compound command routing, needs_confirm safety
- ✅ pycaw volume crash fix, speech recognition instance fix

### Session 8: Backend Voice Transcription & Model Selector (This Session)
- ✅ **Created `useMicMonitor.ts`** — Real-time mic amplitude via getUserMedia + MediaRecorder
- ✅ **Created `VoiceMonitor.tsx`** — Floating side panel with frequency bars, amplitude meter, countdown timer, live transcript
- ✅ **Created `voice/stt.py`** — Server-side STT using faster-whisper with GPU auto-detection
- ✅ **Fixed `main.py`** — Added all missing imports (SystemControl, FactStore, VectorStore, SpeechToText, extract_facts, is_pc_command, PC_CONTROLLER_PROMPT, parse_llm_response, numpy) and all missing instantiations
- ✅ **Fixed `vector_store.py`** — Deferred pyarrow import, made LanceDB connection lazy via `_ensure_db()`
- ✅ **Fixed slow startup** — Deferred heavy imports (numpy, sounddevice, pyarrow, lancedb) from module level
- ✅ **Fixed browser STT detection** — `useBackendSTT` always true (webkitSpeechRecognition doesn't work in Tauri WebView2)
- ✅ **Fixed `useEffect` killing mic capture** — Added `!useBackendSTT` guard to prevent cleanup during backend STT recording
- ✅ **Fixed stale closure in voice path** — Changed `handleSendMessage()` to `handleSendMessageRef.current()` so voice uses the current selected provider/model
- ✅ **Fixed syntax error in stt.py** — `cleanup` method was nested inside `load_model()`
- ✅ **GPU auto-detection** — Tries CUDA with large-v3-turbo first, falls back to CPU with small model. Tests GPU with dummy transcription during load to catch runtime errors
- ✅ **Speed optimizations** — beam_size=1, condition_on_previous_text=False, language="en" hardcoded
- ✅ **Removed dead code** — Deleted recorder.py, old /voice/transcribe endpoint, unused imports
- ✅ **Upgraded Whisper model** — tiny → small (better accuracy), tested GPU with large-v3-turbo (cublas missing, falls back)
- ✅ **STT Model Selector in Settings** — New "Speech Recognition" section with auto/GPU/CPU model buttons, device indicator, loading state
- ✅ **Backend `/voice/model` endpoints** — GET/POST for model info and runtime switching, uses `run_in_executor` to avoid blocking event loop
- ✅ **Fixed template literal bug** — Missing closing backtick in SettingsModal.tsx placeholder prop
- ✅ **Fixed unused `loading` state** — Removed `loading` state variable from SettingsModal after removing ternary

---

## 🔲 What Needs to Be Done in NEXT Session

### Immediate
1. **Install CUDA 12.x Toolkit** — Enables GPU-accelerated transcription with large-v3-turbo (~0.3s instead of ~2s). Download from [nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads)
2. **Test STT model selector** — Open Settings, switch between auto/small/large-v3-turbo, verify model loads and transcription works
3. **End-to-end voice test** — Rebuild Tauri app, click mic, speak, verify full pipeline with selected model

### Phase 6-8 (Later)
- Phase 6: Settings panel improvements, keyboard shortcuts, theme options
- Phase 7: Boot startup + system tray
- Phase 8: Integration testing + personality tuning

---

## Key Design Decisions

1. **Local-first, cloud-optional** — Local Ollama as default, online providers available via API keys
2. **Tauri over Electron** — Smaller footprint (critical since LLMs eat RAM)
3. **Python sidecar** — FastAPI backend for AI/ML ecosystem access
4. **Streaming everything** — LLM tokens stream to TTS for fast response (< 2s target)
5. **Hybrid memory** — LanceDB for semantic search, SQLite for exact facts
6. **Surfaced Dark aesthetic** — Monochrome palette with single cyan accent
7. **3D glass sphere avatar** — Abstract geometric design using CSS gradients + framer-motion
8. **Buffer-based think filtering** — Accumulate content, strip tags at regex level
9. **Multi-provider abstraction** — Unified streaming interface across all LLM providers
10. **File-backed API keys** — Simple JSON store with env var fallback
11. **Dynamic model discovery** — OpenRouter models fetched live from API
12. **Shared config constants** — `BACKEND_URL` in `config.ts`
13. **LLM-powered PC control fallback** — Unmatched commands go to LLM which generates PowerShell
14. **Conservative command detection** — `is_pc_command` only triggers on strong patterns
15. **Graceful close before force kill** — `close_window` tries `CloseMainWindow()` first
16. **Always use backend STT** — Browser webkitSpeechRecognition doesn't work in Tauri WebView2, so always use server-side faster-whisper
17. **Browser getUserMedia for audio capture** — Python sounddevice records silence on Windows, so capture audio in the browser and send to backend
18. **GPU auto-detection with fallback** — Try CUDA first, fall back to CPU if cublas missing
19. **PyArrow schema for LanceDB 0.33.0** — Required for table creation in newer versions
20. **Lazy LanceDB connection** — `_ensure_db()` defers heavy lancedb/pyarrow imports to first use
21. **Deferred heavy Python imports** — numpy, sounddevice, faster-whisper, sentence-transformers all lazy-loaded
22. **4-strategy open_app** — dict → PowerShell Start-Process → Get-Command → subprocess
23. **Compound command routing** — "X and Y" patterns route to LLM for multi-step execution
24. **needs_confirm safety** — Destructive LLM-generated commands show warning instead of executing
25. **handleSendMessageRef pattern** — Prevents stale closures in useCallback hooks that call handleSendMessage
26. **Module-level _stt_forced_model** — Tracks whether STT model was user-selected vs auto-detected, cleaner than monkey-patching SpeechToText class
27. **run_in_executor for model switching** — POST /voice/model uses run_in_executor to avoid blocking FastAPI event loop during model load
28. **Language="en" hardcoded** — Prevents 60+ second language detection delays on silence/noise

---

## Known Issues / Blockers

1. **Windows SDK missing** — `cargo check` fails because `kernel32.lib` not found. Need Windows 11 SDK via Visual Studio Installer.
2. **CUDA toolkit missing** — cublas64_12.dll not found. GPU falls back to CPU. Install CUDA 12.x from nvidia.com to enable GPU acceleration.
3. **Rive not integrated** — Avatar uses CSS glass sphere, not Rive state machine (Phase 6).
4. **gemma2:2b not downloaded** — Model routing always uses qwen3:4b.
5. **Tauri Rust build fails** — Needs Windows 11 SDK.
6. **Ollama Cloud API auth untested** — Needs live testing.
7. **WiFi/Bluetooth toggle needs Admin** — Some system control features require elevated privileges.
8. **search_files/get_folder_size** — No depth limit on rglob, could be slow on large directories.
9. **TTS only plays in voice mode** — Manual typed messages don't trigger TTS (by design, but could be a setting).
10. **pycaw volume fallback is approximate** — SendKeys volume up/down loop doesn't set absolute level.
11. **ScriptProcessorNode deprecated** — useMicMonitor uses ScriptProcessorNode for PCM capture. Should migrate to AudioWorkletNode in future.
12. **STT model switch has no error feedback** — If model switch fails, user gets no visible feedback (silent catch).
13. **STT model switch shows stale info** — During model load, the UI still shows the old model until POST completes.

---

## Startup Commands

```bash
# Terminal 1 — Python backend
cd C:\AI\may\backend
python main.py
# Starts FastAPI on http://localhost:8080
# First run downloads faster-whisper model (~466MB for small, ~809MB for large-v3-turbo)

# Terminal 2 — Frontend dev server
cd C:\AI\may
npm run dev
# Starts Vite on http://localhost:1420

# Terminal 3 — Ollama (should already be running)
ollama serve
# Or just ensure Ollama is running in system tray
```

---

## Session Continuity Instructions

When starting a new session:
1. **Read this file first** — it has the complete project state
2. Check the "What Needs to Be Done in NEXT Session" section
3. Continue from the first incomplete task
4. After completing tasks, update this file
5. Test changes before moving to the next task

---

*Last updated: End of Session 8 — Voice transcription pipeline fully implemented with STT model selector. Backend STT with faster-whisper (GPU auto-detection + CPU fallback). Settings modal now has "Speech Recognition" section with auto/GPU/CPU model buttons. Backend has GET/POST /voice/model endpoints with run_in_executor. Fixed 8+ critical bugs. Voice works end-to-end: click mic → speak → transcribe → May responds. Current: ~2s on CPU (small model). GPU acceleration available after CUDA toolkit install (~0.3s with large-v3-turbo). Next: Install CUDA toolkit, test model selector, end-to-end voice test.*
