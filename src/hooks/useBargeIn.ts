import { useRef, useCallback, useEffect } from "react";

interface BargeInOptions {
  /** Whether TTS is currently playing */
  isSpeaking: boolean;
  /** Current mic amplitude (0.0 - 1.0) */
  amplitude: number;
  /** Whether mic is currently capturing */
  isCapturing: boolean;
  /** Callback to stop TTS when barge-in detected */
  onBargeIn: () => void;
  /** Amplitude threshold to detect user speaking (default 0.15) */
  threshold?: number;
  /** How many consecutive frames above threshold before triggering (default 3) */
  consecutiveFrames?: number;
  /** Cooldown after barge-in to prevent re-triggering (ms, default 1000) */
  cooldownMs?: number;
}

/**
 * Detects barge-in: when May is speaking and the user starts talking,
 * automatically stops the TTS playback.
 *
 * Uses amplitude analysis from the mic monitor. If the mic amplitude
 * exceeds a threshold for several consecutive frames (debounce), it
 * triggers the barge-in callback.
 *
 * All config values stored in refs to avoid recreating checkBargeIn on every render.
 */
export function useBargeIn({
  isSpeaking,
  amplitude,
  isCapturing,
  onBargeIn,
  threshold = 0.15,
  consecutiveFrames = 3,
  cooldownMs = 1000,
}: BargeInOptions) {
  const aboveThresholdCountRef = useRef(0);
  const lastBargeInRef = useRef(0);
  // Store config in refs so checkBargeIn never needs to recreate
  const configRef = useRef({ threshold, consecutiveFrames, cooldownMs });
  configRef.current = { threshold, consecutiveFrames, cooldownMs };
  const onBargeInRef = useRef(onBargeIn);
  onBargeInRef.current = onBargeIn;
  const isSpeakingRef = useRef(isSpeaking);
  isSpeakingRef.current = isSpeaking;
  const isCapturingRef = useRef(isCapturing);
  isCapturingRef.current = isCapturing;
  const amplitudeRef = useRef(amplitude);
  amplitudeRef.current = amplitude;

  // Reset counter when TTS stops
  useEffect(() => {
    if (!isSpeaking) {
      aboveThresholdCountRef.current = 0;
    }
  }, [isSpeaking]);

  // Stable function that reads from refs — never recreated
  const checkBargeIn = useCallback(() => {
    if (!isSpeakingRef.current || !isCapturingRef.current) {
      return;
    }

    const { threshold: t, consecutiveFrames: c, cooldownMs: cd } = configRef.current;
    const now = Date.now();

    if (amplitudeRef.current > t) {
      aboveThresholdCountRef.current += 1;
      if (aboveThresholdCountRef.current >= c) {
        if (now - lastBargeInRef.current > cd) {
          lastBargeInRef.current = now;
          aboveThresholdCountRef.current = 0;
          onBargeInRef.current();
        }
      }
    } else {
      aboveThresholdCountRef.current = 0;
    }
  }, []);  // Never recreates — reads all state from refs

  return { checkBargeIn };
}
