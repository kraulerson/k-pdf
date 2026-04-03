# Feature 6: Text Markup Annotations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add text markup annotations (highlight, underline, strikethrough) with click-drag text selection, a floating toolbar with color picker, and annotation deletion via right-click context menu.

**Architecture:** `AnnotationModel` (enum + dataclass) in `core/`. `AnnotationEngine` (service) wraps all PyMuPDF annotation operations — no other layer imports fitz for annotations. `PdfViewport` gets a text selection mode that maps mouse drags to PDF word rectangles and emits a `text_selected` signal. `AnnotationToolbar` (floating frameless widget) shows near the selection with type buttons and color picker. `AnnotationPresenter` coordinates selection state, toolbar, engine calls, and dirty flag. `KPdfApp` wires everything together. Each tab maintains independent selection state; tab switch clears selection and hides toolbar.

**Tech Stack:** Python 3.13, PySide6 6.11, PyMuPDF 1.27, pytest + pytest-qt

**Spec:** `docs/superpowers/specs/2026-04-02-feature6-text-markup-annotations-design.md`

---

## File Map

**New files:**
- `k_pdf/core/annotation_model.py` — `AnnotationType` enum + `AnnotationData` dataclass
- `k_pdf/views/annotation_toolbar.py` — `AnnotationToolbar(QWidget)` floating frameless widget
- `tests/test_annotation_model.py` — unit tests for AnnotationType and AnnotationData
- `tests/test_annotation_engine.py` — unit tests for AnnotationEngine with real PDFs
- `tests/test_annotation_toolbar.py` — unit tests for AnnotationToolbar widget
- `tests/test_annotation_presenter.py` — unit tests for AnnotationPresenter
- `tests/test_viewport_selection.py` — unit tests for PdfViewport text selection mode
- `tests/test_annotation_integration.py` — integration tests through KPdfApp

**Modified files:**
- `k_pdf/services/annotation_engine.py` — replace one-line stub with full implementation
- `k_pdf/presenters/annotation_presenter.py` — replace one-line stub with full implementation
- `k_pdf/views/pdf_viewport.py` — add `text_selected` signal, `set_selection_mode()`, mouse handlers for text selection, selection overlay, right-click context menu
- `k_pdf/views/main_window.py` — add Tools menu with "Text Selection Mode" toggle (Ctrl+T), expose `tools_menu` property, add `text_selection_toggled` signal
- `k_pdf/app.py` — create `AnnotationPresenter`, wire all annotation signals
- `pyproject.toml` — add mypy overrides for new modules
- `CLAUDE.md` — update current state
- `tests/conftest.py` — add `annotatable_pdf` fixture (PDF with selectable text for annotation tests)

---

### Task 1: AnnotationModel (core/annotation_model.py)

**Files:**
- Create: `k_pdf/core/annotation_model.py`
- Create: `tests/test_annotation_model.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_annotation_model.py`:

```python
"""Tests for AnnotationType enum and AnnotationData dataclass."""

from __future__ import annotations

from datetime import datetime

from k_pdf.core.annotation_model import AnnotationData, AnnotationType


class TestAnnotationType:
    def test_enum_values(self) -> None:
        assert AnnotationType.HIGHLIGHT.value == "highlight"
        assert AnnotationType.UNDERLINE.value == "underline"
        assert AnnotationType.STRIKETHROUGH.value == "strikethrough"

    def test_enum_member_count(self) -> None:
        assert len(AnnotationType) == 3


class TestAnnotationData:
    def test_construction_required_fields(self) -> None:
        data = AnnotationData(
            type=AnnotationType.HIGHLIGHT,
            page=0,
            quads=[(0.0, 0.0, 100.0, 10.0)],
            color=(1.0, 1.0, 0.0),
        )
        assert data.type is AnnotationType.HIGHLIGHT
        assert data.page == 0
        assert data.quads == [(0.0, 0.0, 100.0, 10.0)]
        assert data.color == (1.0, 1.0, 0.0)

    def test_default_author_is_empty(self) -> None:
        data = AnnotationData(
            type=AnnotationType.UNDERLINE,
            page=1,
            quads=[(0.0, 0.0, 50.0, 10.0)],
            color=(1.0, 0.0, 0.0),
        )
        assert data.author == ""

    def test_default_created_at_is_set(self) -> None:
        before = datetime.now()
        data = AnnotationData(
            type=AnnotationType.STRIKETHROUGH,
            page=2,
            quads=[(10.0, 20.0, 80.0, 30.0)],
            color=(0.0, 0.0, 1.0),
        )
        after = datetime.now()
        assert before <= data.created_at <= after

    def test_custom_author(self) -> None:
        data = AnnotationData(
            type=AnnotationType.HIGHLIGHT,
            page=0,
            quads=[],
            color=(1.0, 1.0, 0.0),
            author="Karl",
        )
        assert data.author == "Karl"

    def test_is_mutable(self) -> None:
        data = AnnotationData(
            type=AnnotationType.HIGHLIGHT,
            page=0,
            quads=[],
            color=(1.0, 1.0, 0.0),
        )
        data.color = (0.0, 0.8, 0.0)
        assert data.color == (0.0, 0.8, 0.0)
```

- [ ] **Step 2: Run tests — verify RED**

```bash
uv run pytest tests/test_annotation_model.py -v
```

Expected: `ModuleNotFoundError` — all tests fail because `k_pdf/core/annotation_model.py` does not exist.

- [ ] **Step 3: Implement AnnotationModel**

Create `k_pdf/core/annotation_model.py`:

```python
"""Annotation data model.

Framework-free data layer for annotation type and annotation metadata.
Used by AnnotationPresenter and AnnotationEngine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AnnotationType(Enum):
    """Text markup annotation types."""

    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"


@dataclass
class AnnotationData:
    """Metadata for a single text markup annotation.

    Attributes:
        type: The annotation kind (highlight, underline, strikethrough).
        page: Zero-based page index.
        quads: Quad-point coordinates defining the annotated region.
        color: RGB color as 0.0-1.0 floats.
        author: Author name (optional metadata).
        created_at: Creation timestamp.
    """

    type: AnnotationType
    page: int
    quads: list[tuple]
    color: tuple[float, float, float]
    author: str = ""
    created_at: datetime = field(default_factory=datetime.now)
```

- [ ] **Step 4: Run tests — verify GREEN**

```bash
uv run pytest tests/test_annotation_model.py -v
```

Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add k_pdf/core/annotation_model.py tests/test_annotation_model.py
git commit -m "feat(f6): add AnnotationType enum and AnnotationData dataclass

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: AnnotationEngine (services/annotation_engine.py)

**Files:**
- Modify: `k_pdf/services/annotation_engine.py` (replace stub)
- Create: `tests/test_annotation_engine.py`
- Modify: `tests/conftest.py` (add `annotatable_pdf` fixture)
- Modify: `pyproject.toml` (add mypy override)

- [ ] **Step 1: Add `annotatable_pdf` fixture to conftest.py**

Add at the end of `tests/conftest.py`:

```python
@pytest.fixture
def annotatable_pdf(tmp_path: Path) -> Path:
    """Create a 2-page PDF with selectable text suitable for annotation tests."""
    path = tmp_path / "annotatable.pdf"
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1} first line of text")
        page.insert_text(pymupdf.Point(72, 100), f"Page {i + 1} second line of text")
        page.insert_text(pymupdf.Point(72, 128), f"Page {i + 1} third line of text")
    doc.save(str(path))
    doc.close()
    return path
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_annotation_engine.py`:

```python
"""Tests for AnnotationEngine — uses real PDFs via PyMuPDF."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from k_pdf.services.annotation_engine import AnnotationEngine


class TestGetTextWords:
    def test_returns_words_for_text_page(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        assert len(words) > 0
        # Each word tuple: (x0, y0, x1, y1, word, block_no, line_no, word_no)
        assert len(words[0]) == 8
        doc.close()

    def test_returns_empty_for_image_only_page(self, image_only_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(image_only_pdf))
        words = engine.get_text_words(doc, 0)
        assert words == []
        doc.close()


class TestAddHighlight:
    def test_creates_highlight_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        assert len(words) > 0
        # Use the first word's rect as a quad
        w = words[0]
        quads = [pymupdf.Rect(w[0], w[1], w[2], w[3]).quad]
        annot = engine.add_highlight(doc, 0, quads, (1.0, 1.0, 0.0))
        assert annot is not None
        # Verify annotation exists on page
        page = doc[0]
        annots = list(page.annots())
        assert len(annots) == 1
        doc.close()

    def test_highlight_has_correct_color(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        w = words[0]
        quads = [pymupdf.Rect(w[0], w[1], w[2], w[3]).quad]
        annot = engine.add_highlight(doc, 0, quads, (0.0, 0.8, 0.0))
        colors = annot.colors
        # Stroke color for highlights
        assert colors["stroke"] is not None
        stroke = tuple(round(c, 1) for c in colors["stroke"])
        assert stroke == (0.0, 0.8, 0.0)
        doc.close()


class TestAddUnderline:
    def test_creates_underline_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        w = words[0]
        quads = [pymupdf.Rect(w[0], w[1], w[2], w[3]).quad]
        annot = engine.add_underline(doc, 0, quads, (1.0, 0.0, 0.0))
        assert annot is not None
        page = doc[0]
        annots = list(page.annots())
        assert len(annots) == 1
        doc.close()


class TestAddStrikeout:
    def test_creates_strikeout_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        w = words[0]
        quads = [pymupdf.Rect(w[0], w[1], w[2], w[3]).quad]
        annot = engine.add_strikeout(doc, 0, quads, (1.0, 0.0, 0.0))
        assert annot is not None
        page = doc[0]
        annots = list(page.annots())
        assert len(annots) == 1
        doc.close()


class TestDeleteAnnotation:
    def test_removes_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        w = words[0]
        quads = [pymupdf.Rect(w[0], w[1], w[2], w[3]).quad]
        annot = engine.add_highlight(doc, 0, quads, (1.0, 1.0, 0.0))
        # Verify it exists
        page = doc[0]
        assert len(list(page.annots())) == 1
        # Delete it
        engine.delete_annotation(doc, 0, annot)
        assert len(list(page.annots())) == 0
        doc.close()


class TestGetAnnotations:
    def test_returns_empty_for_unannotated_page(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annots = engine.get_annotations(doc, 0)
        assert annots == []
        doc.close()

    def test_returns_annotations_after_adding(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        w = words[0]
        quads = [pymupdf.Rect(w[0], w[1], w[2], w[3]).quad]
        engine.add_highlight(doc, 0, quads, (1.0, 1.0, 0.0))
        engine.add_underline(doc, 0, quads, (1.0, 0.0, 0.0))
        annots = engine.get_annotations(doc, 0)
        assert len(annots) == 2
        doc.close()


class TestRectsToQuads:
    def test_converts_rects_to_quads(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
        quads = engine.rects_to_quads(rects)
        assert len(quads) == 2
        # Each quad should be a pymupdf.Quad object
        for q in quads:
            assert hasattr(q, "ul")  # Quad has corner attributes
        doc.close()

    def test_empty_rects_returns_empty(self) -> None:
        engine = AnnotationEngine()
        quads = engine.rects_to_quads([])
        assert quads == []

    def test_quads_usable_for_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        rects = [(w[0], w[1], w[2], w[3]) for w in words[:1]]
        quads = engine.rects_to_quads(rects)
        # Should be usable to create an annotation without error
        annot = engine.add_highlight(doc, 0, quads, (1.0, 1.0, 0.0))
        assert annot is not None
        doc.close()
```

- [ ] **Step 3: Run tests — verify RED**

```bash
uv run pytest tests/test_annotation_engine.py -v
```

Expected: `AttributeError` — `AnnotationEngine` has no methods (only a docstring stub). All 11 tests fail.

- [ ] **Step 4: Implement AnnotationEngine**

Replace `k_pdf/services/annotation_engine.py`:

```python
"""Create, modify, delete annotations.

PyMuPDF annotation operations isolated here per AGPL containment rule.
No other layer imports fitz/pymupdf directly for annotations.
"""

from __future__ import annotations

import logging
from typing import Any

import pymupdf

logger = logging.getLogger("k_pdf.services.annotation_engine")


class AnnotationEngine:
    """Wraps PyMuPDF annotation creation, deletion, and query operations.

    All methods take a doc_handle (pymupdf.Document) and page_index.
    The caller (AnnotationPresenter) never imports pymupdf directly.
    """

    def get_text_words(self, doc_handle: Any, page_index: int) -> list[tuple]:
        """Return word rectangles for text selection hit-testing.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.

        Returns:
            List of (x0, y0, x1, y1, word, block_no, line_no, word_no) tuples.
            Empty list if the page has no text layer.
        """
        page = doc_handle[page_index]
        words: list[tuple] = page.get_text("words")
        return words

    def add_highlight(
        self,
        doc_handle: Any,
        page_index: int,
        quads: list,
        color: tuple[float, float, float],
    ) -> Any:
        """Add a highlight annotation to a page.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            quads: Quad-point coordinates defining the region.
            color: RGB color as 0.0-1.0 floats.

        Returns:
            The created pymupdf.Annot object.
        """
        page = doc_handle[page_index]
        annot = page.add_highlight_annot(quads=quads)
        annot.set_colors(stroke=color)
        annot.update()
        logger.debug("Added highlight on page %d with color %s", page_index, color)
        return annot

    def add_underline(
        self,
        doc_handle: Any,
        page_index: int,
        quads: list,
        color: tuple[float, float, float],
    ) -> Any:
        """Add an underline annotation to a page.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            quads: Quad-point coordinates defining the region.
            color: RGB color as 0.0-1.0 floats.

        Returns:
            The created pymupdf.Annot object.
        """
        page = doc_handle[page_index]
        annot = page.add_underline_annot(quads=quads)
        annot.set_colors(stroke=color)
        annot.update()
        logger.debug("Added underline on page %d with color %s", page_index, color)
        return annot

    def add_strikeout(
        self,
        doc_handle: Any,
        page_index: int,
        quads: list,
        color: tuple[float, float, float],
    ) -> Any:
        """Add a strikethrough annotation to a page.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            quads: Quad-point coordinates defining the region.
            color: RGB color as 0.0-1.0 floats.

        Returns:
            The created pymupdf.Annot object.
        """
        page = doc_handle[page_index]
        annot = page.add_strikeout_annot(quads=quads)
        annot.set_colors(stroke=color)
        annot.update()
        logger.debug("Added strikeout on page %d with color %s", page_index, color)
        return annot

    def delete_annotation(
        self,
        doc_handle: Any,
        page_index: int,
        annot: Any,
    ) -> None:
        """Delete an annotation from a page.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            annot: The pymupdf.Annot object to delete.
        """
        page = doc_handle[page_index]
        page.delete_annot(annot)
        logger.debug("Deleted annotation on page %d", page_index)

    def get_annotations(self, doc_handle: Any, page_index: int) -> list[Any]:
        """Return all annotations on a page.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.

        Returns:
            List of pymupdf.Annot objects. Empty list if none.
        """
        page = doc_handle[page_index]
        return list(page.annots())

    def rects_to_quads(self, rects: list[tuple[float, float, float, float]]) -> list:
        """Convert word bounding-box rectangles to quad points.

        Used by AnnotationPresenter to convert viewport selection rects
        (plain tuples) into pymupdf Quad objects, keeping pymupdf isolated
        to the services layer.

        Args:
            rects: List of (x0, y0, x1, y1) bounding boxes.

        Returns:
            List of pymupdf.Quad objects suitable for annotation creation.
        """
        quads = []
        for x0, y0, x1, y1 in rects:
            quads.append(pymupdf.Rect(x0, y0, x1, y1).quad)
        return quads
```

- [ ] **Step 5: Add mypy override for annotation_engine**

Add to `pyproject.toml` after the existing `k_pdf.services.search_engine` override block:

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.services.annotation_engine"]
disable_error_code = ["no-untyped-call"]
```

- [ ] **Step 6: Run tests — verify GREEN**

```bash
uv run pytest tests/test_annotation_engine.py -v
```

Expected: All 11 tests pass.

- [ ] **Step 7: Run linters**

```bash
uv run ruff check k_pdf/services/annotation_engine.py tests/test_annotation_engine.py
uv run mypy k_pdf/services/annotation_engine.py
```

Expected: No errors.

- [ ] **Step 8: Commit**

```bash
git add k_pdf/services/annotation_engine.py tests/test_annotation_engine.py tests/conftest.py pyproject.toml
git commit -m "feat(f6): implement AnnotationEngine with highlight/underline/strikeout/delete

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: PdfViewport text selection mode

**Files:**
- Modify: `k_pdf/views/pdf_viewport.py`
- Create: `tests/test_viewport_selection.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_viewport_selection.py`:

```python
"""Tests for PdfViewport text selection mode."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QGraphicsView

from k_pdf.core.document_model import PageInfo
from k_pdf.views.pdf_viewport import PdfViewport

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestSelectionModeToggle:
    def test_default_is_not_selection_mode(self) -> None:
        viewport = PdfViewport()
        assert viewport.selection_mode is False

    def test_set_selection_mode_true(self) -> None:
        viewport = PdfViewport()
        viewport.set_selection_mode(True)
        assert viewport.selection_mode is True

    def test_set_selection_mode_false(self) -> None:
        viewport = PdfViewport()
        viewport.set_selection_mode(True)
        viewport.set_selection_mode(False)
        assert viewport.selection_mode is False

    def test_selection_mode_true_changes_cursor_to_ibeam(self) -> None:
        viewport = PdfViewport()
        viewport.set_selection_mode(True)
        assert viewport.cursor().shape() == Qt.CursorShape.IBeamCursor

    def test_selection_mode_false_restores_drag_mode(self) -> None:
        viewport = PdfViewport()
        viewport.set_selection_mode(True)
        viewport.set_selection_mode(False)
        assert viewport.dragMode() == QGraphicsView.DragMode.ScrollHandDrag

    def test_selection_mode_true_disables_drag(self) -> None:
        viewport = PdfViewport()
        viewport.set_selection_mode(True)
        assert viewport.dragMode() == QGraphicsView.DragMode.NoDrag


class TestSelectionOverlay:
    def test_clear_selection_overlay_no_crash(self) -> None:
        viewport = PdfViewport()
        viewport.clear_selection_overlay()
        # Should not raise even with no overlays

    def test_set_selection_mode_false_clears_overlay(self) -> None:
        viewport = PdfViewport()
        pages = [
            PageInfo(
                index=0, width=612, height=792, rotation=0,
                has_text=True, annotation_count=0,
            ),
        ]
        viewport.set_document(pages)
        viewport.set_selection_mode(True)
        # Add a fake overlay rect
        viewport._selection_overlays.append(
            viewport._scene.addRect(0, 0, 50, 10)
        )
        assert len(viewport._selection_overlays) == 1
        viewport.set_selection_mode(False)
        assert len(viewport._selection_overlays) == 0


class TestTextSelectedSignal:
    def test_text_selected_signal_exists(self) -> None:
        viewport = PdfViewport()
        # Verify the signal is present (does not raise AttributeError)
        assert hasattr(viewport, "text_selected")

    def test_annotation_context_signal_exists(self) -> None:
        viewport = PdfViewport()
        assert hasattr(viewport, "annotation_delete_requested")


class TestAnnotationEngineAccessor:
    def test_set_annotation_engine(self) -> None:
        viewport = PdfViewport()
        from unittest.mock import MagicMock

        mock_engine = MagicMock()
        viewport.set_annotation_engine(mock_engine)
        assert viewport._annotation_engine is mock_engine

    def test_set_doc_handle(self) -> None:
        viewport = PdfViewport()
        from unittest.mock import MagicMock

        mock_handle = MagicMock()
        viewport.set_doc_handle(mock_handle)
        assert viewport._doc_handle is mock_handle
```

- [ ] **Step 2: Run tests — verify RED**

```bash
uv run pytest tests/test_viewport_selection.py -v
```

Expected: `AttributeError` — `selection_mode`, `set_selection_mode`, `text_selected`, etc. do not exist.

- [ ] **Step 3: Implement text selection mode in PdfViewport**

Add the following imports to the top of `k_pdf/views/pdf_viewport.py` (after the existing imports):

```python
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QMenu
```

Add these new signals to the `PdfViewport` class (after the existing signals):

```python
    text_selected = Signal(int, list)  # (page_index, quads)
    annotation_delete_requested = Signal(int, object)  # (page_index, annot)
```

Add new instance variables in `__init__` (after `self._current_highlight`):

```python
        self._selection_mode: bool = False
        self._selection_overlays: list[QGraphicsRectItem] = []
        self._drag_start: QPointF | None = None
        self._annotation_engine: object | None = None
        self._doc_handle: object | None = None
```

Add these new methods to the `PdfViewport` class:

```python
    @property
    def selection_mode(self) -> bool:
        """Return whether text selection mode is active."""
        return self._selection_mode

    def set_selection_mode(self, active: bool) -> None:
        """Toggle between pan mode and text selection mode.

        Args:
            active: True to enable text selection, False for pan.
        """
        self._selection_mode = active
        if active:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.IBeamCursor)
        else:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.unsetCursor()
            self.clear_selection_overlay()
        self._drag_start = None

    def set_annotation_engine(self, engine: object) -> None:
        """Set the annotation engine for word rect queries.

        Args:
            engine: An AnnotationEngine instance.
        """
        self._annotation_engine = engine

    def set_doc_handle(self, doc_handle: object) -> None:
        """Set the document handle for annotation operations.

        Args:
            doc_handle: A pymupdf.Document handle (opaque to this layer).
        """
        self._doc_handle = doc_handle

    def clear_selection_overlay(self) -> None:
        """Remove all text selection overlay items from the scene."""
        for item in self._selection_overlays:
            self._scene.removeItem(item)
        self._selection_overlays.clear()

    def _page_at_scene_pos(self, scene_pos: QPointF) -> int:
        """Return the page index at the given scene position, or -1."""
        if not self._pages or not self._page_y_offsets:
            return -1
        for i, y_off in enumerate(self._page_y_offsets):
            page_bottom = y_off + self._pages[i].height
            if y_off <= scene_pos.y() <= page_bottom:
                return i
        return -1

    def _scene_to_pdf_coords(
        self, scene_pos: QPointF, page_index: int, zoom: float
    ) -> tuple[float, float]:
        """Map scene coordinates to PDF page coordinates.

        Args:
            scene_pos: Position in scene coordinates.
            page_index: The page index.
            zoom: Current zoom factor.

        Returns:
            (x, y) in PDF page coordinates.
        """
        y_off = self._page_y_offsets[page_index]
        x = (scene_pos.x()) / zoom if zoom else scene_pos.x()
        y = (scene_pos.y() - y_off) / zoom if zoom else (scene_pos.y() - y_off)
        return (x, y)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press — start text selection drag or check context menu."""
        if self._selection_mode and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = self.mapToScene(event.pos())
            self.clear_selection_overlay()
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._show_annotation_context_menu(event)
            event.accept()
            return
        super().mousePressEvent(event)

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move — update text selection overlay during drag."""
        if self._selection_mode and self._drag_start is not None:
            current = self.mapToScene(event.pos())
            self._update_selection_overlay(self._drag_start, current)
            event.accept()
            return
        super().mouseMoveEvent(event)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release — finalize text selection and emit signal."""
        if (
            self._selection_mode
            and event.button() == Qt.MouseButton.LeftButton
            and self._drag_start is not None
        ):
            end = self.mapToScene(event.pos())
            page_index, quads = self._finalize_selection(self._drag_start, end)
            self._drag_start = None
            if page_index >= 0 and quads:
                self.text_selected.emit(page_index, quads)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _update_selection_overlay(
        self, start: QPointF, current: QPointF
    ) -> None:
        """Draw selection overlay rectangles over words in the drag range."""
        self.clear_selection_overlay()
        if self._annotation_engine is None or self._doc_handle is None:
            return

        page_index = self._page_at_scene_pos(start)
        if page_index < 0:
            return

        # Determine zoom from page geometry
        page_info = self._pages[page_index]
        item = self._page_items.get(page_index)
        if item is None:
            return
        zoom = item.boundingRect().width() / page_info.width if page_info.width else 1.0

        pdf_start = self._scene_to_pdf_coords(start, page_index, zoom)
        pdf_end = self._scene_to_pdf_coords(current, page_index, zoom)

        # Get selection rectangle in PDF coords
        x0 = min(pdf_start[0], pdf_end[0])
        y0 = min(pdf_start[1], pdf_end[1])
        x1 = max(pdf_start[0], pdf_end[0])
        y1 = max(pdf_start[1], pdf_end[1])

        words = self._annotation_engine.get_text_words(self._doc_handle, page_index)  # type: ignore[union-attr]
        y_base = self._page_y_offsets[page_index]

        pen = QPen(QColor(0, 100, 200, 100))
        pen.setWidthF(0.5)
        brush = QBrush(QColor(51, 153, 255, 80))

        for w in words:
            wx0, wy0, wx1, wy1 = w[0], w[1], w[2], w[3]
            # Check if word overlaps selection rectangle
            if wx1 >= x0 and wx0 <= x1 and wy1 >= y0 and wy0 <= y1:
                sx = wx0 * zoom
                sy = wy0 * zoom + y_base
                sw = (wx1 - wx0) * zoom
                sh = (wy1 - wy0) * zoom
                rect_item = self._scene.addRect(
                    QRectF(0, 0, sw, sh), pen=pen, brush=brush
                )
                rect_item.setPos(sx, sy)
                rect_item.setZValue(15)
                self._selection_overlays.append(rect_item)

    def _finalize_selection(
        self, start: QPointF, end: QPointF
    ) -> tuple[int, list]:
        """Finalize selection and return page index + selected word rects.

        Returns word bounding-box tuples (not pymupdf Quads) to keep pymupdf
        out of the view layer. The presenter converts to quads via
        AnnotationEngine.rects_to_quads() before creating annotations.

        Args:
            start: Drag start in scene coordinates.
            end: Drag end in scene coordinates.

        Returns:
            Tuple of (page_index, word_rects) where word_rects is a list
            of (x0, y0, x1, y1) tuples in PDF coordinates for selected words.
            page_index is -1 if no words selected.
        """
        if self._annotation_engine is None or self._doc_handle is None:
            return (-1, [])

        page_index = self._page_at_scene_pos(start)
        if page_index < 0:
            return (-1, [])

        page_info = self._pages[page_index]
        item = self._page_items.get(page_index)
        if item is None:
            return (-1, [])
        zoom = item.boundingRect().width() / page_info.width if page_info.width else 1.0

        pdf_start = self._scene_to_pdf_coords(start, page_index, zoom)
        pdf_end = self._scene_to_pdf_coords(end, page_index, zoom)

        x0 = min(pdf_start[0], pdf_end[0])
        y0 = min(pdf_start[1], pdf_end[1])
        x1 = max(pdf_start[0], pdf_end[0])
        y1 = max(pdf_start[1], pdf_end[1])

        words = self._annotation_engine.get_text_words(self._doc_handle, page_index)  # type: ignore[union-attr]

        selected_rects: list[tuple[float, float, float, float]] = []
        for w in words:
            wx0, wy0, wx1, wy1 = w[0], w[1], w[2], w[3]
            if wx1 >= x0 and wx0 <= x1 and wy1 >= y0 and wy0 <= y1:
                selected_rects.append((wx0, wy0, wx1, wy1))

        return (page_index, selected_rects)

    def _show_annotation_context_menu(self, event: QMouseEvent) -> None:
        """Show a context menu for deleting annotations on right-click."""
        if self._annotation_engine is None or self._doc_handle is None:
            return

        scene_pos = self.mapToScene(event.pos())
        page_index = self._page_at_scene_pos(scene_pos)
        if page_index < 0:
            return

        page_info = self._pages[page_index]
        item = self._page_items.get(page_index)
        if item is None:
            return
        zoom = item.boundingRect().width() / page_info.width if page_info.width else 1.0

        pdf_x, pdf_y = self._scene_to_pdf_coords(scene_pos, page_index, zoom)

        annots = self._annotation_engine.get_annotations(self._doc_handle, page_index)  # type: ignore[union-attr]

        # Find the topmost annotation at click point
        hit_annot = None
        for annot in reversed(annots):
            rect = annot.rect
            if rect.x0 <= pdf_x <= rect.x1 and rect.y0 <= pdf_y <= rect.y1:
                hit_annot = annot
                break

        if hit_annot is None:
            return

        menu = QMenu(self)
        delete_action = menu.addAction("Delete Annotation")
        chosen = menu.exec(event.globalPosition().toPoint())
        if chosen == delete_action:
            self.annotation_delete_requested.emit(page_index, hit_annot)
```

**AGPL isolation note:** The viewport emits `text_selected(page_index, selected_rects)` where `selected_rects` is `list[tuple[float, float, float, float]]` -- plain tuples, no pymupdf dependency. The presenter converts to quads via `AnnotationEngine.rects_to_quads()` (added in Task 2) before calling annotation creation methods. This keeps all pymupdf usage in `k_pdf/services/`.

- [ ] **Step 4: Run tests — verify GREEN**

```bash
uv run pytest tests/test_viewport_selection.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 5: Run linters**

```bash
uv run ruff check k_pdf/views/pdf_viewport.py tests/test_viewport_selection.py
uv run mypy k_pdf/views/pdf_viewport.py
```

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add k_pdf/views/pdf_viewport.py tests/test_viewport_selection.py k_pdf/services/annotation_engine.py
git commit -m "feat(f6): add text selection mode to PdfViewport with selection overlay

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Floating AnnotationToolbar (views/annotation_toolbar.py)

**Files:**
- Create: `k_pdf/views/annotation_toolbar.py`
- Create: `tests/test_annotation_toolbar.py`
- Modify: `pyproject.toml` (add mypy override)

- [ ] **Step 1: Write failing tests**

Create `tests/test_annotation_toolbar.py`:

```python
"""Tests for AnnotationToolbar floating widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from k_pdf.core.annotation_model import AnnotationType
from k_pdf.views.annotation_toolbar import AnnotationToolbar

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestAnnotationToolbarConstruction:
    def test_creates_without_error(self) -> None:
        toolbar = AnnotationToolbar()
        assert toolbar is not None

    def test_is_frameless(self) -> None:
        toolbar = AnnotationToolbar()
        flags = toolbar.windowFlags()
        assert flags & Qt.WindowType.FramelessWindowHint

    def test_has_three_annotation_buttons(self) -> None:
        toolbar = AnnotationToolbar()
        assert toolbar._highlight_btn is not None
        assert toolbar._underline_btn is not None
        assert toolbar._strikethrough_btn is not None

    def test_has_color_picker(self) -> None:
        toolbar = AnnotationToolbar()
        assert toolbar._color_combo is not None


class TestAnnotationToolbarSignals:
    def test_highlight_button_emits_signal(self, qtbot: object) -> None:
        toolbar = AnnotationToolbar()
        with qtbot.waitSignal(toolbar.annotation_requested, timeout=1000) as blocker:  # type: ignore[union-attr]
            toolbar._highlight_btn.click()
        ann_type, color = blocker.args
        assert ann_type is AnnotationType.HIGHLIGHT

    def test_underline_button_emits_signal(self, qtbot: object) -> None:
        toolbar = AnnotationToolbar()
        with qtbot.waitSignal(toolbar.annotation_requested, timeout=1000) as blocker:  # type: ignore[union-attr]
            toolbar._underline_btn.click()
        ann_type, color = blocker.args
        assert ann_type is AnnotationType.UNDERLINE

    def test_strikethrough_button_emits_signal(self, qtbot: object) -> None:
        toolbar = AnnotationToolbar()
        with qtbot.waitSignal(toolbar.annotation_requested, timeout=1000) as blocker:  # type: ignore[union-attr]
            toolbar._strikethrough_btn.click()
        ann_type, color = blocker.args
        assert ann_type is AnnotationType.STRIKETHROUGH


class TestAnnotationToolbarColor:
    def test_default_color_is_yellow(self) -> None:
        toolbar = AnnotationToolbar()
        assert toolbar.current_color == (1.0, 1.0, 0.0)

    def test_set_color_updates_picker(self) -> None:
        toolbar = AnnotationToolbar()
        toolbar.set_color((0.0, 0.8, 0.0))
        assert toolbar.current_color == (0.0, 0.8, 0.0)

    def test_color_picker_selection_changes_color(self) -> None:
        toolbar = AnnotationToolbar()
        # Select "Red" (index 1)
        toolbar._color_combo.setCurrentIndex(1)
        assert toolbar.current_color == (1.0, 0.0, 0.0)

    def test_highlight_emits_selected_color(self, qtbot: object) -> None:
        toolbar = AnnotationToolbar()
        toolbar._color_combo.setCurrentIndex(2)  # Green
        with qtbot.waitSignal(toolbar.annotation_requested, timeout=1000) as blocker:  # type: ignore[union-attr]
            toolbar._highlight_btn.click()
        _, color = blocker.args
        assert color == (0.0, 0.8, 0.0)


class TestAnnotationToolbarPosition:
    def test_show_near_sets_position(self) -> None:
        toolbar = AnnotationToolbar()
        toolbar.show_near(100, 200)
        pos = toolbar.pos()
        # Position should be near the requested coordinates
        # Exact values depend on clamping, but should not be (0, 0)
        assert pos.x() >= 0
        assert pos.y() >= 0


class TestAnnotationToolbarDismiss:
    def test_dismissed_signal_exists(self) -> None:
        toolbar = AnnotationToolbar()
        assert hasattr(toolbar, "dismissed")

    def test_hide_emits_dismissed(self, qtbot: object) -> None:
        toolbar = AnnotationToolbar()
        toolbar.show()
        with qtbot.waitSignal(toolbar.dismissed, timeout=1000):  # type: ignore[union-attr]
            toolbar.hide()
```

- [ ] **Step 2: Run tests — verify RED**

```bash
uv run pytest tests/test_annotation_toolbar.py -v
```

Expected: `ModuleNotFoundError` — `k_pdf/views/annotation_toolbar.py` does not exist.

- [ ] **Step 3: Implement AnnotationToolbar**

Create `k_pdf/views/annotation_toolbar.py`:

```python
"""Floating annotation toolbar for text markup creation.

Appears near text selections. Offers Highlight, Underline, Strikethrough
buttons plus a color picker dropdown. Frameless widget that auto-dismisses.
"""

from __future__ import annotations

import logging
from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

from k_pdf.core.annotation_model import AnnotationType

logger = logging.getLogger("k_pdf.views.annotation_toolbar")

# Named colors with text labels for accessibility
_COLORS: list[tuple[str, tuple[float, float, float]]] = [
    ("Yellow", (1.0, 1.0, 0.0)),
    ("Red", (1.0, 0.0, 0.0)),
    ("Green", (0.0, 0.8, 0.0)),
    ("Blue", (0.0, 0.0, 1.0)),
    ("Orange", (1.0, 0.65, 0.0)),
    ("Purple", (0.5, 0.0, 0.5)),
]


class AnnotationToolbar(QWidget):
    """Floating frameless toolbar for text markup annotation creation.

    Layout: [Highlight] [Underline] [Strikethrough] | [Color picker]

    Emits annotation_requested when user clicks a type button.
    Emits dismissed when toolbar is hidden or loses focus.
    """

    annotation_requested = Signal(object, object)  # (AnnotationType, color tuple)
    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the toolbar with annotation buttons and color picker."""
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Annotation type buttons — icon + text for accessibility
        self._highlight_btn = QPushButton("Highlight")
        self._highlight_btn.setToolTip("Add highlight annotation")
        self._highlight_btn.clicked.connect(
            lambda: self._emit_annotation(AnnotationType.HIGHLIGHT)
        )
        layout.addWidget(self._highlight_btn)

        self._underline_btn = QPushButton("Underline")
        self._underline_btn.setToolTip("Add underline annotation")
        self._underline_btn.clicked.connect(
            lambda: self._emit_annotation(AnnotationType.UNDERLINE)
        )
        layout.addWidget(self._underline_btn)

        self._strikethrough_btn = QPushButton("Strikethrough")
        self._strikethrough_btn.setToolTip("Add strikethrough annotation")
        self._strikethrough_btn.clicked.connect(
            lambda: self._emit_annotation(AnnotationType.STRIKETHROUGH)
        )
        layout.addWidget(self._strikethrough_btn)

        # Color picker dropdown with named colors
        self._color_combo = QComboBox()
        for name, _rgb in _COLORS:
            self._color_combo.addItem(name)
        self._color_combo.setCurrentIndex(0)  # Yellow default
        self._color_combo.setToolTip("Annotation color")
        layout.addWidget(self._color_combo)

    @property
    def current_color(self) -> tuple[float, float, float]:
        """Return the currently selected color as RGB floats."""
        idx = self._color_combo.currentIndex()
        if 0 <= idx < len(_COLORS):
            return _COLORS[idx][1]
        return _COLORS[0][1]

    def set_color(self, color: tuple[float, float, float]) -> None:
        """Set the active color in the picker.

        Args:
            color: RGB color as 0.0-1.0 floats.
        """
        for i, (_name, rgb) in enumerate(_COLORS):
            if rgb == color:
                self._color_combo.setCurrentIndex(i)
                return
        # If color not in presets, default to first
        logger.debug("Color %s not in presets, keeping current selection", color)

    def show_near(self, x: int, y: int) -> None:
        """Position the toolbar near the given coordinates, clamped to screen.

        Args:
            x: X coordinate in screen pixels.
            y: Y coordinate in screen pixels.
        """
        self.adjustSize()
        screen = self.screen()
        if screen is not None:
            screen_rect = screen.availableGeometry()
            # Clamp to screen bounds
            clamped_x = max(screen_rect.left(), min(x, screen_rect.right() - self.width()))
            clamped_y = max(screen_rect.top(), min(y, screen_rect.bottom() - self.height()))
            self.move(clamped_x, clamped_y)
        else:
            self.move(x, y)
        self.show()

    @override
    def hideEvent(self, event: object) -> None:
        """Emit dismissed when toolbar is hidden."""
        super().hideEvent(event)  # type: ignore[arg-type]
        self.dismissed.emit()

    def _emit_annotation(self, ann_type: AnnotationType) -> None:
        """Emit annotation_requested with the given type and current color."""
        self.annotation_requested.emit(ann_type, self.current_color)
```

- [ ] **Step 4: Add mypy override**

Add to `pyproject.toml` after the existing views override block. Update the existing views override to include the new module:

Find the line:
```toml
module = ["k_pdf.core.event_bus", "k_pdf.views.pdf_viewport", "k_pdf.views.main_window", "k_pdf.views.navigation_panel", "k_pdf.views.search_bar", "k_pdf.views.zoom_toolbar"]
```

Replace with:
```toml
module = ["k_pdf.core.event_bus", "k_pdf.views.pdf_viewport", "k_pdf.views.main_window", "k_pdf.views.navigation_panel", "k_pdf.views.search_bar", "k_pdf.views.zoom_toolbar", "k_pdf.views.annotation_toolbar"]
```

- [ ] **Step 5: Run tests — verify GREEN**

```bash
uv run pytest tests/test_annotation_toolbar.py -v
```

Expected: All 11 tests pass.

- [ ] **Step 6: Run linters**

```bash
uv run ruff check k_pdf/views/annotation_toolbar.py tests/test_annotation_toolbar.py
uv run mypy k_pdf/views/annotation_toolbar.py
```

Expected: No errors.

- [ ] **Step 7: Commit**

```bash
git add k_pdf/views/annotation_toolbar.py tests/test_annotation_toolbar.py pyproject.toml
git commit -m "feat(f6): add floating AnnotationToolbar with type buttons and color picker

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: AnnotationPresenter (presenters/annotation_presenter.py)

**Files:**
- Modify: `k_pdf/presenters/annotation_presenter.py` (replace stub)
- Create: `tests/test_annotation_presenter.py`
- Modify: `pyproject.toml` (add mypy override)

- [ ] **Step 1: Write failing tests**

Create `tests/test_annotation_presenter.py`:

```python
"""Tests for AnnotationPresenter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from PySide6.QtWidgets import QApplication, QTabWidget

from k_pdf.core.annotation_model import AnnotationType
from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.presenters.annotation_presenter import AnnotationPresenter
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.annotation_engine import AnnotationEngine
from k_pdf.views.annotation_toolbar import AnnotationToolbar

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_model(file_path: Path | None = None, page_count: int = 3) -> DocumentModel:
    fp = file_path or Path("/tmp/test.pdf")
    metadata = DocumentMetadata(
        file_path=fp,
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
        file_path=fp,
        doc_handle=MagicMock(),
        metadata=metadata,
        pages=pages,
    )


def _make_tab_manager() -> TabManager:
    tab_widget = QTabWidget()
    recent_files = MagicMock()
    return TabManager(tab_widget=tab_widget, recent_files=recent_files)


def _make_presenter(
    tab_manager: TabManager | None = None,
) -> tuple[AnnotationPresenter, TabManager, AnnotationEngine, AnnotationToolbar]:
    tm = tab_manager or _make_tab_manager()
    engine = AnnotationEngine()
    toolbar = AnnotationToolbar()
    presenter = AnnotationPresenter(
        tab_manager=tm,
        engine=engine,
        toolbar=toolbar,
    )
    return presenter, tm, engine, toolbar


class TestAnnotationPresenterInit:
    def test_creates_without_error(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        assert presenter is not None

    def test_initial_selection_mode_false(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        assert presenter._selection_mode is False

    def test_initial_selected_quads_empty(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        assert presenter._selected_rects == []

    def test_initial_selected_page_negative(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        assert presenter._selected_page == -1


class TestSetSelectionMode:
    def test_toggle_on(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter.set_selection_mode(True)
        assert presenter._selection_mode is True
        mock_viewport.set_selection_mode.assert_called_once_with(True)

    def test_toggle_off(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter.set_selection_mode(True)
        presenter.set_selection_mode(False)
        assert presenter._selection_mode is False

    def test_no_viewport_no_crash(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        tm.get_active_viewport = MagicMock(return_value=None)
        presenter.set_selection_mode(True)
        assert presenter._selection_mode is True


class TestOnTextSelected:
    def test_stores_selection(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        rects = [(10.0, 20.0, 80.0, 30.0), (10.0, 32.0, 80.0, 42.0)]
        presenter.on_text_selected(0, rects)
        assert presenter._selected_page == 0
        assert presenter._selected_rects == rects

    def test_shows_toolbar(self, qtbot: object) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        mock_viewport.mapToGlobal.return_value = MagicMock(x=MagicMock(return_value=100), y=MagicMock(return_value=200))
        rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter.on_text_selected(0, rects)
        assert presenter._selected_page == 0

    def test_empty_rects_does_not_store(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        presenter.on_text_selected(0, [])
        assert presenter._selected_page == -1
        assert presenter._selected_rects == []


class TestCreateAnnotation:
    def test_calls_engine_highlight(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)

        # Simulate selection
        rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_rects = rects
        presenter._selected_page = 0

        with patch.object(engine, "rects_to_quads", return_value=["quad1"]) as mock_r2q, \
             patch.object(engine, "add_highlight", return_value=MagicMock()) as mock_add:
            presenter.create_annotation(AnnotationType.HIGHLIGHT, (1.0, 1.0, 0.0))
            mock_r2q.assert_called_once_with(rects)
            mock_add.assert_called_once_with(
                model.doc_handle, 0, ["quad1"], (1.0, 1.0, 0.0)
            )

    def test_calls_engine_underline(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)
        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0

        with patch.object(engine, "rects_to_quads", return_value=["quad1"]), \
             patch.object(engine, "add_underline", return_value=MagicMock()) as mock_add:
            presenter.create_annotation(AnnotationType.UNDERLINE, (1.0, 0.0, 0.0))
            mock_add.assert_called_once()

    def test_calls_engine_strikeout(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)
        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0

        with patch.object(engine, "rects_to_quads", return_value=["quad1"]), \
             patch.object(engine, "add_strikeout", return_value=MagicMock()) as mock_add:
            presenter.create_annotation(AnnotationType.STRIKETHROUGH, (1.0, 0.0, 0.0))
            mock_add.assert_called_once()

    def test_sets_dirty_flag(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)
        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0

        with patch.object(engine, "rects_to_quads", return_value=["quad1"]), \
             patch.object(engine, "add_highlight", return_value=MagicMock()):
            presenter.create_annotation(AnnotationType.HIGHLIGHT, (1.0, 1.0, 0.0))
            assert model.dirty is True

    def test_no_selection_is_noop(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)
        # No selection stored
        with patch.object(engine, "add_highlight") as mock_add:
            presenter.create_annotation(AnnotationType.HIGHLIGHT, (1.0, 1.0, 0.0))
            mock_add.assert_not_called()


class TestDeleteAnnotation:
    def test_calls_engine_delete(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)

        mock_annot = MagicMock()
        with patch.object(engine, "delete_annotation") as mock_del:
            presenter.delete_annotation(0, mock_annot)
            mock_del.assert_called_once_with(model.doc_handle, 0, mock_annot)

    def test_sets_dirty_flag(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)

        with patch.object(engine, "delete_annotation"):
            presenter.delete_annotation(0, MagicMock())
            assert model.dirty is True


class TestOnTabSwitched:
    def test_clears_selection(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0
        presenter.on_tab_switched("some-session-id")
        assert presenter._selected_rects == []
        assert presenter._selected_page == -1

    def test_hides_toolbar(self) -> None:
        presenter, tm, engine, toolbar = _make_presenter()
        toolbar.show()
        presenter.on_tab_switched("some-session-id")
        assert not toolbar.isVisible()
```

- [ ] **Step 2: Run tests — verify RED**

```bash
uv run pytest tests/test_annotation_presenter.py -v
```

Expected: `ImportError` — `AnnotationPresenter` is a stub with no `__init__` accepting `tab_manager`, `engine`, `toolbar`.

- [ ] **Step 3: Implement AnnotationPresenter**

Replace `k_pdf/presenters/annotation_presenter.py`:

```python
"""Annotation presenter — coordinates text selection, toolbar, and annotation engine.

Manages text selection mode, selected text regions, floating toolbar visibility,
annotation creation/deletion, and the dirty flag. Subscribes to TabManager signals
for tab-switch coordination.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from k_pdf.core.annotation_model import AnnotationType
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.annotation_engine import AnnotationEngine
from k_pdf.views.annotation_toolbar import AnnotationToolbar

logger = logging.getLogger("k_pdf.presenters.annotation_presenter")


class AnnotationPresenter(QObject):
    """Coordinates text selection, annotation toolbar, and annotation engine."""

    dirty_changed = Signal(bool)  # emitted when dirty flag transitions
    annotation_created = Signal()  # emitted after annotation added (triggers re-render)
    annotation_deleted = Signal()  # emitted after annotation removed (triggers re-render)

    def __init__(
        self,
        tab_manager: TabManager,
        engine: AnnotationEngine,
        toolbar: AnnotationToolbar,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the annotation presenter.

        Args:
            tab_manager: The tab manager for accessing active tab state.
            engine: The annotation engine for PyMuPDF operations.
            toolbar: The floating annotation toolbar widget.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._tab_manager = tab_manager
        self._engine = engine
        self._toolbar = toolbar

        self._selection_mode: bool = False
        self._selected_rects: list[tuple[float, float, float, float]] = []
        self._selected_page: int = -1

        # Connect toolbar signals
        self._toolbar.annotation_requested.connect(self._on_annotation_requested)
        self._toolbar.dismissed.connect(self._on_toolbar_dismissed)

        # Connect tab manager signals
        self._tab_manager.tab_switched.connect(self.on_tab_switched)

    def set_selection_mode(self, active: bool) -> None:
        """Toggle text selection mode on the active viewport.

        Args:
            active: True to enable text selection, False for pan mode.
        """
        self._selection_mode = active
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.set_selection_mode(active)
        if not active:
            self._clear_selection()
            self._toolbar.hide()

    def on_text_selected(
        self, page_index: int, rects: list[tuple[float, float, float, float]]
    ) -> None:
        """Handle text selection from viewport.

        Stores the selection and shows the floating toolbar.

        Args:
            page_index: Zero-based page index.
            rects: List of (x0, y0, x1, y1) word bounding boxes in PDF coords.
        """
        if not rects:
            return

        self._selected_page = page_index
        self._selected_rects = rects

        # Show toolbar near the selection
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            # Map the midpoint of the first selected rect to global coords
            # Use a rough position above the selection area
            global_pos = viewport.mapToGlobal(viewport.rect().center())
            self._toolbar.show_near(global_pos.x(), global_pos.y() - 60)

    def create_annotation(
        self,
        ann_type: AnnotationType,
        color: tuple[float, float, float],
    ) -> None:
        """Create a text markup annotation from the current selection.

        Args:
            ann_type: The annotation type (HIGHLIGHT, UNDERLINE, STRIKETHROUGH).
            color: RGB color as 0.0-1.0 floats.
        """
        if not self._selected_rects or self._selected_page < 0:
            return

        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return

        model = doc_presenter.model
        quads = self._engine.rects_to_quads(self._selected_rects)

        if ann_type is AnnotationType.HIGHLIGHT:
            self._engine.add_highlight(model.doc_handle, self._selected_page, quads, color)
        elif ann_type is AnnotationType.UNDERLINE:
            self._engine.add_underline(model.doc_handle, self._selected_page, quads, color)
        elif ann_type is AnnotationType.STRIKETHROUGH:
            self._engine.add_strikeout(model.doc_handle, self._selected_page, quads, color)

        model.dirty = True
        self.dirty_changed.emit(True)
        self.annotation_created.emit()

        # Clear selection after annotation creation
        self._clear_selection()
        self._toolbar.hide()

        logger.debug(
            "Created %s annotation on page %d with color %s",
            ann_type.value,
            self._selected_page,
            color,
        )

    def delete_annotation(self, page_index: int, annot: object) -> None:
        """Delete an annotation from a page.

        Args:
            page_index: Zero-based page index.
            annot: The annotation object to delete.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return

        model = doc_presenter.model
        self._engine.delete_annotation(model.doc_handle, page_index, annot)

        model.dirty = True
        self.dirty_changed.emit(True)
        self.annotation_deleted.emit()

        logger.debug("Deleted annotation on page %d", page_index)

    def on_tab_switched(self, session_id: str) -> None:
        """Handle tab switch — clear selection and hide toolbar.

        Args:
            session_id: The new active tab's session ID.
        """
        self._clear_selection()
        self._toolbar.hide()

    def _clear_selection(self) -> None:
        """Clear the stored text selection state."""
        self._selected_rects = []
        self._selected_page = -1

    def _on_annotation_requested(
        self, ann_type: AnnotationType, color: tuple[float, float, float]
    ) -> None:
        """Handle annotation creation request from toolbar."""
        self.create_annotation(ann_type, color)

    def _on_toolbar_dismissed(self) -> None:
        """Handle toolbar dismissal — clear selection overlay on viewport."""
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.clear_selection_overlay()
```

- [ ] **Step 4: Add mypy override**

Add to `pyproject.toml` after the existing `k_pdf.presenters.search_presenter` override:

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.presenters.annotation_presenter"]
disable_error_code = ["misc"]
```

- [ ] **Step 5: Run tests — verify GREEN**

```bash
uv run pytest tests/test_annotation_presenter.py -v
```

Expected: All 16 tests pass.

- [ ] **Step 6: Run linters**

```bash
uv run ruff check k_pdf/presenters/annotation_presenter.py tests/test_annotation_presenter.py
uv run mypy k_pdf/presenters/annotation_presenter.py
```

Expected: No errors.

- [ ] **Step 7: Commit**

```bash
git add k_pdf/presenters/annotation_presenter.py tests/test_annotation_presenter.py pyproject.toml
git commit -m "feat(f6): implement AnnotationPresenter with selection, creation, deletion

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Wire into MainWindow — Tools menu

**Files:**
- Modify: `k_pdf/views/main_window.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_views.py` (at the end of the file):

```python
class TestMainWindowToolsMenu:
    def test_tools_menu_exists(self) -> None:
        window = MainWindow()
        assert window.tools_menu is not None

    def test_text_selection_action_exists(self) -> None:
        window = MainWindow()
        actions = window.tools_menu.actions()
        names = [a.text() for a in actions]
        assert any("Text Selection" in n for n in names)

    def test_text_selection_action_is_checkable(self) -> None:
        window = MainWindow()
        actions = window.tools_menu.actions()
        sel_action = [a for a in actions if "Text Selection" in a.text()][0]
        assert sel_action.isCheckable()

    def test_text_selection_toggle_emits_signal(self, qtbot: object) -> None:
        window = MainWindow()
        with qtbot.waitSignal(window.text_selection_toggled, timeout=1000):  # type: ignore[union-attr]
            actions = window.tools_menu.actions()
            sel_action = [a for a in actions if "Text Selection" in a.text()][0]
            sel_action.trigger()

    def test_text_selection_shortcut_is_ctrl_t(self) -> None:
        window = MainWindow()
        actions = window.tools_menu.actions()
        sel_action = [a for a in actions if "Text Selection" in a.text()][0]
        assert sel_action.shortcut().toString() == "Ctrl+T"
```

- [ ] **Step 2: Run tests — verify RED**

```bash
uv run pytest tests/test_views.py::TestMainWindowToolsMenu -v
```

Expected: `AttributeError` — `MainWindow` has no `tools_menu` property or `text_selection_toggled` signal.

- [ ] **Step 3: Implement Tools menu in MainWindow**

Add a new signal to the `MainWindow` class (after the existing signals):

```python
    text_selection_toggled = Signal(bool)
```

Add a `tools_menu` property to the `MainWindow` class:

```python
    @property
    def tools_menu(self) -> QMenu:
        """Return the Tools menu."""
        return self._tools_menu
```

Add the `QMenu` import if not already present. In `_setup_menus`, add at the end (after the View menu block):

```python
        # Tools menu
        self._tools_menu = menu_bar.addMenu("&Tools")

        text_select_action = QAction("&Text Selection Mode", self)
        text_select_action.setShortcut(QKeySequence("Ctrl+T"))
        text_select_action.setCheckable(True)
        text_select_action.setToolTip("Toggle text selection for annotations")
        text_select_action.toggled.connect(self.text_selection_toggled.emit)
        self._tools_menu.addAction(text_select_action)
```

Also add `QMenu` to the imports from `PySide6.QtWidgets` if not already there.

- [ ] **Step 4: Run tests — verify GREEN**

```bash
uv run pytest tests/test_views.py::TestMainWindowToolsMenu -v
```

Expected: All 5 tests pass.

- [ ] **Step 5: Run existing tests to verify no regressions**

```bash
uv run pytest tests/test_views.py -v
```

Expected: All existing tests plus the new 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add k_pdf/views/main_window.py tests/test_views.py
git commit -m "feat(f6): add Tools menu with Text Selection Mode toggle to MainWindow

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Wire AnnotationPresenter in KPdfApp

**Files:**
- Modify: `k_pdf/app.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_views.py` (at the end):

```python
class TestKPdfAppAnnotationWiring:
    def test_app_has_annotation_presenter(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert kpdf.annotation_presenter is not None
        kpdf.shutdown()

    def test_app_has_annotation_toolbar(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert kpdf._annotation_toolbar is not None
        kpdf.shutdown()
```

- [ ] **Step 2: Run tests — verify RED**

```bash
uv run pytest tests/test_views.py::TestKPdfAppAnnotationWiring -v
```

Expected: `AttributeError` — `KPdfApp` has no `annotation_presenter` attribute.

- [ ] **Step 3: Implement wiring in KPdfApp**

In `k_pdf/app.py`, add imports:

```python
from k_pdf.presenters.annotation_presenter import AnnotationPresenter
from k_pdf.services.annotation_engine import AnnotationEngine
from k_pdf.views.annotation_toolbar import AnnotationToolbar
```

In `__init__`, after `self._search_presenter` creation, add:

```python
        self._annotation_engine = AnnotationEngine()
        self._annotation_toolbar = AnnotationToolbar()
        self._annotation_presenter = AnnotationPresenter(
            tab_manager=self._tab_manager,
            engine=self._annotation_engine,
            toolbar=self._annotation_toolbar,
        )
```

Add a property:

```python
    @property
    def annotation_presenter(self) -> AnnotationPresenter:
        """Return the annotation presenter."""
        return self._annotation_presenter
```

In `_connect_signals`, add at the end:

```python
        # Annotation wiring
        # MainWindow Tools menu → AnnotationPresenter
        self._window.text_selection_toggled.connect(
            self._annotation_presenter.set_selection_mode
        )

        # AnnotationPresenter → re-render on create/delete
        self._annotation_presenter.annotation_created.connect(
            self._on_annotation_changed
        )
        self._annotation_presenter.annotation_deleted.connect(
            self._on_annotation_changed
        )

        # AnnotationPresenter → dirty flag → tab title
        self._annotation_presenter.dirty_changed.connect(
            self._on_annotation_dirty_changed
        )

        # When a new document loads, wire viewport annotation signals
        self._tab_manager.document_ready.connect(self._on_document_ready_annotation)
```

Add handler methods to `KPdfApp`:

```python
    def _on_annotation_changed(self) -> None:
        """Re-render current page after annotation create/delete."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and viewport is not None:
            # Invalidate cache and re-request visible pages
            presenter.cache.invalidate()
            presenter._pending_renders.clear()
            first, last = viewport.get_visible_page_range()
            if first >= 0:
                presenter.request_pages(list(range(first, last + 1)))

    def _on_annotation_dirty_changed(self, dirty: bool) -> None:
        """Update tab title with dirty indicator."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and presenter.model is not None and viewport is not None:
            name = presenter.model.file_path.name
            title = f"* {name}" if dirty else name
            idx = self._window.tab_widget.indexOf(viewport)
            if idx >= 0:
                self._window.tab_widget.setTabText(idx, title)

    def _on_document_ready_annotation(self, session_id: str, model: object) -> None:
        """Wire viewport annotation signals for a newly loaded document tab."""
        viewport = self._tab_manager.get_active_viewport()
        presenter = self._tab_manager.get_active_presenter()
        if viewport is not None:
            viewport.set_annotation_engine(self._annotation_engine)
            if presenter is not None and presenter.model is not None:
                viewport.set_doc_handle(presenter.model.doc_handle)
            viewport.text_selected.connect(self._annotation_presenter.on_text_selected)
            viewport.annotation_delete_requested.connect(
                self._annotation_presenter.delete_annotation
            )
```

In `shutdown`, add before the existing shutdown calls:

```python
        self._annotation_toolbar.hide()
```

- [ ] **Step 4: Run tests — verify GREEN**

```bash
uv run pytest tests/test_views.py::TestKPdfAppAnnotationWiring -v
```

Expected: Both tests pass.

- [ ] **Step 5: Run full test suite to verify no regressions**

```bash
uv run pytest -v
```

Expected: All tests pass.

- [ ] **Step 6: Run linters**

```bash
uv run ruff check k_pdf/app.py
uv run mypy k_pdf/app.py
```

Expected: No errors.

- [ ] **Step 7: Commit**

```bash
git add k_pdf/app.py tests/test_views.py
git commit -m "feat(f6): wire AnnotationPresenter, engine, and toolbar in KPdfApp

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Integration tests

**Files:**
- Create: `tests/test_annotation_integration.py`

- [ ] **Step 1: Write integration tests**

Create `tests/test_annotation_integration.py`:

```python
"""Integration tests for text markup annotation flows with real PDFs."""

from __future__ import annotations

from pathlib import Path

import pymupdf
from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.core.annotation_model import AnnotationType

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _wait_for_document(kpdf: KPdfApp, qtbot: object) -> None:
    """Wait until the active tab has a loaded document."""
    tm = kpdf.tab_manager

    def check_loaded() -> None:
        assert tm.get_active_presenter() is not None
        assert tm.get_active_presenter().model is not None  # type: ignore[union-attr]

    qtbot.waitUntil(check_loaded, timeout=10000)  # type: ignore[union-attr]


def test_create_highlight_annotation(annotatable_pdf: Path, qtbot: object) -> None:
    """Toggle selection mode, select text, create highlight — annotation exists on page."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    # Get word rects from engine
    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    assert len(words) > 0

    # Simulate text selection: first 3 words
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:3]]
    ap.on_text_selected(0, rects)
    ap.create_annotation(AnnotationType.HIGHLIGHT, (1.0, 1.0, 0.0))

    # Verify annotation exists on page
    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) >= 1
    assert presenter.model.dirty is True

    kpdf.shutdown()


def test_create_underline_annotation(annotatable_pdf: Path, qtbot: object) -> None:
    """Same flow with underline type."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
    ap.on_text_selected(0, rects)
    ap.create_annotation(AnnotationType.UNDERLINE, (1.0, 0.0, 0.0))

    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) >= 1

    kpdf.shutdown()


def test_create_strikethrough_annotation(annotatable_pdf: Path, qtbot: object) -> None:
    """Same flow with strikethrough type."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
    ap.on_text_selected(0, rects)
    ap.create_annotation(AnnotationType.STRIKETHROUGH, (1.0, 0.0, 0.0))

    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) >= 1

    kpdf.shutdown()


def test_delete_annotation(annotatable_pdf: Path, qtbot: object) -> None:
    """Create annotation, then delete it — annotation removed, dirty still True."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
    ap.on_text_selected(0, rects)
    ap.create_annotation(AnnotationType.HIGHLIGHT, (1.0, 1.0, 0.0))

    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) == 1

    # Delete it
    annot = annots[0]
    ap.delete_annotation(0, annot)

    annots_after = list(page.annots())
    assert len(annots_after) == 0
    # Dirty flag is still True (changes were made)
    assert presenter.model.dirty is True

    kpdf.shutdown()


def test_dirty_flag_updates_tab_title(annotatable_pdf: Path, qtbot: object) -> None:
    """Create annotation — verify tab title starts with '*'."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    # Verify tab title does NOT start with * before annotation
    viewport = tm.get_active_viewport()
    assert viewport is not None
    idx = kpdf.window.tab_widget.indexOf(viewport)
    title_before = kpdf.window.tab_widget.tabText(idx)
    assert not title_before.startswith("*")

    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
    ap.on_text_selected(0, rects)
    ap.create_annotation(AnnotationType.HIGHLIGHT, (1.0, 1.0, 0.0))

    # Process events to let dirty_changed propagate
    QApplication.processEvents()

    title_after = kpdf.window.tab_widget.tabText(idx)
    assert title_after.startswith("*")

    kpdf.shutdown()


def test_no_text_layer_returns_empty(image_only_pdf: Path, qtbot: object) -> None:
    """Open image-only PDF — get_text_words returns empty, no crash."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager

    tm.open_file(image_only_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    assert words == []

    kpdf.shutdown()


def test_color_picker_changes_annotation_color(annotatable_pdf: Path, qtbot: object) -> None:
    """Select text, change color to Green, Highlight — verify annotation color is green."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
    ap.on_text_selected(0, rects)

    green = (0.0, 0.8, 0.0)
    ap.create_annotation(AnnotationType.HIGHLIGHT, green)

    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) == 1
    colors = annots[0].colors
    stroke = tuple(round(c, 1) for c in colors["stroke"])
    assert stroke == green

    kpdf.shutdown()


def test_tab_switch_clears_selection(annotatable_pdf: Path, qtbot: object) -> None:
    """Select text on tab 1, switch to tab 2 — verify selection cleared."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    # Open two tabs
    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    # Create a second copy for second tab
    import shutil
    second_pdf = annotatable_pdf.parent / "second.pdf"
    shutil.copy(annotatable_pdf, second_pdf)
    tm.open_file(second_pdf)

    def check_two_tabs() -> None:
        assert kpdf.window.tab_widget.count() == 2

    qtbot.waitUntil(check_two_tabs, timeout=10000)  # type: ignore[union-attr]

    # Switch to first tab
    kpdf.window.tab_widget.setCurrentIndex(0)
    QApplication.processEvents()

    # Select text on first tab
    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None
    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
    ap.on_text_selected(0, rects)
    assert ap._selected_rects == rects

    # Switch to second tab
    kpdf.window.tab_widget.setCurrentIndex(1)
    QApplication.processEvents()

    # Selection should be cleared
    assert ap._selected_rects == []
    assert ap._selected_page == -1

    kpdf.shutdown()
```

- [ ] **Step 2: Run integration tests**

```bash
uv run pytest tests/test_annotation_integration.py -v
```

Expected: All 8 tests pass.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest -v
```

Expected: All tests pass with no regressions.

- [ ] **Step 4: Run coverage check**

```bash
uv run pytest --cov=k_pdf --cov-report=term-missing
```

Expected: Coverage remains at or above 65%.

- [ ] **Step 5: Commit**

```bash
git add tests/test_annotation_integration.py
git commit -m "feat(f6): add integration tests for text markup annotation flows

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update current state in CLAUDE.md**

Find the `## Current State` section and update:

```markdown
## Current State
- **Project:** K-PDF
- **Phase:** 2 (Construction)
- **Track:** Standard
- **Features built:** Feature 1 (Open and Render PDF), Feature 2 (Multi-Tab), Feature 3 (Page Navigation), Feature 4 (Text Search), Feature 5 (Zoom, Rotate, Page Fit Modes), Feature 6 (Text Markup Annotations)
- **Features remaining:** Features 7-12 + 7 implicit (see MVP Cutline)
- **Known issues:** Coverage at 65%+ (threshold 65%)
- **Last session summary:** Feature 6 complete — AnnotationType/AnnotationData model, AnnotationEngine with highlight/underline/strikeout/delete, PdfViewport text selection mode with overlay, floating AnnotationToolbar with color picker, AnnotationPresenter coordinating selection/creation/deletion/dirty flag, MainWindow Tools menu with Ctrl+T toggle, KPdfApp full wiring
```

- [ ] **Step 2: Run linters one final time**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy k_pdf/
```

Expected: No errors.

- [ ] **Step 3: Final commit**

```bash
git add CLAUDE.md
git commit -m "feat(f6): update CLAUDE.md with Feature 6 completion state

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Implementation Notes

**AGPL isolation:** The viewport does NOT import pymupdf at module level. Word rectangle coordinates flow as plain `tuple[float, float, float, float]` from the viewport to the presenter. The presenter calls `AnnotationEngine.rects_to_quads()` to convert to pymupdf Quad objects before passing to annotation creation methods. All pymupdf operations are isolated in `k_pdf/services/annotation_engine.py`.

**Signal flow summary:**
1. User toggles Tools > Text Selection Mode (Ctrl+T) --> `MainWindow.text_selection_toggled(bool)` --> `AnnotationPresenter.set_selection_mode()` --> `PdfViewport.set_selection_mode()`
2. User drags over text --> `PdfViewport` queries `AnnotationEngine.get_text_words()`, draws overlay, emits `text_selected(page_index, rects)`
3. `AnnotationPresenter.on_text_selected()` stores selection, shows `AnnotationToolbar`
4. User clicks toolbar button --> `AnnotationToolbar.annotation_requested(type, color)` --> `AnnotationPresenter.create_annotation()` --> `AnnotationEngine.add_highlight/underline/strikeout()` --> `model.dirty = True` --> re-render
5. Right-click on annotation --> `PdfViewport.annotation_delete_requested(page_index, annot)` --> `AnnotationPresenter.delete_annotation()` --> `AnnotationEngine.delete_annotation()` --> `model.dirty = True` --> re-render

**Dirty flag:** Tab title gains `*` prefix on annotation create/delete. Full Save/Discard/Cancel close-guard dialog is deferred to Feature 8.

**mypy overrides needed:**
- `k_pdf.services.annotation_engine` — `disable_error_code = ["no-untyped-call"]`
- `k_pdf.views.annotation_toolbar` — added to existing views override with `disable_error_code = ["misc"]`
- `k_pdf.presenters.annotation_presenter` — `disable_error_code = ["misc"]`
