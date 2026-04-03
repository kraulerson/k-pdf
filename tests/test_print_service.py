"""Tests for PrintService — renders PDF pages to QPrinter."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage

from k_pdf.services.print_service import PrintResult, PrintService


@pytest.fixture
def print_service() -> PrintService:
    return PrintService()


@pytest.fixture
def mock_pdf_engine() -> MagicMock:
    engine = MagicMock()
    # Default: render_page returns a 100x100 QImage
    engine.render_page.return_value = QImage(100, 100, QImage.Format.Format_RGB888)
    return engine


@pytest.fixture
def mock_printer() -> MagicMock:
    printer = MagicMock()
    printer.fromPage.return_value = 0
    printer.toPage.return_value = 0
    printer.pageRect.return_value = QRectF(0, 0, 2550, 3300)  # 8.5x11 @ 300dpi
    printer.newPage.return_value = True
    return printer


@pytest.fixture
def mock_doc_handle() -> MagicMock:
    return MagicMock()


class TestPrintResult:
    def test_success_result_fields(self) -> None:
        result = PrintResult(success=True, pages_printed=3, error_message="")
        assert result.success is True
        assert result.pages_printed == 3
        assert result.error_message == ""

    def test_failure_result_fields(self) -> None:
        result = PrintResult(success=False, pages_printed=0, error_message="Printer error")
        assert result.success is False
        assert result.pages_printed == 0
        assert result.error_message == "Printer error"

    def test_result_is_frozen(self) -> None:
        result = PrintResult(success=True, pages_printed=1, error_message="")
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]


class TestPrintAllPages:
    @patch("k_pdf.services.print_service.QPainter")
    def test_print_all_pages_renders_every_page(
        self,
        mock_painter_cls: MagicMock,
        print_service: PrintService,
        mock_printer: MagicMock,
        mock_pdf_engine: MagicMock,
        mock_doc_handle: MagicMock,
    ) -> None:
        mock_painter = MagicMock()
        mock_painter.begin.return_value = True
        mock_painter_cls.return_value = mock_painter

        result = print_service.print_document(
            printer=mock_printer,
            doc_handle=mock_doc_handle,
            page_count=3,
            pdf_engine=mock_pdf_engine,
        )

        assert result.success is True
        assert result.pages_printed == 3
        assert mock_pdf_engine.render_page.call_count == 3

    @patch("k_pdf.services.print_service.QPainter")
    def test_print_all_pages_calls_new_page_between_pages(
        self,
        mock_painter_cls: MagicMock,
        print_service: PrintService,
        mock_printer: MagicMock,
        mock_pdf_engine: MagicMock,
        mock_doc_handle: MagicMock,
    ) -> None:
        mock_painter = MagicMock()
        mock_painter.begin.return_value = True
        mock_painter_cls.return_value = mock_painter

        print_service.print_document(
            printer=mock_printer,
            doc_handle=mock_doc_handle,
            page_count=3,
            pdf_engine=mock_pdf_engine,
        )

        # newPage called between pages (2 times for 3 pages)
        assert mock_printer.newPage.call_count == 2


class TestPrintPageRange:
    @patch("k_pdf.services.print_service.QPainter")
    def test_print_page_range(
        self,
        mock_painter_cls: MagicMock,
        print_service: PrintService,
        mock_printer: MagicMock,
        mock_pdf_engine: MagicMock,
        mock_doc_handle: MagicMock,
    ) -> None:
        mock_painter = MagicMock()
        mock_painter.begin.return_value = True
        mock_painter_cls.return_value = mock_painter

        # QPrinter uses 1-based page numbers
        mock_printer.fromPage.return_value = 2
        mock_printer.toPage.return_value = 3

        result = print_service.print_document(
            printer=mock_printer,
            doc_handle=mock_doc_handle,
            page_count=3,
            pdf_engine=mock_pdf_engine,
        )

        assert result.success is True
        assert result.pages_printed == 2
        # Rendered pages 1 and 2 (0-based) i.e. pages 2 and 3 (1-based)
        render_calls = mock_pdf_engine.render_page.call_args_list
        assert render_calls[0] == call(mock_doc_handle, 1, zoom=pytest.approx(4.1667, abs=0.001))
        assert render_calls[1] == call(mock_doc_handle, 2, zoom=pytest.approx(4.1667, abs=0.001))

    @patch("k_pdf.services.print_service.QPainter")
    def test_print_single_page(
        self,
        mock_painter_cls: MagicMock,
        print_service: PrintService,
        mock_printer: MagicMock,
        mock_pdf_engine: MagicMock,
        mock_doc_handle: MagicMock,
    ) -> None:
        mock_painter = MagicMock()
        mock_painter.begin.return_value = True
        mock_painter_cls.return_value = mock_painter

        mock_printer.fromPage.return_value = 1
        mock_printer.toPage.return_value = 1

        result = print_service.print_document(
            printer=mock_printer,
            doc_handle=mock_doc_handle,
            page_count=3,
            pdf_engine=mock_pdf_engine,
        )

        assert result.success is True
        assert result.pages_printed == 1
        # No newPage called for single page
        mock_printer.newPage.assert_not_called()


class TestProgressCallback:
    @patch("k_pdf.services.print_service.QPainter")
    def test_progress_callback_invoked(
        self,
        mock_painter_cls: MagicMock,
        print_service: PrintService,
        mock_printer: MagicMock,
        mock_pdf_engine: MagicMock,
        mock_doc_handle: MagicMock,
    ) -> None:
        mock_painter = MagicMock()
        mock_painter.begin.return_value = True
        mock_painter_cls.return_value = mock_painter

        callback = MagicMock()

        print_service.print_document(
            printer=mock_printer,
            doc_handle=mock_doc_handle,
            page_count=3,
            pdf_engine=mock_pdf_engine,
            progress_callback=callback,
        )

        assert callback.call_count == 3
        callback.assert_any_call(1, 3)
        callback.assert_any_call(2, 3)
        callback.assert_any_call(3, 3)


class TestPrintErrors:
    @patch("k_pdf.services.print_service.QPainter")
    def test_render_failure_returns_error(
        self,
        mock_painter_cls: MagicMock,
        print_service: PrintService,
        mock_printer: MagicMock,
        mock_pdf_engine: MagicMock,
        mock_doc_handle: MagicMock,
    ) -> None:
        mock_painter = MagicMock()
        mock_painter.begin.return_value = True
        mock_painter_cls.return_value = mock_painter

        mock_pdf_engine.render_page.side_effect = RuntimeError("Render failed")

        result = print_service.print_document(
            printer=mock_printer,
            doc_handle=mock_doc_handle,
            page_count=3,
            pdf_engine=mock_pdf_engine,
        )

        assert result.success is False
        assert "Render failed" in result.error_message
        assert result.pages_printed == 0

    @patch("k_pdf.services.print_service.QPainter")
    def test_painter_begin_failure_returns_error(
        self,
        mock_painter_cls: MagicMock,
        print_service: PrintService,
        mock_printer: MagicMock,
        mock_pdf_engine: MagicMock,
        mock_doc_handle: MagicMock,
    ) -> None:
        mock_painter = MagicMock()
        mock_painter.begin.return_value = False
        mock_painter_cls.return_value = mock_painter

        result = print_service.print_document(
            printer=mock_printer,
            doc_handle=mock_doc_handle,
            page_count=3,
            pdf_engine=mock_pdf_engine,
        )

        assert result.success is False
        assert result.pages_printed == 0
        assert "painter" in result.error_message.lower() or "begin" in result.error_message.lower()


class TestPrintZoom:
    @patch("k_pdf.services.print_service.QPainter")
    def test_renders_at_300_dpi_zoom(
        self,
        mock_painter_cls: MagicMock,
        print_service: PrintService,
        mock_printer: MagicMock,
        mock_pdf_engine: MagicMock,
        mock_doc_handle: MagicMock,
    ) -> None:
        mock_painter = MagicMock()
        mock_painter.begin.return_value = True
        mock_painter_cls.return_value = mock_painter

        mock_printer.fromPage.return_value = 1
        mock_printer.toPage.return_value = 1

        print_service.print_document(
            printer=mock_printer,
            doc_handle=mock_doc_handle,
            page_count=1,
            pdf_engine=mock_pdf_engine,
        )

        # 300 / 72 = 4.1666...
        _, kwargs = mock_pdf_engine.render_page.call_args
        assert kwargs["zoom"] == pytest.approx(300 / 72, abs=0.001)
