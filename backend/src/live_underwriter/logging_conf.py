"""Centralized logging configuration for live_underwriter.

All modules should use ``logging.getLogger(__name__)`` and never print.
This module sets up console + rotating file handlers so errors are always
captured with file/line context.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

# Project root is two levels up from this file: src/live_underwriter/logging_conf.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "live_underwriter.log"

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(level: int = logging.INFO, log_file: Path | None = None, force: bool = False) -> None:
    """Configure root logging.

    By default this is a no-op after the first call (guarded by ``_configured``).
    Pass ``force=True`` to reconfigure (e.g. in tests with a different log file).
    """
    global _configured
    if _configured and not force:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    target = log_file or LOG_FILE

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        target,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    # Replace any existing handlers so reconfiguration takes effect.
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.addHandler(console)
    root.addHandler(file_handler)

    _configured = True
    logging.getLogger(__name__).info("Logging initialized -> %s", target)


def get_logger(name: str) -> logging.Logger:
    """Return a logger, ensuring logging is configured first."""
    setup_logging()
    return logging.getLogger(name)
