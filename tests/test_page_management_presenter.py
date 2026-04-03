"""Tests for PageManagementPresenter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf
import pytest

from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.core.page_model import PageOperation, PageOperationResult
from k_pdf.presenters.page_management_presenter import PageManagementPresenter
from k_pdf.services.page_engine import PageEngine


@pytest.fixture
def mock_tab_manager() -> MagicMock:
    manager = MagicMock()
    manager.active_session_id = "test-session"
    manager.get_active_presenter.return_value = MagicMock()
    return manager


@pytest.fixture
def mock_panel() -> MagicMock:
    panel = MagicMock()
    panel.get_selected_pages.return_value = []
    return panel


@pytest.fixture
def mock_engine() -> MagicMock:
    return MagicMock(spec=PageEngine)


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


class TestRotatePages:
    def test_rotate_calls_engine(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        mock_engine.rotate_pages.return_value = PageOperationResult(
            operation=PageOperation.ROTATE,
            success=True,
            new_page_count=3,
            affected_pages=[0, 1],
        )
        mock_engine.render_thumbnail.return_value = MagicMock()

        presenter.rotate_pages([0, 1], 90)

        mock_engine.rotate_pages.assert_called_once_with(model.doc_handle, [0, 1], 90)

    def test_rotate_sets_dirty(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        mock_engine.rotate_pages.return_value = PageOperationResult(
            operation=PageOperation.ROTATE,
            success=True,
            new_page_count=3,
            affected_pages=[0],
        )
        mock_engine.render_thumbnail.return_value = MagicMock()

        presenter.rotate_pages([0], 90)

        assert model.dirty is True

    def test_rotate_no_model_noop(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        mock_tab_manager.get_active_presenter.return_value = None

        presenter.rotate_pages([0], 90)

        mock_engine.rotate_pages.assert_not_called()

    def test_rotate_empty_indices_noop(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        mock_tab_manager.get_active_presenter.return_value.model = model

        presenter.rotate_pages([], 90)

        mock_engine.rotate_pages.assert_not_called()


class TestDeletePages:
    def test_delete_calls_engine_on_confirm(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        mock_engine.delete_pages.return_value = PageOperationResult(
            operation=PageOperation.DELETE,
            success=True,
            new_page_count=2,
            affected_pages=[1],
        )
        mock_engine.get_page_count.return_value = 2
        mock_engine.render_thumbnail.return_value = MagicMock()

        with patch("k_pdf.presenters.page_management_presenter.QMessageBox") as mock_msgbox:
            mock_msgbox.StandardButton.Yes = 1
            mock_msgbox.StandardButton.No = 0
            mock_msgbox.question.return_value = 1  # Yes

            presenter.delete_pages([1])

        mock_engine.delete_pages.assert_called_once_with(model.doc_handle, [1])

    def test_delete_cancelled_on_no(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        with patch("k_pdf.presenters.page_management_presenter.QMessageBox") as mock_msgbox:
            mock_msgbox.StandardButton.Yes = 1
            mock_msgbox.StandardButton.No = 0
            mock_msgbox.question.return_value = 0  # No

            presenter.delete_pages([1])

        mock_engine.delete_pages.assert_not_called()

    def test_delete_blocked_when_all_pages(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        doc_presenter = mock_tab_manager.get_active_presenter.return_value
        doc_presenter.model = model

        mock_engine.delete_pages.return_value = PageOperationResult(
            operation=PageOperation.DELETE,
            success=False,
            new_page_count=3,
            affected_pages=[0, 1, 2],
            error_message="Cannot delete all pages. A PDF must contain at least one page.",
        )

        with patch("k_pdf.presenters.page_management_presenter.QMessageBox") as mock_msgbox:
            mock_msgbox.StandardButton.Yes = 1
            mock_msgbox.StandardButton.No = 0
            mock_msgbox.question.return_value = 1  # Yes

            presenter.delete_pages([0, 1, 2])

        assert model.dirty is False


class TestInsertPages:
    def test_insert_calls_engine(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        mock_engine.insert_pages_from.return_value = PageOperationResult(
            operation=PageOperation.INSERT,
            success=True,
            new_page_count=5,
            affected_pages=[2, 3],
        )
        mock_engine.get_page_count.return_value = 5
        mock_engine.render_thumbnail.return_value = MagicMock()

        presenter.insert_pages(Path("/fake/source.pdf"), 2)

        mock_engine.insert_pages_from.assert_called_once()

    def test_insert_sets_dirty(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        mock_engine.insert_pages_from.return_value = PageOperationResult(
            operation=PageOperation.INSERT,
            success=True,
            new_page_count=5,
            affected_pages=[2, 3],
        )
        mock_engine.get_page_count.return_value = 5
        mock_engine.render_thumbnail.return_value = MagicMock()

        presenter.insert_pages(Path("/fake/source.pdf"), 2)

        assert model.dirty is True


class TestMovePage:
    def test_move_calls_engine(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        mock_engine.move_page.return_value = PageOperationResult(
            operation=PageOperation.MOVE,
            success=True,
            new_page_count=3,
            affected_pages=[0, 2],
        )
        mock_engine.get_page_count.return_value = 3
        mock_engine.render_thumbnail.return_value = MagicMock()

        presenter.move_page(0, 2)

        mock_engine.move_page.assert_called_once_with(model.doc_handle, 0, 2)

    def test_move_same_position_is_noop(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        presenter.move_page(2, 2)

        mock_engine.move_page.assert_not_called()
        assert model.dirty is False


class TestTabLifecycle:
    def test_on_tab_switched_refreshes_panel(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        mock_tab_manager.get_active_presenter.return_value.model = model
        mock_engine.get_page_count.return_value = 3
        mock_engine.render_thumbnail.return_value = MagicMock()

        presenter.on_tab_switched("new-session")

        mock_panel.set_thumbnails.assert_called_once()
        mock_panel.set_buttons_enabled.assert_called_with(True)

    def test_on_tab_switched_no_document(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        mock_tab_manager.get_active_presenter.return_value = None

        presenter.on_tab_switched("new-session")

        mock_panel.set_thumbnails.assert_called_with([])
        mock_panel.set_buttons_enabled.assert_called_with(False)

    def test_on_tab_closed_clears_panel(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        mock_tab_manager.get_active_presenter.return_value = None

        presenter.on_tab_closed("closed-session")

        mock_panel.set_thumbnails.assert_called_with([])
        mock_panel.set_buttons_enabled.assert_called_with(False)
