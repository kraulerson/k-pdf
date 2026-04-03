"""Integration tests for Printing (Ctrl+P) end-to-end wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.services.print_service import PrintResult

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_model(page_count: int = 3) -> DocumentModel:
    pages = [
        PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
        for i in range(page_count)
    ]
    metadata = DocumentMetadata(
        file_path=Path("/tmp/test.pdf"),
        page_count=page_count,
        title="Test",
        author=None,
        has_forms=False,
        has_outline=False,
        has_javascript=False,
        is_encrypted=False,
        file_size_bytes=1000,
    )
    return DocumentModel(
        file_path=Path("/tmp/test.pdf"),
        doc_handle=MagicMock(),
        metadata=metadata,
        pages=pages,
    )


class TestPrintActionState:
    def test_print_disabled_on_startup(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert not kpdf.window._print_action.isEnabled()
        kpdf.shutdown()

    def test_print_enabled_after_document_load(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        model = _make_model()
        kpdf._on_document_ready_print("session-1", model)

        assert kpdf.window._print_action.isEnabled()
        kpdf.shutdown()

    def test_print_disabled_after_all_tabs_closed(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        kpdf.window.set_print_enabled(True)
        kpdf.tab_manager.tab_count_changed.emit(0)

        assert not kpdf.window._print_action.isEnabled()
        kpdf.shutdown()


class TestPrintFlow:
    @patch("k_pdf.app.QPrintDialog")
    def test_print_flow_calls_service(self, mock_dialog_cls: MagicMock) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        model = _make_model(3)
        mock_presenter = MagicMock()
        mock_presenter.model = model
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )

        # Mock QPrintDialog to return Accepted
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = 1  # QDialog.DialogCode.Accepted
        mock_dialog_cls.return_value = mock_dialog

        kpdf._print_service.print_document = MagicMock(  # type: ignore[method-assign]
            return_value=PrintResult(success=True, pages_printed=3),
        )

        kpdf._on_print_requested()

        kpdf._print_service.print_document.assert_called_once()
        kpdf.shutdown()

    @patch("k_pdf.app.QPrintDialog")
    def test_print_cancelled_no_service_call(self, mock_dialog_cls: MagicMock) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        model = _make_model(3)
        mock_presenter = MagicMock()
        mock_presenter.model = model
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )

        # Mock QPrintDialog to return Rejected
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = 0  # QDialog.DialogCode.Rejected
        mock_dialog_cls.return_value = mock_dialog

        kpdf._print_service.print_document = MagicMock(  # type: ignore[method-assign]
            return_value=PrintResult(success=True, pages_printed=3),
        )

        kpdf._on_print_requested()

        kpdf._print_service.print_document.assert_not_called()
        kpdf.shutdown()

    @patch("k_pdf.app.QPrintDialog")
    @patch.object(KPdfApp, "_show_print_error")
    def test_print_error_shows_dialog(
        self,
        mock_show_error: MagicMock,
        mock_dialog_cls: MagicMock,
    ) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        model = _make_model(3)
        mock_presenter = MagicMock()
        mock_presenter.model = model
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = 1
        mock_dialog_cls.return_value = mock_dialog

        kpdf._print_service.print_document = MagicMock(  # type: ignore[method-assign]
            return_value=PrintResult(success=False, pages_printed=0, error_message="Out of paper"),
        )

        kpdf._on_print_requested()

        mock_show_error.assert_called_once_with("Out of paper")
        kpdf.shutdown()

    @patch("k_pdf.app.QPrintDialog")
    def test_print_status_bar_shows_completion(self, mock_dialog_cls: MagicMock) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        model = _make_model(3)
        mock_presenter = MagicMock()
        mock_presenter.model = model
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = 1
        mock_dialog_cls.return_value = mock_dialog

        kpdf._print_service.print_document = MagicMock(  # type: ignore[method-assign]
            return_value=PrintResult(success=True, pages_printed=3),
        )

        kpdf._on_print_requested()

        # Status bar should show completion message
        status = kpdf.window._status_bar.currentMessage()
        assert "complete" in status.lower() or "Printing" in status

        kpdf.shutdown()

    def test_print_no_document_does_nothing(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        # No presenter / no model
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=None,
        )
        kpdf._print_service.print_document = MagicMock(  # type: ignore[method-assign]
            return_value=PrintResult(success=True, pages_printed=0),
        )

        # Should not raise
        kpdf._on_print_requested()

        kpdf._print_service.print_document.assert_not_called()
        kpdf.shutdown()


class TestPrintServiceAttribute:
    def test_app_has_print_service(self) -> None:
        from k_pdf.services.print_service import PrintService

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert isinstance(kpdf._print_service, PrintService)
        kpdf.shutdown()
