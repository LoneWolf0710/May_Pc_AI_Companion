"""Test script: Open and close Horizon Zero Dawn via the Control Core daemon."""
import asyncio
import sys
import os
import time

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test():
    from core.client import send_command, is_daemon_running

    # Check daemon is running
    running = await is_daemon_running()
    print(f"Daemon running: {running}")
    if not running:
        print("ERROR: Daemon not running on port 7650. Start it first.")
        return

    import psutil

    # ── Step 1: Open Horizon Zero Dawn ──────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 1: Opening Horizon Zero Dawn Remastered")
    print("=" * 60)
    t0 = time.monotonic()
    result = await send_command("application", "launch_app",
                                {"app_name": "horizon zero dawn remastered"}, timeout=20)
    elapsed = time.monotonic() - t0
    print(f"  Success:   {result.success}")
    print(f"  Data:      {result.data}")
    print(f"  Error:     {result.error}")
    print(f"  Method:    {result.method_used}")
    print(f"  Verified:  {result.verified}")
    print(f"  Time:      {elapsed:.1f}s")

    if not result.success:
        # Try the shorter name
        print("\n  Retrying with 'horizon zero dawn'...")
        t0 = time.monotonic()
        result = await send_command("application", "launch_app",
                                    {"app_name": "horizon zero dawn"}, timeout=20)
        elapsed = time.monotonic() - t0
        print(f"  Success:   {result.success}")
        print(f"  Data:      {result.data}")
        print(f"  Error:     {result.error}")
        print(f"  Method:    {result.method_used}")
        print(f"  Verified:  {result.verified}")
        print(f"  Time:      {elapsed:.1f}s")

    # ── Step 2: Check if running ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 2: Checking if Horizon Zero Dawn is running")
    print("=" * 60)
    await asyncio.sleep(3)  # Wait for app to start
    found = []
    for p in psutil.process_iter(["name", "pid", "exe"]):
        name = (p.info["name"] or "").lower()
        if "horizon" in name or "HZD" in (p.info["name"] or "") or "guerrilla" in name:
            found.append(p.info)
    print(f"  Found {len(found)} Horizon-related process(es):")
    for p in found:
        print(f"    PID {p['pid']}: {p['name']} ({p.get('exe', 'N/A')})")

    if not found:
        print("  No Horizon processes found — app may not have started.")
        print("  This is expected if the game requires Steam/Epic launcher.")
        print("  Testing close anyway to verify error handling...")

    # ── Step 3: Close Horizon Zero Dawn ────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 3: Closing Horizon Zero Dawn")
    print("=" * 60)
    t0 = time.monotonic()
    result2 = await send_command("application", "close_app",
                                 {"app_name": "horizon zero dawn"}, timeout=15)
    elapsed = time.monotonic() - t0
    print(f"  Success:   {result2.success}")
    print(f"  Data:      {result2.data}")
    print(f"  Error:     {result2.error}")
    print(f"  Method:    {result2.method_used}")
    print(f"  Verified:  {result2.verified}")
    print(f"  Time:      {elapsed:.1f}s")

    # ── Step 4: Verify it's closed ────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 4: Verifying Horizon Zero Dawn is closed")
    print("=" * 60)
    await asyncio.sleep(1)
    still_running = []
    for p in psutil.process_iter(["name", "pid"]):
        name = (p.info["name"] or "").lower()
        if "horizon" in name or "guerrilla" in name:
            still_running.append(p.info)
    
    if still_running:
        print(f"  STILL RUNNING ({len(still_running)} processes):")
        for p in still_running:
            print(f"    PID {p['pid']}: {p['name']}")
        print("  RESULT: FAIL — app not closed!")
    else:
        if found:
            print("  No Horizon processes found.")
            print("  RESULT: PASS — app was closed successfully!")
        else:
            print("  No Horizon processes found (none were running to begin with).")
            print("  RESULT: PASS — close_app handled gracefully with no process to close")

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    open_ok = result.success if result else False
    close_ok = result2.success if result2 else False
    print(f"  Open:  {'PASS' if open_ok else 'FAIL'} ({result.error if not open_ok else result.method_used})")
    print(f"  Close: {'PASS' if close_ok else 'FAIL'} ({result2.error if not close_ok else result2.method_used})")

if __name__ == "__main__":
    asyncio.run(test())
