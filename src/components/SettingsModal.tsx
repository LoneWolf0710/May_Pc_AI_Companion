import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { BACKEND_URL } from "../config";

interface ProviderInfo {
  id: string;
  name: string;
  requires_key: boolean;
  has_key: boolean;
  models: { id: string; name: string; fast: boolean }[];
}

interface SttModelInfo {
  device: string;
  model: string;
  gpu_models: string[];
  cpu_models: string[];
  auto: boolean;
}

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onKeySaved: () => void;
}

export function SettingsModal({ isOpen, onClose, onKeySaved }: SettingsModalProps) {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [sttModel, setSttModel] = useState<SttModelInfo | null>(null);
  const [sttLoading, setSttLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchProviders();
      fetchSttModel();
    }
  }, [isOpen]);

  const fetchSttModel = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/voice/model`);
      if (res.ok) {
        const data = await res.json();
        setSttModel(data);
      }
    } catch {
      // silent
    }
  };

  const handleSetSttModel = async (model: string | null) => {
    setSttLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/voice/model`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model }),
      });
      if (res.ok) {
        const data = await res.json();
        setSttModel(data);
      }
    } catch {
      // silent
    } finally {
      setSttLoading(false);
    }
  };

  const fetchProviders = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/providers`);
      if (res.ok) {
        const data = await res.json();
        setProviders(data.providers);
      }
    } catch {
      // silent
    }
  };

  const handleSaveKey = async (providerId: string) => {
    const key = keys[providerId];
    if (!key?.trim()) return;
    setSaving(providerId);
    try {
      const res = await fetch(`${BACKEND_URL}/api-keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: providerId, key: key.trim() }),
      });
      if (res.ok) {
        setKeys((prev) => ({ ...prev, [providerId]: "" }));
        await fetchProviders();
        onKeySaved();
      }
    } catch {
      // silent
    } finally {
      setSaving(null);
    }
  };

  const handleDeleteKey = async (providerId: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api-keys/${providerId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        await fetchProviders();
        onKeySaved();
      }
    } catch {
      // silent
    }
  };

  const providerIcon = (provider: string) => {
    switch (provider) {
      case "ollama": return "🖥️";
      case "openai": return "🟢";
      case "anthropic": return "🟠";
      case "gemini": return "🔵";
      case "openrouter": return "🌐";
      case "ollama_cloud": return "☁️";
      default: return "🤖";
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="fixed inset-0 flex items-center justify-center z-50 p-4"
          >
            <div className="w-full max-w-lg bg-surface border border-border rounded-xl shadow-elevated overflow-hidden">
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                <div className="flex items-center gap-2.5">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-accent"
                  >
                    <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                  <span className="text-sm font-medium text-text">Settings</span>
                </div>
                <button
                  onClick={onClose}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-text-muted hover:text-text hover:bg-surface-elevated transition-all"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 6 6 18" />
                    <path d="m6 6 12 12" />
                  </svg>
                </button>
              </div>

              {/* Content */}
              <div className="px-5 py-4 max-h-[400px] overflow-y-auto">
                {/* STT Model Section */}
                <div className="mb-4 bg-surface-elevated border border-border rounded-xl p-3.5">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">🎙️</span>
                    <span className="text-xs font-medium text-text">Speech Recognition</span>
                    <span className="ml-auto text-2xs font-mono text-accent bg-accent/10 px-1.5 py-0.5 rounded">
                      {sttModel?.device === "cuda" ? "⚡ GPU" : "🖥️ CPU"}
                    </span>
                  </div>
                  <p className="text-2xs text-text-muted mb-2.5">
                    Current: <span className="text-text font-medium">{sttModel?.model || "loading..."}</span>
                    {sttModel?.auto && <span className="text-accent/60 ml-1">(auto)</span>}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      onClick={() => handleSetSttModel(null)}
                      disabled={sttLoading}
                      className={`text-2xs font-mono px-2 py-1 rounded-lg border transition-all ${
                        sttModel?.auto
                          ? "bg-accent/20 border-accent/30 text-accent"
                          : "bg-surface border-border text-text-muted hover:border-accent/30 hover:text-text"
                      } disabled:opacity-40`}
                    >
                      auto
                    </button>
                    {sttModel?.gpu_models.map((m) => (
                      <button
                        key={m}
                        onClick={() => handleSetSttModel(m)}
                        disabled={sttLoading}
                        className={`text-2xs font-mono px-2 py-1 rounded-lg border transition-all ${
                          sttModel?.model === m && !sttModel?.auto
                            ? "bg-accent/20 border-accent/30 text-accent"
                            : "bg-surface border-border text-text-muted hover:border-accent/30 hover:text-text"
                        } disabled:opacity-40`}
                      >
                        {m} ⚡
                      </button>
                    ))}
                    {sttModel?.cpu_models.map((m) => (
                      <button
                        key={m}
                        onClick={() => handleSetSttModel(m)}
                        disabled={sttLoading}
                        className={`text-2xs font-mono px-2 py-1 rounded-lg border transition-all ${
                          sttModel?.model === m && !sttModel?.auto
                            ? "bg-accent/20 border-accent/30 text-accent"
                            : "bg-surface border-border text-text-muted hover:border-accent/30 hover:text-text"
                        } disabled:opacity-40`}
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                  {sttLoading && <p className="text-2xs text-text-muted mt-2 italic">Loading model...</p>}
                </div>

                {/* Provider API Keys Section */}
                <div className="space-y-3">
                  {providers.map((provider) => (
                      <div
                        key={provider.id}
                        className="bg-surface-elevated border border-border rounded-xl p-3.5"
                      >
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-sm">{providerIcon(provider.id)}</span>
                          <span className="text-xs font-medium text-text">{provider.name}</span>
                          {provider.requires_key ? (
                            provider.has_key ? (
                              <span className="ml-auto text-2xs font-mono text-success bg-success/10 px-1.5 py-0.5 rounded">
                                ✓ configured
                              </span>
                            ) : (
                              <span className="ml-auto text-2xs font-mono text-warning bg-warning/10 px-1.5 py-0.5 rounded">
                                no key
                              </span>
                            )
                          ) : (
                            <span className="ml-auto text-2xs font-mono text-accent bg-accent/10 px-1.5 py-0.5 rounded">
                              local
                            </span>
                          )}
                        </div>

                        {/* Models list */}
                        <div className="flex flex-wrap gap-1 mb-2.5">
                          {provider.models.map((m) => (
                            <span
                              key={m.id}
                              className="text-2xs font-mono text-text-muted bg-surface border border-border rounded px-1.5 py-0.5"
                            >
                              {m.name}
                              {m.fast && <span className="text-success/60 ml-1">⚡</span>}
                            </span>
                          ))}
                        </div>

                        {/* Key input */}
                        {provider.requires_key && (
                          <div className="flex items-center gap-2">
                            <input
                              type="password"
                              placeholder={
                                provider.has_key
                                  ? "••••••••••••••••"
                                  : `Enter ${provider.name} API key...`
                              }
                              value={keys[provider.id] || ""}
                              onChange={(e) =>
                                setKeys((prev) => ({ ...prev, [provider.id]: e.target.value }))
                              }
                              className="flex-1 bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-text placeholder-text-muted focus:outline-none focus:border-accent/50 transition-colors font-mono"
                              style={{ color: "#ffffff" }}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") handleSaveKey(provider.id);
                              }}
                            />
                            {provider.has_key && (
                              <button
                                onClick={() => handleDeleteKey(provider.id)}
                                className="flex-shrink-0 px-2 py-1.5 rounded-lg bg-danger/10 border border-danger/20 text-danger text-2xs font-mono hover:bg-danger/20 transition-all"
                              >
                                remove
                              </button>
                            )}
                            <button
                              onClick={() => handleSaveKey(provider.id)}
                              disabled={!keys[provider.id]?.trim() || saving === provider.id}
                              className="flex-shrink-0 px-2.5 py-1.5 rounded-lg bg-accent/10 border border-accent/20 text-accent text-2xs font-mono hover:bg-accent/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                            >
                              {saving === provider.id ? "..." : "save"}
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
              </div>

              {/* Footer */}
              <div className="px-5 py-3 border-t border-border">
                <p className="text-2xs font-mono text-text-muted">
                  API keys are stored locally on your machine. They are never sent anywhere except the respective provider's API.
                </p>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
