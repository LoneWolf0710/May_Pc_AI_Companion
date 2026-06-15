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
from typing import AsyncGenerator

logger = logging.getLogger("may.llm.providers")

# ── Provider definitions ────────────────────────────────────────────────────

PROVIDERS = {
    "ollama": {
        "name": "Ollama (Local)",
        "requires_key": False,
        "base_url": "http://localhost:11434",
        "models": [
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
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "fast": True},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "fast": False},
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
            # Other
            {"id": "databricks/dbrx-instruct", "name": "DBRX Instruct", "fast": False},
            {"id": "nousresearch/hermes-3-llama-3.1-405b", "name": "Hermes 3 405B", "fast": False},
            {"id": "nousresearch/hermes-3-llama-3.1-70b", "name": "Hermes 3 70B", "fast": False},
            {"id": "microsoft/phi-3.5-moe-instruct", "name": "Phi-3.5 MoE", "fast": True},
            {"id": "microsoft/phi-4", "name": "Phi-4", "fast": True},
        ],
    },
    "ollama_cloud": {
        "name": "Ollama Cloud",
        "requires_key": True,
        "env_key": "OLLAMA_API_KEY",
        "base_url": "https://ollama.com/api",
        "models": [
            # Popular models available on Ollama Cloud
            {"id": "llama3.1:405b", "name": "Llama 3.1 405B", "fast": False},
            {"id": "llama3.1:70b", "name": "Llama 3.1 70B", "fast": False},
            {"id": "llama3.1:8b", "name": "Llama 3.1 8B", "fast": True},
            {"id": "llama3:70b", "name": "Llama 3 70B", "fast": False},
            {"id": "llama3:8b", "name": "Llama 3 8B", "fast": True},
            {"id": "qwen3:32b", "name": "Qwen3 32B", "fast": False},
            {"id": "qwen3:8b", "name": "Qwen3 8B", "fast": True},
            {"id": "qwen3:4b", "name": "Qwen3 4B", "fast": True},
            {"id": "qwen2.5:72b", "name": "Qwen 2.5 72B", "fast": False},
            {"id": "qwen2.5:32b", "name": "Qwen 2.5 32B", "fast": False},
            {"id": "qwen2.5:7b", "name": "Qwen 2.5 7B", "fast": True},
            {"id": "gemma2:27b", "name": "Gemma2 27B", "fast": False},
            {"id": "gemma2:9b", "name": "Gemma2 9B", "fast": True},
            {"id": "gemma2:2b", "name": "Gemma2 2B", "fast": True},
            {"id": "mistral-large:latest", "name": "Mistral Large", "fast": False},
            {"id": "mixtral:8x22b", "name": "Mixtral 8x22B", "fast": False},
            {"id": "mixtral:8x7b", "name": "Mixtral 8x7B", "fast": True},
            {"id": "command-r:35b", "name": "Command R 35B", "fast": False},
            {"id": "deepseek-r1:70b", "name": "DeepSeek R1 70B", "fast": False},
            {"id": "deepseek-r1:32b", "name": "DeepSeek R1 32B", "fast": False},
            {"id": "deepseek-r1:8b", "name": "DeepSeek R1 8B", "fast": True},
            {"id": "phi4:14b", "name": "Phi-4 14B", "fast": True},
            {"id": "phi3:14b", "name": "Phi-3 14B", "fast": True},
            {"id": "nous-hermes2:10.7b", "name": "Nous Hermes 2 10.7B", "fast": True},
            {"id": "codellama:34b", "name": "CodeLlama 34B", "fast": False},
            {"id": "codellama:13b", "name": "CodeLlama 13B", "fast": True},
            {"id": "vicuna:33b", "name": "Vicuna 33B", "fast": False},
            {"id": "orca2:13b", "name": "Orca 2 13B", "fast": True},
            {"id": "solar:10.7b", "name": "Solar 10.7B", "fast": True},
            {"id": "dolphin-mixtral:8x7b", "name": "Dolphin Mixtral 8x7B", "fast": True},
            {"id": "openhermes:13b", "name": "OpenHermes 13B", "fast": True},
        ],
    },
}


async def fetch_openrouter_models() -> list[dict]:
    """Fetch available models from OpenRouter's /models API.

    Merges with hardcoded list — API models are added under an 'OpenRouter Live' section.
    Falls back to hardcoded list if the API call fails.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://openrouter.ai/api/v1/models")
            response.raise_for_status()
            data = response.json()

            api_models = data.get("data", [])
            live_models = []
            for m in api_models:
                model_id = m.get("id", "")
                name = m.get("name", model_id)
                # Estimate fast/slow by context length — smaller models tend to be faster
                context_length = m.get("context_length", 0)
                is_fast = context_length <= 32000
                live_models.append({
                    "id": model_id,
                    "name": name,
                    "fast": is_fast,
                })

            return live_models
    except Exception as e:
        logger.warning(f"Failed to fetch OpenRouter models: {e}")
        return []


def get_provider_for_model(model_id: str) -> str | None:
    """Determine which provider owns a given model ID."""
    for provider_id, provider in PROVIDERS.items():
        for m in provider["models"]:
            if m["id"] == model_id:
                return provider_id
    return None


# ── API Key Store (file-backed JSON) ────────────────────────────────────────

import os

_KEYS_FILE = os.path.join(os.path.dirname(__file__), "..", ".api_keys.json")


def _load_keys() -> dict[str, str]:
    """Load API keys from disk."""
    if os.path.exists(_KEYS_FILE):
        try:
            with open(_KEYS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_keys(keys: dict[str, str]) -> None:
    """Persist API keys to disk."""
    with open(_KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)


def get_api_key(provider: str) -> str | None:
    """Get API key for a provider. Checks file store first, then env var."""
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
    """Store an API key for a provider."""
    keys = _load_keys()
    keys[provider] = key
    _save_keys(keys)


def delete_api_key(provider: str) -> None:
    """Remove an API key for a provider."""
    keys = _load_keys()
    keys.pop(provider, None)
    _save_keys(keys)


def get_all_key_status() -> dict[str, bool]:
    """Return which providers have keys configured."""
    keys = _load_keys()
    result = {}
    for provider_id, provider_info in PROVIDERS.items():
        if provider_info["requires_key"]:
            has_key = bool(keys.get(provider_id)) or bool(
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
            "num_ctx": 4096,
            "num_predict": max_tokens,
            "think": False,
        },
    }

    from llm.ollama_client import strip_think_tags

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0)
    ) as client:
        async with client.stream(
            "POST", "http://localhost:11434/api/chat", json=payload
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
                    delta = data.get("choices", [{}])[0].get("delta", {})
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


async def _stream_gemini(
    messages: list[dict],
    model: str,
    system_prompt: str | None,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """Stream from Google Gemini API."""
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


async def _stream_openrouter(
    messages: list[dict],
    model: str,
    system_prompt: str | None,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """Stream from OpenRouter (OpenAI-compatible endpoint)."""
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
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://may-ai.local",
                "X-Title": "May AI Companion",
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
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue


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

    payload = {
        "model": model,
        "messages": payload_messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "think": False,
        },
    }

    from llm.ollama_client import strip_think_tags

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0)
    ) as client:
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
        provider: One of 'ollama', 'openai', 'anthropic', 'gemini', 'openrouter'.
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
