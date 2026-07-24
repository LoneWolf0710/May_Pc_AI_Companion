import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BACKEND_URL } from '../config';

interface GhostTask {
  id: string;
  description: string;
  steps: any[];
  created_at: number;
  started_at: number;
  completed_at: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  result: string;
  error: string;
  priority: number;
  created_display: string;
}

interface GhostStatus {
  active: boolean;
  idle_threshold_sec: number;
  time_since_input_sec: number;
  is_idle: boolean;
  queue: GhostTask[];
  queue_count: number;
  completed: GhostTask[];
  completed_count: number;
}

export default function GhostMode({ onClose }: { onClose: () => void }) {
  const [status, setStatus] = useState<GhostStatus | null>(null);
  const [newTask, setNewTask] = useState('');
  const [loading, setLoading] = useState(false);

  // Poll ghost status every 5 seconds
  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadStatus = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/ghost/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch {}
  };

  const queueTask = useCallback(async () => {
    if (!newTask.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/ghost/queue`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: newTask.trim() }),
      });
      if (res.ok) {
        setNewTask('');
        loadStatus();
      }
    } catch (e) {
      console.error('Failed to queue task:', e);
    }
    setLoading(false);
  }, [newTask]);

  const cancelTask = useCallback(async (taskId: string) => {
    try {
      await fetch(`${BACKEND_URL}/ghost/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId }),
      });
      loadStatus();
    } catch {}
  }, []);

  const cancelAll = useCallback(async () => {
    try {
      await fetch(`${BACKEND_URL}/ghost/cancel-all`, { method: 'POST' });
      loadStatus();
    } catch {}
  }, []);

  if (!status) return null;

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
  };

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
          <div className={`ghost-status-dot ${status.active ? 'active' : ''}`} />
          <span className="ghost-title-text">Ghost Mode</span>
        </div>
        <button onClick={onClose} className="ghost-close-btn">✕</button>
      </div>

      {/* Status bar */}
      <div className="ghost-status-bar">
        <div className="ghost-status-item">
          <span className="ghost-status-label">Status</span>
          <span className={`ghost-status-value ${status.active ? 'active' : 'inactive'}`}>
            {status.active ? 'Active' : 'Inactive'}
          </span>
        </div>
        <div className="ghost-status-item">
          <span className="ghost-status-label">Idle</span>
          <span className="ghost-status-value">
            {status.is_idle ? 'Yes' : `In ${formatDuration(status.idle_threshold_sec - status.time_since_input_sec)}`}
          </span>
        </div>
        <div className="ghost-status-item">
          <span className="ghost-status-label">Queue</span>
          <span className="ghost-status-value">{status.queue_count}</span>
        </div>
        <div className="ghost-status-item">
          <span className="ghost-status-label">Done</span>
          <span className="ghost-status-value">{status.completed_count}</span>
        </div>
      </div>

      {/* Task input */}
      <div className="ghost-input-area">
        <input
          type="text"
          placeholder="What should May do while you're away?"
          value={newTask}
          onChange={(e) => setNewTask(e.target.value)}
          className="ghost-task-input"
          onKeyDown={(e) => e.key === 'Enter' && queueTask()}
        />
        <button
          onClick={queueTask}
          disabled={loading || !newTask.trim()}
          className="ghost-queue-btn"
        >
          {loading ? '...' : '+ Queue'}
        </button>
      </div>

      {/* Queue */}
      {status.queue.length > 0 && (
        <div className="ghost-section">
          <div className="ghost-section-header">
            <span>Queued Tasks ({status.queue.length})</span>
            <button onClick={cancelAll} className="ghost-cancel-all-btn">
              Cancel All
            </button>
          </div>
          <div className="ghost-task-list">
            <AnimatePresence>
              {status.queue.map((task) => (
                <motion.div
                  key={task.id}
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className={`ghost-task-item ${task.status}`}
                >
                  <div className="ghost-task-info">
                    <div className="ghost-task-desc">{task.description}</div>
                    <div className="ghost-task-meta">
                      {task.created_display && `Queued ${task.created_display}`}
                      {task.priority > 0 && ` • Priority ${task.priority}`}
                    </div>
                  </div>
                  {task.status === 'pending' && (
                    <button
                      onClick={() => cancelTask(task.id)}
                      className="ghost-task-cancel"
                    >
                      ✕
                    </button>
                  )}
                  {task.status === 'running' && (
                    <div className="ghost-task-spinner" />
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}

      {/* Completed */}
      {status.completed.length > 0 && (
        <div className="ghost-section">
          <div className="ghost-section-header">
            <span>Completed ({status.completed_count})</span>
          </div>
          <div className="ghost-task-list">
            {status.completed.slice(-5).reverse().map((task) => (
              <div key={task.id} className={`ghost-task-item ${task.status}`}>
                <div className="ghost-task-info">
                  <div className="ghost-task-desc">
                    {task.status === 'completed' ? '✓' : task.status === 'failed' ? '✗' : '○'}{' '}
                    {task.description}
                  </div>
                  <div className="ghost-task-meta">
                    {task.result && task.result.slice(0, 100)}
                    {task.error && <span className="ghost-error">{task.error.slice(0, 100)}</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {status.queue.length === 0 && status.completed.length === 0 && (
        <div className="ghost-empty">
          <div className="ghost-empty-icon">👻</div>
          <p>Queue tasks for May to handle while you're away.</p>
          <p className="ghost-empty-hint">
            She'll execute them when you're idle for 5+ minutes.
          </p>
        </div>
      )}
    </motion.div>
  );
}
