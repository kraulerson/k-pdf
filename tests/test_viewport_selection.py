"""Tests for PdfViewport text selection mode."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QGraphicsView

from k_pdf.core.document_model import PageInfo
from k_pdf.views.pdf_viewport import PdfViewport

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestSelectionModeToggle:
    def test_default_is_not_selection_mode(self) -> None:
        viewport = PdfViewport()
        assert viewport.selection_mode is False

    def test_set_selection_mode_true(self) -> None:
        viewport = PdfViewport()
        viewport.set_selection_mode(True)
        assert viewport.selection_mode is True

    def test_set_selection_mode_false(self) -> None:
        viewport = PdfViewport()
        viewport.set_selection_mode(True)
        viewport.set_selection_mode(False)
        assert viewport.selection_mode is False

    def test_selection_mode_true_changes_cursor_to_ibeam(self) -> None:
        viewport = PdfViewport()
        viewport.set_selection_mode(True)
        assert viewport.cursor().shape() == Qt.CursorShape.IBeamCursor

    def test_selection_mode_false_restores_drag_mode(self) -> None:
        viewport = PdfViewport()
        viewport.set_selection_mode(True)
        viewport.set_selection_mode(False)
        assert viewport.dragMode() == QGraphicsView.DragMode.ScrollHandDrag

    def test_selection_mode_true_disables_drag(self) -> None:
        viewport = PdfViewport()
        viewport.set_selection_mode(True)
        assert viewport.dragMode() == QGraphicsView.DragMode.NoDrag


class TestSelectionOverlay:
    def test_clear_selection_overlay_no_crash(self) -> None:
        viewport = PdfViewport()
        viewport.clear_selection_overlay()
        # Should not raise even with no overlays

    def test_set_selection_mode_false_clears_overlay(self) -> None:
        viewport = PdfViewport()
        pages = [
            PageInfo(
                index=0,
                width=612,
                height=792,
                rotation=0,
                has_text=True,
                annotation_count=0,
            ),
        ]
        viewport.set_document(pages)
        viewport.set_selection_mode(True)
        # Add a fake overlay rect
        viewport._selection_overlays.append(viewport._scene.addRect(0, 0, 50, 10))
        assert len(viewport._selection_overlays) == 1
        viewport.set_selection_mode(False)
        assert len(viewport._selection_overlays) == 0


class TestTextSelectedSignal:
    def test_text_selected_signal_exists(self) -> None:
        viewport = PdfViewport()
        # Verify the signal is present (does not raise AttributeError)
        assert hasattr(viewport, "text_selected")

    def test_annotation_context_signal_exists(self) -> None:
        viewport = PdfViewport()
        assert hasattr(viewport, "annotation_delete_requested")


class TestAnnotationEngineAccessor:
    def test_set_annotation_engine(self) -> None:
        viewport = PdfViewport()
        from unittest.mock import MagicMock

        mock_engine = MagicMock()
        viewport.set_annotation_engine(mock_engine)
        assert viewport._annotation_engine is mock_engine

    def test_set_doc_handle(self) -> None:
        viewport = PdfViewport()
        from unittest.mock import MagicMock

        mock_handle = MagicMock()
        viewport.set_doc_handle(mock_handle)
        assert viewport._doc_handle is mock_handle
