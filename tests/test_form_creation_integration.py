"""Integration tests for form field creation wiring."""

from __future__ import annotations

from k_pdf.core.annotation_model import ToolMode
from k_pdf.views.main_window import MainWindow
from k_pdf.views.pdf_viewport import PdfViewport


class TestViewportFormFieldSignal:
    """Tests for form field placement signal on PdfViewport."""

    def test_viewport_has_form_field_placed_signal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Verify form_field_placed signal exists on PdfViewport."""
        vp = PdfViewport()
        qtbot.addWidget(vp)
        assert hasattr(vp, "form_field_placed")

    def test_viewport_handles_form_tool_modes(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Verify viewport accepts FORM_TEXT tool mode."""
        vp = PdfViewport()
        qtbot.addWidget(vp)
        vp.set_tool_mode(ToolMode.FORM_TEXT)
        assert vp._tool_mode is ToolMode.FORM_TEXT


class TestMainWindowFormMenu:
    """Tests for form field signals and menu items on MainWindow."""

    def test_form_field_signals_exist(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Verify all form field signals exist on MainWindow."""
        win = MainWindow()
        qtbot.addWidget(win)
        assert hasattr(win, "form_text_field_requested")
        assert hasattr(win, "form_checkbox_requested")
        assert hasattr(win, "form_dropdown_requested")
        assert hasattr(win, "form_radio_requested")
        assert hasattr(win, "form_signature_requested")

    def test_has_form_properties_panel(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Verify MainWindow has form_properties_panel property."""
        win = MainWindow()
        qtbot.addWidget(win)
        assert hasattr(win, "form_properties_panel")
        assert win.form_properties_panel is not None

    def test_form_tools_disabled_initially(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Verify form tools start disabled."""
        win = MainWindow()
        qtbot.addWidget(win)
        assert not win._form_text_action.isEnabled()
        assert not win._form_checkbox_action.isEnabled()

    def test_set_form_tools_enabled(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Verify set_form_tools_enabled toggles all form actions."""
        win = MainWindow()
        qtbot.addWidget(win)
        win.set_form_tools_enabled(True)
        assert win._form_text_action.isEnabled()
        assert win._form_checkbox_action.isEnabled()
        assert win._form_dropdown_action.isEnabled()
        assert win._form_radio_action.isEnabled()
        assert win._form_signature_action.isEnabled()
        assert win._text_edit_action.isEnabled()
