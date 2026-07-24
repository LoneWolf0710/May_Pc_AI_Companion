# 🔍 May AI Companion — Comprehensive Bug Audit

> **Generated:** Session 27 — Full codebase audit across all Python backend, Control Core, intelligence layer, integrations, voice system, memory, and frontend files.

---

## 📊 Summary

| Severity | Count | Status |
|:---|:---|:---|
| 🔴 Critical | 4 | 1 fixed, 3 open |
| 🟠 High | 7 | 7 fixed, 0 open |
| 🟡 Medium | 9 | 4 fixed, 5 open |
| 🔵 Low | 13 | 4 fixed, 9 open |
| **Total** | **33** | **16 fixed, 17 open** |

---

## 🔴 CRITICAL — Security & Data Loss Risks

### C1. Passwords stored in plaintext on disk
- **Files:** `backend/integrations/email_monitor.py`, `backend/integrations/smart_home.py`, `backend/llm/providers.py`
- **Details:** Email IMAP/SMTP passwords in `~/.may/email.json`, Home Assistant tokens in `~/.may/smart_home.json`, API keys in `~/.may/.api_keys.json` — all plain JSON, no encryption
- **Risk:** Anyone with file access can read all credentials
- **Fix:** Encrypt at rest using `keyring` library or system keychain, or at minimum XOR obfuscation with a machine-bound key
- **Status:** ⬜ Open

### C2. Backend listens on `0.0.0.0` with no auth on most endpoints
- **File:** `backend/main.py` line 1722
- **Details:** `uvicorn.run(app, host="0.0.0.0", port=8080)` exposes ALL endpoints to the entire LAN. Remote control has PIN auth, but `/api-keys`, `/email/send`, `/chat`, `/voice/transcribe-audio` etc. have ZERO auth.
- **Risk:** Anyone on the network can read API keys, send emails, execute arbitrary tools, read personal data
- **Fix:** Add FastAPI auth middleware (API key or JWT), or bind to `127.0.0.1` by default and only expose to LAN when remote control is explicitly enabled
- **Status:** ⬜ Open

### C3. `shell=True` in subprocess calls — command injection
- **File:** `core/layers/L9_browser.py` lines 783, 808; `core/layers/L2_process.py` line 201
- **Details:** `_subprocess.Popen(["start", url], shell=True, ...)` and `os.system(f"start {cmd}")` — direct shell injection via crafted URLs/commands
- **Fix:** Use `subprocess.Popen(["cmd", "/c", "start", "", url])` without `shell=True`; replace `os.system` with `subprocess.Popen` without shell
- **Status:** ✅ **Fixed** (Session 27)

### C4. `run_powershell` tool executes arbitrary commands with bypassable confirmation
- **File:** `backend/llm/jarvis.py`
- **Details:** `run_powershell` is in `DESTRUCTIVE_TOOLS`, but the confirmation check `args.get("confirm")` could be set by the LLM itself in its tool call args, bypassing user confirmation
- **Fix:** Strip `confirm` from destructive tool args when user's message isn't a confirmation, then set it only from the confirmation flow
- **Status:** ✅ **Fixed** (Session 27)

---

## 🟠 HIGH — Bugs That Cause Failures

### H1. `get_unread_emails` expects wrong API response format
- **File:** `backend/llm/jarvis.py`
- **Details:** Email tools check `if isinstance(data, list)` but the API returns `{"emails": [...], "count": N}`. Same bug in `search_emails` and `get_recent_emails`.
- **Fix:** Parse `data.get("emails", [])` with dict/list fallback
- **Status:** ✅ **Fixed** (Session 27)

### H2. `get_wellness_suggestions` shows raw dict instead of message
- **File:** `backend/llm/jarvis.py`
- **Details:** Response is `{"suggestions": [{"message": "...", ...}]}` but code does `f"  - {s}"` on each dict
- **Fix:** Extract `s.get("message", str(s))` from each suggestion
- **Status:** ✅ **Fixed** (Session 27)

### H3. `meeting_mode.py` has hardcoded Ollama URL
- **File:** `backend/intelligence/meeting_mode.py`
- **Details:** Directly calls `http://localhost:11434/api/chat` instead of using `MAY_BACKEND_URL`
- **Fix:** Read `MAY_BACKEND_URL` env var, fall back to localhost:8080
- **Status:** ✅ **Fixed** (Session 27)

### H4. `screen_watcher.py` loop runs one extra cycle after stop
- **File:** `backend/intelligence/screen_watcher.py`
- **Details:** `while True:` loop checks `self._active` AFTER `await asyncio.sleep()`, so one extra iteration runs after `stop()`
- **Fix:** Changed `while True:` to `while self._active:` and `continue` to `break`
- **Status:** ✅ **Fixed** (Session 27)

### H5. `biometrics.py` imports numpy at module level
- **File:** `backend/voice/biometrics.py`
- **Details:** Top-level `import numpy as np` crashes entire biometrics module if numpy unavailable
- **Fix:** Replaced with lazy `_get_np()` helper
- **Status:** ✅ **Fixed** (Session 27)

### H6. `ghost_mode.py` imports jarvis_chat inside method
- **File:** `backend/intelligence/ghost_mode.py`
- **Details:** `from llm.jarvis import jarvis_chat` inside `_autonomous_execute()` depends on sys.path being correct; bare except silently swallows import failures
- **Fix:** Added `set_jarvis_chat()` setter (like `set_executor()`), wired from `main.py` during startup. Lazy fallback stored on `self` for safety.
- **Status:** ✅ **Fixed** (Session 27)

### H7. `voice/stt.py` has inconsistent `\r\n` line endings
- **File:** `backend/voice/stt.py`
- **Details:** Windows `\r\n` line endings while all other files use Unix `\n`
- **Fix:** Normalize to `\n` line endings
- **Status:** ⬜ Open

---

## 🟡 MEDIUM — Code Quality & Reliability

### M1. 188 bare `except Exception` catches (99 with just `pass`)
- **Scope:** 50+ files
- **Status:** ⬜ Open

### M2. Global variable mutations — race conditions in async code
- **Details:** `stt`/`_stt_forced_model` in main.py, `_pending_tool_calls` in jarvis.py
- **Status:** ✅ **Fixed** (Session 27) — `_stt_lock` and `_pending_lock` asyncio.Lock()

### M3. `_pending_tool_calls` race condition in jarvis.py
- **Status:** ✅ **Fixed** (Session 27) — `_pending_lock` asyncio.Lock() with snapshot-under-lock pattern

### M4. `send_email` tool not in `DESTRUCTIVE_TOOLS`
- **Status:** ✅ **Fixed** (Session 27)

### M5. `delete_folder` and `format_disk` missing from `DESTRUCTIVE_TOOLS`
- **Status:** ✅ **Fixed** (Session 27)

### M6. SQLite LIKE wildcard not sanitized in vector_store.py
- **Status:** ⬜ Open

### M7. Missing `__init__.py` exports for intelligence modules
- **Status:** ⬜ Open

### M8. `type_text` window_title not enforced
- **Status:** ⬜ Open

### M9. Email endpoint `/email/{uid}` has no UID format validation
- **Status:** ⬜ Open

---

## 🔵 LOW — Minor Issues & Technical Debt

### L1. Dead code: `backend/system/fallback.py`
- **Status:** ⬜ Open

### L2. `settings.py` silently ignores unknown keys
- **Status:** ⬜ Open

### L3. Health monitor only checks 3 of 6 registered services
- **Status:** ✅ **Fixed** (Session 27) — Added memory + intelligence checks

### L4. Dead code: `handle_command()` in main.py
- **Status:** ⬜ Open

### L5. `_search_files_params` doesn't forward `max_depth`
- **Status:** ⬜ Open

### L6. `test_internet` uses only Google DNS
- **Status:** ⬜ Open

### L7. `screen_watcher` hash collision for same-title windows
- **Status:** ⬜ Open

### L8. Weather empty string city bypasses IP geolocation
- **Status:** ✅ **Fixed** (Session 27)

### L9. Frontend `config.ts` has hardcoded `BACKEND_URL`
- **Status:** ⬜ Open

### L10. No `requirements.txt` version pinning
- **Status:** ⬜ Open

### L11. `ghost_mode.py` task counter not persisted across restarts
- **Status:** ✅ **Fixed** (Session 27)

### L12. Deprecated `ScriptProcessorNode` in useMicMonitor.ts
- **Status:** ⬜ Open

### L13. `voice/stt.py` has `\r\n` line endings
- **Status:** ⬜ Open

---

## ✅ Previously Fixed (Sessions 22-26)

| ID | Issue | Fixed In |
|:---|:---|:---|
| F1 | `search_files`/`get_folder_size` no depth limit | Session 27 — L1_filesystem.py |
| F2 | Daemon readiness not signaled | Session 27 — main.py TCP probe |
| F3 | Limited `_handle_direct_tool` coverage | Session 27 — 28 total handlers |
| F4 | Verifier results unused by core_bridge | Session 27 — `[verified]` appended |
| F5 | pycaw volume fallback | Session 27 — Direct pycaw handlers |
| F6 | Duplicate `_execute_http_tool` | Session 26 |
| F7 | `close_app` param mismatch | Session 26 |
| F8 | `search_files` param mismatch | Session 26 |
| F9 | Daemon health check timing | Session 26 |
| F10 | Weather 500 error (surrogate pairs) | Session 22 |
| F11 | `os.path.basename` undefined `os` | Session 22 |
| F12 | Chat slow with 171 tools | Session 23 — Tool tiering |
| F13 | Duplicate OpenRouter models | Session 21.5 |
| F14 | shell=True command injection | Session 27 — L9/L2 |
| F15 | Email tools wrong format | Session 27 |
| F16 | Wellness raw dict display | Session 27 |
| F17 | Meeting hardcoded URL | Session 27 |
| F18 | Biometrics top-level numpy | Session 27 |
| F19 | send_email not in DESTRUCTIVE_TOOLS | Session 27 |
| F20 | Health monitor missing checks | Session 27 |
| F21 | Weather empty string city | Session 27 |
| F22 | Ghost task counter collisions | Session 27 |
| F23 | Screen watcher extra cycle (H4) | Session 27 |
| F24 | run_powershell confirmation bypass (C4) | Session 27 |
| F25 | Ghost mode fragile import (H6) | Session 27 |
| F26 | _pending_tool_calls race (M3) | Session 27 |
| F27 | stt/stt_forced_model race (M2) | Session 27 |
