"""Fuzzy matching for app names — resolves typos, abbreviations, and partial names.

Supports:
  - Levenshtein edit distance (pure Python, no deps)
  - Abbreviation matching ("chrm" → "chrome", "vscode" → "vs code")
  - Substring containment ("fire" → "firefox")
  - Token-based overlap ("google browser" → "google chrome")
  - Exact prefix matching ("notep" → "notepad")

Usage:
    from core.layers.fuzzy_match import fuzzy_resolve
    result = fuzzy_resolve("chrm", KNOWN_APPS.keys())
    # → "chrome"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

logger = logging.getLogger("may.core.layers.fuzzy_match")


# ══════════════════════════════════════════════════════════════════════════════
# Levenshtein Distance (pure Python, O(n*m) time, O(min(n,m)) space)
# ══════════════════════════════════════════════════════════════════════════════

def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings.

    Uses the single-row optimization (O(min(n,m)) space).
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    # Ensure a is the shorter string for space optimization
    if len(a) > len(b):
        a, b = b, a

    a_len, b_len = len(a), len(b)
    # Previous row of distances
    prev = list(range(a_len + 1))
    curr = [0] * (a_len + 1)

    for j in range(1, b_len + 1):
        curr[0] = j
        bj = b[j - 1]
        for i in range(1, a_len + 1):
            cost = 0 if a[i - 1] == bj else 1
            curr[i] = min(
                prev[i] + 1,       # deletion
                curr[i - 1] + 1,   # insertion
                prev[i - 1] + cost, # substitution
            )
        prev, curr = curr, prev

    return prev[a_len]


# ══════════════════════════════════════════════════════════════════════════════
# Normalization
# ══════════════════════════════════════════════════════════════════════════════

# Characters to strip when normalizing app names
_STRIP_CHARS = " -_+()[]{}!@#$%^&*"  # Note: '.' kept for file extensions like file.txt

def _normalize(name: str) -> str:
    """Normalize an app name for comparison.

    Strips special characters, collapses whitespace, lowercases.
    "Visual Studio Code" → "visual studio code"
    "Notepad++" → "notepad"
    "Google Chrome" → "google chrome"
    "GOG Galaxy" → "gog galaxy"
    """
    name = name.lower().strip()
    # Remove common suffixes that don't affect matching
    for suffix in (".exe", ".lnk", ".app", ".msc"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    # Strip special chars but keep spaces
    result = []
    prev_was_space = False
    for ch in name:
        if ch in _STRIP_CHARS:
            if not prev_was_space:
                result.append(" ")
                prev_was_space = True
        else:
            result.append(ch)
            prev_was_space = False
    return "".join(result).strip()


def _tokens(name: str) -> list[str]:
    """Split a normalized name into tokens."""
    return _normalize(name).split()


# ══════════════════════════════════════════════════════════════════════════════
# Matching Strategies (each returns a confidence 0.0–1.0, or 0 for no match)
# ══════════════════════════════════════════════════════════════════════════════

def _exact_match(query: str, candidate: str) -> float:
    """Exact match after normalization. Returns 1.0 or 0.0."""
    if _normalize(query) == _normalize(candidate):
        return 1.0
    return 0.0


def _prefix_match(query: str, candidate: str) -> float:
    """Candidate starts with query (or vice versa). Returns 0.7–0.95.

    Longer prefix overlap → higher confidence.
    """
    nq = _normalize(query)
    nc = _normalize(candidate)
    if not nq or not nc:
        return 0.0

    # Check if one is a prefix of the other
    if nc.startswith(nq):
        ratio = len(nq) / len(nc)
        return 0.7 + 0.25 * ratio  # 0.70 – 0.95
    if nq.startswith(nc):
        ratio = len(nc) / len(nq)
        return 0.6 + 0.3 * ratio  # 0.60 – 0.90
    return 0.0


def _substring_match(query: str, candidate: str) -> float:
    """Query is a substring of candidate (or vice versa). Returns 0.6–0.85.

    Used for partial names like "firefox" matching "mozilla firefox".
    """
    nq = _normalize(query)
    nc = _normalize(candidate)
    if not nq or not nc:
        return 0.0

    if nq in nc:
        ratio = len(nq) / len(nc)
        # Longer substring relative to candidate = higher confidence
        return 0.6 + 0.25 * ratio  # 0.60 – 0.85
    if nc in nq:
        ratio = len(nc) / len(nq)
        return 0.5 + 0.3 * ratio  # 0.50 – 0.80
    return 0.0


def _abbreviation_match(query: str, candidate: str) -> float:
    """Check if query is an abbreviation of candidate.

    "chrm" → "chrome" (first letters of syllables/words)
    "gimp" → "gimp" (exact, handled elsewhere)
    "vscode" → "visual studio code" (concatenated initials)

    Returns 0.65–0.90 or 0.0.
    """
    nq = _normalize(query).replace(" ", "")
    nc = _normalize(candidate).replace(" ", "")
    if not nq or not nc:
        return 0.0

    # Strategy 1: First-letter initials of each token
    cand_tokens = _tokens(candidate)
    if len(cand_tokens) >= 2:
        initials = "".join(t[0] for t in cand_tokens if t)
        if nq == initials:
            return 0.85
        # Check if query is a prefix of the initials
        if initials.startswith(nq) and len(nq) >= 2:
            return 0.70 + 0.15 * (len(nq) / len(initials))

    # Strategy 2: Token-initial subsequence
    # "vscode" → each char maps to start of token in order
    # v→visual, s→studio, code→code (full token match)
    if len(cand_tokens) >= 2 and len(nq) >= 2:
        qi = 0
        for tok in cand_tokens:
            if qi >= len(nq):
                break
            # Try to match query chars against token characters
            ti = 0
            while qi < len(nq) and ti < len(tok) and nq[qi] == tok[ti]:
                qi += 1
                ti += 1
            if ti == 0:
                break  # No chars matched this token
        if qi == len(nq):
            return 0.80  # All query chars consumed across tokens

    # Strategy 3: Syllable-based abbreviation
    # Remove vowels from candidate (except first char) and compare
    if len(nq) >= 3 and len(nc) >= 4:
        # Build a "consonant skeleton" for the candidate
        skeleton = nc[0]
        for ch in nc[1:]:
            if ch not in "aeiou":
                skeleton += ch
        if nq == skeleton:
            return 0.80
        # Levenshtein on skeleton vs query
        dist = _levenshtein(nq, skeleton)
        max_len = max(len(nq), len(skeleton))
        if max_len > 0 and dist <= max(1, max_len // 4):
            return 0.65 + 0.15 * (1 - dist / max_len)

    return 0.0


def _levenshtein_match(query: str, candidate: str) -> float:
    """Levenshtein edit distance normalized to confidence 0.0–0.95.

    Only fires for short-to-medium strings (app names are typically 2–20 chars).
    """
    nq = _normalize(query).replace(" ", "")
    nc = _normalize(candidate).replace(" ", "")

    if not nq or not nc:
        return 0.0

    # Skip for very long candidates — too many false positives
    if len(nc) > 30 or len(nq) > 20:
        return 0.0

    dist = _levenshtein(nq, nc)
    max_len = max(len(nq), len(nc))

    if max_len == 0:
        return 0.0

    # Only match if edit distance is reasonable
    # For very short names (≤3 chars): max 1 edit
    # For short names (4-7 chars): max 2 edits (handles typos like "chrm" → "chrome")
    # For medium names (8-10): max 2 edits
    # For long names (11+): max 3 edits
    max_allowed = 1 if len(nq) <= 3 else (2 if len(nq) <= 10 else 3)

    if dist > max_allowed:
        return 0.0

    # Confidence: closer edit distance → higher confidence
    # dist=0 → 0.95, dist=1 → 0.85, dist=2 → 0.75, dist=3 → 0.65
    return 0.95 - (dist * 0.10)


def _token_overlap_match(query: str, candidate: str) -> float:
    """Match based on shared tokens between query and candidate.

    "google browser" → "google chrome" (1/2 tokens match = 0.6)
    "mozilla firefox browser" → "mozilla firefox" (2/3 match = 0.7)
    Returns 0.0–0.85.
    """
    q_tokens = set(_tokens(query))
    c_tokens = set(_tokens(candidate))

    if not q_tokens or not c_tokens:
        return 0.0

    # Jaccard-like overlap
    intersection = q_tokens & c_tokens
    union = q_tokens | c_tokens

    if not intersection:
        return 0.0

    # We weight by how many query tokens matched (user intent matters more)
    query_coverage = len(intersection) / len(q_tokens)
    candidate_coverage = len(intersection) / len(c_tokens)

    # If all query tokens match at least one candidate token → high confidence
    if query_coverage >= 0.8:
        return 0.65 + 0.20 * candidate_coverage  # 0.65 – 0.85
    if query_coverage >= 0.5:
        return 0.50 + 0.15 * candidate_coverage  # 0.50 – 0.65

    return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FuzzyResult:
    """Result of a fuzzy match attempt."""
    matched: bool
    candidate: str | None = None  # The matched candidate name
    confidence: float = 0.0       # 0.0–1.0
    method: str = ""              # Which strategy matched


# All matching strategies in priority order (first high-confidence match wins)
_STRATEGIES = [
    ("exact", _exact_match),
    ("prefix", _prefix_match),
    ("abbreviation", _abbreviation_match),
    ("substring", _substring_match),
    ("levenshtein", _levenshtein_match),
    ("token_overlap", _token_overlap_match),
]


def fuzzy_resolve(
    query: str,
    candidates: Sequence[str],
    threshold: float = 0.60,
    max_results: int = 3,
) -> list[FuzzyResult]:
    """Resolve a fuzzy app name query against a list of candidates.

    Args:
        query: The user's input (e.g., "chrm", "vs code", "fire").
        candidates: Known app names to match against (e.g., KNOWN_APPS.keys()).
        threshold: Minimum confidence to consider a match (default 0.60).
        max_results: Maximum number of results to return.

    Returns:
        List of FuzzyResult sorted by confidence descending.
        Empty list if nothing matches above threshold.
    """
    if not query or not candidates:
        return []

    query_normalized = _normalize(query)
    if not query_normalized:
        return []

    scored: list[tuple[float, str, str]] = []  # (confidence, method, candidate)

    for candidate in candidates:
        if not candidate:
            continue

        # Quick exact check first
        if _normalize(candidate) == query_normalized:
            return [FuzzyResult(matched=True, candidate=candidate, confidence=1.0, method="exact")]

        # Run each strategy, take the best score per candidate
        best_score = 0.0
        best_method = ""
        for method_name, strategy_fn in _STRATEGIES:
            score = strategy_fn(query, candidate)
            if score > best_score:
                best_score = score
                best_method = method_name

        if best_score >= threshold:
            scored.append((best_score, best_method, candidate))

    # Sort by confidence descending, return top N
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for conf, method, candidate in scored[:max_results]:
        results.append(FuzzyResult(
            matched=True,
            candidate=candidate,
            confidence=conf,
            method=method,
        ))

    return results


def fuzzy_best(
    query: str,
    candidates: Sequence[str],
    threshold: float = 0.60,
) -> FuzzyResult | None:
    """Return the single best fuzzy match, or None.

    Convenience wrapper around fuzzy_resolve() for the common single-match case.
    """
    results = fuzzy_resolve(query, candidates, threshold=threshold, max_results=1)
    return results[0] if results else None
