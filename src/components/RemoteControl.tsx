import { useState, useEffect, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import { BACKEND_URL } from "../config";

interface RemoteControlProps {
  onClose: () => void;
}

interface RemoteMessage {
  role: "user" | "may";
  content: string;
  timestamp: number;
}

export default function RemoteControl({ onClose }: RemoteControlProps) {
  const [messages, setMessages] = useState<RemoteMessage[]>([
    {
      role: "may",
      content: "Remote control connected~ Scan the QR code from your phone, or send commands here.",
      timestamp: Date.now(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [connectionInfo, setConnectionInfo] = useState<{
    url: string;
    ip: string;
    port: number;
    qr_svg: string;
    connected_clients: number;
  } | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Fetch connection info
  useEffect(() => {
    fetch(`${BACKEND_URL}/remote/info`)
      .then((r) => r.json())
      .then(setConnectionInfo)
      .catch(() => {});
  }, []);

  // WebSocket connection
  const connectWs = useCallback(() => {
    const wsUrl = `${BACKEND_URL.replace("http", "ws").replace(":8080", ":8080")}/ws/remote`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === "response") {
          setIsProcessing(false);
          setMessages((prev) => [
            ...prev,
            { role: "may", content: data.content, timestamp: Date.now() },
          ]);
        }
      } catch {
        // ignore
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      // Auto-reconnect after 3s
      setTimeout(connectWs, 3000);
    };

    ws.onerror = () => ws.close();
    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connectWs();
    return () => {
      wsRef.current?.close();
    };
  }, [connectWs]);

  const sendMessage = useCallback(() => {
    if (!input.trim() || isProcessing) return;
    const content = input.trim();
    setInput("");
    setIsProcessing(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content, timestamp: Date.now() },
    ]);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "message", content }));
    }
  }, [input, isProcessing]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="bg-surface rounded-xl border border-border shadow-2xl flex flex-col overflow-hidden"
      style={{ height: "min(70vh, 600px)" }}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[var(--accent)] to-[var(--purple)] flex items-center justify-center text-sm">
            📱
          </div>
          <div>
            <h3 className="text-sm font-semibold text-text">Remote Control</h3>
            <p className="text-2xs text-text-muted font-mono">
              {isConnected ? (
                <span className="text-[var(--success)]">Connected</span>
              ) : (
                <span className="text-[var(--warning)]">Connecting...</span>
              )}
              {connectionInfo?.connected_clients
                ? ` · ${connectionInfo.connected_clients} client(s)`
                : ""}
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded-full bg-surface-elevated border border-border flex items-center justify-center text-text-muted hover:text-text hover:border-border-hover transition-all text-xs"
        >
          ✕
        </button>
      </div>

      {/* QR Code + Connection Info */}
      <div className="px-4 py-3 border-b border-border bg-surface-elevated/30">
        <div className="flex items-center gap-4">
          {connectionInfo?.qr_svg ? (
            <div
              className="w-20 h-20 flex-shrink-0 bg-white rounded-lg p-1"
              dangerouslySetInnerHTML={{ __html: connectionInfo.qr_svg }}
            />
          ) : (
            <div className="w-20 h-20 flex-shrink-0 bg-surface-elevated rounded-lg flex items-center justify-center text-text-muted text-xs">
              Loading QR...
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-xs text-text-muted mb-1">
              Scan to connect from your phone:
            </p>
            <p className="text-xs font-mono text-accent truncate">
              {connectionInfo?.url || "Loading..."}
            </p>
            <p className="text-2xs text-text-muted mt-1">
              IP: {connectionInfo?.ip || "—"} · Port: {connectionInfo?.port || "—"}
            </p>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] px-3 py-2 rounded-2xl text-sm ${
                msg.role === "user"
                  ? "bg-accent text-black rounded-br-sm"
                  : "bg-surface-elevated border border-border text-text rounded-bl-sm"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {isProcessing && (
          <div className="flex justify-start">
            <div className="bg-surface-elevated border border-border px-3 py-2 rounded-2xl rounded-bl-sm flex gap-1">
              <span className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-3 py-2 border-t border-border flex gap-2 items-center">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder="Type a command..."
          className="flex-1 px-3 py-2 bg-surface-elevated border border-border rounded-full text-sm text-text placeholder-text-muted outline-none focus:border-accent transition-colors"
          disabled={isProcessing}
        />
        <button
          onClick={sendMessage}
          disabled={!input.trim() || isProcessing}
          className="w-9 h-9 rounded-full bg-accent text-black flex items-center justify-center text-lg font-bold disabled:opacity-30 transition-opacity flex-shrink-0"
        >
          ↑
        </button>
      </div>
    </motion.div>
  );
}
