"""Annotation presenter — coordinates text selection, note editing, toolbar, and engine.

Manages tool modes (text selection, sticky note, text box), floating toolbar visibility,
annotation creation/deletion/update, and the dirty flag. Subscribes to TabManager signals
for tab-switch coordination.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from k_pdf.core.annotation_model import AnnotationType, ToolMode
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.annotation_engine import AnnotationEngine
from k_pdf.views.annotation_toolbar import AnnotationToolbar
from k_pdf.views.note_editor import NoteEditor

logger = logging.getLogger("k_pdf.presenters.annotation_presenter")


class AnnotationPresenter(QObject):
    """Coordinates text selection, note editing, annotation toolbar, and annotation engine."""

    dirty_changed = Signal(bool)  # emitted when dirty flag transitions
    annotation_created = Signal()  # emitted after annotation added (triggers re-render)
    annotation_deleted = Signal()  # emitted after annotation removed (triggers re-render)
    tool_mode_changed = Signal(int)  # emitted when tool mode changes
    text_copied = Signal(str)  # emitted after text is copied to clipboard
    selection_changed = Signal(bool)  # emitted when selection state changes

    def __init__(
        self,
        tab_manager: TabManager,
        engine: AnnotationEngine,
        toolbar: AnnotationToolbar,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the annotation presenter.

        Args:
            tab_manager: The tab manager for accessing active tab state.
            engine: The annotation engine for PyMuPDF operations.
            toolbar: The floating annotation toolbar widget.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._tab_manager = tab_manager
        self._engine = engine
        self._toolbar = toolbar

        self._tool_mode: ToolMode = ToolMode.NONE
        self._selection_mode: bool = False
        self._selected_rects: list[tuple[float, float, float, float]] = []
        self._selected_page: int = -1

        self._note_editor: NoteEditor | None = None
        self._pending_point: tuple[float, float] | None = None
        self._pending_rect: tuple[float, float, float, float] | None = None

        # Connect toolbar signals
        self._toolbar.annotation_requested.connect(self._on_annotation_requested)
        self._toolbar.dismissed.connect(self._on_toolbar_dismissed)

        # Connect tab manager signals
        self._tab_manager.tab_switched.connect(self.on_tab_switched)

    def set_note_editor(self, editor: NoteEditor) -> None:
        """Set the NoteEditor widget reference.

        Args:
            editor: A NoteEditor instance.
        """
        self._note_editor = editor

    @property
    def has_selection(self) -> bool:
        """Return True when text is currently selected."""
        return bool(self._selected_rects) and self._selected_page >= 0

    def copy_selected_text(self) -> str:
        """Extract text from current selection and copy to system clipboard.

        Returns:
            The extracted text string. Empty string if no selection or no document.
        """
        if not self.has_selection:
            return ""

        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return ""

        model = doc_presenter.model
        text = self._engine.extract_text_in_rects(
            model.doc_handle, self._selected_page, self._selected_rects
        )

        if text:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(text)
            self.text_copied.emit(text)
            logger.debug("Copied %d characters to clipboard", len(text))

        return text

    def set_tool_mode(self, mode: ToolMode) -> None:
        """Set the active tool mode.

        Updates viewport interaction mode and cursor, clears selection
        and hides toolbar when switching to NONE.

        Args:
            mode: The tool mode to activate.
        """
        self._tool_mode = mode
        self._selection_mode = mode is ToolMode.TEXT_SELECT

        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.set_tool_mode(mode)

        if mode is ToolMode.NONE:
            self._clear_selection()
            self._toolbar.hide()

        self.tool_mode_changed.emit(int(mode))

    def set_selection_mode(self, active: bool) -> None:
        """Compatibility shim — sets TEXT_SELECT or NONE mode.

        Args:
            active: True to enable text selection, False for pan mode.
        """
        self.set_tool_mode(ToolMode.TEXT_SELECT if active else ToolMode.NONE)

    def on_text_selected(
        self, page_index: int, rects: list[tuple[float, float, float, float]]
    ) -> None:
        """Handle text selection from viewport.

        Stores the selection and shows the floating toolbar.

        Args:
            page_index: Zero-based page index.
            rects: List of (x0, y0, x1, y1) word bounding boxes in PDF coords.
        """
        if not rects:
            return

        self._selected_page = page_index
        self._selected_rects = rects
        self.selection_changed.emit(True)

        # Show toolbar near the selection
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            global_pos = viewport.mapToGlobal(viewport.rect().center())
            self._toolbar.show_near(global_pos.x(), global_pos.y() - 60)

    def create_annotation(
        self,
        ann_type: AnnotationType,
        color: tuple[float, float, float],
    ) -> None:
        """Create a text markup annotation from the current selection.

        Args:
            ann_type: The annotation type (HIGHLIGHT, UNDERLINE, STRIKETHROUGH).
            color: RGB color as 0.0-1.0 floats.
        """
        if not self._selected_rects or self._selected_page < 0:
            return

        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return

        model = doc_presenter.model
        quads = self._engine.rects_to_quads(self._selected_rects)

        if ann_type is AnnotationType.HIGHLIGHT:
            self._engine.add_highlight(model.doc_handle, self._selected_page, quads, color)
        elif ann_type is AnnotationType.UNDERLINE:
            self._engine.add_underline(model.doc_handle, self._selected_page, quads, color)
        elif ann_type is AnnotationType.STRIKETHROUGH:
            self._engine.add_strikeout(model.doc_handle, self._selected_page, quads, color)

        model.dirty = True
        self.dirty_changed.emit(True)
        self.annotation_created.emit()

        # Clear selection after annotation creation
        self._clear_selection()
        self._toolbar.hide()

        logger.debug(
            "Created %s annotation on page %d with color %s",
            ann_type.value,
            self._selected_page,
            color,
        )

    def delete_annotation(self, page_index: int, annot: object) -> None:
        """Delete an annotation from a page.

        Args:
            page_index: Zero-based page index.
            annot: The annotation object to delete.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return

        model = doc_presenter.model
        self._engine.delete_annotation(model.doc_handle, page_index, annot)

        model.dirty = True
        self.dirty_changed.emit(True)
        self.annotation_deleted.emit()

        logger.debug("Deleted annotation on page %d", page_index)

    def on_note_placed(self, page_index: int, point: tuple[float, float]) -> None:
        """Handle sticky note placement click from viewport.

        Opens the NoteEditor for a new sticky note at the given point.

        Args:
            page_index: Zero-based page index.
            point: (x, y) position in PDF coordinates.
        """
        self._pending_point = point
        self._pending_rect = None

        if self._note_editor is not None:
            viewport = self._tab_manager.get_active_viewport()
            x, y = 100, 200
            if viewport is not None:
                global_pos = viewport.mapToGlobal(viewport.rect().center())
                x, y = global_pos.x(), global_pos.y()
            self._note_editor.show_for_new("sticky_note", page_index, x, y)

    def on_textbox_drawn(self, page_index: int, rect: tuple[float, float, float, float]) -> None:
        """Handle text box drag completion from viewport.

        Opens the NoteEditor for a new text box with the given rectangle.

        Args:
            page_index: Zero-based page index.
            rect: (x0, y0, x1, y1) bounding rectangle in PDF coordinates.
        """
        self._pending_rect = rect
        self._pending_point = None

        if self._note_editor is not None:
            viewport = self._tab_manager.get_active_viewport()
            x, y = 100, 200
            if viewport is not None:
                global_pos = viewport.mapToGlobal(viewport.rect().center())
                x, y = global_pos.x(), global_pos.y()
            self._note_editor.show_for_new("text_box", page_index, x, y)

    def on_annotation_double_clicked(self, page_index: int, annot: object) -> None:
        """Handle double-click on existing annotation — open editor with content.

        Args:
            page_index: Zero-based page index.
            annot: The annotation object that was double-clicked.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return
        model = doc_presenter.model
        content = self._engine.get_annotation_content(model.doc_handle, page_index, annot)

        # Determine mode from annotation type (via engine to avoid stale ref)
        annot_type = self._engine.get_annotation_type(model.doc_handle, page_index, annot)
        # Type 0 = Text (sticky note), Type 2 = FreeText (text box)
        mode = "sticky_note" if annot_type[0] == 0 else "text_box"

        if self._note_editor is not None:
            viewport = self._tab_manager.get_active_viewport()
            x, y = 100, 200
            if viewport is not None:
                global_pos = viewport.mapToGlobal(viewport.rect().center())
                x, y = global_pos.x(), global_pos.y()
            self._note_editor.show_for_existing(mode, page_index, annot, content, x, y)

    def _on_editing_finished(self, content: str) -> None:
        """Handle NoteEditor save — create or update annotation.

        Args:
            content: The text content from the NoteEditor.
        """
        if self._note_editor is None:
            return

        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return
        model = doc_presenter.model

        editor = self._note_editor
        target_annot = editor._target_annot
        page_index: int = editor._target_page
        mode: str = editor._mode
        if target_annot is not None:
            # Update existing annotation
            self._engine.update_annotation_content(
                model.doc_handle, page_index, target_annot, content
            )
        elif mode == "sticky_note" and self._pending_point is not None:
            self._engine.add_sticky_note(model.doc_handle, page_index, self._pending_point, content)
        elif mode == "text_box" and self._pending_rect is not None:
            self._engine.add_text_box(model.doc_handle, page_index, self._pending_rect, content)

        model.dirty = True
        self.dirty_changed.emit(True)
        self.annotation_created.emit()

        self._pending_point = None
        self._pending_rect = None
        self.set_tool_mode(ToolMode.NONE)

        logger.debug("Annotation editing finished on page %d", page_index)

    def _on_editing_cancelled(self) -> None:
        """Handle NoteEditor cancel — reset pending state and tool mode."""
        self._pending_point = None
        self._pending_rect = None
        self.set_tool_mode(ToolMode.NONE)

    def on_tab_switched(self, session_id: str) -> None:
        """Handle tab switch — clear selection, hide toolbar, cancel editing.

        Args:
            session_id: The new active tab's session ID.
        """
        # _clear_selection emits selection_changed(False) if there was a selection
        self._clear_selection()
        self._toolbar.hide()
        if self._note_editor is not None:
            self._note_editor.hide()
        self._tool_mode = ToolMode.NONE
        self._selection_mode = False

    def _clear_selection(self) -> None:
        """Clear the stored text selection state and emit selection_changed(False)."""
        had_selection = self.has_selection
        self._selected_rects = []
        self._selected_page = -1
        if had_selection:
            self.selection_changed.emit(False)

    def _on_annotation_requested(
        self, ann_type: AnnotationType, color: tuple[float, float, float]
    ) -> None:
        """Handle annotation creation request from toolbar."""
        self.create_annotation(ann_type, color)

    def _on_toolbar_dismissed(self) -> None:
        """Handle toolbar dismissal — clear selection overlay on viewport."""
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.clear_selection_overlay()
