"""Integration tests for MainWindow, PdfViewport, and KPdfApp."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.core.document_model import PageInfo
from k_pdf.core.zoom_model import FitMode
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.views.pdf_viewport import PdfViewport, ViewportState

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestPdfViewport:
    """Tests for PdfViewport states and page display."""

    def test_initial_state_is_empty(self) -> None:
        """Test viewport starts in EMPTY state."""
        viewport = PdfViewport()
        assert viewport.state == ViewportState.EMPTY

    def test_viewport_has_no_welcome_widget(self) -> None:
        """Test that PdfViewport does not have a welcome overlay."""
        viewport = PdfViewport()
        assert not hasattr(viewport, "welcome_widget")

    def test_set_loading_changes_state(self) -> None:
        """Test set_loading transitions to LOADING state."""
        viewport = PdfViewport()
        viewport.set_loading("test.pdf")
        assert viewport.state == ViewportState.LOADING

    def test_set_error_changes_state(self) -> None:
        """Test set_error transitions to ERROR state."""
        viewport = PdfViewport()
        viewport.set_error("Something went wrong")
        assert viewport.state == ViewportState.ERROR

    def test_set_document_creates_placeholders(self) -> None:
        """Test set_document transitions to SUCCESS and creates page items."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
            PageInfo(index=1, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        assert viewport.state == ViewportState.SUCCESS

    def test_set_page_pixmap_replaces_placeholder(self) -> None:
        """Test set_page_pixmap replaces the placeholder item."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=100, height=100, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        img = QImage(100, 100, QImage.Format.Format_RGB888)
        img.fill(0)
        viewport.set_page_pixmap(0, QPixmap.fromImage(img))
        # Verify the item was replaced (no crash, item exists)
        assert 0 in viewport._page_items

    def test_scroll_to_page_exists(self) -> None:
        """Test that scroll_to_page method exists and doesn't raise."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
            PageInfo(index=1, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
            PageInfo(index=2, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        viewport.scroll_to_page(1)

    def test_current_page_changed_signal_exists(self) -> None:
        """Test that current_page_changed signal exists."""
        viewport = PdfViewport()
        spy = MagicMock()
        viewport.current_page_changed.connect(spy)

    def test_add_search_highlights(self) -> None:
        """Test adding search highlight overlays to a page."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        viewport.add_search_highlights(0, [(10.0, 20.0, 100.0, 40.0)], zoom=1.0)
        assert len(viewport._search_highlights) == 1

    def test_add_search_highlights_multiple_rects(self) -> None:
        """Test adding multiple highlight rects on one page."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        rects = [(10.0, 20.0, 100.0, 40.0), (50.0, 60.0, 150.0, 80.0)]
        viewport.add_search_highlights(0, rects, zoom=1.0)
        assert len(viewport._search_highlights) == 2

    def test_clear_search_highlights(self) -> None:
        """Test clearing all search highlights."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        viewport.add_search_highlights(0, [(10.0, 20.0, 100.0, 40.0)], zoom=1.0)
        assert len(viewport._search_highlights) == 1
        viewport.clear_search_highlights()
        assert len(viewport._search_highlights) == 0

    def test_set_current_highlight(self) -> None:
        """Test setting the current match highlight."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        viewport.add_search_highlights(0, [(10.0, 20.0, 100.0, 40.0)], zoom=1.0)
        # Should not raise — sets a distinct highlight
        viewport.set_current_highlight(0, (10.0, 20.0, 100.0, 40.0), zoom=1.0)
        # Current highlight item is tracked separately
        assert viewport._current_highlight is not None

    def test_clear_removes_current_highlight(self) -> None:
        """Test that clear also removes the current highlight."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        viewport.add_search_highlights(0, [(10.0, 20.0, 100.0, 40.0)], zoom=1.0)
        viewport.set_current_highlight(0, (10.0, 20.0, 100.0, 40.0), zoom=1.0)
        viewport.clear_search_highlights()
        assert viewport._current_highlight is None
        assert len(viewport._search_highlights) == 0

    def test_highlights_on_invalid_page_ignored(self) -> None:
        """Test that highlights on a non-existent page are silently ignored."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        viewport.add_search_highlights(5, [(10.0, 20.0, 100.0, 40.0)], zoom=1.0)
        assert len(viewport._search_highlights) == 0

    def test_viewport_resized_signal_exists(self) -> None:
        """Test that viewport_resized signal exists."""
        viewport = PdfViewport()
        spy = MagicMock()
        viewport.viewport_resized.connect(spy)

    def test_zoom_at_cursor_signal_exists(self) -> None:
        """Test that zoom_at_cursor signal exists."""
        viewport = PdfViewport()
        spy = MagicMock()
        viewport.zoom_at_cursor.connect(spy)

    def test_set_document_with_zoom(self) -> None:
        """Test set_document applies zoom to page dimensions."""
        viewport = PdfViewport()
        pages = [
            PageInfo(
                index=0,
                width=612,
                height=792,
                rotation=0,
                has_text=True,
                annotation_count=0,
            ),
        ]
        viewport.set_document(pages, zoom=2.0)
        assert viewport.state == ViewportState.SUCCESS
        # Scene rect should reflect zoomed page width
        scene_rect = viewport.scene().sceneRect()
        assert scene_rect.width() >= 612 * 2.0

    def test_resize_event_emits_viewport_resized(self, qtbot: object) -> None:
        """Test that resizeEvent emits viewport_resized signal."""
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QResizeEvent

        viewport = PdfViewport()
        spy = MagicMock()
        viewport.viewport_resized.connect(spy)
        viewport.show()
        viewport.resize(800, 600)

        # Force a resize event
        event = QResizeEvent(QSize(800, 600), QSize(400, 300))
        viewport.resizeEvent(event)

        assert spy.call_count >= 1
        width, height = spy.call_args[0]
        assert width > 0
        assert height > 0

    def test_wheel_event_with_ctrl_emits_zoom_at_cursor(self, qtbot: object) -> None:
        """Test that Ctrl+scroll emits zoom_at_cursor signal."""
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QWheelEvent

        viewport = PdfViewport()
        pages = [
            PageInfo(
                index=0,
                width=612,
                height=792,
                rotation=0,
                has_text=True,
                annotation_count=0,
            ),
        ]
        viewport.set_document(pages)
        viewport.show()
        viewport.resize(800, 600)

        spy = MagicMock()
        viewport.zoom_at_cursor.connect(spy)

        # Simulate Ctrl+scroll up
        event = QWheelEvent(
            QPointF(400, 300),  # pos
            QPointF(400, 300),  # globalPos
            QPoint(0, 120),  # pixelDelta
            QPoint(0, 120),  # angleDelta
            Qt.MouseButton.NoButton,  # buttons
            Qt.KeyboardModifier.ControlModifier,  # modifiers
            Qt.ScrollPhase.NoScrollPhase,
            False,  # inverted
        )
        viewport.wheelEvent(event)
        spy.assert_called_once()
        step, _pos = spy.call_args[0]
        assert step > 0  # scroll up = zoom in


class TestMainWindow:
    """Tests for MainWindow with multi-tab support."""

    def test_initial_state_shows_welcome(self) -> None:
        """Test that MainWindow starts showing the welcome widget."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert window.stacked_widget.currentIndex() == 0

    def test_tab_widget_is_configured(self) -> None:
        """Test QTabWidget has closable, movable, document-mode tabs."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        tw = window.tab_widget
        assert tw.tabsClosable() is True
        assert tw.isMovable() is True
        assert tw.documentMode() is True

    def test_navigation_panel_exists(self) -> None:
        """Test that MainWindow has a navigation panel dock widget."""
        from k_pdf.views.main_window import MainWindow
        from k_pdf.views.navigation_panel import NavigationPanel

        window = MainWindow()
        assert isinstance(window.navigation_panel, NavigationPanel)

    def test_navigation_panel_starts_hidden(self) -> None:
        """Test that navigation panel is hidden by default."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert not window.navigation_panel.isVisible()

    def test_tab_close_requested_signal(self) -> None:
        """Test that tab_close_requested signal exists and is emittable."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        spy = MagicMock()
        window.tab_close_requested.connect(spy)
        window.tab_close_requested.emit()
        spy.assert_called_once()

    def test_file_open_requested_signal(self) -> None:
        """Test that file_open_requested signal can be emitted and received."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        spy = MagicMock()
        window.file_open_requested.connect(spy)
        window.file_open_requested.emit(Path("/tmp/test.pdf"))
        spy.assert_called_once_with(Path("/tmp/test.pdf"))

    def test_update_page_status(self) -> None:
        """Test status bar page label updates."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        window.update_page_status(3, 10)
        assert window._page_label.text() == "Page 3 of 10"

    def test_welcome_open_button_exists(self) -> None:
        """Test that WelcomeWidget open button is connected."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert hasattr(window._welcome, "open_clicked")

    def test_show_tabs_switches_stacked_widget(self) -> None:
        """Test show_tabs switches to tab widget page."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        window.show_tabs()
        assert window.stacked_widget.currentIndex() == 1

    def test_show_welcome_switches_stacked_widget(self) -> None:
        """Test show_welcome switches back to welcome page."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        window.show_tabs()
        window.show_welcome()
        assert window.stacked_widget.currentIndex() == 0
        assert window._page_label.text() == "No document"

    def test_search_bar_exists(self) -> None:
        """Test that MainWindow has a search bar."""
        from k_pdf.views.main_window import MainWindow
        from k_pdf.views.search_bar import SearchBar

        window = MainWindow()
        assert isinstance(window.search_bar, SearchBar)

    def test_search_bar_starts_hidden(self) -> None:
        """Test that search bar is hidden by default."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert not window.search_bar.isVisible()

    def test_edit_menu_has_find_action(self) -> None:
        """Test that Edit menu has a Find action with Ctrl+F."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        menu_bar = window.menuBar()
        edit_menu = None
        for action in menu_bar.actions():
            if action.text() == "&Edit":
                edit_menu = action.menu()
                break
        assert edit_menu is not None
        find_action = None
        for action in edit_menu.actions():
            if "Find" in action.text():
                find_action = action
                break
        assert find_action is not None
        assert find_action.shortcut().toString() == "Ctrl+F"

    def test_zoom_toolbar_exists(self) -> None:
        """Test that MainWindow has a zoom toolbar."""
        from k_pdf.views.main_window import MainWindow
        from k_pdf.views.zoom_toolbar import ZoomToolBar

        window = MainWindow()
        assert isinstance(window.zoom_toolbar, ZoomToolBar)

    def test_view_menu_has_rotate_cw(self) -> None:
        """Test View menu has Rotate Clockwise action with Ctrl+R."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        # Find the Rotate Clockwise action via window.findChildren
        from PySide6.QtGui import QAction

        found = None
        for action in window.findChildren(QAction):
            text = action.text()
            if "Clockwise" in text and "Counter" not in text:
                found = action
                break
        assert found is not None
        assert found.shortcut().toString() == "Ctrl+R"

    def test_view_menu_has_rotate_ccw(self) -> None:
        """Test View menu has Rotate Counter-Clockwise action with Ctrl+Shift+R."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        from PySide6.QtGui import QAction

        found = None
        for action in window.findChildren(QAction):
            if "ounter-Clockwise" in action.text():
                found = action
                break
        assert found is not None
        assert found.shortcut().toString() == "Ctrl+Shift+R"

    def test_zoom_in_action_signal(self) -> None:
        """Test that Ctrl+= zoom in action exists."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert hasattr(window, "zoom_in_triggered")
        spy = MagicMock()
        window.zoom_in_triggered.connect(spy)

    def test_zoom_out_action_signal(self) -> None:
        """Test that Ctrl+- zoom out action exists."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert hasattr(window, "zoom_out_triggered")
        spy = MagicMock()
        window.zoom_out_triggered.connect(spy)

    def test_zoom_reset_action_signal(self) -> None:
        """Test that Ctrl+0 reset zoom action exists."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert hasattr(window, "zoom_reset_triggered")
        spy = MagicMock()
        window.zoom_reset_triggered.connect(spy)

    def test_rotate_cw_action_signal(self) -> None:
        """Test that rotate CW menu action exists as a signal."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert hasattr(window, "rotate_cw_triggered")
        spy = MagicMock()
        window.rotate_cw_triggered.connect(spy)

    def test_rotate_ccw_action_signal(self) -> None:
        """Test that rotate CCW menu action exists as a signal."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert hasattr(window, "rotate_ccw_triggered")
        spy = MagicMock()
        window.rotate_ccw_triggered.connect(spy)


class TestKPdfAppIntegration:
    """Tests for KPdfApp wiring with TabManager."""

    def test_app_creates_tab_manager(self) -> None:
        """Test that KPdfApp creates a TabManager instead of single presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert isinstance(kpdf.tab_manager, TabManager)
        kpdf.shutdown()

    def test_app_wires_file_open_to_tab_manager(self) -> None:
        """Test that file_open_requested routes to TabManager.open_file."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        spy = MagicMock()
        kpdf.tab_manager.open_file = spy  # type: ignore[method-assign]
        kpdf.window.file_open_requested.emit(Path("/tmp/test.pdf"))
        spy.assert_called_once_with(Path("/tmp/test.pdf"))
        kpdf.shutdown()

    def test_tab_count_zero_shows_welcome(self) -> None:
        """Test that tab_count_changed(0) switches to welcome screen."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        kpdf.window.show_tabs()
        assert kpdf.window.stacked_widget.currentIndex() == 1
        kpdf.tab_manager.tab_count_changed.emit(0)
        assert kpdf.window.stacked_widget.currentIndex() == 0
        kpdf.shutdown()

    def test_app_creates_navigation_presenter(self) -> None:
        """Test that KPdfApp creates a NavigationPresenter."""
        from k_pdf.presenters.navigation_presenter import NavigationPresenter

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert isinstance(kpdf.navigation_presenter, NavigationPresenter)
        kpdf.shutdown()

    def test_app_creates_search_presenter(self) -> None:
        """Test that KPdfApp creates a SearchPresenter."""
        from k_pdf.presenters.search_presenter import SearchPresenter

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert isinstance(kpdf.search_presenter, SearchPresenter)
        kpdf.shutdown()

    def test_search_bar_search_requested_reaches_presenter(self) -> None:
        """Test that search bar's search_requested connects to presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        spy = MagicMock()
        kpdf.search_presenter.start_search = spy  # type: ignore[method-assign]
        kpdf.window.search_bar.search_requested.emit("hello", False, False)
        spy.assert_called_once_with("hello", case_sensitive=False, whole_word=False)
        kpdf.shutdown()

    def test_app_has_zoom_toolbar(self) -> None:
        """Test that KPdfApp's window has a zoom toolbar."""
        from k_pdf.views.zoom_toolbar import ZoomToolBar

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert isinstance(kpdf.window.zoom_toolbar, ZoomToolBar)
        kpdf.shutdown()

    def test_zoom_toolbar_zoom_routes_to_presenter(self) -> None:
        """Test that toolbar zoom_changed reaches the active presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_presenter = MagicMock()
        mock_presenter.zoom = 1.0
        mock_presenter.rotation = 0
        mock_presenter.fit_mode = FitMode.NONE
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )
        kpdf.window.zoom_toolbar.zoom_changed.emit(2.0)
        mock_presenter.set_zoom.assert_called_once_with(2.0)
        kpdf.shutdown()

    def test_zoom_toolbar_rotate_cw_routes(self) -> None:
        """Test that toolbar rotate_cw_requested reaches the active presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_presenter = MagicMock()
        mock_presenter.rotation = 0
        mock_presenter.zoom = 1.0
        mock_presenter.fit_mode = FitMode.NONE
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )
        kpdf.window.zoom_toolbar.rotate_cw_requested.emit()
        mock_presenter.set_rotation.assert_called_once_with(90)
        kpdf.shutdown()

    def test_zoom_toolbar_rotate_ccw_routes(self) -> None:
        """Test that toolbar rotate_ccw_requested reaches the active presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_presenter = MagicMock()
        mock_presenter.rotation = 0
        mock_presenter.zoom = 1.0
        mock_presenter.fit_mode = FitMode.NONE
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )
        kpdf.window.zoom_toolbar.rotate_ccw_requested.emit()
        mock_presenter.set_rotation.assert_called_once_with(-90)
        kpdf.shutdown()

    def test_zoom_in_shortcut_routes(self) -> None:
        """Test that Ctrl+= zoom in routes to presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_presenter = MagicMock()
        mock_presenter.zoom = 1.0
        mock_presenter.rotation = 0
        mock_presenter.fit_mode = FitMode.NONE
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )
        kpdf.window.zoom_in_triggered.emit()
        mock_presenter.set_zoom.assert_called_once_with(1.1)
        kpdf.shutdown()

    def test_zoom_out_shortcut_routes(self) -> None:
        """Test that Ctrl+- zoom out routes to presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_presenter = MagicMock()
        mock_presenter.zoom = 1.0
        mock_presenter.rotation = 0
        mock_presenter.fit_mode = FitMode.NONE
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )
        kpdf.window.zoom_out_triggered.emit()
        mock_presenter.set_zoom.assert_called_once_with(0.9)
        kpdf.shutdown()

    def test_zoom_reset_shortcut_routes(self) -> None:
        """Test that Ctrl+0 reset zoom routes to presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_presenter = MagicMock()
        mock_presenter.zoom = 2.0
        mock_presenter.rotation = 0
        mock_presenter.fit_mode = FitMode.NONE
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )
        kpdf.window.zoom_reset_triggered.emit()
        mock_presenter.set_zoom.assert_called_once_with(1.0)
        kpdf.shutdown()


class TestMainWindowToolsMenu:
    def test_tools_menu_exists(self) -> None:
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert window.tools_menu is not None

    def test_text_selection_action_exists(self) -> None:
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        actions = window.tools_menu.actions()
        names = [a.text() for a in actions]
        assert any("Text Selection" in n for n in names)

    def test_text_selection_action_is_checkable(self) -> None:
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        actions = window.tools_menu.actions()
        sel_action = next(a for a in actions if "Text Selection" in a.text())
        assert sel_action.isCheckable()

    def test_text_selection_toggle_emits_signal(self, qtbot: object) -> None:
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        with qtbot.waitSignal(window.text_selection_toggled, timeout=1000):  # type: ignore[union-attr]
            actions = window.tools_menu.actions()
            sel_action = next(a for a in actions if "Text Selection" in a.text())
            sel_action.trigger()

    def test_text_selection_shortcut_is_ctrl_t(self) -> None:
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        actions = window.tools_menu.actions()
        sel_action = next(a for a in actions if "Text Selection" in a.text())
        assert sel_action.shortcut().toString() == "Ctrl+T"


class TestKPdfAppAnnotationWiring:
    def test_app_has_annotation_presenter(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert kpdf.annotation_presenter is not None
        kpdf.shutdown()

    def test_app_has_annotation_toolbar(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert kpdf._annotation_toolbar is not None
        kpdf.shutdown()
