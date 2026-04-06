"""QApplication shell and event bus initialization.

Creates the main window, tab manager, and wires signals together.
Handles CLI file arguments.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QTimer
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from k_pdf.core.annotation_model import ToolMode
from k_pdf.core.form_model import FormFieldType
from k_pdf.core.preferences_manager import PreferencesManager
from k_pdf.core.theme_manager import ThemeManager, ThemeMode
from k_pdf.core.undo_manager import UndoManager
from k_pdf.core.zoom_model import FitMode
from k_pdf.persistence.recent_files import RecentFiles
from k_pdf.persistence.settings_db import init_db
from k_pdf.presenters.annotation_presenter import AnnotationPresenter
from k_pdf.presenters.annotation_summary_presenter import AnnotationSummaryPresenter
from k_pdf.presenters.form_creation_presenter import FormCreationPresenter
from k_pdf.presenters.form_presenter import FormPresenter
from k_pdf.presenters.navigation_presenter import NavigationPresenter
from k_pdf.presenters.page_management_presenter import PageManagementPresenter
from k_pdf.presenters.search_presenter import SearchPresenter
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.presenters.text_edit_presenter import TextEditPresenter
from k_pdf.services.annotation_engine import AnnotationEngine
from k_pdf.services.form_engine import FormEngine
from k_pdf.services.page_engine import PageEngine
from k_pdf.services.pdf_engine import PdfEngine
from k_pdf.services.print_service import PrintService
from k_pdf.services.text_edit_engine import TextEditEngine
from k_pdf.views.annotation_toolbar import AnnotationToolbar
from k_pdf.views.form_field_popup import FormFieldPopup
from k_pdf.views.main_window import MainWindow
from k_pdf.views.note_editor import NoteEditor

if TYPE_CHECKING:
    from k_pdf.views.pdf_viewport import PdfViewport

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
        self._form_engine = FormEngine()
        self._form_presenter = FormPresenter(
            form_engine=self._form_engine,
            tab_manager=self._tab_manager,
        )
        self._page_engine = PageEngine()
        self._form_creation_presenter = FormCreationPresenter(
            form_engine=self._form_engine,
            tab_manager=self._tab_manager,
        )
        self._text_edit_engine = TextEditEngine()
        self._text_edit_presenter = TextEditPresenter(
            text_edit_engine=self._text_edit_engine,
            tab_manager=self._tab_manager,
        )
        self._form_field_popup: FormFieldPopup | None = None
        self._page_management_presenter = PageManagementPresenter(
            page_engine=self._page_engine,
            tab_manager=self._tab_manager,
            panel=self._window.page_manager_panel,
        )
        self._annotation_summary_presenter = AnnotationSummaryPresenter(
            tab_manager=self._tab_manager,
            annotation_engine=self._annotation_engine,
            panel=self._window.annotation_summary_panel,
        )
        self._theme_manager = ThemeManager(app)
        self._pdf_engine = PdfEngine()
        self._print_service = PrintService()
        self._prefs_manager = PreferencesManager(self._db)
        self._initial_file = file_path
        self._active_undo_manager: UndoManager | None = None

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

    @property
    def page_management_presenter(self) -> PageManagementPresenter:
        """Return the page management presenter."""
        return self._page_management_presenter

    @property
    def annotation_summary_presenter(self) -> AnnotationSummaryPresenter:
        """Return the annotation summary presenter."""
        return self._annotation_summary_presenter

    @property
    def theme_manager(self) -> ThemeManager:
        """Return the theme manager."""
        return self._theme_manager

    @property
    def preferences_manager(self) -> PreferencesManager:
        """Return the preferences manager."""
        return self._prefs_manager

    def _connect_signals(self) -> None:
        """Wire MainWindow signals to TabManager and vice versa."""
        # View → TabManager
        self._window.file_open_requested.connect(self._tab_manager.open_file)
        self._window.tab_close_requested.connect(self._on_close_current_tab)
        self._window.password_submitted.connect(self._on_password_submitted)
        self._window.merge_requested.connect(self._on_merge_requested)
        self._window.print_requested.connect(self._on_print_requested)
        self._window.preferences_requested.connect(self._on_preferences_requested)

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

        # Clear panel before re-populating on tab switch, and when all tabs close
        nav.clear_requested.connect(panel.clear)
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

        # Text copy wiring
        self._window.copy_requested.connect(self._annotation_presenter.copy_selected_text)
        self._window.select_all_requested.connect(self._annotation_presenter.select_all_text)
        self._annotation_presenter.text_copied.connect(self._on_text_copied)
        self._annotation_presenter.selection_changed.connect(self._window.set_copy_enabled)

        # NoteEditor -> AnnotationPresenter
        self._note_editor.editing_finished.connect(self._annotation_presenter._on_editing_finished)
        self._note_editor.editing_cancelled.connect(
            self._annotation_presenter._on_editing_cancelled
        )

        # When a new document loads, wire viewport annotation signals
        self._tab_manager.document_ready.connect(self._on_document_ready_annotation)

        # Form wiring
        self._tab_manager.document_ready.connect(self._on_document_ready_form)
        self._window.save_requested.connect(self._on_save_requested)
        self._window.save_as_requested.connect(self._on_save_as_requested)
        self._form_presenter.form_detected.connect(self._on_form_detected)
        self._form_presenter.xfa_detected.connect(self._on_xfa_detected)
        self._form_presenter.dirty_changed.connect(self._on_form_dirty_changed)
        self._form_presenter.save_succeeded.connect(self._on_save_succeeded)
        self._form_presenter.save_failed.connect(self._on_save_failed)
        self._tab_manager.tab_closed.connect(self._form_presenter.on_tab_closed)
        self._tab_manager.close_guard_requested.connect(self._on_close_guard)

        # Dark mode wiring
        self._window.dark_mode_changed.connect(self._on_dark_mode_changed)
        self._window.dark_mode_toggle_requested.connect(self._on_dark_mode_toggle)
        self._theme_manager.theme_changed.connect(self._on_theme_changed)
        self._theme_manager.inversion_changed.connect(self._on_inversion_changed)

        # Page management wiring
        pm_panel = self._window.page_manager_panel
        pm = self._page_management_presenter
        pm_panel.rotate_left_clicked.connect(self._on_page_rotate_left)
        pm_panel.rotate_right_clicked.connect(self._on_page_rotate_right)
        pm_panel.delete_clicked.connect(self._on_page_delete)
        pm_panel.add_clicked.connect(self._on_page_add)
        pm_panel.page_moved.connect(pm.move_page)
        pm_panel.page_clicked.connect(self._nav_presenter.navigate_to_page)
        pm.pages_changed.connect(self._on_pages_changed)
        pm.dirty_changed.connect(self._on_page_dirty_changed)
        self._tab_manager.tab_switched.connect(pm.on_tab_switched)
        self._tab_manager.tab_closed.connect(pm.on_tab_closed)
        self._tab_manager.document_ready.connect(self._on_document_ready_page_mgmt)

        # Annotation summary panel wiring
        asp = self._annotation_summary_presenter
        self._tab_manager.document_ready.connect(self._on_document_ready_annotation_summary)
        self._tab_manager.tab_switched.connect(asp.on_tab_switched)
        self._tab_manager.tab_closed.connect(asp.on_tab_closed)
        self._annotation_presenter.annotation_created.connect(asp.refresh_annotations)
        self._annotation_presenter.annotation_deleted.connect(asp.refresh_annotations)
        self._window.annotation_summary_panel.annotation_clicked.connect(asp.on_annotation_clicked)

        # Print wiring
        self._tab_manager.document_ready.connect(self._on_document_ready_print)

        # Undo/Redo wiring
        self._window.undo_requested.connect(self._on_undo)
        self._window.redo_requested.connect(self._on_redo)
        self._tab_manager.tab_switched.connect(self._on_tab_switched_undo)
        self._tab_manager.document_ready.connect(self._on_document_ready_undo)

        # Form creation wiring
        self._window.form_text_field_requested.connect(
            lambda: self._form_creation_presenter.set_tool_mode(ToolMode.FORM_TEXT)
        )
        self._window.form_checkbox_requested.connect(
            lambda: self._form_creation_presenter.set_tool_mode(ToolMode.FORM_CHECKBOX)
        )
        self._window.form_dropdown_requested.connect(
            lambda: self._form_creation_presenter.set_tool_mode(ToolMode.FORM_DROPDOWN)
        )
        self._window.form_radio_requested.connect(
            lambda: self._form_creation_presenter.set_tool_mode(ToolMode.FORM_RADIO)
        )
        self._window.form_signature_requested.connect(
            lambda: self._form_creation_presenter.set_tool_mode(ToolMode.FORM_SIGNATURE)
        )
        self._form_creation_presenter.tool_mode_changed.connect(self._on_form_tool_mode_changed)
        self._form_creation_presenter.field_created.connect(self._on_form_field_changed)
        self._form_creation_presenter.field_deleted.connect(self._on_form_field_changed)

        # Form properties panel wiring
        self._window.form_properties_panel.delete_requested.connect(
            self._on_form_field_delete_from_panel
        )
        self._window.form_properties_panel.properties_changed.connect(
            self._on_form_field_props_changed
        )

        # Document ready -> enable form creation tools
        self._tab_manager.document_ready.connect(self._on_document_ready_form_creation)

        # Text editing wiring
        # Find-replace bar -> search (reuses SearchPresenter for finding)
        find_replace = self._window.find_replace_bar
        find_replace.search_requested.connect(
            lambda q, cs, ww: self._search_presenter.start_search(
                q, case_sensitive=cs, whole_word=ww
            )
        )
        find_replace.next_requested.connect(self._search_presenter.next_match)
        find_replace.previous_requested.connect(self._search_presenter.previous_match)
        find_replace.closed.connect(self._search_presenter.close_search)
        find_replace.replace_requested.connect(self._on_replace_current)
        find_replace.replace_all_requested.connect(self._on_replace_all)

        # SearchPresenter -> FindReplaceBar (match count updates)
        self._search_presenter.matches_updated.connect(find_replace.set_match_count)
        self._search_presenter.no_text_layer.connect(find_replace.set_no_text_layer)

        # TextEditPresenter signals
        self._text_edit_presenter.text_changed.connect(self._on_text_edit_changed)
        self._text_edit_presenter.replace_status.connect(find_replace.set_status)

        # Text edit mode from tools menu
        self._window.text_edit_toggled.connect(self._on_text_edit_toggled)

        # Document ready -> wire text edit double-click
        self._tab_manager.document_ready.connect(self._on_document_ready_text_edit)

    def _on_document_ready_annotation_summary(self, session_id: str, model: object) -> None:
        """Wire annotation summary panel for a newly loaded document."""
        from k_pdf.core.document_model import DocumentModel

        if isinstance(model, DocumentModel):
            self._annotation_summary_presenter.on_document_ready(session_id, model)

    def _on_tab_count_changed(self, count: int) -> None:
        """Toggle between welcome screen and tab view."""
        if count == 0:
            self._window.show_welcome()
            self._window.set_print_enabled(False)
            self._window.set_tools_enabled(False)
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

    @staticmethod
    def _effective_viewport_size(
        viewport: PdfViewport,
    ) -> tuple[float, float]:
        """Return usable viewport size, subtracting scrollbar space.

        QGraphicsView.viewport() reports its full size even when a
        scrollbar is not yet visible but will appear after zoom changes.
        We unconditionally subtract scrollbar dimensions so Fit Page and
        Fit Width never produce a zoom that causes content to overflow.

        Args:
            viewport: The PdfViewport (QGraphicsView subclass).

        Returns:
            (width, height) in pixels with scrollbar space subtracted.
        """
        vp = viewport.viewport()
        sb_w = viewport.verticalScrollBar().sizeHint().width()
        sb_h = viewport.horizontalScrollBar().sizeHint().height()
        w = max(1.0, float(vp.width()) - sb_w)
        h = max(1.0, float(vp.height()) - sb_h)
        return w, h

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
            w, h = self._effective_viewport_size(viewport)
            presenter.set_fit_mode(FitMode.PAGE, w, h)

    def _on_fit_width_requested(self) -> None:
        """Route Fit Width request to active presenter."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and viewport is not None:
            w, h = self._effective_viewport_size(viewport)
            presenter.set_fit_mode(FitMode.WIDTH, w, h)

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

    def _on_viewport_resized(self, _width: float, _height: float) -> None:
        """Recalculate fit mode zoom on viewport resize."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if (
            presenter is not None
            and presenter.fit_mode is not FitMode.NONE
            and viewport is not None
        ):
            w, h = self._effective_viewport_size(viewport)
            presenter.set_fit_mode(presenter.fit_mode, w, h)

    def _on_zoom_at_cursor(self, step: float, _scene_pos: QPointF) -> None:
        """Handle Ctrl+scroll zoom from viewport."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_zoom(presenter.zoom + step)

    def _on_presenter_zoom_changed(self, zoom: float) -> None:
        """Push zoom changes from presenter back to toolbar and re-render."""
        self._window.zoom_toolbar.set_zoom(zoom)
        self._window._zoom_label.setText(f"{int(zoom * 100)}%")
        self._relayout_viewport()

    def _on_presenter_rotation_changed(self, rotation: int) -> None:
        """Push rotation changes from presenter back to toolbar and re-render."""
        self._window.zoom_toolbar.set_rotation(rotation)
        self._relayout_viewport()

    def _relayout_viewport(self) -> None:
        """Re-layout the active viewport and re-render visible pages.

        Called after zoom or rotation changes to immediately update the
        display without requiring the user to scroll.
        """
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and viewport is not None and presenter.model is not None:
            viewport.set_document(
                presenter.model.pages,
                zoom=presenter.zoom,
                rotation=presenter.rotation,
            )

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

    def _on_text_copied(self, text: str) -> None:
        """Show status bar message when text is copied to clipboard."""
        self._window.update_status_message("Copied to clipboard")

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
        self._window.set_tools_enabled(True)
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

    # --- Form / Save handlers ---

    def _on_document_ready_form(self, session_id: str, model: object) -> None:
        """Wire form detection for a newly loaded document."""
        from k_pdf.core.document_model import DocumentModel

        if isinstance(model, DocumentModel):
            self._form_presenter.on_document_opened(session_id, model)
            self._window.set_save_enabled(True)

    def _on_save_requested(self) -> None:
        """Handle File > Save."""
        sid = self._tab_manager.active_session_id
        if sid is not None:
            self._form_presenter.save(sid)

    def _on_save_as_requested(self) -> None:
        """Handle File > Save As — show file picker then save."""
        sid = self._tab_manager.active_session_id
        if sid is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save As",
            "",
            "PDF Files (*.pdf);;All Files (*)",
        )
        if path:
            self._form_presenter.save_as(sid, Path(path))

    def _on_form_detected(self, count: int) -> None:
        """Show form field count in status bar."""
        self._window.update_status_message(
            f"This document contains {count} form field{'s' if count != 1 else ''}"
        )

    def _on_xfa_detected(self, message: str) -> None:
        """Show XFA notification in status bar."""
        self._window.update_status_message(message)

    def _on_form_dirty_changed(self, dirty: bool) -> None:
        """Update tab title with dirty indicator from form changes."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and presenter.model is not None and viewport is not None:
            name = presenter.model.file_path.name
            title = f"* {name}" if dirty else name
            idx = self._window.tab_widget.indexOf(viewport)
            if idx >= 0:
                self._window.tab_widget.setTabText(idx, title)

    def _on_save_succeeded(self) -> None:
        """Handle successful save."""
        self._window.update_status_message("Document saved")
        # Update tab title to remove dirty indicator
        self._on_form_dirty_changed(False)

    def _on_save_failed(self, error: str) -> None:
        """Handle save failure — show error dialog."""
        self._window.show_error("Save Failed", error)

    def _on_close_guard(self, session_id: str) -> None:
        """Show Save/Discard/Cancel dialog for dirty tab close."""
        msg_box = QMessageBox(self._window)
        msg_box.setWindowTitle("Unsaved Changes")
        msg_box.setText("This document has unsaved changes.")
        msg_box.setInformativeText("Do you want to save before closing?")
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.Save)
        result = msg_box.exec()

        if result == QMessageBox.StandardButton.Save:
            self._form_presenter.save(session_id)
            # If save succeeded (dirty cleared), close the tab
            ctx = self._tab_manager._tabs.get(session_id)
            if ctx and ctx.presenter and ctx.presenter.model and not ctx.presenter.model.dirty:
                self._tab_manager.force_close_tab(session_id)
        elif result == QMessageBox.StandardButton.Discard:
            self._tab_manager.force_close_tab(session_id)
        # Cancel: do nothing, tab stays open

    # --- Dark mode handlers ---

    def _on_dark_mode_changed(self, mode_value: str) -> None:
        """Handle dark mode menu selection."""
        mode_map = {
            "off": ThemeMode.OFF,
            "dark_original": ThemeMode.DARK_ORIGINAL,
            "dark_inverted": ThemeMode.DARK_INVERTED,
        }
        mode = mode_map.get(mode_value)
        if mode is not None:
            self._theme_manager.set_mode(mode)

    def _on_dark_mode_toggle(self) -> None:
        """Handle Ctrl+D toggle."""
        self._theme_manager.toggle()

    def _on_theme_changed(self, mode_value: str) -> None:
        """Update MainWindow UI when theme changes."""
        mode_map = {
            "off": ThemeMode.OFF,
            "dark_original": ThemeMode.DARK_ORIGINAL,
            "dark_inverted": ThemeMode.DARK_INVERTED,
        }
        mode = mode_map.get(mode_value)
        if mode is not None:
            self._window.set_theme_mode(mode)

    def _on_inversion_changed(self, inverted: bool) -> None:
        """Update viewport inversion when theme inversion state changes.

        Sets the inversion flag on the active viewport, then invalidates
        the render cache and re-renders visible pages so already-displayed
        pages are immediately updated with the new inversion state.
        """
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.set_invert_pdf(inverted)
            # Re-render visible pages so existing pixmaps get inverted
            presenter = self._tab_manager.get_active_presenter()
            if presenter is not None:
                presenter.cache.invalidate()
                presenter._pending_renders.clear()
                first, last = viewport.get_visible_page_range()
                if first >= 0:
                    presenter.request_pages(list(range(first, last + 1)))

    # --- Page management handlers ---

    def _on_page_rotate_left(self) -> None:
        """Rotate selected pages 90 degrees counter-clockwise (modifies PDF)."""
        selected = self._window.page_manager_panel.get_selected_pages()
        if selected:
            self._page_management_presenter.rotate_pages(selected, 270)

    def _on_page_rotate_right(self) -> None:
        """Rotate selected pages 90 degrees clockwise (modifies PDF)."""
        selected = self._window.page_manager_panel.get_selected_pages()
        if selected:
            self._page_management_presenter.rotate_pages(selected, 90)

    def _on_page_delete(self) -> None:
        """Delete selected pages from the document."""
        selected = self._window.page_manager_panel.get_selected_pages()
        if selected:
            self._page_management_presenter.delete_pages(selected)

    def _on_page_add(self) -> None:
        """Show file picker and insert pages from another PDF."""
        path, _ = QFileDialog.getOpenFileName(
            self._window,
            "Add Pages from PDF",
            "",
            "PDF Files (*.pdf);;All Files (*)",
        )
        if path:
            selected = self._window.page_manager_panel.get_selected_pages()
            insert_at = max(selected) + 1 if selected else 0
            model = self._page_management_presenter._get_active_model()
            if model is not None and not selected:
                insert_at = model.doc_handle.page_count
            self._page_management_presenter.insert_pages(Path(path), insert_at)

    def _on_pages_changed(self) -> None:
        """Re-render viewport and update navigation after page operations."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and viewport is not None:
            presenter.cache.invalidate()
            presenter._pending_renders.clear()
            first, last = viewport.get_visible_page_range()
            if first >= 0:
                presenter.request_pages(list(range(first, last + 1)))

    def _on_page_dirty_changed(self, dirty: bool) -> None:
        """Update tab title with dirty indicator from page changes."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and presenter.model is not None and viewport is not None:
            name = presenter.model.file_path.name
            title = f"* {name}" if dirty else name
            idx = self._window.tab_widget.indexOf(viewport)
            if idx >= 0:
                self._window.tab_widget.setTabText(idx, title)

    def _on_document_ready_page_mgmt(self, session_id: str, model: object) -> None:
        """Refresh page management panel when a new document loads."""
        self._page_management_presenter.on_tab_switched(session_id)

    # --- Merge handlers ---

    def _on_merge_requested(self) -> None:
        """Show the Merge Documents dialog and handle result."""
        from k_pdf.views.merge_dialog import MergeDialog

        dialog = MergeDialog(self._window)
        dialog.merge_complete.connect(self._on_merge_complete)
        dialog.exec()

    def _on_merge_complete(self, output_path_str: str) -> None:
        """Open the merged file in a new tab.

        Args:
            output_path_str: Path to the merged output file.
        """
        self._tab_manager.open_file(Path(output_path_str))

    # --- Print handlers ---

    def _on_document_ready_print(self, session_id: str, model: object) -> None:
        """Enable print action when a document is loaded."""
        from k_pdf.core.document_model import DocumentModel

        if isinstance(model, DocumentModel):
            self._window.set_print_enabled(True)

    def _on_print_requested(self) -> None:
        """Handle File > Print — show QPrintDialog and print document."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is None or presenter.model is None:
            return

        model = presenter.model
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)

        dialog = QPrintDialog(printer, self._window)
        dialog.setMinMax(1, model.metadata.page_count)

        if dialog.exec() != 1:  # QDialog.DialogCode.Accepted
            return

        def progress(current: int, total: int) -> None:
            self._window.update_status_message(f"Printing page {current} of {total}...")

        result = self._print_service.print_document(
            printer=printer,
            doc_handle=model.doc_handle,
            page_count=model.metadata.page_count,
            pdf_engine=self._pdf_engine,
            progress_callback=progress,
        )

        if result.success:
            self._window.update_status_message("Printing complete")
        else:
            self._show_print_error(result.error_message)

    def _show_print_error(self, message: str) -> None:
        """Show a print error dialog.

        Args:
            message: Error message to display.
        """
        self._window.show_error("Print Failed", message)

    # --- Preferences handler ---

    def _on_preferences_requested(self) -> None:
        """Show the Preferences dialog."""
        from k_pdf.views.preferences_dialog import PreferencesDialog

        dialog = PreferencesDialog(self._prefs_manager, self._window)
        dialog.preferences_saved.connect(self._on_preferences_saved)
        dialog.exec()

    def _on_preferences_saved(self) -> None:
        """Apply preference changes after dialog OK.

        Syncs theme preference with ThemeManager.
        """
        dark_mode = self._prefs_manager.get_dark_mode()
        mode_map = {
            "off": ThemeMode.OFF,
            "dark_original": ThemeMode.DARK_ORIGINAL,
            "dark_inverted": ThemeMode.DARK_INVERTED,
        }
        mode = mode_map.get(dark_mode)
        if mode is not None:
            self._theme_manager.set_mode(mode)

    # --- Undo/Redo handlers ---

    def _on_undo(self) -> None:
        """Execute undo on the active tab's UndoManager."""
        undo_mgr = self._tab_manager.get_active_undo_manager()
        if undo_mgr is not None:
            undo_mgr.undo()

    def _on_redo(self) -> None:
        """Execute redo on the active tab's UndoManager."""
        undo_mgr = self._tab_manager.get_active_undo_manager()
        if undo_mgr is not None:
            undo_mgr.redo()

    def _on_tab_switched_undo(self, session_id: str) -> None:
        """Update undo/redo menu state when tab switches."""
        undo_mgr = self._tab_manager.get_active_undo_manager()
        self._connect_undo_manager(undo_mgr)
        self._update_undo_menu_state()

    def _on_document_ready_undo(self, session_id: str, model: object) -> None:
        """Connect the new tab's UndoManager state_changed signal."""
        undo_mgr = self._tab_manager.get_active_undo_manager()
        self._connect_undo_manager(undo_mgr)

    def _connect_undo_manager(self, undo_mgr: UndoManager | None) -> None:
        """Connect/disconnect UndoManager.state_changed for menu updates.

        Args:
            undo_mgr: The UndoManager to connect, or None to disconnect only.
        """
        # Disconnect previous
        if self._active_undo_manager is not None:
            with contextlib.suppress(RuntimeError):
                self._active_undo_manager.state_changed.disconnect(self._update_undo_menu_state)

        self._active_undo_manager = undo_mgr

        # Connect new
        if undo_mgr is not None:
            undo_mgr.state_changed.connect(self._update_undo_menu_state)

    def _update_undo_menu_state(self) -> None:
        """Sync Edit menu Undo/Redo enabled state and text with active UndoManager."""
        undo_mgr = self._tab_manager.get_active_undo_manager()
        if undo_mgr is None:
            self._window.set_undo_state(can_undo=False, undo_text="", can_redo=False, redo_text="")
            return

        undo_text = f"&Undo {undo_mgr.undo_description}" if undo_mgr.can_undo else ""
        redo_text = f"&Redo {undo_mgr.redo_description}" if undo_mgr.can_redo else ""
        self._window.set_undo_state(
            can_undo=undo_mgr.can_undo,
            undo_text=undo_text,
            can_redo=undo_mgr.can_redo,
            redo_text=redo_text,
        )

    # --- Form creation handlers ---

    def _on_form_tool_mode_changed(self, mode_int: int) -> None:
        """Update viewport tool mode for form field placement."""
        mode = ToolMode(mode_int)
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.set_tool_mode(mode)

    def _on_document_ready_form_creation(self, session_id: str, model: object) -> None:
        """Enable form creation tools when a document loads."""
        self._window.set_form_tools_enabled(True)
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            # Avoid duplicate connections by disconnecting first
            with contextlib.suppress(RuntimeError):
                viewport.form_field_placed.disconnect(self._on_form_field_placed)
            viewport.form_field_placed.connect(self._on_form_field_placed)

    def _on_form_field_placed(
        self, page_index: int, point: tuple[float, float], tool_mode_int: int
    ) -> None:
        """Handle click-to-place from viewport — show FormFieldPopup."""
        field_type = self._form_creation_presenter.pending_field_type
        if field_type is None:
            return

        # Create and show popup
        self._form_field_popup = FormFieldPopup(field_type)
        self._form_field_popup.create_requested.connect(
            lambda props: self._on_popup_create(page_index, point, field_type, props)
        )
        self._form_field_popup.more_requested.connect(
            lambda props: self._on_popup_more(page_index, point, field_type, props)
        )
        self._form_field_popup.cancel_requested.connect(self._on_popup_cancel)

        # Position near click point
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            global_pos = viewport.mapToGlobal(viewport.rect().center())
            self._form_field_popup.show_near(global_pos.x(), global_pos.y())

    def _on_popup_create(
        self,
        page_index: int,
        point: tuple[float, float],
        field_type: FormFieldType,
        props: dict[str, object],
    ) -> None:
        """Handle Create from FormFieldPopup."""
        self._form_creation_presenter.create_field(page_index, point, field_type, props)

    def _on_popup_more(
        self,
        page_index: int,
        point: tuple[float, float],
        field_type: FormFieldType,
        props: dict[str, object],
    ) -> None:
        """Handle More... from FormFieldPopup — create field and open properties panel."""
        self._form_creation_presenter.create_field(page_index, point, field_type, props)
        props["field_type"] = field_type
        props["page"] = page_index
        self._window.form_properties_panel.load_properties(props)
        self._window.form_properties_panel.show()

    def _on_popup_cancel(self) -> None:
        """Handle Cancel from FormFieldPopup — tool mode stays active."""

    def _on_form_field_changed(self) -> None:
        """Re-render viewport after form field create/delete."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and viewport is not None:
            presenter.cache.invalidate()
            presenter._pending_renders.clear()
            first, last = viewport.get_visible_page_range()
            if first >= 0:
                presenter.request_pages(list(range(first, last + 1)))

    def _on_form_field_delete_from_panel(self) -> None:
        """Handle Delete button from FormPropertiesPanel."""
        self._window.form_properties_panel.clear()

    def _on_form_field_props_changed(self, props: dict[str, object]) -> None:
        """Handle property changes from FormPropertiesPanel.

        Will be connected to FormCreationPresenter.update_field_properties
        when field selection tracking is added.
        """

    # --- Text editing handlers ---

    def _on_text_edit_toggled(self, checked: bool) -> None:
        """Handle Edit Text tool toggle."""
        if checked:
            self._text_edit_presenter.set_tool_mode(ToolMode.TEXT_EDIT)
        else:
            self._text_edit_presenter.set_tool_mode(ToolMode.NONE)
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.set_tool_mode(ToolMode.TEXT_EDIT if checked else ToolMode.NONE)

    def _on_document_ready_text_edit(self, session_id: str, model: object) -> None:
        """Wire text edit signals when a document loads."""
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            with contextlib.suppress(RuntimeError):
                viewport.text_edit_requested.disconnect(self._on_text_edit_requested)
            viewport.text_edit_requested.connect(self._on_text_edit_requested)

    def _on_text_edit_requested(self, page_index: int, pdf_x: float, pdf_y: float) -> None:
        """Handle double-click in text edit mode — show inline edit overlay."""
        block = self._text_edit_presenter.get_text_block_at(page_index, pdf_x, pdf_y)
        if block is None:
            return  # No text at this position — no-op per spec

        # Show font limitation dialog if subset font
        if not block.is_fully_embedded:
            reply = QMessageBox.warning(
                self._window,
                "Cannot Edit Text Directly",
                f"This text uses a subset font ({block.font_name}) that only "
                "contains the original characters. Direct editing is not possible.\n\n"
                "Redact the original text and overlay new text using a standard "
                "font (Helvetica). The result will look similar but use a different font.",
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Ok:
                return
            # Will use redact_and_overlay path below

        # For now, use a simple QInputDialog for inline editing
        # A full floating overlay (like NoteEditor) can be added as a refinement
        from PySide6.QtWidgets import QInputDialog

        new_text, ok = QInputDialog.getText(
            self._window,
            "Edit Text",
            f"Editing text (font: {block.font_name})",
            text=block.text,
        )
        if not ok or new_text == block.text:
            return

        if block.is_fully_embedded:
            result = self._text_edit_presenter.edit_inline(
                page_index, block.rect, block.text, new_text
            )
            if not result.success:
                QMessageBox.warning(
                    self._window,
                    "Edit Failed",
                    result.error_message,
                )
        else:
            self._text_edit_presenter.redact_and_overlay(
                page_index, block.rect, new_text, block.font_size
            )

    def _on_replace_current(self, replacement_text: str) -> None:
        """Handle Replace button from FindReplaceBar."""
        # Get current match from SearchPresenter
        sid = self._search_presenter._active_session_id
        if sid is None or sid not in self._search_presenter._results:
            return

        result = self._search_presenter._results[sid]
        rect = result.current_rect()
        if rect is None:
            return

        self._text_edit_presenter.replace_current(
            result.current_page,
            rect,
            result.query,
            replacement_text,
        )
        # Advance to next match
        self._search_presenter.next_match()

    def _on_replace_all(self, replacement_text: str) -> None:
        """Handle Replace All button from FindReplaceBar."""
        sid = self._search_presenter._active_session_id
        if sid is None or sid not in self._search_presenter._results:
            return

        search_result = self._search_presenter._results[sid]
        if not search_result.matches:
            return

        result = self._text_edit_presenter.replace_all(
            search_result.matches,
            search_result.query,
            replacement_text,
        )

        if result is not None and result.replaced_count > 0:
            # Clear search results since text has changed
            self._search_presenter.close_search()

    def _on_text_edit_changed(self) -> None:
        """Re-render viewport after text edit."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and viewport is not None:
            presenter.cache.invalidate()
            presenter._pending_renders.clear()
            first, last = viewport.get_visible_page_range()
            if first >= 0:
                presenter.request_pages(list(range(first, last + 1)))

    def shutdown(self) -> None:
        """Clean up resources before exit."""
        self._annotation_toolbar.hide()
        self._note_editor.hide()
        self._search_presenter.shutdown()
        self._nav_presenter.shutdown()
        self._tab_manager.shutdown()
