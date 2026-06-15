import { useState, useRef, useCallback, useEffect } from "react";

interface MicMonitorHook {
  amplitude: number;
  frequencies: number[];
  isCapturing: boolean;
  startCapture: () => Promise<void>;
  stopCapture: () => void;
  getRecordedBlob: () => Promise<Blob | null>;
  isSupported: boolean;
  error: string | null;
}

/**
 * Real-time mic amplitude monitor + audio recorder using getUserMedia.
 * Captures audio in the browser (which works) and returns it as a Blob
 * for the backend to transcribe — bypassing the Python PortAudio issue.
 */
export function useMicMonitor(): MicMonitorHook {
  const [amplitude, setAmplitude] = useState(0);
  const [frequencies, setFrequencies] = useState<number[]>(new Array(32).fill(0));
  const [isCapturing, setIsCapturing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number>(0);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const isSupported =
    typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;

  const startCapture = useCallback(async () => {
    if (!isSupported) {
      setError("getUserMedia not supported");
      return;
    }

    try {
      setError(null);
      chunksRef.current = [];

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      streamRef.current = stream;

      // Set up audio analyser for amplitude visualization
      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);

      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 64;
      analyser.smoothingTimeConstant = 0.8;
      source.connect(analyser);
      analyserRef.current = analyser;

      // Set up MediaRecorder to capture audio for backend transcription
      // Pick a supported MIME type (Opera/Edge may not support all codecs)
      const mimeType =
        MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : MediaRecorder.isTypeSupported("audio/webm")
            ? "audio/webm"
            : "";
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      recorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      recorder.start(100); // Collect data every 100ms
      setIsCapturing(true);

      // Start amplitude polling loop
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const freqArray = new Float32Array(analyser.frequencyBinCount);

      const tick = () => {
        analyser.getByteTimeDomainData(dataArray);

        // Calculate RMS amplitude
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          const normalized = (dataArray[i] - 128) / 128;
          sum += normalized * normalized;
        }
        const rms = Math.sqrt(sum / dataArray.length);
        setAmplitude(Math.min(1, rms * 3));

        // Get frequency data for bar visualization
        analyser.getFloatFrequencyData(freqArray);
        const bars: number[] = [];
        const binCount = analyser.frequencyBinCount;
        const barCount = 16;
        const binsPerBar = Math.floor(binCount / barCount);

        for (let i = 0; i < barCount; i++) {
          let avg = 0;
          for (let j = 0; j < binsPerBar; j++) {
            const db = freqArray[i * binsPerBar + j];
            avg += Math.max(0, (db + 100) / 100);
          }
          bars.push(avg / binsPerBar);
        }
        setFrequencies(bars);

        rafRef.current = requestAnimationFrame(tick);
      };

      rafRef.current = requestAnimationFrame(tick);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Mic access failed";
      setError(msg);
      console.error("Mic capture error:", err);
    }
  }, [isSupported]);

  const getRecordedBlob = useCallback(async (): Promise<Blob | null> => {
    if (!recorderRef.current || recorderRef.current.state === "inactive") {
      return null;
    }

    return new Promise((resolve) => {
      const recorder = recorderRef.current!;
      const originalOnStop = recorder.onstop;

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        chunksRef.current = [];
        resolve(blob);
        recorder.onstop = originalOnStop;
      };

      recorder.stop();
    });
  }, []);

  const stopCapture = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = 0;
    }
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
      recorderRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close();
      audioCtxRef.current = null;
    }
    analyserRef.current = null;
    setIsCapturing(false);
    setAmplitude(0);
    setFrequencies(new Array(32).fill(0));
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop();
      }
      if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
      if (audioCtxRef.current) audioCtxRef.current.close();
    };
  }, []);

  return {
    amplitude,
    frequencies,
    isCapturing,
    startCapture,
    stopCapture,
    getRecordedBlob,
    isSupported,
    error,
  };
}
