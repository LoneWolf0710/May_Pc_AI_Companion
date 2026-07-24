"""Control Core TCP Client — sends commands to the daemon and returns results.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 2:
  Transport: TCP 127.0.0.1:7650 (local connections only)
  Protocol: JSON with newline framing
  Each connection = one command/response cycle

Usage:
    from core.client import send_command, is_daemon_running

    if await is_daemon_running():
        result = await send_command("filesystem", "read_file", {"path": "C:/test.txt"})
        if result.success:
            print(result.data)
"""

from __future__ import annotations

import asyncio
import json
import socket
import logging
from typing import Any

from .bus import Command, Result

logger = logging.getLogger("may.core.client")

CORE_HOST = "127.0.0.1"
CORE_PORT = 7650


async def send_command(
    layer: str,
    action: str,
    params: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> Result:
    """Send a command to the control core daemon via TCP.

    Args:
        layer:    Target layer (e.g. 'filesystem', 'system', 'input').
        action:   Action name (e.g. 'read_file', 'set_volume').
        params:   Action-specific parameters.
        timeout:  Max time to wait for a response.

    Returns:
        Result with success/failure, data, timing, and verification status.
    """
    cmd = Command(layer=layer, action=action, params=params or {}, timeout=timeout)

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(CORE_HOST, CORE_PORT),
            timeout=3.0,
        )

        try:
            # Send command JSON — newline-terminated for reliable framing
            payload = cmd.to_json().encode("utf-8") + b"\n"
            writer.write(payload)
            await writer.drain()

            # Read response — server sends one JSON line + \n
            data = await asyncio.wait_for(reader.readline(), timeout=timeout + 5.0)
        finally:
            writer.close()
            await writer.wait_closed()

        if not data:
            return Result.error_result(cmd.id, "Empty response from control core")

        result_data = json.loads(data.decode("utf-8").strip())

        # Reconstruct Result from dict, handling unknown fields gracefully
        known_fields = {f.name for f in Result.__dataclass_fields__.values()}
        filtered = {k: v for k, v in result_data.items() if k in known_fields}
        return Result(**filtered)

    except ConnectionRefusedError:
        logger.warning("Control core daemon not running on %s:%d", CORE_HOST, CORE_PORT)
        return Result.error_result(cmd.id, "Control core daemon not running")
    except asyncio.TimeoutError:
        logger.warning("Control core command timed out: %s.%s", layer, action)
        return Result.error_result(cmd.id, f"Timeout connecting to control core")
    except OSError as e:
        logger.warning("Control core connection error: %s", e)
        return Result.error_result(cmd.id, f"Connection error: {e}")
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error("Failed to parse control core response: %s", e)
        return Result.error_result(cmd.id, f"Invalid response from control core: {e}")
    except Exception as e:
        logger.error("Unexpected error in TCP client: %s", e)
        return Result.error_result(cmd.id, f"TCP client error: {e}")


async def is_daemon_running() -> bool:
    """Check if the control core daemon is listening on the TCP port.

    Uses a quick socket connect+close to test port availability.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(CORE_HOST, CORE_PORT),
            timeout=1.0,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (ConnectionRefusedError, asyncio.TimeoutError, OSError):
        return False


def is_daemon_running_sync() -> bool:
    """Synchronous check — useful for non-async contexts."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((CORE_HOST, CORE_PORT))
        s.close()
        return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False
