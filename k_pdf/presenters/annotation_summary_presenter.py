"""Annotation summary presenter.

Subscribes to TabManager and AnnotationPresenter signals, maintains
per-tab annotation lists, and coordinates the AnnotationSummaryPanel.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject

from k_pdf.core.annotation_model import AnnotationInfo
from k_pdf.core.document_model import DocumentModel
from k_pdf.services.annotation_engine import AnnotationEngine

logger = logging.getLogger("k_pdf.presenters.annotation_summary_presenter")


class AnnotationSummaryPresenter(QObject):
    """Manages per-tab annotation lists for the annotation summary panel."""

    def __init__(
        self,
        tab_manager: Any,
        annotation_engine: AnnotationEngine,
        panel: Any,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the annotation summary presenter.

        Args:
            tab_manager: The TabManager for accessing active tab state.
            annotation_engine: The AnnotationEngine service.
            panel: The AnnotationSummaryPanel view.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._tab_manager = tab_manager
        self._engine = annotation_engine
        self._panel = panel
        self._per_tab_annotations: dict[str, list[AnnotationInfo]] = {}

    def on_document_ready(self, session_id: str, model: DocumentModel) -> None:
        """Scan all pages for annotations and update the panel.

        Args:
            session_id: The tab's session ID.
            model: The DocumentModel for the loaded document.
        """
        annotations = self._scan_annotations(model)
        self._per_tab_annotations[session_id] = annotations

        # Only update panel if this is the active tab
        if self._tab_manager.active_session_id == session_id:
            self._panel.set_annotations(annotations)

    def refresh_annotations(self) -> None:
        """Rescan the active document's annotations and update the panel."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is None or presenter.model is None:
            self._panel.clear()
            return

        model = presenter.model
        session_id = self._tab_manager.active_session_id
        annotations = self._scan_annotations(model)

        if session_id is not None:
            self._per_tab_annotations[session_id] = annotations

        self._panel.set_annotations(annotations)

    def on_tab_switched(self, session_id: str) -> None:
        """Swap panel content to the stored annotations for the new tab.

        Args:
            session_id: The session ID of the newly active tab.
        """
        stored = self._per_tab_annotations.get(session_id)
        if stored is not None:
            self._panel.set_annotations(stored)
        else:
            self._panel.clear()

    def on_tab_closed(self, session_id: str) -> None:
        """Remove stored annotations for a closed tab.

        Args:
            session_id: The session ID of the closed tab.
        """
        self._per_tab_annotations.pop(session_id, None)

    def on_annotation_clicked(self, page_index: int) -> None:
        """Navigate the viewport to the annotation's page.

        Args:
            page_index: Zero-based page index to navigate to.
        """
        viewport = self._tab_manager.get_active_viewport()
        if viewport is None:
            return
        viewport.scroll_to_page(page_index)

    def _scan_annotations(self, model: DocumentModel) -> list[AnnotationInfo]:
        """Scan all pages for annotations and build an AnnotationInfo list.

        Args:
            model: The DocumentModel to scan.

        Returns:
            List of AnnotationInfo for all annotations in the document.
        """
        result: list[AnnotationInfo] = []
        page_count = model.metadata.page_count

        for page_idx in range(page_count):
            annots = self._engine.get_annotations(model.doc_handle, page_idx)
            for annot in annots:
                info_dict = self._engine.get_annotation_info(model.doc_handle, page_idx, annot)
                ann_info = AnnotationInfo(
                    page=page_idx,
                    ann_type=info_dict.get("type_name", "Unknown"),
                    author=info_dict.get("author", ""),
                    content=info_dict.get("content", ""),
                    color=info_dict.get("color", (0.0, 0.0, 0.0)),
                    rect=info_dict.get("rect", (0.0, 0.0, 0.0, 0.0)),
                )
                result.append(ann_info)

        return result
