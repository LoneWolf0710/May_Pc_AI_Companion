# 🚀 May AI Companion — Next 50 Features Roadmap

> **Goal:** Make May the most capable, proactive, and personality-rich desktop AI companion ever built.
> Organized by category with priority (P0=Critical, P1=High, P2=Medium, P3=Nice-to-have),
> effort (S/M/L/XL), and impact (★★★★★ = transformative).

---

## 🎙️ Category 1: Voice & Interaction (Features 1–8)

### Feature 1: Continuous Conversation Mode ★★★★★
**Priority:** P0 | **Effort:** M | **Session:** 26
May stays "awake" after responding — no need to click the mic button each time. After she finishes speaking, she automatically listens for your next command for a configurable timeout (5–30s). The avatar enters a "listening" state with a subtle pulse.
- **Backend:** Add `POST /voice/continuous` endpoint with timeout config
- **Frontend:** `useContinuousVoice` hook — auto-restart mic after TTS completes, countdown indicator
- **Config:** `~/.may/voice.json` → `continuous_timeout`, `continuous_enabled`

### Feature 2: Multi-Language Voice Support ★★★★☆
**Priority:** P1 | **Effort:** M | **Session:** 27
May speaks and understands multiple languages. The STT model auto-detects language, and TTS can be set to any supported language. May switches personality language to match the user.
- **Backend:** Remove hardcoded `language="en"`, add language detection caching to prevent 60s delays
- **Frontend:** Language selector in Settings, flag emojis in status
- **Integration:** faster-whisper supports 99 languages natively

### Feature 3: Voice Cloning (Custom TTS Voice) ★★★★★
**Priority:** P1 | **Effort:** L | **Session:** 28
May can speak in a custom voice cloned from a short audio sample. User records 30s of any voice, May adopts it for all TTS output.
- **Backend:** Integrate XTTS v2 (Coqui) or Bark for local voice cloning
- **Storage:** `~/.may/voice_clone/` — model weights + speaker embedding
- **GPU:** RTX 4050 can run XTTS v2 in ~2s per sentence

### Feature 4: Emotion-Responsive Voice ★★★★☆
**Priority:** P2 | **Effort:** L | **Session:** 29
May adjusts her voice tone based on context — faster/higher when excited, slower/softer when concerned. Uses SSML or prosody control in TTS.
- **Backend:** Map mood states to TTS parameters (rate, pitch, volume)
- **Personality:** Excited = "I found something cool~", Concerned = "Hmm, that file might be important..."
- **Integration:** Works with browser TTS and custom voice clone

### Feature 5: Voice Activity Detection (VAD) ★★★★☆
**Priority:** P1 | **Effort:** S | **Session:** 26
Instead of fixed 5-second recording, May detects when the user stops speaking and immediately processes. Uses Silero VAD (runs locally, <1ms per frame).
- **Backend:** Add `silero-vad` dependency, process audio chunks in real-time
- **Frontend:** Streaming VAD — mic stays open until silence detected
- **Benefit:** Faster response, no wasted recording time, more natural conversation

### Feature 6: Voice Commands (Hands-Free Activation) ★★★★★
**Priority:** P0 | **Effort:** M | **Session:** 26
Replace the broken openwakeword system with a working wake word detector. Uses Silero VAD + keyword spotting to detect "Hey May" from continuous audio stream.
- **Backend:** Silero VAD for speech detection + a lightweight keyword spotter (MYQ or custom)
- **Frontend:** Background audio processing, wake word indicator in StatusHUD
- **Fallback:** "Hey May" phrase + fallback to keyboard shortcut

### Feature 7: Meeting Transcription & Summaries ★★★★☆
**Priority:** P1 | **Effort:** M | **Session:** 30
Enhance Meeting Mode with real-time transcription, speaker diarization, and AI-generated summaries. Exports to Markdown, Notion, or email.
- **Backend:** Use faster-whisper `--output_format srt` for timestamps, LLM for summarization
- **Export:** `POST /meeting/export` — Markdown, PDF, email, clipboard
- **Storage:** `~/may/meetings/` with structured JSON + Markdown

### Feature 8: Whisper Chat (Type-to-Talk) ★★★☆☆
**Priority:** P2 | **Effort:** S | **Session:** 31
When voice input isn't available (noisy environment), May can "think" silently and output a voice response from typed input. Type the question, May responds by voice.
- **Backend:** No changes needed — existing TTS pipeline handles this
- **Frontend:** Toggle "voice response" mode in ChatPanel
- **Use Case:** Late night, shared space, library

---

## 🧠 Category 2: Intelligence & Proactive Features (Features 9–16)

### Feature 9: Contextual Memory Retrieval ★★★★★
**Priority:** P0 | **Effort:** M | **Session:** 26
May proactively retrieves relevant memories during conversations. When you mention a project, she recalls previous discussions about it. Uses LanceDB vector search + fact store joins.
- **Backend:** Before each LLM call, search memory for top-5 relevant facts/episodes, inject into system prompt
- **Performance:** <50ms vector search with existing LanceDB setup
- **Example:** "What did I say about the API?" → May searches memory and answers

### Feature 10: Habit Tracking & Insights ★★★★☆
**Priority:** P1 | **Effort:** L | **Session:** 27
May tracks your daily habits (coding hours, app usage, break patterns) and provides weekly insights. No manual input needed — uses shadow learner data.
- **Backend:** New `intelligence/habit_tracker.py` — aggregates shadow_learner events into daily/weekly patterns
- **Storage:** SQLite table `habits` with date, category, duration, metadata
- **Display:** Weekly habit summary in morning briefing

### Feature 11: Smart Notifications ★★★★★
**Priority:** P0 | **Effort:** M | **Session:** 26
May filters and prioritizes notifications intelligently. Urgent messages (emails from boss, security alerts) come through immediately. Low-priority (social media, newsletters) batched into hourly digests.
- **Backend:** New `intelligence/notification_filter.py` — ML-free rule-based priority scoring
- **Rules:** Sender importance, keyword urgency, time-of-day, user response patterns
- **Integration:** Works with email monitoring + Windows notification APIs

### Feature 12: Automated Workflows (No-Code) ★★★★★
**Priority:** P0 | **Effort:** XL | **Session:** 28
May can create and execute multi-step workflows from natural language. "Every morning at 8am, check my email, summarize unread messages, check weather, and send me a briefing" → May creates and runs this automation.
- **Backend:** New `intelligence/workflow_engine.py` — DAG-based task execution
- **Storage:** `~/.may/workflows/` — JSON workflow definitions
- **Triggers:** Time-based, event-based, voice command
- **Editor:** Visual workflow builder in frontend (Phase 2)

### Feature 13: Predictive Suggestions ★★★★☆
**Priority:** P1 | **Effort:** M | **Session:** 28
May suggests actions before you ask. Based on time, context, and habits:
- Monday 9am → "Ready for standup? Want me to open Slack?"
- After 4 hours of coding → "Time for a break? I can set a 5-min timer"
- Before meeting → "Your meeting starts in 10 min. Want me to open the notes?"
- **Backend:** `intelligence/predictive_engine.py` — time-based + context-based triggers
- **Integration:** Uses shadow_learner patterns + calendar + clock

### Feature 14: Code Assistant ★★★★★
**Priority:** P0 | **Effort:** L | **Session:** 27
May can read, write, and analyze code files. She understands programming languages and can:
- Explain what a function does
- Find bugs and suggest fixes
- Write unit tests
- Refactor code
- Generate boilerplate
- **Backend:** Leverage existing `read_file`/`write_file` tools + LLM code understanding
- **Frontend:** Code syntax highlighting in chat, diff view for suggested changes
- **Integration:** VS Code extension (future) for inline assistance

### Feature 15: Screen Understanding ★★★★★
**Priority:** P1 | **Effort:** L | **Session:** 29
May takes screenshots and understands what's on screen. She can:
- Read error messages from dialogs and suggest fixes
- Navigate complex UIs by describing what she sees
- Help with form filling
- Debug visual issues
- **Backend:** Use `core/L9_browser.py` Playwright for structured screenshots, or native screenshot
- **Integration:** Vision-capable LLMs (GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro)
- **Privacy:** Sensitive content blurring option

### Feature 16: Learning Mode ★★★★☆
**Priority:** P2 | **Effort:** L | **Session:** 30
May can learn new skills from user demonstrations. User shows May how to do something once, she remembers and can repeat it. Uses shadow learner + memory system.
- **Backend:** Record sequence of actions during "teaching" mode, store as replayable workflow
- **Storage:** `~/.may/learned_skills/` — action sequences with context
- **Trigger:** "May, learn how I organize my downloads folder" → records the process

---

## ⚡ Category 3: System & Productivity (Features 17–24)

### Feature 17: Clipboard History Manager ★★★★☆
**Priority:** P1 | **Effort:** S | **Session:** 26
May maintains a searchable clipboard history. Every copied item is stored with timestamp, source app, and optional tags. Users can search, pin, and recall past clips.
- **Backend:** New `intelligence/clipboard_monitor.py` — polls clipboard every 500ms, stores in SQLite
- **Tools:** `clipboard_history`, `clipboard_search`, `clipboard_pin`
- **Privacy:** Auto-delete after configurable retention (default 7 days)

### Feature 18: File Organization Assistant ★★★★☆
**Priority:** P1 | **Effort:** M | **Session:** 27
May can organize files automatically. "Organize my Downloads folder" → she categorizes files by type, date, or content and moves them to appropriate folders.
- **Tools:** Enhanced `batch_move` with AI categorization
- **Rules:** User-configurable categorization rules, or AI-suggested
- **Safety:** Dry-run mode showing what would be moved before executing

### Feature 19: System Performance Monitor ★★★★☆
**Priority:** P1 | **Effort:** M | **Session:** 28
May monitors system performance in real-time and alerts on issues. Tracks CPU/RAM/GPU/temperature history, disk space trends, and network usage.
- **Backend:** `intelligence/performance_monitor.py` — continuous psutil monitoring, SQLite time-series
- **Alerts:** High temperature (>85°C), low disk (<10GB), memory pressure (>90%)
- **Display:** Real-time graph in StatusHUD, weekly performance report

### Feature 20: Application Launcher & Switcher ★★★★☆
**Priority:** P2 | **Effort:** S | **Session:** 26
May becomes the fastest way to launch anything. Type or say partial app name, she fuzzy-matches and opens it. Remembers your most-used apps and suggests them.
- **Backend:** Enhanced `_KNOWN_APPS` with usage frequency tracking
- **Frontend:** Spotlight-like launcher popup (Cmd+K / Ctrl+K)
- **Features:** Fuzzy matching, recent apps, pinned favorites, keyboard navigation

### Feature 21: Scheduled Commands ★★★★★
**Priority:** P0 | **Effort:** M | **Session:** 27
May can schedule any command to run at specific times. "Run my backup script every day at 2am" or "Remind me to commit every 4 hours during work days."
- **Backend:** New `POST /scheduler/create` endpoint — uses Windows Task Scheduler via core/L7
- **Tools:** `schedule_command`, `list_schedules`, `cancel_schedule`
- **Persistence:** `~/.may/schedules.json`

### Feature 22: Smart Backup & Sync ★★★★☆
**Priority:** P1 | **Effort:** L | **Session:** 29
May can back up important folders to a local or cloud destination on a schedule. Tracks file changes and only backs up modified files.
- **Backend:** `intelligence/backup_manager.py` — incremental backup with file hashing
- **Destinations:** Local folder, network share, OneDrive, Google Drive (via API)
- **Config:** `~/.may/backup.json` — source dirs, destination, schedule, retention

### Feature 23: Browser Automation ★★★★★
**Priority:** P0 | **Effort:** M | **Session:** 28
May can automate browser tasks via voice. "Fill out my time sheet" → opens browser, navigates to the page, fills in fields. Uses Playwright (already in L9).
- **Backend:** Enhanced L9 browser layer with high-level actions (fill_form, click_element, wait_for)
- **Tools:** `browser_navigate`, `browser_fill`, `browser_click`, `browser_screenshot`
- **Safety:** Confirmation required for financial/irreversible actions

### Feature 24: Window Layout Presets ★★★☆☆
**Priority:** P2 | **Effort:** S | **Session:** 27
May can save and restore window layouts. "Save this as my coding layout" → remembers window positions and sizes. "Switch to my coding layout" → restores them.
- **Tools:** `save_window_layout`, `restore_window_layout`, `list_layouts`
- **Storage:** `~/.may/layouts.json` — window titles, positions, sizes
- **Enhancement:** Auto-switch layouts based on time of day or active project

---

## 🔐 Category 4: Security & Privacy (Features 25–30)

### Feature 25: Password Manager Integration ★★★★★
**Priority:** P0 | **Effort:** L | **Session:** 29
May integrates with popular password managers (Bitwarden, 1Password, KeePass) to auto-fill credentials. "Log in to GitHub" → May finds the credential and fills it.
- **Backend:** Integration with Bitwarden CLI or KeePass CLI
- **Security:** Credentials never stored in May's memory, transient access only
- **Privacy:** All processing local, no cloud password sync

### Feature 26: File Encryption ★★★★☆
**Priority:** P1 | **Effort:** M | **Session:** 30
May can encrypt/decrypt files using AES-256. "Encrypt my tax documents" → password-protected ZIP or age encryption.
- **Tools:** `encrypt_file`, `decrypt_file`, `secure_delete`
- **Backend:** Python `cryptography` library, password-derived key
- **Secure Delete:** Multi-pass overwrite before deletion

### Feature 27: Security Audit Dashboard ★★★★☆
**Priority:** P1 | **Effort:** L | **Session:** 31
May monitors system security: checks for suspicious processes, monitors network connections, alerts on unusual activity.
- **Backend:** `intelligence/security_monitor.py` — process monitoring, network connection tracking
- **Alerts:** New unknown processes, unusual network traffic, login attempts
- **Dashboard:** Security score in StatusHUD, weekly security report

### Feature 28: Privacy Mode Enhanced ★★★★☆
**Priority:** P2 | **Effort:** M | **Session:** 30
Enhanced privacy controls: app-level blocking (no monitoring of specific apps), browser history exclusion, per-folder memory exclusion.
- **Backend:** Configurable exclusion lists in privacy_mode.py
- **Config:** `~/.may/privacy.json` — excluded apps, folders, domains
- **Auto-mode:** Activates privacy mode automatically in certain locations (home vs work)

### Feature 29: Auto-Lock & Presence Detection ★★★★☆
**Priority:** P1 | **Effort:** M | **Session:** 28
May detects when the user leaves the computer (keyboard/mouse idle + no face detection) and optionally locks the screen or activates privacy mode.
- **Backend:** Idle detection from mouse/keyboard events, optional camera-based presence
- **Config:** Idle timeout, lock action, privacy mode toggle
- **Integration:** Core L8 system control for lock, privacy_mode for data protection

### Feature 30: Audit Log Viewer ★★★☆☆
**Priority:** P2 | **Effort:** S | **Session:** 31
Enhanced audit logging: every tool execution, file access, and system command is logged with timestamp, parameters, and result. Viewable in the frontend.
- **Backend:** SQLite audit log table, new `GET /audit` endpoint
- **Frontend:** Searchable, filterable log viewer in Settings
- **Retention:** Configurable (default 30 days)

---

## 🎨 Category 5: Frontend & UX (Features 31–38)

### Feature 31: Command Palette (Ctrl+K) ★★★★★
**Priority:** P0 | **Effort:** M | **Session:** 26
A Spotlight/VS Code-style command palette for quick access to everything. Type to search commands, apps, files, settings, and recent conversations.
- **Frontend:** New `CommandPalette.tsx` — modal with search, categories, keyboard navigation
- **Commands:** All May actions, app launcher, settings, recent chats
- **Shortcut:** Ctrl+K / Cmd+K to open, Escape to close

### Feature 32: Dark/Light Theme Toggle ★★★☆☆
**Priority:** P2 | **Effort:** S | **Session:** 32
Add a light theme option. May remembers the user's preference. Surfaced Light variant of the existing Surfaced Dark palette.
- **Frontend:** Theme context provider, CSS variables, toggle in Settings
- **Colors:** Light palette based on existing Surfaced Dark (inverted, still with cyan accent)
- **Persistence:** `localStorage` + backend config

### Feature 33: Conversation Branching ★★★★☆
**Priority:** P1 | **Effort:** M | **Session:** 31
May can branch conversations — like git branches for chat. "Let me try a different approach" → creates a new branch from the current point. Switch between branches to explore different paths.
- **Frontend:** Visual branch tree in chat history, branch selector dropdown
- **Storage:** Conversations stored as DAG in SQLite, not linear list
- **Merge:** "Go back to the other approach" → switches branch

### Feature 34: Rich Media in Chat ★★★★☆
**Priority:** P1 | **Effort:** M | **Session:** 30
May can display images, charts, code blocks, and interactive elements in chat. Weather data shows as a chart, code has syntax highlighting, file previews show thumbnails.
- **Frontend:** Markdown renderer with custom components (charts, code, images, tables)
- **Backend:** Return structured data (not just text) from tool results
- **Libraries:** recharts for charts, highlight.js for code, react-markdown for rich text

### Feature 35: Floating Widget Mode ★★★★☆
**Priority:** P2 | **Effort:** M | **Session:** 32
May can be minimized to a tiny floating widget (like the existing FloatingOrb) that stays on top. Click to expand to full chat, drag to reposition.
- **Frontend:** Draggable FloatingOrb with expand/collapse animation
- **Config:** Opacity, size, position persistence, always-on-top toggle
- **Tauri:** `setAlwaysOnTop()` API for window management

### Feature 36: Quick Action Bar ★★★★☆
**Priority:** P1 | **Effort:** S | **Session:** 27
A persistent toolbar with one-click access to common actions: volume, brightness, mute, screenshot, timer, quick note.
- **Frontend:** `QuickActionBar.tsx` — horizontal bar below chat, scrollable on mobile
- **Config:** Customizable actions, order, visibility
- **Integration:** Maps to existing tool calls

### Feature 37: Onboarding Wizard ★★★☆☆
**Priority:** P2 | **Effort:** M | **Session:** 33
First-time setup wizard that walks users through configuration: API keys, voice settings, personality preferences, privacy settings, tool permissions.
- **Frontend:** Multi-step wizard component with progress indicator
- **Steps:** Welcome → API Keys → Voice Setup → Personality → Privacy → Done
- **Skip:** Can skip any step, complete later in Settings

### Feature 38: Notification Center ★★★★☆
**Priority:** P1 | **Effort:** M | **Session:** 31
A notification center in the frontend that aggregates all May's alerts: wellness reminders, email summaries, security alerts, calendar events. Swipe to dismiss, click to act.
- **Frontend:** `NotificationCenter.tsx` — slide-out panel with notification cards
- **Backend:** New `GET /notifications` endpoint — returns unread notifications
- **Actions:** Each notification has action buttons (dismiss, snooze, act)

---

## 🔌 Category 6: Integrations & Plugins (Features 39–44)

### Feature 39: Notion Integration ★★★★★
**Priority:** P0 | **Effort:** M | **Session:** 30
May reads and writes to Notion databases. "What's on my project board?" → queries Notion. "Add this to my task list" → creates a page.
- **Backend:** New `integrations/notion.py` — Notion API client
- **Tools:** `notion_query`, `notion_create_page`, `notion_update_page`, `notion_search`
- **Config:** `~/.may/notion.json` — API key, workspace, default database

### Feature 40: GitHub Integration ★★★★★
**Priority:** P0 | **Effort:** M | **Session:** 29
May interacts with GitHub: creates issues, reviews PRs, checks build status, manages repositories.
- **Backend:** New `integrations/github.py` — GitHub REST/GraphQL API client
- **Tools:** `github_create_issue`, `github_list_prs`, `github_check_status`, `github_review_pr`
- **Auth:** Personal access token via Settings

### Feature 41: Calendar Sync (Google/Outlook) ★★★★☆
**Priority:** P1 | **Effort:** L | **Session:** 30
May syncs with Google Calendar or Outlook. Reads events, creates meetings, sends invites. Real-time sync via CalDAV or API.
- **Backend:** Enhanced `calendar_reader.py` — add CalDAV support + OAuth2 for Google/Outlook
- **Tools:** `create_calendar_event`, `delete_event`, `list_todays_events`
- **Sync:** Bidirectional — May-created events appear in the calendar app

### Feature 42: Spotify Enhanced ★★★★☆
**Priority:** P1 | **Effort:** M | **Session:** 31
Beyond the basic plugin: queue management, playlist creation, music recommendations based on mood/time, lyrics display, volume normalization.
- **Backend:** Enhanced `plugins/spotify.py` — playlist, queue, recommendations APIs
- **Tools:** `spotify_queue`, `spotify_create_playlist`, `spotify_recommend`, `spotify_lyrics`
- **Mood:** Auto-select playlist based on time and activity

### Feature 43: Slack/Discord Bot ★★★★☆
**Priority:** P2 | **Effort:** L | **Session:** 33
May acts as a bot in Slack or Discord channels. Users can @mention May for help, she responds in-channel. Great for team use.
- **Backend:** New `integrations/slack_bot.py` / `discord_bot.py` — bot frameworks
- **Features:** @May for help, summarize channel, create reminders, search messages
- **Privacy:** Configurable which channels May can access

### Feature 44: Home Assistant Deep Integration ★★★★★
**Priority:** P1 | **Effort:** M | **Session:** 32
Beyond basic toggle: May creates automations, monitors device states, provides energy reports. "Dim all lights to 30% and play jazz" → scene creation.
- **Backend:** Enhanced `smart_home.py` — scene creation, automation rules, energy monitoring
- **Tools:** `ha_create_scene`, `ha_create_automation`, `ha_energy_report`, `ha_device_history`
- **Config:** Enhanced `~/.may/smart_home.json`

---

## 📊 Category 7: Data & Analytics (Features 45–48)

### Feature 45: Time Tracking Dashboard ★★★★★
**Priority:** P1 | **Effort:** M | **Session:** 28
May automatically tracks how you spend time on your computer. Categorizes by app/activity, generates daily/weekly reports with visualizations.
- **Backend:** `intelligence/time_tracker.py` — foreground window tracking via psutil, app categorization
- **Storage:** SQLite time_series table — timestamp, app, category, duration
- **Display:** Weekly pie chart, daily timeline, productive vs. leisure breakdown

### Feature 46: Expense Tracker ★★★★☆
**Priority:** P2 | **Effort:** M | **Session:** 32
May tracks expenses from receipts (photo → text → structured data) or voice input. Generates monthly reports and budget alerts.
- **Backend:** `integrations/expense_tracker.py` — OCR for receipts, categorization
- **Tools:** `add_expense`, `list_expenses`, `monthly_report`, `budget_alert`
- **Storage:** `~/.may/expenses.json` — SQLite with categories

### Feature 47: Knowledge Base ★★★★☆
**Priority:** P1 | **Effort:** L | **Session:** 31
May builds a personal knowledge base from your conversations, documents, and bookmarks. Searchable, taggable, auto-categorized.
- **Backend:** Enhanced LanceDB usage — index documents, bookmarks, conversation snippets
- **Tools:** `kb_search`, `kb_add`, `kb_tag`, `kb_export`
- **Storage:** LanceDB collections for different content types

### Feature 48: Analytics Dashboard ★★★★☆
**Priority:** P2 | **Effort:** L | **Session:** 33
A local web dashboard showing May's metrics: total interactions, tool usage breakdown, uptime, error rates, memory usage, response times.
- **Backend:** New `GET /analytics` endpoint — aggregated metrics
- **Frontend:** Optional web dashboard at `http://localhost:8080/analytics`
- **Charts:** Usage over time, tool frequency, error trends, response latency

---

## 🎮 Category 8: Fun & Personality (Features 49–50)

### Feature 49: Personality Engine ★★★★★
**Priority:** P0 | **Effort:** M | **Session:** 27
May's personality becomes dynamic and evolving. She remembers your preferences, adjusts her tone based on context, develops inside jokes, and celebrates milestones together.
- **Backend:** `intelligence/personality_engine.py` — mood tracking, relationship scoring, joke/memory bank
- **Moods:** Happy, neutral, concerned, excited, tired — affects responses and avatar
- **Memory:** Remembers user preferences (favorite apps, habits, pet peeves) and references them naturally
- **Milestones:** "We've been working together for 30 days! 🎉"

### Feature 50: Easter Eggs & Hidden Features ★★★☆☆
**Priority:** P3 | **Effort:** S | **Session:** 34
May has hidden features and personality quirks that reward exploration:
- "May, sing me a song" → generates a song about the user
- "May, tell me a joke" → context-aware humor
- "May, what's your favorite color?" → personality-driven response
- "May, play a game" → text adventure or trivia
- Secret commands that unlock special avatar animations
- Anniversary acknowledgments and milestone celebrations
- **Backend:** Easter egg detection in message processing, special response generators
- **Frontend:** Hidden avatar animations (rainbow, disco, etc.)

---

## 📋 Implementation Priority Matrix

### Tier 1 — Foundation (Session 26–27)
Features that unlock everything else:
1. **#1 Continuous Conversation** — makes May feel alive
2. **#5 VAD** — enables natural voice interaction
3. **#6 Voice Commands** — hands-free activation
4. **#9 Contextual Memory** — makes May truly intelligent
5. **#17 Clipboard History** — daily productivity win
6. **#31 Command Palette** — instant access to everything
7. **#49 Personality Engine** — makes May feel human
8. **#20 App Launcher** — replaces Windows Start menu

### Tier 2 — Power User (Session 28–29)
Features that make May indispensable:
9. **#11 Smart Notifications** — signal over noise
10. **#12 Automated Workflows** — the killer feature
11. **#14 Code Assistant** — for developers
12. **#19 System Monitor** — proactive care
13. **#21 Scheduled Commands** — set-and-forget
14. **#23 Browser Automation** — voice-controlled web
15. **#39 Notion Integration** — project management
16. **#40 GitHub Integration** — developer workflow
17. **#45 Time Tracking** — productivity insights

### Tier 3 — Advanced (Session 30–32)
Features for power users:
18. **#3 Voice Cloning** — personalized experience
19. **#10 Habit Tracking** — behavioral insights
20. **#13 Predictive Suggestions** — proactive May
21. **#15 Screen Understanding** — visual intelligence
22. **#18 File Organization** — desktop cleanup
23. **#25 Password Manager** — security integration
24. **#33 Conversation Branching** — non-linear chat
25. **#41 Calendar Sync** — full calendar integration
26. **#42 Spotify Enhanced** — music intelligence
27. **#47 Knowledge Base** — personal wiki

### Tier 4 — Polish (Session 33–34)
Features for completeness:
28. **#34 Rich Media** — visual chat
29. **#35 Floating Widget** — desktop integration
30. **#37 Onboarding** — new user experience
31. **#43 Slack/Discord Bot** — team collaboration
32. **#44 Home Assistant Deep** — smart home mastery
33. **#46 Expense Tracker** — financial awareness
34. **#48 Analytics Dashboard** — self-monitoring
35. **#50 Easter Eggs** — personality and delight

---

## 🔧 Technical Dependencies

| Feature | New Dependencies | Existing Integrations |
|:---|:---|:---|
| #1 Continuous Voice | — | useMicMonitor, STT |
| #3 Voice Cloning | XTTS v2 (coqui-tts) | TTS pipeline |
| #5 VAD | silero-vad | Audio pipeline |
| #9 Memory Retrieval | — | LanceDB, fact_store |
| #12 Workflows | — | shadow_learner, ghost_mode |
| #14 Code Assistant | — | read_file, write_file |
| #15 Screen Understanding | Vision LLM API | Screenshot tools |
| #23 Browser Automation | — | Playwright (L9) |
| #25 Password Manager | bitwarden-cli or pykeepass | None |
| #39 Notion | notion-client | None |
| #40 GitHub | PyGithub | None |
| #41 Calendar Sync | caldav, google-api-python | calendar_reader |
| #44 Home Assistant | — | smart_home.py |

---

## 🎯 Success Metrics

After implementing these 50 features, May should:

1. **Response time:** <2s for voice, <1s for text
2. **Proactiveness:** 5+ unsolicited helpful suggestions per day
3. **Tool accuracy:** >95% successful tool execution
4. **Memory recall:** Relevant memories surfaced in >80% of relevant conversations
5. **User satisfaction:** "May is indispensable" — can't imagine using the PC without her
6. **Uptime:** 99.9% availability during waking hours
7. **Automation:** 10+ saved workflows running daily/weekly
8. **Voice quality:** Natural, emotion-aware speech that users enjoy listening to

---

*Created: June 30, 2026 — 50 features across 8 categories, prioritized P0–P3, with effort estimates and technical dependencies.*
