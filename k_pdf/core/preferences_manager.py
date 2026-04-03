"""Preferences manager — typed access to user settings.

Reads/writes preference key-value pairs from the SQLite settings
database. Emits a signal when any preference changes so that views
and presenters can react.
"""

from __future__ import annotations

import json
import logging
import sqlite3

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("k_pdf.core.preferences_manager")

# Keys used in the preferences table
KEY_AUTHOR_NAME = "annotation_author"
KEY_DEFAULT_ZOOM = "default_zoom"
KEY_RECENT_FILES_MAX = "recent_files_max"
KEY_DARK_MODE = "dark_mode"

# Valid zoom choices (display label -> stored value)
ZOOM_CHOICES: dict[str, str] = {
    "50%": "0.5",
    "75%": "0.75",
    "100%": "1.0",
    "150%": "1.5",
    "200%": "2.0",
    "Fit Page": "fit_page",
    "Fit Width": "fit_width",
}

# Valid dark mode choices (display label -> stored value)
DARK_MODE_CHOICES: dict[str, str] = {
    "Off": "off",
    "Dark UI + Original PDF": "dark_original",
    "Dark UI + Inverted PDF": "dark_inverted",
}

# Reverse maps for display
ZOOM_VALUE_TO_LABEL: dict[str, str] = {v: k for k, v in ZOOM_CHOICES.items()}
DARK_MODE_VALUE_TO_LABEL: dict[str, str] = {v: k for k, v in DARK_MODE_CHOICES.items()}


class PreferencesManager(QObject):
    """Typed accessor for user preferences stored in SQLite.

    All values are stored as JSON-encoded strings in the preferences table.
    This class provides typed getters and setters that handle serialization.

    Signals:
        preference_changed: Emitted with (key, new_value_str) after a write.
    """

    preference_changed = Signal(str, str)  # (key, new_value)

    def __init__(self, db: sqlite3.Connection, parent: QObject | None = None) -> None:
        """Initialize with a database connection.

        Args:
            db: SQLite connection with preferences table already created.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._db = db

    # --- Raw read/write ---

    def _get_raw(self, key: str, default: str = '""') -> str:
        """Read a raw value from the preferences table.

        Args:
            key: Preference key.
            default: Default value if key is missing.

        Returns:
            The stored value string.
        """
        cursor = self._db.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

    def _set_raw(self, key: str, value: str) -> None:
        """Write a raw value to the preferences table and emit signal.

        Args:
            key: Preference key.
            value: Value to store.
        """
        self._db.execute(
            """INSERT INTO preferences (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value),
        )
        self._db.commit()
        self.preference_changed.emit(key, value)
        logger.info("Preference '%s' updated", key)

    # --- Typed getters ---

    def get_author_name(self) -> str:
        """Return the annotation author name.

        Returns:
            Author name string (empty string if unset).
        """
        raw = self._get_raw(KEY_AUTHOR_NAME, '""')
        return str(json.loads(raw))

    def get_default_zoom(self) -> str:
        """Return the default zoom setting.

        Returns:
            Zoom value string (e.g., '1.0', 'fit_width', 'fit_page').
        """
        raw = self._get_raw(KEY_DEFAULT_ZOOM, '"fit_width"')
        return str(json.loads(raw))

    def get_recent_files_max(self) -> int:
        """Return the maximum number of recent files to display.

        Returns:
            Integer between 5 and 50.
        """
        raw = self._get_raw(KEY_RECENT_FILES_MAX, "20")
        try:
            value = int(raw)
        except (ValueError, TypeError):
            value = 20
        return max(5, min(50, value))

    def get_dark_mode(self) -> str:
        """Return the dark mode setting.

        Returns:
            One of 'off', 'dark_original', 'dark_inverted'.
        """
        raw = self._get_raw(KEY_DARK_MODE, '"off"')
        return str(json.loads(raw))

    # --- Typed setters ---

    def set_author_name(self, name: str) -> None:
        """Set the annotation author name.

        Args:
            name: Author name string.
        """
        self._set_raw(KEY_AUTHOR_NAME, json.dumps(name))

    def set_default_zoom(self, value: str) -> None:
        """Set the default zoom level.

        Args:
            value: Zoom value (e.g., '1.0', 'fit_width').
        """
        self._set_raw(KEY_DEFAULT_ZOOM, json.dumps(value))

    def set_recent_files_max(self, value: int) -> None:
        """Set the maximum number of recent files.

        Args:
            value: Integer between 5 and 50.
        """
        clamped = max(5, min(50, value))
        self._set_raw(KEY_RECENT_FILES_MAX, str(clamped))

    def set_dark_mode(self, value: str) -> None:
        """Set the dark mode preference.

        Args:
            value: One of 'off', 'dark_original', 'dark_inverted'.
        """
        valid = {"off", "dark_original", "dark_inverted"}
        if value not in valid:
            logger.warning("Invalid dark_mode value: %s", value)
            return
        self._set_raw(KEY_DARK_MODE, json.dumps(value))

    # --- Bulk operations ---

    def get_all(self) -> dict[str, str]:
        """Return all preferences as a dict of {key: raw_value}.

        Returns:
            Dictionary of all stored preferences.
        """
        cursor = self._db.execute("SELECT key, value FROM preferences")
        return dict(cursor.fetchall())
