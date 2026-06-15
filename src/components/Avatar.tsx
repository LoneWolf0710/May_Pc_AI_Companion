import { motion } from "framer-motion";
import type { MayState, MayMood } from "../App";

interface AvatarProps {
  state: MayState;
  mood: MayMood;
}

export function Avatar({ state }: AvatarProps) {
  const isThinking = state === "thinking";
  const isListening = state === "listening";
  const isSpeaking = state === "speaking";

  const glowIntensity =
    state === "thinking"
      ? "0 0 40px rgba(6,182,212,0.3), 0 0 80px rgba(6,182,212,0.15)"
      : state === "listening"
        ? "0 0 50px rgba(74,222,128,0.3), 0 0 100px rgba(74,222,128,0.15)"
        : state === "speaking"
          ? "0 0 60px rgba(6,182,212,0.35), 0 0 120px rgba(6,182,212,0.2)"
          : "0 0 30px rgba(6,182,212,0.15), 0 0 60px rgba(6,182,212,0.06)";

  const accentGradient =
    state === "listening"
      ? "radial-gradient(circle at 35% 30%, rgba(74,222,128,0.30) 0%, rgba(139,92,246,0.12) 40%, rgba(0,0,0,0.5) 80%)"
      : "radial-gradient(circle at 35% 30%, rgba(6,182,212,0.30) 0%, rgba(139,92,246,0.12) 40%, rgba(0,0,0,0.5) 80%)";

  const pulseAnim = isListening
    ? { scale: [1, 1.03, 1] }
    : isSpeaking
      ? { scale: [1, 1.05, 1] }
      : isThinking
        ? { scale: [1, 1.02, 1] }
        : {};

  const pulseDuration = isSpeaking ? 0.8 : isListening ? 1.5 : isThinking ? 2 : 2;

  return (
    <div className="relative w-36 h-36 flex items-center justify-center">
      {/* Outermost glow ring */}
      <motion.div
        className="absolute inset-0 rounded-full"
        animate={{
          boxShadow: [
            glowIntensity,
            glowIntensity.replace("0.3", "0.4").replace("0.15", "0.2").replace("0.35", "0.45").replace("0.2", "0.25"),
            glowIntensity,
          ],
        }}
        transition={{ duration: 2, repeat: Infinity }}
      />

      {/* Orbital ring 1 — slow rotation */}
      <motion.svg
        viewBox="0 0 140 140"
        className="absolute inset-0 w-full h-full"
        animate={{ rotate: 360 }}
        transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
        style={{ opacity: 0.5 }}
      >
        <circle
          cx="70"
          cy="70"
          r="64"
          fill="none"
          stroke="#06B6D420"
          strokeWidth="1"
          strokeDasharray="4 402"
          strokeLinecap="round"
        />
      </motion.svg>

      {/* Orbital ring 2 — counter-rotation */}
      <motion.svg
        viewBox="0 0 140 140"
        className="absolute inset-0 w-full h-full"
        animate={{ rotate: -360 }}
        transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
        style={{ opacity: 0.3 }}
      >
        <circle
          cx="70"
          cy="70"
          r="58"
          fill="none"
          stroke="#8B5CF630"
          strokeWidth="0.5"
          strokeDasharray="2 362"
          strokeLinecap="round"
        />
        {/* Orbiting micro particles */}
        <circle cx="128" cy="70" r="2" fill="#06B6D4" opacity={0.6} />
        <circle cx="12" cy="70" r="1.5" fill="#8B5CF6" opacity={0.4} />
      </motion.svg>

      {/* Main glass sphere */}
      <motion.div
        className="glass-sphere w-28 h-28"
        style={{
          background: accentGradient,
        }}
        animate={pulseAnim}
        transition={{ duration: pulseDuration, repeat: Infinity }}
      />

      {/* Inner glow overlay on thinking/speaking */}
      {(isThinking || isSpeaking) && (
        <motion.div
          className="absolute w-28 h-28 rounded-full"
          style={{
            background: "radial-gradient(circle at 50% 50%, rgba(6,182,212,0.15) 0%, transparent 60%)",
          }}
          animate={{ opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
      )}

      {/* Listening concentric rings */}
      {isListening && (
        <>
          <motion.div
            className="absolute rounded-full"
            style={{
              width: 120,
              height: 120,
              border: "1.5px solid rgba(74,222,128,0.25)",
            }}
            animate={{ scale: [1, 1.35], opacity: [0.4, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
          <motion.div
            className="absolute rounded-full"
            style={{
              width: 120,
              height: 120,
              border: "1px solid rgba(74,222,128,0.15)",
            }}
            animate={{ scale: [1, 1.55], opacity: [0.3, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, delay: 0.4 }}
          />
        </>
      )}

      {/* Speaking amplitude waves */}
      {isSpeaking && (
        <>
          <motion.div
            className="absolute rounded-full"
            style={{
              width: 120,
              height: 120,
              border: "1px solid rgba(6,182,212,0.2)",
            }}
            animate={{ scale: [1, 1.2], opacity: [0.3, 0] }}
            transition={{ duration: 0.8, repeat: Infinity }}
          />
          <motion.div
            className="absolute rounded-full"
            style={{
              width: 120,
              height: 120,
              border: "1px solid rgba(139,92,246,0.15)",
            }}
            animate={{ scale: [1, 1.3], opacity: [0.2, 0] }}
            transition={{ duration: 0.8, repeat: Infinity, delay: 0.25 }}
          />
        </>
      )}

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
              stroke="#8B5CF6"
              strokeWidth="1.5"
              strokeDasharray="12 38"
              opacity={0.7}
            />
          </svg>
        </motion.div>
      )}
    </div>
  );
}
