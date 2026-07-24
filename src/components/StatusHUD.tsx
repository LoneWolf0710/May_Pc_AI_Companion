import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import type { MayState } from "../App";
import { ModelSelector } from "./ModelSelector";
import { BACKEND_URL } from "../config";

interface ModelInfo {
  provider: string;
  provider_name: string;
  id: string;
  name: string;
  fast: boolean;
  available: boolean;
}

interface StatusHUDProps {
  mayState: MayState;
  isConnected?: boolean | null;
  isMockMode?: boolean | null;
  models: ModelInfo[];
  selectedModel: string;
  selectedProvider: string;
  onSelectModel: (provider: string, model: string) => void;
  onOpenSettings: () => void;
  controlMode?: string;
  onSetControlMode?: (mode: string) => void;
  personalityMode?: string;
  personalityProfiles?: Record<string, { name: string; description: string }>;
  onSetPersonality?: (mode: string) => void;
}

const PERSONALITY_ICONS: Record<string, string> = {
  shikimori: "🌸",
  formal: "💼",
  debug: "🐛",
  silent: "🤫",
  playful: "✨",
};

interface SystemStats {
  ram_percent: number;
  gpu_percent: number | null;
}

const MODE_ICONS: Record<string, string> = {
  normal: "🟢",
  focus: "🎯",
  silent: "🔇",
  automation: "🤖",
};
const MODE_LABELS: Record<string, string> = {
  normal: "Normal",
  focus: "Focus",
  silent: "Silent",
  automation: "Auto",
};

export function StatusHUD({
  mayState,
  isConnected,
  isMockMode,
  models,
  selectedModel,
  selectedProvider,
  onSelectModel,
  onOpenSettings,
  controlMode = "normal",
  onSetControlMode,
  personalityMode = "shikimori",
  personalityProfiles = {},
  onSetPersonality,
}: StatusHUDProps) {
  const [time, setTime] = useState(new Date());
  const [stats, setStats] = useState<SystemStats>({ ram_percent: 0, gpu_percent: null });

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Poll system stats every 3 seconds
  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/system/stats`, {
        signal: AbortSignal.timeout(3000),
      });
      if (res.ok) {
        const data: SystemStats = await res.json();
        setStats(data);
      }
    } catch {
      // Silently fail — keep showing last known values
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 3000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  const formatTime = (d: Date) =>
    d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });

  const formatDate = (d: Date) =>
    d.toLocaleDateString("en-US", { month: "short", day: "numeric" });

  const dotClass = mayState === "idle" ? "online" : "busy";

  const connectionLabel =
    isConnected === true
      ? isMockMode
        ? "Mock"
        : "Connected"
      : isConnected === false
        ? "Offline"
        : "...";

  const gpuPercent = stats.gpu_percent ?? 0;
  const ramPercent = stats.ram_percent;

  return (
    <div className="border-b border-border px-4 py-2.5">
      <div className="flex items-center justify-between">
        {/* Left — State + connection */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className={`status-dot ${dotClass}`} />
            <span className="text-2xs font-mono text-text-secondary uppercase tracking-[0.12em]">
              {mayState === "idle" ? "Online" : mayState === "listening" ? "Listen" : mayState === "thinking" ? "Process" : "Speak"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isConnected === true
                  ? isMockMode
                    ? "bg-warning"
                    : "bg-success"
                  : isConnected === false
                    ? "bg-danger"
                    : "bg-text-muted"
              }`}
            />
            <span className="text-2xs font-mono text-text-muted">{connectionLabel}</span>
          </div>
        </div>

        {/* Center — Time + date */}
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm font-medium text-text tracking-wider">
            {formatTime(time)}
          </span>
          <span className="text-2xs font-mono text-text-muted">{formatDate(time)}</span>
        </div>

        {/* Right — Model selector + GPU/RAM stats */}
        <div className="flex items-center gap-3">
          {/* Control Mode selector */}
          {onSetControlMode && (
            <div className="relative group">
              <button
                className={`flex items-center gap-1 px-2 py-1 rounded-lg border text-2xs font-mono transition-all ${
                  controlMode !== "normal"
                    ? "bg-accent/15 border-accent/30 text-accent"
                    : "bg-surface-elevated border-border text-text-muted hover:border-accent/20"
                }`}
                title={`Mode: ${MODE_LABELS[controlMode] || controlMode}`}
              >
                <span>{MODE_ICONS[controlMode] || "🟢"}</span>
                <span className="hidden sm:inline">{MODE_LABELS[controlMode] || controlMode}</span>
                <svg width="8" height="8" viewBox="0 0 8 8" className="opacity-50">
                  <path d="M1 3l3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                </svg>
              </button>
              {/* Dropdown */}
              <div className="absolute right-0 top-full mt-1 hidden group-hover:block z-50">
                <div className="bg-surface-elevated border border-border rounded-lg shadow-panel py-1 min-w-[100px]">
                  {Object.entries(MODE_LABELS).map(([mode, label]) => (
                    <button
                      key={mode}
                      onClick={() => onSetControlMode(mode)}
                      className={`w-full flex items-center gap-2 px-3 py-1.5 text-2xs font-mono transition-colors ${
                        controlMode === mode
                          ? "bg-accent/10 text-accent"
                          : "text-text-secondary hover:bg-surface hover:text-text"
                      }`}
                    >
                      <span>{MODE_ICONS[mode]}</span>
                      <span>{label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Personality Mode selector */}
          {onSetPersonality && (
            <div className="relative group">
              <button
                className={`flex items-center gap-1 px-2 py-1 rounded-lg border text-2xs font-mono transition-all ${
                  personalityMode !== "shikimori"
                    ? "bg-purple/15 border-purple/30 text-purple"
                    : "bg-surface-elevated border-border text-text-muted hover:border-purple/20"
                }`}
                title={`Personality: ${personalityProfiles[personalityMode]?.name || personalityMode}`}
              >
                <span>{PERSONALITY_ICONS[personalityMode] || "🌸"}</span>
                <span className="hidden sm:inline">{personalityProfiles[personalityMode]?.name || personalityMode}</span>
                <svg width="8" height="8" viewBox="0 0 8 8" className="opacity-50">
                  <path d="M1 3l3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                </svg>
              </button>
              <div className="absolute right-0 top-full mt-1 hidden group-hover:block z-50">
                <div className="bg-surface-elevated border border-border rounded-lg shadow-panel py-1 min-w-[100px]">
                  {Object.entries(personalityProfiles).map(([key, p]) => (
                    <button
                      key={key}
                      onClick={() => onSetPersonality(key)}
                      className={`w-full flex items-center gap-2 px-3 py-1.5 text-2xs font-mono transition-colors ${
                        personalityMode === key
                          ? "bg-purple/10 text-purple"
                          : "text-text-secondary hover:bg-surface hover:text-text"
                      }`}
                    >
                      <span>{PERSONALITY_ICONS[key] || "🤖"}</span>
                      <span>{p.name || key}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Model Selector */}
          <ModelSelector
            models={models}
            selectedModel={selectedModel}
            selectedProvider={selectedProvider}
            onSelect={onSelectModel}
            onOpenSettings={onOpenSettings}
          />

          <div className="w-px h-4 bg-border" />

          <div className="flex items-center gap-2">
            <span className="text-2xs font-mono text-text-secondary">GPU</span>
            <div className="w-16 h-2 bg-[#1A1A1A] border border-border rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-accent rounded-full"
                animate={{ width: `${gpuPercent}%` }}
                transition={{ duration: 0.5, ease: "easeOut" }}
              />
            </div>
            <span className="text-2xs font-mono text-text-muted w-7 text-right">
              {stats.gpu_percent !== null ? `${Math.round(gpuPercent)}%` : "--"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-2xs font-mono text-text-secondary">RAM</span>
            <div className="w-16 h-2 bg-[#1A1A1A] border border-border rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-lavender rounded-full"
                animate={{ width: `${ramPercent}%` }}
                transition={{ duration: 0.5, ease: "easeOut" }}
              />
            </div>
            <span className="text-2xs font-mono text-text-muted w-7 text-right">
              {Math.round(ramPercent)}%
            </span>
          </div>
        </div>
      </div>

      {/* Thin accent bar when active */}
      {mayState !== "idle" && (
        <motion.div
          className="h-[1px] bg-gradient-to-r from-accent/40 via-purple/30 to-transparent mt-2"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.3 }}
          style={{ transformOrigin: "left" }}
        />
      )}
    </div>
  );
}
