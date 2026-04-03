"""Page management presenter.

Coordinates page operations between the PageManagerPanel view
and PageEngine service. Manages dirty flag and thumbnail refresh.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QMessageBox

from k_pdf.services.page_engine import PageEngine

logger = logging.getLogger("k_pdf.presenters.page_management_presenter")


class PageManagementPresenter(QObject):
    """Manages page operations, dirty flag, and thumbnail refresh."""

    dirty_changed = Signal(bool)
    pages_changed = Signal()

    def __init__(
        self,
        page_engine: PageEngine,
        tab_manager: Any,
        panel: Any,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the page management presenter.

        Args:
            page_engine: The PageEngine service for PDF operations.
            tab_manager: The TabManager for accessing active tab state.
            panel: The PageManagerPanel view.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._page_engine = page_engine
        self._tab_manager = tab_manager
        self._panel = panel

    def _get_active_model(self) -> Any | None:
        """Return the active tab's DocumentModel, or None."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is None or presenter.model is None:
            return None
        return presenter.model

    def rotate_pages(self, page_indices: list[int], angle: int) -> None:
        """Rotate selected pages and update thumbnails.

        Args:
            page_indices: Zero-based indices of pages to rotate.
            angle: Rotation angle (90 for right, 270 for left).
        """
        model = self._get_active_model()
        if model is None or not page_indices:
            return

        result = self._page_engine.rotate_pages(model.doc_handle, page_indices, angle)
        if result.success:
            model.dirty = True
            self.dirty_changed.emit(True)
            self._update_thumbnails_for(model.doc_handle, result.affected_pages)
            self.pages_changed.emit()

    def delete_pages(self, page_indices: list[int]) -> None:
        """Delete selected pages after confirmation.

        Args:
            page_indices: Zero-based indices of pages to delete.
        """
        model = self._get_active_model()
        if model is None or not page_indices:
            return

        count = len(page_indices)
        reply = QMessageBox.question(
            None,
            "Delete Pages",
            f"Delete {count} selected page(s)? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        result = self._page_engine.delete_pages(model.doc_handle, page_indices)
        if result.success:
            model.dirty = True
            self.dirty_changed.emit(True)
            self._refresh_all_thumbnails(model.doc_handle)
            self.pages_changed.emit()
        else:
            QMessageBox.warning(
                None,
                "Cannot Delete Pages",
                result.error_message,
            )

    def insert_pages(self, source_path: Path, insert_index: int) -> None:
        """Insert pages from another PDF at the given position.

        Args:
            source_path: Path to the source PDF.
            insert_index: Zero-based insertion position.
        """
        model = self._get_active_model()
        if model is None:
            return

        result = self._page_engine.insert_pages_from(model.doc_handle, source_path, insert_index)
        if result.success:
            model.dirty = True
            self.dirty_changed.emit(True)
            self._refresh_all_thumbnails(model.doc_handle)
            self.pages_changed.emit()
        else:
            QMessageBox.warning(
                None,
                "Insert Failed",
                result.error_message,
            )

    def move_page(self, from_index: int, to_index: int) -> None:
        """Move a page to a new position.

        Args:
            from_index: Current zero-based page index.
            to_index: Target zero-based page index.
        """
        if from_index == to_index:
            return

        model = self._get_active_model()
        if model is None:
            return

        result = self._page_engine.move_page(model.doc_handle, from_index, to_index)
        if result.success:
            model.dirty = True
            self.dirty_changed.emit(True)
            self._refresh_all_thumbnails(model.doc_handle)
            self.pages_changed.emit()

    def on_tab_switched(self, session_id: str) -> None:
        """Refresh panel for the newly active document.

        Args:
            session_id: The session ID of the new active tab.
        """
        model = self._get_active_model()
        if model is None:
            self._panel.set_thumbnails([])
            self._panel.set_buttons_enabled(False)
            self._panel.set_page_count_label(0)
            return

        self._panel.set_buttons_enabled(True)
        self._refresh_all_thumbnails(model.doc_handle)

    def on_tab_closed(self, session_id: str) -> None:
        """Clear panel if no tabs remain.

        Args:
            session_id: The session ID of the closed tab.
        """
        model = self._get_active_model()
        if model is None:
            self._panel.set_thumbnails([])
            self._panel.set_buttons_enabled(False)
            self._panel.set_page_count_label(0)

    def _refresh_all_thumbnails(self, doc_handle: Any) -> None:
        """Regenerate all thumbnails and update the panel.

        Args:
            doc_handle: The pymupdf.Document handle.
        """
        count = self._page_engine.get_page_count(doc_handle)
        pixmaps: list[QPixmap] = []
        for i in range(count):
            pixmaps.append(self._page_engine.render_thumbnail(doc_handle, i))
        self._panel.set_thumbnails(pixmaps)
        self._panel.set_page_count_label(count)

    def _update_thumbnails_for(self, doc_handle: Any, page_indices: list[int]) -> None:
        """Update thumbnails for specific pages.

        Args:
            doc_handle: The pymupdf.Document handle.
            page_indices: Pages to re-render.
        """
        for idx in page_indices:
            pixmap = self._page_engine.render_thumbnail(doc_handle, idx)
            self._panel.update_thumbnail(idx, pixmap)
