"""SQLite preferences database.

Database location: {config_dir}/k-pdf/settings.db
- Windows: %APPDATA%/K-PDF/settings.db
- macOS: ~/Library/Application Support/K-PDF/settings.db
- Linux: ~/.config/k-pdf/settings.db
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from k_pdf.core.logging import _get_config_dir
from k_pdf.persistence.migrations import CURRENT_VERSION, get_schema_version, migrate, seed_defaults

logger = logging.getLogger("k_pdf.persistence.settings_db")


def get_db_path() -> Path:
    """Return the path to the settings database file."""
    return _get_config_dir() / "settings.db"


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Initialize the settings database, running migrations as needed.

    Args:
        db_path: Optional override for the database file path.
            Defaults to the platform-specific config directory.

    Returns:
        An open SQLite connection with WAL mode and foreign keys enabled.
    """
    if db_path is None:
        db_path = get_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(db_path))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")

    current = get_schema_version(db)
    if current < CURRENT_VERSION:
        migrate(db)
        seed_defaults(db)
        logger.info("Database initialized at %s (v%d)", db_path, CURRENT_VERSION)
    else:
        logger.info("Database loaded at %s (v%d)", db_path, current)

    return db
