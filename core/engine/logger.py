"""Structured Logging — for the Control Core engine.

Per JARVIS_CONTROL_CORE_ARCHITECTURE.md:
  Logs to both console and file with structured format.
  Every action is logged with command ID, method used, success/failure,
  verification status, and execution time.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path

try:
    import win32evtlog
    import win32evtlogutil
    _HAS_WIN32EVTLOG = True
except ImportError:
    _HAS_WIN32EVTLOG = False


# ── Windows Event Log ───────────────────────────────────────────────────────

EVENT_LOG_SOURCE = "MayControlCore"
EVENT_LOG_TYPE_INFO = win32evtlog.EVENTLOG_INFORMATION_TYPE if _HAS_WIN32EVTLOG else None
EVENT_LOG_TYPE_WARN = win32evtlog.EVENTLOG_WARNING_TYPE if _HAS_WIN32EVTLOG else None
EVENT_LOG_TYPE_ERROR = win32evtlog.EVENTLOG_ERROR_TYPE if _HAS_WIN32EVTLOG else None


class WinEventHandler(logging.Handler):
    """Log handler that writes to the Windows Event Log.

    Only active on Windows when pywin32 is installed.
    Falls back silently on other platforms.
    """

    def __init__(self):
        super().__init__(level=logging.WARNING)
        if not _HAS_WIN32EVTLOG:
            return
        # Register the event source if not already registered
        try:
            win32evtlogutil.AddSourceToRegistry(
                EVENT_LOG_SOURCE,
                "% System%\\System32\\winsevnt.dll",
                "Application",
            )
        except Exception:
            pass

    def emit(self, record: logging.LogRecord):
        if not _HAS_WIN32EVTLOG:
            return
        try:
            msg = self.format(record)
            if record.levelno >= logging.ERROR:
                event_type = EVENT_LOG_TYPE_ERROR
            elif record.levelno >= logging.WARNING:
                event_type = EVENT_LOG_TYPE_WARN
            else:
                event_type = EVENT_LOG_TYPE_INFO
            win32evtlog.ReportEvent(
                EVENT_LOG_SOURCE,
                1000,  # Event ID
                0,      # Category
                event_type,
                [msg],
            )
        except Exception:
            pass  # Never let Event Log failures break the app


# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_LOG_DIR = Path(os.environ.get("MAY_LOG_DIR", Path(__file__).parent.parent / "logs"))
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "control_core.log"
MAX_LOG_SIZE_MB = 10
LOG_BACKUP_COUNT = 5

# Structured format with timestamps
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ── Setup ────────────────────────────────────────────────────────────────────

def setup_logger(
    name: str = "may.core",
    level: int = logging.INFO,
    log_file: str | Path | None = None,
    log_dir: str | Path | None = None,
    console: bool = True,
) -> logging.Logger:
    """Set up structured logging for the Control Core.

    Creates a logger with both console and rotating file handlers.

    Args:
        name:      Logger name (hierarchical, e.g. 'may.core.bus').
        level:     Logging level.
        log_file:  Explicit log file path. If None, uses default.
        log_dir:   Directory for log files. If None, uses default.
        console:   Whether to also log to stderr.

    Returns:
        Configured logger instance.
    """
    root_logger = logging.getLogger(name)
    root_logger.setLevel(level)

    # Prevent duplicate handlers on repeated setup
    if root_logger.handlers:
        return root_logger

    # Ensure log directory exists
    if log_dir:
        log_path = Path(log_dir)
    elif log_file:
        log_path = Path(log_file).parent
    else:
        log_path = DEFAULT_LOG_DIR
    log_path.mkdir(parents=True, exist_ok=True)

    # ── File Handler (rotating) ──
    file_path = Path(log_file) if log_file else DEFAULT_LOG_FILE
    file_handler = logging.handlers.RotatingFileHandler(
        file_path,
        maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # ── Console Handler ──
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # ── Windows Event Log Handler (errors + warnings only) ──
    if console:  # Only add when running in interactive mode
        try:
            evt_handler = WinEventHandler()
            evt_handler.setFormatter(file_formatter)
            root_logger.addHandler(evt_handler)
        except Exception:
            pass  # Non-fatal

    root_logger.info("Logger initialized: name=%s level=%s file=%s", name, logging.getLevelName(level), file_path)
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the may.core hierarchy.

    Usage:
        logger = get_logger("may.core.bus")
        logger.info("Something happened")
    """
    return logging.getLogger(name)


# ── Pre-configured loggers for each engine component ─────────────────────────

def get_bus_logger() -> logging.Logger:
    return logging.getLogger("may.core.bus")


def get_fallback_logger() -> logging.Logger:
    return logging.getLogger("may.core.fallback")


def get_verifier_logger() -> logging.Logger:
    return logging.getLogger("may.core.verifier")


def get_router_logger() -> logging.Logger:
    return logging.getLogger("may.core.router")


def get_daemon_logger() -> logging.Logger:
    return logging.getLogger("may.core.daemon")


def get_layer_logger(layer_name: str) -> logging.Logger:
    """Get a logger for a specific control layer.

    Usage:
        logger = get_layer_logger("L1_filesystem")
    """
    return logging.getLogger(f"may.core.layers.{layer_name}")
