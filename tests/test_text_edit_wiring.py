"""Tests that KPdfApp wires text editing correctly."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp


class TestKPdfAppTextEditing:
    def test_app_has_text_edit_presenter(self, qtbot) -> None:
        app = QApplication.instance()
        k_app = KPdfApp(app)
        qtbot.addWidget(k_app.window)
        assert hasattr(k_app, "_text_edit_presenter")
        k_app.shutdown()

    def test_app_has_find_replace_bar(self, qtbot) -> None:
        app = QApplication.instance()
        k_app = KPdfApp(app)
        qtbot.addWidget(k_app.window)
        assert hasattr(k_app.window, "find_replace_bar")
        k_app.shutdown()
