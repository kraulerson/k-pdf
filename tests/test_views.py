"""Integration tests for MainWindow and PdfViewport."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from k_pdf.core.document_model import PageInfo
from k_pdf.views.main_window import MainWindow
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


class TestMainWindow:
    """Tests for MainWindow signals and dialogs."""

    def test_file_open_requested_signal(self) -> None:
        """Test that file_open_requested signal can be emitted and received."""
        window = MainWindow()
        spy = MagicMock()
        window.file_open_requested.connect(spy)

        # Simulate emitting directly (dialog is modal, can't test via UI)
        window.file_open_requested.emit(Path("/tmp/test.pdf"))

        spy.assert_called_once_with(Path("/tmp/test.pdf"))

    def test_update_page_status(self) -> None:
        """Test status bar page label updates."""
        window = MainWindow()
        window.update_page_status(3, 10)
        assert window._page_label.text() == "Page 3 of 10"
