"""Tests for NavigationPanel view."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from k_pdf.core.outline_model import OutlineNode
from k_pdf.views.navigation_panel import NavigationPanel

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def test_panel_has_two_tabs() -> None:
    panel = NavigationPanel()
    assert panel.tab_widget.count() == 2
    assert panel.tab_widget.tabText(0) == "Thumbnails"
    assert panel.tab_widget.tabText(1) == "Outline"


def test_thumbnail_clicked_signal() -> None:
    panel = NavigationPanel()
    spy = MagicMock()
    panel.thumbnail_clicked.connect(spy)

    img = QImage(90, 120, QImage.Format.Format_RGB888)
    img.fill(0)
    panel.add_thumbnail(0, QPixmap.fromImage(img))

    # Simulate click on first item
    panel._thumbnail_list.setCurrentRow(0)
    spy.assert_called_once_with(0)


def test_outline_clicked_signal() -> None:
    panel = NavigationPanel()
    spy = MagicMock()
    panel.outline_clicked.connect(spy)

    nodes = [OutlineNode(title="Chapter 1", page=0, children=[])]
    panel.set_outline(nodes)

    # Simulate click on first item
    item = panel._outline_tree.topLevelItem(0)
    panel._outline_tree.setCurrentItem(item)
    spy.assert_called_once_with(0)


def test_empty_outline_shows_label() -> None:
    panel = NavigationPanel()
    panel.set_outline([])
    assert panel._outline_stack.currentIndex() == 1


def test_invalid_outline_entry_no_emit() -> None:
    panel = NavigationPanel()
    spy = MagicMock()
    panel.outline_clicked.connect(spy)

    nodes = [OutlineNode(title="Bad Link", page=-1, children=[])]
    panel.set_outline(nodes)

    item = panel._outline_tree.topLevelItem(0)
    panel._outline_tree.setCurrentItem(item)
    spy.assert_not_called()


def test_set_current_page_highlights_thumbnail() -> None:
    panel = NavigationPanel()
    img = QImage(90, 120, QImage.Format.Format_RGB888)
    img.fill(0)
    panel.add_thumbnail(0, QPixmap.fromImage(img))
    panel.add_thumbnail(1, QPixmap.fromImage(img))

    panel.set_current_page(1)
    assert panel._thumbnail_list.currentRow() == 1


def test_clear_resets_both_tabs() -> None:
    panel = NavigationPanel()
    img = QImage(90, 120, QImage.Format.Format_RGB888)
    img.fill(0)
    panel.add_thumbnail(0, QPixmap.fromImage(img))
    panel.set_outline([OutlineNode(title="Test", page=0, children=[])])

    panel.clear()
    assert panel._thumbnail_list.count() == 0
    assert panel._outline_tree.topLevelItemCount() == 0
