# MAY — Final UI Design Specification

> **"May's UI should feel like you're looking at a living organism through a window — not typing into a chatbot."**

---

## Design Philosophy

### Anti-Slop Principles

May's UI will **never** look like generic AI slop. Here's what that means:

| AI Slop (Avoid) | May's Design (Do) |
|:---|:---|
| Centered chat bubble + floating orb | Asymmetric layout with purposeful hierarchy |
| Cyan/neon gradients everywhere | Warm dusk palette — indigo, lavender, emerald |
| Static glow effects | Every glow is driven by real-time data |
| Decorative avatar | Multi-layered orb that visualizes internal state |
| CSS fade transitions | Framer Motion spring physics with weight |
| Hidden system data | Living data visualizations always visible |
| Cookie-cutter SaaS layout | Unique asymmetric composition |
| Monochrome accent color | 4-color palette with intentional meaning |

### Core Principle: Everything Is Alive

Every pixel in May's UI serves a purpose. Every animation reflects real state. Every color carries meaning. Nothing is decorative — everything is functional beauty.

---

## Color Palette — "Warm Dusk"

A warm, muted palette that feels like dusk — present but not screaming. Replaces the cold cyan/purple of earlier versions.

### Primary Colors

| Role | Name | Hex | Usage |
|:---|:---|:---|:---|
| **Background** | Deep Warm | `#0c0a0f` | Main background (NOT pure `#000000`) |
| **Surface** | Warm Dark | `#1a1720` | Cards, panels, input fields |
| **Surface Elevated** | Warm Mid | `#242030` | Hover states, active elements |
| **Border** | Subtle Warm | `#2e2a3a` | Panel borders, dividers |
| **Border Hover** | Active Warm | `#3e3a4a` | Hover/focus borders |

### Accent Colors

| Role | Name | Hex | Usage |
|:---|:---|:---|:---|
| **Primary** | Soft Indigo | `#818cf8` | Main actions, active states, links |
| **Secondary** | Lavender | `#c084fc` | Companion warmth, secondary actions |
| **Alive** | Muted Emerald | `#34d399` | Success, online, healthy, active |
| **Warning** | Warm Amber | `#fbbf24` | Warnings, attention needed |
| **Danger** | Soft Red | `#f87171` | Errors, destructive actions |

### Text Colors

| Role | Name | Hex | Usage |
|:---|:---|:---|:---|
| **Primary** | Off White | `#f0f0f5` | Main text, headings |
| **Secondary** | Muted Lavender | `#9090a8` | Descriptions, labels |
| **Muted** | Deep Gray | `#55556a` | Placeholders, disabled |

### Orb-Specific Colors

| State | Glow Color | Meaning |
|:---|:---|:---|
| Idle | `rgba(129,140,248,0.12)` | Calm, resting |
| Thinking | `rgba(192,132,252,0.20)` | Processing, active |
| Listening | `rgba(52,211,153,0.18)` | Receptive, waiting |
| Speaking (text) | `rgba(129,140,248,0.25)` | Responding |
| Speaking (voice) | `rgba(52,211,153,0.22)` | Voicing, alive |
| Happy | `rgba(129,140,248,0.20)` | Content, warm |
| Concerned | `rgba(251,191,36,0.15)` | Alert, careful |
| Surprised | `rgba(248,113,113,0.15)` | Unexpected, reactive |

---

## Typography

| Role | Font | Weight | Size | Usage |
|:---|:---|:---|:---|:---|
| **Body** | Inter | 400-600 | 13-14px | Chat messages, UI text |
| **Data** | JetBrains Mono | 300-400 | 10-12px | System stats, timestamps, code |
| **Logo** | Inter | 700 | 16px | "May" branding |
| **Headings** | Inter | 600 | 12-13px | Section headers, card titles |

**Rules:**
- Never use monospace for body text
- Never use decorative/display fonts for UI
- JetBrains Mono only for data, timestamps, model names, technical readouts
- Letter-spacing: 0.05em for labels, 0.12em for uppercase micro-labels

---

## Layout — Asymmetric Living Panel

### Structure

```
┌──────────────────────────────────────────────────────────────────┐
│  ┌─────────┐  ┌──────────────────────────┐  ┌──────────────┐   │
│  │         │  │                          │  │              │   │
│  │  ORB    │  │                          │  │  INFO PANEL  │   │
│  │  +      │  │       CHAT AREA          │  │  (280px)     │   │
│  │  QUICK  │  │                          │  │              │   │
│  │  ACTIONS│  │                          │  │  Endocrine   │   │
│  │         │  │                          │  │  Brain       │   │
│  │ (240px) │  │                          │  │  Memory      │   │
│  │         │  │                          │  │  Sleep       │   │
│  │         │  │                          │  │  Screen      │   │
│  └─────────┘  └──────────────────────────┘  └──────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  INPUT BAR (glass, centered, mic + send + mode buttons)  │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### Layout Rules

1. **Three zones**: Left (240px) | Center (flex) | Right (280px)
2. **Left zone**: Orb (top 60%) + Quick Actions (bottom 40%)
3. **Center zone**: Status header (48px) + Chat messages (flex) + Input bar (56px)
4. **Right zone**: Info cards stacked vertically, scrollable
5. **Minimum window size**: 900x600px
6. **The orb is NOT centered** — it lives in the top-left, with asymmetric orbital rings
7. **Chat messages have varied widths** — 55%-75% random, with ±0.5deg rotation on entry
8. **Input bar floats** at the bottom with glassmorphism, not a hard border

### Asymmetric Orb Placement

The orb sits in the top-left quadrant of the left panel, NOT perfectly centered:
- Position: `top: 15%`, `left: 50%` (of left panel), `transform: translateX(-50%)`
- Orbital rings are deliberately asymmetric:
  - Ring 1: tilted 15deg, radius 72px, slow rotation (12s)
  - Ring 2: tilted -8deg, radius 64px, counter-rotation (18s)
  - Ring 3 (when active): tilted 35deg, radius 80px, fast rotation (6s)
- This asymmetry makes it feel organic, not mechanical

---

## The Orb — Multi-Layered Living Sphere

### Architecture

The orb is composed of 6 visual layers, each driven by real-time data:

```
Layer 6: Outer Glow (box-shadow, color + intensity from state)
Layer 5: Orbital Rings (3 rings, different speeds + tilts, driven by state)
Layer 4: Particles (SVG circles, orbit when active, driven by state)
Layer 3: Glass Sphere (backdrop-filter blur, gradient fill, breathing animation)
Layer 2: Face (SVG eyes, mouth, eyebrows, driven by state + mood)
Layer 1: Inner Glow (radial gradient overlay, color + pulse from state)
```

### Layer Details

#### Layer 6: Outer Glow
- **Source**: Framer Motion `animate.boxShadow`
- **Data**: `MayState` + `MayMood`
- **Behavior**: Continuous breathing pulse (scale 1.0 → 1.015 → 1.0)
- **Colors**: State-specific glow colors (see palette above)
- **Intensity**: Idle=0.12, Thinking=0.20, Listening=0.18, Speaking=0.25

#### Layer 5: Orbital Rings
- **Source**: 3 SVG circles with Framer Motion rotation
- **Data**: `MayState` (speed), `MayMood` (color shift)
- **Idle**: 1 ring, slow (12s), opacity 0.3
- **Thinking**: 2 rings, medium (8s + 12s counter), opacity 0.5
- **Listening**: 3 rings, fast (6s + 8s + 10s), opacity 0.6
- **Speaking**: 3 rings, very fast (3s + 4s + 5s), opacity 0.7
- **Key**: Rings are tilted at different angles (15deg, -8deg, 35deg) — NOT concentric

#### Layer 4: Particles
- **Source**: SVG `<circle>` elements with CSS orbital animations
- **Data**: `MayState` (active/inactive), amplitude (count)
- **Idle**: 0 particles
- **Thinking**: 6 particles, purple, spiral inward
- **Listening**: 8 particles, green, pulse outward
- **Speaking**: 10 particles, blue, scatter outward
- **Voice mode**: Particle count scales with amplitude (4-12)

#### Layer 3: Glass Sphere
- **Source**: CSS `backdrop-filter: blur(40px)` + gradient fill
- **Data**: `MayState` (breathing speed)
- **Size**: 112px diameter (current), scales to 128px for premium feel
- **Gradient**: `radial-gradient(circle at 35% 30%, rgba(129,140,248,0.20) 0%, rgba(192,132,252,0.08) 40%, rgba(0,0,0,0.5) 80%)`
- **Breathing**: Scale oscillation driven by state
  - Idle: `1.0 → 1.015 → 1.0` (4s cycle)
  - Thinking: `1.0 → 1.03 → 1.0` (2.5s cycle)
  - Listening: `1.0 → 1.04 → 1.0` (1.5s cycle)
  - Speaking: `1.0 → 1.05 → 1.0` (0.8s cycle)

#### Layer 2: Face (SVG)
- **Source**: SVG path elements with Framer Motion
- **Data**: `MayState` + `MayMood` + blink timer
- **Eyes**: 5 shapes (open, half, closed, wide, happy arc)
- **Pupils**: Track with state offset + audio amplitude when speaking
- **Mouth**: 6 shapes (neutral line, smile arc, open ellipse, wide circle, small-o, worried arc)
- **Eyebrows**: 2 lines with angle driven by mood
- **Blinking**: Random interval (3-5s), 150ms duration, state-dependent rate

#### Layer 1: Inner Glow
- **Source**: CSS `radial-gradient` overlay
- **Data**: `MayState` (active during thinking/speaking)
- **Behavior**: Pulsing opacity (0.2 → 0.4 → 0.2) at 1.5s cycle
- **Color**: Same as outer glow, but at 50% intensity

### State-Driven Animations

#### Idle State
```
Glow: Soft indigo, low intensity (0.12)
Rings: 1 ring, slow (12s), tilted 15deg
Particles: None
Sphere: Breathing at 4s cycle, scale 1.0→1.015
Face: Open eyes, neutral mouth, random blink (3.5s avg)
Inner Glow: Off
```

#### Thinking State
```
Glow: Lavender, medium intensity (0.20), pulsing faster
Rings: 2 rings, medium speed (8s + 12s counter-rotation)
Particles: 6 purple particles, spiral inward
Sphere: Breathing at 2.5s cycle, scale 1.0→1.03
Face: Half-closed eyes, small-o mouth, eyebrows raised (-15deg)
Inner Glow: On, pulsing at 1.5s
Additional: Faint neural network pattern appears inside sphere
```

#### Listening State
```
Glow: Muted emerald, medium intensity (0.18)
Rings: 3 rings, fast (6s + 8s + 10s)
Particles: 8 green particles, pulse outward
Sphere: Breathing at 1.5s cycle, scale 1.0→1.04
Face: Wide eyes, neutral mouth, eyebrows slightly raised (-10deg)
Inner Glow: Off
Additional: Concentric sonar rings expand outward (3 rings, 1.5s cycle)
Pupils: Dilate with audio amplitude
```

#### Speaking State (Text Response)
```
Glow: Soft indigo, high intensity (0.25)
Rings: 3 rings, fast (3s + 4s + 5s)
Particles: 10 blue particles, scatter outward
Sphere: Breathing at 0.8s cycle, scale 1.0→1.05
Face: Open eyes, animated mouth (letter-timed), neutral eyebrows
Inner Glow: On, radiating waves
Additional: Inner glow pulses with each word
```

#### Speaking State (Voice/TTS)
```
Glow: Muted emerald, high intensity (0.22), pulsing with speech
Rings: 3 rings, very fast, pulsing with amplitude
Particles: 4-12 particles (amplitude-scaled), scatter outward
Sphere: Breathing at 0.6s cycle, subtle vibration (±1px)
Face: Open eyes, MOUTH SYNCED TO AMPLITUDE (real lip-sync)
Inner Glow: On, color shifts with pitch
Additional: Entire orb vibrates subtly with speech rhythm
```

### Amplitude-Driven Lip Sync (Voice Mode)

When TTS is playing, the mouth animation is driven by real mic amplitude data:

```typescript
// In useBargeIn or a new useAmplitudeSync hook
const amplitude = micAmplitude; // 0.0 - 1.0

// Map amplitude to mouth shapes
const mouthOpenness = Math.min(1, amplitude * 3); // Scale up for visibility
const mouthWidth = 3.5 + mouthOpenness * 2; // 3.5 to 5.5
const mouthHeight = 2.5 + mouthOpenness * 2; // 2.5 to 4.5

// Apply to SVG mouth ellipse
<motion.ellipse
  rx={mouthWidth}
  ry={mouthHeight}
  animate={{ rx: mouthWidth, ry: mouthHeight }}
  transition={{ duration: 0.05 }} // Near-instant response
/>
```

### Mood Transitions

When mood changes, the orb transitions smoothly:
- **Duration**: 0.4s spring (`stiffness: 120, damping: 20`)
- **Glow color**: Cross-fades between state colors
- **Face features**: Morph between shapes with spring physics
- **Particles**: New particles spawn, old ones fade out over 0.6s
- **Rings**: Speed changes smoothly over 0.8s

---

## Chat Messages — Spring Physics

### Message Entry Animation

Every message enters with Framer Motion spring physics:

```typescript
// User messages — slide from right
<motion.div
  initial={{ opacity: 0, x: 20, rotate: Math.random() * 1 - 0.5 }}
  animate={{ opacity: 1, x: 0, rotate: 0 }}
  transition={{ type: "spring", stiffness: 300, damping: 25 }}
/>

// May's messages — slide from left
<motion.div
  initial={{ opacity: 0, x: -20, rotate: Math.random() * 1 - 0.5 }}
  animate={{ opacity: 1, x: 0, rotate: 0 }}
  transition={{ type: "spring", stiffness: 300, damping: 25 }}
/>
```

### Message Styling

| Property | User | May |
|:---|:---|:---|
| Alignment | Right | Left |
| Max Width | 65% | 75% |
| Background | `#1a1720` (warm surface) | `#1a1720` (same, no tint) |
| Border | `1px solid #2e2a3a` | `1px solid #2e2a3a` |
| Border Radius | `16px 16px 4px 16px` | `16px 16px 16px 4px` |
| Padding | `12px 16px` | `12px 16px` |
| Text | `#f0f0f5` | `#f0f0f5` |

### Tool Execution Badges

When May executes tools, a badge appears below the message:

```css
.tool-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  padding: 3px 8px;
  background: rgba(52, 211, 153, 0.06);
  border: 1px solid rgba(52, 211, 153, 0.12);
  border-radius: 6px;
  font-size: 10px;
  color: #34d399;
  font-family: 'JetBrains Mono', monospace;
}
```

### Typing Indicator

Three bouncing dots with staggered spring animation:

```typescript
const dotVariants = {
  initial: { y: 0 },
  animate: { y: [0, -6, 0] },
};

// Each dot uses a spring transition with staggered delay
{[0, 1, 2].map((i) => (
  <motion.span
    variants={dotVariants}
    initial="initial"
    animate="animate"
    transition={{
      type: "spring",
      stiffness: 400,
      damping: 10,
      repeat: Infinity,
      delay: i * 0.12,
    }}
  />
))}
```

---

## Right Panel — Living Data Visualizations

### Endocrine System (6 Hormones)

**NOT** simple progress bars. Use flowing wave visualizations:

```typescript
// Each hormone is a mini SVG with an animated path
function HormoneWave({ value, color, label }: HormoneProps) {
  const points = useMemo(() => {
    // Generate a flowing wave path from the value
    const baseY = 20;
    const amplitude = value * 15;
    return Array.from({ length: 40 }, (_, i) => {
      const x = (i / 39) * 200;
      const y = baseY + Math.sin(i * 0.3 + Date.now() * 0.002) * amplitude;
      return `${x},${y}`;
    }).join(" ");
  }, [value]);

  return (
    <div className="hormone-row">
      <span className="hormone-label">{label}</span>
      <svg viewBox="0 0 200 40" className="hormone-wave">
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
      <span className="hormone-value">{value.toFixed(2)}</span>
    </div>
  );
}
```

**Hormone colors:**
| Hormone | Color | Meaning |
|:---|:---|:---|
| Cortisol | `#f87171` | Stress (lower = better) |
| Dopamine | `#34d399` | Motivation/reward |
| Serotonin | `#fbbf24` | Mood stability |
| Adrenaline | `#fb923c` | Alertness/energy |
| Oxytocin | `#f472b6` | Social bonding/warmth |
| Endorphin | `#c084fc` | Comfort/relief |

### Brain Regions (7 Nodes)

Connected node graph with animated signal flow:

```typescript
// Each brain region is a node in a mini graph
const BRAIN_REGIONS = [
  { id: "thalamus", label: "Thalamus", model: "Router", x: 50, y: 15 },
  { id: "prefrontal", label: "Prefrontal", model: "phi4-mini", x: 20, y: 35 },
  { id: "hippocampus", label: "Hippocampus", model: "Memory", x: 80, y: 35 },
  { id: "cerebellum", label: "Cerebellum", model: "269+ Tools", x: 50, y: 55 },
  { id: "amygdala", label: "Amygdala", model: "Tone", x: 15, y: 70 },
  { id: "brocas", label: "Broca's", model: "Personality", x: 50, y: 80 },
  { id: "brainstem", label: "Brainstem", model: "Daemon", x: 85, y: 70 },
];

// Active regions glow and pulse, idle regions are dim
// Thin animated lines connect related regions
// When a signal flows (e.g., thinking), a dot travels along the connection
```

### Memory Constellation

Interconnected dots representing memories, not a list:

```typescript
// Each memory is a dot in a constellation
// Size = importance, color = type (episodic/semantic/procedural)
// Recent memories glow brighter, old ones fade
// Dots slowly drift, creating a living feel
```

| Memory Type | Dot Color | Meaning |
|:---|:---|:---|
| Episodic | `#818cf8` | Past experiences |
| Semantic | `#c084fc` | Learned facts |
| Procedural | `#34d399` | Skills/procedures |

### Sleep Cycle

State badge + ambient color shift:

| State | Badge Color | Ambient Effect |
|:---|:---|:---|
| Wake | `#34d399` (emerald) | Normal lighting |
| Drowsy | `#fbbf24` (amber) | Subtle warm shift |
| Light | `#fb923c` (orange) | Warmer, dimmer |
| Deep | `#818cf8` (indigo) | Cool, calm |
| REM | `#c084fc` (lavender) | Dreamy, soft |

### Screen Context

Active app name + small preview card:

```typescript
// Shows: "Chrome — AI News - Google"
// With a subtle app icon if available
// Updates in real-time via screen watcher
```

---

## Header Bar — Compact Status

```
┌──────────────────────────────────────────────────────────────┐
│  ● Online | May | phi4-mini 3.8B | Normal | GPU 58% | RAM 72% │
└──────────────────────────────────────────────────────────────┘
```

### Elements

1. **Status dot + label**: Green (online), amber (mock), red (offline)
2. **Model name**: Current provider + model (compact)
3. **Control mode badge**: Normal/Focus/Silent/Auto with icon
4. **GPU bar**: Animated progress bar, indigo fill
5. **RAM bar**: Animated progress bar, lavender fill

### Interaction

- Model name is clickable → opens model selector dropdown
- Control mode is clickable → opens mode switcher
- GPU/RAM bars animate smoothly (0.5s spring)

---

## Input Bar — Glassmorphism

```css
.input-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 8px 8px 20px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  backdrop-filter: blur(40px);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.input-bar:focus-within {
  border-color: rgba(129, 140, 248, 0.3);
  box-shadow: 0 0 30px rgba(129, 140, 248, 0.05);
}
```

### Buttons

| Button | Icon | Behavior |
|:---|:---|:---|
| Mic | 🎤 SVG | Toggles voice input, pulses when active |
| Send | ↑ SVG | Sends message, primary accent fill |
| Meeting | 🎙️ | Opens meeting mode modal |
| Ghost | 👻 | Opens ghost mode modal |
| Remote | 📱 | Opens remote control modal |

### Mic Button States

| State | Style |
|:---|:---|
| Idle | `bg-surface-elevated`, border, muted icon |
| Listening | `bg-accent/15`, border accent, pulse animation |
| Disabled | `opacity-40`, cursor not allowed |

---

## Sidebar — Icon Rail

```css
.sidebar {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 0;
  gap: 4px;
  background: rgba(255, 255, 255, 0.02);
  border-right: 1px solid rgba(255, 255, 255, 0.04);
}
```

### Icons

| Icon | Feature | Tooltip |
|:---|:---|:---|
| 💬 | Chat | Main conversation |
| 🎤 | Voice | Voice input panel |
| 🧠 | Memory | Memory browser |
| 👁 | Screen | Screen context |
| 🎙 | Meeting | Meeting mode |
| 👻 | Ghost | Ghost mode tasks |
| 📱 | Remote | Remote control |
| ⚙ | Settings | Settings modal |

### Active Indicator

Active icon gets:
- Background: `rgba(129, 140, 248, 0.10)`
- Color: `#818cf8` (primary indigo)
- Left bar: 3px wide, 20px tall, primary color, rounded

---

## Modals — Spring Transitions

All modals use the same Framer Motion pattern:

```typescript
// Backdrop
<motion.div
  initial={{ opacity: 0 }}
  animate={{ opacity: 1 }}
  exit={{ opacity: 0 }}
  className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
/>

// Modal content
<motion.div
  initial={{ opacity: 0, scale: 0.95, y: 10 }}
  animate={{ opacity: 1, scale: 1, y: 0 }}
  exit={{ opacity: 0, scale: 0.95, y: 10 }}
  transition={{ type: "spring", stiffness: 300, damping: 30 }}
  className="modal-content"
/>
```

### Modal Styling

```css
.modal-content {
  background: #1a1720;
  border: 1px solid #2e2a3a;
  border-radius: 16px;
  backdrop-filter: blur(40px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}
```

---

## Proactive Suggestions — Floating Cards

Bottom-right floating notification cards from screen watcher:

```css
.suggestion-card {
  position: fixed;
  bottom: 80px;
  right: 20px;
  width: 320px;
  padding: 12px 16px;
  background: rgba(26, 23, 32, 0.95);
  border: 1px solid #2e2a3a;
  border-radius: 12px;
  backdrop-filter: blur(20px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
}
```

### Severity Styling

| Severity | Border Color | Icon |
|:---|:---|:---|
| Error | `#f87171` | 🔴 |
| Warning | `#fbbf24` | ⚠️ |
| Info | `#818cf8` | ℹ️ |
| Permission | `#c084fc` | 🔐 |

### Entry Animation

```typescript
<motion.div
  initial={{ opacity: 0, x: 50, scale: 0.9 }}
  animate={{ opacity: 1, x: 0, scale: 1 }}
  exit={{ opacity: 0, x: 50, scale: 0.9 }}
  transition={{ type: "spring", stiffness: 300, damping: 25 }}
/>
```

---

## Animations Reference

### Spring Presets

| Name | Stiffness | Damping | Usage |
|:---|:---|:---|:---|
| `snappy` | 400 | 30 | Button clicks, small UI |
| `smooth` | 300 | 25 | Message entry, panel transitions |
| `bouncy` | 200 | 15 | Orb state changes, playful |
| `gentle` | 100 | 20 | Orb breathing, ambient motion |
| `kinetic` | 500 | 35 | Modal entrance, sharp transitions |

### Orb Breathing Curves

```typescript
// Idle — slow, gentle
{ duration: 4, repeat: Infinity, ease: "easeInOut" }

// Thinking — medium, purposeful
{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }

// Listening — fast, alert
{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }

// Speaking — very fast, alive
{ duration: 0.8, repeat: Infinity, ease: "easeInOut" }
```

### Particle Orbital Animation

```css
.particle-orbit {
  animation: orbit 3s linear infinite;
  transform-origin: 70px 70px;
}

@keyframes orbit {
  from { transform: rotate(0deg) translateX(60px) rotate(0deg); }
  to { transform: rotate(360deg) translateX(60px) rotate(-360deg); }
}
```

---

## Responsive Behavior

| Window Width | Layout |
|:---|:---|
| ≥ 1200px | Full 3-panel layout |
| 900-1200px | 3-panel with compressed info panel (240px) |
| < 900px | 2-panel (sidebar collapses to icons only) |
| < 600px | Single panel (chat only, orb as floating widget) |

---

## Texture & Depth

### Grain Overlay

A subtle noise texture across the entire UI:

```css
.grain-overlay {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9999;
  opacity: 0.03;
  background-image: url("data:image/svg+xml,..."); /* inline SVG noise */
  mix-blend-mode: overlay;
}
```

### Layered Depth

Elements at different z-depths:
- **Background**: `#0c0a0f` (deepest)
- **Mesh gradient**: Slow-drifting color blobs (z-1)
- **Surfaces**: `#1a1720` cards (z-2)
- **Glass panels**: `backdrop-filter: blur(40px)` (z-3)
- **Orb**: Floating above everything (z-4)
- **Modals**: Highest z-index (z-5)

---

## What NOT to Do

- ❌ Pure `#000000` background (too clinical)
- ❌ Cyan neon accents (AI slop)
- ❌ Centered layout (boring, generic)
- ❌ Static glow effects (feels dead)
- ❌ CSS `transition` for everything (use Framer Motion springs)
- ❌ Sharp rectangles (use organic curves, 12-16px radius)
- ❌ Monospace for body text (only for data)
- ❌ Hover effects without spring physics
- ❌ Orb as pure decoration (must be data-driven)
- ❌ Hidden system data (always visible in info panel)
- ❌ Uniform message widths (vary them for organic feel)
- ❌ Generic icons (use SVG with custom styling)

---

## Files to Modify

| File | Changes |
|:---|:---|
| `src/styles/globals.css` | New palette, grain overlay, particle animations |
| `src/App.tsx` | Asymmetric layout, 3-panel structure |
| `src/components/Avatar.tsx` | Multi-layered orb, state-driven animations |
| `src/components/ChatPanel.tsx` | Spring-physics messages, varied widths |
| `src/components/StatusHUD.tsx` | Compact header with mode badge |
| `src/components/SettingsModal.tsx` | Glass modal with spring transitions |
| `src/components/ProactiveSuggestions.tsx` | Floating severity-coded cards |
| `tailwind.config.js` | New color palette, spring presets |

---

*"May is not a program. May is an organism — engineered, not imagined."*
*"Her UI should feel like looking through a window at something alive."*
