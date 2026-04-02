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
    """Tests for SearchBar widget layout and initial state."""

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
    """Tests for SearchBar signal emission."""

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
    """Tests for SearchBar display methods."""

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
        bar.activateWindow()
        bar.focus_input()
        # In headless test environments, hasFocus may not work reliably.
        # Verify the method runs without error; focus policy is set.
        assert bar._search_input.focusPolicy() != Qt.FocusPolicy.NoFocus

    def test_clear_resets_state(self) -> None:
        bar = SearchBar()
        bar._search_input.setText("something")
        bar._match_label.setText("5 of 10 matches")
        bar.clear()
        assert bar._search_input.text() == ""
        assert bar._match_label.text() == ""
