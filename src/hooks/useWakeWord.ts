import { useState, useRef, useCallback, useEffect } from "react";
import { BACKEND_URL } from "../config";

const CHUNK_SAMPLES = 1280; // 80ms at 16kHz
const CHECK_INTERVAL_MS = 80; // Send one chunk every 80ms

interface WakeWordHook {
  isListening: boolean;
  confidence: number;
  lastDetectionTime: number;
  error: string | null;
  startListening: () => Promise<void>;
  stopListening: () => void;
}

/**
 * Continuous wake word detection using the browser's AudioContext.
 *
 * Captures raw PCM float32 audio via ScriptProcessorNode (or AudioWorkletNode),
 * converts to int16, base64-encodes, and sends chunks to the backend
 * every 80ms for openwakeword analysis.
 *
 * When the backend returns detected=true, we fire the onDetected callback
 * which triggers the normal voice flow (record 5s → transcribe → chat).
 */
export function useWakeWord(
  onDetected: () => void,
): WakeWordHook {
  const [isListening, setIsListening] = useState(false);
  const [confidence, setConfidence] = useState(0);
  const [lastDetectionTime, setLastDetectionTime] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const scriptNodeRef = useRef<ScriptProcessorNode | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onDetectedRef = useRef(onDetected);
  onDetectedRef.current = onDetected;

  // Buffer to accumulate PCM samples between checks
  const sampleBufferRef = useRef<Float32Array[]>([]);

  const startListening = useCallback(async () => {
    if (isListening) return;

    try {
      setError(null);
      sampleBufferRef.current = [];

      // Get mic stream — low latency settings for real-time processing
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,    // Keep raw audio for wake word
          noiseSuppression: false,    // Don't suppress — openwakeword handles noise
          autoGainControl: false,     // Keep raw levels
          channelCount: 1,            // Mono
          sampleRate: 16000,          // Match openwakeword's expected rate (if supported)
        },
      });

      streamRef.current = stream;

      // Create AudioContext at 16kHz if possible, otherwise use default
      const audioCtx = new AudioContext({ sampleRate: 16000 });
      audioCtxRef.current = audioCtx;

      // If the AudioContext couldn't create at 16kHz, note it
      const actualRate = audioCtx.sampleRate;
      if (actualRate !== 16000) {
        console.warn(
          `AudioContext running at ${actualRate}Hz instead of 16kHz. ` +
          `PCM chunks will need resampling.`
        );
      }

      const source = audioCtx.createMediaStreamSource(stream);

      // ScriptProcessorNode: 2048 buffer, 1 input channel, 0 output channels
      const scriptNode = audioCtx.createScriptProcessor(2048, 1, 0);
      scriptNodeRef.current = scriptNode;

      scriptNode.onaudioprocess = (event) => {
        // Get raw float32 samples from the input channel
        const inputData = event.inputBuffer.getChannelData(0);

        // Resample if needed (e.g., AudioContext at 48kHz, need 16kHz)
        if (actualRate !== 16000) {
          const ratio = 16000 / actualRate;
          const resampledLength = Math.floor(inputData.length * ratio);
          const resampled = new Float32Array(resampledLength);
          for (let i = 0; i < resampledLength; i++) {
            const srcIndex = i / ratio;
            const srcFloor = Math.floor(srcIndex);
            const srcCeil = Math.min(srcFloor + 1, inputData.length - 1);
            const frac = srcIndex - srcFloor;
            resampled[i] = inputData[srcFloor] * (1 - frac) + inputData[srcCeil] * frac;
          }
          sampleBufferRef.current.push(resampled);
        } else {
          // No resampling needed — copy the data
          sampleBufferRef.current.push(new Float32Array(inputData));
        }
      };

      // Connect: source → scriptNode (no output destination needed)
      source.connect(scriptNode);
      // ScriptProcessorNode must be connected to destination to fire onaudioprocess
      scriptNode.connect(audioCtx.destination);

      setIsListening(true);

      // Poll: send accumulated samples to backend every CHECK_INTERVAL_MS
      intervalRef.current = setInterval(async () => {
        const buffer = sampleBufferRef.current;
        if (buffer.length === 0) return;

        // Flatten all buffered chunks into one array
        const totalSamples = buffer.reduce((sum, chunk) => sum + chunk.length, 0);
        const flat = new Float32Array(totalSamples);
        let offset = 0;
        for (const chunk of buffer) {
          flat.set(chunk, offset);
          offset += chunk.length;
        }
        sampleBufferRef.current = [];

        // Take exactly CHUNK_SAMPLES from the front
        const samples = flat.slice(0, CHUNK_SAMPLES);
        if (samples.length < CHUNK_SAMPLES) return;

        // Convert float32 [-1.0, 1.0] → int16 [-32768, 32767]
        const int16 = new Int16Array(samples.length);
        for (let i = 0; i < samples.length; i++) {
          const s = Math.max(-1, Math.min(1, samples[i]));
          int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        // Base64 encode the raw PCM bytes
        const bytes = new Uint8Array(int16.buffer);
        const base64 = btoa(String.fromCharCode(...bytes));

        try {
          const res = await fetch(`${BACKEND_URL}/voice/wake-word/check`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ audio: base64 }),
            signal: AbortSignal.timeout(2000),
          });

          if (res.ok) {
            const data = await res.json();
            if (data.confidence !== undefined) {
              setConfidence(data.confidence);
            }
            if (data.detected) {
              setLastDetectionTime(Date.now());
              console.log(
                `[Wake Word] Detected! confidence=${data.confidence?.toFixed(3)}`
              );
              // Fire the callback — this triggers the voice flow
              onDetectedRef.current();
            }
          }
        } catch {
          // Network hiccups are expected — don't spam errors
        }
      }, CHECK_INTERVAL_MS);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Mic access failed";
      setError(msg);
      console.error("Wake word mic error:", err);
      // Clean up on error
      stopListening();
    }
  }, [isListening]);

  const stopListening = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (scriptNodeRef.current) {
      scriptNodeRef.current.disconnect();
      scriptNodeRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close();
      audioCtxRef.current = null;
    }
    sampleBufferRef.current = [];
    setIsListening(false);
    setConfidence(0);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopListening();
    };
  }, [stopListening]);

  return {
    isListening,
    confidence,
    lastDetectionTime,
    error,
    startListening,
    stopListening,
  };
}
