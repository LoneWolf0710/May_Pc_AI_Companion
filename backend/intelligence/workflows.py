"""Automated Workflows — chain tool calls triggered by conditions.

Users can create multi-step workflows via natural language or the API:
- "Every morning, check weather and send me a summary"
- "When I open VS Code, set volume to 30%"
- "Every hour, remind me to stretch"

Workflows are stored in ~/.may/workflows.json and executed by the
WorkflowEngine which hooks into the proactive_assistant and tool executor.
"""

import json
import re
import time
import logging
import asyncio
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

logger = logging.getLogger("may.intelligence.workflows")

_CONFIG_DIR = Path.home() / ".may"
_WORKFLOWS_FILE = _CONFIG_DIR / "workflows.json"


class TriggerType(str, Enum):
    """How a workflow is triggered."""
    MANUAL = "manual"          # User runs it on demand
    SCHEDULED = "scheduled"    # Runs on a cron-like schedule
    EVENT = "event"            # Runs on a system event (app open, idle, etc.)
    CHAT_PATTERN = "chat"      # Runs when user says something matching a pattern


class WorkflowStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class WorkflowStep:
    """A single step in a workflow — a tool call with parameters."""
    tool_name: str
    params: dict = field(default_factory=dict)
    description: str = ""
    condition: str = ""  # Optional: only run if this condition is truthy
    delay_after: float = 0.0  # Seconds to wait after this step


@dataclass
class Workflow:
    """An automated workflow — a named sequence of steps."""
    id: str
    name: str
    description: str = ""
    steps: list = field(default_factory=list)
    trigger: str = "manual"
    trigger_config: dict = field(default_factory=dict)
    enabled: bool = True
    last_run: float = 0.0
    run_count: int = 0
    last_error: str = ""
    created_at: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["trigger"] = self.trigger
        d["status"] = WorkflowStatus.IDLE.value
        return d


def _parse_percent(text: str) -> int:
    """Extract a percentage number from text like '50%' or '50'."""
    match = re.search(r'(\d+)', text)
    return min(100, max(0, int(match.group(1)))) if match else 50


class WorkflowEngine:
    """Manages and executes automated workflows."""

    def __init__(self):
        self._workflows: dict[str, Workflow] = {}
        self._executor = None
        self._chat_fn = None
        self._running: set = set()
        self._schedule_loop_task = None
        self._load()

    # ── Persistence ────────────────────────────────────────────────────

    def _load(self):
        """Load workflows from disk."""
        if not _WORKFLOWS_FILE.exists():
            return
        try:
            data = json.loads(_WORKFLOWS_FILE.read_text(encoding="utf-8"))
            for wd in data.get("workflows", []):
                steps_raw = wd.pop("steps", [])
                steps = []
                for s in steps_raw:
                    if isinstance(s, dict):
                        steps.append(WorkflowStep(
                            tool_name=s.get("tool_name", ""),
                            params=s.get("params", {}),
                            description=s.get("description", ""),
                            condition=s.get("condition", ""),
                            delay_after=s.get("delay_after", 0.0),
                        ))
                trigger = wd.get("trigger", "manual")
                wf = Workflow(
                    id=wd.get("id", ""),
                    name=wd.get("name", ""),
                    description=wd.get("description", ""),
                    steps=steps,
                    trigger=trigger,
                    trigger_config=wd.get("trigger_config", {}),
                    enabled=wd.get("enabled", True),
                    last_run=wd.get("last_run", 0.0),
                    run_count=wd.get("run_count", 0),
                    last_error=wd.get("last_error", ""),
                    created_at=wd.get("created_at", 0.0),
                )
                self._workflows[wf.id] = wf
            logger.info("Loaded %d workflows", len(self._workflows))
        except Exception as e:
            logger.error("Failed to load workflows: %s", e)

    def _save(self):
        """Persist workflows to disk."""
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "workflows": [
                {**asdict(wf), "trigger": wf.trigger}
                for wf in self._workflows.values()
            ]
        }
        _WORKFLOWS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ── Wiring ─────────────────────────────────────────────────────────

    def set_executor(self, executor):
        """Set the tool executor function (from jarvis.py execute_tool)."""
        self._executor = executor

    def set_chat_fn(self, chat_fn):
        """Set the jarvis_chat function for LLM-powered step generation."""
        self._chat_fn = chat_fn

    # ── Scheduled Workflow Executor (background loop) ───────────────────

    async def start_schedule_loop(self):
        """Start background loop that checks and runs scheduled workflows every 30s."""
        if self._schedule_loop_task is not None:
            return  # Already running
        self._schedule_loop_task = asyncio.create_task(self._schedule_loop())
        logger.info("Workflow schedule loop started")

    async def _schedule_loop(self):
        """Background loop: check for due scheduled workflows every 30s."""
        while True:
            try:
                await asyncio.sleep(30)
                due = self.get_scheduled_workflows()
                for wf in due:
                    logger.info("Running scheduled workflow: %s", wf.name)
                    result = await self.execute(wf.id)
                    if result.get("status") == "ok":
                        logger.info("Scheduled workflow '%s' completed (%d steps)", wf.name, result.get("steps_executed", 0))
                    else:
                        logger.warning("Scheduled workflow '%s' failed: %s", wf.name, result.get("error", "unknown"))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Schedule loop error: %s", e)

    def stop_schedule_loop(self):
        """Stop the background schedule loop."""
        if self._schedule_loop_task is not None:
            self._schedule_loop_task.cancel()
            self._schedule_loop_task = None

    # ── Natural Language Parsing ─────────────────────────────────────────

    # Keyword → tool mapping for common user actions
    _NL_PATTERNS: list[tuple[list[str], str, str, callable]] = [
        # (keywords, tool_name, description_template, param_extractor)
        # Apps
        (["open", "launch", "start"], "open_app", "Open {app}",
         lambda m: {"app_name": m.group(1).strip() if m.group(1) else ""}),
        (["close", "kill", "quit"], "close_app", "Close {app}",
         lambda m: {"app_name": m.group(1).strip() if m.group(1) else ""}),
        # Volume
        (["set volume", "volume to"], "set_volume", "Set volume to {level}",
         lambda m: {"level": _parse_percent(m.group(1) or "")}),
        (["volume up", "increase volume", "louder"], "set_volume", "Volume up",
         lambda m: {"level": 75}),
        (["volume down", "decrease volume", "quieter", "softer"], "set_volume", "Volume down",
         lambda m: {"level": 25}),
        (["mute"], "set_volume", "Mute audio",
         lambda m: {"level": 0}),
        # Brightness
        (["set brightness", "brightness to"], "set_brightness", "Set brightness to {level}",
         lambda m: {"level": _parse_percent(m.group(1) or "")}),
        (["brighter", "increase brightness"], "set_brightness", "Increase brightness",
         lambda m: {"level": 80}),
        (["dimmer", "decrease brightness"], "set_brightness", "Decrease brightness",
         lambda m: {"level": 30}),
        # Screenshot
        (["screenshot", "take a screenshot", "capture screen"], "screenshot_full", "Take screenshot",
         lambda m: {}),
        # Weather
        (["check weather", "weather in", "what's the weather"], "get_weather", "Get weather",
         lambda m: {"city": m.group(1).strip() if m.group(1) else ""}),
        # Time
        (["what time", "current time", "tell me the time"], "get_time", "Get current time",
         lambda m: {}),
        # Search / Web
        (["search for", "google", "look up", "web search"], "search_web", "Web search: {query}",
         lambda m: {"query": m.group(1).strip() if m.group(1) else ""}),
        (["open url", "go to", "navigate to"], "open_url", "Open URL: {url}",
         lambda m: {"url": m.group(1).strip() if m.group(1) else ""}),
        # System
        (["shutdown", "shut down"], "shutdown", "Shutdown PC",
         lambda m: {}),
        (["restart", "reboot"], "restart", "Restart PC",
         lambda m: {}),
        (["sleep", "put to sleep"], "sleep", "Sleep PC",
         lambda m: {}),
        (["lock screen", "lock pc"], "lock_screen", "Lock screen",
         lambda m: {}),
        # Clipboard
        (["copy to clipboard", "copy text"], "copy_clipboard", "Copy to clipboard",
         lambda m: {"text": m.group(1).strip() if m.group(1) else ""}),
        # Media
        (["play music", "play"], "media_play", "Play media",
         lambda m: {}),
        (["pause"], "media_pause", "Pause media",
         lambda m: {}),
        (["next track", "skip"], "media_next", "Next track",
         lambda m: {}),
        (["previous track", "previous"], "media_previous", "Previous track",
         lambda m: {}),
        # Process
        (["list processes", "show processes", "running processes"], "list_processes", "List processes",
         lambda m: {}),
        # ── NEW: Reminders (delay-based) ──
        (["remind me in", "set a reminder", "remind in"], "set_reminder", "Set reminder in {delay}",
         lambda m: {"message": "reminder", "delay": m.group(1).strip() if m.group(1) else ""}),
        # ── NEW: Network ──
        (["wifi on", "enable wifi", "turn on wifi"], "set_wifi", "Enable WiFi",
         lambda m: {"enabled": True}),
        (["wifi off", "disable wifi", "turn off wifi"], "set_wifi", "Disable WiFi",
         lambda m: {"enabled": False}),
        (["bluetooth on", "enable bluetooth"], "set_bluetooth", "Enable Bluetooth",
         lambda m: {"enabled": True}),
        (["bluetooth off", "disable bluetooth"], "set_bluetooth", "Disable Bluetooth",
         lambda m: {"enabled": False}),
        # ── NEW: System info ──
        (["system info", "system status", "pc info"], "system_info", "Get system info",
         lambda m: {}),
        (["battery", "battery status"], "battery_info", "Get battery info",
         lambda m: {}),
        # ── NEW: Power ──
        (["cancel shutdown", "abort shutdown"], "cancel_shutdown", "Cancel shutdown",
         lambda m: {}),
        # ── NEW: Window management ──
        (["list windows", "show windows", "all windows"], "list_windows", "List windows",
         lambda m: {}),
        (["minimize all", "show desktop"], "minimize_all", "Minimize all windows",
         lambda m: {}),
    ]

    # ── CRUD ───────────────────────────────────────────────────────────

    def parse_description(self, description: str) -> list[WorkflowStep]:
        """Convert a natural language description into workflow steps.

        Uses keyword pattern matching to map common phrases to tool calls.
        Falls back to LLM if available and pattern matching fails.
        Returns a list of WorkflowStep objects.
        """
        if not description or not description.strip():
            return []

        text = description.lower().strip()
        steps = []

        # Split on common separators: "and", ",", ";", "then", "after that"
        segments = re.split(r'\s*(?:;|\band\b|\bthen\b|\bafter that\b|\bnext\b),?\s*', text)
        segments = [s.strip() for s in segments if s.strip()]

        for segment in segments:
            step = self._match_segment_to_step(segment)
            if step:
                steps.append(step)

        return steps

    def _match_segment_to_step(self, segment: str) -> WorkflowStep | None:
        """Match a single text segment against known NL patterns."""
        for keywords, tool_name, desc_template, param_extractor in self._NL_PATTERNS:
            # Build a regex that matches any of the keywords at the start of the segment
            kw_patterns = '|'.join(re.escape(kw) for kw in keywords)
            # Capture everything after the keyword phrase as a parameter value (optional)
            pattern = rf'(?:{kw_patterns})(?:\s+(.*))?$'
            match = re.match(pattern, segment)
            if match:
                try:
                    params = param_extractor(match)
                except Exception:
                    params = {}
                return WorkflowStep(
                    tool_name=tool_name,
                    params=params,
                    description=desc_template.format(**{k: v for k, v in params.items() if isinstance(v, str)}),
                )

        return None



    def create(
        self,
        name: str,
        description: str = "",
        description_input: str = "",
        steps: list | None = None,
        trigger: str = "manual",
        trigger_config: dict | None = None,
    ) -> Workflow:
        """Create a new workflow. If description_input is provided, parse it into steps."""
        import uuid
        wf_id = f"wf_{uuid.uuid4().hex[:12]}"

        # If no explicit steps but description_input provided, parse it
        wf_steps = []
        if steps:
            for s in steps:
                if isinstance(s, dict):
                    wf_steps.append(WorkflowStep(
                        tool_name=s.get("tool_name", ""),
                        params=s.get("params", {}),
                        description=s.get("description", ""),
                        condition=s.get("condition", ""),
                        delay_after=s.get("delay_after", 0.0),
                    ))
                elif isinstance(s, WorkflowStep):
                    wf_steps.append(s)
        elif description_input:
            wf_steps = self.parse_description(description_input)

        wf = Workflow(
            id=wf_id,
            name=name,
            description=description or description_input,
            steps=wf_steps,
            trigger=trigger,
            trigger_config=trigger_config or {},
            created_at=time.time(),
        )
        self._workflows[wf_id] = wf
        self._save()
        return wf

    def preview_steps(self, description: str) -> list[dict]:
        """Preview what steps would be generated from a description.

        Returns a list of step dicts without creating a workflow.
        Used by the frontend to show a preview before creation.
        """
        steps = self.parse_description(description)
        if steps:
            return [
                {
                    "tool_name": s.tool_name,
                    "params": s.params,
                    "description": s.description,
                }
                for s in steps
            ]
        # If no patterns matched, return empty — chat_fn fallback
        # is handled async via /workflows/preview endpoint
        return []

    async def preview_steps_async(self, description: str) -> list[dict]:
        """Async preview: try regex patterns first, then LLM fallback.

        If no NL patterns match, uses the LLM chat function to parse
        the description into workflow steps. This is async-safe because
        it yields to the event loop.
        """
        steps = self.parse_description(description)
        if steps:
            return [
                {"tool_name": s.tool_name, "params": s.params, "description": s.description}
                for s in steps
            ]
        # LLM fallback — ask the LLM to convert NL to tool calls
        if self._chat_fn:
            try:
                tools_prompt = (
                    "Convert this user request into a JSON array of tool calls. "
                    "Each object must have 'tool_name' (string) and 'params' (object). "
                    "Available tools: open_app({app_name}), close_app({app_name}), "
                    "set_volume({level:0-100}), set_brightness({level:0-100}), "
                    "screenshot_full, get_weather, get_time, search_web({query}), "
                    "list_processes, system_info, lock_screen, shutdown, restart, sleep, "
                    "media_play, media_pause, media_next, media_previous, list_windows. "
                    f'User request: "{description}"\nRespond ONLY with the JSON array, nothing else.'
                )
                full_response = ""
                async for chunk in self._chat_fn(
                    message=tools_prompt, history=[], provider="ollama", model=None,
                ):
                    full_response += chunk
                # Extract JSON array from response
                json_match = re.search(r'\[.*\]', full_response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    llm_steps = []
                    for item in parsed:
                        if isinstance(item, dict) and "tool_name" in item:
                            llm_steps.append({
                                "tool_name": item["tool_name"],
                                "params": item.get("params", {}),
                                "description": f"LLM: {item['tool_name']}" + (
                                    f" ({item['params']})" if item.get('params') else ""),
                            })
                    if llm_steps:
                        return llm_steps
            except Exception as e:
                logger.debug("LLM NL parsing failed: %s", e)
        return []

    def get(self, workflow_id: str) -> Workflow | None:
        return self._workflows.get(workflow_id)

    def list_all(self) -> list[Workflow]:
        return list(self._workflows.values())

    def delete(self, workflow_id: str) -> bool:
        if workflow_id in self._workflows:
            del self._workflows[workflow_id]
            self._save()
            return True
        return False

    def toggle(self, workflow_id: str) -> bool:
        wf = self._workflows.get(workflow_id)
        if wf:
            wf.enabled = not wf.enabled
            self._save()
            return True
        return False

    # ── Execution ──────────────────────────────────────────────────────

    async def execute(self, workflow_id: str) -> dict:
        """Execute a workflow's steps sequentially."""
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {"error": "Workflow not found"}
        if not wf.enabled:
            return {"error": "Workflow is disabled"}
        if workflow_id in self._running:
            return {"error": "Workflow is already running"}
        if not self._executor:
            return {"error": "Tool executor not available"}

        self._running.add(workflow_id)
        results = []
        wf.last_run = time.time()

        try:
            for i, step in enumerate(wf.steps):
                result = await self._execute_step(step)
                results.append({
                    "step": i,
                    "tool": step.tool_name,
                    "description": step.description,
                    "status": "ok" if result.get("success") else "error",
                    "result": str(result.get("data", ""))[:500],
                })

                if step.delay_after > 0:
                    await asyncio.sleep(step.delay_after)

            wf.run_count += 1
            wf.last_error = ""
            self._save()
            return {
                "status": "ok",
                "workflow": wf.name,
                "steps_executed": len(results),
                "results": results,
            }
        except Exception as e:
            wf.last_error = str(e)[:200]
            self._save()
            return {
                "status": "error",
                "error": str(e)[:200],
                "results": results,
            }
        finally:
            self._running.discard(workflow_id)

    async def _execute_step(self, step: WorkflowStep) -> dict:
        """Execute a single workflow step via the tool executor."""
        if self._executor:
            try:
                result = await self._executor(step.tool_name, step.params)
                return {"success": True, "data": str(result)[:500]}
            except Exception as e:
                return {"success": False, "data": str(e)[:200]}
        return {"success": False, "data": "No executor available"}

    def get_scheduled_workflows(self) -> list:
        """Get workflows that should run based on schedule."""
        now = time.time()
        due = []
        for wf in self._workflows.values():
            if not wf.enabled or wf.trigger != TriggerType.SCHEDULED.value:
                continue
            interval = wf.trigger_config.get("interval_seconds", 3600)
            if now - wf.last_run >= interval:
                due.append(wf)
        return due

    def get_chat_triggered_workflows(self, message: str) -> list:
        """Get workflows whose chat pattern matches the user message."""
        msg_lower = message.lower()
        triggered = []
        for wf in self._workflows.values():
            if not wf.enabled or wf.trigger != TriggerType.CHAT_PATTERN.value:
                continue
            pattern = wf.trigger_config.get("pattern", "").lower()
            if pattern and pattern in msg_lower:
                triggered.append(wf)
        return triggered

    # ── Status ─────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        total = len(self._workflows)
        enabled = sum(1 for wf in self._workflows.values() if wf.enabled)
        running = len(self._running)
        total_runs = sum(wf.run_count for wf in self._workflows.values())
        return {
            "total_workflows": total,
            "enabled": enabled,
            "running": running,
            "total_runs": total_runs,
        }


# ── Singleton ──────────────────────────────────────────────────────────
_engine = None


def get_workflow_engine():
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
    return _engine
