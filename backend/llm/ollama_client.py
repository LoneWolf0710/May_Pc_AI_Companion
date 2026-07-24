"""Ollama LLM client for streaming chat responses.

Supports:
- Streaming chat with qwen3:4b (with thinking disabled)
- Model routing: simple queries → fast model, complex → main model
- Health checks and model availability detection
- Mock/dev mode when Ollama has no models available
"""

import httpx
import json
import random
import asyncio
import logging
import re
from typing import AsyncGenerator

logger = logging.getLogger("may.llm")

# ── Single Ollama Instance ─────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434"

# Model configuration
# Using qwen3:0.6b on single Ollama instance (port 11434)
# Thinking is disabled via the 'think' option in the API payload + 回答 tag filter
PRIMARY_MODEL = "qwen3:0.6b"      # Main model (port 11434)
FAST_MODEL = "qwen3:0.6b"              # Router model (same)
ROUTER_MODEL = "qwen3:0.6b"            # Explicit router model name


# ── Single-port routing ─────────────────────────────────────────────────
def get_ollama_url(model: str | None = None) -> str:
    """Route to the single Ollama instance (port 11434)."""
    return OLLAMA_URL

# ── Mock/dev mode: simulated responses when Ollama has no models ──────────
_MOCK_RESPONSES = [
    "Hey~ I'm May! Ollama is running but no models are loaded yet. Download one with `ollama pull phi4-mini:3.8b` and I'll be back to normal~",
    "I'm in dev mode right now~ No models available in Ollama. Once you pull a model, I'll have real answers for you!",
    "Hmm, it looks like Ollama doesn't have any models downloaded. Try `ollama pull phi4-mini:3.8b` to get me working properly~",
    "Just a heads up — I'm running in mock mode because Ollama has no models. I can still help with system commands though!",
    "I'm here~ but my brain (LLM) isn't loaded yet. Pull a model with Ollama and I'll be good to go!",
]

# Simulated streaming tokens for mock mode (word-by-word)
MOCK_DELAY_PER_WORD = 0.03  # seconds between words for realistic feel


async def get_available_models() -> list[str]:
    """Get list of available Ollama models from both dual ports."""
    models = []
    for port in (11434, 11435):
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"http://localhost:{port}/api/tags")
                response.raise_for_status()
                port_models = response.json().get("models", [])
                models.extend([m.get("name", "").split(":")[0] for m in port_models])
            except (httpx.HTTPError, ConnectionError):
                continue
    return models


async def is_ollama_running() -> bool:
    """Check if at least one Ollama instance is reachable (router or main)."""
    for port in (11434, 11435):
        async with httpx.AsyncClient(timeout=3.0) as client:
            try:
                response = await client.get(f"http://localhost:{port}/api/tags")
                if response.status_code == 200:
                    return True
            except (httpx.HTTPError, ConnectionError):
                continue
    return False


async def has_available_models() -> bool:
    """Check if Ollama has at least one model downloaded."""
    models = await get_available_models()
    return len(models) > 0


async def mock_stream_chat(message: str) -> AsyncGenerator[str, None]:
    """Generate a mock streaming response when Ollama has no models.

    Simulates token-by-token streaming so the frontend streaming UI works.
    Note: System commands (time, date, volume, etc.) are handled by main.py's
    handle_command() BEFORE reaching here, so we only handle conversational input.
    """
    msg = message.lower().strip()

    if any(w in msg for w in ["hi", "hey", "hello", "yo", "sup", "how are you"]):
        response = "Hey~ I'm doing fine! Just so you know, I'm in dev mode — no Ollama models loaded yet. Pull one with `ollama pull phi4-mini:3.8b` and I'll be back to normal!"
    elif "help" in msg:
        response = "I'm May, your AI companion! Right now I'm running in mock mode because Ollama has no models. I can still handle system commands like time, date, volume, and brightness~"
    elif "who are you" in msg or "what are you" in msg:
        response = "I'm May~ Your AI companion, inspired by Shikimori. Right now I'm in dev mode because Ollama doesn't have any models downloaded yet. Once you run `ollama pull phi4-mini:3.8b`, I'll be fully functional!"
    else:
        response = random.choice(_MOCK_RESPONSES)

    # Stream word-by-word for realistic feel
    words = response.split(" ")
    for i, word in enumerate(words):
        prefix = "" if i == 0 else " "
        yield prefix + word
        await asyncio.sleep(MOCK_DELAY_PER_WORD)


async def resolve_model(requested_model: str | None = None) -> str:
    """Pick the best available model, checking what's actually downloaded."""
    if requested_model:
        return requested_model

    available = await get_available_models()
    if PRIMARY_MODEL.split(":")[0] in available:
        return PRIMARY_MODEL
    if FAST_MODEL.split(":")[0] in available:
        return FAST_MODEL
    # Return primary anyway — Ollama will pull if needed or error
    return PRIMARY_MODEL


def strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from text.

    Kept for backward compatibility with qwen3 models that use thinking mode.
    phi4-mini does NOT produce think tags, so this is a no-op for the primary model.
    """
    if "<think>" not in text:
        return text  # Fast path — phi4-mini never produces think tags
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    last_open = text.rfind("<think>")
    last_close = text.rfind("</think>")
    if last_open > last_close:
        text = text[:last_open]
    return text



async def stream_chat(
    message: str,
    history: list[dict] | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a chat response from Ollama.

    Yields text chunks as they are generated.
    Disables qwen3 thinking mode via API param + <think> tag filter.
    Falls back to mock streaming when Ollama has no models.

    The <think> tag filter uses an accumulated buffer approach to handle
    tokens that are split across streaming chunks (which happens with
    qwen3's character-level token streaming).
    """
    # Check if Ollama has models — if not, use mock mode
    available = await get_available_models()
    if not available:
        async for chunk in mock_stream_chat(message):
            yield chunk
        return

    # Use qwen3:4b directly
    if model is None:
        model = PRIMARY_MODEL

    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if history:
        for msg in history[-10:]:  # Keep last 10 messages for context
            role = msg.get("role", "user")
            if role in ("user", "may"):
                messages.append({
                    "role": "user" if role == "user" else "assistant",
                    "content": msg.get("content", ""),
                })

    messages.append({"role": "user", "content": message})

    # P5: Read gene values from auto-tuner (cached via tuner_cache)
    from intelligence.tuner_cache import get_gene
    temperature = get_gene("temperature", 0.7)
    num_ctx = int(get_gene("num_ctx", 131072))
    num_predict = int(get_gene("num_predict", 512))

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "num_gpu": 999,  # Force all layers to GPU (prevent CPU offload)
        },
    }

    from llm.providers import get_ollama_client
    client = await get_ollama_client()
    # Route to correct Ollama port based on model (router 11434 vs main 11435)
    ollama_url = get_ollama_url(model)
    try:
        async with client.stream(
            "POST",
            f"{ollama_url}/api/chat",
            json=payload,
        ) as response:
            response.raise_for_status()

            # Buffer-based approach for <think> tag filtering:
            # 1. Accumulate all content in a buffer
            # 2. Strip <think>...</think> blocks from the buffer
            # 3. Yield only new clean content since last iteration
            _full_accumulator = ""
            _last_yielded_len = 0

            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    # Skip explicit thinking blocks from Ollama
                    if data.get("thinking"):
                        continue
                    if "message" in data and "content" in data["message"]:
                        # Append to the accumulated buffer
                        _full_accumulator += data["message"]["content"]

                        # Strip <think>...</think> blocks from the accumulator
                        clean = strip_think_tags(_full_accumulator)

                        # Yield only new clean text since last time
                        new_clean = clean[_last_yielded_len:]
                        if new_clean:
                            yield new_clean
                            _last_yielded_len = len(clean)
                except json.JSONDecodeError:
                    continue
    except httpx.ConnectError:
        raise ConnectionError("Cannot connect to Ollama. Is it running?")
    except httpx.TimeoutException:
        raise TimeoutError("Ollama response timed out. The model may be loading.")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Ollama error: {e.response.status_code} — {e.response.text}")


# ── Speculative Decoding (P5) ─────────────────────────────────────────────
# Two modes:
# 1. TRUE speculative decoding via llama-server (25-40% speedup)
#    llama-server internally runs draft model → batch verify → accept/reject
#    Uses OpenAI-compatible /v1/chat/completions endpoint
# 2. Software approximation fallback (~10-20% speedup)
#    Draft prefix → main continuation via dual Ollama instances
#
# Mode is selected at runtime: if llama-server is running, use true mode.
# Otherwise fall back to software approximation.

_SPECULATIVE_DRAFT_MODEL = FAST_MODEL  # qwen3:0.6b as draft


async def speculative_generate(
    messages: list[dict],
    model: str = PRIMARY_MODEL,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    num_ctx: int = 131072,
    num_predict: int = 512,
) -> AsyncGenerator[str, None]:
    """Speculative decoding with automatic mode selection.

    If llama-server is running (with draft model), uses true batch-verified
    speculative decoding via its OpenAI-compatible endpoint (~25-40% speedup).

    Otherwise falls back to software approximation: draft with fast model,
    then continue with main model (~10-20% speedup).
    """
    # Try true speculative decoding first
    try:
        from llm.llama_server import is_llama_server_running, get_llama_server_url
        if is_llama_server_running():
            async for chunk in _speculative_generate_true(
                messages, system_prompt, temperature, max_tokens=num_predict,
            ):
                yield chunk
            return
    except ImportError:
        pass

    # Fallback: software approximation
    async for chunk in _speculative_generate_approx(
        messages, model, system_prompt, temperature, num_ctx, num_predict,
    ):
        yield chunk


async def _speculative_generate_true(
    messages: list[dict],
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """TRUE speculative decoding via llama-server's OpenAI-compatible API.

    llama-server internally handles draft → batch verify → accept/reject.
    We just stream from the standard /v1/chat/completions endpoint.
    The server does the magic transparently — see --spec-type draft-simple.
    """
    from llm.llama_server import get_llama_server_url
    from llm.providers import get_external_client

    base_url = get_llama_server_url()

    # Build OpenAI-compatible messages
    api_messages = []
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})
    for msg in messages:
        api_messages.append({"role": msg["role"], "content": msg["content"]})

    payload = {
        "model": "speculative",
        "messages": api_messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    client = await get_external_client()
    try:
        async with client.stream(
            "POST",
            f"{base_url}/v1/chat/completions",
            json=payload,
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
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                except json.JSONDecodeError:
                    continue
    except httpx.ConnectError:
        raise ConnectionError(f"Cannot connect to llama-server at {base_url}. Is it running?")
    except httpx.TimeoutException:
        raise TimeoutError("llama-server response timed out.")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"llama-server error: {e.response.status_code} — {e.response.text}")


async def _speculative_generate_approx(
    messages: list[dict],
    model: str = PRIMARY_MODEL,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    num_ctx: int = 131072,
    num_predict: int = 512,
) -> AsyncGenerator[str, None]:
    """Software approximation: draft with fast model, continue with main model.

    Step 1: Generate N draft tokens from the fast model (qwen3:0.6b)
    Step 2: Send draft tokens as prefix to the main model (phi4-mini:3.8b)
            which continues from that prefix.
    """
    from llm.providers import get_ollama_client
    client = await get_ollama_client()

    # Step 1: Generate draft tokens from fast model
    draft_messages = []
    if system_prompt:
        draft_messages.append({"role": "system", "content": system_prompt})
    draft_messages.extend(messages)
    draft_payload = {
        "model": _SPECULATIVE_DRAFT_MODEL,
        "messages": draft_messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": 8,
            "num_ctx": num_ctx,
            "num_gpu": 999,
        },
    }

    draft_text = ""
    try:
        url = get_ollama_url(_SPECULATIVE_DRAFT_MODEL)
        async with client.stream("POST", f"{url}/api/chat", json=draft_payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        draft_text += data["message"]["content"]
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.debug("Draft model failed, falling back to main: %s", e)
        draft_text = ""

    # Step 2: Continue with main model using draft as prefix
    if draft_text.strip():
        verify_messages = list(messages)
        verify_messages.append({
            "role": "assistant",
            "content": draft_text.strip()[:200],
        })
        verify_messages.append({
            "role": "user",
            "content": "(Continue your response from where you left off. The above was a draft.)",
        })
    else:
        verify_messages = list(messages)

    verify_payload = {
        "model": model,
        "messages": verify_messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "num_gpu": 999,
        },
    }

    _full_accumulator = ""
    _last_yielded_len = 0

    try:
        url = get_ollama_url(model)
        async with client.stream("POST", f"{url}/api/chat", json=verify_payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("thinking"):
                        continue
                    if "message" in data and "content" in data["message"]:
                        _full_accumulator += data["message"]["content"]
                        clean = strip_think_tags(_full_accumulator)
                        new_clean = clean[_last_yielded_len:]
                        if new_clean:
                            yield new_clean
                            _last_yielded_len = len(clean)
                except json.JSONDecodeError:
                    continue
    except httpx.ConnectError:
        raise ConnectionError("Cannot connect to Ollama. Is it running?")
    except httpx.TimeoutException:
        raise TimeoutError("Ollama response timed out.")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Ollama error: {e.response.status_code} — {e.response.text}")


async def check_model_available(model: str = "qwen3:4b") -> bool:
    """Check if a model is available in Ollama."""
    models = await get_available_models()
    return any(model.split(":")[0] in m for m in models)


async def extract_facts(
    message: str,
    response: str,
    existing_facts: list[str] | None = None,
) -> list[str]:
    """Use the LLM to extract user facts from a conversation exchange."""
    existing = "\n".join(f"- {f}" for f in (existing_facts or []))
    prompt = f"""Extract facts about the user from this conversation. Return ONLY new facts, one per line.
Do not repeat existing facts.

Existing facts:
{existing or "(none yet)"}

User said: {message}
May responded: {response}

New facts (one per line, or "none" if no new facts):"""

    try:
        full_response = ""
        async for chunk in stream_chat(
            message=prompt,
            system_prompt="You are a fact extractor. Be concise. Return only facts, nothing else.",
        ):
            full_response += chunk

        if full_response.lower().strip() == "none" or not full_response.strip():
            return []
        return [
            line.lstrip("- ").strip()
            for line in full_response.split("\n")
            if line.strip() and line.strip().lower() != "none"
        ]
    except (ConnectionError, TimeoutError, RuntimeError):
        return []


async def summarize_conversation(messages: list[dict]) -> str:
    """Summarize a conversation into key points for long-term memory."""
    conversation = "\n".join(
        f"{'User' if m.get('role') == 'user' else 'May'}: {m.get('content', '')}"
        for m in messages
    )
    prompt = f"""Summarize this conversation in 3-5 bullet points. Focus on:
- Key topics discussed
- User preferences revealed
- Actions taken or requested
- Any commitments or reminders

Conversation:
{conversation}

Summary (bullet points):"""

    try:
        full_response = ""
        async for chunk in stream_chat(
            message=prompt,
            system_prompt="You are a conversation summarizer. Be concise.",
        ):
            full_response += chunk
        return full_response.strip()
    except (ConnectionError, TimeoutError, RuntimeError):
        return "Unable to summarize conversation."
