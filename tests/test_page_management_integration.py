"""Integration tests for Feature 9: Page Management."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf
import pytest
from PySide6.QtWidgets import QApplication

from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.presenters.page_management_presenter import PageManagementPresenter
from k_pdf.services.page_engine import PageEngine

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists for QPixmap creation."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


@pytest.fixture
def multi_page_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "multi.pdf"
    doc = pymupdf.open()
    for i in range(5):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1} content")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def source_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "source.pdf"
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Source {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def engine() -> PageEngine:
    return PageEngine()


@pytest.fixture
def panel() -> MagicMock:
    p = MagicMock()
    p.get_selected_pages.return_value = []
    return p


@pytest.fixture
def tab_manager_with_doc(multi_page_pdf: Path) -> MagicMock:
    doc_handle = pymupdf.open(str(multi_page_pdf))
    metadata = DocumentMetadata(
        file_path=multi_page_pdf,
        page_count=5,
        title=None,
        author=None,
        has_forms=False,
        has_outline=False,
        has_javascript=False,
        is_encrypted=False,
        file_size_bytes=multi_page_pdf.stat().st_size,
    )
    pages = [
        PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
        for i in range(5)
    ]
    model = DocumentModel(
        file_path=multi_page_pdf,
        doc_handle=doc_handle,
        metadata=metadata,
        pages=pages,
    )
    doc_presenter = MagicMock()
    doc_presenter.model = model
    manager = MagicMock()
    manager.active_session_id = model.session_id
    manager.get_active_presenter.return_value = doc_presenter
    return manager


class TestDeleteSinglePage:
    def test_delete_single_page(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        with patch("k_pdf.presenters.page_management_presenter.QMessageBox") as mock_msgbox:
            mock_msgbox.StandardButton.Yes = 1
            mock_msgbox.StandardButton.No = 0
            mock_msgbox.question.return_value = 1

            presenter.delete_pages([2])

        assert model.doc_handle.page_count == 4
        assert model.dirty is True


class TestDeleteMultiplePages:
    def test_delete_multiple_pages(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        with patch("k_pdf.presenters.page_management_presenter.QMessageBox") as mock_msgbox:
            mock_msgbox.StandardButton.Yes = 1
            mock_msgbox.StandardButton.No = 0
            mock_msgbox.question.return_value = 1

            presenter.delete_pages([0, 2, 4])

        assert model.doc_handle.page_count == 2
        assert model.dirty is True


class TestDeleteAllPagesBlocked:
    def test_delete_all_pages_blocked(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        with patch("k_pdf.presenters.page_management_presenter.QMessageBox") as mock_msgbox:
            mock_msgbox.StandardButton.Yes = 1
            mock_msgbox.StandardButton.No = 0
            mock_msgbox.question.return_value = 1

            presenter.delete_pages([0, 1, 2, 3, 4])

        assert model.doc_handle.page_count == 5  # unchanged
        assert model.dirty is False


class TestRotatePageLeft:
    def test_rotate_page_left(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        presenter.rotate_pages([0], 270)

        assert model.doc_handle[0].rotation == 270
        assert model.dirty is True


class TestRotatePageRight:
    def test_rotate_page_right(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        presenter.rotate_pages([0], 90)

        assert model.doc_handle[0].rotation == 90
        assert model.dirty is True


class TestRotateMultiplePages:
    def test_rotate_multiple_pages(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        presenter.rotate_pages([0, 1, 2], 90)

        for i in [0, 1, 2]:
            assert model.doc_handle[i].rotation == 90
        assert model.dirty is True


class TestAddPagesFromPdf:
    def test_add_pages(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
        source_pdf: Path,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        presenter.insert_pages(source_pdf, 2)

        assert model.doc_handle.page_count == 7
        assert model.dirty is True


class TestDragReorder:
    def test_move_page(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model
        original_p3_text = model.doc_handle[3].get_text("text").strip()

        presenter.move_page(3, 1)

        assert model.doc_handle[1].get_text("text").strip() == original_p3_text
        assert model.dirty is True


class TestDirtyFlagOnPageOperation:
    def test_dirty_after_rotate(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model
        assert model.dirty is False

        presenter.rotate_pages([0], 90)
        assert model.dirty is True


class TestPanelEmptyNoDocument:
    def test_panel_empty_no_document(self, panel: MagicMock, engine: PageEngine) -> None:
        manager = MagicMock()
        manager.get_active_presenter.return_value = None

        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=manager,
            panel=panel,
        )
        presenter.on_tab_switched("any-session")

        panel.set_thumbnails.assert_called_with([])
        panel.set_buttons_enabled.assert_called_with(False)


class TestTabSwitchRefreshesPanel:
    def test_tab_switch_refreshes(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )

        presenter.on_tab_switched("new-session")

        panel.set_thumbnails.assert_called_once()
        args = panel.set_thumbnails.call_args[0][0]
        assert len(args) == 5  # 5 page thumbnails
