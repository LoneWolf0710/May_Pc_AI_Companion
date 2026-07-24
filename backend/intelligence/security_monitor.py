"""Security Monitor — USB, microphone, and app monitoring with proactive alerts.

Runs background watchers that detect:
1. USB device connect/disconnect events
2. Microphone access by unknown apps
3. Suspicious app launches (unknown or high-risk processes)

Alerts are surfaced via the screen watcher's proactive suggestion system.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("may.intelligence.security_monitor")

_CONFIG_FILE = Path.home() / ".may" / "security_monitor.json"


@dataclass
class SecurityAlert:
    """A single security monitoring alert."""
    timestamp: float
    category: str  # "usb", "microphone", "app_launch"
    severity: str  # "info", "warning", "critical"
    title: str
    description: str
    details: dict = field(default_factory=dict)
    acknowledged: bool = False


class SecurityMonitor:
    """Background security monitoring for USB, microphone, and app activity.

    Integrates with the proactive suggestion system to surface alerts.
    """

    def __init__(self):
        self._active = False
        self._alerts: list[SecurityAlert] = []
        self._max_alerts = 100
        self._poll_interval = 10.0  # seconds between checks
        self._task: asyncio.Task | None = None
        # Known state
        self._known_usb_devices: set[str] = set()
        self._known_mic_apps: set[str] = set()
        self._monitored_apps: set[str] = set()
        self._config: dict[str, Any] = {}
        self._load_config()
        self._scan_usb_initial()

    def _load_config(self):
        """Load security monitor configuration."""
        try:
            if _CONFIG_FILE.exists():
                self._config = {
                    **_DEFAULT_CONFIG,
                    **(__import__("json").loads(_CONFIG_FILE.read_text(encoding="utf-8"))),
                }
            else:
                self._config = dict(_DEFAULT_CONFIG)
        except Exception:
            self._config = dict(_DEFAULT_CONFIG)

    def _save_config(self):
        """Persist configuration."""
        try:
            _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            import json as _json
            _CONFIG_FILE.write_text(_json.dumps(self._config, indent=2), encoding="utf-8")
        except OSError as e:
            logger.warning("Failed to save security monitor config: %s", e)

    def _scan_usb_initial(self):
        """Take initial snapshot of connected USB devices."""
        try:
            devices = self._get_usb_devices()
            self._known_usb_devices = devices
            logger.info("Security monitor: found %d USB devices", len(devices))
        except Exception as e:
            logger.debug("USB initial scan failed: %s", e)

    def _get_usb_devices(self) -> set[str]:
        """Get set of currently connected USB device IDs.

        Uses PowerShell Get-CimInstance (Windows 11 compatible) instead of
        deprecated wmic which is removed in recent Windows versions.
        """
        devices = set()
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_PnPEntity | "
                 "Where-Object { $_.PNPClass -eq 'USB' } | "
                 "Select-Object DeviceID, Name | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0 and result.stdout.strip():
                import json as _json
                items = _json.loads(result.stdout)
                if isinstance(items, dict):
                    items = [items]
                for item in items:
                    device_id = item.get("DeviceID", "")
                    name = item.get("Name", "")
                    if device_id:
                        devices.add(f"{device_id}|{name}")
        except Exception:
            pass
        return devices

    def _check_usb_changes(self) -> list[SecurityAlert]:
        """Check for USB device connect/disconnect events."""
        alerts = []
        try:
            current = self._get_usb_devices()
            # New devices connected
            new_devices = current - self._known_usb_devices
            for device_id in new_devices:
                alerts.append(SecurityAlert(
                    timestamp=time.time(),
                    category="usb",
                    severity="warning",
                    title="USB Device Connected",
                    description=f"New USB device detected: {device_id[:60]}",
                    details={"device_id": device_id, "event": "connected"},
                ))
            # Devices disconnected
            removed = self._known_usb_devices - current
            for device_id in removed:
                alerts.append(SecurityAlert(
                    timestamp=time.time(),
                    category="usb",
                    severity="info",
                    title="USB Device Disconnected",
                    description=f"USB device removed: {device_id[:60]}",
                    details={"device_id": device_id, "event": "disconnected"},
                ))
            self._known_usb_devices = current
        except Exception as e:
            logger.debug("USB check error: %s", e)
        return alerts

    def _check_microphone_access(self) -> list[SecurityAlert]:
        """Check for apps currently using the microphone."""
        alerts = []
        try:
            # Use PowerShell to query audio sessions for microphone input
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-AudioSession -ErrorAction SilentlyContinue | "
                 "Where-Object {$_.State -eq 'Active' -and $_.AudioMeterInformation -ne $null} | "
                 "Select-Object ProcessName, State | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0 and result.stdout.strip():
                import json as _json
                sessions = _json.loads(result.stdout)
                if isinstance(sessions, dict):
                    sessions = [sessions]
                for session in sessions:
                    proc = session.get("ProcessName", "")
                    if proc and proc.lower() not in _KNOWN_SAFE_MIC_APPS:
                        if proc not in self._known_mic_apps:
                            alerts.append(SecurityAlert(
                                timestamp=time.time(),
                                category="microphone",
                                severity="warning",
                                title="Microphone Access Detected",
                                description=f"'{proc}' is using the microphone",
                                details={"process": proc, "state": session.get("State", "Active")},
                            ))
                            self._known_mic_apps.add(proc)
                    elif proc:
                        self._known_mic_apps.add(proc)
        except Exception:
            pass
        return alerts

    def _check_suspicious_apps(self) -> list[SecurityAlert]:
        """Check for suspicious or newly launched high-risk apps."""
        alerts = []
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process | Select-Object ProcessName, Id, Path | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0 and result.stdout.strip():
                import json as _json
                procs = _json.loads(result.stdout)
                if isinstance(procs, dict):
                    procs = [procs]
                for proc in procs:
                    name = proc.get("ProcessName", "")
                    path = proc.get("Path", "")
                    if name and name not in self._monitored_apps:
                        # Check against suspicious patterns
                        for pattern in _SUSPICIOUS_PATTERNS:
                            if pattern.lower() in name.lower():
                                alerts.append(SecurityAlert(
                                    timestamp=time.time(),
                                    category="app_launch",
                                    severity="warning",
                                    title="Suspicious App Launch",
                                    description=f"'{name}' matches suspicious pattern '{pattern}'",
                                    details={"process": name, "path": path},
                                ))
                                break
                        self._monitored_apps.add(name)
        except Exception:
            pass
        return alerts

    async def _monitor_loop(self):
        """Background monitoring loop."""
        while self._active:
            try:
                alerts = []
                alerts.extend(self._check_usb_changes())
                alerts.extend(self._check_microphone_access())
                alerts.extend(self._check_suspicious_apps())

                for alert in alerts:
                    self._alerts.append(alert)
                    logger.info(
                        "Security alert [%s]: %s — %s",
                        alert.severity, alert.title, alert.description,
                    )

                # Trim old alerts
                if len(self._alerts) > self._max_alerts:
                    self._alerts = self._alerts[-self._max_alerts:]

            except Exception as e:
                logger.debug("Security monitor loop error: %s", e)

            await asyncio.sleep(self._poll_interval)

    async def start(self):
        """Start the background monitoring loop."""
        if self._active:
            return
        if not any(self._config.get(k, True) for k in ("usb_monitoring", "microphone_monitoring", "app_monitoring")):
            logger.info("Security monitor: all monitoring disabled, skipping start")
            return
        self._active = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Security monitor started (interval=%ds)", self._poll_interval)

    async def stop(self):
        """Stop the background monitoring loop."""
        self._active = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Security monitor stopped")

    def get_alerts(
        self,
        category: str = "",
        severity: str = "",
        limit: int = 50,
        unacknowledged_only: bool = False,
    ) -> list[dict]:
        """Get security alerts with optional filters."""
        alerts = self._alerts
        if category:
            alerts = [a for a in alerts if a.category == category]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        return [
            {
                "timestamp": a.timestamp,
                "category": a.category,
                "severity": a.severity,
                "title": a.title,
                "description": a.description,
                "details": a.details,
                "acknowledged": a.acknowledged,
            }
            for a in reversed(alerts[-limit:])
        ]

    def acknowledge_alert(self, index: int) -> bool:
        """Acknowledge an alert by index (0 = most recent)."""
        if 0 <= index < len(self._alerts):
            self._alerts[-(index + 1)].acknowledged = True
            return True
        return False

    def get_status(self) -> dict:
        """Get security monitor status."""
        return {
            "active": self._active,
            "usb_devices_known": len(self._known_usb_devices),
            "mic_apps_known": len(self._known_mic_apps),
            "total_alerts": len(self._alerts),
            "unacknowledged": sum(1 for a in self._alerts if not a.acknowledged),
            "poll_interval": self._poll_interval,
            "config": self._config,
        }

    def update_config(self, **kwargs) -> dict:
        """Update configuration."""
        for key, value in kwargs.items():
            if key in _DEFAULT_CONFIG:
                self._config[key] = value
        if "poll_interval" in kwargs:
            self._poll_interval = max(5.0, float(kwargs["poll_interval"]))
        self._save_config()
        return {"status": "ok", "config": self._config}


# ── Constants ──────────────────────────────────────────────────────────────

_DEFAULT_CONFIG = {
    "usb_monitoring": True,
    "microphone_monitoring": True,
    "app_monitoring": True,
    "poll_interval": 10.0,
    "alert_on_safe_usb": False,  # Only alert on new/unknown devices
}

# Apps that commonly use the microphone — don't alert on these
_KNOWN_SAFE_MIC_APPS = {
    "teams", "zoom", "discord", "skype", "chrome", "firefox", "edge",
    "ms-teams", "whatsapp", "telegram", "slack",
}

# Patterns that indicate potentially suspicious apps
_SUSPICIOUS_PATTERNS = {
    "keylogger", "rat", "trojan", "backdoor", "hack", "exploit",
    "inject", "credential", "stealer", "miner", "crypto",
}
