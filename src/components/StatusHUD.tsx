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
}

interface SystemStats {
  ram_percent: number;
  gpu_percent: number | null;
}

export function StatusHUD({
  mayState,
  isConnected,
  isMockMode,
  models,
  selectedModel,
  selectedProvider,
  onSelectModel,
  onOpenSettings,
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
                className="h-full bg-[#06B6D4] rounded-full"
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
                className="h-full bg-[#8B5CF6] rounded-full"
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
