# Feature 3: Page Navigation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapsible left navigation panel with page thumbnails and document outline/bookmarks, synchronized with the active tab's viewport.

**Architecture:** QDockWidget-based NavigationPanel with Thumbnails (QListWidget) and Outline (QTreeWidget) tabs. NavigationPresenter coordinates between TabManager signals and the panel. ThumbnailCache pre-renders all page thumbnails on a dedicated QThread per document. OutlineService parses PyMuPDF's TOC into OutlineNode domain objects.

**Tech Stack:** Python 3.13, PySide6 6.11, PyMuPDF 1.27, pytest + pytest-qt

**Spec:** `docs/superpowers/specs/2026-04-02-feature3-page-navigation-design.md`

---

## File Map

**New files:**
- `k_pdf/core/outline_model.py` — `OutlineNode` frozen dataclass
- `k_pdf/services/outline_service.py` — parses `doc.get_toc()` into `OutlineNode` tree
- `k_pdf/core/thumbnail_cache.py` — `ThumbnailCache`, pre-renders page thumbnails on QThread
- `k_pdf/presenters/navigation_presenter.py` — coordinates TabManager ↔ NavigationPanel
- `k_pdf/views/navigation_panel.py` — QDockWidget with Thumbnails + Outline tabs (replaces stub)

**New test files:**
- `tests/test_outline_model.py`
- `tests/test_outline_service.py`
- `tests/test_thumbnail_cache.py`
- `tests/test_navigation_presenter.py`
- `tests/test_navigation_panel.py`
- `tests/test_navigation_integration.py`

**Modified files:**
- `k_pdf/presenters/tab_manager.py` — add `tab_switched(str)`, `tab_closed(str)` signals, `get_active_viewport()` method
- `k_pdf/views/pdf_viewport.py` — add `current_page_changed(int)` signal, `scroll_to_page()` method
- `k_pdf/views/main_window.py` — add NavigationPanel dock widget, View menu F5 toggle
- `k_pdf/app.py` — create NavigationPresenter, wire signals
- `pyproject.toml` — mypy overrides for new modules
- `tests/conftest.py` — add bookmark PDF fixture

---

### Task 1: OutlineNode dataclass

**Files:**
- Create: `k_pdf/core/outline_model.py`
- Create: `tests/test_outline_model.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_outline_model.py`:

```python
"""Tests for OutlineNode dataclass."""

from __future__ import annotations

from k_pdf.core.outline_model import OutlineNode


def test_outline_node_construction() -> None:
    node = OutlineNode(title="Chapter 1", page=0, children=[])
    assert node.title == "Chapter 1"
    assert node.page == 0
    assert node.children == []


def test_outline_node_with_children() -> None:
    child = OutlineNode(title="Section 1.1", page=2, children=[])
    parent = OutlineNode(title="Chapter 1", page=0, children=[child])
    assert len(parent.children) == 1
    assert parent.children[0].title == "Section 1.1"


def test_outline_node_is_frozen() -> None:
    node = OutlineNode(title="Test", page=0, children=[])
    try:
        node.title = "Changed"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_outline_node_invalid_page() -> None:
    node = OutlineNode(title="Bad Link", page=-1, children=[])
    assert node.page == -1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_outline_model.py -v`

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement OutlineNode**

Create `k_pdf/core/outline_model.py`:

```python
"""Outline/bookmark tree model.

OutlineNode is a pure data structure — no Qt or PyMuPDF imports.
Used by OutlineService (services/) and NavigationPanel (views/).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OutlineNode:
    """A single node in the document outline/bookmark tree."""

    title: str
    page: int  # 0-based page index, -1 if invalid
    children: list[OutlineNode] = field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_outline_model.py -v`

Expected: All 4 pass.

- [ ] **Step 5: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run ruff check . && uv run mypy k_pdf/core/outline_model.py`

- [ ] **Step 6: Commit**

```bash
git add k_pdf/core/outline_model.py tests/test_outline_model.py
git commit -m "feat(f3): add OutlineNode dataclass"
```

---

### Task 2: OutlineService

**Files:**
- Create: `k_pdf/services/outline_service.py`
- Create: `tests/test_outline_service.py`
- Modify: `tests/conftest.py` (add bookmark fixture)

- [ ] **Step 1: Add bookmark PDF fixture**

In `tests/conftest.py`, add:

```python
@pytest.fixture
def pdf_with_outline(tmp_path: Path) -> Path:
    """Create a PDF with a table of contents / bookmarks."""
    path = tmp_path / "with_outline.pdf"
    doc = pymupdf.open()
    for i in range(5):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Chapter {i + 1}")
    toc = [
        [1, "Chapter 1", 1],
        [2, "Section 1.1", 1],
        [2, "Section 1.2", 2],
        [1, "Chapter 2", 3],
        [1, "Chapter 3", 5],
    ]
    doc.set_toc(toc)
    doc.save(str(path))
    doc.close()
    return path
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_outline_service.py`:

```python
"""Tests for OutlineService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pymupdf

from k_pdf.core.outline_model import OutlineNode
from k_pdf.services.outline_service import get_outline


def test_parse_flat_toc_into_tree(pdf_with_outline: Path) -> None:
    doc = pymupdf.open(str(pdf_with_outline))
    nodes = get_outline(doc)
    doc.close()

    assert len(nodes) == 3  # 3 top-level chapters
    assert nodes[0].title == "Chapter 1"
    assert nodes[0].page == 0  # 1-based page 1 → 0-based 0
    assert len(nodes[0].children) == 2
    assert nodes[0].children[0].title == "Section 1.1"
    assert nodes[0].children[1].title == "Section 1.2"
    assert nodes[1].title == "Chapter 2"
    assert nodes[1].page == 2
    assert nodes[2].title == "Chapter 3"
    assert nodes[2].page == 4


def test_empty_outline(valid_pdf: Path) -> None:
    doc = pymupdf.open(str(valid_pdf))
    nodes = get_outline(doc)
    doc.close()
    assert nodes == []


def test_invalid_page_gets_negative_one() -> None:
    doc = MagicMock()
    doc.get_toc.return_value = [[1, "Bad Link", 999]]
    doc.page_count = 5
    nodes = get_outline(doc)
    assert len(nodes) == 1
    assert nodes[0].page == -1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_outline_service.py -v`

Expected: FAIL — module does not exist.

- [ ] **Step 4: Implement OutlineService**

Create `k_pdf/services/outline_service.py`:

```python
"""Outline parsing service — transforms PyMuPDF TOC into OutlineNode tree.

PyMuPDF import is isolated here per AGPL containment rule.
"""

from __future__ import annotations

from typing import Any

from k_pdf.core.outline_model import OutlineNode


def get_outline(doc_handle: Any) -> list[OutlineNode]:
    """Parse a document's table of contents into an OutlineNode tree.

    Args:
        doc_handle: A pymupdf.Document handle.

    Returns:
        List of top-level OutlineNode objects. Empty list if no outline.
    """
    try:
        toc = doc_handle.get_toc()
    except Exception:
        return []

    if not toc:
        return []

    page_count: int = doc_handle.page_count
    root: list[OutlineNode] = []
    stack: list[tuple[int, list[OutlineNode]]] = [(0, root)]

    for entry in toc:
        level: int = entry[0]
        title: str = str(entry[1])
        page_1based: int = int(entry[2])

        # Convert to 0-based, mark invalid as -1
        page_0based = page_1based - 1
        if page_0based < 0 or page_0based >= page_count:
            page_0based = -1

        node = OutlineNode(title=title, page=page_0based, children=[])

        # Find the right parent level
        while len(stack) > 1 and stack[-1][0] >= level:
            stack.pop()

        stack[-1][1].append(node)
        stack.append((level, node.children))

    return root
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_outline_service.py -v`

Expected: All 3 pass.

- [ ] **Step 6: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run ruff check . && uv run mypy k_pdf/services/outline_service.py`

- [ ] **Step 7: Commit**

```bash
git add k_pdf/services/outline_service.py tests/test_outline_service.py tests/conftest.py
git commit -m "feat(f3): implement OutlineService for bookmark parsing"
```

---

### Task 3: Add scroll_to_page and current_page_changed to PdfViewport

**Files:**
- Modify: `k_pdf/views/pdf_viewport.py`
- Modify: `tests/test_views.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_views.py` in `TestPdfViewport`:

```python
    def test_scroll_to_page_exists(self) -> None:
        """Test that scroll_to_page method exists."""
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
            PageInfo(index=1, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
            PageInfo(index=2, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        # Should not raise
        viewport.scroll_to_page(1)

    def test_current_page_changed_signal_exists(self) -> None:
        """Test that current_page_changed signal exists."""
        viewport = PdfViewport()
        spy = MagicMock()
        viewport.current_page_changed.connect(spy)
        # Signal exists and is connectable
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_views.py::TestPdfViewport::test_scroll_to_page_exists tests/test_views.py::TestPdfViewport::test_current_page_changed_signal_exists -v`

Expected: FAIL — methods/signals don't exist.

- [ ] **Step 3: Add current_page_changed signal and scroll_to_page to PdfViewport**

In `k_pdf/views/pdf_viewport.py`, add a second signal to the class:

```python
class PdfViewport(QGraphicsView):
    visible_pages_changed = Signal(list)
    current_page_changed = Signal(int)  # NEW: topmost visible page index
```

Add instance variable in `__init__`:

```python
        self._current_page: int = -1
```

Add `scroll_to_page` method after `set_page_error`:

```python
    def scroll_to_page(self, page_index: int) -> None:
        """Scroll the viewport to show the specified page at the top.

        Args:
            page_index: 0-based page index to scroll to.
        """
        if page_index < 0 or page_index >= len(self._page_y_offsets):
            return
        y = self._page_y_offsets[page_index]
        self.verticalScrollBar().setValue(int(y))
```

Modify `_emit_visible_pages` to emit `current_page_changed`:

```python
    def _emit_visible_pages(self) -> None:
        """Calculate and emit the list of visible page indices."""
        first, last = self.get_visible_page_range()
        if first >= 0:
            self.visible_pages_changed.emit(list(range(first, last + 1)))
            if first != self._current_page:
                self._current_page = first
                self.current_page_changed.emit(first)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_views.py -v`

Expected: All pass.

- [ ] **Step 5: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run ruff check . && uv run mypy k_pdf/views/pdf_viewport.py`

- [ ] **Step 6: Commit**

```bash
git add k_pdf/views/pdf_viewport.py tests/test_views.py
git commit -m "feat(f3): add scroll_to_page and current_page_changed to PdfViewport"
```

---

### Task 4: Add tab_switched, tab_closed signals and get_active_viewport to TabManager

**Files:**
- Modify: `k_pdf/presenters/tab_manager.py`
- Modify: `tests/test_tab_manager.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tab_manager.py`:

```python
class TestTabManagerSignals:
    """Tests for TabManager tab_switched and tab_closed signals."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_tab_switched_emits_session_id(self, mock_presenter_cls: MagicMock) -> None:
        """Test that switching tabs emits tab_switched with session_id."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        switched_spy = MagicMock()
        manager.tab_switched.connect(switched_spy)

        manager.open_file(Path("/tmp/a.pdf"))
        manager.open_file(Path("/tmp/b.pdf"))

        sids = list(manager._tabs.keys())
        tab_widget.setCurrentIndex(0)

        switched_spy.assert_called_with(sids[0])

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_tab_closed_emits_session_id(self, mock_presenter_cls: MagicMock) -> None:
        """Test that closing a tab emits tab_closed with session_id."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        closed_spy = MagicMock()
        manager.tab_closed.connect(closed_spy)

        manager.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(manager._tabs))
        manager.close_tab(sid)

        closed_spy.assert_called_once_with(sid)

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_get_active_viewport_returns_viewport(self, mock_presenter_cls: MagicMock) -> None:
        """Test get_active_viewport returns the active tab's PdfViewport."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        viewport = manager.get_active_viewport()

        assert viewport is not None
        from k_pdf.views.pdf_viewport import PdfViewport
        assert isinstance(viewport, PdfViewport)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_tab_manager.py::TestTabManagerSignals -v`

Expected: FAIL — `tab_switched`, `tab_closed`, `get_active_viewport` don't exist.

- [ ] **Step 3: Add signals and method to TabManager**

In `k_pdf/presenters/tab_manager.py`, add two new signals to the class:

```python
    # Signals
    document_ready = Signal(str, object)
    error_occurred = Signal(str, str)
    password_requested = Signal(object)
    tab_count_changed = Signal(int)
    status_message = Signal(str)
    active_page_status = Signal(int, int)
    tab_switched = Signal(str)  # NEW: session_id
    tab_closed = Signal(str)  # NEW: session_id
```

Add `get_active_viewport` method after `get_active_presenter`:

```python
    def get_active_viewport(self) -> PdfViewport | None:
        """Return the active tab's viewport, or None."""
        if self._active_session_id is None:
            return None
        ctx = self._tabs.get(self._active_session_id)
        if ctx is None:
            return None
        return ctx.viewport
```

In `_on_tab_switched`, emit `tab_switched` after setting `_active_session_id`:

```python
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
```

In `close_tab`, emit `tab_closed` before removing from `_tabs`:

```python
    def close_tab(self, session_id: str) -> None:
        ctx = self._tabs.get(session_id)
        if ctx is None:
            return

        self.tab_closed.emit(session_id)  # NEW: emit before cleanup

        # Shut down presenter...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_tab_manager.py -v`

Expected: All pass.

- [ ] **Step 5: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run ruff check . && uv run mypy k_pdf/presenters/tab_manager.py`

- [ ] **Step 6: Commit**

```bash
git add k_pdf/presenters/tab_manager.py tests/test_tab_manager.py
git commit -m "feat(f3): add tab_switched, tab_closed signals and get_active_viewport to TabManager"
```

---

### Task 5: ThumbnailCache

**Files:**
- Create: `k_pdf/core/thumbnail_cache.py`
- Create: `tests/test_thumbnail_cache.py`
- Modify: `pyproject.toml` (mypy override)

- [ ] **Step 1: Write failing tests**

Create `tests/test_thumbnail_cache.py`:

```python
"""Tests for ThumbnailCache."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from k_pdf.core.document_model import PageInfo
from k_pdf.core.thumbnail_cache import ThumbnailCache

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def test_pre_renders_all_pages(valid_pdf: Path, qtbot: object) -> None:
    doc = pymupdf.open(str(valid_pdf))
    pages = [
        PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
        for i in range(doc.page_count)
    ]
    cache = ThumbnailCache(doc_handle=doc, pages=pages, thumb_width=90)
    ready_spy = MagicMock()
    cache.all_thumbnails_ready.connect(ready_spy)

    cache.start()

    def check_done() -> None:
        assert ready_spy.call_count == 1

    qtbot.waitUntil(check_done, timeout=10000)

    for i in range(3):
        thumb = cache.get(i)
        assert thumb is not None
        assert isinstance(thumb, QPixmap)
        assert thumb.width() > 0

    cache.shutdown()
    doc.close()


def test_get_returns_none_before_render() -> None:
    doc = MagicMock()
    pages = [
        PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0),
    ]
    cache = ThumbnailCache(doc_handle=doc, pages=pages, thumb_width=90)
    assert cache.get(0) is None


def test_thumbnail_ready_signal(valid_pdf: Path, qtbot: object) -> None:
    doc = pymupdf.open(str(valid_pdf))
    pages = [
        PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
        for i in range(doc.page_count)
    ]
    cache = ThumbnailCache(doc_handle=doc, pages=pages, thumb_width=90)
    ready_spy = MagicMock()
    cache.thumbnail_ready.connect(ready_spy)

    cache.start()

    def check_all() -> None:
        assert ready_spy.call_count == 3

    qtbot.waitUntil(check_all, timeout=10000)

    cache.shutdown()
    doc.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_thumbnail_cache.py -v`

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement ThumbnailCache**

Create `k_pdf/core/thumbnail_cache.py`:

```python
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
                image = self._engine.render_page(
                    doc_handle, page_info.index, zoom=zoom, rotation=0
                )
                self.thumbnail_rendered.emit(page_info.index, image)
            except Exception:
                logger.warning(
                    "Failed to render thumbnail for page %d", page_info.index, exc_info=True
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
```

- [ ] **Step 4: Add mypy override**

In `pyproject.toml`, add:

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.core.thumbnail_cache"]
disable_error_code = ["misc"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_thumbnail_cache.py -v`

Expected: All 3 pass.

- [ ] **Step 6: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run ruff check . && uv run mypy k_pdf/core/thumbnail_cache.py`

- [ ] **Step 7: Commit**

```bash
git add k_pdf/core/thumbnail_cache.py tests/test_thumbnail_cache.py pyproject.toml
git commit -m "feat(f3): implement ThumbnailCache with background pre-rendering"
```

---

### Task 6: NavigationPanel view

**Files:**
- Modify: `k_pdf/views/navigation_panel.py` (replace stub)
- Create: `tests/test_navigation_panel.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_navigation_panel.py`:

```python
"""Tests for NavigationPanel view."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from k_pdf.core.outline_model import OutlineNode
from k_pdf.views.navigation_panel import NavigationPanel

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def test_panel_has_two_tabs() -> None:
    panel = NavigationPanel()
    assert panel.tab_widget.count() == 2
    assert panel.tab_widget.tabText(0) == "Thumbnails"
    assert panel.tab_widget.tabText(1) == "Outline"


def test_thumbnail_clicked_signal() -> None:
    panel = NavigationPanel()
    spy = MagicMock()
    panel.thumbnail_clicked.connect(spy)

    img = QImage(90, 120, QImage.Format.Format_RGB888)
    img.fill(0)
    panel.add_thumbnail(0, QPixmap.fromImage(img))

    # Simulate click on first item
    panel._thumbnail_list.setCurrentRow(0)
    spy.assert_called_once_with(0)


def test_outline_clicked_signal() -> None:
    panel = NavigationPanel()
    spy = MagicMock()
    panel.outline_clicked.connect(spy)

    nodes = [OutlineNode(title="Chapter 1", page=0, children=[])]
    panel.set_outline(nodes)

    # Simulate click on first item
    item = panel._outline_tree.topLevelItem(0)
    panel._outline_tree.setCurrentItem(item)
    spy.assert_called_once_with(0)


def test_empty_outline_shows_label() -> None:
    panel = NavigationPanel()
    panel.set_outline([])
    # Outline tab should show "No bookmarks" via stacked widget
    assert panel._outline_stack.currentIndex() == 1


def test_invalid_outline_entry_no_emit() -> None:
    panel = NavigationPanel()
    spy = MagicMock()
    panel.outline_clicked.connect(spy)

    nodes = [OutlineNode(title="Bad Link", page=-1, children=[])]
    panel.set_outline(nodes)

    item = panel._outline_tree.topLevelItem(0)
    panel._outline_tree.setCurrentItem(item)
    spy.assert_not_called()


def test_set_current_page_highlights_thumbnail() -> None:
    panel = NavigationPanel()
    img = QImage(90, 120, QImage.Format.Format_RGB888)
    img.fill(0)
    panel.add_thumbnail(0, QPixmap.fromImage(img))
    panel.add_thumbnail(1, QPixmap.fromImage(img))

    panel.set_current_page(1)
    assert panel._thumbnail_list.currentRow() == 1


def test_clear_resets_both_tabs() -> None:
    panel = NavigationPanel()
    img = QImage(90, 120, QImage.Format.Format_RGB888)
    img.fill(0)
    panel.add_thumbnail(0, QPixmap.fromImage(img))
    panel.set_outline([OutlineNode(title="Test", page=0, children=[])])

    panel.clear()
    assert panel._thumbnail_list.count() == 0
    assert panel._outline_tree.topLevelItemCount() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_navigation_panel.py -v`

Expected: FAIL — NavigationPanel is a stub.

- [ ] **Step 3: Implement NavigationPanel**

Replace `k_pdf/views/navigation_panel.py` with:

```python
"""Navigation panel — thumbnails and outline/bookmarks.

QDockWidget containing a QTabWidget with Thumbnails and Outline tabs.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from k_pdf.core.outline_model import OutlineNode

logger = logging.getLogger("k_pdf.views.navigation_panel")


class NavigationPanel(QDockWidget):
    """Left-side navigation panel with thumbnails and outline."""

    thumbnail_clicked = Signal(int)  # page index
    outline_clicked = Signal(int)  # page index

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the navigation panel."""
        super().__init__("Navigation", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setMinimumWidth(120)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget)

        # Thumbnails tab
        self._thumbnail_list = QListWidget()
        self._thumbnail_list.setViewMode(QListWidget.ViewMode.IconMode)
        self._thumbnail_list.setFlow(QListWidget.Flow.TopToBottom)
        self._thumbnail_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._thumbnail_list.setWrapping(False)
        self._thumbnail_list.setSpacing(4)
        self._thumbnail_list.setIconSize(self._thumbnail_list.iconSize())
        self._thumbnail_list.currentRowChanged.connect(self._on_thumbnail_selected)
        self._tab_widget.addTab(self._thumbnail_list, "Thumbnails")

        # Outline tab with stacked widget for empty state
        self._outline_tree = QTreeWidget()
        self._outline_tree.setHeaderHidden(True)
        self._outline_tree.currentItemChanged.connect(self._on_outline_selected)

        self._no_outline_label = QLabel("No bookmarks in this document.")
        self._no_outline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_outline_label.setWordWrap(True)

        self._outline_stack = QStackedWidget()
        self._outline_stack.addWidget(self._outline_tree)  # index 0
        self._outline_stack.addWidget(self._no_outline_label)  # index 1
        self._tab_widget.addTab(self._outline_stack, "Outline")

        self.setWidget(container)

        # Suppress thumbnail_clicked during programmatic updates
        self._updating = False

    @property
    def tab_widget(self) -> QTabWidget:
        """Return the internal tab widget."""
        return self._tab_widget

    def add_thumbnail(self, page_index: int, pixmap: QPixmap) -> None:
        """Add a single thumbnail to the list.

        Args:
            page_index: 0-based page index.
            pixmap: The rendered thumbnail pixmap.
        """
        item = QListWidgetItem(QIcon(pixmap), f"Page {page_index + 1}")
        item.setData(Qt.ItemDataRole.UserRole, page_index)
        self._thumbnail_list.addItem(item)

    def set_outline(self, nodes: list[OutlineNode]) -> None:
        """Populate the outline tree.

        Args:
            nodes: Top-level outline nodes. Empty list shows "no bookmarks" label.
        """
        self._outline_tree.clear()
        if not nodes:
            self._outline_stack.setCurrentIndex(1)
            return

        self._outline_stack.setCurrentIndex(0)
        for node in nodes:
            self._add_outline_node(node, self._outline_tree)
        self._outline_tree.expandAll()

    def set_current_page(self, page_index: int) -> None:
        """Highlight the thumbnail for the current page.

        Args:
            page_index: 0-based page index.
        """
        self._updating = True
        if 0 <= page_index < self._thumbnail_list.count():
            self._thumbnail_list.setCurrentRow(page_index)
            self._thumbnail_list.scrollToItem(
                self._thumbnail_list.item(page_index),
            )
        self._updating = False

    def clear(self) -> None:
        """Reset both tabs to empty state."""
        self._thumbnail_list.clear()
        self._outline_tree.clear()
        self._outline_stack.setCurrentIndex(1)

    def _add_outline_node(
        self, node: OutlineNode, parent: QTreeWidget | QTreeWidgetItem
    ) -> None:
        """Recursively add an outline node to the tree."""
        if node.page == -1:
            item = QTreeWidgetItem([f"\u26a0 {node.title} — Invalid target"])
        else:
            item = QTreeWidgetItem([node.title])
        item.setData(0, Qt.ItemDataRole.UserRole, node.page)

        if isinstance(parent, QTreeWidget):
            parent.addTopLevelItem(item)
        else:
            parent.addChild(item)

        for child in node.children:
            self._add_outline_node(child, item)

    def _on_thumbnail_selected(self, row: int) -> None:
        """Handle thumbnail list selection change."""
        if self._updating or row < 0:
            return
        item = self._thumbnail_list.item(row)
        if item is not None:
            page_index = item.data(Qt.ItemDataRole.UserRole)
            if page_index is not None:
                self.thumbnail_clicked.emit(page_index)

    def _on_outline_selected(
        self,
        current: QTreeWidgetItem | None,
        _previous: QTreeWidgetItem | None,
    ) -> None:
        """Handle outline tree selection change."""
        if current is None:
            return
        page_index = current.data(0, Qt.ItemDataRole.UserRole)
        if page_index is not None and page_index >= 0:
            self.outline_clicked.emit(page_index)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_navigation_panel.py -v`

Expected: All 7 pass.

- [ ] **Step 5: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run ruff check . && uv run mypy k_pdf/views/navigation_panel.py`

- [ ] **Step 6: Commit**

```bash
git add k_pdf/views/navigation_panel.py tests/test_navigation_panel.py
git commit -m "feat(f3): implement NavigationPanel with thumbnails and outline tabs"
```

---

### Task 7: NavigationPresenter

**Files:**
- Create: `k_pdf/presenters/navigation_presenter.py`
- Create: `tests/test_navigation_presenter.py`
- Modify: `pyproject.toml` (mypy override)

- [ ] **Step 1: Write failing tests**

Create `tests/test_navigation_presenter.py`:

```python
"""Tests for NavigationPresenter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QTabWidget

from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.presenters.navigation_presenter import NavigationPresenter
from k_pdf.presenters.tab_manager import TabManager

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_model(file_path: Path, page_count: int = 3) -> DocumentModel:
    metadata = DocumentMetadata(
        file_path=file_path,
        page_count=page_count,
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
        for i in range(page_count)
    ]
    return DocumentModel(
        file_path=file_path,
        doc_handle=MagicMock(),
        metadata=metadata,
        pages=pages,
    )


class TestNavigationPresenter:

    @patch("k_pdf.presenters.navigation_presenter.ThumbnailCache")
    @patch("k_pdf.presenters.navigation_presenter.get_outline")
    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_document_ready_creates_cache(
        self,
        mock_presenter_cls: MagicMock,
        mock_get_outline: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """Test that document_ready creates a ThumbnailCache and fetches outline."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        mock_get_outline.return_value = []
        mock_cache = MagicMock()
        mock_cache_cls.return_value = mock_cache

        tab_widget = QTabWidget()
        recent_files = MagicMock()
        tm = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        nav = NavigationPresenter(tab_manager=tm)

        tm.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(tm._tabs))
        model = _make_model(Path("/tmp/test.pdf"))

        tm._on_document_ready(sid, model)

        mock_cache_cls.assert_called_once()
        mock_cache.start.assert_called_once()
        mock_get_outline.assert_called_once()
        assert sid in nav._thumbnail_caches

    @patch("k_pdf.presenters.navigation_presenter.ThumbnailCache")
    @patch("k_pdf.presenters.navigation_presenter.get_outline")
    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_tab_closed_discards_cache(
        self,
        mock_presenter_cls: MagicMock,
        mock_get_outline: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """Test that closing a tab shuts down and discards its thumbnail cache."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        mock_get_outline.return_value = []
        mock_cache = MagicMock()
        mock_cache_cls.return_value = mock_cache

        tab_widget = QTabWidget()
        recent_files = MagicMock()
        tm = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        nav = NavigationPresenter(tab_manager=tm)

        tm.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(tm._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        tm._on_document_ready(sid, model)

        tm.close_tab(sid)

        mock_cache.shutdown.assert_called_once()
        assert sid not in nav._thumbnail_caches
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_navigation_presenter.py -v`

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement NavigationPresenter**

Create `k_pdf/presenters/navigation_presenter.py`:

```python
"""Navigation presenter — coordinates thumbnails and outline with TabManager.

Listens to TabManager signals for document load, tab switch, and tab close.
Manages per-tab ThumbnailCache and outline data.
"""

from __future__ import annotations

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
        self._viewport_connection: object | None = None

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

    def get_outline(self, session_id: str) -> list[OutlineNode]:
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

        # If this is the active tab, push to view
        if session_id == self._tab_manager.active_session_id:
            self._active_session_id = session_id
            self.outline_ready.emit(outline)
            self._connect_viewport(session_id)

    def _on_tab_switched(self, session_id: str) -> None:
        """Handle tab switch — swap navigation data."""
        self._active_session_id = session_id

        # Push cached outline
        outline = self._outlines.get(session_id, [])
        self.outline_ready.emit(outline)

        # Push existing thumbnails
        cache = self._thumbnail_caches.get(session_id)
        if cache is not None:
            for i in range(1000):  # iterate reasonable range
                thumb = cache.get(i)
                if thumb is None and i > 0:
                    break
                if thumb is not None:
                    self.thumbnail_ready.emit(i, thumb)

        self._connect_viewport(session_id)

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
        """Forward thumbnail from cache to view (only for active tab)."""
        self.thumbnail_ready.emit(page_index, pixmap)

    def _on_viewport_page_changed(self, page_index: int) -> None:
        """Handle viewport scroll — update current page highlight."""
        self.active_thumbnail_changed.emit(page_index)

    def _connect_viewport(self, session_id: str) -> None:
        """Connect to the active viewport's current_page_changed signal."""
        # Disconnect previous
        if self._viewport_connection is not None:
            try:
                self._viewport_connection = None
            except RuntimeError:
                pass

        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.current_page_changed.connect(self._on_viewport_page_changed)
            self._viewport_connection = viewport
```

- [ ] **Step 4: Add mypy override**

In `pyproject.toml`, add:

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.presenters.navigation_presenter"]
disable_error_code = ["misc"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_navigation_presenter.py -v`

Expected: All 2 pass.

- [ ] **Step 6: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run ruff check . && uv run mypy k_pdf/presenters/navigation_presenter.py`

- [ ] **Step 7: Commit**

```bash
git add k_pdf/presenters/navigation_presenter.py tests/test_navigation_presenter.py pyproject.toml
git commit -m "feat(f3): implement NavigationPresenter"
```

---

### Task 8: Wire NavigationPanel into MainWindow

**Files:**
- Modify: `k_pdf/views/main_window.py`
- Modify: `tests/test_views.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_views.py` in `TestMainWindow`:

```python
    def test_navigation_panel_exists(self) -> None:
        """Test that MainWindow has a navigation panel dock widget."""
        from k_pdf.views.main_window import MainWindow
        from k_pdf.views.navigation_panel import NavigationPanel

        window = MainWindow()
        assert isinstance(window.navigation_panel, NavigationPanel)

    def test_navigation_panel_starts_hidden(self) -> None:
        """Test that navigation panel is hidden by default."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert not window.navigation_panel.isVisible()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_views.py::TestMainWindow::test_navigation_panel_exists tests/test_views.py::TestMainWindow::test_navigation_panel_starts_hidden -v`

Expected: FAIL — `navigation_panel` doesn't exist.

- [ ] **Step 3: Add NavigationPanel to MainWindow**

In `k_pdf/views/main_window.py`, add import:

```python
from k_pdf.views.navigation_panel import NavigationPanel
```

In `MainWindow.__init__`, after setting up the status bar and before menus:

```python
        # Navigation panel (left dock)
        self._nav_panel = NavigationPanel(self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._nav_panel)
        self._nav_panel.hide()
```

Add property:

```python
    @property
    def navigation_panel(self) -> NavigationPanel:
        """Return the navigation panel dock widget."""
        return self._nav_panel
```

In `_setup_menus`, add a View menu after the File menu:

```python
        # View menu
        view_menu = menu_bar.addMenu("&View")

        toggle_nav = self._nav_panel.toggleViewAction()
        toggle_nav.setText("Navigation &Panel")
        toggle_nav.setShortcut(QKeySequence("F5"))
        view_menu.addAction(toggle_nav)
```

Add `QKeySequence` to the imports from `PySide6.QtGui` (it's already imported).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_views.py -v`

Expected: All pass.

- [ ] **Step 5: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run ruff check . && uv run mypy k_pdf/views/main_window.py`

- [ ] **Step 6: Commit**

```bash
git add k_pdf/views/main_window.py tests/test_views.py
git commit -m "feat(f3): add NavigationPanel dock widget to MainWindow with F5 toggle"
```

---

### Task 9: Wire NavigationPresenter in KPdfApp

**Files:**
- Modify: `k_pdf/app.py`
- Modify: `tests/test_views.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_views.py` in `TestKPdfAppIntegration`:

```python
    def test_app_creates_navigation_presenter(self) -> None:
        """Test that KPdfApp creates a NavigationPresenter."""
        from k_pdf.presenters.navigation_presenter import NavigationPresenter

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert isinstance(kpdf.navigation_presenter, NavigationPresenter)
        kpdf.shutdown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_views.py::TestKPdfAppIntegration::test_app_creates_navigation_presenter -v`

Expected: FAIL — `navigation_presenter` doesn't exist on `KPdfApp`.

- [ ] **Step 3: Wire NavigationPresenter in KPdfApp**

In `k_pdf/app.py`, add import:

```python
from k_pdf.presenters.navigation_presenter import NavigationPresenter
```

In `KPdfApp.__init__`, after creating `_tab_manager`:

```python
        self._nav_presenter = NavigationPresenter(
            tab_manager=self._tab_manager,
        )
```

Add property:

```python
    @property
    def navigation_presenter(self) -> NavigationPresenter:
        """Return the navigation presenter."""
        return self._nav_presenter
```

In `_connect_signals`, add navigation wiring:

```python
        # NavigationPresenter → NavigationPanel
        nav = self._nav_presenter
        panel = self._window.navigation_panel
        nav.thumbnail_ready.connect(panel.add_thumbnail)
        nav.outline_ready.connect(panel.set_outline)
        nav.active_thumbnail_changed.connect(panel.set_current_page)

        # NavigationPanel → NavigationPresenter
        panel.thumbnail_clicked.connect(nav.navigate_to_page)
        panel.outline_clicked.connect(nav.navigate_to_page)

        # Clear panel when tabs change
        self._tab_manager.tab_switched.connect(lambda _: panel.clear())
        self._tab_manager.tab_count_changed.connect(
            lambda count: panel.clear() if count == 0 else None
        )
```

In `shutdown`, add:

```python
        self._nav_presenter.shutdown()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_views.py -v`

Expected: All pass.

- [ ] **Step 5: Run full test suite**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest -v`

Expected: All pass.

- [ ] **Step 6: Run linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run ruff check . && uv run mypy k_pdf/`

- [ ] **Step 7: Commit**

```bash
git add k_pdf/app.py tests/test_views.py
git commit -m "feat(f3): wire NavigationPresenter in KPdfApp"
```

---

### Task 10: Integration tests with real PDFs

**Files:**
- Create: `tests/test_navigation_integration.py`

- [ ] **Step 1: Write integration tests**

Create `tests/test_navigation_integration.py`:

```python
"""Integration tests for navigation panel flows."""

from __future__ import annotations

from pathlib import Path

import pymupdf
from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestNavigationIntegration:

    def test_open_pdf_shows_thumbnails(self, valid_pdf: Path, qtbot: object) -> None:
        """Test opening a PDF populates thumbnails in the navigation panel."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        panel = kpdf.window.navigation_panel
        tm = kpdf.tab_manager

        tm.open_file(valid_pdf)

        def check_thumbnails() -> None:
            assert panel._thumbnail_list.count() == 3

        qtbot.waitUntil(check_thumbnails, timeout=10000)
        kpdf.shutdown()

    def test_open_pdf_with_outline(
        self, pdf_with_outline: Path, qtbot: object
    ) -> None:
        """Test opening a PDF with bookmarks populates the outline tree."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        panel = kpdf.window.navigation_panel
        tm = kpdf.tab_manager

        tm.open_file(pdf_with_outline)

        def check_outline() -> None:
            assert panel._outline_tree.topLevelItemCount() == 3

        qtbot.waitUntil(check_outline, timeout=10000)

        # Check nested structure
        ch1 = panel._outline_tree.topLevelItem(0)
        assert ch1 is not None
        assert ch1.text(0) == "Chapter 1"
        assert ch1.childCount() == 2

        kpdf.shutdown()

    def test_close_last_tab_clears_panel(self, valid_pdf: Path, qtbot: object) -> None:
        """Test closing the last tab clears the navigation panel."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        panel = kpdf.window.navigation_panel
        tm = kpdf.tab_manager

        tm.open_file(valid_pdf)

        def check_loaded() -> None:
            assert panel._thumbnail_list.count() == 3

        qtbot.waitUntil(check_loaded, timeout=10000)

        sid = next(iter(tm._tabs))
        tm.close_tab(sid)

        assert panel._thumbnail_list.count() == 0

        kpdf.shutdown()

    def test_switch_tabs_updates_panel(
        self, valid_pdf: Path, tmp_path: Path, qtbot: object
    ) -> None:
        """Test switching tabs updates the navigation panel."""
        # Create a 5-page PDF
        path2 = tmp_path / "five.pdf"
        doc = pymupdf.open()
        for i in range(5):
            page = doc.new_page(width=612, height=792)
            page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1}")
        doc.save(str(path2))
        doc.close()

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        panel = kpdf.window.navigation_panel
        tm = kpdf.tab_manager

        tm.open_file(valid_pdf)

        def check_first() -> None:
            assert panel._thumbnail_list.count() == 3

        qtbot.waitUntil(check_first, timeout=10000)

        tm.open_file(path2)

        def check_second() -> None:
            assert panel._thumbnail_list.count() == 5

        qtbot.waitUntil(check_second, timeout=10000)

        kpdf.shutdown()
```

- [ ] **Step 2: Run integration tests**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest tests/test_navigation_integration.py -v`

Expected: All 4 pass.

- [ ] **Step 3: Run full test suite with coverage**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run pytest --cov=k_pdf --cov-report=term-missing`

Expected: All pass, coverage >= 65%.

- [ ] **Step 4: Run all linters**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf/.worktrees/feature3-navigation" && uv run ruff check . && uv run ruff format --check . && uv run mypy k_pdf/ && gitleaks detect --source .`

Expected: All clean.

- [ ] **Step 5: Commit**

```bash
git add tests/test_navigation_integration.py
git commit -m "test(f3): add navigation panel integration tests"
```

---

### Task 11: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update current state**

In `CLAUDE.md`, update the "Current State" section:

```markdown
## Current State
- **Project:** K-PDF
- **Phase:** 2 (Construction)
- **Track:** Standard
- **Features built:** Feature 1 (Open and Render PDF), Feature 2 (Multi-Tab), Feature 3 (Page Navigation)
- **Features remaining:** Features 4-12 + 7 implicit (see MVP Cutline)
- **Known issues:** Coverage at [X]% (threshold 65%)
- **Last session summary:** Feature 3 complete — NavigationPanel (QDockWidget), ThumbnailCache, OutlineService, NavigationPresenter, [N] tests passing
```

Replace `[X]` and `[N]` with actual values from the test run.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md current state — Feature 3 complete"
```
