"""Integration tests for Preferences feature wiring in KPdfApp and MainWindow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.core.preferences_manager import PreferencesManager
from k_pdf.core.theme_manager import ThemeMode
from k_pdf.views.main_window import MainWindow

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestMainWindowPreferencesSignal:
    def test_preferences_requested_signal_exists(self) -> None:
        win = MainWindow()
        assert hasattr(win, "preferences_requested")

    def test_preferences_menu_action_exists(self) -> None:
        win = MainWindow()
        found = False
        for action in win.menuBar().actions():
            menu = action.menu()
            if menu is not None:
                for sub_action in menu.actions():
                    if "Preferences" in sub_action.text():
                        found = True
                        break
        assert found

    def test_preferences_action_shortcut(self) -> None:
        win = MainWindow()
        for action in win.menuBar().actions():
            menu = action.menu()
            if menu is not None:
                for sub_action in menu.actions():
                    if "Preferences" in sub_action.text():
                        assert sub_action.shortcut().toString() in (
                            "Ctrl+,",
                            "Meta+,",  # macOS translates Ctrl -> Meta
                        )
                        return
        pytest.fail("Preferences action not found")

    def test_preferences_action_emits_signal(self, qtbot) -> None:
        win = MainWindow()
        # Find the preferences action
        prefs_action = None
        for action in win.menuBar().actions():
            menu = action.menu()
            if menu is not None:
                for sub_action in menu.actions():
                    if "Preferences" in sub_action.text():
                        prefs_action = sub_action
                        break
        assert prefs_action is not None
        with qtbot.waitSignal(win.preferences_requested, timeout=1000):
            prefs_action.trigger()


class TestKPdfAppPreferencesManager:
    def test_app_has_preferences_manager(self, qapp) -> None:
        with patch("k_pdf.app.init_db") as mock_init:
            mock_init.return_value = MagicMock()
            # We need to avoid the full init, just verify the property exists
            pass
        # Direct test: create app with temp DB
        app_ctrl = KPdfApp(qapp)
        assert isinstance(app_ctrl.preferences_manager, PreferencesManager)
        app_ctrl.shutdown()

    def test_preferences_saved_applies_theme(self, qapp) -> None:
        app_ctrl = KPdfApp(qapp)
        # Set dark mode in preferences
        app_ctrl.preferences_manager.set_dark_mode("dark_original")
        # Simulate dialog save callback
        app_ctrl._on_preferences_saved()
        assert app_ctrl.theme_manager.mode is ThemeMode.DARK_ORIGINAL
        # Reset for next tests
        app_ctrl.theme_manager.set_mode(ThemeMode.OFF)
        app_ctrl.shutdown()

    def test_preferences_saved_applies_off_theme(self, qapp) -> None:
        app_ctrl = KPdfApp(qapp)
        # First go dark
        app_ctrl.theme_manager.set_mode(ThemeMode.DARK_ORIGINAL)
        # Set off in preferences
        app_ctrl.preferences_manager.set_dark_mode("off")
        app_ctrl._on_preferences_saved()
        assert app_ctrl.theme_manager.mode is ThemeMode.OFF
        app_ctrl.shutdown()


import pytest  # noqa: E402
