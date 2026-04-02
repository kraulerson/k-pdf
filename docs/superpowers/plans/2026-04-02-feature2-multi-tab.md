# Feature 2: Multi-Tab Document Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable multiple PDF documents open simultaneously in tabs, with independent per-tab state and tab lifecycle management.

**Architecture:** One `DocumentPresenter` per tab (each owning its own `PdfWorker` thread, `PageCache`, and `DocumentModel`). A new `TabManager` coordinates tab lifecycle — creation, switching, closing, duplicate detection. The view layer uses `QStackedWidget(WelcomeWidget, QTabWidget)` as the central widget.

**Tech Stack:** Python 3.13, PySide6 6.11, PyMuPDF 1.27, pytest + pytest-qt

**Spec:** `docs/superpowers/specs/2026-04-02-feature2-multi-tab-design.md`

---

## File Map

**New files:**
- `k_pdf/presenters/tab_manager.py` — `TabContext` dataclass + `TabManager` class
- `tests/test_tab_manager.py` — unit tests for TabManager
- `tests/test_tab_integration.py` — integration tests for multi-tab flows

**Modified files:**
- `k_pdf/views/pdf_viewport.py` — remove `WelcomeWidget`, remove welcome overlay from `PdfViewport`
- `k_pdf/views/main_window.py` — replace single viewport with `QStackedWidget(WelcomeWidget, QTabWidget)`, add Close Tab action, expose `tab_widget` property
- `k_pdf/app.py` — replace single `DocumentPresenter` with `TabManager`, rewire signals
- `k_pdf/views/tab_bar.py` — delete stub (functionality absorbed by QTabWidget in MainWindow)
- `pyproject.toml` — add mypy override for `tab_manager.py`
- `tests/test_views.py` — update tests broken by MainWindow/PdfViewport changes

---

### Task 1: Strip WelcomeWidget from PdfViewport

`PdfViewport` currently owns a `WelcomeWidget` overlay and a `show_welcome()` method. For multi-tab, the welcome screen lives at the `MainWindow` level (in the `QStackedWidget`), not inside individual viewports. This task makes `PdfViewport` a pure document renderer.

**Files:**
- Modify: `k_pdf/views/pdf_viewport.py`
- Modify: `tests/test_views.py`

- [ ] **Step 1: Write failing test — PdfViewport no longer has welcome_widget attribute**

In `tests/test_views.py`, add a new test to the `TestPdfViewport` class:

```python
def test_viewport_has_no_welcome_widget(self) -> None:
    """Test that PdfViewport does not have a welcome overlay."""
    viewport = PdfViewport()
    assert not hasattr(viewport, "welcome_widget")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest tests/test_views.py::TestPdfViewport::test_viewport_has_no_welcome_widget -v`

Expected: FAIL — `PdfViewport` currently has `welcome_widget` property.

- [ ] **Step 3: Remove WelcomeWidget from pdf_viewport.py**

In `k_pdf/views/pdf_viewport.py`:

1. Delete the entire `WelcomeWidget` class (lines 43-69).
2. In `PdfViewport.__init__`, remove these lines:

```python
        # Welcome widget overlay
        self._welcome = WelcomeWidget(self)
        self._welcome.show()
```

3. Remove the `welcome_widget` property (lines 103-106):

```python
    @property
    def welcome_widget(self) -> WelcomeWidget:
        """Return the welcome widget for external signal connections."""
        return self._welcome
```

4. In `set_loading`, `set_error`, `set_document` methods, remove `self._welcome.hide()` calls.

5. Delete the `show_welcome` method (lines 234-240):

```python
    def show_welcome(self) -> None:
        """Show the welcome screen (no document open)."""
        self._state = ViewportState.EMPTY
        self._scene.clear()
        self._page_items.clear()
        self._pages = []
        self._welcome.show()
```

6. Remove unused imports: `QPushButton`, `QVBoxLayout` (only used by `WelcomeWidget`). Keep `QLabel` only if still used elsewhere — it is not, so remove it too.

- [ ] **Step 4: Update existing tests that reference welcome_widget**

In `tests/test_views.py`, the `TestMainWindow.test_file_open_requested_signal` test does not reference welcome_widget directly, but `MainWindow.__init__` does via `self.viewport.welcome_widget.open_clicked.connect(...)`. That line will break. For now, temporarily comment out the welcome_widget line in `main_window.py` line 50 so tests can run:

```python
        # TODO(feature2): reconnect after WelcomeWidget moves to MainWindow
        # self.viewport.welcome_widget.open_clicked.connect(self._open_file_dialog)
```

- [ ] **Step 5: Run all tests to verify nothing is broken**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest -v`

Expected: All tests pass. The `test_initial_state_is_empty` test should still pass since it only checks `viewport.state`, not the welcome widget.

- [ ] **Step 6: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run ruff check . && uv run mypy k_pdf/`

Expected: Clean (no errors).

- [ ] **Step 7: Commit**

```bash
cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf"
git add k_pdf/views/pdf_viewport.py tests/test_views.py k_pdf/views/main_window.py
git commit -m "refactor(f2): strip WelcomeWidget from PdfViewport"
```

---

### Task 2: Rebuild MainWindow with QStackedWidget + QTabWidget

Replace the single `PdfViewport` central widget with a `QStackedWidget` that holds the `WelcomeWidget` (page 0) and a `QTabWidget` (page 1). Add Close Tab menu action and tab-related signals.

**Files:**
- Modify: `k_pdf/views/main_window.py`
- Modify: `tests/test_views.py`

- [ ] **Step 1: Write failing tests for new MainWindow structure**

In `tests/test_views.py`, replace the `TestMainWindow` class with:

```python
class TestMainWindow:
    """Tests for MainWindow with multi-tab support."""

    def test_initial_state_shows_welcome(self) -> None:
        """Test that MainWindow starts showing the welcome widget."""
        window = MainWindow()
        assert window.stacked_widget.currentIndex() == 0

    def test_tab_widget_is_configured(self) -> None:
        """Test QTabWidget has closable, movable, document-mode tabs."""
        window = MainWindow()
        tw = window.tab_widget
        assert tw.tabsClosable() is True
        assert tw.isMovable() is True
        assert tw.documentMode() is True

    def test_tab_close_requested_signal(self) -> None:
        """Test that tab_close_requested signal exists and is emittable."""
        window = MainWindow()
        spy = MagicMock()
        window.tab_close_requested.connect(spy)
        window.tab_close_requested.emit()
        spy.assert_called_once()

    def test_file_open_requested_signal(self) -> None:
        """Test that file_open_requested signal can be emitted and received."""
        window = MainWindow()
        spy = MagicMock()
        window.file_open_requested.connect(spy)
        window.file_open_requested.emit(Path("/tmp/test.pdf"))
        spy.assert_called_once_with(Path("/tmp/test.pdf"))

    def test_update_page_status(self) -> None:
        """Test status bar page label updates."""
        window = MainWindow()
        window.update_page_status(3, 10)
        assert window._page_label.text() == "Page 3 of 10"

    def test_welcome_open_button_emits_file_open(self) -> None:
        """Test that WelcomeWidget open button triggers file dialog flow."""
        window = MainWindow()
        # WelcomeWidget exists and has open_clicked signal
        assert hasattr(window._welcome, "open_clicked")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest tests/test_views.py::TestMainWindow -v`

Expected: FAIL — `MainWindow` doesn't have `stacked_widget`, `tab_widget`, or `tab_close_requested` yet.

- [ ] **Step 3: Rewrite MainWindow with QStackedWidget + QTabWidget**

Replace the contents of `k_pdf/views/main_window.py` with:

```python
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
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

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
        self.setCentralWidget(self._stacked)

        # Status bar
        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)
        self._page_label = QLabel("No document")
        self._zoom_label = QLabel("100%")
        self._status_bar.addPermanentWidget(self._page_label)
        self._status_bar.addPermanentWidget(self._zoom_label)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest tests/test_views.py -v`

Expected: All `TestMainWindow` and `TestPdfViewport` tests pass.

- [ ] **Step 5: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run ruff check . && uv run mypy k_pdf/`

Expected: Clean. If mypy complains about the new module, add an override to `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.views.main_window"]
disable_error_code = ["misc"]
```

(This override already exists in pyproject.toml line 84.)

- [ ] **Step 6: Commit**

```bash
cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf"
git add k_pdf/views/main_window.py tests/test_views.py
git commit -m "feat(f2): rebuild MainWindow with QStackedWidget + QTabWidget"
```

---

### Task 3: Create TabContext and TabManager skeleton

Create the `TabManager` class with `TabContext` dataclass. Implement `open_file()`, `close_tab()`, `activate_tab()`, and `shutdown()` methods. This task builds the core logic with tests.

**Files:**
- Create: `k_pdf/presenters/tab_manager.py`
- Create: `tests/test_tab_manager.py`
- Modify: `pyproject.toml` (mypy override)

- [ ] **Step 1: Write failing tests for TabManager**

Create `tests/test_tab_manager.py`:

```python
"""Tests for TabManager tab lifecycle."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QTabWidget

from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.presenters.tab_manager import TabContext, TabManager

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_model(file_path: Path) -> DocumentModel:
    """Create a minimal DocumentModel for testing."""
    metadata = DocumentMetadata(
        file_path=file_path,
        page_count=3,
        title=None,
        author=None,
        has_forms=False,
        has_outline=False,
        has_javascript=False,
        is_encrypted=False,
        file_size_bytes=1000,
    )
    pages = [
        PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
        for i in range(3)
    ]
    return DocumentModel(
        file_path=file_path,
        doc_handle=MagicMock(),
        metadata=metadata,
        pages=pages,
    )


class TestTabManagerOpenFile:
    """Tests for TabManager.open_file flow."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_open_file_creates_tab(self, mock_presenter_cls: MagicMock) -> None:
        """Test that open_file creates a TabContext and adds a tab."""
        mock_presenter = MagicMock()
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))

        assert tab_widget.count() == 1
        assert tab_widget.tabText(0) == "Loading..."
        assert len(manager._tabs) == 1
        mock_presenter.open_file.assert_called_once()

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_open_duplicate_activates_existing(self, mock_presenter_cls: MagicMock) -> None:
        """Test that opening an already-open file activates the existing tab."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        status_spy = MagicMock()
        manager.status_message.connect(status_spy)

        # Open a file and simulate document_ready to register the path
        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        manager._on_document_ready(session_id, model)

        # Try to open the same file again
        manager.open_file(Path("/tmp/test.pdf"))

        assert tab_widget.count() == 1
        assert len(manager._tabs) == 1
        status_spy.assert_called_with("This file is already open")


class TestTabManagerCloseTab:
    """Tests for TabManager.close_tab flow."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_close_tab_removes_tab(self, mock_presenter_cls: MagicMock) -> None:
        """Test that close_tab removes the tab and shuts down the presenter."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))

        manager.close_tab(session_id)

        assert tab_widget.count() == 0
        assert len(manager._tabs) == 0
        mock_presenter.shutdown.assert_called_once()

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_close_last_tab_emits_zero_count(self, mock_presenter_cls: MagicMock) -> None:
        """Test that closing the last tab emits tab_count_changed(0)."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        count_spy = MagicMock()
        manager.tab_count_changed.connect(count_spy)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        manager.close_tab(session_id)

        count_spy.assert_called_with(0)


class TestTabManagerDocumentReady:
    """Tests for TabManager._on_document_ready flow."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_document_ready_updates_title(self, mock_presenter_cls: MagicMock) -> None:
        """Test that document_ready updates the tab title to the filename."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        manager._on_document_ready(session_id, model)

        assert tab_widget.tabText(0) == "test.pdf"

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_document_ready_registers_path(self, mock_presenter_cls: MagicMock) -> None:
        """Test that document_ready registers the resolved path for duplicate detection."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        manager._on_document_ready(session_id, model)

        resolved = Path("/tmp/test.pdf").resolve()
        assert resolved in manager._open_paths

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_document_ready_adds_to_recent_files(self, mock_presenter_cls: MagicMock) -> None:
        """Test that document_ready adds the file to recent files."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        manager._on_document_ready(session_id, model)

        recent_files.add.assert_called_once_with(Path("/tmp/test.pdf"))

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_tab_title_dirty_prefix(self, mock_presenter_cls: MagicMock) -> None:
        """Test that dirty documents show * prefix in tab title."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        model.dirty = True
        manager._on_document_ready(session_id, model)

        assert tab_widget.tabText(0) == "* test.pdf"


class TestTabManagerActivate:
    """Tests for TabManager.activate_tab flow."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_activate_tab_switches_widget(self, mock_presenter_cls: MagicMock) -> None:
        """Test that activate_tab changes the QTabWidget current index."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/a.pdf"))
        manager.open_file(Path("/tmp/b.pdf"))

        session_ids = list(manager._tabs.keys())
        manager.activate_tab(session_ids[0])

        assert tab_widget.currentIndex() == 0


class TestTabManagerShutdown:
    """Tests for TabManager.shutdown flow."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_shutdown_cleans_all_tabs(self, mock_presenter_cls: MagicMock) -> None:
        """Test that shutdown calls presenter.shutdown() for all tabs."""
        presenters: list[MagicMock] = []

        def make_presenter() -> MagicMock:
            p = MagicMock()
            p.model = None
            presenters.append(p)
            return p

        mock_presenter_cls.side_effect = make_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/a.pdf"))
        manager.open_file(Path("/tmp/b.pdf"))
        manager.shutdown()

        for p in presenters:
            p.shutdown.assert_called_once()
        assert len(manager._tabs) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest tests/test_tab_manager.py -v`

Expected: FAIL — `k_pdf.presenters.tab_manager` does not exist.

- [ ] **Step 3: Implement TabContext and TabManager**

Create `k_pdf/presenters/tab_manager.py`:

```python
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
        """Close a tab and clean up its resources.

        Args:
            session_id: The session ID of the tab to close.
        """
        ctx = self._tabs.get(session_id)
        if ctx is None:
            return

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
```

- [ ] **Step 4: Add mypy override for tab_manager**

In `pyproject.toml`, update the existing mypy override for presenters to include tab_manager:

Add a new override block:

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.presenters.tab_manager"]
disable_error_code = ["misc"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest tests/test_tab_manager.py -v`

Expected: All 10 tests pass.

- [ ] **Step 6: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run ruff check . && uv run mypy k_pdf/`

Expected: Clean.

- [ ] **Step 7: Commit**

```bash
cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf"
git add k_pdf/presenters/tab_manager.py tests/test_tab_manager.py pyproject.toml
git commit -m "feat(f2): implement TabManager with tab lifecycle management"
```

---

### Task 4: Rewire KPdfApp to use TabManager

Replace the single `DocumentPresenter` in `KPdfApp` with `TabManager`. Wire signals between `MainWindow` and `TabManager`.

**Files:**
- Modify: `k_pdf/app.py`
- Modify: `tests/test_views.py` (add integration test)

- [ ] **Step 1: Write failing integration test**

Add to `tests/test_views.py`:

```python
from k_pdf.app import KPdfApp
from k_pdf.presenters.tab_manager import TabManager


class TestKPdfAppIntegration:
    """Tests for KPdfApp wiring with TabManager."""

    def test_app_creates_tab_manager(self) -> None:
        """Test that KPdfApp creates a TabManager instead of single presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert isinstance(kpdf.tab_manager, TabManager)
        kpdf.shutdown()

    def test_app_wires_file_open_to_tab_manager(self) -> None:
        """Test that file_open_requested routes to TabManager.open_file."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        spy = MagicMock()
        kpdf.tab_manager.open_file = spy  # type: ignore[method-assign]
        kpdf.window.file_open_requested.emit(Path("/tmp/test.pdf"))
        spy.assert_called_once_with(Path("/tmp/test.pdf"))
        kpdf.shutdown()

    def test_tab_count_zero_shows_welcome(self) -> None:
        """Test that tab_count_changed(0) switches to welcome screen."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        kpdf.window.show_tabs()
        assert kpdf.window.stacked_widget.currentIndex() == 1
        kpdf.tab_manager.tab_count_changed.emit(0)
        assert kpdf.window.stacked_widget.currentIndex() == 0
        kpdf.shutdown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest tests/test_views.py::TestKPdfAppIntegration -v`

Expected: FAIL — `KPdfApp` doesn't have `tab_manager` property yet.

- [ ] **Step 3: Rewrite KPdfApp to use TabManager**

Replace `k_pdf/app.py` with:

```python
"""QApplication shell and event bus initialization.

Creates the main window, tab manager, and wires signals together.
Handles CLI file arguments.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from k_pdf.persistence.recent_files import RecentFiles
from k_pdf.persistence.settings_db import init_db
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.views.main_window import MainWindow

logger = logging.getLogger("k_pdf.app")


class KPdfApp:
    """Application controller — wires TabManager to views."""

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
        self._tab_manager = TabManager(
            tab_widget=self._window.tab_widget,
            recent_files=self._recent_files,
        )
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
    def tab_manager(self) -> TabManager:
        """Return the tab manager."""
        return self._tab_manager

    def _connect_signals(self) -> None:
        """Wire MainWindow signals to TabManager and vice versa."""
        # View → TabManager
        self._window.file_open_requested.connect(self._tab_manager.open_file)
        self._window.tab_close_requested.connect(self._on_close_current_tab)
        self._window.password_submitted.connect(self._on_password_submitted)

        # TabManager → View
        self._tab_manager.error_occurred.connect(self._window.show_error)
        self._tab_manager.password_requested.connect(self._window.show_password_dialog)
        self._tab_manager.status_message.connect(self._window.update_status_message)
        self._tab_manager.active_page_status.connect(self._window.update_page_status)
        self._tab_manager.tab_count_changed.connect(self._on_tab_count_changed)

    def _on_tab_count_changed(self, count: int) -> None:
        """Toggle between welcome screen and tab view."""
        if count == 0:
            self._window.show_welcome()
        else:
            self._window.show_tabs()

    def _on_close_current_tab(self) -> None:
        """Close the currently active tab."""
        sid = self._tab_manager.active_session_id
        if sid is not None:
            self._tab_manager.close_tab(sid)

    def _on_password_submitted(self, path: Path, password: str) -> None:
        """Forward password to the active tab's presenter."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.open_file_with_password(path, password)

    def _open_initial_file(self) -> None:
        """Open the file passed via CLI argument."""
        if self._initial_file:
            self._tab_manager.open_file(Path(self._initial_file))

    def shutdown(self) -> None:
        """Clean up resources before exit."""
        self._tab_manager.shutdown()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest tests/test_views.py -v`

Expected: All tests pass including the new integration tests.

- [ ] **Step 5: Run full test suite**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest -v`

Expected: All 43+ tests pass. Some existing tests in `test_document_presenter.py` may need the `presenter` property removed or adjusted — they test `DocumentPresenter` directly and should still work.

- [ ] **Step 6: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run ruff check . && uv run mypy k_pdf/`

Expected: Clean.

- [ ] **Step 7: Commit**

```bash
cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf"
git add k_pdf/app.py tests/test_views.py
git commit -m "feat(f2): rewire KPdfApp to use TabManager"
```

---

### Task 5: Handle load failure and password cancel (empty tab cleanup)

When a file fails to load or the user cancels the password dialog, the empty "Loading..." tab must be removed automatically.

**Files:**
- Create: `tests/test_tab_manager.py` (add tests)
- Verify: `k_pdf/presenters/tab_manager.py` (already handles this in `_on_error`)

- [ ] **Step 1: Write failing tests for error cleanup**

Add to the existing `tests/test_tab_manager.py`:

```python
class TestTabManagerErrorHandling:
    """Tests for TabManager error and password flows."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_load_failure_removes_tab(self, mock_presenter_cls: MagicMock) -> None:
        """Test that a load error removes the empty Loading... tab."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        error_spy = MagicMock()
        manager.error_occurred.connect(error_spy)

        manager.open_file(Path("/tmp/bad.pdf"))
        session_id = next(iter(manager._tabs))

        # Simulate load failure (resolved_path is still None)
        manager._on_error(session_id, "Cannot open file", "File is corrupt")

        assert tab_widget.count() == 0
        assert len(manager._tabs) == 0
        error_spy.assert_called_once_with("Cannot open file", "File is corrupt")

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_error_after_load_does_not_remove_tab(self, mock_presenter_cls: MagicMock) -> None:
        """Test that an error after successful load does NOT remove the tab."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        manager._on_document_ready(session_id, model)

        # Error after load (e.g., save failure) — tab should stay
        manager._on_error(session_id, "Save error", "Cannot save")

        assert tab_widget.count() == 1
        assert len(manager._tabs) == 1
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest tests/test_tab_manager.py::TestTabManagerErrorHandling -v`

Expected: PASS — the logic is already implemented in `_on_error` (checks `resolved_path is None` to decide whether to remove the tab).

- [ ] **Step 3: Commit**

```bash
cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf"
git add tests/test_tab_manager.py
git commit -m "test(f2): add error handling tests for TabManager"
```

---

### Task 6: Delete tab_bar.py stub

The existing `k_pdf/views/tab_bar.py` is a one-line stub (`"""Multi-tab document bar."""`). Its functionality is now handled by `QTabWidget` in `MainWindow`. Remove it.

**Files:**
- Delete: `k_pdf/views/tab_bar.py`

- [ ] **Step 1: Verify no imports reference tab_bar**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run ruff check . && grep -r "tab_bar" k_pdf/ tests/ --include="*.py" | grep -v __pycache__ | grep -v ".pyc"`

Expected: No imports found (only the file itself).

- [ ] **Step 2: Delete the stub file**

```bash
cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf"
rm k_pdf/views/tab_bar.py
```

- [ ] **Step 3: Run full test suite**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest -v`

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf"
git add -A k_pdf/views/tab_bar.py
git commit -m "chore(f2): remove tab_bar.py stub, replaced by QTabWidget in MainWindow"
```

---

### Task 7: Integration tests with real PDFs

End-to-end tests that open real PDF fixtures through `TabManager`, verify multi-tab behavior.

**Files:**
- Create: `tests/test_tab_integration.py`

- [ ] **Step 1: Write integration tests**

Create `tests/test_tab_integration.py`:

```python
"""Integration tests for multi-tab document flows."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QTabWidget

from k_pdf.app import KPdfApp
from k_pdf.presenters.tab_manager import TabManager

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestMultiTabIntegration:
    """Integration tests for multi-tab flows with real PDFs."""

    def test_open_two_files_two_tabs(self, valid_pdf: Path, tmp_path: Path, qtbot: object) -> None:
        """Test opening two different PDFs creates two tabs."""
        import pymupdf

        # Create a second PDF
        path2 = tmp_path / "second.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), "Second doc")
        doc.save(str(path2))
        doc.close()

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        tm = kpdf.tab_manager
        tw = kpdf.window.tab_widget

        # Open first file
        tm.open_file(valid_pdf)

        def check_first_tab() -> None:
            assert tw.count() == 1
            assert tw.tabText(0) != "Loading..."

        qtbot.waitUntil(check_first_tab, timeout=5000)
        assert tw.tabText(0) == valid_pdf.name

        # Open second file
        tm.open_file(path2)

        def check_second_tab() -> None:
            assert tw.count() == 2
            assert tw.tabText(1) != "Loading..."

        qtbot.waitUntil(check_second_tab, timeout=5000)
        assert tw.tabText(1) == "second.pdf"

        kpdf.shutdown()

    def test_close_tab_shows_welcome(self, valid_pdf: Path, qtbot: object) -> None:
        """Test that closing the only tab shows the welcome screen."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        tm = kpdf.tab_manager
        tw = kpdf.window.tab_widget

        # Open a file
        tm.open_file(valid_pdf)

        def check_loaded() -> None:
            assert tw.count() == 1
            assert tw.tabText(0) != "Loading..."

        qtbot.waitUntil(check_loaded, timeout=5000)

        # Stacked widget should be on tabs page
        assert kpdf.window.stacked_widget.currentIndex() == 1

        # Close the tab
        session_id = next(iter(tm._tabs))
        tm.close_tab(session_id)

        # Should be back to welcome
        assert tw.count() == 0
        assert kpdf.window.stacked_widget.currentIndex() == 0

        kpdf.shutdown()

    def test_switch_tab_preserves_state(
        self, valid_pdf: Path, tmp_path: Path, qtbot: object
    ) -> None:
        """Test that switching tabs preserves each tab's viewport state."""
        import pymupdf

        # Create a second PDF with different page count
        path2 = tmp_path / "five_pages.pdf"
        doc = pymupdf.open()
        for i in range(5):
            page = doc.new_page(width=612, height=792)
            page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1}")
        doc.save(str(path2))
        doc.close()

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        tm = kpdf.tab_manager
        tw = kpdf.window.tab_widget

        # Open both files
        tm.open_file(valid_pdf)

        def check_first() -> None:
            assert tw.count() == 1
            assert tw.tabText(0) != "Loading..."

        qtbot.waitUntil(check_first, timeout=5000)

        tm.open_file(path2)

        def check_second() -> None:
            assert tw.count() == 2
            assert tw.tabText(1) != "Loading..."

        qtbot.waitUntil(check_second, timeout=5000)

        # Get session IDs
        sids = list(tm._tabs.keys())
        ctx0 = tm._tabs[sids[0]]
        ctx1 = tm._tabs[sids[1]]

        # Each viewport has its own pages
        assert ctx0.viewport is not None
        assert ctx1.viewport is not None
        assert len(ctx0.viewport._pages) == 3  # valid_pdf has 3 pages
        assert len(ctx1.viewport._pages) == 5  # five_pages.pdf has 5 pages

        # Switch to first tab
        tm.activate_tab(sids[0])
        assert tw.currentIndex() == 0

        # Pages are still correct after switch
        assert len(ctx0.viewport._pages) == 3
        assert len(ctx1.viewport._pages) == 5

        kpdf.shutdown()
```

- [ ] **Step 2: Run integration tests**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest tests/test_tab_integration.py -v`

Expected: All 3 tests pass.

- [ ] **Step 3: Run full test suite and coverage**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest --cov=k_pdf --cov-report=term-missing`

Expected: All tests pass. Coverage at or above 65%.

- [ ] **Step 4: Run all linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run ruff check . && uv run mypy k_pdf/`

Expected: Clean.

- [ ] **Step 5: Commit**

```bash
cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf"
git add tests/test_tab_integration.py
git commit -m "test(f2): add multi-tab integration tests with real PDFs"
```

---

### Task 8: Update CLAUDE.md and verify final state

Update the project's current state documentation and run final verification.

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Run full test suite with coverage**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest --cov=k_pdf --cov-report=term-missing`

Expected: All tests pass, coverage >= 65%.

- [ ] **Step 2: Run all linters and security checks**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run ruff check . && uv run ruff format --check . && uv run mypy k_pdf/ && gitleaks detect --source .`

Expected: All clean.

- [ ] **Step 3: Update CLAUDE.md current state**

In `CLAUDE.md`, update the "Current State" section:

```markdown
## Current State
- **Project:** K-PDF
- **Phase:** 2 (Construction)
- **Track:** Standard
- **Features built:** Feature 1 (Open and Render PDF), Feature 2 (Multi-Tab Document Support)
- **Features remaining:** Features 3-12 + 7 implicit (see MVP Cutline)
- **Known issues:** Coverage at [X]% (threshold 65%)
- **Last session summary:** Feature 2 complete — TabManager, QTabWidget-based multi-tab, per-tab presenter/viewport/thread, duplicate detection, [N] tests passing
```

Replace `[X]` and `[N]` with actual values from the test run.

- [ ] **Step 4: Commit**

```bash
cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf"
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md current state — Feature 2 complete"
```
