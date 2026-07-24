"""OWASP Top 10 for Agentic Applications (2026) — Formal Mapping.

Per MAY_FINAL_ARCHITECTURE.md Part 5 (Immune System):

Maps May's risk tiers and security controls to the OWASP Top 10
for Agentic Applications. This provides a formal security framework
for evaluating May's defenses against known attack vectors.

Reference: Microsoft Agent Governance Toolkit, OWASP Agentic Security (Dec 2025)
"""

from __future__ import annotations

import logging

logger = logging.getLogger("may.system.owasp_mapping")


# ── OWASP Top 10 for Agentic Applications (2026) ──────────────────────

OWASP_CATEGORIES = {
    "A01": {
        "name": "Tool Misuse & Exploitation",
        "description": "Crafted input tricks the agent into calling destructive tools or misuse capabilities.",
        "attack_examples": [
            "User (or injected content) requests format_disk",
            "Prompt injection causes agent to send email with sensitive data",
            "Nested tool calls chain to escalate privileges",
        ],
        "may_mitigations": [
            "Risk tier classification (SAFE/MODERATE/DESTRUCTIVE/CRITICAL)",
            "Confirmation gates for DESTRUCTIVE and CRITICAL actions",
            "System process protection guard (never kill explorer, svchost, etc.)",
            "Input sanitization (_sanitize_http_args)",
            "Rate limiting on voice endpoints",
        ],
        "risk_tiers_affected": ["destructive", "critical"],
        "controls_active": True,
    },
    "A02": {
        "name": "Identity & Privilege Abuse",
        "description": "Agent runs with more access than needed, enabling privilege escalation.",
        "attack_examples": [
            "Agent process runs as SYSTEM instead of user-level",
            "Tool calls escalate to TrustedInstaller without authorization",
            "Remote control bypasses PIN authentication",
        ],
        "may_mitigations": [
            "User-level process (not SYSTEM by default)",
            "Privilege escalation requires explicit user action",
            "PIN-based remote control authentication",
            "DPAPI encryption tied to user account",
        ],
        "risk_tiers_affected": ["critical"],
        "controls_active": True,
    },
    "A03": {
        "name": "Memory & Context Poisoning",
        "description": "Slowly shifting 'normal' behavior to smuggle bad actions past defenses.",
        "attack_examples": [
            "Repeated benign requests train behavioral profile to accept destructive ones",
            "Injected content in conversation history shifts context",
            "Shadow learner records malicious patterns as 'normal'",
        ],
        "may_mitigations": [
            "CRITICAL actions always require confirmation (never bypassed by profile)",
            "Behavioral profile updates are logged with drift visibility",
            "MemoryInjector treats all external text as DATA, never instructions",
            "Audit log provides tamper-evident trail of all actions",
        ],
        "risk_tiers_affected": ["destructive", "critical"],
        "controls_active": True,
    },
    "A04": {
        "name": "Agent Goal Hijack",
        "description": "Injected content in screenshots/clipboard changes the agent's objective.",
        "attack_examples": [
            "Malicious website shows text that hijacks screen watcher",
            "Clipboard contains prompt injection targeting LLM",
            "OCR text from screen injected as instructions",
        ],
        "may_mitigations": [
            "Screen watcher treats OCR text as DATA, never as instructions",
            "Clipboard text is sanitized before LLM processing",
            "Vision model output is treated as description, not command",
            "MemoryInjector does not execute text from screen context",
        ],
        "risk_tiers_affected": ["moderate", "destructive"],
        "controls_active": True,
    },
    "A05": {
        "name": "Rogue Agents",
        "description": "Self-healing mechanisms resist the legitimate user's control.",
        "attack_examples": [
            "Agent restarts itself after user tries to stop it",
            "Health monitor auto-restarts daemon against user wishes",
            "Ghost mode executes tasks user didn't actually request",
        ],
        "may_mitigations": [
            "Kill switch available (privacy mode stops all intelligence)",
            "Ghost mode requires explicit user queueing",
            "Daemon health check can be disabled",
            "Control modes allow user to restrict agent autonomy",
        ],
        "risk_tiers_affected": ["moderate"],
        "controls_active": True,
    },
    "A06": {
        "name": "Supply Chain Attacks",
        "description": "Compromised dependencies or plugins inject malicious behavior.",
        "attack_examples": [
            "Malicious Ollama model contains hidden instructions",
            "Plugin system loads code with backdoor",
            "pip package update introduces keylogger",
        ],
        "may_mitigations": [
            "Plugin sandboxing (tools only, no arbitrary code execution)",
            "Local-first architecture (no cloud dependency)",
            "DPAPI encryption protects keys even if filesystem is compromised",
            "Audit log detects unexpected tool executions",
        ],
        "risk_tiers_affected": ["moderate", "destructive", "critical"],
        "controls_active": True,
    },
    "A07": {
        "name": "Data Leakage",
        "description": "Agent exfiltrates sensitive data through tool calls or responses.",
        "attack_examples": [
            "send_email tool used to exfiltrate files",
            "Web search sends sensitive queries to external APIs",
            "Memory store contains PII accessible via API",
        ],
        "may_mitigations": [
            "send_email classified as DESTRUCTIVE (requires confirmation)",
            "Web search queries are sanitized",
            "Memory store is local-only (LanceDB + SQLite)",
            "No cloud telemetry or analytics by default",
        ],
        "risk_tiers_affected": ["destructive"],
        "controls_active": True,
    },
    "A08": {
        "name": "Inadequate Audit & Logging",
        "description": "Actions are not logged, making incidents undetectable.",
        "attack_examples": [
            "Tool executions happen without audit trail",
            "Logs can be tampered with to hide malicious activity",
            "No integrity verification on audit entries",
        ],
        "may_mitigations": [
            "Hash-chain audit log (SHA-256 tamper-evident)",
            "verify_integrity() checks entire chain",
            "Every tool execution logged with params, result, risk tier",
            "Audit log append-only (JSONL format)",
        ],
        "risk_tiers_affected": ["safe", "moderate", "destructive", "critical"],
        "controls_active": True,
    },
    "A09": {
        "name": "Insufficient Human Oversight",
        "description": "Agent operates without adequate human-in-the-loop controls.",
        "attack_examples": [
            "Destructive actions execute without confirmation",
            "No way to pause or restrict agent autonomy",
            "Agent makes decisions user never approved",
        ],
        "may_mitigations": [
            "4 control modes (observe_only, ask_before_action, background, takeover)",
            "Confirmation flow for destructive/critical actions",
            "Pending tool calls saved for user review",
            "Privacy mode pauses all intelligence modules",
        ],
        "risk_tiers_affected": ["destructive", "critical"],
        "controls_active": True,
    },
    "A10": {
        "name": "Insecure Configuration",
        "description": "Default configurations expose attack surface.",
        "attack_examples": [
            "Remote control accessible without authentication",
            "API keys stored in plaintext",
            "Debug endpoints exposed in production",
        ],
        "may_mitigations": [
            "PIN-based remote control auth",
            "DPAPI encryption for API keys",
            "Health check endpoint uses cached results (no debug exposure)",
            "Ollama env vars configured for security (not just performance)",
        ],
        "risk_tiers_affected": ["moderate"],
        "controls_active": True,
    },
}


def get_owasp_mapping() -> dict:
    """Get the full OWASP Top 10 mapping for May's security controls."""
    return OWASP_CATEGORIES


def get_owasp_summary() -> dict:
    """Get a summary of OWASP coverage — how many categories are mitigated."""
    total = len(OWASP_CATEGORIES)
    mitigated = sum(1 for cat in OWASP_CATEGORIES.values() if cat["controls_active"])
    return {
        "total_categories": total,
        "mitigated": mitigated,
        "coverage_percent": round(mitigated / total * 100, 1),
        "categories": {
            k: {
                "name": v["name"],
                "mitigated": v["controls_active"],
                "controls_count": len(v["may_mitigations"]),
            }
            for k, v in OWASP_CATEGORIES.items()
        },
    }


def check_action_owasp(tool_name: str, risk_tier: str) -> list[dict]:
    """Check which OWASP categories are relevant for a given tool action.

    Returns list of relevant OWASP categories with their mitigations.
    """
    relevant = []
    for cat_id, cat in OWASP_CATEGORIES.items():
        if risk_tier in cat["risk_tiers_affected"]:
            relevant.append({
                "category": cat_id,
                "name": cat["name"],
                "mitigations": cat["may_mitigations"],
            })
    return relevant
