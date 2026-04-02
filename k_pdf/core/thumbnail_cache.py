"""Pre-rendering thumbnail cache for document pages.

One instance per open document. Renders all page thumbnails
on a dedicated QThread for instant scrolling in the navigation panel.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QImage, QPixmap

from k_pdf.core.document_model import PageInfo
from k_pdf.services.pdf_engine import PdfEngine

logger = logging.getLogger("k_pdf.core.thumbnail_cache")


class _ThumbnailWorker(QObject):
    """Worker that renders thumbnails off the main thread."""

    thumbnail_rendered = Signal(int, QImage)
    all_done = Signal()

    def __init__(self) -> None:
        """Initialize the thumbnail worker."""
        super().__init__()
        self._engine = PdfEngine()
        self._cancelled = False

    @Slot(object, list, int)
    def render_all(
        self,
        doc_handle: Any,
        pages: list[PageInfo],
        thumb_width: int,
    ) -> None:
        """Render thumbnails for all pages."""
        for page_info in pages:
            if self._cancelled:
                return
            zoom = thumb_width / page_info.width
            try:
                image = self._engine.render_page(doc_handle, page_info.index, zoom=zoom, rotation=0)
                self.thumbnail_rendered.emit(page_info.index, image)
            except Exception:
                logger.warning(
                    "Failed to render thumbnail for page %d",
                    page_info.index,
                    exc_info=True,
                )
        self.all_done.emit()

    def cancel(self) -> None:
        """Signal the worker to stop rendering."""
        self._cancelled = True


class ThumbnailCache(QObject):
    """Pre-renders and caches page thumbnails."""

    thumbnail_ready = Signal(int, object)  # (page_index, QPixmap)
    all_thumbnails_ready = Signal()

    def __init__(
        self,
        doc_handle: Any,
        pages: list[PageInfo],
        thumb_width: int = 90,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the thumbnail cache.

        Args:
            doc_handle: PyMuPDF document handle.
            pages: List of PageInfo for the document.
            thumb_width: Target thumbnail width in pixels.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._doc_handle = doc_handle
        self._pages = pages
        self._thumb_width = thumb_width
        self._cache: dict[int, QPixmap] = {}
        self._thread: QThread | None = None
        self._worker: _ThumbnailWorker | None = None

    def get(self, page_index: int) -> QPixmap | None:
        """Return a cached thumbnail, or None if not yet rendered."""
        return self._cache.get(page_index)

    def start(self) -> None:
        """Begin pre-rendering thumbnails on a background thread."""
        self._thread = QThread()
        self._worker = _ThumbnailWorker()
        self._worker.moveToThread(self._thread)
        self._thread.finished.connect(self._worker.deleteLater)

        self._worker.thumbnail_rendered.connect(self._on_thumbnail_rendered)
        self._worker.all_done.connect(self._on_all_done)

        self._thread.started.connect(
            lambda: self._worker.render_all(  # type: ignore[union-attr]
                self._doc_handle, self._pages, self._thumb_width
            )
        )
        self._thread.start()

    def cancel(self) -> None:
        """Cancel ongoing rendering."""
        if self._worker is not None:
            self._worker.cancel()

    def shutdown(self) -> None:
        """Stop the worker thread and clean up."""
        self.cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
        self._worker = None

    @Slot(int, QImage)
    def _on_thumbnail_rendered(self, page_index: int, image: QImage) -> None:
        """Convert QImage to QPixmap on main thread and cache it."""
        pixmap = QPixmap.fromImage(image)
        self._cache[page_index] = pixmap
        self.thumbnail_ready.emit(page_index, pixmap)

    @Slot()
    def _on_all_done(self) -> None:
        """Signal that all thumbnails have been rendered."""
        self.all_thumbnails_ready.emit()
