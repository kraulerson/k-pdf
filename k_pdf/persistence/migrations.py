"""SQLite schema migration system.

Applies versioned migrations to the K-PDF settings database.
Each migration is a SQL string keyed by version number.
Rollback for v1 MVP is: delete database, recreate from defaults.
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger("k_pdf.persistence.migrations")

MIGRATIONS: dict[int, str] = {
    1: """
    -- v1: Initial schema — preferences + recent_files

    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER NOT NULL,
        applied_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS preferences (
        key TEXT PRIMARY KEY NOT NULL,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS recent_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT NOT NULL UNIQUE,
        last_opened_at TEXT NOT NULL DEFAULT (datetime('now')),
        page_number INTEGER DEFAULT 1,
        zoom_level TEXT DEFAULT 'fit_width'
    );

    CREATE INDEX IF NOT EXISTS idx_recent_files_last_opened
        ON recent_files(last_opened_at DESC);
    """,
}

CURRENT_VERSION: int = max(MIGRATIONS)

DEFAULT_PREFERENCES: dict[str, str] = {
    "default_zoom": '"fit_width"',
    "dark_mode": '"off"',
    "annotation_author": '""',
    "recent_files_max": "20",
    "nav_panel_visible": "true",
    "nav_panel_width": "250",
    "annotation_panel_visible": "false",
    "window_width": "1200",
    "window_height": "800",
    "window_x": "null",
    "window_y": "null",
    "window_maximized": "false",
    "page_cache_limit": "50",
    "log_level": '"INFO"',
}


def get_schema_version(db: sqlite3.Connection) -> int:
    """Return the current schema version, or 0 if no schema exists."""
    try:
        cursor = db.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


def apply_migration(db: sqlite3.Connection, version: int) -> None:
    """Apply a single migration by version number.

    Args:
        db: SQLite database connection.
        version: The migration version to apply.

    Raises:
        KeyError: If the migration version is not defined.
    """
    sql = MIGRATIONS[version]
    db.executescript(sql)
    db.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    logger.info("Applied migration v%d", version)


def migrate(db: sqlite3.Connection) -> None:
    """Run all pending migrations up to CURRENT_VERSION.

    Args:
        db: SQLite database connection.
    """
    current = get_schema_version(db)
    if current >= CURRENT_VERSION:
        logger.info("Schema up to date at v%d", current)
        return

    for version in range(current + 1, CURRENT_VERSION + 1):
        apply_migration(db, version)

    db.commit()
    logger.info("Migrated from v%d to v%d", current, CURRENT_VERSION)


def seed_defaults(db: sqlite3.Connection) -> None:
    """Insert default preference values if they don't exist.

    Args:
        db: SQLite database connection.
    """
    for key, value in DEFAULT_PREFERENCES.items():
        db.execute(
            "INSERT OR IGNORE INTO preferences (key, value) VALUES (?, ?)",
            (key, value),
        )
    db.commit()
    logger.info("Default preferences seeded")
