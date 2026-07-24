# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for May AI Backend sidecar.

Build with:
    cd backend && pyinstaller may_backend.spec

Output: backend/dist/may-backend/may-backend.exe
"""

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ── Paths ───────────────────────────────────────────────────────────────
# When running: cd may && python -m PyInstaller backend/may_backend.spec
# SPEC = 'backend/may_backend.spec'
# os.path.dirname(SPEC) = 'backend', so we go up one level
MAY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))
BACKEND_DIR = os.path.join(MAY_ROOT, 'backend')
PROJECT_ROOT = MAY_ROOT

# ── Hidden imports (packages that PyInstaller can't auto-detect) ────────
HIDDEN_IMPORTS = [
    # FastAPI ecosystem
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'fastapi.middleware',
    'fastapi.middleware.cors',
    'fastapi.responses',
    'fastapi.staticfiles',
    'pydantic',
    'starlette',
    'starlette.routing',
    'starlette.responses',
    # HTTP client
    'httpx',
    'httpcore',
    'h11',
    # Voice / ML
    'faster_whisper',
    'faster_whisper.transcribe',
    'sentence_transformers',
    'torch',
    'numpy',
    'lancedb',
    'pyarrow',
    # System control
    'psutil',
    'pycaw',
    'comtypes',
    'comtypes.client',
    'screen_brightness_control',
    'pywinauto',
    'pywinauto.application',
    'pywinauto.keyboard',
    'pywinauto.mouse',
    # Windows
    'win32com',
    'win32com.client',
    'pythoncom',
    'wmi',
    'winshell',
    'send2trash',
    # Browser automation
    'playwright',
    'playwright.async_api',
    # RSS / feed parsing
    'feedparser',
    # Image processing
    'PIL',
    'PIL.Image',
    'imagehash',
    # QR code
    'qrcode',
    'qrcode.image.pil',
    # Voice biometrics
    'resemblyzer',
    # Process management
    'watchdog',
    'watchdog.observers',
    # Archive support
    'py7zr',
    # UI Automation
    'uiautomation',
    # Background tasks
    'aiofiles',
    # JSON Web Tokens (if used)
    'jwt',
    # setuptools vendored deps (needed even though setuptools is excluded)
    'jaraco',
    'jaraco.text',
    'jaraco.functools',
    'jaraco.context',
    'pkg_resources',
    # Our own packages
    'llm',
    'llm.ollama_client',
    'llm.providers',
    'llm.jarvis',
    'llm.core_bridge',
    'llm.tools',
    'llm.tool_tiering',
    'llm.resilience',
    'llm.ollama_config',
    'llm.llama_server',
    'memory',
    'memory.fact_store',
    'memory.vector_store',
    'memory.skill_store',
    'memory.memory_injector',
    'system',
    'system.secure_storage',
    'system.audit_log',
    'system.risk_classifier',
    'system.immune_system',
    'system.behavioral_profile',
    'system.notifications',
    'system.owasp_mapping',
    'system.fallback',
    'system.tracing',
    'voice',
    'voice.stt',
    'voice.vad',
    'voice.biometrics',
    'voice.streaming_stt',
    'voice.audio_emotion',
    'intelligence',
    'intelligence.shadow_learner',
    'intelligence.frustration_detector',
    'intelligence.screen_watcher',
    'intelligence.privacy_mode',
    'intelligence.meeting_mode',
    'intelligence.ghost_mode',
    'intelligence.tone_analyzer',
    'intelligence.control_modes',
    'intelligence.mood_history',
    'intelligence.endocrine',
    'intelligence.sleep_cycle',
    'intelligence.personality_modes',
    'intelligence.security_monitor',
    'intelligence.conditioned_reflexes',
    'intelligence.auto_tuner',
    'intelligence.internet_learning',
    'intelligence.workflows',
    'intelligence.morning_briefing',
    'intelligence.wake_word',
    'intelligence.proactive_assistant',
    'intelligence.ocr_reader',
    'intelligence.ui_accessibility',
    'intelligence.tuner_cache',
    'intelligence.frustration_detector',
    'integrations',
    'integrations.weather',
    'integrations.news',
    'integrations.calendar_reader',
    'integrations.email_monitor',
    'integrations.smart_home',
    'plugins',
    'plugins.spotify',
    'remote',
    'remote.control',
]

# ── Data files to include ───────────────────────────────────────────────
DATAS = [
    # Backend Python files (the entire backend directory)
    (BACKEND_DIR, 'backend'),
    # Core daemon (needed for Control Core)
    (os.path.join(PROJECT_ROOT, 'core'), 'core'),
    # Static assets
    (os.path.join(BACKEND_DIR, 'remote', 'template.html'), os.path.join('backend', 'remote')),
]

# Collect any additional data files from heavy packages
try:
    DATAS += collect_data_files('faster_whisper')
except Exception:
    pass

try:
    DATAS += collect_data_files('sentence_transformers')
except Exception:
    pass

try:
    DATAS += collect_data_files('lancedb')
except Exception:
    pass

# ── Analysis ────────────────────────────────────────────────────────────
a = Analysis(
    [os.path.join(BACKEND_DIR, 'launcher.py')],
    pathex=[BACKEND_DIR, PROJECT_ROOT],
    binaries=[],
    datas=DATAS,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[        # Exclude heavy unused packages
        'tkinter', '_tkinter',
        'matplotlib', 'scipy', 'pandas',
        'notebook', 'IPython',
        'pytest', 'unittest', '_pytest',
        'pip',
    ],
    noarchive=False,
    optimize=1,
)

# ── PYZ (compressed Python archive) ────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data)

# ── EXE (one-file mode: single self-contained EXE for Tauri sidecar) ──
# Tauri's externalBin only bundles a single EXE file, so we must use
# one-file mode (exclude_binaries=False, no COLLECT) to produce a
# self-contained executable that includes all Python DLLs.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    exclude_binaries=False,
    name='may-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll'],
    console=True,  # Keep console for logging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
