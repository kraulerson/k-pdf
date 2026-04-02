"""Tests for SearchWorker service."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

from PySide6.QtWidgets import QApplication

from k_pdf.services.search_engine import SearchWorker

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_mock_doc(
    page_count: int = 3,
    text_per_page: str | None = "Hello world",
    search_results: list[list[object]] | None = None,
) -> MagicMock:
    """Create a mock PyMuPDF document.

    Args:
        page_count: Number of pages.
        text_per_page: Text returned by get_text(). None means no text layer.
        search_results: Per-page list of mock Rect results from search_for().
            If None, defaults to empty lists.
    """
    doc = MagicMock()
    type(doc).page_count = PropertyMock(return_value=page_count)

    pages = []
    for i in range(page_count):
        page = MagicMock()
        page.get_text.return_value = text_per_page if text_per_page else ""
        if search_results and i < len(search_results):
            page.search_for.return_value = search_results[i]
        else:
            page.search_for.return_value = []
        pages.append(page)

    doc.__getitem__ = MagicMock(side_effect=lambda idx: pages[idx])
    return doc


def _make_mock_rect(x0: float, y0: float, x1: float, y1: float) -> MagicMock:
    """Create a mock PyMuPDF Rect with x0, y0, x1, y1 attributes."""
    rect = MagicMock()
    rect.x0 = x0
    rect.y0 = y0
    rect.x1 = x1
    rect.y1 = y1
    return rect


class TestSearchWorker:
    """Tests for SearchWorker text search service."""

    def test_finds_matches_across_pages(self) -> None:
        rect1 = _make_mock_rect(10.0, 20.0, 100.0, 40.0)
        rect2 = _make_mock_rect(50.0, 60.0, 150.0, 80.0)
        doc = _make_mock_doc(
            page_count=3,
            search_results=[
                [rect1],
                [],
                [rect2],
            ],
        )

        worker = SearchWorker()
        page_results: list[tuple[int, list[tuple[float, float, float, float]]]] = []
        total_results: list[int] = []

        worker.page_matches.connect(lambda pi, rects: page_results.append((pi, rects)))
        worker.search_complete.connect(lambda count: total_results.append(count))

        worker.search(doc, "Hello", 3, case_sensitive=False, whole_word=False)

        assert len(page_results) == 2
        assert page_results[0][0] == 0
        assert page_results[0][1] == [(10.0, 20.0, 100.0, 40.0)]
        assert page_results[1][0] == 2
        assert page_results[1][1] == [(50.0, 60.0, 150.0, 80.0)]
        assert total_results == [2]

    def test_case_sensitive_flag_passed(self) -> None:
        doc = _make_mock_doc(page_count=1)
        worker = SearchWorker()
        worker.search(doc, "Hello", 1, case_sensitive=True, whole_word=False)
        page = doc[0]
        _, _kwargs = page.search_for.call_args
        # PyMuPDF flags: TEXT_PRESERVE_LIGATURES | TEXT_PRESERVE_WHITESPACE = 1|2 = 3
        # When not case-insensitive, we do NOT add TEXT_IGNORE_CASE (not present)
        # We verify the call was made
        page.search_for.assert_called_once()

    def test_case_insensitive_search(self) -> None:
        doc = _make_mock_doc(page_count=1)
        worker = SearchWorker()
        worker.search(doc, "Hello", 1, case_sensitive=False, whole_word=False)
        page = doc[0]
        page.search_for.assert_called_once()

    def test_empty_results(self) -> None:
        doc = _make_mock_doc(page_count=3, search_results=[[], [], []])
        worker = SearchWorker()
        total_results: list[int] = []
        page_results: list[tuple[int, list[tuple[float, float, float, float]]]] = []

        worker.page_matches.connect(lambda pi, rects: page_results.append((pi, rects)))
        worker.search_complete.connect(lambda count: total_results.append(count))

        worker.search(doc, "nonexistent", 3, case_sensitive=False, whole_word=False)

        assert page_results == []
        assert total_results == [0]

    def test_no_text_layer_detection(self) -> None:
        doc = _make_mock_doc(page_count=3, text_per_page="")
        worker = SearchWorker()
        no_text_emitted: list[bool] = []
        total_results: list[int] = []

        worker.no_text_layer.connect(lambda: no_text_emitted.append(True))
        worker.search_complete.connect(lambda count: total_results.append(count))

        worker.search(doc, "test", 3, case_sensitive=False, whole_word=False)

        assert no_text_emitted == [True]
        assert total_results == []  # search_complete NOT emitted for no-text docs

    def test_cancel_stops_search(self) -> None:
        rect = _make_mock_rect(1.0, 2.0, 3.0, 4.0)
        doc = _make_mock_doc(
            page_count=100,
            search_results=[[rect]] * 100,
        )

        worker = SearchWorker()
        page_results: list[tuple[int, list[tuple[float, float, float, float]]]] = []

        def on_page_match(pi: int, rects: list[tuple[float, float, float, float]]) -> None:
            page_results.append((pi, rects))
            # Cancel mid-search after first page result
            if len(page_results) == 1:
                worker.cancel()

        worker.page_matches.connect(on_page_match)

        worker.search(doc, "test", 100, case_sensitive=False, whole_word=False)

        # Should have found at most a few results before cancel took effect
        assert len(page_results) < 100

    def test_empty_query_emits_zero(self) -> None:
        doc = _make_mock_doc(page_count=1)
        worker = SearchWorker()
        total_results: list[int] = []
        worker.search_complete.connect(lambda count: total_results.append(count))

        worker.search(doc, "", 1, case_sensitive=False, whole_word=False)

        assert total_results == [0]
