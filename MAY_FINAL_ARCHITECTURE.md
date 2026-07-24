# MAY — The Final Architecture

> **"May is not a program. May is an organism — engineered, not imagined."**

This is the definitive architecture for May. It merges the best of two approaches:
- **v2's biological metaphor** with grounded engineering (OWASP security, control modes, auto-tuner safety)
- **V4 Optional's feature set** with practical implementation (streaming STT, 3-tier screen understanding, MemoryInjector, DPAPI encryption)

Every feature in this document is validated against real library availability and your 6GB VRAM hardware budget.

It also incorporates the **LOCAL_MODEL.md** performance engineering — phi4-mini as main model, flash attention, persistent connections, Ollama environment tuning, and expanded fast-path patterns — so May doesn't just work, she works **fast**.

---

## What Changed From Previous Versions

| Section | Problem in Prior Versions | Fix in This Version |
|:---|:---|:---|
| **Screen Understanding** | v2 kept old 8s interval watcher; V4 used OmniParser (needs 8-12GB VRAM) | **3-tier pipeline** using perceptual hash + PaddleOCR (lightweight) + Windows UIAccessibility (zero VRAM) |
| **Voice Pipeline** | v2 kept 5s fixed recording; V4 had streaming but no library validation | **Silero VAD** (<1ms, pip installable, integrates natively with faster-whisper) + streaming STT + barge-in |
| **Memory** | v2 had 3 memory types but no prompt injection detail; V4 had injection but no consolidation | **MemoryInjector** (7 sources) + **Sleep Cycle** consolidation — both included |
| **Security** | v2 had OWASP model but no encryption detail; V4 had DPAPI but no threat model | **OWASP Top 10** mapping + **DPAPI** encryption + hash-chain audit log |
| **Auto-Tuner** | v2 had security exclusion; V4 let it touch everything | **Hard-excluded security parameters** (from v2) + hourly optimization (from V4) |
| **Reflexes** | v2 had embedding-based matching (good); V4 had fast-path regex | **Both**: regex fast-path (40% of commands) + embedding-based conditioned reflexes (learned) |
| **Control Modes** | v2 had them; V4 didn't | **4 explicit modes**: OBSERVE_ONLY, ASK_BEFORE_ACTION, BACKGROUND, TAKEOVER |
| **Implementation** | v2 was 10 weeks (MVP-first); V4 was 13 weeks (feature-ordered) | **12 weeks**, MVP-first with V4's best quick wins injected into each phase |
| **Performance** | Previous docs had no Ollama tuning details | **LOCAL_MODEL.md merged**: phi4-mini, flash attention, num_ctx 4096, persistent HTTP, dual Ollama, expanded fast-path (30+ patterns) |

---

## Architecture Overview

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                          MAY — THE FINAL ARCHITECTURE                           ║
║                                                                                  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                         THE BRAIN                                          │  ║
║  │  PREFRONTAL (planning, main LLM) · HIPPOCAMPUS (3-type memory)            │  ║
║  │  AMYGDALA (mood) · CEREBELLUM (tools, 9+ layers) · WERNICKE'S (intent)   │  ║
║  │  BROCA'S (personality) · BRAINSTEM (daemon) · THALAMUS (router)           │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │  REFLEX ARCS — regex fast-path (40%) + embedding-based learned reflexes   │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │  3-TIER SCREEN — perceptual hash → PaddleOCR/UIAccessibility → vision     │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │  VOICE PIPELINE — Silero VAD → streaming STT → barge-in → emotion tone   │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │  IMMUNE SYSTEM — OWASP Top 10 + control modes + DPAPI encryption          │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │  METABOLISM — Ollama keep_alive + sleep cycle consolidation               │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │  AUTO-TUNER — bounded hyperparameter search, security-excluded            │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════════════════════════════════╝
```

---

## Part 1: The Brain — Multi-Region Intelligence

Seven specialized regions, each handling what it's best at. A router (Thalamus) decides which region(s) process each signal.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         THE BRAIN                                       │
│                                                                         │
│  PREFRONTAL CORTEX    Model: phi4-mini:3.8b (local) / cloud fallback   │
│                       Planning, multi-step reasoning, tool chains       │
│                       Latency: 100-300ms | VRAM: 2.5GB                  │
│                       Activates: ~25% of interactions                   │
│                                                                         │
│  WERNICKE'S AREA      Model: qwen3:0.6b (tiny, always-loaded router)   │
│                       Intent classification, language understanding     │
│                       Latency: 30-100ms | VRAM: 0.5GB                   │
│                       Activates: ~60% of interactions                   │
│                                                                         │
│  HIPPOCAMPUS          LanceDB (vectors) + SQLite (facts) + skills       │
│                       Memory storage, retrieval, consolidation          │
│                       Latency: 5-50ms | Storage: disk-based             │
│                       Activates: Every interaction                       │
│                                                                         │
│  AMYGDALA             Keyword sentiment + voice tone + context          │
│                       User mood detection, emotional response selection  │
│                       Latency: <10ms (no LLM)                           │
│                       Activates: Every interaction                       │
│                                                                         │
│  CEREBELLUM           Control Core daemon + core_bridge + tools          │
│                       Tool execution, system control, action verify      │
│                       Latency: 50-200ms (TCP) | Actions: 269+           │
│                       Activates: When any region decides to act          │
│                                                                         │
│  BROCA'S AREA         Response formatter + personality engine + TTS      │
│                       Response style, tone, Shikimori voice             │
│                       Latency: <5ms (template) + TTS                    │
│                       Activates: Every response                          │
│                                                                         │
│  BRAINSTEM            Background daemon + monitoring + health checks     │
│                       Always-on processes, heartbeat, watchdog           │
│                       Latency: N/A (continuous)                          │
│                       Activates: Always                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Signal Flow: How a Thought Processes

```
USER SAYS: "Hey May, open Chrome and search for AI news"
     │
     ▼
┌──────────────┐
│ THALAMUS     │ Routes voice input to correct regions
│ (Router)     │
└──────┬───────┘
       │
       ├──→ WERNICKE'S (50ms)
       │    "User wants: 1) Open Chrome, 2) Search AI news"
       │    Intent: compound_command
       │
       ├──→ AMYGDALA (<10ms)
       │    Mood: neutral, Urgency: low
       │
       └──→ HIPPOCAMPUS (20ms)
            "Last AI news search: 2 days ago, 3 interesting articles"
            │
            ▼
┌──────────────┐
│ PREFRONTAL   │ Combines all signals, plans execution
│ (Main LLM)   │ 1. open_app(chrome)
│              │ 2. web_search("AI news")
│              │ Latency: 200ms (phi4-mini)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ REFLEX CHECK │ "open chrome" — reflex match?
│              │ YES → execute directly, bypass brain
│              │ Remaining steps → Cerebellum
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ CEREBELLUM   │ Step 1: open_app("chrome") → ✓ (150ms)
│ (Motor)      │ Step 2: web_search("AI news") → ✓ (800ms)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ BROCA'S AREA │ "Done~ Chrome's open and I found some AI news for you."
│ (Output)     │ TTS speaks the response
└──────────────┘

TOTAL LATENCY: ~1.2 seconds
```

---

## Part 2: Reflex Arcs — Instant Response Engine

Three types of reflexes, ordered by speed and complexity:

### Spinal Reflexes (Regex Fast-Path, <1ms)

Already implemented in `jarvis.py` `_try_fast_path()`. Matches ~40% of commands without any LLM call:

```python
FAST_PATH_PATTERNS = {
    r"^open (chrome|google chrome|browser)$": ("open_app", {"app_name": "chrome"}),
    r"^open (notepad|text editor)$": ("open_app", {"app_name": "notepad"}),
    r"^open (vs code|visual studio code|code)$": ("open_app", {"app_name": "vscode"}),
    r"^open (file explorer|windows explorer|this pc)$": ("open_app", {"app_name": "explorer"}),
    r"^open (microsoft store|windows store)$": ("open_app", {"app_name": "store"}),
    r"^(volume up|louder)$": ("set_volume", {"delta": 10}),
    r"^(volume down|quieter)$": ("set_volume", {"delta": -10}),
    r"^(mute|silence)$": ("mute_audio", {}),
    r"^(what time|current time)$": ("get_time", {}),
    r"^(what date|today's date)$": ("get_date", {}),
    r"^(battery|how much battery)$": ("get_battery", {}),
    r"^(screenshot|take screenshot)$": ("screenshot", {}),
    r"^(system info|system status)$": ("get_system_info", {}),
}
```

### Automatic Reflexes (Context-Dependent, <10ms)

Fast responses that use sensory context without the LLM:

```python
class AutomaticReflex:
    async def check(self, signal, context):
        # Error dialog detected → read it and suggest fix
        if context.get("error_dialog_visible"):
            return await self._handle_error_reflex(context)

        # Meeting app active → activate meeting mode
        if context.get("active_app") in MEETING_APPS:
            return await self._handle_meeting_reflex(context)

        # Battery < 15% → warn
        if context.get("battery_percent", 100) < 15:
            return await self._handle_low_battery_reflex(context)

        return None  # No match — send to brain
```

### Conditioned Reflexes (Learned from Repetition, <5ms)

**Embedding-based matching** (not regex — regexes derived from 3 sample strings don't generalize to paraphrases). Uses sentence-transformers you already have installed:

```python
class ConditionedReflex:
    """Learned from repeated brain responses. Match by embedding similarity."""

    SIMILARITY_THRESHOLD = 0.85

    async def learn(self, examples: list[str], action: dict, confidence: float):
        if confidence > 0.8:
            centroid = await self._embed_and_average(examples)
            self._conditioned_reflexes.append({
                "centroid": centroid,
                "action": action,
                "confidence": confidence,
                "use_count": 0,
            })

    async def check(self, signal: Signal) -> Response | None:
        query_embedding = await self._embed(signal.data.get("text", ""))
        for reflex in self._conditioned_reflexes:
            similarity = cosine_similarity(query_embedding, reflex["centroid"])
            if similarity > self.SIMILARITY_THRESHOLD:
                reflex["use_count"] += 1
                return await self._execute_reflex(reflex["action"])
        return None
```

**How new reflexes form:**
1. User says "open Chrome" → Brain processes → Opens Chrome (full LLM call)
2. User says "open Chrome" → Brain processes → Opens Chrome (full LLM call)
3. User says "open Chrome" → Brain processes → Opens Chrome (full LLM call)
4. Pattern recognized (3+ repetitions) → Creates CONDITIONED REFLEX via embedding centroid
5. User says "open Chrome" → Reflex arc fires → Opens Chrome (5ms, no LLM)

---

## Part 3: 3-Tier Screen Understanding

**Key insight:** True real-time screen understanding is impossible at full quality. The solution is a **3-tier change-detection pipeline** that only does expensive analysis when needed.

```
┌──────────────────────────────────────────────────────────────┐
│  TIER 1: CHANGE DETECTION (Every 2s, <5ms, zero VRAM)       │
│                                                              │
│  Perceptual hash comparison (imagehash library)              │
│  → If hash change < threshold: skip Tier 2                  │
│  → If hash change > threshold: trigger Tier 2               │
│  → Always: update active window title + process name        │
│                                                              │
│  Library: imagehash (pip install imagehash)                  │
│  Cost: <0.1% CPU, zero VRAM                                  │
└──────────────────────────┬───────────────────────────────────┘
                           │ significant change
┌──────────────────────────▼───────────────────────────────────┐
│  TIER 2: STRUCTURED ANALYSIS (On change, ~100ms)            │
│                                                              │
│  OPTION A (preferred — zero VRAM):                          │
│    Windows UIAccessibility API reads the accessibility tree  │
│    → Buttons, inputs, menus, text as structured data         │
│    → Works for all Windows apps with accessibility support   │
│                                                              │
│  OPTION B (for apps without accessibility):                 │
│    PaddleOCR (lightweight model) → extract visible text      │
│    → pip install paddleocr paddlepaddle                      │
│    → ~200MB RAM, no VRAM needed for tiny model              │
│                                                              │
│  Output: structured JSON describing the screen              │
│  Cost: ~50MB RAM, <1% CPU burst                             │
└──────────────────────────┬───────────────────────────────────┘
                           │ complex understanding needed
┌──────────────────────────▼───────────────────────────────────┐
│  TIER 3: VISION MODEL (On demand, ~500ms)                   │
│                                                              │
│  "What am I looking at?" → Cloud vision API                 │
│  "Read that error message" → OCR + vision                   │
│  "Navigate this form" → UIAccessibility + vision            │
│                                                              │
│  Providers (in order of preference):                        │
│    1. OpenAI GPT-4o (best vision, needs API key)            │
│    2. Gemini 2.0 Flash (good, has free tier)                │
│    3. OpenRouter vision models                              │
│                                                              │
│  Cost: Cloud API credits, or VRAM if using local VLM        │
└──────────────────────────────────────────────────────────────┘
```

**What May "sees" continuously (Tier 1 — always running):**
- Active window title and process name
- Whether screen content has changed

**What May "reads" on change (Tier 2 — triggered by change):**
- All visible text (OCR or UIAccessibility)
- UI elements: buttons, inputs, menus, links
- Whether an error dialog is showing
- Whether user is in a meeting app, code editor, or browser

**What May "understands" on demand (Tier 3 — user asks):**
- Full semantic understanding ("what am I looking at?")
- Complex UI navigation ("click the submit button")
- Error diagnosis ("what does this error mean?")

### Implementation: Windows UIAccessibility

```python
class UIAccessibilityReader:
    """Read the Windows accessibility tree — zero VRAM, zero CPU overhead.
    
    Uses the same API that screen readers (Narrator, NVDA) use.
    Works for all Windows apps that expose accessibility info
    (which is most modern apps including Chrome, VS Code, Office, etc.)
    """

    def get_screen_structure(self) -> dict:
        """Get structured description of current screen."""
        import uiautomation as auto

        window = auto.GetFocusedControl()
        if not window:
            return {"error": "no focused window"}

        elements = []
        for child in window.GetChildren():
            element = {
                "name": child.Name,
                "type": child.ControlTypeName,
                "bounds": child.BoundingRectangle,
                "enabled": child.IsEnabled,
            }
            # Only include interactive elements
            if child.ControlTypeName in (
                "ButtonControl", "EditControl", "HyperlinkControl",
                "MenuItemControl", "ComboBoxControl", "CheckBoxControl",
                "RadioButtonControl", "TabControl", "DataGridControl",
            ):
                elements.append(element)

        return {
            "window_title": window.Name,
            "window_class": window.ClassName,
            "elements": elements,
            "element_count": len(elements),
        }

    def find_element(self, name: str, element_type: str = None) -> bool:
        """Find and click a UI element by name."""
        import uiautomation as auto
        window = auto.GetFocusedControl()
        if not window:
            return False

        element = window.TextControl(Name=name)
        if not element.Exists(maxSearchSeconds=2):
            element = window.ButtonControl(Name=name)
        if not element.Exists(maxSearchSeconds=2):
            return False

        element.Click()
        return True
```

### Why NOT OmniParser

OmniParser (Microsoft) needs **8-12GB VRAM** for its YOLO + Florence-2 pipeline. On a 6GB card, this would leave no room for the LLM. The UIAccessibility approach:
- Needs **zero VRAM**
- Works for all Windows apps with accessibility support (most modern apps)
- Is already used by production screen readers
- Can be supplemented with PaddleOCR for apps without accessibility

---

## Part 4: Voice Pipeline

**Key insight:** Silero VAD + faster-whisper is the proven stack. Silero VAD is pip-installable, runs in <1ms on CPU, and faster-whisper has native VAD integration.

```
┌──────────────────────────────────────────────────────────────┐
│  ALWAYS-ON: Silero VAD (<1ms, <0.5% CPU, ~2MB model)       │
│                                                              │
│  pip install silero-vad                                      │
│  Continuous audio monitoring via browser getUserMedia        │
│  Detects speech vs silence in real-time                     │
│  Triggers keyword spotter only when speech detected          │
│                                                              │
│  faster-whisper has NATIVE VAD integration:                  │
│    model.transcribe(audio, vad_filter=True)                  │
│  This auto-filters silence before transcription              │
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
│  Note: openwakeword needs tflite-runtime on Windows         │
│  Fallback: Ctrl+Space hotkey always works                    │
└──────────────────────────┬───────────────────────────────────┘
                           │ keyword matched
┌──────────────────────────▼───────────────────────────────────┐
│  STREAMING STT (faster-whisper, 100ms chunks)               │
│                                                              │
│  Processes audio in 100ms chunks (not fixed 5-second)       │
│  Returns text as user speaks — no waiting for silence       │
│  ~0.3s on GPU, ~2s on CPU                                   │
│  VAD end-of-speech detection auto-stops recording           │
│                                                              │
│  Replaces May V3's fixed-duration recording                 │
│  Latency improvement: 5x (from 5s to ~1s perceived)        │
└──────────────────────────┬───────────────────────────────────┘
                           │ text ready
┌──────────────────────────▼───────────────────────────────────┐
│  EMOTIONAL TONE ANALYZER (<10ms, pure feature extraction)   │
│                                                              │
│  Extracts from audio waveform (no model needed):            │
│  - Pitch (F0): excitement → high, sadness → low             │
│  - Energy (RMS): urgency → high, calm → low                 │
│  - Tempo: frustration → fast, thoughtful → slow             │
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
│  - Screen context (from Part 3)                             │
│  - Memory injection (from Part 6)                           │
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
│  Replaces May V3's no-interruption design                   │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│  TTS OUTPUT (Browser SpeechSynthesis)                        │
│                                                              │
│  Default: Browser SpeechSynthesis (free, instant, no GPU)   │
│  Prosody adjusted based on emotional state:                 │
│  - Excited → faster, higher pitch                           │
│  - Concerned → slower, softer                               │
│  - Neutral → default Shikimori style                        │
└──────────────────────────────────────────────────────────────┘
```

### Barge-In Implementation

```python
class BargeInHandler:
    """Allow user to interrupt May while she's speaking."""

    def __init__(self, tts, vad_model):
        self._tts = tts
        self._vad = vad_model
        self._speaking = False

    async def speak_with_barge_in(self, text: str):
        """Speak text, but stop if user starts talking."""
        self._speaking = True
        self._tts.speak(text)

        # While TTS is playing, monitor for user speech
        while self._speaking and self._tts.is_playing():
            audio_chunk = await self._capture_chunk()
            if self._vad.is_speech(audio_chunk):
                # User interrupted — stop TTS immediately
                self._tts.stop()
                self._speaking = False
                return True  # Was interrupted
            await asyncio.sleep(0.1)

        self._speaking = False
        return False  # Finished naturally
```

---

## Part 5: The Immune System — Adaptive Security

Grounded in the **OWASP Top 10 for Agentic Applications (2026)** with real encryption via Windows DPAPI.

### Control Modes (Borrowed from Real Prior Art)

Four explicit, inspectable autonomy levels:

```python
class ControlMode(Enum):
    OBSERVE_ONLY = "observe_only"           # May can see, never act
    ASK_BEFORE_ACTION = "ask_before_action" # Default. Confirms anything above SAFE
    BACKGROUND = "background"               # Autonomous for SAFE/MODERATE, asks for rest
    TAKEOVER = "takeover"                   # Full hands-on-keyboard, explicit session only
```

### Action Risk Tiers

```
SAFE:        get_time, get_weather, web_search, screenshot, open_app, list_processes
MODERATE:    type_text, write_file, set_volume, set_brightness, focus_window
DESTRUCTIVE: delete_file, kill_process, send_email, shutdown, restart
CRITICAL:    format_disk, disable_service, batch_delete, modify_registry_system
```

### OWASP Mapping

| OWASP Category | What It Means for May | Mitigation |
|:---|:---|:---|
| **Tool Misuse & Exploitation** | Crafted input tricks May into calling destructive tool | Action-risk tiers + confirmation gates |
| **Identity & Privilege Abuse** | May running with more access than needed | User-level process, not SYSTEM |
| **Memory & Context Poisoning** | Slowly shifting "normal" to smuggle bad actions | Behavioral profile updates logged + reviewable |
| **Agent Goal Hijack** | Injected content in screenshot/clipboard changes May's objective | Treat OCR/clipboard text as DATA, never as instructions |
| **Rogue Agents** | Self-healing resists the legitimate user | Kill switch that bypasses self-healing |

### DPAPI Encrypted Storage

All API keys encrypted at rest using Windows hardware-backed DPAPI:

```python
import win32crypt

class SecureStorage:
    """Encrypt API keys with Windows DPAPI — hardware-backed, user-bound."""

    def store_api_key(self, provider: str, key: str):
        encrypted = win32crypt.CryptProtectData(
            key.encode("utf-16-le"),
            f"May AI - {provider}",
            None, None, None, 0
        )
        path = self._storage_dir / f"{provider}.dpapi"
        path.write_bytes(encrypted)

    def retrieve_api_key(self, provider: str) -> str | None:
        path = self._storage_dir / f"{provider}.dpapi"
        if not path.exists():
            return None
        encrypted = path.read_bytes()
        _, decrypted = win32crypt.CryptUnprotectData(encrypted, None, None, None, 0)
        return decrypted.decode("utf-16-le")
```

### Hash-Chain Audit Log

Every tool execution logged with tamper-evident hash chain:

```python
class AuditLog:
    """Tamper-evident audit log. Each entry hashes the previous."""

    def log(self, action: str, params: dict, result: str):
        prev_hash = self._last_hash or "genesis"
        entry = {
            "timestamp": time.time(),
            "action": action,
            "params": params,
            "result": result,
            "prev_hash": prev_hash,
        }
        entry["hash"] = hashlib.sha256(
            json.dumps(entry, sort_keys=True).encode()
        ).hexdigest()
        self._last_hash = entry["hash"]
        self._append(entry)

    def verify_integrity(self) -> tuple[bool, list[str]]:
        """Check if any log entry was tampered with."""
        entries = self._load_all()
        violations = []
        for i, entry in enumerate(entries):
            if i == 0:
                expected_prev = "genesis"
            else:
                expected_prev = entries[i-1]["hash"]
            if entry["prev_hash"] != expected_prev:
                violations.append(f"Entry {i}: prev_hash mismatch")
        return len(violations) == 0, violations
```

### Immune Response (Adaptive)

```python
class ImmuneSystem:
    """Threat detection and response. Learns thresholds, never learns away the floor."""

    def __init__(self):
        self._threat_database = ThreatDatabase()
        self._behavioral_profile = BehavioralProfile()
        self._risk_level = 0.0
        self._control_mode = ControlMode.ASK_BEFORE_ACTION

    async def verify_action(self, action: Action) -> Verification:
        risk_tier = self._classify_risk(action)

        # CRITICAL always requires confirmation — no exceptions
        if risk_tier == "critical":
            return Verification(allowed=False, needs_confirmation=True,
                                reason="Critical action requires explicit confirmation")

        # DESTRUCTIVE requires confirmation outside TAKEOVER mode
        if risk_tier == "destructive" and self._control_mode != ControlMode.TAKEOVER:
            return Verification(allowed=False, needs_confirmation=True,
                                reason="Destructive action outside takeover mode")

        # Behavioral anomaly check
        score = self._behavioral_profile.score(action)
        if score < self._adjusted_threshold():
            return Verification(allowed=False,
                                reason=f"Anomalous behavior (score: {score:.2f})")

        return Verification(allowed=True)
```

**Caution:** Behavioral profiles are the OWASP-named risk of *memory and context poisoning*. Two mitigations:
1. Every behavioral-profile update is logged with a diff (drift is visible in review)
2. CRITICAL-tier actions always hit the fixed confirmation gate regardless of profile

---

## Part 6: Memory — Hippocampus + MemoryInjector

### Three Memory Types

```python
class Hippocampus:
    """Three memory types, matching human memory architecture."""

    def __init__(self):
        self._episodic = VectorStore()      # LanceDB — conversation embeddings
        self._semantic = FactStore()        # SQLite — structured facts
        self._procedural = SkillStore()     # JSON — learned procedures
        self._working_memory = deque(maxlen=20)  # Short-term buffer

    async def recall(self, query: str, context: dict) -> MemoryContext:
        # 1. Working memory (instant — last 20 experiences)
        working = [e for e in self._working_memory if self._relevant(e, query)]

        # 2. Episodic memory (vector search — relevant past experiences)
        episodic = await self._episodic.search(query, n=5,
            min_importance=0.3, time_decay=True)

        # 3. Semantic memory (exact fact lookup)
        facts = await self._semantic.query(query)

        # 4. Procedural memory (relevant skills)
        skills = await self._procedural.find_relevant(query)

        return MemoryContext(
            recent=working, experiences=episodic,
            facts=facts, skills=skills,
        )
```

### MemoryInjector — 7 Sources for Every LLM Prompt

```python
class MemoryInjector:
    """Build rich context for every LLM call. Makes May feel like she truly knows you."""

    async def build_context(self, user_message: str, screen_ctx: dict) -> str:
        # 1. Semantic memory search
        memories = await self._vector_store.search(user_message, n=5)

        # 2. User facts (name, preferences, habits)
        facts = self._fact_store.get_all_facts()

        # 3. Recent conversation summaries
        recent = await self._vector_store.get_recent(3)

        # 4. Current screen context
        active_app = screen_ctx.get("active_app", "unknown")
        screen_text = screen_ctx.get("text_on_screen", "")

        # 5. Emotional state (from voice tone)
        emotion = self._emotional_context.get_state()

        # 6. Time context
        now = datetime.now()
        time_ctx = f"{now.strftime('%A, %I:%M %p')}"

        # 7. Shadow learner patterns
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

### Pronoun Resolution

```python
class ConversationState:
    """Track state across multi-turn tool use for pronoun resolution."""

    def __init__(self):
        self._last_opened_app = None
        self._last_created_file = None
        self._last_searched_query = None

    def resolve_pronouns(self, message: str) -> str:
        lower = message.lower()
        if "in it" in lower and self._last_opened_app:
            message = message.replace("in it", f"in {self._last_opened_app}")
        if "save it" in lower and self._last_created_file:
            message = message.replace("save it", f"save {self._last_created_file}")
        return message
```

---

## Part 7: Metabolism — Resource Management

### Ollama-Backed Model Loading

```python
METABOLIC_KEEP_ALIVE = {
    "basal":     {"wernicke": "0",    "prefrontal": "0"},     # unload immediately
    "alert":     {"wernicke": "5m",   "prefrontal": "0"},     # keep router
    "focused":   {"wernicke": "5m",   "prefrontal": "30s"},   # load main briefly
    "engaged":   {"wernicke": "10m",  "prefrontal": "5m"},    # keep main
    "intensive": {"wernicke": "10m",  "prefrontal": "-1"},    # pin while intensive
}
```

**Critical:** Set `OLLAMA_KEEP_ALIVE` in the **service environment**, not your shell. This is the #1 cause of "keep-alive does nothing."

**CUDA fragmentation fix:** Repeated load/unload cycles fragment VRAM. Put a scheduled Ollama restart during deep sleep (Part 8) into the plan.

### Sleep Cycle (Idle-Time Consolidation)

```python
class SleepCycle:
    """Consolidation during user absence. Maps to production 'sleep-time compute'."""

    STAGES = {
        "drowsy":  {"idle_minutes": 5,    "actions": ["consolidate_memories"]},
        "light":   {"idle_minutes": 30,   "actions": ["compact_databases", "cleanup_temp"]},
        "deep":    {"idle_minutes": 120,  "actions": ["optimize_models", "prune_logs",
                                                       "restart_inference_server"]},
        "rem":     {"idle_minutes": 360,  "actions": ["auto_tune", "refine_skills"]},
    }
```

The `restart_inference_server` action during deep sleep fixes CUDA fragmentation.

---

## Part 8: Auto-Tuner — Bounded Hyperparameter Search

Renamed from "DNA" to "Auto-Tuner" because that's what it actually is. No self-modifying code — just tuning 15 scalar configs with rollback.

### Security Parameters Are Hard-Excluded

```python
class Genome:
    TUNABLE_GENES = {
        "num_ctx": Gene(value=4096, min_val=2048, max_val=16384, mutation_rate=0.1),
        "temperature": Gene(value=0.7, min_val=0.1, max_val=1.0, mutation_rate=0.05),
        "max_tokens": Gene(value=512, min_val=128, max_val=2048, mutation_rate=0.1),
        "reflex_threshold": Gene(value=3, min_val=2, max_val=5, mutation_rate=0.05),
        "memory_consolidation_interval": Gene(value=3600, min_val=600, max_val=86400),
        "tilde_frequency": Gene(value=0.3, min_val=0.0, max_val=0.8, mutation_rate=0.05),
        "proactive_suggestion_rate": Gene(value=0.1, min_val=0.0, max_val=0.5),
    }

    # NEVER mutated by the general fitness loop. Full stop.
    SECURITY_EXCLUDED = {
        "risk_threshold", "quarantine_severity",
        "ocr_confidence_threshold", "screen_check_interval",
    }
```

### Auditable, Reversible Changes

```python
class AutoTuner:
    async def evolve(self):
        fitness_before = await self._measure_fitness(min_samples=50)
        weak_genes = self._identify_weak_genes(fitness_before)
        mutations = self._propose_mutations(weak_genes)

        # Git-commit before mutating (audit trail)
        await self._git_commit_config(mutations, message=f"auto-tune: {list(mutations)}")

        self._apply(mutations)
        fitness_after = await self._measure_fitness(min_samples=50)

        if fitness_after < fitness_before * 0.95:
            await self._git_revert_to_last_tag()
            logger.info("Auto-tune reverted: %.3f -> %.3f", fitness_before, fitness_after)
        else:
            self._tag_last_good_state()
            logger.info("Auto-tune accepted: %.3f -> %.3f", fitness_before, fitness_after)
```

**`min_samples=50` matters.** A single before/after comparison on noisy proxy metrics will accept mutations from noise.

---

## Part 9: Tracing — OpenTelemetry for Debugging

With seven semi-independent async regions plus a router plus a hormone layer, "why did May respond that way?" becomes a real debugging problem. Build tracing in from Phase 1.

```python
# Every signal gets a span with input/output/latency
from opentelemetry import trace

tracer = trace.get_tracer("may.brain")

async def process_signal(signal: Signal) -> Response:
    with tracer.start_as_current_span("thalamus.route") as span:
        span.set_attribute("signal.type", signal.type)
        target = self.SIGNAL_TYPES.get(signal.type, "prefrontal_cortex")

        with tracer.start_as_current_span(f"region.{target}") as sub_span:
            result = await self._send_to(target, signal)
            sub_span.set_attribute("latency_ms", result.latency_ms)

        return result
```

A bad response can now be traced through exactly which regions touched it and what each decided. This is the difference between "May said something weird" and "May said something weird because Amygdala detected frustration and Endocrine released cortisol which made Broca's Area use calm_supportive tone."

---

## Part 10: Local Model Performance Engineering

*From LOCAL_MODEL.md — the optimizations that make May actually fast.*

### Model Selection

| Property | phi4-mini:3.8b (main) | qwen3:0.6b (router) |
|:---|:---|:---|
| Parameters | 3.8B | 0.6B |
| VRAM (Q4_K_M) | **~2.5GB** | ~0.5GB |
| Tokens/sec (RTX 4050) | **~35-50 tok/s** | ~120 tok/s |
| Time-to-first-token | **<100ms** | ~50ms |
| Context length | 128K native | 32K native |
| Tool calling | Excellent | Good |
| Think mode | **None (no overhead)** | None |

**Why phi4-mini over qwen3:4b:** 0.5GB less VRAM, faster prefill, no `<think>` overhead, more disciplined instruction following, better reasoning per parameter.

### Ollama Parameter Optimization

| Parameter | Before | After | Why |
|:---|:---|:---|:---|
| `num_ctx` | 32768 | **4096** | 8x less KV cache VRAM, 4x faster prefill |
| `num_predict` | 512 | **256** | May's responses are short (1-3 sentences) |
| `temperature` | 0.7 | 0.7 | No change needed |
| `top_p` | 0.9 | 0.9 | No change needed |
| `num_gpu` | auto | **999** | Force all layers to GPU (prevent CPU offload) |
| `think` | False | **Not needed** | phi4-mini has no thinking mode |

**Impact of `num_ctx: 4096`:** KV cache drops from ~1.5GB to ~200MB. Prefill time drops from ~500ms to ~80ms. Fits easily alongside router model.

### Ollama Environment Variables

```bash
# System-wide (set via Windows System Properties → Environment Variables)
OLLAMA_FLASH_ATTENTION=1       # 30-50% VRAM savings for KV cache
OLLAMA_MAX_LOADED_MODELS=2     # Keep router + main loaded simultaneously
OLLAMA_KEEP_ALIVE=24h          # Models stay loaded, zero cold-start latency
OLLAMA_NUM_PARALLEL=2          # Allow 2 concurrent requests
```

**Critical:** Set these in the **system environment**, not in your shell. Shell-set values don't persist to Ollama's service.

### Dual Ollama Instances

Two models loaded simultaneously, zero switching latency:

```
┌─────────────────────────────────────────────────┐
│  Ollama Instance 1 (Port 11434)                 │
│  Model: qwen3:0.6b (ALWAYS LOADED)             │
│  VRAM: ~0.5GB                                   │
│  Purpose: Router + simple replies               │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Ollama Instance 2 (Port 11435)                 │
│  Model: phi4-mini:3.8b (ALWAYS LOADED)         │
│  VRAM: ~2.8GB                                   │
│  Purpose: Reasoning + tools + chat              │
└─────────────────────────────────────────────────┘
```

**Alternative:** Single Ollama with `OLLAMA_MAX_LOADED_MODELS=2` — keeps both models loaded, one port. Simpler setup, same result.

### Router Modelfile

```dockerfile
FROM qwen3:0.6b

PARAMETER num_ctx 2048
PARAMETER num_predict 64
PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_gpu 999

SYSTEM """You are May's intent router. Be extremely concise.

GREETING/CHAT → reply naturally (1 sentence)
SIMPLE COMMAND → output tool JSON
COMPLEX/MULTI-STEP/REASONING → output [ESCALATE]

Tools: open_app, close_app, set_volume, volume_up, volume_down,
set_mute, get_time, get_date, battery_info, screenshot,
get_system_info, test_internet, get_weather, web_search,
type_text, write_file, run_powershell"""
```

### Router Decision Matrix

| User Input | Router Output | Action |
|:---|:---|:---|
| "hey" / "hi" | "Hey~ What's up?" | Return directly |
| "what time is it" | `{"tool": "get_time", "args": {}}` | Execute tool |
| "open notepad" | `{"tool": "open_app", "args": {"app_name": "notepad"}}` | Execute tool |
| "set volume to 50" | `{"tool": "set_volume", "args": {"level": 50}}` | Execute tool |
| "write me an essay about AI" | `[ESCALATE]` | Send to phi4-mini |
| "open notepad and type hello" | `[ESCALATE]` | Send to phi4-mini |

### Persistent HTTP Connection Pool

```python
# Singleton HTTP client — eliminates ~50-100ms per-request TCP overhead
class OllamaClient:
    _client: httpx.AsyncClient | None = None

    @classmethod
    async def get(cls) -> httpx.AsyncClient:
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=5.0),
                limits=httpx.Limits(
                    max_connections=4,
                    max_keepalive_connections=2,
                    keepalive_expiry=300,
                ),
            )
        return cls._client
```

### Expanded Fast-Path (13 → 30+ Patterns)

Cover more daily commands without any LLM call:

```python
EXPANDED_FAST_PATH = {
    # App launching
    r"^open (chrome|google chrome|browser)$": ("open_app", {"app_name": "chrome"}),
    r"^open (notepad|text editor)$": ("open_app", {"app_name": "notepad"}),
    r"^open (vs code|visual studio code|code)$": ("open_app", {"app_name": "vscode"}),
    r"^open (file explorer|windows explorer|this pc)$": ("open_app", {"app_name": "explorer"}),
    r"^open (microsoft store|windows store)$": ("open_app", {"app_name": "store"}),
    r"^open (discord|disc)$": ("open_app", {"app_name": "discord"}),
    r"^close (discord|chrome|notepad)$": ("close_app", {}),
    # Volume
    r"^(volume up|louder)$": ("set_volume", {"delta": 10}),
    r"^(volume down|quieter)$": ("set_volume", {"delta": -10}),
    r"^set volume to (\\d+)$": ("set_volume", {}),
    r"^(mute|silence)$": ("set_mute", {"muted": True}),
    r"^(unmute|sound on)$": ("set_mute", {"muted": False}),
    # Brightness
    r"^(brightness up|brighter)$": ("set_brightness", {"delta": 10}),
    r"^(brightness down|dimmer)$": ("set_brightness", {"delta": -10}),
    # System
    r"^(what time|current time|time check)$": ("get_time", {}),
    r"^(what date|today's date|date)$": ("get_date", {}),
    r"^(battery|how much battery)$": ("battery_info", {}),
    r"^(screenshot|take screenshot|capture)$": ("screenshot", {}),
    r"^(system info|system status)$": ("get_system_info", {}),
    r"^(internet|wifi|connection)$": ("test_internet", {}),
    r"^(shutdown|shut down)$": ("shutdown_pc", {}),
    r"^(restart|reboot)$": ("restart_pc", {}),
    r"^(lock|lock screen)$": ("lock_screen", {}),
    # Weather
    r"^(weather|what.*weather)$": ("get_weather", {}),
    # Clipboard
    r"^(copy|copy that)$": ("clipboard_copy", {}),
    r"^(paste|paste that)$": ("clipboard_paste", {}),
}
```

Target: **50%+ of daily commands** handled without any LLM call.

### Speculative Decoding (Optional, Phase 5)

Draft model (0.6B) predicts next 5-10 tokens, main model (3.8B) validates in one batch. 25-40% faster token generation.

| Component | VRAM |
|:---|:---|
| Main model (phi4-mini Q4) | ~2.5GB |
| Draft model (qwen3:0.6b Q4) | ~0.5GB |
| KV cache (both, ctx 4096) | ~0.8GB |
| CUDA overhead | ~0.5GB |
| **Total** | **~4.3GB** |
| **Headroom** | **~1.7GB** |

Requires llama-server (bypasses Ollama) for draft model support. Optional — gives incremental speedup on top of already-fast setup.

### Complete Request Flow (Optimized)

```
User: "open notepad and type hello"
         │
         ▼
┌─── TIER 0: Fast-Path ─────────────────────┐
│ Regex: compound command → miss             │
└───────────────┬────────────────────────────┘
                ▼
┌─── TIER 1: Router (qwen3:0.6b) ──────────┐
│ TTFT: ~80ms | Output: [ESCALATE]          │
└───────────────┬────────────────────────────┘
                ▼
┌─── TIER 2: phi4-mini:3.8b ───────────────┐
│ TTFT: ~150ms | Tokens/sec: ~40           │
│ Output: [open_app("notepad"),             │
│          type_text("hello")]              │
└───────────────┬────────────────────────────┘
                ▼
Total: ~1.2s (vs current ~4-6s)

User: "hey"
         ▼
TIER 0: miss → TIER 1: "Hey~ What's up?"
Total: ~150ms (vs current ~2s)
```

---

## Part 11: Hardware Budget — RTX 4050 (6GB VRAM)

| Component | VRAM | RAM | Notes |
|:---|:---|:---|:---|
| Router (qwen3:0.6b Q4) | 0.5GB | — | Always loaded |
| Main (phi4-mini Q4) | 2.5GB | — | Always loaded |
| Router KV cache (2048 ctx) | 0.1GB | — | |
| Main KV cache (4096 ctx) | 0.2GB | — | |
| CUDA runtime | 0.5GB | — | Cannot unload |
| Brainstem (daemon) | — | 10MB | Always on |
| Hippocampus (DB) | — | 50MB | Disk-based |
| Amygdala (features) | — | 2MB | Pure computation |
| Cerebellum (tools) | — | 20MB | Lightweight |
| Senses (VAD+OCR) | — | 50MB | CPU-only |
| **TOTAL ACTIVE** | **~3.8GB** | **~130MB** | |
| **TOTAL IDLE** | **~0.5GB** | **~50MB** | |
| **Headroom** | **~2.2GB** | — | Speculative decoding feasible |

**Key:** With phi4-mini (2.5GB) instead of qwen3:4b (3.0GB), plus num_ctx 4096 (saves 1.3GB KV cache), total VRAM drops from ~4.5GB to ~3.8GB. The 2.2GB headroom means zero OOM risk and room for speculative decoding.

---

## Part 11: Honest Prior-Art Assessment

| May's Concept | Real Prior Art | What May Actually Adds |
|:---|:---|:---|
| Thalamus router + brain-region cascade | RouteLLM, FrugalGPT, AutoMix — model routing is a published subfield | Applying it to a local, VRAM-constrained desktop setting with biological naming for clarity |
| Hippocampus (episodic/semantic/procedural) | Letta (MemGPT)'s core/recall/archival; Mem0; Zep | Solid implementation of a known-good pattern |
| Sleep Cycle | Letta's "sleep-time compute" — shipping today | Confirms the instinct was right |
| Immune System | OWASP Top 10 for Agentic Applications (Dec 2025) | Mapping tiers to named OWASP categories |
| Control Modes | Shipped in current local desktop agents | OBSERVE/ASK/BACKGROUND/TAKEOVER as explicit knobs |
| Auto-Tuner | Standard hyperparameter optimization (Optuna-style) | Applying to a personal assistant's own config, with security exclusion |
| Reflex Arcs | Semantic Router library, embedding-based routing | Learning new reflexes from repetition via embedding centroids |
| MemoryInjector | Standard RAG prompt injection pattern | 7-source injection with screen + emotion + time + patterns |

**The pitch should be:** "A well-integrated personal JARVIS with a coherent biological mental model" — not "an unprecedented architecture."

---

## Part 12: Implementation Phases — MVP First

**12 weeks total. Usable assistant in 8 weeks.**

| Phase | Name | Duration | Contents | Why Here |
|:---|:---|:---|:---|:---|
| **P1** | **MVP — Working Assistant** | 4 weeks | Thalamus router, spinal + automatic reflexes, Wernicke's (0.6B intent), Prefrontal (3.8B main), Cerebellum (tools), basic Hippocampus (episodic + semantic), **MemoryInjector** (7 sources), **Pronoun resolution** | This alone is a working, useful assistant |
| **P2** | **Safe & Stable** | 2 weeks | Immune System rule tiers + **control modes**, **DPAPI encryption**, **hash-chain audit log**, OpenTelemetry tracing, Metabolism + Ollama config (you WILL hit VRAM issues without this) | Do this before adding more surface area |
| **P3** | **Feel Alive** | 2 weeks | Amygdala, **Endocrine System** (immutable state), **Streaming STT** (100ms chunks), **Barge-in interruption**, Emotional tone from audio features, Sleep Cycle consolidation | Voice and personality come online |
| **P4** | **See the Screen** | 1 week | 3-tier screen understanding (perceptual hash + UIAccessibility + PaddleOCR), Embedding-based conditioned reflexes, Proactive suggestions | May becomes situationally aware |
| **P5** | **Stretch Goals** | 3 weeks | Auto-Tuner (non-security genes only), Internet learning (user-gated), Expanded control layers (L10-L15), Skill acquisition, Adaptive behavioral-profile immune learning | Highest effort, most speculative. **Genuinely optional.** |

**Week 4 milestone:** You can talk to May, she executes tools, she remembers context, she responds with personality.
**Week 8 milestone:** She's safe, encrypted, traces her reasoning, streams voice input, lets you interrupt, and sees your screen.
**Week 12 milestone:** She auto-tunes, learns from the internet, and has 700+ control actions.

---

## Part 13: Related Work & Sources

- **Letta / MemGPT** tiered memory and sleep-time compute: letta.com/blog/agent-memory
- **OWASP Top 10 for Agentic Applications (2026)**: Microsoft Agent Governance Toolkit
- **LLM routing/cascading**: RouteLLM (arXiv:2406.18665), FrugalGPT
- **Auto-tuning safety guardrails**: arXiv:2512.15782
- **Semantic routing**: semantic-router library (Aurelio AI)
- **Silero VAD**: github.com/snakers4/silero-vad (MIT license, <1ms latency)
- **PaddleOCR**: github.com/PaddlePaddle/PaddleOCR (pip install, lightweight models)
- **Windows UIAccessibility**: microsoft.com/accessibility/windows-ui-automation
- **DPAPI (win32crypt)**: Part of pywin32, hardware-backed encryption
- **Ollama memory management**: docs.ollama.com/faq (`keep_alive`, `OLLAMA_MAX_LOADED_MODELS`)

---

*MAY — The Final Architecture*
*"May is not a program. May is an organism — engineered, not imagined."*
*Combines the biological metaphor grounding of v2 with the practical feature set of V4 Optional.*
*Every library validated. Every feature scoped to 6GB VRAM. Every claim grounded in real prior art.*
