"""QApplication shell and event bus initialization.

Creates the main window, presenter, and wires signals together.
Handles CLI file arguments.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from k_pdf.core.document_model import DocumentModel
from k_pdf.persistence.recent_files import RecentFiles
from k_pdf.persistence.settings_db import init_db
from k_pdf.presenters.document_presenter import DocumentPresenter
from k_pdf.views.main_window import MainWindow

logger = logging.getLogger("k_pdf.app")


class KPdfApp:
    """Application controller — wires presenter to views."""

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
        self._presenter = DocumentPresenter()
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
    def presenter(self) -> DocumentPresenter:
        """Return the document presenter."""
        return self._presenter

    def _connect_signals(self) -> None:
        """Wire presenter signals to view slots and vice versa."""
        # View → Presenter
        self._window.file_open_requested.connect(self._presenter.open_file)
        self._window.password_submitted.connect(self._presenter.open_file_with_password)
        self._window.viewport.visible_pages_changed.connect(self._presenter.request_pages)

        # Presenter → View
        self._presenter.document_ready.connect(self._on_document_ready)
        self._presenter.error_occurred.connect(self._window.show_error)
        self._presenter.password_requested.connect(self._window.show_password_dialog)
        self._presenter.password_was_incorrect.connect(self._on_password_incorrect)
        self._presenter.page_pixmap_ready.connect(self._window.viewport.set_page_pixmap)
        self._presenter.page_error.connect(self._window.viewport.set_page_error)
        self._presenter.status_message.connect(self._window.update_status_message)

    def _on_document_ready(self, model: DocumentModel) -> None:
        """Handle a successfully loaded document."""
        self._window.viewport.set_document(model.pages)
        self._window.update_page_status(1, model.metadata.page_count)
        self._recent_files.add(model.file_path)

    def _on_password_incorrect(self, path: Path) -> None:
        """Re-show the password dialog with an error hint."""
        self._window.show_error("Incorrect password", "Incorrect password. Try again.")
        self._window.show_password_dialog(path)

    def _open_initial_file(self) -> None:
        """Open the file passed via CLI argument."""
        if self._initial_file:
            self._presenter.open_file(Path(self._initial_file))

    def shutdown(self) -> None:
        """Clean up resources before exit."""
        self._presenter.shutdown()
