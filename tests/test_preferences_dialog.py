"""Tests for PreferencesDialog — tabbed settings UI."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from k_pdf.core.preferences_manager import (
    DARK_MODE_CHOICES,
    ZOOM_CHOICES,
    PreferencesManager,
)
from k_pdf.persistence.migrations import migrate, seed_defaults
from k_pdf.views.preferences_dialog import PreferencesDialog


@pytest.fixture
def prefs_db(tmp_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(tmp_path / "test_prefs.db"))
    migrate(db)
    seed_defaults(db)
    return db


@pytest.fixture
def prefs(prefs_db: sqlite3.Connection, qapp) -> PreferencesManager:
    return PreferencesManager(prefs_db)


@pytest.fixture
def dialog(prefs: PreferencesManager) -> PreferencesDialog:
    return PreferencesDialog(prefs)


class TestDialogStructure:
    def test_window_title(self, dialog: PreferencesDialog) -> None:
        assert dialog.windowTitle() == "Preferences"

    def test_has_two_tabs(self, dialog: PreferencesDialog) -> None:
        assert dialog.tabs.count() == 2

    def test_tab_names(self, dialog: PreferencesDialog) -> None:
        assert dialog.tabs.tabText(0) == "General"
        assert dialog.tabs.tabText(1) == "Appearance"

    def test_minimum_size(self, dialog: PreferencesDialog) -> None:
        assert dialog.minimumWidth() >= 450
        assert dialog.minimumHeight() >= 300


class TestGeneralTab:
    def test_author_name_edit_exists(self, dialog: PreferencesDialog) -> None:
        assert dialog.author_name_edit is not None

    def test_author_name_default_empty(self, dialog: PreferencesDialog) -> None:
        assert dialog.author_name_edit.text() == ""

    def test_author_name_placeholder(self, dialog: PreferencesDialog) -> None:
        assert "annotation" in dialog.author_name_edit.placeholderText().lower()

    def test_author_name_max_length(self, dialog: PreferencesDialog) -> None:
        assert dialog.author_name_edit.maxLength() == 200

    def test_recent_files_spin_exists(self, dialog: PreferencesDialog) -> None:
        assert dialog.recent_files_spin is not None

    def test_recent_files_spin_range(self, dialog: PreferencesDialog) -> None:
        assert dialog.recent_files_spin.minimum() == 5
        assert dialog.recent_files_spin.maximum() == 50

    def test_recent_files_spin_default(self, dialog: PreferencesDialog) -> None:
        assert dialog.recent_files_spin.value() == 20

    def test_default_zoom_combo_exists(self, dialog: PreferencesDialog) -> None:
        assert dialog.default_zoom_combo is not None

    def test_default_zoom_combo_count(self, dialog: PreferencesDialog) -> None:
        assert dialog.default_zoom_combo.count() == len(ZOOM_CHOICES)

    def test_default_zoom_combo_items(self, dialog: PreferencesDialog) -> None:
        combo = dialog.default_zoom_combo
        labels = [combo.itemText(i) for i in range(combo.count())]
        for zoom_label in ZOOM_CHOICES:
            assert zoom_label in labels

    def test_default_zoom_initial_selection(self, dialog: PreferencesDialog) -> None:
        assert dialog.default_zoom_combo.currentText() == "Fit Width"


class TestAppearanceTab:
    def test_theme_combo_exists(self, dialog: PreferencesDialog) -> None:
        assert dialog.theme_combo is not None

    def test_theme_combo_count(self, dialog: PreferencesDialog) -> None:
        assert dialog.theme_combo.count() == len(DARK_MODE_CHOICES)

    def test_theme_combo_items(self, dialog: PreferencesDialog) -> None:
        labels = [dialog.theme_combo.itemText(i) for i in range(dialog.theme_combo.count())]
        for theme_label in DARK_MODE_CHOICES:
            assert theme_label in labels

    def test_theme_combo_initial_off(self, dialog: PreferencesDialog) -> None:
        assert dialog.theme_combo.currentText() == "Off"


class TestLoadValues:
    def test_loads_custom_author(self, prefs: PreferencesManager) -> None:
        prefs.set_author_name("Custom Author")
        dlg = PreferencesDialog(prefs)
        assert dlg.author_name_edit.text() == "Custom Author"

    def test_loads_custom_recent_max(self, prefs: PreferencesManager) -> None:
        prefs.set_recent_files_max(35)
        dlg = PreferencesDialog(prefs)
        assert dlg.recent_files_spin.value() == 35

    def test_loads_custom_zoom(self, prefs: PreferencesManager) -> None:
        prefs.set_default_zoom("1.5")
        dlg = PreferencesDialog(prefs)
        assert dlg.default_zoom_combo.currentText() == "150%"

    def test_loads_custom_theme(self, prefs: PreferencesManager) -> None:
        prefs.set_dark_mode("dark_inverted")
        dlg = PreferencesDialog(prefs)
        assert dlg.theme_combo.currentText() == "Dark UI + Inverted PDF"


class TestSaveOnAccept:
    def test_saves_author_name(self, prefs: PreferencesManager) -> None:
        dlg = PreferencesDialog(prefs)
        dlg.author_name_edit.setText("Saved Author")
        dlg._on_accepted()
        assert prefs.get_author_name() == "Saved Author"

    def test_saves_recent_files_max(self, prefs: PreferencesManager) -> None:
        dlg = PreferencesDialog(prefs)
        dlg.recent_files_spin.setValue(15)
        dlg._on_accepted()
        assert prefs.get_recent_files_max() == 15

    def test_saves_default_zoom(self, prefs: PreferencesManager) -> None:
        dlg = PreferencesDialog(prefs)
        idx = dlg.default_zoom_combo.findText("100%")
        dlg.default_zoom_combo.setCurrentIndex(idx)
        dlg._on_accepted()
        assert prefs.get_default_zoom() == "1.0"

    def test_saves_theme(self, prefs: PreferencesManager) -> None:
        dlg = PreferencesDialog(prefs)
        idx = dlg.theme_combo.findText("Dark UI + Original PDF")
        dlg.theme_combo.setCurrentIndex(idx)
        dlg._on_accepted()
        assert prefs.get_dark_mode() == "dark_original"

    def test_strips_author_whitespace(self, prefs: PreferencesManager) -> None:
        dlg = PreferencesDialog(prefs)
        dlg.author_name_edit.setText("  Padded  ")
        dlg._on_accepted()
        assert prefs.get_author_name() == "Padded"

    def test_preferences_saved_signal_emitted(self, prefs: PreferencesManager, qtbot) -> None:
        dlg = PreferencesDialog(prefs)
        with qtbot.waitSignal(dlg.preferences_saved, timeout=1000):
            dlg._on_accepted()


class TestCancelDoesNotSave:
    def test_reject_does_not_save_author(self, prefs: PreferencesManager) -> None:
        prefs.set_author_name("Original")
        dlg = PreferencesDialog(prefs)
        dlg.author_name_edit.setText("Changed")
        dlg.reject()
        assert prefs.get_author_name() == "Original"

    def test_reject_does_not_save_zoom(self, prefs: PreferencesManager) -> None:
        dlg = PreferencesDialog(prefs)
        idx = dlg.default_zoom_combo.findText("200%")
        dlg.default_zoom_combo.setCurrentIndex(idx)
        dlg.reject()
        assert prefs.get_default_zoom() == "fit_width"


class TestAccessibility:
    def test_author_name_accessible_name(self, dialog: PreferencesDialog) -> None:
        assert dialog.author_name_edit.accessibleName() == "Author name"

    def test_recent_files_accessible_name(self, dialog: PreferencesDialog) -> None:
        assert dialog.recent_files_spin.accessibleName() == "Recent files limit"

    def test_zoom_accessible_name(self, dialog: PreferencesDialog) -> None:
        assert dialog.default_zoom_combo.accessibleName() == "Default zoom level"

    def test_theme_accessible_name(self, dialog: PreferencesDialog) -> None:
        assert dialog.theme_combo.accessibleName() == "Theme"
