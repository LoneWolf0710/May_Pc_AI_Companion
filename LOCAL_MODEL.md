# 🚀 May — High-Speed Local Model Architecture

> **Goal:** Make May respond instantly using local models — zero cloud dependency, sub-200ms first token, 40+ tokens/sec generation.
> **Main Model:** phi4-mini:3.8b (fast, excellent reasoning, reliable tool calling)

---

## Current State — Why May Is Slow

| Bottleneck | Impact | Current Value |
|:---|:---|:---|
| `num_ctx: 32768` | Massive KV cache eats VRAM, slow prefill | 32768 tokens |
| No flash attention | ~40% more VRAM used for KV cache | Disabled |
| Ollama overhead | 5-15% slower than raw llama.cpp | Ollama wrapper |
| HTTP connection per request | ~50-100ms connection overhead | New `httpx.AsyncClient()` each call |
| 171 tools sent to LLM | Huge system prompt = slow prefill | Tool tiering helps but still 20-40 tools |
| No prefix caching | System prompt re-encoded every request | Zero caching |
| Large model for simple tasks | 3.8B model for "what time is it?" | phi4-mini for everything |

**Estimated current latency:**
- Simple command (with fast-path): ~50ms ✅
- Simple chat (LLM required): ~1-3s first token, ~35 tokens/sec
- Complex multi-tool: ~3-5s first token, ~30 tokens/sec

---

## Why phi4-mini:3.8b

| Property | phi4-mini:3.8b | qwen3:4b (comparison) |
|:---|:---|:---|
| Parameters | 3.8B | 4B |
| VRAM (Q4_K_M) | **~2.5GB** | ~3.0GB |
| Tokens/sec (RTX 4050) | **~35-50 tok/s** | ~30-40 tok/s |
| Time-to-first-token | **<100ms** | ~150-200ms |
| Context length | 128K native | 32K native |
| Tool calling | **Excellent** (Microsoft function calling) | Excellent |
| Instruction following | **More disciplined** | Good |
| Reasoning | **Strong** (outperforms 2x larger models) | Good |
| Thinking mode | No `<think>` overhead | Requires `<think>` filtering |

**Key advantages of phi4-mini over qwen3:4b:**
- **0.5GB less VRAM** — more headroom for router model + KV cache
- **Faster prefill** — smaller model = faster prompt processing
- **No `<think>` overhead** — qwen3 requires think-tag filtering which adds latency and complexity
- **More instruction-following** — less likely to hallucinate tool parameters
- **Better reasoning per parameter** — Microsoft's training focuses on data quality over quantity

---

## Architecture: Three-Tier Inference Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER MESSAGE INPUT                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  TIER 0:    │
                    │  Fast-Path  │  Pattern matcher (regex)
                    │  ~0ms       │  13+ command types
                    └──────┬──────┘
                           │ miss
                    ┌──────▼──────┐
                    │  TIER 1:    │
                    │  Router     │  Tiny model (0.6B)
                    │  ~50-150ms  │  Intent classification + simple replies
                    └──────┬──────┘
                           │ complex
                    ┌──────▼──────┐
                    │  TIER 2:    │
                    │  Main Model │  phi4-mini:3.8b
                    │  ~100-300ms │  Reasoning + multi-step tools + chat
                    └─────────────┘
```

---

## Tier 0: Fast-Path Pattern Matcher (Already Implemented)

**Latency: ~0ms | Covers: ~40% of daily commands**

Already implemented in `jarvis.py` as `_try_fast_path()`. Matches 13 command types:
- `open/launch/start [app]` → `open_app`
- `close/quit/kill [app]` → `close_app`
- `volume up/down/set/mute/unmute` → volume tools
- `what time/date` → `get_time`/`get_date`
- `battery/screenshot/system info/internet` → system tools

**Enhancement needed:** Expand from 13 to ~30 patterns to cover more common daily commands.

---

## Tier 1: Tiny Router Model (New)

**Latency: ~50-150ms first token, ~120+ tokens/sec | Covers: ~35% of remaining queries**

### Model Choice

| Model | Params | VRAM (Q4) | Speed (RTX 4050) | Tool Calling |
|:---|:---|:---|:---|:---|
| **Qwen3-0.6B** | 0.6B | ~0.5GB | ~120 tokens/sec | Good (fine-tuned) |
| Gemma 3 1B | 1B | ~0.7GB | ~80 tokens/sec | Good |
| SmolLM2-1.7B | 1.7B | ~1.2GB | ~60 tokens/sec | Moderate |

**Recommended: `qwen3:0.6b`** — Smallest model with reliable tool calling. At 0.6B params with Q4 quantization, it uses only ~0.5GB VRAM and runs at 120+ tokens/sec on RTX 4050.

### What the Router Does

1. **Intent Classification** — Is this a simple command, a chat message, or a multi-step task?
2. **Simple Replies** — Greetings, acknowledgments, short factual answers
3. **Tool Routing** — For simple tool calls, generates the JSON directly
4. **Escalation** — Complex queries get flagged and sent to Tier 2 (phi4-mini)

### Router System Prompt (Optimized for Speed)

```
You are May's intent router. Classify the user message and respond accordingly.

RULES:
- GREETING/CHAT: Reply naturally (1 sentence max). No tools.
- SIMPLE COMMAND: Output tool JSON. One tool only.
- COMPLEX/MULTI-STEP: Output [ESCALATE]
- AMBIGUOUS: Output [ESCALATE]

Response format:
- Chat: Just reply naturally
- Tool: {"tool": "tool_name", "args": {"param": "value"}}
- Escalate: [ESCALATE]
```

### Router Decision Matrix

| User Input | Router Output | Action |
|:---|:---|:---|
| "hey" / "hi" | "Hey~ What's up?" | Return directly |
| "what time is it" | `{"tool": "get_time", "args": {}}` | Execute tool |
| "open notepad" | `{"tool": "open_app", "args": {"app_name": "notepad"}}` | Execute tool |
| "set volume to 50" | `{"tool": "set_volume", "args": {"level": 50}}` | Execute tool |
| "write me an essay about AI" | `[ESCALATE]` | Send to phi4-mini |
| "open notepad and type hello" | `[ESCALATE]` | Send to phi4-mini (multi-step) |
| "explain quantum computing" | `[ESCALATE]` | Send to phi4-mini (reasoning) |

### Implementation: Persistent Router Process

The router model stays **permanently loaded** in VRAM via a persistent Ollama instance. This eliminates model load time (2-5s) entirely.

```
┌─────────────────────────────────────────┐
│  Ollama Instance 1 (Port 11434)         │
│  Model: qwen3:0.6b (ALWAYS LOADED)     │
│  VRAM: ~0.5GB                           │
│  Purpose: Router + simple replies       │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Ollama Instance 2 (Port 11435)         │
│  Model: phi4-mini:3.8b (ALWAYS LOADED) │
│  VRAM: ~2.8GB                           │
│  Purpose: Reasoning + tools + chat      │
└─────────────────────────────────────────┘

Total VRAM: ~3.3GB (fits in 6GB with 2.7GB headroom)
```

**Alternative: Single Ollama with model hot-swap**
- Ollama keeps the last-used model loaded
- First request after model switch: ~2-3s cold start
- Subsequent requests: instant (model already in VRAM)
- Trade-off: switching between router and main model adds latency

**Recommended: Dual Ollama instances** for zero-switching-latency.

---

## Tier 2: Main Model — phi4-mini:3.8b (Optimized)

**Latency: ~100-300ms first token, ~35-50 tokens/sec | Handles: ~25% of queries (complex ones)**

### Why phi4-mini Excels Here

1. **No `<think>` overhead** — qwen3 generates hidden thinking tokens that must be filtered; phi4-mini doesn't, so every token is useful output
2. **Instruction discipline** — Follows tool schemas precisely, fewer hallucinated parameters
3. **Reasoning per parameter** — Microsoft's training on high-quality data means 3.8B params do the work of 7B+ in other models
4. **Fast prefill** — Smaller than qwen3:4b (2.5GB vs 3.0GB Q4), prefill is proportionally faster
5. **128K native context** — While we cap at 4096 for speed, the model's architecture supports much longer contexts if needed

### Ollama Environment Optimization

```bash
# Enable flash attention (30-50% VRAM savings for KV cache)
set OLLAMA_FLASH_ATTENTION=1

# Keep both models loaded simultaneously
set OLLAMA_MAX_LOADED_MODELS=2

# Use mmap for fast model loading
# (enabled by default in recent Ollama versions)
```

### API Parameter Optimization

| Parameter | Current | Optimized | Reason |
|:---|:---|:---|:---|
| `num_ctx` | 32768 | **4096** | 8x less KV cache VRAM, 4x faster prefill |
| `num_predict` | 512 | **256** | May's responses are short (1-3 sentences) |
| `temperature` | 0.7 | 0.7 | No change needed |
| `top_p` | 0.9 | 0.9 | No change needed |
| `num_gpu` | auto | **999** | Force all layers to GPU (prevent CPU offload) |
| `think` | False | **Not needed** | phi4-mini has no thinking mode |

**Impact of `num_ctx: 4096` on phi4-mini:**
- KV cache drops from ~1.5GB to ~200MB (phi4-mini is more efficient)
- Prefill time drops from ~500ms to ~80ms
- Fits easily alongside router model in 6GB VRAM
- Conversation history trimmed to last 4 messages (already done)

---

## Tier 2.5: Persistent Connection Pool

**Latency savings: ~50-100ms per request**

Currently, every API call creates a new `httpx.AsyncClient()`. This adds TCP connection overhead.

### Solution: Singleton HTTP Client

```python
# In providers.py — replace per-request clients with a persistent pool

class OllamaClient:
    """Persistent HTTP client for Ollama with connection pooling."""
    
    _instance = None
    _client: httpx.AsyncClient | None = None
    
    @classmethod
    async def get(cls) -> httpx.AsyncClient:
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=5.0),
                limits=httpx.Limits(
                    max_connections=4,
                    max_keepalive_connections=2,
                    keepalive_expiry=300,  # 5 minutes
                ),
            )
        return cls._client
```

**Savings:** ~50-100ms per request from eliminated TCP handshake.

---

## Tier 3: Speculative Decoding (Advanced)

**Latency savings: ~25-40% faster token generation**

### How It Works
1. A tiny "draft" model (0.6B) predicts the next 5-10 tokens
2. The main model (phi4-mini 3.8B) validates all predicted tokens in one batch
3. If predictions are correct → 5-10 tokens generated in one forward pass
4. Net speedup: 25-40% more tokens/sec

### Feasibility on RTX 4050 (6GB VRAM)

| Component | VRAM |
|:---|:---|
| Main model (phi4-mini Q4) | ~2.5GB |
| Draft model (qwen3:0.6b Q4) | ~0.5GB |
| KV cache (both, ctx 4096) | ~0.8GB |
| CUDA overhead | ~0.5GB |
| **Total** | **~4.3GB** |
| **Remaining headroom** | **~1.7GB** |

**Verdict: Comfortably feasible!** phi4-mini's smaller footprint (2.5GB vs qwen3's 3.0GB) leaves 1.7GB headroom — enough for speculative decoding without OOM risk. This is significantly better than with qwen3:4b.

### Implementation via llama-server

```bash
# Start llama-server with speculative decoding
llama-server \
  -m ~/.ollama/models/phi4-mini-Q4_K_M.gguf \
  --draft ~/.ollama/models/qwen3-0.6b-Q4_K_M.gguf \
  --n-predict-draft 8 \
  --ctx-size 4096 \
  --n-gpu-layers 999 \
  --flash-attn \
  --port 11434
```

**Note:** This bypasses Ollama entirely and uses llama.cpp server directly. Requires manual model management but gives maximum performance.

---

## Complete Request Flow

```
User: "open notepad and type hello"
         │
         ▼
┌─── TIER 0: Fast-Path ─────────────────────┐
│ Regex: "open notepad and type hello"       │
│ Pattern: compound command → miss           │
│ (fast-path only matches single commands)   │
└───────────────┬────────────────────────────┘
                │ miss
                ▼
┌─── TIER 1: Router (qwen3:0.6b) ──────────┐
│ Input: "open notepad and type hello"       │
│ TTFT: ~80ms                                │
│ Output: [ESCALATE]                         │
│ (multi-step = too complex for router)      │
└───────────────┬────────────────────────────┘
                │ escalate
                ▼
┌─── TIER 2: phi4-mini:3.8b ───────────────┐
│ Input: "open notepad and type hello"       │
│ TTFT: ~150ms                               │
│ Output: [open_app("notepad"),              │
│          type_text("hello",                 │
│          window_title="notepad")]           │
│ Tokens/sec: ~40                            │
└───────────────┬────────────────────────────┘
                │
                ▼
┌─── Tool Execution ────────────────────────┐
│ open_app("notepad") → ~500ms              │
│ type_text("hello") → ~300ms               │
│ Total: ~800ms                              │
└───────────────┬────────────────────────────┘
                │
                ▼
Response: "Done~ Notepad opened and typed hello~"
Total time: ~1.2s (vs current ~4-6s)
```

```
User: "hey"
         │
         ▼
┌─── TIER 0: Fast-Path ─────────────────────┐
│ Regex: no match for "hey"                  │
└───────────────┬────────────────────────────┘
                │ miss
                ▼
┌─── TIER 1: Router (qwen3:0.6b) ──────────┐
│ Input: "hey"                               │
│ TTFT: ~50ms                                │
│ Output: "Hey~ What's up?"                  │
│ Tokens/sec: ~120                           │
└───────────────┬────────────────────────────┘
                │
                ▼
Total time: ~150ms (vs current ~2s)
```

```
User: "what's the weather in Tokyo?"
         │
         ▼
┌─── TIER 0: Fast-Path ─────────────────────┐
│ Regex: "weather" matches, but has city arg │
│ → miss (too complex for simple pattern)    │
└───────────────┬────────────────────────────┘
                │ miss
                ▼
┌─── TIER 1: Router (qwen3:0.6b) ──────────┐
│ Input: "what's the weather in Tokyo?"      │
│ TTFT: ~60ms                                │
│ Output: [ESCALATE]                         │
│ (needs API call = too complex)             │
└───────────────┬────────────────────────────┘
                │ escalate
                ▼
┌─── TIER 2: phi4-mini:3.8b ───────────────┐
│ Input: "what's the weather in Tokyo?"      │
│ TTFT: ~120ms                               │
│ Output: {"tool": "get_weather",            │
│          "args": {"city": "Tokyo"}}        │
│ Tokens/sec: ~45                            │
└───────────────┬────────────────────────────┘
                │
                ▼
┌─── Tool Execution ────────────────────────┐
│ get_weather("Tokyo") → ~1.5s (API call)   │
└───────────────┬────────────────────────────┘
                │
                ▼
Response: "It's 28°C and sunny in Tokyo~ Perfect weather~"
Total time: ~2s (vs current ~5s)
```

---

## Ollama Configuration

### Modelfile for Router (Tier 1)

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

Tools: open_app, close_app, set_volume, volume_up, volume_down, set_mute, get_time, get_date, battery_info, screenshot, get_system_info, test_internet, describe_screen, get_weather, web_search, type_text, write_file, run_powershell"""
```

### Modelfile for Main Model (Tier 2)

```dockerfile
FROM phi4-mini:3.8b

PARAMETER num_ctx 4096
PARAMETER num_predict 256
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_gpu 999
```

**Note:** No `think false` needed — phi4-mini has no thinking mode, unlike qwen3. This is one less parameter to manage and one less source of latency.

### Environment Variables (System-Wide)

```bash
# Windows System Environment Variables
OLLAMA_FLASH_ATTENTION=1
OLLAMA_MAX_LOADED_MODELS=2
OLLAMA_KEEP_ALIVE=24h          # Keep models loaded indefinitely
OLLAMA_NUM_PARALLEL=2          # Allow 2 concurrent requests
```

---

## Implementation Plan

### Phase 1: Ollama Optimization (Quick Wins)
1. Set `OLLAMA_FLASH_ATTENTION=1` environment variable
2. Reduce `num_ctx` from 32768 to 4096 in all Ollama calls
3. Reduce `num_predict` from 512 to 256
4. Force `num_gpu: 999` to prevent CPU offloading
5. Persistent HTTP client in providers.py
6. Remove `<think>` filtering code (phi4-mini doesn't need it)

### Phase 2: Switch Main Model to phi4-mini
1. Pull phi4-mini: `ollama pull phi4-mini`
2. Update `PRIMARY_MODEL` in `ollama_client.py` from `qwen3:4b` to `phi4-mini`
3. Update default model in `App.tsx` localStorage
4. Update `JARVIS_SYSTEM_PROMPT` if needed for phi4-mini's instruction style
5. Test tool calling accuracy with phi4-mini

### Phase 3: Dual-Model Router Setup
1. Pull `qwen3:0.6b` model (`ollama pull qwen3:0.6b`)
2. Create router Modelfile and register as `may-router`
3. Create new `router.py` module in `backend/llm/`
4. Implement intent classification logic
5. Wire into `jarvis.py` between fast-path and main LLM

### Phase 4: Expanded Fast-Path
1. Add 15+ new patterns to `_try_fast_path()`
2. Cover: brightness, reminders, weather, clipboard, power commands
3. Target: 50%+ of daily commands handled without any LLM

### Phase 5: Speculative Decoding (Optional)
1. Download Q4_K_M GGUF files for both models
2. Set up llama-server with draft model
3. Replace Ollama with llama-server as inference backend
4. Benchmark and tune draft prediction length

---

## Expected Performance

| Scenario | Current | After Optimization | Improvement |
|:---|:---|:---|:---|
| "hey" / greeting | ~2s | **~150ms** | **13x faster** |
| "open notepad" | ~2.5s | **~200ms** | **12x faster** |
| "volume up" | ~0ms (fast-path) | ~0ms | Same |
| "what's the weather" | ~3s | **~250ms** | **12x faster** |
| "write an essay" | ~8s | ~3s | **2.7x faster** |
| Multi-step command | ~10s | ~2.5s | **4x faster** |
| **Avg daily interaction** | **~3s** | **~350ms** | **8.5x faster** |

### VRAM Budget (6GB RTX 4050)

| Component | VRAM |
|:---|:---|
| Router model (qwen3:0.6b Q4) | 0.5GB |
| Main model (phi4-mini Q4) | 2.5GB |
| Router KV cache (2048 ctx) | 0.1GB |
| Main KV cache (4096 ctx) | 0.2GB |
| CUDA runtime | 0.5GB |
| **Total** | **3.8GB** |
| **Remaining headroom** | **2.2GB** |

The 2.2GB headroom means:
- Speculative decoding is comfortably feasible (needs ~1.3GB extra)
- No risk of OOM under normal usage
- Room for background apps using GPU

---

## Key Design Decisions

1. **phi4-mini:3.8b as main model** — Faster, smaller, no `<think>` overhead, better instruction following than qwen3:4b
2. **Dual Ollama instances** over single instance with model swap — eliminates switching latency
3. **Router model at 0.6B** — smallest model with reliable tool calling, 120+ tokens/sec
4. **num_ctx: 4096** — 8x reduction from current 32768, massive prefill speedup
5. **Flash attention mandatory** — 30-50% VRAM savings, enables dual-model setup
6. **Persistent HTTP connections** — eliminate per-request TCP overhead
7. **Tier 0 → 1 → 2 cascade** — 75% of queries never reach the main model
8. **No `<think>` filtering needed** — phi4-mini has no thinking mode, simpler pipeline
9. **Speculative decoding as Phase 5** — phi4-mini's smaller footprint makes it more feasible
10. **OLLAMA_KEEP_ALIVE=24h** — models stay loaded, zero cold-start latency

---

## Comparison: Before vs After Architecture

| Aspect | Before (Current) | After (phi4-mini optimized) |
|:---|:---|:---|
| Main model | qwen3:4b | **phi4-mini:3.8b** |
| Router model | None | **qwen3:0.6b** |
| num_ctx | 32768 | **4096** |
| Flash attention | Disabled | **Enabled** |
| Think-tag filtering | Yes (overhead) | **None needed** |
| HTTP connections | Per-request | **Persistent pool** |
| VRAM usage | ~4.5GB | **3.8GB** (0.7GB savings) |
| VRAM headroom | 1.5GB | **2.2GB** |
| Avg response time | ~3s | **~350ms** |
| TTFT (main model) | ~1.5s | **~150ms** |
| Tokens/sec | ~15 | **~40** |

---

*Created: Session 32 — High-Speed Local Model Architecture for May AI Companion*
*Updated: phi4-mini:3.8b as main model (replacing qwen3:4b)*
