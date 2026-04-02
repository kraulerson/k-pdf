"""Recent files tracking via SQLite.

Stores file paths, last-viewed page, and zoom level.
Upserts on each open. Ordered by last_opened_at descending.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class RecentFiles:
    """CRUD operations for the recent_files table."""

    def __init__(self, db: sqlite3.Connection) -> None:
        """Initialize with a database connection.

        Args:
            db: SQLite connection (must have recent_files table).
        """
        self._db = db

    def add(
        self,
        file_path: Path,
        page_number: int = 1,
        zoom_level: str = "fit_width",
    ) -> None:
        """Add or update a recent file entry.

        Args:
            file_path: Absolute path to the PDF file.
            page_number: Last viewed page number.
            zoom_level: Last zoom setting.
        """
        now = datetime.now(tz=UTC).isoformat()
        self._db.execute(
            """INSERT INTO recent_files (file_path, page_number, zoom_level, last_opened_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                page_number = excluded.page_number,
                zoom_level = excluded.zoom_level,
                last_opened_at = excluded.last_opened_at
            """,
            (str(file_path), page_number, zoom_level, now),
        )
        self._db.commit()

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent files ordered by last opened time (newest first).

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of dicts with file_path, page_number, zoom_level keys.
        """
        cursor = self._db.execute(
            """SELECT file_path, page_number, zoom_level
            FROM recent_files
            ORDER BY last_opened_at DESC
            LIMIT ?""",
            (limit,),
        )
        return [
            {
                "file_path": row[0],
                "page_number": row[1],
                "zoom_level": row[2],
            }
            for row in cursor.fetchall()
        ]

    def remove(self, file_path: Path) -> None:
        """Remove a file from the recent list.

        Args:
            file_path: Path to remove.
        """
        self._db.execute(
            "DELETE FROM recent_files WHERE file_path = ?",
            (str(file_path),),
        )
        self._db.commit()
