"""May AI Companion — Sidecar Launcher.

Entry point for the PyInstaller-bundled Python backend.
Handles path resolution for both development and bundled modes,
then launches the FastAPI server via uvicorn.
"""

import os
import sys
import logging
import signal
import subprocess
import time
import socket


def _setup_logging():
    """Configure logging for the sidecar."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger('may.sidecar')
    return logger


def _wait_for_port(port: int, host: str = '127.0.0.1', timeout: float = 30.0) -> bool:
    """Wait until a port is accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


def _kill_port(port: int, host: str = '127.0.0.1'):
    """Kill any process using the specified port."""
    try:
        import psutil
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr.port == port and conn.status == 'LISTEN':
                try:
                    proc = psutil.Process(conn.pid)
                    proc.terminate()
                    proc.wait(timeout=5)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    except ImportError:
        pass


def main():
    """Main entry point for the sidecar."""
    logger = _setup_logging()
    logger.info("May AI Backend sidecar starting...")

    # Determine paths based on bundled vs development mode
    if getattr(sys, 'frozen', False):
        # PyInstaller bundled mode
        bundle_dir = sys._MEIPASS
        app_dir = bundle_dir  # core/ is extracted into _MEIPASS alongside backend/
        logger.info("Running in bundled mode. Bundle dir: %s", bundle_dir)
    else:
        # Development mode
        bundle_dir = os.path.dirname(os.path.abspath(__file__))
        app_dir = os.path.dirname(bundle_dir)
        logger.info("Running in dev mode. Bundle dir: %s", bundle_dir)

    # The backend directory contains main.py and all submodules
    # In bundled mode, the spec bundles (BACKEND_DIR, 'backend') so
    # main.py is at bundle_dir/backend/main.py
    backend_dir = os.path.join(bundle_dir, 'backend') if getattr(sys, 'frozen', False) else bundle_dir

    # Add backend directory to Python path
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # Add app directory (project root) to path for 'core.*' imports
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    # Set environment variables for proper operation
    os.environ['MAY_SIDECAR'] = '1'
    os.environ['MAY_APP_DIR'] = app_dir
    # Force CPU-only mode for torch to avoid CUDA DLL crashes
    # when CUDA toolkit is not installed
    os.environ['CUDA_VISIBLE_DEVICES'] = ''

    # Check if port 8080 is already in use
    port = 8080
    if _wait_for_port(port, timeout=1.0):
        logger.warning("Port %d already in use — killing existing process...", port)
        _kill_port(port)
        time.sleep(1)

    # Import and run the FastAPI application
    try:
        logger.info("Importing main module from %s", backend_dir)
        main_module_path = os.path.join(backend_dir, 'main.py')

        if not os.path.exists(main_module_path):
            logger.error("main.py not found at %s", main_module_path)
            sys.exit(1)

        # Import the main module
        import importlib.util
        spec = importlib.util.spec_from_file_location("may_main", main_module_path)
        may_main = importlib.util.module_from_spec(spec)
        sys.modules['may_main'] = may_main
        spec.loader.exec_module(may_main)

        import uvicorn

        logger.info("Starting uvicorn on port %d...", port)

        # Run uvicorn with the FastAPI app
        uvicorn.run(
            may_main.app,
            host="127.0.0.1",
            port=port,
            log_level="info",
            access_log=False,
        )

    except KeyboardInterrupt:
        logger.info("Sidecar interrupted by user")
    except Exception as e:
        logger.error("Sidecar failed to start: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
