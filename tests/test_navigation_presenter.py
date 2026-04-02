"""Tests for NavigationPresenter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QTabWidget

from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.presenters.navigation_presenter import NavigationPresenter
from k_pdf.presenters.tab_manager import TabManager

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_model(file_path: Path, page_count: int = 3) -> DocumentModel:
    metadata = DocumentMetadata(
        file_path=file_path,
        page_count=page_count,
        title=None,
        author=None,
        has_forms=False,
        has_outline=False,
        has_javascript=False,
        is_encrypted=False,
        file_size_bytes=1000,
    )
    pages = [
        PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
        for i in range(page_count)
    ]
    return DocumentModel(
        file_path=file_path,
        doc_handle=MagicMock(),
        metadata=metadata,
        pages=pages,
    )


class TestNavigationPresenter:
    """Tests for NavigationPresenter."""

    @patch("k_pdf.presenters.navigation_presenter.ThumbnailCache")
    @patch("k_pdf.presenters.navigation_presenter.get_outline")
    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_document_ready_creates_cache(
        self,
        mock_presenter_cls: MagicMock,
        mock_get_outline: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        mock_get_outline.return_value = []
        mock_cache = MagicMock()
        mock_cache_cls.return_value = mock_cache

        tab_widget = QTabWidget()
        recent_files = MagicMock()
        tm = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        nav = NavigationPresenter(tab_manager=tm)

        tm.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(tm._tabs))
        model = _make_model(Path("/tmp/test.pdf"))

        tm._on_document_ready(sid, model)

        mock_cache_cls.assert_called_once()
        mock_cache.start.assert_called_once()
        mock_get_outline.assert_called_once()
        assert sid in nav._thumbnail_caches

    @patch("k_pdf.presenters.navigation_presenter.ThumbnailCache")
    @patch("k_pdf.presenters.navigation_presenter.get_outline")
    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_tab_closed_discards_cache(
        self,
        mock_presenter_cls: MagicMock,
        mock_get_outline: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        mock_get_outline.return_value = []
        mock_cache = MagicMock()
        mock_cache_cls.return_value = mock_cache

        tab_widget = QTabWidget()
        recent_files = MagicMock()
        tm = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        nav = NavigationPresenter(tab_manager=tm)

        tm.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(tm._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        tm._on_document_ready(sid, model)

        tm.close_tab(sid)

        mock_cache.shutdown.assert_called_once()
        assert sid not in nav._thumbnail_caches
