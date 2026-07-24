"""May Control Core — The PC Control Engine.

A standalone Python daemon that receives structured commands and
executes them against Windows with verified results.

Module structure per JARVIS_CONTROL_CORE_ARCHITECTURE.md:
  core/
  ├── daemon.py          # Entry point, Windows Service host
  ├── bus.py             # Command/Result dataclasses, CommandBus
  ├── router.py          # Maps commands → layers
  ├── privilege.py       # UAC, token, elevation management
  ├── layers/            # The 9 Control Layers
  ├── engine/
  │   ├── verifier.py
  │   ├── fallback.py
  │   ├── transaction.py
  │   └── logger.py
  └── config/
      ├── layer_caps.json
      └── fallback_chains.json
"""
