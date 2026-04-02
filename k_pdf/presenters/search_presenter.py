"""Search presenter — coordinates search bar, worker, and viewport highlights.

Manages per-tab SearchResult state. Subscribes to TabManager for
tab switch/close. Runs SearchWorker on a dedicated QThread.
"""

from __future__ import annotations

import logging

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
