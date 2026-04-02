"""Integration tests for MainWindow, PdfViewport, and KPdfApp."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.core.document_model import PageInfo
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.views.pdf_viewport import PdfViewport, ViewportState

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestPdfViewport:
    """Tests for PdfViewport states and page display."""

    def test_initial_state_is_empty(self) -> None:
        """Test viewport starts in EMPTY state."""
        viewport = PdfViewport()
        assert viewport.state == ViewportState.EMPTY

    def test_viewport_has_no_welcome_widget(self) -> None:
        """Test that PdfViewport does not have a welcome overlay."""
        viewport = PdfViewport()
        assert not hasattr(viewport, "welcome_widget")

    def test_set_loading_changes_state(self) -> None:
        """Test set_loading transitions to LOADING state."""
        viewport = PdfViewport()
        viewport.set_loading("test.pdf")
        assert viewport.state == ViewportState.LOADING

    def test_set_error_changes_state(self) -> None:
        """Test set_error transitions to ERROR state."""
        viewport = PdfViewport()
        viewport.set_error("Something went wrong")
        assert viewport.state == ViewportState.ERROR

    def test_set_document_creates_placeholders(self) -> None:
        """Test set_document transitions to SUCCESS and creates page items."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
            PageInfo(index=1, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        assert viewport.state == ViewportState.SUCCESS

    def test_set_page_pixmap_replaces_placeholder(self) -> None:
        """Test set_page_pixmap replaces the placeholder item."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=100, height=100, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        img = QImage(100, 100, QImage.Format.Format_RGB888)
        img.fill(0)
        viewport.set_page_pixmap(0, QPixmap.fromImage(img))
        # Verify the item was replaced (no crash, item exists)
        assert 0 in viewport._page_items

    def test_scroll_to_page_exists(self) -> None:
        """Test that scroll_to_page method exists and doesn't raise."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
            PageInfo(index=1, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
            PageInfo(index=2, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        viewport.scroll_to_page(1)

    def test_current_page_changed_signal_exists(self) -> None:
        """Test that current_page_changed signal exists."""
        viewport = PdfViewport()
        spy = MagicMock()
        viewport.current_page_changed.connect(spy)


class TestMainWindow:
    """Tests for MainWindow with multi-tab support."""

    def test_initial_state_shows_welcome(self) -> None:
        """Test that MainWindow starts showing the welcome widget."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert window.stacked_widget.currentIndex() == 0

    def test_tab_widget_is_configured(self) -> None:
        """Test QTabWidget has closable, movable, document-mode tabs."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        tw = window.tab_widget
        assert tw.tabsClosable() is True
        assert tw.isMovable() is True
        assert tw.documentMode() is True

    def test_navigation_panel_exists(self) -> None:
        """Test that MainWindow has a navigation panel dock widget."""
        from k_pdf.views.main_window import MainWindow
        from k_pdf.views.navigation_panel import NavigationPanel

        window = MainWindow()
        assert isinstance(window.navigation_panel, NavigationPanel)

    def test_navigation_panel_starts_hidden(self) -> None:
        """Test that navigation panel is hidden by default."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert not window.navigation_panel.isVisible()

    def test_tab_close_requested_signal(self) -> None:
        """Test that tab_close_requested signal exists and is emittable."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        spy = MagicMock()
        window.tab_close_requested.connect(spy)
        window.tab_close_requested.emit()
        spy.assert_called_once()

    def test_file_open_requested_signal(self) -> None:
        """Test that file_open_requested signal can be emitted and received."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        spy = MagicMock()
        window.file_open_requested.connect(spy)
        window.file_open_requested.emit(Path("/tmp/test.pdf"))
        spy.assert_called_once_with(Path("/tmp/test.pdf"))

    def test_update_page_status(self) -> None:
        """Test status bar page label updates."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        window.update_page_status(3, 10)
        assert window._page_label.text() == "Page 3 of 10"

    def test_welcome_open_button_exists(self) -> None:
        """Test that WelcomeWidget open button is connected."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert hasattr(window._welcome, "open_clicked")

    def test_show_tabs_switches_stacked_widget(self) -> None:
        """Test show_tabs switches to tab widget page."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        window.show_tabs()
        assert window.stacked_widget.currentIndex() == 1

    def test_show_welcome_switches_stacked_widget(self) -> None:
        """Test show_welcome switches back to welcome page."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        window.show_tabs()
        window.show_welcome()
        assert window.stacked_widget.currentIndex() == 0
        assert window._page_label.text() == "No document"


class TestKPdfAppIntegration:
    """Tests for KPdfApp wiring with TabManager."""

    def test_app_creates_tab_manager(self) -> None:
        """Test that KPdfApp creates a TabManager instead of single presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert isinstance(kpdf.tab_manager, TabManager)
        kpdf.shutdown()

    def test_app_wires_file_open_to_tab_manager(self) -> None:
        """Test that file_open_requested routes to TabManager.open_file."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        spy = MagicMock()
        kpdf.tab_manager.open_file = spy  # type: ignore[method-assign]
        kpdf.window.file_open_requested.emit(Path("/tmp/test.pdf"))
        spy.assert_called_once_with(Path("/tmp/test.pdf"))
        kpdf.shutdown()

    def test_tab_count_zero_shows_welcome(self) -> None:
        """Test that tab_count_changed(0) switches to welcome screen."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        kpdf.window.show_tabs()
        assert kpdf.window.stacked_widget.currentIndex() == 1
        kpdf.tab_manager.tab_count_changed.emit(0)
        assert kpdf.window.stacked_widget.currentIndex() == 0
        kpdf.shutdown()

    def test_app_creates_navigation_presenter(self) -> None:
        """Test that KPdfApp creates a NavigationPresenter."""
        from k_pdf.presenters.navigation_presenter import NavigationPresenter

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert isinstance(kpdf.navigation_presenter, NavigationPresenter)
        kpdf.shutdown()
