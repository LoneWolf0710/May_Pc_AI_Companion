"""Command Bus — The backbone of the Control Core.

Every layer communicates only through the bus. The AI brain sends
commands as JSON over TCP, the bus dispatches to the correct layer,
and returns verified results.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 2:

Transport: TCP 127.0.0.1:7650 (local connections only)
Protocol: JSON with newline framing
"""

from __future__ import annotations

import asyncio
import json
import uuid
import time
import logging
import collections
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Awaitable

logger = logging.getLogger("may.core.bus")


# ── Core Structures ──────────────────────────────────────────────────────────

@dataclass
class Command:
    """A structured command from the AI brain to the Control Core.

    Attributes:
        layer:    Target layer: 'filesystem', 'process', 'application', etc.
        action:   Action name: 'delete_file', 'kill_process', 'set_volume', etc.
        params:   Action-specific parameters.
        id:       UUID for tracking.
        priority: 0=low, 1=normal, 2=urgent.
        timeout:  Max execution time in seconds.
    """
    layer:    str
    action:   str
    params:   dict[str, Any] = field(default_factory=dict)
    id:       str            = field(default_factory=lambda: str(uuid.uuid4()))
    priority: int            = 1
    timeout:  float          = 10.0

    def to_json(self) -> str:
        """Serialize to JSON for transport."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str | dict) -> Command:
        """Deserialize from JSON string or dict."""
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        """Convert to plain dict."""
        return asdict(self)


@dataclass
class Result:
    """The result of executing a command through the Control Core.

    Attributes:
        command_id:  Matches the Command id.
        success:     Did it work?
        data:        Return value of the action.
        error:       Error message if failed.
        verified:    True if post-action verification passed.
        method_used: Which fallback method succeeded.
        time_ms:     Execution time in milliseconds.
    """
    command_id:  str
    success:     bool
    data:        Any        = None
    error:       str | None = None
    verified:    bool       = False
    method_used: str        = "none"
    time_ms:     int        = 0
    suggested_action: str | None = None

    def to_json(self) -> str:
        """Serialize to JSON for transport."""
        d = asdict(self)
        # Handle non-serializable data values
        try:
            json.dumps(d["data"])
        except (TypeError, ValueError):
            d["data"] = str(d["data"]) if d["data"] is not None else None
        return json.dumps(d)

    def to_dict(self) -> dict:
        """Convert to plain dict."""
        d = asdict(self)
        try:
            json.dumps(d["data"])
        except (TypeError, ValueError):
            d["data"] = str(d["data"]) if d["data"] is not None else None
        return d

    @classmethod
    def error_result(cls, command_id: str, error: str) -> Result:
        """Create a failure result."""
        return cls(command_id=command_id, success=False, error=error)


# ── Command Bus ──────────────────────────────────────────────────────────────

# Type alias for layer handler functions
LayerHandler = Callable[[str, dict[str, Any]], Awaitable[Result]]


class CommandBus:
    """Central dispatcher that routes commands to the correct layer handler.

    Usage:
        bus = CommandBus()
        bus.register("filesystem", filesystem_handler)
        bus.register("process", process_handler)
        result = await bus.dispatch(command)
    """

    def __init__(self, history_size: int = 100):
        self.handlers: dict[str, LayerHandler] = {}
        self._history: collections.deque[dict] = collections.deque(maxlen=history_size)
        self._crash_context: dict = {}
        logger.info("CommandBus initialized (history_size=%d)", history_size)

    def register(self, layer_name: str, handler: LayerHandler):
        """Register a layer handler for a given layer name."""
        self.handlers[layer_name] = handler
        logger.info("Registered handler for layer: %s", layer_name)

    def unregister(self, layer_name: str):
        """Remove a layer handler."""
        self.handlers.pop(layer_name, None)
        logger.info("Unregistered handler for layer: %s", layer_name)

    def list_layers(self) -> list[str]:
        """Return list of registered layer names."""
        return list(self.handlers.keys())

    async def dispatch(self, cmd: Command) -> Result:
        """Route a command to its layer handler with timeout protection.

        Args:
            cmd: The command to execute.

        Returns:
            Result with success/failure, data, timing, and verification status.
        """
        t_start = time.monotonic()

        # Normalize layer name (resolve aliases like 'file' → 'filesystem')
        from .router import LAYER_ALIASES
        cmd.layer = LAYER_ALIASES.get(cmd.layer, cmd.layer)

        handler = self.handlers.get(cmd.layer)
        if not handler:
            elapsed = int((time.monotonic() - t_start) * 1000)
            error = f"Unknown layer: '{cmd.layer}'. Available: {self.list_layers()}"
            logger.error(error)
            return Result(
                command_id=cmd.id,
                success=False,
                error=error,
                time_ms=elapsed,
            )

        # Update crash context with the command being dispatched
        self._crash_context["last_command"] = {
            "layer": cmd.layer, "action": cmd.action,
            "params": str(cmd.params)[:200], "id": cmd.id,
            "timestamp": time.time(),
        }

        logger.info(
            "Dispatching: layer=%s action=%s id=%s timeout=%.1fs",
            cmd.layer, cmd.action, cmd.id, cmd.timeout,
        )

        try:
            result = await asyncio.wait_for(
                handler(cmd.action, cmd.params),
                timeout=cmd.timeout,
            )
            elapsed = int((time.monotonic() - t_start) * 1000)
            result.time_ms = elapsed

            status = "OK" if result.success else "FAIL"
            logger.info(
                "Result [%s]: layer=%s action=%s method=%s verified=%s time=%dms%s",
                status, cmd.layer, cmd.action, result.method_used,
                result.verified, elapsed,
                f" error={result.error}" if result.error else "",
            )

            # Record in history ring buffer
            self._history.append({
                "timestamp": time.time(),
                "layer": cmd.layer, "action": cmd.action,
                "params": str(cmd.params)[:200], "id": cmd.id,
                "success": result.success, "error": result.error,
                "method": result.method_used, "time_ms": elapsed,
                "verified": result.verified,
            })
            return result

        except asyncio.TimeoutError:
            elapsed = int((time.monotonic() - t_start) * 1000)
            error = f"Timeout after {cmd.timeout}s for {cmd.layer}.{cmd.action}"
            logger.error(error)
            self._history.append({
                "timestamp": time.time(),
                "layer": cmd.layer, "action": cmd.action,
                "params": str(cmd.params)[:200], "id": cmd.id,
                "success": False, "error": error,
                "method": "none", "time_ms": elapsed,
            })
            return Result(
                command_id=cmd.id,
                success=False,
                error=error,
                time_ms=elapsed,
            )

        except Exception as e:
            elapsed = int((time.monotonic() - t_start) * 1000)
            error = f"Exception in {cmd.layer}.{cmd.action}: {type(e).__name__}: {e}"
            logger.exception("Bus dispatch error for %s.%s", cmd.layer, cmd.action)
            self._history.append({
                "timestamp": time.time(),
                "layer": cmd.layer, "action": cmd.action,
                "params": str(cmd.params)[:200], "id": cmd.id,
                "success": False, "error": error,
                "method": "exception", "time_ms": elapsed,
            })
            return Result(
                command_id=cmd.id,
                success=False,
                error=error,
                time_ms=elapsed,
            )

    def get_history(self, limit: int = 20) -> list[dict]:
        """Get the last N commands from the history ring buffer."""
        items = list(self._history)
        return items[-limit:]

    def get_crash_context(self) -> dict:
        """Get crash context — last command, stats, and recent failures.

        Called by daemon.py on crash to log diagnostic info.
        """
        failures = [h for h in self._history if not h.get("success")]
        return {
            "last_command": self._crash_context.get("last_command"),
            "total_history": len(self._history),
            "recent_failures": failures[-5:],
            "registered_layers": self.list_layers(),
        }

    async def dispatch_json(self, json_str: str) -> Result:
        """Parse a JSON command string and dispatch it.

        Convenience method for the TCP listener in daemon.py.
        """
        try:
            cmd = Command.from_json(json_str)
            return await self.dispatch(cmd)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            return Result.error_result("parse_error", f"Invalid command JSON: {e}")


# ── TCP Server ───────────────────────────────────────────────────────────────

class BusServer:
    """TCP server that listens for commands and dispatches them via the bus.

    Per the architecture doc:
      - Listens on 127.0.0.1:7650 (local connections only)
      - JSON over TCP with newline framing
      - Each connection = one command/response cycle
    """

    def __init__(self, bus: CommandBus, host: str = "127.0.0.1", port: int = 7650):
        self.bus = bus
        self.host = host
        self.port = port
        self._server: asyncio.AbstractServer | None = None
        self._serve_task: asyncio.Task | None = None
        self._active_connections: int = 0
        self._total_commands: int = 0
        self._total_failures: int = 0
        self._start_time: float = time.time()

    async def start(self):
        """Start the TCP server."""
        try:
            self._server = await asyncio.start_server(
                self._handle_connection,
                self.host,
                self.port,
            )
            logger.info("BusServer listening on %s:%d", self.host, self.port)
            # Run serve_forever in background with exception handler
            self._serve_task = asyncio.create_task(self._serve_with_guard())
        except OSError as e:
            if "in use" in str(e).lower() or "already" in str(e).lower():
                logger.error(
                    "Port %d is already in use. Is another Control Core instance running?",
                    self.port,
                )
            else:
                logger.error("Failed to start BusServer on port %d: %s", self.port, e)
            raise

    async def _serve_with_guard(self):
        """Wrapper around serve_forever that catches and logs fatal errors.

        If the server dies, logs crash context (last commands, recent failures)
        then re-raises so the daemon process exits and the health check
        in main.py can restart it.
        """
        try:
            await self._server.serve_forever()
        except asyncio.CancelledError:
            logger.info("BusServer serve_forever cancelled (normal shutdown)")
        except Exception as e:
            # Log crash context for post-mortem diagnosis
            ctx = self.bus.get_crash_context()
            last = ctx.get("last_command")
            logger.critical(
                "BusServer CRASHED: %s\n"
                "  Last command: %s.%s (id=%s)\n"
                "  Recent failures: %d\n"
                "  Registered layers: %s",
                e,
                last["layer"] if last else "none",
                last["action"] if last else "none",
                last["id"] if last else "none",
                len(ctx.get("recent_failures", [])),
                ctx.get("registered_layers", []),
                exc_info=True,
            )
            raise  # Re-raise so daemon process exits → health check restarts it

    async def stop(self):
        """Stop the TCP server."""
        if self._serve_task and not self._serve_task.done():
            self._serve_task.cancel()
            try:
                await self._serve_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._server:
            self._server.close()
            try:
                await self._server.wait_closed()
            except Exception:
                pass
            logger.info(
                "BusServer stopped — processed %d commands, %d active connections",
                self._total_commands, self._active_connections,
            )

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a single TCP connection — one command per connection.

        Protocol: Client sends one line of JSON terminated by \n.
        Server reads until \n (or EOF) to avoid partial-read issues,
        dispatches the command, and writes the result as one JSON line + \n.
        """
        self._active_connections += 1
        addr = writer.get_extra_info("peername")
        try:
            # Read until newline — avoids partial JSON from TCP segment splits
            data = await reader.readline()
            if not data:
                return

            json_str = data.decode("utf-8").strip()
            if not json_str:
                return
            logger.debug("Received from %s: %s", addr, json_str[:200])

            result = await self.bus.dispatch_json(json_str)
            self._total_commands += 1
            if not result.success:
                self._total_failures += 1

            response = result.to_json()
            writer.write((response + "\n").encode("utf-8"))
            await writer.drain()

        except Exception as e:
            logger.exception("Error handling connection from %s", addr)
            error_result = Result.error_result("connection_error", str(e))
            try:
                writer.write((error_result.to_json() + "\n").encode("utf-8"))
                await writer.drain()
            except Exception:
                pass
        finally:
            self._active_connections = max(0, self._active_connections - 1)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
