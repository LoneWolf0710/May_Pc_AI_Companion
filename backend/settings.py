"""May AI Settings — persistent preferences stored at ~/.may/settings.json.

Provides a simple key-value store for user preferences like default model,
city location, and other app-wide settings.
"""

import json
import logging
import os as _os
import threading
from pathlib import Path

logger = logging.getLogger("may.settings")

_SETTINGS_DIR = Path(_os.path.expanduser("~")) / ".may"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"

# Default settings
_DEFAULTS = {
    "default_provider": "ollama",
    "default_model": "qwen3:4b",
    "city": "",  # Empty = use IP geolocation
}

_lock = threading.Lock()


def _load() -> dict:
    """Load settings from disk. Returns merged defaults."""
    settings = dict(_DEFAULTS)
    if _SETTINGS_FILE.exists():
        try:
            stored = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                settings.update(stored)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load settings: %s", e)
    return settings


def _save(settings: dict) -> None:
    """Persist settings to disk."""
    try:
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        _SETTINGS_FILE.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Settings saved to %s", _SETTINGS_FILE)
    except OSError as e:
        logger.warning("Failed to save settings: %s", e)


def get_settings() -> dict:
    """Get all current settings."""
    with _lock:
        return _load()


def update_settings(updates: dict) -> dict:
    """Update specific settings and save. Returns the full updated settings."""
    with _lock:
        settings = _load()
        for key, value in updates.items():
            if key in _DEFAULTS:
                settings[key] = value
            else:
                logger.warning("Unknown setting key: %s", key)
        _save(settings)
        return settings


def get_setting(key: str, default=None):
    """Get a single setting value."""
    with _lock:
        settings = _load()
        return settings.get(key, default)
