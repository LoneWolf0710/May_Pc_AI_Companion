import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { MayState } from "../App";

interface VoiceMonitorProps {
  isVisible: boolean;
  mayState: MayState;
  amplitude: number;
  frequencies: number[];
  liveTranscript: string;
  recordingDuration: number;
  maxDuration: number;
  isBackendRecording: boolean;
  onClose: () => void;
}

/**
 * Floating voice monitor panel — shows real-time mic amplitude
 * and transcribed text so the user knows May is actually listening.
 */
export function VoiceMonitor({
  isVisible,
  mayState,
  amplitude,
  frequencies,
  liveTranscript,
  recordingDuration,
  maxDuration,
  isBackendRecording,
  onClose,
}: VoiceMonitorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const prevFrequenciesRef = useRef<number[]>(new Array(16).fill(0));

  // Draw frequency bars on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    const barCount = 16;
    const gap = 3;
    const barWidth = (w - gap * (barCount - 1)) / barCount;

    ctx.clearRect(0, 0, w, h);

    // Smooth interpolation
    const smoothed = frequencies.map((val, i) => {
      const prev = prevFrequenciesRef.current[i] || 0;
      return prev + (val - prev) * 0.4;
    });
    prevFrequenciesRef.current = smoothed;

    for (let i = 0; i < barCount && i < smoothed.length; i++) {
      const val = Math.max(0.02, smoothed[i]);
      const barH = val * h * 0.9;
      const x = i * (barWidth + gap);
      const y = h - barH;

      // Gradient based on amplitude
      const hue = 180 + val * 60; // cyan to teal
      const saturation = 70 + val * 30;
      const lightness = 40 + val * 25;
      const alpha = 0.6 + val * 0.4;

      ctx.fillStyle = `hsla(${hue}, ${saturation}%, ${lightness}%, ${alpha})`;
      ctx.beginPath();
      if (ctx.roundRect) {
        ctx.roundRect(x, y, barWidth, barH, 2);
      } else {
        ctx.rect(x, y, barWidth, barH);
      }
      ctx.fill();

      // Glow effect on high bars
      if (val > 0.3) {
        ctx.shadowColor = `hsla(${hue}, ${saturation}%, ${lightness}%, 0.5)`;
        ctx.shadowBlur = 6;
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    }
  }, [frequencies]);

  const progress = maxDuration > 0 ? recordingDuration / maxDuration : 0;
  const isActive = mayState === "listening" || isBackendRecording;

  const statusText = isBackendRecording
    ? `Recording... ${Math.ceil(maxDuration - recordingDuration)}s`
    : mayState === "listening"
      ? "Listening..."
      : mayState === "thinking"
        ? "Processing..."
        : mayState === "speaking"
          ? "Speaking..."
          : "Idle";

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ x: 320, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 320, opacity: 0 }}
          transition={{ type: "spring", damping: 25, stiffness: 300 }}
          className="fixed top-2 right-2 bottom-2 w-72 z-50 flex flex-col"
        >
          <div className="h-full flex flex-col rounded-xl overflow-hidden border border-border bg-[#111111]/95 backdrop-blur-xl shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-2.5 border-b border-border">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${isActive ? "bg-success animate-pulse" : "bg-text-muted"}`} />
                <span className="text-2xs font-mono font-medium text-text-secondary uppercase tracking-wider">
                  Voice Monitor
                </span>
              </div>
              <button
                onClick={onClose}
                className="w-5 h-5 rounded flex items-center justify-center text-text-muted hover:text-text hover:bg-surface-elevated transition-colors text-xs"
              >
                x
              </button>
            </div>

            {/* Status bar */}
            <div className="px-3 py-2 border-b border-border">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-2xs font-mono text-text-muted">{statusText}</span>
                <span className="text-2xs font-mono text-accent">
                  {Math.round(amplitude * 100)}%
                </span>
              </div>

              {/* Recording progress bar */}
              {isBackendRecording && (
                <div className="w-full h-1 bg-surface-elevated rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-accent rounded-full"
                    animate={{ width: `${progress * 100}%` }}
                    transition={{ duration: 0.1 }}
                  />
                </div>
              )}

              {/* Amplitude bar */}
              <div className="w-full h-1.5 bg-surface-elevated rounded-full overflow-hidden mt-1.5">
                <motion.div
                  className="h-full rounded-full"
                  style={{
                    background: amplitude > 0.5
                      ? "linear-gradient(90deg, #06B6D4, #4ADE80)"
                      : "linear-gradient(90deg, #06B6D4, #06B6D4)",
                  }}
                  animate={{ width: `${Math.min(100, amplitude * 100)}%` }}
                  transition={{ duration: 0.05 }}
                />
              </div>
            </div>

            {/* Frequency visualization */}
            <div className="px-3 py-3 border-b border-border">
              <canvas
                ref={canvasRef}
                className="w-full h-20"
                style={{ imageRendering: "auto" }}
              />
            </div>

            {/* Transcript display */}
            <div className="flex-1 px-3 py-3 overflow-y-auto">
              <div className="text-2xs font-mono text-text-muted uppercase tracking-wider mb-2">
                Transcript
              </div>
              {liveTranscript ? (
                <div className="text-sm text-text leading-relaxed">
                  {liveTranscript}
                  {isBackendRecording && (
                    <span className="inline-block w-1.5 h-4 bg-accent/60 ml-0.5 animate-pulse align-middle" />
                  )}
                </div>
              ) : (
                <div className="text-xs text-text-muted/50 italic">
                  {isActive ? "Waiting for speech..." : "Click mic to start"}
                </div>
              )}
            </div>

            {/* Footer with amplitude numeric */}
            <div className="px-3 py-2 border-t border-border flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="text-2xs font-mono">
                  <span className="text-text-muted">Peak </span>
                  <span className="text-accent">{(amplitude * 100).toFixed(1)}%</span>
                </div>
              </div>
              <div className="text-2xs font-mono text-text-muted">
                {frequencies.length} bands
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
