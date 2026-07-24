/**
 * SkillsPanel — View and manage learned skills from the Skill Acquisition system.
 *
 * Shows all skills auto-created by the shadow learner, with options to
 * execute, search, and delete skills.
 */

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { BACKEND_URL } from "../config";

interface SkillStep {
  tool_name: string;
  params: Record<string, unknown>;
  description: string;
}

interface Skill {
  id: string;
  name: string;
  description: string;
  steps: SkillStep[];
  trigger_phrases: string[];
  use_count: number;
  confidence: number;
  created_at: number;
  last_used: number;
  tags: string[];
}

interface SkillsPanelProps {
  onClose: () => void;
}

export default function SkillsPanel({ onClose }: SkillsPanelProps) {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [_, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Skill[] | null>(null);
  const [executing, setExecuting] = useState<string | null>(null);
  const [executionResult, setExecutionResult] = useState<string | null>(null);

  const fetchSkills = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${BACKEND_URL}/skills`, {
        signal: AbortSignal.timeout(5000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSkills(data.skills || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load skills");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    try {
      const res = await fetch(
        `${BACKEND_URL}/skills/search?q=${encodeURIComponent(searchQuery)}`,
        { signal: AbortSignal.timeout(5000) },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSearchResults(data.skills || []);
    } catch {
      setSearchResults([]);
    }
  }, [searchQuery]);

  const handleExecute = useCallback(async (skillId: string) => {
    setExecuting(skillId);
    setExecutionResult(null);
    try {
      const res = await fetch(`${BACKEND_URL}/skills/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ skill_id: skillId }),
        signal: AbortSignal.timeout(30000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.error) {
        setExecutionResult(`Error: ${data.error}`);
      } else {
        const results = data.results || [];
        const ok = results.filter((r: { ok: boolean }) => r.ok).length;
        setExecutionResult(
          `✓ Executed '${data.skill}' — ${ok}/${results.length} steps succeeded`,
        );
        fetchSkills(); // Refresh to update use_count
      }
    } catch (err) {
      setExecutionResult(`Error: ${err instanceof Error ? err.message : "Unknown"}`);
    } finally {
      setExecuting(null);
    }
  }, [fetchSkills]);

  const handleDelete = useCallback(
    async (skillId: string) => {
      try {
        await fetch(`${BACKEND_URL}/skills/${skillId}`, {
          method: "DELETE",
          signal: AbortSignal.timeout(5000),
        });
        setSkills((prev) => prev.filter((s) => s.id !== skillId));
        setSearchResults((prev) =>
          prev ? prev.filter((s) => s.id !== skillId) : null,
        );
      } catch {
        // silent
      }
    },
    [],
  );

  const displaySkills = searchResults ?? skills;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      className="card-glow rounded-xl p-4 w-full max-h-[70vh] flex flex-col overflow-hidden"
      style={{ background: "#1A1A1A" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">🧠</span>
          <h2 className="text-sm font-semibold text-text">Learned Skills</h2>
        </div>
        <button
          onClick={onClose}
          className="w-6 h-6 rounded-md flex items-center justify-center text-text-muted hover:text-text hover:bg-surface-elevated transition-all"
        >
          ✕
        </button>
      </div>

      {/* Search */}
      <div className="flex gap-2 mb-3">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Search skills..."
          className="flex-1 px-3 py-1.5 text-xs bg-surface rounded-lg border border-border text-text placeholder:text-text-muted focus:outline-none focus:border-accent/50"
        />
        <button
          onClick={handleSearch}
          className="px-3 py-1.5 text-xs bg-accent/10 text-accent rounded-lg hover:bg-accent/20 transition-all"
        >
          Search
        </button>
        {searchResults !== null && (
          <button
            onClick={() => {
              setSearchResults(null);
              setSearchQuery("");
            }}
            className="px-3 py-1.5 text-xs bg-surface-elevated text-text-muted rounded-lg hover:text-text transition-all"
          >
            Clear
          </button>
        )}
      </div>

      {/* Execution result */}
      {executionResult && (
        <div className="mb-3 px-3 py-2 text-xs rounded-lg bg-surface-elevated border border-border text-text-secondary">
          {executionResult}
        </div>
      )}

      {/* Stats */}
      <div className="flex gap-3 mb-3 text-2xs text-text-muted font-mono">
        <span>{skills.length} skills</span>
        <span>{skills.reduce((a, s) => a + s.use_count, 0)} total uses</span>
        <span>
          avg conf{" "}
          {skills.length > 0
            ? (
                skills.reduce((a, s) => a + s.confidence, 0) / skills.length
              ).toFixed(0)
            : 0}
          %
        </span>
      </div>

      {/* Skill list */}
      <div className="flex-1 overflow-y-auto space-y-2 min-h-0">
        {loading && (
          <div className="text-center text-text-muted text-xs py-8">
            Loading skills...
          </div>
        )}

        {!loading && displaySkills.length === 0 && (
          <div className="text-center py-8">
            <p className="text-text-muted text-xs mb-2">No learned skills yet</p>
            <p className="text-text-muted text-2xs">
              Skills are auto-created when May detects repeated action patterns
              (3+ repetitions).
            </p>
          </div>
        )}

        {displaySkills.map((skill) => (
          <div
            key={skill.id}
            className="glass rounded-lg p-3 border border-border hover:border-accent/20 transition-all"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-text truncate">
                    {skill.name}
                  </span>
                  <span className="text-2xs font-mono px-1.5 py-0.5 rounded bg-accent/10 text-accent shrink-0">
                    {skill.confidence.toFixed(0)}%
                  </span>
                </div>

                {/* Steps */}
                <div className="flex flex-wrap gap-1 mb-1.5">
                  {skill.steps.map((step, i) => (
                    <span
                      key={i}
                      className="text-2xs font-mono px-1.5 py-0.5 rounded bg-surface text-text-secondary"
                    >
                      {step.tool_name}
                      {i < skill.steps.length - 1 && (
                        <span className="text-text-muted ml-1">→</span>
                      )}
                    </span>
                  ))}
                </div>

                {/* Meta */}
                <div className="flex gap-3 text-2xs text-text-muted font-mono">
                  <span>used {skill.use_count}x</span>
                  {skill.tags.length > 0 && (
                    <span className="text-text-muted">
                      {skill.tags
                        .filter((t) => !["auto_learned", "shadow_learner"].includes(t))
                        .slice(0, 2)
                        .join(", ")}
                    </span>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-1 shrink-0">
                <button
                  onClick={() => handleExecute(skill.id)}
                  disabled={executing === skill.id}
                  className="px-2 py-1 text-2xs rounded bg-accent/10 text-accent hover:bg-accent/20 transition-all disabled:opacity-50"
                >
                  {executing === skill.id ? "..." : "Run"}
                </button>
                <button
                  onClick={() => handleDelete(skill.id)}
                  className="px-2 py-1 text-2xs rounded bg-danger/10 text-danger hover:bg-danger/20 transition-all"
                >
                  ✕
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
