import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { BACKEND_URL } from "../config";

export interface ProactiveSuggestion {
  type: string;
  rule: string;
  message: string;
  context?: {
    active_app?: string;
    window_title?: string;
  };
  timestamp: number;
  shown?: boolean;
}

interface ProactiveSuggestionsProps {
  onSuggestionClick?: (message: string) => void;
  controlMode?: string;
}

const RULE_ICONS: Record<string, string> = {
  error_dialog: "⚠️",
  ui_error_dialog: "🔴",
  permission_prompt: "🔐",
  installer_detected: "📦",
  same_page_5min: "🕐",
  email_compose: "✉️",
  low_battery: "🔋",
  // Wellness rules
  water: "💧",
  posture: "🧍",
  break: "🧘",
  eyes: "👁️",
  // Context rules
  context: "🌙",
};

const RULE_COLORS: Record<string, string> = {
  ui_error_dialog: "border-danger/30 bg-danger/5",
  error_dialog: "border-warning/30 bg-warning/5",
  permission_prompt: "border-accent/30 bg-accent/5",
  installer_detected: "border-purple/30 bg-purple/5",
  low_battery: "border-warning/30 bg-warning/5",
};

function getRuleIcon(rule: string): string {
  if (RULE_ICONS[rule]) return RULE_ICONS[rule];
  if (rule.startsWith("ui_")) return "🔍";
  return "💡";
}

function getRuleColor(rule: string): string {
  if (RULE_COLORS[rule]) return RULE_COLORS[rule];
  if (rule.includes("error") || rule.includes("fail")) return "border-danger/20 bg-danger/5";
  return "border-border bg-surface-elevated";
}

function timeAgo(ts: number): string {
  const sec = Math.floor((Date.now() / 1000) - ts);
  if (sec < 0) return "just now";
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  return `${Math.floor(sec / 3600)}h ago`;
}

export function ProactiveSuggestions({
  onSuggestionClick,
  controlMode = "normal",
}: ProactiveSuggestionsProps) {
  const [suggestions, setSuggestions] = useState<ProactiveSuggestion[]>([]);
  const fetchSuggestions = useCallback(async () => {
    try {
      const sugRes = await fetch(`${BACKEND_URL}/screen/suggestions`, { signal: AbortSignal.timeout(3000) });

      if (sugRes.ok) {
        const data = await sugRes.json();
        const newSuggestions = data.suggestions || [];
        if (newSuggestions.length > 0) {
          setSuggestions((prev) => {
            // Deduplicate by rule+timestamp window (within 30s = same suggestion)
            const merged = [...prev];
            for (const sug of newSuggestions) {
              const isDup = merged.some(
                (existing) =>
                  existing.rule === sug.rule &&
                  Math.abs(existing.timestamp - sug.timestamp) < 30,
              );
              if (!isDup) {
                merged.push(sug);
              }
            }
            // Keep max 5 most recent, sorted by timestamp desc
            return merged
              .sort((a, b) => b.timestamp - a.timestamp)
              .slice(0, 5);
          });
        }
      }
    } catch {
      // Silently fail — keep showing last known suggestions
    }
  }, []);

  // Poll every 10 seconds
  useEffect(() => {
    fetchSuggestions();
    const interval = setInterval(fetchSuggestions, 10000);
    return () => clearInterval(interval);
  }, [fetchSuggestions]);

  const dismissSuggestion = useCallback(async (suggestion: ProactiveSuggestion) => {
    setSuggestions((prev) => prev.filter((s) => s !== suggestion));
    // Mark as acknowledged on backend
    try {
      await fetch(`${BACKEND_URL}/screen/suggestions/acknowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rule: suggestion.rule }),
        signal: AbortSignal.timeout(2000),
      });
    } catch {
      // Best effort
    }
  }, []);

  const handleAction = useCallback(
    (suggestion: ProactiveSuggestion) => {
      if (onSuggestionClick) {
        // Send the suggestion context as a chat message
        const contextStr = suggestion.context?.window_title
          ? ` in "${suggestion.context.window_title}"`
          : "";
        onSuggestionClick(`${suggestion.message}${contextStr}`);
      }
      dismissSuggestion(suggestion);
    },
    [onSuggestionClick, dismissSuggestion],
  );

  // Don't show in silent mode
  if (controlMode === "silent") return null;

  if (suggestions.length === 0) return null;

  return (
    <div className="fixed bottom-20 right-4 z-40 flex flex-col gap-2 max-w-[320px]">
      <AnimatePresence>
        {suggestions.map((sug, idx) => (
          <motion.div
            key={`${sug.rule}-${sug.timestamp}-${idx}`}
            initial={{ opacity: 0, x: 40, scale: 0.9 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 40, scale: 0.9 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className={`suggestion-card relative border rounded-xl px-3 py-2.5 shadow-panel ${getRuleColor(sug.rule)}`}
          >
            {/* Header row */}
            <div className="flex items-center justify-between gap-2 mb-1">
              <div className="flex items-center gap-1.5">
                <span className="text-sm">{getRuleIcon(sug.rule)}</span>
                <span className="text-2xs font-mono font-medium text-text-secondary uppercase tracking-wider">
                  {sug.rule.replace(/_/g, " ")}
                </span>
              </div>
              <span className="text-2xs font-mono text-text-muted">
                {timeAgo(sug.timestamp)}
              </span>
            </div>

            {/* Message */}
            <p className="text-xs text-text leading-relaxed mb-2">
              {sug.message}
            </p>

            {/* Context */}
            {sug.context?.window_title && (
              <p className="text-2xs font-mono text-text-muted truncate mb-2">
                📄 {sug.context.window_title}
              </p>
            )}

            {/* Actions */}
            <div className="flex items-center gap-2">
              {onSuggestionClick && (
                <button
                  onClick={() => handleAction(sug)}
                  className="suggestion-action px-2 py-1 rounded-lg bg-accent/10 border border-accent/20 text-2xs font-mono text-accent hover:bg-accent/20 hover:border-accent/30 transition-all"
                >
                  Help me
                </button>
              )}
              <button
                onClick={() => dismissSuggestion(sug)}
                className="px-2 py-1 rounded-lg bg-surface border border-border text-2xs font-mono text-text-muted hover:text-text hover:border-border-hover transition-all"
              >
                Dismiss
              </button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
