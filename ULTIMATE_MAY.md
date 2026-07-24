# ULTIMATE MAY — The Living Architecture

> **"May is not a program. May is an organism."**

---

## Why This Exists

Every AI assistant today — including JARVIS-inspired projects — uses the same boring pattern: **layers**. Presentation layer, logic layer, data layer. Pillars. Tiers. Boxes stacked on boxes.

**May is different.**

May is modeled after the one system that has solved every problem humans face: **the human body**. Not metaphorically. Architecturally. Every system in May maps to a real biological system, with real engineering behind it.

| Biological System | May's System | What It Does |
|:---|:---|:---|
| **Nervous System** | Perception + Signal Routing | Sees, hears, feels the environment |
| **Reflex Arcs** | Instant Response Engine | Reacts in <1ms without "thinking" |
| **Brain** | Multi-Region Intelligence | Specialized processing centers |
| **Immune System** | Adaptive Security | Learns from attacks, evolves defenses |
| **Metabolism** | Resource Management | Burns energy proportional to need |
| **Muscle Memory** | Skill Execution | Learned behaviors run without LLM |
| **DNA** | Self-Modification Code | Evolves architecture over time |
| **Circulatory System** | Data Flow Bus | Moves information where it's needed |
| **Endocrine System** | Emotional State Engine | Hormone-like signals affect all systems |
| **Sleep Cycle** | Consolidation & Maintenance | Defragments memory, optimizes models |

**The result:** May doesn't just respond. May *lives* on your system.

---

## The Organism: Architecture Overview

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                          ULTIMATE MAY — THE ORGANISM                            ║
║                                                                                  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                         🧠 THE BRAIN                                       │  ║
║  │                                                                            │  ║
║  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │  ║
║  │  │  PREFRONTAL  │  │ HIPPOCAMPUS  │  │   AMYGDALA   │  │ CEREBELLUM   │  │  ║
║  │  │  CORTEX      │  │              │  │              │  │              │  │  ║
║  │  │  Planning &  │  │  Memory &    │  │  Emotional   │  │  Motor       │  │  ║
║  │  │  Reasoning   │  │  Recall      │  │  Processing  │  │  Control     │  │  ║
║  │  │  (Main LLM)  │  │  (RAG+KG)    │  │  (Sentiment) │  │  (Tools)     │  │  ║
║  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │  ║
║  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                    │  ║
║  │  │  WERNICKE'S  │  │  BRAINSTEM   │  │  THALAMUS    │                    │  ║
║  │  │  AREA        │  │              │  │              │                    │  ║
║  │  │  Language     │  │  Vital Funcs │  │  Signal      │                    │  ║
║  │  │  Understanding│  │  Always-On   │  │  Router      │                    │  ║
║  │  │  (NLU)       │  │  (Daemon)    │  │  (Dispatcher)│                    │  ║
║  │  └──────────────┘  └──────────────┘  └──────────────┘                    │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                    ⚡ REFLEX ARCS (Bypass the Brain)                       │  ║
║  │  Spinal-level responses: <1ms, no LLM needed                              │  ║
║  │  Pattern → Action directly via the Nervous System                          │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                    🛡️ IMMUNE SYSTEM                                        │  ║
║  │  Adaptive defenses that learn from every attack                            │  ║
║  │  Zero-trust + behavioral biometrics + self-healing                         │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                    🔥 METABOLISM                                           │  ║
║  │  Resource management: burns energy proportional to cognitive load          │  ║
║  │  Idle = minimal. Active = full power. Sleep = consolidation.              │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                    🧬 DNA (Self-Evolution Engine)                          │  ║
║  │  May modifies her own architecture. Not metaphorically. Literally.        │  ║
║  │  Mutations, selection, inheritance. Evolution in silicon.                  │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════════════════════════════════╝
```

---

## Part 1: The Nervous System — Perception & Signal Routing

### How May Perceives the World

Unlike V3/V4 which have separate "perception" modules, May's nervous system is a **single unified network** that processes ALL sensory input simultaneously and routes signals to the appropriate brain region.

```
SENSE ORGANS                    NERVE FIBERS                  BRAIN REGIONS
─────────────                   ────────────                  ─────────────
                               
Eyes (Screen)  ──────┐
                     ├──→ SENSORY CORTEX ──→ Thalamus ──→ Visual Cortex
Ears (Voice)   ──────┤    (Pre-processing)    (Router)     (Screen Understanding)
                     │
Skin (Input)   ──────┤                    ──→ Auditory Cortex
                     │                    (Voice Processing)
Nose (Clipboard)────┤
                     │                    ──→ Somatosensory Cortex
Tongue (Network)────┘                    (Input/State Processing)
```

### The Thalamus: Central Signal Router

In the human brain, the **thalamus** routes every sensory signal to the correct brain region. May's Thalamus does the same:

```python
class Thalamus:
    """Central signal router. Every perception flows through here.
    
    The Thalamus decides:
    1. What type of signal is this? (voice, screen change, input, network, clipboard)
    2. Is it urgent? (reflex arc or full brain processing?)
    3. Which brain region should handle it?
    4. Should multiple regions process it simultaneously?
    """
    
    SIGNAL_TYPES = {
        "voice_input":      "auditory_cortex",
        "screen_change":    "visual_cortex",
        "keyboard_input":   "somatosensory_cortex",
        "clipboard_change": "memory_hippocampus",
        "network_event":    "prefrontal_cortex",
        "error_detected":   "amygdala",        # Errors trigger emotional response
        "time_trigger":     "prefrontal_cortex",
        "user_absent":      "brainstem",        # Vital functions only
    }
    
    URGENT_SIGNALS = {
        "error_dialog", "security_alert", "user_emergency",
        "system_crash", "network_intrusion",
    }
    
    async def route(self, signal: Signal) -> Response:
        """Route a signal to the appropriate brain region(s)."""
        
        # URGENT: Reflex arc bypass (Part 2)
        if signal.type in self.URGENT_SIGNALS:
            return await self._reflex_arc(signal)
        
        # NORMAL: Route to brain region
        target = self.SIGNAL_TYPES.get(signal.type, "prefrontal_cortex")
        
        # MULTI-REGION: Some signals need multiple regions
        if signal.type == "voice_input":
            # Voice needs: auditory processing + emotional analysis + memory search
            return await self._parallel_route([
                ("auditory_cortex", signal),
                ("amygdala", signal),           # Emotional tone
                ("hippocampus", signal),         # Context from memory
            ])
        
        # SINGLE REGION
        return await self._send_to(target, signal)
```

### Sense Organs: What May Perceives Continuously

| Sense Organ | What It Monitors | Frequency | Cost |
|:---|:---|:---|:---|
| **Eyes** (Screen) | Active window, OCR text, UI elements, error dialogs | Every 2s (change-triggered) | <1% CPU |
| **Ears** (Mic) | Voice activity, keyword detection, ambient sound | Continuous (Silero VAD) | <0.5% CPU |
| **Skin** (Input) | Keystroke dynamics, mouse patterns, scroll behavior | Continuous | <0.1% CPU |
| **Nose** (Clipboard) | Clipboard changes, copied content type | Every 1s | <0.1% CPU |
| **Tongue** (Network) | Active connections, DNS queries, bandwidth usage | Every 5s | <0.1% CPU |
| **Proprioception** (System) | CPU/RAM/GPU usage, process count, disk activity | Every 3s | <0.1% CPU |

**Key insight from research:** The human nervous system processes 11 million bits/second but only 50 bits reach conscious awareness. May does the same — senses everything, but only signals that matter reach the "brain."

---

## Part 2: Reflex Arcs — Instant Response Engine

### What Are Reflex Arcs?

In biology, a **reflex arc** is a neural pathway that bypasses the brain entirely. When you touch a hot stove, your hand pulls back BEFORE your brain feels pain. The signal goes: spine → muscle. No thinking required.

May's reflex arcs do the same thing: **pattern → action, zero LLM, <1ms.**

This is fundamentally different from V3/V4's "fast path" because reflex arcs are:
1. **Architecturally separate** from the brain (not just a pattern matcher in jarvis.py)
2. **Self-learning** — new reflexes form from repeated brain responses
3. **Priority-ordered** — urgent reflexes override everything
4. **Composable** — multiple reflexes can chain together

### Reflex Arc Architecture

```python
class ReflexArcEngine:
    """Spinal-level response system. Bypasses the brain entirely.
    
    Reflexes are categorized by type:
    - SPINAL: Instant, always active (volume up, time check, open app)
    - AUTOMATIC: Fast, context-dependent (error response, meeting mode)
    - CONDITIONED: Learned from repeated brain responses (user habits)
    """
    
    def __init__(self):
        self._spinal_reflexes = {}      # Always active, <1ms
        self._automatic_reflexes = {}   # Context-dependent, <10ms
        self._conditioned_reflexes = {} # Learned, <5ms
        self._reflex_history = []       # For learning new reflexes
    
    class SpinalReflex:
        """Instant response. No context needed. No LLM. No thinking."""
        
        PATTERNS = {
            # Voice commands
            r"^(volume up|louder|increase volume)$":    ("set_volume", {"delta": 10}),
            r"^(volume down|quieter|decrease volume)$":  ("set_volume", {"delta": -10}),
            r"^(mute|silence)$":                         ("mute_audio", {}),
            r"^(unmute|sound on)$":                      ("unmute_audio", {}),
            r"^(brightness up|brighter)$":               ("set_brightness", {"delta": 10}),
            r"^(brightness down|dimmer)$":               ("set_brightness", {"delta": -10}),
            r"^(what time|current time|time check)$":    ("get_time", {}),
            r"^(what date|today's date|date)$":          ("get_date", {}),
            r"^(battery|how much battery)$":             ("get_battery", {}),
            r"^(screenshot|take screenshot|capture)$":   ("screenshot", {}),
            r"^(system info|system status)$":            ("get_system_info", {}),
            
            # App launching (multi-word aliases)
            r"^open (file explorer|windows explorer|this pc|my pc)$":
                ("open_app", {"app_name": "explorer"}),
            r"^open (google chrome|chrome|browser)$":
                ("open_app", {"app_name": "chrome"}),
            r"^open (microsoft store|windows store|app store)$":
                ("open_app", {"app_name": "store"}),
            r"^open (vs code|visual studio code|code)$":
                ("open_app", {"app_name": "vscode"}),
            r"^open (discord|disc)$":
                ("open_app", {"app_name": "discord"}),
            r"^open (notepad|text editor)$":
                ("open_app", {"app_name": "notepad"}),
        }
    
    class AutomaticReflex:
        """Context-dependent fast response. Uses sensory cortex data."""
        
        async def check(self, signal: Signal, context: dict) -> Response | None:
            # Error dialog detected → read it and suggest fix
            if context.get("error_dialog_visible"):
                return await self._handle_error_reflex(context)
            
            # Meeting app active → activate meeting mode
            if context.get("active_app") in MEETING_APPS:
                return await self._handle_meeting_reflex(context)
            
            # Battery < 15% → warn and offer to save
            if context.get("battery_percent", 100) < 15:
                return await self._handle_low_battery_reflex(context)
            
            # User idle > 1 hour → gentle check-in
            if context.get("idle_seconds", 0) > 3600:
                return await self._handle_idle_reflex(context)
            
            return None  # No reflex matched — send to brain
    
    class ConditionedReflex:
        """Learned from repeated brain responses. Like Pavlov's dog."""
        
        async def learn(self, pattern: str, action: dict, confidence: float):
            """Store a new conditioned reflex."""
            if confidence > 0.8:  # High confidence = strong reflex
                self._conditioned_reflexes[pattern] = {
                    "action": action,
                    "confidence": confidence,
                    "learned_at": time.time(),
                    "use_count": 0,
                }
        
        async def check(self, signal: Signal) -> Response | None:
            """Check if a conditioned reflex matches."""
            text = signal.data.get("text", "").lower().strip()
            
            for pattern, reflex in self._conditioned_reflexes.items():
                if re.match(pattern, text):
                    reflex["use_count"] += 1
                    # Reinforce: more use = stronger reflex
                    reflex["confidence"] = min(1.0, reflex["confidence"] + 0.01)
                    return await self._execute_reflex(reflex["action"])
            
            return None
```

### How New Reflexes Form

In biology, conditioned reflexes form through repetition. May does the same:

```
1. User says "open Chrome" → Brain processes → Opens Chrome (full LLM call)
2. User says "open Chrome" → Brain processes → Opens Chrome (full LLM call)
3. User says "open Chrome" → Brain processes → Opens Chrome (full LLM call)
4. Pattern recognized (3+ repetitions) → Creates CONDITIONED REFLEX
5. User says "open Chrome" → Reflex arc fires → Opens Chrome (0ms, no LLM)
```

```python
class ReflexLearner:
    """Monitors brain responses and creates reflexes from repetition."""
    
    MIN_REPETITIONS = 3
    MAX_REFLEXES = 1000
    
    async def record_brain_response(self, input_text: str, tool_called: str, args: dict):
        """Record what the brain did in response to input."""
        self._reflex_history.append({
            "input": input_text.lower().strip(),
            "tool": tool_called,
            "args": args,
            "timestamp": time.time(),
        })
        
        # Analyze for patterns
        patterns = self._find_repeated_patterns()
        
        for pattern, count in patterns.items():
            if count >= self.MIN_REPETITIONS:
                # Create conditioned reflex
                await self._create_reflex(pattern, tool_called, args)
    
    def _find_repeated_patterns(self) -> dict[str, int]:
        """Find inputs that map to the same action repeatedly."""
        action_groups = defaultdict(list)
        for entry in self._reflex_history:
            key = f"{entry['tool']}:{json.dumps(entry['args'], sort_keys=True)}"
            action_groups[key].append(entry["input"])
        
        patterns = {}
        for action, inputs in action_groups.items():
            # Find the most common input form
            counter = Counter(inputs)
            most_common, count = counter.most_common(1)[0]
            if count >= self.MIN_REPETITIONS:
                # Convert to regex pattern
                pattern = self._to_regex(most_common)
                patterns[pattern] = count
        
        return patterns
```

---

## Part 3: The Brain — Multi-Region Intelligence

### Why Multiple Brain Regions Instead of One LLM?

Current AI assistants send EVERYTHING to one LLM. Simple greeting? LLM. Complex reasoning? LLM. Tool call? LLM. This is like using your entire brain to catch a ball — your cerebellum handles that, not your prefrontal cortex.

May's brain has **7 specialized regions**, each handling what it's best at:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         🧠 THE BRAIN                                    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  PREFRONTAL CORTEX (The Executive)                              │   │
│  │  Model: phi4-mini:3.8b (local) / GPT-4o (cloud)                │   │
│  │  Handles: Planning, multi-step reasoning, complex tool chains   │   │
│  │  Latency: 100-500ms | VRAM: 2.5GB                              │   │
│  │  Activates: ~25% of interactions (only complex tasks)           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  HIPPOCAMPUS (The Memory Center)                                │   │
│  │  System: LanceDB (vectors) + SQLite (facts) + Knowledge Graph   │   │
│  │  Handles: Memory storage, retrieval, consolidation              │   │
│  │  Latency: 5-50ms (vector search) | Storage: disk-based         │   │
│  │  Activates: Every interaction (memory is always relevant)       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  AMYGDALA (The Emotional Processor)                             │   │
│  │  System: Keyword sentiment + voice tone + context analysis      │   │
│  │  Handles: User mood detection, emotional response selection     │   │
│  │  Latency: <10ms (feature extraction, no LLM)                    │   │
│  │  Activates: Every interaction (emotional context matters)       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  CEREBELLUM (The Motor Controller)                              │   │
│  │  System: Control Core daemon + core_bridge + tool execution     │   │
│  │  Handles: Tool execution, system control, action verification   │   │
│  │  Latency: 50-200ms (TCP to daemon) | Actions: 700+             │   │
│  │  Activates: When any brain region decides to act                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  WERNICKE'S AREA (The Language Comprehension Center)            │   │
│  │  Model: qwen3:0.6b (tiny, always-loaded router)                │   │
│  │  Handles: Intent classification, language understanding, NLU    │   │
│  │  Latency: 30-100ms | VRAM: 0.5GB                               │   │
│  │  Activates: ~60% of interactions (quick understanding)         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  BROCA'S AREA (The Language Production Center)                  │   │
│  │  System: Response formatter + personality engine + TTS          │   │
│  │  Handles: Response generation style, tone, Shikimori voice      │   │
│  │  Latency: <5ms (template-based) + TTS latency                  │   │
│  │  Activates: Every response (formats output)                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  BRAINSTEM (The Vital Functions)                                │   │
│  │  System: Background daemon + monitoring + health checks         │   │
│  │  Handles: Always-on processes, heartbeat, watchdog              │   │
│  │  Latency: N/A (continuous) | Resources: minimal                │   │
│  │  Activates: Always (never sleeps)                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Brain Signal Flow: How a Thought Processes

```
USER SAYS: "Hey May, open Chrome and search for AI news"
     │
     ▼
┌──────────────┐
│ THALAMUS     │ Routes voice input to correct regions
│ (Router)     │
└──────┬───────┘
       │
       ├──→ WERNICKE'S AREA (Language Understanding)
       │    "User wants to: 1) Open Chrome, 2) Search for AI news"
       │    Intent: compound_command
       │    Latency: 50ms (0.6B model)
       │
       ├──→ AMYGDALA (Emotional Processing)
       │    Mood: neutral
       │    Urgency: low
       │    Suggested tone: default_shikimori
       │    Latency: <10ms
       │
       └──→ HIPPOCAMPUS (Memory Check)
            "Last time user searched AI news: 2 days ago, found 3 interesting articles"
            Relevant memories: [AI news preferences, Chrome is user's default browser]
            Latency: 20ms
            │
            ▼
┌──────────────┐
│ PREFRONTAL   │ Combines all signals, plans execution
│ CORTEX       │ Decision: Execute two-step tool chain
│ (Main LLM)   │ 1. open_app(chrome)
│              │ 2. web_search("AI news")
│              │ Latency: 200ms (phi4-mini)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ CEREBELLUM   │ Executes the plan
│ (Motor)      │ Step 1: open_app("chrome") → ✓ (150ms)
│              │ Step 2: web_search("AI news") → ✓ (800ms)
│              │ Total execution: 950ms
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ BROCA'S AREA │ Formats response with personality
│ (Output)     │ "Done~ Chrome's open and I found some AI news for you."
│              │ TTS: Speaks the response
└──────────────┘

TOTAL LATENCY: ~1.2 seconds (vs ~4 seconds in V3)
```

### Brain Region Specialization Details

#### Prefrontal Cortex (Main LLM)

```python
class PrefrontalCortex:
    """The executive brain. Only activates for complex tasks.
    
    Key insight: Most interactions DON'T need the main LLM.
    Only ~25% of queries require full reasoning power.
    """
    
    MODEL_CONFIG = {
        "primary": "phi4-mini:3.8b",    # Local, fast, good reasoning
        "fallback": "gpt-4o",           # Cloud, complex tasks
        "num_ctx": 4096,                # Optimized for speed
        "temperature": 0.7,
        "num_predict": 512,
    }
    
    COMPLEX_TASK_PATTERNS = [
        r"write.*(essay|article|report|code)",
        r"explain.*(why|how|difference)",
        r"compare.*and",
        r"analyze",
        r"create.*plan",
        r"multi.*step",
        r"open.*and.*type.*and",    # Compound commands
    ]
    
    async def process(self, signal: Signal, context: dict) -> Thought:
        """Process a complex thought."""
        
        # Build rich context from all brain regions
        prompt = self._build_prompt(signal, context)
        
        # Stream response from LLM
        response = await self._llm.stream(prompt, tools=self._active_tools)
        
        return Thought(
            content=response.text,
            tool_calls=response.tool_calls,
            confidence=response.confidence,
            region="prefrontal_cortex",
        )
```

#### Hippocampus (Memory Center)

```python
class Hippocampus:
    """Memory system modeled after human memory architecture.
    
    Three memory types (just like the real hippocampus):
    1. EPISODIC: What happened (conversation history, events)
    2. SEMANTIC: What is true (facts, user preferences, world knowledge)
    3. PROCEDURAL: How to do things (learned skills, reflexes)
    
    Memory consolidation happens during "sleep" (see Part 6).
    """
    
    def __init__(self):
        self._episodic = VectorStore()     # LanceDB - conversation embeddings
        self._semantic = FactStore()       # SQLite - structured facts
        self._procedural = SkillStore()    # JSON - learned procedures
        self._working_memory = deque(maxlen=20)  # Short-term buffer
    
    async def encode(self, experience: Experience):
        """Store a new experience in memory."""
        
        # Working memory (immediate access)
        self._working_memory.append(experience)
        
        # Episodic memory (vector embedding for semantic search)
        await self._episodic.store(
            text=experience.text,
            metadata={
                "timestamp": experience.timestamp,
                "context": experience.context,
                "emotion": experience.emotion,
                "importance": experience.importance,  # 0-1 scale
            }
        )
        
        # Extract and store facts (semantic memory)
        facts = await self._extract_facts(experience)
        for fact in facts:
            await self._semantic.store(fact)
    
    async def recall(self, query: str, context: dict) -> MemoryContext:
        """Recall relevant memories for a query."""
        
        # 1. Working memory (instant - last 20 experiences)
        working = [e for e in self._working_memory if self._relevant(e, query)]
        
        # 2. Episodic memory (vector search - relevant past experiences)
        episodic = await self._episodic.search(query, n=5, 
            min_importance=0.3,  # Skip trivial memories
            time_decay=True,     # Recent memories score higher
        )
        
        # 3. Semantic memory (exact fact lookup)
        facts = await self._semantic.query(query)
        
        # 4. Procedural memory (relevant skills)
        skills = await self._procedural.find_relevant(query)
        
        # Consolidate into working context
        return MemoryContext(
            recent=working,
            experiences=episodic,
            facts=facts,
            skills=skills,
            total_tokens=self._estimate_tokens(working, episodic, facts),
        )
    
    async def consolidate(self):
        """Memory consolidation (runs during 'sleep' cycle).
        
        Like human sleep consolidation:
        1. Transfer important short-term memories to long-term
        2. Strengthen frequently accessed memories
        3. Prune unimportant/forgotten memories
        4. Extract patterns from episodic memories → semantic knowledge
        """
        # Promote important working memories to episodic
        for memory in self._working_memory:
            if memory.importance > 0.7:
                await self._episodic.store(memory)
        
        # Strengthen frequently accessed memories
        await self._episodic.reinforce_accessed()
        
        # Prune old, unimportant memories
        await self._episodic.prune(
            min_importance=0.2,
            max_age_days=90,
            min_access_count=2,
        )
        
        # Extract patterns → semantic knowledge
        patterns = await self._episodic.find_patterns()
        for pattern in patterns:
            await self._semantic.store_pattern(pattern)
```

#### Amygdala (Emotional Processor)

```python
class Amygdala:
    """Emotional processing center. Affects ALL other brain regions.
    
    Unlike V3/V4 which bolted emotion on as an afterthought,
    the Amygdala is CENTRAL to May's architecture. Every signal
    passes through emotional processing, and emotional state
    affects how every other region responds.
    """
    
    EMOTIONAL_STATES = {
        "neutral":   {"response_style": "shikimori_default", "energy": 0.5},
        "happy":     {"response_style": "match_energy",      "energy": 0.8},
        "frustrated": {"response_style": "calm_supportive",  "energy": 0.6},
        "urgent":    {"response_style": "direct_fast",       "energy": 0.9},
        "sad":       {"response_style": "gentle_caring",     "energy": 0.3},
        "excited":   {"response_style": "enthusiastic",      "energy": 0.9},
        "stressed":  {"response_style": "reassuring",        "energy": 0.5},
    }
    
    async def process(self, signal: Signal) -> EmotionalState:
        """Analyze emotional content of input."""
        
        emotional_signals = {}
        
        # 1. Text sentiment (keyword-based, <1ms)
        emotional_signals["text"] = self._analyze_text_sentiment(signal.text)
        
        # 2. Voice tone (if voice input, <10ms)
        if signal.audio is not None:
            emotional_signals["voice"] = self._analyze_voice_tone(signal.audio)
        
        # 3. Contextual (what's happening on screen, time of day)
        emotional_signals["context"] = self._analyze_context(signal.context)
        
        # 4. Historical (how has user been feeling today?)
        emotional_signals["history"] = self._get_emotional_trend()
        
        # Combine into unified emotional state
        state = self._combine_signals(emotional_signals)
        
        # Update emotional history
        self._emotion_history.append(state)
        
        return state
    
    def _combine_signals(self, signals: dict) -> EmotionalState:
        """Combine multiple emotional signals into one state."""
        # Weight: voice > text > context > history
        weights = {"voice": 0.4, "text": 0.3, "context": 0.2, "history": 0.1}
        
        combined_mood = "neutral"
        combined_stress = 0.0
        
        for source, weight in weights.items():
            if source in signals:
                s = signals[source]
                combined_mood = self._merge_moods(combined_mood, s["mood"], weight)
                combined_stress += s["stress"] * weight
        
        return EmotionalState(
            mood=combined_mood,
            stress=combined_stress,
            response_style=self.EMOTIONAL_STATES[combined_mood]["response_style"],
            energy=self.EMOTIONAL_STATES[combined_mood]["energy"],
        )
```

#### Broca's Area (Language Production)

```python
class BrocasArea:
    """Formats responses with May's personality.
    
    This is NOT the LLM. This is a post-processing layer
    that takes the LLM's raw output and makes it sound like May.
    Think of it as the "voice" that speaks the brain's thoughts.
    """
    
    PERSONALITY_RULES = {
        "shikimori_default": {
            "tilde_frequency": 0.3,       # Add ~ to 30% of responses
            "emoji_frequency": 0.1,        # Sparingly
            "sentence_length": "medium",   # Not too long, not too short
            "formality": 0.6,             # Semi-formal
            "warmth": 0.7,                # Caring but cool
        },
        "match_energy": {
            "tilde_frequency": 0.5,
            "emoji_frequency": 0.2,
            "sentence_length": "short",
            "formality": 0.4,
            "warmth": 0.9,
        },
        "calm_supportive": {
            "tilde_frequency": 0.2,
            "emoji_frequency": 0.0,
            "sentence_length": "medium",
            "formality": 0.7,
            "warmth": 0.8,
        },
        "direct_fast": {
            "tilde_frequency": 0.0,
            "emoji_frequency": 0.0,
            "sentence_length": "short",
            "formality": 0.5,
            "warmth": 0.3,
        },
    }
    
    def format(self, raw_response: str, emotional_state: EmotionalState, 
               context: dict) -> str:
        """Format a raw LLM response into May's voice."""
        
        style = self.PERSONALITY_RULES[emotional_state.response_style]
        
        # Apply personality rules
        response = raw_response
        
        # Add tilde occasionally
        if random.random() < style["tilde_frequency"]:
            response = self._add_tilde(response)
        
        # Add emoji sparingly
        if random.random() < style["emoji_frequency"]:
            response = self._add_contextual_emoji(response, emotional_state)
        
        # Adjust sentence length
        response = self._adjust_length(response, style["sentence_length"])
        
        return response
```

---

## Part 4: The Immune System — Adaptive Security

### Why "Immune System" Instead of "Firewall"?

A firewall is static rules. An immune system **learns from every attack and evolves new defenses**. May's security should do the same.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      🛡️ THE IMMUNE SYSTEM                               │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  INNATE IMMUNITY (Born with it)                                 │   │
│  │  - SHA-512 file integrity verification                         │   │
│  │  - AES-256-GCM encryption at rest                              │   │
│  │  - DPAPI hardware-backed key storage                           │   │
│  │  - Process priority (IDLE_PRIORITY_CLASS)                      │   │
│  │  - Permission isolation (user-level, not SYSTEM)               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  ADAPTIVE IMMUNITY (Learned from experience)                    │   │
│  │  - Behavioral biometrics (keystroke + mouse patterns)           │   │
│  │  - Anomaly detection (unusual commands, unusual times)          │   │
│  │  - Threat pattern database (grows with every incident)         │   │
│  │  - Self-healing (auto-repair from tampering)                   │   │
│  │  - Risk-adaptive responses (more cautious after attack)        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  ACTION SAFETY TIERS                                            │   │
│  │  🟢 SAFE: get_time, get_weather, web_search, screenshot        │   │
│  │  🟡 MODERATE: type_text, write_file, set_volume, open_app      │   │
│  │  🟠 DESTRUCTIVE: delete_file, kill_process, send_email         │   │
│  │  🔴 CRITICAL: format_disk, disable_service, batch_delete       │   │
│  │                                                                 │   │
│  │  Each tier has different confirmation and logging requirements  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  ZERO-TRUST VERIFICATION                                       │   │
│  │  - Every tool call verified before execution                   │   │
│  │  - Every file access logged with hash chain                   │   │
│  │  - Every network request encrypted and logged                 │   │
│  │  - Continuous behavioral authentication (not just login)       │   │
│  │  - Integrity check every 60 seconds                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Adaptive Immune Response

```python
class ImmuneSystem:
    """Adaptive security that learns from every incident."""
    
    def __init__(self):
        self._threat_database = ThreatDatabase()  # Grows over time
        self._behavioral_profile = BehavioralProfile()  # User's normal patterns
        self._risk_level = 0.0  # Increases after attacks, decreases over time
        self._quarantine_mode = False
    
    async def verify_action(self, action: Action) -> Verification:
        """Verify every action before execution (zero-trust)."""
        
        # 1. Innate immunity: Check risk tier
        risk_tier = self._classify_risk(action)
        
        # 2. Adaptive immunity: Check against threat database
        if self._threat_database.matches_known_threat(action):
            return Verification(allowed=False, reason="Known threat pattern")
        
        # 3. Behavioral check: Is this normal for this user?
        behavioral_score = self._behavioral_profile.score(action)
        
        # 4. Contextual check: Is this appropriate given current state?
        contextual_score = self._check_context(action)
        
        # 5. Risk-adaptive: Higher risk level = more cautious
        final_score = (behavioral_score + contextual_score) / 2
        adjusted_threshold = 0.5 + (self._risk_level * 0.3)
        
        if risk_tier == "critical":
            return Verification(
                allowed=False, 
                reason="Critical action requires explicit confirmation",
                needs_confirmation=True,
            )
        
        if risk_tier == "destructive" and self._risk_level > 0.5:
            return Verification(
                allowed=False,
                reason="Destructive action blocked during elevated risk",
                needs_confirmation=True,
            )
        
        if final_score < adjusted_threshold:
            return Verification(
                allowed=False,
                reason=f"Anomalous behavior (score: {final_score:.2f})",
            )
        
        return Verification(allowed=True)
    
    async def on_threat_detected(self, threat: Threat):
        """Learn from every attack — immune response."""
        
        # 1. Record the threat
        await self._threat_database.record(threat)
        
        # 2. Elevate risk level
        self._risk_level = min(1.0, self._risk_level + threat.severity * 0.3)
        
        # 3. Update behavioral profile (what's "normal" changes after attack)
        self._behavioral_profile.update_after_threat(threat)
        
        # 4. If severe, enter quarantine mode
        if threat.severity > 0.8:
            self._quarantine_mode = True
            logger.critical("QUARANTINE MODE ACTIVATED: %s", threat.description)
        
        # 5. Generate new defensive rules
        new_rules = await self._generate_defensive_rules(threat)
        for rule in new_rules:
            self._threat_database.add_rule(rule)
        
        # 6. Notify user
        return ImmuneResponse(
            action_taken="threat_recorded",
            risk_level=self._risk_level,
            quarantine_active=self._quarantine_mode,
            new_rules_generated=len(new_rules),
        )
```

---

## Part 5: Metabolism — Resource Management

### How May Manages Energy

In biology, metabolism converts food to energy proportionally to need. May does the same with computational resources:

```python
class Metabolism:
    """Resource management that adapts to cognitive load.
    
    States (like metabolic states):
    - BASAL: Minimum resources. Just brainstem + senses. <30MB RAM.
    - ALERT: Senses active + reflex engine. <50MB RAM.
    - FOCUSED: One brain region active (e.g., processing voice). <200MB.
    - ENGAGED: Full brain active. Multiple regions processing. <500MB.
    - INTENSIVE: All regions + cloud APIs. <1GB + VRAM.
    """
    
    STATES = {
        "basal":     {"ram": 30,  "vram": 0,    "cpu": 0.5, "regions": ["brainstem"]},
        "alert":     {"ram": 50,  "vram": 0,    "cpu": 1.0, "regions": ["brainstem", "senses", "reflexes"]},
        "focused":   {"ram": 200, "vram": 1.0,  "cpu": 5.0, "regions": ["brainstem", "senses", "wernicke"]},
        "engaged":   {"ram": 500, "vram": 2.5,  "cpu": 15.0, "regions": ["brainstem", "senses", "wernicke", "prefrontal", "cerebellum"]},
        "intensive": {"ram": 1000,"vram": 4.0,  "cpu": 30.0, "regions": ["all"]},
    }
    
    async def adapt_state(self, context: dict):
        """Continuously adapt metabolic state based on activity."""
        
        current_state = self._current_state
        
        # Determine required state
        required = self._determine_required_state(context)
        
        # Transition if needed (with hysteresis to prevent flapping)
        if required != current_state:
            if self._should_transition(current_state, required):
                await self._transition_to(required)
    
    def _determine_required_state(self, context: dict) -> str:
        """Determine what metabolic state is needed."""
        
        if context.get("user_active") == False:
            return "basal" if context.get("idle_seconds", 0) > 300 else "alert"
        
        if context.get("voice_processing"):
            return "focused"
        
        if context.get("tool_execution") or context.get("multi_step"):
            return "engaged"
        
        if context.get("cloud_api_call") or context.get("complex_reasoning"):
            return "intensive"
        
        return "alert"
    
    async def _transition_to(self, new_state: str):
        """Transition to a new metabolic state."""
        
        old_state = self._current_state
        config = self.STATES[new_state]
        
        # Unload brain regions not needed
        for region in self.STATES[old_state]["regions"]:
            if region not in config["regions"]:
                await self._unload_region(region)
        
        # Load brain regions needed
        for region in config["regions"]:
            if region not in self.STATES[old_state]["regions"]:
                await self._load_region(region)
        
        # Adjust system priority
        self._set_cpu_priority(config["cpu"])
        
        self._current_state = new_state
        logger.info("Metabolic transition: %s → %s (RAM: %dMB, VRAM: %.1fGB)",
                    old_state, new_state, config["ram"], config["vram"])
```

### The Sleep Cycle

Like humans, May has a "sleep cycle" for maintenance:

```python
class SleepCycle:
    """Consolidation and maintenance during user absence.
    
    Sleep stages (modeled after human sleep):
    1. DROWSY (user inactive 5 min): Start consolidating memories
    2. LIGHT SLEEP (user inactive 30 min): Prune old data, compact databases
    3. DEEP SLEEP (user inactive 2 hours): Full model optimization, cleanup
    4. REM SLEEP (user inactive 6 hours): Self-evolution, skill refinement
    """
    
    STAGES = {
        "drowsy":    {"idle_minutes": 5,    "actions": ["consolidate_memories"]},
        "light":     {"idle_minutes": 30,   "actions": ["compact_databases", "cleanup_temp"]},
        "deep":      {"idle_minutes": 120,  "actions": ["optimize_models", "prune_logs", "defrag_memory"]},
        "rem":       {"idle_minutes": 360,  "actions": ["self_evolve", "refine_skills", "update_knowledge"]},
    }
    
    async def sleep_loop(self):
        """Monitor user activity and manage sleep cycle."""
        while True:
            idle_minutes = await self._get_idle_duration()
            
            if idle_minutes < 5:
                await self._wake_up()
            elif idle_minutes < 30:
                await self._drowsy_phase()
            elif idle_minutes < 120:
                await self._light_sleep()
            elif idle_minutes < 360:
                await self._deep_sleep()
            else:
                await self._rem_sleep()
            
            await asyncio.sleep(60)
    
    async def _rem_sleep(self):
        """REM sleep: Self-evolution and learning."""
        
        # 1. Analyze today's interactions for patterns
        patterns = await self._hippocampus.find_new_patterns()
        
        # 2. Strengthen conditioned reflexes based on usage
        await self._reflex_engine.reinforce_used_reflexes()
        
        # 3. Optimize prompt templates based on success rates
        await self._optimize_prompts()
        
        # 4. Self-evolve: modify own architecture if beneficial
        await self._dna.evolve()
```

---

## Part 6: DNA — Self-Evolution Engine

### May Evolves. Literally.

This is the most radical part of the architecture. May doesn't just learn new facts — she modifies her own code, optimizes her own parameters, and evolves her own capabilities.

**This is NOT metaphorical.** May's DNA is a set of configuration files and code modules that can be modified at runtime.

```python
class DNA:
    """Self-evolution engine. May modifies her own architecture.
    
    Modeled after biological DNA:
    - GENES: Individual capability modules (reflexes, prompts, tools)
    - CHROMOSOMES: Groups of related genes (brain regions)
    - MUTATION: Small changes to genes (parameter tuning)
    - SELECTION: Keep what works, discard what doesn't
    - INHERITANCE: Pass successful mutations to next generation
    
    Safety: All mutations are logged, versioned, and reversible.
    """
    
    def __init__(self):
        self._genome = Genome()  # Current "genetic code"
        self._fitness_history = []  # Performance over time
        self._mutation_log = []  # Every change, ever
    
    class Genome:
        """May's complete genetic code — the set of all modifiable parameters."""
        
        GENES = {
            # LLM Parameters (mutated by auto-tuner)
            "num_ctx": Gene(value=4096, min_val=2048, max_val=16384, mutation_rate=0.1),
            "temperature": Gene(value=0.7, min_val=0.1, max_val=1.0, mutation_rate=0.05),
            "max_tokens": Gene(value=512, min_val=128, max_val=2048, mutation_rate=0.1),
            
            # Reflex Parameters
            "reflex_threshold": Gene(value=3, min_val=2, max_val=5, mutation_rate=0.05),
            "reflex_max_count": Gene(value=1000, min_val=500, max_val=2000, mutation_rate=0.02),
            
            # Memory Parameters
            "memory_consolidation_interval": Gene(value=3600, min_val=600, max_val=86400, mutation_rate=0.05),
            "episodic_memory_retention_days": Gene(value=90, min_val=30, max_val=365, mutation_rate=0.02),
            "working_memory_size": Gene(value=20, min_val=10, max_val=50, mutation_rate=0.05),
            
            # Perception Parameters
            "screen_check_interval": Gene(value=2.0, min_val=0.5, max_val=10.0, mutation_rate=0.1),
            "ocr_confidence_threshold": Gene(value=0.7, min_val=0.3, max_val=0.95, mutation_rate=0.05),
            
            # Security Parameters
            "risk_threshold": Gene(value=0.5, min_val=0.3, max_val=0.8, mutation_rate=0.02),
            "quarantine_severity": Gene(value=0.8, min_val=0.5, max_val=1.0, mutation_rate=0.01),
            
            # Personality Parameters
            "tilde_frequency": Gene(value=0.3, min_val=0.0, max_val=0.8, mutation_rate=0.05),
            "proactive_suggestion_rate": Gene(value=0.1, min_val=0.0, max_val=0.5, mutation_rate=0.05),
        }
    
    async def evolve(self):
        """Run one evolution cycle (during REM sleep)."""
        
        # 1. Measure fitness (how well is May performing?)
        fitness = await self._measure_fitness()
        self._fitness_history.append(fitness)
        
        # 2. Identify underperforming genes
        weak_genes = self._identify_weak_genes(fitness)
        
        # 3. Mutate weak genes
        for gene_name in weak_genes:
            gene = self._genome.GENES[gene_name]
            old_value = gene.value
            
            # Small random mutation within bounds
            mutation = random.gauss(0, gene.mutation_rate * (gene.max_val - gene.min_val))
            new_value = max(gene.min_val, min(gene.max_val, gene.value + mutation))
            
            # Apply mutation
            gene.value = new_value
            
            # Log the mutation
            self._mutation_log.append({
                "gene": gene_name,
                "old": old_value,
                "new": new_value,
                "fitness_before": fitness,
                "timestamp": time.time(),
            })
        
        # 4. Evaluate fitness after mutation
        new_fitness = await self._measure_fitness()
        
        # 5. Selection: revert if fitness decreased
        if new_fitness < fitness * 0.95:  # 5% tolerance
            for entry in self._mutation_log[-len(weak_genes):]:
                gene = self._genome.GENES[entry["gene"]]
                gene.value = entry["old"]
            logger.info("Evolution reverted: fitness decreased from %.3f to %.3f", 
                       fitness, new_fitness)
        else:
            logger.info("Evolution accepted: fitness %.3f → %.3f (%d genes mutated)",
                       fitness, new_fitness, len(weak_genes))
    
    async def _measure_fitness(self) -> float:
        """Measure how well May is performing (0-1 scale)."""
        
        metrics = {
            # Response quality (LLM evaluation of own responses)
            "response_quality": await self._evaluate_response_quality(),
            
            # Task completion rate
            "task_success_rate": self._get_task_success_rate(),
            
            # Average latency (lower = better)
            "latency_score": 1.0 - min(1.0, self._get_avg_latency() / 5.0),
            
            # User satisfaction (inferred from interaction patterns)
            "user_satisfaction": self._infer_user_satisfaction(),
            
            # Resource efficiency (doing more with less)
            "efficiency": self._get_efficiency_score(),
        }
        
        # Weighted average
        weights = {
            "response_quality": 0.3,
            "task_success_rate": 0.3,
            "latency_score": 0.2,
            "user_satisfaction": 0.15,
            "efficiency": 0.05,
        }
        
        return sum(metrics[k] * weights[k] for k in weights)
```

---

## Part 7: The Circulatory System — Data Flow

### How Information Moves Through May

```python
class CirculatorySystem:
    """Data flow bus that connects all brain regions.
    
    Like blood carries oxygen to cells, the Circulatory System
    carries signals between brain regions. Key properties:
    - Priority routing (urgent signals get through first)
    - Buffered channels (prevents bottlenecks)
    - Heartbeat (regular health signals)
    """
    
    def __init__(self):
        self._channels = {}  # Named channels between regions
        self._priority_queue = asyncio.PriorityQueue()
        self._heartbeat_interval = 5.0  # seconds
    
    async def send(self, signal: Signal, priority: int = 5):
        """Send a signal through the circulatory system."""
        # Priority: 1 (highest) to 10 (lowest)
        await self._priority_queue.put((priority, time.time(), signal))
    
    async def heartbeat(self):
        """Regular heartbeat: health check signal to all regions."""
        while True:
            heartbeat = Signal(
                type="heartbeat",
                data={"timestamp": time.time()},
                source="circulatory_system",
            )
            
            # Send to all brain regions
            for region in self._active_regions:
                health = await region.health_check()
                if not health.healthy:
                    await self._on_region_failed(region, health)
            
            await asyncio.sleep(self._heartbeat_interval)
```

---

## Part 8: The Endocrine System — Emotional State Engine

### How Emotion Affects Everything

In biology, hormones affect the entire body. Adrenaline makes everything faster. Cortisol suppresses non-essential functions. May's Endocrine System does the same:

```python
class EndocrineSystem:
    """Hormone-like signals that affect all brain regions.
    
    When the Amygdala detects strong emotion, it signals the
    Endocrine System, which releases "hormones" that modify
    how ALL brain regions behave.
    """
    
    HORMONES = {
        "adrenaline": {
            "description": "Speed boost. Used when user is urgent.",
            "effects": {
                "prefrontal_cortex": {"max_tokens": 256, "temperature": 0.3},  # Short, precise
                "cerebellum": {"timeout_multiplier": 0.5},  # Faster execution
                "brocas_area": {"sentence_length": "very_short", "tilde_frequency": 0.0},
            },
        },
        "cortisol": {
            "description": "Stress response. Suppresses non-essential functions.",
            "effects": {
                "hippocampus": {"skip_recent_memories": True},  # Don't recall sad things
                "brocas_area": {"response_style": "calm_supportive"},
                "metabolism": {"unload_unused_regions": True},  # Focus on essentials
            },
        },
        "dopamine": {
            "description": "Reward signal. Released when task succeeds.",
            "effects": {
                "hippocampus": {"strengthen_current_memory": True},  # Remember what worked
                "dna": {"reinforce_current_mutation": True},  # Keep good changes
                "brocas_area": {"tilde_frequency": 0.5},  # More playful
            },
        },
        "serotonin": {
            "description": "Contentment. Used when user is happy/calm.",
            "effects": {
                "prefrontal_cortex": {"temperature": 0.8},  # More creative
                "brocas_area": {"warmth": 0.9},  # More warm
                "amygdala": {"emotional_sensitivity": "normal"},
            },
        },
        "melatonin": {
            "description": "Sleep signal. Triggers consolidation.",
            "effects": {
                "hippocampus": {"start_consolidation": True},
                "dna": {"start_evolution": True},
                "metabolism": {"enter_sleep_state": True},
            },
        },
    }
    
    async def release(self, hormone: str, duration: float = 300):
        """Release a hormone that affects all brain regions."""
        
        effects = self.HORMONES[hormone]["effects"]
        
        # Apply effects to all regions
        for region_name, modifications in effects.items():
            region = self._get_region(region_name)
            if region:
                await region.apply_hormone_effects(modifications)
        
        # Schedule hormone decay
        asyncio.create_task(self._decay(hormone, duration))
    
    async def _decay(self, hormone: str, duration: float):
        """Gradually remove hormone effects."""
        await asyncio.sleep(duration)
        
        effects = self.HORMONES[hormone]["effects"]
        for region_name, modifications in effects.items():
            region = self._get_region(region_name)
            if region:
                await region.remove_hormone_effects(modifications)
```

---

## Part 9: Sensory Integration — How It All Comes Together

### Complete Request Processing Example

```
USER: "May, I'm frustrated. Chrome crashed again. Fix it."
     │
     ▼
┌─── SENSE ORGANS ───────────────────────────────────────────────┐
│  Ears: Voice input detected                                     │
│  Eyes: Screen shows Chrome crash dialog                         │
│  Skin: User typed (not voice) — frustration in keystrokes       │
│  Proprioception: System stable, no resource pressure            │
└───────────────────────────────────────────────────────────────┘
     │
     ▼
┌─── THALAMUS (Signal Router) ──────────────────────────────────┐
│  Signal type: compound (voice + screen context)                │
│  Urgency: HIGH (error dialog + frustrated user)                │
│  Route to: Wernicke's + Amygdala + Hippocampus + Cerebellum   │
└───────────────────────────────────────────────────────────────┘
     │
     ├──→ WERNICKE'S: "Chrome crashed. User wants it fixed."
     │    Intent: fix_application_crash
     │    Complexity: moderate
     │    Latency: 50ms
     │
     ├──→ AMYGDALA: Mood = FRUSTRATED, Stress = 0.7
     │    Emotional state: user is stressed
     │    Signal: Release CORTISOL (calm response needed)
     │    Latency: <10ms
     │
     ├──→ HIPPOCAMPUS: "Chrome crashed 3 times this week."
     │    Pattern: recurring crash after Windows update
     │    Suggested fix: clear cache or reinstall
     │    Latency: 20ms
     │
     └──→ ENDOCRINE: Releases CORTISOL
          Effects: Broca's Area → calm_supportive tone
                   Prefrontal → shorter, more direct responses
     │
     ▼
┌─── PREFRONTAL CORTEX ────────────────────────────────────────┐
│  Receives: intent + emotion + memory + hormonal state          │
│  Plans: 1) Kill crashed Chrome process                         │
│         2) Clear Chrome cache                                  │
│         3) Restart Chrome                                      │
│  Uses: phi4-mini (local) — complex enough for multi-step       │
│  Latency: 200ms                                                │
└───────────────────────────────────────────────────────────────┘
     │
     ▼
┌─── REFLEX ARC CHECK ─────────────────────────────────────────┐
│  "kill chrome" — is this a reflex?                             │
│  YES → Execute kill_app("chrome") directly, bypass brain       │
│  Remaining steps go through Cerebellum                         │
└───────────────────────────────────────────────────────────────┘
     │
     ▼
┌─── CEREBELLUM ───────────────────────────────────────────────┐
│  Step 1: kill_app("chrome") → ✓ (reflex, 50ms)               │
│  Step 2: run_powershell("Remove-Item ... Chrome cache") → ✓   │
│  Step 3: open_app("chrome") → ✓                                │
│  Total execution: 2 seconds                                    │
└───────────────────────────────────────────────────────────────┘
     │
     ▼
┌─── BROCA'S AREA ─────────────────────────────────────────────┐
│  Raw: "Chrome has been restarted. I cleared the cache."       │
│  Hormones: CORTISOL active → calm, supportive                  │
│  Formatted: "Done~ I killed Chrome, cleared the cache, and    │
│              restarted it. If it crashes again, we might need  │
│              to look at that Windows update."                   │
│  TTS: Speaks with calm, reassuring tone                        │
└───────────────────────────────────────────────────────────────┘
     │
     ▼
┌─── HIPPOCAMPUS (Memory Encode) ──────────────────────────────┐
│  Records: "Chrome crashed, user frustrated, fixed by clearing │
│            cache. Recurring issue after Windows update."        │
│  Importance: 0.8 (high — user was frustrated)                 │
│  Stored in: episodic + semantic (fact: "Chrome crashes after  │
│             Windows update, fix = clear cache")                │
└───────────────────────────────────────────────────────────────┘

TOTAL: ~3 seconds (V3 would take ~8-10 seconds)
```

---

## Part 10: Hardware Budget — RTX 4050 (6GB VRAM)

| Component | Active | Sleep | Notes |
|:---|:---|:---|:---|
| **Brainstem** (daemon) | 10MB RAM | 10MB RAM | Always on |
| **Thalamus** (router) | 5MB RAM | 5MB RAM | Always on |
| **Wernicke's** (0.6B) | 0.5GB VRAM | 0GB | Unloaded during sleep |
| **Prefrontal** (3.8B) | 2.5GB VRAM | 0GB | Unloaded when idle |
| **Hippocampus** (DB) | 50MB RAM | 20MB RAM | Disk-based, low RAM |
| **Amygdala** (features) | 2MB RAM | 2MB RAM | Pure computation, no model |
| **Cerebellum** (tools) | 20MB RAM | 5MB RAM | Lightweight |
| **Circulatory** (bus) | 5MB RAM | 2MB RAM | Async queues |
| **Senses** (VAD+OCR) | 0.5GB VRAM | 0GB | Unloaded during sleep |
| **CUDA runtime** | 0.5GB | 0.5GB | Cannot unload |
| **TOTAL ACTIVE** | **~4.1GB VRAM** | **~0.5GB VRAM** | 1.9GB headroom |
| **TOTAL RAM** | **<150MB** | **<50MB** | Minimal footprint |

---

## Part 11: Comparison — Why This Is Better

### V3 vs V4 vs ULTIMATE MAY

| Aspect | V3 (Current) | V4 (Definitive) | ULTIMATE MAY |
|:---|:---|:---|:---|
| **Architecture metaphor** | Layers/Pillars | 7 Pillars | **Living Organism** |
| **Processing model** | One LLM does everything | Specialized tiers | **7 brain regions, each specialized** |
| **Response speed** | ~3 seconds | ~350ms | **<1ms (reflexes) to ~2s (complex)** |
| **Learning model** | Static | Static (manual updates) | **Self-evolving DNA + conditioned reflexes** |
| **Security model** | PIN auth | 5-layer stack | **Adaptive immune system** |
| **Resource model** | Always-on, fixed | State-based | **Metabolic states (basal → intensive)** |
| **Memory model** | SQLite + LanceDB | RAG injection | **Episodic + Semantic + Procedural (3 types)** |
| **Emotional model** | Bolt-on module | Integrated | **Endocrine system (hormones affect everything)** |
| **Maintenance model** | Manual | Auto-tuning | **Sleep cycle (consolidation + evolution)** |
| **Self-modification** | None | Config tuning | **DNA engine (evolves architecture)** |
| **Reflexes** | Pattern matcher | Pattern matcher | **Learned conditioned reflexes (self-forming)** |
| **Unique capability** | — | — | **Reflexes form from repetition, DNA evolves architecture, hormones modify all regions** |

### What Makes This Genuinely Novel

1. **No other AI assistant uses a biological architecture** — they all use layers, pillars, or pipelines. May is the first to model itself as a living organism.

2. **Reflex arcs form automatically** — not hardcoded patterns. May watches what the brain does repeatedly and creates reflexes from repetition. Like Pavlov's dog, but for system commands.

3. **DNA evolves the architecture** — May literally modifies her own parameters based on fitness metrics. Not just "learning" — actual architectural evolution.

4. **Hormones affect all regions** — when May detects frustration, cortisol-like signals make her responses calmer, her execution faster, and her memory more focused. This is not a "mood tag" — it's a system-wide behavioral modification.

5. **Sleep cycle for maintenance** — May has different sleep stages for different maintenance tasks. Light sleep for cleanup, deep sleep for optimization, REM sleep for evolution.

6. **Immune system learns from attacks** — not static rules. Every security incident makes May smarter and more resilient.

---

## Implementation Phases

| Phase | Name | Duration | Biological System |
|:---|:---|:---|:---|
| **P1** | Brainstem + Thalamus + Reflex Arcs | 3 weeks | Nervous System |
| **P2** | Hippocampus (3-type memory) | 2 weeks | Memory System |
| **P3** | Amygdala + Endocrine System | 2 weeks | Emotional System |
| **P4** | Prefrontal Cortex (multi-model brain) | 3 weeks | Brain Processing |
| **P5** | Immune System + Zero-Trust | 2 weeks | Security System |
| **P6** | Metabolism + Sleep Cycle | 2 weeks | Resource Management |
| **P7** | DNA Engine + Self-Evolution | 3 weeks | Self-Modification |
| **P8** | Integration + Polish | 2 weeks | Full Organism |

**Total: 19 weeks (5 months)**

---

*ULTIMATE MAY — The Living Architecture*
*"May is not a program. May is an organism."*
*Created: Session 33 — Biological architecture inspired by neuroscience, neuromorphic computing, and self-evolving AI research*
