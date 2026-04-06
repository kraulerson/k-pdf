"""Tests that KPdfApp wires form creation presenter correctly."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp


class TestKPdfAppFormCreation:
    """Verify form creation presenter is wired into KPdfApp."""

    def test_app_has_form_creation_presenter(self, qtbot) -> None:
        """KPdfApp should instantiate a FormCreationPresenter."""
        app = QApplication.instance()
        k_app = KPdfApp(app)
        qtbot.addWidget(k_app.window)
        assert hasattr(k_app, "_form_creation_presenter")
        k_app.shutdown()

    def test_form_tools_disabled_initially(self, qtbot) -> None:
        """Form creation tools should be disabled before any document loads."""
        app = QApplication.instance()
        k_app = KPdfApp(app)
        qtbot.addWidget(k_app.window)
        assert not k_app.window._form_text_action.isEnabled()
        k_app.shutdown()
