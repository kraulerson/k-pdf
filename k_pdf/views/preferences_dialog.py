"""User preferences dialog.

Tabbed QDialog with General and Appearance settings. Changes are
applied when OK is clicked (not live preview). Reads current values
from PreferencesManager and writes back on accept.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from k_pdf.core.preferences_manager import (
    DARK_MODE_CHOICES,
    DARK_MODE_VALUE_TO_LABEL,
    ZOOM_CHOICES,
    ZOOM_VALUE_TO_LABEL,
    PreferencesManager,
)

logger = logging.getLogger("k_pdf.views.preferences_dialog")


class PreferencesDialog(QDialog):
    """Tabbed preferences dialog with General and Appearance tabs.

    Signals:
        preferences_saved: Emitted after OK is clicked and values are written.
    """

    preferences_saved = Signal()

    def __init__(
        self,
        prefs_manager: PreferencesManager,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the preferences dialog.

        Args:
            prefs_manager: The PreferencesManager to read/write settings.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._prefs = prefs_manager
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(450)
        self.setMinimumHeight(300)

        # Main layout
        layout = QVBoxLayout(self)

        # Tab widget
        self._tabs = QTabWidget(self)
        layout.addWidget(self._tabs)

        # General tab
        self._general_tab = QWidget()
        self._setup_general_tab()
        self._tabs.addTab(self._general_tab, "General")

        # Appearance tab
        self._appearance_tab = QWidget()
        self._setup_appearance_tab()
        self._tabs.addTab(self._appearance_tab, "Appearance")

        # Button box
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self._button_box.accepted.connect(self._on_accepted)
        self._button_box.rejected.connect(self.reject)
        layout.addWidget(self._button_box)

        # Load current values
        self._load_values()

    @property
    def tabs(self) -> QTabWidget:
        """Return the tab widget for test introspection."""
        return self._tabs

    @property
    def author_name_edit(self) -> QLineEdit:
        """Return the author name line edit."""
        return self._author_name_edit

    @property
    def recent_files_spin(self) -> QSpinBox:
        """Return the recent files limit spin box."""
        return self._recent_files_spin

    @property
    def default_zoom_combo(self) -> QComboBox:
        """Return the default zoom combo box."""
        return self._default_zoom_combo

    @property
    def theme_combo(self) -> QComboBox:
        """Return the theme combo box."""
        return self._theme_combo

    def _setup_general_tab(self) -> None:
        """Create the General settings tab with author, recent files, default zoom."""
        form = QFormLayout(self._general_tab)

        # Author name
        self._author_name_edit = QLineEdit()
        self._author_name_edit.setPlaceholderText("Enter your name for annotations")
        self._author_name_edit.setMaxLength(200)
        self._author_name_edit.setAccessibleName("Author name")
        form.addRow("Author Name:", self._author_name_edit)

        # Recent files limit
        self._recent_files_spin = QSpinBox()
        self._recent_files_spin.setRange(5, 50)
        self._recent_files_spin.setSingleStep(1)
        self._recent_files_spin.setAccessibleName("Recent files limit")
        form.addRow("Recent Files Limit:", self._recent_files_spin)

        # Default zoom level
        self._default_zoom_combo = QComboBox()
        for label in ZOOM_CHOICES:
            self._default_zoom_combo.addItem(label, ZOOM_CHOICES[label])
        self._default_zoom_combo.setAccessibleName("Default zoom level")
        form.addRow("Default Zoom:", self._default_zoom_combo)

    def _setup_appearance_tab(self) -> None:
        """Create the Appearance settings tab with theme selection."""
        form = QFormLayout(self._appearance_tab)

        # Theme selection
        self._theme_combo = QComboBox()
        for label in DARK_MODE_CHOICES:
            self._theme_combo.addItem(label, DARK_MODE_CHOICES[label])
        self._theme_combo.setAccessibleName("Theme")
        form.addRow("Theme:", self._theme_combo)

    def _load_values(self) -> None:
        """Populate widgets with current preference values."""
        # Author name
        self._author_name_edit.setText(self._prefs.get_author_name())

        # Recent files limit
        self._recent_files_spin.setValue(self._prefs.get_recent_files_max())

        # Default zoom
        zoom_value = self._prefs.get_default_zoom()
        zoom_label = ZOOM_VALUE_TO_LABEL.get(zoom_value, "Fit Width")
        idx = self._default_zoom_combo.findText(zoom_label)
        if idx >= 0:
            self._default_zoom_combo.setCurrentIndex(idx)

        # Theme
        dark_mode = self._prefs.get_dark_mode()
        theme_label = DARK_MODE_VALUE_TO_LABEL.get(dark_mode, "Off")
        idx = self._theme_combo.findText(theme_label)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)

    def _on_accepted(self) -> None:
        """Save all preferences and close the dialog."""
        # Author name
        self._prefs.set_author_name(self._author_name_edit.text().strip())

        # Recent files limit
        self._prefs.set_recent_files_max(self._recent_files_spin.value())

        # Default zoom
        zoom_data = self._default_zoom_combo.currentData()
        if zoom_data is not None:
            self._prefs.set_default_zoom(str(zoom_data))

        # Theme
        theme_data = self._theme_combo.currentData()
        if theme_data is not None:
            self._prefs.set_dark_mode(str(theme_data))

        self.preferences_saved.emit()
        logger.info("Preferences saved")
        self.accept()
