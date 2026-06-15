# 🌸 May — AI Desktop Companion

**May** is a full-featured desktop AI companion that runs locally on Windows, controls your PC via voice/text commands, and has long-term memory. She's inspired by Shikimori from *Shikimori Not Just a Cutie* — cool, calm, caring, and subtly adorable.

> **Repository:** [LoneWolf0710/May_Pc_AI_Companion](https://github.com/LoneWolf0710/May_Pc_AI_Companion/tree/May) (`May` branch)

---

## ✨ Features

| Feature | Description |
|:---|:---|
| 🎤 **Voice Commands** | Click the mic, speak naturally — May transcribes and responds by voice |
| 💬 **Multi-Provider Chat** | Supports Ollama (local), OpenAI, Anthropic, Gemini, OpenRouter, and Ollama Cloud |
| 🖥️ **Full PC Control** | Open apps, adjust volume/brightness, manage files, run PowerShell, take screenshots, control media, and 60+ more commands |
| 🧠 **Long-Term Memory** | LanceDB vector store for semantic search + SQLite for structured facts — remembers everything across sessions |
| 🎨 **Animated Avatar** | CSS glass sphere with Framer Motion orbital rings, state-reactive animations |
| ⚡ **GPU Acceleration** | Auto-detects NVIDIA GPU for near-instant speech transcription via faster-whisper |
| 🔐 **API Key Management** | Secure Settings modal for managing provider API keys locally |
| 🔔 **Toast Notifications** | Windows native notifications for reminders and alerts |
| 🚀 **Desktop App** | Built with Tauri v2 — lightweight, fast, native Windows feel |

---

## 🛠️ Tech Stack

| Layer | Technology |
|:---|:---|
| **Desktop Framework** | [Tauri v2](https://tauri.app/) (Rust + Web frontend) |
| **Frontend** | React 18 + TypeScript + Tailwind CSS + Framer Motion |
| **Backend** | Python FastAPI (sidecar process) |
| **LLM Runtime** | [Ollama](https://ollama.ai/) + 5 online providers |
| **Speech-to-Text** | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (GPU auto-detect → CPU fallback) |
| **Text-to-Speech** | Browser SpeechSynthesis API |
| **Long-Term Memory** | [LanceDB](https://lancedb.com/) 0.33.0 (vectors) + SQLite (facts) |
| **Embeddings** | [all-MiniLM-L6-v2](https://www.sbert.net/) via sentence-transformers |
| **System Control** | pycaw, screen_brightness_control, psutil, winotify |

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
```

### Running May

You'll need 3 terminals:

```bash
# Terminal 1 — Backend (FastAPI server)
cd backend
python main.py
# Starts on http://localhost:8080

# Terminal 2 — Frontend (Vite dev server)
npm run dev
# Starts on http://localhost:1420

# Terminal 3 — Ollama (should already be running)
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
├── src/                        # React frontend
│   ├── App.tsx                 # Main app — state, chat, voice, streaming
│   ├── components/
│   │   ├── Avatar.tsx          # 3D glass sphere with orbital ring animations
│   │   ├── ChatPanel.tsx       # Chat bubbles + input + model selector
│   │   ├── ModelSelector.tsx   # Multi-provider model dropdown
│   │   ├── SettingsModal.tsx   # API keys + STT model selector
│   │   ├── VoiceMonitor.tsx    # Voice recording panel with frequency bars
│   │   └── ...
│   └── hooks/
│       ├── useMicMonitor.ts    # Browser mic capture
│       └── useSpeechSynthesis.ts
├── src-tauri/                  # Tauri Rust desktop shell
├── backend/                    # Python FastAPI server
│   ├── main.py                 # API endpoints, streaming chat, voice
│   ├── llm/
│   │   ├── ollama_client.py    # Ollama streaming
│   │   └── providers.py        # Multi-provider abstraction
│   ├── voice/
│   │   └── stt.py              # faster-whisper with GPU auto-detection
│   ├── memory/
│   │   ├── vector_store.py     # LanceDB semantic search
│   │   └── fact_store.py       # SQLite structured facts
│   └── system/
│       ├── control.py          # 60+ PC control methods
│       ├── notifications.py    # Toast notifications + reminders
│       └── pc_controller.py    # LLM-powered PowerShell translation
└── knowledge.md                # Full project knowledge base
```

---

## 🎙️ Voice Commands

Click the **mic button** or press the voice toggle to speak to May. Examples:

- *"What time is it?"*
- *"Open Spotify"*
- *"Set volume to 50%"*
- *"Remind me in 30 minutes to take a break"*
- *"What's the weather in Tokyo?"*
- *"Take a screenshot"*

---

## 🖥️ PC Control Examples

May can control virtually anything on your PC:

| Category | Examples |
|:---|:---|
| **Apps** | Open Chrome, close Spotify, list windows |
| **Volume** | Volume up, mute, set volume to 40% |
| **Brightness** | Brighter, dimmer, set brightness to 80% |
| **Files** | Read file, list directory, delete file |
| **Media** | Play, pause, next track, previous track |
| **System** | Shutdown, restart, sleep, lock screen |
| **Network** | WiFi on/off, Bluetooth on/off, IP address |
| **Search** | Google anything, open URLs |
| **Keyboard** | Press keys, type text, alt+tab |
| **PowerShell** | Run any command directly |

---

## 🔧 Configuration

### API Keys

Open **Settings** (gear icon) to add API keys for online providers:

- **OpenAI** — GPT-4o, GPT-4o-mini
- **Anthropic** — Claude 3.5 Sonnet, Claude 3 Haiku
- **Google Gemini** — Gemini 2.0 Flash, Gemini 1.5 Pro
- **OpenRouter** — 100+ models from various providers
- **Ollama Cloud** — Cloud-hosted Ollama models

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
