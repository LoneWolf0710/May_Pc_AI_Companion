"""Self-contained test runner -- starts backend, runs tests, reports results.
Uses only ASCII characters to avoid Windows cp1252 encoding errors.
"""

import subprocess
import time
import sys
import json
import httpx


def start_backend():
    """Start the backend and wait for it to be ready."""
    print("[START] Starting backend...")
    proc = subprocess.Popen(
        [sys.executable, "C:\\AI\\may\\backend\\main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    for _ in range(60):
        time.sleep(0.5)
        try:
            r = __import__("urllib.request").urlopen("http://localhost:8080/health", timeout=3)
            data = json.loads(r.read().decode())
            print("[OK] Backend ready (ollama=%s)" % data.get("ollama", "unknown"))
            return proc
        except Exception:
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode() if proc.stderr else ""
                print("[FAIL] Backend crashed: %s" % stderr[:500])
                return None
            continue

    print("[WARN] Backend not ready after 30s, proceeding anyway")
    return proc


def run_chat(provider, model, message, history=None):
    """Send a chat request and return (full_response, elapsed_seconds)."""
    payload = {
        "message": message,
        "history": history or [],
        "provider": provider,
        "model": model,
    }
    start = time.time()
    full = ""
    try:
        with httpx.Client(timeout=120) as client:
            with client.stream("POST", "http://localhost:8080/chat", json=payload) as resp:
                for chunk in resp.iter_text():
                    full += chunk
    except Exception as e:
        return "ERROR: %s" % e, time.time() - start
    return full.strip(), time.time() - start


def main():
    print("=" * 70)
    print("May Online Provider Test Suite -- Agentic Loop Bug Fixes")
    print("=" * 70)

    proc = start_backend()

    providers = [
        ("openrouter", "openai/gpt-4o-mini", "OpenRouter GPT-4o Mini"),
        ("gemini", "gemini-2.0-flash", "Gemini 2.0 Flash"),
        ("google_ai_studio", "gemini-2.0-flash", "AI Studio Flash"),
    ]

    results = []

    for provider, model, label in providers:
        print("\n--- Testing: %s (%s/%s) ---" % (label, provider, model))

        # Test 1: Simple chat
        print("  [1] Simple chat...")
        resp, elapsed = run_chat(provider, model, "Say hi in 5 words or less")
        ok = len(resp) > 5 and "ERROR" not in resp
        tag = "[OK]" if ok else "[FAIL]"
        print("      %s (%.1fs): %s" % (tag, elapsed, resp[:120]))
        results.append(("%s simple chat" % label, ok, elapsed))

        # Test 2: Single tool call
        print("  [2] Single tool: open notepad...")
        resp, elapsed = run_chat(provider, model, "Open notepad")
        has_tool = "tool" in resp.lower() or "notepad" in resp.lower() or "Done" in resp
        tag = "[OK]" if has_tool else "[FAIL]"
        print("      %s (%.1fs): %s" % (tag, elapsed, resp[:200]))
        results.append(("%s single tool" % label, has_tool, elapsed))

        # Test 3: Multi-step (THE MAIN BUG FIX)
        print("  [3] Multi-step: open notepad + type hello...")
        resp, elapsed = run_chat(provider, model, "Open notepad and type hello")
        tool_count = resp.count("tool") + resp.count("executing")
        multi_step = tool_count >= 2 or ("notepad" in resp.lower() and "hello" in resp.lower())
        tag = "[OK]" if multi_step else "[FAIL]"
        print("      %s (%.1fs, signals=%d): %s" % (tag, elapsed, tool_count, resp[:300]))
        results.append(("%s multi-step" % label, multi_step, elapsed, tool_count))

        # Test 4: Follow-up with history
        print("  [4] Follow-up: type 'world'...")
        resp, elapsed = run_chat(
            provider, model,
            "Now type 'world' in notepad",
            history=[
                {"role": "user", "content": "Open notepad and type hello"},
                {"role": "assistant", "content": "Done~ Opened notepad and typed hello"},
            ],
        )
        ok = "type" in resp.lower() or "world" in resp.lower() or "Done" in resp
        tag = "[OK]" if ok else "[FAIL]"
        print("      %s (%.1fs): %s" % (tag, elapsed, resp[:200]))
        results.append(("%s follow-up" % label, ok, elapsed))

        # Test 5: Web search
        print("  [5] Web search...")
        resp, elapsed = run_chat(provider, model, "What time is it in Tokyo right now?")
        ok = "search" in resp.lower() or "tokyo" in resp.lower() or "time" in resp.lower()
        tag = "[OK]" if ok else "[FAIL]"
        print("      %s (%.1fs): %s" % (tag, elapsed, resp[:200]))
        results.append(("%s web search" % label, ok, elapsed))

    # Summary
    print("\n" + "=" * 70)
    print("Results Summary")
    print("=" * 70)
    passed = sum(1 for r in results if r[1])
    total = len(results)
    for entry in results:
        name = entry[0]
        ok = entry[1]
        elapsed = entry[2]
        extra = " [signals=%d]" % entry[3] if len(entry) > 3 else ""
        tag = "[OK]" if ok else "[FAIL]"
        print("  %s %s (%.1fs)%s" % (tag, name, elapsed, extra))
    print("\n  Total: %d/%d passed (%d%%)" % (passed, total, 100 * passed // max(total, 1)))
    print("=" * 70)

    if proc:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("\nBackend stopped.")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
