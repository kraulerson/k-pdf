"""QApplication shell and event bus initialization.

Creates the main window, tab manager, and wires signals together.
Handles CLI file arguments.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QPointF, QTimer
from PySide6.QtWidgets import QApplication

from k_pdf.core.annotation_model import ToolMode
from k_pdf.core.zoom_model import FitMode
from k_pdf.persistence.recent_files import RecentFiles
from k_pdf.persistence.settings_db import init_db
from k_pdf.presenters.annotation_presenter import AnnotationPresenter
from k_pdf.presenters.navigation_presenter import NavigationPresenter
from k_pdf.presenters.search_presenter import SearchPresenter
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.annotation_engine import AnnotationEngine
from k_pdf.views.annotation_toolbar import AnnotationToolbar
from k_pdf.views.main_window import MainWindow
from k_pdf.views.note_editor import NoteEditor

logger = logging.getLogger("k_pdf.app")


class KPdfApp:
    """Application controller — wires TabManager to views."""

    def __init__(self, app: QApplication, file_path: str | None = None) -> None:
        """Initialize the app controller.

        Args:
            app: The QApplication instance.
            file_path: Optional path to open on startup (from CLI args).
        """
        self._app = app
        self._db = init_db()
        self._recent_files = RecentFiles(self._db)
        self._window = MainWindow()
        self._tab_manager = TabManager(
            tab_widget=self._window.tab_widget,
            recent_files=self._recent_files,
        )
        self._nav_presenter = NavigationPresenter(
            tab_manager=self._tab_manager,
        )
        self._search_presenter = SearchPresenter(
            tab_manager=self._tab_manager,
        )
        self._annotation_engine = AnnotationEngine()
        self._annotation_toolbar = AnnotationToolbar()
        self._annotation_presenter = AnnotationPresenter(
            tab_manager=self._tab_manager,
            engine=self._annotation_engine,
            toolbar=self._annotation_toolbar,
        )
        self._note_editor = NoteEditor()
        self._annotation_presenter.set_note_editor(self._note_editor)
        self._initial_file = file_path

        self._connect_signals()
        self._window.show()

        # Open file from CLI argument after event loop starts
        if self._initial_file:
            QTimer.singleShot(0, self._open_initial_file)

    @property
    def window(self) -> MainWindow:
        """Return the main window."""
        return self._window

    @property
    def tab_manager(self) -> TabManager:
        """Return the tab manager."""
        return self._tab_manager

    @property
    def navigation_presenter(self) -> NavigationPresenter:
        """Return the navigation presenter."""
        return self._nav_presenter

    @property
    def search_presenter(self) -> SearchPresenter:
        """Return the search presenter."""
        return self._search_presenter

    @property
    def annotation_presenter(self) -> AnnotationPresenter:
        """Return the annotation presenter."""
        return self._annotation_presenter

    def _connect_signals(self) -> None:
        """Wire MainWindow signals to TabManager and vice versa."""
        # View → TabManager
        self._window.file_open_requested.connect(self._tab_manager.open_file)
        self._window.tab_close_requested.connect(self._on_close_current_tab)
        self._window.password_submitted.connect(self._on_password_submitted)

        # TabManager → View
        self._tab_manager.error_occurred.connect(self._window.show_error)
        self._tab_manager.password_requested.connect(self._window.show_password_dialog)
        self._tab_manager.status_message.connect(self._window.update_status_message)
        self._tab_manager.active_page_status.connect(self._window.update_page_status)
        self._tab_manager.tab_count_changed.connect(self._on_tab_count_changed)

        # NavigationPresenter → NavigationPanel
        nav = self._nav_presenter
        panel = self._window.navigation_panel
        nav.thumbnail_ready.connect(panel.add_thumbnail)
        nav.outline_ready.connect(panel.set_outline)
        nav.active_thumbnail_changed.connect(panel.set_current_page)

        # NavigationPanel → NavigationPresenter
        panel.thumbnail_clicked.connect(nav.navigate_to_page)
        panel.outline_clicked.connect(nav.navigate_to_page)

        # Clear panel on tab switch and when all tabs close
        self._tab_manager.tab_switched.connect(lambda _: panel.clear())
        self._tab_manager.tab_count_changed.connect(self._on_nav_tab_count)

        # SearchBar -> SearchPresenter
        search_bar = self._window.search_bar
        search_bar.search_requested.connect(
            lambda q, cs, ww: self._search_presenter.start_search(
                q, case_sensitive=cs, whole_word=ww
            )
        )
        search_bar.next_requested.connect(self._search_presenter.next_match)
        search_bar.previous_requested.connect(self._search_presenter.previous_match)
        search_bar.closed.connect(self._search_presenter.close_search)

        # SearchPresenter -> SearchBar
        sp = self._search_presenter
        sp.matches_updated.connect(search_bar.set_match_count)
        sp.no_text_layer.connect(search_bar.set_no_text_layer)

        # SearchPresenter -> PdfViewport (highlight overlays)
        sp.highlight_page.connect(self._on_search_highlight_page)
        sp.clear_highlights.connect(self._on_search_clear_highlights)

        # ZoomToolBar -> presenter
        zoom_tb = self._window.zoom_toolbar
        zoom_tb.zoom_changed.connect(self._on_toolbar_zoom_changed)
        zoom_tb.fit_page_requested.connect(self._on_fit_page_requested)
        zoom_tb.fit_width_requested.connect(self._on_fit_width_requested)
        zoom_tb.rotate_cw_requested.connect(self._on_rotate_cw)
        zoom_tb.rotate_ccw_requested.connect(self._on_rotate_ccw)

        # MainWindow zoom/rotation shortcuts -> presenter
        self._window.zoom_in_triggered.connect(self._on_zoom_in)
        self._window.zoom_out_triggered.connect(self._on_zoom_out)
        self._window.zoom_reset_triggered.connect(self._on_zoom_reset)
        self._window.rotate_cw_triggered.connect(self._on_rotate_cw)
        self._window.rotate_ccw_triggered.connect(self._on_rotate_ccw)

        # Tab switch -> push zoom state to toolbar
        self._tab_manager.tab_switched.connect(self._on_tab_switched_zoom)

        # When a new tab's document is ready, wire its zoom signals
        self._tab_manager.document_ready.connect(self._on_document_ready_zoom)

        # Annotation wiring
        # MainWindow Tools menu -> AnnotationPresenter
        self._window.text_selection_toggled.connect(self._annotation_presenter.set_selection_mode)
        self._window.sticky_note_toggled.connect(self._on_sticky_note_toggled)
        self._window.text_box_toggled.connect(self._on_text_box_toggled)

        # AnnotationPresenter -> re-render on create/delete
        self._annotation_presenter.annotation_created.connect(self._on_annotation_changed)
        self._annotation_presenter.annotation_deleted.connect(self._on_annotation_changed)

        # AnnotationPresenter -> dirty flag -> tab title
        self._annotation_presenter.dirty_changed.connect(self._on_annotation_dirty_changed)

        # AnnotationPresenter tool mode -> update MainWindow tool check states
        self._annotation_presenter.tool_mode_changed.connect(self._on_tool_mode_changed)

        # NoteEditor -> AnnotationPresenter
        self._note_editor.editing_finished.connect(self._annotation_presenter._on_editing_finished)
        self._note_editor.editing_cancelled.connect(
            self._annotation_presenter._on_editing_cancelled
        )

        # When a new document loads, wire viewport annotation signals
        self._tab_manager.document_ready.connect(self._on_document_ready_annotation)

    def _on_tab_count_changed(self, count: int) -> None:
        """Toggle between welcome screen and tab view."""
        if count == 0:
            self._window.show_welcome()
        else:
            self._window.show_tabs()

    def _on_close_current_tab(self) -> None:
        """Close the currently active tab."""
        sid = self._tab_manager.active_session_id
        if sid is not None:
            self._tab_manager.close_tab(sid)

    def _on_password_submitted(self, path: Path, password: str) -> None:
        """Forward password to the active tab's presenter."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.open_file_with_password(path, password)

    def _open_initial_file(self) -> None:
        """Open the file passed via CLI argument."""
        if self._initial_file:
            self._tab_manager.open_file(Path(self._initial_file))

    def _on_nav_tab_count(self, count: int) -> None:
        """Clear navigation panel when all tabs close."""
        if count == 0:
            self._window.navigation_panel.clear()

    def _on_search_highlight_page(
        self,
        page_index: int,
        rects: list[tuple[float, float, float, float]],
    ) -> None:
        """Route highlight overlay to the active viewport."""
        viewport = self._tab_manager.get_active_viewport()
        presenter = self._tab_manager.get_active_presenter()
        if viewport is not None:
            zoom = presenter.zoom if presenter is not None else 1.0
            viewport.add_search_highlights(page_index, rects, zoom=zoom)

    def _on_search_clear_highlights(self) -> None:
        """Clear search highlights on the active viewport."""
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.clear_search_highlights()

    # --- Zoom/rotation handlers ---

    def _on_toolbar_zoom_changed(self, zoom: float) -> None:
        """Route toolbar zoom change to active presenter."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_zoom(zoom)

    def _on_fit_page_requested(self) -> None:
        """Route Fit Page request to active presenter."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and viewport is not None:
            vp = viewport.viewport()
            presenter.set_fit_mode(FitMode.PAGE, float(vp.width()), float(vp.height()))

    def _on_fit_width_requested(self) -> None:
        """Route Fit Width request to active presenter."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and viewport is not None:
            vp = viewport.viewport()
            presenter.set_fit_mode(FitMode.WIDTH, float(vp.width()), float(vp.height()))

    def _on_rotate_cw(self) -> None:
        """Route rotate clockwise to active presenter."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_rotation(presenter.rotation + 90)

    def _on_rotate_ccw(self) -> None:
        """Route rotate counter-clockwise to active presenter."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_rotation(presenter.rotation - 90)

    def _on_zoom_in(self) -> None:
        """Zoom in by 10% via keyboard shortcut."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_zoom(presenter.zoom + 0.1)

    def _on_zoom_out(self) -> None:
        """Zoom out by 10% via keyboard shortcut."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_zoom(presenter.zoom - 0.1)

    def _on_zoom_reset(self) -> None:
        """Reset zoom to 100% via keyboard shortcut."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_zoom(1.0)

    def _on_viewport_resized(self, width: float, height: float) -> None:
        """Recalculate fit mode zoom on viewport resize."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None and presenter.fit_mode is not FitMode.NONE:
            presenter.set_fit_mode(presenter.fit_mode, width, height)

    def _on_zoom_at_cursor(self, step: float, _scene_pos: QPointF) -> None:
        """Handle Ctrl+scroll zoom from viewport."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_zoom(presenter.zoom + step)

    def _on_presenter_zoom_changed(self, zoom: float) -> None:
        """Push zoom changes from presenter back to toolbar."""
        self._window.zoom_toolbar.set_zoom(zoom)
        self._window._zoom_label.setText(f"{int(zoom * 100)}%")

    def _on_presenter_rotation_changed(self, rotation: int) -> None:
        """Push rotation changes from presenter back to toolbar."""
        self._window.zoom_toolbar.set_rotation(rotation)

    def _on_tab_switched_zoom(self, session_id: str) -> None:
        """Push the new tab's zoom/rotation/fit_mode state to toolbar."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            self._window.zoom_toolbar.set_zoom(presenter.zoom)
            self._window.zoom_toolbar.set_rotation(presenter.rotation)
            self._window.zoom_toolbar.set_fit_mode(presenter.fit_mode)
            self._window._zoom_label.setText(f"{int(presenter.zoom * 100)}%")

    def _on_document_ready_zoom(self, session_id: str, model: object) -> None:
        """Wire zoom/rotation signals for a newly loaded document tab."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None:
            presenter.zoom_changed.connect(self._on_presenter_zoom_changed)
            presenter.rotation_changed.connect(self._on_presenter_rotation_changed)
        if viewport is not None:
            viewport.viewport_resized.connect(self._on_viewport_resized)
            viewport.zoom_at_cursor.connect(self._on_zoom_at_cursor)

    # --- Annotation handlers ---

    def _on_annotation_changed(self) -> None:
        """Re-render current page after annotation create/delete."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and viewport is not None:
            # Invalidate cache and re-request visible pages
            presenter.cache.invalidate()
            presenter._pending_renders.clear()
            first, last = viewport.get_visible_page_range()
            if first >= 0:
                presenter.request_pages(list(range(first, last + 1)))

    def _on_annotation_dirty_changed(self, dirty: bool) -> None:
        """Update tab title with dirty indicator."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and presenter.model is not None and viewport is not None:
            name = presenter.model.file_path.name
            title = f"* {name}" if dirty else name
            idx = self._window.tab_widget.indexOf(viewport)
            if idx >= 0:
                self._window.tab_widget.setTabText(idx, title)

    def _on_document_ready_annotation(self, session_id: str, model: object) -> None:
        """Wire viewport annotation signals for a newly loaded document tab."""
        viewport = self._tab_manager.get_active_viewport()
        presenter = self._tab_manager.get_active_presenter()
        if viewport is not None:
            viewport.set_annotation_engine(self._annotation_engine)
            if presenter is not None and presenter.model is not None:
                viewport.set_doc_handle(presenter.model.doc_handle)
            viewport.text_selected.connect(self._annotation_presenter.on_text_selected)
            viewport.annotation_delete_requested.connect(
                self._annotation_presenter.delete_annotation
            )
            viewport.note_placed.connect(self._annotation_presenter.on_note_placed)
            viewport.textbox_drawn.connect(self._annotation_presenter.on_textbox_drawn)
            viewport.annotation_double_clicked.connect(
                self._annotation_presenter.on_annotation_double_clicked
            )

    def _on_sticky_note_toggled(self, checked: bool) -> None:
        """Route Sticky Note tool toggle to annotation presenter."""
        if checked:
            self._annotation_presenter.set_tool_mode(ToolMode.STICKY_NOTE)
        else:
            self._annotation_presenter.set_tool_mode(ToolMode.NONE)

    def _on_text_box_toggled(self, checked: bool) -> None:
        """Route Text Box tool toggle to annotation presenter."""
        if checked:
            self._annotation_presenter.set_tool_mode(ToolMode.TEXT_BOX)
        else:
            self._annotation_presenter.set_tool_mode(ToolMode.NONE)

    def _on_tool_mode_changed(self, mode: int) -> None:
        """Update MainWindow tool menu check states when tool mode changes."""
        tool_mode = ToolMode(mode)
        # Block signals to avoid feedback loop
        self._window._text_select_action.blockSignals(True)
        self._window._sticky_note_action.blockSignals(True)
        self._window._text_box_action.blockSignals(True)

        self._window._text_select_action.setChecked(tool_mode is ToolMode.TEXT_SELECT)
        self._window._sticky_note_action.setChecked(tool_mode is ToolMode.STICKY_NOTE)
        self._window._text_box_action.setChecked(tool_mode is ToolMode.TEXT_BOX)

        self._window._text_select_action.blockSignals(False)
        self._window._sticky_note_action.blockSignals(False)
        self._window._text_box_action.blockSignals(False)

    def shutdown(self) -> None:
        """Clean up resources before exit."""
        self._annotation_toolbar.hide()
        self._note_editor.hide()
        self._search_presenter.shutdown()
        self._nav_presenter.shutdown()
        self._tab_manager.shutdown()
