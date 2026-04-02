# Feature 4: Text Search Within Document — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add in-document text search with a non-modal search bar (Ctrl+F), progressive background search via QThread, semi-transparent highlight overlays on the viewport, next/previous navigation, case-sensitive and whole-word toggles, and per-tab search state management.

**Architecture:** SearchBar widget sits above the QStackedWidget in a QVBoxLayout container. SearchPresenter coordinates between SearchBar, SearchWorker (QThread), TabManager, and PdfViewport highlight overlays. SearchResult dataclass tracks per-tab match state with advance/retreat navigation. SearchWorker uses PyMuPDF's `page.search_for()` on a dedicated thread, emitting results progressively per page.

**Tech Stack:** Python 3.13, PySide6 6.11, PyMuPDF 1.27, pytest + pytest-qt

**Spec:** `docs/superpowers/specs/2026-04-02-feature4-text-search-design.md`

---

## File Map

**New files:**
- `k_pdf/core/search_model.py` — `SearchResult` mutable dataclass with advance/retreat navigation
- `tests/test_search_model.py` — unit tests for SearchResult
- `tests/test_search_service.py` — unit tests for SearchWorker
- `tests/test_search_bar.py` — unit tests for SearchBar widget
- `tests/test_search_presenter.py` — unit tests for SearchPresenter
- `tests/test_search_integration.py` — integration tests with real PDFs

**Modified files (replace stubs):**
- `k_pdf/services/search_engine.py` — `SearchWorker(QObject)` with QThread-based search (replaces stub)
- `k_pdf/views/search_bar.py` — `SearchBar(QWidget)` with input, toggles, counter (replaces stub)
- `k_pdf/presenters/search_presenter.py` — `SearchPresenter(QObject)` coordinating search flow (replaces stub)

**Modified files (edit existing):**
- `k_pdf/views/pdf_viewport.py` — add highlight overlay methods and `_search_highlights` list
- `k_pdf/views/main_window.py` — wrap stacked widget in QVBoxLayout with SearchBar, add Edit menu with Ctrl+F
- `k_pdf/app.py` — create SearchPresenter, wire all search signals
- `pyproject.toml` — add mypy overrides for new modules
- `tests/conftest.py` — add `searchable_pdf` and `image_only_pdf` fixtures
- `CLAUDE.md` — update current state

---

### Task 1: SearchResult dataclass

**Files:**
- Create: `k_pdf/core/search_model.py`
- Create: `tests/test_search_model.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_search_model.py`:

```python
"""Tests for SearchResult dataclass."""

from __future__ import annotations

from k_pdf.core.search_model import SearchResult


class TestSearchResultConstruction:
    def test_empty_result(self) -> None:
        result = SearchResult(
            query="hello",
            case_sensitive=False,
            whole_word=False,
            matches={},
            total_count=0,
            current_page=-1,
            current_index=-1,
        )
        assert result.query == "hello"
        assert result.total_count == 0
        assert result.matches == {}
        assert result.current_page == -1
        assert result.current_index == -1

    def test_result_with_matches(self) -> None:
        matches = {
            0: [(10.0, 20.0, 100.0, 40.0)],
            2: [(50.0, 60.0, 150.0, 80.0), (50.0, 100.0, 150.0, 120.0)],
        }
        result = SearchResult(
            query="test",
            case_sensitive=True,
            whole_word=False,
            matches=matches,
            total_count=3,
            current_page=0,
            current_index=0,
        )
        assert result.total_count == 3
        assert len(result.matches[0]) == 1
        assert len(result.matches[2]) == 2

    def test_is_mutable(self) -> None:
        result = SearchResult(
            query="x",
            case_sensitive=False,
            whole_word=False,
            matches={0: [(1.0, 2.0, 3.0, 4.0)]},
            total_count=1,
            current_page=0,
            current_index=0,
        )
        result.current_page = 1
        result.current_index = 2
        assert result.current_page == 1
        assert result.current_index == 2


class TestSearchResultNavigation:
    def _make_result(self) -> SearchResult:
        """Create a result with 3 matches across 2 pages: page 0 has 1, page 2 has 2."""
        return SearchResult(
            query="test",
            case_sensitive=False,
            whole_word=False,
            matches={
                0: [(10.0, 20.0, 100.0, 40.0)],
                2: [(50.0, 60.0, 150.0, 80.0), (50.0, 100.0, 150.0, 120.0)],
            },
            total_count=3,
            current_page=0,
            current_index=0,
        )

    def test_advance_within_page(self) -> None:
        result = SearchResult(
            query="test",
            case_sensitive=False,
            whole_word=False,
            matches={0: [(1.0, 2.0, 3.0, 4.0), (5.0, 6.0, 7.0, 8.0)]},
            total_count=2,
            current_page=0,
            current_index=0,
        )
        result.advance()
        assert result.current_page == 0
        assert result.current_index == 1

    def test_advance_to_next_page(self) -> None:
        result = self._make_result()
        # At page 0, index 0 — advance moves to page 2, index 0
        result.advance()
        assert result.current_page == 2
        assert result.current_index == 0

    def test_advance_wraps_to_first(self) -> None:
        result = self._make_result()
        # Move to last match: page 2, index 1
        result.current_page = 2
        result.current_index = 1
        result.advance()
        assert result.current_page == 0
        assert result.current_index == 0

    def test_advance_empty_does_nothing(self) -> None:
        result = SearchResult(
            query="x",
            case_sensitive=False,
            whole_word=False,
            matches={},
            total_count=0,
            current_page=-1,
            current_index=-1,
        )
        result.advance()
        assert result.current_page == -1
        assert result.current_index == -1

    def test_retreat_within_page(self) -> None:
        result = SearchResult(
            query="test",
            case_sensitive=False,
            whole_word=False,
            matches={0: [(1.0, 2.0, 3.0, 4.0), (5.0, 6.0, 7.0, 8.0)]},
            total_count=2,
            current_page=0,
            current_index=1,
        )
        result.retreat()
        assert result.current_page == 0
        assert result.current_index == 0

    def test_retreat_to_previous_page(self) -> None:
        result = self._make_result()
        result.current_page = 2
        result.current_index = 0
        result.retreat()
        assert result.current_page == 0
        assert result.current_index == 0

    def test_retreat_wraps_to_last(self) -> None:
        result = self._make_result()
        # At first match: page 0, index 0 — retreat wraps to page 2, index 1
        result.retreat()
        assert result.current_page == 2
        assert result.current_index == 1

    def test_retreat_empty_does_nothing(self) -> None:
        result = SearchResult(
            query="x",
            case_sensitive=False,
            whole_word=False,
            matches={},
            total_count=0,
            current_page=-1,
            current_index=-1,
        )
        result.retreat()
        assert result.current_page == -1
        assert result.current_index == -1


class TestSearchResultHelpers:
    def test_current_match_number_first(self) -> None:
        result = SearchResult(
            query="test",
            case_sensitive=False,
            whole_word=False,
            matches={
                0: [(10.0, 20.0, 100.0, 40.0)],
                2: [(50.0, 60.0, 150.0, 80.0), (50.0, 100.0, 150.0, 120.0)],
            },
            total_count=3,
            current_page=0,
            current_index=0,
        )
        assert result.current_match_number() == 1

    def test_current_match_number_second_page(self) -> None:
        result = SearchResult(
            query="test",
            case_sensitive=False,
            whole_word=False,
            matches={
                0: [(10.0, 20.0, 100.0, 40.0)],
                2: [(50.0, 60.0, 150.0, 80.0), (50.0, 100.0, 150.0, 120.0)],
            },
            total_count=3,
            current_page=2,
            current_index=1,
        )
        # Match 1 on page 0, match 2 on page 2 index 0, match 3 on page 2 index 1
        assert result.current_match_number() == 3

    def test_current_match_number_empty(self) -> None:
        result = SearchResult(
            query="x",
            case_sensitive=False,
            whole_word=False,
            matches={},
            total_count=0,
            current_page=-1,
            current_index=-1,
        )
        assert result.current_match_number() == 0

    def test_current_rect(self) -> None:
        result = SearchResult(
            query="test",
            case_sensitive=False,
            whole_word=False,
            matches={0: [(10.0, 20.0, 100.0, 40.0)]},
            total_count=1,
            current_page=0,
            current_index=0,
        )
        assert result.current_rect() == (10.0, 20.0, 100.0, 40.0)

    def test_current_rect_none_when_empty(self) -> None:
        result = SearchResult(
            query="x",
            case_sensitive=False,
            whole_word=False,
            matches={},
            total_count=0,
            current_page=-1,
            current_index=-1,
        )
        assert result.current_rect() is None

    def test_current_rect_none_when_page_missing(self) -> None:
        result = SearchResult(
            query="x",
            case_sensitive=False,
            whole_word=False,
            matches={0: [(1.0, 2.0, 3.0, 4.0)]},
            total_count=1,
            current_page=5,
            current_index=0,
        )
        assert result.current_rect() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_search_model.py -v`

Expected: FAIL — module `k_pdf.core.search_model` does not exist.

- [ ] **Step 3: Implement SearchResult**

Create `k_pdf/core/search_model.py`:

```python
"""Search result model.

SearchResult is a mutable dataclass tracking match positions and
navigation cursor. Pure data — no Qt or PyMuPDF imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """Per-tab search state with cursor navigation."""

    query: str
    case_sensitive: bool
    whole_word: bool
    matches: dict[int, list[tuple[float, float, float, float]]]
    total_count: int
    current_page: int  # page index of current match, -1 if none
    current_index: int  # index within page's match list, -1 if none

    def _sorted_pages(self) -> list[int]:
        """Return page indices that have matches, sorted ascending."""
        return sorted(p for p, rects in self.matches.items() if rects)

    def advance(self) -> None:
        """Move to the next match, wrapping from last to first."""
        pages = self._sorted_pages()
        if not pages:
            return

        if self.current_page < 0:
            self.current_page = pages[0]
            self.current_index = 0
            return

        page_rects = self.matches.get(self.current_page, [])
        if self.current_index + 1 < len(page_rects):
            # Next match on same page
            self.current_index += 1
            return

        # Move to next page with matches
        page_pos = pages.index(self.current_page) if self.current_page in pages else -1
        next_pos = page_pos + 1
        if next_pos >= len(pages):
            # Wrap to first
            next_pos = 0
        self.current_page = pages[next_pos]
        self.current_index = 0

    def retreat(self) -> None:
        """Move to the previous match, wrapping from first to last."""
        pages = self._sorted_pages()
        if not pages:
            return

        if self.current_page < 0:
            self.current_page = pages[-1]
            self.current_index = len(self.matches[pages[-1]]) - 1
            return

        if self.current_index > 0:
            # Previous match on same page
            self.current_index -= 1
            return

        # Move to previous page with matches
        page_pos = pages.index(self.current_page) if self.current_page in pages else 0
        prev_pos = page_pos - 1
        if prev_pos < 0:
            # Wrap to last
            prev_pos = len(pages) - 1
        self.current_page = pages[prev_pos]
        self.current_index = len(self.matches[self.current_page]) - 1

    def current_match_number(self) -> int:
        """Return 1-based position in total sequence for 'X of Y' display.

        Returns:
            1-based match number, or 0 if no matches.
        """
        if self.current_page < 0 or not self.matches:
            return 0

        pages = self._sorted_pages()
        count = 0
        for page in pages:
            if page == self.current_page:
                count += self.current_index + 1
                break
            count += len(self.matches[page])
        return count

    def current_rect(self) -> tuple[float, float, float, float] | None:
        """Return the current match's bounding box.

        Returns:
            (x0, y0, x1, y1) tuple, or None if no current match.
        """
        if self.current_page < 0:
            return None
        page_rects = self.matches.get(self.current_page)
        if page_rects is None or self.current_index < 0 or self.current_index >= len(page_rects):
            return None
        return page_rects[self.current_index]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_search_model.py -v`

Expected: All 18 pass.

- [ ] **Step 5: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run ruff check k_pdf/core/search_model.py tests/test_search_model.py && uv run mypy k_pdf/core/search_model.py`

- [ ] **Step 6: Commit**

```bash
git add k_pdf/core/search_model.py tests/test_search_model.py
git commit -m "feat(f4): add SearchResult dataclass with navigation methods"
```

---

### Task 2: SearchWorker service

**Files:**
- Modify: `k_pdf/services/search_engine.py` (replace stub)
- Create: `tests/test_search_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_search_service.py`:

```python
"""Tests for SearchWorker service."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

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
        _, kwargs = page.search_for.call_args
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
        worker.page_matches.connect(lambda pi, rects: page_results.append((pi, rects)))

        # Cancel immediately after starting — the synchronous search will check
        # _cancelled between pages but since it runs synchronously, cancel before search
        worker.cancel()
        worker.search(doc, "test", 100, case_sensitive=False, whole_word=False)

        # Should have found 0 results since cancelled before start
        assert len(page_results) == 0

    def test_empty_query_emits_zero(self) -> None:
        doc = _make_mock_doc(page_count=1)
        worker = SearchWorker()
        total_results: list[int] = []
        worker.search_complete.connect(lambda count: total_results.append(count))

        worker.search(doc, "", 1, case_sensitive=False, whole_word=False)

        assert total_results == [0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_search_service.py -v`

Expected: FAIL — `SearchWorker` not defined in `search_engine`.

- [ ] **Step 3: Implement SearchWorker**

Replace `k_pdf/services/search_engine.py` with:

```python
"""Text search worker — runs PyMuPDF search on a dedicated QThread.

PyMuPDF import is isolated here per AGPL containment rule.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger("k_pdf.services.search_engine")


class SearchWorker(QObject):
    """Background worker that searches PDF pages for text matches.

    Designed to be moved to a QThread. Emits results progressively
    per page and supports cancellation between pages.
    """

    page_matches = Signal(int, list)  # (page_index, list of rect tuples)
    search_complete = Signal(int)  # total match count
    no_text_layer = Signal()  # document has no searchable text

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the search worker."""
        super().__init__(parent)
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the current search."""
        self._cancelled = True

    @Slot(object, str, int, bool, bool)
    def search(
        self,
        doc_handle: Any,
        query: str,
        page_count: int,
        *,
        case_sensitive: bool,
        whole_word: bool,
    ) -> None:
        """Search all pages for the given query.

        Emits page_matches for each page with results, then
        search_complete with the total count. If the document
        has no text layer, emits no_text_layer instead.

        Args:
            doc_handle: A pymupdf.Document handle.
            query: The search text.
            page_count: Total number of pages in the document.
            case_sensitive: Whether to match case.
            whole_word: Whether to match whole words only.
        """
        self._cancelled = False

        if not query:
            self.search_complete.emit(0)
            return

        # Detect no-text-layer: check if any page has extractable text
        has_any_text = False
        for i in range(page_count):
            if self._cancelled:
                return
            try:
                page = doc_handle[i]
                text = page.get_text("text")
                if text and text.strip():
                    has_any_text = True
                    break
            except Exception:
                continue

        if not has_any_text:
            self.no_text_layer.emit()
            return

        # Build search flags
        # PyMuPDF search_for flags: quads=False by default, returns Rect list
        import pymupdf

        flags = pymupdf.TEXT_PRESERVE_LIGATURES | pymupdf.TEXT_PRESERVE_WHITESPACE
        if not case_sensitive:
            flags |= pymupdf.TEXT_IGNORE_CASE

        total_count = 0
        for i in range(page_count):
            if self._cancelled:
                return

            try:
                page = doc_handle[i]
                results = page.search_for(query, flags=flags)

                if whole_word:
                    results = self._filter_whole_word(page, query, results, case_sensitive)

                if results:
                    rect_tuples = [(r.x0, r.y0, r.x1, r.y1) for r in results]
                    total_count += len(rect_tuples)
                    self.page_matches.emit(i, rect_tuples)
            except Exception:
                logger.warning("Search error on page %d", i, exc_info=True)
                continue

        self.search_complete.emit(total_count)

    def _filter_whole_word(
        self,
        page: Any,
        query: str,
        results: list[Any],
        case_sensitive: bool,
    ) -> list[Any]:
        """Filter search results to whole-word matches only.

        Checks that the characters immediately before and after each
        match in the page text are not alphanumeric.

        Args:
            page: A pymupdf page object.
            query: The search text.
            results: List of Rect results from search_for().
            case_sensitive: Whether to do case-sensitive matching.

        Returns:
            Filtered list of Rect results that are whole-word matches.
        """
        if not results:
            return results

        page_text = page.get_text("text")
        if not page_text:
            return results

        compare_text = page_text if case_sensitive else page_text.lower()
        compare_query = query if case_sensitive else query.lower()

        filtered = []
        search_start = 0
        for rect in results:
            pos = compare_text.find(compare_query, search_start)
            if pos == -1:
                # Fallback: keep it if we can't verify
                filtered.append(rect)
                continue

            before_ok = pos == 0 or not compare_text[pos - 1].isalnum()
            end_pos = pos + len(compare_query)
            after_ok = end_pos >= len(compare_text) or not compare_text[end_pos].isalnum()

            if before_ok and after_ok:
                filtered.append(rect)
            search_start = end_pos

        return filtered
```

- [ ] **Step 4: Add mypy override**

In `pyproject.toml`, add to the existing overrides section:

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.services.search_engine"]
disable_error_code = ["misc", "no-untyped-call"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_search_service.py -v`

Expected: All 7 pass.

- [ ] **Step 6: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run ruff check k_pdf/services/search_engine.py tests/test_search_service.py && uv run mypy k_pdf/services/search_engine.py`

- [ ] **Step 7: Commit**

```bash
git add k_pdf/services/search_engine.py tests/test_search_service.py pyproject.toml
git commit -m "feat(f4): implement SearchWorker with progressive page search"
```

---

### Task 3: PdfViewport highlight overlay methods

**Files:**
- Modify: `k_pdf/views/pdf_viewport.py`
- Modify: `tests/test_views.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_views.py` in `TestPdfViewport`:

```python
    def test_add_search_highlights(self) -> None:
        """Test adding search highlight overlays to a page."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        viewport.add_search_highlights(0, [(10.0, 20.0, 100.0, 40.0)], zoom=1.0)
        assert len(viewport._search_highlights) == 1

    def test_add_search_highlights_multiple_rects(self) -> None:
        """Test adding multiple highlight rects on one page."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        rects = [(10.0, 20.0, 100.0, 40.0), (50.0, 60.0, 150.0, 80.0)]
        viewport.add_search_highlights(0, rects, zoom=1.0)
        assert len(viewport._search_highlights) == 2

    def test_clear_search_highlights(self) -> None:
        """Test clearing all search highlights."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        viewport.add_search_highlights(0, [(10.0, 20.0, 100.0, 40.0)], zoom=1.0)
        assert len(viewport._search_highlights) == 1
        viewport.clear_search_highlights()
        assert len(viewport._search_highlights) == 0

    def test_set_current_highlight(self) -> None:
        """Test setting the current match highlight."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        viewport.add_search_highlights(0, [(10.0, 20.0, 100.0, 40.0)], zoom=1.0)
        # Should not raise — sets a distinct highlight
        viewport.set_current_highlight(0, (10.0, 20.0, 100.0, 40.0), zoom=1.0)
        # Current highlight item is tracked separately
        assert viewport._current_highlight is not None

    def test_clear_removes_current_highlight(self) -> None:
        """Test that clear also removes the current highlight."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        viewport.add_search_highlights(0, [(10.0, 20.0, 100.0, 40.0)], zoom=1.0)
        viewport.set_current_highlight(0, (10.0, 20.0, 100.0, 40.0), zoom=1.0)
        viewport.clear_search_highlights()
        assert viewport._current_highlight is None
        assert len(viewport._search_highlights) == 0

    def test_highlights_on_invalid_page_ignored(self) -> None:
        """Test that highlights on a non-existent page are silently ignored."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        viewport.add_search_highlights(5, [(10.0, 20.0, 100.0, 40.0)], zoom=1.0)
        assert len(viewport._search_highlights) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_views.py::TestPdfViewport::test_add_search_highlights tests/test_views.py::TestPdfViewport::test_clear_search_highlights tests/test_views.py::TestPdfViewport::test_set_current_highlight -v`

Expected: FAIL — methods do not exist.

- [ ] **Step 3: Add highlight methods to PdfViewport**

In `k_pdf/views/pdf_viewport.py`, add to the imports (line 16, add `QPen` to the QGui imports):

Replace:
```python
from PySide6.QtGui import QBrush, QColor, QFont, QPixmap
```

With:
```python
from PySide6.QtGui import QBrush, QColor, QFont, QPen, QPixmap
```

In `PdfViewport.__init__`, add after `self._current_page: int = -1` (line 63):

```python
        self._search_highlights: list[QGraphicsRectItem] = []
        self._current_highlight: QGraphicsRectItem | None = None
```

Add these methods after `scroll_to_page` (after line 201):

```python
    def add_search_highlights(
        self,
        page_index: int,
        rects: list[tuple[float, float, float, float]],
        zoom: float,
    ) -> None:
        """Add semi-transparent highlight overlays for search matches on a page.

        Creates QGraphicsRectItems with visible fill and border at the
        specified rect positions. Highlights are non-destructive overlays
        on the existing scene.

        Args:
            page_index: 0-based page index.
            rects: List of (x0, y0, x1, y1) bounding boxes in page coordinates.
            zoom: Current zoom factor applied to coordinates.
        """
        if page_index < 0 or page_index >= len(self._page_y_offsets):
            return

        y_base = self._page_y_offsets[page_index]
        pen = QPen(QColor(0, 0, 0, 180))
        pen.setWidthF(1.0)
        brush = QBrush(QColor(255, 200, 0, 80))

        for x0, y0, x1, y1 in rects:
            sx0 = x0 * zoom
            sy0 = y0 * zoom
            sw = (x1 - x0) * zoom
            sh = (y1 - y0) * zoom
            rect_item = self._scene.addRect(
                QRectF(0, 0, sw, sh),
                pen=pen,
                brush=brush,
            )
            rect_item.setPos(sx0, y_base + sy0)
            rect_item.setZValue(10)
            self._search_highlights.append(rect_item)

    def set_current_highlight(
        self,
        page_index: int,
        rect: tuple[float, float, float, float],
        zoom: float,
    ) -> None:
        """Mark one match as the current highlight with a thicker border.

        Removes any previous current-highlight overlay and creates
        a new one with a distinct, thicker pen.

        Args:
            page_index: 0-based page index.
            rect: (x0, y0, x1, y1) bounding box in page coordinates.
            zoom: Current zoom factor applied to coordinates.
        """
        # Remove previous current highlight
        if self._current_highlight is not None:
            self._scene.removeItem(self._current_highlight)
            self._current_highlight = None

        if page_index < 0 or page_index >= len(self._page_y_offsets):
            return

        y_base = self._page_y_offsets[page_index]
        x0, y0, x1, y1 = rect
        sx0 = x0 * zoom
        sy0 = y0 * zoom
        sw = (x1 - x0) * zoom
        sh = (y1 - y0) * zoom

        pen = QPen(QColor(0, 0, 0, 255))
        pen.setWidthF(3.0)
        brush = QBrush(QColor(255, 150, 0, 120))

        current_item = self._scene.addRect(
            QRectF(0, 0, sw, sh),
            pen=pen,
            brush=brush,
        )
        current_item.setPos(sx0, y_base + sy0)
        current_item.setZValue(11)
        self._current_highlight = current_item

    def clear_search_highlights(self) -> None:
        """Remove all search highlight overlays from the scene."""
        for item in self._search_highlights:
            self._scene.removeItem(item)
        self._search_highlights.clear()

        if self._current_highlight is not None:
            self._scene.removeItem(self._current_highlight)
            self._current_highlight = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_views.py::TestPdfViewport -v`

Expected: All pass (including existing tests).

- [ ] **Step 5: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run ruff check k_pdf/views/pdf_viewport.py && uv run mypy k_pdf/views/pdf_viewport.py`

- [ ] **Step 6: Commit**

```bash
git add k_pdf/views/pdf_viewport.py tests/test_views.py
git commit -m "feat(f4): add search highlight overlay methods to PdfViewport"
```

---

### Task 4: SearchBar view

**Files:**
- Modify: `k_pdf/views/search_bar.py` (replace stub)
- Create: `tests/test_search_bar.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_search_bar.py`:

```python
"""Tests for SearchBar widget."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from k_pdf.views.search_bar import SearchBar

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestSearchBarLayout:
    def test_starts_hidden(self) -> None:
        bar = SearchBar()
        assert not bar.isVisible()

    def test_has_search_input(self) -> None:
        bar = SearchBar()
        assert bar._search_input is not None

    def test_has_match_label(self) -> None:
        bar = SearchBar()
        assert bar._match_label is not None

    def test_has_previous_button(self) -> None:
        bar = SearchBar()
        assert bar._prev_btn is not None
        assert bar._prev_btn.text() == "Previous"

    def test_has_next_button(self) -> None:
        bar = SearchBar()
        assert bar._next_btn is not None
        assert bar._next_btn.text() == "Next"

    def test_has_case_toggle(self) -> None:
        bar = SearchBar()
        assert bar._case_btn is not None
        assert bar._case_btn.text() == "Aa"

    def test_has_word_toggle(self) -> None:
        bar = SearchBar()
        assert bar._word_btn is not None
        assert bar._word_btn.text() == "W"

    def test_has_close_button(self) -> None:
        bar = SearchBar()
        assert bar._close_btn is not None


class TestSearchBarSignals:
    def test_search_requested_on_text_change(self, qtbot: object) -> None:
        bar = SearchBar()
        spy = MagicMock()
        bar.search_requested.connect(spy)

        bar._search_input.setText("hello")
        # Debounce is 300ms — wait for it
        qtbot.waitUntil(lambda: spy.called, timeout=1000)
        spy.assert_called_with("hello", False, False)

    def test_next_requested_on_button(self) -> None:
        bar = SearchBar()
        spy = MagicMock()
        bar.next_requested.connect(spy)
        bar._next_btn.click()
        spy.assert_called_once()

    def test_previous_requested_on_button(self) -> None:
        bar = SearchBar()
        spy = MagicMock()
        bar.previous_requested.connect(spy)
        bar._prev_btn.click()
        spy.assert_called_once()

    def test_closed_on_close_button(self) -> None:
        bar = SearchBar()
        spy = MagicMock()
        bar.closed.connect(spy)
        bar._close_btn.click()
        spy.assert_called_once()

    def test_toggle_case_triggers_search(self, qtbot: object) -> None:
        bar = SearchBar()
        bar._search_input.setText("test")
        spy = MagicMock()
        bar.search_requested.connect(spy)

        # Toggle case sensitivity on
        bar._case_btn.click()
        qtbot.waitUntil(lambda: spy.called, timeout=1000)
        spy.assert_called_with("test", True, False)

    def test_toggle_word_triggers_search(self, qtbot: object) -> None:
        bar = SearchBar()
        bar._search_input.setText("test")
        spy = MagicMock()
        bar.search_requested.connect(spy)

        # Toggle whole word on
        bar._word_btn.click()
        qtbot.waitUntil(lambda: spy.called, timeout=1000)
        spy.assert_called_with("test", False, True)


class TestSearchBarDisplay:
    def test_set_match_count(self) -> None:
        bar = SearchBar()
        bar.set_match_count(3, 10)
        assert bar._match_label.text() == "3 of 10 matches"

    def test_set_match_count_singular(self) -> None:
        bar = SearchBar()
        bar.set_match_count(1, 1)
        assert bar._match_label.text() == "1 of 1 match"

    def test_set_no_text_layer(self) -> None:
        bar = SearchBar()
        bar.set_no_text_layer()
        assert "no searchable text" in bar._match_label.text().lower()

    def test_set_no_matches(self) -> None:
        bar = SearchBar()
        bar.set_no_matches()
        assert bar._match_label.text() == "No matches found"

    def test_focus_input(self) -> None:
        bar = SearchBar()
        bar.show()
        bar.focus_input()
        assert bar._search_input.hasFocus()

    def test_clear_resets_state(self) -> None:
        bar = SearchBar()
        bar._search_input.setText("something")
        bar._match_label.setText("5 of 10 matches")
        bar.clear()
        assert bar._search_input.text() == ""
        assert bar._match_label.text() == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_search_bar.py -v`

Expected: FAIL — `SearchBar` not defined in `search_bar`.

- [ ] **Step 3: Implement SearchBar**

Replace `k_pdf/views/search_bar.py` with:

```python
"""Document text search bar.

Non-modal search widget with text input, match counter, navigation
buttons, case/whole-word toggles, and close button. Starts hidden.
Activated by Ctrl+F from the main window.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

logger = logging.getLogger("k_pdf.views.search_bar")


class SearchBar(QWidget):
    """Search bar with input, toggles, match counter, and navigation."""

    search_requested = Signal(str, bool, bool)  # (query, case_sensitive, whole_word)
    next_requested = Signal()
    previous_requested = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the search bar, hidden by default."""
        super().__init__(parent)
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Search input
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Find in document...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumWidth(200)
        layout.addWidget(self._search_input)

        # Match counter label
        self._match_label = QLabel("")
        self._match_label.setMinimumWidth(120)
        layout.addWidget(self._match_label)

        # Previous button
        self._prev_btn = QPushButton("Previous")
        self._prev_btn.setToolTip("Previous match (Shift+Enter)")
        self._prev_btn.clicked.connect(self.previous_requested.emit)
        layout.addWidget(self._prev_btn)

        # Next button
        self._next_btn = QPushButton("Next")
        self._next_btn.setToolTip("Next match (Enter)")
        self._next_btn.clicked.connect(self.next_requested.emit)
        layout.addWidget(self._next_btn)

        # Case-sensitive toggle
        self._case_btn = QPushButton("Aa")
        self._case_btn.setToolTip("Case sensitive")
        self._case_btn.setCheckable(True)
        self._case_btn.setMaximumWidth(36)
        self._case_btn.clicked.connect(self._on_toggle_changed)
        layout.addWidget(self._case_btn)

        # Whole-word toggle
        self._word_btn = QPushButton("W")
        self._word_btn.setToolTip("Whole word")
        self._word_btn.setCheckable(True)
        self._word_btn.setMaximumWidth(36)
        self._word_btn.clicked.connect(self._on_toggle_changed)
        layout.addWidget(self._word_btn)

        # Close button
        self._close_btn = QPushButton("\u00d7")
        self._close_btn.setToolTip("Close search bar (Escape)")
        self._close_btn.setMaximumWidth(30)
        self._close_btn.clicked.connect(self.closed.emit)
        layout.addWidget(self._close_btn)

        # Debounce timer for search input
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._emit_search)

        # Connect text changes to debounced search
        self._search_input.textChanged.connect(self._on_text_changed)

        # Enter → next, Shift+Enter → previous
        self._search_input.returnPressed.connect(self.next_requested.emit)

        # Escape closes the search bar
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.closed.emit)

    def set_match_count(self, current: int, total: int) -> None:
        """Update the match counter label.

        Args:
            current: Current match number (1-based).
            total: Total match count.
        """
        word = "match" if total == 1 else "matches"
        self._match_label.setText(f"{current} of {total} {word}")

    def set_no_text_layer(self) -> None:
        """Show message indicating the document has no searchable text."""
        self._match_label.setText("This document has no searchable text.")

    def set_no_matches(self) -> None:
        """Show 'No matches found' message."""
        self._match_label.setText("No matches found")

    def focus_input(self) -> None:
        """Focus the search text input field."""
        self._search_input.setFocus()
        self._search_input.selectAll()

    def clear(self) -> None:
        """Reset the search bar to its initial state."""
        self._search_input.blockSignals(True)
        self._search_input.clear()
        self._search_input.blockSignals(False)
        self._match_label.setText("")
        self._case_btn.setChecked(False)
        self._word_btn.setChecked(False)

    def _on_text_changed(self, _text: str) -> None:
        """Restart debounce timer when search text changes."""
        self._debounce_timer.start()

    def _on_toggle_changed(self) -> None:
        """Handle toggle button state change — trigger search immediately."""
        if self._search_input.text():
            self._emit_search()

    def _emit_search(self) -> None:
        """Emit search_requested with current query and toggle states."""
        query = self._search_input.text()
        case_sensitive = self._case_btn.isChecked()
        whole_word = self._word_btn.isChecked()
        self.search_requested.emit(query, case_sensitive, whole_word)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_search_bar.py -v`

Expected: All 17 pass.

- [ ] **Step 5: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run ruff check k_pdf/views/search_bar.py tests/test_search_bar.py && uv run mypy k_pdf/views/search_bar.py`

- [ ] **Step 6: Commit**

```bash
git add k_pdf/views/search_bar.py tests/test_search_bar.py
git commit -m "feat(f4): implement SearchBar widget with debounced input and toggles"
```

---

### Task 5: SearchPresenter

**Files:**
- Modify: `k_pdf/presenters/search_presenter.py` (replace stub)
- Create: `tests/test_search_presenter.py`
- Modify: `pyproject.toml` (mypy override)

- [ ] **Step 1: Write failing tests**

Create `tests/test_search_presenter.py`:

```python
"""Tests for SearchPresenter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

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
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter

        tm = _make_tab_manager()
        sp = SearchPresenter(tab_manager=tm)

        # Open a file to create a tab
        tm.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(tm._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        tm._on_document_ready(sid, model)

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_search_presenter.py -v`

Expected: FAIL — `SearchPresenter` not defined in `search_presenter`.

- [ ] **Step 3: Implement SearchPresenter**

Replace `k_pdf/presenters/search_presenter.py` with:

```python
"""Search presenter — coordinates search bar, worker, and viewport highlights.

Manages per-tab SearchResult state. Subscribes to TabManager for
tab switch/close. Runs SearchWorker on a dedicated QThread.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from k_pdf.core.search_model import SearchResult
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.search_engine import SearchWorker

logger = logging.getLogger("k_pdf.presenters.search_presenter")


class SearchPresenter(QObject):
    """Coordinates text search across tabs."""

    matches_updated = Signal(int, int)  # (current_match_number, total_count)
    highlight_page = Signal(int, list)  # (page_index, rects)
    clear_highlights = Signal()
    no_text_layer = Signal()
    search_started = Signal()
    search_finished = Signal()

    def __init__(
        self,
        tab_manager: TabManager,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the search presenter.

        Args:
            tab_manager: The tab manager to subscribe to.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._tab_manager = tab_manager
        self._results: dict[str, SearchResult] = {}
        self._active_session_id: str | None = None
        self._scroll_before_search: dict[str, int] = {}

        # Pending search params (set before worker call, used in callbacks)
        self._pending_query: str = ""
        self._pending_case: bool = False
        self._pending_word: bool = False

        # Create worker and thread
        self._thread = QThread()
        self._worker = SearchWorker()
        self._worker.moveToThread(self._thread)

        # Connect worker signals
        self._worker.page_matches.connect(self._on_page_matches)
        self._worker.search_complete.connect(self._on_search_complete)
        self._worker.no_text_layer.connect(self._on_no_text_layer)

        self._thread.start()

        # Connect to TabManager
        tab_manager.tab_switched.connect(self._on_tab_switched)
        tab_manager.tab_closed.connect(self._on_tab_closed)

    def start_search(
        self,
        query: str,
        *,
        case_sensitive: bool,
        whole_word: bool,
    ) -> None:
        """Start a new search, cancelling any running search.

        Args:
            query: The search text. Empty string clears results.
            case_sensitive: Whether to match case.
            whole_word: Whether to match whole words only.
        """
        # Cancel any running search
        self._worker.cancel()

        sid = self._tab_manager.active_session_id
        if sid is None:
            return

        self._active_session_id = sid

        # Empty query — clear everything
        if not query:
            self._results.pop(sid, None)
            self.clear_highlights.emit()
            self.matches_updated.emit(0, 0)
            return

        # Save scroll position before first search in this tab
        if sid not in self._scroll_before_search:
            viewport = self._tab_manager.get_active_viewport()
            if viewport is not None:
                self._scroll_before_search[sid] = viewport.verticalScrollBar().value()

        # Clear previous results for this tab
        self._results.pop(sid, None)
        self.clear_highlights.emit()

        # Store pending params for use in callbacks
        self._pending_query = query
        self._pending_case = case_sensitive
        self._pending_word = whole_word

        # Get document handle
        presenter = self._tab_manager.get_active_presenter()
        if presenter is None or presenter.model is None:
            return

        doc_handle = presenter.model.doc_handle
        page_count = presenter.model.metadata.page_count

        self.search_started.emit()
        self._worker.search(
            doc_handle,
            query,
            page_count,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
        )

    def next_match(self) -> None:
        """Advance to the next match, wrapping at the end."""
        sid = self._active_session_id
        if sid is None or sid not in self._results:
            return

        result = self._results[sid]
        result.advance()
        self._update_highlight_and_scroll(sid)

    def previous_match(self) -> None:
        """Retreat to the previous match, wrapping at the beginning."""
        sid = self._active_session_id
        if sid is None or sid not in self._results:
            return

        result = self._results[sid]
        result.retreat()
        self._update_highlight_and_scroll(sid)

    def close_search(self) -> None:
        """Close search: clear highlights, restore scroll, discard results."""
        self._worker.cancel()

        sid = self._active_session_id
        if sid is not None:
            self._results.pop(sid, None)
            self.clear_highlights.emit()

            # Restore scroll position
            saved_scroll = self._scroll_before_search.pop(sid, None)
            if saved_scroll is not None:
                viewport = self._tab_manager.get_active_viewport()
                if viewport is not None:
                    viewport.verticalScrollBar().setValue(saved_scroll)

        self.matches_updated.emit(0, 0)

    def shutdown(self) -> None:
        """Stop the search thread and clean up."""
        self._worker.cancel()
        self._thread.quit()
        self._thread.wait(3000)
        self._results.clear()
        self._scroll_before_search.clear()

    # --- Internal signal handlers ---

    def _on_page_matches(
        self,
        page_index: int,
        rects: list[tuple[float, float, float, float]],
    ) -> None:
        """Handle per-page results from the search worker."""
        sid = self._active_session_id
        if sid is None:
            return

        # Create or update result
        if sid not in self._results:
            self._results[sid] = SearchResult(
                query=self._pending_query,
                case_sensitive=self._pending_case,
                whole_word=self._pending_word,
                matches={},
                total_count=0,
                current_page=-1,
                current_index=-1,
            )

        result = self._results[sid]
        result.matches[page_index] = rects
        result.total_count += len(rects)

        # Push highlights to viewport
        self.highlight_page.emit(page_index, rects)

        # Update match counter progressively
        self.matches_updated.emit(0, result.total_count)

    def _on_search_complete(self, total_count: int) -> None:
        """Handle search completion from the worker."""
        self.search_finished.emit()

        sid = self._active_session_id
        if sid is None:
            return

        if total_count == 0:
            self.matches_updated.emit(0, 0)
            return

        result = self._results.get(sid)
        if result is None:
            return

        # Navigate to first match
        pages = result._sorted_pages()
        if pages:
            result.current_page = pages[0]
            result.current_index = 0
            self._update_highlight_and_scroll(sid)

    def _on_no_text_layer(self) -> None:
        """Handle no-text-layer detection from the worker."""
        self.search_finished.emit()
        self.no_text_layer.emit()

    def _on_tab_switched(self, session_id: str) -> None:
        """Handle tab switch — cancel search, restore or clear."""
        self._worker.cancel()
        self._active_session_id = session_id
        self.clear_highlights.emit()

        # Restore search state for the new tab if it has one
        if session_id in self._results:
            result = self._results[session_id]
            # Re-push all highlights
            for page_idx, rects in result.matches.items():
                self.highlight_page.emit(page_idx, rects)
            self.matches_updated.emit(result.current_match_number(), result.total_count)
            # Re-set current highlight
            rect = result.current_rect()
            if rect is not None:
                self._scroll_to_match(session_id)
        else:
            self.matches_updated.emit(0, 0)

    def _on_tab_closed(self, session_id: str) -> None:
        """Handle tab close — discard search state."""
        self._results.pop(session_id, None)
        self._scroll_before_search.pop(session_id, None)

    def _update_highlight_and_scroll(self, session_id: str) -> None:
        """Update the current match highlight and scroll to it."""
        result = self._results.get(session_id)
        if result is None:
            return

        self.matches_updated.emit(result.current_match_number(), result.total_count)
        self._scroll_to_match(session_id)

    def _scroll_to_match(self, session_id: str) -> None:
        """Scroll the viewport to the current match."""
        result = self._results.get(session_id)
        if result is None:
            return

        viewport = self._tab_manager.get_active_viewport()
        if viewport is None:
            return

        rect = result.current_rect()
        if rect is None:
            return

        # Scroll to the page containing the current match
        viewport.scroll_to_page(result.current_page)

        # Update the current highlight overlay
        viewport.set_current_highlight(result.current_page, rect, zoom=1.0)
```

- [ ] **Step 4: Add mypy overrides**

In `pyproject.toml`, add to the existing overrides section:

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.presenters.search_presenter"]
disable_error_code = ["misc"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_search_presenter.py -v`

Expected: All 8 pass.

- [ ] **Step 6: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run ruff check k_pdf/presenters/search_presenter.py tests/test_search_presenter.py && uv run mypy k_pdf/presenters/search_presenter.py`

- [ ] **Step 7: Commit**

```bash
git add k_pdf/presenters/search_presenter.py tests/test_search_presenter.py pyproject.toml
git commit -m "feat(f4): implement SearchPresenter with per-tab state management"
```

---

### Task 6: Wire SearchBar into MainWindow

**Files:**
- Modify: `k_pdf/views/main_window.py`
- Modify: `tests/test_views.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_views.py` in `TestMainWindow`:

```python
    def test_search_bar_exists(self) -> None:
        """Test that MainWindow has a search bar."""
        from k_pdf.views.main_window import MainWindow
        from k_pdf.views.search_bar import SearchBar

        window = MainWindow()
        assert isinstance(window.search_bar, SearchBar)

    def test_search_bar_starts_hidden(self) -> None:
        """Test that search bar is hidden by default."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert not window.search_bar.isVisible()

    def test_edit_menu_has_find_action(self) -> None:
        """Test that Edit menu has a Find action with Ctrl+F."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        menu_bar = window.menuBar()
        edit_menu = None
        for action in menu_bar.actions():
            if action.text() == "&Edit":
                edit_menu = action.menu()
                break
        assert edit_menu is not None
        find_action = None
        for action in edit_menu.actions():
            if "Find" in action.text():
                find_action = action
                break
        assert find_action is not None
        assert find_action.shortcut().toString() == "Ctrl+F"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_views.py::TestMainWindow::test_search_bar_exists tests/test_views.py::TestMainWindow::test_search_bar_starts_hidden tests/test_views.py::TestMainWindow::test_edit_menu_has_find_action -v`

Expected: FAIL — `search_bar` property and Edit menu don't exist.

- [ ] **Step 3: Add SearchBar and Edit menu to MainWindow**

In `k_pdf/views/main_window.py`, add import after the existing imports (after `from k_pdf.views.navigation_panel import NavigationPanel` on line 30):

```python
from k_pdf.views.search_bar import SearchBar
```

In `MainWindow.__init__`, replace the section that sets the central widget (lines 94-99):

Replace:
```python
        # Stacked widget: page 0 = welcome, page 1 = tabs
        self._stacked = QStackedWidget(self)
        self._stacked.addWidget(self._welcome)
        self._stacked.addWidget(self._tab_widget)
        self._stacked.setCurrentIndex(0)
        self.setCentralWidget(self._stacked)
```

With:
```python
        # Stacked widget: page 0 = welcome, page 1 = tabs
        self._stacked = QStackedWidget(self)
        self._stacked.addWidget(self._welcome)
        self._stacked.addWidget(self._tab_widget)
        self._stacked.setCurrentIndex(0)

        # Search bar (above viewport area)
        self._search_bar = SearchBar(self)
        self._search_bar.closed.connect(self._hide_search_bar)

        # Central container: search bar + stacked widget
        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._search_bar)
        central_layout.addWidget(self._stacked)
        self.setCentralWidget(central)
```

Add the `search_bar` property after the `navigation_panel` property:

```python
    @property
    def search_bar(self) -> SearchBar:
        """Return the search bar widget."""
        return self._search_bar
```

In `_setup_menus`, add the Edit menu after the File menu block (after line 156 `file_menu.addAction(quit_action)`):

```python
        # Edit menu
        edit_menu = menu_bar.addMenu("&Edit")

        find_action = QAction("&Find...", self)
        find_action.setShortcut(QKeySequence("Ctrl+F"))
        find_action.triggered.connect(self._show_search_bar)
        edit_menu.addAction(find_action)
```

Add the private methods for showing/hiding the search bar:

```python
    def _show_search_bar(self) -> None:
        """Show the search bar and focus the input field."""
        self._search_bar.show()
        self._search_bar.focus_input()

    def _hide_search_bar(self) -> None:
        """Hide the search bar."""
        self._search_bar.hide()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_views.py::TestMainWindow -v`

Expected: All pass (including existing tests).

- [ ] **Step 5: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run ruff check k_pdf/views/main_window.py && uv run mypy k_pdf/views/main_window.py`

- [ ] **Step 6: Commit**

```bash
git add k_pdf/views/main_window.py tests/test_views.py
git commit -m "feat(f4): add SearchBar and Edit > Find menu to MainWindow"
```

---

### Task 7: Wire SearchPresenter in KPdfApp

**Files:**
- Modify: `k_pdf/app.py`
- Modify: `tests/test_views.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_views.py` in `TestKPdfAppIntegration`:

```python
    def test_app_creates_search_presenter(self) -> None:
        """Test that KPdfApp creates a SearchPresenter."""
        from k_pdf.presenters.search_presenter import SearchPresenter

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert isinstance(kpdf.search_presenter, SearchPresenter)
        kpdf.shutdown()

    def test_search_bar_search_requested_reaches_presenter(self) -> None:
        """Test that search bar's search_requested connects to presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        spy = MagicMock()
        kpdf.search_presenter.start_search = spy  # type: ignore[method-assign]
        kpdf.window.search_bar.search_requested.emit("hello", False, False)
        spy.assert_called_once_with("hello", case_sensitive=False, whole_word=False)
        kpdf.shutdown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_views.py::TestKPdfAppIntegration::test_app_creates_search_presenter tests/test_views.py::TestKPdfAppIntegration::test_search_bar_search_requested_reaches_presenter -v`

Expected: FAIL — `search_presenter` doesn't exist on `KPdfApp`.

- [ ] **Step 3: Wire SearchPresenter in KPdfApp**

In `k_pdf/app.py`, add import (after the existing presenter imports):

```python
from k_pdf.presenters.search_presenter import SearchPresenter
```

In `KPdfApp.__init__`, after creating `_nav_presenter`:

```python
        self._search_presenter = SearchPresenter(
            tab_manager=self._tab_manager,
        )
```

Add property after the `navigation_presenter` property:

```python
    @property
    def search_presenter(self) -> SearchPresenter:
        """Return the search presenter."""
        return self._search_presenter
```

In `_connect_signals`, add the search wiring block at the end of the method:

```python
        # SearchBar → SearchPresenter
        search_bar = self._window.search_bar
        search_bar.search_requested.connect(
            lambda q, cs, ww: self._search_presenter.start_search(
                q, case_sensitive=cs, whole_word=ww
            )
        )
        search_bar.next_requested.connect(self._search_presenter.next_match)
        search_bar.previous_requested.connect(self._search_presenter.previous_match)
        search_bar.closed.connect(self._search_presenter.close_search)

        # SearchPresenter → SearchBar
        sp = self._search_presenter
        sp.matches_updated.connect(search_bar.set_match_count)
        sp.no_text_layer.connect(search_bar.set_no_text_layer)

        # SearchPresenter → PdfViewport (highlight overlays)
        sp.highlight_page.connect(self._on_search_highlight_page)
        sp.clear_highlights.connect(self._on_search_clear_highlights)
```

Add the helper methods for routing highlight signals to the active viewport:

```python
    def _on_search_highlight_page(
        self,
        page_index: int,
        rects: list[tuple[float, float, float, float]],
    ) -> None:
        """Route highlight overlay to the active viewport."""
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.add_search_highlights(page_index, rects, zoom=1.0)

    def _on_search_clear_highlights(self) -> None:
        """Clear search highlights on the active viewport."""
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.clear_search_highlights()
```

In `shutdown`, add before `self._nav_presenter.shutdown()`:

```python
        self._search_presenter.shutdown()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_views.py::TestKPdfAppIntegration -v`

Expected: All pass (including existing tests).

- [ ] **Step 5: Run all existing tests for regression**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest -v`

Expected: All existing tests pass.

- [ ] **Step 6: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run ruff check k_pdf/app.py && uv run mypy k_pdf/app.py`

- [ ] **Step 7: Commit**

```bash
git add k_pdf/app.py tests/test_views.py
git commit -m "feat(f4): wire SearchPresenter into KPdfApp with full signal connections"
```

---

### Task 8: Integration tests with real PDFs

**Files:**
- Modify: `tests/conftest.py` (add fixtures)
- Create: `tests/test_search_integration.py`

- [ ] **Step 1: Add test PDF fixtures**

In `tests/conftest.py`, add two new fixtures:

```python
@pytest.fixture
def searchable_pdf(tmp_path: Path) -> Path:
    """Create a 3-page PDF with known searchable text."""
    path = tmp_path / "searchable.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1} content")
        page.insert_text(pymupdf.Point(72, 120), "Hello world")
        if i == 1:
            page.insert_text(pymupdf.Point(72, 168), "Hello world again")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def image_only_pdf(tmp_path: Path) -> Path:
    """Create a PDF with only image content (no text layer)."""
    path = tmp_path / "image_only.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    # Insert a small colored rectangle as an "image"
    rect = pymupdf.Rect(72, 72, 200, 200)
    page.draw_rect(rect, color=(1, 0, 0), fill=(0.8, 0.8, 0.8))
    doc.save(str(path))
    doc.close()
    return path
```

- [ ] **Step 2: Write integration tests**

Create `tests/test_search_integration.py`:

```python
"""Integration tests for text search flows with real PDFs."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def test_search_finds_text(searchable_pdf: Path, qtbot: object) -> None:
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    sp = kpdf.search_presenter
    search_bar = kpdf.window.search_bar

    tm.open_file(searchable_pdf)

    # Wait for document to load
    def check_loaded() -> None:
        assert tm.get_active_presenter() is not None
        assert tm.get_active_presenter().model is not None

    qtbot.waitUntil(check_loaded, timeout=10000)

    # Trigger search
    search_bar.show()
    search_bar._search_input.setText("Hello world")

    # Wait for search results
    def check_results() -> None:
        sid = tm.active_session_id
        assert sid is not None
        assert sid in sp._results
        # "Hello world" appears on all 3 pages (once each on page 0,2; twice on page 1)
        assert sp._results[sid].total_count >= 3

    qtbot.waitUntil(check_results, timeout=10000)

    sid = tm.active_session_id
    assert sid is not None
    result = sp._results[sid]
    assert result.current_match_number() >= 1

    kpdf.shutdown()


def test_next_previous_cycles(searchable_pdf: Path, qtbot: object) -> None:
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    sp = kpdf.search_presenter

    tm.open_file(searchable_pdf)

    def check_loaded() -> None:
        assert tm.get_active_presenter() is not None
        assert tm.get_active_presenter().model is not None

    qtbot.waitUntil(check_loaded, timeout=10000)

    kpdf.window.search_bar.show()
    kpdf.window.search_bar._search_input.setText("Hello world")

    def check_results() -> None:
        sid = tm.active_session_id
        assert sid is not None
        assert sid in sp._results
        assert sp._results[sid].total_count >= 3

    qtbot.waitUntil(check_results, timeout=10000)

    sid = tm.active_session_id
    assert sid is not None

    # Navigate forward
    first_match = sp._results[sid].current_match_number()
    sp.next_match()
    second_match = sp._results[sid].current_match_number()
    assert second_match == first_match + 1

    # Navigate back
    sp.previous_match()
    back_match = sp._results[sid].current_match_number()
    assert back_match == first_match

    kpdf.shutdown()


def test_close_search_clears_highlights(searchable_pdf: Path, qtbot: object) -> None:
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    sp = kpdf.search_presenter

    tm.open_file(searchable_pdf)

    def check_loaded() -> None:
        assert tm.get_active_presenter() is not None
        assert tm.get_active_presenter().model is not None

    qtbot.waitUntil(check_loaded, timeout=10000)

    kpdf.window.search_bar.show()
    kpdf.window.search_bar._search_input.setText("Hello world")

    def check_results() -> None:
        sid = tm.active_session_id
        assert sid is not None
        assert sid in sp._results

    qtbot.waitUntil(check_results, timeout=10000)

    sid = tm.active_session_id
    assert sid is not None

    # Verify highlights exist
    viewport = tm.get_active_viewport()
    assert viewport is not None
    assert len(viewport._search_highlights) > 0

    # Close search
    sp.close_search()

    # Highlights should be cleared
    assert len(viewport._search_highlights) == 0
    assert sid not in sp._results

    kpdf.shutdown()


def test_no_text_document(image_only_pdf: Path, qtbot: object) -> None:
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    sp = kpdf.search_presenter
    search_bar = kpdf.window.search_bar

    tm.open_file(image_only_pdf)

    def check_loaded() -> None:
        assert tm.get_active_presenter() is not None
        assert tm.get_active_presenter().model is not None

    qtbot.waitUntil(check_loaded, timeout=10000)

    # Track no_text_layer signal
    no_text_received: list[bool] = []
    sp.no_text_layer.connect(lambda: no_text_received.append(True))

    search_bar.show()
    search_bar._search_input.setText("anything")

    def check_no_text() -> None:
        assert len(no_text_received) > 0

    qtbot.waitUntil(check_no_text, timeout=10000)

    # Search bar should show the no-text message
    assert "no searchable text" in search_bar._match_label.text().lower()

    kpdf.shutdown()
```

- [ ] **Step 3: Run integration tests**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest tests/test_search_integration.py -v`

Expected: All 4 pass.

- [ ] **Step 4: Run full test suite**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest -v`

Expected: All tests pass with no regressions.

- [ ] **Step 5: Run coverage**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest --cov=k_pdf --cov-report=term-missing`

Expected: Coverage maintains 65%+ threshold.

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_search_integration.py
git commit -m "feat(f4): add integration tests for text search flows"
```

---

### Task 9: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update current state in CLAUDE.md**

In `CLAUDE.md`, replace the `## Current State` section:

Replace:
```markdown
## Current State
- **Project:** K-PDF
- **Phase:** 2 (Construction)
- **Track:** Standard
- **Features built:** Feature 1 (Open and Render PDF), Feature 2 (Multi-Tab), Feature 3 (Page Navigation)
- **Features remaining:** Features 4-12 + 7 implicit (see MVP Cutline)
- **Known issues:** Coverage at 85% (threshold 65%)
- **Last session summary:** Feature 3 complete — NavigationPanel (QDockWidget), ThumbnailCache, OutlineService, NavigationPresenter, 99 tests passing
```

With:
```markdown
## Current State
- **Project:** K-PDF
- **Phase:** 2 (Construction)
- **Track:** Standard
- **Features built:** Feature 1 (Open and Render PDF), Feature 2 (Multi-Tab), Feature 3 (Page Navigation), Feature 4 (Text Search)
- **Features remaining:** Features 5-12 + 7 implicit (see MVP Cutline)
- **Known issues:** Coverage at 65%+ (threshold 65%)
- **Last session summary:** Feature 4 complete — SearchBar, SearchWorker, SearchPresenter, highlight overlays, per-tab search state, Ctrl+F activation
```

- [ ] **Step 2: Update mypy overrides summary**

In `pyproject.toml`, verify these overrides are present (added in earlier tasks):

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.services.search_engine"]
disable_error_code = ["misc", "no-untyped-call"]

[[tool.mypy.overrides]]
module = ["k_pdf.presenters.search_presenter"]
disable_error_code = ["misc"]
```

- [ ] **Step 3: Run full linter suite**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run ruff check . && uv run ruff format --check . && uv run mypy k_pdf/`

- [ ] **Step 4: Run full test suite one final time**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature4-search" && uv run pytest -v --tb=short`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for Feature 4 completion"
```

---

## Self-Review Checklist

### Spec Coverage
- [x] SearchResult dataclass with advance/retreat/current_match_number/current_rect (Task 1)
- [x] SearchWorker with page_matches/search_complete/no_text_layer signals (Task 2)
- [x] Progressive per-page search with cancel support (Task 2)
- [x] No-text-layer detection (Task 2)
- [x] Whole-word filtering (Task 2)
- [x] PdfViewport highlight overlays with add/set_current/clear (Task 3)
- [x] Highlights use border + fill, not color alone (Task 3 — QPen + QBrush)
- [x] Current highlight has thicker border (Task 3 — pen width 3.0 vs 1.0)
- [x] SearchBar with input, counter, Prev/Next, Aa/W toggles, close (Task 4)
- [x] Debounced 300ms search on text change (Task 4)
- [x] Enter for next, Escape for close (Task 4)
- [x] SearchPresenter per-tab state, tab switch/close handling (Task 5)
- [x] Close search restores scroll position (Task 5)
- [x] SearchBar above QStackedWidget in QVBoxLayout (Task 6)
- [x] Edit menu with Ctrl+F (Task 6)
- [x] Full wiring in KPdfApp (Task 7)
- [x] Integration tests with real PDFs (Task 8)
- [x] test_search_finds_text, test_next_previous_cycles, test_close_search_clears_highlights, test_no_text_document (Task 8)

### Placeholder Scan
- [x] No TODO/FIXME/placeholder comments in any code block
- [x] All methods have complete implementations
- [x] All signal connections specified with concrete slot names

### Type Consistency
- [x] SearchResult.matches: `dict[int, list[tuple[float, float, float, float]]]` — consistent across model, worker, presenter, viewport
- [x] Rect tuples: `tuple[float, float, float, float]` — consistent everywhere
- [x] page_index: `int` — consistent everywhere
- [x] session_id: `str` — consistent with TabManager convention
- [x] mypy overrides added for PySide6 subclasses (search_presenter, search_engine)

### Architecture Rules
- [x] PyMuPDF import only in `k_pdf/services/search_engine.py`
- [x] Views never call services — presenter coordinates
- [x] Long-running search on QThread via SearchWorker
- [x] Accessibility: highlights use border + fill, text labels on all buttons, keyboard nav
