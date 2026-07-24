import { useState, useEffect, useRef, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { MayState, MayMood } from "../App";

interface AvatarProps {
  state: MayState;
  mood: MayMood;
  amplitude?: number; // 0.0 - 1.0, for voice lip-sync
}

// ── State Machine ──────────────────────────────────────────────────────────
// Maps (state, mood) → visual configuration
// This is the "Rive state machine" equivalent — replace with .riv inputs when ready

interface AvatarConfig {
  eyeShape: "open" | "half" | "closed" | "wide" | "happy";
  mouthShape: "neutral" | "smile" | "open" | "wide" | "small-o" | "worried" | "cat";
  eyebrowAngle: number; // -30 (raised) to 30 (furrowed)
  pupilOffset: { x: number; y: number };
  glowColor: string;
  glowIntensity: number;
  breatheScale: number;
  breatheSpeed: number;
  blinkRate: number; // seconds between blinks
  particles: boolean;
  particleColor: string;
  ringSpeed: number;
  innerGlow: boolean;
  innerGlowColor: string;
  blush: boolean;
  blushColor: string;
  tilt: number;
  squish: number;
}

function getConfig(state: MayState, mood: MayMood): AvatarConfig {
  const stateConfig: Record<MayState, Partial<AvatarConfig>> = {
    idle: {
      eyeShape: "open",
      mouthShape: "neutral",
      glowColor: "rgba(129,140,248,0.12)",
      glowIntensity: 0.12,
      breatheScale: 1.0,
      breatheSpeed: 4,
      blinkRate: 3.5,
      particles: false,
      particleColor: "#818cf8",
      ringSpeed: 12,
      innerGlow: false,
      innerGlowColor: "rgba(129,140,248,0.10)",
      blush: false,
      blushColor: "rgba(248,113,113,0.25)",
      tilt: 0,
      squish: 1.0,
    },
    thinking: {
      eyeShape: "half",
      mouthShape: "small-o",
      pupilOffset: { x: 2, y: -1 },
      eyebrowAngle: -15,
      glowColor: "rgba(192,132,252,0.20)",
      glowIntensity: 0.20,
      breatheScale: 1.03,
      breatheSpeed: 2.5,
      blinkRate: 5,
      particles: true,
      particleColor: "#c084fc",
      ringSpeed: 6,
      innerGlow: true,
      innerGlowColor: "rgba(192,132,252,0.15)",
      blush: false,
      blushColor: "rgba(248,113,113,0.25)",
      tilt: -1.5,
      squish: 1.0,
    },
    listening: {
      eyeShape: "wide",
      mouthShape: "neutral",
      pupilOffset: { x: 0, y: 0 },
      eyebrowAngle: -10,
      glowColor: "rgba(52,211,153,0.18)",
      glowIntensity: 0.18,
      breatheScale: 1.04,
      breatheSpeed: 1.5,
      blinkRate: 4,
      particles: true,
      particleColor: "#34d399",
      ringSpeed: 4,
      innerGlow: false,
      innerGlowColor: "rgba(52,211,153,0.12)",
      blush: false,
      blushColor: "rgba(248,113,113,0.25)",
      tilt: 0,
      squish: 1.0,
    },
    speaking: {
      eyeShape: "open",
      mouthShape: "open",
      pupilOffset: { x: 0, y: 0 },
      eyebrowAngle: 0,
      glowColor: "rgba(129,140,248,0.25)",
      glowIntensity: 0.25,
      breatheScale: 1.05,
      breatheSpeed: 0.8,
      blinkRate: 2.5,
      particles: true,
      particleColor: "#818cf8",
      ringSpeed: 3,
      innerGlow: true,
      innerGlowColor: "rgba(129,140,248,0.18)",
      blush: false,
      blushColor: "rgba(248,113,113,0.25)",
      tilt: 0.5,
      squish: 1.01,
    },
  };

  const moodOverrides: Record<MayMood, Partial<AvatarConfig>> = {
    neutral: {},
    happy: {
      eyeShape: "happy",
      mouthShape: "cat",
      eyebrowAngle: -5,
      glowColor: "rgba(251,191,36,0.18)",
      innerGlowColor: "rgba(251,191,36,0.12)",
      blush: true,
      blushColor: "rgba(248,113,113,0.30)",
      tilt: 1,
    },
    cool: {
      eyeShape: "half",
      mouthShape: "smile",
      eyebrowAngle: -8,
      pupilOffset: { x: 1, y: 0 },
      tilt: -1,
    },
    concerned: {
      eyeShape: "open",
      mouthShape: "worried",
      eyebrowAngle: 15,
      pupilOffset: { x: 0, y: 1 },
      glowColor: "rgba(251,191,36,0.15)",
      innerGlowColor: "rgba(251,191,36,0.10)",
      squish: 0.98,
    },
    surprised: {
      eyeShape: "wide",
      mouthShape: "wide",
      eyebrowAngle: -25,
      glowColor: "rgba(248,113,113,0.15)",
      innerGlowColor: "rgba(248,113,113,0.10)",
      tilt: 0,
      squish: 1.03,
    },
  };

  const base = stateConfig[state] || stateConfig.idle;
  const moodOvr = moodOverrides[mood] || {};

  return {
    eyeShape: moodOvr.eyeShape || base.eyeShape || "open",
    mouthShape: moodOvr.mouthShape || base.mouthShape || "neutral",
    eyebrowAngle: moodOvr.eyebrowAngle ?? base.eyebrowAngle ?? 0,
    pupilOffset: moodOvr.pupilOffset || base.pupilOffset || { x: 0, y: 0 },
    glowColor: moodOvr.glowColor || base.glowColor || "rgba(129,140,248,0.12)",
    glowIntensity: moodOvr.glowIntensity ?? base.glowIntensity ?? 0.12,
    breatheScale: moodOvr.breatheScale ?? base.breatheScale ?? 1.0,
    breatheSpeed: moodOvr.breatheSpeed ?? base.breatheSpeed ?? 4,
    blinkRate: moodOvr.blinkRate ?? base.blinkRate ?? 3.5,
    particles: moodOvr.particles ?? base.particles ?? false,
    particleColor: moodOvr.particleColor || base.particleColor || "#818cf8",
    ringSpeed: moodOvr.ringSpeed ?? base.ringSpeed ?? 12,
    innerGlow: moodOvr.innerGlow ?? base.innerGlow ?? false,
    innerGlowColor: moodOvr.innerGlowColor || base.innerGlowColor || "rgba(129,140,248,0.10)",
    blush: moodOvr.blush ?? base.blush ?? false,
    blushColor: moodOvr.blushColor || base.blushColor || "rgba(248,113,113,0.25)",
    tilt: moodOvr.tilt ?? base.tilt ?? 0,
    squish: moodOvr.squish ?? base.squish ?? 1.0,
  };
}

// ── Floating Particles (SVG-optimized) ──────────────────────────────────────
// Uses a single SVG with <circle> elements and CSS animations instead of
// nested motion.divs. ~50% fewer DOM nodes and GPU compositor layers.

function Particles({ color, count = 8, ambient = false }: { color: string; count?: number; ambient?: boolean }) {
  const particles = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        id: i,
        startAngle: (360 / count) * i,
        delay: (i / count) * (ambient ? 5 : 3),
        size: ambient ? 0.8 + Math.random() * 0.8 : 1.5 + Math.random() * 1.5,
        radius: ambient ? 52 + Math.random() * 20 : 58 + Math.random() * 14,
      })),
    [count, ambient],
  );

  const filterId = useMemo(() => `pglow-${color.replace("#", "")}-${count}`, [color, count]);

  return (
    <svg viewBox="0 0 140 140" className="absolute inset-0 w-full h-full pointer-events-none">
      <defs>
        <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="1.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      {particles.map((p) => {
        const rad = (p.startAngle * Math.PI) / 180;
        const cx = 70 + p.radius * Math.cos(rad);
        const cy = 70 + p.radius * Math.sin(rad);
        return (
          <circle
            key={p.id}
            cx={cx}
            cy={cy}
            r={p.size}
            fill={color}
            filter={`url(#${filterId})`}
            className="particle-orbit"
            style={{
              animationDelay: `${p.delay}s`,
              transformOrigin: "70px 70px",
            }}
          />
        );
      })}
    </svg>
  );
}

// ── Neural Network Pattern (thinking state) ─────────────────────────────────
// Faint interconnected nodes that appear inside the sphere when thinking

function NeuralPattern() {
  const nodes = useMemo(
    () =>
      Array.from({ length: 12 }, (_, i) => ({
        id: i,
        x: 25 + Math.random() * 30,
        y: 20 + Math.random() * 30,
        size: 1 + Math.random() * 1.5,
      })),
    [],
  );

  const connections = useMemo(() => {
    const lines: { from: number; to: number }[] = [];
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        if (Math.sqrt(dx * dx + dy * dy) < 18) {
          lines.push({ from: i, to: j });
        }
      }
    }
    return lines;
  }, [nodes]);

  return (
    <svg viewBox="0 0 80 80" className="absolute inset-0 w-full h-full pointer-events-none opacity-30">
      {connections.map((conn, i) => (
        <motion.line
          key={`conn-${i}`}
          x1={nodes[conn.from].x}
          y1={nodes[conn.from].y}
          x2={nodes[conn.to].x}
          y2={nodes[conn.to].y}
          stroke="#c084fc"
          strokeWidth="0.3"
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.4, 0] }}
          transition={{
            duration: 2,
            repeat: Infinity,
            delay: i * 0.15,
            ease: "easeInOut",
          }}
        />
      ))}
      {nodes.map((node) => (
        <motion.circle
          key={`node-${node.id}`}
          cx={node.x}
          cy={node.y}
          r={node.size}
          fill="#c084fc"
          initial={{ opacity: 0.3 }}
          animate={{ opacity: [0.3, 0.8, 0.3], r: [node.size, node.size * 1.3, node.size] }}
          transition={{
            duration: 1.5 + Math.random(),
            repeat: Infinity,
            delay: node.id * 0.1,
            ease: "easeInOut",
          }}
        />
      ))}
    </svg>
  );
}

// ── Sonar Rings (listening state) ───────────────────────────────────────────
// Concentric rings that expand outward like sonar when listening

function SonarRings() {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <motion.div
          key={`sonar-${i}`}
          className="absolute rounded-full pointer-events-none"
          style={{
            width: 120,
            height: 120,
            border: `${1.5 - i * 0.3}px solid rgba(52,211,153,${0.25 - i * 0.07})`,
          }}
          initial={{ scale: 1, opacity: 0.4 }}
          animate={{ scale: [1, 1.3 + i * 0.15], opacity: [0.4, 0] }}
          exit={{ opacity: 0 }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            delay: i * 0.3,
          }}
        />
      ))}
    </>
  );
}

// ── SVG Eye Component ──────────────────────────────────────────────────────

function Eye({
  cx,
  cy,
  shape,
  pupilOffset,
  isBlinking,
  flip,
}: {
  cx: number;
  cy: number;
  shape: "open" | "half" | "closed" | "wide" | "happy";
  pupilOffset: { x: number; y: number };
  isBlinking: boolean;
  flip?: boolean;
}) {
  const effectiveShape = isBlinking ? "closed" : shape;

  const eyeHeight =
    effectiveShape === "wide"
      ? 10
      : effectiveShape === "open"
        ? 8
        : effectiveShape === "half"
          ? 5
          : effectiveShape === "happy"
            ? 7
            : 1.5;

  const eyeWidth = effectiveShape === "happy" ? 9 : 8;

  if (effectiveShape === "happy") {
    return (
      <g transform={`translate(${cx}, ${cy})${flip ? " scale(-1,1)" : ""}`}>
        <path
          d={`M ${-eyeWidth / 2} 0 Q 0 ${-eyeHeight} ${eyeWidth / 2} 0`}
          fill="none"
          stroke="#E5E5E5"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </g>
    );
  }

  return (
    <g transform={`translate(${cx}, ${cy})${flip ? " scale(-1,1)" : ""}`}>
      <ellipse
        cx={0}
        cy={0}
        rx={eyeWidth / 2}
        ry={eyeHeight / 2}
        fill={effectiveShape === "closed" ? "none" : "#1a1a2e"}
        stroke="#E5E5E5"
        strokeWidth={effectiveShape === "closed" ? 2 : 0}
      />
      {effectiveShape !== "closed" && (
        <motion.circle
          cx={pupilOffset.x}
          cy={pupilOffset.y}
          r={effectiveShape === "wide" ? 3.5 : 3}
          fill="#E5E5E5"
          animate={{ cx: pupilOffset.x, cy: pupilOffset.y }}
          transition={{ duration: 0.3 }}
        />
      )}
      {/* Animated eye reflection — subtle drift for life-like feel */}
      {effectiveShape !== "closed" && (
        <motion.circle
          cx={pupilOffset.x + 1.2}
          cy={pupilOffset.y - 1.2}
          r={effectiveShape === "wide" ? 1.3 : 1}
          fill="white"
          animate={{
            cx: [pupilOffset.x + 1.0, pupilOffset.x + 1.4, pupilOffset.x + 1.0],
            cy: [pupilOffset.y - 1.4, pupilOffset.y - 1.0, pupilOffset.y - 1.4],
            opacity: [0.6, 0.85, 0.6],
          }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      {/* Secondary smaller reflection for depth */}
      {effectiveShape !== "closed" && effectiveShape !== "half" && (
        <motion.circle
          cx={pupilOffset.x - 1.5}
          cy={pupilOffset.y + 0.8}
          r={0.5}
          fill="white"
          animate={{ opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
        />
      )}
    </g>
  );
}

// ── SVG Mouth Component ────────────────────────────────────────────────────
// Now accepts amplitude for voice lip-sync

function Mouth({
  cx,
  cy,
  shape,
  isSpeaking,
  amplitude = 0,
}: {
  cx: number;
  cy: number;
  shape: "neutral" | "smile" | "open" | "wide" | "small-o" | "worried" | "cat";
  isSpeaking: boolean;
  amplitude?: number;
}) {
  const w = 12;

  // Amplitude-driven mouth for voice mode
  if (isSpeaking && amplitude > 0) {
    const openness = Math.min(1, amplitude * 3); // Scale up for visibility
    const mouthRx = 3.5 + openness * 2; // 3.5 to 5.5
    const mouthRy = 2.5 + openness * 2.5; // 2.5 to 5.0
    return (
      <motion.ellipse
        cx={cx}
        cy={cy}
        rx={mouthRx}
        ry={mouthRy}
        fill="#1a1a2e"
        stroke="#E5E5E5"
        strokeWidth="1.5"
        animate={{ rx: mouthRx, ry: mouthRy }}
        transition={{ duration: 0.05 }} // Near-instant response
      />
    );
  }

  switch (shape) {
    case "smile":
      return (
        <path
          d={`M ${cx - w / 2} ${cy} Q ${cx} ${cy + 6} ${cx + w / 2} ${cy}`}
          fill="none"
          stroke="#E5E5E5"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      );
    case "open":
      return (
        <motion.ellipse
          cx={cx}
          cy={cy}
          rx={isSpeaking ? 4 : 3.5}
          ry={isSpeaking ? 3 : 2.5}
          fill="#1a1a2e"
          stroke="#E5E5E5"
          strokeWidth="1.5"
          animate={{
            ry: isSpeaking ? [2.5, 3.5, 2.5] : 2.5,
            rx: isSpeaking ? [3.5, 4.5, 3.5] : 3.5,
          }}
          transition={{ duration: 0.3, repeat: isSpeaking ? Infinity : 0 }}
        />
      );
    case "wide":
      return (
        <motion.ellipse
          cx={cx}
          cy={cy}
          rx={5}
          ry={4}
          fill="#1a1a2e"
          stroke="#E5E5E5"
          strokeWidth="1.5"
        />
      );
    case "small-o":
      return (
        <circle cx={cx} cy={cy} r={2.5} fill="#1a1a2e" stroke="#E5E5E5" strokeWidth="1.5" />
      );
    case "worried":
      return (
        <path
          d={`M ${cx - w / 2} ${cy + 2} Q ${cx} ${cy - 3} ${cx + w / 2} ${cy + 2}`}
          fill="none"
          stroke="#E5E5E5"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      );
    case "cat":
      // ω cat mouth — cute "w" shape for happy/playful mood
      return (
        <path
          d={`M ${cx - 5} ${cy} Q ${cx - 2.5} ${cy + 3} ${cx} ${cy} Q ${cx + 2.5} ${cy + 3} ${cx + 5} ${cy}`}
          fill="none"
          stroke="#E5E5E5"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      );
    case "neutral":
    default:
      return (
        <line
          x1={cx - w / 2}
          y1={cy}
          x2={cx + w / 2}
          y2={cy}
          stroke="#E5E5E5"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      );
  }
}

// ── Main Avatar Component ──────────────────────────────────────────────────

export function Avatar({ state, mood, amplitude = 0 }: AvatarProps) {
  const config = getConfig(state, mood);
  const [isBlinking, setIsBlinking] = useState(false);
  const blinkTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Blinking logic — natural double-blink pattern
  useEffect(() => {
    const scheduleBlink = () => {
      const delay = config.blinkRate * 1000 + Math.random() * 1500;
      blinkTimeoutRef.current = setTimeout(() => {
        // First blink
        setIsBlinking(true);
        setTimeout(() => {
          setIsBlinking(false);
          // ~30% chance of a quick double-blink
          if (Math.random() < 0.3) {
            setTimeout(() => {
              setIsBlinking(true);
              setTimeout(() => {
                setIsBlinking(false);
                scheduleBlink();
              }, 120);
            }, 180);
          } else {
            scheduleBlink();
          }
        }, 130);
      }, delay);
    };

    scheduleBlink();
    return () => {
      if (blinkTimeoutRef.current) clearTimeout(blinkTimeoutRef.current);
    };
  }, [config.blinkRate, state]);

  const isSpeaking = state === "speaking";
  const isThinking = state === "thinking";
  const isListening = state === "listening";

  // Particle count scales with amplitude in voice mode
  const particleCount = isSpeaking && amplitude > 0
    ? Math.round(4 + amplitude * 8) // 4-12 particles
    : isThinking ? 6
    : isListening ? 8
    : isSpeaking ? 10
    : 0;
  const isIdle = state === "idle" && !isThinking && !isListening && !isSpeaking;

  return (
    <div className="relative w-36 h-36 flex items-center justify-center">
      {/* Layer 6: Outer Glow — breathing pulse driven by state */}
      <motion.div
        className="absolute rounded-full"
        style={{ width: 144, height: 144 }}
        animate={{
          boxShadow: [
            `0 0 30px ${config.glowColor}, 0 0 60px ${config.glowColor}`,
            `0 0 45px ${config.glowColor}, 0 0 90px ${config.glowColor}`,
            `0 0 30px ${config.glowColor}, 0 0 60px ${config.glowColor}`,
          ],
        }}
        transition={{ duration: 2, repeat: Infinity }}
      />

      {/* Layer 5: Orbital Rings — 3 rings at different angles and speeds */}
      {/* Ring 1: tilted 15deg, slow rotation */}
      <motion.svg
        viewBox="0 0 140 140"
        className="absolute inset-0 w-full h-full"
        style={{ opacity: 0.4, transform: "rotate(15deg)" }}
        animate={{ rotate: [15, 375] }}
        transition={{ duration: config.ringSpeed, repeat: Infinity, ease: "linear" }}
      >
        <circle
          cx="70"
          cy="70"
          r="64"
          fill="none"
          stroke="rgba(129,140,248,0.15)"
          strokeWidth="1"
          strokeDasharray="4 402"
          strokeLinecap="round"
        />
      </motion.svg>

      {/* Ring 2: tilted -8deg, counter-rotation */}
      <motion.svg
        viewBox="0 0 140 140"
        className="absolute inset-0 w-full h-full"
        style={{ opacity: 0.25, transform: "rotate(-8deg)" }}
        animate={{ rotate: [-8, -368] }}
        transition={{
          duration: config.ringSpeed * 1.5,
          repeat: Infinity,
          ease: "linear",
        }}
      >
        <circle
          cx="70"
          cy="70"
          r="58"
          fill="none"
          stroke="rgba(192,132,252,0.12)"
          strokeWidth="0.5"
          strokeDasharray="2 362"
          strokeLinecap="round"
        />
        <circle cx="128" cy="70" r="2" fill="#818cf8" opacity={0.5} />
        <circle cx="12" cy="70" r="1.5" fill="#c084fc" opacity={0.3} />
      </motion.svg>

      {/* Ring 3: tilted 35deg, fast rotation (only when active) */}
      <AnimatePresence>
        {(isThinking || isListening || isSpeaking) && (
          <motion.svg
            viewBox="0 0 140 140"
            className="absolute inset-0 w-full h-full"
            style={{ opacity: 0.2, transform: "rotate(35deg)" }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.2, rotate: [35, 395] }}
            exit={{ opacity: 0 }}
            transition={{
              opacity: { duration: 0.3 },
              rotate: { duration: config.ringSpeed * 0.6, repeat: Infinity, ease: "linear" },
            }}
          >
            <circle
              cx="70"
              cy="70"
              r="72"
              fill="none"
              stroke="rgba(129,140,248,0.10)"
              strokeWidth="0.5"
              strokeDasharray="3 450"
              strokeLinecap="round"
            />
          </motion.svg>
        )}
      </AnimatePresence>

      {/* Layer 4: Particles — orbit when active, faint ambient when idle */}
      {config.particles && particleCount > 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Particles color={config.particleColor} count={particleCount} />
        </div>
      )}
      {isIdle && (
        <div className="absolute inset-0 flex items-center justify-center" style={{ opacity: 0.4 }}>
          <Particles color="#818cf8" count={3} ambient />
        </div>
      )}

      {/* Layer 3: Glass Sphere — backdrop blur + gradient + breathing + idle sway */}
      <motion.div
        className="relative rounded-full overflow-hidden"
        style={{
          width: 112,
          height: 112,
          background: `radial-gradient(circle at 35% 30%, rgba(129,140,248,0.22) 0%, rgba(192,132,252,0.08) 40%, rgba(15,15,30,0.6) 80%)`,
          boxShadow: `
            inset 0 -6px 24px rgba(0,0,0,0.5),
            inset 0 6px 24px ${config.glowColor},
            inset 0 0 40px rgba(129,140,248,0.05),
            0 0 30px ${config.glowColor},
            0 4px 20px rgba(0,0,0,0.3)
          `,
        }}
        animate={{
          scale: [config.breatheScale, config.breatheScale * 1.015, config.breatheScale],
          rotate: config.tilt,
          scaleY: config.squish,
          y: state === "idle" ? [0, -2, 0, 2, 0] : 0,
        }}
        transition={{
          scale: { duration: config.breatheSpeed, repeat: Infinity, ease: "easeInOut" },
          rotate: { duration: 0.6, ease: "easeOut" },
          scaleY: { duration: 0.4, ease: "easeOut" },
          y: { duration: 6, repeat: Infinity, ease: "easeInOut" },
        }}
      >
        {/* Glass highlight — top-left specular */}
        <div
          className="absolute pointer-events-none"
          style={{
            top: "6%",
            left: "18%",
            width: "38%",
            height: "22%",
            background: "radial-gradient(ellipse, rgba(255,255,255,0.14) 0%, rgba(255,255,255,0.04) 40%, transparent 70%)",
            borderRadius: "50%",
            transform: "rotate(-20deg)",
          }}
        />
        {/* Glass highlight — bottom-right subtle rim */}
        <div
          className="absolute pointer-events-none"
          style={{
            bottom: "12%",
            right: "15%",
            width: "25%",
            height: "10%",
            background: "radial-gradient(ellipse, rgba(255,255,255,0.06) 0%, transparent 70%)",
            borderRadius: "50%",
            transform: "rotate(30deg)",
          }}
        />

        {/* Layer 1: Neural Pattern (thinking state) */}
        {isThinking && (
          <div className="absolute inset-0 flex items-center justify-center">
            <NeuralPattern />
          </div>
        )}

        {/* Layer 2: Face SVG — eyes, mouth, eyebrows */}
        <svg viewBox="-40 -40 80 80" className="absolute inset-0 w-full h-full" style={{ transform: "scale(0.85)" }}>
          {/* Left eye */}
          <Eye
            cx={-12}
            cy={-4}
            shape={config.eyeShape}
            pupilOffset={config.pupilOffset}
            isBlinking={isBlinking}
          />

          {/* Right eye */}
          <Eye
            cx={12}
            cy={-4}
            shape={config.eyeShape}
            pupilOffset={config.pupilOffset}
            isBlinking={isBlinking}
            flip
          />

          {/* Blush circles — shown for happy mood */}
          {config.blush && (
            <>
              <motion.ellipse
                cx={-18}
                cy={6}
                rx={6}
                ry={3.5}
                fill={config.blushColor}
                initial={{ opacity: 0 }}
                animate={{ opacity: [0.6, 0.8, 0.6] }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
              />
              <motion.ellipse
                cx={18}
                cy={6}
                rx={6}
                ry={3.5}
                fill={config.blushColor}
                initial={{ opacity: 0 }}
                animate={{ opacity: [0.6, 0.8, 0.6] }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut", delay: 0.3 }}
              />
            </>
          )}

          {/* Left eyebrow */}
          <motion.line
            x1={-18}
            y1={-14}
            x2={-6}
            y2={-14 + config.eyebrowAngle * 0.15}
            stroke="#E5E5E5"
            strokeWidth="1.5"
            strokeLinecap="round"
            animate={{ y2: -14 + config.eyebrowAngle * 0.15 }}
            transition={{ duration: 0.3 }}
          />

          {/* Right eyebrow */}
          <motion.line
            x1={6}
            y1={-14}
            x2={18}
            y2={-14 + config.eyebrowAngle * 0.15}
            stroke="#E5E5E5"
            strokeWidth="1.5"
            strokeLinecap="round"
            animate={{ y2: -14 + config.eyebrowAngle * 0.15 }}
            transition={{ duration: 0.3 }}
          />

          {/* Mouth — amplitude-driven when speaking with voice */}
          <Mouth
            cx={0}
            cy={10}
            shape={config.mouthShape}
            isSpeaking={isSpeaking}
            amplitude={amplitude}
          />
        </svg>

        {/* Layer 1: Inner Glow — pulsing overlay during thinking/speaking */}
        {config.innerGlow && (
          <motion.div
            className="absolute inset-0 rounded-full pointer-events-none"
            style={{
              background: `radial-gradient(circle at 50% 50%, ${config.innerGlowColor} 0%, transparent 60%)`,
            }}
            animate={{ opacity: [0.2, 0.4, 0.2] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        )}
      </motion.div>

      {/* Listening sonar rings */}
      <AnimatePresence>
        {isListening && <SonarRings />}
      </AnimatePresence>

      {/* Speaking amplitude waves — faster pulse when speaking */}
      <AnimatePresence>
        {isSpeaking && (
          <>
            {[0, 1, 2].map((i) => (
              <motion.div
                key={`speak-ring-${i}`}
                className="absolute rounded-full pointer-events-none"
                style={{
                  width: 120,
                  height: 120,
                  border: `1px solid rgba(129,140,248,${0.2 - i * 0.05})`,
                }}
                initial={{ scale: 1, opacity: 0.3 }}
                animate={{ scale: [1, 1.15 + i * 0.1], opacity: [0.3, 0] }}
                exit={{ opacity: 0 }}
                transition={{
                  duration: 0.8,
                  repeat: Infinity,
                  delay: i * 0.2,
                }}
              />
            ))}
          </>
        )}
      </AnimatePresence>

      {/* Thinking spinner */}
      {isThinking && (
        <motion.div
          className="absolute -top-1 -right-1 w-5 h-5"
          animate={{ rotate: 360 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
        >
          <svg width="20" height="20" viewBox="0 0 20 20">
            <circle
              cx="10"
              cy="10"
              r="8"
              fill="none"
              stroke="#c084fc"
              strokeWidth="1.5"
              strokeDasharray="12 38"
              opacity={0.7}
            />
          </svg>
        </motion.div>
      )}

      {/* Surprised sparkle effect — 6 sparkles burst outward */}
      <AnimatePresence>
        {mood === "surprised" && (
          <>
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <motion.div
                key={`sparkle-${i}`}
                className="absolute pointer-events-none"
                style={{
                  width: i % 2 === 0 ? 5 : 3,
                  height: i % 2 === 0 ? 5 : 3,
                  backgroundColor: i % 3 === 0 ? "#fbbf24" : i % 3 === 1 ? "#f472b6" : "#818cf8",
                  borderRadius: i % 2 === 0 ? "50%" : "1px",
                  transform: i % 2 !== 0 ? "rotate(45deg)" : undefined,
                  boxShadow: `0 0 8px ${i % 3 === 0 ? "#fbbf24" : i % 3 === 1 ? "#f472b6" : "#818cf8"}`,
                }}
                initial={{ scale: 0, opacity: 1 }}
                animate={{
                  scale: [0, 1.8, 0],
                  opacity: [0, 1, 0],
                  x: [0, Math.cos((i * 60 * Math.PI) / 180) * (35 + i * 4)],
                  y: [0, Math.sin((i * 60 * Math.PI) / 180) * (35 + i * 4)],
                }}
                transition={{ duration: 0.7, delay: i * 0.06, ease: "easeOut" }}
              />
            ))}
          </>
        )}
      </AnimatePresence>

      {/* Happy mood — floating hearts/stars */}
      <AnimatePresence>
        {mood === "happy" && (
          <>
            {[0, 1, 2].map((i) => (
              <motion.div
                key={`happy-${i}`}
                className="absolute pointer-events-none"
                initial={{ opacity: 0, y: 0 }}
                animate={{
                  opacity: [0, 0.8, 0],
                  y: [0, -30 - i * 10],
                  x: [(i - 1) * 15, (i - 1) * 20],
                }}
                transition={{ duration: 1.5, delay: i * 0.4, repeat: Infinity, repeatDelay: 2 }}
              >
                <span style={{ fontSize: 12, color: i % 2 === 0 ? "#f472b6" : "#fbbf24" }}>
                  {i === 0 ? "♡" : i === 1 ? "✦" : "♡"}
                </span>
              </motion.div>
            ))}
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
