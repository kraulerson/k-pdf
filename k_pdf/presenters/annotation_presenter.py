"""Annotation presenter — coordinates text selection, toolbar, and annotation engine.

Manages text selection mode, selected text regions, floating toolbar visibility,
annotation creation/deletion, and the dirty flag. Subscribes to TabManager signals
for tab-switch coordination.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from k_pdf.core.annotation_model import AnnotationType
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.annotation_engine import AnnotationEngine
from k_pdf.views.annotation_toolbar import AnnotationToolbar

logger = logging.getLogger("k_pdf.presenters.annotation_presenter")


class AnnotationPresenter(QObject):
    """Coordinates text selection, annotation toolbar, and annotation engine."""

    dirty_changed = Signal(bool)  # emitted when dirty flag transitions
    annotation_created = Signal()  # emitted after annotation added (triggers re-render)
    annotation_deleted = Signal()  # emitted after annotation removed (triggers re-render)

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

        self._selection_mode: bool = False
        self._selected_rects: list[tuple[float, float, float, float]] = []
        self._selected_page: int = -1

        # Connect toolbar signals
        self._toolbar.annotation_requested.connect(self._on_annotation_requested)
        self._toolbar.dismissed.connect(self._on_toolbar_dismissed)

        # Connect tab manager signals
        self._tab_manager.tab_switched.connect(self.on_tab_switched)

    def set_selection_mode(self, active: bool) -> None:
        """Toggle text selection mode on the active viewport.

        Args:
            active: True to enable text selection, False for pan mode.
        """
        self._selection_mode = active
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.set_selection_mode(active)
        if not active:
            self._clear_selection()
            self._toolbar.hide()

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

        # Show toolbar near the selection
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            # Map the midpoint of the first selected rect to global coords
            # Use a rough position above the selection area
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

    def on_tab_switched(self, session_id: str) -> None:
        """Handle tab switch — clear selection and hide toolbar.

        Args:
            session_id: The new active tab's session ID.
        """
        self._clear_selection()
        self._toolbar.hide()

    def _clear_selection(self) -> None:
        """Clear the stored text selection state."""
        self._selected_rects = []
        self._selected_page = -1

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
