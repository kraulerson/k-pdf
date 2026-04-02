"""Search result model.

SearchResult is a mutable dataclass tracking match positions and
navigation cursor. Pure data — no Qt or PyMuPDF imports.
"""

from __future__ import annotations

from dataclasses import dataclass


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
