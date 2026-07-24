import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { BACKEND_URL } from "../config";

interface WeatherData {
  location: string;
  temperature: number;
  feels_like: number;
  humidity: number;
  wind_speed: number;
  wind_direction: string;
  condition: string;
  condition_icon: string;
  uv_index: number;
  daily: { date: string; condition: string; temp_min: number; temp_max: number }[];
}

interface NewsItem {
  title: string;
  link: string;
  source: string;
  summary: string;
}

interface CalendarEvent {
  summary: string;
  start: string;
  end: string | null;
  location: string;
}

interface BriefingData {
  weather: WeatherData | null;
  news: { items: NewsItem[] } | null;
  calendar: { events: CalendarEvent[] } | null;
  reminders: { message: string; remind_at: string }[];
}

interface MorningBriefingProps {
  onDismiss: () => void;
  onSendMessage: (message: string) => void;
}

function getWeatherEmoji(condition: string): string {
  const lower = condition.toLowerCase();
  if (lower.includes("clear")) return "\u2600\ufe0f";
  if (lower.includes("cloud")) return "\u2601\ufe0f";
  if (lower.includes("rain") || lower.includes("drizzle")) return "\ud83c\udf27\ufe0f";
  if (lower.includes("snow")) return "\u2744\ufe0f";
  if (lower.includes("fog")) return "\ud83c\udf2b\ufe0f";
  if (lower.includes("thunder")) return "\u26c8\ufe0f";
  return "\ud83c\udf24\ufe0f";
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00");
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  if (date.toDateString() === today.toDateString()) return "Today";
  if (date.toDateString() === tomorrow.toDateString()) return "Tomorrow";
  return date.toLocaleDateString("en-US", { weekday: "short" });
}

const DOTS_FRAMES = ["", ".", "..", "..."];

function LoadingDots() {
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setFrame((f) => (f + 1) % DOTS_FRAMES.length), 400);
    return () => clearInterval(id);
  }, []);
  return <span>{DOTS_FRAMES[frame]}</span>;
}

export function MorningBriefing({ onDismiss, onSendMessage }: MorningBriefingProps) {
  const [data, setData] = useState<BriefingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(true);

  const fetchBriefing = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch all sections in parallel (single set of requests, no redundancy)
      const [weatherRes, newsRes, calendarRes, remindersRes] = await Promise.allSettled([
        fetch(`${BACKEND_URL}/weather`, { signal: AbortSignal.timeout(8000) }),
        fetch(`${BACKEND_URL}/news?category=technology&max_items=3`, { signal: AbortSignal.timeout(8000) }),
        fetch(`${BACKEND_URL}/calendar?days=1`, { signal: AbortSignal.timeout(5000) }),
        fetch(`${BACKEND_URL}/reminders`, { signal: AbortSignal.timeout(3000) }),
      ]);

      const weather = weatherRes.status === "fulfilled" && weatherRes.value.ok
        ? await weatherRes.value.json() : null;
      const news = newsRes.status === "fulfilled" && newsRes.value.ok
        ? await newsRes.value.json() : null;
      const calendar = calendarRes.status === "fulfilled" && calendarRes.value.ok
        ? await calendarRes.value.json() : null;
      const remindersData = remindersRes.status === "fulfilled" && remindersRes.value.ok
        ? await remindersRes.value.json() : null;

      setData({
        weather,
        news,
        calendar,
        reminders: remindersData?.reminders ?? [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load briefing");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBriefing();
  }, [fetchBriefing]);

  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-4 mb-3"
      >
        <div className="briefing-card bg-surface border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">{"\u2615"}</span>
            <span className="text-xs font-medium text-text">Morning Briefing</span>
            <span className="ml-auto text-2xs text-text-muted">Loading<LoadingDots /></span>
          </div>
          <div className="space-y-2">
            <div className="skeleton-line h-3 w-3/4 rounded" />
            <div className="skeleton-line h-3 w-1/2 rounded" />
            <div className="skeleton-line h-3 w-2/3 rounded" />
          </div>
        </div>
      </motion.div>
    );
  }

  if (error || !data) {
    return (
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className="mx-4 mb-3"
      >
        <div className="bg-surface border border-border rounded-xl p-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm">{"\u26a0\ufe0f"}</span>
            <span className="text-xs text-text-muted">Briefing unavailable: {error}</span>
          </div>
          <button
            onClick={onDismiss}
            className="text-2xs text-text-muted hover:text-text transition-colors px-2 py-1"
          >
            dismiss
          </button>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="mx-4 mb-3"
    >
      <div className="briefing-card bg-surface border border-border rounded-xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
          <div className="flex items-center gap-2">
            <span className="text-lg">{"\ud83c\udf1e"}</span>
            <span className="text-xs font-medium text-text">Morning Briefing</span>
            <span className="text-2xs font-mono text-text-muted">
              {new Date().toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" })}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setExpanded(!expanded)}
              className="w-6 h-6 rounded-lg flex items-center justify-center text-text-muted hover:text-text hover:bg-surface-elevated transition-all"
              title={expanded ? "Collapse" : "Expand"}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d={expanded ? "m18 15-6-6-6 6" : "m6 9 6 6 6-6"} />
              </svg>
            </button>
            <button
              onClick={onDismiss}
              className="w-6 h-6 rounded-lg flex items-center justify-center text-text-muted hover:text-text hover:bg-surface-elevated transition-all"
              title="Dismiss"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6 6 18" />
                <path d="m6 6 12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="p-4 space-y-3">
                {/* Weather Section */}
                {data.weather && (
                  <div className="briefing-section">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm">{getWeatherEmoji(data.weather.condition)}</span>
                      <span className="text-2xs font-medium text-text uppercase tracking-wider">Weather</span>
                      <span className="text-2xs text-text-muted ml-auto">{data.weather.location}</span>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="text-center">
                        <span className="text-2xl">{getWeatherEmoji(data.weather.condition)}</span>
                        <p className="text-2xs text-text-muted mt-0.5">{data.weather.condition}</p>
                      </div>
                      <div className="flex-1">
                        <div className="flex items-baseline gap-1">
                          <span className="text-lg font-semibold text-text">{Math.round(data.weather.temperature)}</span>
                          <span className="text-xs text-text-muted">°C</span>
                          <span className="text-2xs text-text-muted ml-1">(feels {Math.round(data.weather.feels_like)}°)</span>
                        </div>
                        <div className="flex gap-3 mt-1">
                          <span className="text-2xs text-text-muted">{data.weather.humidity}% hum</span>
                          <span className="text-2xs text-text-muted">{Math.round(data.weather.wind_speed)} km/h {data.weather.wind_direction}</span>
                          {data.weather.uv_index > 3 && (
                            <span className="text-2xs text-warning">UV {data.weather.uv_index.toFixed(1)}</span>
                          )}
                        </div>
                      </div>
                    </div>
                    {/* 3-day forecast */}
                    {data.weather.daily && data.weather.daily.length > 0 && (
                      <div className="flex gap-2 mt-2 pt-2 border-t border-border/50">
                        {data.weather.daily.map((day, i) => (
                          <div key={i} className="flex-1 text-center">
                            <p className="text-2xs text-text-muted">{formatDate(day.date)}</p>
                            <p className="text-sm">{getWeatherEmoji(day.condition)}</p>
                            <p className="text-2xs text-text">
                              {Math.round(day.temp_max)}° / {Math.round(day.temp_min)}°
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* News Section */}
                {data.news && data.news.items && data.news.items.length > 0 && (
                  <div className="briefing-section">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm">{"\ud83d\udcf0"}</span>
                      <span className="text-2xs font-medium text-text uppercase tracking-wider">Tech News</span>
                    </div>
                    <div className="space-y-1.5">
                      {data.news.items.map((item, i) => (
                        <a
                          key={i}
                          href={item.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="briefing-news-item block px-3 py-2 rounded-lg bg-surface-elevated border border-border hover:border-accent/30 transition-all group"
                        >
                          <p className="text-xs text-text group-hover:text-accent transition-colors leading-snug">
                            {item.title}
                          </p>
                          <p className="text-2xs text-text-muted mt-0.5">{item.source}</p>
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* Calendar Section */}
                {data.calendar && data.calendar.events && data.calendar.events.length > 0 && (
                  <div className="briefing-section">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm">{"\ud83d\udcc5"}</span>
                      <span className="text-2xs font-medium text-text uppercase tracking-wider">Calendar</span>
                    </div>
                    <div className="space-y-1.5">
                      {data.calendar.events.map((event, i) => {
                        const time = new Date(event.start).toLocaleTimeString("en-US", {
                          hour: "numeric",
                          minute: "2-digit",
                        });
                        return (
                          <div key={i} className="px-3 py-2 rounded-lg bg-surface-elevated border border-border">
                            <div className="flex items-center gap-2">
                              <span className="text-2xs font-mono text-accent">{time}</span>
                              <span className="text-xs text-text">{event.summary}</span>
                            </div>
                            {event.location && (
                              <p className="text-2xs text-text-muted mt-0.5 ml-8">{event.location}</p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Reminders Section */}
                {data.reminders && data.reminders.length > 0 && (
                  <div className="briefing-section">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm">{"\ud83d\udd14"}</span>
                      <span className="text-2xs font-medium text-text uppercase tracking-wider">Reminders</span>
                    </div>
                    <div className="space-y-1.5">
                      {data.reminders.map((r, i) => (
                        <div key={i} className="px-3 py-2 rounded-lg bg-surface-elevated border border-border">
                          <p className="text-xs text-text">{r.message}</p>
                          {r.remind_at && (
                            <p className="text-2xs text-text-muted mt-0.5">due: {r.remind_at}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Quick actions */}
                <div className="flex gap-2 pt-2 border-t border-border/50">
                  <button
                    onClick={() => onSendMessage("what's the weather like?")}
                    className="briefing-action text-2xs px-3 py-1.5 rounded-lg bg-surface-elevated border border-border text-text-muted hover:text-accent hover:border-accent/30 transition-all"
                  >
                    {"\ud83c\udf24\ufe0f"} Details
                  </button>
                  <button
                    onClick={() => onSendMessage("what's the news today?")}
                    className="briefing-action text-2xs px-3 py-1.5 rounded-lg bg-surface-elevated border border-border text-text-muted hover:text-accent hover:border-accent/30 transition-all"
                  >
                    {"\ud83d\udcf0"} More news
                  </button>
                  <button
                    onClick={() => onSendMessage("what's on my schedule?")}
                    className="briefing-action text-2xs px-3 py-1.5 rounded-lg bg-surface-elevated border border-border text-text-muted hover:text-accent hover:border-accent/30 transition-all"
                  >
                    {"\ud83d\udcc5"} Schedule
                  </button>
                  <button
                    onClick={fetchBriefing}
                    className="briefing-action text-2xs px-3 py-1.5 rounded-lg bg-surface-elevated border border-border text-text-muted hover:text-accent hover:border-accent/30 transition-all ml-auto"
                  >
                    {"\ud83d\udd04"} Refresh
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
