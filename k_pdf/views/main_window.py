"""Main application window.

Three-panel layout (navigation | viewport | annotations) with
menu bar, toolbar, status bar, and tab bar. Uses QStackedWidget
to switch between welcome screen (no tabs) and QTabWidget (tabs open).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from k_pdf.views.navigation_panel import NavigationPanel
from k_pdf.views.search_bar import SearchBar
from k_pdf.views.zoom_toolbar import ZoomToolBar

logger = logging.getLogger("k_pdf.views.main_window")


class WelcomeWidget(QWidget):
    """Welcome screen shown when no document is open."""

    open_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the welcome widget with title, subtitle, and open button."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("K-PDF")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(24)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        subtitle = QLabel("Free, offline PDF reader and editor")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        open_btn = QPushButton("Open File")
        open_btn.setFixedWidth(200)
        open_btn.clicked.connect(self.open_clicked.emit)
        layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)


class MainWindow(QMainWindow):
    """K-PDF main application window."""

    file_open_requested = Signal(Path)
    password_submitted = Signal(Path, str)  # (path, password)
    tab_close_requested = Signal()
    zoom_in_triggered = Signal()
    zoom_out_triggered = Signal()
    zoom_reset_triggered = Signal()
    rotate_cw_triggered = Signal()
    rotate_ccw_triggered = Signal()
    text_selection_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the main window with stacked widget, menus, and status bar."""
        super().__init__(parent)
        self.setWindowTitle("K-PDF")
        self.setMinimumSize(800, 600)
        self.resize(1200, 800)
        self.setAcceptDrops(True)

        # Welcome widget
        self._welcome = WelcomeWidget(self)
        self._welcome.open_clicked.connect(self._open_file_dialog)

        # Tab widget
        self._tab_widget = QTabWidget(self)
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.setMovable(True)
        self._tab_widget.setDocumentMode(True)
        self._tab_widget.setElideMode(Qt.TextElideMode.ElideRight)
        self._tab_widget.setStyleSheet(
            "QTabBar::tab:selected { border-bottom: 2px solid palette(text); }"
        )

        # Stacked widget: page 0 = welcome, page 1 = tabs
        self._stacked = QStackedWidget(self)
        self._stacked.addWidget(self._welcome)
        self._stacked.addWidget(self._tab_widget)
        self._stacked.setCurrentIndex(0)

        # Search bar (above viewport area)
        self._search_bar = SearchBar(self)
        self._search_bar.closed.connect(self._hide_search_bar)

        # Central container: search bar + stacked widget
        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._search_bar)
        central_layout.addWidget(self._stacked)
        self.setCentralWidget(central)

        # Navigation panel (left dock)
        self._nav_panel = NavigationPanel(self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._nav_panel)
        self._nav_panel.hide()

        # Status bar
        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)
        self._page_label = QLabel("No document")
        self._zoom_label = QLabel("100%")
        self._status_bar.addPermanentWidget(self._page_label)
        self._status_bar.addPermanentWidget(self._zoom_label)

        # Zoom toolbar
        self._zoom_toolbar = ZoomToolBar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._zoom_toolbar)

        # Menus
        self._setup_menus()

    @property
    def stacked_widget(self) -> QStackedWidget:
        """Return the stacked widget for external state control."""
        return self._stacked

    @property
    def tab_widget(self) -> QTabWidget:
        """Return the tab widget for TabManager to add/remove viewports."""
        return self._tab_widget

    @property
    def navigation_panel(self) -> NavigationPanel:
        """Return the navigation panel dock widget."""
        return self._nav_panel

    @property
    def search_bar(self) -> SearchBar:
        """Return the search bar widget."""
        return self._search_bar

    @property
    def zoom_toolbar(self) -> ZoomToolBar:
        """Return the zoom toolbar widget."""
        return self._zoom_toolbar

    @property
    def tools_menu(self) -> QMenu:
        """Return the Tools menu."""
        return self._tools_menu

    def _setup_menus(self) -> None:
        """Create the menu bar with File > Open, Close Tab, and Quit."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        close_tab_action = QAction("Close &Tab", self)
        close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        close_tab_action.triggered.connect(self.tab_close_requested.emit)
        file_menu.addAction(close_tab_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menu_bar.addMenu("&Edit")

        find_action = QAction("&Find...", self)
        find_action.setShortcut(QKeySequence("Ctrl+F"))
        find_action.triggered.connect(self._show_search_bar)
        edit_menu.addAction(find_action)

        # View menu
        view_menu = menu_bar.addMenu("&View")

        toggle_nav = self._nav_panel.toggleViewAction()
        toggle_nav.setText("Navigation &Panel")
        toggle_nav.setShortcut(QKeySequence("F5"))
        view_menu.addAction(toggle_nav)

        view_menu.addSeparator()

        rotate_cw_action = QAction("Rotate &Clockwise", self)
        rotate_cw_action.setShortcut(QKeySequence("Ctrl+R"))
        rotate_cw_action.setToolTip("Rotate page 90 degrees clockwise")
        rotate_cw_action.triggered.connect(self.rotate_cw_triggered.emit)
        view_menu.addAction(rotate_cw_action)

        rotate_ccw_action = QAction("Rotate C&ounter-Clockwise", self)
        rotate_ccw_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        rotate_ccw_action.setToolTip("Rotate page 90 degrees counter-clockwise")
        rotate_ccw_action.triggered.connect(self.rotate_ccw_triggered.emit)
        view_menu.addAction(rotate_ccw_action)

        view_menu.addSeparator()

        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut(QKeySequence("Ctrl+="))
        zoom_in_action.setToolTip("Zoom in")
        zoom_in_action.triggered.connect(self.zoom_in_triggered.emit)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.setToolTip("Zoom out")
        zoom_out_action.triggered.connect(self.zoom_out_triggered.emit)
        view_menu.addAction(zoom_out_action)

        zoom_reset_action = QAction("&Reset Zoom", self)
        zoom_reset_action.setShortcut(QKeySequence("Ctrl+0"))
        zoom_reset_action.setToolTip("Reset zoom to 100%")
        zoom_reset_action.triggered.connect(self.zoom_reset_triggered.emit)
        view_menu.addAction(zoom_reset_action)

        # Tools menu
        self._tools_menu = menu_bar.addMenu("&Tools")

        text_select_action = QAction("&Text Selection Mode", self)
        text_select_action.setShortcut(QKeySequence("Ctrl+T"))
        text_select_action.setCheckable(True)
        text_select_action.setToolTip("Toggle text selection for annotations")
        text_select_action.toggled.connect(self.text_selection_toggled.emit)
        self._tools_menu.addAction(text_select_action)

    def _show_search_bar(self) -> None:
        """Show the search bar and focus the input field."""
        self._search_bar.show()
        self._search_bar.focus_input()

    def _hide_search_bar(self) -> None:
        """Hide the search bar."""
        self._search_bar.hide()

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

    def show_tabs(self) -> None:
        """Switch stacked widget to show the tab widget."""
        self._stacked.setCurrentIndex(1)

    def show_welcome(self) -> None:
        """Switch stacked widget to show the welcome screen."""
        self._stacked.setCurrentIndex(0)
        self._page_label.setText("No document")

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
