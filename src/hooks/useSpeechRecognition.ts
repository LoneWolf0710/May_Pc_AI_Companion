import { useState, useRef, useCallback, useEffect } from "react";

interface SpeechRecognitionHook {
  isListening: boolean;
  transcript: string;
  interimTranscript: string;
  startListening: () => void;
  stopListening: () => void;
  isSupported: boolean;
  useBackendSTT: boolean;
}

/**
 * Browser-based speech recognition using webkitSpeechRecognition (Chrome).
 * Falls back gracefully if not supported.
 *
 * This replaces the Python Silero VAD + faster-whisper approach because
 * Python sounddevice records silence on Windows. The browser API handles
 * mic permissions and streaming natively.
 */
export function useSpeechRecognition(
  onResult?: (text: string) => void,
  onError?: (error: string) => void,
): SpeechRecognitionHook {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const recognitionRef = useRef<any>(null);
  const restartTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isStoppedByUserRef = useRef(false);

  // Use refs for callbacks to avoid recreating the recognition instance
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  const isSupported =
    typeof window !== "undefined" &&
    ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

  // Always use backend STT — browser webkitSpeechRecognition exists in
  // Chromium-based browsers (Opera, Chrome) but doesn't work in Tauri WebView2.
  // Backend STT uses the browser's getUserMedia (confirmed working) + faster-whisper.
  const [useBackendSTT] = useState(() => true);

  // Create recognition instance ONCE on mount — never recreate
  useEffect(() => {
    if (!isSupported) return;

    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: any) => {
      let finalText = "";
      let interimText = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalText += result[0].transcript;
        } else {
          interimText += result[0].transcript;
        }
      }

      if (finalText) {
        setTranscript(finalText);
        setInterimTranscript("");
        onResultRef.current?.(finalText.trim());
      } else if (interimText) {
        setInterimTranscript(interimText);
      }
    };

    recognition.onerror = (event: any) => {
      // "no-speech" and "aborted" are expected — just restart
      if (event.error === "no-speech" || event.error === "aborted") {
        if (!isStoppedByUserRef.current) {
          restartTimeoutRef.current = setTimeout(() => {
            try {
              recognition.start();
            } catch {
              // ignore
            }
          }, 100);
        }
        return;
      }

      // "not-allowed" means mic permission denied
      if (event.error === "not-allowed") {
        onErrorRef.current?.("Microphone permission denied. Please allow mic access in your browser.");
        setIsListening(false);
        return;
      }

      onErrorRef.current?.(`Speech recognition error: ${event.error}`);
    };

    recognition.onend = () => {
      // Auto-restart if not stopped by user
      if (!isStoppedByUserRef.current) {
        restartTimeoutRef.current = setTimeout(() => {
          try {
            recognition.start();
          } catch {
            // ignore
          }
        }, 100);
      }
    };

    recognitionRef.current = recognition;

    return () => {
      if (restartTimeoutRef.current) {
        clearTimeout(restartTimeoutRef.current);
      }
      try {
        recognition.abort();
      } catch {
        // ignore
      }
    };
  }, [isSupported]); // Only depends on isSupported — runs once on mount

  const startListening = useCallback(() => {
    if (!recognitionRef.current) return;
    isStoppedByUserRef.current = false;
    setTranscript("");
    setInterimTranscript("");
    try {
      recognitionRef.current.start();
      setIsListening(true);
    } catch {
      // Already started — ignore
    }
  }, []);

  const stopListening = useCallback(() => {
    if (!recognitionRef.current) return;
    isStoppedByUserRef.current = true;
    if (restartTimeoutRef.current) {
      clearTimeout(restartTimeoutRef.current);
    }
    try {
      recognitionRef.current.stop();
    } catch {
      // ignore
    }
    setIsListening(false);
    setInterimTranscript("");
  }, []);

  return {
    isListening,
    transcript,
    interimTranscript,
    startListening,
    stopListening,
    isSupported,
    useBackendSTT,
  };
}
