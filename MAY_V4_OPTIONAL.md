# May V4 — The Definitive Architecture

> **"An AI that controls everything, sees everything, learns everything, speaks naturally, stays invisible, protects itself, and evolves on its own."**

---

## What This Document Is

This is the **complete, definitive architecture** for May V4. It is NOT an incremental upgrade. It is a **ground-up redesign** based on deep research of every major AI assistant in 2025-2026 (Open Interpreter, Anthropic Computer Use, Apple Intelligence, Microsoft Copilot, Rabbit R1, Humane AI Pin, Auto-GPT, Samsung Galaxy AI).

**Why a rewrite?** Because May V3 has fundamental architectural limitations:
- The Control Core daemon only covers 269 actions — not EVERYTHING
- Screen understanding is on-demand only — not continuous
- Voice is fixed 5-second recording — not natural conversation
- No real security — API keys stored in plaintext JSON
- No self-awareness — can't tune, update, or improve itself
- No internet learning — can only read RSS feeds
- The 3-process model creates artificial barriers between perception and action

**May V4 merges perception, intelligence, and control into a unified system.**

---

## Architecture Overview: The 7 Pillars

```
╔════════════════════════════════════════════════════════════════════════════════╗
║                          MAY V4 — 7 PILLARS                                   ║
║                                                                               ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │  PILLAR 1: UNIVERSAL CONTROL                                            │  ║
║  │  Every file, app, software, terminal, command, setting, device          │  ║
║  │  15 layers, 700+ actions, PowerShell deep integration                  │  ║
║  │  Native Win32 + COM + WMI + Playwright + UIAutomation                  │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                                                               ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │  PILLAR 2: CONTINUOUS PERCEPTION                                        │  ║
║  │  Screen understanding (OCR + UI detection + semantic analysis)          │  ║
║  │  Always-on voice (Silero VAD + streaming STT + emotional tone)         │  ║
║  │  Process lifecycle, network traffic, clipboard, window state            │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                                                               ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │  PILLAR 3: INVISIBLE PRESENCE                                           │  ║
║  │  Memory minimization (<50MB idle), CPU idle priority                   │  ║
║  │  DPAPI encrypted storage, rotating logs, temp file cleanup             │  ║
║  │  Windows Service + tray app hybrid, legitimate process identity        │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                                                               ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │  PILLAR 4: NATURAL CONVERSATION                                         │  ║
║  │  Barge-in interruption, backchanneling, emotional intelligence         │  ║
║  │  Persistent memory (weeks/months), topic tracking, ambiguity resolve   │  ║
║  │  Multi-turn tool chains, adaptive personality, relationship building   │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                                                               ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │  PILLAR 5: BULLETPROOF SECURITY                                         │  ║
║  │  AES-256-GCM encryption at rest, DPAPI key storage                     │  ║
║  │  SHA-512 integrity verification, signed manifests                      │  ║
║  │  Anti-tampering, permission isolation, audit trail                     │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                                                               ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │  PILLAR 6: HYBRID INTELLIGENCE                                          │  ║
║  │  Auto-switching local/cloud, model cascading (0.6B → 3.8B → cloud)    │  ║
║  │  Self-tuning parameters, latency profiling, cost optimization          │  ║
║  │  RAG memory injection, predictive suggestions                          │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                                                               ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │  PILLAR 7: SELF-EVOLUTION                                               │  ║
║  │  Internet learning (RAG pipeline, user-permission-gated)               │  ║
║  │  Self-update with rollback, hot-reload, integrity verification         │  ║
║  │  Skill acquisition, dynamic tool registration, auto-optimization       │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
╚════════════════════════════════════════════════════════════════════════════════╝
```

---

## PILLAR 1: Universal Control — The 15-Layer Execution Engine

### Why 15 Layers?

V3's 9 layers cover files, processes, apps, windows, input, registry, services, system, and browser. But May can't:
- Control Windows Settings (UWP apps with no standard API)
- Manage network configuration (firewall, DNS, proxy)
- Control audio routing (per-app volume, spatial sound)
- Manage drivers and hardware
- Control Windows features and optional components

V4 adds 6 new layers for TOTAL system control.

### The 15 Layers

| Layer | Name | Controls | Key APIs | V3→V4 |
|:---|:---|:---|:---|:---|
| **L1** | Filesystem | Files, folders, drives, ACLs, symlinks, shadow copies | pathlib, win32file, win32security | +15 actions |
| **L2** | Process | Launch, kill, suspend, inject, memory read, DLL listing | psutil, win32process, ctypes | +10 actions |
| **L3** | Application | App launch (7 strategies), UWP, COM automation, DDE | winreg, win32com, pywinauto | +12 actions |
| **L4** | Window | Position, size, state, z-order, DPI, multi-monitor, virtual desktops | win32gui, ctypes.user32 | +8 actions |
| **L5** | Input | Keyboard, mouse, clipboard, raw input hooks, game input, touch/pen | win32api, ctypes.user32, pynput | +10 actions |
| **L6** | Registry | All hives, ACL editing, key permissions, hive mounting | winreg, win32security | +8 actions |
| **L7** | Services | Windows Services, Task Scheduler, service dependencies, recovery | win32serviceutil, COM | +10 actions |
| **L8** | System | Power, audio, display, network, env vars, power plans | pycaw, ctypes, WMI | +15 actions |
| **L9** | Browser | DOM automation, multi-tab, cookies, downloads, screenshots | playwright | +10 actions |
| **L10** | Network | Firewall rules, DNS, proxy, hosts file, packet capture, WiFi | scapy, netsh, WMI | NEW — 25 actions |
| **L11** | Clipboard | History, monitoring, format conversion, bulk paste, image paste | win32clipboard, pyperclip | NEW — 8 actions |
| **L12** | Device | USB management, printers, displays, audio devices, Bluetooth | WMI, win32api, ctypes | NEW — 12 actions |
| **L13** | Windows Settings | Display, sound, network, bluetooth, personalization, privacy | pywinauto UIAutomation, UWP | NEW — 20 actions |
| **L14** | Windows Features | Optional features, drivers, Windows Update, .NET, WSL | DISM, PowerShell, WMI | NEW — 15 actions |
| **L15** | PowerShell Deep | Arbitrary PowerShell execution with safety checks, variable scope | subprocess, win32com | NEW — unlimited |

**Total: 700+ actions** across 15 layers.

### PowerShell Deep Integration (L15)

The escape hatch. When no specific layer action exists, L15 executes arbitrary PowerShell with safety:

```python
class PowerShellDeep:
    """Execute ANY PowerShell command with safety controls."""
    
    # Block list — never execute these
    BLOCKED_PATTERNS = [
        r"Format-Volume", r"Clear-Disk", r"Initialize-Disk",
        r"Remove-Item.*System32", r"Stop-Service.*WinDefend",
        r"Disable-WindowsOptionalFeature.*Hyper-V",
        r"BCEdit.*/set.*noexecutablenet", r"reagentc.*disable",
    ]
    
    # Confirmation required — execute but ask user first
    CONFIRM_PATTERNS = [
        r"Stop-Service", r"Restart-Computer", r"shutdown",
        r"Remove-Item.*-Recurse", r"reg delete",
    ]
    
    async def execute(self, command: str, timeout: int = 30) -> Result:
        # Safety check
        if self._is_blocked(command):
            return Result(success=False, error="Command blocked by safety policy")
        
        needs_confirm = self._needs_confirmation(command)
        
        # Execute via subprocess
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True, text=True, timeout=timeout,
        )
        
        return Result(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr,
        )
```

### UWP/Windows Settings Control (L13)

Windows Settings, Store apps, and UWP apps can't be controlled with standard Win32 APIs. May uses **UIAutomation** (the accessibility API that screen readers use):

```python
class UWPController:
    """Control UWP apps and Windows Settings via UIAutomation."""
    
    async def open_settings_page(self, page: str):
        """Open any Windows Settings page by URI."""
        URIS = {
            "display": "ms-settings:display",
            "sound": "ms-settings:sound",
            "network": "ms-settings:network",
            "bluetooth": "ms-settings:bluetooth",
            "privacy": "ms-settings:privacy",
            "personalization": "ms-settings:personalization",
            "apps": "ms-settings:appsfeatures",
            "update": "ms-settings:windowsupdate",
            "firewall": "ms-settings:firewall",
            "defender": "ms-settings:windowsdefender",
        }
        uri = URIS.get(page, f"ms-settings:{page}")
        os.startfile(uri)
    
    async def click_ui_element(self, app_name: str, element_name: str):
        """Click a UI element by its automation name."""
        import uiautomation as auto
        # Find the app window
        window = auto.WindowControl(searchDepth=1, Name=app_name)
        if not window.Exists(maxSearchSeconds=5):
            return False
        # Find the element
        element = window.TextControl(Name=element_name)
        if not element.Exists(maxSearchSeconds=2):
            # Try ButtonControl
            element = window.ButtonControl(Name=element_name)
        if element.Exists(maxSearchSeconds=2):
            element.Click()
            return True
        return False
```

### Network Control (L10)

```python
class NetworkController:
    """Full network control — firewall, DNS, WiFi, packet capture."""
    
    async def get_firewall_rules(self) -> list[dict]:
        """List all Windows Firewall rules."""
        result = await self._run_powershell("Get-NetFirewallRule | Select-Object Name,Direction,Action,Enabled | ConvertTo-Json")
        return json.loads(result.output)
    
    async def block_app_network(self, app_path: str):
        """Block an app from accessing the network."""
        await self._run_powershell(
            f'New-NetFirewallRule -DisplayName "May Block {app_path}" '
            f'-Direction Outbound -Action Block -Program "{app_path}" -Enabled True'
        )
    
    async def set_dns(self, adapter: str, primary: str, secondary: str):
        """Set DNS servers for a network adapter."""
        await self._run_powershell(
            f'Set-DnsClientServerAddress -InterfaceAlias "{adapter}" '
            f'-ServerAddresses "{primary}","{secondary}"'
        )
    
    async def get_wifi_password(self, ssid: str = None) -> str:
        """Get WiFi password for current or specified network."""
        result = await self._run_powershell(
            'netsh wlan show profiles | Select-String "All User Profile" | '
            'ForEach-Object { $_ -match ":(.+)$" | Out-Null; '
            'netsh wlan show profile name="$($Matches[1].Trim())" key=clear }'
        )
        return result.output
```

### Audio Routing (L8 — Enhanced)

```python
class AudioController:
    """Per-app volume, audio device routing, spatial sound."""
    
    async def set_app_volume(self, process_name: str, volume: float):
        """Set volume for a specific application (0.0 - 1.0)."""
        from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            if session.Process and session.Process.name() == process_name:
                volume_ctl = session._ctl.QueryInterface(ISimpleAudioVolume)
                volume_ctl.SetMasterVolume(volume, None)
    
    async def set_default_device(self, device_name: str):
        """Switch default audio output device."""
        # Uses Windows Core Audio API via pycaw
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetSpeakers()
        # ... enumerate and set default device
    
    async def mute_app(self, process_name: str, mute: bool = True):
        """Mute/unmute a specific application."""
        from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            if session.Process and session.Process.name() == process_name:
                volume_ctl = session._ctl.QueryInterface(ISimpleAudioVolume)
                volume_ctl.SetMute(1 if mute else 0, None)
```

---

## PILLAR 2: Continuous Perception — The Senses

### 2.1 Screen Understanding Pipeline

**Key insight from research:** True real-time screen understanding (sub-100ms) is impossible with current VLMs. The solution is a **3-tier change-detection pipeline**.

```
┌──────────────────────────────────────────────────────────────┐
│  TIER 1: CHANGE DETECTION (Every 2s, <5ms)                  │
│                                                              │
│  Perceptual hash comparison (imagehash library)              │
│  → If hash change < threshold: skip Tier 2                  │
│  → If hash change > threshold: trigger Tier 2               │
│  → Always: update active window title + process name        │
│                                                              │
│  Cost: <0.1% CPU, zero VRAM                                 │
└──────────────────────────┬───────────────────────────────────┘
                           │ significant change
┌──────────────────────────▼───────────────────────────────────┐
│  TIER 2: STRUCTURED ANALYSIS (On change, ~100ms)            │
│                                                              │
│  PaddleOCR → extract all visible text                       │
│  OmniParser → detect UI elements (buttons, inputs, menus)   │
│  Active window class detection                              │
│  → Output: structured JSON describing the screen            │
│                                                              │
│  Cost: ~50MB RAM, <1% CPU burst                             │
└──────────────────────────┬───────────────────────────────────┘
                           │ complex understanding needed
┌──────────────────────────▼───────────────────────────────────┐
│  TIER 3: VISION MODEL (On demand, ~500ms)                   │
│                                                              │
│  "What am I looking at?" → Qwen3-VL or GPT-4o Vision       │
│  "Read that error message" → OCR + vision                   │
│  "Navigate this form" → OmniParser + vision                 │
│                                                              │
│  Cost: VRAM for model loading, or cloud API credits         │
└──────────────────────────────────────────────────────────────┘
```

**What May "sees" continuously:**
- Active window title and process name (always)
- Whether an error dialog is showing
- Whether the user is in a meeting app
- Whether the user is coding (VS Code, terminal)
- Whether the user is browsing
- Text on screen (OCR, updated on change)

**What May sees on demand:**
- Full semantic understanding ("what am I looking at?")
- Complex UI navigation ("click the submit button")
- Error diagnosis ("what does this error mean?")

### 2.2 Always-On Voice Pipeline

**Key insight from research:** The industry has moved to end-to-end speech-to-speech models, but for May (local-first + tool use), the traditional pipeline is BETTER because speech-to-speech models can't call tools.

```
┌──────────────────────────────────────────────────────────────┐
│  ALWAYS-ON: Silero VAD (<1ms, <0.5% CPU)                   │
│                                                              │
│  Continuous audio monitoring via browser getUserMedia        │
│  Detects speech vs silence in real-time                     │
│  Triggers keyword spotter only when speech detected          │
│  → Replaces May V3's fixed 5-second recording              │
│                                                              │
│  This runs 24/7 with negligible resource usage              │
└──────────────────────────┬───────────────────────────────────┘
                           │ speech detected
┌──────────────────────────▼───────────────────────────────────┐
│  KEYWORD SPOTTER (OpenWakeWord, ~5ms)                        │
│                                                              │
│  Cascaded detection:                                         │
│  1. Ultra-low-power acoustic model (always running)         │
│  2. Verify model runs only when acoustic model fires        │
│  3. "Hey May" confirmed → activate full STT                │
│                                                              │
│  → Replaces May V3's openwakeword (which needs tflite)     │
└──────────────────────────┬───────────────────────────────────┘
                           │ keyword matched
┌──────────────────────────▼───────────────────────────────────┐
│  STREAMING STT (faster-whisper, continuous chunks)           │
│                                                              │
│  Processes audio in 100ms chunks (not fixed 5-second)       │
│  Returns text as user speaks — no waiting                   │
│  ~0.3s on GPU, ~2s on CPU                                   │
│  VAD end-of-speech detection auto-stops recording           │
│                                                              │
│  → Replaces May V3's fixed-duration recording              │
└──────────────────────────┬───────────────────────────────────┘
                           │ text ready
┌──────────────────────────▼───────────────────────────────────┐
│  EMOTIONAL TONE ANALYZER (<10ms, pure feature extraction)   │
│                                                              │
│  Extracts from audio waveform:                              │
│  - Pitch (F0): excitement → high, sadness → low             │
│  - Energy (RMS): urgency → high, calm → low                 │
│  - Tempo: frustration → fast, thoughtful → slow             │
│  - Spectral features: voice quality indicators              │
│                                                              │
│  Classifies: neutral | excited | frustrated | sad | urgent   │
│  Injects into LLM system prompt for emotional context       │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│  LLM PROCESSING                                             │
│                                                              │
│  Receives:                                                  │
│  - Transcribed text                                         │
│  - Emotional tone classification                            │
│  - Screen context (from Pillar 2.1)                         │
│  - Memory injection (from Pillar 6)                         │
│  - Conversation history with topic tracking                 │
│                                                              │
│  Generates response with full situational awareness         │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│  BARGE-IN HANDLER (listens while speaking)                   │
│                                                              │
│  While TTS is playing:                                      │
│  - Silero VAD monitors microphone                           │
│  - If speech detected → immediately stop TTS                │
│  - Process new user input                                   │
│  - This is what makes conversation feel natural             │
│                                                              │
│  → May V3 has NO interruption handling                      │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│  TTS OUTPUT (Browser SpeechSynthesis or XTTS v2)            │
│                                                              │
│  Browser TTS: free, instant, no GPU (default)              │
│  XTTS v2: voice cloning, ~2s per sentence (optional)       │
│  Prosody adjusted based on emotional state:                 │
│  - Excited → faster, higher pitch                           │
│  - Concerned → slower, softer                               │
│  - Neutral → default Shikimori style                        │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 Ambient Monitoring (No Camera Needed)

```python
class AmbientMonitor:
    """Monitor system state without camera or microphone."""
    
    def __init__(self):
        self._clipboard_history = []
        self._process_lifecycle = {}
        self._network_connections = []
        self._window_stack = []
    
    async def monitor_loop(self):
        """Continuous system monitoring."""
        while True:
            # 1. Clipboard monitoring — track what user copies
            clip = await self._get_clipboard()
            if clip != self._last_clipboard:
                self._clipboard_history.append({
                    "text": clip[:200],
                    "timestamp": time.time(),
                    "source": self._get_active_app(),
                })
            
            # 2. Process lifecycle — detect new/terminated processes
            processes = await self._get_process_list()
            new, terminated = self._diff_processes(processes)
            for p in new:
                await self._on_process_started(p)
            for p in terminated:
                await self._on_process_terminated(p)
            
            # 3. Network connections — detect new connections
            connections = await self._get_network_connections()
            new_conn = self._diff_connections(connections)
            for c in new_conn:
                await self._on_new_connection(c)
            
            # 4. Window stack — track focus changes
            focused = await self._get_focused_window()
            if focused != self._last_focused:
                self._on_window_focus_changed(focused)
            
            await asyncio.sleep(1)
```

---

## PILLAR 3: Invisible Presence

### 3.1 Memory Minimization

**Target: <50MB RAM when idle, <2% CPU when idle**

```python
class MemoryManager:
    """Keep May's footprint minimal when not actively helping."""
    
    async def on_user_idle(self, idle_seconds: int):
        """Progressively release resources as user idleness increases."""
        
        if idle_seconds > 60:
            # After 1 minute idle: unload screen analysis model
            self._unload_vision_model()
        
        if idle_seconds > 300:
            # After 5 minutes idle: unload LLM from VRAM
            self._unload_llm()
            # Force garbage collection
            import gc
            gc.collect()
            # Compress SQLite WAL
            self._compact_databases()
        
        if idle_seconds > 1800:
            # After 30 minutes: minimal mode
            self._reduce_monitoring_interval()  # 5s instead of 1s
            self._disable_clipboard_monitoring()
            self._disable_process_monitoring()
    
    async def on_user_active(self):
        """Reload everything when user becomes active."""
        self._preload_llm()      # Background, non-blocking
        self._preload_stt()      # If voice mode
        self._restore_monitoring()
        self._enable_all_monitors()
    
    def get_memory_budget(self) -> dict:
        return {
            "idle": {
                "python_process": "<30MB RAM",
                "vram": "0MB (all models unloaded)",
                "cpu": "<0.5% (VAD only)",
                "open_files": "0 (temp files cleaned)",
            },
            "active": {
                "python_process": "<150MB RAM",
                "vram": "<4GB (phi4-mini + VAD)",
                "cpu": "<10% (normal usage)",
                "open_files": "database handles only",
            },
        }
```

### 3.2 Encryption & Secure Storage

```python
class SecureStorage:
    """Encrypt all sensitive data. No plaintext ever on disk."""
    
    def __init__(self):
        self._storage_dir = Path.home() / ".may" / "secure"
        self._storage_dir.mkdir(exist_ok=True)
    
    def store_api_key(self, provider: str, key: str):
        """Encrypt API key using Windows DPAPI (hardware-backed)."""
        import win32crypt
        encrypted = win32crypt.CryptProtectData(
            key.encode('utf-8'),
            f"May AI - {provider}",
            None, None, None, 0
        )
        path = self._storage_dir / f"{provider}.dpapi"
        path.write_bytes(encrypted)
    
    def retrieve_api_key(self, provider: str) -> str | None:
        """Decrypt API key."""
        import win32crypt
        path = self._storage_dir / f"{provider}.dpapi"
        if not path.exists():
            return None
        encrypted = path.read_bytes()
        decrypted = win32crypt.CryptUnprotectData(encrypted, None, None, None, 0)
        return decrypted[1].decode('utf-8')
    
    def store_general(self, key: str, data: str):
        """Encrypt general data using AES-256-GCM."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = os.urandom(12)
        aesgcm = AESGCM(self._master_key)
        ct = aesgcm.encrypt(nonce, data.encode(), None)
        path = self._storage_dir / f"{key}.enc"
        path.write_bytes(nonce + ct)
    
    def retrieve_general(self, key: str) -> str | None:
        """Decrypt general data."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        path = self._storage_dir / f"{key}.enc"
        if not path.exists():
            return None
        raw = path.read_bytes()
        nonce, ct = raw[:12], raw[12:]
        aesgcm = AESGCM(self._master_key)
        return aesgcm.decrypt(nonce, ct, None).decode()
```

### 3.3 Integrity Verification

```python
class IntegrityVerifier:
    """Verify May's code hasn't been tampered with."""
    
    MANIFEST_PATH = Path.home() / ".may" / "integrity.dat"
    
    def compute_manifest(self) -> dict[str, str]:
        """SHA-512 hash all critical files."""
        import hashlib
        critical_files = [
            "backend/main.py", "backend/llm/jarvis.py", "backend/llm/providers.py",
            "backend/llm/tools.py", "backend/llm/core_bridge.py",
            "core/daemon.py", "core/router.py",
        ]
        manifest = {}
        for f in critical_files:
            full_path = Path(__file__).parent / f
            if full_path.exists():
                h = hashlib.sha512(full_path.read_bytes()).hexdigest()
                manifest[f] = h
        return manifest
    
    def save_manifest(self):
        """Save current manifest for future comparison."""
        import json
        manifest = self.compute_manifest()
        self.MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    
    def verify(self) -> tuple[bool, list[str]]:
        """Check if any critical files were modified."""
        import json
        if not self.MANIFEST_PATH.exists():
            return True, []  # No manifest yet — first run
        stored = json.loads(self.MANIFEST_PATH.read_text())
        current = self.compute_manifest()
        violations = []
        for f, expected in stored.items():
            if f in current and current[f] != expected:
                violations.append(f)
        return len(violations) == 0, violations
```

### 3.4 Process Identity

May should run as a **legitimate-looking Windows process**, not as "python.exe":

```python
class ProcessIdentity:
    """Make May look like a legitimate Windows component."""
    
    def disguise(self):
        """Rename process to a legitimate-looking name."""
        # Method 1: Windows Service (most stealthy)
        # Registered as "MayAudioService" or "DwmHelper"
        # Appears in Services tab, not Apps tab
        
        # Method 2: Rename process display name
        # SetProcessDescription (via SetProcessDEPPolicy + registry)
        
        # Method 3: Run as a child of a legitimate process
        # Spawn under svchost.exe's service group
    
    def set_idle_priority(self):
        """Run at lowest CPU priority when not needed."""
        import psutil, ctypes
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetPriorityClass(handle, 0x40)  # IDLE_PRIORITY_CLASS
    
    def cleanup_on_exit(self):
        """Remove all traces when May exits."""
        # 1. Delete all temp files (audio conversions, screenshots)
        for tmp in Path(tempfile.gettempdir()).glob("may_*"):
            tmp.unlink(missing_ok=True)
        
        # 2. Truncate log files (keep directory, remove content)
        for log in Path.home() / ".may" / "logs":
            log.write_text("")
        
        # 3. Clear PowerShell history for May's commands
        subprocess.run(["powershell", "-Command", 
                       "Remove-Item (Get-PSReadlineOption).HistorySavePath -Force"],
                      capture_output=True)
```

---

## PILLAR 4: Natural Conversation

### 4.1 Memory Injection System

**Every LLM call includes relevant memories, making May feel like she truly knows you:**

```python
class MemoryInjector:
    """Inject relevant context into every LLM prompt."""
    
    async def build_context(self, user_message: str, screen_ctx: dict) -> str:
        """Build a rich context string for the LLM."""
        
        # 1. Semantic memory search (what have we discussed about this topic?)
        memories = await self._vector_store.search(user_message, n=5)
        
        # 2. User facts (name, preferences, habits)
        facts = self._fact_store.get_all_facts()
        
        # 3. Recent conversation summaries (last 3 conversations)
        recent = await self._vector_store.get_recent(3)
        
        # 4. Current screen context (what app, what's visible)
        active_app = screen_ctx.get("active_app", "unknown")
        screen_text = screen_ctx.get("text_on_screen", "")
        
        # 5. Emotional state (from voice tone analysis)
        emotion = self._emotional_context.get_state()
        
        # 6. Time context (morning/afternoon/evening, day of week)
        now = datetime.now()
        time_ctx = f"{now.strftime('%A, %I:%M %p')}"
        
        # 7. Shadow learner patterns (what does user usually do at this time?)
        patterns = self._shadow_learner.get_relevant_patterns(active_app, now)
        
        return f"""
[USER IDENTITY]
Name: {facts.get('name', 'unknown')}
Preferences: {facts.get('preferences', 'none recorded')}
Habits: {', '.join(patterns[:3]) if patterns else 'none detected'}

[SCREEN CONTEXT]
Active app: {active_app}
Visible text: {screen_text[:300]}

[CONVERSATION MEMORY]
{self._format_memories(memories)}

[RECENT CONVERSATIONS]
{self._format_recent(recent)}

[TIME & EMOTION]
Current time: {time_ctx}
User emotion: {emotion.get('type', 'neutral')}
Stress level: {emotion.get('stress', 0)}
"""
```

### 4.2 Multi-Turn Tool Chains

**"Open notepad" → "Now type hello" → "Save it as test.txt"**

The key is maintaining context across tool executions:

```python
class ConversationState:
    """Track state across multi-turn tool use."""
    
    def __init__(self):
        self._last_opened_app = None
        self._last_created_file = None
        self._last_searched_query = None
        self._pending_confirmation = None
        self._active_window_title = None
    
    def update_from_tool_result(self, tool_name: str, args: dict, result: str):
        """Update state after a tool call."""
        if tool_name == "open_app":
            self._last_opened_app = args.get("app_name")
        elif tool_name == "write_file":
            self._last_created_file = args.get("path")
        elif tool_name == "web_search":
            self._last_searched_query = args.get("query")
    
    def resolve_pronouns(self, message: str) -> str:
        """Resolve 'it', 'that', 'the file' to concrete references."""
        lower = message.lower()
        
        # "type in it" → "type in [last opened app]"
        if "in it" in lower and self._last_opened_app:
            message = message.replace("in it", f"in {self._last_opened_app}")
        
        # "save it" → "save [last created file]"
        if "save it" in lower and self._last_created_file:
            message = message.replace("save it", f"save {self._last_created_file}")
        
        return message
```

### 4.3 Emotional Intelligence

```python
class EmotionalIntelligence:
    """Track and respond to user's emotional state."""
    
    def __init__(self):
        self._emotion_history = []
        self._relationship_score = 0.5  # 0=stranger, 1=best friend
        self._interaction_count = 0
        self._shared_memories = []
    
    def analyze_input(self, text: str, voice_tone: str = None) -> dict:
        """Determine user's emotional state from input."""
        # Text sentiment (simple keyword-based, no model needed)
        positive_words = {"thanks", "great", "awesome", "perfect", "love", "amazing"}
        negative_words = {"frustrated", "annoying", "stupid", "broken", "hate", "ugh"}
        urgent_words = {"now", "hurry", "quickly", "asap", "urgent", "emergency"}
        
        words = set(text.lower().split())
        
        if words & urgent_words:
            mood = "urgent"
        elif words & negative_words:
            mood = "frustrated"
        elif words & positive_words:
            mood = "happy"
        elif len(text) > 200:
            mood = "detailed"  # User is being thorough
        else:
            mood = "neutral"
        
        # Adjust relationship score
        self._interaction_count += 1
        if self._interaction_count > 100:
            self._relationship_score = min(1.0, self._relationship_score + 0.001)
        
        return {
            "mood": mood,
            "relationship": self._relationship_score,
            "interaction_count": self._interaction_count,
            "suggested_style": self._get_response_style(mood),
        }
    
    def _get_response_style(self, mood: str) -> str:
        """Determine how May should respond."""
        styles = {
            "frustrated": "be calm, empathetic, solution-focused",
            "urgent": "be fast, direct, no filler words",
            "happy": "match energy, be warm and playful",
            "detailed": "be thorough, technical, precise",
            "neutral": "default Shikimori style — cool, calm, subtly cute",
        }
        return styles.get(mood, styles["neutral"])
```

### 4.4 Proactive Suggestions

```python
class ProactiveEngine:
    """Suggest actions before the user asks."""
    
    SUGGESTION_RULES = [
        # Time-based
        {"time": "09:00", "day": "Monday", "message": "Ready for the week? Want me to check your emails?"},
        {"time": "17:30", "message": "It's getting late. Want me to save your work?"},
        {"idle": 3600, "message": "You've been idle for an hour. Need anything?"},
        
        # Pattern-based (from shadow learner)
        {"pattern": "open_chrome_then_gmail_3x", "message": "You open Chrome → Gmail every morning. Want me to automate that?"},
        
        # Context-based
        {"error_dialog_detected", "message": "I see an error dialog. Want me to read it and find a fix?"},
        {"same_file_5min", "message": "You've been on this file for 5 minutes. Want help?"},
        {"battery_low", "message": "Battery is at 15%. Want me to save everything?"},
    ]
    
    async def check_suggestions(self, context: dict) -> str | None:
        """Check if any proactive suggestion should fire."""
        for rule in self.SUGGESTION_RULES:
            if self._matches_rule(rule, context):
                # Don't spam — max 1 suggestion per 10 minutes
                if time.time() - self._last_suggestion_time < 600:
                    continue
                self._last_suggestion_time = time.time()
                return rule["message"]
        return None
```

---

## PILLAR 5: Bulletproof Security

### 5.1 Security Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  SECURITY LAYERS                                             │
│                                                              │
│  Layer 1: Authentication                                     │
│  - Voice biometrics (resemblyzer, cosine similarity)         │
│  - PIN fallback (6-char hex)                                 │
│  - Auto-lock on user absence                                │
│                                                              │
│  Layer 2: Encryption                                         │
│  - API keys: Windows DPAPI (hardware-backed, user-bound)    │
│  - General data: AES-256-GCM                                │
│  - Conversation logs: Fernet symmetric encryption            │
│  - No plaintext ever on disk                                │
│                                                              │
│  Layer 3: Integrity                                          │
│  - SHA-512 manifest of all critical files                    │
│  - Verified on startup + every 60 seconds                   │
│  - Tampering alert → lock down mode                          │
│                                                              │
│  Layer 4: Permission Isolation                               │
│  - May runs with user-level permissions (not SYSTEM)         │
│  - Destructive actions require explicit confirmation         │
│  - Financial/irreversible actions blocked by default         │
│                                                              │
│  Layer 5: Audit Trail                                        │
│  - Every tool execution logged (SQLite)                      │
│  - Every file access logged                                  │
│  - Every network request logged                              │
│  - Log integrity: hash chain (each entry hashes previous)   │
│  - Viewable by user, exportable, deletable                  │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 Action Safety Classification

```python
class SafetyClassifier:
    """Classify every action by risk level."""
    
    RISK_LEVELS = {
        # SAFE — execute immediately
        "safe": [
            "get_time", "get_date", "get_weather", "web_search",
            "screenshot", "list_processes", "get_volume", "get_brightness",
            "open_app", "list_windows", "get_system_info",
        ],
        
        # MODERATE — execute but log
        "moderate": [
            "type_text", "write_file", "move_file", "rename_file",
            "set_volume", "set_brightness", "focus_window",
            "create_folder", "install_app",
        ],
        
        # DESTRUCTIVE — require user confirmation
        "destructive": [
            "delete_file", "delete_folder", "kill_process",
            "uninstall_app", "format_disk", "run_powershell",
            "send_email", "shutdown_pc", "restart_pc",
        ],
        
        # CRITICAL — require explicit confirmation + cooldown
        "critical": [
            "delete_folder_tree", "empty_recycle_bin",
            "disable_service", "modify_registry_system",
            "batch_delete", "clear_browser_data",
        ],
    }
    
    def classify(self, tool_name: str, args: dict) -> str:
        """Return risk level for a tool call."""
        for level, tools in self.RISK_LEVELS.items():
            if tool_name in tools:
                return level
        return "moderate"  # Unknown tools are moderate by default
    
    def requires_confirmation(self, tool_name: str) -> bool:
        """Check if this action needs user approval."""
        level = self.classify(tool_name, {})
        return level in ("destructive", "critical")
```

---

## PILLAR 6: Hybrid Intelligence

### 6.1 Three-Tier Model Routing

```
┌──────────────────────────────────────────────────────────────┐
│  USER INPUT                                                   │
│       │                                                       │
│  ┌────▼────────────────────┐                                  │
│  │  TIER 0: Fast-Path      │  Regex pattern matching         │
│  │  ~40% of commands       │  No LLM needed                  │
│  │  Latency: 0ms           │  "open notepad" → execute       │
│  └────┬────────────────────┘                                  │
│       │ miss                                                  │
│  ┌────▼────────────────────┐                                  │
│  │  TIER 1: Router (0.6B)  │  Tiny model for simple tasks    │
│  │  ~35% of queries        │  Greetings, simple commands     │
│  │  Latency: 50-150ms      │  "hey" → "Hey~ What's up?"    │
│  │  VRAM: 0.5GB            │  "time?" → "It's 3:45 PM~"    │
│  └────┬────────────────────┘                                  │
│       │ complex                                               │
│  ┌────▼────────────────────┐                                  │
│  │  TIER 2: Main (3.8B)    │  Full reasoning + tools         │
│  │  ~25% of queries        │  Multi-step, reasoning, chat    │
│  │  Latency: 100-300ms     │  "write essay" → generate       │
│  │  VRAM: 2.5GB            │  "open and type" → tool chain   │
│  └────┬────────────────────┘                                  │
│       │ needs vision/cloud                                    │
│  ┌────▼────────────────────┐                                  │
│  │  TIER 3: Cloud          │  GPT-4o, Claude, Gemini         │
│  │  Complex reasoning      │  "analyze this document"        │
│  │  Vision tasks           │  "what am I looking at?"        │
│  │  Latency: 500ms-2s      │  "explain this code"            │
│  └─────────────────────────┘                                  │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 Auto-Tuning Engine

```python
class AutoTuner:
    """Self-optimize May's parameters based on actual usage."""
    
    async def tune_loop(self):
        """Run every hour to optimize parameters."""
        while True:
            await asyncio.sleep(3600)
            metrics = self._collect_metrics()
            
            # Optimize context window
            avg_ctx = metrics["avg_context_tokens"]
            if avg_ctx < 1500:
                self._config.num_ctx = 2048    # Save VRAM
            elif avg_ctx < 3000:
                self._config.num_ctx = 4096    # Default
            elif avg_ctx < 6000:
                self._config.num_ctx = 8196    # More context
            else:
                self._config.num_ctx = 16384   # Full context
            
            # Optimize temperature
            if metrics["tool_call_ratio"] > 0.7:
                self._config.temperature = 0.3  # Deterministic for tools
            else:
                self._config.temperature = 0.7  # Creative for chat
            
            # Optimize max_tokens
            avg_response = metrics["avg_response_tokens"]
            self._config.max_tokens = min(1024, int(avg_response * 1.5))
            
            # Auto-switch local/cloud
            local_latency = metrics["avg_local_latency"]
            if local_latency > 3.0:
                self._config.prefer_cloud = True
            elif local_latency < 1.0:
                self._config.prefer_cloud = False
            
            logger.info("Auto-tuned: ctx=%d, temp=%.1f, max_tok=%d, cloud=%s",
                       self._config.num_ctx, self._config.temperature,
                       self._config.max_tokens, self._config.prefer_cloud)
```

---

## PILLAR 7: Self-Evolution

### 7.1 Internet Learning Pipeline

**User says "learn about X" → May searches, extracts, stores knowledge**

```python
class InternetLearner:
    """Learn from the internet when user gives permission."""
    
    def __init__(self):
        self._enabled = False  # NEVER enabled by default
        self._knowledge_store = VectorStore()
        self._allowed_topics = []  # Empty = can't learn anything yet
    
    def enable(self):
        """User explicitly enables learning."""
        self._enabled = True
    
    def set_allowed_topics(self, topics: list[str]):
        """User sets which topics May can learn about."""
        self._allowed_topics = topics
    
    async def learn(self, topic: str) -> str:
        """Learn about a specific topic."""
        if not self._enabled:
            return "Internet learning is disabled. Enable it in Settings first."
        
        if self._allowed_topics and topic not in self._allowed_topics:
            return f"I'm not allowed to learn about '{topic}'. Allowed: {self._allowed_topics}"
        
        # 1. Search the internet
        results = await self._web_search(topic, max_results=5)
        
        # 2. Extract content from each result
        all_facts = []
        for result in results:
            content = await self._extract_content(result.url)
            facts = await self._extract_facts(content, topic)
            all_facts.extend(facts)
        
        # 3. Store in knowledge base
        for fact in all_facts:
            await self._knowledge_store.store(
                text=fact,
                metadata={
                    "topic": topic,
                    "source": "internet",
                    "learned_at": time.time(),
                    "confidence": 0.8,
                }
            )
        
        return f"Learned {len(all_facts)} facts about '{topic}' from {len(results)} sources."
    
    async def recall(self, query: str) -> list[str]:
        """Recall learned knowledge relevant to a query."""
        if not self._enabled:
            return []
        return await self._knowledge_store.search(query, n=5)
```

### 7.2 Self-Update Mechanism

```python
class SelfUpdater:
    """May updates herself automatically with rollback safety."""
    
    VERSION_URL = "https://may-ai.local/api/version"
    
    async def check_for_updates(self):
        """Check every 24 hours."""
        while True:
            await asyncio.sleep(86400)
            latest = await self._fetch_latest()
            if self._is_newer(latest.version):
                await self._apply_update(latest)
    
    async def _apply_update(self, update):
        """Apply with full rollback capability."""
        # 1. Create backup
        backup_dir = Path.home() / ".may" / "backups" / f"v{self._version}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        for critical_file in self._CRITICAL_FILES:
            src = Path(__file__).parent / critical_file
            if src.exists():
                dst = backup_dir / critical_file
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        
        try:
            # 2. Download update
            files = await self._download(update.url)
            
            # 3. Verify signatures
            if not self._verify_signatures(files):
                raise SecurityError("Signature verification failed")
            
            # 4. Apply files
            for path, content in files.items():
                (Path(__file__).parent / path).write_bytes(content)
            
            # 5. Run smoke test
            if not await self._smoke_test():
                raise RuntimeError("Smoke test failed")
            
            # 6. Update version
            self._version = update.version
            self._save_version()
            
            logger.info("Updated to v%s", update.version)
            
        except Exception as e:
            # ROLLBACK
            for critical_file in self._CRITICAL_FILES:
                src = backup_dir / critical_file
                if src.exists():
                    dst = Path(__file__).parent / critical_file
                    shutil.copy2(src, dst)
            logger.error("Update failed, rolled back: %s", e)
```

### 7.3 Skill Acquisition

```python
class SkillAcquisition:
    """May learns new skills from demonstrations or the internet."""
    
    def __init__(self):
        self._skills_dir = Path.home() / ".may" / "skills"
        self._skills_dir.mkdir(exist_ok=True)
    
    async def learn_from_demonstration(self, name: str, steps: list[dict]):
        """Record a sequence of actions as a reusable skill."""
        skill = {
            "name": name,
            "steps": steps,
            "learned_at": time.time(),
            "use_count": 0,
        }
        skill_path = self._skills_dir / f"{name}.json"
        skill_path.write_text(json.dumps(skill, indent=2))
        
        # Register as a callable tool
        self._register_skill_tool(name)
        
        return f"Learned skill '{name}' with {len(steps)} steps."
    
    async def execute_skill(self, name: str) -> str:
        """Execute a previously learned skill."""
        skill_path = self._skills_dir / f"{name}.json"
        if not skill_path.exists():
            return f"Skill '{name}' not found."
        
        skill = json.loads(skill_path.read_text())
        skill["use_count"] += 1
        skill_path.write_text(json.dumps(skill, indent=2))
        
        results = []
        for step in skill["steps"]:
            result = await self._execute_step(step)
            results.append(result)
        
        return f"Skill '{name}' completed: {len(results)} steps executed."
    
    async def list_skills(self) -> list[dict]:
        """List all learned skills."""
        skills = []
        for path in self._skills_dir.glob("*.json"):
            skill = json.loads(path.read_text())
            skills.append({
                "name": skill["name"],
                "steps": len(skill["steps"]),
                "use_count": skill["use_count"],
            })
        return skills
```

---

## Implementation Phases

| Phase | Name | Duration | What It Builds |
|:---|:---|:---|:---|
| **P1** | Control Core Expansion | 2 weeks | L10-L15 layers (700+ actions total) |
| **P2** | Perception Pipeline | 2 weeks | Screen OCR, OmniParser, change detection |
| **P3** | Voice Overhaul | 2 weeks | Silero VAD, streaming STT, barge-in, emotion |
| **P4** | Security Hardening | 1 week | DPAPI encryption, integrity verification, audit |
| **P5** | Memory & Conversation | 2 weeks | Memory injection, topic tracking, ambiguity resolve |
| **P6** | Hybrid Intelligence | 1 week | Model cascading, auto-tuning, local/cloud switching |
| **P7** | Self-Evolution | 2 weeks | Internet learning, self-update, skill acquisition |
| **P8** | Stealth & Polish | 1 week | Memory minimization, process identity, cleanup |

**Total: 13 weeks (3 months)**

---

## VRAM Budget (RTX 4050 6GB)

| Component | Active | Idle |
|:---|:---|:---|
| Router (qwen3:0.6b Q4) | 0.5GB | 0GB |
| Main (phi4-mini Q4) | 2.5GB | 0GB |
| STT (faster-whisper small) | 1.0GB | 0GB |
| Screen analysis | 0.3GB | 0GB |
| CUDA runtime | 0.5GB | 0.5GB |
| KV caches | 0.5GB | 0GB |
| **Total** | **5.3GB** | **0.5GB** |
| **Headroom** | **0.7GB** | **5.5GB** |

---

## Expected Performance

| Scenario | V3 (Current) | V4 (New) | Improvement |
|:---|:---|:---|:---|
| "hey" | ~2s | **~150ms** | **13x** |
| "open notepad" | ~2.5s | **~0ms** | **∞** |
| "volume up" | ~0ms | ~0ms | Same |
| "what am I looking at" | ~5s | **~1.5s** | **3.3x** |
| Voice input (fixed 5s) | 5s delay | **Instant (VAD)** | **5x** |
| Conversation interruption | Not possible | **Barge-in** | **New** |
| "open notepad and type hello" | ~10s | **~2.5s** | **4x** |
| Proactive suggestion | None | **Contextual** | **New** |
| "learn about quantum computing" | Not possible | **RAG pipeline** | **New** |
| Self-update | Manual | **Auto with rollback** | **New** |
| **Average interaction** | **~3s** | **~350ms** | **8.5x** |

---

*May V4 — The Definitive Architecture*
*7 Pillars: Universal Control, Continuous Perception, Invisible Presence, Natural Conversation, Bulletproof Security, Hybrid Intelligence, Self-Evolution*
*Created: Session 32 — Deep research synthesis from 11 industry AI systems*
