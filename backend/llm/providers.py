"""Multi-provider LLM abstraction.

Supports:
- Ollama (local, no key needed)
- OpenAI (GPT-4o, GPT-4o-mini)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Haiku)
- Google Gemini (Gemini 1.5 Flash, Gemini 1.5 Pro)
- OpenRouter (access to 100+ models via single API)

All providers expose the same async streaming interface.
"""

import httpx
import json
import asyncio
import logging
import time
import os as _os
from pathlib import Path
from typing import AsyncGenerator

logger = logging.getLogger("may.llm.providers")


# ── Persistent HTTP Connection Pool ─────────────────────────────────────
# Singleton httpx.AsyncClient that reuses TCP connections across requests.
# Saves ~50-100ms per request from eliminated TCP handshake overhead.
# From LOCAL_MODEL.md — one of the key performance optimizations.

_ollama_http_client: httpx.AsyncClient | None = None
_external_http_client: httpx.AsyncClient | None = None


async def get_ollama_client() -> httpx.AsyncClient:
    """Get or create the persistent Ollama HTTP client with connection pooling."""
    global _ollama_http_client
    if _ollama_http_client is None or _ollama_http_client.is_closed:
        _ollama_http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=5.0),
            limits=httpx.Limits(
                max_connections=4,
                max_keepalive_connections=2,
                keepalive_expiry=300,  # 5 minutes
            ),
        )
    return _ollama_http_client


async def get_external_client() -> httpx.AsyncClient:
    """Get or create a persistent HTTP client for external API calls (OpenAI, OpenRouter, Gemini, Anthropic)."""
    global _external_http_client
    if _external_http_client is None or _external_http_client.is_closed:
        _external_http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(
                max_connections=8,
                max_keepalive_connections=4,
                keepalive_expiry=300,  # 5 minutes
            ),
        )
    return _external_http_client


async def close_http_clients():
    """Close all persistent HTTP clients. Called on app shutdown."""
    global _ollama_http_client, _external_http_client
    if _ollama_http_client and not _ollama_http_client.is_closed:
        await _ollama_http_client.aclose()
        logger.info("Closed Ollama HTTP client")
    _ollama_http_client = None
    if _external_http_client and not _external_http_client.is_closed:
        await _external_http_client.aclose()
        logger.info("Closed external HTTP client")
    _external_http_client = None

# ── OpenRouter Free Models Cache ─────────────────────────────────────────
# Free models are fetched from the OpenRouter API at startup and cached
# locally to ~/.may/openrouter_free_models.json so they never go stale.
# The hardcoded list in PROVIDERS serves as a fallback when API + cache fail.
_OPENROUTER_FREE_CACHE_DIR = Path(_os.path.expanduser("~")) / ".may"
_OPENROUTER_FREE_CACHE_FILE = _OPENROUTER_FREE_CACHE_DIR / "openrouter_free_models.json"

# In-memory cache of live free models (updated by refresh_openrouter_free_models)
_openrouter_free_models_cache: list[dict] = []
_openrouter_free_last_refresh: float = 0.0  # timestamp
_OPENROUTER_FREE_REFRESH_INTERVAL = 3600.0  # re-fetch from API every hour

# ── Provider definitions ────────────────────────────────────────────────────

PROVIDERS = {
    "ollama": {
        "name": "Ollama (Local)",
        "requires_key": False,
        "base_url": "http://localhost:11434",
    "models": [
        {"id": "phi4-mini:3.8b", "name": "Phi-4 Mini 3.8B", "fast": True},
        {"id": "qwen3:0.6b", "name": "Qwen3 0.6B (Router)", "fast": True},
        {"id": "qwen3:4b", "name": "Qwen3 4B", "fast": True},
        {"id": "gemma2:2b", "name": "Gemma2 2B", "fast": True},
    ],
    },
    "openai": {
        "name": "OpenAI",
        "requires_key": True,
        "env_key": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o", "fast": False},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "fast": True},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "fast": False},
        ],
    },
    "anthropic": {
        "name": "Anthropic",
        "requires_key": True,
        "env_key": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com",
        "models": [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "fast": False},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "fast": True},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "fast": False},
        ],
    },
    "gemini": {
        "name": "Google Gemini",
        "requires_key": True,
        "env_key": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models": [
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "fast": False},
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "fast": True},
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "fast": True},
            {"id": "gemini-2.0-flash-lite", "name": "Gemini 2.0 Flash Lite", "fast": True},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "fast": False},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "fast": True},
        ],
    },
    "google_ai_studio": {
        "name": "Google AI Studio",
        "requires_key": True,
        "env_key": "GOOGLE_AI_STUDIO_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models": [
            # Free tier models available at aistudio.google.com
            # Same API as Gemini — key obtained from AI Studio (free)
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "fast": True},
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "fast": True},
            {"id": "gemini-2.0-flash-lite", "name": "Gemini 2.0 Flash Lite", "fast": True},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "fast": True},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "fast": False},
            {"id": "gemma-3-27b-it", "name": "Gemma 3 27B", "fast": False},
            {"id": "gemma-3-12b-it", "name": "Gemma 3 12B", "fast": True},
            {"id": "gemma-3-4b-it", "name": "Gemma 3 4B", "fast": True},
        ],
    },
    "openrouter": {
        "name": "OpenRouter",
        "requires_key": True,
        "env_key": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            # OpenAI
            {"id": "openai/gpt-4o", "name": "GPT-4o", "fast": False},
            {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "fast": True},
            {"id": "openai/gpt-4-turbo", "name": "GPT-4 Turbo", "fast": False},
            {"id": "openai/o1", "name": "o1 Reasoning", "fast": False},
            {"id": "openai/o1-mini", "name": "o1 Mini", "fast": True},
            {"id": "openai/o1-pro", "name": "o1 Pro", "fast": False},
            # Anthropic
            {"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4", "fast": False},
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "fast": False},
            {"id": "anthropic/claude-3.5-haiku", "name": "Claude 3.5 Haiku", "fast": True},
            {"id": "anthropic/claude-3-opus", "name": "Claude 3 Opus", "fast": False},
            # Google
            {"id": "google/gemini-2.0-flash", "name": "Gemini 2.0 Flash", "fast": True},
            {"id": "google/gemini-2.0-flash-lite", "name": "Gemini 2.0 Flash Lite", "fast": True},
            {"id": "google/gemini-1.5-pro", "name": "Gemini 1.5 Pro", "fast": False},
            {"id": "google/gemini-1.5-flash", "name": "Gemini 1.5 Flash", "fast": True},
            # Meta Llama
            {"id": "meta-llama/llama-4-maverick", "name": "Llama 4 Maverick", "fast": False},
            {"id": "meta-llama/llama-4-scout", "name": "Llama 4 Scout", "fast": True},
            {"id": "meta-llama/llama-3.1-405b-instruct", "name": "Llama 3.1 405B", "fast": False},
            {"id": "meta-llama/llama-3.1-70b-instruct", "name": "Llama 3.1 70B", "fast": False},
            {"id": "meta-llama/llama-3.1-8b-instruct", "name": "Llama 3.1 8B", "fast": True},
            # Mistral
            {"id": "mistralai/mistral-large-2411", "name": "Mistral Large 2411", "fast": False},
            {"id": "mistralai/mistral-small-2409", "name": "Mistral Small 2409", "fast": True},
            {"id": "mistralai/mixtral-8x22b-instruct", "name": "Mixtral 8x22B", "fast": False},
            {"id": "mistralai/mixtral-8x7b-instruct", "name": "Mixtral 8x7B", "fast": True},
            # DeepSeek
            {"id": "deepseek/deepseek-r1", "name": "DeepSeek R1", "fast": False},
            {"id": "deepseek/deepseek-chat", "name": "DeepSeek V3 Chat", "fast": False},
            {"id": "deepseek/deepseek-r1-distill-qwen-32b", "name": "DeepSeek R1 Distill 32B", "fast": False},
            # Qwen
            {"id": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 2.5 72B", "fast": False},
            {"id": "qwen/qwen-2.5-7b-instruct", "name": "Qwen 2.5 7B", "fast": True},
            {"id": "qwen/qwen-2.5-coder-32b-instruct", "name": "Qwen 2.5 Coder 32B", "fast": False},
            # Cohere
            {"id": "cohere/command-r-plus", "name": "Command R+", "fast": False},
            {"id": "cohere/command-r", "name": "Command R", "fast": True},
            # Kimi (Moonshot AI)
            {"id": "moonshotai/kimi-latest", "name": "Kimi Latest", "fast": True},
            {"id": "moonshotai/kimi-k2.6", "name": "Kimi K2.6", "fast": False},
            {"id": "moonshotai/kimi-k2.5", "name": "Kimi K2.5", "fast": False},
            {"id": "moonshotai/kimi-k2-thinking", "name": "Kimi K2 Thinking", "fast": False},
            {"id": "moonshotai/kimi-k2-0905", "name": "Kimi K2 0905", "fast": False},
            {"id": "moonshotai/kimi-k2", "name": "Kimi K2", "fast": False},
            # MiniMax
            {"id": "minimax/minimax-m2.5", "name": "MiniMax M2.5", "fast": True},
            {"id": "minimax/minimax-m2.7", "name": "MiniMax M2.7", "fast": False},
            {"id": "minimax/minimax-m3", "name": "MiniMax M3 Free", "fast": True},
            # DeepSeek V4
            {"id": "deepseek/deepseek-v4-flash", "name": "DeepSeek V4 Flash", "fast": True},
            {"id": "deepseek/deepseek-v4-flash:free", "name": "DeepSeek V4 Flash Free", "fast": True},
            {"id": "deepseek/deepseek-v4-pro", "name": "DeepSeek V4 Pro", "fast": False},
            # GLM (Z.ai)
            {"id": "z-ai/glm-5", "name": "GLM 5", "fast": False},
            {"id": "z-ai/glm-5.1", "name": "GLM 5.1", "fast": False},
            # Qwen 3.x
            {"id": "qwen/qwen3.5-plus", "name": "Qwen3.5 Plus", "fast": True},
            {"id": "qwen/qwen3.6-plus", "name": "Qwen3.6 Plus", "fast": True},
            {"id": "qwen/qwen3.6-plus:free", "name": "Qwen3.6 Plus Free", "fast": True},
            # xAI
            {"id": "x-ai/grok-build-0.1", "name": "Grok Build 0.1", "fast": False},
            # Xiaomi
            {"id": "xiaomi/mimo-v2.5:free", "name": "MiMo V2.5 Free", "fast": True},
            # Other
            {"id": "databricks/dbrx-instruct", "name": "DBRX Instruct", "fast": False},
            {"id": "nousresearch/hermes-3-llama-3.1-405b", "name": "Hermes 3 405B", "fast": False},
            {"id": "nousresearch/hermes-3-llama-3.1-70b", "name": "Hermes 3 70B", "fast": False},
            {"id": "microsoft/phi-3.5-moe-instruct", "name": "Phi-3.5 MoE", "fast": True},
            {"id": "microsoft/phi-4", "name": "Phi-4", "fast": True},
            # ── Free models (fetched live from OpenRouter API, June 2026) ──
            # Models verified against OpenRouter /api/v1/models endpoint
            # "fast" = small/fewer params, lower latency; false = large model, slower
            {"id": "openrouter/free", "name": "Free Models Router", "fast": False},
            {"id": "cohere/north-mini-code:free", "name": "Cohere North Mini Code (Free)", "fast": True},
            {"id": "nvidia/nemotron-3-super-120b-a12b:free", "name": "Nemotron 3 Super (Free)", "fast": False},
            {"id": "nvidia/nemotron-3-nano-30b-a3b:free", "name": "Nemotron 3 Nano 30B (Free)", "fast": True},
            {"id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "name": "Nemotron 3 Nano Omni (Free)", "fast": True},
            {"id": "nvidia/nemotron-3-ultra-550b-a55b:free", "name": "Nemotron 3 Ultra (Free)", "fast": False},
            {"id": "nvidia/nemotron-3.5-content-safety:free", "name": "Nemotron 3.5 Content Safety (Free)", "fast": False},
            {"id": "nvidia/nemotron-nano-12b-v2-vl:free", "name": "Nemotron Nano 12B VL (Free)", "fast": True},
            {"id": "nvidia/nemotron-nano-9b-v2:free", "name": "Nemotron Nano 9B V2 (Free)", "fast": True},
            {"id": "google/gemma-4-26b-a4b-it:free", "name": "Gemma 4 26B (Free)", "fast": False},
            {"id": "google/gemma-4-31b-it:free", "name": "Gemma 4 31B (Free)", "fast": False},
            {"id": "meta-llama/llama-3.2-3b-instruct:free", "name": "Llama 3.2 3B (Free)", "fast": True},
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B (Free)", "fast": False},
            {"id": "nousresearch/hermes-3-llama-3.1-405b:free", "name": "Hermes 3 405B (Free)", "fast": False},
            {"id": "openai/gpt-oss-120b:free", "name": "GPT OSS 120B (Free)", "fast": True},
            {"id": "openai/gpt-oss-20b:free", "name": "GPT OSS 20B (Free)", "fast": True},
            {"id": "poolside/laguna-xs.2:free", "name": "Laguna XS.2 (Free)", "fast": True},
            {"id": "poolside/laguna-m.1:free", "name": "Laguna M.1 (Free)", "fast": False},
            {"id": "qwen/qwen3-coder:free", "name": "Qwen3 Coder 480B (Free)", "fast": False},
            {"id": "qwen/qwen3-next-80b-a3b-instruct:free", "name": "Qwen3 Next 80B (Free)", "fast": True},
            {"id": "liquid/lfm-2.5-1.2b-thinking:free", "name": "LFM 2.5 1.2B Thinking (Free)", "fast": True},
            {"id": "liquid/lfm-2.5-1.2b-instruct:free", "name": "LFM 2.5 1.2B Instruct (Free)", "fast": True},
            {"id": "cognitivecomputations/dolphin-mistral-24b-venice-edition:free", "name": "Venice Uncensored (Free)", "fast": False},
        ],
    },
    "ollama_cloud": {
        "name": "Ollama Cloud",
        "requires_key": True,
        "env_key": "OLLAMA_API_KEY",
        "base_url": "https://ollama.com/api",
        "models": [
            # ── Hardcoded fallback models (verified June 2026) ──
            # Dynamic models are fetched from https://ollama.com/api/tags at startup
            {"id": "gpt-oss:120b", "name": "GPT OSS 120B", "fast": False},
            {"id": "gpt-oss:20b", "name": "GPT OSS 20B", "fast": True},
            {"id": "deepseek-v3.1:671b", "name": "DeepSeek V3.1 671B", "fast": False},
            {"id": "qwen3-coder:480b", "name": "Qwen3 Coder 480B", "fast": False},
            {"id": "glm-4.6", "name": "GLM 4.6", "fast": False},
            {"id": "llama3.1:405b", "name": "Llama 3.1 405B", "fast": False},
            {"id": "llama3.1:70b", "name": "Llama 3.1 70B", "fast": False},
            {"id": "llama3.1:8b", "name": "Llama 3.1 8B", "fast": True},
            {"id": "qwen3:32b", "name": "Qwen3 32B", "fast": False},
            {"id": "qwen3:8b", "name": "Qwen3 8B", "fast": True},
            {"id": "qwen2.5:72b", "name": "Qwen 2.5 72B", "fast": False},
            {"id": "mistral-large:latest", "name": "Mistral Large", "fast": False},
            {"id": "gemma2:27b", "name": "Gemma2 27B", "fast": False},
            {"id": "deepseek-r1:70b", "name": "DeepSeek R1 70B", "fast": False},
            {"id": "deepseek-r1:8b", "name": "DeepSeek R1 8B", "fast": True},
            {"id": "phi4:14b", "name": "Phi-4 14B", "fast": True},
        ],
    },
}


def _rebuild_openrouter_models() -> list[dict]:
    """Rebuild PROVIDERS["openrouter"]["models"] from paid + cached free models.

    Returns the rebuilt model list for convenience.
    """
    # Paid models are always the ones defined in the PROVIDERS dict
    # (they stay hardcoded since they change rarely)
    paid = [m for m in PROVIDERS["openrouter"]["models"] if ":free" not in m["id"]]
    # Merge with cached free models (dedup by id)
    seen_ids = {m["id"] for m in paid}
    free = []
    for m in _openrouter_free_models_cache:
        if m["id"] not in seen_ids:
            free.append(m)
            seen_ids.add(m["id"])
    PROVIDERS["openrouter"]["models"] = paid + free
    return PROVIDERS["openrouter"]["models"]


def _load_cached_free_models() -> list[dict]:
    """Load free models from the local cache file (~/.may/openrouter_free_models.json).

    Returns the cached list, or empty list if cache doesn't exist or is invalid.
    """
    if not _OPENROUTER_FREE_CACHE_FILE.exists():
        return []
    try:
        data = json.loads(_OPENROUTER_FREE_CACHE_FILE.read_text(encoding="utf-8"))
        models = data.get("models", [])
        refreshed_at = data.get("refreshed_at", 0)
        if models:
            logger.info("Loaded %d cached free OpenRouter models (from %s)", len(models),
                        time.strftime("%Y-%m-%d %H:%M", time.localtime(refreshed_at)))
        return models
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load cached free models: %s", e)
        return []


def _save_cached_free_models(models: list[dict]) -> None:
    """Persist free models to local cache file."""
    try:
        _OPENROUTER_FREE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "models": models,
            "refreshed_at": time.time(),
            "count": len(models),
        }
        _OPENROUTER_FREE_CACHE_FILE.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        logger.info("Saved %d free OpenRouter models to cache", len(models))
    except OSError as e:
        logger.warning("Failed to save free models cache: %s", e)


async def refresh_openrouter_free_models(force: bool = False) -> dict:
    """Fetch free models from OpenRouter API and update the cache.

    Three-tier fallback:
    1. Fetch live free models from OpenRouter /api/v1/models
    2. Fall back to locally cached models (~/.may/openrouter_free_models.json)
    3. Fall back to hardcoded free models in PROVIDERS

    Returns a status dict with model count and source.
    """
    global _openrouter_free_models_cache, _openrouter_free_last_refresh

    # Skip if recently refreshed AND cache is populated (unless forced)
    now = time.time()
    if not force and _openrouter_free_models_cache and (now - _openrouter_free_last_refresh) < _OPENROUTER_FREE_REFRESH_INTERVAL:
        return {
            "status": "cached",
            "free_count": len(_openrouter_free_models_cache),
            "source": "memory",
        }

    # Tier 1: Fetch from API
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get("https://openrouter.ai/api/v1/models")
            response.raise_for_status()
            data = response.json()

            api_models = data.get("data", [])
            free_models = []
            for m in api_models:
                model_id = m.get("id", "")
                # Free models have :free suffix or $0 pricing
                is_free = (
                    model_id.endswith(":free")
                    or m.get("pricing", {}).get("prompt", "1") == "0"
                    or m.get("pricing", {}).get("completion", "1") == "0"
                )
                if not is_free:
                    continue

                name = m.get("name", model_id)
                context_length = m.get("context_length", 0)
                # Heuristic: smaller context = likely smaller/faster model
                # Also check for known fast indicators in the name
                name_lower = (name + model_id).lower()
                is_fast = (
                    context_length <= 32000
                    or any(kw in name_lower for kw in ["nano", "mini", "flash", "lite"])
                )
                # Override: explicitly large models are not fast
                if any(kw in name_lower for kw in ["120b", "405b", "550b", "70b"]):
                    is_fast = False
                # Override: explicitly small models are fast
                if any(kw in name_lower for kw in ["1.2b", "2b", "3b", "9b", "12b"]):
                    is_fast = True

                free_models.append({
                    "id": model_id,
                    "name": name,
                    "fast": is_fast,
                })

            if free_models:
                _openrouter_free_models_cache = free_models
                _openrouter_free_last_refresh = now
                _save_cached_free_models(free_models)
                _rebuild_openrouter_models()
                logger.info("Refreshed %d free OpenRouter models from API", len(free_models))
                return {
                    "status": "refreshed",
                    "free_count": len(free_models),
                    "source": "api",
                }
    except Exception as e:
        logger.warning("Failed to fetch free models from API: %s", e)

    # Tier 2: Load from local cache file
    if not _openrouter_free_models_cache:
        cached = _load_cached_free_models()
        if cached:
            _openrouter_free_models_cache = cached
            _rebuild_openrouter_models()
            return {
                "status": "cached",
                "free_count": len(cached),
                "source": "file",
            }

    # Tier 3: Use hardcoded fallback (already in PROVIDERS)
    if not _openrouter_free_models_cache:
        hardcoded_free = [m for m in PROVIDERS["openrouter"]["models"] if ":free" in m["id"]]
        if hardcoded_free:
            _openrouter_free_models_cache = hardcoded_free
            _rebuild_openrouter_models()
    return {
        "status": "fallback",
        "free_count": len(_openrouter_free_models_cache),
        "source": "hardcoded",
    }


def get_free_models_status() -> dict:
    """Get the current status of the free models cache."""
    return {
        "cached_count": len(_openrouter_free_models_cache),
        "last_refresh": time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(_openrouter_free_last_refresh)
        ) if _openrouter_free_last_refresh else "never",
        "cache_file": str(_OPENROUTER_FREE_CACHE_FILE),
        "cache_exists": _OPENROUTER_FREE_CACHE_FILE.exists(),
    }


# ── Ollama Cloud Dynamic Model Fetcher ────────────────────────────────────
# Fetches available models from https://ollama.com/api/tags at startup
# so the model list is always up to date.
_ollama_cloud_models_cache: list[dict] = []
_ollama_cloud_last_refresh: float = 0.0
_OLLAMA_CLOUD_REFRESH_INTERVAL = 3600.0  # re-fetch every hour
_OLLAMA_CLOUD_CACHE_FILE = _OPENROUTER_FREE_CACHE_DIR / "ollama_cloud_models.json"


# Heuristic: classify a model as fast or slow based on name/context
# (same logic as OpenRouter free model classifier)
def _classify_cloud_model_speed(name: str, model_id: str) -> bool:
    """Heuristic fast/slow classification for cloud models."""
    name_lower = (name + model_id).lower()
    # Large models are slow
    if any(kw in name_lower for kw in ["120b", "405b", "550b", "671b", "480b", "70b"]):
        return False
    # Small models are fast
    if any(kw in name_lower for kw in ["1.2b", "2b", "3b", "8b", "9b", "12b", "14b", "20b"]):
        return True
    # Medium models: 32b+ are slow, smaller are fast
    if any(kw in name_lower for kw in ["32b", "34b", "35b", "33b"]):
        return False
    # Default: assume SLOW for unknown sizes (safer than mislabeling large models as fast)
    return False


def _save_ollama_cloud_models(models: list[dict]) -> None:
    """Persist Ollama Cloud models to local cache."""
    try:
        _OPENROUTER_FREE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "models": models,
            "refreshed_at": time.time(),
            "count": len(models),
        }
        _OLLAMA_CLOUD_CACHE_FILE.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        logger.info("Saved %d Ollama Cloud models to cache", len(models))
    except OSError as e:
        logger.warning("Failed to save Ollama Cloud models cache: %s", e)


def _load_ollama_cloud_models() -> list[dict]:
    """Load Ollama Cloud models from local cache."""
    if not _OLLAMA_CLOUD_CACHE_FILE.exists():
        return []
    try:
        data = json.loads(_OLLAMA_CLOUD_CACHE_FILE.read_text(encoding="utf-8"))
        models = data.get("models", [])
        if models:
            logger.info("Loaded %d cached Ollama Cloud models", len(models))
        return models
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load Ollama Cloud models cache: %s", e)
        return []


def _rebuild_ollama_cloud_models() -> list[dict]:
    """Rebuild PROVIDERS['ollama_cloud']['models'] from hardcoded + live models."""
    # Keep hardcoded models that aren't in the live cache
    hardcoded = PROVIDERS["ollama_cloud"]["models"]
    seen_ids = {m["id"] for m in hardcoded}
    live_added = []
    for m in _ollama_cloud_models_cache:
        if m["id"] not in seen_ids:
            live_added.append(m)
            seen_ids.add(m["id"])
    PROVIDERS["ollama_cloud"]["models"] = hardcoded + live_added
    return PROVIDERS["ollama_cloud"]["models"]


async def refresh_ollama_cloud_models(force: bool = False) -> dict:
    """Fetch available models from Ollama Cloud /api/tags.

    Three-tier fallback:
    1. Fetch live models from https://ollama.com/api/tags
    2. Fall back to local cache file
    3. Fall back to hardcoded model list

    Returns status dict.
    """
    global _ollama_cloud_models_cache, _ollama_cloud_last_refresh

    now = time.time()
    if not force and _ollama_cloud_models_cache and (now - _ollama_cloud_last_refresh) < _OLLAMA_CLOUD_REFRESH_INTERVAL:
        return {
            "status": "cached",
            "model_count": len(_ollama_cloud_models_cache),
            "source": "memory",
        }

    # Get API key
    api_key = get_api_key("ollama_cloud")
    if not api_key:
        return {
            "status": "no_key",
            "model_count": 0,
            "source": "none",
        }

    # Tier 1: Fetch from API
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://ollama.com/api/tags",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
            data = response.json()

            tags = data.get("models", [])
            live_models = []
            for tag in tags:
                raw_id = tag.get("name", "")
                if not raw_id:
                    continue
                # Strip :cloud suffix — Ollama Cloud chat API doesn't need it
                model_id = raw_id.replace(":cloud", "")
                display_name = tag.get("name", model_id).replace(":cloud", "")
                live_models.append({
                    "id": model_id,
                    "name": display_name,
                    "fast": _classify_cloud_model_speed(display_name, model_id),
                })

            if live_models:
                _ollama_cloud_models_cache = live_models
                _ollama_cloud_last_refresh = now
                _save_ollama_cloud_models(live_models)
                _rebuild_ollama_cloud_models()
                logger.info("Refreshed %d Ollama Cloud models from API", len(live_models))
                return {
                    "status": "refreshed",
                    "model_count": len(live_models),
                    "source": "api",
                }
    except Exception as e:
        logger.warning("Failed to fetch Ollama Cloud models from API: %s", e)

    # Tier 2: Load from cache
    if not _ollama_cloud_models_cache:
        cached = _load_ollama_cloud_models()
        if cached:
            _ollama_cloud_models_cache = cached
            _rebuild_ollama_cloud_models()
            return {
                "status": "cached",
                "model_count": len(cached),
                "source": "file",
            }

    # Tier 3: Use hardcoded fallback
    return {
        "status": "fallback",
        "model_count": len(PROVIDERS["ollama_cloud"]["models"]),
        "source": "hardcoded",
    }


def get_ollama_cloud_status() -> dict:
    """Get Ollama Cloud models status."""
    return {
        "cached_count": len(_ollama_cloud_models_cache),
        "last_refresh": time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(_ollama_cloud_last_refresh)
        ) if _ollama_cloud_last_refresh else "never",
        "total_models": len(PROVIDERS["ollama_cloud"]["models"]),
        "has_api_key": bool(get_api_key("ollama_cloud")),
    }


# ── Ollama Local Dynamic Model Fetcher ─────────────────────────────────
# Fetches locally installed models from http://localhost:11434/api/tags
# at startup and periodically, so the model list is always accurate.
_ollama_local_models_cache: list[dict] = []
_ollama_local_last_refresh: float = 0.0
_OLLAMA_LOCAL_REFRESH_INTERVAL = 300.0  # re-fetch every 5 minutes (local is fast)


def _classify_ollama_model_speed(model: dict) -> bool:
    """Heuristic fast/slow classification for local Ollama models.

    Uses parameter size from the API response when available,
    falls back to name-based heuristics.
    """
    # Check parameter count from API (most reliable)
    details = model.get("details", {})
    params_str = details.get("parameter_size", "")  # e.g. "3.8B", "70B"
    if params_str:
        try:
            # Extract number from strings like "3.8B", "70B", "1.2B"
            num = float(params_str.replace("B", "").replace("b", ""))
            return num <= 14.0  # <= 14B params = fast
        except (ValueError, AttributeError):
            pass
    # Fallback: name-based heuristics
    name_lower = model.get("name", "").lower()
    if any(kw in name_lower for kw in ["120b", "405b", "70b", "34b", "32b"]):
        return False
    if any(kw in name_lower for kw in ["1.2b", "2b", "3b", "4b", "8b", "9b", "12b", "14b"]):
        return True
    return False  # default slow for unknown sizes


def _rebuild_ollama_local_models() -> list[dict]:
    """Rebuild PROVIDERS['ollama']['models'] from live + hardcoded models."""
    # Hardcoded fallback models (always available)
    hardcoded = [
        {"id": "qwen3:4b", "name": "Qwen3 4B", "fast": True},
        {"id": "gemma2:2b", "name": "Gemma2 2B", "fast": True},
    ]
    if not _ollama_local_models_cache:
        PROVIDERS["ollama"]["models"] = hardcoded
        return hardcoded
    # Merge: live models take priority, add hardcoded as fallbacks
    seen_ids = {m["id"] for m in _ollama_local_models_cache}
    merged = list(_ollama_local_models_cache)
    for m in hardcoded:
        if m["id"] not in seen_ids:
            merged.append(m)
            seen_ids.add(m["id"])
    PROVIDERS["ollama"]["models"] = merged
    return merged


async def refresh_ollama_local_models(force: bool = False) -> dict:
    """Fetch locally installed Ollama models from both dual ports.

    Queries port 11434 (router) and port 11435 (main) to discover
    models from both Ollama instances.

    Two-tier fallback:
    1. Fetch live models from both local Ollama APIs
    2. Fall back to hardcoded model list

    Returns status dict.
    """
    global _ollama_local_models_cache, _ollama_local_last_refresh

    now = time.time()
    if not force and _ollama_local_models_cache and (now - _ollama_local_last_refresh) < _OLLAMA_LOCAL_REFRESH_INTERVAL:
        return {
            "status": "cached",
            "model_count": len(_ollama_local_models_cache),
            "source": "memory",
        }

    # Tier 1: Fetch from both local Ollama ports
    live_models = []
    for port in (11434, 11435):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"http://localhost:{port}/api/tags")
                response.raise_for_status()
                data = response.json()

                tags = data.get("models", [])
                for tag in tags:
                    model_name = tag.get("name", "")
                    if not model_name:
                        continue
                    # Mark which port this model lives on
                    live_models.append({
                        "id": model_name,
                        "name": model_name,
                        "fast": _classify_ollama_model_speed(tag),
                        "port": port,
                    })
        except Exception as e:
            logger.debug("Failed to fetch models from port %d: %s", port, e)

    if live_models:
        _ollama_local_models_cache = live_models
        _ollama_local_last_refresh = now
        _rebuild_ollama_local_models()
        logger.info("Refreshed %d local Ollama models from dual ports (11434+11435)", len(live_models))
        return {
            "status": "refreshed",
            "model_count": len(live_models),
            "source": "api",
        }

    # Tier 2: Use hardcoded fallback
    _rebuild_ollama_local_models()
    return {
        "status": "fallback",
        "model_count": len(PROVIDERS["ollama"]["models"]),
        "source": "hardcoded",
    }


def get_ollama_local_status() -> dict:
    """Get Ollama local models status (dual-port aware)."""
    router_models = [m for m in _ollama_local_models_cache if m.get('port') == 11434]
    main_models = [m for m in _ollama_local_models_cache if m.get('port') == 11435]
    return {
        "cached_count": len(_ollama_local_models_cache),
        "last_refresh": time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(_ollama_local_last_refresh)
        ) if _ollama_local_last_refresh else "never",
        "total_models": len(PROVIDERS["ollama"]["models"]),
        "dual_port": True,
        "router_port": 11434,
        "main_port": 11435,
        "router_model_count": len(router_models),
        "main_model_count": len(main_models),
    }


def get_provider_for_model(model_id: str) -> str | None:
    """Determine which provider owns a given model ID."""
    for provider_id, provider in PROVIDERS.items():
        for m in provider["models"]:
            if m["id"] == model_id:
                return provider_id
    return None


# ── API Key Store (DPAPI-encrypted with plaintext fallback) ─────────────────
# P2 SECURITY: Keys are now encrypted at rest via Windows DPAPI.
# Falls back to base64 on non-Windows. Migrates from legacy .api_keys.json.

import os

try:
    from system.secure_storage import (
        store_api_key as _secure_store,
        retrieve_api_key as _secure_retrieve,
        delete_api_key as _secure_delete,
        get_key_status as _secure_status,
    )
    _SECURE_STORAGE_AVAILABLE = True
except ImportError:
    _SECURE_STORAGE_AVAILABLE = False
    logger.warning("Secure storage not available — using legacy plaintext key store")

# Legacy plaintext store (used as fallback)
_KEYS_FILE = os.path.join(os.path.dirname(__file__), "..", ".api_keys.json")


def _load_keys() -> dict[str, str]:
    """Load API keys from legacy plaintext store."""
    if os.path.exists(_KEYS_FILE):
        try:
            with open(_KEYS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_keys(keys: dict[str, str]) -> None:
    """Persist API keys to legacy plaintext store."""
    with open(_KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)


def get_api_key(provider: str) -> str | None:
    """Get API key for a provider. Checks secure store first, then env var."""
    # P2 SECURITY: Try DPAPI-encrypted store first
    if _SECURE_STORAGE_AVAILABLE:
        key = _secure_retrieve(provider)
        if key:
            return key
    # Fallback to legacy plaintext store
    keys = _load_keys()
    if provider in keys and keys[provider]:
        return keys[provider]
    # Fallback to environment variable
    provider_info = PROVIDERS.get(provider, {})
    env_key = provider_info.get("env_key")
    if env_key:
        return os.environ.get(env_key)
    return None


def set_api_key(provider: str, key: str) -> None:
    """Store an API key for a provider. Uses DPAPI encryption when available."""
    if _SECURE_STORAGE_AVAILABLE:
        _secure_store(provider, key)
    else:
        # Legacy fallback
        keys = _load_keys()
        keys[provider] = key
        _save_keys(keys)


def delete_api_key(provider: str) -> None:
    """Remove an API key for a provider."""
    if _SECURE_STORAGE_AVAILABLE:
        _secure_delete(provider)
    # Also remove from legacy store
    keys = _load_keys()
    if provider in keys:
        keys.pop(provider, None)
        _save_keys(keys)


def get_all_key_status() -> dict[str, bool]:
    """Return which providers have keys configured."""
    # P2 SECURITY: Check secure store first
    if _SECURE_STORAGE_AVAILABLE:
        status = _secure_status()
        stored = set(status.get("stored_providers", []))
    else:
        stored = set(_load_keys().keys())

    result = {}
    for provider_id, provider_info in PROVIDERS.items():
        if provider_info["requires_key"]:
            has_key = provider_id in stored or bool(
                os.environ.get(provider_info.get("env_key", ""))
            )
            result[provider_id] = has_key
        else:
            result[provider_id] = True  # Ollama doesn't need a key
    return result


# ── Streaming implementations ───────────────────────────────────────────────


async def _stream_ollama(
    messages: list[dict],
    model: str,
    system_prompt: str | None,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """Stream from Ollama local API."""
    payload_messages = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    payload_messages.extend(messages)

    payload = {
        "model": model,
        "messages": payload_messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "num_ctx": 131072,
            "num_predict": max_tokens,
            "num_gpu": 999,  # Force all layers to GPU
        },
    }

    from llm.ollama_client import strip_think_tags, get_ollama_url

    # Route to correct Ollama port based on model
    ollama_url = get_ollama_url(model)
    client = await get_ollama_client()
    async with client.stream(
        "POST", f"{ollama_url}/api/chat", json=payload
    ) as response:
        response.raise_for_status()
        _full = ""
        _last_yielded = 0
        async for line in response.aiter_lines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get("thinking"):
                    continue
                if "message" in data and "content" in data["message"]:
                    _full += data["message"]["content"]
                    clean = strip_think_tags(_full)
                    new = clean[_last_yielded:]
                    if new:
                        yield new
                        _last_yielded = len(clean)
            except json.JSONDecodeError:
                continue


async def _stream_openai(
    messages: list[dict],
    model: str,
    system_prompt: str | None,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """Stream from OpenAI-compatible API (also used for OpenRouter)."""
    payload_messages = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    payload_messages.extend(messages)

    payload = {
        "model": model,
        "messages": payload_messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0)
    ) as client:
        async with client.stream(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue


async def _stream_anthropic(
    messages: list[dict],
    model: str,
    system_prompt: str | None,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """Stream from Anthropic Claude API."""
    payload_messages = []
    for msg in messages:
        payload_messages.append({"role": msg["role"], "content": msg["content"]})

    payload: dict = {
        "model": model,
        "messages": payload_messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if system_prompt:
        payload["system"] = system_prompt

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0)
    ) as client:
        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                try:
                    data = json.loads(data_str)
                    if data.get("type") == "content_block_delta":
                        delta = data.get("delta", {})
                        text = delta.get("text")
                        if text:
                            yield text
                except json.JSONDecodeError:
                    continue


def _tools_to_gemini_format(tools: list[dict]) -> list[dict]:
    """Convert our tool schemas to Gemini function calling format.

    Gemini uses function_declarations (snake_case) inside a tools array,
    with UPPERCASE type names (STRING, OBJECT, etc.).
    """
    _TYPE_MAP = {
        "string": "STRING",
        "number": "NUMBER",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
        "object": "OBJECT",
        "array": "ARRAY",
    }
    declarations = []
    for t in tools:
        decl: dict = {
            "name": t["name"],
            "description": t.get("description", ""),
        }
        params = t.get("parameters", {})
        if params and isinstance(params, dict):
            gemini_params: dict = {"type": "OBJECT", "properties": {}}
            for param_name, param_info in params.items():
                if param_name == "type":
                    continue  # skip the top-level "type": "object"
                if param_name == "required":
                    gemini_params["required"] = param_info
                    continue
                if not isinstance(param_info, dict):
                    continue
                prop: dict = {
                    "type": _TYPE_MAP.get(
                        param_info.get("type", "string").lower(), "STRING"
                    ),
                }
                if param_info.get("description"):
                    prop["description"] = param_info["description"]
                if param_info.get("enum"):
                    prop["enum"] = param_info["enum"]
                gemini_params["properties"][param_name] = prop
            decl["parameters"] = gemini_params
        declarations.append(decl)
    return [{"function_declarations": declarations}]


async def _stream_gemini(
    messages: list[dict],
    model: str,
    system_prompt: str | None,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """Stream from Google Gemini API (text-only, no tools)."""
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    payload: dict = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":streamGenerateContent?key={api_key}&alt=sse"
    )

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0)
    ) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                try:
                    data = json.loads(data_str)
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            text = part.get("text")
                            if text:
                                yield text
                except json.JSONDecodeError:
                    continue


async def _stream_gemini_with_tools(
    messages: list[dict],
    model: str,
    system_prompt: str | None,
    api_key: str,
    tools: list[dict] | None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> AsyncGenerator[dict, None]:
    """Stream from Google Gemini API with native function calling.

    If the API returns 400 (model doesn't support tools), retries without
    tools and injects tool definitions into the system prompt instead.
    """
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    payload: dict = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    # Add native tool format
    if tools:
        payload["tools"] = _tools_to_gemini_format(tools)

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":streamGenerateContent?key={api_key}&alt=sse"
    )

    try:
        async for event in _do_gemini_stream(url, payload, tools is not None):
            yield event
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400 and tools:
            # Model doesn't support native tools -- retry with tools in prompt
            logger.info(
                "Model '%s' doesn't support native Gemini tools, "
                "falling back to prompt-based tools",
                model,
            )
            fallback_system = _tools_as_prompt_text(tools, system_prompt)
            payload["systemInstruction"] = {"parts": [{"text": fallback_system}]}
            payload.pop("tools", None)
            async for event in _do_gemini_stream(url, payload, False):
                yield event
        else:
            raise


async def _do_gemini_stream(
    url: str,
    payload: dict,
    has_native_tools: bool,
) -> AsyncGenerator[dict, None]:
    """Execute a single Gemini streaming request, yielding text and tool_call events."""
    collected_tool_calls: list[dict] = []

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0)
    ) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                try:
                    data = json.loads(data_str)
                    candidates = data.get("candidates", [])
                    if not candidates:
                        continue
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        # Handle text content
                        text = part.get("text")
                        if text:
                            yield {"type": "text", "content": text}

                        # Handle native function calls
                        if has_native_tools and "functionCall" in part:
                            fc = part["functionCall"]
                            collected_tool_calls.append({
                                "id": f"gemini_call_{len(collected_tool_calls)}",
                                "name": fc.get("name", ""),
                                "args": fc.get("args", {}),
                            })
                except json.JSONDecodeError:
                    continue

            # Emit collected tool calls at the end
            if collected_tool_calls:
                yield {"type": "tool_calls", "tool_calls": collected_tool_calls}


async def _stream_openai_compatible(
    messages: list[dict],
    model: str,
    system_prompt: str | None,
    api_key: str,
    base_url: str,
    temperature: float = 0.7,
    max_tokens: int = 512,
    extra_headers: dict | None = None,
) -> AsyncGenerator[str, None]:
    """Stream from any OpenAI-compatible API (OpenRouter, OpenCode, etc.)."""
    payload_messages = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    payload_messages.extend(messages)

    payload = {
        "model": model,
        "messages": payload_messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    url = f"{base_url}/chat/completions"

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0)
    ) as client:
        async with client.stream(
            "POST", url, json=payload, headers=headers,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue


async def _stream_openrouter(
    messages: list[dict],
    model: str,
    system_prompt: str | None,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """Stream from OpenRouter."""
    async for chunk in _stream_openai_compatible(
        messages, model, system_prompt, api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=temperature, max_tokens=max_tokens,
        extra_headers={
            "HTTP-Referer": "https://may-ai.local",
            "X-Title": "May AI Companion",
        },
    ):
        yield chunk


# ── Unified streaming entry point ───────────────────────────────────────────

# Ollama Cloud reuses the Ollama local streaming function since the API is compatible
# (Ollama Cloud is accessed via ollama.com/api with an API key)
async def _stream_ollama_cloud(
    messages: list[dict],
    model: str,
    system_prompt: str | None,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """Stream from Ollama Cloud API (Ollama-native format)."""
    payload_messages = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    payload_messages.extend(messages)

    # NOTE: Ollama Cloud may not support local-only options like 'think',
    # 'num_ctx', 'num_predict', 'top_p'. Only send temperature.
    payload = {
        "model": model,
        "messages": payload_messages,
        "stream": True,
        "options": {
            "temperature": temperature,
        },
    }

    from llm.ollama_client import strip_think_tags

    client = await get_external_client()
    async with client.stream(
        "POST",
        "https://ollama.com/api/chat",
        json=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    ) as response:
        response.raise_for_status()
        _full = ""
        _last_yielded = 0
        async for line in response.aiter_lines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get("thinking"):
                    continue
                if "message" in data and "content" in data["message"]:
                    _full += data["message"]["content"]
                    clean = strip_think_tags(_full)
                    new = clean[_last_yielded:]
                    if new:
                        yield new
                        _last_yielded = len(clean)
            except json.JSONDecodeError:
                continue


_STREAM_MAP = {
    "ollama": _stream_ollama,
    "openai": _stream_openai,
    "anthropic": _stream_anthropic,
    "gemini": _stream_gemini,
    "google_ai_studio": _stream_gemini,  # Same API as Gemini — key from aistudio.google.com
    "openrouter": _stream_openrouter,
    "ollama_cloud": _stream_ollama_cloud,
}


async def stream_chat_multi(
    provider: str,
    model: str,
    messages: list[dict],
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """Unified streaming entry point. Routes to the correct provider.

    Args:
        provider: One of 'ollama', 'openai', 'anthropic', 'gemini', 'google_ai_studio', 'openrouter'.
        model: Model ID (e.g. 'gpt-4o', 'claude-sonnet-4-20250514').
        messages: List of {'role': 'user'|'assistant', 'content': str}.
        system_prompt: Optional system prompt.
        temperature: Sampling temperature.
        max_tokens: Max tokens to generate.
    """
    if provider not in _STREAM_MAP:
        raise ValueError(f"Unknown provider: {provider}")

    api_key = get_api_key(provider)
    if PROVIDERS[provider]["requires_key"] and not api_key:
        raise ValueError(
            f"No API key configured for {PROVIDERS[provider]['name']}. "
            f"Add one in Settings."
        )

    stream_fn = _STREAM_MAP[provider]

    if provider == "ollama":
        async for chunk in stream_fn(messages, model, system_prompt, temperature, max_tokens):
            yield chunk
    else:
        async for chunk in stream_fn(messages, model, system_prompt, api_key, temperature, max_tokens):
            yield chunk


# ── Tool-aware streaming (for Jarvis brain) ────────────────────────────────


async def stream_chat_with_tools(
    provider: str,
    model: str,
    messages: list[dict],
    system_prompt: str | None = None,
    tools: list[dict] | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    _is_fallback: bool = False,
) -> AsyncGenerator[dict, None]:
    """Stream chat with optional tool support + retry + fallback.

    Yields events: {"type": "text", "content": str} or {"type": "tool_calls", "tool_calls": list}.

    P0: Retries on transient errors (connection, timeout, 429, 5xx).
        CRITICAL: Buffers events during retry — only yields on success or final attempt.
        This prevents duplicate content when a retry succeeds after partial yield.
    P1: Falls back to alternative provider if primary fails after retries.
    """
    from llm.resilience import is_retryable_error, is_rate_limit_error, _retry_delay

    MAX_STREAM_RETRIES = 2
    last_exc = None

    for attempt in range(MAX_STREAM_RETRIES + 1):
        # Buffer events during retry — only yield on success or final attempt
        buffered_events: list[dict] = []
        try:
            if provider == "ollama":
                async for event in _stream_ollama_with_tools(messages, model, system_prompt, tools, temperature, max_tokens):
                    if attempt < MAX_STREAM_RETRIES:
                        buffered_events.append(event)  # buffer for potential retry
                    else:
                        yield event  # final attempt — yield directly
                # Success — yield all buffered events
                for event in buffered_events:
                    yield event
                return
            elif provider in ("openai", "openrouter"):
                api_key = get_api_key(provider)
                if PROVIDERS[provider]["requires_key"] and not api_key:
                    raise ValueError(f"No API key configured for {PROVIDERS[provider]['name']}.")
                base_url = PROVIDERS[provider]["base_url"]
                async for event in _stream_openai_with_tools(messages, model, system_prompt, api_key, base_url, tools, temperature, max_tokens):
                    if attempt < MAX_STREAM_RETRIES:
                        buffered_events.append(event)  # buffer for potential retry
                    else:
                        yield event  # final attempt — yield directly
                # Success — yield all buffered events
                for event in buffered_events:
                    yield event
                return
            elif provider in ("gemini", "google_ai_studio"):
                api_key = get_api_key(provider)
                if PROVIDERS[provider]["requires_key"] and not api_key:
                    raise ValueError(f"No API key configured for {PROVIDERS[provider]['name']}.")
                async for event in _stream_gemini_with_tools(
                    messages, model, system_prompt, api_key, tools, temperature, max_tokens,
                ):
                    if attempt < MAX_STREAM_RETRIES:
                        buffered_events.append(event)
                    else:
                        yield event
                for event in buffered_events:
                    yield event
                return
            else:
                # For Anthropic -- fall back to text-only (tools injected as prompt)
                async for chunk in stream_chat_multi(provider, model, messages, system_prompt, temperature, max_tokens):
                    event = {"type": "text", "content": chunk}
                    if attempt < MAX_STREAM_RETRIES:
                        buffered_events.append(event)
                    else:
                        yield event
                for event in buffered_events:
                    yield event
                return
        except Exception as e:
            last_exc = e
            if attempt < MAX_STREAM_RETRIES and is_retryable_error(e):
                rate_limited = is_rate_limit_error(e)
                delay = _retry_delay(attempt, rate_limited=rate_limited)
                logger.warning("Stream retry %d/%d for %s/%s after %.1fs (rate_limited=%s): %s",
                               attempt + 1, MAX_STREAM_RETRIES, provider, model, delay, rate_limited, str(e)[:100])
                await asyncio.sleep(delay)
            else:
                break

    # P1: Provider fallback — try an alternative provider before giving up
    if not _is_fallback:
        from llm.resilience import get_fallback_chain
        chain = get_fallback_chain(provider)
        for fb in chain:
            fb_provider = fb["provider"]
            fb_model = fb["model"]
            fb_api_key = get_api_key(fb_provider)
            # Skip fallback providers that don't have a required key
            if PROVIDERS.get(fb_provider, {}).get("requires_key") and not fb_api_key:
                logger.info("Skipping fallback %s (no API key)", fb["label"])
                continue
            logger.info("Falling back to %s (%s)", fb["label"], fb_model)
            try:
                async for event in stream_chat_with_tools(
                    provider=fb_provider, model=fb_model, messages=messages,
                    system_prompt=system_prompt, tools=tools, temperature=temperature,
                    max_tokens=max_tokens, _is_fallback=True,
                ):
                    yield event
                return
            except Exception as fb_exc:
                logger.warning("Fallback %s also failed: %s", fb["label"], fb_exc)
                continue

    raise last_exc


async def _stream_ollama_with_tools(
    messages: list[dict],
    model: str,
    system_prompt: str | None,
    tools: list[dict] | None,
    temperature: float,
    max_tokens: int,
) -> AsyncGenerator[dict, None]:
    """Stream from Ollama with native tool support."""
    from llm.ollama_client import strip_think_tags

    payload_messages = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    payload_messages.extend(messages)

    # Read num_ctx from auto-tuner instead of hardcoding 131072.
    # Small models (phi4-mini etc.) have ~8K effective context — 128K is harmful.
    from intelligence.tuner_cache import get_gene
    num_ctx = int(get_gene("num_ctx", default=6144))

    # Cap num_ctx for small local models to avoid OOM / HTTP 500
    _small_model_markers = ("phi4", "tiny", "mini", "3b", "1b", "qwen3:4b")
    if any(m in model.lower() for m in _small_model_markers):
        num_ctx = min(num_ctx, 8192)

    payload = {
        "model": model,
        "messages": payload_messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "num_ctx": num_ctx,
            "num_predict": max_tokens,
            "num_gpu": 999,  # Force all layers to GPU
        },
    }

    # Ollama supports tools since version 0.4.0
    if tools:
        # Convert tools to Ollama format (OpenAI-compatible)
        payload["tools"] = tools

    # Route to correct Ollama port based on model
    from llm.ollama_client import get_ollama_url
    ollama_url = get_ollama_url(model)
    client = await get_ollama_client()

    async def _stream_payload(pld: dict) -> AsyncGenerator[dict, None]:
        """Inner helper: stream a single payload and yield events."""
        async with client.stream(
            "POST", f"{ollama_url}/api/chat", json=pld
        ) as resp:
            resp.raise_for_status()
            _full = ""
            _last_yielded = 0
            collected_tool_calls: list[dict] = []
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("thinking"):
                        continue
                    msg = data.get("message", {})
                    if "tool_calls" in msg:
                        for tc in msg["tool_calls"]:
                            func = tc.get("function", {})
                            collected_tool_calls.append({
                                "id": tc.get("id", f"call_{len(collected_tool_calls)}"),
                                "name": func.get("name", ""),
                                "args": _parse_tool_args(func.get("arguments", "")),
                            })
                    if "content" in msg and msg["content"]:
                        _full += msg["content"]
                        clean = strip_think_tags(_full)
                        new = clean[_last_yielded:]
                        if new:
                            yield {"type": "text", "content": new}
                            _last_yielded = len(clean)
                    if data.get("done"):
                        if collected_tool_calls:
                            yield {"type": "tool_calls", "tool_calls": collected_tool_calls}
                except json.JSONDecodeError:
                    continue

    # Try with tools first; on HTTP 500 strip tools, inject them as text,
    # and retry — the model still needs to know what tools are available.
    try:
        async for event in _stream_payload(payload):
            yield event
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 500 and tools:
            logger.warning(
                "Ollama HTTP 500 with %d tools for %s — retrying with tools in prompt",
                len(tools), model,
            )
            payload.pop("tools", None)
            # Inject tool definitions into system prompt so model still knows about them
            fallback_system = _tools_as_prompt_text(tools, system_prompt)
            # Rebuild messages with updated system prompt
            payload["messages"] = [{"role": "system", "content": fallback_system}] + messages
            async for event in _stream_payload(payload):
                yield event
        else:
            raise


def _tools_to_openai_format(tools: list[dict]) -> list[dict]:
    """Convert our tool schemas to OpenAI function calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t.get("parameters", {}),
            }
        }
        for t in tools
    ]


def _tools_as_prompt_text(tools: list[dict], system_prompt: str | None) -> str:
    """Inject tool definitions into the system prompt as text for models that don't support native tools."""
    tool_text = "\n\n## Available Tools\nYou have access to the following tools. To use a tool, respond with a JSON block like:\n```json\n{\"tool\": \"tool_name\", \"args\": {\"param\": \"value\"}}\n```\nMultiple tools can be called by listing multiple JSON blocks.\n\n"
    for t in tools:
        params = t.get("parameters", {})
        param_str = ", ".join(f"{k}: {v.get('type', 'string')}" for k, v in params.items()) if params else "none"
        tool_text += f"- **{t['name']}**: {t['description']} (params: {param_str})\n"
    tool_text += "\nRespond with tool calls as JSON when the user asks you to do something on the PC."

    if system_prompt:
        return system_prompt + tool_text
    return tool_text


async def _stream_openai_with_tools(
    messages: list[dict],
    model: str,
    system_prompt: str | None,
    api_key: str,
    base_url: str,
    tools: list[dict] | None,
    temperature: float,
    max_tokens: int,
) -> AsyncGenerator[dict, None]:
    """Stream from OpenAI-compatible API with native tool support.

    If the API returns 400 (model doesn't support tools), retries without tools
    and injects tool definitions into the system prompt instead.
    """
    payload_messages = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    payload_messages.extend(messages)

    payload = {
        "model": model,
        "messages": payload_messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Add native tool format
    if tools:
        payload["tools"] = _tools_to_openai_format(tools)

    # Determine the correct URL
    if "openrouter" in base_url:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://may-ai.local",
            "X-Title": "May AI Companion",
        }
    else:
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    try:
        async for event in _do_openai_stream(url, payload, headers, tools is not None):
            yield event
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400 and tools:
            # Model doesn't support native tools — retry with tools in prompt
            logger.info(f"Model '{model}' doesn't support native tools, falling back to prompt-based tools")
            fallback_messages = []
            fallback_system = _tools_as_prompt_text(tools, system_prompt)
            fallback_messages.append({"role": "system", "content": fallback_system})
            fallback_messages.extend(messages)
            payload["messages"] = fallback_messages
            payload.pop("tools", None)
            async for event in _do_openai_stream(url, payload, headers, False):
                yield event
        else:
            raise


async def _do_openai_stream(
    url: str,
    payload: dict,
    headers: dict,
    has_native_tools: bool,
) -> AsyncGenerator[dict, None]:
    """Execute a single OpenAI-compatible streaming request."""
    collected_tool_calls = {}  # idx -> {name, arguments}

    client = await get_external_client()
    async with client.stream("POST", url, json=payload, headers=headers) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                data = json.loads(data_str)
                choices = data.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})

                # Handle text content
                content = delta.get("content")
                if content:
                    yield {"type": "text", "content": content}

                # Handle native tool calls (streamed incrementally)
                if has_native_tools:
                    tool_calls_delta = delta.get("tool_calls", [])
                    for tc_delta in tool_calls_delta:
                        idx = tc_delta.get("index", 0)
                        if idx not in collected_tool_calls:
                            collected_tool_calls[idx] = {
                                "id": tc_delta.get("id", f"call_{idx}"),
                                "name": "",
                                "arguments": "",
                            }
                        func = tc_delta.get("function", {})
                        if func.get("name"):
                            collected_tool_calls[idx]["name"] = func["name"]
                        if func.get("arguments"):
                            collected_tool_calls[idx]["arguments"] += func["arguments"]

            except json.JSONDecodeError:
                continue

        # Emit collected native tool calls
        if collected_tool_calls:
            tool_calls_list = []
            for idx in sorted(collected_tool_calls.keys()):
                tc = collected_tool_calls[idx]
                tool_calls_list.append({
                    "id": tc["id"],
                    "name": tc["name"],
                    "args": _parse_tool_args(tc["arguments"]),
                })
            yield {"type": "tool_calls", "tool_calls": tool_calls_list}


def _parse_tool_args(args) -> dict:
    """Parse tool arguments from JSON string or dict."""
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            return json.loads(args)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}
