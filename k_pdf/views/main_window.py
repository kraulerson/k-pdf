"""Main application window.

Three-panel layout (navigation | viewport | annotations) with
menu bar, toolbar, status bar, and tab bar. For Feature 1, only
the viewport center panel is active. Navigation and annotation
panels are placeholders for Features 3 and 12.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import override

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QWidget,
)

from k_pdf.views.pdf_viewport import PdfViewport

logger = logging.getLogger("k_pdf.views.main_window")


class MainWindow(QMainWindow):
    """K-PDF main application window."""

    file_open_requested = Signal(Path)
    password_submitted = Signal(Path, str)  # (path, password)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the main window with viewport, menus, and status bar."""
        super().__init__(parent)
        self.setWindowTitle("K-PDF")
        self.setMinimumSize(800, 600)
        self.resize(1200, 800)
        self.setAcceptDrops(True)

        # Central viewport
        self.viewport = PdfViewport(self)
        self.setCentralWidget(self.viewport)
        self.viewport.welcome_widget.open_clicked.connect(self._open_file_dialog)

        # Status bar
        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)
        self._page_label = QLabel("No document")
        self._zoom_label = QLabel("100%")
        self._status_bar.addPermanentWidget(self._page_label)
        self._status_bar.addPermanentWidget(self._zoom_label)

        # Menus
        self._setup_menus()

    def _setup_menus(self) -> None:
        """Create the menu bar with File > Open and File > Quit."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _open_file_dialog(self) -> None:
        """Show the native file picker and emit file_open_requested."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF",
            "",
            "PDF Files (*.pdf);;All Files (*)",
        )
        if path:
            self.file_open_requested.emit(Path(path))

    def show_error(self, title: str, message: str) -> None:
        """Show an error dialog.

        Args:
            title: Dialog title.
            message: Error message body.
        """
        QMessageBox.critical(self, title, message)

    def show_password_dialog(self, path: Path) -> None:
        """Show a password input dialog for encrypted PDFs.

        Args:
            path: Path to the encrypted PDF.
        """
        password, ok = QInputDialog.getText(
            self,
            "Password Required",
            f"This document is protected.\nEnter the password to open it.\n\n{path.name}",
            QLineEdit.EchoMode.Password,
        )
        if ok and password:
            self.password_submitted.emit(path, password)

    def update_page_status(self, current: int, total: int) -> None:
        """Update the page indicator in the status bar.

        Args:
            current: Current page number (1-based).
            total: Total number of pages.
        """
        self._page_label.setText(f"Page {current} of {total}")

    def update_status_message(self, message: str) -> None:
        """Show a temporary message in the status bar.

        Args:
            message: Message text.
        """
        self._status_bar.showMessage(message, 5000)

    # --- Drag and drop ---

    @override
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drag events for PDF files."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".pdf"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    @override
    def dropEvent(self, event: QDropEvent) -> None:
        """Handle dropped PDF files."""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(".pdf"):
                self.file_open_requested.emit(Path(file_path))
                break
