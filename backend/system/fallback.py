"""
Fallback Chain Engine — DEPRECATED RE-EXPORT.

The canonical implementations live in:
  core/engine/fallback.py   — FallbackChain
  core/engine/verifier.py   — Verifiers, VERIFIER_MAP
  core/engine/transaction.py — Transaction, Step

This module re-exports them for backward compatibility.
New code should import directly from core.engine.*.
"""

from core.engine.fallback import FallbackChain
from core.engine.verifier import Verifiers, VERIFIER_MAP, get_verifier
from core.engine.transaction import Transaction, Step

__all__ = ["FallbackChain", "Verifiers", "VERIFIER_MAP", "get_verifier", "Transaction", "Step"]
