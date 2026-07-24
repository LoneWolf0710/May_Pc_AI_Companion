# FKerrors.md — May Project Error & Bug Report

**Audited:** 2026-07-21
**Scope:** Runtime artifacts under `C:\Users\RED\.may\` (audit log, control_core.log, JSON state, DBs)
**Overall action success rate:** 89.5% (111/124) — inflated by slow 14–20s "success via fallback" launches

---

## 🔴 CRITICAL

### 1. Audit log hash-chain is BROKEN (tamper-evidence defeated)
`audit_log.jsonl` claims to be a cryptographically chained tamper-proof trail (`prev_hash` → `hash`), but:
- **98 of 124 entries have broken chain links** — `prev_hash` does NOT match the previous entry's `hash`.
- **5 separate "genesis" entries** exist (should be exactly 1).
- `prev_hash` only advances on **daemon restart**, not per-entry. Up to **21 consecutive entries reuse the same `prev_hash`** (e.g. `3174af46...` reused 21×, `092cf71c...` 13×, `2f8f6563...` 12×).

**Root cause:** Daemon loads `prev_hash` once at startup and never updates in-memory `last_hash` after writing each entry. On restart it also fails to read the real tail hash (hence repeated "genesis").

**Impact:** Entire tamper-evidence guarantee is void. Entries can be deleted/reordered/forged within a session undetectably. Critical for a system logging `close_app`, registry, and system-level actions.

**Fix:** After writing each entry, set `self.last_hash = entry["hash"]`. On startup, seed `last_hash` from the hash of the last non-empty line (fall back to `"genesis"` only if file is empty).

---

## 🟠 HIGH

### 2. `system.get_volume` is 100% broken — 119 failures
```
Method method_1__get_volume_pycaw failed: 'AudioDevice' object has no attribute 'Activate'
```
Every volume query fails. pycaw API misuse / version incompatibility — `Activate` must be called on an `IMMDevice`, not the `AudioDevice` wrapper. Correct pattern: `AudioUtilities.GetSpeakers()` → `.Activate(IAudioEndpointVolume._iid_, ...)`. No working fallback → volume control entirely dead.

### 3. Privilege escalation is broken — 31 errors
```
ERROR | may.core.privilege | Failed to open process token: [WinError 0] The handle is invalid.
Token privileges enabled: 0/8
NOT running as admin — some operations will fail
```
`OpenProcessToken` passed an invalid handle. Result: **0 of 8 privileges enabled**, every session. Elevated operations silently degrade.

---

## 🟡 MEDIUM

### 4. "Everything" search integration misconfigured — 564+ errors
```
Error reading result N: function 'Everything_GetResultExtension' not found   (×564)
Everything DB not loaded yet — is Everything running?                        (×76)
HTTP search failed: All connection attempts failed
```
- Wrong/old `Everything64.dll` — `Everything_GetResultExtension` doesn't exist in loaded DLL version (API mismatch). Fires on every result of every search.
- HTTP/es.exe fallbacks also fail ("All connection attempts failed") → no working path when DB isn't loaded, just an 8s timeout.

### 5. App-launch fallback chain slow and noisy — 74 exhaustions, 1830 warnings
- `launch_app` failed all methods **74 times**; **1,830 fallback warnings** total.
- Common apps fail repeatedly: `notepad` (`launch_shell_uri` + `known_registry` both fail 38–40× each), `file explorer`, `discord`, `opera`.
- Latencies of **14–24 seconds** logged for fallback launches (`pc manager` 14.6s, `nte` 20s) — walks 7–10 methods serially with per-method timeouts.
- Notepad should never reach the fallback chain. Known-app registry is missing baseline Windows apps.

### 6. `close_app` verification races — 149 verification failures
```
Verification failed for application.close_app.method_2__close_taskkill — trying next method   (×27+)
taskkill failed for 'store.exe' / 'calculator.exe' / 'microsoft store.exe': process not found
```
- UWP apps (Store, Calculator) don't run as `<name>.exe` — taskkill by image name fails.
- Verification fires too fast after kill, before process actually exits (149 "verification failed → trying next method").

---

## 🔵 LOW / HOUSEKEEPING

### 7. Plaintext PIN & 20 MB unrotated log
- `remote_pin.json` stores remote-access PIN in **plaintext** (`"pin": "04AFF9"`) next to the encrypted key store.
- `control_core.log` is **20 MB** with no rotation; full of DEBUG-level "Error reading result N" spam (564 lines) that shouldn't be per-result DEBUG.

### 8. Ambiguous single-word commands cause destructive-intent failures
```
close_app "it"        → tries to taskkill "it.exe"
open_app "api_key.txt" → tries to launch a data file as an app
```
No guard against 1–2 char / pronoun app names or non-executable targets.

### 9. Auto-tuner has stalled
`auto_tuner_state.json`: fitness flat at **0.405 for the last ~10 cycles**, `is_running: false`, and several genes have `step_size: 0.0` (temperature, reflex_threshold, conciseness…) meaning **those genes can never mutate** — the GA does nothing for them.

---

## 📊 Summary Table

| Severity | Issue | Signal |
|----------|-------|--------|
| 🔴 Critical | Audit hash-chain broken | 98/124 broken links, 5 genesis |
| 🟠 High | `get_volume` dead | 119 failures |
| 🟠 High | Privilege token invalid | 31 errors, 0/8 privs |
| 🟡 Medium | Everything DLL mismatch | 564+ errors |
| 🟡 Medium | Launch fallback slow/noisy | 74 exhausted, 1830 warns |
| 🟡 Medium | close_app verify races | 149 fails |
| 🔵 Low | Plaintext PIN, 20MB log | — |
| 🔵 Low | Auto-tuner stalled, dead genes | flat 0.405 |
