/**
 * RiveAvatar — Wraps a Rive animation file (.riv) with state machine inputs
 * mapped to May's states (idle, thinking, listening, speaking) and moods.
 *
 * Falls back to the SVG Avatar when no .riv file is available.
 *
 * To use a custom Rive avatar:
 * 1. Create a .riv file in Rive Editor (rive.app)
 * 2. Define a state machine with these inputs:
 *    - Boolean: isThinking, isListening, isSpeaking
 *    - Number: mood (0=neutral, 1=happy, 2=cool, 3=concerned, 4=surprised)
 *    - Number: amplitude (0.0-1.0, for lip-sync)
 * 3. Place the file at `public/avatar.riv`
 */

import { useState, useEffect } from "react";
import type { MayState, MayMood } from "../App";
import { Avatar } from "./Avatar";

interface RiveAvatarProps {
  state: MayState;
  mood: MayMood;
  amplitude?: number;
}

// Mood → numeric mapping for the Rive state machine
const MOOD_MAP: Record<MayMood, number> = {
  neutral: 0,
  happy: 1,
  cool: 2,
  concerned: 3,
  surprised: 4,
};

// Path to the .riv file (in the public directory)
const RIVE_SRC = "/avatar.riv";
const STATE_MACHINE_NAME = "MayStateMachine";

/**
 * Try to load the Rive runtime dynamically.
 * Returns the Rive class or null if loading fails.
 */
async function loadRiveRuntime() {
  try {
    const mod = await import("@rive-app/react-canvas");
    return mod;
  } catch {
    return null;
  }
}

/**
 * Inner Rive avatar that uses the actual Rive runtime.
 * Only rendered when the .riv file is successfully loaded.
 */
function RiveInner({
  state,
  mood,
  amplitude = 0,
}: {
  state: MayState;
  mood: MayMood;
  amplitude: number;
}) {
  const [riveModule, setRiveModule] = useState<any>(null);
  const [riveReady, setRiveReady] = useState(false);

  useEffect(() => {
    loadRiveRuntime().then((mod) => {
      if (mod) {
        setRiveModule(mod);
        setRiveReady(true);
      }
    });
  }, []);

  // Always render the Rive component placeholder — it mounts once riveReady is true
  // We use a child component that calls useRive only when the module is available
  if (!riveReady || !riveModule) {
    return <Avatar state={state} mood={mood} amplitude={amplitude} />;
  }

  return <RiveLoaded state={state} mood={mood} amplitude={amplitude} riveModule={riveModule} />;
}

/** Inner component that safely calls useRive — only mounted when riveModule is available. */
function RiveLoaded({
  state,
  mood,
  amplitude,
  riveModule,
}: {
  state: MayState;
  mood: MayMood;
  amplitude: number;
  riveModule: any;
}) {
  const [loadError, setLoadError] = useState(false);

  const { rive, RiveComponent } = riveModule.useRive({
    src: RIVE_SRC,
    stateMachines: STATE_MACHINE_NAME,
    autoplay: true,
    onError: () => setLoadError(true),
  });

  // Update state machine inputs when May's state/mood changes
  useEffect(() => {
    if (!rive || loadError) return;

    try {
      const isThinking = rive.getBooleanMachineInput?.(STATE_MACHINE_NAME, "isThinking")
        || rive.getTextMachineInput?.(STATE_MACHINE_NAME, "isThinking");
      const isListening = rive.getBooleanMachineInput?.(STATE_MACHINE_NAME, "isListening")
        || rive.getTextMachineInput?.(STATE_MACHINE_NAME, "isListening");
      const isSpeaking = rive.getBooleanMachineInput?.(STATE_MACHINE_NAME, "isSpeaking")
        || rive.getTextMachineInput?.(STATE_MACHINE_NAME, "isSpeaking");

      if (isThinking) isThinking.value = state === "thinking";
      if (isListening) isListening.value = state === "listening";
      if (isSpeaking) isSpeaking.value = state === "speaking";

      const moodInput = rive.getNumberMachineInput?.(STATE_MACHINE_NAME, "mood");
      if (moodInput) moodInput.value = MOOD_MAP[mood];

      const ampInput = rive.getNumberMachineInput?.(STATE_MACHINE_NAME, "amplitude");
      if (ampInput) ampInput.value = Math.min(1, Math.max(0, amplitude));
    } catch {
      setLoadError(true);
    }
  }, [rive, state, mood, amplitude, loadError]);

  if (loadError || !RiveComponent) {
    return <Avatar state={state} mood={mood} amplitude={amplitude} />;
  }

  return (
    <div className="relative w-36 h-36 flex items-center justify-center">
      <RiveComponent style={{ width: "100%", height: "100%" }} />
    </div>
  );
}

/**
 * RiveAvatar — Smart wrapper that:
 * 1. Checks if a .riv file exists at /avatar.riv
 * 2. If yes → renders the Rive state machine avatar
 * 3. If no → renders the SVG Avatar fallback
 *
 * The check is done once on mount and cached.
 */
export function RiveAvatar({ state, mood, amplitude = 0 }: RiveAvatarProps) {
  const [riveAvailable, setRiveAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    // Check if the .riv file exists
    fetch(RIVE_SRC, { method: "HEAD" })
      .then((res) => setRiveAvailable(res.ok))
      .catch(() => setRiveAvailable(false));
  }, []);

  // Still checking — show SVG avatar as placeholder
  if (riveAvailable === null) {
    return <Avatar state={state} mood={mood} amplitude={amplitude} />;
  }

  // .riv file not found — use SVG fallback
  if (!riveAvailable) {
    return <Avatar state={state} mood={mood} amplitude={amplitude} />;
  }

  // .riv file found — use Rive
  return <RiveInner state={state} mood={mood} amplitude={amplitude} />;
}

export default RiveAvatar;
