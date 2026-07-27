"""
May's Jarvis Brain — LLM-powered tool calling for universal PC control.

Every user message goes through the LLM which decides what tools to call.
No pattern matching. The LLM IS the controller.

Tools are executed via the Control Core daemon (TCP on port 7650).
Tools without a core mapping fall back to direct SystemControl.
"""

import json
import logging
import os
import re
import asyncio
from typing import AsyncGenerator

logger = logging.getLogger("may.jarvis")

# Resilience helpers (P4: graceful degradation)
from llm.resilience import format_partial_results as _format_partial_results

# All tool definitions
from .tools import TOOLS

# Intent-based tool tiering — sends only relevant tools per request
from .tool_tiering import get_tools_for_message

# Tool executor — routes through control core daemon via TCP
from .core_bridge import execute_tool_via_core

# Plugin system
from plugins import get_plugin_manager

# P2 SECURITY: Risk classification + audit logging
try:
    from system.risk_classifier import classify_action, needs_confirmation, RiskTier
    from system.audit_log import log_action as _audit_log
    _SECURITY_AVAILABLE = True
except ImportError:
    _SECURITY_AVAILABLE = False
    # Fallback stubs
    def classify_action(tool_name, params=None): return "safe"
    def needs_confirmation(tool_name, params=None, control_mode="ask_before_action"): return tool_name in DESTRUCTIVE_TOOLS
    class RiskTier:
        SAFE = "safe"
        MODERATE = "moderate"
        DESTRUCTIVE = "destructive"
        CRITICAL = "critical"
    def _audit_log(**kwargs): pass
_plugin_manager_ref = None  # Set by main.py after plugin manager loads
_control_modes_ref = None  # Set by main.py after intelligence loads
_memory_injector_ref = None  # Set by main.py after intelligence loads
_skill_store_ref = None  # Set by main.py after memory loads
_immune_system_ref = None  # Set by main.py after security loads
_conditioned_reflexes_ref = None  # P4: Set by main.py after intelligence loads
_screen_watcher_ref = None  # P4: Set by main.py for Tier 2 screen context

# ── Pronoun Resolution — tracks context for "in it", "close it", etc. ─────
_last_opened_app: str = ""
_last_created_file: str = ""
_last_searched_query: str = ""


def _resolve_pronouns(message: str) -> str:
    """Resolve pronouns like 'in it', 'close it', 'save it' using conversation state.

    Architecture spec (Part 6): ConversationState tracks last_opened_app,
    last_created_file, last_searched_query. Resolves 'in it', 'save it', 'close it'.
    Handles natural variations like 'turn it off', 'make it bigger', etc.
    """
    lower = message.lower()
    result = message
    
    # ── App references ──
    if _last_opened_app:
        # "in it" / "in there" / "in that" -> "in {app}" (use word boundary to avoid 'unit')
        for pattern in ("in it", "in there", "in that"):
            if re.search(r'\b' + re.escape(pattern) + r'\b', lower):
                result = re.sub(r'\b' + re.escape(pattern) + r'\b', f"in {_last_opened_app}", result, flags=re.IGNORECASE)
        
        # "close it" / "close that" / "close this" -> "close {app}"
        for pattern in ("close it", "close that", "close this"):
            if re.search(r'\b' + re.escape(pattern) + r'\b', lower):
                result = re.sub(r'\b' + re.escape(pattern) + r'\b', f"close {_last_opened_app}", result, flags=re.IGNORECASE)
        
        # "open it" / "open that" / "open this" -> "open {app}"
        for pattern in ("open it", "open that", "open this"):
            if re.search(r'\b' + re.escape(pattern) + r'\b', lower):
                result = re.sub(r'\b' + re.escape(pattern) + r'\b', f"open {_last_opened_app}", result, flags=re.IGNORECASE)
        
        # "restart it" / "restart that" -> "restart {app}"
        for pattern in ("restart it", "restart that", "relaunch it"):
            if re.search(r'\b' + re.escape(pattern) + r'\b', lower):
                result = re.sub(r'\b' + re.escape(pattern) + r'\b', f"restart {_last_opened_app}", result, flags=re.IGNORECASE)
        
        # "maximize it" / "minimize it" -> "maximize/minimize {app}"
        for pattern in ("maximize it", "maximize that", "maximize this"):
            if re.search(r'\b' + re.escape(pattern) + r'\b', lower):
                result = re.sub(r'\b' + re.escape(pattern) + r'\b', f"maximize {_last_opened_app}", result, flags=re.IGNORECASE)
        for pattern in ("minimize it", "minimize that", "minimize this"):
            if re.search(r'\b' + re.escape(pattern) + r'\b', lower):
                result = re.sub(r'\b' + re.escape(pattern) + r'\b', f"minimize {_last_opened_app}", result, flags=re.IGNORECASE)
    
    # ── File references (with word boundaries) ──
    if _last_created_file:
        # "save it" / "save that" -> "save {file}"
        for pattern in ("save it", "save that", "save this"):
            if re.search(r'\b' + re.escape(pattern) + r'\b', lower):
                result = re.sub(r'\b' + re.escape(pattern) + r'\b', f"save {_last_created_file}", result)
        
        # "open it" when referring to a file -> "open {file}"
        if _last_opened_app == "":
            for pattern in ("open it", "open that", "open this"):
                if re.search(r'\b' + re.escape(pattern) + r'\b', lower):
                    result = re.sub(r'\b' + re.escape(pattern) + r'\b', f"open {_last_created_file}", result)
    
    # ── Search query references (with word boundaries) ──
    if _last_searched_query:
        # "search that" / "search for that" -> "search for {query}"
        for pattern in ("search that", "search for that", "look that up", "look it up"):
            if re.search(r'\b' + re.escape(pattern) + r'\b', lower):
                result = re.sub(r'\b' + re.escape(pattern) + r'\b', f"search for {_last_searched_query}", result)
    
    # ── Generic pronoun fixes for natural speech ──
    # "turn it on" / "turn it off" when referring to an app
    if _last_opened_app:
        if "turn it on" in lower:
            result = result.replace("turn it on", f"open {_last_opened_app}")
        if "turn it off" in lower:
            result = result.replace("turn it off", f"close {_last_opened_app}")
    
    return result


def _update_pronoun_state(tool_name: str, args: dict):
    """Update pronoun resolution state after a tool executes.

    Tracks last opened app, created file, and searched query so pronouns
    like 'in it', 'save it', 'close it' resolve correctly in follow-up messages.
    Also tracks for natural speech like 'turn it on/off', 'restart it', etc.
    """
    global _last_opened_app, _last_created_file, _last_searched_query
    if tool_name in ("open_app", "launch_with_args", "launch_as_admin"):
        _last_opened_app = args.get("app_name", "")
    elif tool_name in ("close_app", "force_close_app"):
        _last_opened_app = ""  # Clear when app is closed
    elif tool_name == "write_file":
        _last_created_file = args.get("path", "")
    elif tool_name == "web_search":
        _last_searched_query = args.get("query", "")
    elif tool_name == "type_text":
        # Track window_title as last opened app for typing context
        # Only set when window_title differs from current (avoid unnecessary overwrites)
        wt = args.get("window_title", "")
        if wt and wt.lower() != _last_opened_app.lower():
            _last_opened_app = wt


def _get_all_tools() -> list[dict]:
    """Get all tools: built-in + plugin tools."""
    all_tools = list(TOOLS)
    pm = _plugin_manager_ref
    if pm is not None:
        all_tools.extend(pm.get_all_plugin_tools())
    return all_tools


def _get_tools_for_message(message: str) -> list[dict]:
    """Get tools filtered by message intent using tiering.

    Returns only the ~20-40 tools relevant to the user's request
    instead of all 171 tools. Dramatically reduces token usage
    and speeds up LLM response time.
    """
    all_tools = _get_all_tools()
    return get_tools_for_message(message, all_tools)


def _is_small_local_model(model: str) -> bool:
    """Check if a model is too small for native tool calling.

    Small models (phi4-mini, qwen3:4b, qwen3:0.6b etc.) often return HTTP 500
    when sent native tool definitions, or produce reasoning dumps instead of
    tool calls. For these, we inject tools as text into the system prompt.
    """
    model_lower = model.lower()
    small_markers = ("phi4", "tiny", "mini", "3b", "1b", "0.6b", "0.5b", "qwen3:4b", "qwen2.5:3b")
    # Also catch any model with a sub-4B size pattern like ":1.5b", ":0.6b", ":2b"
    import re as _re_small
    if _re_small.search(r':\d*\.?\d+b\b', model_lower):
        # Extract the number before 'b'
        size_match = _re_small.search(r':(\d*\.?\d+)b\b', model_lower)
        if size_match:
            try:
                size_val = float(size_match.group(1))
                if size_val < 8:  # Sub-8B models can't do reliable native tool calling
                    return True
            except ValueError:
                pass
    return any(m in model_lower for m in small_markers)


def set_plugin_manager(manager):
    """Called by main.py to register the plugin manager instance."""
    global _plugin_manager_ref
    _plugin_manager_ref = manager


def set_control_modes(control_modes):
    """Called by main.py to register the control modes instance."""
    global _control_modes_ref
    _control_modes_ref = control_modes


def set_memory_injector(injector):
    """Called by main.py to register the memory injector instance."""
    global _memory_injector_ref
    _memory_injector_ref = injector


def set_skill_store(store):
    """Called by main.py to register the skill store instance."""
    global _skill_store_ref
    _skill_store_ref = store


def set_immune_system(system):
    """Called by main.py to register the immune system instance."""
    global _immune_system_ref
    _immune_system_ref = system


# P4: Conditioned reflexes + screen context setters
def set_conditioned_reflexes(reflexes):
    """Called by main.py to register the conditioned reflexes instance."""
    global _conditioned_reflexes_ref
    _conditioned_reflexes_ref = reflexes


def set_screen_watcher_for_context(watcher):
    """Called by main.py to register the screen watcher for Tier 2 context injection."""
    global _screen_watcher_ref
    _screen_watcher_ref = watcher

# ── Shadow learning integration (avoids circular import with main.py) ─────
_shadow_learner_ref = None  # Set by main.py after intelligence loads
_personality_modes_ref = None  # Set by main.py for personality prompt injection


def _record_shadow_event(action_type: str, target: str, timestamp: float):
    """Record an action event for shadow learning. Called after every tool execution."""
    ref = _shadow_learner_ref
    if ref is not None:
        ref.record_event(action_type, target, timestamp)


def set_shadow_learner(learner):
    """Called by main.py to register the shadow learner instance."""
    global _shadow_learner_ref
    _shadow_learner_ref = learner


def set_personality_modes(modes):
    """Called by main.py to register the personality modes instance."""
    global _personality_modes_ref
    _personality_modes_ref = modes


# ── Personality prompt (trimmed for token efficiency) ──────────────────────
# Reduced from ~2000 tokens to ~800 tokens to save API quota.
# Key info preserved: personality, behavior rules, tool guidelines.
# P5: Personality genes (tilde_frequency, response_concisseness) dynamically
# modify the prompt via _build_dynamic_prompt().

JARVIS_SYSTEM_PROMPT_BASE = """You are May, an AI companion (Shikimori-inspired). Cool, calm, caring, subtly cute.

CAPABILITIES: Full PC control via tools — open apps, volume, files, web search, media, screenshots, emails, reminders, etc.

BEHAVIOR:
- DO something -> use tool(s). QUESTION -> answer with tools if needed. CHAT -> respond naturally, no tools.
- Keep responses SHORT. Never say "As an AI".
- Destructive actions (delete, shutdown, kill, install) need confirmation first.
- When asked to DO something, ALWAYS execute the tool(s) — do not just describe what you would do.

MULTI-STEP (CRITICAL): Call ALL required tools in a SINGLE response. Do not stop after one.
- "open notepad and write hello" -> open_app("notepad") + type_text("hello", window_title="notepad") in ONE response.
- "open notepad and write a 100 words about pokemon" -> open_app("notepad") + type_text("Pokemon content...", window_title="notepad") — ALWAYS type into notepad regardless of content length.
- "open chrome, search for cats, then screenshot" -> open_app("chrome") + web_search("cats") + screenshot() in ONE response.
- "set volume to 50 and open spotify" -> set_volume(50) + open_app("spotify") in ONE response.

NATURAL LANGUAGE UNDERSTANDING:
Users speak naturally. Parse intent, not exact words:
- "can you open chrome" / "launch chrome" / "start up chrome" / "chrome please" -> open_app("chrome")
- "turn the volume up" / "make it louder" / "crank the volume" -> volume_up()
- "dim the screen" / "brightness down" / "it's too bright" -> set_brightness(level=-10)
- "what time is it" / "got the time" / "what's the clock say" -> get_time()
- "am i online" / "do i have internet" / "is the wifi working" -> test_internet()
- "how much battery" / "power status" / "battery level" -> battery_info()
- "take a pic" / "screenshot" / "capture my screen" -> screenshot()
- "what am i looking at" / "describe screen" / "what's on my screen" -> describe_screen()

CONTENT GENERATION (CRITICAL — like Google Assistant):
When the user asks you to "write", "make", "create", "draft", "compose", "list", "note", " jot", "put down", "type up", or "put together" something, you must GENERATE the content yourself — do NOT type their request literally.
The user's request is a COMMAND to create content, not the content itself.

Examples:
- "write a list for me in notepad" -> open_app("notepad") + type_text("Shopping List:\n1. Milk\n2. Eggs\n3. Bread", window_title="notepad")
- "make me a to-do list" -> type_text("To-Do List:\n- Task 1\n- Task 2\n- Task 3", window_title="notepad")
- "write a poem about cats" -> type_text("A Poem About Cats\n\nSoft paws on velvet feet,\nPurring secrets, bittersweet...", window_title="notepad")
- "draft an email for me" -> type_text("Dear [Name],\n\nI am writing to inform you that...", window_title="notepad")
- "write code for a calculator" -> write_file(path="calculator.py", content="def add(a,b): return a+b\n...")
- "can you write down my grocery list" -> type_text("Grocery List:\n- Apples\n- Milk\n- Bread\n- Eggs", window_title="notepad")
- "I have a meeting at 3pm, remind me" -> set_reminder(message="Meeting at 3pm", minutes=180)
- "put together a pros and cons list" -> type_text("Pros and Cons:\n\nPros:\n1. ...\n\nCons:\n1. ...", window_title="notepad")
- "jot down some notes about the project" -> type_text("Project Notes:\n\n- ...", window_title="notepad")
- "type up a quick summary" -> type_text("Summary:\n\n...", window_title="notepad")

CONTENT TYPE DETECTION:
- If user says "write in notepad", "type in notepad", "open notepad and write", or specifies an app to write IN: ALWAYS use type_text(window_title="app_name", text="content") — even for long content.
- Short content (<200 chars) without a target app: use type_text(window_title="app_name", text="content")
- Long content (>200 chars) without a target app: use write_file(path="filename.ext", content="the code") THEN open_app("filename.ext")
- Code/HTML/CSS/JS: use write_file — never type_code via type_text
- Emails/letters: use type_text with proper formatting (Dear..., Sincerely...)
- Lists: use type_text with numbered/bulleted format

WINDOW TARGETING: When using type_text, ALWAYS provide window_title matching the target app.

APP-SPECIFIC SEQUENCES:
- After opening Notepad and typing: the user may want to save. If they say "save it", use send_keys("ctrl+s").
- After opening a browser: if they say "search for X", use web_search("X") or browser actions.
- After opening any app: if they say "close it", use close_app with the app name.
- If user says "undo", use send_keys("ctrl+z") — works in most apps.
- If user says "select all", use send_keys("ctrl+a").
- If user says "copy that", use send_keys("ctrl+c").
- If user says "paste", use send_keys("ctrl+v").

TOOL GUIDELINES (CRITICAL):
- "open notepad and write X in it" -> open_app("notepad") + type_text("X", window_title="notepad") — ALWAYS type into notepad, never write to a file.
- "type X in notepad" -> type_text("X", window_title="notepad")
- "write X in notepad" -> type_text("X", window_title="notepad")
- Short text (<200 chars) without target app -> type_text(window_title="app_name", text="content")
- Long text (code, HTML, essays, >200 chars) without target app -> write_file(path="filename.ext", content="the code") THEN open_app("filename.ext") to view it.
- Code/HTML/CSS/JS: use write_file — never type_code via type_text
- For reminders: use set_reminder(message, minutes) — do NOT write to a file.
- For web searches: use web_search(query) — do NOT open a browser manually.

APP MAPPING:
- microsoft store/store -> open_app("store")
- file explorer/explorer -> open_app("explorer")
- this pc/my computer -> open_app("this pc")
- settings/control panel -> open_app("settings")
- task manager -> open_app("task manager")
- NEVER close system processes (explorer, svchost, csrss). "close pc" -> respond it cannot be closed.

SCREEN: "what am I looking at" / "describe screen" -> describe_screen().

QUICK COMMANDS (fast-path handles these, but know them):
- time/date/battery/screenshot/system info -> single tool call
- volume up/down/set -> volume tools
- brightness up/down -> set_brightness
- open/close app -> open_app/close_app
- lock/sleep/shutdown/restart -> system tools

Be proactive: notice things, suggest improvements.
If something fails, explain what went wrong and suggest a fix.
"""

# Static fallback (used when tuner_cache is unavailable or _build_dynamic_prompt fails)
JARVIS_SYSTEM_PROMPT = JARVIS_SYSTEM_PROMPT_BASE


def _build_dynamic_prompt() -> str:
    """P5: Build the system prompt with auto-tuner personality genes.

    Reads tilde_frequency and response_conciseness from tuner_cache
    to dynamically adjust May's speaking style.

    Returns:
        A dynamically customized system prompt, or JARVIS_SYSTEM_PROMPT_BASE
        as a safe fallback if tuner_cache is unavailable.
    """
    try:
        from intelligence.tuner_cache import get_gene
        tilde_freq = get_gene("tilde_frequency", default=0.3)
        conciseness = get_gene("response_conciseness", default=0.5)
    except Exception:
        return JARVIS_SYSTEM_PROMPT_BASE

    prompt = JARVIS_SYSTEM_PROMPT_BASE

    # Tilde frequency: 0=never use ~, 0.5=occasionally, 1=always use ~
    if tilde_freq >= 0.6:
        prompt += '\n- Always end sentences with "~" — it is your signature style.'
    elif tilde_freq >= 0.2:
        prompt += '\n- Use "~" occasionally at the end of sentences to sound cute.'
    else:
        prompt += '\n- Keep responses professional — do not use "~".'

    # Response conciseness: 0=verbose, 0.5=balanced, 1=one-word answers
    if conciseness >= 0.7:
        prompt += '\n- Be extremely brief — one sentence max. No fluff.'
    elif conciseness >= 0.3:
        prompt += '\n- Keep responses SHORT (1-3 sentences).'
    else:
        prompt += '\n- You may give longer, more detailed responses when helpful.'

    return prompt


# ── Destructive actions that need confirmation ──────────────────────────────
# P2 SECURITY: This set is kept for backward compatibility with existing
# code that references DESTRUCTIVE_TOOLS directly. The authoritative
# classification lives in system/risk_classifier.py which has the full
# SAFE/MODERATE/DESTRUCTIVE/CRITICAL tier mapping.

DESTRUCTIVE_TOOLS = {
    "shutdown_pc", "restart_pc", "kill_process", "delete_file",
    "batch_delete", "install_app", "run_powershell",
    "send_email", "format_disk", "delete_folder",
    "delete_skill",
}

# Biometrics tools — routed via HTTP to backend (not Control Core daemon)
_BIOMETRICS_TOOLS = {"biometrics_status", "biometrics_toggle", "biometrics_delete"}  # voice_enroll/voice_verify handled in execute_tool before HTTP routing

# Email tools — routed via HTTP to backend email integration
_EMAIL_TOOLS = {"get_unread_emails", "get_unread_count", "search_emails", "read_email", "get_recent_emails"}

# Wellness tools — routed via HTTP to backend proactive assistant
_WELLNESS_TOOLS = {"get_wellness_status", "get_wellness_suggestions", "set_wellness_rule"}

# Meeting tools — routed via HTTP to backend meeting mode
_MEETING_TOOLS = {"start_meeting", "stop_meeting", "meeting_status"}

# Ghost mode tools — routed via HTTP to backend ghost mode
_GHOST_TOOLS = {"queue_ghost_task", "ghost_status", "cancel_ghost_task", "cancel_all_ghost_tasks"}

# Skill tools — routed via HTTP to backend skill store
_SKILL_TOOLS = {"execute_skill", "list_skills", "search_skills", "delete_skill"}

# Human-readable tool names for clean UI output
_TOOL_DISPLAY_NAMES = {
    "open_app": "Opening app",
    "close_app": "Closing app",
    "type_text": "Typing text",
    "send_keys": "Sending keys",
    "web_search": "Searching web",
    "screenshot": "Taking screenshot",
    "describe_screen": "Analyzing screen",
    "get_time": "Checking time",
    "get_weather": "Getting weather",
    "volume_up": "Increasing volume",
    "volume_down": "Decreasing volume",
    "set_volume": "Setting volume",
    "set_mute": "Toggling mute",
    "set_brightness": "Setting brightness",
    "mouse_click": "Clicking",
    "drag_and_drop": "Dragging",
    "run_powershell": "Running command",
    "write_file": "Writing file",
    "read_file": "Reading file",
    "open_folder": "Opening folder",
    "focus_window": "Focusing window",
    "kill_process": "Stopping process",
    "restart_app": "Restarting app",
    "list_processes": "Listing processes",
    "get_clipboard": "Reading clipboard",
    "copy_to_clipboard": "Copying to clipboard",
}

# All HTTP-routed tools (not Control Core daemon)
_HTTP_TOOLS = _BIOMETRICS_TOOLS | _EMAIL_TOOLS | _WELLNESS_TOOLS | _MEETING_TOOLS | _GHOST_TOOLS | _SKILL_TOOLS


def _is_confirmation(message: str) -> bool:
    """Check if the user is confirming a destructive action."""
    lower = message.lower().strip()
    return lower in ("yes", "confirm", "yeah", "yep", "y", "ok", "okay", "do it", "go ahead", "sure")


# ── Pending tool calls (for confirmation flow) ──────────────────────────────
# When the LLM asks for confirmation (e.g. "want me to type hello?"),
# we save the pending tool calls here. When the user says "yes", we re-execute them.
#
# M3 FIX: Protected by asyncio.Lock() to prevent race conditions when
# multiple concurrent chat requests read/write this shared state.
_pending_tool_calls: list[dict] = []
_pending_lock = asyncio.Lock()


async def _save_pending_tool_calls(tool_calls: list[dict]):
    """Save tool calls that need user confirmation before execution."""
    global _pending_tool_calls
    async with _pending_lock:
        _pending_tool_calls = list(tool_calls)  # copy to avoid mutation by caller


async def _clear_pending_tool_calls():
    """Clear pending tool calls after they've been executed or discarded."""
    global _pending_tool_calls
    async with _pending_lock:
        _pending_tool_calls = []


# ── Tool executor ──────────────────────────────────────────────────────────

async def execute_tool(name: str, args: dict) -> str:
    """Execute a tool call from the LLM and return the result.

    Routes through the Control Core daemon via TCP when possible.
    Falls back to direct execution for unmapped tools.

    P2 SECURITY: Classifies risk tier, checks confirmation, logs to audit trail.
    """
    import time as _exec_time
    _exec_start = _exec_time.time()

    # Clean garbled text from LLM output before execution
    # NOTE: We ONLY strip leaked <think>...</think> tags here.
    # We do NOT collapse repeated characters — that regex destroyed legitimate content
    # like double letters in essays, code, poetry, etc. (the "pokemon ddddd" bug).
    # The LLM output is trusted as-is for content; only structural tags are stripped.
    if name == "type_text" and "text" in args:
        import re as _re_clean
        raw = args["text"]
        # Remove <think>...</think> tags if leaked into text (reasoning model artifact)
        cleaned = _re_clean.sub(r"<think>.*?</think>", "", raw, flags=_re_clean.DOTALL)
        # Also remove lines that are just XML-like tags (e.g. <answer>, </answer>)
        cleaned = _re_clean.sub(r"^\s*<[^>]+>\s*$", "", cleaned, flags=_re_clean.MULTILINE)
        cleaned = cleaned.strip()
        if cleaned:
            args["text"] = cleaned
        else:
            args["text"] = raw  # fallback to original if cleaning removed everything

    if name == "write_file" and "content" in args:
        import re as _re_clean2
        raw = args["content"]
        # Remove <think>...</think> tags only — do NOT touch the actual content
        cleaned = _re_clean2.sub(r"<think>.*?</think>", "", raw, flags=_re_clean2.DOTALL)
        cleaned = _re_clean2.sub(r"^\s*<[^>]+>\s*$", "", cleaned, flags=_re_clean2.MULTILINE)
        cleaned = cleaned.strip()
        if cleaned:
            args["content"] = cleaned

    # Read actual control mode from ControlModes once at the top
    current_control_mode = "normal"
    if _control_modes_ref is not None:
        try:
            current_control_mode = _control_modes_ref.get_status().get("active_mode", "normal")
        except Exception:
            pass

    try:
        # P2 SECURITY: Immune system verification (risk tiers + behavioral profile + control modes)
        if _immune_system_ref is not None:
            try:
                verification = await _immune_system_ref.verify_action(
                    name, args, control_mode=current_control_mode
                )
                if not verification.allowed:
                    action_desc = name.replace("_pc", "").replace("_", " ")
                    tier_label = {"critical": "🚨 CRITICAL", "destructive": "⚠️ DESTRUCTIVE", "moderate": "⚠️ MODERATE", "safe": "ℹ️ SAFE"}.get(verification.risk_tier, "⚠️ ACTION")
                    return f"{tier_label} — {verification.reason}. Please confirm by saying 'yes' or 'confirm'."
                risk_tier = verification.risk_tier
            except Exception:
                # Fallback to basic risk classification if immune system fails
                risk_tier = classify_action(name, args)
        else:
            # Fallback: basic risk classification without behavioral profile
            risk_tier = classify_action(name, args)
            if not args.get("confirm") and needs_confirmation(name, args, control_mode=current_control_mode):
                action_desc = name.replace("_pc", "").replace("_", " ")
                tier_label = {"critical": "🚨 CRITICAL", "destructive": "⚠️ DESTRUCTIVE", "moderate": "⚠️ MODERATE", "safe": "ℹ️ SAFE"}.get(risk_tier, "⚠️ ACTION")
                return f"{tier_label} — Need confirmation to {action_desc}. Please confirm by saying 'yes' or 'confirm'."

        # Check if this is a plugin tool
        pm = _plugin_manager_ref
        if pm is not None and pm.is_plugin_tool(name):
            result = await pm.execute_plugin_tool(name, args)
            # P2 SECURITY: Audit log plugin tool execution
            try:
                _audit_log(
                    action=name, params=args, result=result[:500],
                    risk_tier=risk_tier,
                )
            except Exception:
                pass
            return result

        # Handle tools that don't need HTTP (voice instructions)
        if name in _HTTP_TOOLS:
            # P1: Skip httpx for tools that just return instructions
            if name == "voice_enroll":
                speaker_name = args.get("name", "user")
                return f"To enroll a voice profile, please record audio through the voice input. Say '{speaker_name}' clearly for 2-3 seconds. You can also enroll from Settings -> Voice Biometrics."
            if name == "voice_verify":
                return "Voice verification happens automatically when voice biometrics is enabled. Speak and May will verify your identity."
            result = await _execute_http_tool(name, args)
            # P2 SECURITY: Audit log HTTP tool execution
            try:
                _audit_log(
                    action=name, params=args, result=result[:500],
                    risk_tier=risk_tier,
                )
            except Exception:
                pass
            return result

        # Route through the control core bridge
        result = await execute_tool_via_core(name, args)

        # Record the action for shadow learning (best-effort, non-blocking)
        try:
            _target = args.get("app_name") or args.get("path") or args.get("name") or args.get("query") or ""
            if not _target and args:
                _target = str(list(args.values())[:1])
            _record_shadow_event(name, _target, _exec_time.time())
        except Exception:
            pass  # Never block tool execution for shadow learning

        # P4: Record for conditioned reflex learning (non-blocking)
        if _conditioned_reflexes_ref is not None:
            try:
                _conditioned_reflexes_ref.record_example(
                    _target or name, name, args,
                )
            except Exception:
                pass  # Never block tool execution for reflex learning

        # P2 SECURITY: Audit log core tool execution
        try:
            _exec_latency = (_exec_time.time() - _exec_start) * 1000
            _audit_log(
                action=name, params=args, result=result[:500],
                risk_tier=risk_tier, latency_ms=_exec_latency,
            )
        except Exception:
            pass  # Never block tool execution for audit logging

        return result

    except Exception as e:
        logger.error("Tool '%s' failed: %s", name, e)
        # P2 SECURITY: Audit log failures too
        try:
            _audit_log(
                action=name, params=args, result=f"ERROR: {str(e)[:200]}",
                risk_tier=classify_action(name, args),
            )
        except Exception:
            pass
        return f"Error: {str(e)[:200]}"
    finally:
        # Guarantee no modifier keys (Ctrl, Alt, Shift, Win) remain stuck in Windows OS
        try:
            from core.layers.L5_input import _release_all_modifiers
            _release_all_modifiers()
        except Exception:
            pass


def _sanitize_http_args(name: str, args: dict) -> None:
    """SEC6: Sanitize and validate parameters for HTTP-routed tools.

    Strips dangerous characters, validates types, and enforces length limits
    to prevent injection attacks via crafted tool arguments.
    """
    import re as _re

    # Max lengths for string parameters
    _MAX_QUERY = 500
    _MAX_SUBJECT = 200
    _MAX_BODY = 50000
    _MAX_PATH = 1000
    _MAX_EMAIL = 254

    def _strip_control(s: str) -> str:
        """Remove control characters and null bytes from strings."""
        return _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', s)

    # Apply to all string values in args
    for key in list(args.keys()):
        val = args[key]
        if isinstance(val, str):
            args[key] = _strip_control(val)

    # Tool-specific validation
    if name in ("search_emails", "get_wellness_suggestions"):
        if "query" in args and isinstance(args["query"], str):
            args["query"] = args["query"][:_MAX_QUERY].strip()

    if name == "send_email":
        if "to" in args and isinstance(args["to"], str):
            # Basic email format check
            to = args["to"].strip()
            if not to or "@" not in to:
                raise ValueError(f"Invalid email address: {to[:50]}")
            args["to"] = to[:_MAX_EMAIL]
        if "subject" in args and isinstance(args["subject"], str):
            args["subject"] = args["subject"][:_MAX_SUBJECT].strip()
        if "body" in args and isinstance(args["body"], str):
            args["body"] = args["body"][:_MAX_BODY]

    if name == "read_email":
        if "uid" in args and isinstance(args["uid"], str):
            # UIDs should be alphanumeric
            args["uid"] = _re.sub(r'[^a-zA-Z0-9:@.\-]', '', args["uid"])[:100]

    if name == "cancel_ghost_task":
        if "task_id" in args and isinstance(args["task_id"], str):
            args["task_id"] = _re.sub(r'[^a-zA-Z0-9\-_]', '', args["task_id"])[:100]

    if name == "set_wellness_rule":
        if "rule" in args and isinstance(args["rule"], str):
            allowed_rules = {"water", "posture", "break", "eyes"}
            rule = args["rule"].strip().lower()
            if rule and rule not in allowed_rules:
                raise ValueError(f"Unknown wellness rule: {rule}. Allowed: {', '.join(allowed_rules)}")
            args["rule"] = rule

    if name == "queue_ghost_task":
        if "description" in args and isinstance(args["description"], str):
            args["description"] = args["description"][:1000].strip()
        if "priority" in args:
            try:
                args["priority"] = max(0, min(10, int(args["priority"])))
            except (TypeError, ValueError):
                args["priority"] = 0


async def _execute_http_tool(name: str, args: dict) -> str:
    """Execute a tool via HTTP to the backend API.

    Handles biometrics, email, wellness, meeting, and ghost mode tools
    that are served by the FastAPI backend rather than the Control Core daemon.
    """
    # SEC6: Input sanitization
    _sanitize_http_args(name, args)

    import httpx as _httpx
    import os as _os_mod
    base = _os_mod.environ.get("MAY_BACKEND_URL", "http://localhost:8080")
    try:
        async with _httpx.AsyncClient(timeout=15) as client:
            # ── Biometrics tools ────────────────────────────────────────
            if name == "biometrics_status":
                r = await client.get(f"{base}/voice/biometrics")
                return str(r.json())
            elif name == "biometrics_toggle":
                r = await client.post(f"{base}/voice/biometrics/toggle")
                return str(r.json())
            elif name == "biometrics_delete":
                r = await client.post(f"{base}/voice/biometrics/delete")
                return str(r.json())

            # ── Email tools ─────────────────────────────────────────────
            elif name == "get_unread_emails":
                max_items = args.get("max_items", 10)
                r = await client.get(f"{base}/email/unread", params={"max_items": max_items})
                data = r.json()
                if isinstance(data, dict) and "error" in data:
                    return f"Email error: {data['error']}"
                emails = data.get("emails", []) if isinstance(data, dict) else data if isinstance(data, list) else []
                if not emails:
                    return "No unread emails."
                lines = []
                for e in emails:
                    sender = e.get("from", "Unknown")
                    subject = e.get("subject", "(no subject)")
                    date = e.get("date", "")
                    lines.append(f"  [{date}] {sender}: {subject}")
                return f"{len(emails)} unread emails:\n" + "\n".join(lines)
            elif name == "get_unread_count":
                r = await client.get(f"{base}/email/unread/count")
                data = r.json()
                count = data.get("count", 0) if isinstance(data, dict) else 0
                return f"{count} unread emails"
            elif name == "search_emails":
                query = args.get("query", "")
                max_items = args.get("max_items", 10)
                r = await client.get(f"{base}/email/search", params={"query": query, "max_items": max_items})
                data = r.json()
                if isinstance(data, dict) and "error" in data:
                    return f"Email error: {data['error']}"
                emails = data.get("emails", []) if isinstance(data, dict) else data if isinstance(data, list) else []
                if not emails:
                    return f"No emails found matching '{query}'."
                lines = []
                for e in emails:
                    sender = e.get("from", "Unknown")
                    subject = e.get("subject", "(no subject)")
                    lines.append(f"  {sender}: {subject}")
                return f"{len(emails)} emails found:\n" + "\n".join(lines)
            elif name == "read_email":
                uid = args.get("uid", "")
                r = await client.get(f"{base}/email/{uid}")
                data = r.json()
                if isinstance(data, dict) and "error" in data:
                    return f"Email error: {data['error']}"
                subject = data.get("subject", "(no subject)")
                sender = data.get("from", "Unknown")
                body = data.get("body", "")
                return f"From: {sender}\nSubject: {subject}\n\n{body[:2000]}"
            elif name == "get_recent_emails":
                max_items = args.get("max_items", 5)
                r = await client.get(f"{base}/email/recent", params={"max_items": max_items})
                data = r.json()
                if isinstance(data, dict) and "error" in data:
                    return f"Email error: {data['error']}"
                emails = data.get("emails", []) if isinstance(data, dict) else data if isinstance(data, list) else []
                if not emails:
                    return "No recent emails."
                lines = []
                for e in emails:
                    sender = e.get("from", "Unknown")
                    subject = e.get("subject", "(no subject)")
                    read = "" if e.get("unread", True) else " [read]"
                    lines.append(f"  {sender}: {subject}{read}")
                return f"{len(emails)} recent emails:\n" + "\n".join(lines)

            # ── Wellness tools ──────────────────────────────────────────
            elif name == "get_wellness_status":
                r = await client.get(f"{base}/wellness")
                return str(r.json())
            elif name == "get_wellness_suggestions":
                r = await client.get(f"{base}/wellness/suggestions")
                data = r.json()
                if isinstance(data, dict):
                    suggestions = data.get("suggestions", [])
                    if not suggestions:
                        return "No wellness suggestions right now."
                    lines = []
                    for s in suggestions:
                        if isinstance(s, dict):
                            lines.append(f"  - {s.get('message', str(s))}")
                        else:
                            lines.append(f"  - {s}")
                    return "Wellness suggestions:\n" + "\n".join(lines)
                return str(data)
            elif name == "set_wellness_rule":
                rule = args.get("rule", "")
                enabled = args.get("enabled", True)
                r = await client.post(f"{base}/wellness/rule", json={"rule": rule, "enabled": enabled})
                return str(r.json())

            # ── Meeting tools ───────────────────────────────────────────
            elif name == "start_meeting":
                title = args.get("title", "")
                r = await client.post(f"{base}/meeting/start", json={"title": title})
                data = r.json()
                return data.get("message", str(data)) if isinstance(data, dict) else str(data)
            elif name == "stop_meeting":
                r = await client.post(f"{base}/meeting/stop")
                data = r.json()
                return data.get("message", str(data)) if isinstance(data, dict) else str(data)
            elif name == "meeting_status":
                r = await client.get(f"{base}/meeting/status")
                return str(r.json())

            # ── Ghost mode tools ────────────────────────────────────────
            elif name == "queue_ghost_task":
                desc = args.get("description", "")
                priority = args.get("priority", 0)
                r = await client.post(f"{base}/ghost/queue", json={"description": desc, "priority": priority})
                data = r.json()
                return data.get("message", str(data)) if isinstance(data, dict) else str(data)
            elif name == "ghost_status":
                r = await client.get(f"{base}/ghost/status")
                return str(r.json())
            elif name == "cancel_ghost_task":
                task_id = args.get("task_id", "")
                r = await client.post(f"{base}/ghost/cancel", json={"task_id": task_id})
                return str(r.json())
            elif name == "cancel_all_ghost_tasks":
                r = await client.post(f"{base}/ghost/cancel-all")
                return str(r.json())

            # ── Skill tools ──────────────────────────────────────────────
            elif name == "execute_skill":
                skill_id = args.get("skill_id", "")
                r = await client.post(f"{base}/skills/execute", json={"skill_id": skill_id})
                data = r.json()
                if "error" in data:
                    return f"Skill error: {data['error']}"
                results = data.get("results", [])
                skill_name = data.get("skill", "unknown")
                lines = [f"  {'✓' if r.get('ok') else '✗'} {r.get('tool', '?')}: {r.get('result', '')[:100]}" for r in results]
                return f"Executed skill '{skill_name}' ({len(results)} steps):\n" + "\n".join(lines)
            elif name == "list_skills":
                r = await client.get(f"{base}/skills")
                data = r.json()
                skills = data.get("skills", [])
                if not skills:
                    return "No learned skills yet. Skills are auto-created when May detects repeated action patterns."
                lines = []
                for s in skills:
                    steps_desc = " → ".join(step.get("tool_name", "?") for step in s.get("steps", []))
                    lines.append(f"  [{s.get('id', '?')[:8]}] {s.get('name', '?')} ({s.get('use_count', 0)} uses, {s.get('confidence', 0):.0%} conf)\n    Steps: {steps_desc}")
                return f"{len(skills)} learned skills:\n" + "\n".join(lines)
            elif name == "search_skills":
                query = args.get("query", "")
                r = await client.get(f"{base}/skills/search", params={"q": query})
                data = r.json()
                skills = data.get("skills", [])
                if not skills:
                    return f"No skills matching '{query}'."
                lines = []
                for s in skills:
                    steps_desc = " → ".join(step.get("tool_name", "?") for step in s.get("steps", []))
                    lines.append(f"  [{s.get('id', '?')[:8]}] {s.get('name', '?')} — {steps_desc}")
                return f"Skills matching '{query}':\n" + "\n".join(lines)
            elif name == "delete_skill":
                skill_id = args.get("skill_id", "")
                r = await client.delete(f"{base}/skills/{skill_id}")
                data = r.json()
                return f"Deleted skill {skill_id}." if data.get("status") == "ok" else f"Skill {skill_id} not found."

    except _httpx.ConnectError:
        return f"Error: Backend not running (cannot connect to {base}). Start the backend first."
    except Exception as e:
        return f"{name} error: {e}"
    return f"Unknown HTTP tool: {name}"


# ── Text-based tool call parser (for prompt-based fallback) ───────────────

_code_block_re = re.compile(r'```json\s*\n([\s\S]*?)\n\s*```')


def _parse_text_tool_calls(text: str) -> list[dict]:
    """Extract tool calls from LLM text response.

    Handles three formats:
    1. ```json blocks: ```json\n{"tool": "open_app", "args": {...}}\n```
    2. Bare JSON: {"tool": "open_app", "args": {...}}
    3. Python function calls: open_app("notepad"), type_text("hello", window_title="notepad")

    Uses brace-counting for correct nested JSON extraction.
    Returns list of {name, args, id} dicts.
    """
    parsed_objects = []
    seen = set()

    # 1. Extract from ```json code blocks
    for m in _code_block_re.finditer(text):
        try:
            obj = json.loads(m.group(1).strip())
            key = json.dumps(obj, sort_keys=True)
            if key not in seen:
                seen.add(key)
                parsed_objects.append(obj)
        except (json.JSONDecodeError, TypeError):
            pass

    # 2. Extract bare {"tool": ...} by scanning for opening braces
    for i, ch in enumerate(text):
        if ch != '{':
            continue
        # Check if this looks like a tool call
        snippet = text[i:i+30]
        if '"tool"' not in snippet:
            continue
        # Count braces to find the complete JSON object
        depth = 0
        for j in range(i, len(text)):
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[i:j+1]
                    try:
                        obj = json.loads(candidate)
                        key = json.dumps(obj, sort_keys=True)
                        if key not in seen:
                            seen.add(key)
                            parsed_objects.append(obj)
                    except (json.JSONDecodeError, TypeError):
                        pass
                    break

    # 3. Extract Python-style function calls: tool_name(arg1, arg2, key=val, ...)
    tool_names = {t["name"] for t in _get_all_tools()}
    _func_call_re = re.compile(
        r'(?<!\w)(' + '|'.join(re.escape(n) for n in tool_names) + r')\s*\(([^)]*)\)',
        re.IGNORECASE,
    )
    for m in _func_call_re.finditer(text):
        func_name = m.group(1).lower()
        args_str = m.group(2).strip()
        args = {}
        if args_str:
            # Parse positional and keyword args
            # Handle: open_app("notepad"), type_text("hello", window_title="notepad")
            import ast as _ast
            try:
                # Wrap in a dummy function call to make it valid Python
                parsed = _ast.literal_eval(f"f({args_str})")
                # parsed is a tuple of the positional args
                if isinstance(parsed, tuple):
                    # First positional arg is typically the main value
                    if parsed:
                        # Determine which arg name to use based on tool
                        if func_name in ("open_app", "open_folder", "close_app", "launch_app"):
                            args["app_name"] = str(parsed[0])
                        elif func_name == "type_text":
                            args["text"] = str(parsed[0])
                        elif func_name == "write_file":
                            args["content"] = str(parsed[0])
                        elif func_name == "send_keys":
                            args["keys"] = str(parsed[0])
                        elif func_name == "web_search":
                            args["query"] = str(parsed[0])
                        elif func_name == "set_reminder":
                            args["message"] = str(parsed[0])
                        elif func_name == "set_volume":
                            args["level"] = int(parsed[0]) if str(parsed[0]).isdigit() else parsed[0]
                        else:
                            args["value"] = str(parsed[0])
            except (ValueError, SyntaxError):
                pass
            # Parse keyword args: key=value
            for kw_match in re.finditer(r'(\w+)\s*=\s*["\']([^"\']*)["\']', args_str):
                args[kw_match.group(1)] = kw_match.group(2)
            for kw_match in re.finditer(r'(\w+)\s*=\s*(\d+)', args_str):
                args[kw_match.group(1)] = int(kw_match.group(2))
        key = json.dumps({"tool": func_name, "args": args}, sort_keys=True)
        if key not in seen:
            seen.add(key)
            parsed_objects.append({"tool": func_name, "args": args})

    # Convert to tool call format — validate against known tool names
    tool_calls = []
    for parsed in parsed_objects:
        # Handle JSON arrays like [{"tool": ...}, {"tool": ...}]
        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            if not isinstance(item, dict):
                continue
            tool_name = item.get("tool", "")
            tool_args = item.get("args", {})
            # Ensure args is always a dict
            if not isinstance(tool_args, dict):
                tool_args = {}
            if tool_name and tool_name in tool_names:
                tool_calls.append({
                    "name": tool_name,
                    "args": tool_args,
                    "id": f"text_call_{len(tool_calls)}",
                })
    return tool_calls


def _strip_tool_json(text: str) -> str:
    """Remove tool call JSON from text, leaving only conversational text."""
    # Remove ```json blocks that contain tool calls
    text = _code_block_re.sub("", text)
    # Remove bare {"tool": ...} blocks using brace counting
    result = []
    i = 0
    while i < len(text):
        if text[i] == '{' and '"tool"' in text[i:i+30]:
            depth = 0
            for j in range(i, len(text)):
                if text[j] == '{':
                    depth += 1
                elif text[j] == '}':
                    depth -= 1
                    if depth == 0:
                        i = j + 1
                        break
            else:
                break
        else:
            result.append(text[i])
            i += 1
    return "".join(result).strip()


def _clean_response_text(text: str) -> str:
    """Clean garbled/repetitive text and think tags from LLM output.

    Handles:
    - Repetitive characters (tttttttttttthe → the)
    - Garbled prefixes before tool calls
    - <think>...</think> blocks
    - Leftover tool call syntax (🔧 tool_name(...))
    """
    import re
    if not text:
        return ""
    # Remove <think>...</think> blocks (including multiline)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Remove standalone think tags
    text = re.sub(r"</?think>", "", text)
    # Collapse repetitive characters (3+ of same char → 1)
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    # Remove leftover tool call lines (🔧 tool_name(...))
    text = re.sub(r"🔧\s*`\w+\([^)]*\)`\s*", "", text)
    # Remove leftover JSON tool calls
    text = re.sub(r'\{[^{}]*"tool"\s*:\s*"[^"]+"[^{}]*\}', "", text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


# ── Smart content routing helper (extracted for testability) ──────────────

def _smart_route_type_text(tool_name: str, tool_args: dict) -> tuple[str, dict, dict | None]:
    """If type_text content is extremely long without a target window, convert to write_file.

    Never converts if a target window_title is specified (e.g. Notepad, Word), allowing
    direct clipboard typing into the application window.
    """
    if tool_name != "type_text":
        return tool_name, tool_args, None

    # Never convert if typing into a target app window (like Notepad or Word)
    if tool_args.get("window_title"):
        return tool_name, tool_args, None

    text_content = tool_args.get("text", "")
    if len(text_content) <= 3000:
        return tool_name, tool_args, None

    # Determine file extension from content hints
    ext = ".txt"
    text_lower = text_content.lower()
    if "<!doctype html" in text_lower or "<html" in text_lower:
        ext = ".html"
    elif text_lower.strip().startswith("{") and ('"' in text_content or "function" in text_lower):
        ext = ".js"
    elif text_lower.strip().startswith("import ") or text_lower.strip().startswith("from "):
        ext = ".py"
    elif text_lower.strip().startswith("# ") and "\n" in text_content:
        ext = ".md"
    elif "body {" in text_lower or "@import" in text_lower or "@media" in text_lower or ("{" in text_content and ("." in text_content[:200] or "#" in text_content[:200])):
        ext = ".css"

    file_path = os.path.join(os.path.expanduser("~"), "Desktop", f"may_output{ext}")
    logger.info("Smart routing: type_text (%d chars) → write_file(%s)", len(text_content), file_path)

    new_args = {"path": file_path, "content": text_content}
    extra_open = None
    return "write_file", new_args, extra_open


def _parse_app_and_tab_intent(app_name_raw: str) -> tuple[str, bool, str]:
    """Parse raw app name for tab/file intent.

    e.g. 'a new tab in notepad' -> ('notepad', True, 'ctrl+n')
    e.g. 'a new tab in chrome'  -> ('chrome',  True, 'ctrl+t')
    e.g. 'notepad'              -> ('notepad', False, '')
    """
    clean = app_name_raw.lower().strip()
    wants_new_tab = False
    shortcut = "ctrl+n"

    # Check for "tab in X", "new tab in X", "document in X", "file in X"
    tab_match = re.search(r'(?:a\s+)?(?:new\s+)?(?:tab|doc|document|file|window)\s+(?:in|into|of|on)\s+(.+)$', clean, re.IGNORECASE)
    if tab_match:
        clean = tab_match.group(1).strip()
        wants_new_tab = True
        if any(b in clean for b in ("chrome", "firefox", "edge", "brave", "browser", "opera")):
            shortcut = "ctrl+t"
        else:
            shortcut = "ctrl+n"

    return clean, wants_new_tab, shortcut


# ── Fast-path: skip LLM for obvious single-tool commands ─────────────────
# Each pattern match saves 1 full LLM API call (~1000-3000 tokens).
# Returns (tool_name, args) or None if the message needs the LLM.

def _try_fast_path(message: str) -> tuple[str, dict] | None:
    """Try to match a user message to a simple tool call, skipping the LLM.

    Returns (tool_name, args) if matched, None if the message needs the LLM.
    Only matches single-tool commands with high confidence.
    Expanded to 50+ patterns covering natural language variations.
    """
    m = message.lower().strip()
    
    # Strip common politeness markers
    _polite_prefixes = ('please ', 'can you ', 'could you ', 'would you ', 'hey may, ', 'hey may ', 'may, ')
    for prefix in _polite_prefixes:
        if m.startswith(prefix):
            m = m[len(prefix):].strip()
            break
    if not m:
        return None  # Empty after stripping politeness

    # ── COMPOUND: "open X and write/create Y" → open_app + type_text ──
    _compound_match = re.match(
        r'^(?:open|launch|start|run)\s+(.+?)\s*(?:and|then|,|;)\s*'
        r'(?:write|create|make|type|add|put|save)\s+(?:a\s+)?(?:new\s+)?(?:file\s+)?(?:in\s+it\s+)?'
        r'["\']?(.+?)["\']?\s*$', m
    )
    if _compound_match:
        app_name = _compound_match.group(1).strip()
        content_hint = _compound_match.group(2).strip().strip('"\' ')
        _TOPIC_SIGNALS = (
            r'\b(?:essay|poem|story|article|report|letter|email|code|script|function|'
            r'summary|list of|notes? (?:about|on)|paragraph|description|biography|'
            r'tutorial|guide|explanation|definition|example|sample|template|draft|'
            r'review|analysis|comparison|pros and cons|advantages|disadvantages)\b',
        )
        _ABOUT_SIGNALS = re.search(
            r'\b(?:about|on|for|regarding|concerning|related to|on the topic of)\b',
            content_hint, re.IGNORECASE
        )
        _TOPIC_MATCH = any(
            re.search(p, content_hint, re.IGNORECASE) for p in _TOPIC_SIGNALS
        )
        if _TOPIC_MATCH or _ABOUT_SIGNALS:
            return ("__compound_generate_and_type", {"app_name": app_name, "prompt": content_hint, "full_prompt": message})
        else:
            return ("__compound_open_and_type", {"app_name": app_name, "text": content_hint})

    # ── COMPOUND: "write/type/create X in/into Y" → generate/open + type ──
    _write_in_app_match = re.match(
        r'^(?:write|type|put|draft|compose|create|make)\s+(?:a\s+)?(?:new\s+)?(?:file\s+)?'
        r'["\']?(.+?)["\']?\s+(?:in|into|on)\s+["\']?(.+?)["\']?\s*$', m
    )
    if _write_in_app_match:
        content_hint = _write_in_app_match.group(1).strip().strip('"\' ')
        app_name = _write_in_app_match.group(2).strip().strip('"\' ')
        _TOPIC_SIGNALS = (
            r'\b(?:essay|poem|story|article|report|letter|email|code|script|function|'
            r'summary|list of|notes? (?:about|on)|paragraph|description|biography|'
            r'tutorial|guide|explanation|definition|example|sample|template|draft|'
            r'review|analysis|comparison|pros and cons|advantages|disadvantages)\b',
        )
        _ABOUT_SIGNALS = re.search(
            r'\b(?:about|on|for|regarding|concerning|related to|on the topic of)\b',
            content_hint, re.IGNORECASE
        )
        _TOPIC_MATCH = any(
            re.search(p, content_hint, re.IGNORECASE) for p in _TOPIC_SIGNALS
        )
        if _TOPIC_MATCH or _ABOUT_SIGNALS:
            return ("__compound_generate_and_type", {"app_name": app_name, "prompt": content_hint, "full_prompt": message})
        else:
            return ("__compound_open_and_type", {"app_name": app_name, "text": content_hint})

    # ── COMPOUND: "create/make X and open it in Y" → write_file + open_app ──
    _create_open_match = re.match(
        r'^(?:create|make|write|generate)\s+(?:a\s+)?(?:new\s+)?(?:file\s+)?'
        r'["\']?(\S+?)["\']?\s*(?:and|then|,|;)\s*'
        r'(?:open|launch|show)\s+(?:it\s+)?(?:in|with)\s+(.+?)\s*$', m
    )
    if _create_open_match:
        filename = _create_open_match.group(1).strip()
        app_name = _create_open_match.group(2).strip()
        # Create file on Desktop, then open in the app
        _file_path = os.path.join(os.path.expanduser("~"), "Desktop", filename)
        return ("__compound_create_and_open", {"path": _file_path, "app_name": app_name})

    # ── COMPOUND: "create X and write Y in it" → write_file + open_app ──
    _create_write_match = re.match(
        r'^(?:create|make|write|generate)\s+(?:a\s+)?(?:new\s+)?(?:file\s+)?'
        r'["\']?(\S+?)["\']?\s*(?:and|then|,|;)\s*'
        r'(?:write|type|put|add|save)\s+(?:an?\s+)?(?:essay\s+(?:on|about)\s+)?'
        r'["\']?(.+?)["\']?\s*(?:$|(?=\s+(?:and|then)\s+(?:open|launch|show)))', m
    )
    if _create_write_match:
        filename = _create_write_match.group(1).strip()
        content = _create_write_match.group(2).strip()
        _file_path = os.path.join(os.path.expanduser("~"), "Desktop", filename)
        # Check if there's a trailing "and open it in Y" part
        _trail = m[_create_write_match.end():]
        _open_trail = re.match(r'\s*(?:and|then)\s+(?:open|launch|show)\s+(?:it\s+)?(?:in|with)\s+(.+?)\s*$', _trail)
        _app = _open_trail.group(1).strip() if _open_trail else "notepad"
        return ("__compound_create_write_open", {"path": _file_path, "content": content, "app_name": _app})

    # ── App launching: "open X", "launch X", "start X" ──
    _app_match = re.match(
        r'^(?:open|launch|start|run)\s+(.+)$', m
    )
    # Common multi-word app aliases (saves LLM call for frequent commands)
    _APP_ALIASES = {
        # Browsers (only multi-word aliases)
        'google chrome': 'chrome', 'microsoft edge': 'edge', 'mozilla firefox': 'firefox',
        # Dev (only multi-word aliases)
        'visual studio code': 'vscode', 'vs code': 'vscode',
        'sublime text': 'sublime', 'intellij idea': 'intellij',
        'android studio': 'android studio', 'github desktop': 'github desktop',
        'docker desktop': 'docker',
        # Productivity (only multi-word aliases)
        'microsoft word': 'word', 'microsoft excel': 'excel',
        'microsoft powerpoint': 'powerpoint', 'microsoft outlook': 'outlook',
        'microsoft onenote': 'onenote', 'microsoft teams': 'teams',
        # Media (only multi-word aliases)
        'obs studio': 'obs', 'adobe photoshop': 'photoshop',
        'premiere pro': 'premiere pro', 'after effects': 'after effects',
        'adobe lightroom': 'lightroom', 'adobe illustrator': 'illustrator',
        # Gaming (only multi-word aliases)
        'epic games': 'epic', 'gog galaxy': 'gog', 'ea app': 'ea', 'origin': 'ea',
        'ubisoft connect': 'ubisoft', 'battle.net': 'battle.net', 'blizzard': 'battle.net',
        'league of legends': 'league of legends', 'geforce now': 'geforce now',
        # System (only multi-word aliases that need resolution)
        'file explorer': 'explorer', 'windows explorer': 'explorer', 'files': 'explorer',
        'my computer': 'this pc', 'my pc': 'this pc',
        'command prompt': 'cmd',
        'windows terminal': 'wt', 'control panel': 'settings',
        'microsoft store': 'store', 'windows store': 'store',
        # Cloud (only multi-word aliases)
        'google drive': 'google drive',
        # Dev tools (only multi-word aliases)
        'postman': 'postman', 'insomnia': 'insomnia',
    }
    if _app_match:
        app_name = _app_match.group(1).strip()
        # Guard: if app_name contains "and"/"then" followed by action words,
        # it's a compound command, not an app name — fall through to LLM.
        _ACTION_WORDS = ('write', 'create', 'make', 'type', 'add', 'put', 'save', 'open', 'close', 'search', 'delete', 'move', 'copy', 'paste', 'send', 'install', 'uninstall', 'rename', 'edit', 'run', 'execute', 'download', 'upload', 'print', 'share', 'export', 'import', 'compress', 'extract', 'merge', 'split', 'sort', 'filter', 'replace')
        if app_name and re.search(r'\b(?:and|then)\s+(?:' + '|'.join(_ACTION_WORDS) + r')\b', app_name.lower()):
            pass  # fall through to LLM
        elif app_name and len(app_name) < 60:
            # 1) Exact alias match
            resolved = _APP_ALIASES.get(app_name)
            if resolved:
                return ("open_app", {"app_name": resolved})
            # 2) Single-word name (no fuzzy needed — send to daemon)
            if ' ' not in app_name:
                return ("open_app", {"app_name": app_name})
            # 3) Multi-word input that's not an alias — try fuzzy match against known apps
            try:
                import sys as _sys
                _proj_root = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
                if _proj_root not in _sys.path:
                    _sys.path.insert(0, _proj_root)
                from core.layers.fuzzy_match import fuzzy_best
                from core.layers.L3_application import KNOWN_APPS
                fuzzy = fuzzy_best(app_name, KNOWN_APPS.keys(), threshold=0.60)
                if fuzzy and fuzzy.confidence >= 0.65:
                    logger.info("Fast-path fuzzy: '%s' → '%s' (%.2f, %s)",
                                app_name, fuzzy.candidate, fuzzy.confidence, fuzzy.method)
                    return ("open_app", {"app_name": fuzzy.candidate})
            except Exception:
                pass  # Never block fast-path for fuzzy failures
            # 4) Fallback: send multi-word name as-is to daemon
            return ("open_app", {"app_name": app_name})

    # ── App closing: "close X", "quit X", "kill X" ──
    _close_match = re.match(
        r'^(?:close|quit|kill|exit)\s+(.+)$', m
    )
    if _close_match:
        app_name = _close_match.group(1).strip()
        _blocked = ('pc', 'computer', 'this pc', 'explorer', 'svchost',
                    'csrss', 'wininit', 'smss', 'lsass', 'services')
        if app_name and len(app_name) < 60 and app_name not in _blocked:
            return ("close_app", {"app_name": app_name})

    # ── Volume: up, down, set, mute, unmute ──
    if m in ('volume up', 'vol up', 'louder', 'volume+', 'turn volume up', 'make it louder', 'crank the volume', 'raise the volume', 'boost volume', 'volume up please', 'can you turn the volume up'):
        return ("volume_up", {})
    if m in ('volume down', 'vol down', 'quieter', 'softer', 'volume-', 'turn volume down', 'make it quieter', 'lower the volume', 'turn it down', 'volume down please', 'can you turn the volume down'):
        return ("volume_down", {})
    if m in ('mute', 'mute volume', 'silence', 'muted', 'mute it', 'turn off sound', 'no sound', 'silent mode'):
        return ("mute", {})
    if m in ('unmute', 'unmute volume', 'unmuted', 'unmute it', 'turn on sound', 'sound on'):
        return ("unmute", {})
    _vol_match = re.match(
        r'^(?:set\s+)?volume\s+(?:to\s+)?(\d+)(?:%|\s+percent)?$', m
    )
    if _vol_match:
        level = int(_vol_match.group(1))
        if 0 <= level <= 100:
            return ("set_volume", {"level": level})
    # Natural volume: "volume to 50", "set volume 75", "put volume at 30"
    _vol_nat = re.match(r'^(?:turn|set|put|adjust)?\s*volume\s+(?:to\s+|at\s+)?(\d+)', m)
    if _vol_nat:
        level = int(_vol_nat.group(1))
        if 0 <= level <= 100:
            return ("set_volume", {"level": level})

    # ── Brightness: up, down, set ──
    if m in ('brightness up', 'brighter', 'increase brightness', 'turn brightness up', 'make it brighter', 'turn up brightness', 'screen brighter', 'brightness up please'):
        return ("set_brightness", {"delta": 10})
    if m in ('brightness down', 'dimmer', 'decrease brightness', 'dim', 'turn brightness down', 'make it dimmer', 'turn down brightness', 'screen dimmer', 'brightness down please'):
        return ("set_brightness", {"delta": -10})
    _bright_match = re.match(r'(?:set\s+)?brightness\s+(?:to\s+)?(\d+)', m)
    if _bright_match:
        level = int(_bright_match.group(1))
        if 0 <= level <= 100:
            return ("set_brightness", {"level": level})

    # ── Time ──
    if m in ('what time', 'time', 'what time is it', 'current time', 'tell me the time', 'got the time', 'what\'s the time', 'what does the clock say', 'time please', 'what time do you have', 'do you know the time'):
        return ("get_time", {})

    # ── Date ──
    if m in ('what day', 'date', 'what date is it', 'what day is it', 'today', "what's today", 'what\'s the date', 'what\'s the day', 'what day is today', 'date please', 'what\'s today\'s date'):
        return ("get_date", {})

    # ── Battery ──
    if m in ('battery', 'battery status', 'how much battery', 'battery level', 'power', 'power status', 'battery percentage', 'how\'s the battery', 'am i plugged in', 'battery life'):
        return ("battery_info", {})

    # ── Screenshot ──
    if m in ('screenshot', 'take screenshot', 'capture screen', 'screen capture', 'take a screenshot', 'screenshot please', 'capture the screen', 'take a pic', 'snap the screen', 'grab a screenshot'):
        return ("screenshot", {})

    # ── System info ──
    if m in ('system info', 'system status', 'pc info', 'computer info', 'specs', 'what are my specs', 'system specs', 'computer specs', 'pc specs', 'what\'s my system info', 'tell me about my pc'):
        return ("system_info", {})

    # ── Internet ──
    if m in ('internet status', 'test internet', 'internet', 'am i online', 'is the internet working', 'do i have internet', 'wifi working', 'is wifi up', 'internet connection', 'check internet', 'am i connected'):
        return ("test_internet", {})

    # ── Power commands (no confirm — flows through destructive-action gate) ──
    if m in ('shutdown', 'shut down', 'shut down pc', 'turn off pc', 'power off', 'shut down my computer', 'turn off my computer', 'shutdown please'):
        return ("shutdown_pc", {})
    if m in ('restart', 'reboot', 'restart pc', 'restart computer', 'reboot my computer', 'restart my pc', 'restart please'):
        return ("restart_pc", {})
    if m in ('lock', 'lock screen', 'lock pc', 'lock my computer', 'lock the screen', 'lock it'):
        return ("lock_screen", {})
    if m in ('sleep', 'sleep pc', 'hibernate', 'put pc to sleep', 'go to sleep', 'suspend'):
        return ("sleep_pc", {})

    # ── Clipboard (PowerShell clipboard, not keyboard shortcut) ──
    # Note: 'copy' and 'paste' are handled by send_keys below for keyboard shortcuts

    # ── Window management ──
    if m in ('minimize', 'minimize window', 'minimize this', 'minimize it', 'shrink window'):
        return ("minimize_window", {})
    if m in ('maximize', 'maximize window', 'maximize this', 'maximize it', 'full screen', 'fullscreen'):
        return ("maximize_window", {})

    # ── Quick keyboard shortcuts (strict — only short messages to avoid false positives) ──
    # These shortcuts only fire for very short messages (<=5 words) to avoid
    # matching "save the file to my documents" as Ctrl+S.
    _word_count = len(m.split())
    if _word_count <= 5:
        if m in ('undo', 'undo that', 'undo it', 'ctrl z'):
            return ("send_keys", {"keys": "ctrl+z"})
        if m in ('redo', 'redo that', 'redo it', 'ctrl y'):
            return ("send_keys", {"keys": "ctrl+y"})
        if m in ('select all', 'select everything', 'ctrl a'):
            return ("send_keys", {"keys": "ctrl+a"})
        if m in ('copy', 'copy that', 'copy this', 'copy selection', 'ctrl c'):
            return ("send_keys", {"keys": "ctrl+c"})
        if m in ('paste', 'paste that', 'paste this', 'ctrl v'):
            return ("send_keys", {"keys": "ctrl+v"})
        if m in ('cut', 'cut that', 'ctrl x'):
            return ("send_keys", {"keys": "ctrl+x"})
        if m in ('save', 'save it', 'save this', 'ctrl s', 'save file', 'save document'):
            return ("send_keys", {"keys": "ctrl+s"})
        if m in ('new file', 'new document', 'ctrl n'):
            return ("send_keys", {"keys": "ctrl+n"})
        if m in ('find', 'find text', 'ctrl f', 'search in page', 'find in page'):
            return ("send_keys", {"keys": "ctrl+f"})
        if m in ('print', 'print page', 'ctrl p', 'print this'):
            return ("send_keys", {"keys": "ctrl+p"})
        if m in ('refresh', 'reload', 'refresh page', 'f5'):
            return ("send_keys", {"keys": "f5"})
        if m in ('new tab', 'ctrl t', 'open new tab'):
            return ("send_keys", {"keys": "ctrl+t"})
        if m in ('close tab', 'ctrl w', 'close this tab'):
            return ("send_keys", {"keys": "ctrl+w"})
        if m in ('alt tab', 'switch window', 'switch apps', 'alt-tab'):
            return ("send_keys", {"keys": "alt+tab"})
        if m in ('alt f4', 'close window', 'close app', 'close this window'):
            return ("send_keys", {"keys": "alt+f4"})
        if m in ('show desktop', 'win d', 'minimize all'):
            return ("send_keys", {"keys": "win+d"})
        if m in ('file explorer', 'open explorer', 'open files'):
            return ("open_app", {"app_name": "explorer"})

    # No match — needs the LLM
    return None


# ── LLM-powered chat path ────────────────────────────────────────────────

# Compact system prompt for fast-path follow-ups (when we need LLM after all)
# This is the SAME as JARVIS_SYSTEM_PROMPT but used for the fast-path fallback
# (i.e., when fast-path doesn't match and we fall through to LLM).

async def jarvis_chat(
    message: str,
    history: list[dict],
    provider: str = "ollama",
    model: str = "qwen3:4b",
) -> AsyncGenerator[str, None]:
    """Process a user message through the Jarvis brain.

    Fast-path: If the message matches a simple command pattern, execute directly
    without calling the LLM. Saves 1 API call per matched message.

    LLM path: For complex/multi-step messages, send to LLM with tools.
    """
    global _last_opened_app, _last_created_file, _last_searched_query
    from llm.providers import stream_chat_with_tools

    # ── Pronoun resolution — resolve 'in it', 'close it', etc. ──
    resolved_message = _resolve_pronouns(message)

    # ── P5: SKILL MATCHING: Check learned skills before hitting the LLM ──
    if _skill_store_ref is not None and not _is_confirmation(resolved_message):
        try:
            matched_skills = _skill_store_ref.find_relevant(resolved_message, top_k=1)
            if matched_skills:
                skill = matched_skills[0]
                # Only use skill if confidence > 0.6 and it has steps
                if skill.confidence >= 0.6 and skill.steps:
                    logger.info(
                        "Skill match: '%s' → %s (confidence: %.3f, used %d times)",
                        resolved_message[:40], skill.name, skill.confidence, skill.use_count,
                    )
                    # Execute skill steps sequentially
                    all_results = []
                    for step in skill.steps:
                        step_result = await execute_tool(step.tool_name, step.params)
                        all_results.append(f"{step.tool_name}: {step_result[:200]}")
                        _update_pronoun_state(step.tool_name, step.params)
                    _skill_store_ref.record_use(skill.id)
                    skill_summary = "\n".join(f"  ✓ {r}" for r in all_results)
                    yield f"Done~ Ran skill '{skill.name}':\n{skill_summary}"
                    return
        except Exception:
            pass  # Never block chat for skill matching failures

    # ── FAST PATH: Try pattern matching first (saves 1 API call) ──
    # Skip fast-path if user is confirming a previous destructive action
    if not _is_confirmation(resolved_message):
        fast = _try_fast_path(resolved_message)
        if fast is not None:
            tool_name, tool_args = fast
            logger.info("Fast-path: %s(%s)", tool_name, tool_args)

            # Handle compound commands (open_app + type_text)
            if tool_name == "__compound_open_and_type":
                raw_app = tool_args["app_name"]
                text = tool_args["text"]
                real_app, wants_tab, shortcut = _parse_app_and_tab_intent(raw_app)
                # Step 1: Open the app
                open_result = await execute_tool("open_app", {"app_name": real_app})
                _update_pronoun_state("open_app", {"app_name": real_app})
                yield f"*Opening {real_app}...*\n"
                import asyncio as _aio_cmp
                await _aio_cmp.sleep(1.0)
                if wants_tab:
                    yield f"*Opening new tab in {real_app}...*\n"
                    await execute_tool("send_keys", {"keys": shortcut})
                    await _aio_cmp.sleep(0.5)
                yield f"*Typing into {real_app}...*\n"
                type_result = await execute_tool("type_text", {"text": text, "window_title": real_app})
                _update_pronoun_state("type_text", {"text": text, "window_title": real_app})
                return

            # Handle compound generate & type (open_app + generate_content + type_text)
            if tool_name == "__compound_generate_and_type":
                raw_app = tool_args["app_name"]
                full_prompt = tool_args.get("full_prompt", message)
                real_app, wants_tab, shortcut = _parse_app_and_tab_intent(raw_app)
                # Step 1: Open the target app
                yield f"*Opening {real_app}...*\n"
                await execute_tool("open_app", {"app_name": real_app})
                _update_pronoun_state("open_app", {"app_name": real_app})
                import asyncio as _aio_gen
                await _aio_gen.sleep(1.0)
                if wants_tab:
                    yield f"*Opening new tab in {real_app}...*\n"
                    await execute_tool("send_keys", {"keys": shortcut})
                    await _aio_gen.sleep(0.5)
                # Step 2: Generate content via LLM
                yield f"*Generating content for {real_app}...*\n"
                gen_prompt = f"Write the requested content for: '{full_prompt}'. Output ONLY the body of the document/essay/poem/code. Do NOT include intro conversational text like 'Here is the essay' or 'Sure'."
                generated_text = ""
                try:
                    from llm.providers import stream_chat_with_tools
                    async for event in stream_chat_with_tools(
                        provider=provider,
                        model=model,
                        messages=[{"role": "user", "content": gen_prompt}],
                        system_prompt="You are a document generator. Output ONLY the document text directly. No commentary.",
                        tools=None,
                        max_tokens=2048,
                    ):
                        if event["type"] == "text":
                            generated_text += event["content"]
                except Exception as e:
                    logger.error("Failed to generate content: %s", e)
                    generated_text = f"Content for: {full_prompt}"

                import re as _re_g
                generated_text = _re_g.sub(r"<think>.*?</think>", "", generated_text, flags=_re_g.DOTALL).strip()
                # Step 3: Wait and type into app
                yield f"*Typing into {real_app}...*\n"
                await execute_tool("type_text", {"text": generated_text, "window_title": real_app})
                _update_pronoun_state("type_text", {"text": generated_text, "window_title": real_app})
                yield f"Done~ Typed into {real_app}!\n"
                return

            # Handle "create X and open it in Y" → write_file + open_app
            if tool_name == "__compound_create_and_open":
                file_path = tool_args["path"]
                app_name = tool_args["app_name"]
                # Step 1: Create empty file
                await execute_tool("write_file", {"path": file_path, "content": ""})
                yield f"*Creating {os.path.basename(file_path)}...*\n"
                # Step 2: Open in app
                import asyncio as _aio_cmp2
                await _aio_cmp2.sleep(0.3)
                await execute_tool("open_app", {"app_name": app_name})
                _update_pronoun_state("open_app", {"app_name": app_name})
                yield f"*Opening in {app_name}...*\n"
                return

            # Handle "create X and write Y in it" → write_file + open_app
            if tool_name == "__compound_create_write_open":
                file_path = tool_args["path"]
                content = tool_args["content"]
                app_name = tool_args.get("app_name", "notepad")
                # Step 1: Write content to file
                await execute_tool("write_file", {"path": file_path, "content": content})
                yield f"*Creating {os.path.basename(file_path)}...*\n"
                # Step 2: Open in app
                import asyncio as _aio_cmp3
                await _aio_cmp3.sleep(0.3)
                await execute_tool("open_app", {"app_name": app_name})
                _update_pronoun_state("open_app", {"app_name": app_name})
                yield f"*Opening in {app_name}...*\n"
                return

            result = await execute_tool(tool_name, tool_args)
            # Update pronoun resolution state based on what was executed
            _update_pronoun_state(tool_name, tool_args)
            # P4: Record for conditioned reflex learning
            if _conditioned_reflexes_ref is not None:
                try:
                    _conditioned_reflexes_ref.record_example(message, tool_name, tool_args)
                except Exception:
                    pass
            # Yield a brief summary matching May's personality
            if tool_name == 'get_time':
                yield f"It's {result}~"
            elif tool_name == 'get_date':
                yield f"Today is {result}~"
            else:
                yield f"Done~ {tool_name.replace('_', ' ')}: {result[:200]}"
            return

    # ── P4: CONDITIONED REFLEXES: Check learned reflexes before hitting the LLM ──
    if _conditioned_reflexes_ref is not None and not _is_confirmation(resolved_message):
        try:
            reflex_match = _conditioned_reflexes_ref.check(resolved_message)
            if reflex_match.matched:
                logger.info(
                    "Conditioned reflex: '%s' → %s (confidence: %.3f)",
                    resolved_message[:40], reflex_match.tool_name, reflex_match.confidence,
                )
                result = await execute_tool(reflex_match.tool_name, reflex_match.tool_args)
                _update_pronoun_state(reflex_match.tool_name, reflex_match.tool_args)
                # Record for further reflex reinforcement
                try:
                    _conditioned_reflexes_ref.record_example(
                        message, reflex_match.tool_name, reflex_match.tool_args,
                    )
                except Exception:
                    pass
                yield f"Done~ {reflex_match.tool_name.replace('_', ' ')}: {result[:200]}"
                return
        except Exception:
            pass  # Never block chat for reflex failures

    # ── Memory injection — build rich context from 8 sources ──
    system_prompt = JARVIS_SYSTEM_PROMPT
    if _memory_injector_ref is not None:
        try:
            # P4: Build screen context from Tier 2 UIAccessibility if available
            screen_ctx = None
            if _screen_watcher_ref is not None:
                try:
                    last_data = _screen_watcher_ref.get_last_screen_data()
                    if last_data:
                        screen_ctx = last_data
                except Exception:
                    pass
            ctx = await _memory_injector_ref.build_context(
                user_message=message,
                active_app=_last_opened_app,
                screen_ctx=screen_ctx,
            )
            if ctx:
                system_prompt = ctx + system_prompt
        except Exception:
            pass  # Never block chat for context injection

    # ── LLM PATH: Send to LLM with tools ──
    # Build message history — keep last 4 messages (reduced from 8 to save tokens)
    messages = []
    for msg in history[-4:]:
        role = "user" if msg.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": msg.get("content", "")})
    messages.append({"role": "user", "content": resolved_message})

    # P5: Read max_tokens from auto-tuner (cached via tuner_cache)
    from intelligence.tuner_cache import get_gene
    max_tokens = int(get_gene("max_tokens", default=1024))

    # P5: Build dynamic system prompt with personality genes (tilde_frequency, response_conciseness)
    system_prompt = _build_dynamic_prompt()

    # P6: Append personality profile suffix if available
    if _personality_modes_ref is not None:
        try:
            profile_suffix = _personality_modes_ref.get_system_prompt_suffix()
            if profile_suffix:
                system_prompt = profile_suffix + "\n\n" + system_prompt
        except Exception:
            pass

    # Send to LLM with filtered tools
    # Buffer everything — don't yield until we know if there are tool calls
    full_response = ""
    tool_calls_list = []

    tools = _get_tools_for_message(message)
    use_native_tools = not _is_small_local_model(model)

    if use_native_tools:
        # Normal path: send tools in native format
        async for event in stream_chat_with_tools(
            provider=provider,
            model=model,
            messages=messages,
            system_prompt=system_prompt,
            tools=tools,
            max_tokens=max_tokens,
        ):
            if event["type"] == "text":
                full_response += event["content"]
            elif event["type"] == "tool_calls":
                tool_calls_list = event["tool_calls"]
    else:
        # Small model path: inject tools as text, parse response for tool calls
        from llm.providers import _tools_as_prompt_text
        text_system = _tools_as_prompt_text(tools, system_prompt)
        # Add STRONG instructions for small models to output tool calls as JSON
        # Small models like qwen3:0.6b tend to "think out loud" instead of calling tools
        text_system += (
            "\n\n## CRITICAL RULES FOR TOOL CALLING\n"
            "When the user asks you to DO something (open app, write text, search, etc.), "
            "you MUST respond ONLY with JSON tool call(s). Do NOT explain or plan — just output the JSON.\n\n"
            "Example: User says \"open notepad and write hello\"\n"
            "Your response must be ONLY:\n"
            "```json\n"
            "{\"tool\": \"open_app\", \"args\": {\"app_name\": \"notepad\"}}\n"
            "```\n"
            "```json\n"
            "{\"tool\": \"type_text\", \"args\": {\"text\": \"hello\", \"window_title\": \"notepad\"}}\n"
            "```\n\n"
            "Example: User says \"write an essay on pokemon in notepad\"\n"
            "Your response must be ONLY:\n"
            "```json\n"
            "{\"tool\": \"open_app\", \"args\": {\"app_name\": \"notepad\"}}\n"
            "```\n"
            "```json\n"
            "{\"tool\": \"type_text\", \"args\": {\"text\": \"Pokemon Essay\\n\\nPokemon is a franchise...\", \"window_title\": \"notepad\"}}\n"
            "```\n\n"
            "Example: User says \"search for cats\"\n"
            "Your response must be ONLY:\n"
            "```json\n"
            "{\"tool\": \"web_search\", \"args\": {\"query\": \"cats\"}}\n"
            "```\n\n"
            "NEVER explain what you would do. NEVER say 'I will' or 'We need to'. "
            "NEVER describe steps. Just output the tool call JSON blocks.\n"
            "When generating content (essays, poems, code), YOU write the full content and put it in the tool args."
        )
        async for event in stream_chat_with_tools(
            provider=provider,
            model=model,
            messages=messages,
            system_prompt=text_system,
            tools=None,  # No native tools — text-only
            max_tokens=max_tokens,
        ):
            if event["type"] == "text":
                full_response += event["content"]
            elif event["type"] == "tool_calls":
                tool_calls_list = event["tool_calls"]

    # Also parse text response for tool calls (prompt-based fallback)
    if not tool_calls_list and full_response:
        tool_calls_list = _parse_text_tool_calls(full_response)

    # ── Confirmation flow: if user says "yes" and LLM didn't call new tools,
    # re-execute the previously pending tool calls ──
    # M3 FIX: Acquire lock to atomically read+clear pending calls
    async with _pending_lock:
        pending_snapshot = list(_pending_tool_calls)  # snapshot under lock

    _from_confirmation = False
    if not tool_calls_list and _is_confirmation(message) and pending_snapshot:
        logger.info("User confirmed — re-executing %d pending tool calls", len(pending_snapshot))
        tool_calls_list = pending_snapshot
        await _clear_pending_tool_calls()
        # Mark all tools as confirmed
        for tc in tool_calls_list:
            tc.setdefault("args", {})["confirm"] = True
        _from_confirmation = True

    # DEDUP: Remove duplicate tool calls (same name + args) that may come from
    # confirmation flow + LLM response overlap
    if tool_calls_list:
        seen = set()
        deduped = []
        for tc in tool_calls_list:
            # Normalize args for deduplication: ignore 'confirm' flag
            args = {k: v for k, v in tc.get("args", {}).items() if k != "confirm"}
            key = (tc["name"], json.dumps(args, sort_keys=True))
            if key not in seen:
                seen.add(key)
                deduped.append(tc)
        tool_calls_list = deduped

    # ── NOTepad FIX: Convert write_file → type_text when user asked to write in notepad ──
    # The LLM often chooses write_file for long content even when the user explicitly
    # said "write in notepad". Intercept this and convert to type_text.
    if tool_calls_list:
        msg_lower = message.lower()
        wants_notepad = any(phrase in msg_lower for phrase in [
            "in notepad", "into notepad", "in the notepad", "type in notepad",
            "write in notepad", "write in it", "open notepad and write",
        ])
        logger.info("Notepad interceptor: message='%s', wants_notepad=%s, tools=%s",
                     message[:80], wants_notepad, [tc["name"] for tc in tool_calls_list])
        if wants_notepad:
            converted = []
            opened_notepad = False
            for tc in tool_calls_list:
                if tc["name"] == "open_app" and "notepad" in tc.get("args", {}).get("app_name", "").lower():
                    opened_notepad = True
                    converted.append(tc)
                elif tc["name"] == "write_file":
                    # Convert write_file to type_text targeting notepad
                    content = tc.get("args", {}).get("content", "")
                    if content:
                        logger.info("Converting write_file → type_text for notepad request (%d chars)", len(content))
                        converted.append({
                            "name": "type_text",
                            "args": {"text": content, "window_title": "notepad"},
                            "id": f"converted_{len(converted)}",
                        })
                else:
                    converted.append(tc)
            if converted != tool_calls_list:
                logger.info("Notepad interceptor: converted tools from %s to %s",
                            [tc["name"] for tc in tool_calls_list], [tc["name"] for tc in converted])
                tool_calls_list = converted

    # If tool calls found — execute them, get natural response
    if tool_calls_list:
        # BUG-1 FIX: Yield the LLM's conversational text before entering the loop.
        # Without this, May's initial response (e.g. "Opening notepad~") is silently
        # dropped when tool calls are present, making the UI feel unresponsive.
        initial_text = _clean_response_text(_strip_tool_json(full_response))
        if initial_text:
            yield initial_text
    else:
        # No tool calls — yield clean conversational text
        # Also clear any stale pending calls since user moved on to chat
        await _clear_pending_tool_calls()
        clean = _clean_response_text(_strip_tool_json(full_response))
        msg_lower = message.lower()
        wants_app_write = any(p in msg_lower for p in ["in notepad", "into notepad", "in the notepad", "write in notepad", "type in notepad"])
        target_app = "notepad" if wants_app_write else _last_opened_app

        # SAFETY NET: If user requested typing in an app (or Notepad is open) and LLM produced
        # text content without tool calls, automatically type the text into the target app!
        if target_app and clean and len(clean) > 30 and ("\n" in clean or len(clean.split()) > 15):
            # Strip conversational prefix if present (e.g. "Here's an essay on...")
            import re as _re_sn
            doc_body = _re_sn.sub(r'^(?:here(?:\'s| is)|i\'ve (?:written|created|opened)|sure|certainly)[^\n]*\n+', '', clean, flags=_re_sn.IGNORECASE).strip()
            if not doc_body:
                doc_body = clean
            logger.info("Safety Net: Auto-typing conversational response into '%s' (%d chars)", target_app, len(doc_body))
            yield f"\n\n*Typing content into {target_app}...*\n"
            await execute_tool("type_text", {"text": doc_body, "window_title": target_app})
            _update_pronoun_state("type_text", {"text": doc_body, "window_title": target_app})
        elif clean:
            yield clean

    # ═══ AGENTIC LOOP: keep executing tools until the LLM stops requesting ═══
    MAX_TOOL_ROUNDS = 5  # safety cap to prevent infinite loops
    # BUG-2 FIX: Increased from 12 to 20 — small models like qwen3:4b need to see
    # the original user request + all tool results to maintain chain intent.
    _MAX_CONTEXT_MESSAGES = 20
    if tool_calls_list:
        all_results = []
        # BUG-3 FIX: Build loop context with explicit loop tracking.
        # The LLM needs: (1) original request, (2) what it planned, (3) results so far.
        # This prevents small models from "forgetting" they're in a multi-step flow.
        loop_messages = list(messages)  # copy the original messages
        # Add the assistant's tool-calling response so LLM sees its own decisions
        tool_names_str = ", ".join(tc["name"] for tc in tool_calls_list)
        loop_messages.append({
            "role": "assistant",
            "content": f"(calling {tool_names_str})",
        })
        # BUG-2 FIX: Capture the index of the initial plan so we can reliably
        # find it later during context trimming (len(messages) could shift).
        _loop_plan_idx = len(loop_messages) - 1

        # Save pending tool calls for confirmation flow (skip if from confirmation — already cleared)
        if not _from_confirmation:
            await _save_pending_tool_calls(tool_calls_list)

        # Track already-opened apps to prevent duplicate open_app calls
        _opened_apps: set[str] = set()

        for round_num in range(MAX_TOOL_ROUNDS):
            # Execute all tool calls from this round
            # P5 PARALLEL: Group tools into independent batches for concurrent execution.
            # Tools that modify shared state (type_text, open_app with app name) run sequentially.
            # Read-only and independent tools (get_time, screenshot, list_processes) run in parallel.
            _SEQUENTIAL_TOOLS = {
                "type_text", "open_app", "close_app", "write_file", "send_keys",
                "mouse_click", "drag_and_drop", "run_powershell", "focus_window",
                "set_volume", "volume_up", "volume_down", "set_mute",
                "set_brightness", "kill_process", "restart_app",
                "open_folder",
            }

            def _classify_tool(tc: dict) -> str:
                """Classify a tool as 'sequential' or 'parallel' for batching."""
                name = tc["name"]
                if name in _SEQUENTIAL_TOOLS:
                    return "sequential"
                return "parallel"

            # Separate into sequential and parallel buckets
            parallel_batch = []
            sequential_queue = []
            for tool_call in tool_calls_list:
                if _classify_tool(tool_call) == "parallel":
                    parallel_batch.append(tool_call)
                else:
                    sequential_queue.append(tool_call)

            round_results = []

            # Run parallel tools concurrently
            async def _exec_one(tc: dict) -> str:
                tn = tc["name"]
                ta = tc.get("args", {})
                result = await execute_tool(tn, ta)
                return f"{tn}: {result}"

            if parallel_batch:
                # Dedup parallel batch too
                seen_parallel = set()
                deduped_parallel = []
                for tc in parallel_batch:
                    key = (tc["name"], json.dumps(tc.get("args", {}), sort_keys=True))
                    if key not in seen_parallel:
                        seen_parallel.add(key)
                        deduped_parallel.append(tc)
                parallel_batch = deduped_parallel

                tasks = [_exec_one(tc) for tc in parallel_batch]
                parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, res in enumerate(parallel_results):
                    tc = parallel_batch[i]
                    tn = tc["name"]
                    ta = tc.get("args", {})
                    if isinstance(res, Exception):
                        res_str = f"Error: {str(res)[:200]}"
                    else:
                        res_str = res
                    round_results.append(res_str)
                    all_results.append(res_str)
                    # Post-execution side effects
                    if tn in ("open_app", "open_folder", "close_app", "force_close_app"):
                        ak = ta.get("app_name", "").lower().strip()
                        if ak:
                            _opened_apps.add(ak)
                            _last_opened_app = ak
                    if tn == "type_text" and not ta.get("window_title") and _last_opened_app:
                        ta["window_title"] = _last_opened_app
                    _update_pronoun_state(tn, ta)
                    # Show clean tool execution feedback
                    _tool_label = _TOOL_DISPLAY_NAMES.get(tn, tn)
                    yield f"\n\n*{_tool_label}...*\n"

            # Run sequential tools one by one (preserves ordering for dependent actions)
            for tool_call in sequential_queue:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})

                # ── DEDUP: Skip duplicate open_app/close_app for the same app ──
                if tool_name in ("open_app", "open_folder", "close_app", "force_close_app"):
                    app_key = tool_args.get("app_name", "").lower().strip()
                    if app_key in _opened_apps:
                        round_results.append(f"{tool_name}: skipped (already handled for '{app_key}')")
                        continue
                    _opened_apps.add(app_key)
                    _last_opened_app = app_key

                # ── AUTO window_title: If type_text has no window_title, infer from last opened app ──
                if tool_name == "type_text" and not tool_args.get("window_title") and _last_opened_app:
                    tool_args["window_title"] = _last_opened_app

                # ── SMART ROUTING: If type_text content is long (>500 chars), auto-convert to write_file ──
                # This is a safety net for when the LLM ignores the system prompt guideline.
                tool_name, tool_args, _extra_open = _smart_route_type_text(tool_name, tool_args)

                # ── DELAY: Add delay before type_text if an app was just opened this round ──
                if tool_name == "type_text" and _last_opened_app and _last_opened_app in _opened_apps:
                    import asyncio as _aio_delay
                    await _aio_delay.sleep(0.5)  # Let the window fully load before typing

                # C4 FIX: Strip LLM-injected confirm flags for destructive tools.
                if tool_name in DESTRUCTIVE_TOOLS and not _is_confirmation(message):
                    tool_args.pop("confirm", None)

                if _is_confirmation(message):
                    tool_args["confirm"] = True

                # Execute the tool via the control core daemon
                result = await execute_tool(tool_name, tool_args)
                round_results.append(f"{tool_name}: {result}")
                all_results.append(f"{tool_name}: {result}")
                _update_pronoun_state(tool_name, tool_args)

                # Show clean tool execution feedback
                _tool_label = _TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
                yield f"\n\n*{_tool_label}...*\n"

                # ── SMART ROUTING: Execute the auto-generated open_app after write_file ──
                if _extra_open is not None:
                    _eo_name = _extra_open["name"]
                    _eo_args = _extra_open["args"]
                    _eo_result = await execute_tool(_eo_name, _eo_args)
                    round_results.append(f"{_eo_name}: {_eo_result}")
                    all_results.append(f"{_eo_name}: {_eo_result}")
                    _update_pronoun_state(_eo_name, _eo_args)
                    _eo_label = _TOOL_DISPLAY_NAMES.get(_eo_name, _eo_name)
                    yield f"\n\n*{_eo_label}...*\n"

            # NOTE: Don't clear _pending_tool_calls here — only clear when:
            # 1. User confirms (handled in confirmation flow above)
            # 2. User sends a non-confirmation message (handled in jarvis_chat entry)
            # This preserves the confirmation flow for destructive tools.

            # Feed results back to the LLM so it can decide what to do next
            # BUG-3 FIX: Clear, explicit instructions so small models (qwen3:4b)
            # know they must continue until ALL requested actions are done.
            tool_results_content = "\n".join(round_results)
            loop_messages.append({
                "role": "user",
                "content": (
                    f"Tool execution results for round {round_num + 1}:\n{tool_results_content}\n\n"
                    "REVIEW the original user request at the top of this conversation. "
                    "If MORE actions are still needed to fulfill the request, call the next "
                    "tool(s) NOW. If ALL requested actions are complete, respond with a brief "
                    "summary (no tools). Do NOT stop until the full request is fulfilled."
                ),
            })

            # BUG-2 FIX: Smarter context trimming — always preserve:
            # 1. Current user message (_loop_plan_idx - 1, right before the assistant plan)
            # 2. LLM's first tool-calling response (captured index _loop_plan_idx)
            # 3. Most recent messages (tool results + LLM responses)
            if len(loop_messages) > _MAX_CONTEXT_MESSAGES:
                first_user = loop_messages[_loop_plan_idx - 1:_loop_plan_idx]  # current user request
                first_assistant = loop_messages[_loop_plan_idx:_loop_plan_idx + 1]  # LLM's tool plan
                recent_count = _MAX_CONTEXT_MESSAGES - len(first_user) - len(first_assistant)
                recent = loop_messages[-recent_count:] if recent_count > 0 else []
                trimmed = first_user + first_assistant + recent
                loop_messages = trimmed

            # Call the LLM again WITH tools — it can chain more actions
            next_tool_calls = []
            next_response = ""
            llm_failed = False
            try:
                loop_tools = _get_tools_for_message(message)
                if use_native_tools:
                    async for event in stream_chat_with_tools(
                        provider=provider,
                        model=model,
                        messages=loop_messages,
                        system_prompt=system_prompt,
                        tools=loop_tools,
                        max_tokens=1024,
                    ):
                        if event["type"] == "text":
                            next_response += event["content"]
                        elif event["type"] == "tool_calls":
                            next_tool_calls = event["tool_calls"]
                else:
                    # Small model: inject tools as text
                    from llm.providers import _tools_as_prompt_text
                    loop_system = _tools_as_prompt_text(loop_tools, system_prompt)
                    loop_system += (
                        "\n\n## CRITICAL RULES FOR TOOL CALLING\n"
                        "When the user asks you to DO something (open app, write text, search, etc.), "
                        "you MUST respond ONLY with JSON tool call(s). Do NOT explain or plan — just output the JSON.\n\n"
                        "Example: User says \"open notepad and write hello\"\n"
                        "Your response must be ONLY:\n"
                        "```json\n"
                        "{\"tool\": \"open_app\", \"args\": {\"app_name\": \"notepad\"}}\n"
                        "```\n"
                        "```json\n"
                        "{\"tool\": \"type_text\", \"args\": {\"text\": \"hello\", \"window_title\": \"notepad\"}}\n"
                        "```\n\n"
                        "NEVER explain what you would do. NEVER say 'I will' or 'We need to'. "
                        "NEVER describe steps. Just output the tool call JSON blocks."
                    )
                    async for event in stream_chat_with_tools(
                        provider=provider,
                        model=model,
                        messages=loop_messages,
                        system_prompt=loop_system,
                        tools=None,
                        max_tokens=1024,
                    ):
                        if event["type"] == "text":
                            next_response += event["content"]
                        elif event["type"] == "tool_calls":
                            next_tool_calls = event["tool_calls"]

                # Also check for text-based tool calls (prompt fallback)
                if not next_tool_calls and next_response:
                    next_tool_calls = _parse_text_tool_calls(next_response)
            except Exception as e:
                logger.warning("Agentic loop round %d failed: %s", round_num + 1, e)
                llm_failed = True

            if llm_failed:
                # P4: Graceful degradation — show partial results instead of nothing
                if round_results:
                    yield "\n\n" + _format_partial_results(round_results)
                    yield "\n\n_(LLM connection lost, but actions were executed~)"
                else:
                    yield "\n\nHmm, I lost connection to the model~ Try again in a moment."
                break

            if not next_tool_calls:
                # LLM is done — yield its natural summary
                clean = _clean_response_text(_strip_tool_json(next_response))
                if clean:
                    yield f"\n\n{clean}"
                elif round_results:
                    # LLM gave empty response — yield a brief tool summary
                    summary_lines = []
                    for r in round_results:
                        tool_part, result_part = r.split(": ", 1) if ": " in r else (r, "done")
                        summary_lines.append(f"✓ {tool_part}")
                    yield "\n\n" + "\n".join(summary_lines)
                break

            # More tools to execute — yield any conversational text, then continue
            clean = _clean_response_text(_strip_tool_json(next_response))
            if clean:
                yield f"\n\n{clean}"

            # Add assistant message so LLM sees its own previous response
            # BUG-3 FIX: Include explicit loop progress indicator in the assistant message
            # so small models know how many rounds have completed and what's left.
            total_done = len(all_results)
            loop_messages.append({
                "role": "assistant",
                "content": next_response or f"(executing tools... round {round_num + 1}/{MAX_TOOL_ROUNDS}, {total_done} actions completed)"
            })

            # Continue the agentic loop with the newly requested tools.
            tool_calls_list = next_tool_calls
        else:
            # Safety cap hit — yield whatever results we have
            if all_results:
                joined = "\n".join(all_results)
                yield f"\n\n{joined}"
