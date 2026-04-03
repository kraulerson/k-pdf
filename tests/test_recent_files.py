"""Tests for recent files persistence."""

from __future__ import annotations

from pathlib import Path

from k_pdf.persistence.recent_files import RecentFiles
from k_pdf.persistence.settings_db import init_db


def test_add_and_list(tmp_path: Path) -> None:
    """Test adding files and listing them in reverse chronological order."""
    db = init_db(tmp_path / "test.db")
    rf = RecentFiles(db)
    rf.add(Path("/tmp/a.pdf"))
    rf.add(Path("/tmp/b.pdf"))
    files = rf.list_recent(limit=10)
    assert len(files) == 2
    # Most recent first
    assert files[0]["file_path"] == str(Path("/tmp/b.pdf"))
    db.close()


def test_upsert_updates_timestamp(tmp_path: Path) -> None:
    """Test re-adding same file updates its metadata instead of duplicating."""
    db = init_db(tmp_path / "test.db")
    rf = RecentFiles(db)
    rf.add(Path("/tmp/a.pdf"), page_number=1)
    rf.add(Path("/tmp/a.pdf"), page_number=5)
    files = rf.list_recent(limit=10)
    assert len(files) == 1
    assert files[0]["page_number"] == 5
    db.close()


def test_list_respects_limit(tmp_path: Path) -> None:
    """Test that list_recent returns at most limit entries."""
    db = init_db(tmp_path / "test.db")
    rf = RecentFiles(db)
    for i in range(10):
        rf.add(Path(f"/tmp/file{i}.pdf"))
    files = rf.list_recent(limit=5)
    assert len(files) == 5
    db.close()


def test_remove_deletes_entry(tmp_path: Path) -> None:
    """Test removing a file from the recent list."""
    db = init_db(tmp_path / "test.db")
    rf = RecentFiles(db)
    rf.add(Path("/tmp/a.pdf"))
    rf.remove(Path("/tmp/a.pdf"))
    files = rf.list_recent(limit=10)
    assert len(files) == 0
    db.close()
