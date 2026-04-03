"""Tests for the Help menu in MainWindow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from k_pdf.views.main_window import MainWindow

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestHelpMenu:
    """Tests for Help menu existence and actions."""

    def test_help_menu_exists(self) -> None:
        window = MainWindow()
        menu_bar = window.menuBar()
        menu_titles = [action.text() for action in menu_bar.actions()]
        assert "&Help" in menu_titles

    def test_help_menu_is_last(self) -> None:
        window = MainWindow()
        menu_bar = window.menuBar()
        actions = menu_bar.actions()
        assert actions[-1].text() == "&Help"

    def test_keyboard_shortcuts_action_exists(self) -> None:
        window = MainWindow()
        help_menu = window._help_menu
        action_texts = [a.text() for a in help_menu.actions() if not a.isSeparator()]
        assert "Keyboard &Shortcuts" in action_texts

    def test_keyboard_shortcuts_shortcut_is_f1(self) -> None:
        window = MainWindow()
        help_menu = window._help_menu
        for action in help_menu.actions():
            if action.text() == "Keyboard &Shortcuts":
                assert action.shortcut() == QKeySequence("F1")
                return
        msg = "Keyboard Shortcuts action not found"
        raise AssertionError(msg)

    def test_about_action_exists(self) -> None:
        window = MainWindow()
        help_menu = window._help_menu
        action_texts = [a.text() for a in help_menu.actions() if not a.isSeparator()]
        assert "&About K-PDF" in action_texts

    def test_keyboard_shortcuts_action_opens_dialog(self) -> None:
        window = MainWindow()
        with patch("k_pdf.views.main_window.KeyboardShortcutsDialog") as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog_cls.return_value = mock_dialog
            # Find and trigger the action
            for action in window._help_menu.actions():
                if action.text() == "Keyboard &Shortcuts":
                    action.trigger()
                    break
            mock_dialog_cls.assert_called_once_with(window)
            mock_dialog.exec.assert_called_once()

    def test_about_action_opens_message_box(self) -> None:
        window = MainWindow()
        with patch("k_pdf.views.main_window.QMessageBox") as mock_mb:
            for action in window._help_menu.actions():
                if action.text() == "&About K-PDF":
                    action.trigger()
                    break
            mock_mb.about.assert_called_once()
            call_args = mock_mb.about.call_args
            # Verify version is in the message
            assert "0.1.0" in call_args[0][2]

    def test_about_dialog_contains_app_description(self) -> None:
        window = MainWindow()
        with patch("k_pdf.views.main_window.QMessageBox") as mock_mb:
            for action in window._help_menu.actions():
                if action.text() == "&About K-PDF":
                    action.trigger()
                    break
            call_args = mock_mb.about.call_args
            assert "Free, offline" in call_args[0][2]

    def test_menu_order_is_correct(self) -> None:
        """Menus should be: File, Edit, View, Tools, Help."""
        window = MainWindow()
        menu_bar = window.menuBar()
        menu_titles = [a.text() for a in menu_bar.actions()]
        assert menu_titles == ["&File", "&Edit", "&View", "&Tools", "&Help"]
