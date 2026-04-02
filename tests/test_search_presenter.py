"""Tests for SearchPresenter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QTabWidget

from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.presenters.search_presenter import SearchPresenter
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


def _make_tab_manager() -> TabManager:
    tab_widget = QTabWidget()
    recent_files = MagicMock()
    return TabManager(tab_widget=tab_widget, recent_files=recent_files)


class TestSearchPresenterInit:
    def test_creates_worker_and_thread(self) -> None:
        tm = _make_tab_manager()
        sp = SearchPresenter(tab_manager=tm)
        assert sp._worker is not None
        assert sp._thread is not None
        sp.shutdown()

    def test_initial_state_empty(self) -> None:
        tm = _make_tab_manager()
        sp = SearchPresenter(tab_manager=tm)
        assert sp._results == {}
        assert sp._active_session_id is None
        sp.shutdown()


class TestSearchPresenterSearch:
    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_start_search_calls_worker(
        self,
        mock_presenter_cls: MagicMock,
    ) -> None:
        model = _make_model(Path("/tmp/test.pdf"))
        mock_presenter = MagicMock()
        mock_presenter.model = model
        mock_presenter_cls.return_value = mock_presenter

        tm = _make_tab_manager()
        sp = SearchPresenter(tab_manager=tm)

        # Open a file to create a tab
        tm.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(tm._tabs))
        tm._on_document_ready(sid, model)

        # Now set the mock presenter's model (simulating DocumentPresenter storing it)
        ctx = tm._tabs[sid]
        ctx.presenter = mock_presenter  # type: ignore[assignment]

        # Mock the worker search method
        sp._worker.search = MagicMock()

        sp.start_search("hello", case_sensitive=False, whole_word=False)

        sp._worker.search.assert_called_once()
        call_args = sp._worker.search.call_args
        assert call_args[0][1] == "hello"  # query
        assert call_args[0][2] == 3  # page_count
        sp.shutdown()

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_start_search_empty_query_clears(
        self,
        mock_presenter_cls: MagicMock,
    ) -> None:
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter

        tm = _make_tab_manager()
        sp = SearchPresenter(tab_manager=tm)

        tm.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(tm._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        tm._on_document_ready(sid, model)

        clear_spy = MagicMock()
        sp.clear_highlights.connect(clear_spy)

        sp.start_search("", case_sensitive=False, whole_word=False)

        clear_spy.assert_called_once()
        assert sid not in sp._results
        sp.shutdown()

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_page_matches_stores_results(
        self,
        mock_presenter_cls: MagicMock,
    ) -> None:
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter

        tm = _make_tab_manager()
        sp = SearchPresenter(tab_manager=tm)

        tm.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(tm._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        tm._on_document_ready(sid, model)

        # Simulate starting a search to set up state
        sp._active_session_id = sid
        sp._pending_query = "test"
        sp._pending_case = False
        sp._pending_word = False

        # Simulate worker emitting page_matches
        rects = [(10.0, 20.0, 100.0, 40.0)]
        sp._on_page_matches(0, rects)

        assert sid in sp._results
        assert 0 in sp._results[sid].matches
        assert sp._results[sid].matches[0] == rects
        sp.shutdown()


class TestSearchPresenterNavigation:
    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_next_match_advances(
        self,
        mock_presenter_cls: MagicMock,
    ) -> None:
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter

        tm = _make_tab_manager()
        sp = SearchPresenter(tab_manager=tm)

        tm.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(tm._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        tm._on_document_ready(sid, model)

        sp._active_session_id = sid
        sp._pending_query = "test"
        sp._pending_case = False
        sp._pending_word = False

        # Populate results
        sp._on_page_matches(0, [(10.0, 20.0, 100.0, 40.0)])
        sp._on_page_matches(1, [(50.0, 60.0, 150.0, 80.0)])
        sp._on_search_complete(2)

        matches_spy = MagicMock()
        sp.matches_updated.connect(matches_spy)

        sp.next_match()

        assert sp._results[sid].current_match_number() == 2
        sp.shutdown()

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_previous_match_retreats(
        self,
        mock_presenter_cls: MagicMock,
    ) -> None:
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter

        tm = _make_tab_manager()
        sp = SearchPresenter(tab_manager=tm)

        tm.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(tm._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        tm._on_document_ready(sid, model)

        sp._active_session_id = sid
        sp._pending_query = "test"
        sp._pending_case = False
        sp._pending_word = False

        sp._on_page_matches(0, [(10.0, 20.0, 100.0, 40.0)])
        sp._on_page_matches(1, [(50.0, 60.0, 150.0, 80.0)])
        sp._on_search_complete(2)

        # Move to match 2
        sp.next_match()

        # Go back to match 1
        sp.previous_match()
        assert sp._results[sid].current_match_number() == 1
        sp.shutdown()


class TestSearchPresenterTabManagement:
    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_tab_closed_discards_results(
        self,
        mock_presenter_cls: MagicMock,
    ) -> None:
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter

        tm = _make_tab_manager()
        sp = SearchPresenter(tab_manager=tm)

        tm.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(tm._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        tm._on_document_ready(sid, model)

        sp._active_session_id = sid
        sp._pending_query = "test"
        sp._pending_case = False
        sp._pending_word = False
        sp._on_page_matches(0, [(10.0, 20.0, 100.0, 40.0)])
        sp._on_search_complete(1)

        assert sid in sp._results

        tm.close_tab(sid)

        assert sid not in sp._results
        assert sid not in sp._scroll_before_search
        sp.shutdown()

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_close_search_clears_highlights(
        self,
        mock_presenter_cls: MagicMock,
    ) -> None:
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter

        tm = _make_tab_manager()
        sp = SearchPresenter(tab_manager=tm)

        tm.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(tm._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        tm._on_document_ready(sid, model)

        sp._active_session_id = sid
        sp._pending_query = "test"
        sp._pending_case = False
        sp._pending_word = False
        sp._on_page_matches(0, [(10.0, 20.0, 100.0, 40.0)])
        sp._on_search_complete(1)

        clear_spy = MagicMock()
        sp.clear_highlights.connect(clear_spy)

        sp.close_search()

        clear_spy.assert_called_once()
        assert sid not in sp._results
        sp.shutdown()
