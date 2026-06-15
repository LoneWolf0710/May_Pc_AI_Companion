import { motion } from "framer-motion";

interface QuickActionsProps {
  onAction: (message: string) => void;
}

const actions = [
  {
    label: "Weather",
    shortcut: "⌘1",
    icon: "☀",
    command: "What's the weather right now?",
  },
  {
    label: "Time",
    shortcut: "⌘2",
    icon: "◎",
    command: "What time is it?",
  },
  {
    label: "Volume Up",
    shortcut: "⌘↑",
    icon: "⊕",
    command: "Turn up the volume",
  },
  {
    label: "Volume Down",
    shortcut: "⌘↓",
    icon: "⊖",
    command: "Turn down the volume",
  },
  {
    label: "Search",
    shortcut: "⌘3",
    icon: "⌕",
    command: "Search the web for ",
  },
  {
    label: "Remind Me",
    shortcut: "⌘4",
    icon: "⏱",
    command: "Set a reminder for ",
  },
];

export function QuickActions({ onAction }: QuickActionsProps) {
  return (
    <div className="border-t border-border px-2 py-2">
      <p className="text-2xs font-mono text-text-muted uppercase tracking-wider px-2 mb-1.5">
        Commands
      </p>
      <div className="space-y-0.5">
        {actions.map((action) => (
          <motion.button
            key={action.label}
            whileTap={{ scale: 0.98 }}
            onClick={() => onAction(action.command)}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-elevated transition-colors text-left group"
          >
            <span className="w-4 text-center text-xs text-text-muted/60 group-hover:text-accent transition-colors">
              {action.icon}
            </span>
            <span className="flex-1 text-xs text-text-secondary group-hover:text-text transition-colors">
              {action.label}
            </span>
            <span className="text-2xs font-mono text-text-muted/40">
              {action.shortcut}
            </span>
          </motion.button>
        ))}
      </div>
    </div>
  );
}
