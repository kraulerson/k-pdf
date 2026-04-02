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
                logger.debug("Error reading text on page %d", i, exc_info=True)
                continue

        if not has_any_text:
            self.no_text_layer.emit()
            return

        # Build search flags
        # PyMuPDF 1.27 search_for is always case-insensitive;
        # case-sensitive filtering is applied as a post-filter step.
        import pymupdf

        flags = pymupdf.TEXT_PRESERVE_LIGATURES | pymupdf.TEXT_PRESERVE_WHITESPACE

        total_count = 0
        for i in range(page_count):
            if self._cancelled:
                return

            try:
                page = doc_handle[i]
                results = page.search_for(query, flags=flags)

                if case_sensitive:
                    results = self._filter_case_sensitive(page, query, results)

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

    def _filter_case_sensitive(
        self,
        page: Any,
        query: str,
        results: list[Any],
    ) -> list[Any]:
        """Filter search results to case-sensitive matches only.

        PyMuPDF 1.27 search_for is always case-insensitive, so we
        post-filter by checking the page text for exact-case occurrences.

        Args:
            page: A pymupdf page object.
            query: The search text (exact case).
            results: List of Rect results from search_for().

        Returns:
            Filtered list of Rect results that match the exact case.
        """
        if not results:
            return results

        page_text = page.get_text("text")
        if not page_text:
            return results

        # Count exact-case occurrences in the text
        filtered = []
        search_start = 0
        for rect in results:
            pos = page_text.find(query, search_start)
            if pos == -1:
                # No more exact-case matches — skip remaining rects
                continue
            filtered.append(rect)
            search_start = pos + len(query)

        return filtered

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
