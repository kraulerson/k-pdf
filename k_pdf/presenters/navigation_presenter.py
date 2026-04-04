"""Navigation presenter — coordinates thumbnails and outline with TabManager.

Listens to TabManager signals for document load, tab switch, and tab close.
Manages per-tab ThumbnailCache and outline data.
"""

from __future__ import annotations

import contextlib
import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap

from k_pdf.core.document_model import DocumentModel
from k_pdf.core.outline_model import OutlineNode
from k_pdf.core.thumbnail_cache import ThumbnailCache
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.outline_service import get_outline

logger = logging.getLogger("k_pdf.presenters.navigation_presenter")


class NavigationPresenter(QObject):
    """Coordinates navigation panel with active tab's data."""

    thumbnail_ready = Signal(int, object)  # (page_index, QPixmap)
    outline_ready = Signal(list)  # list[OutlineNode]
    active_thumbnail_changed = Signal(int)  # current page
    clear_requested = Signal()  # emitted before re-populating on tab switch

    def __init__(
        self,
        tab_manager: TabManager,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the navigation presenter.

        Args:
            tab_manager: The tab manager to subscribe to.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._tab_manager = tab_manager
        self._thumbnail_caches: dict[str, ThumbnailCache] = {}
        self._outlines: dict[str, list[OutlineNode]] = {}
        self._active_session_id: str | None = None

        # Connect to TabManager
        tab_manager.document_ready.connect(self._on_document_ready)
        tab_manager.tab_switched.connect(self._on_tab_switched)
        tab_manager.tab_closed.connect(self._on_tab_closed)
        tab_manager.tab_count_changed.connect(self._on_tab_count_changed)

    def navigate_to_page(self, page_index: int) -> None:
        """Scroll the active viewport to the given page.

        Args:
            page_index: 0-based page index.
        """
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.scroll_to_page(page_index)

    def get_outline_for(self, session_id: str) -> list[OutlineNode]:
        """Return cached outline for a session, or empty list."""
        return self._outlines.get(session_id, [])

    def get_thumbnail_cache(self, session_id: str) -> ThumbnailCache | None:
        """Return the thumbnail cache for a session, or None."""
        return self._thumbnail_caches.get(session_id)

    def shutdown(self) -> None:
        """Shut down all thumbnail caches."""
        for cache in self._thumbnail_caches.values():
            cache.shutdown()
        self._thumbnail_caches.clear()
        self._outlines.clear()

    def _on_document_ready(self, session_id: str, model: DocumentModel) -> None:
        """Handle new document loaded — start thumbnail rendering and fetch outline."""
        # Create thumbnail cache
        cache = ThumbnailCache(
            doc_handle=model.doc_handle,
            pages=model.pages,
            thumb_width=90,
        )
        cache.thumbnail_ready.connect(self._on_thumbnail_rendered)
        self._thumbnail_caches[session_id] = cache
        cache.start()

        # Fetch outline
        outline = get_outline(model.doc_handle)
        self._outlines[session_id] = outline
        logger.debug("outline loaded for %s: %d top-level nodes", session_id, len(outline))

        # If this is the active tab, push to view
        if session_id == self._tab_manager.active_session_id:
            self._active_session_id = session_id
            logger.debug("emitting outline_ready with %d nodes", len(outline))
            self.outline_ready.emit(outline)
            self._connect_viewport()

    def _on_tab_switched(self, session_id: str) -> None:
        """Handle tab switch — swap navigation data."""
        self._active_session_id = session_id

        # Clear previous tab's data before re-populating
        self.clear_requested.emit()

        # Push cached outline
        outline = self._outlines.get(session_id, [])
        self.outline_ready.emit(outline)

        # Push existing thumbnails
        cache = self._thumbnail_caches.get(session_id)
        if cache is not None:
            for i in range(10000):
                thumb = cache.get(i)
                if thumb is None and i > 0:
                    break
                if thumb is not None:
                    self.thumbnail_ready.emit(i, thumb)

        self._connect_viewport()

    def _on_tab_closed(self, session_id: str) -> None:
        """Handle tab close — clean up thumbnail cache and outline."""
        cache = self._thumbnail_caches.pop(session_id, None)
        if cache is not None:
            cache.shutdown()
        self._outlines.pop(session_id, None)

    def _on_tab_count_changed(self, count: int) -> None:
        """Handle all tabs closed."""
        if count == 0:
            self._active_session_id = None

    def _on_thumbnail_rendered(self, page_index: int, pixmap: QPixmap) -> None:
        """Forward thumbnail from cache to view."""
        self.thumbnail_ready.emit(page_index, pixmap)

    def _on_viewport_page_changed(self, page_index: int) -> None:
        """Handle viewport scroll — update current page highlight."""
        self.active_thumbnail_changed.emit(page_index)

    def _connect_viewport(self) -> None:
        """Connect to the active viewport's current_page_changed signal."""
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            with contextlib.suppress(RuntimeError, RuntimeWarning):
                viewport.current_page_changed.disconnect(self._on_viewport_page_changed)
            viewport.current_page_changed.connect(self._on_viewport_page_changed)
