import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BACKEND_URL } from '../config';

interface KnowledgeItem {
  id: string;
  query: string;
  source: string;
  facts: string[];
  confidence: number;
  timestamp: number;
  status: string;
  created_display?: string;
}

interface LearningStatus {
  total_extracted: number;
  total_approved: number;
  total_rejected: number;
  total_pending: number;
  pending_count: number;
  learned_count: number;
}

export default function InternetLearning({ onClose }: { onClose: () => void }) {
  const [status, setStatus] = useState<LearningStatus | null>(null);
  const [pendingItems, setPendingItems] = useState<KnowledgeItem[]>([]);
  const [recentItems, setRecentItems] = useState<KnowledgeItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 15000);
    return () => clearInterval(interval);
  }, []);

  const loadAll = async () => {
    await Promise.allSettled([loadStatus(), loadPending(), loadRecent()]);
  };

  const loadStatus = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/learning`);
      if (res.ok) setStatus(await res.json());
    } catch {}
  };

  const loadPending = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/learning/pending`);
      if (res.ok) {
        const data = await res.json();
        setPendingItems(data.items || []);
      }
    } catch {}
  };

  const loadRecent = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/learning/recent`);
      if (res.ok) {
        const data = await res.json();
        setRecentItems(data.items || []);
      }
    } catch {}
  };

  const approveItem = useCallback(async (id: string) => {
    setLoading(true);
    try {
      await fetch(`${BACKEND_URL}/learning/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      });
      await loadAll();
    } catch {} finally {
      setLoading(false);
    }
  }, []);

  const rejectItem = useCallback(async (id: string) => {
    setLoading(true);
    try {
      await fetch(`${BACKEND_URL}/learning/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      });
      await loadAll();
    } catch {} finally {
      setLoading(false);
    }
  }, [])

  const clearPending = useCallback(async () => {
    try {
      await fetch(`${BACKEND_URL}/learning/clear`, { method: 'POST' });
      await loadAll();
    } catch {}
  }, []);

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
          <div className="ghost-status-dot active" style={{ background: '#34d399' }} />
          <span className="ghost-title-text">Internet Learning</span>
        </div>
        <button onClick={onClose} className="ghost-close-btn">✕</button>
      </div>

      {/* Status bar */}
      <div className="ghost-status-bar">
        <div className="ghost-status-item">
          <span className="ghost-status-label">Pending</span>
          <span className="ghost-status-value" style={{ color: '#fbbf24' }}>{status?.pending_count ?? 0}</span>
        </div>
        <div className="ghost-status-item">
          <span className="ghost-status-label">Learned</span>
          <span className="ghost-status-value" style={{ color: '#34d399' }}>{status?.learned_count ?? 0}</span>
        </div>
        <div className="ghost-status-item">
          <span className="ghost-status-label">Extracted</span>
          <span className="ghost-status-value">{status?.total_extracted ?? 0}</span>
        </div>
        <div className="ghost-status-item">
          <span className="ghost-status-label">Rejected</span>
          <span className="ghost-status-value" style={{ color: '#55556a' }}>{status?.total_rejected ?? 0}</span>
        </div>
      </div>

      {/* Clear all pending */}
      {pendingItems.length > 0 && (
        <div style={{ padding: '8px 20px 0' }}>
          <button onClick={clearPending} className="ghost-cancel-all-btn" style={{ width: '100%', textAlign: 'center' }}>
            Clear All Pending
          </button>
        </div>
      )}

      {/* Pending knowledge cards */}
      <div style={{ padding: '12px 20px', overflowY: 'auto', flex: 1, maxHeight: '50vh' }}>
        <div className="ghost-section-header">
          <span>Pending Review ({pendingItems.length})</span>
        </div>
        <AnimatePresence>
          {pendingItems.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '30px 0', color: '#55556a', fontSize: 13 }}>
              🧠 No pending knowledge items
            </div>
          ) : (
            pendingItems.map((item) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                style={{
                  padding: 12, marginBottom: 8, borderRadius: 10,
                  border: '1px solid #2e2a3a', background: '#242030',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                  <div style={{ fontSize: 12, fontWeight: 500, color: '#f0f0f5' }}>
                    {item.query}
                  </div>
                  <span style={{
                    fontSize: 9, padding: '2px 6px', borderRadius: 4,
                    background: item.confidence > 0.6 ? 'rgba(52,211,153,0.1)' : 'rgba(251,191,36,0.1)',
                    color: item.confidence > 0.6 ? '#34d399' : '#fbbf24',
                  }}>
                    {Math.round(item.confidence * 100)}% conf
                  </span>
                </div>
                {item.source && (
                  <div style={{ fontSize: 10, color: '#55556a', marginBottom: 6, fontFamily: "'JetBrains Mono', monospace" }}>
                    📎 {item.source.length > 60 ? item.source.slice(0, 60) + '...' : item.source}
                  </div>
                )}
                {item.facts.length > 0 && (
                  <div style={{ marginBottom: 8 }}>
                    {item.facts.slice(0, 3).map((fact, i) => (
                      <div key={i} style={{ fontSize: 11, color: '#9090a8', paddingLeft: 12, marginBottom: 2, position: 'relative' }}>
                        <span style={{ position: 'absolute', left: 0, color: '#818cf8' }}>•</span>
                        {fact.length > 120 ? fact.slice(0, 120) + '...' : fact}
                      </div>
                    ))}
                  </div>
                )}
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    onClick={() => approveItem(item.id)}
                    disabled={loading}
                    style={{
                      flex: 1, padding: '6px 12px', borderRadius: 6, border: '1px solid rgba(52,211,153,0.3)',
                      background: 'rgba(52,211,153,0.1)', color: '#34d399', fontSize: 11, fontWeight: 500,
                      cursor: 'pointer', transition: 'all 0.15s',
                    }}
                  >
                    ✓ Learn
                  </button>
                  <button
                    onClick={() => rejectItem(item.id)}
                    disabled={loading}
                    style={{
                      flex: 1, padding: '6px 12px', borderRadius: 6, border: '1px solid rgba(248,113,113,0.3)',
                      background: 'rgba(248,113,113,0.1)', color: '#f87171', fontSize: 11, fontWeight: 500,
                      cursor: 'pointer', transition: 'all 0.15s',
                    }}
                  >
                    ✕ Discard
                  </button>
                </div>
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>

      {/* Recent learned */}
      {recentItems.length > 0 && (
        <div style={{ padding: '0 20px 16px' }}>
          <div className="ghost-section-header">
            <span>Recently Learned ({recentItems.length})</span>
          </div>
          {recentItems.slice(0, 5).map((item) => (
            <div
              key={item.id}
              style={{
                padding: '8px 10px', marginBottom: 4, borderRadius: 8,
                border: '1px solid rgba(52,211,153,0.1)', background: 'rgba(52,211,153,0.02)',
              }}
            >
              <div style={{ fontSize: 11, color: '#34d399' }}>
                ✓ {item.query}
              </div>
              <div style={{ fontSize: 10, color: '#55556a', marginTop: 2 }}>
                {item.facts.length} facts • {Math.round(item.confidence * 100)}% confidence
              </div>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
