"""Ollama Configuration Helper — Auto-sets optimal environment variables.

Architecture spec (Part 10):
    OLLAMA_FLASH_ATTENTION=1       # 30-50% VRAM savings for KV cache
    OLLAMA_MAX_LOADED_MODELS=2     # Keep router + main loaded simultaneously
    OLLAMA_KEEP_ALIVE=24h          # Models stay loaded, zero cold-start latency
    OLLAMA_NUM_PARALLEL=2          # Allow 2 concurrent requests

These must be set at the SYSTEM level (Windows System Properties → Environment Variables),
not in the shell, for Ollama's service to pick them up.

This module:
1. Checks if optimal env vars are already set
2. Logs warnings if they're missing or suboptimal
3. Can optionally set them via `setx` (Windows) or shell export
4. Provides a health check that reports current Ollama config status
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess

logger = logging.getLogger("may.llm.ollama_config")

# Optimal environment variables for May's dual-instance setup
OPTIMAL_ENV = {
    "OLLAMA_FLASH_ATTENTION": "1",        # 30-50% VRAM savings for KV cache
    "OLLAMA_MAX_LOADED_MODELS": "2",      # Keep router + main loaded simultaneously
    "OLLAMA_KEEP_ALIVE": "24h",           # Models stay loaded, zero cold-start latency
    "OLLAMA_NUM_PARALLEL": "2",           # Allow 2 concurrent requests
}

# Recommended but not critical
RECOMMENDED_ENV = {
    "OLLAMA_HOST": "0.0.0.0:11434",      # Listen on all interfaces (for remote access)
}


def check_ollama_config() -> dict:
    """Check current Ollama environment variable configuration.

    Returns a dict with:
    - status: 'optimal', 'partial', or 'missing'
    - set_vars: dict of currently set vars and their values
    - missing_vars: list of vars that should be set
    - recommendations: list of human-readable recommendations
    """
    set_vars = {}
    missing_vars = []
    recommendations = []

    for var, expected in OPTIMAL_ENV.items():
        current = os.environ.get(var, "")
        if current:
            set_vars[var] = current
            if current != expected:
                recommendations.append(
                    f"{var}={current} (recommended: {expected})"
                )
        else:
            missing_vars.append(var)

    # Check recommended (non-critical)
    for var, expected in RECOMMENDED_ENV.items():
        current = os.environ.get(var, "")
        if current:
            set_vars[var] = current
        else:
            recommendations.append(f"{var} not set (recommended: {expected})")

    if not missing_vars:
        status = "optimal"
    elif len(missing_vars) < len(OPTIMAL_ENV):
        status = "partial"
    else:
        status = "missing"

    return {
        "status": status,
        "set_vars": set_vars,
        "missing_vars": missing_vars,
        "recommendations": recommendations,
        "platform": platform.system(),
    }


def set_ollama_env_vars() -> dict:
    """Set optimal Ollama environment variables at the system level.

    On Windows: uses `setx` to set persistent system environment variables.
    On Linux/macOS: provides instructions for ~/.bashrc or systemd.

    Returns a dict with status and details.
    """
    if platform.system() != "Windows":
        return {
            "status": "manual",
            "message": "Non-Windows platform. Set env vars manually or via systemd.",
            "vars": OPTIMAL_ENV,
        }

    results = {}
    for var, value in OPTIMAL_ENV.items():
        current = os.environ.get(var, "")
        if current == value:
            results[var] = {"status": "already_set", "value": value}
            continue

        # Always set in current process so it takes effect immediately
        os.environ[var] = value

        try:
            # setx sets persistent system environment variables on Windows
            proc = subprocess.run(
                ["setx", var, value],
                capture_output=True, text=True, timeout=10,
            )
            if proc.returncode == 0:
                results[var] = {"status": "set", "value": value}
                logger.info("Set %s=%s", var, value)
            else:
                results[var] = {
                    "status": "persist_failed",
                    "value": value,
                    "error": proc.stderr.strip()[:200],
                }
                logger.warning("setx failed for %s (set in current process): %s", var, proc.stderr[:100])
        except FileNotFoundError:
            results[var] = {
                "status": "persist_failed",
                "value": value,
                "error": "setx not found — set in current process only",
            }
        except Exception as e:
            results[var] = {"status": "persist_failed", "value": value, "error": str(e)[:200]}

    # Count success as "set" OR "persist_failed" (var is in os.environ either way)
    active_count = sum(1 for r in results.values() if r["status"] in ("set", "already_set", "persist_failed"))
    return {
        "status": "ok" if active_count == len(OPTIMAL_ENV) else "partial",
        "results": results,
        "message": f"Set {active_count}/{len(OPTIMAL_ENV)} variables in current process. setx persistence may require admin.",
    }


def get_ollama_config_summary() -> str:
    """Get a human-readable summary of Ollama configuration status."""
    config = check_ollama_config()
    lines = [f"Ollama Config: {config['status'].upper()}"]

    for var, value in config["set_vars"].items():
        lines.append(f"  ✓ {var}={value}")

    for var in config["missing_vars"]:
        lines.append(f"  ✗ {var} (not set)")

    for rec in config["recommendations"]:
        lines.append(f"  ℹ {rec}")

    if config["missing_vars"]:
        lines.append("")
        lines.append("To fix, run:")
        lines.append("  python -c \"from llm.ollama_config import set_ollama_env_vars; print(set_ollama_env_vars())\"")
        lines.append("Then restart Ollama service.")

    return "\n".join(lines)
