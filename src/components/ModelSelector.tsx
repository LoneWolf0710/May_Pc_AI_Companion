import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface ModelInfo {
  provider: string;
  provider_name: string;
  id: string;
  name: string;
  fast: boolean;
  available: boolean;
}

interface ModelSelectorProps {
  models: ModelInfo[];
  selectedModel: string;
  selectedProvider: string;
  onSelect: (provider: string, model: string) => void;
  onOpenSettings: () => void;
  variant?: "compact" | "full";
}

export function ModelSelector({
  models,
  selectedModel,
  selectedProvider,
  onSelect,
  onOpenSettings,
  variant = "compact",
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [expandedProvider, setExpandedProvider] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setSearch("");
      }
    };
    if (isOpen) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [isOpen]);

  // Focus search input when dropdown opens
  useEffect(() => {
    if (isOpen && searchRef.current) {
      searchRef.current.focus();
    }
  }, [isOpen]);

  const selected = models.find(
    (m) => m.id === selectedModel && m.provider === selectedProvider
  );

  // Filter models by search query
  const filteredModels = search.trim()
    ? models.filter(
        (m) =>
          m.name.toLowerCase().includes(search.toLowerCase()) ||
          m.id.toLowerCase().includes(search.toLowerCase()) ||
          m.provider_name.toLowerCase().includes(search.toLowerCase())
      )
    : models;

  // Group models by provider
  const grouped = filteredModels.reduce(
    (acc, m) => {
      if (!acc[m.provider]) acc[m.provider] = { name: m.provider_name, models: [] };
      acc[m.provider].models.push(m);
      return acc;
    },
    {} as Record<string, { name: string; models: ModelInfo[] }>
  );

  // Auto-expand first provider with search matches when searching
  useEffect(() => {
    if (search.trim()) {
      const firstMatch = Object.keys(grouped)[0];
      setExpandedProvider(firstMatch ?? null);
    } else {
      setExpandedProvider(null);
    }
  }, [search, filteredModels.length]);

  const toggleProvider = (provider: string) => {
    setExpandedProvider((prev) => (prev === provider ? null : provider));
  };

  // Provider icons
  const providerIcon = (provider: string) => {
    switch (provider) {
      case "ollama":
        return "🖥️";
      case "openai":
        return "🟢";
      case "anthropic":
        return "🟠";
      case "gemini":
        return "🔵";
      case "openrouter":
        return "🌐";
      case "ollama_cloud":
        return "☁️";
      default:
        return "🤖";
    }
  };

  const dropdownWidth = variant === "full" ? "w-80" : "w-72";
  const maxHeight = variant === "full" ? "max-h-[400px]" : "max-h-[320px]";

  if (variant === "full") {
    return (
      <div className="relative" ref={dropdownRef}>
        {/* Full variant - prominent button for chat input area */}
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-elevated border border-border hover:border-accent/30 transition-all text-left"
          title="Select model"
        >
          <span className="text-sm">{selected ? providerIcon(selected.provider) : "🤖"}</span>
          <div className="flex-1 min-w-0">
            <span className="text-xs font-mono text-text block truncate">
              {selected ? selected.name : "Select model"}
            </span>
            <span className="text-2xs font-mono text-text-muted">
              {selected ? selected.provider_name : "Choose a provider"}
            </span>
          </div>
          <svg
            width="10"
            height="10"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            className={`text-text-muted transition-transform flex-shrink-0 ${isOpen ? "rotate-180" : ""}`}
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </button>

        {/* Dropdown */}
        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: -4, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.98 }}
              transition={{ duration: 0.12 }}
              className={`absolute bottom-full mb-2 left-0 ${dropdownWidth} bg-surface border border-border rounded-xl shadow-elevated z-50 overflow-hidden`}
            >
              {/* Search input */}
              <div className="px-3 pt-3 pb-2">
                <div className="relative">
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
                  >
                    <circle cx="11" cy="11" r="8" />
                    <path d="m21 21-4.3-4.3" />
                  </svg>
                  <input
                    ref={searchRef}
                    type="text"
                    placeholder="Search models..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full bg-surface-elevated border border-border rounded-lg pl-8 pr-3 py-2 text-xs font-mono text-text placeholder-text-muted focus:outline-none focus:border-accent/50 transition-colors"
                    style={{ color: '#ffffff' }}
                    onKeyDown={(e) => {
                      if (e.key === "Escape") {
                        setSearch("");
                        setIsOpen(false);
                      }
                    }}
                  />
                </div>
              </div>

              <div className={`px-1.5 pb-1.5 ${maxHeight} overflow-y-auto`}>
                {Object.entries(grouped).map(([providerId, group]) => (
                  <div key={providerId} className="mb-1">
                    {/* Collapsible provider header */}
                    <button
                      onClick={() => toggleProvider(providerId)}
                      className="w-full flex items-center gap-2 px-2 py-2 hover:bg-surface-elevated rounded-lg transition-all"
                    >
                      <span className="text-sm">{providerIcon(providerId)}</span>
                      <span className="text-xs font-mono font-medium text-text-secondary uppercase tracking-wider">
                        {group.name}
                      </span>
                      <span className="text-2xs font-mono text-text-muted ml-1">
                        {group.models.length}
                      </span>
                      {group.models.some((m) => !m.available) && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setIsOpen(false);
                            onOpenSettings();
                          }}
                          className="ml-auto text-2xs font-mono text-accent hover:text-accent/80 transition-colors"
                        >
                          + key
                        </button>
                      )}
                      <svg
                        width="10"
                        height="10"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                      className={`text-text-muted transition-transform ${expandedProvider === providerId ? "rotate-180" : ""}`}
                    >
                      <path d="m6 9 6 6 6-6" />
                    </svg>
                    </button>

                    {/* Models (collapsible) */}
                    <AnimatePresence>
                      {expandedProvider === providerId && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.15 }}
                          className="overflow-hidden"
                        >
                          {group.models.map((model) => {
                            const isSelected =
                              model.id === selectedModel && model.provider === selectedProvider;
                            return (
                              <button
                                key={`${model.provider}-${model.id}`}
                                onClick={() => {
                                  if (model.available) {
                                    onSelect(model.provider, model.id);
                                    setIsOpen(false);
                                    setSearch("");
                                  }
                                }}
                                disabled={!model.available}
                                className={`w-full flex items-center gap-2 px-2 py-2 rounded-lg text-left transition-all ${
                                  isSelected
                                    ? "bg-accent/10 border border-accent/20"
                                    : model.available
                                      ? "hover:bg-surface-elevated border border-transparent"
                                      : "opacity-40 cursor-not-allowed border border-transparent"
                                }`}
                              >
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-1.5">
                                    <span
                                      className={`text-xs font-mono ${
                                        isSelected ? "text-accent" : "text-text"
                                      }`}
                                    >
                                      {model.name}
                                    </span>
                                    {model.fast && (
                                      <span className="text-2xs font-mono text-success/70 bg-success/10 px-1.5 py-0.5 rounded">
                                        fast
                                      </span>
                                    )}
                                  </div>
                                </div>
                                {isSelected && (
                                  <span className="w-2 h-2 rounded-full bg-accent shadow-glow" />
                                )}
                                {!model.available && (
                                  <span className="text-2xs font-mono text-text-muted">no key</span>
                                )}
                              </button>
                            );
                          })}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                ))}
              </div>

              {/* Settings link */}
              <div className="border-t border-border p-2">
                <button
                  onClick={() => {
                    setIsOpen(false);
                    onOpenSettings();
                  }}
                  className="w-full flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-surface-elevated transition-all text-left"
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-text-muted"
                  >
                    <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                  <span className="text-xs font-mono text-text-muted">API Key Settings</span>
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  }

  // Compact variant for StatusHUD
  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-surface-elevated border border-border hover:border-accent/30 transition-all text-left"
        title="Select model"
      >
        <span className="text-xs">{selected ? providerIcon(selected.provider) : "🤖"}</span>
        <span className="text-2xs font-mono text-text-secondary truncate max-w-[100px]">
          {selected ? selected.name : "Select model"}
        </span>
        <svg
          width="8"
          height="8"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          className={`text-text-muted transition-transform ${isOpen ? "rotate-180" : ""}`}
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {/* Dropdown */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.12 }}
            className="absolute right-0 top-full mt-1 w-72 bg-surface border border-border rounded-xl shadow-elevated z-50 overflow-hidden"
          >
            {/* Search input */}
            <div className="px-2.5 pt-2.5 pb-1.5">
              <div className="relative">
                <svg
                  width="11"
                  height="11"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted"
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.3-4.3" />
                </svg>
                <input
                  ref={searchRef}
                  type="text"
                  placeholder="Search models..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full bg-surface-elevated border border-border rounded-lg pl-7 pr-3 py-1.5 text-2xs font-mono text-text placeholder-text-muted focus:outline-none focus:border-accent/50 transition-colors"
                  style={{ color: '#ffffff' }}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") {
                      setSearch("");
                      setIsOpen(false);
                    }
                  }}
                />
              </div>
            </div>

            <div className="p-1.5 pt-0.5 max-h-[320px] overflow-y-auto">
              {Object.entries(grouped).map(([providerId, group]) => (
                <div key={providerId} className="mb-1">
                  {/* Collapsible provider header */}
                  <button
                    onClick={() => toggleProvider(providerId)}
                    className="w-full flex items-center gap-1.5 px-2 py-1.5 hover:bg-surface-elevated rounded-lg transition-all"
                  >
                    <span className="text-xs">{providerIcon(providerId)}</span>
                    <span className="text-2xs font-mono font-medium text-text-secondary uppercase tracking-wider">
                      {group.name}
                    </span>
                    <span className="text-2xs font-mono text-text-muted ml-0.5">
                      {group.models.length}
                    </span>
                    {group.models.some((m) => !m.available) && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setIsOpen(false);
                          onOpenSettings();
                        }}
                        className="ml-auto text-2xs font-mono text-accent hover:text-accent/80 transition-colors"
                      >
                        + key
                      </button>
                    )}
                    <svg
                      width="8"
                      height="8"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      className={`text-text-muted transition-transform ${expandedProvider === providerId ? "rotate-180" : ""}`}
                    >
                      <path d="m6 9 6 6 6-6" />
                    </svg>
                  </button>

                  {/* Models (collapsible) */}
                  <AnimatePresence>
                    {expandedProvider === providerId && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.15 }}
                        className="overflow-hidden"
                      >
                        {group.models.map((model) => {
                          const isSelected =
                            model.id === selectedModel && model.provider === selectedProvider;
                          return (
                            <button
                              key={`${model.provider}-${model.id}`}
                              onClick={() => {
                                if (model.available) {
                                  onSelect(model.provider, model.id);
                                  setIsOpen(false);
                                  setSearch("");
                                }
                              }}
                              disabled={!model.available}
                              className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-all ${
                                isSelected
                                  ? "bg-accent/10 border border-accent/20"
                                  : model.available
                                    ? "hover:bg-surface-elevated border border-transparent"
                                    : "opacity-40 cursor-not-allowed border border-transparent"
                              }`}
                            >
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1.5">
                                  <span
                                    className={`text-2xs font-mono ${
                                      isSelected ? "text-accent" : "text-text"
                                    }`}
                                  >
                                    {model.name}
                                  </span>
                                  {model.fast && (
                                    <span className="text-2xs font-mono text-success/70 bg-success/10 px-1 rounded">
                                      fast
                                    </span>
                                  )}
                                </div>
                              </div>
                              {isSelected && (
                                <span className="w-1.5 h-1.5 rounded-full bg-accent shadow-glow" />
                              )}
                              {!model.available && (
                                <span className="text-2xs font-mono text-text-muted">no key</span>
                              )}
                            </button>
                          );
                        })}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              ))}
            </div>

            {/* Settings link */}
            <div className="border-t border-border p-1.5">
              <button
                onClick={() => {
                  setIsOpen(false);
                  onOpenSettings();
                }}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-surface-elevated transition-all text-left"
              >
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-text-muted"
                >
                  <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                <span className="text-2xs font-mono text-text-muted">API Key Settings</span>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
