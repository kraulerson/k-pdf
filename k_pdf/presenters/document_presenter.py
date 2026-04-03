"""Document presenter — coordinates PDF services with views.

Receives file-open requests, validates paths, dispatches PyMuPDF work
to a background thread via PdfWorker, and updates the viewport via
signals when pages are ready.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QImage, QPixmap

from k_pdf.core.document_model import DocumentModel
from k_pdf.core.page_cache import PageCache
from k_pdf.core.zoom_model import FitMode, ZoomState
from k_pdf.services.pdf_engine import OpenResult, PdfEngine
from k_pdf.services.pdf_errors import (
    PageRenderError,
    PdfError,
    PdfPasswordIncorrectError,
    PdfPasswordRequiredError,
    PdfValidationError,
)

logger = logging.getLogger("k_pdf.presenters.document_presenter")


class PdfWorker(QObject):
    """Worker that runs PdfEngine operations off the Qt event loop."""

    document_loaded = Signal(object)  # OpenResult
    load_failed = Signal(str, str)  # (title, message)
    password_required = Signal(object)  # Path
    password_incorrect = Signal(object)  # Path
    page_rendered = Signal(int, QImage)  # (page_index, QImage)
    page_render_failed = Signal(int)  # page_index

    def __init__(self) -> None:
        """Initialize the worker with a PdfEngine instance."""
        super().__init__()
        self._engine = PdfEngine()

    @Slot(object, object)
    def open_document(self, path: Path, password: str | None = None) -> None:
        """Open a PDF in the background thread."""
        try:
            result = self._engine.open_document(path, password=password)
            self.document_loaded.emit(result)
        except PdfPasswordRequiredError:
            self.password_required.emit(path)
        except PdfPasswordIncorrectError:
            self.password_incorrect.emit(path)
        except PdfError as e:
            self.load_failed.emit("Cannot open file", str(e))
        except Exception as e:
            self.load_failed.emit(
                "Unexpected error",
                f"An unexpected error occurred: {type(e).__name__}: {e}",
            )

    @Slot(object, list, float, int)
    def render_pages(
        self,
        doc_handle: Any,
        page_indices: list[int],
        zoom: float,
        rotation: int,
    ) -> None:
        """Render a batch of pages in the background thread."""
        for idx in page_indices:
            try:
                image = self._engine.render_page(doc_handle, idx, zoom, rotation)
                self.page_rendered.emit(idx, image)
            except PageRenderError:
                logger.warning("Failed to render page %d", idx, exc_info=True)
                self.page_render_failed.emit(idx)


class DocumentPresenter(QObject):
    """Coordinates PdfEngine, DocumentModel, PageCache, and views."""

    # Signals for the view layer
    document_ready = Signal(object)  # DocumentModel
    error_occurred = Signal(str, str)  # (title, message)
    password_requested = Signal(object)  # Path
    password_was_incorrect = Signal(object)  # Path
    page_pixmap_ready = Signal(int, object)  # (page_index, QPixmap)
    page_error = Signal(int)  # page_index
    status_message = Signal(str)
    zoom_changed = Signal(float)  # emitted after zoom level changes
    rotation_changed = Signal(int)  # emitted after rotation changes

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the presenter with worker thread and page cache."""
        super().__init__(parent)
        self._engine = PdfEngine()
        self._model: DocumentModel | None = None
        self._cache = PageCache()
        self._pending_renders: set[int] = set()
        self._zoom_state = ZoomState()

        # Worker thread setup
        self._thread = QThread()
        self._worker = PdfWorker()
        self._worker.moveToThread(self._thread)
        self._thread.finished.connect(self._worker.deleteLater)

        # Connect worker signals
        self._worker.document_loaded.connect(self._on_document_loaded)
        self._worker.load_failed.connect(self._on_load_failed)
        self._worker.password_required.connect(self._on_password_required)
        self._worker.password_incorrect.connect(self._on_password_incorrect)
        self._worker.page_rendered.connect(self._on_page_rendered)
        self._worker.page_render_failed.connect(self._on_page_render_failed)

        self._thread.start()

    @property
    def model(self) -> DocumentModel | None:
        """Return the current document model, or None if no document is open."""
        return self._model

    @property
    def cache(self) -> PageCache:
        """Return the page cache."""
        return self._cache

    @property
    def zoom(self) -> float:
        """Return the current zoom level."""
        return self._zoom_state.zoom

    @property
    def rotation(self) -> int:
        """Return the current rotation in degrees."""
        return self._zoom_state.rotation

    @property
    def fit_mode(self) -> FitMode:
        """Return the current fit mode."""
        return self._zoom_state.fit_mode

    def open_file(self, path: Path) -> None:
        """Start the file-open flow.

        Validates the path on the main thread, then dispatches
        the heavy PyMuPDF open to the worker thread.
        """
        try:
            self._engine.validate_pdf_path(path)
        except PdfValidationError as e:
            self.error_occurred.emit("Validation Error", str(e))
            return

        self.status_message.emit(f"Opening {path.name}...")
        self._worker.open_document(path)

    def open_file_with_password(self, path: Path, password: str) -> None:
        """Retry opening an encrypted file with a password."""
        self._worker.open_document(path, password)

    def request_pages(self, page_indices: list[int]) -> None:
        """Request rendering for a list of page indices.

        Pages already in the cache are emitted immediately.
        Missing pages are dispatched to the worker thread.
        """
        if self._model is None:
            return

        to_render: list[int] = []
        for idx in page_indices:
            cached = self._cache.get(idx)
            if cached is not None:
                self.page_pixmap_ready.emit(idx, cached)
            elif idx not in self._pending_renders:
                to_render.append(idx)
                self._pending_renders.add(idx)

        if to_render:
            self._worker.render_pages(
                self._model.doc_handle,
                to_render,
                self._zoom_state.zoom,
                self._zoom_state.rotation,
            )

    def set_zoom(self, zoom: float) -> None:
        """Set the zoom level, clamp, clear fit mode, invalidate cache, re-render.

        Emits zoom_changed if the value actually changed.

        Args:
            zoom: Desired zoom level (1.0 = 100%).
        """
        clamped = self._zoom_state.clamp_zoom(zoom)
        if clamped == self._zoom_state.zoom:
            return
        self._zoom_state.zoom = clamped
        self._zoom_state.fit_mode = FitMode.NONE
        self._cache.invalidate()
        self._pending_renders.clear()
        self.zoom_changed.emit(clamped)

    def set_rotation(self, rotation: int) -> None:
        """Set the rotation, normalize, invalidate cache, re-render.

        Emits rotation_changed if the value actually changed.

        Args:
            rotation: Desired rotation in degrees (any integer).
        """
        normalized = self._zoom_state.normalize_rotation(rotation)
        if normalized == self._zoom_state.rotation:
            return
        self._zoom_state.rotation = normalized
        self._cache.invalidate()
        self._pending_renders.clear()
        self.rotation_changed.emit(normalized)

    def set_fit_mode(self, mode: FitMode, viewport_width: float, viewport_height: float) -> None:
        """Set a fit mode and calculate zoom from viewport and page dimensions.

        Emits zoom_changed if the calculated zoom differs from current.
        Does nothing if mode is NONE or no document is loaded.

        Args:
            mode: The fit mode to apply.
            viewport_width: Current viewport width in pixels.
            viewport_height: Current viewport height in pixels.
        """
        if mode is FitMode.NONE or self._model is None or not self._model.pages:
            return

        page = self._model.pages[0]
        # Account for rotation: swap width/height at 90/270 degrees
        if self._zoom_state.rotation in (90, 270):
            page_w = page.height
            page_h = page.width
        else:
            page_w = page.width
            page_h = page.height

        if mode is FitMode.PAGE:
            new_zoom = min(viewport_width / page_w, viewport_height / page_h)
        else:  # FitMode.WIDTH
            new_zoom = viewport_width / page_w

        new_zoom = self._zoom_state.clamp_zoom(new_zoom)
        self._zoom_state.fit_mode = mode
        if new_zoom != self._zoom_state.zoom:
            self._zoom_state.zoom = new_zoom
            self._cache.invalidate()
            self._pending_renders.clear()
            self.zoom_changed.emit(new_zoom)

    def shutdown(self) -> None:
        """Stop the worker thread and clean up."""
        self._thread.quit()
        self._thread.wait()
        if self._model is not None:
            self._engine.close_document(self._model.doc_handle)
            self._model = None

    # --- Worker signal handlers ---

    @Slot(object)
    def _on_document_loaded(self, result: OpenResult) -> None:
        """Handle successful document load from worker."""
        self._model = DocumentModel(
            file_path=result.metadata.file_path,
            doc_handle=result.doc_handle,
            metadata=result.metadata,
            pages=result.pages,
        )
        self._cache.invalidate()
        self._pending_renders.clear()
        self.status_message.emit(
            f"Loaded {result.metadata.file_path.name} ({result.metadata.page_count} pages)"
        )
        self.document_ready.emit(self._model)

    @Slot(str, str)
    def _on_load_failed(self, title: str, message: str) -> None:
        """Handle load failure from worker."""
        self.error_occurred.emit(title, message)
        self.status_message.emit("Failed to open file")

    @Slot(object)
    def _on_password_required(self, path: Path) -> None:
        """Handle password-required signal from worker."""
        self.password_requested.emit(path)

    @Slot(object)
    def _on_password_incorrect(self, path: Path) -> None:
        """Handle incorrect password from worker."""
        self.password_was_incorrect.emit(path)

    @Slot(int, QImage)
    def _on_page_rendered(self, page_index: int, image: QImage) -> None:
        """Handle rendered page from worker — convert to QPixmap on main thread."""
        self._pending_renders.discard(page_index)
        pixmap = QPixmap.fromImage(image)
        self._cache.put(page_index, pixmap)
        self.page_pixmap_ready.emit(page_index, pixmap)

    @Slot(int)
    def _on_page_render_failed(self, page_index: int) -> None:
        """Handle page render failure."""
        self._pending_renders.discard(page_index)
        self.page_error.emit(page_index)
