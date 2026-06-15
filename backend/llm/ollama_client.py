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

OLLAMA_BASE_URL = "http://localhost:11434"

# Model configuration
# Using qwen3:4b directly — custom Modelfile creation unsupported in ollama 0.30.6
# Thinking is disabled via the 'think' option in the API payload + <think> tag filter
PRIMARY_MODEL = "qwen3:4b"
FAST_MODEL = "gemma2:2b"  # Fallback for simple queries if available

# ── Mock/dev mode: simulated responses when Ollama has no models ──────────
_MOCK_RESPONSES = [
    "Hey~ I'm May! Ollama is running but no models are loaded yet. Download one with `ollama pull qwen3:4b` and I'll be back to normal~",
    "I'm in dev mode right now~ No models available in Ollama. Once you pull a model, I'll have real answers for you!",
    "Hmm, it looks like Ollama doesn't have any models downloaded. Try `ollama pull qwen3:4b` to get me working properly~",
    "Just a heads up — I'm running in mock mode because Ollama has no models. I can still help with system commands though!",
    "I'm here~ but my brain (LLM) isn't loaded yet. Pull a model with Ollama and I'll be good to go!",
]

# Simulated streaming tokens for mock mode (word-by-word)
MOCK_DELAY_PER_WORD = 0.03  # seconds between words for realistic feel


def is_simple_query(message: str) -> bool:
    """Determine if a message is simple enough for the fast model.

    Simple queries: time, date, math, short factual questions.
    Complex queries: reasoning, creative writing, coding, long conversations.
    """
    msg = message.lower().strip()

    # Short messages are likely simple
    if len(msg.split()) <= 6:
        # But exclude coding/reasoning keywords
        complex_keywords = [
            "write", "code", "create", "explain", "why", "how does",
            "implement", "design", "compare", "analyze", "summarize",
            "translate", "write me", "help me", "what do you think",
        ]
        if not any(kw in msg for kw in complex_keywords):
            return True

    # Time/date/math queries
    simple_patterns = [
        "what time", "current time", "what day", "today",
        "what date", "what's the date", "what year",
    ]
    if any(p in msg for p in simple_patterns):
        return True

    # Very short greetings
    if len(msg.split()) <= 3 and any(w in msg for w in ["hi", "hey", "hello", "yo", "sup"]):
        return True

    return False


async def get_available_models() -> list[str]:
    """Get list of available Ollama models."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            return [m.get("name", "").split(":")[0] for m in models]
        except (httpx.HTTPError, ConnectionError):
            return []


async def is_ollama_running() -> bool:
    """Check if Ollama is reachable."""
    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return response.status_code == 200
        except (httpx.HTTPError, ConnectionError):
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
        response = "Hey~ I'm doing fine! Just so you know, I'm in dev mode — no Ollama models loaded yet. Pull one with `ollama pull qwen3:4b` and I'll be back to normal!"
    elif "help" in msg:
        response = "I'm May, your AI companion! Right now I'm running in mock mode because Ollama has no models. I can still handle system commands like time, date, volume, and brightness~"
    elif "who are you" in msg or "what are you" in msg:
        response = "I'm May~ Your AI companion, inspired by Shikimori. Right now I'm in dev mode because Ollama doesn't have any models downloaded yet. Once you run `ollama pull qwen3:4b`, I'll be fully functional!"
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

    Uses repeated regex to handle nested tags robustly.
    Also strips content from the last unclosed <think> tag (handles the
    common case where </think> hasn't arrived in the stream yet).
    Works at the text level (not per-chunk) to handle tokens split across chunks.
    """
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Strip unclosed <think> blocks — </think> hasn't arrived yet
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

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_ctx": 4096,
            "num_predict": 512,
            "think": False,  # Disable qwen3 thinking mode — in options for ollama compat
        },
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0)
    ) as client:
        try:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/chat",
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
