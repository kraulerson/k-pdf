"""Tests for SQLite schema migration system."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from k_pdf.persistence.migrations import (
    CURRENT_VERSION,
    DEFAULT_PREFERENCES,
    get_schema_version,
    migrate,
    seed_defaults,
)
from k_pdf.persistence.settings_db import init_db


def test_fresh_migration_applies_schema(tmp_path: Path) -> None:
    db = sqlite3.connect(str(tmp_path / "test.db"))
    assert get_schema_version(db) == 0
    migrate(db)
    assert get_schema_version(db) == CURRENT_VERSION
    db.close()


def test_migration_creates_all_tables(tmp_path: Path) -> None:
    db = sqlite3.connect(str(tmp_path / "test.db"))
    migrate(db)
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    assert "schema_version" in tables
    assert "preferences" in tables
    assert "recent_files" in tables
    db.close()


def test_seed_defaults_inserts_all_preferences(tmp_path: Path) -> None:
    db = sqlite3.connect(str(tmp_path / "test.db"))
    migrate(db)
    seed_defaults(db)
    cursor = db.execute("SELECT key FROM preferences ORDER BY key")
    keys = {row[0] for row in cursor.fetchall()}
    assert keys == set(DEFAULT_PREFERENCES.keys())
    db.close()


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = sqlite3.connect(str(tmp_path / "test.db"))
    migrate(db)
    version_after_first = get_schema_version(db)
    migrate(db)
    version_after_second = get_schema_version(db)
    assert version_after_first == version_after_second == CURRENT_VERSION
    db.close()


def test_init_db_creates_database(tmp_path: Path) -> None:
    db_path = tmp_path / "settings.db"
    db = init_db(db_path)
    assert db_path.exists()
    assert get_schema_version(db) == CURRENT_VERSION
    cursor = db.execute("SELECT COUNT(*) FROM preferences")
    count = cursor.fetchone()[0]
    assert count == len(DEFAULT_PREFERENCES)
    db.close()


def test_recent_files_table_accepts_entries(tmp_path: Path) -> None:
    db = sqlite3.connect(str(tmp_path / "test.db"))
    migrate(db)
    db.execute(
        "INSERT INTO recent_files (file_path) VALUES (?)",
        ("/tmp/test.pdf",),
    )
    db.commit()
    cursor = db.execute("SELECT file_path, page_number, zoom_level FROM recent_files")
    row = cursor.fetchone()
    assert row == ("/tmp/test.pdf", 1, "fit_width")
    db.close()
