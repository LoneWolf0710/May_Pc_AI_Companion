import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { BACKEND_URL } from "../config";

interface WorkflowStep {
  tool_name: string;
  params: Record<string, unknown>;
  description: string;
  condition: string;
  delay_after: number;
}

interface Workflow {
  id: string;
  name: string;
  description: string;
  steps: WorkflowStep[];
  trigger: string;
  trigger_config: Record<string, unknown>;
  enabled: boolean;
  last_run: number;
  run_count: number;
  last_error: string;
  created_at: number;
  status?: string;
}

interface WorkflowStats {
  total_workflows: number;
  enabled: number;
  running: number;
  total_runs: number;
}

interface WorkflowsPanelProps {
  onClose: () => void;
}

export default function WorkflowsPanel({ onClose }: WorkflowsPanelProps) {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [stats, setStats] = useState<WorkflowStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSteps, setNewSteps] = useState<string>(""); // Natural language description
  const [newTrigger, setNewTrigger] = useState<string>("manual");
  const [newTriggerConfig, setNewTriggerConfig] = useState<string>(""); // interval or pattern
  const [previewSteps, setPreviewSteps] = useState<WorkflowStep[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const showError = useCallback((msg: string) => {
    setError(msg);
    setTimeout(() => setError(null), 5000);
  }, []);

  const fetchWorkflows = useCallback(async () => {
    try {
      const [wfRes, statsRes] = await Promise.all([
        fetch(`${BACKEND_URL}/workflows`, { signal: AbortSignal.timeout(5000) }),
        fetch(`${BACKEND_URL}/workflows/stats`, { signal: AbortSignal.timeout(5000) }),
      ]);
      if (wfRes.ok) {
        const data = await wfRes.json();
        setWorkflows(data.workflows || []);
      }
      if (statsRes.ok) {
        const data = await statsRes.json();
        setStats(data);
      }
    } catch (err) {
      showError("Failed to load workflows — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  const handlePreview = async () => {
    if (!newSteps.trim()) return;
    setPreviewing(true);
    try {
      const res = await fetch(`${BACKEND_URL}/workflows/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: newSteps.trim() }),
        signal: AbortSignal.timeout(10000),
      });
      if (res.ok) {
        const data = await res.json();
        setPreviewSteps(data.steps || []);
      } else {
        showError("Failed to parse steps");
      }
    } catch (err) {
      showError("Preview failed — backend may be offline");
    } finally {
      setPreviewing(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const res = await fetch(`${BACKEND_URL}/workflows`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },          body: JSON.stringify({
          name: newName.trim(),
          description: newSteps.trim(),
          steps: previewSteps.length > 0 ? previewSteps : [],
          trigger: newTrigger,
          trigger_config: newTrigger === "scheduled" ? { interval_seconds: Math.max(60, parseInt(newTriggerConfig) || 3600) } : newTrigger === "chat" ? { pattern: newTriggerConfig } : {},
          description_input: newSteps.trim(),
        }),
        signal: AbortSignal.timeout(10000),
      });
      if (res.ok) {
        setNewName("");
        setNewSteps("");
        setNewTrigger("manual");
        setNewTriggerConfig("");
        setPreviewSteps([]);
        fetchWorkflows();
      } else {
        showError("Failed to create workflow");
      }
    } catch (err) {
      showError("Create failed — backend may be offline");
    } finally {
      setCreating(false);
    }
  };

  const handleRun = async (wfId: string) => {
    setRunResult(null);
    setSelectedWorkflow(wfId);
    try {
      const res = await fetch(`${BACKEND_URL}/workflows/${wfId}/run`, {
        method: "POST",
        signal: AbortSignal.timeout(60000),
      });
      const data = await res.json();
      if (data.status === "ok") {
        setRunResult(`✓ Executed ${data.steps_executed} steps`);
      } else {
        setRunResult(`✗ ${data.error || "Execution failed"}`);
      }
      fetchWorkflows();
    } catch (err) {
      setRunResult(`✗ ${err instanceof Error ? err.message : "Network error"}`);
    }
  };

  const handleToggle = async (wfId: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/workflows/${wfId}/toggle`, {
        method: "POST",
        signal: AbortSignal.timeout(5000),
      });
      if (res.ok) fetchWorkflows();
      else showError("Toggle failed");
    } catch {
      showError("Toggle failed — backend may be offline");
    }
  };

  const handleDelete = async (wfId: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/workflows/${wfId}`, {
        method: "DELETE",
        signal: AbortSignal.timeout(5000),
      });
      if (res.ok) {
        if (selectedWorkflow === wfId) setSelectedWorkflow(null);
        fetchWorkflows();
      } else showError("Delete failed");
    } catch {
      showError("Delete failed — backend may be offline");
    }
  };

  const formatTime = (ts: number) => {
    if (!ts) return "Never";
    const d = new Date(ts * 1000);
    return d.toLocaleString([], { hour: "2-digit", minute: "2-digit", month: "short", day: "numeric" });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      className="bg-surface rounded-xl border border-border shadow-panel overflow-hidden"
    >
      {/* Error toast */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mx-3 mt-2 px-3 py-2 rounded-lg bg-danger/10 border border-danger/30 text-xs font-mono text-danger"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-lg">⚡</span>
          <h2 className="text-sm font-semibold text-text">Automated Workflows</h2>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded-lg flex items-center justify-center text-text-muted hover:text-text hover:bg-surface-elevated transition-all"
        >
          ×
        </button>
      </div>

      <div className="max-h-[60vh] overflow-y-auto">
        {/* Stats bar */}
        {stats && (
          <div className="px-4 py-2 border-b border-border flex gap-4">
            <span className="text-2xs font-mono text-text-muted">
              {stats.total_workflows} workflows
            </span>
            <span className="text-2xs font-mono text-emerald">
              {stats.enabled} enabled
            </span>
            <span className="text-2xs font-mono text-accent">
              {stats.total_runs} total runs
            </span>
          </div>
        )}

        {/* Workflow list */}
        <div className="p-3 space-y-2">
          {loading ? (
            <div className="text-center py-6">
              <div className="w-5 h-5 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto" />
              <p className="text-2xs text-text-muted mt-2 font-mono">Loading workflows...</p>
            </div>
          ) : workflows.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-xs text-text-muted">No workflows yet</p>
              <p className="text-2xs text-text-muted/60 mt-1">
                Create one below or ask May: "Create a workflow to..."
              </p>
            </div>
          ) : (
            workflows.map((wf) => (
              <motion.div
                key={wf.id}
                layout
                className={`rounded-lg border p-3 transition-all ${
                  selectedWorkflow === wf.id
                    ? "border-accent/40 bg-accent/5"
                    : "border-border bg-surface-elevated hover:border-border-hover"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${wf.enabled ? "bg-emerald" : "bg-text-muted/30"}`} />
                      <h3 className="text-sm font-medium text-text truncate">{wf.name}</h3>
                      <span className="text-2xs font-mono px-1.5 py-0.5 rounded bg-surface border border-border text-text-muted">
                        {wf.trigger}
                      </span>
                    </div>
                    {wf.description && (
                      <p className="text-2xs text-text-muted mt-1 line-clamp-2">{wf.description}</p>
                    )}
                    <div className="flex items-center gap-3 mt-1.5">
                      <span className="text-2xs font-mono text-text-muted">
                        {wf.steps.length} steps
                      </span>
                      <span className="text-2xs font-mono text-text-muted">
                        Run {wf.run_count}×
                      </span>
                      <span className="text-2xs font-mono text-text-muted">
                        Last: {formatTime(wf.last_run)}
                      </span>
                    </div>
                    {wf.last_error && (
                      <p className="text-2xs font-mono text-danger mt-1 truncate">
                        Error: {wf.last_error}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-1 ml-2">
                    <button
                      onClick={() => handleRun(wf.id)}
                      disabled={wf.status === "running"}
                      className="px-2 py-1 rounded text-2xs font-mono bg-accent/10 text-accent border border-accent/20 hover:bg-accent/20 transition-all disabled:opacity-50"
                      title="Run workflow"
                    >
                      {wf.status === "running" ? "⟳" : "▶"}
                    </button>
                    <button
                      onClick={() => handleToggle(wf.id)}
                      className={`px-2 py-1 rounded text-2xs font-mono border transition-all ${
                        wf.enabled
                          ? "bg-emerald/10 text-emerald border-emerald/20 hover:bg-emerald/20"
                          : "bg-surface border-border text-text-muted hover:border-border-hover"
                      }`}
                      title={wf.enabled ? "Disable" : "Enable"}
                    >
                      {wf.enabled ? "ON" : "OFF"}
                    </button>
                    <button
                      onClick={() => handleDelete(wf.id)}
                      className="px-2 py-1 rounded text-2xs font-mono bg-danger/10 text-danger border border-danger/20 hover:bg-danger/20 transition-all"
                      title="Delete workflow"
                    >
                      ×
                    </button>
                  </div>
                </div>
                {/* Steps preview */}
                {selectedWorkflow === wf.id && wf.steps.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-border space-y-1">
                    {wf.steps.map((step, i) => (
                      <div key={i} className="flex items-center gap-2 text-2xs font-mono">
                        <span className="text-text-muted w-4 text-right">{i + 1}.</span>
                        <span className="text-accent">{step.tool_name}</span>
                        <span className="text-text-muted truncate">
                          {step.description || JSON.stringify(step.params).slice(0, 60)}
                        </span>
                        {step.delay_after > 0 && (
                          <span className="text-amber">+{step.delay_after}s</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            ))
          )}
        </div>

        {/* Run result */}
        <AnimatePresence>
          {runResult && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mx-3 mb-2 px-3 py-2 rounded-lg bg-surface-elevated border border-border text-xs font-mono"
            >
              {runResult}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Create new workflow */}
        <div className="p-3 border-t border-border">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-2xs font-mono text-text-muted uppercase tracking-wider">New Workflow</span>
          </div>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Workflow name..."
            className="w-full bg-surface-elevated border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-[#666666] focus:outline-none focus:border-accent/50 transition-colors mb-2"
          />
          {/* Trigger selector */}
          <div className="flex gap-1 mb-2">
            {["manual", "scheduled", "chat"].map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => { setNewTrigger(t); setNewTriggerConfig(""); }}
                className={`flex-1 py-1.5 rounded-lg text-2xs font-mono border transition-all ${
                  newTrigger === t
                    ? "bg-accent/10 border-accent/30 text-accent"
                    : "bg-surface-elevated border-border text-text-muted hover:border-border-hover"
                }`}
              >
                {t === "manual" ? "🖐 Manual" : t === "scheduled" ? "⏱ Schedule" : "💬 Chat"}
              </button>
            ))}
          </div>
          {newTrigger === "scheduled" && (
            <input
              type="number"
              value={newTriggerConfig}
              onChange={(e) => setNewTriggerConfig(e.target.value)}
              placeholder="Interval in seconds (default 3600)"
              min="60"
              className="w-full bg-surface-elevated border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-[#666666] focus:outline-none focus:border-accent/50 transition-colors mb-2"
            />
          )}
          {newTrigger === "chat" && (
            <input
              type="text"
              value={newTriggerConfig}
              onChange={(e) => setNewTriggerConfig(e.target.value)}
              placeholder='Trigger phrase, e.g. "what time" or "weather"'
              className="w-full bg-surface-elevated border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-[#666666] focus:outline-none focus:border-accent/50 transition-colors mb-2"
            />
          )}
          <textarea
            value={newSteps}
            onChange={(e) => { setNewSteps(e.target.value); setPreviewSteps([]); }}
            placeholder='Describe what this workflow does, e.g. "Check weather and notify me" or "Open Chrome and set volume to 50%"...'
            rows={3}
            className="w-full bg-surface-elevated border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-[#666666] focus:outline-none focus:border-accent/50 transition-colors resize-none mb-2"
          />
          {/* Preview parsed steps */}
          {previewSteps.length > 0 && (
            <div className="mb-2 p-2 rounded-lg bg-surface-elevated border border-border">
              <div className="flex items-center justify-between mb-1">
                <span className="text-2xs font-mono text-text-muted uppercase tracking-wider">Parsed Steps</span>
                <span className="text-2xs font-mono text-accent">{previewSteps.length} steps</span>
              </div>
              {previewSteps.map((step, i) => (
                <div key={i} className="flex items-center gap-2 text-2xs font-mono py-0.5">
                  <span className="text-text-muted w-4 text-right">{i + 1}.</span>
                  <span className="text-accent">{step.tool_name}</span>
                  <span className="text-text-muted truncate">
                    {step.description || JSON.stringify(step.params).slice(0, 40)}
                  </span>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <button
              onClick={handlePreview}
              disabled={!newSteps.trim() || previewing}
              className="flex-1 py-2 rounded-lg bg-surface-elevated border border-border text-text-muted text-xs font-mono hover:border-accent/30 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {previewing ? "Parsing..." : "Preview Steps"}
            </button>
            <button
              onClick={handleCreate}
              disabled={!newName.trim() || creating}
              className="flex-1 py-2 rounded-lg bg-accent/10 border border-accent/20 text-accent text-xs font-mono hover:bg-accent/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {creating ? "Creating..." : "Create Workflow"}
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
