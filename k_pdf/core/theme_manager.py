"""Theme management for Dark / Night Reading Mode.

Manages application-wide theme state with three modes: Off (light),
Dark UI / Original PDF, and Dark UI / Inverted PDF. Loads QSS
stylesheets and applies them to the QApplication instance. No
PyMuPDF dependency.
"""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

logger = logging.getLogger("k_pdf.core.theme_manager")

_THEMES_DIR = Path(__file__).parent.parent / "resources" / "themes"


class ThemeMode(Enum):
    """Application theme modes."""

    OFF = "off"
    DARK_ORIGINAL = "dark_original"
    DARK_INVERTED = "dark_inverted"


class ThemeManager(QObject):
    """Manages application-wide theme state and QSS stylesheet application.

    Emits signals when the theme or PDF inversion state changes so that
    views can update accordingly.
    """

    theme_changed = Signal(str)  # ThemeMode.value
    inversion_changed = Signal(bool)  # True if PDF inversion is active

    def __init__(self, app: QApplication, parent: QObject | None = None) -> None:
        """Initialize the ThemeManager.

        Args:
            app: The QApplication instance to apply stylesheets to.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._app = app
        self._mode = ThemeMode.OFF
        self._last_dark_mode = ThemeMode.DARK_ORIGINAL
        self._light_qss = self._load_qss("light.qss")
        self._dark_qss = self._load_qss("dark.qss")

        # Apply the light stylesheet on startup so the UI starts in light mode
        self._app.setStyleSheet(self._light_qss)

    @property
    def mode(self) -> ThemeMode:
        """Return the current theme mode."""
        return self._mode

    @property
    def is_dark(self) -> bool:
        """Return True if the current mode is a dark mode."""
        return self._mode in (ThemeMode.DARK_ORIGINAL, ThemeMode.DARK_INVERTED)

    @property
    def is_inverted(self) -> bool:
        """Return True if PDF inversion is active."""
        return self._mode is ThemeMode.DARK_INVERTED

    def set_mode(self, mode: ThemeMode) -> None:
        """Set the theme mode and apply the corresponding stylesheet.

        Emits theme_changed if the mode changed. Emits inversion_changed
        if the PDF inversion state changed.

        Args:
            mode: The desired theme mode.
        """
        if mode == self._mode:
            return

        old_inverted = self.is_inverted
        self._mode = mode

        # Remember last dark mode for toggle
        if mode in (ThemeMode.DARK_ORIGINAL, ThemeMode.DARK_INVERTED):
            self._last_dark_mode = mode

        # Apply stylesheet
        if mode is ThemeMode.OFF:
            self._app.setStyleSheet(self._light_qss)
        else:
            self._app.setStyleSheet(self._dark_qss)

        self.theme_changed.emit(mode.value)
        logger.info("Theme changed to %s", mode.value)

        # Emit inversion change only if it actually changed
        new_inverted = self.is_inverted
        if old_inverted != new_inverted:
            self.inversion_changed.emit(new_inverted)

    def toggle(self) -> None:
        """Toggle between Off and the last-used dark mode.

        If currently Off, switches to the last-used dark mode
        (defaults to DARK_ORIGINAL if no dark mode was previously used).
        If currently in any dark mode, switches to Off.
        """
        if self._mode is ThemeMode.OFF:
            self.set_mode(self._last_dark_mode)
        else:
            self.set_mode(ThemeMode.OFF)

    @staticmethod
    def _load_qss(filename: str) -> str:
        """Load a QSS stylesheet file from the themes directory.

        Args:
            filename: Name of the QSS file (e.g., 'light.qss').

        Returns:
            The stylesheet content as a string, or empty string on error.
        """
        path = _THEMES_DIR / filename
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            logger.warning("Failed to load stylesheet: %s", path)
            return ""
