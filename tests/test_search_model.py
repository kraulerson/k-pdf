"""Tests for SearchResult dataclass."""

from __future__ import annotations

from k_pdf.core.search_model import SearchResult


class TestSearchResultConstruction:
    """Tests for SearchResult construction and mutability."""

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
    """Tests for SearchResult advance/retreat navigation."""

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
    """Tests for SearchResult helper methods."""

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
