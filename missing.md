# 🧩 Missing Dependencies — May AI Companion

Below are all dependencies that are **not installed**, **partially installed**, or **need system-level setup**. Run these in order.

---

## 1. Python pip Packages

```bash
cd C:\AI\may\backend

# QR code generation for remote control (phone connection)
pip install "qrcode[pil]>=7.4"

# Voice biometrics — speaker enrollment & verification (256-dim embeddings)
pip install resemblyzer>=0.1.3
```

### Already installed (no action needed):

| Package | Version |
|:---|:---:|
| fastapi | ✅ |
| uvicorn | 0.49.0 |
| httpx | ✅ |
| pydantic | 2.13.4 |
| faster-whisper | ✅ |
| psutil | ✅ |
| pycaw | ✅ |
| lancedb | ✅ |
| openwakeword | ✅ |
| feedparser | ✅ |
| imagehash | ✅ |
| playwright | ✅ |
| py7zr | ✅ |
| comtypes | ✅ |
| Pillow | ✅ |
| easyocr | 1.7.2 |
| torch | 2.12.1 |

---

## 2. Playwright Browser Binaries

`playwright` (pip package) is installed, but **browser binaries are not** — the Control Core browser automation layer (L9) needs Chromium.

```bash
cd C:\AI\may\backend
python -m playwright install chromium
```

---

## 3. CUDA Toolkit 12.x (GPU Acceleration)

**Missing:** `cublas64_12.dll` not found. The RTX 4050 (6GB VRAM) falls back to CPU transcription (~2s instead of ~0.3s).

**Download & install:**  
https://developer.nvidia.com/cuda-downloads

Choose: Windows → x86_64 → exe (local)

After install, verify:
```bash
nvcc --version
# Should show: Cuda compilation tools, release 12.x
```

No pip install needed — `faster-whisper` and PyTorch auto-detect CUDA once the dll is present.

---

## 4. Wake Word — tflite-runtime (Windows)

`openwakeword` is installed but `tflite-runtime` is **not available via pip on Windows**. The wake word feature ("Hey May") will fail to load the model until this is resolved.

**Option A — Install from pre-built wheel:**
```bash
# Download the appropriate .whl from:
# https://github.com/nicktajzsr/tflite-runtime-wheels/releases
# Then:
pip install path\to\downloaded\tflite_runtime-*.whl
```

**Option B — Switch openwakeword to ONNX backend** (avoids tflite entirely):
```python
# In code, when initializing openwakeword:
# oww = openwakeword.Model(backend="onnx")
# ONNX runtime is already bundled with openwakeword on Windows
```

---

## 5. Windows 11 SDK (Tauri Rust Build)

**Missing:** `kernel32.lib` not found — `cargo check` / `npm run tauri build` fails.

**Install via Visual Studio Installer:**
1. Open **Visual Studio Installer**
2. Click **Modify** on your Visual Studio installation
3. Go to **Individual components** tab
4. Search for and check: **"Windows 11 SDK (10.0.22621.0)"**
5. Click **Modify** to install

Or download standalone:  
https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/

After install, verify:
```bash
dir "C:\Program Files (x86)\Windows Kits\10\Lib\10.0.*\um\x64\kernel32.lib"
```

---

## 6. Ollama Models (Dual-Instance Setup)

The backend now uses **two Ollama ports** — a router (qwen3:0.6b) on port 11434 and a main model (phi4-mini:3.8b) on port 11435.

```bash
# Pull both models
ollama pull phi4-mini:3.8b
ollama pull qwen3:0.6b

# Start two Ollama instances (in separate terminals):
# Terminal 1 — Router (port 11434, default)
ollama serve

# Terminal 2 — Main model (port 11435)
set OLLAMA_HOST=127.0.0.1:11435
ollama serve
```

---

## 7. Silero VAD Model (Auto-Downloaded)

The Silero Voice Activity Detection model (~2MB) is **auto-downloaded via torch.hub** on first use. No manual action needed, but the first VAD call will be slow (~5s).

To pre-cache:
```bash
cd C:\AI\may\backend
python -c "
import torch
torch.hub.load(
    'snakers4/silero-vad:v4.1',
    'silero_vad',
    force_reload=False,
    onnx=False,
    verbose=False
)
print('Silero VAD model cached')
"
```

---

## 8. Ollama Model Corruption Check

**Known issue:** `qwen3:4b` may return "does not support chat". If you see this error:

```bash
ollama pull qwen3:4b  # Re-pull to fix corruption
```

---

## Quick Install — All at Once

```bash
cd C:\AI\may\backend

# Python packages
pip install "qrcode[pil]>=7.4" resemblyzer>=0.1.3

# Playwright browser binaries
python -m playwright install chromium

# Pre-cache Silero VAD model
python -c "import torch; torch.hub.load('snakers4/silero-vad:v4.1', 'silero_vad', force_reload=False, onnx=False, verbose=False)"

# Ollama models
ollama pull phi4-mini:3.8b
ollama pull qwen3:0.6b
```
