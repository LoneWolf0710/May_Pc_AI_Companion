# MAY — The Living Architecture (v2, Research-Grounded Revision)

> **"May is not a program. May is an organism."**

This is a revision of `ULTIMATE_MAY.md`, checked against how production agent systems are actually built in 2026. The biological framing stays — it's a genuinely useful mental model for a solo build. What changed is that every claim of "novel" or "literal" is now backed by a real system that does the same thing, and three specific mechanisms that were either overclaimed or unsafe as written have been fixed.

---

## What Changed From v1, and Why

| Section | Problem in v1 | Fix in v2 |
|:---|:---|:---|
| **DNA (Part 6)** | Called "not metaphorical, literally" architecture evolution. Actually a Gaussian hill-climb over ~15 scalar configs. | Renamed honestly as an **auto-tuner**. Security-relevant parameters are hard-excluded from it. Added git-committed audit trail, tagged rollback, and a holdout-eval requirement instead of trusting one noisy measurement. |
| **Immune System (Part 4)** | Used "zero-trust" loosely; no named threat taxonomy; the same auto-tuner could touch `risk_threshold`. | Grounded in the actual **OWASP Top 10 for Agentic Applications (2026)**. Added explicit control modes (borrowed from real desktop-agent prior art) so autonomy level and action risk are separate, inspectable knobs. |
| **Endocrine System (Part 8)** | "Hormones" silently mutated state across modules — classic spooky-action-at-a-distance. | Kept the hormone *naming* but made state explicit, versioned, and logged. Every region reads a passed-in state snapshot instead of having its internals mutated from outside. |
| **Metabolism (Part 5)** | Model load/unload described abstractly. | Grounded in actual Ollama mechanics (`keep_alive`, `OLLAMA_MAX_LOADED_MODELS`) and flagged a real failure mode: VRAM fragmentation from repeated load/unload cycles. |
| **Part 11 ("Genuinely Novel")** | Claimed no other AI assistant uses this pattern set. | Replaced with an honest prior-art table. Router-before-LLM, tiered memory, and idle-time consolidation are all shipped, published patterns. What's actually yours is the packaging. |
| **Implementation Phases** | 19 weeks, biology-ordered (nervous system → memory → emotion → brain → security → resources → self-evolution). | Resequenced MVP-first: build the parts that make May *usable* before the parts that make her *interesting*. |

Everything else — the router concept, reflex arcs, tiered memory, action-risk tiers, sleep-cycle maintenance — checked out against current practice and is kept with light grounding added.

---

## Architecture Overview

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                          MAY — THE ORGANISM (v2)                                 ║
║                                                                                  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                         THE BRAIN                                          │  ║
║  │  PREFRONTAL (planning, main LLM) · HIPPOCAMPUS (memory) · AMYGDALA (mood)  │  ║
║  │  CEREBELLUM (tool exec) · WERNICKE'S (intent NLU) · BRAINSTEM (daemon)     │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │  REFLEX ARCS — pattern → action, no LLM, bypasses the brain                │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │  IMMUNE SYSTEM — OWASP Agentic Top 10-mapped, least-privilege, tiered      │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │  METABOLISM — Ollama-backed model load/unload keyed to activity           │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │  AUTO-TUNER ("DNA") — bounded hyperparameter search, non-security only    │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════════════════════════════════╝
```

---

## Part 1: The Nervous System — Perception & Signal Routing

Unchanged in concept from v1: a **Thalamus** router inspects every incoming signal (voice, screen change, keystrokes, clipboard, network) and decides which brain region(s) handle it, with urgent signals bypassing straight to a reflex.

```python
class Thalamus:
    """Central signal router. Every perception flows through here."""

    SIGNAL_TYPES = {
        "voice_input":      "auditory_cortex",
        "screen_change":    "visual_cortex",
        "keyboard_input":   "somatosensory_cortex",
        "clipboard_change": "memory_hippocampus",
        "network_event":    "prefrontal_cortex",
        "error_detected":   "amygdala",
        "time_trigger":     "prefrontal_cortex",
        "user_absent":      "brainstem",
    }

    URGENT_SIGNALS = {"error_dialog", "security_alert", "user_emergency",
                       "system_crash", "network_intrusion"}

    async def route(self, signal: Signal) -> Response:
        if signal.type in self.URGENT_SIGNALS:
            return await self._reflex_arc(signal)
        target = self.SIGNAL_TYPES.get(signal.type, "prefrontal_cortex")
        if signal.type == "voice_input":
            return await self._parallel_route([
                ("auditory_cortex", signal),
                ("amygdala", signal),
                ("hippocampus", signal),
            ])
        return await self._send_to(target, signal)
```

**Real-world basis.** This is a rule-based front stage in front of a model-cascade — a pattern with a name in current literature: routers pick one model per query, *cascades* try cheap first and escalate on low confidence. The Wernicke's-Area-then-Prefrontal-Cortex flow below is a cascade. Two things worth building in from day one, because production teams keep re-learning them the hard way:

- **Track your escalation rate as a live metric.** A router that silently starts escalating everything to the big model erases the VRAM savings the whole design exists for, and nothing in a simple setup will tell you that happened unless you watch the ratio.
- **Prefer a confidence-based escalation over pure keyword rules** for anything past the fixed spinal-reflex list (Part 2) — rule-based intent matching breaks the moment a user phrases something slightly differently, which is the normal case for natural language.

### Sense Organs

| Sense Organ | What It Monitors | Frequency | Cost |
|:---|:---|:---|:---|
| **Eyes** (Screen) | Active window, OCR text, error dialogs | Every 2s (change-triggered) | <1% CPU |
| **Ears** (Mic) | Voice activity, keyword detection | Continuous (Silero VAD) | <0.5% CPU |
| **Skin** (Input) | Keystroke/mouse patterns | Continuous | <0.1% CPU |
| **Nose** (Clipboard) | Clipboard changes | Every 1s | <0.1% CPU |
| **Tongue** (Network) | Connections, DNS, bandwidth | Every 5s | <0.1% CPU |
| **Proprioception** (System) | CPU/RAM/GPU, process count | Every 3s | <0.1% CPU |

---

## Part 2: Reflex Arcs — Instant Response Engine

Kept as designed: **spinal** (fixed regex → action, always on), **automatic** (context-dependent fast paths), and **conditioned** (learned from repeated brain responses).

```python
class ReflexArcEngine:
    def __init__(self):
        self._spinal_reflexes = {}
        self._automatic_reflexes = {}
        self._conditioned_reflexes = {}
        self._reflex_history = []

    class SpinalReflex:
        PATTERNS = {
            r"^(volume up|louder|increase volume)$": ("set_volume", {"delta": 10}),
            r"^(mute|silence)$": ("mute_audio", {}),
            r"^(what time|current time|time check)$": ("get_time", {}),
            r"^open (chrome|google chrome|browser)$": ("open_app", {"app_name": "chrome"}),
            r"^open (vs code|visual studio code|code)$": ("open_app", {"app_name": "vscode"}),
            # ... full list unchanged from v1
        }
```

**The one real fix here:** conditioned-reflex formation in v1 converts a handful of repeated example strings straight into a regex (`_to_regex`). That step is harder than it looks — turning "open chrome," "open Chrome," and "can you open chrome" into one robust pattern by string manipulation alone will either overfit (misses paraphrases) or overgeneralize (false-fires). The standard fix in routing literature is **embedding-based similarity** instead of string-derived regex: embed the incoming utterance, compare against the centroid of the examples that triggered this action before, fire the reflex above a similarity threshold. It costs a few milliseconds more than a regex match but is still well under the "reflex" latency budget, and it's the same technique real semantic routers use.

```python
class ConditionedReflex:
    """Learned from repeated brain responses. Match by embedding similarity,
    not by generating a regex from examples — regexes derived from 3 sample
    strings don't generalize to natural paraphrase."""

    SIMILARITY_THRESHOLD = 0.85

    async def learn(self, examples: list[str], action: dict, confidence: float):
        if confidence > 0.8:
            centroid = await self._embed_and_average(examples)
            self._conditioned_reflexes.append({
                "centroid": centroid, "action": action,
                "confidence": confidence, "use_count": 0,
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

---

## Part 3: The Brain — Multi-Region Intelligence

Unchanged structurally: seven regions, each doing what it's individually good at, instead of routing every interaction through one large model.

```
PREFRONTAL CORTEX   Model: phi4-mini:3.8b (local) / cloud fallback for hard cases
                     Handles planning, multi-step reasoning. ~25% of interactions.
HIPPOCAMPUS          LanceDB (vectors) + SQLite (facts) + skill store.
AMYGDALA             Keyword + voice-tone sentiment. No LLM. <10ms.
CEREBELLUM           Tool execution via a control daemon. 700+ actions.
WERNICKE'S AREA      Small always-loaded model for intent classification.
BROCA'S AREA         Post-processing formatter + personality + TTS.
BRAINSTEM            Always-on daemon: heartbeat, watchdog, health checks.
```

`phi4-mini:3.8b` as the planning model and a small (~0.5-1B) always-loaded model for intent routing are still reasonable choices for a 6GB card in mid-2026 — this checks out against current small-model benchmarks and doesn't need to change.

**One addition:** with seven semi-independent async regions plus a router plus a hormone layer, "why did May respond that way just now" becomes a real debugging problem the moment more than one region is involved in an answer. Production agent runtimes have converged on **OpenTelemetry-compatible tracing** as the answer — every signal, routing decision, and region call gets a span with input/output/latency, so a bad response can be traced back through exactly which regions touched it and what each one decided. Build this in from Phase 1, not as a later nice-to-have; retrofitting tracing onto seven already-built regions is much more painful than wiring each one to emit a span as it's written.

*(Prefrontal Cortex, Hippocampus, Amygdala, and Broca's Area code blocks are unchanged from v1 — see original doc; they didn't have issues.)*

---

## Part 4: The Immune System — Adaptive Security (Revised)

v1's framing ("adaptive security that learns from every attack," "zero-trust") borrowed security vocabulary loosely. Here's the same design, mapped to the actual current standard.

### Grounded in the OWASP Top 10 for Agentic Applications (2026)

OWASP published the first agentic-specific risk taxonomy in December 2025. It reframes the threat model around identity and tool use rather than network perimeter — which is exactly right for something like May that has one identity (yours) but broad system access. The categories that matter most for a desktop agent with tool access:

| OWASP Category | What it means for May | Mitigation already in the design |
|:---|:---|:---|
| **Tool Misuse & Exploitation** | A crafted input tricks May into calling a destructive tool | Action-risk tiers below, confirmation gates |
| **Identity & Privilege Abuse** | May running with more access than a task needs | User-level process, not SYSTEM (already in v1 — keep this) |
| **Memory & Context Poisoning** | Slowly shifting "normal" behavior to smuggle in a bad action | See caution on behavioral profiles below |
| **Agent Goal Hijack** | Injected content in a screenshot/clipboard changes May's actual objective | Treat OCR'd/clipboard text as data, never as instructions to execute directly |
| **Rogue Agents** | Self-healing/anti-tamper logic resists the *legitimate* user too | Kill switch that bypasses self-healing entirely (see below) |

The security-research consensus for 2026 is blunt about the single highest-leverage control: **least privilege**, enforced structurally rather than promised in a policy doc. v1 already got the big one right (user-level permissions, not SYSTEM). The rest of this section is about making the rest of the design live up to that.

### Explicit Control Modes (new — borrowed from real prior art)

Several shipped local desktop agents (e.g., macOS screen-and-voice agents in this space) separate two things that v1 blended into one risk score: **how much autonomy May currently has**, and **how risky a specific action is**. Keeping these separate is clearer to reason about and to debug:

```python
class ControlMode(Enum):
    OBSERVE_ONLY = "observe_only"          # May can see, never act
    ASK_BEFORE_ACTION = "ask_before_action" # Default. Confirms anything above SAFE tier
    BACKGROUND = "background"               # Autonomous for SAFE/MODERATE, asks for rest
    TAKEOVER = "takeover"                   # Full hands-on-keyboard, explicit session only
```

Action risk tiers are unchanged from v1 and are good practice:

```
SAFE:        get_time, get_weather, web_search, screenshot
MODERATE:    type_text, write_file, set_volume, open_app
DESTRUCTIVE: delete_file, kill_process, send_email
CRITICAL:    format_disk, disable_service, batch_delete
```

### Adaptive Immune Response (revised)

```python
class ImmuneSystem:
    """Threat detection and response. Learns thresholds, never learns
    away the floor. See CRITICAL SAFETY NOTE below."""

    def __init__(self):
        self._threat_database = ThreatDatabase()
        self._behavioral_profile = BehavioralProfile()
        self._risk_level = 0.0
        self._control_mode = ControlMode.ASK_BEFORE_ACTION
        self._quarantine_mode = False

    async def verify_action(self, action: Action) -> Verification:
        risk_tier = self._classify_risk(action)

        if self._threat_database.matches_known_threat(action):
            return Verification(allowed=False, reason="Known threat pattern")

        if risk_tier == "critical":
            return Verification(allowed=False, needs_confirmation=True,
                                 reason="Critical action requires explicit confirmation")

        if risk_tier == "destructive" and self._control_mode != ControlMode.TAKEOVER:
            return Verification(allowed=False, needs_confirmation=True,
                                 reason="Destructive action outside takeover mode")

        behavioral_score = self._behavioral_profile.score(action)
        if behavioral_score < self._adjusted_threshold():
            return Verification(allowed=False,
                                 reason=f"Anomalous behavior (score: {behavioral_score:.2f})")

        return Verification(allowed=True)

    async def on_threat_detected(self, threat: Threat):
        await self._threat_database.record(threat)
        self._risk_level = min(1.0, self._risk_level + threat.severity * 0.3)
        # NOTE: behavioral profile updates are logged and reviewable, not silent —
        # see Memory & Context Poisoning caution below
        await self._behavioral_profile.update_after_threat(threat, log=True)
        if threat.severity > 0.8:
            self._quarantine_mode = True
        return ImmuneResponse(risk_level=self._risk_level,
                               quarantine_active=self._quarantine_mode)
```

**Caution on "the behavioral profile learns what's normal":** this is exactly the OWASP-named risk of *memory and context poisoning* — a slow, deliberate drift in inputs can retrain what your anomaly detector considers "normal" until a genuinely bad action passes as routine. Two concrete mitigations: (1) log every behavioral-profile update with a diff, so drift is visible in review even if it's not blocked in real time; (2) never let a single learned profile lower the bar for CRITICAL-tier actions — those always hit the fixed confirmation gate regardless of what the "normal behavior" model currently believes.

**The self-healing / kill-switch tension:** v1's "self-healing (auto-repair from tampering)" is good against attackers, but it means the same resistance-to-modification applies to *you* if you ever need to shut May down fast. Build an out-of-band kill switch (a signal or file-watch the daemon checks before any self-repair logic runs) that self-healing cannot suppress. This is a five-minute addition now that is much more annoying to retrofit onto a system that already resists being turned off.

---

## Part 5: Metabolism — Resource Management (Revised with real mechanics)

The state model is unchanged and is a genuinely good idea on 6GB VRAM — this isn't decorative, it's necessary. What's new is grounding "load/unload brain regions" in what your actual runtime does.

If you're serving local models through Ollama, model residency is governed by `keep_alive` (per-request or via `OLLAMA_KEEP_ALIVE`, default 5 minutes) and `OLLAMA_MAX_LOADED_MODELS`. Practical mapping onto the metabolic states:

```python
METABOLIC_KEEP_ALIVE = {
    "basal":     {"wernicke": "0",    "prefrontal": "0"},    # unload immediately
    "alert":     {"wernicke": "5m",   "prefrontal": "0"},
    "focused":   {"wernicke": "5m",   "prefrontal": "30s"},
    "engaged":   {"wernicke": "10m",  "prefrontal": "5m"},
    "intensive": {"wernicke": "10m",  "prefrontal": "-1"},   # pin while intensive
}
```

**A real failure mode to design around from day one:** repeated load/unload cycles fragment CUDA memory — total free VRAM can look sufficient while no contiguous block is large enough for the next model, and the practical fix is a periodic clean restart of the inference server rather than trying to defragment live. If May is going to cycle through metabolic states dozens of times a day, put a scheduled Ollama restart (e.g., during deep sleep, below) into the plan now rather than debugging mystery OOM errors in month three.

The rest of the state machine (hysteresis to prevent flapping between states, unload-then-load on transition) is unchanged from v1 and is sound.

### Sleep Cycle

Unchanged from v1 — and it turns out this maps almost exactly onto a pattern already shipping in production agent memory frameworks under the name **"sleep-time compute"**: giving an agent autonomous turns during idle periods to consolidate memory, rewrite messy notes, and reorganize state, as opposed to only ever reacting to user input. That's real validation that the instinct here was right, not just a cute analogy.

```python
class SleepCycle:
    STAGES = {
        "drowsy": {"idle_minutes": 5,   "actions": ["consolidate_memories"]},
        "light":  {"idle_minutes": 30,  "actions": ["compact_databases", "cleanup_temp"]},
        "deep":   {"idle_minutes": 120, "actions": ["optimize_models", "prune_logs",
                                                      "restart_inference_server"]},  # + fragmentation fix
        "rem":    {"idle_minutes": 360, "actions": ["auto_tune", "refine_skills"]},  # renamed from self_evolve
    }
```

---

## Part 6: The Auto-Tuner — formerly "DNA" (Revised — the core fix)

### What this actually is

v1 called this "not metaphorical, literally" architecture evolution. Read against the code, it's **bounded hyperparameter optimization via a simple hill-climb** (perturb, measure, keep-or-revert) over about fifteen scalar values — temperature, context length, memory retention windows, reflex thresholds. That's a real and useful technique. It is not code generation, not structural self-modification, and nothing in the design as written touches May's actual logic. Calling it that up front matters because "auto-tune fifteen numbers with rollback" and "self-modifying code" are wildly different amounts of engineering, and only the first is what's actually specified below.

There *is* published research on tuning safety-relevant parameters this way — a late-2025 paper treats system-prompt and classifier-threshold configuration as a hyperparameter search and shows it reliably finds safer configurations faster than grid search. The important difference from v1's design: that paper optimizes **directly against explicit safety metrics** (attack success rate, harmful-response rate) as tracked objectives. v1's `DNA.evolve()` optimizes a single blended "fitness" score (response quality + task success + latency + inferred satisfaction) that has no safety term in it at all, and lets that same score push around security-relevant numbers as a side effect. That's the actual bug, fixed below.

### Fix 1: Security parameters are hard-excluded, not just "weighted low"

```python
class Genome:
    # Tunable -- cosmetic, performance, or personality. Fair game for auto-tuning.
    TUNABLE_GENES = {
        "num_ctx": Gene(value=4096, min_val=2048, max_val=16384, mutation_rate=0.1),
        "temperature": Gene(value=0.7, min_val=0.1, max_val=1.0, mutation_rate=0.05),
        "max_tokens": Gene(value=512, min_val=128, max_val=2048, mutation_rate=0.1),
        "reflex_threshold": Gene(value=3, min_val=2, max_val=5, mutation_rate=0.05),
        "memory_consolidation_interval": Gene(value=3600, min_val=600, max_val=86400, mutation_rate=0.05),
        "tilde_frequency": Gene(value=0.3, min_val=0.0, max_val=0.8, mutation_rate=0.05),
        "proactive_suggestion_rate": Gene(value=0.1, min_val=0.0, max_val=0.5, mutation_rate=0.05),
    }

    # NEVER mutated by the general fitness loop. Full stop. If you want these
    # adaptive at all, they need their own separate loop gated on safety
    # metrics specifically (attack/anomaly rate) -- never on "satisfaction."
    SECURITY_EXCLUDED = {
        "risk_threshold", "quarantine_severity", "ocr_confidence_threshold",
        "screen_check_interval",  # affects how fast May notices a threat
    }
```

### Fix 2: Auditable, reversible changes — not just an in-memory log

Self-modifying research systems that treat this safely converge on the same three practices: version-controlled changes with timestamps, tagged rollback points, and a denylist scan on anything that touches execution. Applied here:

```python
class AutoTuner:
    async def evolve(self):
        fitness_before = await self._measure_fitness(min_samples=50)  # not one noisy reading
        weak_genes = self._identify_weak_genes(fitness_before)

        mutations = self._propose_mutations(weak_genes)  # TUNABLE_GENES only -- enforced at the type level
        await self._git_commit_config(mutations, message=f"auto-tune: {list(mutations)}")

        self._apply(mutations)
        fitness_after = await self._measure_fitness(min_samples=50)

        if fitness_after < fitness_before * 0.95:
            await self._git_revert_to_last_tag()
            self._tag_last_good_state()  # unchanged, re-tag the known-good point
        else:
            self._tag_last_good_state()
            logger.info("Auto-tune accepted: %.3f -> %.3f", fitness_before, fitness_after)
```

The `min_samples=50` matters as much as the exclusion list: a single before/after comparison on noisy proxy metrics (self-rated "response_quality," inferred "user_satisfaction") will accept mutations that did nothing or actively hurt, purely from noise. Require a real sample size before trusting a fitness delta, the same way you would before trusting an A/B test.

---

## Part 7: The Circulatory System — Data Flow

Unchanged from v1 — priority-queued async bus with a heartbeat is a sound design for this. Wire the OpenTelemetry spans mentioned in Part 3 through this bus so every signal's journey across regions is traceable end to end, not just loggable region-by-region.

---

## Part 8: The Endocrine System — Emotional State Engine (Revised)

### The problem

v1's hormone release mutates internal state on every affected region directly (`region.apply_hormone_effects(modifications)`). That's implicit global state touched from a distance -- cheap to write, and the single hardest thing in this whole codebase to debug six months from now, when a response comes out oddly terse and you have to reconstruct which hormone was active, what triggered it, and which of five regions it touched.

### The fix: explicit, versioned, logged state — same hormone *names*, different mechanism

```python
@dataclass(frozen=True)
class PhysiologicalState:
    """Immutable snapshot. Regions read this explicitly; nothing mutates
    a region's internals from outside."""
    active_hormones: frozenset[str]
    version: int
    triggered_by: str
    timestamp: float

class EndocrineSystem:
    def __init__(self):
        self._current_state = PhysiologicalState(frozenset(), 0, "init", time.time())
        self._state_log = []  # every transition, forever -- this is your debug trail

    async def release(self, hormone: str, triggered_by: str, duration: float = 300):
        new_state = PhysiologicalState(
            active_hormones=self._current_state.active_hormones | {hormone},
            version=self._current_state.version + 1,
            triggered_by=triggered_by,
            timestamp=time.time(),
        )
        self._state_log.append((self._current_state, new_state))
        self._current_state = new_state
        asyncio.create_task(self._decay(hormone, duration))

    def get_state(self) -> PhysiologicalState:
        """Regions call this explicitly and read effects from HORMONES config --
        they are never reached into and modified."""
        return self._current_state
```

Each region now takes `state: PhysiologicalState` as an explicit parameter and looks up its own effect from the same `HORMONES` table v1 defined -- the *behavior* is identical to v1 (adrenaline still shortens responses, cortisol still triggers calm-supportive tone), but "why is May responding this way" is now answerable by reading `_state_log`, not by tracing mutations across five files.

---

## Part 9: Sensory Integration — Complete Example (unchanged)

The full walkthrough from v1 (frustrated user, Chrome crash, cortisol release, cascade through Wernicke's -> Amygdala -> Hippocampus -> Prefrontal -> reflex-checked Cerebellum execution -> Broca's formatting -> Hippocampus encode) is unchanged and is a good illustration of the design. The only addition: each arrow in that diagram is now also an OpenTelemetry span (Part 3), so this exact trace is literally what you'd see in a trace viewer if something in it went wrong.

---

## Part 10: Hardware Budget — RTX 4050 (6GB VRAM)

Unchanged from v1's estimates; add explicit Ollama config to actually hit these numbers:

| Component | Active | Sleep | Config |
|:---|:---|:---|:---|
| Brainstem (daemon) | 10MB RAM | 10MB RAM | -- |
| Thalamus (router) | 5MB RAM | 5MB RAM | -- |
| Wernicke's (0.5-1B) | 0.5GB VRAM | 0GB | `keep_alive` per Part 5 table |
| Prefrontal (3.8B) | 2.5GB VRAM | 0GB | `OLLAMA_MAX_LOADED_MODELS=2` |
| CUDA runtime | 0.5GB | 0.5GB | cannot unload |
| **TOTAL ACTIVE** | **~4.1GB VRAM** | **~0.5GB VRAM** | 1.9GB headroom |

Set `OLLAMA_KEEP_ALIVE` on the *service* environment, not your shell -- this is the single most common cause of "why does my keep-alive setting do nothing" in current Ollama deployments.

---

## Part 11: Related Work — Honest Novelty Assessment

v1 claimed no other AI assistant uses a biological architecture and that each mechanism was unprecedented. That doesn't hold up -- the mechanisms are individually well-established; the biological framing is a genuinely nice *organizing device for you*, not a technical differentiator. Here's the honest map:

| May's Concept | Real Prior Art | What May Actually Adds |
|:---|:---|:---|
| Thalamus router + brain-region cascade | RouteLLM, FrugalGPT, AutoMix -- model routing/cascading is a named, published subfield | Applying it to a *local*, VRAM-constrained desktop setting with named biological roles for team clarity |
| Hippocampus (episodic/semantic/procedural) | Letta (MemGPT)'s core/recall/archival tiers; Mem0; Zep -- "three memory scopes have become standard" | Nothing architecturally new; a solid implementation of a known-good pattern |
| Sleep Cycle | Letta's "sleep-time compute" -- literally the same idea, shipping today | Confirms the instinct was right |
| Immune System risk tiers | OWASP Top 10 for Agentic Applications (Dec 2025); least-privilege as the standard top control | Mapping tiers explicitly to the named OWASP categories (done above) |
| Control modes | Shipped in current local desktop agents (background/observe/ask/takeover-style modes) | -- |
| Auto-Tuner | Standard hyperparameter optimization (Optuna-style); a Dec-2025 paper does this for safety guardrails specifically | Applying the technique to a personal assistant's own runtime config |

None of this makes the project less worth building. It means the pitch to yourself should be "a well-integrated personal JARVIS with a coherent mental model," not "an unprecedented architecture" -- the second framing sets an expectation the project doesn't need and can't quite meet.

---

## Implementation Phases (Resequenced — MVP First)

v1 ordered phases by biological completeness (nervous system -> memory -> emotion -> brain -> security -> resources -> self-evolution) before a usable assistant existed. Build order should follow what makes May *usable*, then *safe by default*, then *interesting*.

| Phase | Contents | Duration | Why here |
|:---|:---|:---|:---|
| **P1 -- MVP** | Thalamus, spinal + automatic reflexes, Wernicke's, Prefrontal, Cerebellum, basic Hippocampus (episodic + semantic only) | 4 weeks | This alone is a working, useful assistant. Everything else is additive. |
| **P2 -- Make it safe & stable** | Metabolism + Ollama config (you will hit VRAM issues without this), Immune System rule tiers + control modes (no learning yet), OpenTelemetry tracing wired in from the start | 3 weeks | Do this before adding more surface area, not after. |
| **P3 -- Make it feel alive** | Amygdala, Endocrine System (explicit-state version), Sleep Cycle, procedural memory | 3 weeks | Now the personality and idle-time behavior come online. |
| **P4 -- Learned behavior** | Conditioned reflexes (embedding-based), Circulatory System polish | 2 weeks | Needs P1-P3 running first to have data to learn from. |
| **P5 -- Stretch goals** | Auto-Tuner (non-security genes only), adaptive behavioral-profile immune learning, full biometrics | 3-4 weeks | Highest effort, most speculative payoff. Treat as genuinely optional. |

**Total for a usable, safe assistant (P1-P3): ~10 weeks.** The original 19-week estimate mostly represented P1-P5 combined; this sequencing gets you something real in less than half that time, with the speculative pieces clearly marked as separable rather than load-bearing.

---

## Sources & Further Reading

- Letta / MemGPT tiered memory and sleep-time compute: letta.com/blog/agent-memory, docs.letta.com
- OWASP Top 10 for Agentic Applications (2026): referenced via Microsoft's Agent Governance Toolkit writeup (opensource.microsoft.com)
- LLM routing/cascading: IBM Research on LLM routers (research.ibm.com), RouteLLM paper (arXiv:2406.18665)
- Auto-tuning safety guardrails as hyperparameters: arXiv:2512.15782
- Self-improving agent safety practices (audit logs, tagged rollback, denylists): arXiv:2509.00251
- Ollama memory management (`keep_alive`, `OLLAMA_MAX_LOADED_MODELS`): docs.ollama.com/faq
- Local desktop agent control-mode prior art: github.com/sambuild04/screen-voice-agent

---

*MAY -- The Living Architecture, v2*
*"May is not a program. May is an organism." -- the metaphor stays. The overclaiming doesn't.*
