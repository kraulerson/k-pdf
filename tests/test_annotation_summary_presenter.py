"""Tests for AnnotationSummaryPresenter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
import pytest

from k_pdf.core.annotation_model import AnnotationInfo
from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.presenters.annotation_summary_presenter import AnnotationSummaryPresenter
from k_pdf.services.annotation_engine import AnnotationEngine


@pytest.fixture
def mock_tab_manager() -> MagicMock:
    manager = MagicMock()
    manager.active_session_id = "test-session"
    manager.get_active_presenter.return_value = MagicMock()
    return manager


@pytest.fixture
def mock_panel() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_engine() -> MagicMock:
    return MagicMock(spec=AnnotationEngine)


@pytest.fixture
def sample_model(tmp_path: Path) -> DocumentModel:
    path = tmp_path / "test.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1}")
    doc.save(str(path))
    doc.close()

    doc_handle = pymupdf.open(str(path))
    metadata = DocumentMetadata(
        file_path=path,
        page_count=3,
        title=None,
        author=None,
        has_forms=False,
        has_outline=False,
        has_javascript=False,
        is_encrypted=False,
        file_size_bytes=path.stat().st_size,
    )
    pages = [
        PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
        for i in range(3)
    ]
    return DocumentModel(
        file_path=path,
        doc_handle=doc_handle,
        metadata=metadata,
        pages=pages,
    )


class TestOnDocumentReady:
    def test_scans_pages_and_updates_panel(
        self,
        mock_tab_manager: MagicMock,
        mock_panel: MagicMock,
        mock_engine: MagicMock,
        sample_model: DocumentModel,
    ) -> None:
        presenter = AnnotationSummaryPresenter(
            tab_manager=mock_tab_manager,
            annotation_engine=mock_engine,
            panel=mock_panel,
        )
        # Mock engine: no annotations on any page
        mock_engine.get_annotations.return_value = []
        mock_tab_manager.active_session_id = "session-1"

        presenter.on_document_ready("session-1", sample_model)

        # Should call get_annotations for all 3 pages
        assert mock_engine.get_annotations.call_count == 3
        mock_panel.set_annotations.assert_called_once()

    def test_stores_per_tab_annotations(
        self,
        mock_tab_manager: MagicMock,
        mock_panel: MagicMock,
        mock_engine: MagicMock,
        sample_model: DocumentModel,
    ) -> None:
        presenter = AnnotationSummaryPresenter(
            tab_manager=mock_tab_manager,
            annotation_engine=mock_engine,
            panel=mock_panel,
        )
        mock_engine.get_annotations.return_value = []
        mock_tab_manager.active_session_id = "session-1"

        presenter.on_document_ready("session-1", sample_model)

        assert "session-1" in presenter._per_tab_annotations

    def test_with_annotations(
        self,
        mock_tab_manager: MagicMock,
        mock_panel: MagicMock,
        mock_engine: MagicMock,
        sample_model: DocumentModel,
    ) -> None:
        presenter = AnnotationSummaryPresenter(
            tab_manager=mock_tab_manager,
            annotation_engine=mock_engine,
            panel=mock_panel,
        )

        # Page 0 has 1 annotation, pages 1-2 have none
        mock_annot = MagicMock()
        mock_engine.get_annotations.side_effect = [
            [mock_annot],  # page 0
            [],  # page 1
            [],  # page 2
        ]
        mock_engine.get_annotation_info.return_value = {
            "type_name": "Highlight",
            "author": "Karl",
            "content": "",
            "color": (1.0, 1.0, 0.0),
            "rect": (72.0, 72.0, 200.0, 82.0),
        }
        mock_tab_manager.active_session_id = "session-1"

        presenter.on_document_ready("session-1", sample_model)

        mock_panel.set_annotations.assert_called_once()
        args = mock_panel.set_annotations.call_args[0][0]
        assert len(args) == 1
        assert args[0].page == 0
        assert args[0].ann_type == "Highlight"


class TestRefreshAnnotations:
    def test_rescans_and_updates_panel(
        self,
        mock_tab_manager: MagicMock,
        mock_panel: MagicMock,
        mock_engine: MagicMock,
        sample_model: DocumentModel,
    ) -> None:
        presenter = AnnotationSummaryPresenter(
            tab_manager=mock_tab_manager,
            annotation_engine=mock_engine,
            panel=mock_panel,
        )
        mock_tab_manager.active_session_id = "session-1"
        doc_presenter = mock_tab_manager.get_active_presenter.return_value
        doc_presenter.model = sample_model
        mock_engine.get_annotations.return_value = []

        presenter.refresh_annotations()

        mock_panel.set_annotations.assert_called_once()

    def test_no_active_model_clears_panel(
        self,
        mock_tab_manager: MagicMock,
        mock_panel: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        presenter = AnnotationSummaryPresenter(
            tab_manager=mock_tab_manager,
            annotation_engine=mock_engine,
            panel=mock_panel,
        )
        mock_tab_manager.get_active_presenter.return_value = None

        presenter.refresh_annotations()

        mock_panel.clear.assert_called_once()


class TestTabSwitch:
    def test_swaps_to_stored_annotations(
        self,
        mock_tab_manager: MagicMock,
        mock_panel: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        presenter = AnnotationSummaryPresenter(
            tab_manager=mock_tab_manager,
            annotation_engine=mock_engine,
            panel=mock_panel,
        )
        stored = [AnnotationInfo(page=0, ann_type="Highlight")]
        presenter._per_tab_annotations["session-2"] = stored

        presenter.on_tab_switched("session-2")

        mock_panel.set_annotations.assert_called_once_with(stored)

    def test_unknown_session_clears_panel(
        self,
        mock_tab_manager: MagicMock,
        mock_panel: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        presenter = AnnotationSummaryPresenter(
            tab_manager=mock_tab_manager,
            annotation_engine=mock_engine,
            panel=mock_panel,
        )

        presenter.on_tab_switched("unknown-session")

        mock_panel.clear.assert_called_once()


class TestTabClosed:
    def test_removes_stored_data(
        self,
        mock_tab_manager: MagicMock,
        mock_panel: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        presenter = AnnotationSummaryPresenter(
            tab_manager=mock_tab_manager,
            annotation_engine=mock_engine,
            panel=mock_panel,
        )
        presenter._per_tab_annotations["session-1"] = [AnnotationInfo(page=0, ann_type="Note")]

        presenter.on_tab_closed("session-1")

        assert "session-1" not in presenter._per_tab_annotations


class TestAnnotationClicked:
    def test_navigates_to_page(
        self,
        mock_tab_manager: MagicMock,
        mock_panel: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        presenter = AnnotationSummaryPresenter(
            tab_manager=mock_tab_manager,
            annotation_engine=mock_engine,
            panel=mock_panel,
        )
        mock_viewport = MagicMock()
        mock_tab_manager.get_active_viewport.return_value = mock_viewport

        presenter.on_annotation_clicked(5)

        mock_viewport.scroll_to_page.assert_called_once_with(5)

    def test_no_viewport_is_noop(
        self,
        mock_tab_manager: MagicMock,
        mock_panel: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        presenter = AnnotationSummaryPresenter(
            tab_manager=mock_tab_manager,
            annotation_engine=mock_engine,
            panel=mock_panel,
        )
        mock_tab_manager.get_active_viewport.return_value = None

        # Should not raise
        presenter.on_annotation_clicked(5)
