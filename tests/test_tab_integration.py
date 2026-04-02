"""Integration tests for multi-tab document flows."""

from __future__ import annotations

from pathlib import Path

import pymupdf
from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestMultiTabIntegration:
    """Integration tests for multi-tab flows with real PDFs."""

    def test_open_two_files_two_tabs(self, valid_pdf: Path, tmp_path: Path, qtbot: object) -> None:
        """Test opening two different PDFs creates two tabs."""
        # Create a second PDF
        path2 = tmp_path / "second.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), "Second doc")
        doc.save(str(path2))
        doc.close()

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        tm = kpdf.tab_manager
        tw = kpdf.window.tab_widget

        # Open first file
        tm.open_file(valid_pdf)

        def check_first_tab() -> None:
            assert tw.count() == 1
            assert tw.tabText(0) != "Loading..."

        qtbot.waitUntil(check_first_tab, timeout=5000)
        assert tw.tabText(0) == valid_pdf.name

        # Open second file
        tm.open_file(path2)

        def check_second_tab() -> None:
            assert tw.count() == 2
            assert tw.tabText(1) != "Loading..."

        qtbot.waitUntil(check_second_tab, timeout=5000)
        assert tw.tabText(1) == "second.pdf"

        kpdf.shutdown()

    def test_close_tab_shows_welcome(self, valid_pdf: Path, qtbot: object) -> None:
        """Test that closing the only tab shows the welcome screen."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        tm = kpdf.tab_manager
        tw = kpdf.window.tab_widget

        # Open a file
        tm.open_file(valid_pdf)

        def check_loaded() -> None:
            assert tw.count() == 1
            assert tw.tabText(0) != "Loading..."

        qtbot.waitUntil(check_loaded, timeout=5000)

        # Stacked widget should be on tabs page
        assert kpdf.window.stacked_widget.currentIndex() == 1

        # Close the tab
        session_id = next(iter(tm._tabs))
        tm.close_tab(session_id)

        # Should be back to welcome
        assert tw.count() == 0
        assert kpdf.window.stacked_widget.currentIndex() == 0

        kpdf.shutdown()

    def test_switch_tab_preserves_state(
        self, valid_pdf: Path, tmp_path: Path, qtbot: object
    ) -> None:
        """Test that switching tabs preserves each tab's viewport state."""
        # Create a second PDF with different page count
        path2 = tmp_path / "five_pages.pdf"
        doc = pymupdf.open()
        for i in range(5):
            page = doc.new_page(width=612, height=792)
            page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1}")
        doc.save(str(path2))
        doc.close()

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        tm = kpdf.tab_manager
        tw = kpdf.window.tab_widget

        # Open both files
        tm.open_file(valid_pdf)

        def check_first() -> None:
            assert tw.count() == 1
            assert tw.tabText(0) != "Loading..."

        qtbot.waitUntil(check_first, timeout=5000)

        tm.open_file(path2)

        def check_second() -> None:
            assert tw.count() == 2
            assert tw.tabText(1) != "Loading..."

        qtbot.waitUntil(check_second, timeout=5000)

        # Get session IDs
        sids = list(tm._tabs.keys())
        ctx0 = tm._tabs[sids[0]]
        ctx1 = tm._tabs[sids[1]]

        # Each viewport has its own pages
        assert ctx0.viewport is not None
        assert ctx1.viewport is not None
        assert len(ctx0.viewport._pages) == 3  # valid_pdf has 3 pages
        assert len(ctx1.viewport._pages) == 5  # five_pages.pdf has 5 pages

        # Switch to first tab
        tm.activate_tab(sids[0])
        assert tw.currentIndex() == 0

        # Pages are still correct after switch
        assert len(ctx0.viewport._pages) == 3
        assert len(ctx1.viewport._pages) == 5

        kpdf.shutdown()
