"""
Remote Control — LAN web UI for phone control.

Serves a mobile-friendly chat/control interface via HTTP + WebSocket.
QR code generation for easy phone connection.
PIN-based authentication for LAN security.
"""

import asyncio
import json
import logging
import os
import secrets
import socket
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("may.remote")

PIN_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".may", "remote_pin.json")


class RemoteControl:
    """LAN-accessible remote control with WebSocket communication."""

    def __init__(self):
        self._connections: list = []
        self._message_callback: Optional[Callable] = None
        self._chat_history: list[dict] = []
        self._local_ip: str | None = None
        self._pin: str | None = None
        self._load_pin()

    def _load_pin(self):
        """Load or generate a PIN for remote control authentication."""
        try:
            if os.path.exists(PIN_CONFIG_PATH):
                with open(PIN_CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    self._pin = data.get("pin")
                    if self._pin and data.get("disabled"):
                        self._pin = None  # Auth disabled by user
                        return
                    if self._pin:
                        logger.info("Remote control PIN loaded")
                        return
        except (json.JSONDecodeError, OSError):
            pass
        # Generate a new random 6-digit PIN
        self._pin = secrets.token_hex(3).upper()  # 6 hex chars like "A3F2B1"
        self._save_pin()
        logger.info("Generated remote control PIN: %s", self._pin)

    def _save_pin(self):
        """Persist the PIN to disk."""
        os.makedirs(os.path.dirname(PIN_CONFIG_PATH), exist_ok=True)
        with open(PIN_CONFIG_PATH, "w") as f:
            json.dump({"pin": self._pin}, f, indent=2)
        # Restrict file permissions on Windows
        try:
            import stat
            os.chmod(PIN_CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)
        except (OSError, AttributeError):
            pass

    def verify_pin(self, pin: str | None) -> bool:
        """Verify a PIN. Returns True if auth is disabled or PIN matches."""
        if self._pin is None:
            return True  # Auth disabled
        if not pin:
            return False
        return secrets.compare_digest(pin.upper(), self._pin)

    def regenerate_pin(self) -> str:
        """Generate a new PIN and return it."""
        self._pin = secrets.token_hex(3).upper()
        self._save_pin()
        logger.info("Remote control PIN regenerated")
        return self._pin

    def disable_pin(self):
        """Disable PIN authentication."""
        os.makedirs(os.path.dirname(PIN_CONFIG_PATH), exist_ok=True)
        with open(PIN_CONFIG_PATH, "w") as f:
            json.dump({"pin": self._pin, "disabled": True}, f, indent=2)
        logger.info("Remote control PIN auth disabled")

    def enable_pin(self):
        """Re-enable PIN authentication."""
        self._load_pin()
        if self._pin is None:
            self._pin = secrets.token_hex(3).upper()
        self._save_pin()
        logger.info("Remote control PIN auth enabled")

    def get_pin(self) -> str | None:
        """Return the current PIN (for display in remote info)."""
        return self._pin

    def set_message_callback(self, callback: Callable):
        """Set the callback for when remote sends a message.

        The callback receives (message: str) and should return a response string or None.
        """
        self._message_callback = callback

    def get_local_ip(self) -> str:
        """Get the machine's local IP address."""
        if self._local_ip:
            return self._local_ip
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            self._local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            self._local_ip = "127.0.0.1"
        return self._local_ip

    def get_connection_info(self, port: int = 8080) -> dict:
        """Get connection info for the remote UI."""
        ip = self.get_local_ip()
        return {
            "url": f"http://{ip}:{port}/remote",
            "ip": ip,
            "port": port,
            "websocket_url": f"ws://{ip}:{port}/ws/remote",
            "connected_clients": len(self._connections),
        }

    def generate_qr(self, url: str) -> bytes | None:
        """Generate a QR code PNG image for the given URL."""
        try:
            import qrcode
            import qrcode.image.svg
            qr = qrcode.QRCode(version=1, box_size=8, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            # Generate PNG in memory
            from io import BytesIO
            buf = BytesIO()
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(buf, format="PNG")
            return buf.getvalue()
        except ImportError:
            logger.warning("qrcode not installed — run: pip install qrcode[pil]")
            return None
        except Exception as e:
            logger.error("QR generation failed: %s", e)
            return None

    def generate_qr_svg(self, url: str) -> str:
        """Generate a QR code as SVG string for embedding in HTML."""
        try:
            import qrcode
            import qrcode.image.svg
            qr = qrcode.QRCode(version=1, box_size=4, border=1)
            qr.add_data(url)
            qr.make(fit=True)
            factory = qrcode.image.svg.SvgPathImage
            img = qr.make_image(image_factory=factory)
            from io import StringIO
            buf = StringIO()
            img.save(buf)
            return buf.getvalue()
        except ImportError:
            return ""
        except Exception as e:
            logger.warning("QR SVG generation failed: %s", e)
            return ""

    def get_chat_history(self, limit: int = 50) -> list[dict]:
        """Get recent chat history from remote sessions."""
        return self._chat_history[-limit:]

    def record_message(self, role: str, content: str):
        """Record a message in the remote chat history."""
        self._chat_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        # Keep last 200 messages
        if len(self._chat_history) > 200:
            self._chat_history = self._chat_history[-200:]

    def get_status(self) -> dict:
        """Get remote control status."""
        return {
            "enabled": True,
            "connected_clients": len(self._connections),
            "local_ip": self.get_local_ip(),
            "message_count": len(self._chat_history),
        }

    async def broadcast(self, message: str):
        """Send a message to all connected WebSocket clients."""
        disconnected = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            if ws in self._connections:
                self._connections.remove(ws)

    def add_connection(self, ws):
        """Register a new WebSocket connection."""
        self._connections.append(ws)
        logger.info("Remote client connected (%d total)", len(self._connections))

    def remove_connection(self, ws):
        """Remove a WebSocket connection."""
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info("Remote client disconnected (%d total)", len(self._connections))


# Lazy singleton
_remote_control: Optional[RemoteControl] = None


def get_remote_control() -> RemoteControl:
    global _remote_control
    if _remote_control is None:
        _remote_control = RemoteControl()
    return _remote_control
