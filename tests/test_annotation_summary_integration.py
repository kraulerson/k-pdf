"""Integration tests for annotation summary panel (Feature 12)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.presenters.annotation_summary_presenter import AnnotationSummaryPresenter
from k_pdf.services.annotation_engine import AnnotationEngine
from k_pdf.views.annotation_panel import AnnotationSummaryPanel

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestAnnotationSummaryIntegration:
    def test_app_has_annotation_summary_presenter(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert isinstance(kpdf.annotation_summary_presenter, AnnotationSummaryPresenter)
        kpdf.shutdown()

    def test_annotation_panel_exists_on_window(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert isinstance(kpdf.window.annotation_summary_panel, AnnotationSummaryPanel)
        kpdf.shutdown()

    def test_panel_starts_hidden(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert not kpdf.window.annotation_summary_panel.isVisible()
        kpdf.shutdown()

    def test_annotation_created_refreshes_panel(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        # Mock the refresh call
        spy = MagicMock()
        kpdf.annotation_summary_presenter.refresh_annotations = spy  # type: ignore[method-assign]
        # Emit annotation_created
        kpdf.annotation_presenter.annotation_created.emit()
        spy.assert_called_once()
        kpdf.shutdown()

    def test_annotation_deleted_refreshes_panel(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        spy = MagicMock()
        kpdf.annotation_summary_presenter.refresh_annotations = spy  # type: ignore[method-assign]
        kpdf.annotation_presenter.annotation_deleted.emit()
        spy.assert_called_once()
        kpdf.shutdown()

    def test_tab_switched_updates_panel(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        spy = MagicMock()
        kpdf.annotation_summary_presenter.on_tab_switched = spy  # type: ignore[method-assign]
        kpdf.tab_manager.tab_switched.emit("test-session")
        # tab_switched is connected to multiple handlers; just verify ours was called
        spy.assert_called()
        kpdf.shutdown()

    def test_tab_closed_cleans_up(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        spy = MagicMock()
        kpdf.annotation_summary_presenter.on_tab_closed = spy  # type: ignore[method-assign]
        kpdf.tab_manager.tab_closed.emit("test-session")
        spy.assert_called_with("test-session")
        kpdf.shutdown()

    def test_click_navigates_to_page(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        spy = MagicMock()
        kpdf.annotation_summary_presenter.on_annotation_clicked = spy  # type: ignore[method-assign]
        kpdf.window.annotation_summary_panel.annotation_clicked.emit(3)
        spy.assert_called_once_with(3)
        kpdf.shutdown()


class TestAnnotationScanIntegration:
    def test_scan_annotations_from_real_pdf(self, annotatable_pdf: Path) -> None:
        """Scan annotations from a real PDF with actual annotations."""
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))

        # Add annotations to the PDF
        page0 = doc[0]
        words = page0.get_text("words")
        quads = [pymupdf.Rect(*w[:4]).quad for w in words[:2]]
        page0.add_highlight_annot(quads=quads)
        page0.add_text_annot((100, 200), "A note", icon="Note")

        page1 = doc[1]
        words1 = page1.get_text("words")
        quads1 = [pymupdf.Rect(*w[:4]).quad for w in words1[:1]]
        page1.add_underline_annot(quads=quads1)

        # Build model
        metadata = DocumentMetadata(
            file_path=annotatable_pdf,
            page_count=doc.page_count,
            title=None,
            author=None,
            has_forms=False,
            has_outline=False,
            has_javascript=False,
            is_encrypted=False,
            file_size_bytes=annotatable_pdf.stat().st_size,
        )
        pages = [
            PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
            for i in range(doc.page_count)
        ]
        model = DocumentModel(
            file_path=annotatable_pdf,
            doc_handle=doc,
            metadata=metadata,
            pages=pages,
        )

        # Create presenter with mock panel
        mock_tab_manager = MagicMock()
        mock_tab_manager.active_session_id = "test"
        mock_panel = MagicMock()

        presenter = AnnotationSummaryPresenter(
            tab_manager=mock_tab_manager,
            annotation_engine=engine,
            panel=mock_panel,
        )

        presenter.on_document_ready("test", model)

        # Should have been called with 3 annotations
        mock_panel.set_annotations.assert_called_once()
        annotations = mock_panel.set_annotations.call_args[0][0]
        assert len(annotations) == 3

        # Check types
        types = {a.ann_type for a in annotations}
        assert "Highlight" in types
        assert "Note" in types
        assert "Underline" in types

        # Check pages
        pages_found = {a.page for a in annotations}
        assert 0 in pages_found
        assert 1 in pages_found

        doc.close()

    def test_empty_document_shows_empty(self, annotatable_pdf: Path) -> None:
        """Document with no annotations shows empty state."""
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))

        metadata = DocumentMetadata(
            file_path=annotatable_pdf,
            page_count=doc.page_count,
            title=None,
            author=None,
            has_forms=False,
            has_outline=False,
            has_javascript=False,
            is_encrypted=False,
            file_size_bytes=annotatable_pdf.stat().st_size,
        )
        pages = [
            PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
            for i in range(doc.page_count)
        ]
        model = DocumentModel(
            file_path=annotatable_pdf,
            doc_handle=doc,
            metadata=metadata,
            pages=pages,
        )

        mock_tab_manager = MagicMock()
        mock_tab_manager.active_session_id = "test"
        mock_panel = MagicMock()

        presenter = AnnotationSummaryPresenter(
            tab_manager=mock_tab_manager,
            annotation_engine=engine,
            panel=mock_panel,
        )

        presenter.on_document_ready("test", model)

        mock_panel.set_annotations.assert_called_once()
        annotations = mock_panel.set_annotations.call_args[0][0]
        assert len(annotations) == 0

        doc.close()
