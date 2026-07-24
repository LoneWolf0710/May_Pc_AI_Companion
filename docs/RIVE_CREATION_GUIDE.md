# 🎨 Creating May's Rive Avatar (.riv File)

> **Important:** `.riv` files can only be created using the **Rive Editor** (visual animation tool at [rive.app](https://rive.app)). There is no API, CLI, or SDK for generating `.riv` files programmatically. This guide provides the exact specifications to create the file in the Rive Editor.

---

## Quick Start

1. Go to [rive.app](https://rive.app) and create a free account
2. Click **"New File"** → **"Blank"**
3. Design May's avatar (a simple character or abstract face)
4. Set up the state machine with the inputs listed below
5. **Export** as `.riv` → place at `public/avatar.riv`
6. Restart the frontend dev server

---

## Required File Layout

| Property | Value |
|:---|:---|
| **Artboard name** | `MayAvatar` (or any name — but `MayAvatar` is clean) |
| **State Machine name** | `MayStateMachine` **(must match `STATE_MACHINE_NAME` in `RiveAvatar.tsx`)** |
| **File location** | `public/avatar.riv` (project root's `public/` directory) |

---

## Visual Design (Recommended)

Create a simple character face similar to the current SVG Avatar:

### Elements to Include

| Layer | Element | Description |
|:---|:---|:---|
| **Background** | Circle (144x144px) | Glass sphere with gradient fill (dark, like the SVG) |
| **Face** | Left eye + Right eye | Ellipses with pupil circles inside |
| **Face** | Mouth | Shape that can animate between neutral/smile/open/worried |
| **Face** | Eyebrows (left + right) | Lines that can rotate for expressions |
| **Decorations** | 2-3 orbital rings | Thin elliptical rings rotating at different angles |
| **Decorations** | Floating particles | Small circles that orbit around the face |

### Color Palette

| Element | Color | Hex |
|:---|:---|:---|
| Sphere background | Deep dark gradient | `#1a1a2e` to `#0D0D0D` |
| Eye whites | Off-white | `#E5E5E5` |
| Pupils | Light | `#FFFFFF` |
| Eyebrows | Off-white | `#E5E5E5` |
| Ring 1 | Cyan (faint) | `#818cf8` at 15% opacity |
| Ring 2 | Purple (faint) | `#c084fc` at 12% opacity |
| Particles (idle) | Cyan | `#818cf8` |
| Particles (thinking) | Purple | `#c084fc` |
| Particles (listening) | Green | `#34d399` |

---

## State Machine — Required Inputs

The **RiveAvatar** component maps May's runtime states to Rive state machine inputs. You MUST create these exact inputs in the state machine:

### Boolean Inputs (3 total)

| Input Name | True When | Visual Effect |
|:---|:---|:---|
| `isThinking` | May is processing/thinking | Half-closed eyes, small mouth, purple glow, neural pattern particles |
| `isListening` | May is listening to voice input | Wide eyes, green sonar rings, listening particles |
| `isSpeaking` | May is speaking (TTS active) | Animated mouth, vibrant glow, speaking particles |

### Number Inputs (2 total)

| Input Name | Range | Usage | Visual Effect |
|:---|:---|:---|:---|
| `mood` | `0` to `4` | Maps May's emotional state | `0`=neutral, `1`=happy, `2`=cool, `3`=concerned, `4`=surprised |
| `amplitude` | `0.0` to `1.0` | Voice amplitude for lip-sync | Drives mouth openness when speaking |

### How the Inputs Control the Avatar

Here's the expected behavior for each state + mood combination:

| State | Mood | isThinking | isListening | isSpeaking | mood | Expected Animation |
|:---|:---|:---|:---|:---|:---|:---|
| idle | neutral | false | false | false | 0 | Default breathing, orbital rings |
| idle | happy | false | false | false | 1 | Smile, brighter glow |
| idle | cool | false | false | false | 2 | Half-closed eyes, slight smile |
| idle | concerned | false | false | false | 3 | Worried mouth, furrowed brows |
| idle | surprised | false | false | false | 4 | Wide eyes, open mouth, sparkle |
| thinking | any | **true** | false | false | varies | Half-closed eyes, small-o mouth, neural dots |
| listening | any | false | **true** | false | varies | Wide eyes, green sonar rings |
| speaking | any | false | false | **true** | varies | Animated mouth (amplitude-driven) |

---

## Step-by-Step: Rive Editor Instructions

### 1. Create a New File

- Open [rive.app/editor](https://rive.app/editor/new)
- Choose **"Blank"** template
- Name the artboard: `MayAvatar`

### 2. Design the Face

1. **Add a Circle** (background sphere)
   - Select the **Ellipse** tool (or press `E`)
   - Draw a circle ~144x144px centered on the canvas
   - Fill: Radial gradient from `#2a2a4e` to `#0D0D0D`
   - Stroke: None

2. **Add left eye**
   - Draw a small horizontal ellipse (~8x6px)
   - Position: approximately (-10, -4) relative to center
   - Fill: `#E5E5E5`
   - Add a smaller circle inside for the pupil
   - Group them as "Left Eye"

3. **Add right eye**
   - Same as left eye
   - Position: approximately (10, -4) relative to center

4. **Add mouth**
   - Draw a path or ellipse for the mouth
   - Position: approximately (0, 8) relative to center
   - Create different mouth shapes as separate paths or use a single path with points you can animate

5. **Add eyebrows**
   - Two lines positioned above the eyes
   - Can be animated (rotated) to show expressions

6. **Add orbital rings**
   - 2-3 thin ellipses around the sphere
   - No fill, very thin stroke (0.5-1px) at low opacity
   - Rotate each at a different angle

### 3. Create the State Machine

1. In the bottom panel, switch to the **State Machine** tab
2. Click **"+"** to create a new state machine
3. Name it: `MayStateMachine`

4. **Add Inputs:**
   - Click **"Inputs"** → **"Boolean"**
   - Name: `isThinking`
   - Repeat for `isListening` and `isSpeaking`
   - Click **"Inputs"** → **"Number"** → Name: `mood`
   - Click **"Inputs"** → **"Number"** → Name: `amplitude`

5. **Create animation states for each May state:**
   - Create idle animation (default)
   - Create thinking animation
   - Create listening animation
   - Create speaking animation
   - For each, you can animate opacity, position, rotation, etc. of the face elements

6. **Wire transitions:**
   - Transition from idle → thinking when `isThinking == true`
   - Transition from idle → listening when `isListening == true`
   - Transition from idle → speaking when `isSpeaking == true`
   - All states transition back to idle when their boolean becomes false
   - Use instant transitions (0s duration) for responsive feel

### 4. Animate the Mood Number Input

- In each state, you can add blend shapes or opacity changes that respond to the `mood` value
- At mood = 0 (neutral): default face
- At mood = 1 (happy): raise mouth corners, brighten glow
- At mood = 2 (cool): half-close eyes, slight smirk
- At mood = 3 (concerned): furrow brows, worry mouth
- At mood = 4 (surprised): widen eyes, open mouth

### 5. Export the File

1. Click the **Export** button (top-right, or press `Ctrl+E`)
2. Ensure **"Rive"** format is selected
3. Click **Export**
4. Save the file as `avatar.riv`
5. Copy it to: `C:\AI\may\public\avatar.riv`

### 6. Verify

After placing the file, run the frontend:
```bash
cd C:\AI\may
npm run dev
```

Open `http://localhost:1420` in your browser. You should see May's new Rive avatar instead of the SVG fallback.

If the avatar fails to load, open the browser's developer console (F12) and check for:
- 404 errors on `/avatar.riv` — file not in the right place
- Rive runtime errors — check state machine input names match exactly
- CORS errors — not applicable for local files served by Vite

---

## Troubleshooting

### "The Rive component shows a blank canvas"
- Check the browser console for errors
- Verify the state machine name is exactly `MayStateMachine`
- Verify all 5 inputs exist with the exact names listed above
- Make sure the artboard has at least one visible shape

### "The avatar doesn't respond to state changes"
- The `useRive` hook in `RiveAvatar.tsx` sets inputs by name
- Open the browser console and check if you see: `Rive state machine inputs may not exist`
- This means the input names in your .riv don't match what the code expects

### "I want to use a different state machine name"
- Update `STATE_MACHINE_NAME` constant in `src/components/RiveAvatar.tsx`

---

## Alternative: Hire a Designer

If you don't want to create the animation yourself:
1. Export the SVG design from the current `Avatar.tsx` component
2. Hire a Rive designer on [rive.app/community](https://rive.app/community) or [Fiverr](https://fiverr.com)
3. Give them this spec sheet — they'll know exactly what to build

---

## Resources

- **Rive Editor**: [rive.app/editor](https://rive.app/editor)
- **Rive Tutorials**: [rive.app/learn](https://rive.app/learn)
- **Rive State Machines**: [rive.app/docs/state-machines](https://rive.app/docs/state-machines)
- **Rive File Format Docs**: [rive.app/docs/runtimes/advanced-topic/format](https://rive.app/docs/runtimes/advanced-topic/format)
- **Our RiveAvatar Component**: `src/components/RiveAvatar.tsx`
- **Our SVG Avatar (reference)**: `src/components/Avatar.tsx`
