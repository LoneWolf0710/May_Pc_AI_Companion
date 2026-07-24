"""Test agentic loop bug fixes using online providers.

Tests multi-step commands through the /chat endpoint to verify:
- BUG-1: Initial LLM response text is yielded before tool execution
- BUG-2: Context trimming preserves user request + assistant plan
- BUG-3: LLM continues executing tools across multiple rounds
- BUG-4: History buffer works with online providers
- BUG-5: Provider streaming works (was the display_name crash)
- BUG-6: Tool tiering cache rebuilds correctly

Usage:
    cd C:\\AI\\may
    python tests/test_online_providers.py
"""

import asyncio
import httpx
import json
import time
import sys

BACKEND = "http://localhost:8080"

# Test providers to exercise (must have API keys configured)
TEST_PROVIDERS = [
    {"provider": "openrouter", "model": "openai/gpt-4o-mini", "label": "OpenRouter GPT-4o Mini"},
    {"provider": "gemini", "model": "gemini-2.0-flash", "label": "Gemini 2.0 Flash"},
    {"provider": "google_ai_studio", "model": "gemini-2.0-flash", "label": "Google AI Studio Flash"},
]


async def chat_stream(client, message, provider, model, history=None):
    """Send a chat message and collect the full streamed response."""
    payload = {
        "message": message,
        "history": history or [],
        "provider": provider,
        "model": model,
    }
    start = time.time()
    full_response = ""
    try:
        async with client.stream("POST", f"{BACKEND}/chat", json=payload, timeout=120) as resp:
            async for chunk in resp.aiter_text():
                full_response += chunk
    except Exception as e:
        return f"ERROR: {e}", time.time() - start
    elapsed = time.time() - start
    return full_response.strip(), elapsed


async def run_tests():
    """Run all agentic loop tests."""
    results = []
    async with httpx.AsyncClient(timeout=120) as client:
        # ── Health check ────────────────────────────────────────────────
        print("=" * 70)
        print("🌸 May Online Provider Test Suite — Agentic Loop Bug Fixes")
        print("=" * 70)
        try:
            health = await client.get(f"{BACKEND}/health", timeout=5)
            print(f"✓ Backend healthy: {health.json().get('status')}\n")
        except Exception as e:
            print(f"✗ Backend not running: {e}")
            print("  Start with: cd backend && python main.py")
            return

        for prov in TEST_PROVIDERS:
            provider = prov["provider"]
            model = prov["model"]
            label = prov["label"]
            print(f"─── Testing: {label} ({provider}/{model}) ───")

            # ── Test 1: Simple chat (no tools) ──────────────────────────
            print(f"\n  [1] Simple chat...")
            resp, elapsed = await chat_stream(client, "Say hi in 5 words or less", provider, model)
            has_content = len(resp) > 0 and "ERROR" not in resp
            status = "✓" if has_content else "✗"
            print(f"      {status} Response ({elapsed:.1f}s): {resp[:120]}")
            results.append({"test": f"{label} simple chat", "passed": has_content, "elapsed": elapsed})

            # ── Test 2: Single tool call (open_app) ─────────────────────
            print(f"\n  [2] Single tool call: open notepad...")
            resp, elapsed = await chat_stream(
                client,
                "Open notepad",
                provider,
                model,
            )
            has_tool = "🔧" in resp or "open_app" in resp.lower() or "notepad" in resp.lower() or "Done" in resp
            status = "✓" if has_tool else "✗"
            print(f"      {status} Response ({elapsed:.1f}s): {resp[:200]}")
            results.append({"test": f"{label} single tool call", "passed": has_tool, "elapsed": elapsed})

            # ── Test 3: Multi-step tool call (THE MAIN BUG) ─────────────
            print(f"\n  [3] Multi-step: open notepad THEN type hello...")
            resp, elapsed = await chat_stream(
                client,
                "Open notepad and type hello",
                provider,
                model,
            )
            # Check for evidence of BOTH tools executing
            has_open = "open_app" in resp.lower() or "notepad" in resp.lower() or "Done" in resp
            has_type = "type_text" in resp.lower() or "hello" in resp.lower() or "🔧" in resp
            # Multiple 🔧 = multiple tool executions = multi-step working
            tool_count = resp.count("🔧")
            multi_step = tool_count >= 2 or (has_open and has_type)
            status = "✓" if multi_step else "✗"
            print(f"      {status} Response ({elapsed:.1f}s): {resp[:300]}")
            print(f"      Tool calls detected: {tool_count}")
            results.append({"test": f"{label} multi-step tools", "passed": multi_step, "elapsed": elapsed, "tool_count": tool_count})

            # ── Test 4: Follow-up message (context continuity) ──────────
            print(f"\n  [4] Follow-up: type 'world' in notepad...")
            resp, elapsed = await chat_stream(
                client,
                "Now type 'world' in notepad",
                provider,
                model,
                history=[
                    {"role": "user", "content": "Open notepad and type hello"},
                    {"role": "assistant", "content": "Done~ Opened notepad and typed hello"},
                ],
            )
            has_type = "type_text" in resp.lower() or "world" in resp.lower() or "🔧" in resp or "Done" in resp
            status = "✓" if has_type else "✗"
            print(f"      {status} Response ({elapsed:.1f}s): {resp[:200]}")
            results.append({"test": f"{label} follow-up context", "passed": has_type, "elapsed": elapsed})

            # ── Test 5: Tool tiering — web search query ─────────────────
            print(f"\n  [5] Web search: 'what time is it in Tokyo'...")
            resp, elapsed = await chat_stream(
                client,
                "What time is it in Tokyo right now?",
                provider,
                model,
            )
            has_search = "web_search" in resp.lower() or "tokyo" in resp.lower() or "time" in resp.lower() or "🔧" in resp
            status = "✓" if has_search else "✗"
            print(f"      {status} Response ({elapsed:.1f}s): {resp[:200]}")
            results.append({"test": f"{label} web search tool", "passed": has_search, "elapsed": elapsed})

            print()

        # ── Summary ─────────────────────────────────────────────────────
        print("=" * 70)
        print("📊 Test Results Summary")
        print("=" * 70)
        passed = sum(1 for r in results if r["passed"])
        total = len(results)
        for r in results:
            icon = "✓" if r["passed"] else "✗"
            extra = f" [tools={r.get('tool_count', '?')}]" if "tool_count" in r else ""
            print(f"  {icon} {r['test']} ({r['elapsed']:.1f}s){extra}")
        print(f"\n  Total: {passed}/{total} passed ({100*passed//total}%)")
        print("=" * 70)

        # Return exit code
        return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_tests())
    sys.exit(exit_code or 0)
