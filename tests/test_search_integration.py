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
        assert tm.get_active_presenter().model is not None  # type: ignore[union-attr]

    qtbot.waitUntil(check_loaded, timeout=10000)  # type: ignore[union-attr]

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

    qtbot.waitUntil(check_results, timeout=10000)  # type: ignore[union-attr]

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
        assert tm.get_active_presenter().model is not None  # type: ignore[union-attr]

    qtbot.waitUntil(check_loaded, timeout=10000)  # type: ignore[union-attr]

    kpdf.window.search_bar.show()
    kpdf.window.search_bar._search_input.setText("Hello world")

    def check_results() -> None:
        sid = tm.active_session_id
        assert sid is not None
        assert sid in sp._results
        assert sp._results[sid].total_count >= 3

    qtbot.waitUntil(check_results, timeout=10000)  # type: ignore[union-attr]

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
        assert tm.get_active_presenter().model is not None  # type: ignore[union-attr]

    qtbot.waitUntil(check_loaded, timeout=10000)  # type: ignore[union-attr]

    kpdf.window.search_bar.show()
    kpdf.window.search_bar._search_input.setText("Hello world")

    def check_results() -> None:
        sid = tm.active_session_id
        assert sid is not None
        assert sid in sp._results

    qtbot.waitUntil(check_results, timeout=10000)  # type: ignore[union-attr]

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
        assert tm.get_active_presenter().model is not None  # type: ignore[union-attr]

    qtbot.waitUntil(check_loaded, timeout=10000)  # type: ignore[union-attr]

    # Track no_text_layer signal
    no_text_received: list[bool] = []
    sp.no_text_layer.connect(lambda: no_text_received.append(True))

    search_bar.show()
    search_bar._search_input.setText("anything")

    def check_no_text() -> None:
        assert len(no_text_received) > 0

    qtbot.waitUntil(check_no_text, timeout=10000)  # type: ignore[union-attr]

    # Search bar should show the no-text message
    assert "no searchable text" in search_bar._match_label.text().lower()

    kpdf.shutdown()
