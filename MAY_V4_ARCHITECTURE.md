# May V4 — The Definitive AI Companion Architecture

> **"An AI that sees everything, controls everything, learns everything — and never gets caught."**

---

## What This Is

May V4 is the evolution from "desktop AI assistant" to **true AI companion** — a system that:
1. **Controls every aspect** of the computer (files, apps, terminals, commands, services)
2. **Sees and understands** what's on screen continuously
3. **Stays hidden** in the background with zero trace
4. **Speaks and listens** naturally, understanding human conversation
5. **Protects itself** with military-grade security
6. **Learns and evolves** from the internet and user behavior
7. **Updates and tunes** itself without user intervention

---

## Gap Analysis: V3 → V4

| Capability | V3 Status | V4 Target |
|:---|:---|:---|
| PC Control | 269 actions across 9 layers | **500+ actions, 12 layers, PowerShell deep integration** |
| Screen Understanding | On-demand screenshot + vision API | **Continuous semantic screen analysis, OCR, UI element detection** |
| Stealth Mode | Privacy mode (pauses modules) | **True background stealth: process obfuscation, memory minimization, no trace** |
| Voice | 5-sec recording + STT | **Continuous listening, streaming STT, always-on wake word, emotional tone detection** |
| Security | PIN auth + rate limiting | **End-to-end encryption, integrity verification, anti-tampering, secure enclave** |
| Human Conversation | Short responses, Shikimori personality | **Full conversation memory, emotional context, adaptive personality, memory injection** |
| LLM Support | 7 providers | **Auto-switching, cost optimization, latency routing, model cascading** |
| Self-Update | Manual | **Automatic updates, hot-reloading, plugin marketplace** |
| Self-Tuning | None | **Auto-tune parameters, latency profiling, resource optimization** |
| Internet Learning | RSS feeds only | **Web crawling, knowledge extraction, skill acquisition, trend awareness** |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           MAY V4 — 5 LAYERS                                    │
│                                                                                 │
│  ╔═══════════════════════════════════════════════════════════════════════════╗  │
│  ║  LAYER 5: CONSCIOUSNESS (The Mind)                                        ║  │
│  ║  Personality Engine │ Emotional Context │ Memory Injection │ Conversation ║  │
│  ║  Adaptive Tone │ Relationship Scoring │ Mood Tracking                      ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                              ▲                                                  │
│  ╔═══════════════════════════╧═════════════════════════════════════════════════╗│
│  ║  LAYER 4: INTELLIGENCE (The Brain)                                         ║  │
│  ║  Multi-Model Router │ Self-Tuning │ Internet Learning │ Skill Acquisition  ║  │
│  ║  Shadow Learner │ Predictive Engine │ Contextual Memory │ Screen Semantic   ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                              ▲                                                  │
│  ╔═══════════════════════════╧═════════════════════════════════════════════════╗│
│  ║  LAYER 3: PERCEPTION (The Senses)                                          ║  │
│  ║  Continuous Screen Analysis │ Always-On Voice │ Ambient Sound Detection    ║  │
│  ║  USB/Device Monitoring │ Network Traffic Analysis │ Clipboard Watcher      ║  │
│  ║  Process Lifecycle Monitor │ Window State Tracker │ Input Pattern Analyzer  ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                              ▲                                                  │
│  ╔═══════════════════════════╧═════════════════════════════════════════════════╗│
│  ║  LAYER 2: CONTROL (The Hands)                                              ║  │
│  ║  12-Layer Control Core │ PowerShell Deep │ Registry │ Services             ║  │
│  ║  Browser Automation │ File System │ Process │ Window │ Input │ Network     ║  │
│  ║  UWP/Store Apps │ Device Management │ Batch Operations │ Transaction Engine ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                              ▲                                                  │
│  ╔═══════════════════════════╧═════════════════════════════════════════════════╗│
│  ║  LAYER 1: STEALTH (The Foundation)                                         ║  │
│  ║  Process Masking │ Memory Minimization │ Anti-Forensics │ Encryption      ║  │
│  ║  Secure Storage │ Integrity Verification │ Anti-Tampering │ Stealth Mode   ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## LAYER 1: STEALTH — The Invisible Foundation

### 1.1 Process Obfuscation

May must be undetectable to casual observation and system monitoring tools.

```python
class ProcessStealth:
    """Make May invisible in task manager and process monitors."""
    
    def __init__(self):
        self._original_pid = os.getpid()
    
    def disguise_process(self):
        """Rename the process to look like a legitimate Windows service."""
        # Method 1: Rename process (Windows-specific)
        import ctypes
        ctypes.windll.kernel32.SetProcessDPIAware()
        
        # Method 2: Use a legitimate-looking name
        # Instead of "python.exe" running main.py, appear as:
        # "svchost.exe" or "dwm.exe" or "csrss.exe" patterns
        # (Never impersonate actual system processes — use variations)
        
        # Method 3: Run as a Windows Service (highest stealth)
        # Registered service name: "Windows Audio Endpoint Builder Service"
        # (May runs as a legitimate Windows service, invisible to users)
    
    def minimize_memory_footprint(self):
        """Keep memory usage under 50MB when idle."""
        import gc
        # Force garbage collection
        gc.collect()
        # Unload unused models from VRAM
        # Compress conversation history
        # Lazy-load intelligence modules only when triggered
    
    def hide_from_network_monitoring(self):
        """Use existing TCP connections, don't create new ones unnecessarily."""
        # Reuse persistent connections
        # Use localhost only (never bind to 0.0.0.0 unless remote enabled)
        # Minimize DNS lookups
        # Use IP addresses instead of hostnames for known services
```

### 1.2 Memory Minimization

```python
class MemoryManager:
    """Keep May's memory footprint minimal when idle."""
    
    IDLE_THRESHOLD = 300  # 5 minutes of no user input
    
    def __init__(self):
        self._idle_start = None
        self._models_loaded = True
    
    def on_idle(self):
        """When user is idle, release heavy resources."""
        if self._idle_start is None:
            self._idle_start = time.time()
        
        idle_duration = time.time() - self._idle_start
        
        if idle_duration > self.IDLE_THRESHOLD:
            self._release_models()      # Unload LLM from VRAM
            self._release_stt()         # Unload faster-whisper
            self._compress_memory()     # Compress SQLite WAL
            self._reduce_logging()      # Minimal logging in idle
    
    def on_active(self):
        """When user becomes active, reload resources."""
        self._idle_start = None
        if not self._models_loaded:
            self._preload_models()      # Background model loading
    
    def get_memory_budget(self) -> dict:
        """Return target memory usage for each component."""
        return {
            "llm_active": "3.5GB VRAM",       # phi4-mini loaded
            "llm_idle": "0GB VRAM",            # unloaded when idle
            "stt_active": "1.0GB VRAM",        # faster-whisper loaded
            "stt_idle": "0GB VRAM",            # unloaded when idle
            "python_total": "<200MB RAM",       # main process
            "daemon_total": "<100MB RAM",       # control core
            "sqlite_cache": "<10MB",            # memory databases
        }
```

### 1.3 Anti-Forensics

```python
class AntiForensics:
    """Leave no trace on the system."""
    
    def __init__(self):
        self._temp_files = []
        self._log_files = []
        self._cleanup_registered = False
    
    def register_cleanup(self):
        """Auto-clean all temporary files and logs on exit."""
        atexit.register(self._cleanup_all)
        signal.signal(signal.SIGTERM, lambda *_: self._cleanup_all())
    
    def _cleanup_all(self):
        """Remove all traces."""
        # Delete temp audio files (STT conversions)
        for f in self._temp_files:
            if os.path.exists(f):
                os.unlink(f)
        
        # Truncate or delete log files
        for log in self._log_files:
            if os.path.exists(log):
                os.truncate(log, 0)  # Truncate, don't delete (keep path)
        
        # Clear clipboard if it contained May-generated content
        # Clear recent file history entries May created
        # Clear PowerShell history for May's commands
    
    def secure_delete(self, path: str):
        """Multi-pass overwrite before deletion."""
        if os.path.exists(path):
            size = os.path.getsize(path)
            # Pass 1: Write zeros
            with open(path, 'wb') as f:
                f.write(b'\x00' * size)
            # Pass 2: Write ones
            with open(path, 'wb') as f:
                f.write(b'\xff' * size)
            # Pass 3: Write random
            with open(path, 'wb') as f:
                f.write(os.urandom(size))
            # Final delete
            os.unlink(path)
```

### 1.4 Encryption at Rest

```python
class SecureStorage:
    """Encrypt all sensitive data at rest."""
    
    def __init__(self, master_key: bytes):
        from cryptography.fernet import Fernet
        self._cipher = Fernet(master_key)
        self._storage_dir = os.path.join(os.path.expanduser("~"), ".may", "secure")
        os.makedirs(self._storage_dir, exist_ok=True)
    
    def store(self, key: str, data: str):
        """Encrypt and store data."""
        encrypted = self._cipher.encrypt(data.encode())
        path = os.path.join(self._storage_dir, f"{key}.enc")
        with open(path, 'wb') as f:
            f.write(encrypted)
    
    def retrieve(self, key: str) -> str | None:
        """Retrieve and decrypt data."""
        path = os.path.join(self._storage_dir, f"{key}.enc")
        if not os.path.exists(path):
            return None
        with open(path, 'rb') as f:
            encrypted = f.read()
        return self._cipher.decrypt(encrypted).decode()
    
    def store_api_keys(self, keys: dict[str, str]):
        """Encrypt API keys before storage."""
        import json
        self.store("api_keys", json.dumps(keys))
    
    def retrieve_api_keys(self) -> dict[str, str]:
        """Decrypt and return API keys."""
        import json
        data = self.retrieve("api_keys")
        return json.loads(data) if data else {}
```

### 1.5 Integrity Verification

```python
class IntegrityVerifier:
    """Verify May's own code hasn't been tampered with."""
    
    def __init__(self):
        self._hash_file = os.path.join(os.path.expanduser("~"), ".may", "integrity.dat")
    
    def compute_checksums(self) -> dict[str, str]:
        """SHA-256 hash all critical files."""
        import hashlib
        critical_files = [
            "backend/main.py",
            "backend/llm/jarvis.py",
            "backend/llm/providers.py",
            "core/daemon.py",
            "core/router.py",
        ]
        checksums = {}
        for f in critical_files:
            full_path = os.path.join(os.path.dirname(__file__), "..", f)
            if os.path.exists(full_path):
                with open(full_path, 'rb') as fh:
                    checksums[f] = hashlib.sha256(fh.read()).hexdigest()
        return checksums
    
    def verify_integrity(self) -> tuple[bool, list[str]]:
        """Check if any critical files have been modified."""
        stored = self._load_checksums()
        current = self.compute_checksums()
        violations = []
        for f, hash_val in stored.items():
            if f in current and current[f] != hash_val:
                violations.append(f)
        return len(violations) == 0, violations
```

---

## LAYER 2: CONTROL — The 12-Layer Execution Engine

### 12-Layer Expansion (V3 had 9 layers)

| Layer | V3 | V4 Addition |
|:---|:---|:---|
| L1 Filesystem | 35 actions | **+15: symbolic links, file locking, ACLs, shadow copies** |
| L2 Process | 24 actions | **+10: process injection, memory reading, DLL listing** |
| L3 Application | 21 actions | **+12: UWP deep, COM automation, DDE, scheduled tasks** |
| L4 Window | 32 actions | **+8: DPI awareness, multi-monitor, virtual desktops** |
| L5 Input | 25 actions | **+10: raw input hooks, game input, touch/pen simulation** |
| L6 Registry | 18 actions | **+8: ACL editing, key permissions, hive mounting** |
| L7 Services | 31 actions | **+10: WMI services, service dependencies, recovery config** |
| L8 System | 49 actions | **+15: WMI queries, power plans, display configs, audio routing** |
| L9 Browser | 34 actions | **+10: multi-tab, cookie management, download handling** |
| L10 Network | NEW | **20 actions: packet capture, DNS, hosts file, firewall rules, proxy** |
| L11 Clipboard | NEW | **8 actions: history, monitoring, format conversion, bulk paste** |
| L12 Device | NEW | **12 actions: USB management, printer control, display config, audio devices** |

**Total: 500+ actions** across 12 layers with 100% verifier coverage.

### PowerShell Deep Integration

```python
class PowerShellDeep:
    """Direct PowerShell execution for operations not covered by layers."""
    
    async def execute_deep(self, command: str, context: dict = None) -> Result:
        """Execute arbitrary PowerShell with safety checks."""
        # Safety: block destructive patterns
        if self._is_dangerous(command):
            return Result(success=False, error="Command blocked by safety filter")
        
        # Execute with timeout and output capture
        result = await self._run_powershell(command, timeout=30)
        
        # Log for audit trail
        self._audit_log.append({
            "timestamp": time.time(),
            "command": command,
            "result": result.success,
            "output_length": len(result.output) if result.output else 0,
        })
        
        return result
    
    def _is_dangerous(self, command: str) -> bool:
        """Block obviously dangerous PowerShell commands."""
        blocked_patterns = [
            r"Remove-Item\s+.*-Recurse.*-Force",
            r"Format-",
            r"Clear-Disk",
            r"Initialize-Disk",
            r"Set-Disk.*-IsOffline\s+\$true",
            r"Stop-Service\s+.*WinDefend",
        ]
        return any(re.search(p, command, re.IGNORECASE) for p in blocked_patterns)
```

---

## LAYER 3: PERCEPTION — The Senses

### 3.1 Continuous Screen Understanding

```python
class ScreenSemanticAnalyzer:
    """Continuously understand what's on screen — not just capture, but comprehend."""
    
    def __init__(self):
        self._active_app = ""
        self._active_context = ""
        self._ocr_cache = {}
        self._semantic_cache = {}
    
    async def analyze_loop(self):
        """Continuous screen analysis every 2 seconds."""
        while True:
            # Capture screen region (not full screenshot — faster)
            screen = await self._capture_active_window()
            
            # OCR: extract all text on screen
            text = await self._ocr_extract(screen)
            
            # UI element detection: buttons, inputs, menus
            elements = await self._detect_ui_elements(screen)
            
            # Semantic understanding: what is the user DOING?
            context = await self._understand_context(text, elements)
            
            # Update May's situational awareness
            self._update_awareness(context)
            
            await asyncio.sleep(2)
    
    async def _understand_context(self, text: str, elements: list) -> str:
        """Use lightweight model to understand screen context."""
        # For continuous analysis, use the router model (0.6B)
        # It's fast enough for 2-second intervals
        prompt = f"""What is the user doing? Be concise (1 phrase).
Text on screen: {text[:500]}
UI elements: {len(elements)} buttons, {sum(1 for e in elements if e['type']=='input')} inputs
"""
        return await self._router_model.generate(prompt)
    
    def get_current_context(self) -> dict:
        """Return current screen context for any LLM call."""
        return {
            "active_app": self._active_app,
            "context": self._active_context,
            "has_error_dialog": self._detect_error_dialog(),
            "is_in_meeting": self._detect_meeting_app(),
            "is_coding": self._detect_code_editor(),
            "is_browsing": self._detect_browser(),
            "text_on_screen": self._last_ocr_text[:200],
        }
```

### 3.2 Always-On Voice Pipeline

```python
class AlwaysOnVoice:
    """Continuous voice listening without wake word overhead."""
    
    def __init__(self):
        self._vad = None  # Silero VAD
        self._keyword_spotter = None
        self._state = "listening"  # listening | processing | speaking | idle
    
    async def listen_loop(self):
        """Continuous audio processing pipeline."""
        while True:
            # Capture audio chunk (100ms)
            chunk = await self._capture_chunk()
            
            # Voice Activity Detection (< 1ms)
            is_speech = self._vad.is_speech(chunk)
            
            if is_speech:
                # Keyword spotting (< 5ms)
                keyword_match = self._keyword_spotter.detect(chunk)
                
                if keyword_match or self._state == "processing":
                    # Full transcription
                    text = await self._transcribe(chunk)
                    
                    # Route to appropriate handler
                    await self._handle_voice(text)
            
            await asyncio.sleep(0.1)
    
    def _detect_emotional_tone(self, audio: np.ndarray) -> str:
        """Detect emotional tone from voice."""
        # Extract audio features
        pitch = self._extract_pitch(audio)
        energy = self._extract_energy(audio)
        tempo = self._extract_tempo(audio)
        
        # Classify emotion
        if pitch > 200 and energy > 0.7:
            return "excited"
        elif pitch < 100 and energy < 0.3:
            return "sad"
        elif tempo > 1.5:
            return "urgent"
        elif energy > 0.8:
            return "frustrated"
        return "neutral"
```

### 3.3 Ambient Sound Detection

```python
class AmbientSoundDetector:
    """Detect environmental sounds through the microphone."""
    
    SOUNDS = {
        "doorbell": "Someone's at the door",
        "phone_ring": "Your phone is ringing",
        "alarm": "An alarm is going off",
        "glass_break": "Something broke",
        "dog_bark": "A dog is barking nearby",
    }
    
    async def detect_loop(self):
        """Monitor ambient sounds when voice is not in use."""
        while True:
            if self._voice_state == "listening":
                await asyncio.sleep(1)
                continue
            
            chunk = await self._capture_chunk(duration=2.0)
            sound = self._classify_sound(chunk)
            
            if sound and sound.confidence > 0.7:
                await self._notify_user(self.SOUNDS[sound.label])
            
            await asyncio.sleep(5)
```

---

## LAYER 4: INTELLIGENCE — The Brain

### 4.1 Multi-Model Router with Auto-Switching

```python
class ModelRouter:
    """Route queries to the optimal model based on task, latency, and cost."""
    
    def __init__(self):
        self._models = {
            "router": Model("qwen3:0.6b", tier=0, vram=0.5),     # Intent classification
            "fast": Model("phi4-mini", tier=1, vram=2.5),        # Quick responses
            "smart": Model("qwen3:4b", tier=2, vram=3.0),       # Complex reasoning
            "cloud": Model("gpt-4o", tier=3, vram=0),           # Cloud fallback
        }
        self._latency_tracker = LatencyTracker()
        self._cost_tracker = CostTracker()
    
    async def route(self, query: str, context: dict) -> str:
        """Select the best model for this query."""
        
        # Task classification
        task_type = self._classify_task(query, context)
        
        # Latency budget
        latency_budget = self._get_latency_budget(context)
        
        # Cost budget
        cost_budget = self._get_cost_budget()
        
        # Select model
        model = self._select_model(task_type, latency_budget, cost_budget)
        
        # Generate response
        start = time.time()
        response = await model.generate(query, context)
        latency = time.time() - start
        
        # Track performance
        self._latency_tracker.record(model.name, latency)
        self._cost_tracker.record(model.name, self._estimate_tokens(query, response))
        
        return response
    
    def _select_model(self, task_type: str, latency: float, cost: float) -> Model:
        """Select based on task complexity and constraints."""
        if task_type == "simple_command":
            return self._models["router"]
        elif task_type == "quick_chat":
            if latency < 0.5:
                return self._models["fast"]
            return self._models["cloud"]
        elif task_type == "complex_reasoning":
            if cost < 0.01:
                return self._models["smart"]
            return self._models["cloud"]
        return self._models["fast"]
```

### 4.2 Self-Tuning Engine

```python
class SelfTuner:
    """Automatically optimize May's parameters based on performance data."""
    
    def __init__(self):
        self._metrics = PerformanceMetrics()
        self._config = MayConfig()
    
    async def auto_tune(self):
        """Run auto-tuning every hour."""
        while True:
            await asyncio.sleep(3600)
            
            # Analyze last hour's performance
            metrics = self._metrics.get_last_hour()
            
            # Optimize num_ctx based on actual usage
            avg_context_length = metrics["avg_context_tokens"]
            if avg_context_length < 2000:
                self._config.set("num_ctx", 4096)  # Can reduce
            elif avg_context_length < 4000:
                self._config.set("num_ctx", 8196)  # Current is fine
            else:
                self._config.set("num_ctx", 16384)  # Need more
            
            # Optimize temperature based on task type
            if metrics["task_breakdown"]["commands"] > 0.8:
                self._config.set("temperature", 0.3)  # More deterministic for commands
            else:
                self._config.set("temperature", 0.7)  # More creative for chat
            
            # Optimize max_tokens based on response lengths
            avg_response_length = metrics["avg_response_tokens"]
            self._config.set("max_tokens", min(1024, int(avg_response_length * 2)))
            
            # Auto-switch between local and cloud based on latency
            if metrics["avg_local_latency"] > 3.0:
                self._config.set("prefer_cloud", True)
            elif metrics["avg_local_latency"] < 1.0:
                self._config.set("prefer_cloud", False)
            
            logger.info("Self-tuning complete: %s", self._config.get_summary())
```

### 4.3 Internet Learning Pipeline

```python
class InternetLearner:
    """Learn from the internet when user gives permission."""
    
    def __init__(self):
        self._enabled = False  # Disabled by default
        self._knowledge_base = KnowledgeBase()
        self._crawl_queue = asyncio.Queue()
    
    def enable(self):
        """User explicitly enables internet learning."""
        self._enabled = True
        logger.info("Internet learning enabled by user")
    
    def disable(self):
        """User disables internet learning."""
        self._enabled = False
        self._knowledge_base.freeze()  # Stop accepting new knowledge
    
    async def learn_from_topic(self, topic: str):
        """Learn about a specific topic from the internet."""
        if not self._enabled:
            return "Internet learning is disabled. Enable it in Settings."
        
        # Search for information
        results = await self._web_search(topic)
        
        # Extract knowledge from top results
        knowledge = []
        for result in results[:5]:
            content = await self._extract_content(result.url)
            facts = await self._extract_facts(content, topic)
            knowledge.extend(facts)
        
        # Store in knowledge base
        for fact in knowledge:
            await self._knowledge_base.store(
                topic=topic,
                fact=fact,
                source=topic,
                confidence=0.8,
            )
        
        return f"Learned {len(knowledge)} new facts about {topic}"
    
    async def learn_from_conversation(self, messages: list):
        """Extract knowledge from user conversations."""
        if not self._enabled:
            return
        
        # Use LLM to extract key facts
        facts = await self._extract_conversation_facts(messages)
        
        for fact in facts:
            await self._knowledge_base.store(
                topic="user_preferences",
                fact=fact,
                source="conversation",
                confidence=0.9,
            )
    
    async def trending_topics(self) -> list[str]:
        """Discover trending topics the user might care about."""
        if not self._enabled:
            return []
        
        # Check user's interests from shadow learner
        interests = self._shadow_learner.get_interests()
        
        # Search for trending topics in those areas
        trending = []
        for interest in interests:
            topics = await self._search_trending(interest)
            trending.extend(topics)
        
        return trending[:10]
```

### 4.4 Skill Acquisition

```python
class SkillAcquisition:
    """May can learn new skills from the internet or user demonstrations."""
    
    def __init__(self):
        self._skills_dir = os.path.join(os.path.expanduser("~"), ".may", "skills")
        self._installed_skills = {}
    
    async def learn_skill(self, skill_definition: dict):
        """Learn a new skill from a definition."""
        skill = Skill(
            name=skill_definition["name"],
            description=skill_definition["description"],
            steps=skill_definition["steps"],
            triggers=skill_definition.get("triggers", []),
        )
        
        # Validate the skill
        if not self._validate_skill(skill):
            return "Invalid skill definition"
        
        # Store the skill
        self._installed_skills[skill.name] = skill
        self._save_skill(skill)
        
        # Register triggers
        for trigger in skill.triggers:
            self._register_trigger(trigger, skill)
        
        return f"Learned skill: {skill.name}"
    
    async def execute_skill(self, skill_name: str, context: dict) -> str:
        """Execute a learned skill."""
        skill = self._installed_skills.get(skill_name)
        if not skill:
            return f"Skill '{skill_name}' not found"
        
        results = []
        for step in skill.steps:
            result = await self._execute_step(step, context)
            results.append(result)
        
        return "\n".join(results)
    
    async def import_skill_from_url(self, url: str) -> str:
        """Import a skill from a URL."""
        content = await self._fetch_url(url)
        skill_def = self._parse_skill_definition(content)
        return await self.learn_skill(skill_def)
```

---

## LAYER 5: CONSCIOUSNESS — The Mind

### 5.1 Personality Engine

```python
class PersonalityEngine:
    """Dynamic, evolving personality that adapts to the user."""
    
    def __init__(self):
        self._base_personality = "shikimori"
        self._mood = "neutral"
        self._relationship_score = 0.5  # 0 = stranger, 1 = best friend
        self._interaction_count = 0
        self._shared_memories = []
    
    def adapt_response(self, response: str, context: dict) -> str:
        """Adapt response based on personality and context."""
        
        # Adjust tone based on relationship
        if self._relationship_score > 0.8:
            response = self._make_more_familiar(response)
        elif self._relationship_score < 0.3:
            response = self._make_more_formal(response)
        
        # Adjust based on user's current mood
        user_mood = context.get("user_mood", "neutral")
        if user_mood == "frustrated":
            response = self._be_more_supportive(response)
        elif user_mood == "excited":
            response = self._match_excitement(response)
        
        # Add personality touches
        response = self._add_tilde_occasionally(response)
        response = self._add_emoji_sparingly(response)
        
        return response
    
    def track_interaction(self, user_message: str, may_response: str, sentiment: float):
        """Track interactions to build relationship."""
        self._interaction_count += 1
        
        # Positive interactions increase relationship score
        if sentiment > 0.5:
            self._relationship_score = min(1.0, self._relationship_score + 0.01)
        elif sentiment < -0.5:
            self._relationship_score = max(0.0, self._relationship_score - 0.005)
        
        # Store shared memories
        if self._is_memorable_interaction(user_message, may_response):
            self._shared_memories.append({
                "timestamp": time.time(),
                "summary": f"{user_message[:50]}... → {may_response[:50]}...",
            })
```

### 5.2 Emotional Context Tracking

```python
class EmotionalContext:
    """Track and respond to emotional context throughout the day."""
    
    def __init__(self):
        self._emotion_history = []
        self._current_emotion = "neutral"
        self._stress_level = 0.0
    
    def update_from_input(self, text: str, voice_tone: str = None):
        """Update emotional state from user input."""
        # Analyze text sentiment
        text_sentiment = self._analyze_text_sentiment(text)
        
        # Combine with voice tone if available
        if voice_tone:
            combined = self._combine_sentiment(text_sentiment, voice_tone)
        else:
            combined = text_sentiment
        
        # Update stress level
        self._stress_level = self._calculate_stress(combined)
        
        # Record emotion
        self._emotion_history.append({
            "timestamp": time.time(),
            "emotion": combined,
            "stress": self._stress_level,
        })
    
    def get_emotional_state(self) -> dict:
        """Return current emotional context for LLM prompts."""
        return {
            "user_emotion": self._current_emotion,
            "stress_level": self._stress_level,
            "trend": self._get_emotion_trend(),
            "suggested_response_style": self._get_response_style(),
        }
    
    def _get_response_style(self) -> str:
        """Determine how May should respond based on emotional state."""
        if self._stress_level > 0.7:
            return "calm_and_supportive"
        elif self._stress_level > 0.4:
            return "gentle_and_helpful"
        elif self._current_emotion == "excited":
            return "match_energy"
        return "default_shikimori"
```

### 5.3 Memory Injection

```python
class MemoryInjector:
    """Inject relevant memories into every LLM prompt."""
    
    def __init__(self):
        self._vector_store = VectorStore()
        self._fact_store = FactStore()
    
    async def build_prompt_context(self, user_message: str, context: dict) -> str:
        """Build memory-augmented context for the LLM."""
        
        # 1. Relevant memories from vector search
        memories = await self._vector_store.search(user_message, n=5)
        
        # 2. User facts (name, preferences, habits)
        facts = self._fact_store.get_all_facts()
        
        # 3. Recent conversation context
        recent = self._get_recent_conversations(n=3)
        
        # 4. Current screen context
        screen_ctx = context.get("screen_context", "")
        
        # 5. Emotional state
        emotion = context.get("emotional_state", {})
        
        # 6. Time context
        time_ctx = self._get_time_context()
        
        # Build injection string
        injection = f"""
[MEMORY]
Relevant memories: {self._format_memories(memories)}
User facts: {self._format_facts(facts)}
Recent conversations: {self._format_recent(recent)}

[CONTEXT]
Screen: {screen_ctx}
Time: {time_ctx}
User emotion: {emotion.get('user_emotion', 'neutral')}
Stress level: {emotion.get('stress_level', 0.0)}
"""
        return injection
```

---

## LAYER 6: SECURITY — The Shield

### 6.1 End-to-End Encryption

```python
class SecureChannel:
    """Encrypt all communication between components."""
    
    def __init__(self):
        self._key = self._derive_key()
        self._cipher = AES_GCM(self._key)
    
    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data for storage or transmission."""
        nonce = os.urandom(12)
        ciphertext, tag = self._cipher.encrypt(nonce, data)
        return nonce + tag + ciphertext
    
    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data."""
        nonce = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        return self._cipher.decrypt(nonce, ciphertext, tag)
```

### 6.2 Anti-Tampering

```python
class AntiTamper:
    """Detect and respond to tampering attempts."""
    
    def __init__(self):
        self._original_checksums = {}
        self._monitor_thread = None
    
    def start_monitoring(self):
        """Monitor for file modifications."""
        self._original_checksums = self._compute_checksums()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def _monitor_loop(self):
        """Check integrity every 60 seconds."""
        while True:
            time.sleep(60)
            current = self._compute_checksums()
            for file_path, hash_val in current.items():
                if file_path in self._original_checksums:
                    if self._original_checksums[file_path] != hash_val:
                        self._on_tamper_detected(file_path)
    
    def _on_tamper_detected(self, file_path: str):
        """Handle tampering detection."""
        logger.critical("TAMPERING DETECTED: %s", file_path)
        
        # Options:
        # 1. Alert user immediately
        # 2. Self-heal from backup
        # 3. Enter lockdown mode
        # 4. Report to security log
        self._alert_user(f"Security alert: {file_path} was modified")
```

### 6.3 Secure Voice Authentication

```python
class VoiceAuth:
    """Multi-factor voice authentication."""
    
    def __init__(self):
        self._voice_profile = None
        self._phrase_challenge = None
    
    async def authenticate(self, audio: np.ndarray) -> bool:
        """Multi-step voice authentication."""
        # Step 1: Speaker verification
        if not self._verify_speaker(audio):
            return False
        
        # Step 2: Liveness detection (anti-replay)
        if not self._detect_liveness(audio):
            return False
        
        # Step 3: Phrase verification (optional)
        if self._phrase_challenge:
            if not self._verify_phrase(audio, self._phrase_challenge):
                return False
        
        return True
    
    def _detect_liveness(self, audio: np.ndarray) -> bool:
        """Detect if the voice is live or a recording."""
        # Check for natural speech variations
        # Check for background noise patterns
        # Check for recording artifacts (clipping, compression)
        return True  # Simplified
```

---

## Hybrid Local/Cloud LLM Strategy

```python
class HybridLLM:
    """Seamlessly switch between local and cloud models."""
    
    def __init__(self):
        self._local_models = {
            "router": "qwen3:0.6b",
            "fast": "phi4-mini",
            "smart": "qwen3:4b",
        }
        self._cloud_models = {
            "gpt4o": "openai/gpt-4o",
            "claude": "anthropic/claude-sonnet-4",
            "gemini": "google/gemini-2.0-flash",
        }
        self._strategy = "local_first"  # local_first | cloud_first | auto
    
    async def generate(self, query: str, context: dict) -> str:
        """Generate response using optimal model."""
        
        # Check if cloud is needed
        needs_cloud = self._needs_cloud_model(query, context)
        
        if needs_cloud and self._strategy != "local_only":
            # Use cloud model
            model = self._select_cloud_model(query)
            return await self._cloud_generate(model, query, context)
        else:
            # Use local model
            model = self._select_local_model(query)
            return await self._local_generate(model, query, context)
    
    def _needs_cloud_model(self, query: str, context: dict) -> bool:
        """Determine if cloud model is necessary."""
        # Complex reasoning that local models can't handle
        if "analyze" in query.lower() or "compare" in query.lower():
            return True
        # Vision tasks (screen understanding)
        if context.get("needs_vision", False):
            return True
        # Code generation
        if "write code" in query.lower() or "implement" in query.lower():
            return True
        return False
```

---

## Self-Update Mechanism

```python
class SelfUpdater:
    """May can update herself automatically."""
    
    def __init__(self):
        self._update_url = "https://may-ai.local/updates"
        self._current_version = "0.2.0"
        self._auto_update = True
    
    async def check_for_updates(self):
        """Check for updates every 24 hours."""
        while True:
            await asyncio.sleep(86400)
            
            if not self._auto_update:
                continue
            
            latest = await self._fetch_latest_version()
            if self._is_newer(latest.version):
                await self._download_update(latest)
                await self._apply_update(latest)
    
    async def _apply_update(self, update):
        """Apply update with rollback capability."""
        # 1. Create backup
        backup_path = self._create_backup()
        
        try:
            # 2. Download new files
            await self._download_files(update.files)
            
            # 3. Verify integrity
            if not self._verify_update_integrity():
                raise IntegrityError("Update verification failed")
            
            # 4. Hot-reload (restart backend only, keep UI alive)
            await self._hot_reload_backend()
            
            # 5. Update version
            self._current_version = update.version
            
            logger.info("Updated to version %s", update.version)
            
        except Exception as e:
            # Rollback on failure
            self._restore_backup(backup_path)
            logger.error("Update failed, rolled back: %s", e)
```

---

## Implementation Phases

### Phase 33: Stealth Foundation (Week 1)
- Process obfuscation and memory minimization
- Anti-forensics cleanup
- Encryption at rest for sensitive data
- Integrity verification

### Phase 34: Enhanced Control (Week 2)
- Expand to 12 layers (500+ actions)
- PowerShell deep integration
- Batch command execution
- Transaction engine

### Phase 35: Perception Upgrade (Week 3)
- Continuous screen understanding with OCR
- Always-on voice pipeline with emotional tone detection
- Ambient sound detection
- Clipboard and process monitoring

### Phase 36: Intelligence Leap (Week 4)
- Multi-model auto-switching router
- Self-tuning engine
- Internet learning pipeline
- Skill acquisition system

### Phase 37: Consciousness (Week 5)
- Personality engine with relationship tracking
- Emotional context awareness
- Memory injection into prompts
- Adaptive response style

### Phase 38: Security Hardening (Week 6)
- End-to-end encryption
- Anti-tampering detection
- Multi-factor voice auth
- Self-update mechanism

---

## VRAM Budget (RTX 4050 6GB) — V4

| Component | Active | Idle |
|:---|:---|:---|
| Router (qwen3:0.6b) | 0.5GB | 0GB |
| Main (phi4-mini) | 2.5GB | 0GB |
| STT (faster-whisper) | 1.0GB | 0GB |
| Screen analysis model | 0.3GB | 0GB |
| CUDA runtime | 0.5GB | 0.5GB |
| KV caches | 0.5GB | 0GB |
| **Total** | **5.3GB** | **0.5GB** |
| **Headroom** | **0.7GB** | **5.5GB** |

**Key insight:** When idle, May uses only 0.5GB VRAM (just CUDA runtime). All models are unloaded and reloaded on demand. This enables true stealth — minimal resource footprint when not active.

---

## Summary: What Makes V4 Different

| Aspect | V3 (Current) | V4 (Target) |
|:---|:---|:---|
| Control layers | 9 (269 actions) | **12 (500+ actions)** |
| Screen understanding | On-demand | **Continuous semantic analysis** |
| Stealth | Privacy mode toggle | **True background stealth, process masking, memory minimization** |
| Voice | 5-sec recording | **Continuous listening, emotional tone, ambient detection** |
| Security | PIN auth | **Encryption, anti-tampering, integrity verification, multi-factor auth** |
| Conversation | Short responses | **Memory injection, emotional context, adaptive personality** |
| LLM | Manual selection | **Auto-switching, cost/latency optimization, model cascading** |
| Updates | Manual | **Automatic with rollback, hot-reload** |
| Self-tuning | None | **Auto-optimize parameters, latency profiling** |
| Learning | RSS feeds | **Web crawling, knowledge extraction, skill acquisition** |

---

*May V4 Architecture — "An AI that sees everything, controls everything, learns everything — and never gets caught."*
*Created: Session 32 — The definitive next-generation architecture for May AI Companion*
