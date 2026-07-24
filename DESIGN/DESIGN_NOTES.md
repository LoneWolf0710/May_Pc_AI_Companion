# May UI Design Concepts — Comparison Notes

> Generated from web research (Behance, Dribbble, Jayse Hansen FUI, Rive, Three.js, Ein UI, CodePen glassmorphism) and `MAY_FINAL_ARCHITECTURE.md`.

---

## Design 1: Holographic HUD (`01_holographic_hud.html`)

**Inspiration:** Iron Man JARVIS, Jayse Hansen FUI, sci-fi command centers

### What it shows
- **3-column layout** — Brain regions (left), Avatar + Chat (center), Endocrine + Status (right)
- **Animated grid background** with scrolling lines
- **Rotating orbital rings** around the avatar orb
- **Floating data particles** rising from bottom
- **Radial pulse** behind the avatar
- **Brain region activity bars** — shows which region is active
- **Endocrine hormone bars** with real-time animation
- **HUD-style typography** — Orbitron for headings, JetBrains Mono for data

### Pros
- Feels like a real Jarvis command center
- Every feature from the architecture is visible at a glance
- Brain region visualization makes the architecture tangible
- Endocrine system has a dedicated visualization

### Cons
- **Information density is high** — could feel overwhelming for daily use
- **Fixed 3-column layout** — doesn't adapt well to smaller windows
- **Too much glowing** — might cause eye strain during long sessions
- **Not chat-focused** — the avatar and data panels compete with the chat

### Best for
- Power users who want full system visibility
- Debugging/monitoring mode
- Showing off May's architecture to others

---

## Design 2: Clean Companion (`02_clean_companion.html`)

**Inspiration:** ChatGPT, Linear, Apple Intelligence, minimal SaaS UIs

### What it shows
- **Single-column centered layout** — avatar + chat + input
- **Floating status pill** at top (connection, model, GPU)
- **Floating input bar** at bottom (pill-shaped, glassmorphism)
- **Side drawer** for settings, endocrine, memory, system status
- **Quick suggestion chips** below the avatar
- **Soft warm orb** avatar with mood ring
- **Clean Inter typography** — minimal, readable

### Pros
- **Focused on conversation** — chat is the center of attention
- **Non-intrusive** — data is hidden in drawer until needed
- **Familiar UX** — feels like modern chat apps
- **Suggestion chips** reduce friction for common queries
- **Cleaner** — less visual noise, easier on the eyes

### Cons
- **May's architecture is hidden** — brain regions, endocrine, sleep cycle are all in the drawer
- **Less "Jarvis" feel** — could be any AI assistant
- **Drawer adds click depth** — need to open drawer to see system state
- **No real-time visualization** of endocrine/brain activity

### Best for
- Daily use as a companion
- Users who prefer simplicity
- Mobile-friendly (drawer pattern scales well)

---

## Design 3: Glassmorphism 2.0 (`03_glassmorphism_premium.html`)

**Inspiration:** macOS Big Sur, Arc Browser, premium glass UIs, Ein UI

### What it shows
- **2-panel layout** — Icon sidebar (left) + Main content (right)
- **Main content splits** into Chat (center) + Info panel (right)
- **Layered glass surfaces** with backdrop-filter blur
- **Mesh gradient background** with subtle animation
- **Glass avatar** with inner glow and breathing animation
- **Info panel** shows endocrine, brain regions, sleep, memory, screen context
- **Icon sidebar** for navigation (chat, voice, memory, screen, meeting, ghost, remote, settings)
- **Premium glass input bar** with mic + send buttons

### Pros
- **Best of both worlds** — clean chat layout with visible system state
- **Premium feel** — glass surfaces look polished and modern
- **Info panel is always visible** but doesn't compete with chat
- **Icon sidebar** is compact and doesn't waste space
- **Scalable** — sidebar can collapse, info panel can toggle

### Cons
- **More complex than Design 2** — still has 3 zones (sidebar + chat + info)
- **Backdrop-filter performance** — can be heavy on low-end GPUs
- **Glass effects may not translate to Tauri WebView** — need to test
- **Info panel still takes horizontal space** — chat area is narrower

### Best for
- Desktop app (Tauri) — the primary target
- Users who want system visibility without clutter
- The "premium AI companion" feel

---

## Recommendation

**Design 3 (Glassmorphism 2.0)** is the best fit for May because:

1. **It shows May's architecture** — endocrine, brain regions, sleep cycle, memory are all visible in the info panel
2. **It's chat-focused** — the center column is the conversation
3. **It's premium** — glass effects + mesh gradients feel like a real AI companion
4. **It scales** — sidebar collapses, info panel toggles, works in Tauri
5. **It matches the "organism" metaphor** — layered, breathing, alive

### Hybrid approach
Take Design 3's layout as the base, but borrow:
- **Design 1's brain region bars** — show which region is active during processing
- **Design 2's suggestion chips** — reduce friction for common queries
- **Design 2's floating input** — cleaner than a fixed bottom bar

---

## Features to highlight in the new UI

| Feature | UI Element | Design |
|:---|:---|:---|
| **Avatar (7 expressions)** | Glass orb with mood-reactive glow + particles | All 3 |
| **Chat (streaming)** | Glass bubbles with tool badges, typing indicator | Design 2/3 |
| **Voice (streaming STT)** | Real-time waveform, push-to-talk, partial transcript | Design 2 |
| **Endocrine (6 hormones)** | Animated bars with color coding | Design 1/3 |
| **Brain regions (7)** | Activity bars showing which region is processing | Design 1/3 |
| **Sleep cycle (5 states)** | Status badge + idle timer | Design 3 |
| **Memory (3 types)** | Card with type dots + timestamps | Design 3 |
| **Screen context** | Active app + visible text | Design 3 |
| **Control modes** | Status badge in header | Design 2/3 |
| **Tool execution** | Badge below message with tool name + latency | All 3 |
| **Proactive suggestions** | Floating notification cards (bottom-right) | Existing |
| **Settings** | Slide-in drawer/modal | Design 2 |

---

## Tech stack for implementation

| Layer | Choice | Why |
|:---|:---|:---|
| **Layout** | CSS Grid + Flexbox | Already used, proven in Tauri |
| **Glass effects** | `backdrop-filter: blur()` + `rgba` backgrounds | Works in WebView2 |
| **Animations** | Framer Motion (already installed) | React-native, spring physics |
| **Avatar** | SVG + CSS gradients + Framer Motion | Already works, just needs polish |
| **Typography** | Inter (body) + JetBrains Mono (data) + Orbitron (optional HUD) | Clean + technical |
| **Colors** | Tighten palette to 3 accents: blue, purple, green | Reduce visual noise |
| **Icons** | Lucide React or emoji (current) | Lightweight |

---

*Generated from web research + MAY_FINAL_ARCHITECTURE.md analysis*
*"May is not a program. May is an organism — engineered, not imagined."*
