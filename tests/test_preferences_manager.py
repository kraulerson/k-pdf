"""Tests for PreferencesManager — typed SQLite preference access."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from k_pdf.core.preferences_manager import (
    DARK_MODE_CHOICES,
    DARK_MODE_VALUE_TO_LABEL,
    KEY_AUTHOR_NAME,
    KEY_DARK_MODE,
    KEY_DEFAULT_ZOOM,
    KEY_RECENT_FILES_MAX,
    ZOOM_CHOICES,
    ZOOM_VALUE_TO_LABEL,
    PreferencesManager,
)
from k_pdf.persistence.migrations import migrate, seed_defaults


@pytest.fixture
def prefs_db(tmp_path: Path) -> sqlite3.Connection:
    """Create an in-memory database with schema and default prefs."""
    db = sqlite3.connect(str(tmp_path / "test_prefs.db"))
    migrate(db)
    seed_defaults(db)
    return db


@pytest.fixture
def prefs(prefs_db: sqlite3.Connection, qapp) -> PreferencesManager:
    """Create a PreferencesManager with a seeded database."""
    return PreferencesManager(prefs_db)


class TestPreferencesManagerGetters:
    def test_get_author_name_default(self, prefs: PreferencesManager) -> None:
        assert prefs.get_author_name() == ""

    def test_get_default_zoom_default(self, prefs: PreferencesManager) -> None:
        assert prefs.get_default_zoom() == "fit_width"

    def test_get_recent_files_max_default(self, prefs: PreferencesManager) -> None:
        assert prefs.get_recent_files_max() == 20

    def test_get_dark_mode_default(self, prefs: PreferencesManager) -> None:
        assert prefs.get_dark_mode() == "off"


class TestPreferencesManagerSetters:
    def test_set_author_name(self, prefs: PreferencesManager) -> None:
        prefs.set_author_name("Karl R")
        assert prefs.get_author_name() == "Karl R"

    def test_set_author_name_empty(self, prefs: PreferencesManager) -> None:
        prefs.set_author_name("Karl R")
        prefs.set_author_name("")
        assert prefs.get_author_name() == ""

    def test_set_default_zoom_numeric(self, prefs: PreferencesManager) -> None:
        prefs.set_default_zoom("1.5")
        assert prefs.get_default_zoom() == "1.5"

    def test_set_default_zoom_fit_page(self, prefs: PreferencesManager) -> None:
        prefs.set_default_zoom("fit_page")
        assert prefs.get_default_zoom() == "fit_page"

    def test_set_recent_files_max(self, prefs: PreferencesManager) -> None:
        prefs.set_recent_files_max(30)
        assert prefs.get_recent_files_max() == 30

    def test_set_recent_files_max_clamps_low(self, prefs: PreferencesManager) -> None:
        prefs.set_recent_files_max(1)
        assert prefs.get_recent_files_max() == 5

    def test_set_recent_files_max_clamps_high(self, prefs: PreferencesManager) -> None:
        prefs.set_recent_files_max(999)
        assert prefs.get_recent_files_max() == 50

    def test_set_dark_mode_dark_original(self, prefs: PreferencesManager) -> None:
        prefs.set_dark_mode("dark_original")
        assert prefs.get_dark_mode() == "dark_original"

    def test_set_dark_mode_dark_inverted(self, prefs: PreferencesManager) -> None:
        prefs.set_dark_mode("dark_inverted")
        assert prefs.get_dark_mode() == "dark_inverted"

    def test_set_dark_mode_off(self, prefs: PreferencesManager) -> None:
        prefs.set_dark_mode("dark_original")
        prefs.set_dark_mode("off")
        assert prefs.get_dark_mode() == "off"

    def test_set_dark_mode_invalid_ignored(self, prefs: PreferencesManager) -> None:
        prefs.set_dark_mode("dark_original")
        prefs.set_dark_mode("bogus")
        assert prefs.get_dark_mode() == "dark_original"


class TestPreferencesManagerSignals:
    def test_signal_emitted_on_set_author(self, prefs: PreferencesManager, qtbot) -> None:
        with qtbot.waitSignal(prefs.preference_changed, timeout=1000):
            prefs.set_author_name("Test Author")

    def test_signal_carries_key_and_value(self, prefs: PreferencesManager, qtbot) -> None:
        signals: list[tuple[str, str]] = []
        prefs.preference_changed.connect(lambda k, v: signals.append((k, v)))
        prefs.set_author_name("Alice")
        assert len(signals) == 1
        assert signals[0][0] == KEY_AUTHOR_NAME
        assert signals[0][1] == '"Alice"'

    def test_signal_emitted_on_set_zoom(self, prefs: PreferencesManager, qtbot) -> None:
        with qtbot.waitSignal(prefs.preference_changed, timeout=1000):
            prefs.set_default_zoom("1.0")

    def test_signal_emitted_on_set_recent_max(self, prefs: PreferencesManager, qtbot) -> None:
        with qtbot.waitSignal(prefs.preference_changed, timeout=1000):
            prefs.set_recent_files_max(10)

    def test_signal_emitted_on_set_dark_mode(self, prefs: PreferencesManager, qtbot) -> None:
        with qtbot.waitSignal(prefs.preference_changed, timeout=1000):
            prefs.set_dark_mode("dark_inverted")


class TestPreferencesManagerGetAll:
    def test_get_all_returns_dict(self, prefs: PreferencesManager) -> None:
        result = prefs.get_all()
        assert isinstance(result, dict)
        assert KEY_AUTHOR_NAME in result
        assert KEY_DEFAULT_ZOOM in result
        assert KEY_RECENT_FILES_MAX in result
        assert KEY_DARK_MODE in result

    def test_get_all_reflects_changes(self, prefs: PreferencesManager) -> None:
        prefs.set_author_name("Bob")
        result = prefs.get_all()
        assert result[KEY_AUTHOR_NAME] == '"Bob"'


class TestPreferencesManagerPersistence:
    def test_values_survive_new_manager_instance(self, prefs_db: sqlite3.Connection, qapp) -> None:
        mgr1 = PreferencesManager(prefs_db)
        mgr1.set_author_name("Persistent")
        mgr1.set_recent_files_max(42)

        mgr2 = PreferencesManager(prefs_db)
        assert mgr2.get_author_name() == "Persistent"
        assert mgr2.get_recent_files_max() == 42


class TestZoomChoicesConstants:
    def test_zoom_choices_has_seven_entries(self) -> None:
        assert len(ZOOM_CHOICES) == 7

    def test_zoom_choices_includes_fit_width(self) -> None:
        assert "Fit Width" in ZOOM_CHOICES
        assert ZOOM_CHOICES["Fit Width"] == "fit_width"

    def test_zoom_value_to_label_roundtrip(self) -> None:
        for label, value in ZOOM_CHOICES.items():
            assert ZOOM_VALUE_TO_LABEL[value] == label


class TestDarkModeChoicesConstants:
    def test_dark_mode_choices_has_three_entries(self) -> None:
        assert len(DARK_MODE_CHOICES) == 3

    def test_dark_mode_value_to_label_roundtrip(self) -> None:
        for label, value in DARK_MODE_CHOICES.items():
            assert DARK_MODE_VALUE_TO_LABEL[value] == label


class TestPreferencesManagerEdgeCases:
    def test_get_recent_files_max_handles_non_numeric_db_value(
        self, prefs_db: sqlite3.Connection, qapp
    ) -> None:
        prefs_db.execute(
            "UPDATE preferences SET value = ? WHERE key = ?",
            ("not_a_number", KEY_RECENT_FILES_MAX),
        )
        prefs_db.commit()
        mgr = PreferencesManager(prefs_db)
        assert mgr.get_recent_files_max() == 20

    def test_get_author_name_missing_key(self, tmp_path: Path, qapp) -> None:
        db = sqlite3.connect(str(tmp_path / "empty.db"))
        migrate(db)
        # Don't seed defaults — key will be missing
        mgr = PreferencesManager(db)
        assert mgr.get_author_name() == ""
        db.close()
