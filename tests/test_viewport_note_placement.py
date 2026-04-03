"""Tests for PdfViewport sticky note and text box placement modes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QGraphicsView

from k_pdf.core.annotation_model import ToolMode
from k_pdf.views.pdf_viewport import PdfViewport

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestToolModeOnViewport:
    def test_default_mode_is_none(self) -> None:
        viewport = PdfViewport()
        assert viewport._tool_mode is ToolMode.NONE

    def test_set_tool_mode_sticky_note(self) -> None:
        viewport = PdfViewport()
        viewport.set_tool_mode(ToolMode.STICKY_NOTE)
        assert viewport._tool_mode is ToolMode.STICKY_NOTE

    def test_set_tool_mode_text_box(self) -> None:
        viewport = PdfViewport()
        viewport.set_tool_mode(ToolMode.TEXT_BOX)
        assert viewport._tool_mode is ToolMode.TEXT_BOX

    def test_sticky_note_mode_sets_crosshair_cursor(self) -> None:
        viewport = PdfViewport()
        viewport.set_tool_mode(ToolMode.STICKY_NOTE)
        assert viewport.cursor().shape() == Qt.CursorShape.CrossCursor

    def test_text_box_mode_sets_crosshair_cursor(self) -> None:
        viewport = PdfViewport()
        viewport.set_tool_mode(ToolMode.TEXT_BOX)
        assert viewport.cursor().shape() == Qt.CursorShape.CrossCursor

    def test_none_mode_restores_drag(self) -> None:
        viewport = PdfViewport()
        viewport.set_tool_mode(ToolMode.STICKY_NOTE)
        viewport.set_tool_mode(ToolMode.NONE)
        assert viewport.dragMode() == QGraphicsView.DragMode.ScrollHandDrag

    def test_text_select_mode_sets_ibeam(self) -> None:
        viewport = PdfViewport()
        viewport.set_tool_mode(ToolMode.TEXT_SELECT)
        assert viewport.cursor().shape() == Qt.CursorShape.IBeamCursor


class TestNotePlacedSignal:
    def test_signal_exists(self) -> None:
        viewport = PdfViewport()
        assert hasattr(viewport, "note_placed")

    def test_textbox_drawn_signal_exists(self) -> None:
        viewport = PdfViewport()
        assert hasattr(viewport, "textbox_drawn")

    def test_annotation_double_clicked_signal_exists(self) -> None:
        viewport = PdfViewport()
        assert hasattr(viewport, "annotation_double_clicked")


class TestSetSelectionModeCompat:
    def test_set_selection_mode_true_sets_text_select(self) -> None:
        viewport = PdfViewport()
        viewport.set_selection_mode(True)
        assert viewport._tool_mode is ToolMode.TEXT_SELECT

    def test_set_selection_mode_false_sets_none(self) -> None:
        viewport = PdfViewport()
        viewport.set_selection_mode(True)
        viewport.set_selection_mode(False)
        assert viewport._tool_mode is ToolMode.NONE
