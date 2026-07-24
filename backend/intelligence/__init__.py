"""Intelligence Layer — proactive awareness for May.

From JARVIS V2: shadow learning, screen watching, frustration detection.
All modules run in background threads and emit events via the event bus.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("may.intelligence")

# Lazy imports — modules are heavy, don't load until needed
_shadow_learner = None
_frustration_detector = None
_screen_watcher = None


def get_shadow_learner():
    global _shadow_learner
    if _shadow_learner is None:
        from .shadow_learner import ShadowLearner
        _shadow_learner = ShadowLearner()
    return _shadow_learner


def get_frustration_detector():
    global _frustration_detector
    if _frustration_detector is None:
        from .frustration_detector import FrustrationDetector
        _frustration_detector = FrustrationDetector()
    return _frustration_detector


def get_screen_watcher():
    global _screen_watcher
    if _screen_watcher is None:
        from .screen_watcher import ScreenWatcher
        _screen_watcher = ScreenWatcher()
    return _screen_watcher
