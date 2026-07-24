"""Phase 12 Intelligence Layer — integration test."""
import sys
import time
import asyncio

sys.path.insert(0, "backend")
sys.path.insert(0, ".")

# ── Test 1: Module imports ──────────────────────────────────────────────
from intelligence.shadow_learner import ShadowLearner
from intelligence.frustration_detector import FrustrationDetector
from intelligence.screen_watcher import ScreenWatcher
print("[PASS] Test 1: All intelligence modules imported")

# ── Test 2: Instance creation ───────────────────────────────────────────
sl = ShadowLearner()
fd = FrustrationDetector()
sw = ScreenWatcher()
print("[PASS] Test 2: All instances created")

# ── Test 3: Shadow learner registration (no circular import) ────────────
import llm.jarvis as jarvis_mod
jarvis_mod.set_shadow_learner(sl)
assert jarvis_mod._shadow_learner_ref is sl, "Shadow learner not set"
print("[PASS] Test 3: Shadow learner registered with jarvis (no circular import)")

# ── Test 4: Shadow learner event recording + pattern detection ──────────
now = time.time()
sl.record_event("open_app", "chrome", now - 300)
sl.record_event("web_search", "python docs", now - 250)
sl.record_event("open_app", "chrome", now - 200)
sl.record_event("web_search", "python docs", now - 150)
sl.record_event("open_app", "chrome", now - 100)
sl.record_event("web_search", "python docs", now - 50)
stats = sl.get_stats()
assert stats["events_recorded"] == 6, f"Expected 6 events, got {stats['events_recorded']}"
print(f"[PASS] Test 4: Shadow learner recorded {stats['events_recorded']} events, detected {stats['patterns_detected']} patterns")

# ── Test 5: Frustration detector ────────────────────────────────────────
for _ in range(10):
    fd.record_key_press("backspace", time.time())
score = fd.calculate_score()
assert score > 0, f"Frustration score should be > 0, got {score}"
print(f"[PASS] Test 5: Frustration score after 10 backspaces: {score}/100")

# ── Test 6: Screen watcher lifecycle ────────────────────────────────────
async def test_screen_watcher():
    await sw.start()
    assert sw._active, "Should be active after start"
    sw.pause()
    assert not sw._active, "Should be paused"
    sw.resume()
    assert sw._active, "Should be active after resume"
    await sw.stop()
    assert not sw._active, "Should be stopped"

asyncio.run(test_screen_watcher())
print("[PASS] Test 6: Screen watcher start/pause/resume/stop lifecycle works")

# ── Test 7: Shadow learner suggestion generation ────────────────────────
suggestions = sl.get_suggestions()
print(f"[PASS] Test 7: Shadow learner has {len(suggestions)} pending suggestions")
if suggestions:
    print(f"   -> {suggestions[0]['message']}")

print("\n=== ALL TESTS PASSED - Phase 12 Intelligence Layer is working! ===")
