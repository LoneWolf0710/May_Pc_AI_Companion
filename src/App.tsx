import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChatPanel } from "./components/ChatPanel";
import { Avatar } from "./components/Avatar";
import { StatusHUD } from "./components/StatusHUD";
import { FloatingOrb } from "./components/FloatingOrb";
import { QuickActions } from "./components/QuickActions";
import { SettingsModal } from "./components/SettingsModal";
import { useSpeechRecognition } from "./hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "./hooks/useSpeechSynthesis";
import { useMicMonitor } from "./hooks/useMicMonitor";
import { useWakeWord } from "./hooks/useWakeWord";
import { useBargeIn } from "./hooks/useBargeIn";
import { VoiceMonitor } from "./components/VoiceMonitor";
import { MorningBriefing } from "./components/MorningBriefing";
import MeetingMode from "./components/MeetingMode";
import GhostMode from "./components/GhostMode";
import RemoteControl from "./components/RemoteControl";
import { ProactiveSuggestions } from "./components/ProactiveSuggestions";
import AutoTunerPanel from "./components/AutoTunerPanel";
import InternetLearning from "./components/InternetLearning";
import SkillsPanel from "./components/SkillsPanel";
import MoodTimeline from "./components/MoodTimeline";
import WorkflowsPanel from "./components/WorkflowsPanel";
import { BACKEND_URL } from "./config";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { invoke } from "@tauri-apps/api/core";

export type MayState = "idle" | "listening" | "thinking" | "speaking";
export type MayMood = "neutral" | "happy" | "cool" | "concerned" | "surprised";

export interface Message {
  id: string;
  role: "user" | "may";
  content: string;
  timestamp: number;
}

interface ModelInfo {
  provider: string;
  provider_name: string;
  id: string;
  name: string;
  fast: boolean;
  available: boolean;
}

const RECORDING_DURATION = 5; // seconds

const HORMONE_COLORS: Record<string, string> = {
  cortisol: "#f87171", dopamine: "#34d399", serotonin: "#fbbf24",
  adrenaline: "#fb923c", oxytocin: "#f472b6", endorphin: "#c084fc",
};

const BRAIN_REGION_LABELS: Record<string, string> = {
  thalamus: "Thalamus", prefrontal: "Prefrontal", hippocampus: "Hippocampus",
  cerebellum: "Cerebellum", amygdala: "Amygdala", brocas: "Broca's", brainstem: "Brainstem",
};

function App() {
  const [isPanelOpen, setIsPanelOpen] = useState(true);
  const [mayState, setMayState] = useState<MayState>("idle");
  const [mayMood, setMayMood] = useState<MayMood>("neutral");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "may",
      content: "Hey~ I'm May. What's up?",
      timestamp: Date.now(),
    },
  ]);
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [isMockMode, setIsMockMode] = useState<boolean | null>(null);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [voiceMonitorOpen, setVoiceMonitorOpen] = useState(false);
  const [backendRecording, setBackendRecording] = useState(false);
  const [recordingElapsed, setRecordingElapsed] = useState(0);
  const recordingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const autoSendRef = useRef(false);
  // P6: Continuous conversation mode — auto-restart mic after May responds
  const [continuousMode, setContinuousMode] = useState(
    () => localStorage.getItem("may_continuous_mode") === "true"
  );
  const continuousModeRef = useRef(continuousMode);
  continuousModeRef.current = continuousMode;
  const { amplitude: micAmplitude, frequencies: micFrequencies, isCapturing, startCapture, stopCapture, getRecordedBlob } = useMicMonitor();
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  // Wake word detection state
  const [wakeWordEnabled, setWakeWordEnabled] = useState(false);
  const handleWakeWordDetected = useCallback(() => {
    // Wake word fired — trigger the normal voice flow
    if (mayState !== "idle") return; // Don't interrupt active conversations
    console.log("[Wake Word] Triggering voice flow");
    handleVoiceToggleRef.current();
  }, [mayState]);

  const { isListening: isWakeWordActive, startListening: startWakeWord, stopListening: stopWakeWord } = useWakeWord(handleWakeWordDetected);

  // Model selection state — persisted to localStorage so it survives reloads
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState(
    () => localStorage.getItem("may_default_provider") || "ollama"
  );
  const [selectedModel, setSelectedModel] = useState(
    () => localStorage.getItem("may_default_model") || "qwen3:4b"
  );
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [showBriefing, setShowBriefing] = useState(true);
  const [meetingModeOpen, setMeetingModeOpen] = useState(false);
  const [ghostModeOpen, setGhostModeOpen] = useState(false);
  const [remoteOpen, setRemoteOpen] = useState(false);
  const [autoTunerOpen, setAutoTunerOpen] = useState(false);
  const [internetLearningOpen, setInternetLearningOpen] = useState(false);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [moodTimelineOpen, setMoodTimelineOpen] = useState(false);
  const [workflowsOpen, setWorkflowsOpen] = useState(false);
  const [controlMode, setControlMode] = useState<string>("normal");
  const [personalityMode, setPersonalityMode] = useState<string>("shikimori");
  const [personalityProfiles, setPersonalityProfiles] = useState<Record<string, { name: string; description: string }>>({
    shikimori: { name: "Shikimori", description: "Default" },
    formal: { name: "Formal", description: "Professional" },
    debug: { name: "Debug", description: "Verbose" },
    silent: { name: "Silent", description: "Minimal" },
    playful: { name: "Playful", description: "Expressive" },
  });

  // Fetch available models (combines static + live OpenRouter models)
  const fetchModels = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/models`, { signal: AbortSignal.timeout(5000) });
      if (res.ok) {
        const data = await res.json();
        setModels(data.models);
      }
    } catch {
      // silent
    }
    try {
      const orRes = await fetch(`${BACKEND_URL}/models/openrouter`, { signal: AbortSignal.timeout(8000) });
      if (orRes.ok) {
        const orData = await orRes.json();
        if (orData.models?.length) {
          setModels((prev) => {
            const nonOr = prev.filter((m) => m.provider !== "openrouter");
            return [...nonOr, ...orData.models];
          });
        }
      }
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    fetchModels();
    const interval = setInterval(fetchModels, 30000);
    return () => clearInterval(interval);
  }, [fetchModels]);

  // Start the Python sidecar backend when running as built EXE
  useEffect(() => {
    const startBackend = async () => {
      try {
        // Skip in dev mode — backend is started manually via `python main.py`
        const result = await invoke<string>("start_backend");
        console.log("[May]", result);
      } catch (err) {
        console.error("[May] Failed to start backend sidecar:", err);
        setIsConnected(false);
      }
    };
    startBackend();
  }, []);

  const checkBackend = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(3000) });
      if (res.ok) {
        try {
          const data = await res.json();
          setIsMockMode(data.mock_mode ?? false);
        } catch {
          setIsMockMode(false);
        }
        setIsConnected(true);
      } else {
        setIsConnected(false);
      }
    } catch {
      setIsConnected(false);
    }
  }, []);

  useEffect(() => {
    checkBackend();
    const interval = setInterval(checkBackend, 10000);
    return () => clearInterval(interval);
  }, [checkBackend]);

  const handleSendMessage = async (content: string) => {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setMayState("thinking");
    setMayMood("cool");

    try {
      const response = await fetch(`${BACKEND_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          history: messagesRef.current.slice(-10),
          provider: selectedProvider,
          model: selectedModel,
        }),
        signal: AbortSignal.timeout(120000),
      });

      if (!response.ok) throw new Error(`Backend responded ${response.status}`);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullResponse = "";
      const mayMsgId = crypto.randomUUID();

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          fullResponse += chunk;
          setMessages((prev) => {
            const existing = prev.find((m) => m.id === mayMsgId);
            if (existing) {
              return prev.map((m) =>
                m.id === mayMsgId ? { ...m, content: fullResponse } : m,
              );
            }
            return [
              ...prev,
              {
                id: mayMsgId,
                role: "may" as const,
                content: fullResponse,
                timestamp: Date.now(),
              },
            ];
          });
        }
      }

      // Streaming complete — speak the full response via TTS
      setMayState("speaking");
      // Use happy mood for successful responses, surprised for tool results
      const hasToolCalls = fullResponse.includes("🔧");
      setMayMood(hasToolCalls ? "surprised" : "happy");
      if (ttsSupported && fullResponse && autoSendRef.current) {
        const responseToSpeak = fullResponse;
        speak(responseToSpeak);
      }

      setIsConnected(true);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Unknown error";
      let reply: string;
      let errorMood: MayMood = "concerned";
      if (errorMsg.includes("timeout") || errorMsg.includes("aborted")) {
        reply = "That took too long~ The model might be loading. Try again in a moment.";
        errorMood = "concerned";
      } else if (errorMsg.includes("Failed to fetch") || errorMsg.includes("NetworkError")) {
        reply = "I can't reach my backend~ Make sure the Python server is running on port 8080.";
        setIsConnected(false);
        errorMood = "concerned";
      } else {
        reply = `Something went wrong: ${errorMsg}. Check that Ollama is running~`;
        errorMood = "surprised";
      }
      setMayMood(errorMood);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "may",
          content: reply,
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setMayState("idle");
      // On success: mood stays happy/surprised (set in try block)
      // On error: mood stays concerned/surprised (set in catch block)
      // Next user message resets mood to "cool" (thinking)
    }
  };

  // TTS — speak May's responses aloud
  const { speak, stop: stopSpeaking, isSupported: ttsSupported } = useSpeechSynthesis();

  // STT — browser speech recognition
  const handleSendMessageRef = useRef(handleSendMessage);
  handleSendMessageRef.current = handleSendMessage;

  const handleSpeechResult = useCallback((text: string) => {
    if (text && autoSendRef.current) {
      setLiveTranscript("");
      handleSendMessageRef.current(text);
      // Don't set autoSendRef to false here — keep it true so auto-restart works
    } else if (text) {
      setLiveTranscript(text);
    }
  }, []);

  const handleSpeechError = useCallback((error: string) => {
    setSpeechError(error);
    setTimeout(() => setSpeechError(null), 5000);
  }, []);

  const {
    isListening,
    interimTranscript,
    startListening,
    stopListening,
    isSupported: sttSupported,
    useBackendSTT,
  } = useSpeechRecognition(handleSpeechResult, handleSpeechError);

  // Sync listening state to May's state (only for browser STT)
  useEffect(() => {
    if (!useBackendSTT && isListening) {
      setMayState("listening");
      setMayMood("cool");
    } else if (!useBackendSTT && mayState === "listening") {
      setMayState("idle");
      setMayMood("neutral");
    }
  }, [isListening, useBackendSTT]);

  // Barge-in handler: stop TTS when user starts a new message, mic turns on, or any state transition away from speaking
  useEffect(() => {
    if (mayState === "thinking" || mayState === "listening" || (mayState === "idle" && !autoSendRef.current)) {
      stopSpeaking();
    }
  }, [mayState, stopSpeaking]);

  // Auto-restart listening after May finishes responding (browser STT only)
  useEffect(() => {
    if (mayState === "idle" && autoSendRef.current && !useBackendSTT) {
      const timeout = setTimeout(() => {
        if (autoSendRef.current) {
          startListening();
        }
      }, 800);
      return () => clearTimeout(timeout);
    }
  }, [mayState, startListening, useBackendSTT]);

  // P6: Auto-restart backend STT recording in continuous mode
  useEffect(() => {
    if (mayState === "idle" && continuousModeRef.current && useBackendSTT && !backendRecording) {
      // Wait for TTS to finish (if speaking), then restart recording
      const timeout = setTimeout(() => {
        if (continuousModeRef.current && mayState === "idle") {
          handleVoiceToggleRef.current();
        }
      }, 1200); // 1.2s delay for TTS to finish + brief pause
      return () => clearTimeout(timeout);
    }
  }, [mayState, useBackendSTT, backendRecording]);

  // Cleanup recording timer on unmount
  useEffect(() => {
    return () => {
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
    };
  }, []);

  // Fetch wake word status and sync with backend
  useEffect(() => {
    const fetchWakeWordStatus = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/voice/wake-word`);
        if (res.ok) {
          const data = await res.json();
          setWakeWordEnabled(data.enabled ?? false);
        }
      } catch {
        // silent
      }
    };
    fetchWakeWordStatus();
    const interval = setInterval(fetchWakeWordStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  // Start/stop wake word listening based on enabled state and app state
  useEffect(() => {
    if (wakeWordEnabled && mayState === "idle" && !isWakeWordActive) {
      startWakeWord().catch(() => {});
    } else if (!wakeWordEnabled && isWakeWordActive) {
      stopWakeWord();
    } else if (mayState !== "idle" && isWakeWordActive) {
      // Pause wake word during active conversation
      stopWakeWord();
    }
  }, [wakeWordEnabled, mayState, isWakeWordActive, startWakeWord, stopWakeWord]);

  const handleVoiceToggleInner = useCallback(async () => {
    if (isListening) {
      autoSendRef.current = false;
      stopListening();
      stopCapture();
      setLiveTranscript("");
      return;
    }

    // If browser STT isn't available, use backend STT (record + transcribe)
    if (useBackendSTT) {
      autoSendRef.current = false;
      setMayState("listening");
      setMayMood("cool");
      setLiveTranscript("");
      setVoiceMonitorOpen(true);
      setBackendRecording(true);
      setRecordingElapsed(0);

      // Start mic capture for amplitude visualization
      try {
        await startCapture();
      } catch {
        // Mic visualization is nice-to-have, don't block
      }

      // Start countdown timer
      recordingTimerRef.current = setInterval(() => {
        setRecordingElapsed((prev) => {
          const next = prev + 0.1;
          if (next >= RECORDING_DURATION) {
            if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
          }
          return next;
        });
      }, 100);

      // Wait for recording duration then get the browser-captured audio
      await new Promise((resolve) => setTimeout(resolve, RECORDING_DURATION * 1000));
      setRecordingElapsed(RECORDING_DURATION);

      const audioBlob = await getRecordedBlob();
      if (!audioBlob || audioBlob.size < 100) {
        throw new Error("No audio captured from microphone");
      }

      setLiveTranscript("Transcribing...");

      try {
        const res = await fetch(`${BACKEND_URL}/voice/transcribe-audio`, {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: audioBlob,
          signal: AbortSignal.timeout(60000),
        });

        if (!res.ok) throw new Error(`Backend responded ${res.status}`);
        const data = await res.json();

        if (data.error) {
          throw new Error(data.error);
        }

        if (data.text && data.text.trim()) {
          setLiveTranscript(data.text.trim());
          setMayState("idle");
          setMayMood("neutral");
          handleSendMessageRef.current(data.text.trim());
        } else {
          setLiveTranscript("");
          setMayState("idle");
          setMayMood("neutral");
          setSpeechError("No speech detected. Try speaking louder.");
          setTimeout(() => setSpeechError(null), 8000);
        }
      } catch (err) {
        setLiveTranscript("");
        setMayState("idle");
        setMayMood("neutral");
        const msg = err instanceof Error ? err.message : "Unknown error";
        setSpeechError(`Backend STT failed: ${msg}`);
      } finally {
        setBackendRecording(false);
        if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
        stopCapture();
      }
      return;
    }

    // Browser STT path
    autoSendRef.current = true;
    setLiveTranscript("");
    setSpeechError(null);
    setVoiceMonitorOpen(true);
    try {
      await startCapture();
    } catch {
      // Ignore mic visualization errors
    }
    startListening();
  }, [isListening, startListening, stopListening, useBackendSTT, startCapture, stopCapture]);

  // Stop mic capture when listening stops (browser STT only)
  // Must NOT run during backend STT — the 5-second recording is managed by handleVoiceToggle
  useEffect(() => {
    if (!isListening && isCapturing && !useBackendSTT) {
      stopCapture();
    }
  }, [isListening, isCapturing, stopCapture, useBackendSTT]);

  // Barge-in audio detection: stop TTS automatically when user speaks during playback
  // Start a lightweight mic capture during TTS so we can detect user speech
  const [bargeInMicActive, setBargeInMicActive] = useState(false);

  const handleBargeIn = useCallback(() => {
    if (mayState === "speaking") {
      stopSpeaking();
    }
  }, [mayState, stopSpeaking]);

  const { checkBargeIn } = useBargeIn({
    isSpeaking: mayState === "speaking",
    amplitude: micAmplitude,
    isCapturing: bargeInMicActive,
    onBargeIn: handleBargeIn,
    threshold: 0.15,
    consecutiveFrames: 3,
    cooldownMs: 1000,
  });

  // Start/stop lightweight mic capture for barge-in during TTS
  useEffect(() => {
    if (mayState === "speaking" && !bargeInMicActive && !isCapturing) {
      // Start a quiet mic capture for barge-in detection
      setBargeInMicActive(true);
      startCapture().catch(() => {});
    } else if (mayState !== "speaking" && bargeInMicActive && !isListening) {
      // Stop barge-in mic if we started it and user isn't in voice mode
      setBargeInMicActive(false);
      stopCapture();
    } else if (mayState !== "speaking" && bargeInMicActive) {
      // Always clean up barge-in state when TTS ends, even if voice is active
      setBargeInMicActive(false);
    }
  }, [mayState, bargeInMicActive, isCapturing, isListening, startCapture, stopCapture]);

  // Check barge-in on each amplitude update during speaking
  useEffect(() => {
    if (mayState === "speaking" && bargeInMicActive) {
      checkBargeIn();
    }
  }, [micAmplitude, mayState, bargeInMicActive, checkBargeIn]);

  // P6: Toggle continuous conversation mode
  const handleContinuousToggle = useCallback(() => {
    setContinuousMode((prev) => {
      const next = !prev;
      localStorage.setItem("may_continuous_mode", String(next));
      return next;
    });
  }, []);

  // Barge-in wrapper: stops TTS before starting voice input
  const handleVoiceToggle = useCallback(async () => {
    if (mayState === "speaking") {
      stopSpeaking();
    }
    // If manually toggling mic off in continuous mode, disable continuous
    if (isListening && continuousModeRef.current) {
      continuousModeRef.current = false;
      setContinuousMode(false);
      localStorage.setItem("may_continuous_mode", "false");
    }
    return handleVoiceToggleInner();
  }, [mayState, stopSpeaking, handleVoiceToggleInner, isListening]);

  // Keyboard shortcut: Ctrl+Shift+M to toggle voice
  const handleVoiceToggleRef = useRef(handleVoiceToggle);
  handleVoiceToggleRef.current = handleVoiceToggle;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === "M") {
        e.preventDefault();
        handleVoiceToggleRef.current();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Fetch control mode status on mount and periodically
  useEffect(() => {
    const fetchControlMode = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/modes`, { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
          const data = await res.json();
          setControlMode(data.active_mode || "normal");
        }
      } catch { /* silent */ }
    };
    fetchControlMode();
    const interval = setInterval(fetchControlMode, 15000);
    return () => clearInterval(interval);
  }, []);

  // Personality mode: fetch on mount + periodically
  useEffect(() => {
    const fetchPersonality = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/personality`, { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
          const data = await res.json();
          setPersonalityMode(data.active_profile || "shikimori");
          if (data.available_profiles) setPersonalityProfiles(data.available_profiles);
        }
      } catch { /* silent */ }
    };
    fetchPersonality();
    const interval = setInterval(fetchPersonality, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleSetPersonality = useCallback(async (mode: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/personality/set`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: mode }),
        signal: AbortSignal.timeout(3000),
      });
      if (res.ok) {
        const data = await res.json();
        setPersonalityMode(data.active_profile || mode);
      }
    } catch { /* silent */ }
  }, []);

  const handleSetControlMode = useCallback(async (mode: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/modes/set`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, reason: "user_toggle" }),
        signal: AbortSignal.timeout(3000),
      });
      if (res.ok) {
        const data = await res.json();
        setControlMode(data.active_mode || mode);
      }
    } catch { /* silent */ }
  }, []);

  const handleSelectModel = (provider: string, model: string) => {
    setSelectedProvider(provider);
    setSelectedModel(model);
    // Persist to localStorage so it's remembered across reloads
    localStorage.setItem("may_default_provider", provider);
    localStorage.setItem("may_default_model", model);
  };

  const [showInfoPanel, setShowInfoPanel] = useState(true);

  // Endocrine state (fetched from backend)
  const [endocrine, setEndocrine] = useState<Record<string, number>>({
    cortisol: 0.25, dopamine: 0.65, serotonin: 0.70,
    adrenaline: 0.15, oxytocin: 0.45, endorphin: 0.35,
  });
  const [brainRegions, setBrainRegions] = useState<Record<string, string>>({
    thalamus: "IDLE", prefrontal: "IDLE", hippocampus: "READY",
    cerebellum: "269+", amygdala: "CALM", brocas: "IDLE", brainstem: "ONLINE",
  });
  const [sleepState, setSleepState] = useState("WAKE");
  const [idleTime, setIdleTime] = useState(0);
  const [screenContext, setScreenContext] = useState("No active window");



  // Poll endocrine + brain + sleep + screen context every 5s
  useEffect(() => {
    const fetchAll = async () => {
      await Promise.allSettled([
        (async () => {
          const res = await fetch(`${BACKEND_URL}/endocrine/status`, { signal: AbortSignal.timeout(3000) });
          if (res.ok) { const data = await res.json(); if (data.hormones) setEndocrine(data.hormones); }
        })(),
        (async () => {
          const res = await fetch(`${BACKEND_URL}/brain/status`, { signal: AbortSignal.timeout(3000) });
          if (res.ok) { const data = await res.json(); if (data.regions) setBrainRegions(data.regions); }
        })(),
        (async () => {
          const res = await fetch(`${BACKEND_URL}/sleep/status`, { signal: AbortSignal.timeout(3000) });
          if (res.ok) { const data = await res.json(); setSleepState(data.state || "WAKE"); setIdleTime(data.idle_seconds || 0); }
        })(),
        (async () => {
          try {
            const res = await fetch(`${BACKEND_URL}/screen/context`, { signal: AbortSignal.timeout(2000) });
            if (res.ok) { const data = await res.json(); setScreenContext(data.active_app || data.description || "No active window"); }
          } catch { /* screen context is best-effort */ }
        })(),
      ]);
    };
    fetchAll();
    const interval = setInterval(fetchAll, 5000);
    return () => clearInterval(interval);
  }, []);

  // Track idle time locally as fallback
  useEffect(() => {
    if (mayState === "idle") {
      const timer = setInterval(() => setIdleTime((p) => p + 1), 1000);
      return () => clearInterval(timer);
    } else {
      setIdleTime(0);
    }
  }, [mayState]);

  // Update active brain region based on mayState
  useEffect(() => {
    setBrainRegions((prev) => {
      const next = { ...prev };
      // Reset all to IDLE/READY/ONLINE
      next.thalamus = mayState === "thinking" || mayState === "listening" ? "ACTIVE" : "IDLE";
      next.prefrontal = mayState === "thinking" ? "ACTIVE" : "IDLE";
      next.hippocampus = mayState === "thinking" ? "SEARCH" : "READY";
      next.cerebellum = mayState === "thinking" ? "EXEC" : "269+";
      next.amygdala = mayState === "speaking" ? "ACTIVE" : "CALM";
      next.brocas = mayState === "speaking" ? "ACTIVE" : "IDLE";
      next.brainstem = "ONLINE";
      return next;
    });
  }, [mayState]);



  const formatIdleTime = (s: number) => {
    if (s < 60) return `${s}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m`;
    return `${Math.floor(s / 3600)}h`;
  };

  return (
    <div className="h-screen w-screen bg-surface-dark overflow-hidden flex flex-col p-2 gap-2">
      {/* Mesh gradient background */}
      <div className="mesh-bg" />
      {/* Grain texture overlay */}
      <div className="grain-overlay" />

      <AnimatePresence mode="wait">
        {isPanelOpen ? (
          <motion.div
            key="panel"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }} className="relative flex h-full gap-2 z-10"
          >
            {/* Left sidebar card — Avatar + Quick Actions */}
            <div className="w-[240px] h-full card-glow rounded-xl flex flex-col overflow-hidden">
              {/* Avatar Section — asymmetric placement, top-heavy */}
              <div className="flex-[2] flex flex-col items-center justify-start pt-8 pb-4 relative overflow-hidden">
                <div className="absolute inset-0 bg-mesh-gradient pointer-events-none" />
                <Avatar state={mayState} mood={mayMood} amplitude={micAmplitude} />
                <div className="mt-4 text-center relative z-10">
                  <p className="font-sans text-sm font-semibold text-accent">May</p>
                  <p className="text-2xs text-text-muted mt-0.5 font-mono uppercase tracking-[0.15em]">
                    {mayState === "thinking"
                      ? "Processing..."
                      : mayState === "listening"
                        ? "Listening..."
                        : mayState === "speaking"
                          ? "Speaking..."
                          : "Ready"}
                  </p>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="flex-1">
                <QuickActions onAction={handleSendMessage} />
              </div>
            </div>

            {/* Main area — card panel */}
            <div className="flex-1 h-full card-glow rounded-xl flex flex-col overflow-hidden">
              {/* Top bar */}
              <StatusHUD
                mayState={mayState}
                isConnected={isConnected}
                isMockMode={isMockMode}
                models={models}
                selectedModel={selectedModel}
                selectedProvider={selectedProvider}
                onSelectModel={handleSelectModel}
                onOpenSettings={() => setSettingsOpen(true)}
                controlMode={controlMode}
                onSetControlMode={handleSetControlMode}
                personalityMode={personalityMode}
                personalityProfiles={personalityProfiles}
                onSetPersonality={handleSetPersonality}
              />

              {/* Chat Panel */}
              <div className="flex-1 min-h-0 flex flex-col">
                {showBriefing && messages.length <= 1 && (
                  <MorningBriefing
                    onDismiss={() => setShowBriefing(false)}
                    onSendMessage={handleSendMessage}
                  />
                )}
                <ChatPanel
                  messages={messages}
                  mayState={mayState}
                  onSend={handleSendMessage}
                  isListening={isListening || (useBackendSTT && mayState === "listening")}
                  onVoiceToggle={handleVoiceToggle}
                  models={models}
                  selectedModel={selectedModel}
                  selectedProvider={selectedProvider}
                  onSelectModel={handleSelectModel}
                  onOpenSettings={() => setSettingsOpen(true)}
                  liveTranscript={liveTranscript || interimTranscript}
                  speechError={speechError}
                  sttSupported={sttSupported || useBackendSTT}
                  onOpenMeeting={() => setMeetingModeOpen(true)}
                  onOpenGhost={() => setGhostModeOpen(true)}
                  onOpenRemote={() => setRemoteOpen(true)}
                  onOpenAutoTuner={() => setAutoTunerOpen(true)}
                  onOpenInternetLearning={() => setInternetLearningOpen(true)}
                  onOpenSkills={() => setSkillsOpen(true)}
                  onOpenMoodTimeline={() => setMoodTimelineOpen(true)}
                  onOpenWorkflows={() => setWorkflowsOpen(true)}
                  continuousMode={continuousMode}
                  onToggleContinuous={handleContinuousToggle}
                />
              </div>
            </div>

            {/* Right info panel — living data visualizations */}
            {showInfoPanel && (
            <div className="w-[280px] h-full card-glow rounded-xl flex flex-col overflow-y-auto overflow-x-hidden gap-2 p-2 relative">
              {/* Endocrine System */}
              <div className="glass rounded-xl p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-2xs font-mono font-medium text-text-secondary uppercase tracking-[0.1em]">Endocrine</span>
                  <span className="text-2xs font-mono px-1.5 py-0.5 rounded bg-emerald/10 text-emerald">LIVE</span>
                </div>
                {Object.entries(endocrine).map(([name, value]) => (
                  <div key={name} className="hormone-row">
                    <span className="hormone-label">{name}</span>
                    <div className="hormone-wave">
                      <svg viewBox="0 0 200 40" className="w-full h-full">
                        <polyline
                          points={Array.from({ length: 40 }, (_, i) => {
                            const x = (i / 39) * 200;
                            const y = 20 + Math.sin(i * 0.3) * (value as number) * 15;
                            return `${x},${y}`;
                          }).join(" ")}
                          className="hormone-wave-svg"
                          fill="none"
                          stroke={HORMONE_COLORS[name] || "#818cf8"}
                          strokeWidth="1.5"
                          strokeLinecap="round"
                        />
                      </svg>
                    </div>
                    <span className="hormone-value">{(value as number).toFixed(2)}</span>
                  </div>
                ))}
              </div>

              {/* Brain Regions */}
              <div className="glass rounded-xl p-3">
                <span className="text-2xs font-mono font-medium text-text-secondary uppercase tracking-[0.1em] block mb-2">Brain</span>
                {Object.entries(brainRegions).map(([id, status]) => {
                  const isActive = status === "ACTIVE" || status === "SEARCH" || status === "EXEC";
                  return (
                    <div key={id} className="flex items-center justify-between py-1">
                      <span className="text-2xs font-mono text-text-secondary">{BRAIN_REGION_LABELS[id] || id}</span>
                      <span className={`text-2xs font-mono px-1.5 py-0.5 rounded ${
                        isActive
                          ? "bg-accent/10 text-accent"
                          : status === "ONLINE" || status === "READY" || status === "269+" || status === "CALM"
                            ? "bg-emerald/10 text-emerald"
                            : "text-text-muted"
                      }`}>{status}</span>
                    </div>
                  );
                })}
              </div>

              {/* Sleep Cycle */}
              <div className="glass rounded-xl p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-2xs font-mono font-medium text-text-secondary uppercase tracking-[0.1em]">Sleep</span>
                  <span className={`text-2xs font-mono px-1.5 py-0.5 rounded ${
                    sleepState === "WAKE" ? "bg-emerald/10 text-emerald"
                    : sleepState === "DROWSY" ? "bg-amber/10 text-amber"
                    : "bg-accent/10 text-accent"
                  }`}>{sleepState}</span>
                </div>
                <p className="text-2xs font-mono text-text-muted">Idle: {formatIdleTime(idleTime)}</p>
              </div>

              {/* Screen Context */}
              <div className="glass rounded-xl p-3">
                <span className="text-2xs font-mono font-medium text-text-secondary uppercase tracking-[0.1em] block mb-1">Screen</span>
                <p className="text-2xs font-mono text-text-secondary">{screenContext}</p>
              </div>

              {/* Collapse toggle */}
              <button
                onClick={() => setShowInfoPanel(false)}
                className="mx-auto mt-1 w-8 h-6 rounded-md flex items-center justify-center text-text-muted hover:text-text hover:bg-surface-elevated transition-all"
                title="Hide info panel"
              >
                <svg width="10" height="10" viewBox="0 0 10 10">
                  <path d="M3 2l4 3-4 3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>
            )}

            {/* Show info panel toggle (when hidden) */}
            {!showInfoPanel && (
              <button
                onClick={() => setShowInfoPanel(true)}
                className="w-8 h-full card-glow rounded-xl flex items-center justify-center text-text-muted hover:text-text hover:border-accent/30 transition-all border border-border"
                title="Show info panel"
              >
                <svg width="12" height="12" viewBox="0 0 10 10" className="rotate-180">
                  <path d="M3 2l4 3-4 3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            )}

            {/* Minimize to tray button */}
            <button
              onClick={async () => {
                try {
                  await getCurrentWindow().hide();
                } catch {
                  setIsPanelOpen(false);
                }
              }}
              className="absolute -top-1 -right-1 w-7 h-7 bg-surface border border-border rounded-full flex items-center justify-center text-text-muted hover:text-text hover:border-border-hover transition-all text-xs shadow-panel z-20"
              title="Minimize to tray"
            >
              _
            </button>
          </motion.div>
        ) : (
          <motion.div
            key="orb"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            className="h-full flex items-center justify-center"
          >
            <FloatingOrb
              state={mayState}
              onClick={() => setIsPanelOpen(true)}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Meeting Mode Panel */}
      <AnimatePresence>
        {meetingModeOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
            onClick={() => setMeetingModeOpen(false)}
          >
            <div onClick={(e) => e.stopPropagation()} className="w-[420px] max-h-[80vh]">
              <MeetingMode onClose={() => setMeetingModeOpen(false)} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Remote Control Panel */}
      <AnimatePresence>
        {remoteOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
            onClick={() => setRemoteOpen(false)}
          >
            <div onClick={(e) => e.stopPropagation()} className="w-[420px] max-h-[80vh]">
              <RemoteControl onClose={() => setRemoteOpen(false)} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Auto-Tuner Panel */}
      <AnimatePresence>
        {autoTunerOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
            onClick={() => setAutoTunerOpen(false)}
          >
            <div onClick={(e) => e.stopPropagation()} className="w-[420px] max-h-[80vh]">
              <AutoTunerPanel onClose={() => setAutoTunerOpen(false)} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Internet Learning Panel */}
      <AnimatePresence>
        {internetLearningOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
            onClick={() => setInternetLearningOpen(false)}
          >
            <div onClick={(e) => e.stopPropagation()} className="w-[420px] max-h-[80vh]">
              <InternetLearning onClose={() => setInternetLearningOpen(false)} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Ghost Mode Panel */}
      <AnimatePresence>
        {ghostModeOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
            onClick={() => setGhostModeOpen(false)}
          >
            <div onClick={(e) => e.stopPropagation()} className="w-[420px] max-h-[80vh]">
              <GhostMode onClose={() => setGhostModeOpen(false)} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Skills Panel */}
      <AnimatePresence>
        {skillsOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
            onClick={() => setSkillsOpen(false)}
          >
            <div onClick={(e) => e.stopPropagation()} className="w-[420px] max-h-[80vh]">
              <SkillsPanel onClose={() => setSkillsOpen(false)} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Mood Timeline Panel */}
      <AnimatePresence>
        {moodTimelineOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
            onClick={() => setMoodTimelineOpen(false)}
          >
            <div onClick={(e) => e.stopPropagation()} className="w-[420px] max-h-[80vh]">
              <MoodTimeline onClose={() => setMoodTimelineOpen(false)} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Workflows Panel */}
      <AnimatePresence>
        {workflowsOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
            onClick={() => setWorkflowsOpen(false)}
          >
            <div onClick={(e) => e.stopPropagation()} className="w-[420px] max-h-[80vh]">
              <WorkflowsPanel onClose={() => setWorkflowsOpen(false)} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onKeySaved={fetchModels}
      />

      {/* Proactive Suggestions — floating bottom-right notifications */}
      <ProactiveSuggestions
        onSuggestionClick={handleSendMessage}
        controlMode={controlMode}
      />

      {/* Voice Monitor — floating side panel */}
      <VoiceMonitor
        isVisible={voiceMonitorOpen}
        mayState={mayState}
        amplitude={micAmplitude}
        frequencies={micFrequencies}
        liveTranscript={liveTranscript}
        recordingDuration={recordingElapsed}
        maxDuration={RECORDING_DURATION}
        isBackendRecording={backendRecording}
        onClose={() => {
          setVoiceMonitorOpen(false);
          stopCapture();
        }}
      />
    </div>
  );
}

export default App;
