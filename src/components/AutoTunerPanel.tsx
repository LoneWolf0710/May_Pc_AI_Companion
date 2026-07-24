import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { BACKEND_URL } from '../config';

interface Gene {
  name: string;
  value: number;
  min_val: number;
  max_val: number;
  mutation_rate: number;
  step_size: number;
  description: string;
}

interface TunerStatus {
  active: boolean;
  total_cycles: number;
  accepted_mutations: number;
  rejected_mutations: number;
  baseline_fitness: number;
  current_fitness: number;
  last_cycle_time: number;
  last_commit: string;
  gene_count: number;
  genes: Record<string, number>;
  fitness_history: Array<{
    cycle: number;
    fitness_before: number;
    fitness_after: number;
    mutations: number;
    accepted: boolean;
    elapsed_sec: number;
  }>;
}

export default function AutoTunerPanel({ onClose }: { onClose: () => void }) {
  const [status, setStatus] = useState<TunerStatus | null>(null);
  const [genes, setGenes] = useState<Gene[]>([]);
  const [evolving, setEvolving] = useState(false);
  const [editingGene, setEditingGene] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  useEffect(() => {
    loadStatus();
    loadGenes();
    const interval = setInterval(loadStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadStatus = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/auto-tuner`);
      if (res.ok) setStatus(await res.json());
    } catch {}
  };

  const loadGenes = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/auto-tuner/genes`);
      if (res.ok) {
        const data = await res.json();
        setGenes(data.genes || []);
      }
    } catch {}
  };

  const evolve = useCallback(async () => {
    setEvolving(true);
    try {
      const res = await fetch(`${BACKEND_URL}/auto-tuner/evolve`, { method: 'POST' });
      if (res.ok) {
        await loadStatus();
        await loadGenes();
      }
    } catch {}
    setEvolving(false);
  }, []);

  const setGene = useCallback(async (name: string, value: number) => {
    try {
      const res = await fetch(`${BACKEND_URL}/auto-tuner/gene`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, value }),
      });
      if (res.ok) {
        setEditingGene(null);
        await loadGenes();
      }
    } catch {}
  }, []);

  const resetGenes = useCallback(async () => {
    try {
      await fetch(`${BACKEND_URL}/auto-tuner/reset`, { method: 'POST' });
      await loadGenes();
      await loadStatus();
    } catch {}
  }, []);

  const clearHistory = useCallback(async () => {
    try {
      await fetch(`${BACKEND_URL}/auto-tuner/history/clear`, { method: 'POST' });
      await loadStatus();
    } catch {}
  }, []);

  const fitness = status?.current_fitness ?? 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      className="ghost-mode-panel"
    >
      {/* Header */}
      <div className="ghost-header">
        <div className="ghost-header-left">
          <div className={`ghost-status-dot ${status?.active ? 'active' : ''}`} style={{ background: status?.active ? '#fbbf24' : undefined }} />
          <span className="ghost-title-text">Auto-Tuner</span>
        </div>
        <button onClick={onClose} className="ghost-close-btn">✕</button>
      </div>

      {/* Status bar */}
      <div className="ghost-status-bar">
        <div className="ghost-status-item">
          <span className="ghost-status-label">Cycles</span>
          <span className="ghost-status-value">{status?.total_cycles ?? 0}</span>
        </div>
        <div className="ghost-status-item">
          <span className="ghost-status-label">Accepted</span>
          <span className="ghost-status-value" style={{ color: '#34d399' }}>{status?.accepted_mutations ?? 0}</span>
        </div>
        <div className="ghost-status-item">
          <span className="ghost-status-label">Rejected</span>
          <span className="ghost-status-value" style={{ color: '#f87171' }}>{status?.rejected_mutations ?? 0}</span>
        </div>
        <div className="ghost-status-item">
          <span className="ghost-status-label">Fitness</span>
          <span className="ghost-status-value" style={{ color: fitness > 0.5 ? '#34d399' : fitness > 0.3 ? '#fbbf24' : '#f87171' }}>
            {(fitness * 100).toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Evolve button */}
      <div style={{ padding: '12px 20px', display: 'flex', gap: 8 }}>
        <button
          onClick={evolve}
          disabled={evolving}
          className="ghost-queue-btn"
          style={{ flex: 1 }}
        >
          {evolving ? '⏳ Evolving...' : '🧬 Run Evolution Cycle'}
        </button>
        <button onClick={resetGenes} className="meeting-new-btn" style={{ fontSize: 11 }}>Reset</button>
        <button onClick={clearHistory} className="meeting-new-btn" style={{ fontSize: 11 }}>Clear</button>
      </div>

      {/* Fitness history chart (last 10) */}
      {status?.fitness_history && status.fitness_history.length > 0 && (
        <div style={{ padding: '0 20px 12px' }}>
          <div className="ghost-section-header">
            <span>Fitness History</span>
            <span style={{ fontSize: 10, color: '#55556a' }}>
              Last {Math.min(10, status.fitness_history.length)} cycles
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 40 }}>
            {status.fitness_history.slice(-10).map((entry, i) => (
              <div
                key={i}
                style={{
                  flex: 1,
                  height: `${Math.max(4, (entry.fitness_after || 0) * 100)}%`,
                  background: entry.accepted ? 'rgba(52,211,153,0.4)' : 'rgba(248,113,113,0.4)',
                  borderRadius: 3,
                  transition: 'height 0.3s',
                }}
                title={`Cycle ${entry.cycle}: ${(entry.fitness_after * 100).toFixed(1)}%`}
              />
            ))}
          </div>
        </div>
      )}

      {/* Genes list */}
      <div style={{ padding: '0 20px 16px', flex: 1, overflowY: 'auto' }}>
        <div className="ghost-section-header" style={{ marginBottom: 10 }}>
          <span>Tunable Genes ({genes.length})</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {genes.map((gene) => {
            const isEditing = editingGene === gene.name;
            const pct = ((gene.value - gene.min_val) / (gene.max_val - gene.min_val)) * 100;
            return (
              <div
                key={gene.name}
                style={{
                  padding: '10px 12px',
                  borderRadius: 10,
                  border: `1px solid ${isEditing ? 'rgba(251,191,36,0.3)' : '#2e2a3a'}`,
                  background: isEditing ? 'rgba(251,191,36,0.05)' : '#242030',
                  transition: 'all 0.15s',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ fontSize: 12, fontWeight: 500, color: '#f0f0f5', fontFamily: "'JetBrains Mono', monospace" }}>
                    {gene.name}
                  </span>
                  {isEditing ? (
                    <div style={{ display: 'flex', gap: 4 }}>
                      <input
                        type="number"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            const v = parseFloat(editValue);
                            if (!isNaN(v)) setGene(gene.name, v);
                          }
                          if (e.key === 'Escape') setEditingGene(null);
                        }}
                        style={{
                          width: 80, padding: '2px 6px', borderRadius: 4,
                          border: '1px solid #3e3a4a', background: '#1a1720', color: '#f0f0f5',
                          fontSize: 11, fontFamily: "'JetBrains Mono', monospace",
                        }}
                        autoFocus
                      />
                      <button
                        onClick={() => {
                          const v = parseFloat(editValue);
                          if (!isNaN(v)) setGene(gene.name, v);
                        }}
                        style={{ fontSize: 10, color: '#34d399', background: 'none', border: 'none', cursor: 'pointer' }}
                      >✓</button>
                      <button
                        onClick={() => setEditingGene(null)}
                        style={{ fontSize: 10, color: '#f87171', background: 'none', border: 'none', cursor: 'pointer' }}
                      >✕</button>
                    </div>
                  ) : (
                    <button
                      onClick={() => { setEditingGene(gene.name); setEditValue(String(gene.value)); }}
                      style={{
                        fontSize: 11, fontFamily: "'JetBrains Mono', monospace",
                        color: '#818cf8', background: 'none', border: 'none', cursor: 'pointer',
                      }}
                    >
                      {gene.step_size > 0 ? Math.round(gene.value) : gene.value.toFixed(4)}
                    </button>
                  )}
                </div>
                <div style={{ fontSize: 10, color: '#55556a', marginBottom: 4 }}>
                  {gene.description}
                </div>
                {/* Progress bar */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 9, color: '#55556a', fontFamily: "'JetBrains Mono', monospace", width: 32, textAlign: 'right' }}>
                    {gene.min_val}
                  </span>
                  <div style={{ flex: 1, height: 4, borderRadius: 2, background: '#1a1720', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', borderRadius: 2, width: `${Math.max(2, Math.min(100, pct))}%`,
                      background: 'linear-gradient(90deg, #818cf8, #c084fc)',
                      transition: 'width 0.3s',
                    }} />
                  </div>
                  <span style={{ fontSize: 9, color: '#55556a', fontFamily: "'JetBrains Mono', monospace", width: 32 }}>
                    {gene.max_val}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
                  <span style={{ fontSize: 9, color: '#55556a' }}>
                    mutation: {(gene.mutation_rate * 100).toFixed(0)}%
                  </span>
                  {gene.step_size > 0 && (
                    <span style={{ fontSize: 9, color: '#55556a' }}>
                      step: {gene.step_size}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
