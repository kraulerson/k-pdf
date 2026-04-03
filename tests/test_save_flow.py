"""Tests for save flow integration through KPdfApp."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QMessageBox

from k_pdf.app import KPdfApp
from k_pdf.presenters.form_presenter import FormPresenter
from k_pdf.services.form_engine import FormEngine

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestSaveFlowWiring:
    def test_app_has_form_presenter(self) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        assert hasattr(kapp, "_form_presenter")
        assert isinstance(kapp._form_presenter, FormPresenter)
        kapp.shutdown()

    def test_app_has_form_engine(self) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        assert hasattr(kapp, "_form_engine")
        assert isinstance(kapp._form_engine, FormEngine)
        kapp.shutdown()

    def test_save_requested_signal_connected(self) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        # Verify save_requested is wired (no error on emit with no tab)
        kapp.window.save_requested.emit()
        kapp.shutdown()

    def test_save_as_requested_signal_connected(self) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        # Should not crash even with no active session
        kapp._on_save_as_requested()
        kapp.shutdown()

    def test_form_detected_shows_status_message(self) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        spy = MagicMock()
        kapp.window.statusBar().showMessage = spy
        kapp._form_presenter.form_detected.emit(5)
        spy.assert_called_once()
        msg = spy.call_args[0][0]
        assert "5 form fields" in msg
        kapp.shutdown()

    def test_xfa_detected_shows_status_message(self) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        spy = MagicMock()
        kapp.window.statusBar().showMessage = spy
        kapp._form_presenter.xfa_detected.emit("XFA not supported")
        spy.assert_called_once()
        msg = spy.call_args[0][0]
        assert "XFA" in msg
        kapp.shutdown()

    def test_save_failed_shows_error(self) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        with patch.object(kapp.window, "show_error") as mock_err:
            kapp._form_presenter.save_failed.emit("Cannot save to /path")
            mock_err.assert_called_once_with("Save Failed", "Cannot save to /path")
        kapp.shutdown()

    def test_save_succeeded_shows_status(self) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        spy = MagicMock()
        kapp.window.statusBar().showMessage = spy
        kapp._form_presenter.save_succeeded.emit()
        spy.assert_called()
        msgs = [call[0][0] for call in spy.call_args_list]
        assert any("saved" in m.lower() for m in msgs)
        kapp.shutdown()


class TestCloseGuardDialog:
    def test_discard_force_closes_tab(self) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)

        # Setup mock tab context
        mock_ctx = MagicMock()
        mock_ctx.presenter.model.dirty = False  # after discard
        kapp._tab_manager._tabs["test-sid"] = mock_ctx
        kapp._tab_manager.force_close_tab = MagicMock()

        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Discard):
            kapp._on_close_guard("test-sid")
            kapp._tab_manager.force_close_tab.assert_called_once_with("test-sid")

        kapp.shutdown()

    def test_cancel_keeps_tab_open(self) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)

        kapp._tab_manager._tabs["test-sid"] = MagicMock()
        kapp._tab_manager.force_close_tab = MagicMock()

        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Cancel):
            kapp._on_close_guard("test-sid")
            kapp._tab_manager.force_close_tab.assert_not_called()

        kapp.shutdown()
