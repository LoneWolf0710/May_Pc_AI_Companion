"""Llama-Server Lifecycle Manager — True Speculative Decoding via llama.cpp.

Manages a llama-server instance with draft model support for real speculative
decoding (~25-40% speedup). Unlike the previous software approximation (draft
prefix → main continuation), this uses llama-server's internal batch verification:

1. Draft model (qwen3:0.6b) generates N candidate tokens
2. Target model (phi4-mini:3.8b) verifies all N tokens in a single batch forward pass
3. Accepted tokens are kept; rejected tokens are regenerated from the rejection point

The server exposes an OpenAI-compatible /v1/chat/completions endpoint, so our
existing streaming infrastructure works unchanged.

Key config:
- llama-server runs on port 8081 (8080 conflicts with FastAPI backend)
- Both models must share vocabulary/tokenizer (gguf format)
- Draft model should be ~10x smaller than target for optimal speedup

Reference: https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("may.llm.llama_server")

# ── Configuration ───────────────────────────────────────────────────────────

# llama-server port (must NOT conflict with FastAPI on 8080 or Ollama on 11434/11435)
LLAMA_SERVER_PORT = int(os.environ.get("MAY_LLAMA_SERVER_PORT", "8081"))
LLAMA_SERVER_HOST = os.environ.get("MAY_LLAMA_SERVER_HOST", "127.0.0.1")

# Default model paths (GGUF format) — user should configure these
# These are relative to common locations; resolved at startup
_DEFAULT_CONFIG = {
    "enabled": False,  # Disabled by default — user must configure model paths
    "target_model": "",   # Path to target GGUF (e.g. phi4-mini-Q4_K_M.gguf)
    "draft_model": "",    # Path to draft GGUF (e.g. qwen3-0.6b-Q4_K_M.gguf)
    "port": LLAMA_SERVER_PORT,
    "n_ctx": 131072,
    "n_gpu_layers": 999,  # Offload all layers to GPU
    "draft_n_max": 5,     # Max tokens to draft per step
    "threads": None,       # None = auto-detect CPU cores
    "extra_args": [],      # Additional llama-server flags
}

_CONFIG_DIR = Path.home() / ".may"
_CONFIG_FILE = _CONFIG_DIR / "llama_server.json"

# Where Ollama stores GGUF models (common locations)
_OLLAMA_MODEL_DIRS = [
    Path.home() / ".ollama" / "models",
    Path.home() / "AppData" / "Local" / "Ollama" / "models",
]


@dataclass
class LlamaServerState:
    """Tracks the llama-server process and its state."""
    process: subprocess.Popen | None = None
    pid: int | None = None
    port: int = LLAMA_SERVER_PORT
    started_at: float = 0.0
    ready: bool = False
    target_model: str = ""
    draft_model: str = ""
    error: str | None = None
    # Performance stats from server logs
    draft_acceptance_rate: float = 0.0
    total_tokens_generated: int = 0
    avg_tokens_per_second: float = 0.0


# ── Global state ────────────────────────────────────────────────────────────

_state = LlamaServerState()
_config: dict[str, Any] = dict(_DEFAULT_CONFIG)


def _load_config() -> dict[str, Any]:
    """Load config from disk, merging with defaults."""
    global _config
    _config = dict(_DEFAULT_CONFIG)
    try:
        if _CONFIG_FILE.exists():
            saved = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            _config.update(saved)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load llama-server config: %s", e)
    return _config


def _save_config() -> None:
    """Persist config to disk."""
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Don't save runtime state, only user config
        save_data = {k: v for k, v in _config.items()}
        _CONFIG_FILE.write_text(json.dumps(save_data, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("Failed to save llama-server config: %s", e)


# ── Model path resolution ───────────────────────────────────────────────────

def _find_ollama_gguf(model_name: str) -> str | None:
    """Try to find a GGUF file for an Ollama model by name.

    Ollama stores models as blobs. The manifest maps model names to blob hashes.
    We look for the GGUF blob in the Ollama models directory.
    """
    for models_dir in _OLLAMA_MODEL_DIRS:
        manifest_path = models_dir / "manifests" / "registry.ollama.ai" / "library" / model_name / "latest"
        if not manifest_path.exists():
            # Try with tag
            for tag in ["latest", "current"]:
                manifest_path = models_dir / "manifests" / "registry.ollama.ai" / "library" / model_name / tag
                if manifest_path.exists():
                    break
        if not manifest_path.exists():
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            layers = manifest.get("layers", [])
            for layer in layers:
                media_type = layer.get("mediaType", "")
                digest = layer.get("digest", "")
                if "model" in media_type and digest:
                    # Resolve blob path
                    blob_path = models_dir / "blobs" / digest.replace(":", "-")
                    if blob_path.exists():
                        return str(blob_path)
        except Exception as e:
            logger.debug("Failed to parse Ollama manifest for %s: %s", model_name, e)
    return None


def resolve_model_path(model_spec: str) -> str | None:
    """Resolve a model specification to a GGUF file path.

    Accepts:
    - Absolute path to a .gguf file: /path/to/model.gguf
    - Ollama model name: qwen3:0.6b (tries to find the GGUF blob)
    - Relative path: ./models/phi4-mini.gguf (resolved from project root)
    """
    if not model_spec:
        return None

    # Absolute path to GGUF
    path = Path(model_spec)
    if path.is_absolute() and path.exists() and path.suffix == ".gguf":
        return str(path)

    # Relative path
    if not path.is_absolute():
        resolved = Path.cwd() / path
        if resolved.exists() and resolved.suffix == ".gguf":
            return str(resolved)
        # Also check project root
        project_root = Path(__file__).parent.parent.parent
        resolved = project_root / path
        if resolved.exists() and resolved.suffix == ".gguf":
            return str(resolved)

    # Try as Ollama model name (extract base name without tag)
    base_name = model_spec.split(":")[0]
    gguf_path = _find_ollama_gguf(base_name)
    if gguf_path:
        return gguf_path

    return None


# ── Server lifecycle ────────────────────────────────────────────────────────

def is_llama_server_running() -> bool:
    """Check if llama-server is responding on its port."""
    return _state.ready and _state.pid is not None


def get_llama_server_url() -> str:
    """Get the base URL for llama-server API calls."""
    return f"http://{LLAMA_SERVER_HOST}:{_state.port}"


async def check_llama_server_health() -> dict[str, Any]:
    """Check if llama-server is healthy and return status info."""
    url = get_llama_server_url()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            # Try /health endpoint
            resp = await client.get(f"{url}/health")
            if resp.status_code == 200:
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                return {
                    "running": True,
                    "port": _state.port,
                    "pid": _state.pid,
                    "target_model": _state.target_model,
                    "draft_model": _state.draft_model,
                    "uptime_seconds": time.time() - _state.started_at if _state.started_at else 0,
                    "health": data,
                }
    except (httpx.ConnectError, httpx.HTTPError, httpx.TimeoutException):
        pass

    return {
        "running": False,
        "port": _state.port,
        "pid": None,
        "error": _state.error,
    }


async def start_llama_server(
    target_model: str | None = None,
    draft_model: str | None = None,
    port: int | None = None,
    n_ctx: int | None = None,
    n_gpu_layers: int | None = None,
    draft_n_max: int | None = None,
) -> dict[str, Any]:
    """Start llama-server with speculative decoding enabled.

    Args:
        target_model: Path to target GGUF model file
        draft_model: Path to draft GGUF model file
        port: Server port (default 8081)
        n_ctx: Context window size
        n_gpu_layers: Number of GPU layers (-1 or 999 for all)
        draft_n_max: Max tokens to draft per step

    Returns:
        Status dict with success/error info
    """
    global _state

    # Stop existing server if running
    if _state.process and _state.process.poll() is None:
        await stop_llama_server()

    _load_config()

    # Resolve parameters (args > config > defaults)
    target = target_model or _config.get("target_model", "")
    draft = draft_model or _config.get("draft_model", "")
    _port = port or _config.get("port", LLAMA_SERVER_PORT)
    _n_ctx = n_ctx or _config.get("n_ctx", 131072)
    _n_gpu = n_gpu_layers if n_gpu_layers is not None else _config.get("n_gpu_layers", 999)
    _draft_max = draft_n_max or _config.get("draft_n_max", 5)

    # Resolve model paths
    target_path = resolve_model_path(target)
    draft_path = resolve_model_path(draft)

    if not target_path:
        return {
            "success": False,
            "error": f"Target model not found: '{target}'. Provide a GGUF file path or Ollama model name.",
            "hint": "Set the target model in Settings → Speculative Decoding, e.g. 'phi4-mini:3.8b'",
        }

    if not draft_path:
        return {
            "success": False,
            "error": f"Draft model not found: '{draft}'. Provide a GGUF file path or Ollama model name.",
            "hint": "Set the draft model in Settings → Speculative Decoding, e.g. 'qwen3:0.6b'",
        }

    # Check if the required executables exist
    llama_server_exe = _find_llama_server_executable()
    if not llama_server_exe:
        return {
            "success": False,
            "error": "llama-server executable not found. Install llama.cpp or set MAY_LLAMA_SERVER_PATH.",
            "hint": "Download from https://github.com/ggml-org/llama.cpp/releases",
        }

    # Build command
    cmd = [
        llama_server_exe,
        "-m", target_path,
        "-md", draft_path,
        "--port", str(_port),
        "--host", LLAMA_SERVER_HOST,
        "-c", str(_n_ctx),
        "-ngl", str(_n_gpu),
        "--draft-n-max", str(_draft_max),
        "--spec-type", "draft-simple",
    ]

    threads = _config.get("threads")
    if threads:
        cmd.extend(["-t", str(threads)])

    extra_args = _config.get("extra_args", [])
    if extra_args:
        cmd.extend(extra_args)

    logger.info("Starting llama-server: %s", " ".join(cmd))

    try:
        # Start the process
        log_file = _CONFIG_DIR / "llama_server.log"
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        log_fh = open(log_file, "a", encoding="utf-8")

        proc = subprocess.Popen(
            cmd,
            stdout=log_fh,
            stderr=log_fh,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        _state.process = proc
        _state.pid = proc.pid
        _state.port = _port
        _state.started_at = time.time()
        _state.target_model = target_path
        _state.draft_model = draft_path
        _state.error = None
        _state.ready = False

        # Wait for server to become ready (poll /health endpoint)
        url = f"http://{LLAMA_SERVER_HOST}:{_port}"
        ready = False
        for attempt in range(60):  # Up to 30 seconds
            await asyncio.sleep(0.5)
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(f"{url}/health")
                    if resp.status_code == 200:
                        ready = True
                        break
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            # Check if process crashed
            if proc.poll() is not None:
                _state.error = f"llama-server exited with code {proc.returncode}"
                return {
                    "success": False,
                    "error": _state.error,
                    "log_file": str(log_file),
                }

        if ready:
            _state.ready = True
            logger.info(
                "llama-server ready on port %d (PID %d) — target=%s, draft=%s",
                _port, proc.pid, target_path.split("/")[-1], draft_path.split("/")[-1],
            )
            return {
                "success": True,
                "port": _port,
                "pid": proc.pid,
                "target_model": target_path,
                "draft_model": draft_path,
                "url": url,
            }
        else:
            _state.error = "llama-server did not become ready within 30s"
            return {
                "success": False,
                "error": _state.error,
                "log_file": str(log_file),
            }

    except FileNotFoundError as e:
        _state.error = f"Failed to start llama-server: {e}"
        return {"success": False, "error": _state.error}
    except Exception as e:
        _state.error = f"Unexpected error starting llama-server: {e}"
        return {"success": False, "error": _state.error}


async def stop_llama_server() -> dict[str, Any]:
    """Stop the running llama-server process."""
    global _state

    if _state.process is None:
        return {"status": "not_running"}

    try:
        _state.process.terminate()
        # Wait up to 5 seconds for graceful shutdown
        for _ in range(10):
            if _state.process.poll() is not None:
                break
            await asyncio.sleep(0.5)
        # Force kill if still alive
        if _state.process.poll() is None:
            _state.process.kill()
            _state.process.wait(timeout=3)
    except Exception as e:
        logger.warning("Error stopping llama-server: %s", e)

    pid = _state.pid
    _state = LlamaServerState(port=_state.port)
    logger.info("llama-server stopped (PID %d)", pid)
    return {"status": "stopped", "pid": pid}


def _find_llama_server_executable() -> str | None:
    """Find the llama-server executable.

    Search order:
    1. MAY_LLAMA_SERVER_PATH environment variable
    2. llama-server in PATH
    3. Common install locations on Windows
    """
    # Environment variable override
    env_path = os.environ.get("MAY_LLAMA_SERVER_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    # Check PATH
    import shutil
    exe = shutil.which("llama-server") or shutil.which("llama-server.exe")
    if exe:
        return exe

    # Common Windows locations
    common_paths = [
        Path.home() / "llama.cpp" / "build" / "bin" / "Release" / "llama-server.exe",
        Path.home() / "llama.cpp" / "build" / "bin" / "llama-server.exe",
        Path.home() / "AppData" / "Local" / "Programs" / "llama.cpp" / "llama-server.exe",
        Path("C:/llama.cpp/build/bin/Release/llama-server.exe"),
        Path("C:/llama.cpp/build/bin/llama-server.exe"),
    ]
    for p in common_paths:
        if p.exists():
            return str(p)

    return None


def get_status() -> dict[str, Any]:
    """Get current llama-server status for the API."""
    _load_config()
    running = is_llama_server_running()
    return {
        "running": running,
        "port": _state.port,
        "pid": _state.pid if running else None,
        "target_model": _state.target_model if running else _config.get("target_model", ""),
        "draft_model": _state.draft_model if running else _config.get("draft_model", ""),
        "config": _config,
        "executable_found": _find_llama_server_executable() is not None,
        "target_resolved": resolve_model_path(_config.get("target_model", "")) is not None,
        "draft_resolved": resolve_model_path(_config.get("draft_model", "")) is not None,
    }


def update_config(**kwargs) -> dict[str, Any]:
    """Update llama-server configuration."""
    _load_config()
    for key, value in kwargs.items():
        if key in _DEFAULT_CONFIG:
            _config[key] = value
    _save_config()
    return get_status()
