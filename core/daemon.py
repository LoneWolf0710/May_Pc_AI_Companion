"""May Control Core — Windows Service Daemon / Debug Entry Point.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md Section 14:

This is the entry point for the Control Core daemon.
It can run as:
  1. A Windows Service (production) — always on, runs at boot
  2. A debug console app (development) — python daemon.py debug

The daemon:
  - Ensures admin privileges
  - Enables all required token privileges
  - Sets up structured logging
  - Creates the CommandBus
  - Starts the TCP server on port 7650
  - Registers all control layer handlers

Usage:
  # Install as Windows Service
  python daemon.py install

  # Start the service
  python daemon.py start

  # Stop the service
  python daemon.py stop

  # Remove the service
  python daemon.py remove

  # Run in debug mode (console, not service)
  python daemon.py debug
"""

from __future__ import annotations

import asyncio
import sys
import os
import logging

# Ensure the parent directory (may/) is on the path so 'core' is importable
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.bus import CommandBus, BusServer
from core.router import Router
from core.privilege import ensure_admin, enable_all_privileges, is_admin
from core.engine.logger import setup_logger, get_logger
from core.engine.fallback import FallbackChain

# ── Service Configuration ────────────────────────────────────────────────────

SVC_NAME = "MayControlCore"
SVC_DISPLAY_NAME = "May Control Core"
SVC_DESCRIPTION = "May AI Companion — PC Control Engine"
BUS_HOST = "127.0.0.1"
BUS_PORT = 7650

logger = logging.getLogger("may.core.daemon")


# ── Layer Registration (stub — layers will be added in Phase 2) ──────────────

def register_all_layers(router: Router):
    """Register all 15 control layer handlers (L1-L15) with the router.

    Layers without real implementations get stubs that return 'not implemented'.
    """
    from core.bus import Result

    # Placeholder handler for layers not yet implemented
    async def stub_handler(action: str, params: dict) -> Result:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Layer not yet implemented: {action}",
        )

    # ── Phase 2: Load all layer handlers (L1-L15) ──
    real_layers = {}
    layer_modules = [
        ("filesystem",  "L1_filesystem"),
        ("process",     "L2_process"),
        ("application", "L3_application"),
        ("window",      "L4_window"),
        ("input",       "L5_input"),
        ("registry",    "L6_registry"),
        ("services",    "L7_services"),
        ("system",      "L8_system"),
        ("browser",     "L9_browser"),
        # P5: Domain-specific layers (L10-L15)
        ("network",     "L10_network"),
        ("media",       "L11_media"),
        ("developer",   "L12_developer"),
        ("cloud",       "L13_cloud"),
        ("automation",  "L14_automation"),
        ("advanced",    "L15_advanced"),
        # P7: UIAutomation accessibility tree (Hermes-level computer-use)
        ("uiautomation", "L16_uiautomation"),
        # P7: Post-action verification (screenshot + UIA + error scan)
        ("verify",        "L16_verify"),
        # P8: Content & utility tools (math, encoding, format conversion)
        ("content_tools", "L17_content_tools"),
    ]

    for layer_name, module_name in layer_modules:
        try:
            import importlib
            mod = importlib.import_module(f"core.layers.{module_name}")
            real_layers[layer_name] = mod.handler
            logger.info("Loaded handler: %s.%s", layer_name, module_name)
        except (ImportError, ModuleNotFoundError, AttributeError) as e:
            logger.warning("Could not load %s: %s", module_name, e)

    # ── Register all layers ──
    all_layers = [name for name, _ in layer_modules]
    loaded_count = 0
    for layer_name in all_layers:
        handler = real_layers.get(layer_name, stub_handler)
        router.register_layer(layer_name, handler)
        if layer_name in real_layers:
            loaded_count += 1

    logger.info(
        "Registered %d layers (%d real, %d stubs)",
        len(all_layers), loaded_count, len(all_layers) - loaded_count,
    )


# ── Main Async Loop ──────────────────────────────────────────────────────────

async def run_core():
    """Main async entry point — sets up and runs the Control Core.

    This is the shared setup for both Windows Service and debug modes.
    """
    try:
        # 1. Setup logging
        setup_logger("may.core", level=logging.DEBUG)
        logger.info("=" * 60)
        logger.info("May Control Core starting up")
        logger.info("=" * 60)

        # 2. Check admin status
        if is_admin():
            logger.info("Running with Administrator privileges ✓")
        else:
            logger.warning("NOT running as admin — some operations will fail")

        # 2. Enable token privileges
        priv_results = enable_all_privileges()
        enabled = sum(1 for v in priv_results.values() if v)
        logger.info("Token privileges enabled: %d/%d", enabled, len(priv_results))

        # 4. Create Command Bus and Router
        bus = CommandBus()
        router = Router(bus)

        # 5. Register all layers
        register_all_layers(router)

        # 6. Start TCP server
        server = BusServer(bus, host=BUS_HOST, port=BUS_PORT)
        await server.start()

        # Set up global exception handler for asyncio event loop
        loop = asyncio.get_event_loop()
        def handle_exception(loop, context):
            exception = context.get("exception")
            if exception:
                logger.critical("Unhandled exception in event loop: %s", exception, exc_info=exception)
            else:
                logger.critical("Exception in event loop: %s", context.get("message"))
        
        loop.set_exception_handler(handle_exception)

        logger.info(
            "May Control Core is LIVE on %s:%d — accepting commands",
            BUS_HOST, BUS_PORT,
        )

        # 7. Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(3600)  # Sleep 1 hour, loop forever
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Shutdown signal received")
        except Exception as e:
            # Catch any unhandled exception in the main loop
            logger.critical("Unhandled exception in main loop: %s", e, exc_info=True)
            raise
        finally:
            await server.stop()
            logger.info("May Control Core shut down cleanly")
    except Exception as e:
        logger.critical("Fatal error in run_core: %s", e, exc_info=True)
        raise


# ── Windows Service ──────────────────────────────────────────────────────────

def run_as_service():
    """Run the Control Core as a Windows Service."""
    try:
        import win32serviceutil
        import win32service
        import win32event
        import servicemanager

        class MayControlCoreService(win32serviceutil.ServiceFramework):
            _svc_name_ = SVC_NAME
            _svc_display_name_ = SVC_DISPLAY_NAME
            _svc_description_ = SVC_DESCRIPTION

            def __init__(self, args):
                win32serviceutil.ServiceFramework.__init__(self, args)
                self.stop_event = win32event.CreateEvent(None, 0, 0, None)

            def SvcDoRun(self):
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STARTED,
                    (self._svc_name_, ""),
                )
                asyncio.run(run_core())

            def SvcStop(self):
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                win32event.SetEvent(self.stop_event)

        win32serviceutil.HandleCommandLine(MayControlCoreService)

    except ImportError:
        logger.error(
            "pywin32 is not installed. Cannot run as Windows Service.\n"
            "Install with: pip install pywin32\n"
            "Then run: python -m pywin32_postinstall -install"
        )
        sys.exit(1)


# ── Debug Mode ───────────────────────────────────────────────────────────────

def run_as_debug():
    """Run the Control Core in debug mode (console, not service)."""
    import os as _os
    import faulthandler
    faulthandler.enable()
    
    log_dir = _os.path.join(_os.path.expanduser("~"), ".may")
    _os.makedirs(log_dir, exist_ok=True)
    log_path = _os.path.join(log_dir, "control_core.log")

    print(f"Starting May Control Core in DEBUG mode on {BUS_HOST}:{BUS_PORT}")
    print(f"Log file: {log_path}")
    print("Press Ctrl+C to stop\n")
    
    # Set up faulthandler to catch crashes
    faulthandler.dump_traceback_later(30, repeat=True)
    
    try:
        asyncio.run(run_core())
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"\nFATAL: Control Core crashed: {e}")
        import traceback
        traceback.print_exc()
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n=== FATAL CRASH at {__import__('datetime').datetime.now()} ===\n")
                traceback.print_exc(file=f)
        except Exception:
            pass


# ── CLI Entry Point ──────────────────────────────────────────────────────────

def main():
    """CLI dispatcher for the daemon.

    Commands:
        python daemon.py install   — Install as Windows Service
        python daemon.py start     — Start the service
        python daemon.py stop      — Stop the service
        python daemon.py remove    — Remove the service
        python daemon.py debug     — Run in debug mode (console)
    """
    if len(sys.argv) < 2:
        print("Usage: python daemon.py [install|start|stop|remove|debug]")
        print()
        print("  install  — Install as Windows Service (requires pywin32)")
        print("  start    — Start the Windows Service")
        print("  stop     — Stop the Windows Service")
        print("  remove   — Remove the Windows Service")
        print("  debug    — Run in debug mode (console, no service)")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "debug":
        run_as_debug()
    elif command in ("install", "start", "stop", "remove"):
        run_as_service()
    else:
        print(f"Unknown command: {command}")
        print("Valid commands: install, start, stop, remove, debug")
        sys.exit(1)


if __name__ == "__main__":
    main()
