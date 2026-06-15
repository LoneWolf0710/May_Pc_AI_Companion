import { useState, useRef, useCallback } from "react";

interface SpeechSynthesisHook {
  isSpeaking: boolean;
  speak: (text: string) => void;
  stop: () => void;
  isSupported: boolean;
  voices: SpeechSynthesisVoice[];
}

/**
 * Browser-based text-to-speech using the SpeechSynthesis API.
 * Picks the best English voice available, preferring natural-sounding ones.
 */
export function useSpeechSynthesis(): SpeechSynthesisHook {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const stoppedByUserRef = useRef(false);

  const isSupported =
    typeof window !== "undefined" && "speechSynthesis" in window;

  // Load voices (they load async in some browsers)
  const loadVoices = useCallback(() => {
    if (!isSupported) return;
    const available = window.speechSynthesis.getVoices();
    if (available.length > 0) {
      setVoices(available);
    }
  }, [isSupported]);

  // Initialize voices on mount
  if (isSupported && voices.length === 0) {
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }

  // Pick the best English voice
  const getBestVoice = useCallback((): SpeechSynthesisVoice | null => {
    if (voices.length === 0) return null;

    // Preferred voices in order of quality
    const preferred = [
      "Google US English",
      "Google UK English Female",
      "Microsoft Zira",
      "Microsoft David",
      "Samantha",
      "Karen",
      "Daniel",
    ];

    for (const name of preferred) {
      const match = voices.find(
        (v) => v.name.includes(name) && v.lang.startsWith("en"),
      );
      if (match) return match;
    }

    // Fall back to any English voice
    const englishVoice = voices.find((v) => v.lang.startsWith("en"));
    return englishVoice ?? voices[0];
  }, [voices]);

  const speak = useCallback(
    (text: string) => {
      if (!isSupported || !text.trim()) return;

      // Stop any current speech
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      const voice = getBestVoice();
      if (voice) utterance.voice = voice;
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;

      utterance.onstart = () => setIsSpeaking(true);
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);

      utteranceRef.current = utterance;
      stoppedByUserRef.current = false;
      window.speechSynthesis.speak(utterance);
    },
    [isSupported, getBestVoice],
  );

  const stop = useCallback(() => {
    if (!isSupported) return;
    stoppedByUserRef.current = true;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, [isSupported]);

  return {
    isSpeaking,
    speak,
    stop,
    isSupported,
    voices,
  };
}
