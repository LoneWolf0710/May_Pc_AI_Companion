"""Configuration Loader — reads layer_caps.json and fallback_chains.json.

Provides runtime access to:
  - Layer capability maps (which actions each layer supports)
  - Fallback chain strategies (which methods to try per action type)

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md:
  - layer_caps.json: What each layer can do (capability map)
  - fallback_chains.json: Fallback strategy per action type
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("may.core.config_loader")

_CONFIG_DIR = Path(__file__).parent.parent / "config"

# ── Lazy-loaded caches ───────────────────────────────────────────────────────

_layer_caps: dict[str, Any] | None = None
_fallback_chains: dict[str, Any] | None = None


def _load_json(filename: str) -> dict[str, Any]:
    """Load a JSON config file from core/config/."""
    path = _CONFIG_DIR / filename
    if not path.exists():
        logger.warning("Config file not found: %s", path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load %s: %s", path, e)
        return {}


# ── Layer Capabilities ───────────────────────────────────────────────────────

def get_layer_caps() -> dict[str, Any]:
    """Get the full layer capabilities map."""
    global _layer_caps
    if _layer_caps is None:
        data = _load_json("layer_caps.json")
        _layer_caps = data.get("layers", {})
    return _layer_caps


def get_layer_actions(layer_name: str) -> list[str]:
    """Get the list of actions supported by a layer."""
    caps = get_layer_caps()
    layer = caps.get(layer_name, {})
    return layer.get("actions", [])


def get_layer_libraries(layer_name: str) -> list[str]:
    """Get the libraries used by a layer."""
    caps = get_layer_caps()
    layer = caps.get(layer_name, {})
    return layer.get("libraries", [])


def get_layer_privilege_level(layer_name: str) -> str:
    """Get the required privilege level for a layer."""
    caps = get_layer_caps()
    layer = caps.get(layer_name, {})
    return layer.get("privilege_level", "admin")


def is_action_supported(layer_name: str, action_name: str) -> bool:
    """Check if a specific action is supported by a layer."""
    actions = get_layer_actions(layer_name)
    return action_name in actions


# ── Fallback Chain Strategies ────────────────────────────────────────────────

def get_fallback_chains() -> dict[str, Any]:
    """Get the full fallback chains config."""
    global _fallback_chains
    if _fallback_chains is None:
        data = _load_json("fallback_chains.json")
        _fallback_chains = {k: v for k, v in data.items() if not k.startswith("_")}
    return _fallback_chains


def get_fallback_strategy(layer_name: str, action_name: str) -> dict[str, Any] | None:
    """Get the fallback strategy for a specific action.

    Returns dict with keys: description, methods (list of strings), verifier
    Returns None if no strategy defined.
    """
    chains = get_fallback_chains()
    layer = chains.get(layer_name, {})
    return layer.get(action_name)


def get_expected_method_count(layer_name: str, action_name: str) -> int | None:
    """Get the expected number of fallback methods for an action from the config."""
    strategy = get_fallback_strategy(layer_name, action_name)
    if strategy and "methods" in strategy:
        return len(strategy["methods"])
    return None


def reload_configs() -> None:
    """Force reload all config files from disk."""
    global _layer_caps, _fallback_chains
    _layer_caps = None
    _fallback_chains = None
    logger.info("Config files reloaded from disk")
