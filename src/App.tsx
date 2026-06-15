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
import { VoiceMonitor } from "./components/VoiceMonitor";
import { BACKEND_URL } from "./config";

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
  const { amplitude: micAmplitude, frequencies: micFrequencies, isCapturing, startCapture, stopCapture, getRecordedBlob } = useMicMonitor();
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  // Model selection state
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("ollama");
  const [selectedModel, setSelectedModel] = useState("qwen3:4b");
  const [settingsOpen, setSettingsOpen] = useState(false);

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
      setMayMood("happy");
      if (ttsSupported && fullResponse && autoSendRef.current) {
        const responseToSpeak = fullResponse;
        speak(responseToSpeak);
      }

      setIsConnected(true);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Unknown error";
      let reply: string;
      if (errorMsg.includes("timeout") || errorMsg.includes("aborted")) {
        reply = "That took too long~ The model might be loading. Try again in a moment.";
      } else if (errorMsg.includes("Failed to fetch") || errorMsg.includes("NetworkError")) {
        reply = "I can't reach my backend~ Make sure the Python server is running on port 8080.";
        setIsConnected(false);
      } else {
        reply = `Something went wrong: ${errorMsg}. Check that Ollama is running~`;
      }
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
      setMayMood("neutral");
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

  // Stop TTS when user starts a new message or mic turns off
  useEffect(() => {
    if (mayState === "thinking" || (mayState === "idle" && !autoSendRef.current)) {
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

  // Cleanup recording timer on unmount
  useEffect(() => {
    return () => {
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
    };
  }, []);

  const handleVoiceToggle = useCallback(async () => {
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

  const handleSelectModel = (provider: string, model: string) => {
    setSelectedProvider(provider);
    setSelectedModel(model);
  };

  return (
    <div className="h-screen w-screen bg-surface-dark overflow-hidden flex flex-col p-2 gap-2">
      <AnimatePresence mode="wait">
        {isPanelOpen ? (
          <motion.div
            key="panel"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="relative flex h-full gap-2"
          >
            {/* Left sidebar card — Avatar + Quick Actions */}
            <div className="w-[240px] h-full card-glow rounded-xl flex flex-col overflow-hidden">
              {/* Avatar Section */}
              <div className="flex-1 flex flex-col items-center justify-center p-5 relative overflow-hidden">
                <div className="absolute inset-0 bg-mesh-gradient pointer-events-none" />
                <Avatar state={mayState} mood={mayMood} />
                <div className="mt-4 text-center relative z-10">
                  <p className="font-sans text-sm font-semibold text-accent">
                    May
                  </p>
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
              <QuickActions onAction={handleSendMessage} />
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
              />

              {/* Chat Panel */}
              <div className="flex-1 min-h-0">
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
                />
              </div>
            </div>

            {/* Minimize button */}
            <button
              onClick={() => setIsPanelOpen(false)}
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

      {/* Settings Modal */}
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onKeySaved={fetchModels}
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
