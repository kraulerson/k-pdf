"""Tests for PageManagerPanel — page management dock widget."""

from __future__ import annotations

from PySide6.QtGui import QPixmap

from k_pdf.views.page_manager_panel import PageManagerPanel


class TestPageManagerPanelThumbnails:
    def test_set_thumbnails_populates_grid(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        pixmaps = [QPixmap(100, 130) for _ in range(5)]
        panel.set_thumbnails(pixmaps)
        assert panel._thumbnail_list.count() == 5

    def test_set_thumbnails_labels(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        pixmaps = [QPixmap(100, 130) for _ in range(3)]
        panel.set_thumbnails(pixmaps)
        item = panel._thumbnail_list.item(0)
        assert item is not None
        assert "Page 1" in item.text()

    def test_set_thumbnails_clears_old(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.set_thumbnails([QPixmap(100, 130) for _ in range(5)])
        panel.set_thumbnails([QPixmap(100, 130) for _ in range(2)])
        assert panel._thumbnail_list.count() == 2

    def test_update_thumbnail_replaces_single(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.set_thumbnails([QPixmap(100, 130) for _ in range(3)])
        new_pixmap = QPixmap(100, 130)
        panel.update_thumbnail(1, new_pixmap)
        assert panel._thumbnail_list.count() == 3  # count unchanged

    def test_get_selected_pages_empty(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.set_thumbnails([QPixmap(100, 130) for _ in range(3)])
        assert panel.get_selected_pages() == []

    def test_get_selected_pages_single(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.set_thumbnails([QPixmap(100, 130) for _ in range(3)])
        item = panel._thumbnail_list.item(1)
        assert item is not None
        item.setSelected(True)
        assert panel.get_selected_pages() == [1]

    def test_get_selected_pages_multi(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.set_thumbnails([QPixmap(100, 130) for _ in range(5)])
        for i in [0, 2, 4]:
            item = panel._thumbnail_list.item(i)
            assert item is not None
            item.setSelected(True)
        assert panel.get_selected_pages() == [0, 2, 4]


class TestPageManagerPanelSignals:
    def test_rotate_left_signal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        with qtbot.waitSignal(panel.rotate_left_clicked, timeout=1000):
            panel._rotate_left_action.trigger()

    def test_rotate_right_signal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        with qtbot.waitSignal(panel.rotate_right_clicked, timeout=1000):
            panel._rotate_right_action.trigger()

    def test_delete_signal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        with qtbot.waitSignal(panel.delete_clicked, timeout=1000):
            panel._delete_action.trigger()

    def test_add_signal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        with qtbot.waitSignal(panel.add_clicked, timeout=1000):
            panel._add_action.trigger()


class TestPageManagerPanelProgress:
    def test_show_progress(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.show()
        panel.show_progress("Deleting pages...")
        assert panel._progress_bar.isVisible()

    def test_hide_progress(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.show()
        panel.show_progress("Working...")
        panel.hide_progress()
        assert not panel._progress_bar.isVisible()


class TestPageManagerPanelPageCount:
    def test_set_page_count_label(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.set_page_count_label(42)
        assert "42" in panel._page_count_label.text()

    def test_no_document_state(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        # Initially should show no-document message
        assert "No document" in panel._page_count_label.text()


class TestPageManagerPanelButtons:
    def test_set_buttons_enabled(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.set_buttons_enabled(False)
        assert not panel._rotate_left_action.isEnabled()
        assert not panel._delete_action.isEnabled()
        panel.set_buttons_enabled(True)
        assert panel._rotate_left_action.isEnabled()
        assert panel._delete_action.isEnabled()
