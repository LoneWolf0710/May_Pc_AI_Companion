import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { BACKEND_URL } from '../config';

const MOOD_COLORS: Record<string, string> = {
  happy: '#34d399',
  excited: '#fbbf24',
  calm: '#818cf8',
  neutral: '#9090a8',
  sad: '#6366f1',
  frustrated: '#f87171',
  angry: '#ef4444',
  anxious: '#fb923c',
  surprised: '#c084fc',
  tired: '#6b7280',
};

const MOOD_EMOJIS: Record<string, string> = {
  happy: '😊',
  excited: '🎉',
  calm: '😌',
  neutral: '😐',
  sad: '😢',
  frustrated: '😤',
  angry: '😠',
  anxious: '😰',
  surprised: '😲',
  tired: '😴',
};

interface MoodEntry {
  timestamp: number;
  mood: string;
  confidence: number;
  message_preview: string;
  may_mood: string;
  response_style: string;
}

interface MoodTimelineBucket {
  timestamp: number;
  dominant_mood: string;
  mood_count: number;
  average_confidence: number;
}

interface MoodTrend {
  period: string;
  dominant_mood: string;
  mood_distribution: Record<string, number>;
  average_confidence: number;
  average_energy: number;
  total_entries: number;
  mood_shifts: number;
}

interface MoodStats {
  total_entries: number;
  first_entry_age_hours: number;
  last_entry_age_hours: number;
  most_common_mood: string;
  most_common_count: number;
}

interface MoodTimelineProps {
  onClose: () => void;
}

export default function MoodTimeline({ onClose }: MoodTimelineProps) {
  const [entries, setEntries] = useState<MoodEntry[]>([]);
  const [timeline, setTimeline] = useState<MoodTimelineBucket[]>([]);
  const [trend, setTrend] = useState<MoodTrend | null>(null);
  const [stats, setStats] = useState<MoodStats | null>(null);
  const [period, setPeriod] = useState('24h');
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'chart' | 'recent' | 'stats'>('chart');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [entriesRes, timelineRes, trendRes, statsRes] = await Promise.allSettled([
        fetch(`${BACKEND_URL}/mood/recent?count=30`),
        fetch(`${BACKEND_URL}/mood/timeline?hours=${period === '1h' ? 1 : period === '6h' ? 6 : period === '7d' ? 168 : 24}`),
        fetch(`${BACKEND_URL}/mood/trend?period=${period}`),
        fetch(`${BACKEND_URL}/mood/stats`),
      ]);
      if (entriesRes.status === 'fulfilled') {
        const data = await entriesRes.value.json();
        setEntries(data.entries || []);
      }
      if (timelineRes.status === 'fulfilled') {
        const data = await timelineRes.value.json();
        setTimeline(data.timeline || []);
      }
      if (trendRes.status === 'fulfilled') {
        setTrend(await trendRes.value.json());
      }
      if (statsRes.status === 'fulfilled') {
        setStats(await statsRes.value.json());
      }
    } catch (err) {
      console.error('Failed to fetch mood data:', err);
    }
    setLoading(false);
  }, [period]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const getTrendDirection = () => {
    if (!trend || trend.total_entries < 2) return null;
    const dist = trend.mood_distribution;
    const positiveMoods = (dist.happy || 0) + (dist.excited || 0) + (dist.calm || 0);
    const negativeMoods = (dist.frustrated || 0) + (dist.angry || 0) + (dist.sad || 0) + (dist.anxious || 0);
    if (positiveMoods > negativeMoods * 1.5) return { direction: 'improving', color: '#34d399', label: '↑ Improving' };
    if (negativeMoods > positiveMoods * 1.5) return { direction: 'declining', color: '#f87171', label: '↓ Declining' };
    return { direction: 'stable', color: '#9090a8', label: '→ Stable' };
  };

  const trendInfo = getTrendDirection();

  return (
    <div className="card-glow rounded-xl p-4 w-full max-h-[70vh] flex flex-col overflow-hidden" style={{ background: '#1A1A1A' }}>
    <div className="flex items-center justify-between mb-3">
      <h3 className="text-sm font-semibold" style={{ color: '#f0f0f5' }}>
        🎭 Mood History
      </h3>
      <button onClick={onClose} className="w-6 h-6 rounded-md flex items-center justify-center text-text-muted hover:text-text hover:bg-surface-elevated transition-all">
        ✕
      </button>
    </div>
    <div className="flex-1 flex flex-col gap-4 overflow-y-auto pr-1">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1">
          {(['1h', '6h', '24h', '7d'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className="px-2 py-0.5 text-[10px] rounded-md transition-colors"
              style={{
                background: period === p ? 'rgba(129,140,248,0.15)' : 'transparent',
                color: period === p ? '#818cf8' : '#66666a',
                border: period === p ? '1px solid rgba(129,140,248,0.2)' : '1px solid transparent',
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Trend Indicator */}
      {trendInfo && (
        <motion.div
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between px-3 py-2 rounded-lg"
          style={{
            background: 'rgba(26,23,32,0.8)',
            border: `1px solid ${trendInfo.color}22`,
          }}
        >
          <div className="flex items-center gap-2">
            <span className="text-[11px]" style={{ color: trendInfo.color }}>{trendInfo.label}</span>
            <span className="text-[10px]" style={{ color: '#66666a' }}>
              {trend?.total_entries} entries · {trend?.mood_shifts} shifts
            </span>
          </div>
          <span className="text-[11px] font-medium" style={{ color: MOOD_COLORS[trend?.dominant_mood || 'neutral'] || '#9090a8' }}>
            {MOOD_EMOJIS[trend?.dominant_mood || 'neutral'] || '😐'} {trend?.dominant_mood}
          </span>
        </motion.div>
      )}

      {/* Tab Bar */}
      <div className="flex gap-1 border-b" style={{ borderColor: '#2e2a3a' }}>
        {(['chart', 'recent', 'stats'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className="px-3 py-1.5 text-[11px] transition-colors capitalize"
            style={{
              color: activeTab === tab ? '#818cf8' : '#66666a',
              borderBottom: activeTab === tab ? '2px solid #818cf8' : '2px solid transparent',
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {loading && (
        <div className="text-center py-4 text-[11px]" style={{ color: '#66666a' }}>
          Loading mood data...
        </div>
      )}

      {/* Chart View */}
      {!loading && activeTab === 'chart' && (
        <div className="flex flex-col gap-2">
          {timeline.length === 0 ? (
            <div className="text-center py-8 text-[11px]" style={{ color: '#66666a' }}>
              No mood data yet. Mood is tracked automatically from your conversations.
            </div>
          ) : (
            <>
              {/* Simple bar chart */}
              <div className="flex items-end gap-0.5 h-24 px-1">
                {timeline.slice(-20).map((bucket, i) => {
                  const color = MOOD_COLORS[bucket.dominant_mood] || '#9090a8';
                  const height = Math.max(8, (bucket.average_confidence || 0.5) * 100);
                  return (
                    <motion.div
                      key={i}
                      initial={{ height: 0 }}
                      animate={{ height: `${height}%` }}
                      transition={{ delay: i * 0.02, type: 'spring', stiffness: 200, damping: 20 }}
                      className="flex-1 rounded-t cursor-default group relative"
                      style={{ background: color, opacity: 0.7, minWidth: 4 }}
                      title={`${bucket.dominant_mood} (${bucket.mood_count} entries) @ ${formatTime(bucket.timestamp)}`}
                    >
                      <div className="absolute -top-5 left-1/2 -translate-x-1/2 text-[9px] opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap"
                        style={{ color }}>
                        {MOOD_EMOJIS[bucket.dominant_mood] || '😐'}
                      </div>
                    </motion.div>
                  );
                })}
              </div>
              {/* Time labels */}
              <div className="flex justify-between text-[9px] px-1" style={{ color: '#66666a' }}>
                <span>{timeline.length > 0 ? formatTime(timeline[0].timestamp) : ''}</span>
                <span>{timeline.length > 0 ? formatTime(timeline[timeline.length - 1].timestamp) : ''}</span>
              </div>

              {/* Mood Distribution */}
              {trend && Object.keys(trend.mood_distribution).length > 0 && (
                <div className="mt-2 flex flex-col gap-1">
                  <span className="text-[10px] uppercase tracking-wider" style={{ color: '#66666a' }}>Distribution</span>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(trend.mood_distribution)
                      .sort(([, a], [, b]) => b - a)
                      .map(([mood, pct]) => (
                        <div key={mood} className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px]"
                          style={{ background: `${MOOD_COLORS[mood] || '#9090a8'}15`, color: MOOD_COLORS[mood] || '#9090a8' }}>
                          {MOOD_EMOJIS[mood] || '😐'} {mood} {Math.round(pct * 100)}%
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Recent View */}
      {!loading && activeTab === 'recent' && (
        <div className="flex flex-col gap-1.5">
          {entries.length === 0 ? (
            <div className="text-center py-8 text-[11px]" style={{ color: '#66666a' }}>
              No recent mood entries.
            </div>
          ) : (
            entries.map((entry, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.03 }}
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg"
                style={{ background: 'rgba(26,23,32,0.6)', border: '1px solid #2e2a3a' }}
              >
                <span className="text-sm">{MOOD_EMOJIS[entry.mood] || '😐'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] font-medium" style={{ color: MOOD_COLORS[entry.mood] || '#9090a8' }}>
                      {entry.mood}
                    </span>
                    <span className="text-[9px]" style={{ color: '#66666a' }}>
                      {Math.round(entry.confidence * 100)}%
                    </span>
                  </div>
                  {entry.message_preview && (
                    <p className="text-[10px] truncate" style={{ color: '#55556a' }}>
                      {entry.message_preview}
                    </p>
                  )}
                </div>
                <span className="text-[9px] shrink-0" style={{ color: '#66666a' }}>
                  {formatTime(entry.timestamp)}
                </span>
              </motion.div>
            ))
          )}
        </div>
      )}

      {/* Stats View */}
      {!loading && activeTab === 'stats' && stats && (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2">
            <StatCard label="Total Entries" value={stats.total_entries} color="#818cf8" />
            <StatCard label="Most Common" value={`${MOOD_EMOJIS[stats.most_common_mood] || ''} ${stats.most_common_mood}`} color={MOOD_COLORS[stats.most_common_mood] || '#9090a8'} />
            <StatCard label="First Entry" value={`${Math.round(stats.first_entry_age_hours)}h ago`} color="#c084fc" />
            <StatCard label="Last Entry" value={`${Math.round(stats.last_entry_age_hours)}h ago`} color="#34d399" />
          </div>
          {trend && (
            <div className="flex flex-col gap-1.5 mt-1">
              <span className="text-[10px] uppercase tracking-wider" style={{ color: '#66666a' }}>
                {period} Summary
              </span>
              <div className="grid grid-cols-2 gap-2">
                <StatCard label="Dominant Mood" value={`${MOOD_EMOJIS[trend.dominant_mood] || ''} ${trend.dominant_mood}`} color={MOOD_COLORS[trend.dominant_mood] || '#9090a8'} />
                <StatCard label="Avg Confidence" value={`${Math.round(trend.average_confidence * 100)}%`} color="#fbbf24" />
                <StatCard label="Mood Shifts" value={trend.mood_shifts} color="#fb923c" />
                <StatCard label="Energy Level" value={`${Math.round(trend.average_energy * 100)}%`} color="#ef4444" />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="px-3 py-2 rounded-lg" style={{ background: 'rgba(26,23,32,0.6)', border: '1px solid #2e2a3a' }}>
      <div className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: '#66666a' }}>{label}</div>
      <div className="text-[12px] font-medium" style={{ color }}>{value}</div>
    </div>
  );
}
