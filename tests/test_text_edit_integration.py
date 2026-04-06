"""Integration tests for text editing wiring."""

from __future__ import annotations

from k_pdf.core.annotation_model import ToolMode
from k_pdf.views.pdf_viewport import PdfViewport


class TestViewportTextEditMode:
    def test_viewport_has_text_edit_requested_signal(self, qtbot) -> None:
        vp = PdfViewport()
        qtbot.addWidget(vp)
        assert hasattr(vp, "text_edit_requested")

    def test_viewport_handles_text_edit_mode(self, qtbot) -> None:
        vp = PdfViewport()
        qtbot.addWidget(vp)
        vp.set_tool_mode(ToolMode.TEXT_EDIT)
        assert vp._tool_mode is ToolMode.TEXT_EDIT
