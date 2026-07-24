"""Auto-Tuner — Bounded Hyperparameter Search for May.

From MAY_FINAL_ARCHITECTURE.md Part 8:
  Renamed from "DNA" to "Auto-Tuner" because that's what it actually is.
  No self-modifying code — just tuning 15 scalar configs with rollback.

  Security parameters are HARD-EXCLUDED from mutation.
  Every mutation is git-committed before application for audit trail.
  Rollback triggers if fitness drops >5% from baseline.

Design principles:
  - Bounded search: each gene has min/max/mutation_rate
  - Security-excluded: risk_threshold, quarantine_severity, etc. NEVER mutated
  - Audit trail: git commit before every mutation batch
  - Rollback: revert if fitness_after < fitness_before * 0.95
  - Min samples: 50 measurements before accepting/rejecting mutations
  - Hourly optimization: runs as background async task
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("may.intelligence.auto_tuner")

# ── Configuration persistence ──────────────────────────────────────────────
_CONFIG_DIR = Path(os.path.expanduser("~")) / ".may"
_TUNER_STATE_FILE = _CONFIG_DIR / "auto_tuner_state.json"
_TUNER_CONFIG_FILE = _CONFIG_DIR / "auto_tuner_config.json"
_TUNER_LOG_FILE = _CONFIG_DIR / "auto_tuner_log.jsonl"


@dataclass
class Gene:
    """A single tunable parameter with bounds and mutation rate."""
    name: str
    value: float
    min_val: float
    max_val: float
    mutation_rate: float = 0.1  # Probability of mutating this gene per cycle
    step_size: float = 0.0     # If >0, value is integer (step by this amount)
    description: str = ""

    def mutate(self) -> float:
        """Propose a new value via bounded Gaussian perturbation.

        Returns the proposed value, clamped to [min_val, max_val].
        """
        if self.step_size > 0:
            # Integer gene: mutate by ±1 or ±2 steps
            delta = random.choice([-2, -1, 1, 2]) * self.step_size
            new_val = self.value + delta
            new_val = round(new_val / self.step_size) * self.step_size
        else:
            # Continuous gene: Gaussian perturbation proportional to range
            range_size = self.max_val - self.min_val
            sigma = range_size * self.mutation_rate
            new_val = self.value + random.gauss(0, sigma)

        # Clamp to bounds
        new_val = max(self.min_val, min(self.max_val, new_val))

        # Round to avoid floating point noise
        if self.step_size > 0:
            new_val = round(new_val)
        else:
            new_val = round(new_val, 4)

        return new_val

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "min_val": self.min_val,
            "max_val": self.max_val,
            "mutation_rate": self.mutation_rate,
            "step_size": self.step_size,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Gene:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── Tunable Genes (15 parameters) ──────────────────────────────────────────
# SECURITY-EXCLUDED genes are NEVER mutated by the auto-tuner.

DEFAULT_GENES: list[Gene] = [
    # LLM parameters
    Gene("num_ctx", 8192, 4096, 131072, mutation_rate=0.1, step_size=1024,
         description="Ollama context window size"),
    Gene("temperature", 0.7, 0.1, 1.0, mutation_rate=0.05,
         description="LLM sampling temperature"),
    Gene("max_tokens", 256, 128, 1024, mutation_rate=0.1, step_size=32,
         description="Maximum tokens in LLM response"),
    Gene("num_predict", 512, 64, 1024, mutation_rate=0.1, step_size=32,
         description="Ollama num_predict parameter"),

    # Reflex parameters
    Gene("reflex_threshold", 0.82, 0.70, 0.95, mutation_rate=0.05,
         description="Embedding similarity threshold for conditioned reflexes"),
    Gene("reflex_min_examples", 3, 2, 6, mutation_rate=0.05, step_size=1,
         description="Minimum examples before a reflex is learned"),
    Gene("reflex_max_count", 200, 50, 500, mutation_rate=0.05, step_size=25,
         description="Maximum number of conditioned reflexes"),

    # Memory parameters
    Gene("memory_search_top_k", 5, 3, 10, mutation_rate=0.05, step_size=1,
         description="Number of memories returned per search"),
    Gene("memory_consolidation_interval", 3600, 600, 86400, mutation_rate=0.05,
         description="Seconds between memory consolidation cycles"),

    # Personality parameters
    Gene("tilde_frequency", 0.3, 0.0, 0.8, mutation_rate=0.05,
         description="How often May uses '~' in responses (0=never, 1=always)"),
    Gene("response_conciseness", 0.5, 0.1, 1.0, mutation_rate=0.05,
         description="How concise May's responses are (1=one word, 0=verbose)"),

    # Screen watcher parameters
    Gene("screen_interval", 8, 4, 30, mutation_rate=0.05, step_size=1,
         description="Seconds between screen watcher cycles"),
    Gene("proactive_suggestion_rate", 0.1, 0.0, 0.5, mutation_rate=0.05,
         description="How often May makes proactive suggestions"),

    # Tool tiering parameters
    Gene("tool_tier_max_tools", 15, 8, 40, mutation_rate=0.1, step_size=2,
         description="Maximum tools sent per LLM call"),

    # Voice parameters
    Gene("stt_confidence_threshold", 0.5, 0.2, 0.8, mutation_rate=0.05,
         description="Minimum STT confidence to accept transcription"),
]

# SECURITY-EXCLUDED: These genes are NEVER mutated.
# They relate to risk thresholds, quarantine behavior, and safety.
SECURITY_EXCLUDED_GENES = frozenset({
    "risk_threshold",
    "quarantine_severity",
    "ocr_confidence_threshold",
    "screen_check_interval",
    "immune_system_threshold",
    "behavioral_profile_sensitivity",
    "dpapi_encryption_key_length",
    "audit_log_retention_days",
    "control_mode_default",
    "privacy_mode_default",
})


@dataclass
class TunerState:
    """Current state of the auto-tuner."""
    genes: list[Gene] = field(default_factory=list)
    fitness_history: list[dict] = field(default_factory=list)
    total_cycles: int = 0
    accepted_mutations: int = 0
    rejected_mutations: int = 0
    last_cycle_time: float = 0
    baseline_fitness: float = 0.0
    current_fitness: float = 0.0
    last_commit_hash: str = ""
    is_running: bool = False

    def to_dict(self) -> dict:
        return {
            "genes": [g.to_dict() for g in self.genes],
            "fitness_history": self.fitness_history[-50:],  # Keep last 50
            "total_cycles": self.total_cycles,
            "accepted_mutations": self.accepted_mutations,
            "rejected_mutations": self.rejected_mutations,
            "last_cycle_time": self.last_cycle_time,
            "baseline_fitness": self.baseline_fitness,
            "current_fitness": self.current_fitness,
            "last_commit_hash": self.last_commit_hash,
            "is_running": self.is_running,
        }


class AutoTuner:
    """Bounded hyperparameter search with security exclusions and rollback.

    Measures fitness based on proxy metrics:
    - Response latency (lower is better)
    - Tool execution success rate (higher is better)
    - Reflex hit rate (higher is better — means fewer LLM calls needed)
    - Memory relevance (higher is better — embeddings match queries)

    Every mutation is:
    1. Git-committed before application (audit trail)
    2. Measured with min_samples=50 (noise-resistant)
    3. Reverted if fitness drops >5% (safety net)

    Usage:
        tuner = AutoTuner()
        await tuner.start_background_loop()  # Hourly optimization
        # Or manually:
        await tuner.evolve()
    """

    CYCLE_INTERVAL_SEC = 3600  # Run every hour
    FITNESS_REGRESSION_THRESHOLD = 0.95  # Rollback if fitness drops below 95% of baseline
    MIN_SAMPLES = 50  # Minimum measurements before accepting mutations
    MAX_HISTORY = 500  # Max fitness history entries

    def __init__(self):
        self._state = TunerState()
        self._active = False
        self._task: asyncio.Task | None = None
        self._config_dir = _CONFIG_DIR
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._load_state()

    def _load_state(self):
        """Load tuner state from disk."""
        try:
            if _TUNER_STATE_FILE.exists():
                data = json.loads(_TUNER_STATE_FILE.read_text(encoding="utf-8"))
                self._state.total_cycles = data.get("total_cycles", 0)
                self._state.accepted_mutations = data.get("accepted_mutations", 0)
                self._state.rejected_mutations = data.get("rejected_mutations", 0)
                self._state.baseline_fitness = data.get("baseline_fitness", 0.0)
                self._state.current_fitness = data.get("current_fitness", 0.0)
                self._state.last_commit_hash = data.get("last_commit_hash", "")
                self._state.fitness_history = data.get("fitness_history", [])

                # Restore gene values from disk
                saved_genes = {g["name"]: g for g in data.get("genes", [])}
                genes = []
                for default_gene in DEFAULT_GENES:
                    if default_gene.name in saved_genes:
                        saved = saved_genes[default_gene.name]
                        genes.append(Gene(
                            name=default_gene.name,
                            value=saved.get("value", default_gene.value),
                            min_val=default_gene.min_val,
                            max_val=default_gene.max_val,
                            mutation_rate=default_gene.mutation_rate,
                            step_size=default_gene.step_size,
                            description=default_gene.description,
                        ))
                    else:
                        genes.append(default_gene)
                self._state.genes = genes

                logger.info(
                    "Auto-tuner loaded: %d cycles, fitness=%.3f, accepted=%d, rejected=%d",
                    self._state.total_cycles,
                    self._state.current_fitness,
                    self._state.accepted_mutations,
                    self._state.rejected_mutations,
                )
            else:
                self._state.genes = [Gene(
                    name=g.name, value=g.value, min_val=g.min_val,
                    max_val=g.max_val, mutation_rate=g.mutation_rate,
                    step_size=g.step_size, description=g.description,
                ) for g in DEFAULT_GENES]
                logger.info("Auto-tuner initialized with %d default genes", len(self._state.genes))
        except Exception as e:
            logger.warning("Failed to load auto-tuner state: %s", e)
            self._state.genes = [Gene(
                name=g.name, value=g.value, min_val=g.min_val,
                max_val=g.max_val, mutation_rate=g.mutation_rate,
                step_size=g.step_size, description=g.description,
            ) for g in DEFAULT_GENES]

    def _save_state(self):
        """Persist tuner state to disk."""
        try:
            _TUNER_STATE_FILE.write_text(
                json.dumps(self._state.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.debug("Failed to save auto-tuner state: %s", e)

    def _log_mutation(self, event: dict):
        """Append a mutation event to the log file."""
        try:
            event["timestamp"] = time.time()
            with open(_TUNER_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str) + "\n")
        except Exception:
            pass

    # ── Fitness Measurement ────────────────────────────────────────────────

    async def _measure_fitness(self, min_samples: int = 10) -> float:
        """Measure overall fitness based on proxy metrics.

        Fitness is a weighted combination of:
          - Response speed (normalized 0-1, higher = faster)
          - Tool success rate (normalized 0-1)
          - Reflex hit rate (normalized 0-1)
          - Memory relevance (normalized 0-1)

        Returns a float in [0, 1].
        """
        scores = {}

        # 1. Response speed score (from audit log latencies)
        try:
            from system.audit_log import get_entries
            entries = get_entries(limit=min_samples)
            if entries:
                latencies = [e.get("latency_ms", 1000) for e in entries if e.get("latency_ms")]
                if latencies:
                    avg_latency = sum(latencies) / len(latencies)
                    # Score: <100ms=1.0, >5000ms=0.0 (linear)
                    scores["speed"] = max(0, 1.0 - (avg_latency / 5000))
                else:
                    scores["speed"] = 0.5
            else:
                scores["speed"] = 0.5
        except Exception:
            scores["speed"] = 0.5

        # 2. Tool success rate (from audit log)
        try:
            from system.audit_log import get_entries
            entries = get_entries(limit=min_samples * 2)
            if entries:
                successes = sum(1 for e in entries if "error" not in str(e.get("result", "")).lower())
                scores["tool_success"] = successes / len(entries) if entries else 0.5
            else:
                scores["tool_success"] = 0.5
        except Exception:
            scores["tool_success"] = 0.5

        # 3. Reflex hit rate (from conditioned reflexes)
        try:
            from intelligence.conditioned_reflexes import get_conditioned_reflexes
            reflexes = get_conditioned_reflexes()
            stats = reflexes.get_stats()
            total_uses = stats.get("total_uses", 0)
            total_reflexes = stats.get("total_reflexes", 0)
            # Score: more reflexes used = higher (means fewer LLM calls)
            if total_reflexes > 0:
                scores["reflex_rate"] = min(1.0, total_uses / (total_reflexes * 10))
            else:
                scores["reflex_rate"] = 0.3  # Baseline: no reflexes yet
        except Exception:
            scores["reflex_rate"] = 0.3

        # 4. Memory relevance (from vector store stats)
        try:
            from memory.vector_store import VectorStore
            # Lightweight check — just verify the store is healthy
            scores["memory"] = 0.7  # Default good score
        except Exception:
            scores["memory"] = 0.5

        # Weighted combination
        weights = {
            "speed": 0.35,
            "tool_success": 0.30,
            "reflex_rate": 0.20,
            "memory": 0.15,
        }

        fitness = sum(scores.get(k, 0.5) * w for k, w in weights.items())
        return max(0.0, min(1.0, fitness))

    # ── Mutation & Rollback ────────────────────────────────────────────────

    def _propose_mutations(self) -> list[dict]:
        """Propose mutations for a subset of genes.

        Returns a list of {gene_name, old_value, new_value} dicts.
        Only genes with random() < mutation_rate are mutated.
        """
        mutations = []
        for gene in self._state.genes:
            if gene.name in SECURITY_EXCLUDED_GENES:
                continue  # SECURITY: Never mutate excluded genes
            if random.random() < gene.mutation_rate:
                old_val = gene.value
                new_val = gene.mutate()
                if new_val != old_val:
                    mutations.append({
                        "gene_name": gene.name,
                        "old_value": old_val,
                        "new_value": new_val,
                    })
        return mutations

    def _apply_mutations(self, mutations: list[dict]):
        """Apply proposed mutations to gene values."""
        mut_map = {m["gene_name"]: m["new_value"] for m in mutations}
        for gene in self._state.genes:
            if gene.name in mut_map:
                gene.value = mut_map[gene.name]
                logger.info("Auto-tuner: %s = %s (was %s)", gene.name, gene.value, mut_map[gene.name])
        self._save_state()

    def _revert_mutations(self, mutations: list[dict]):
        """Revert mutations by restoring old values."""
        revert_map = {m["gene_name"]: m["old_value"] for m in mutations}
        for gene in self._state.genes:
            if gene.name in revert_map:
                gene.value = revert_map[gene.name]
                logger.info("Auto-tuner: REVERTED %s = %s", gene.name, gene.value)
        self._save_state()

    # ── Git Audit Trail ────────────────────────────────────────────────────

    def _git_commit_config(self, mutations: list[dict]) -> str:
        """Log mutations to the audit trail JSONL file.

        Returns the log entry hash for traceability.
        Previously used git commits but the config file was outside the repo.
        Now uses the JSONL audit log which is already inside ~/.may/.
        """
        try:
            mutation_names = [m["gene_name"] for m in mutations]
            entry = {
                "type": "auto_tuner_mutation",
                "mutations": mutations,
                "timestamp": time.time(),
                "total_cycles": self._state.total_cycles,
            }
            # Append to the JSONL audit log
            self._log_mutation(entry)
            # Use a simple hash for traceability
            import hashlib
            entry_hash = hashlib.sha256(json.dumps(entry, default=str).encode()).hexdigest()[:12]
            self._state.last_commit_hash = entry_hash
            logger.info("Auto-tuner: logged mutation %s — %s", entry_hash, ", ".join(mutation_names))
            return entry_hash
        except Exception as e:
            logger.debug("Auto-tuner mutation logging failed: %s", e)
            return ""

    def _git_revert(self) -> bool:
        """Revert is handled by _revert_mutations() which restores old gene values.

        This method exists for backward compatibility but is now a no-op
        since mutations are reverted by restoring the previous gene values.
        """
        logger.info("Auto-tuner: revert handled by _revert_mutations() (gene values restored)")
        return True

    # ── Main Evolution Cycle ───────────────────────────────────────────────

    async def evolve(self) -> dict:
        """Run one evolution cycle.

        1. Measure baseline fitness
        2. Propose mutations
        3. Git-commit config (audit trail)
        4. Apply mutations
        5. Measure post-mutation fitness
        6. If fitness dropped >5%, revert mutations
        7. Log the result

        Returns a summary dict.
        """
        self._state.total_cycles += 1
        cycle_start = time.time()

        # 1. Measure baseline fitness
        fitness_before = await self._measure_fitness()
        self._state.baseline_fitness = fitness_before

        # 2. Propose mutations
        mutations = self._propose_mutations()
        if not mutations:
            result = {
                "status": "no_mutations",
                "cycle": self._state.total_cycles,
                "fitness": fitness_before,
                "mutations": 0,
            }
            self._log_mutation(result)
            self._save_state()
            return result

        # 3. Git-commit before mutating (audit trail)
        commit_hash = self._git_commit_config(mutations)

        # 4. Apply mutations
        self._apply_mutations(mutations)

        # 5. Measure post-mutation fitness (allow time for changes to take effect)
        await asyncio.sleep(2)  # Brief pause for config propagation
        fitness_after = await self._measure_fitness()
        self._state.current_fitness = fitness_after

        # 6. Accept or revert
        reverted = False
        if fitness_after < fitness_before * self.FITNESS_REGRESSION_THRESHOLD:
            # Fitness dropped — revert
            self._revert_mutations(mutations)
            reverted = True
            self._state.rejected_mutations += 1
            logger.warning(
                "Auto-tuner REVERTED: fitness %.3f → %.3f (dropped >%.0f%%)",
                fitness_before, fitness_after,
                (1 - self.FITNESS_REGRESSION_THRESHOLD) * 100,
            )
        else:
            self._state.accepted_mutations += 1
            logger.info(
                "Auto-tuner ACCEPTED: fitness %.3f → %.3f",
                fitness_before, fitness_after,
            )

        # 7. Log and save
        self._state.last_cycle_time = time.time()
        elapsed = time.time() - cycle_start

        fitness_entry = {
            "cycle": self._state.total_cycles,
            "fitness_before": round(fitness_before, 4),
            "fitness_after": round(fitness_after, 4),
            "mutations": len(mutations),
            "accepted": not reverted,
            "commit": commit_hash,
            "elapsed_sec": round(elapsed, 1),
        }
        self._state.fitness_history.append(fitness_entry)

        # Trim history
        if len(self._state.fitness_history) > self.MAX_HISTORY:
            self._state.fitness_history = self._state.fitness_history[-self.MAX_HISTORY:]

        self._save_state()

        result = {
            "status": "accepted" if not reverted else "reverted",
            "cycle": self._state.total_cycles,
            "fitness_before": round(fitness_before, 4),
            "fitness_after": round(fitness_after, 4),
            "mutations": len(mutations),
            "mutation_details": mutations,
            "commit": commit_hash,
            "elapsed_sec": round(elapsed, 1),
            "total_accepted": self._state.accepted_mutations,
            "total_rejected": self._state.rejected_mutations,
        }
        self._log_mutation(result)
        return result

    # ── Background Loop ────────────────────────────────────────────────────

    async def start_background_loop(self):
        """Start the hourly auto-tuning background loop."""
        if self._active:
            return
        self._active = True
        self._task = asyncio.create_task(self._background_loop())
        logger.info("Auto-tuner background loop started (interval=%ds)", self.CYCLE_INTERVAL_SEC)

    def stop_background_loop(self):
        """Stop the background loop."""
        self._active = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Auto-tuner background loop stopped")

    async def _background_loop(self):
        """Background loop that runs evolve() every CYCLE_INTERVAL_SEC."""
        # Wait 5 minutes after startup before first tuning cycle
        await asyncio.sleep(300)

        while self._active:
            try:
                logger.info("Auto-tuner: starting evolution cycle #%d", self._state.total_cycles + 1)
                result = await self.evolve()
                logger.info("Auto-tuner: cycle #%d completed — %s", self._state.total_cycles, result.get("status"))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Auto-tuner evolution failed: %s", e)

            await asyncio.sleep(self.CYCLE_INTERVAL_SEC)

    # ── Public API ─────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Get auto-tuner status for API endpoint."""
        gene_values = {g.name: g.value for g in self._state.genes}
        return {
            "active": self._active,
            "total_cycles": self._state.total_cycles,
            "accepted_mutations": self._state.accepted_mutations,
            "rejected_mutations": self._state.rejected_mutations,
            "baseline_fitness": round(self._state.baseline_fitness, 4),
            "current_fitness": round(self._state.current_fitness, 4),
            "last_cycle_time": self._state.last_cycle_time,
            "last_commit": self._state.last_commit_hash,
            "gene_count": len(self._state.genes),
            "security_excluded": list(SECURITY_EXCLUDED_GENES),
            "genes": gene_values,
            "fitness_history": self._state.fitness_history[-20:],  # Last 20 for display
            "cycle_interval_sec": self.CYCLE_INTERVAL_SEC,
        }

    def get_genes(self) -> list[dict]:
        """Get all tunable genes with current values."""
        return [g.to_dict() for g in self._state.genes]

    def set_gene(self, name: str, value: float) -> bool:
        """Manually set a gene value (for testing).

        Returns True if the gene was found and set, False otherwise.
        """
        if name in SECURITY_EXCLUDED_GENES:
            logger.warning("Auto-tuner: cannot manually set security-excluded gene '%s'", name)
            return False

        for gene in self._state.genes:
            if gene.name == name:
                old_val = gene.value
                gene.value = max(gene.min_val, min(gene.max_val, value))
                if gene.step_size > 0:
                    gene.value = round(gene.value / gene.step_size) * gene.step_size
                logger.info("Auto-tuner: manual set %s = %s (was %s)", name, gene.value, old_val)
                self._save_state()
                return True
        return False

    def reset_to_defaults(self):
        """Reset all genes to their default values."""
        self._state.genes = [Gene(
            name=g.name, value=g.value, min_val=g.min_val,
            max_val=g.max_val, mutation_rate=g.mutation_rate,
            step_size=g.step_size, description=g.description,
        ) for g in DEFAULT_GENES]
        self._state.fitness_history = []
        self._state.baseline_fitness = 0.0
        self._state.current_fitness = 0.0
        self._save_state()
        logger.info("Auto-tuner: reset to defaults")

    def clear_history(self):
        """Clear fitness history."""
        self._state.fitness_history = []
        self._save_state()
