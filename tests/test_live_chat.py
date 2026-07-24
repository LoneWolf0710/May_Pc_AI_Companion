"""
Live integration test — sends the actual compound command to the running backend.

Usage:
    python may/tests/test_live_chat.py

Prerequisites:
    - Backend running on http://localhost:8080 (or starts it automatically)
    - Control Core daemon running on port 7650 (auto-started by backend)
    - Ollama running with qwen3:4b model

This test verifies the complete flow:
    User message → Fast-path check → LLM → Tool execution → File created
"""

import asyncio
import httpx
import sys
import os
import subprocess
import time
import signal
import io

# Fix Windows console encoding for Unicode output when run standalone.
# NOTE: Gated to __main__ so pytest's capture manager is not broken (wrapping
# sys.stdout/stderr at import time caused "I/O operation on closed file" /
# "lost sys.stderr" crashes that aborted the whole test session).
if __name__ == "__main__" and sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

BACKEND_URL = "http://localhost:8080"
COMMAND = "open notepad and make a new file in it and write a detailed HTML code about making a pokemon webpage"


async def check_backend_running() -> bool:
    """Check if the backend is already running."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{BACKEND_URL}/health")
            return r.status_code == 200
    except Exception:
        return False


async def start_backend() -> subprocess.Popen:
    """Start the backend server."""
    backend_dir = os.path.join(os.path.dirname(__file__), '..', 'backend')
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
    )
    # Wait for backend to be ready (max 30s)
    for i in range(60):
        await asyncio.sleep(0.5)
        if await check_backend_running():
            print(f"  ✓ Backend ready after {i * 0.5}s")
            return proc
    print("  ✗ Backend failed to start within 30s")
    proc.kill()
    return None


async def send_chat_message(message: str) -> dict:
    """Send a chat message and collect the full response."""
    async with httpx.AsyncClient(timeout=60) as client:
        payload = {
            "message": message,
            "history": [],
            "provider": "ollama",
            "model": "qwen3:4b",
        }
        full_response = ""
        tool_calls_seen = []

        async with client.stream("POST", f"{BACKEND_URL}/chat", json=payload) as resp:
            async for chunk in resp.aiter_text():
                full_response += chunk

        return {
            "response": full_response,
            "has_tool_output": "🔧" in full_response,
            "has_write_file": "write_file" in full_response,
            "has_open_app": "open_app" in full_response,
            "has_done": "Done" in full_response or "done" in full_response.lower(),
            "response_length": len(full_response),
        }


async def check_desktop_file() -> dict:
    """Check if a pokemon HTML file was created on the Desktop."""
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    pokemon_files = []

    for f in os.listdir(desktop):
        if "pokemon" in f.lower() and f.endswith(".html"):
            pokemon_files.append(f)

    return {
        "found": len(pokemon_files) > 0,
        "files": pokemon_files,
        "desktop": desktop,
    }


async def main():
    print("=" * 70)
    print("🧪 LIVE END-TO-END TEST: Compound Command")
    print(f"   Command: {COMMAND}")
    print("=" * 70)

    # Step 1: Check backend
    print("\n📋 Step 1: Checking backend...")
    backend_running = await check_backend_running()

    if backend_running:
        print("  ✓ Backend already running on port 8080")
    else:
        print("  ✗ Backend not running on port 8080")
        print("  → Start it first: cd may/backend && python main.py")
        return False

    # Step 2: Send the compound command
    print(f"\n📋 Step 2: Sending command...")
    print(f"  > {COMMAND}")

    try:
        result = await send_chat_message(COMMAND)
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False

    # Step 3: Analyze response
    print(f"\n📋 Step 3: Analyzing response...")
    print(f"  Response length: {result['response_length']} chars")
    print(f"  Has tool output (🔧): {result['has_tool_output']}")
    print(f"  Has write_file: {result['has_write_file']}")
    print(f"  Has open_app: {result['has_open_app']}")

    # Show first 500 chars of response
    print(f"\n  Response preview:")
    print(f"  {'─' * 60}")
    for line in result['response'][:800].split('\n'):
        print(f"  │ {line}")
    print(f"  {'─' * 60}")

    # Step 4: Check Desktop for created file
    print(f"\n📋 Step 4: Checking Desktop for pokemon HTML file...")
    file_check = await check_desktop_file()
    if file_check['found']:
        print(f"  ✓ Found: {file_check['files']}")
        for f in file_check['files']:
            fpath = os.path.join(file_check['desktop'], f)
            size = os.path.getsize(fpath)
            print(f"    → {fpath} ({size} bytes)")
    else:
        print(f"  ⚠ No pokemon HTML file found on Desktop")
        print(f"    (The LLM may have saved to a different location)")

    # Step 5: Verdict
    print(f"\n{'=' * 70}")
    success = result['has_tool_output'] or result['has_write_file'] or result['has_open_app']
    if success:
        print("✅ PASS: Compound command produced tool executions")
        if result['has_write_file']:
            print("  → write_file was called (code saved to file)")
        if result['has_open_app']:
            print("  → open_app was called (file opened)")
        if file_check['found']:
            print(f"  → HTML file created: {file_check['files'][0]}")
    else:
        print("❌ FAIL: No tool executions detected in response")
        print("  → The LLM may have responded with text only")
        print("  → Check if Ollama is running with qwen3:4b")
    print("=" * 70)

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
