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

interface WakeWordInfo {
  enabled: boolean;
  loaded: boolean;
  model: string;
  threshold: number;
  last_confidence: number;
  detection_count: number;
}

interface PrivacyInfo {
  active: boolean;
  duration_sec: number;
  registered_modules: string[];
  total_audit_entries: number;
}

interface AuditEntry {
  timestamp: number;
  action: string;
  reason: string;
  modules_paused: string[];
  duration_sec: number;
}

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onKeySaved: () => void;
}

const LAYERS = [
  { key: 'L1', name: 'Filesystem', actions: 35 },
  { key: 'L2', name: 'Process', actions: 24 },
  { key: 'L3', name: 'Application', actions: 21 },
  { key: 'L4', name: 'Window', actions: 32 },
  { key: 'L5', name: 'Input', actions: 25 },
  { key: 'L6', name: 'Registry', actions: 18 },
  { key: 'L7', name: 'Services', actions: 31 },
  { key: 'L8', name: 'System', actions: 49 },
  { key: 'L9', name: 'Browser', actions: 34 },
  { key: 'L10', name: 'Network', actions: 38 },
  { key: 'L11', name: 'Media', actions: 32 },
  { key: 'L12', name: 'Developer', actions: 35 },
  { key: 'L13', name: 'Cloud', actions: 30 },
  { key: 'L14', name: 'Automation', actions: 28 },
  { key: 'L15', name: 'Advanced', actions: 35 },
];

export function SettingsModal({ isOpen, onClose, onKeySaved }: SettingsModalProps) {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [sttModel, setSttModel] = useState<SttModelInfo | null>(null);
  const [sttLoading, setSttLoading] = useState(false);
  const [sttError, setSttError] = useState<string | null>(null);
  const [wakeWord, setWakeWord] = useState<WakeWordInfo | null>(null);
  const [wakeWordLoading, setWakeWordLoading] = useState(false);
  const [privacy, setPrivacy] = useState<PrivacyInfo | null>(null);
  const [privacyLoading, setPrivacyLoading] = useState(false);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [showAudit, setShowAudit] = useState(false);
  const [city, setCity] = useState("");
  const [citySaving, setCitySaving] = useState(false);
  const [cityStatus, setCityStatus] = useState<string | null>(null);
  const [showLayers, setShowLayers] = useState(false);
  // P6: Personality Modes state
  const [personality, setPersonality] = useState<Record<string, unknown> | null>(null);
  const [personalityLoading, setPersonalityLoading] = useState(false);
  // P5: Llama-Server state
  const [llamaServer, setLlamaServer] = useState<Record<string, unknown> | null>(null);
  const [llamaLoading, setLlamaLoading] = useState(false);
  // P6: Security Monitor state
  const [secMonitor, setSecMonitor] = useState<Record<string, unknown> | null>(null);
  const [secAlerts, setSecAlerts] = useState<Array<Record<string, unknown>>>([]);
  const [showSecAlerts, setShowSecAlerts] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchProviders();
      fetchSttModel();
      fetchWakeWord();
      fetchPrivacy();
      fetchSettings();
      fetchPersonality();
      fetchLlamaServer();
      fetchSecMonitor();
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
    setSttError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/voice/model`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model }),
      });
      if (res.ok) {
        const data = await res.json();
        setSttModel(data);
      } else {
        const data = await res.json().catch(() => ({}));
        setSttError(data.error || `Failed to switch model (HTTP ${res.status})`);
      }
    } catch (e) {
      setSttError(`Connection error: ${e instanceof Error ? e.message : "unknown"}`);
    } finally {
      setSttLoading(false);
    }
  };

  const fetchWakeWord = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/voice/wake-word`);
      if (res.ok) setWakeWord(await res.json());
    } catch {}
  };

  const handleToggleWakeWord = async (enabled: boolean) => {
    setWakeWordLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/voice/wake-word`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      if (res.ok) setWakeWord(await res.json());
    } catch {} finally {
      setWakeWordLoading(false);
    }
  };

  const fetchPrivacy = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/privacy`);
      if (res.ok) setPrivacy(await res.json());
    } catch {}
  };

  const handleTogglePrivacy = async () => {
    setPrivacyLoading(true);
    try {
      await fetch(`${BACKEND_URL}/privacy/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "Settings modal toggle" }),
      });
      // Re-fetch actual state from server instead of guessing from response
      await fetchPrivacy();
    } catch {} finally {
      setPrivacyLoading(false);
    }
  };

  const fetchAuditLog = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/privacy/audit?limit=20`);
      if (res.ok) {
        const data = await res.json();
        setAuditLog(data.entries ?? []);
      }
    } catch {}
  };

  const fetchSettings = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/settings`);
      if (res.ok) {
        const data = await res.json();
        setCity(data.city || "");
      }
    } catch {}
  };

  const handleSaveCity = async () => {
    setCitySaving(true);
    setCityStatus(null);
    try {
      const res = await fetch(`${BACKEND_URL}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city: city.trim() }),
      });
      if (res.ok) {
        setCityStatus("saved");
        setTimeout(() => setCityStatus(null), 2000);
      }
    } catch {
      setCityStatus("error");
    } finally {
      setCitySaving(false);
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

  // P6: Personality Modes handlers
  const fetchPersonality = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/personality`);
      if (res.ok) setPersonality(await res.json());
    } catch {}
  };
  const handleSetPersonality = async (name: string) => {
    setPersonalityLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/personality/set`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (res.ok) setPersonality(await res.json());
    } catch {} finally { setPersonalityLoading(false); }
  };

  // P5: Llama-Server handlers
  const fetchLlamaServer = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/llama-server`);
      if (res.ok) setLlamaServer(await res.json());
    } catch {}
  };
  const [llamaTargetModel, setLlamaTargetModel] = useState("");
  const [llamaDraftModel, setLlamaDraftModel] = useState("");

  const handleLlamaServerAction = async (action: string) => {
    setLlamaLoading(true);
    try {
      if (action === "start") {
        const body: Record<string, string> = {};
        if (llamaTargetModel.trim()) body.target_model = llamaTargetModel.trim();
        if (llamaDraftModel.trim()) body.draft_model = llamaDraftModel.trim();
        const res = await fetch(`${BACKEND_URL}/llama-server/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: Object.keys(body).length ? JSON.stringify(body) : undefined,
        });
        if (res.ok) setLlamaServer(await res.json());
      } else if (action === "stop") {
        const res = await fetch(`${BACKEND_URL}/llama-server/stop`, { method: "POST" });
        if (res.ok) setLlamaServer(await res.json());
      } else if (action === "config") {
        const body: Record<string, string> = {};
        if (llamaTargetModel.trim()) body.target_model = llamaTargetModel.trim();
        if (llamaDraftModel.trim()) body.draft_model = llamaDraftModel.trim();
        const res = await fetch(`${BACKEND_URL}/llama-server/config`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (res.ok) setLlamaServer(await res.json());
      }
    } catch {} finally { setLlamaLoading(false); }
  };

  // P6: Security Monitor handlers
  const fetchSecMonitor = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/security-monitor`);
      if (res.ok) setSecMonitor(await res.json());
    } catch {}
  };
  const fetchSecAlerts = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/security-monitor/alerts?limit=10`);
      if (res.ok) { const data = await res.json(); setSecAlerts(data.alerts ?? []); }
    } catch {}
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
              <div className="px-5 py-4 max-h-[500px] overflow-y-auto">
                {/* Location / City Section */}
                <div className="mb-4 bg-surface-elevated border border-border rounded-xl p-3.5">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">📍</span>
                    <span className="text-xs font-medium text-text">Location</span>
                    {city && (
                      <span className="ml-auto text-2xs font-mono text-success bg-success/10 px-1.5 py-0.5 rounded">
                        {city}
                      </span>
                    )}
                  </div>
                  <p className="text-2xs text-text-muted mb-2.5">
                    Set your city for accurate weather forecasts. Leave empty to use IP-based location.
                  </p>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="e.g. New York, London, Tokyo..."
                      value={city}
                      onChange={(e) => setCity(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") handleSaveCity(); }}
                      className="flex-1 bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-text placeholder-text-muted focus:outline-none focus:border-accent/50 transition-colors font-mono"
                      style={{ color: "#ffffff" }}
                    />
                    <button
                      onClick={handleSaveCity}
                      disabled={citySaving}
                      className="flex-shrink-0 px-2.5 py-1.5 rounded-lg bg-accent/10 border border-accent/20 text-accent text-2xs font-mono hover:bg-accent/20 transition-all disabled:opacity-40"
                    >
                      {citySaving ? "..." : cityStatus === "saved" ? "✓" : "save"}
                    </button>
                  </div>
                </div>

                {/* Privacy Mode Section */}
                <div className="mb-4 bg-surface-elevated border border-border rounded-xl p-3.5">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">🔒</span>
                    <span className="text-xs font-medium text-text">Privacy Mode</span>
                    <span className={`ml-auto text-2xs font-mono px-1.5 py-0.5 rounded ${
                      privacy?.active
                        ? "text-danger bg-danger/10"
                        : "text-success bg-success/10"
                    }`}> {privacy?.active ? "ACTIVE" : "off"}
                    </span>
                  </div>
                  <p className="text-2xs text-text-muted mb-2.5">
                    Pauses shadow learning, screen watching, frustration detection, and wake word.
                    {privacy?.active && privacy.duration_sec > 0 && (
                      <span className="text-warning ml-1">Active for {Math.round(privacy.duration_sec)}s</span>
                    )}
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleTogglePrivacy}
                      disabled={privacyLoading}
                      className={`text-2xs font-mono px-3 py-1.5 rounded-lg border transition-all ${
                        privacy?.active
                          ? "bg-danger/20 border-danger/30 text-danger hover:bg-danger/30"
                          : "bg-surface border-border text-text-muted hover:border-success/30 hover:text-success"
                      } disabled:opacity-40`}
                    >
                      {privacyLoading ? "..." : privacy?.active ? "disable" : "enable"}
                    </button>
                    <button
                      onClick={() => { setShowAudit(!showAudit); fetchAuditLog(); }}
                      className="text-2xs font-mono px-3 py-1.5 rounded-lg border bg-surface border-border text-text-muted hover:border-accent/30 hover:text-text transition-all"
                    >
                      audit log ({privacy?.total_audit_entries ?? 0})
                    </button>
                  </div>
                  {showAudit && auditLog.length > 0 && (
                    <div className="mt-2.5 space-y-1 max-h-28 overflow-y-auto">
                      {auditLog.map((entry, i) => (
                        <div key={`${entry.timestamp}-${entry.action}-${i}`} className="text-2xs font-mono text-text-muted bg-surface border border-border rounded px-2 py-1">
                          <span className={entry.action.includes("enabled") ? "text-danger" : "text-success"}>
                            {entry.action.includes("enabled") ? "PAUSED" : "RESUMED"}
                          </span>
                          <span className="ml-2">{new Date(entry.timestamp * 1000).toLocaleTimeString()}</span>
                          {entry.duration_sec > 0 && <span className="ml-2">({Math.round(entry.duration_sec)}s)</span>}
                          <span className="ml-2 opacity-60">{entry.reason}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Wake Word Section */}
                <div className="mb-4 bg-surface-elevated border border-border rounded-xl p-3.5">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">🎤</span>
                    <span className="text-xs font-medium text-text">Wake Word</span>
                    <span className={`ml-auto text-2xs font-mono px-1.5 py-0.5 rounded ${
                      wakeWord?.enabled
                        ? wakeWord?.loaded ? "text-success bg-success/10" : "text-warning bg-warning/10"
                        : "text-text-muted bg-surface"
                    }`}> {wakeWord?.enabled ? (wakeWord?.loaded ? "listening" : "loading...") : "off"}
                    </span>
                  </div>
                  <p className="text-2xs text-text-muted mb-2.5">
                    Say "{wakeWord?.model === 'hey_jarvis' ? 'Hey Jarvis' : wakeWord?.model || 'wake word'}" to activate May hands-free.
                    {wakeWord?.enabled && wakeWord.last_confidence > 0 && (
                      <span className="text-accent ml-1">confidence: {(wakeWord.last_confidence * 100).toFixed(0)}%</span>
                    )}
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleToggleWakeWord(!wakeWord?.enabled)}
                      disabled={wakeWordLoading}
                      className={`text-2xs font-mono px-3 py-1.5 rounded-lg border transition-all ${
                        wakeWord?.enabled
                          ? "bg-success/20 border-success/30 text-success hover:bg-success/30"
                          : "bg-surface border-border text-text-muted hover:border-accent/30 hover:text-text"
                      } disabled:opacity-40`}
                    >
                      {wakeWordLoading ? "..." : wakeWord?.enabled ? "disable" : "enable"}
                    </button>
                    <span className="text-2xs text-text-muted font-mono">
                      model: {wakeWord?.model || "none"}
                    </span>
                  </div>
                </div>

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
                  {sttError && <p className="text-2xs text-danger mt-2">{sttError}</p>}
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

                {/* Control Core Layers Section */}
                <div className="mt-4 bg-surface-elevated border border-border rounded-xl p-3.5">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm">🏗️</span>
                      <span className="text-xs font-medium text-text">Control Core</span>
                    </div>
                    <button
                      onClick={() => setShowLayers(!showLayers)}
                      className="text-2xs font-mono px-2 py-1 rounded-lg border bg-surface border-border text-text-muted hover:border-accent/30 hover:text-text transition-all"
                    >
                      {showLayers ? 'hide' : `${LAYERS.length} layers`}
                    </button>
                  </div>
                  {showLayers && (
                    <div className="mt-2 space-y-1.5">
                      {LAYERS.map((layer) => (
                        <div key={layer.key} className="flex items-center justify-between py-1">
                          <div className="flex items-center gap-2">
                            <span className="text-2xs font-mono font-medium text-text-secondary">{layer.key}</span>
                            <span className="text-2xs text-text-muted">{layer.name}</span>
                          </div>
                          <span className="text-2xs font-mono px-1.5 py-0.5 rounded bg-accent/10 text-accent">
                            {layer.actions} actions
                          </span>
                        </div>
                      ))}
                      <div className="pt-1 border-t border-border text-2xs font-mono text-text-muted text-center">
                        15 layers • 467 actions total
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* P6: Personality Modes Section */}
              <div className="mt-4 bg-surface-elevated border border-border rounded-xl p-3.5">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm">🎭</span>
                  <span className="text-xs font-medium text-text">Personality Mode</span>
                  <span className="ml-auto text-2xs font-mono text-accent bg-accent/10 px-1.5 py-0.5 rounded">
                    {(personality?.active_profile as string) || "shikimori"}
                  </span>
                </div>
                <p className="text-2xs text-text-muted mb-2.5">
                  Switch May's personality. Each mode changes how she talks and responds.
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries((personality?.available_profiles ?? {}) as Record<string, { name: string; description: string }>).map(([key, p]) => (
                    <button
                      key={key}
                      onClick={() => handleSetPersonality(key)}
                      disabled={personalityLoading}
                      title={p.description}
                      className={`text-2xs font-mono px-2 py-1 rounded-lg border transition-all ${
                        personality?.active_profile === key
                          ? "bg-accent/20 border-accent/30 text-accent"
                          : "bg-surface border-border text-text-muted hover:border-accent/30 hover:text-text"
                      } disabled:opacity-40`}
                    >
                      {p.name || key}
                    </button>
                  ))}
                </div>
              </div>

              {/* P5: Speculative Decoding (Llama-Server) Section */}
              <div className="mt-4 bg-surface-elevated border border-border rounded-xl p-3.5">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm">🚀</span>
                  <span className="text-xs font-medium text-text">Speculative Decoding</span>
                  <span className={`ml-auto text-2xs font-mono px-1.5 py-0.5 rounded ${
                    llamaServer?.running ? "text-success bg-success/10" : "text-text-muted bg-surface"
                  }`}>{
                    llamaServer?.running ? "active" : llamaServer?.executable_found ? "ready" : "not installed"
                  }</span>
                </div>
                <p className="text-2xs text-text-muted mb-2.5">
                  25-40% faster via llama-server draft→verify. Needs llama.cpp installed + GGUF models.
                </p>
                {/* Model path configuration */}
                <div className="space-y-2 mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-2xs font-mono text-text-muted w-14">target:</span>
                    <input
                      type="text"
                      placeholder={String(llamaServer?.target_model || "phi4-mini:3.8b")}
                      value={llamaTargetModel}
                      onChange={(e) => setLlamaTargetModel(e.target.value)}
                      className="flex-1 bg-surface border border-border rounded-lg px-2.5 py-1 text-2xs text-text placeholder-text-muted focus:outline-none focus:border-accent/50 transition-colors font-mono"
                      style={{ color: "#ffffff" }}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-2xs font-mono text-text-muted w-14">draft:</span>
                    <input
                      type="text"
                      placeholder={String(llamaServer?.draft_model || "qwen3:0.6b")}
                      value={llamaDraftModel}
                      onChange={(e) => setLlamaDraftModel(e.target.value)}
                      className="flex-1 bg-surface border border-border rounded-lg px-2.5 py-1 text-2xs text-text placeholder-text-muted focus:outline-none focus:border-accent/50 transition-colors font-mono"
                      style={{ color: "#ffffff" }}
                    />
                  </div>
                </div>
                {llamaServer?.running ? (
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-2xs font-mono text-text-muted">
                      <span>port: {String(llamaServer.port ?? 8081)}</span>
                      <span>pid: {String(llamaServer.pid ?? "—")}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleLlamaServerAction("stop")}
                        disabled={llamaLoading}
                        className="text-2xs font-mono px-3 py-1.5 rounded-lg border bg-danger/10 border-danger/20 text-danger hover:bg-danger/20 transition-all disabled:opacity-40"
                      >
                        {llamaLoading ? "..." : "stop server"}
                      </button>
                      <button
                        onClick={() => handleLlamaServerAction("config")}
                        disabled={llamaLoading}
                        className="text-2xs font-mono px-3 py-1.5 rounded-lg border bg-surface border-border text-text-muted hover:border-accent/30 hover:text-text transition-all disabled:opacity-40"
                      >
                        save config
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleLlamaServerAction("start")}
                      disabled={llamaLoading || !llamaServer?.executable_found}
                      className="text-2xs font-mono px-3 py-1.5 rounded-lg border bg-success/10 border-success/20 text-success hover:bg-success/20 transition-all disabled:opacity-40"
                    >
                      {llamaLoading ? "starting..." : "start server"}
                    </button>
                    {!llamaServer?.executable_found && (
                      <span className="text-2xs font-mono text-warning">
                        llama-server not found — install llama.cpp
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* P6: Security Monitor Section */}
              <div className="mt-4 bg-surface-elevated border border-border rounded-xl p-3.5">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm">🛡️</span>
                  <span className="text-xs font-medium text-text">Security Monitor</span>
                  <span className={`ml-auto text-2xs font-mono px-1.5 py-0.5 rounded ${
                    secMonitor?.active ? "text-success bg-success/10" : "text-text-muted bg-surface"
                  }`}> {
                    secMonitor?.active ? "watching" : "off"
                  }</span>
                </div>
                <p className="text-2xs text-text-muted mb-2.5">
                  USB device tracking, microphone access, suspicious app alerts.
                </p>
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-2xs font-mono text-text-muted">
                    alerts: <span className="text-text">{String(secMonitor?.total_alerts ?? 0)}</span>
                  </span>
                  <span className="text-2xs font-mono text-text-muted">
                    usb: <span className="text-text">{String(secMonitor?.usb_devices_known ?? 0)}</span>
                  </span>
                  <span className="text-2xs font-mono text-text-muted">
                    mic apps: <span className="text-text">{String(secMonitor?.mic_apps_known ?? 0)}</span>
                  </span>
                </div>
                <button
                  onClick={() => { setShowSecAlerts(!showSecAlerts); fetchSecAlerts(); }}
                  className="text-2xs font-mono px-3 py-1.5 rounded-lg border bg-surface border-border text-text-muted hover:border-accent/30 hover:text-text transition-all"
                >
                  {showSecAlerts ? "hide alerts" : `show alerts (${secMonitor?.unacknowledged ?? 0} new)`}
                </button>
                {showSecAlerts && secAlerts.length > 0 && (
                  <div className="mt-2.5 space-y-1 max-h-28 overflow-y-auto">
                    {secAlerts.map((alert, i) => (
                      <div key={i} className="text-2xs font-mono text-text-muted bg-surface border border-border rounded px-2 py-1">
                        <span className={
                          alert.severity === "critical" ? "text-danger" :
                          alert.severity === "warning" ? "text-warning" : "text-text-muted"
                        }>
                          {alert.severity === "critical" ? "🔴" : alert.severity === "warning" ? "⚠️" : "ℹ️"}
                        </span>
                        <span className="ml-1.5 text-text">{alert.title as string}</span>
                        <span className="ml-2 opacity-60">{(alert.timestamp as number) ? new Date((alert.timestamp as number) * 1000).toLocaleTimeString() : ""}</span>
                      </div>
                    ))}
                  </div>
                )}
                {showSecAlerts && secAlerts.length === 0 && (
                  <p className="mt-2 text-2xs font-mono text-text-muted">No alerts recorded.</p>
                )}
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
