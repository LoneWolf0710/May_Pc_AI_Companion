import { motion } from "framer-motion";
import type { MayState } from "../App";

interface FloatingOrbProps {
  state: MayState;
  onClick: () => void;
}

export function FloatingOrb({ state, onClick }: FloatingOrbProps) {
  const isThinking = state === "thinking";
  const isListening = state === "listening";
  const isSpeaking = state === "speaking";

  const glowColor = isListening
    ? "rgba(74,222,128,0.3)"
    : "rgba(6,182,212,0.3)";

  const sphereGradient = isListening
    ? "radial-gradient(circle at 35% 30%, rgba(74,222,128,0.25) 0%, rgba(139,92,246,0.08) 40%, rgba(0,0,0,0.5) 80%)"
    : "radial-gradient(circle at 35% 30%, rgba(6,182,212,0.25) 0%, rgba(139,92,246,0.08) 40%, rgba(0,0,0,0.5) 80%)";

  return (
    <motion.button
      onClick={onClick}
      className="relative w-20 h-20 cursor-pointer group focus-visible:outline-none"
      whileHover={{ scale: 1.08 }}
      whileTap={{ scale: 0.92 }}
    >
      {/* Outer glow */}
      <motion.div
        className="absolute inset-0 rounded-full"
        animate={{
          boxShadow: [
            `0 0 25px ${glowColor}, 0 0 50px ${glowColor.replace("0.3", "0.15")}`,
            `0 0 35px ${glowColor.replace("0.3", "0.4")}, 0 0 70px ${glowColor.replace("0.3", "0.2")}`,
            `0 0 25px ${glowColor}, 0 0 50px ${glowColor.replace("0.3", "0.15")}`,
          ],
        }}
        transition={{ duration: 2, repeat: Infinity }}
      />

      {/* Orbital ring */}
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{
          border: "1px solid rgba(6,182,212,0.15)",
          borderTopColor: "rgba(6,182,212,0.4)",
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
      />

      {/* Listening pulse rings */}
      {isListening && (
        <>
          <motion.div
            className="absolute inset-0 rounded-full"
            style={{ border: "1.5px solid rgba(74,222,128,0.2)" }}
            animate={{ scale: [1, 1.4], opacity: [0.3, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
          <motion.div
            className="absolute inset-0 rounded-full"
            style={{ border: "1px solid rgba(74,222,128,0.1)" }}
            animate={{ scale: [1, 1.6], opacity: [0.2, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, delay: 0.4 }}
          />
        </>
      )}

      {/* Thinking spinner ring */}
      {isThinking && (
        <motion.div
          className="absolute inset-0 rounded-full"
          style={{
            border: "2px solid transparent",
            borderTopColor: "rgba(139,92,246,0.5)",
            borderRightColor: "rgba(6,182,212,0.3)",
          }}
          animate={{ rotate: 360 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
        />
      )}

      {/* Speaking ring */}
      {isSpeaking && (
        <motion.div
          className="absolute inset-0 rounded-full"
          style={{ border: "1px solid rgba(6,182,212,0.2)" }}
          animate={{ scale: [1, 1.15], opacity: [0.3, 0] }}
          transition={{ duration: 0.8, repeat: Infinity }}
        />
      )}

      {/* Glass sphere core */}
      <div
        className="absolute inset-2 rounded-full"
        style={{
          background: sphereGradient,
          boxShadow: "inset 0 -3px 15px rgba(0,0,0,0.4), inset 0 3px 15px rgba(6,182,212,0.1)",
        }}
      />

      {/* Sphere highlight */}
      <div
        className="absolute rounded-full"
        style={{
          top: "18%",
          left: "25%",
          width: "30%",
          height: "15%",
          background: "radial-gradient(ellipse, rgba(255,255,255,0.12) 0%, transparent 70%)",
          transform: "rotate(-20deg)",
        }}
      />

      {/* Center glow dot */}
      <motion.div
        className="absolute inset-0 flex items-center justify-center"
        animate={
          isThinking
            ? { rotate: 360 }
            : isListening
              ? { scale: [1, 1.15, 1] }
              : {}
        }
        transition={
          isThinking
            ? { duration: 2, repeat: Infinity, ease: "linear" }
            : { duration: 1, repeat: Infinity }
        }
      >
        <div
          className="w-2.5 h-2.5 rounded-full"
          style={{
            backgroundColor: isListening ? "#4ADE80" : "#06B6D4",
            boxShadow: `0 0 8px ${isListening ? "#4ADE80" : "#06B6D4"}`,
          }}
        />
      </motion.div>

      {/* Label */}
      <motion.p
        className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-2xs font-mono text-text-muted whitespace-nowrap"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
      >
        {state === "idle"
          ? "Click to open"
          : state === "listening"
            ? "Listening..."
            : state === "thinking"
              ? "Thinking..."
              : "Speaking..."}
      </motion.p>
    </motion.button>
  );
}
