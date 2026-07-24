"""Tests for core.layers.fuzzy_match — fuzzy app name resolution.

Run: python -m pytest tests/test_fuzzy_match.py -v
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.layers.fuzzy_match import (
    _levenshtein,
    _normalize,
    _tokens,
    _exact_match,
    _prefix_match,
    _abbreviation_match,
    _substring_match,
    _levenshtein_match,
    _token_overlap_match,
    fuzzy_resolve,
    fuzzy_best,
)


def check(condition, label):
    status = "✅" if condition else "❌"
    print(f"  {status} {label}")
    assert condition, f"FAILED: {label}"


# ══════════════════════════════════════════════════════════════════════════════
# 1. Levenshtein Distance
# ══════════════════════════════════════════════════════════════════════════════

def test_levenshtein():
    print("\n[1] Levenshtein Distance")
    check(_levenshtein("", "") == 0, "empty strings = 0")
    check(_levenshtein("abc", "abc") == 0, "identical = 0")
    check(_levenshtein("abc", "ab") == 1, "one deletion = 1")
    check(_levenshtein("abc", "abcd") == 1, "one insertion = 1")
    check(_levenshtein("abc", "axc") == 1, "one substitution = 1")
    check(_levenshtein("kitten", "sitting") == 3, "kitten→sitting = 3")
    check(_levenshtein("chrome", "chrm") == 2, "chrome→chrm = 2")
    check(_levenshtein("firefox", "firfox") == 1, "firefox→firfox = 1")
    check(_levenshtein("a", "xyz") == 3, "a→xyz = 3")


# ══════════════════════════════════════════════════════════════════════════════
# 2. Normalization
# ══════════════════════════════════════════════════════════════════════════════

def test_normalize():
    print("\n[2] Normalization")
    check(_normalize("Chrome") == "chrome", "lowercase")
    check(_normalize("Visual Studio Code") == "visual studio code", "multi-word")
    check(_normalize("Notepad++") == "notepad", "strip special chars")
    check(_normalize("GOG Galaxy") == "gog galaxy", "spaces preserved")
    check(_normalize("  Chrome  ") == "chrome", "strip whitespace")
    check(_normalize("chrome.exe") == "chrome", "strip .exe")
    check(_normalize("file.txt") == "file.txt", "keep .txt (not .exe)")


# ══════════════════════════════════════════════════════════════════════════════
# 3. Exact Match
# ══════════════════════════════════════════════════════════════════════════════

def test_exact_match():
    print("\n[3] Exact Match")
    check(_exact_match("chrome", "chrome") == 1.0, "identical")
    check(_exact_match("Chrome", "chrome") == 1.0, "case-insensitive")
    check(_exact_match("chrome", "firefox") == 0.0, "different")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Prefix Match
# ══════════════════════════════════════════════════════════════════════════════

def test_prefix_match():
    print("\n[4] Prefix Match")
    check(_prefix_match("notep", "notepad") > 0.7, "notep→notepad")
    check(_prefix_match("notepad", "notepad++") > 0.6, "notepad→notepad++")
    check(_prefix_match("fire", "firefox") > 0.6, "fire→firefox")
    check(_prefix_match("chrome", "firefox") == 0.0, "no prefix relation")


# ══════════════════════════════════════════════════════════════════════════════
# 5. Abbreviation Match
# ══════════════════════════════════════════════════════════════════════════════

def test_abbreviation_match():
    print("\n[5] Abbreviation Match")
    # Multi-word initials
    check(_abbreviation_match("vs", "visual studio") > 0.7, "vs→visual studio (initials)")
    check(_abbreviation_match("vscode", "visual studio code") > 0.6, "vscode→visual studio code")
    # Single word abbreviation (consonant skeleton)
    check(_abbreviation_match("chrm", "chrome") > 0.6, "chrm→chrome (consonant skeleton)")
    check(_abbreviation_match("ntpd", "notepad") > 0.6, "ntpd→notepad")


# ══════════════════════════════════════════════════════════════════════════════
# 6. Substring Match
# ══════════════════════════════════════════════════════════════════════════════

def test_substring_match():
    print("\n[6] Substring Match")
    check(_substring_match("fire", "firefox") > 0.6, "fire⊂firefox")
    check(_substring_match("chrome", "google chrome") > 0.6, "chrome⊂google chrome")
    check(_substring_match("firefox", "mozilla firefox") > 0.6, "firefox⊂mozilla firefox")
    check(_substring_match("chrome", "firefox") == 0.0, "no substring relation")


# ══════════════════════════════════════════════════════════════════════════════
# 7. Levenshtein Match
# ══════════════════════════════════════════════════════════════════════════════

def test_levenshtein_match():
    print("\n[7] Levenshtein Match")
    check(_levenshtein_match("chrme", "chrome") > 0.8, "chrme→chrome (1 edit)")
    check(_levenshtein_match("firfox", "firefox") > 0.8, "firfox→firefox (1 edit)")
    check(_levenshtein_match("chrm", "chrome") > 0.6, "chrm→chrome (2 edits)")
    check(_levenshtein_match("notepad", "notepad") > 0.9, "notepad→notepad (exact, high confidence)")
    check(_levenshtein_match("", "chrome") == 0.0, "empty query → no match")


# ══════════════════════════════════════════════════════════════════════════════
# 8. Token Overlap Match
# ══════════════════════════════════════════════════════════════════════════════

def test_token_overlap_match():
    print("\n[8] Token Overlap Match")
    check(_token_overlap_match("google browser", "google chrome") > 0.5, "google browser→google chrome")
    check(_token_overlap_match("mozilla firefox browser", "mozilla firefox") > 0.6, "3 tokens→2 tokens overlap")
    check(_token_overlap_match("completely different", "chrome") == 0.0, "no overlap")


# ══════════════════════════════════════════════════════════════════════════════
# 9. fuzzy_resolve Integration
# ══════════════════════════════════════════════════════════════════════════════

# The app registry from L3_application.py
APP_NAMES = [
    "chrome", "google chrome", "firefox", "edge", "brave", "opera", "opera browser",
    "discord", "slack", "telegram", "zoom",
    "vscode", "visual studio code", "vs code", "notepad++", "npp",
    "steam", "epic", "gog", "spotify", "vlc", "obs",
    "photoshop", "adobe photoshop", "adobe illustrator", "adobe lightroom",
    "illustrator", "premiere pro",
    "word", "excel", "powerpoint", "outlook",
    "notepad", "calc", "calculator", "paint", "cmd", "powershell", "terminal",
    "explorer", "file explorer", "windows explorer",
    "sublime", "sublime text", "intellij", "pycharm",
    "blender", "gimp", "audacity",
]


def test_fuzzy_resolve_typo():
    print("\n[9] fuzzy_resolve — Typos")
    r = fuzzy_best("chrme", APP_NAMES)
    check(r is not None and r.candidate == "chrome", "chrme→chrome")

    r = fuzzy_best("firfox", APP_NAMES)
    check(r is not None and r.candidate == "firefox", "firfox→firefox")

    r = fuzzy_best("spotfy", APP_NAMES)
    check(r is not None and r.candidate == "spotify", "spotfy→spotify")


def test_fuzzy_resolve_abbreviation():
    print("\n[10] fuzzy_resolve — Abbreviations")
    r = fuzzy_best("vscode", APP_NAMES)
    check(r is not None, "vscode→found")

    r = fuzzy_best("npp", APP_NAMES)
    check(r is not None and r.candidate == "npp", "npp→npp (exact alias)")


def test_fuzzy_resolve_partial():
    print("\n[11] fuzzy_resolve — Partial Names")
    r = fuzzy_best("fire", APP_NAMES)
    check(r is not None and "firefox" in r.candidate, "fire→firefox")

    r = fuzzy_best("visual studio", APP_NAMES)
    check(r is not None, "visual studio→found")


def test_fuzzy_resolve_exact():
    print("\n[12] fuzzy_resolve — Exact Match")
    r = fuzzy_best("chrome", APP_NAMES)
    check(r is not None and r.confidence == 1.0, "chrome→chrome (exact)")

    r = fuzzy_best("spotify", APP_NAMES)
    check(r is not None and r.confidence == 1.0, "spotify→spotify (exact)")


def test_fuzzy_resolve_no_match():
    print("\n[13] fuzzy_resolve — No Match")
    r = fuzzy_best("xyzzy123", APP_NAMES)
    check(r is None, "xyzzy123→no match")

    r = fuzzy_best("", APP_NAMES)
    check(r is None, "empty→no match")


def test_fuzzy_resolve_multiple_results():
    print("\n[14] fuzzy_resolve — Multiple Results")
    results = fuzzy_resolve("adobe", APP_NAMES, max_results=5)
    check(len(results) >= 2, f"adobe→{len(results)} matches (expected >=2)")
    check(any("adobe" in r.candidate for r in results), "at least one 'adobe' in results")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_levenshtein()
    test_normalize()
    test_exact_match()
    test_prefix_match()
    test_abbreviation_match()
    test_substring_match()
    test_levenshtein_match()
    test_token_overlap_match()
    test_fuzzy_resolve_typo()
    test_fuzzy_resolve_abbreviation()
    test_fuzzy_resolve_partial()
    test_fuzzy_resolve_exact()
    test_fuzzy_resolve_no_match()
    test_fuzzy_resolve_multiple_results()
    print("\n✅ All fuzzy_match tests passed!")
