"""Integration tests for navigation panel flows."""

from __future__ import annotations

from pathlib import Path

import pymupdf
from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def test_open_pdf_shows_thumbnails(valid_pdf: Path, qtbot: object) -> None:
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    panel = kpdf.window.navigation_panel
    tm = kpdf.tab_manager

    tm.open_file(valid_pdf)

    def check_thumbnails() -> None:
        assert panel._thumbnail_list.count() == 3

    qtbot.waitUntil(check_thumbnails, timeout=10000)
    kpdf.shutdown()


def test_open_pdf_with_outline(pdf_with_outline: Path, qtbot: object) -> None:
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    panel = kpdf.window.navigation_panel
    tm = kpdf.tab_manager

    tm.open_file(pdf_with_outline)

    def check_outline() -> None:
        assert panel._outline_tree.topLevelItemCount() == 3

    qtbot.waitUntil(check_outline, timeout=10000)

    # Check nested structure
    ch1 = panel._outline_tree.topLevelItem(0)
    assert ch1 is not None
    assert ch1.text(0) == "Chapter 1"
    assert ch1.childCount() == 2

    kpdf.shutdown()


def test_close_last_tab_clears_panel(valid_pdf: Path, qtbot: object) -> None:
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    panel = kpdf.window.navigation_panel
    tm = kpdf.tab_manager

    tm.open_file(valid_pdf)

    def check_loaded() -> None:
        assert panel._thumbnail_list.count() == 3

    qtbot.waitUntil(check_loaded, timeout=10000)

    sid = next(iter(tm._tabs))
    tm.close_tab(sid)

    assert panel._thumbnail_list.count() == 0

    kpdf.shutdown()


def test_switch_tabs_updates_panel(valid_pdf: Path, tmp_path: Path, qtbot: object) -> None:
    # Create a 5-page PDF
    path2 = tmp_path / "five.pdf"
    doc = pymupdf.open()
    for i in range(5):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1}")
    doc.save(str(path2))
    doc.close()

    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    panel = kpdf.window.navigation_panel
    tm = kpdf.tab_manager

    tm.open_file(valid_pdf)

    def check_first() -> None:
        assert panel._thumbnail_list.count() == 3

    qtbot.waitUntil(check_first, timeout=10000)

    tm.open_file(path2)

    def check_second() -> None:
        assert panel._thumbnail_list.count() == 5

    qtbot.waitUntil(check_second, timeout=10000)

    kpdf.shutdown()
