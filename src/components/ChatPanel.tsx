import { useRef, useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { MayState, Message } from "../App";
import { ModelSelector } from "./ModelSelector";
import { RenderedMessage } from "./CodeBlock";

interface ModelInfo {
  provider: string;
  provider_name: string;
  id: string;
  name: string;
  fast: boolean;
  available: boolean;
}

interface ChatPanelProps {
  messages: Message[];
  mayState: MayState;
  onSend: (message: string) => void;
  isListening: boolean;
  onVoiceToggle: () => void;
  models: ModelInfo[];
  selectedModel: string;
  selectedProvider: string;
  onSelectModel: (provider: string, model: string) => void;
  onOpenSettings: () => void;
  liveTranscript?: string;
  speechError?: string | null;
  sttSupported?: boolean;
  onOpenMeeting?: () => void;
  onOpenGhost?: () => void;
  onOpenRemote?: () => void;
  onOpenAutoTuner?: () => void;
  onOpenInternetLearning?: () => void;
  onOpenSkills?: () => void;
  onOpenMoodTimeline?: () => void;
  onOpenWorkflows?: () => void;
  continuousMode?: boolean;
  onToggleContinuous?: () => void;
}

export function ChatPanel({
  messages,
  mayState,
  onSend,
  isListening,
  onVoiceToggle,
  models,
  selectedModel,
  selectedProvider,
  onSelectModel,
  onOpenSettings,
  liveTranscript = "",
  speechError = null,
  sttSupported = true,
  onOpenMeeting,
  onOpenGhost,
  onOpenRemote,
  onOpenAutoTuner,
  onOpenInternetLearning,
  onOpenSkills,
  onOpenMoodTimeline,
  onOpenWorkflows,
  continuousMode = false,
  onToggleContinuous,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [typedValue, setTypedValue] = useState("");

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (isListening) {
      // Don't send from input while listening — speech handles it
      return;
    }
    if (!typedValue.trim()) return;
    onSend(typedValue.trim());
    setTypedValue("");
  };

  // Show liveTranscript when listening, typedValue when typing
  const inputValue = isListening ? liveTranscript : typedValue;

  return (
    <div className="h-full flex flex-col">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {messages.length === 0 && (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <p className="text-xs text-text-muted font-mono">No messages yet</p>
              <p className="text-2xs text-text-muted/60 mt-1 font-mono">
                Type something below to start~
              </p>
            </div>
          </div>
        )}
        <div className="space-y-3">
          {messages.map((msg, idx) => {
            // Varied max-width for organic feel (55%-75%)
            const maxW = msg.role === "user"
              ? 55 + ((idx * 7 + 3) % 20) // 55-75%
              : 60 + ((idx * 11 + 5) % 18); // 60-78%
            // Slight random rotation for handwritten feel
            const rotation = ((idx * 17 + 3) % 10) * 0.1 - 0.5; // -0.5 to 0.4

            return (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, x: msg.role === "user" ? 20 : -20, rotate: rotation }}
              animate={{ opacity: 1, x: 0, rotate: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 25 }}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`message-content px-4 py-2.5 ${
                  msg.role === "user"
                    ? "bg-surface-elevated border border-border rounded-2xl rounded-br-md"
                    : "bg-surface border border-border rounded-2xl rounded-bl-md"
                }`}
                style={{ maxWidth: `${maxW}%` }}
              >
                {msg.role === "may" && (
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent shadow-glow" />
                    <span className="text-2xs font-mono font-medium text-accent uppercase tracking-wider">
                      May
                    </span>
                    <span className="text-2xs font-mono text-text-muted">
                      {new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                )}
                <div className="text-sm leading-relaxed text-text">
                  <RenderedMessage content={msg.content} />
                  {msg.role === "may" &&
                    mayState === "thinking" &&
                    idx === messages.length - 1 && (
                      <span className="inline-flex items-center gap-1 ml-1.5">
                        <span className="w-1 h-1 bg-accent rounded-full animate-pulse" />
                        <span className="w-1 h-1 bg-accent rounded-full animate-pulse" style={{ animationDelay: "0.2s" }} />
                        <span className="w-1 h-1 bg-accent rounded-full animate-pulse" style={{ animationDelay: "0.4s" }} />
                      </span>
                    )}
                </div>
              </div>
            </motion.div>
            );
          })}
        </div>
        <div ref={messagesEndRef} />
      </div>

      {/* Bottom scan bar when thinking */}
      {mayState === "thinking" && <div className="scan-bar" />}

      {/* Input area */}
      <div className="border-t border-border px-4 py-3">
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          {/* Model selector (full variant) */}
          <ModelSelector
            models={models}
            selectedModel={selectedModel}
            selectedProvider={selectedProvider}
            onSelect={onSelectModel}
            onOpenSettings={onOpenSettings}
            variant="full"
          />
          {/* Voice toggle */}
          <button
            type="button"
            onClick={onVoiceToggle}
            disabled={!sttSupported}
            className={`flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
              !sttSupported
                ? "bg-surface-elevated border border-border opacity-40 cursor-not-allowed"
                : isListening
                  ? "bg-accent/15 border border-accent/30 shadow-glow animate-pulse"
                  : "bg-surface-elevated border border-border hover:border-accent/30"
            }`}
            title={!sttSupported ? "Voice not supported in this browser" : isListening ? "Stop listening (Ctrl+Shift+M)" : "Start voice input (Ctrl+Shift+M)"}
          >
            {isListening ? (
              <div className="voice-wave">
                <span /><span /><span /><span /><span />
              </div>
            ) : (
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className={sttSupported ? "text-text-muted" : "text-text-muted/40"}
              >
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" x2="12" y1="19" y2="22" />
              </svg>
            )}
          </button>
          {/* Speech error toast */}
          {speechError && (
            <div className="relative">
              <div className="absolute bottom-full mb-2 left-0 right-0 mx-4 px-3 py-2 bg-danger/10 border border-danger/30 rounded-lg text-xs font-mono text-danger text-center whitespace-nowrap">
                {speechError}
              </div>
            </div>
          )}

          {/* Text input */}
          <div className="flex-1 relative group">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => !isListening && setTypedValue(e.target.value)}
              placeholder={isListening ? "Listening..." : "Type a message..."}
              readOnly={isListening}
              className="w-full bg-surface-elevated border border-border rounded-xl px-4 py-2.5 text-sm placeholder-[#666666] focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20 transition-colors font-sans"
              style={{ color: '#ffffff' }}
            />
            <div className="absolute bottom-0 left-3 right-3 h-[1.5px] bg-accent/0 group-focus-within:bg-accent/40 rounded-full transition-colors pointer-events-none" />
          </div>

          {/* Meeting & Ghost mode buttons */}
          {onOpenMeeting && (
            <button
              type="button"
              onClick={onOpenMeeting}
              className="flex-shrink-0 w-9 h-9 rounded-xl bg-surface-elevated border border-border flex items-center justify-center hover:border-accent/30 transition-all group"
              title="Meeting Mode"
            >
              <span className="text-sm group-hover:scale-110 transition-transform">🎙️</span>
            </button>
          )}
          {onOpenGhost && (
            <button
              type="button"
              onClick={onOpenGhost}
              className="flex-shrink-0 w-9 h-9 rounded-xl bg-surface-elevated border border-border flex items-center justify-center hover:border-accent/30 transition-all group"
              title="Ghost Mode"
            >
              <span className="text-sm group-hover:scale-110 transition-transform">👻</span>
            </button>
          )}
          {onOpenRemote && (
            <button
              type="button"
              onClick={onOpenRemote}
              className="flex-shrink-0 w-9 h-9 rounded-xl bg-surface-elevated border border-border flex items-center justify-center hover:border-accent/30 transition-all group"
              title="Remote Control"
            >
              <span className="text-sm group-hover:scale-110 transition-transform">📱</span>
            </button>
          )}
          {onOpenAutoTuner && (
            <button
              type="button"
              onClick={onOpenAutoTuner}
              className="flex-shrink-0 w-9 h-9 rounded-xl bg-surface-elevated border border-border flex items-center justify-center hover:border-accent/30 transition-all group"
              title="Auto-Tuner"
            >
              <span className="text-sm group-hover:scale-110 transition-transform">🧬</span>
            </button>
          )}
          {onOpenInternetLearning && (
            <button
              type="button"
              onClick={onOpenInternetLearning}
              className="flex-shrink-0 w-9 h-9 rounded-xl bg-surface-elevated border border-border flex items-center justify-center hover:border-accent/30 transition-all group"
              title="Internet Learning"
            >
              <span className="text-sm group-hover:scale-110 transition-transform">🌐</span>
            </button>
          )}
          {onOpenSkills && (
            <button
              type="button"
              onClick={onOpenSkills}
              className="flex-shrink-0 w-9 h-9 rounded-xl bg-surface-elevated border border-border flex items-center justify-center hover:border-accent/30 transition-all group"
              title="Learned Skills"
            >
              <span className="text-sm group-hover:scale-110 transition-transform">🧠</span>
            </button>
          )}
          {onOpenMoodTimeline && (
            <button
              type="button"
              onClick={onOpenMoodTimeline}
              className="flex-shrink-0 w-9 h-9 rounded-xl bg-surface-elevated border border-border flex items-center justify-center hover:border-accent/30 transition-all group"
              title="Mood History"
            >
              <span className="text-sm group-hover:scale-110 transition-transform">🎭</span>
            </button>
          )}
          {/* P6: Workflows toggle */}
          {onOpenWorkflows && (
            <button
              type="button"
              onClick={onOpenWorkflows}
              className="flex-shrink-0 w-9 h-9 rounded-xl bg-surface-elevated border border-border flex items-center justify-center hover:border-accent/30 transition-all group"
              title="Automated Workflows"
            >
              <span className="text-sm group-hover:scale-110 transition-transform">⚡</span>
            </button>
          )}
          {/* P6: Continuous conversation toggle */}
          {onToggleContinuous && (
            <button
              type="button"
              onClick={onToggleContinuous}
              className={`flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
                continuousMode
                  ? "bg-accent/20 border border-accent/40 shadow-glow"
                  : "bg-surface-elevated border border-border hover:border-accent/30"
              }`}
              title={continuousMode ? "Disable continuous conversation" : "Enable continuous conversation"}
            >
              <span className={`text-sm ${continuousMode ? "scale-110" : ""}`}>🔄</span>
            </button>
          )}
          {/* Send button */}
          <button
            type="submit"
            className="flex-shrink-0 w-9 h-9 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center hover:bg-accent/20 hover:border-accent/30 transition-all shadow-glow"
          >
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="text-accent"
            >
              <path d="m22 2-7 20-4-9-9-4Z" />
              <path d="M22 2 11 13" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}
