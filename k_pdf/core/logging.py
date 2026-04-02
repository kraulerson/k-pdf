"""Structured JSON logging with rotating file handler.

Log format: JSON lines with timestamp, level, module, message, context.
Output: {config_dir}/logs/k-pdf.log (rotating, 5MB, 3 backups).
Sensitive data (file contents, form values, passwords, annotation text) is NEVER logged.
"""

from __future__ import annotations

import json
import logging
import platform
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


def _get_config_dir() -> Path:
    """Return the platform-specific configuration directory for K-PDF."""
    system = platform.system()
    if system == "Windows":
        base = Path(__import__("os").environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "K-PDF"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "K-PDF"
    else:
        xdg = __import__("os").environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
        return base / "k-pdf"


class JsonFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string."""
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        if hasattr(record, "tab_session_id"):
            log_entry["tab_session_id"] = record.tab_session_id
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """Configure structured JSON logging with rotating file output.

    Args:
        level: Logging level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    log_dir = _get_config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "k-pdf.log"

    root_logger = logging.getLogger("k_pdf")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    json_formatter = JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%S%z")

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    if sys.stderr.isatty():
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(json_formatter)
        root_logger.addHandler(stream_handler)
