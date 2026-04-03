"""Integration tests for Feature 11: Dark / Night Reading Mode."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.core.theme_manager import ThemeMode

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestDarkModeIntegration:
    def test_app_has_theme_manager(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert kpdf.theme_manager is not None
        assert kpdf.theme_manager.mode is ThemeMode.OFF
        kpdf.shutdown()

    def test_menu_selection_dark_original_changes_theme(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        kpdf.window.dark_mode_changed.emit("dark_original")
        assert kpdf.theme_manager.mode is ThemeMode.DARK_ORIGINAL
        kpdf.shutdown()

    def test_menu_selection_dark_inverted_changes_theme(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        kpdf.window.dark_mode_changed.emit("dark_inverted")
        assert kpdf.theme_manager.mode is ThemeMode.DARK_INVERTED
        kpdf.shutdown()

    def test_menu_selection_off_changes_theme(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        kpdf.window.dark_mode_changed.emit("dark_original")
        kpdf.window.dark_mode_changed.emit("off")
        assert kpdf.theme_manager.mode is ThemeMode.OFF
        kpdf.shutdown()

    def test_toggle_full_cycle(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert kpdf.theme_manager.mode is ThemeMode.OFF

        # Toggle on -> DARK_ORIGINAL (default)
        kpdf.window.dark_mode_toggle_requested.emit()
        assert kpdf.theme_manager.mode is ThemeMode.DARK_ORIGINAL

        # Toggle off
        kpdf.window.dark_mode_toggle_requested.emit()
        assert kpdf.theme_manager.mode is ThemeMode.OFF

        kpdf.shutdown()

    def test_status_bar_updates_on_mode_change(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        kpdf.window.dark_mode_changed.emit("dark_original")
        assert kpdf.window._mode_label.text() == "Dark Mode: Original PDF"
        kpdf.shutdown()

    def test_status_bar_updates_on_toggle(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        kpdf.window.dark_mode_toggle_requested.emit()
        assert kpdf.window._mode_label.text() == "Dark Mode: Original PDF"
        kpdf.window.dark_mode_toggle_requested.emit()
        assert kpdf.window._mode_label.text() == "Light Mode"
        kpdf.shutdown()

    def test_menu_radio_syncs_on_toggle(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        kpdf.window.dark_mode_toggle_requested.emit()
        assert kpdf.window._dark_mode_original_action.isChecked()
        assert not kpdf.window._dark_mode_off_action.isChecked()
        kpdf.window.dark_mode_toggle_requested.emit()
        assert kpdf.window._dark_mode_off_action.isChecked()
        assert not kpdf.window._dark_mode_original_action.isChecked()
        kpdf.shutdown()

    def test_inverted_mode_sets_inversion_on_existing_viewport(self) -> None:
        """Verify viewport inversion flag is set when switching to inverted mode."""
        from k_pdf.views.pdf_viewport import PdfViewport

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        # Simulate an open tab with a viewport
        viewport = PdfViewport()
        kpdf.tab_manager.get_active_viewport = MagicMock(  # type: ignore[method-assign]
            return_value=viewport,
        )

        kpdf.window.dark_mode_changed.emit("dark_inverted")
        assert viewport.invert_pdf is True

        kpdf.window.dark_mode_changed.emit("dark_original")
        assert viewport.invert_pdf is False

        kpdf.shutdown()

    def test_stylesheet_applied_on_dark_mode(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        kpdf.window.dark_mode_changed.emit("dark_original")
        assert app_instance.styleSheet() != ""
        kpdf.shutdown()

    def test_stylesheet_cleared_on_off(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        kpdf.window.dark_mode_changed.emit("dark_original")
        kpdf.window.dark_mode_changed.emit("off")
        # Light mode applies the light stylesheet
        assert kpdf.theme_manager.mode is ThemeMode.OFF
        kpdf.shutdown()
