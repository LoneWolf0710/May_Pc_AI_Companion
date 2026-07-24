"""Audit Log — Tamper-evident hash-chain log for tool executions.

Per MAY_FINAL_ARCHITECTURE.md Part 5 (Immune System):

Every tool execution is logged with a SHA-256 hash chain:
- Each entry includes the hash of the previous entry
- Tampering with any entry breaks the chain
- verify_integrity() checks the entire chain for modifications

This creates accountability for all actions May takes on the user's system.

Storage: ~/.may/audit_log.jsonl (append-only JSON Lines format)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger("may.system.audit_log")

_AUDIT_DIR = Path(os.path.expanduser("~")) / ".may"
_AUDIT_FILE = _AUDIT_DIR / "audit_log.jsonl"
_AUDIT_MAX_SIZE = 10 * 1024 * 1024  # 10MB — rotate when exceeded

# In-memory cache of the last hash for fast chain updates
_last_hash: str | None = None

# Serializes the read-modify-write of the hash chain. The FastAPI backend is
# multi-threaded, so without this lock concurrent log_action() calls race on
# _last_hash + file append and corrupt the chain (every entry gets "genesis").
_write_lock = threading.Lock()


def _ensure_dir():
    """Create the audit log directory."""
    _AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _rotate_if_needed():
    """Archive the audit log to .old when it exceeds _AUDIT_MAX_SIZE."""
    global _last_hash
    if not _AUDIT_FILE.exists():
        return
    try:
        size = _AUDIT_FILE.stat().st_size
        if size >= _AUDIT_MAX_SIZE:
            old_file = _AUDIT_DIR / "audit_log.jsonl.old"
            # Remove previous .old backup if exists
            if old_file.exists():
                old_file.unlink()
            _AUDIT_FILE.rename(old_file)
            _last_hash = None  # Reset chain cache
            logger.info(
                "Audit log rotated: %d bytes → audit_log.jsonl.old",
                size,
            )
    except OSError as e:
        logger.warning("Failed to rotate audit log: %s", e)


def _compute_hash(entry: dict) -> str:
    """Compute SHA-256 hash of an audit entry (excluding the hash field itself)."""
    # Remove hash field if present to avoid circular reference
    entry_copy = {k: v for k, v in entry.items() if k != "hash"}
    serialized = json.dumps(entry_copy, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _load_last_hash() -> str | None:
    """Load the last hash from the audit log file."""
    global _last_hash
    if _last_hash is not None:
        return _last_hash

    if not _AUDIT_FILE.exists():
        _last_hash = "genesis"
        return _last_hash

    try:
        # Read the last line of the file
        with open(_AUDIT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if lines:
                last_entry = json.loads(lines[-1])
                _last_hash = last_entry.get("hash", "genesis")
            else:
                _last_hash = "genesis"
    except (json.JSONDecodeError, OSError):
        _last_hash = "genesis"

    return _last_hash


def log_action(
    action: str,
    params: dict,
    result: str,
    risk_tier: str = "safe",
    provider: str = "",
    model: str = "",
    user_message: str = "",
    latency_ms: float = 0,
) -> dict:
    """Log a tool execution to the tamper-evident audit trail.

    Args:
        action: Tool/action name (e.g. "open_app", "set_volume", "type_text")
        params: Tool parameters dict
        result: Execution result string (success/error description)
        risk_tier: Risk classification (safe/moderate/destructive/critical)
        provider: LLM provider that requested this action
        model: LLM model that requested this action
        user_message: Original user message that triggered this action
        latency_ms: Execution latency in milliseconds

    Returns:
        The logged entry dict with hash
    """
    global _last_hash
    with _write_lock:
        _ensure_dir()
        _rotate_if_needed()  # Auto-rotate when log exceeds 10MB
        prev_hash = _load_last_hash()

        entry = {
            "timestamp": time.time(),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "action": action,
            "params": params,
            "result": result,
            "risk_tier": risk_tier,
            "provider": provider,
            "model": model,
            "user_message": user_message[:500],  # Truncate long messages
            "latency_ms": round(latency_ms, 1),
            "prev_hash": prev_hash,
        }

        # Compute hash AFTER setting prev_hash
        entry["hash"] = _compute_hash(entry)

        # Append to file
        try:
            with open(_AUDIT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            _last_hash = entry["hash"]
        except OSError as e:
            logger.warning("Failed to write audit log: %s", e)

        return entry


def verify_integrity() -> tuple[bool, list[str]]:
    """Verify the integrity of the entire audit log chain.

    Returns:
        Tuple of (is_valid, list_of_violations)
        - is_valid: True if no tampering detected
        - violations: List of human-readable violation descriptions
    """
    if not _AUDIT_FILE.exists():
        return True, []

    try:
        with open(_AUDIT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        return False, [f"Failed to read audit log: {e}"]

    violations = []
    prev_expected = "genesis"

    for i, line in enumerate(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            violations.append(f"Entry {i}: invalid JSON")
            continue

        # Check prev_hash chain
        entry_prev = entry.get("prev_hash", "")
        if entry_prev != prev_expected:
            violations.append(
                f"Entry {i} (action={entry.get('action', '?')}): "
                f"prev_hash mismatch (expected {prev_expected[:16]}..., got {entry_prev[:16]}...)"
            )

        # Verify entry's own hash
        computed_hash = _compute_hash(entry)
        stored_hash = entry.get("hash", "")
        if computed_hash != stored_hash:
            violations.append(
                f"Entry {i} (action={entry.get('action', '?')}): "
                f"hash mismatch (entry was modified)"
            )

        # Update expected prev_hash for next entry
        prev_expected = entry.get("hash", "")

    return len(violations) == 0, violations


def get_entries(
    limit: int = 100,
    action_filter: str = "",
    risk_filter: str = "",
    since: float = 0,
) -> list[dict]:
    """Get audit log entries with optional filters.

    Args:
        limit: Maximum entries to return (most recent first)
        action_filter: Only return entries matching this action (substring)
        risk_filter: Only return entries matching this risk tier
        since: Only return entries after this timestamp

    Returns:
        List of audit entries, most recent first
    """
    if not _AUDIT_FILE.exists():
        return []

    try:
        with open(_AUDIT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []

    entries = []
    for line in reversed(lines):  # Most recent first
        if len(entries) >= limit:
            break
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Apply filters
        if action_filter and action_filter not in entry.get("action", ""):
            continue
        if risk_filter and entry.get("risk_tier", "") != risk_filter:
            continue
        if since and entry.get("timestamp", 0) < since:
            continue

        entries.append(entry)

    return entries


def get_stats() -> dict:
    """Get audit log statistics."""
    if not _AUDIT_FILE.exists():
        return {
            "total_entries": 0,
            "integrity_valid": True,
            "violations": [],
            "actions": {},
            "risk_tiers": {},
        }

    try:
        with open(_AUDIT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return {"total_entries": 0, "error": "failed to read"}

    total = len(lines)
    actions = {}
    risk_tiers = {}

    for line in lines:
        try:
            entry = json.loads(line)
            action = entry.get("action", "unknown")
            risk = entry.get("risk_tier", "unknown")
            actions[action] = actions.get(action, 0) + 1
            risk_tiers[risk] = risk_tiers.get(risk, 0) + 1
        except json.JSONDecodeError:
            continue

    is_valid, violations = verify_integrity()

    return {
        "total_entries": total,
        "integrity_valid": is_valid,
        "violations": violations,
        "actions": dict(sorted(actions.items(), key=lambda x: -x[1])),
        "risk_tiers": risk_tiers,
    }


def clear_log(keep_last_n: int = 0) -> dict:
    """Clear the audit log.

    Args:
        keep_last_n: If > 0, keep the last N entries (for audit continuity)

    Returns:
        Dict with clearance results
    """
    if not _AUDIT_FILE.exists():
        return {"cleared": 0}

    try:
        with open(_AUDIT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        total = len(lines)

        if keep_last_n > 0:
            # Keep last N entries and re-chain them
            kept_lines = lines[-keep_last_n:]
            # Reset the chain — first kept entry's prev_hash becomes "genesis"
            if kept_lines:
                first_entry = json.loads(kept_lines[0])
                first_entry["prev_hash"] = "genesis"
                first_entry["hash"] = _compute_hash(first_entry)
                kept_lines[0] = json.dumps(first_entry) + "\n"

                # Re-chain remaining entries
                prev_hash = first_entry["hash"]
                for i in range(1, len(kept_lines)):
                    entry = json.loads(kept_lines[i])
                    entry["prev_hash"] = prev_hash
                    entry["hash"] = _compute_hash(entry)
                    kept_lines[i] = json.dumps(entry) + "\n"
                    prev_hash = entry["hash"]

            with open(_AUDIT_FILE, "w", encoding="utf-8") as f:
                f.writelines(kept_lines)
            global _last_hash
            _last_hash = None  # Reset cache
        else:
            _AUDIT_FILE.unlink()
            _last_hash = None

        return {"cleared": total - keep_last_n, "kept": keep_last_n}
    except OSError as e:
        return {"error": str(e)}
