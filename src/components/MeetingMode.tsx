import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BACKEND_URL } from '../config';

interface MeetingStatus {
  active: boolean;
  duration_sec?: number;
  duration_display?: string;
  transcript_segments?: number;
  audio_chunks?: number;
  paused?: boolean;
}

interface MeetingSummary {
  title: string;
  date: string;
  duration_sec: number;
  duration_display: string;
  transcript_length: number;
  summary: string;
  action_items: string[];
  key_points: string[];
  participants: string[];
  saved_path: string;
}

interface MeetingList {
  name: string;
  file: string;
  size: number;
}

export default function MeetingMode({ onClose }: { onClose: () => void }) {
  const [status, setStatus] = useState<MeetingStatus>({ active: false });
  const [summary, setSummary] = useState<MeetingSummary | null>(null);
  const [meetings, setMeetings] = useState<MeetingList[]>([]);
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<'record' | 'history'>('record');

  // Poll meeting status every 2 seconds when active
  useEffect(() => {
    if (!status.active) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/meeting/status`);
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
        }
      } catch {}
    }, 2000);
    return () => clearInterval(interval);
  }, [status.active]);

  // Load meeting history on mount
  useEffect(() => {
    loadMeetings();
  }, []);

  const loadMeetings = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/meeting/list`);
      if (res.ok) {
        const data = await res.json();
        setMeetings(data.meetings || []);
      }
    } catch {}
  };

  const startMeeting = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/meeting/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title || undefined }),
      });
      if (res.ok) {
        await res.json();
        setStatus({ active: true, duration_sec: 0, duration_display: '0s' });
        setSummary(null);
      }
    } catch (e) {
      console.error('Failed to start meeting:', e);
    }
    setLoading(false);
  }, [title]);

  const stopMeeting = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/meeting/stop`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setSummary(data);
        setStatus({ active: false });
        loadMeetings();
      }
    } catch (e) {
      console.error('Failed to stop meeting:', e);
    }
    setLoading(false);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      className="meeting-mode-panel"
    >
      {/* Header */}
      <div className="meeting-header">
        <div className="meeting-header-left">
          <div className={`meeting-status-dot ${status.active ? 'recording' : ''}`} />
          <span className="meeting-title-text">
            {status.active ? 'Recording...' : 'Meeting Mode'}
          </span>
        </div>
        <button onClick={onClose} className="meeting-close-btn">✕</button>
      </div>

      {/* Tab bar */}
      <div className="meeting-tabs">
        <button
          className={`meeting-tab ${tab === 'record' ? 'active' : ''}`}
          onClick={() => setTab('record')}
        >
          Record
        </button>
        <button
          className={`meeting-tab ${tab === 'history' ? 'active' : ''}`}
          onClick={() => setTab('history')}
        >
          History ({meetings.length})
        </button>
      </div>

      <AnimatePresence mode="wait">
        {tab === 'record' ? (
          <motion.div
            key="record"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            className="meeting-content"
          >
            {status.active ? (
              /* Active Recording */
              <div className="meeting-recording">
                <div className="meeting-recording-pulse" />
                <div className="meeting-recording-info">
                  <div className="meeting-timer">{status.duration_display || '0s'}</div>
                  <div className="meeting-stats">
                    <span>{status.transcript_segments || 0} segments</span>
                    <span>•</span>
                    <span>{status.audio_chunks || 0} chunks</span>
                  </div>
                </div>
                <button
                  onClick={stopMeeting}
                  disabled={loading}
                  className="meeting-stop-btn"
                >
                  {loading ? 'Stopping...' : '■ Stop Recording'}
                </button>
              </div>
            ) : summary ? (
              /* Show Summary */
              <div className="meeting-summary">
                <div className="meeting-summary-header">
                  <h3>{summary.title}</h3>
                  <span className="meeting-summary-meta">
                    {summary.duration_display} • {summary.date}
                  </span>
                </div>

                {summary.summary && (
                  <div className="meeting-section">
                    <div className="meeting-section-label">Summary</div>
                    <p>{summary.summary}</p>
                  </div>
                )}

                {summary.action_items.length > 0 && (
                  <div className="meeting-section">
                    <div className="meeting-section-label">Action Items</div>
                    <ul>
                      {summary.action_items.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {summary.key_points.length > 0 && (
                  <div className="meeting-section">
                    <div className="meeting-section-label">Key Points</div>
                    <ul>
                      {summary.key_points.map((point, i) => (
                        <li key={i}>{point}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {summary.participants.length > 0 && (
                  <div className="meeting-section">
                    <div className="meeting-section-label">Participants</div>
                    <div className="meeting-participants">
                      {summary.participants.map((p, i) => (
                        <span key={i} className="meeting-participant-chip">{p}</span>
                      ))}
                    </div>
                  </div>
                )}

                {summary.saved_path && (
                  <div className="meeting-saved">
                    Saved to: {summary.saved_path.split(/[/\\]/).pop()}
                  </div>
                )}

                <button
                  onClick={() => setSummary(null)}
                  className="meeting-new-btn"
                >
                  New Recording
                </button>
              </div>
            ) : (
              /* Start New Recording */
              <div className="meeting-start">
                <div className="meeting-start-icon">🎙️</div>
                <p className="meeting-start-desc">
                  Capture meeting audio, transcribe automatically, and get a summary with action items.
                </p>
                <input
                  type="text"
                  placeholder="Meeting title (optional)"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="meeting-title-input"
                  onKeyDown={(e) => e.key === 'Enter' && startMeeting()}
                />
                <button
                  onClick={startMeeting}
                  disabled={loading}
                  className="meeting-start-btn"
                >
                  {loading ? 'Starting...' : '● Start Recording'}
                </button>
              </div>
            )}
          </motion.div>
        ) : (
          /* History Tab */
          <motion.div
            key="history"
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -10 }}
            className="meeting-content"
          >
            {meetings.length === 0 ? (
              <div className="meeting-empty">
                <div className="meeting-empty-icon">📋</div>
                <p>No meetings recorded yet.</p>
              </div>
            ) : (
              <div className="meeting-list">
                {meetings.map((m, i) => (
                  <div key={i} className="meeting-list-item">
                    <div className="meeting-list-info">
                      <div className="meeting-list-name">{m.name}</div>
                      <div className="meeting-list-meta">
                        {(m.size / 1024).toFixed(1)} KB
                      </div>
                    </div>
                    <button
                      className="meeting-list-open"
                      onClick={async () => {
                        try {
                          await fetch(`${BACKEND_URL}/chat`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                              message: `Open the meeting notes file: ${m.file}`,
                              provider: 'ollama',
                            }),
                          });
                        } catch {}
                      }}
                    >
                      Open
                    </button>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
