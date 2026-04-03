"""Tab lifecycle manager — coordinates multiple DocumentPresenter instances.

Each open document gets a TabContext (presenter + viewport + metadata).
TabManager handles creation, switching, closing, and duplicate detection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QTabWidget

from k_pdf.core.document_model import DocumentModel
from k_pdf.persistence.recent_files import RecentFiles
from k_pdf.presenters.document_presenter import DocumentPresenter
from k_pdf.views.pdf_viewport import PdfViewport

logger = logging.getLogger("k_pdf.presenters.tab_manager")


@dataclass
class TabContext:
    """Per-tab state bundle."""

    session_id: str = field(default_factory=lambda: str(uuid4()))
    presenter: DocumentPresenter | None = None
    viewport: PdfViewport | None = None
    resolved_path: Path | None = None


class TabManager(QObject):
    """Coordinates multiple document tabs."""

    # Signals
    document_ready = Signal(str, object)  # (session_id, DocumentModel)
    error_occurred = Signal(str, str)  # (title, message)
    password_requested = Signal(object)  # Path
    tab_count_changed = Signal(int)
    status_message = Signal(str)
    active_page_status = Signal(int, int)  # (current_page, total_pages)
    tab_switched = Signal(str)  # session_id
    tab_closed = Signal(str)  # session_id
    close_guard_requested = Signal(str)  # session_id — emitted when dirty tab close attempted

    def __init__(
        self,
        tab_widget: QTabWidget,
        recent_files: RecentFiles,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the tab manager.

        Args:
            tab_widget: The QTabWidget to add/remove viewport tabs.
            recent_files: The recent files persistence layer.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._tab_widget = tab_widget
        self._recent_files = recent_files
        self._tabs: dict[str, TabContext] = {}
        self._open_paths: dict[Path, str] = {}
        self._active_session_id: str | None = None

        # Connect QTabWidget signals
        self._tab_widget.currentChanged.connect(self._on_tab_switched)
        self._tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)

    @property
    def active_session_id(self) -> str | None:
        """Return the active tab's session ID."""
        return self._active_session_id

    def open_file(self, path: Path) -> None:
        """Open a PDF in a new tab, or activate existing tab if already open.

        Args:
            path: Path to the PDF file.
        """
        resolved = path.resolve()
        if resolved in self._open_paths:
            self.activate_tab(self._open_paths[resolved])
            self.status_message.emit("This file is already open")
            return

        # Create per-tab components
        ctx = TabContext()
        presenter = DocumentPresenter()
        viewport = PdfViewport()
        ctx.presenter = presenter
        ctx.viewport = viewport

        # Connect presenter → tab manager (bind session_id)
        sid = ctx.session_id
        presenter.document_ready.connect(partial(self._on_document_ready, sid))
        presenter.error_occurred.connect(partial(self._on_error, sid))
        presenter.password_requested.connect(partial(self._on_password_requested, sid))
        presenter.password_was_incorrect.connect(partial(self._on_password_incorrect, sid))
        presenter.page_pixmap_ready.connect(viewport.set_page_pixmap)
        presenter.page_error.connect(viewport.set_page_error)
        presenter.status_message.connect(self.status_message.emit)

        # Connect viewport → presenter
        viewport.visible_pages_changed.connect(presenter.request_pages)

        # Add to tab widget
        tab_index = self._tab_widget.addTab(viewport, "Loading...")
        self._tab_widget.setTabToolTip(tab_index, str(path))
        self._tabs[sid] = ctx
        self._tab_widget.setCurrentIndex(tab_index)
        self._active_session_id = sid
        self.tab_count_changed.emit(self._tab_widget.count())

        # Start loading
        presenter.open_file(path)

    def close_tab(self, session_id: str) -> None:
        """Close a tab, checking for unsaved changes first.

        If the document has unsaved changes (dirty=True), emits
        close_guard_requested instead of closing. The app layer
        handles the Save/Discard/Cancel dialog and calls
        force_close_tab() or save-then-close.

        Args:
            session_id: The session ID of the tab to close.
        """
        ctx = self._tabs.get(session_id)
        if ctx is None:
            return

        # Check dirty flag — defer to app layer for save dialog
        if (
            ctx.presenter is not None
            and ctx.presenter.model is not None
            and ctx.presenter.model.dirty
        ):
            self.close_guard_requested.emit(session_id)
            return

        self.force_close_tab(session_id)

    def force_close_tab(self, session_id: str) -> None:
        """Close a tab unconditionally (after save or discard).

        Args:
            session_id: The session ID of the tab to close.
        """
        ctx = self._tabs.get(session_id)
        if ctx is None:
            return

        self.tab_closed.emit(session_id)

        # Shut down presenter (stops thread, closes doc)
        if ctx.presenter is not None:
            ctx.presenter.shutdown()

        # Remove from tab widget
        if ctx.viewport is not None:
            idx = self._tab_widget.indexOf(ctx.viewport)
            if idx >= 0:
                self._tab_widget.removeTab(idx)

        # Clean up tracking
        if ctx.resolved_path is not None:
            self._open_paths.pop(ctx.resolved_path, None)
        del self._tabs[session_id]

        self.tab_count_changed.emit(len(self._tabs))

    def activate_tab(self, session_id: str) -> None:
        """Switch to the specified tab.

        Args:
            session_id: The session ID of the tab to activate.
        """
        ctx = self._tabs.get(session_id)
        if ctx is None or ctx.viewport is None:
            return

        idx = self._tab_widget.indexOf(ctx.viewport)
        if idx >= 0:
            self._tab_widget.setCurrentIndex(idx)
        self._active_session_id = session_id

        # Push status for this tab
        if ctx.presenter is not None and ctx.presenter.model is not None:
            model = ctx.presenter.model
            self.active_page_status.emit(1, model.metadata.page_count)

    def get_active_presenter(self) -> DocumentPresenter | None:
        """Return the active tab's presenter, or None."""
        if self._active_session_id is None:
            return None
        ctx = self._tabs.get(self._active_session_id)
        if ctx is None:
            return None
        return ctx.presenter

    def get_active_viewport(self) -> PdfViewport | None:
        """Return the active tab's viewport, or None."""
        if self._active_session_id is None:
            return None
        ctx = self._tabs.get(self._active_session_id)
        if ctx is None:
            return None
        return ctx.viewport

    def shutdown(self) -> None:
        """Shut down all tabs and clean up resources."""
        for sid in list(self._tabs):
            ctx = self._tabs[sid]
            if ctx.presenter is not None:
                ctx.presenter.shutdown()
        self._tabs.clear()
        self._open_paths.clear()
        self._active_session_id = None

    # --- Internal signal handlers ---

    def _on_document_ready(self, session_id: str, model: DocumentModel) -> None:
        """Handle successful document load for a tab."""
        ctx = self._tabs.get(session_id)
        if ctx is None:
            return

        # Register resolved path for duplicate detection
        resolved = model.file_path.resolve()
        ctx.resolved_path = resolved
        self._open_paths[resolved] = session_id

        # Update tab title
        title = f"* {model.file_path.name}" if model.dirty else model.file_path.name
        if ctx.viewport is not None:
            idx = self._tab_widget.indexOf(ctx.viewport)
            if idx >= 0:
                self._tab_widget.setTabText(idx, title)
                self._tab_widget.setTabToolTip(idx, str(model.file_path))

        # Set viewport document
        if ctx.viewport is not None:
            ctx.viewport.set_document(model.pages)

        # Recent files
        self._recent_files.add(model.file_path)

        # Emit signals
        self.document_ready.emit(session_id, model)
        self.active_page_status.emit(1, model.metadata.page_count)

    def _on_error(self, session_id: str, title: str, message: str) -> None:
        """Handle load error — show error and remove empty tab."""
        self.error_occurred.emit(title, message)
        # Remove the failed tab if document never loaded
        ctx = self._tabs.get(session_id)
        if ctx is not None and ctx.resolved_path is None:
            self.close_tab(session_id)

    def _on_password_requested(self, session_id: str, path: Path) -> None:
        """Forward password request for the active tab."""
        self.password_requested.emit(path)

    def _on_password_incorrect(self, session_id: str, path: Path) -> None:
        """Forward incorrect password for retry."""
        self.error_occurred.emit("Incorrect password", "Incorrect password. Try again.")
        self.password_requested.emit(path)

    def _on_tab_switched(self, index: int) -> None:
        """Handle QTabWidget currentChanged signal."""
        if index < 0:
            self._active_session_id = None
            return
        widget = self._tab_widget.widget(index)
        for sid, ctx in self._tabs.items():
            if ctx.viewport is widget:
                self._active_session_id = sid
                self.tab_switched.emit(sid)
                if ctx.presenter is not None and ctx.presenter.model is not None:
                    model = ctx.presenter.model
                    self.active_page_status.emit(1, model.metadata.page_count)
                break

    def _on_tab_close_requested(self, index: int) -> None:
        """Handle QTabWidget tabCloseRequested signal."""
        widget = self._tab_widget.widget(index)
        for sid, ctx in self._tabs.items():
            if ctx.viewport is widget:
                self.close_tab(sid)
                break
