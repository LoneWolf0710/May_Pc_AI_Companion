# May AI Companion -- Bug Tracker

> All bugs, errors, and problems found across 21+ sessions of development.
> Includes resolved bugs, newly discovered issues from project-wide audit, and known issues.

---

## Audit Summary (Session 22)

| Check | Result |
|:------|:-------|
| TypeScript compilation (`tsc --noEmit`) | 0 errors |
| Vite production build | 410 modules, 2.10s, no warnings |
| Python AST validation (all files) | All parse OK |
| Control engine tests | 89/89 pass (1 skipped) |

---

## Resolved Bugs

### Voice System Bugs

| # | Severity | File(s) | Bug Description | Root Cause | Fix |
|---|----------|---------|-----------------|------------|-----|
| V1 | CRITICAL | `useSpeechRecognition.ts`, `App.tsx` | `useEffect` killed backend STT mic capture -- voice input completely broken | A `useEffect` meant for cleaning up browser `webkitSpeechRecognition` also stopped the backend STT mic capture because both paths shared the same cleanup logic | Added `!useBackendSTT` guard to the useEffect cleanup so it only cleans up browser STT, not backend STT |
| V2 | HIGH | `App.tsx` | `handleVoiceToggle` always sent `"ollama"` as provider regardless of user selection | `handleVoiceToggle` was a `useCallback` that captured a stale `handleSendMessage` closure, which always used `provider: "ollama"` | Used `handleSendMessageRef.current()` (useRef pattern) instead of the stale closure reference |
| V3 | HIGH | `App.tsx` | `webkitSpeechRecognition` detected in Opera but didn't work in Tauri WebView2 | Opera exposes `webkitSpeechRecognition` in the DOM, but Tauri WebView2 doesn't support the Web Speech API | Set `useBackendSTT` to always `true` -- browser STT path is dead code kept as fallback |
| V4 | HIGH | `voice/stt.py` | faster-whisper spun for 60+ seconds detecting language on silence | Removing `language="en"` caused the model to run language detection on silent audio, which timed out | Re-added `language="en"` parameter to skip language detection entirely |
| V5 | MEDIUM | `voice/stt.py`, `App.tsx` | Attempted raw PCM capture to replace webm+ffmpeg -- was slower on CPU | Raw PCM capture produced larger buffers that were slower to transcribe with the CPU model | Reverted to webm+ffmpeg approach (smaller buffers, faster on CPU) |

### System Control Bugs

| # | Severity | File(s) | Bug Description | Root Cause | Fix |
|---|----------|---------|-----------------|------------|-----|
| S1 | HIGH | `system/control.py` | `pycaw` volume control crashed with AttributeError | pycaw COM object initialization failed silently on some Windows configurations | Added try/except with fallback to `SendKeys` volume up/down loop |
| S2 | MEDIUM | `system/control.py` | `os.startfile("discord")` silently failed -- Discord wouldn't open | `os.startfile()` only works with files, not app names. Discord isn't on PATH | Implemented 7-strategy app launcher: Shell URIs -> Known paths -> os.startfile -> PowerShell Start-Process -> .exe -> Start Menu search -> Common dirs |
| S3 | HIGH | `system/control.py` | Apps with multiple install locations (Chrome, Discord, VS Code) only had one path registered | `_KNOWN_APPS` dict had single string values per app | Changed to list-of-paths with alias resolution and visited-set loop prevention |
| S4 | HIGH | `system/control.py` | Discord special case: `Update.exe` needs specific args to launch | Discord uses `Update.exe --processStart Discord.exe` in its install directory | Added Discord-specific handling as first strategy before general path search |
| S5 | MEDIUM | `system/control.py` | `type_text` sent keystrokes to wrong window | SendKeys has no window focus -- keystrokes went to the most recently focused window, not the one just opened | Added PowerShell `AppActivate` to find and focus the most recently started window before sending keys |
| S6 | MEDIUM | `system/control.py` | `type_text` failed for text >200 chars | SendKeys dropped characters for long strings | Added clipboard paste fallback: base64-encoded `Set-Clipboard` + Ctrl+V for text >200 chars |
| S7 | MEDIUM | `system/control.py` | `open_file_with` with relative path (e.g. `api.txt`) failed | LLM generated relative paths that don't exist on disk | Added `rglob` search across Desktop, Documents, Downloads, Pictures, Videos, Music when path doesn't exist |

### LLM & Tool Execution Bugs

| # | Severity | File(s) | Bug Description | Root Cause | Fix |
|---|----------|---------|-----------------|------------|-----|
| L1 | CRITICAL | `llm/jarvis.py` | Text-based tool calls from OpenRouter/Anthropic never executed | When providers don't support native tool calling, LLM outputs JSON tool calls as plain text. These were never parsed -- tools silently did nothing | Implemented `_parse_text_tool_calls()` with brace-counting JSON extraction, deduplication, and JSON array support |
| L2 | HIGH | `llm/jarvis.py` | Raw JSON tool calls shown to user in chat messages | `_strip_tool_json()` didn't exist -- tool call JSON was part of the streamed text | Added `_strip_tool_json()` using brace-counting to remove both ```json blocks and bare JSON from conversational text |
| L3 | HIGH | `llm/jarvis.py` | Tool calls yielded during streaming (before all tokens received) | `jarvis_chat()` yielded text tokens as they arrived, including incomplete JSON tool calls | Buffer ALL text during streaming. After streaming completes: if tool calls found, execute them; otherwise yield clean text |
| L4 | MEDIUM | `llm/jarvis.py` | Multi-step tool chains only executed first tool | After executing tools, the LLM's follow-up response with additional tool calls was never parsed or executed | Implemented agentic loop: after tool execution, feed results back to LLM with tools still available, up to 5 rounds |
| L5 | MEDIUM | `llm/providers.py` | OpenAI-compatible streaming crashed on empty `choices` array | Some API responses return `{"choices": []}` during stream initialization | Added `if not choices: continue` guard before accessing `choices[0]` |

### Control Core Engine Bugs (Session 22)

| # | Severity | File(s) | Bug Description | Root Cause | Fix |
|---|----------|---------|-----------------|------------|-----|
| C1 | CRITICAL | `llm/core_bridge.py`, `llm/jarvis.py` | **20 tools from Phases 17-21 silently failed** -- returned "Unknown tool" | Email, wellness, meeting, ghost, and biometrics tools were defined in `tools.py` but had NO entry in `TOOL_CORE_MAP` in `core_bridge.py`. `jarvis.py` had no early routing for these tools either | (1) Added `_EMAIL_TOOLS`, `_WELLNESS_TOOLS`, `_MEETING_TOOLS`, `_GHOST_TOOLS` sets in jarvis.py with unified `_HTTP_TOOLS` routing before `execute_tool_via_core()`. (2) Added 20 entries to `TOOL_CORE_MAP` as `(None, None, None, None)` direct entries. (3) Implemented `_execute_http_tool()` handler for all HTTP-routed tools |
| C2 | HIGH | `llm/core_bridge.py` | File corruption from automated script inserting dict entries inside function body | A Python script used `content.rfind('get_weather')` which found the last occurrence (in `_handle_direct_tool`), then `content.find('}')` found the closing brace of a dict inside an f-string, splitting the `get_weather` handler | Rewrote `core_bridge.py` entirely to restore clean content with all 20 new entries properly placed in `TOOL_CORE_MAP` |
| C3 | MEDIUM | `tests/test_control_engine.py` | Test 1.5 expected success when verifier always fails on all methods | Test logic bug: verifier was set to always-fail but assertion expected `success=True` | Split into test 1.5a (verifier fails on m1, succeeds on m2) and test 1.5b (verifier always fails, asserts `success=False`) |
| C4 | MEDIUM | `tests/test_control_engine.py` | Test 1.13 expected success when verifier crashes on all methods | Test logic bug: verifier was set to always-crash but assertion expected `success=True` | Split into test 1.13a (verifier crashes on m1, succeeds on m2) and test 1.13b (verifier always crashes, asserts `success=False`) |
| C5 | LOW | `tests/test_control_engine.py` | Unicode box-drawing characters caused cp1252 encoding errors on Windows | `print()` calls contained Unicode characters (box-drawing, arrows, emojis) that Python's default cp1252 stdout encoding can't handle | Replaced all non-ASCII characters in print statements with ASCII equivalents |

### Backend & Integration Bugs

| # | Severity | File(s) | Bug Description | Root Cause | Fix |
|---|----------|---------|-----------------|------------|-----|
| B1 | MEDIUM | `backend/main.py` | Audio conversion (webm->wav->float32) duplicated 3 times | Same ffmpeg + wav parsing logic in transcribe, enroll, and verify endpoints | Extracted shared `_convert_webm_to_float32()` helper function |
| B2 | LOW | `voice/biometrics.py` | `preprocess_wav()` called without `source_sr` parameter | resemblyzer's `preprocess_wav` assumes 16kHz by default, but browser audio may be at different sample rates | Added explicit `source_sr=16000` parameter to `preprocess_wav()` calls |
| B3 | MEDIUM | `llm/providers.py` | OpenRouter-specific headers hardcoded in streaming function | `HTTP-Referer` and `X-Title` headers were embedded in the OpenRouter streaming function, preventing reuse for other OpenAI-compatible APIs | Extracted `_stream_openai_compatible()` generic function with configurable `base_url` and `extra_headers` |

---

## Newly Discovered Bugs (Session 22 Audit)

### Frontend Bugs

| # | Severity | File(s) | Bug Description | Impact |
|---|----------|---------|-----------------|--------|
| F1 | LOW | `src/components/SettingsModal.tsx` | STT model switch shows stale info during load -- UI still shows old model until POST completes | User sees incorrect model name for 1-3 seconds during switch |
| F2 | LOW | `src/components/SettingsModal.tsx` | STT model switch has no error feedback -- silent catch on failure | User has no idea if model switch failed |
| F3 | LOW | `src/hooks/useMicMonitor.ts` | Uses deprecated `ScriptProcessorNode` for PCM capture | Web Audio API spec deprecates this; should migrate to `AudioWorkletNode` for future browser compatibility |
| F4 | LOW | `src/components/ChatPanel.tsx` | TTS only plays in voice mode -- manual typed messages don't trigger TTS | Could be a user setting (design choice, not a bug per se) |
| F5 | LOW | `src/styles/globals.css` | `LoadingDots` CSS animation works via useState workaround because CSS `@keyframes` with `content` property is broken in Chromium WebView2 | The `LoadingDots` component uses JS-based frame switching instead of CSS animation as a workaround |

### Backend Bugs

| # | Severity | File(s) | Bug Description | Impact |
|---|----------|---------|-----------------|--------|
| P1 | MEDIUM | `llm/jarvis.py` | `_execute_http_tool()` opens `httpx.AsyncClient` context even for `voice_enroll` and `voice_verify` which don't make HTTP calls -- wasted connection pool overhead | Minor performance waste; opens and closes a TCP connection for each enroll/verify call |
| P2 | MEDIUM | `llm/core_bridge.py` | 20 new `(None, None, None, None)` TOOL_CORE_MAP entries route to `_handle_direct_tool()` which returns `"Direct handler not implemented"` -- only safe because jarvis.py intercepts first | If jarvis.py interception ever fails, these 20 tools silently return errors instead of executing |
| P3 | LOW | `llm/providers.py` | Duplicate model IDs in OpenRouter model list: `gemma2:2b`, `nvidia/nemotron-3-ultra-550b-a55b:free`, and `qwen3:4b` appear twice | Model selector may show duplicates; last entry wins in dict operations |
| P4 | LOW | `backend/main.py` | Remote control WebSocket handler (`/ws/remote`) hardcodes `provider="ollama"` and `model=PRIMARY_MODEL` | Remote control chat always uses Ollama regardless of user's selected provider |
| P5 | LOW | `voice/stt.py` | GPU fallback tests with a dummy transcription during `load_model()` -- if CUDA is broken, this adds 2-3 seconds to startup | The test transcription is necessary for safety but adds latency |

### Security Issues

| # | Severity | File(s) | Bug Description | Impact |
|---|----------|---------|-----------------|--------|
| SEC1 | HIGH | `integrations/email_monitor.py` | Email IMAP/SMTP credentials stored in plaintext at `~/.may/email.json` | Anyone with file access can read email passwords |
| SEC2 | MEDIUM | `integrations/smart_home.py` | Home Assistant access token stored in plaintext in config; placeholder `"your_token"` in default config | Token exposure if config file is leaked |
| SEC3 | HIGH | `remote/control.py`, `main.py` | Remote control has NO authentication -- anyone on the LAN can access `/remote` and send commands via WebSocket | Any device on the same network can control the user's PC |
| SEC4 | MEDIUM | `main.py` | Voice biometrics endpoints (`/voice/biometrics/*`) have no authentication | Anyone can enroll/verify/delete voice profiles remotely |
| SEC5 | MEDIUM | `main.py` | No rate limiting on `/voice/transcribe-audio` endpoint | Could be abused for DoS by sending repeated audio uploads |
| SEC6 | MEDIUM | `main.py` | No input sanitization on `_execute_http_tool()` parameters -- email UIDs, task IDs, query strings passed directly to HTTP endpoints | Potential for path traversal or injection via crafted tool arguments |
| SEC7 | LOW | `llm/core_bridge.py` | `run_powershell` tool executes arbitrary PowerShell commands with no sandboxing | The LLM can execute any command on the system (mitigated by destructive-action confirmation flow) |
| SEC8 | LOW | `plugins/__init__.py` | Plugin system loads from `~/.may/plugins/` with no signature verification | Malicious plugins could execute arbitrary code |

### Architecture & Design Issues

| # | Severity | Area | Bug Description | Impact |
|---|----------|------|-----------------|--------|
| A1 | MEDIUM | `llm/jarvis.py` | Hardcoded `http://localhost:8080` in `_execute_http_tool()` -- not configurable | If backend runs on different port, all HTTP-routed tools break silently |
| A2 | LOW | `knowledge.md` | Duplicate "Future Improvements" sections | Documentation confusion |
| A3 | LOW | `llm/tools.py` | `send_email` tool is in TOOL_CORE_MAP as `("system", "send_email", ...)` but the actual email sending is done via the email integration HTTP API | Tool routes through daemon system layer, which may not have the handler; unclear if it actually works |
| A4 | MEDIUM | `llm/providers.py` | `_stream_ollama_cloud` sets `num_ctx: 131072` (128K context) which may exceed model capacity | Could cause OOM or unexpected truncation for smaller models |
| A5 | LOW | `backend/main.py` | `preload_stt` uses `threading.Thread` for heavy model loading but `_start_screen_watcher` uses `asyncio.create_task` with polling -- inconsistent startup patterns | Could cause race conditions if endpoints are called before intelligence modules finish loading |
| A6 | LOW | Multiple | No health check endpoint for the Control Core daemon -- `is_daemon_running_sync()` only checks TCP connectivity | Daemon could be running but in a bad state; no way to check its internal health |

---

## Known Issues (Unresolved)

| # | Severity | Area | Description | Workaround |
|---|----------|------|-------------|------------|
| K1 | HIGH | Build | **Windows SDK missing** -- `cargo check` fails because `kernel32.lib` not found | Install Windows 11 SDK via Visual Studio Installer |
| K2 | MEDIUM | Voice | **CUDA toolkit missing** -- cublas64_12.dll not found, GPU falls back to CPU for STT | Install CUDA 12.x from nvidia.com/cuda-downloads |
| K3 | LOW | Avatar | **Rive not integrated** -- Avatar uses programmatic SVG, not Rive state machine | Planned for future (component is designed for easy swap) |
| K4 | LOW | LLM | **gemma2:2b not downloaded** -- Model routing always uses qwen3:4b | Run `ollama pull gemma2:2b` |
| K5 | LOW | Build | **Tauri Rust build fails** -- Needs Windows 11 SDK | Same as K1 |
| K6 | LOW | LLM | **Ollama Cloud API auth untested** -- Needs live testing | Requires Ollama Cloud account setup |
| K7 | LOW | System | **WiFi/Bluetooth toggle needs Admin** -- Some system control features require elevated privileges | Run May as administrator |
| K8 | LOW | System | **search_files/get_folder_size** -- No depth limit on rglob, could be slow on large directories | Add configurable depth limit |
| K9 | LOW | System | **pycaw volume fallback is approximate** -- SendKeys volume loop doesn't set absolute level | Use pycaw directly when available |
| K10 | MEDIUM | System | **type_text window focus is fragile** -- Finds most recently started window, not necessarily the target | Refactor to accept window title parameter from open_app return value |
| K11 | LOW | System | **Hardcoded _KNOWN_APPS paths** -- Some paths may not exist on all PCs | Start Menu search serves as fallback |
| K12 | LOW | LLM | **Remote control WebSocket hardcodes Ollama** -- Doesn't respect user's selected provider | Pass provider/model from frontend |
| K13 | LOW | LLM | **Wake word needs tflite-runtime** -- openwakeword defaults need tflite-runtime which isn't available on Windows | Install tflite-runtime when Windows support is added |
| K14 | LOW | LLM | **Smart Home needs Home Assistant setup** -- Integration implemented but requires HA instance | Configure Home Assistant URL and token |

---

## Bug Statistics

| Category | Found | Fixed | Remaining |
|:---------|------:|------:|----------:|
| Voice System | 5 | 5 | 0 |
| System Control | 7 | 7 | 0 |
| LLM & Tool Execution | 5 | 5 | 0 |
| Control Core Engine | 5 | 5 | 0 |
| Backend & Integration | 3 | 3 | 0 |
| Frontend (new) | 5 | 0 | 5 |
| Backend (new) | 5 | 0 | 5 |
| Security (new) | 8 | 0 | 8 |
| Architecture (new) | 6 | 0 | 6 |
| **Total Resolved** | **25** | **25** | **0** |
| **Total Unresolved** | -- | -- | **29** |
| **Grand Total** | **54** | **25** | **29** |

### Priority Fix Order for Unresolved Issues

1. **SEC3** (HIGH) -- Add PIN/token auth to remote control
2. **SEC1** (HIGH) -- Encrypt or use OS keychain for email credentials
3. **SEC5** (MEDIUM) -- Add rate limiting to voice transcription endpoint
4. **SEC6** (MEDIUM) -- Add input validation/sanitization to HTTP tool parameters
5. **SEC2** (MEDIUM) -- Encrypt Home Assistant token storage
6. **P1** (MEDIUM) -- Skip httpx client for tools that don't need it
7. **P2** (MEDIUM) -- Add fallback HTTP handlers in `_handle_direct_tool()` for the 20 new tools
8. **A1** (MEDIUM) -- Make backend URL configurable instead of hardcoded localhost:8080
9. **A4** (MEDIUM) -- Review `num_ctx: 131072` for Ollama Cloud compatibility
10. **P3** (LOW) -- Remove duplicate model entries from OpenRouter list

---

*Last updated: Session 22 -- Comprehensive project-wide audit. 25 bugs resolved, 29 remaining (8 security, 5 frontend, 5 backend, 6 architecture, 14 known issues). Full codebase validated: TypeScript 0 errors, Vite clean build, Python AST clean, 89/89 tests pass.*
