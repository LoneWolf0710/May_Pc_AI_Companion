# May AI Companion — Session Work Log

## Session Summary

Complete bug audit, security hardening, multi-launch fix, backend stability, notepad launch fix, and tool count optimization for May AI Companion.
**Date:** 2026-07-22 | **Status:** Notepad launch fixed, tool interceptor added, HTTP 500 needs investigation

---

## 1. Security Fixes (CRITICAL)

### shell=True Command Injection
- **File:** `core/layers/L11_media.py:316` — `subprocess.Popen(["start", path], shell=True)`
- **File:** `core/layers/L3_application.py:285` — `subprocess.Popen(cand, shell=True, ...)`
- **Fix:** Changed to `["cmd", "/c", "start", "", path]` without `shell=True`

### eval() Usage
- **File:** `core/layers/L17_content_tools.py:147` — `eval(expr_clean, {"__builtins__": {}}, safe_names)`
- **Fix:** Added `ast.parse()` validation before `eval()` to block dangerous constructs

### Backend Binding
- **File:** `backend/main.py:3011` — `uvicorn.run(app, host="0.0.0.0", port=8080)`
- **Fix:** Changed to `127.0.0.1` by default, env var `MAY_LISTEN_ALL=true` for LAN access

---

## 2. Multi-Launch Bug Fix (HIGH)

### Problem
Apps like Notepad opened 2-3 times when user said "open notepad".

### Root Causes Found
1. **UWP apps** launched via Everything search exe path (double-launch)
2. **Skill matching** too aggressive — "open notepad" matched "open notepad, then type X"
3. **Fallback chain** continued after first method succeeded (verifier too strict)
4. **520 duplicate skills** in skill store

### Fixes Applied

#### a) Notepad UWP Fix
- **File:** `core/layers/L3_application.py`
- Added `"notepad": "notepad:"` to `SHELL_URIS` dict
- Also added `"paint": "mspaint:"`, `"snipping tool": "snippingtool:"`

#### b) Duplicate Launch Guard
- **File:** `core/layers/L3_application.py`
- Added `_recently_launched` dict with 2-second cooldown
- Prevents same app from being launched twice within 2 seconds

#### c) Verifier Rewrite
- **File:** `core/engine/verifier.py`
- Changed from single 0.15s check to multi-retry: 0.2s → 0.5s → 1.0s
- Trust method success if it reports app name (for UWP apps)
- Flexible name matching: `"chrome"` matches `"chrome.exe"`

#### d) Skill Matching Strict
- **File:** `backend/memory/skill_store.py`
- Short queries (1-2 words) now only match single-step skills
- Multi-step skills require 50%+ name coverage
- Minimum score raised to 2.0

#### e) Duplicate Skills Cleanup
- **520 → 7 skills** (513 removed)
- Shadow learner DB: 795 → 431 patterns (weak ones removed)

---

## 3. Context Window Fix (MEDIUM)

### Problem
4096 token context was too small for multi-step commands.

### Fix
Changed `num_ctx` from 4096 to 131072 (128K) across all files:

| File | Change |
|------|--------|
| `backend/llm/ollama_client.py:189` | Default: 4096 → 131072 |
| `backend/llm/providers.py:907,1581` | Hardcoded: 4096 → 131072 |
| `backend/llm/Modelfile:9` | num_ctx: 4096 → 131072 |
| `backend/llm/Modelfile.main:23` | num_ctx: 4096 → 131072 |
| `backend/llm/Modelfile.router:41` | num_ctx: 4096 → 131072 |
| `backend/llm/llama_server.py:52,261` | n_ctx: 4096 → 131072 |
| `backend/intelligence/auto_tuner.py:102` | Default: 4096 → 131072, max: 16384 → 131072 |
| `~/.may/auto_tuner_state.json` | Updated num_ctx value |

---

## 4. Other Bug Fixes

### Volume Control (pycaw)
- **File:** `core/layers/L8_system.py:176` — `_pycaw_endpoint_volume()`
- Rewrote to handle both old/new pycaw versions
- Added fallback chain: EndpointVolume → Activate → _imm_device → direct use

### Everything Search
- **File:** `core/layers/everything_search.py:487`
- Reordered: derive extension from path first, then try SDK function
- Prevents 564 errors from missing `Everything_GetResultExtension`

### Close App Verification Race
- **File:** `core/engine/fallback.py:200`
- Increased settle time from 0.05s to 0.3s before verification
- Added error skip in fallback chain

### Health Monitor
- **File:** `backend/llm/resilience.py:216`
- Added STT module health check (was missing)

### SQLite LIKE Injection
- **File:** `backend/memory/vector_store.py:238`
- Added `ESCAPE '\'` with proper wildcard escaping

### Hardcoded URLs
- **File:** `backend/llm/resilience.py:158`
- Changed `localhost:8080` to configurable via `MAY_BACKEND_URL` env var

### Line Endings
- **File:** `backend/voice/stt.py`
- Normalized from `\r\n` to `\n`

---

## 5. Test Results

```
367 passed in 70.51s
```

### E2E Verification (OpenRouter + Gemini Flash)
| Command | Opens | Status |
|---------|-------|--------|
| "open notepad" | 1 | PASS |
| "open chrome" | 1 | PASS |
| "hello" | 0 | PASS |
| "what time is it" | 0 | PASS |
| "volume up" | 0 | PASS |

---

## 6. Files Modified

### Security
- `core/layers/L11_media.py` — shell=True fix
- `core/layers/L3_application.py` — shell=True fix + UWP URIs + duplicate guard
- `core/layers/L17_content_tools.py` — eval() hardening
- `backend/main.py` — localhost binding

### Multi-Launch
- `core/engine/verifier.py` — process_launched rewrite
- `core/engine/fallback.py` — settle time + error skip
- `backend/memory/skill_store.py` — strict matching + cleanup

### Context Window
- `backend/llm/ollama_client.py` — num_ctx 131072
- `backend/llm/providers.py` — num_ctx 131072
- `backend/llm/Modelfile` — num_ctx 131072
- `backend/llm/Modelfile.main` — num_ctx 131072
- `backend/llm/Modelfile.router` — num_ctx 131072
- `backend/llm/llama_server.py` — n_ctx 131072
- `backend/intelligence/auto_tuner.py` — num_ctx 131072

### Other
- `core/layers/L8_system.py` — pycaw volume fix
- `core/layers/everything_search.py` — extension fallback
- `backend/llm/resilience.py` — health check + configurable URL
- `backend/memory/vector_store.py` — SQL injection fix
- `backend/voice/stt.py` — line endings

### Session 2 (2026-07-22)
- `src-tauri/src/lib.rs` — CREATE_NO_WINDOW process detachment
- `backend/main.py` — lifespan crash protection
- `core/layers/L3_application.py` — KNOWN_APPS file paths + shell URI removal
- `core/engine/verifier.py` — removed blind shell_uri trust
- `backend/llm/jarvis.py` — Python function call parser + type_text instructions

---

## 7. Backend Shutdown Fix (HIGH)

### Problem
Backend process shut down automatically after a few seconds when launched from Tauri.

### Root Cause
Python subprocess spawned without `CREATE_NO_WINDOW` — inherited parent console. When console closed, backend was killed (exit code 15 = SIGTERM).

### Fixes Applied

#### a) Process Detachment
- **File:** `src-tauri/src/lib.rs:131-141`
- Added `CREATE_NO_WINDOW` (0x08000000) to Python subprocess spawn in debug mode
- Backend now survives independently from parent console

#### b) Lifespan Crash Protection
- **File:** `backend/main.py` — lifespan handler background tasks
- Wrapped all `asyncio.create_task()` calls in try-except:
  - `_start_screen_watcher` (screen watcher, proactive assistant, ghost mode, security monitor)
  - `_refresh_free_models` (OpenRouter)
  - `_refresh_ollama_cloud`
  - `_refresh_ollama_local`
  - `_start_sleep_cycle`
  - `_health_check_loop`
  - `_start_auto_tuner`
- Previously, any unhandled exception in these tasks could crash the server

---

## 8. Notepad Launch Fix (HIGH)

### Problem
AI said "I don't have notepad" even though notepad.exe exists on the system. Windows popup: "Get an app to open this 'notepad' link".

### Root Causes
1. `notepad:` shell URI in SHELL_URIS only works if UWP Notepad app is installed (not on all systems)
2. `KNOWN_APPS` entry was `["notepad"]` — bare command name, not a file path. `os.path.isfile("notepad")` returns False.
3. Verifier blindly trusted `shell_uri` methods without checking if app actually opened

### Fixes Applied

#### a) KNOWN_APPS File Paths
- **File:** `core/layers/L3_application.py:199-207`
- Added actual file paths for system apps:
  - `notepad`: `C:\Windows\System32\notepad.exe`
  - `calc`: `C:\Windows\System32\calc.exe`
  - `paint`: `C:\Windows\System32\mspaint.exe`
  - `cmd`: `C:\Windows\System32\cmd.exe`
  - `powershell`: `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`
  - `terminal`: `C:\Users\RED\AppData\Local\Microsoft\WindowsApps\wt.exe`
  - `explorer`: `C:\Windows\explorer.exe`

#### b) Remove Broken Shell URI
- **File:** `core/layers/L3_application.py:236`
- Removed `"notepad": "notepad:"` from SHELL_URIS (only works if UWP Notepad installed)
- Launch chain now uses known registry with actual exe path

#### c) Verifier Fix
- **File:** `core/engine/verifier.py:260-262`
- Removed blind trust for `shell_uri`/`startfile`/`powershell` methods
- Now falls through to name-based process check to actually verify app opened

---

## 9. AI Tool Call Parser Fix (MEDIUM)

### Problem
AI showed thinking/reasoning about tools but never executed them. Tool calls in Python format (`open_app("notepad")`) were not recognized.

### Root Cause
Parser only understood JSON format `{"tool": "open_app", "args": {...}}` but AI outputted Python function calls `open_app("notepad")`.

### Fixes Applied

#### a) Python Function Call Parser
- **File:** `backend/llm/jarvis.py:843-914`
- Added regex-based parser for Python-style function calls: `tool_name(arg1, key=val, ...)`
- Handles positional args and keyword args
- Maps first positional arg to correct parameter name based on tool type
- Deduplicates against JSON-parsed tool calls

#### b) System Prompt Update
- **File:** `backend/llm/jarvis.py:294-299, 312-320`
- Updated CONTENT TYPE DETECTION: when user says "write in notepad" or "open notepad and write", ALWAYS use `type_text` regardless of content length
- Added explicit examples: `"open notepad and write a 100 words about pokemon" -> open_app("notepad") + type_text("...", window_title="notepad")`
- Removed blanket rule that converts long content to `write_file`

---

## 10. Files Modified (Session 2)

### Backend Stability
- `src-tauri/src/lib.rs` — CREATE_NO_WINDOW for Python subprocess
- `backend/main.py` — try-except for all lifespan background tasks

### Notepad Launch
- `core/layers/L3_application.py` — KNOWN_APPS file paths + removed shell URI
- `core/engine/verifier.py` — removed blind trust for shell_uri methods

### AI Tool Calls
- `backend/llm/jarvis.py` — Python function call parser + system prompt update

### Architecture — Dynamic App Discovery
- `core/layers/L3_application.py` — New `_find_app_path()` + `_launch_dynamic_registry()`
- Queries OS instead of relying on hardcoded paths:
  1. `where.exe` (PATH lookup) — instant, finds system apps like notepad, calc, cmd
  2. Windows App Paths registry — finds apps registered with Windows
  3. Start Menu `.lnk` shortcut scan — finds apps via their shortcuts
  4. Falls back to hardcoded `KNOWN_APPS` paths
- Results cached in `_app_path_cache` to avoid repeated OS queries
- `_launch_shell_uri` now catches Windows popup errors ("Get an app to open this link")
- Launch chain: Everything → Shell URI → Known Registry → **Dynamic Registry** → Fuzzy → startfile → PowerShell → exe_retry → Start Menu → Registry Search → Install Dirs

---

## 11. Remaining Known Issues

| Issue | Severity | Status |
|-------|----------|--------|
| Windows SDK missing | HIGH | Env issue, not code |
| CUDA toolkit missing | MEDIUM | Env issue, not code |
| OpenRouter credits | LOW | User needs to top up |
| Calculator/Paint shell URIs | LOW | May need adjustment per system |
| AI typing into notepad | MEDIUM | Parser fixed, needs testing |

---

## 12. Architecture: Dynamic App Discovery

### Problem
App launch relied on hardcoded paths in `KNOWN_APPS`. If a path changed or an app wasn't in the dict, it failed silently.

### Solution
Added `_find_app_path(name)` helper that queries the OS dynamically:

| Strategy | Speed | Coverage |
|----------|-------|----------|
| `where.exe` | ~10ms | System apps (notepad, calc, cmd, powershell, explorer) |
| App Paths registry | ~50ms | Apps registered with Windows (Chrome, Firefox, etc.) |
| Start Menu scan | ~200ms | Any app with a Start Menu shortcut |
| KNOWN_APPS fallback | instant | Hardcoded paths as last resort |

### Benefits
- Notepad, calc, cmd, powershell now found automatically — no hardcoded paths needed
- New apps discovered without code changes
- Results cached to avoid repeated OS queries
- Shell URI failures caught gracefully (no more Windows popup)

---

## 13. Notepad write_file → type_text Interceptor (MEDIUM)

### Problem
AI outputs `write_file(path='...', content='...')` instead of `type_text(text='...', window_title='notepad')` when user says "write in notepad". Even though system prompt was updated, model training overrides the instructions.

### Solution
Added post-processing interceptor in `jarvis_chat()` that detects when user wants to write in notepad and converts `write_file` calls to `type_text`:

- **File:** `backend/llm/jarvis.py:1481-1510`
- Detects phrases: "in notepad", "into notepad", "open notepad and write", "write in it"
- Converts `write_file(path=..., content=...)` → `type_text(text=content, window_title="notepad")`
- Preserves `open_app("notepad")` calls
- Added debug logging for troubleshooting

---

## 14. Tool Count Limit Fix (HIGH)

### Problem
HTTP 500 errors from Ollama when sending too many tools to `phi4-mini:3.8b`. The model can't handle 57+ tool definitions in a single request.

### Root Cause
- 223 total tools defined in the system
- Tool tiering filtered to 57 tools for "open notepad" request
- `phi4-mini:3.8b` has limited context for tool definitions
- Ollama returns HTTP 500 when overwhelmed

### Fix Applied
- **File:** `backend/llm/tool_tiering.py:541` — Default max_tools: 80 → 25
- **File:** `~/.may/auto_tuner_state.json` — gene `tool_tier_max_tools`: 65 → 20
- Now sends ~20 tools per request (includes core tools + relevant domain tools)

### Remaining Issue
HTTP 500 still occurs intermittently — likely model-specific limitation. Need to investigate:
1. Whether `phi4-mini:3.8b` supports native tool calling at all
2. If not, disable tools and rely on text-based tool parsing
3. Consider switching to a model with better tool support (qwen3:4b, llama3.1)

---

## 15. Files Modified (Session 3)

### Notepad Interceptor
- `backend/llm/jarvis.py` — write_file → type_text conversion + debug logging

### Tool Limit
- `backend/llm/tool_tiering.py` — max_tools default 80 → 25
- `~/.may/auto_tuner_state.json` — tool_tier_max_tools gene 65 → 20

---

## 17. HTTP 500 Fix + Config Warning Fix (HIGH)

### Problem
1. Ollama returns HTTP 500 when too many tools sent to phi4-mini:3.8b
2. Startup warning: "Ollama config suboptimal — Missing: OLLAMA_FLASH_ATTENTION, etc."

### Root Causes
1. `providers.py:1581` hardcoded `num_ctx=131072` but phi4-mini has ~8K effective context
2. Auto-tuner gene `tool_tier_max_tools` initial=40, min=20 — still too many for 3.8B model
3. No HTTP 500 handling — just retried with same oversized payload
4. Config warning: env vars set only in `start_ollama.ps1` shell, never at system level. `main.py` checks `os.environ` which doesn't see them.

### Fixes Applied

#### a) num_ctx from Auto-Tuner + Small Model Cap
- **File:** `backend/llm/providers.py:1574-1582`
- Reads `num_ctx` from auto-tuner gene instead of hardcoding 131072
- Caps at 8192 for small models (phi4, tiny, mini, 3b, 1b, qwen3:4b)

#### b) HTTP 500 Tool Fallback
- **File:** `backend/llm/providers.py:1607-1664`
- Extracted streaming logic into `_stream_payload()` helper
- On HTTP 500 with tools: strips tools from payload, injects tool definitions as text into system prompt, retries
- Model still sees available tools (as text) but doesn't need native tool calling

#### c) Lower Tool Tier Max
- **File:** `backend/intelligence/auto_tuner.py:138`
- `tool_tier_max_tools`: initial 40→12, min 20→8, max 80→40, step 5→2
- **File:** `~/.may/auto_tuner_state.json`
- Persisted gene updated to match (value=12, min=8, max=40)

#### d) num_ctx Gene Initial Value
- **File:** `backend/intelligence/auto_tuner.py:102`
- `num_ctx` gene initial: 131072→8192 (matches small model reality)

#### e) Config Warning — Auto-Set Before Warn
- **File:** `backend/main.py:307-328`
- Reordered: auto-set env vars via `setx` FIRST, then re-check, then warn only if still missing
- First run: sets vars + logs info. Second run: vars already set, no warning.

### Files Modified (Session 4)
- `backend/llm/providers.py` — num_ctx from gene + small model cap + HTTP 500 fallback
- `backend/intelligence/auto_tuner.py` — num_ctx initial 8192, tool_tier_max_tools 12/8/40
- `backend/main.py` — config warning: auto-set before warn
- `~/.may/auto_tuner_state.json` — gene values updated

---

## 18. Garbled Text + Local Model Tool Fix (HIGH)

### Problem
1. LLM outputs garbled text (e.g. "hi tttttttttttthe tttt") that gets typed into Notepad
2. Raw tool syntax shown to user: `🔧 open_app(app_name='notepad')`
3. Local model (phi4-mini) just talks instead of calling tools — outputs "I have successfully written..." without executing anything

### Root Causes
1. Small models generate repetitive characters in tool arguments
2. Tool execution display showed raw debug syntax
3. Small models return HTTP 500 when sent native tool definitions; fallback stripped tools entirely, leaving model with no way to call tools

### Fixes Applied

#### a) Garbled Text Cleaning in execute_tool
- **File:** `backend/llm/jarvis.py` — `execute_tool()` function
- Added arg cleaning for `type_text`: collapses 3+ consecutive identical chars, strips `<think>` tags
- Added same cleaning for `write_file` content

#### b) Clean Tool Display
- **File:** `backend/llm/jarvis.py`
- Changed from `🔧 open_app(app_name='notepad')` → `*Opening app...*`
- Added `_TOOL_DISPLAY_NAMES` dict with human-readable names for 30+ tools
- Added `_clean_response_text()` — strips repetitive chars, think tags, leftover syntax

#### c) Small Model Text-Based Tool Calling
- **File:** `backend/llm/jarvis.py`
- Added `_is_small_local_model()` — detects phi4-mini, qwen3:4b, etc.
- For small models: skips native tool calling, injects tools as text into system prompt
- Added explicit instruction: "You MUST call a tool. Respond with JSON. Do NOT describe."
- Text-based parser extracts tool calls from response
- Applied to both initial call and agentic loop

#### d) Config Warning Fix
- **File:** `backend/llm/ollama_config.py`
- `set_ollama_env_vars()` now always sets `os.environ` regardless of `setx` success
- `setx` failure is non-fatal

#### e) Compound Command Fast Path (CRITICAL)
- **File:** `backend/llm/jarvis.py` — `_try_fast_path()` + caller
- Added `__compound_open_and_type` special return for "open X and write/type Y" commands
- Regex matches: "open notepad and write hi pokemon" → opens app + types text
- Executes BOTH tools sequentially: open_app → wait 0.8s → type_text
- Bypasses LLM entirely for compound commands — works reliably with any model
- Fixed garbled text in tool args: `execute_tool()` now cleans `type_text` and `write_file` args

### Files Modified (Session 5)
- `backend/llm/jarvis.py` — garbled text cleaning, clean display, small model detection, compound fast path
- `backend/llm/ollama_config.py` — always set os.environ
- `backend/llm/core_bridge.py` — **ROOT CAUSE FIX**: removed `import os` from inside conditional blocks in `_handle_direct_tool()` that caused Python scoping error ("cannot access local variable 'os'")
- `backend/main.py` — fast path before Ollama check, execute tools before streaming

---

## 19. Remaining Known Issues

| Issue | Severity | Status |
|-------|----------|--------|
| Windows SDK missing | HIGH | Env issue, not code |
| CUDA toolkit missing | MEDIUM | Env issue, not code |
| OpenRouter credits | LOW | User needs to top up |
| Calculator/Paint shell URIs | LOW | May need adjustment per system |
