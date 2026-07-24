# What's Done — May AI Companion Fixes Summary

> **Date:** July 18, 2026  
> **Session:** L16 UIAutomation — Hermes-level computer-use agent

---

## 🧠 **L16 UIAutomation Implementation (July 18, 2026)**

### 31. **Phase 1: Accessibility Tree Tools (11 tools)** ✅
- **Problem:** May couldn't interact with Windows apps by UI structure — only by coordinates (fragile)
- **Fix:** Created `core/layers/L16_uiautomation.py` with 11 tools:
  - `inspect_ui_tree` — Read full UI tree of any window
  - `find_ui_element` — Find element by role + name or automation_id
  - `click_ui_element` — Click element by role + name
  - `double_click_ui_element` / `right_click_ui_element`
  - `type_into_ui_element` — Type into specific input element
  - `select_ui_dropdown` / `toggle_ui_checkbox`
  - `read_ui_text` / `set_ui_value` / `get_ui_state`
- **Key Features:** 30+ role alias map, LRU connection cache, Edit/Document cross-search

### 32. **Phase 2: Post-Action Verification (4 tools)** ✅
- `take_action_verify` — Screenshot after any action
- `verify_element_exists` — Poll UIA tree for element presence
- `verify_no_error` — Scan windows for error dialogs
- `compare_screenshots` — pHash + pixel diff comparison

### 33. **Phase 3: Wait Tools (3 tools)** ✅
- `wait_for_app` — Wait for window to appear
- `wait_for_element` — Wait for UI element in accessibility tree
- `wait_for_text` — Wait for text to appear/disappear

### 34. **Connection Reliability Fixes** ✅
- 3-strategy connection: cache → Application.connect(re.escape) → Desktop scan fallback
- `top_window()` fallback in `_get_window_element`
- Edit/Document cross-search in `_find_element_by_role_and_name`

### 35. **Role-Only Bug Fixes** ✅
- Fixed `find_ui_element` and `click_ui_element`: `role and name` → `role`

### 36. **E2E Test Script** ✅
- `tests/test_l16_uiautomation.py` — 18-step Notepad test
- Last run: 12/18 passing (67%)

---

## 📁 **Files Modified**

| File | Changes |
|------|---------|
| `core/layers/L16_uiautomation.py` | **NEW** — 18 tools, 3-strategy connection |
| `core/daemon.py` | Registered uiautomation + verify layers |
| `core/router.py` | Added to VALID_LAYERS + aliases |
| `backend/llm/tools.py` | 18 tool definitions |
| `backend/llm/core_bridge.py` | 18 tool->layer mappings |
| `backend/llm/tool_tiering.py` | uiautomation + verification tiers |
| `tests/test_l16_uiautomation.py` | **NEW** — E2E test |

---

## ✅ **Verification**

| Test | Status |
|------|--------|
| All AST validation (7 files) | ✅ |
| E2E test: 12/18 passing | 🟡 |

---

## 📋 **Remaining**

1. E2E timing failures (6/18) — pywinauto connection timing
2. Final code review needed (rate-limited)
3. Phase 3 tools wired but not re-tested after final wiring

---

**Total:** 18 new tools, 196 total tools in May
