"""Smart Home integration — Home Assistant REST API client.

Provides a simple interface to control Home Assistant-compatible devices.
Requires a long-lived access token configured in Settings.

Usage:
    smart_home = SmartHomeClient(token="your_token")
    await smart_home.connect()
    lights = await smart_home.get_entities(domain="light")
    await smart_home.call_service("light", "turn_on", {"entity_id": "light.living_room"})
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger("may.integrations.smart_home")

# Config file for smart home settings
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".may", "smart_home.json")


@dataclass
class SmartHomeConfig:
    """Smart home configuration."""
    ha_url: str = ""           # e.g., "http://192.168.1.100:8123"
    ha_token: str = ""         # Long-lived access token
    enabled: bool = False

    def save(self):
        """Save config to disk."""
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump({
                "ha_url": self.ha_url,
                "ha_token": self.ha_token,
                "enabled": self.enabled,
            }, f, indent=2)

    @classmethod
    def load(cls) -> "SmartHomeConfig":
        """Load config from disk."""
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
                return cls(
                    ha_url=data.get("ha_url", ""),
                    ha_token=data.get("ha_token", ""),
                    enabled=data.get("enabled", False),
                )
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()


@dataclass
class SmartDevice:
    """A smart home device/entity."""
    entity_id: str
    state: str
    friendly_name: str = ""
    domain: str = ""           # "light", "switch", "climate", etc.
    attributes: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "friendly_name": self.friendly_name,
            "domain": self.domain,
            "attributes": {k: v for k, v in self.attributes.items()
                          if k in ("brightness", "temperature", "hue", "rgb_color")},
        }

    def to_briefing_text(self) -> str:
        """Brief text for the morning briefing."""
        status = "on" if self.state == "on" else "off"
        name = self.friendly_name or self.entity_id
        return f"{name}: {status}"


class SmartHomeClient:
    """Client for Home Assistant REST API.

    Requires:
    - Home Assistant running on the local network
    - A long-lived access token (created in HA profile settings)
    """

    def __init__(self, config: SmartHomeConfig | None = None):
        self._config = config or SmartHomeConfig.load()
        self._connected = False

    @property
    def enabled(self) -> bool:
        return self._config.enabled and bool(self._config.ha_url and self._config.ha_token)

    def configure(self, ha_url: str, ha_token: str):
        """Configure Home Assistant connection."""
        self._config.ha_url = ha_url.rstrip("/")
        self._config.ha_token = ha_token
        self._config.enabled = True
        self._config.save()
        logger.info("Smart home configured: %s", ha_url)

    def disable(self):
        """Disable smart home integration."""
        self._config.enabled = False
        self._config.save()
        self._connected = False

    async def _request(self, method: str, path: str, data: dict | None = None) -> dict | list | None:
        """Make an authenticated request to Home Assistant."""
        if not self.enabled:
            return None

        try:
            import httpx
            url = f"{self._config.ha_url}{path}"
            headers = {
                "Authorization": f"Bearer {self._config.ha_token}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=10) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                elif method == "POST":
                    resp = await client.post(url, headers=headers, json=data)
                else:
                    return None

                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning("Smart home request failed: %s", e)
            return None

    async def test_connection(self) -> bool:
        """Test connection to Home Assistant."""
        result = await self._request("GET", "/api/")
        if result:
            self._connected = True
            logger.info("Connected to Home Assistant: %s", result.get("message", "OK"))
            return True
        self._connected = False
        return False

    async def get_states(self) -> list[SmartDevice]:
        """Get all entity states from Home Assistant."""
        result = await self._request("GET", "/api/states")
        if not result or not isinstance(result, list):
            return []

        devices = []
        for entity in result:
            entity_id = entity.get("entity_id", "")
            domain = entity_id.split(".")[0] if "." in entity_id else ""

            # Filter to useful domains
            if domain not in ("light", "switch", "climate", "media_player",
                              "sensor", "binary_sensor", "cover", "fan",
                              "lock", "vacuum", "camera"):
                continue

            devices.append(SmartDevice(
                entity_id=entity_id,
                state=entity.get("state", "unknown"),
                friendly_name=entity.get("attributes", {}).get("friendly_name", ""),
                domain=domain,
                attributes=entity.get("attributes", {}),
            ))

        return devices

    async def get_entities(self, domain: str | None = None) -> list[SmartDevice]:
        """Get entities, optionally filtered by domain."""
        devices = await self.get_states()
        if domain:
            devices = [d for d in devices if d.domain == domain]
        return devices

    async def call_service(self, domain: str, service: str,
                           data: dict | None = None) -> bool:
        """Call a Home Assistant service.

        Examples:
            await call_service("light", "turn_on", {"entity_id": "light.living_room"})
            await call_service("climate", "set_temperature", {"entity_id": "climate.bedroom", "temperature": 22})
            await call_service("media_player", "media_pause", {"entity_id": "media_player.living_room"})
        """
        path = f"/api/services/{domain}/{service}"
        result = await self._request("POST", path, data or {})
        if result is not None:
            logger.info("Smart home service called: %s.%s", domain, service)
            return True
        return False

    async def toggle_entity(self, entity_id: str) -> bool:
        """Toggle a device on/off."""
        domain = entity_id.split(".")[0]
        return await self.call_service(domain, "toggle", {"entity_id": entity_id})

    async def get_automation_summary(self) -> str:
        """Get a summary of automations for the morning briefing."""
        automations = await self.get_entities(domain="automation")
        if not automations:
            return "No automations found."

        active = sum(1 for a in automations if a.state == "on")
        return f"{active}/{len(automations)} automations active"

    def get_status(self) -> dict:
        """Get smart home integration status."""
        return {
            "enabled": self.enabled,
            "connected": self._connected,
            "ha_url": self._config.ha_url if self.enabled else "",
            "has_token": bool(self._config.ha_token),
        }
