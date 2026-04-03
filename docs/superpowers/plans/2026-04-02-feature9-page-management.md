# Feature 9: Page Management — Implementation Plan

**Date:** 2026-04-02
**Spec:** `docs/superpowers/specs/2026-04-02-feature9-page-management-design.md`
**Branch:** `feature/page-management`
**Depends on:** Features 1, 2, 5, 8 (all complete)

---

## Task Overview

| # | Task | Type | Files |
|---|------|------|-------|
| 1 | PageOperation enum + PageOperationResult dataclass | model | `k_pdf/core/page_model.py`, `tests/test_page_model.py` |
| 2 | PageEngine service (replace stub) | service | `k_pdf/services/page_engine.py`, `tests/test_page_engine.py` |
| 3 | PageManagerPanel view (replace stub) | view | `k_pdf/views/page_manager_panel.py`, `tests/test_page_manager_panel.py` |
| 4 | PageManagementPresenter (replace stub) | presenter | `k_pdf/presenters/page_management_presenter.py`, `tests/test_page_management_presenter.py` |
| 5 | MainWindow: add Page Manager dock + F7 toggle | view | `k_pdf/views/main_window.py`, `tests/test_views.py` |
| 6 | KPdfApp: wire all signals | app | `k_pdf/app.py`, `tests/test_page_management_integration.py` |
| 7 | Mypy overrides + CLAUDE.md update | config | `pyproject.toml`, `CLAUDE.md` |

---

## Task 1: PageOperation + PageOperationResult Model

### RED — Write failing tests

**File: `tests/test_page_model.py`**

```python
"""Tests for page management data model."""

from __future__ import annotations

from k_pdf.core.page_model import PageOperation, PageOperationResult


class TestPageOperation:
    def test_rotate_value(self) -> None:
        assert PageOperation.ROTATE.value == "rotate"

    def test_delete_value(self) -> None:
        assert PageOperation.DELETE.value == "delete"

    def test_insert_value(self) -> None:
        assert PageOperation.INSERT.value == "insert"

    def test_move_value(self) -> None:
        assert PageOperation.MOVE.value == "move"

    def test_all_members(self) -> None:
        assert set(PageOperation) == {
            PageOperation.ROTATE,
            PageOperation.DELETE,
            PageOperation.INSERT,
            PageOperation.MOVE,
        }


class TestPageOperationResult:
    def test_construction_success(self) -> None:
        result = PageOperationResult(
            operation=PageOperation.DELETE,
            success=True,
            new_page_count=2,
            affected_pages=[1],
        )
        assert result.operation == PageOperation.DELETE
        assert result.success is True
        assert result.new_page_count == 2
        assert result.affected_pages == [1]
        assert result.error_message == ""

    def test_construction_failure(self) -> None:
        result = PageOperationResult(
            operation=PageOperation.DELETE,
            success=False,
            new_page_count=3,
            affected_pages=[],
            error_message="Cannot delete all pages",
        )
        assert result.success is False
        assert result.error_message == "Cannot delete all pages"

    def test_frozen(self) -> None:
        result = PageOperationResult(
            operation=PageOperation.ROTATE,
            success=True,
            new_page_count=3,
            affected_pages=[0, 1],
        )
        import pytest
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_default_error_message(self) -> None:
        result = PageOperationResult(
            operation=PageOperation.MOVE,
            success=True,
            new_page_count=5,
            affected_pages=[2],
        )
        assert result.error_message == ""
```

### GREEN — Implement model

**File: `k_pdf/core/page_model.py`**

```python
"""Page management data model.

Framework-free data layer for page operations.
Used by PageEngine and PageManagementPresenter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PageOperation(Enum):
    """Types of page manipulation operations."""

    ROTATE = "rotate"
    DELETE = "delete"
    INSERT = "insert"
    MOVE = "move"


@dataclass(frozen=True)
class PageOperationResult:
    """Immutable result of a page operation.

    Attributes:
        operation: The operation that was performed.
        success: Whether the operation succeeded.
        new_page_count: Total page count after operation.
        affected_pages: Zero-based indices of pages affected.
        error_message: Error description if success is False.
    """

    operation: PageOperation
    success: bool
    new_page_count: int
    affected_pages: list[int] = field(default_factory=list)
    error_message: str = ""
```

---

## Task 2: PageEngine Service (Replace Stub)

### RED — Write failing tests

**File: `tests/test_page_engine.py`**

```python
"""Tests for PageEngine — page manipulation via PyMuPDF."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from k_pdf.core.page_model import PageOperation, PageOperationResult
from k_pdf.services.page_engine import PageEngine


@pytest.fixture
def multi_page_pdf(tmp_path: Path) -> Path:
    """Create a 5-page PDF with identifiable text on each page."""
    path = tmp_path / "multi.pdf"
    doc = pymupdf.open()
    for i in range(5):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1} content")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def single_page_pdf(tmp_path: Path) -> Path:
    """Create a 1-page PDF."""
    path = tmp_path / "single.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(pymupdf.Point(72, 72), "Only page")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def source_pdf(tmp_path: Path) -> Path:
    """Create a 2-page PDF to insert from."""
    path = tmp_path / "source.pdf"
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Source page {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


class TestPageEngineDeletePages:
    def test_delete_single_page(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.delete_pages(doc, [2])
        assert result.success is True
        assert result.operation == PageOperation.DELETE
        assert result.new_page_count == 4
        assert doc.page_count == 4
        doc.close()

    def test_delete_multiple_pages(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.delete_pages(doc, [0, 2, 4])
        assert result.success is True
        assert result.new_page_count == 2
        doc.close()

    def test_delete_all_pages_blocked(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.delete_pages(doc, [0, 1, 2, 3, 4])
        assert result.success is False
        assert "at least one page" in result.error_message.lower()
        assert doc.page_count == 5  # unchanged
        doc.close()

    def test_delete_single_page_doc_blocked(self, single_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(single_page_pdf))
        result = engine.delete_pages(doc, [0])
        assert result.success is False
        assert doc.page_count == 1
        doc.close()

    def test_delete_returns_affected_pages(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.delete_pages(doc, [1, 3])
        assert result.affected_pages == [1, 3]
        doc.close()


class TestPageEngineMovePage:
    def test_move_page_forward(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        text_before = doc[0].get_text("text").strip()
        result = engine.move_page(doc, 0, 2)
        assert result.success is True
        assert result.operation == PageOperation.MOVE
        # Page that was at 0 is now at 2
        assert doc[2].get_text("text").strip() == text_before
        doc.close()

    def test_move_page_backward(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        text_before = doc[3].get_text("text").strip()
        result = engine.move_page(doc, 3, 1)
        assert result.success is True
        assert doc[1].get_text("text").strip() == text_before
        doc.close()

    def test_move_page_same_position(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.move_page(doc, 2, 2)
        assert result.success is True
        assert result.new_page_count == 5
        doc.close()


class TestPageEngineRotatePages:
    def test_rotate_single_page_90(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        original = doc[0].rotation
        result = engine.rotate_pages(doc, [0], 90)
        assert result.success is True
        assert result.operation == PageOperation.ROTATE
        assert doc[0].rotation == (original + 90) % 360
        doc.close()

    def test_rotate_multiple_pages(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.rotate_pages(doc, [0, 1, 2], 90)
        assert result.success is True
        assert result.affected_pages == [0, 1, 2]
        for i in [0, 1, 2]:
            assert doc[i].rotation == 90
        doc.close()

    def test_rotate_270(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.rotate_pages(doc, [0], 270)
        assert result.success is True
        assert doc[0].rotation == 270
        doc.close()

    def test_rotate_180(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.rotate_pages(doc, [0], 180)
        assert result.success is True
        assert doc[0].rotation == 180
        doc.close()

    def test_rotate_invalid_angle(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.rotate_pages(doc, [0], 45)
        assert result.success is False
        assert "angle" in result.error_message.lower()
        doc.close()


class TestPageEngineInsertPages:
    def test_insert_at_end(self, multi_page_pdf: Path, source_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.insert_pages_from(doc, source_pdf, 5)
        assert result.success is True
        assert result.operation == PageOperation.INSERT
        assert result.new_page_count == 7
        assert doc.page_count == 7
        doc.close()

    def test_insert_at_beginning(self, multi_page_pdf: Path, source_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.insert_pages_from(doc, source_pdf, 0)
        assert result.success is True
        assert result.new_page_count == 7
        # Source pages should be at position 0 and 1
        text_p0 = doc[0].get_text("text").strip()
        assert "Source" in text_p0
        doc.close()

    def test_insert_at_middle(self, multi_page_pdf: Path, source_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.insert_pages_from(doc, source_pdf, 2)
        assert result.success is True
        assert result.new_page_count == 7
        doc.close()

    def test_insert_from_invalid_path(self, multi_page_pdf: Path, tmp_path: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        bad_path = tmp_path / "nonexistent.pdf"
        result = engine.insert_pages_from(doc, bad_path, 0)
        assert result.success is False
        assert result.new_page_count == 5  # unchanged
        doc.close()

    def test_insert_affected_pages(self, multi_page_pdf: Path, source_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.insert_pages_from(doc, source_pdf, 2)
        assert result.affected_pages == [2, 3]
        doc.close()


class TestPageEngineGetPageCount:
    def test_get_page_count(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        assert engine.get_page_count(doc) == 5
        doc.close()

    def test_get_page_count_after_delete(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        engine.delete_pages(doc, [0])
        assert engine.get_page_count(doc) == 4
        doc.close()


class TestPageEngineRenderThumbnail:
    def test_render_thumbnail_returns_pixmap(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        pixmap = engine.render_thumbnail(doc, 0, width=150)
        assert pixmap is not None
        assert not pixmap.isNull()
        assert pixmap.width() == 150
        doc.close()

    def test_render_thumbnail_correct_aspect(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        pixmap = engine.render_thumbnail(doc, 0, width=150)
        # US Letter: 612x792 -> aspect ~0.77 -> height ~194 for width 150
        assert pixmap.height() > pixmap.width()
        doc.close()
```

### GREEN — Implement PageEngine

**File: `k_pdf/services/page_engine.py`**

```python
"""Page manipulation (add, delete, reorder, rotate).

All pymupdf page manipulation calls are isolated in this service.
No other module in k_pdf may import pymupdf for page operations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pymupdf
from PySide6.QtGui import QImage, QPixmap

from k_pdf.core.page_model import PageOperation, PageOperationResult

logger = logging.getLogger("k_pdf.services.page_engine")

_VALID_ANGLES = {90, 180, 270}


class PageEngine:
    """Wraps PyMuPDF page manipulation operations.

    All methods take a doc_handle (pymupdf.Document).
    The caller (PageManagementPresenter) never imports pymupdf directly.
    """

    def delete_pages(
        self, doc_handle: Any, page_indices: list[int]
    ) -> PageOperationResult:
        """Delete pages from the document.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_indices: Zero-based indices of pages to delete.

        Returns:
            PageOperationResult indicating success or failure.
        """
        current_count = doc_handle.page_count
        if len(page_indices) >= current_count:
            return PageOperationResult(
                operation=PageOperation.DELETE,
                success=False,
                new_page_count=current_count,
                affected_pages=page_indices,
                error_message=(
                    "Cannot delete all pages. "
                    "A PDF must contain at least one page."
                ),
            )

        try:
            doc_handle.delete_pages(page_indices)
            new_count = doc_handle.page_count
            logger.debug(
                "Deleted pages %s, new count: %d", page_indices, new_count
            )
            return PageOperationResult(
                operation=PageOperation.DELETE,
                success=True,
                new_page_count=new_count,
                affected_pages=page_indices,
            )
        except Exception as e:
            logger.warning("Failed to delete pages %s: %s", page_indices, e)
            return PageOperationResult(
                operation=PageOperation.DELETE,
                success=False,
                new_page_count=doc_handle.page_count,
                affected_pages=page_indices,
                error_message=str(e),
            )

    def move_page(
        self, doc_handle: Any, from_index: int, to_index: int
    ) -> PageOperationResult:
        """Move a page from one position to another.

        Args:
            doc_handle: A pymupdf.Document handle.
            from_index: Current zero-based page index.
            to_index: Target zero-based page index.

        Returns:
            PageOperationResult indicating success or failure.
        """
        try:
            doc_handle.move_page(from_index, to_index)
            logger.debug("Moved page %d to %d", from_index, to_index)
            return PageOperationResult(
                operation=PageOperation.MOVE,
                success=True,
                new_page_count=doc_handle.page_count,
                affected_pages=[from_index, to_index],
            )
        except Exception as e:
            logger.warning(
                "Failed to move page %d to %d: %s", from_index, to_index, e
            )
            return PageOperationResult(
                operation=PageOperation.MOVE,
                success=False,
                new_page_count=doc_handle.page_count,
                affected_pages=[from_index, to_index],
                error_message=str(e),
            )

    def rotate_pages(
        self, doc_handle: Any, page_indices: list[int], angle: int
    ) -> PageOperationResult:
        """Rotate selected pages by the given angle.

        Modifies the PDF /Rotate attribute (permanent, unlike view rotation).

        Args:
            doc_handle: A pymupdf.Document handle.
            page_indices: Zero-based indices of pages to rotate.
            angle: Rotation angle — must be 90, 180, or 270.

        Returns:
            PageOperationResult indicating success or failure.
        """
        if angle not in _VALID_ANGLES:
            return PageOperationResult(
                operation=PageOperation.ROTATE,
                success=False,
                new_page_count=doc_handle.page_count,
                affected_pages=page_indices,
                error_message=(
                    f"Invalid angle {angle}. Must be 90, 180, or 270."
                ),
            )

        try:
            for idx in page_indices:
                page = doc_handle[idx]
                new_rotation = (page.rotation + angle) % 360
                page.set_rotation(new_rotation)
            logger.debug(
                "Rotated pages %s by %d degrees", page_indices, angle
            )
            return PageOperationResult(
                operation=PageOperation.ROTATE,
                success=True,
                new_page_count=doc_handle.page_count,
                affected_pages=page_indices,
            )
        except Exception as e:
            logger.warning(
                "Failed to rotate pages %s: %s", page_indices, e
            )
            return PageOperationResult(
                operation=PageOperation.ROTATE,
                success=False,
                new_page_count=doc_handle.page_count,
                affected_pages=page_indices,
                error_message=str(e),
            )

    def insert_pages_from(
        self, doc_handle: Any, source_path: Path, insert_index: int
    ) -> PageOperationResult:
        """Insert all pages from a source PDF at the given position.

        Args:
            doc_handle: A pymupdf.Document handle (target).
            source_path: Path to the source PDF file.
            insert_index: Zero-based position to insert pages.

        Returns:
            PageOperationResult indicating success or failure.
        """
        original_count = doc_handle.page_count
        try:
            source_doc = pymupdf.open(str(source_path))
        except Exception as e:
            logger.warning(
                "Failed to open source PDF %s: %s", source_path, e
            )
            return PageOperationResult(
                operation=PageOperation.INSERT,
                success=False,
                new_page_count=original_count,
                affected_pages=[],
                error_message=(
                    f"Could not insert pages from {source_path.name}. {e}"
                ),
            )

        try:
            source_count = source_doc.page_count
            doc_handle.insert_pdf(
                source_doc,
                from_page=0,
                to_page=source_count - 1,
                start_at=insert_index,
            )
            source_doc.close()
            new_count = doc_handle.page_count
            affected = list(range(insert_index, insert_index + source_count))
            logger.debug(
                "Inserted %d pages from %s at index %d",
                source_count,
                source_path.name,
                insert_index,
            )
            return PageOperationResult(
                operation=PageOperation.INSERT,
                success=True,
                new_page_count=new_count,
                affected_pages=affected,
            )
        except Exception as e:
            source_doc.close()
            logger.warning(
                "Failed to insert pages from %s: %s", source_path, e
            )
            return PageOperationResult(
                operation=PageOperation.INSERT,
                success=False,
                new_page_count=doc_handle.page_count,
                affected_pages=[],
                error_message=(
                    f"Could not insert pages from {source_path.name}. {e}"
                ),
            )

    def render_thumbnail(
        self, doc_handle: Any, page_index: int, width: int = 150
    ) -> QPixmap:
        """Render a page at thumbnail resolution.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            width: Target thumbnail width in pixels.

        Returns:
            QPixmap with the rendered thumbnail.
        """
        page = doc_handle[page_index]
        zoom = width / page.rect.width
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        image = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format.Format_RGB888,
        )
        # Deep copy — QImage references pix.samples buffer
        return QPixmap.fromImage(image.copy())

    def get_page_count(self, doc_handle: Any) -> int:
        """Return the document page count.

        Args:
            doc_handle: A pymupdf.Document handle.

        Returns:
            Number of pages in the document.
        """
        return doc_handle.page_count
```

---

## Task 3: PageManagerPanel View (Replace Stub)

### RED — Write failing tests

**File: `tests/test_page_manager_panel.py`**

```python
"""Tests for PageManagerPanel — page management dock widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from k_pdf.views.page_manager_panel import PageManagerPanel


class TestPageManagerPanelThumbnails:
    def test_set_thumbnails_populates_grid(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        pixmaps = [QPixmap(100, 130) for _ in range(5)]
        panel.set_thumbnails(pixmaps)
        assert panel._thumbnail_list.count() == 5

    def test_set_thumbnails_labels(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        pixmaps = [QPixmap(100, 130) for _ in range(3)]
        panel.set_thumbnails(pixmaps)
        item = panel._thumbnail_list.item(0)
        assert item is not None
        assert "Page 1" in item.text()

    def test_set_thumbnails_clears_old(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.set_thumbnails([QPixmap(100, 130) for _ in range(5)])
        panel.set_thumbnails([QPixmap(100, 130) for _ in range(2)])
        assert panel._thumbnail_list.count() == 2

    def test_update_thumbnail_replaces_single(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.set_thumbnails([QPixmap(100, 130) for _ in range(3)])
        new_pixmap = QPixmap(100, 130)
        panel.update_thumbnail(1, new_pixmap)
        assert panel._thumbnail_list.count() == 3  # count unchanged

    def test_get_selected_pages_empty(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.set_thumbnails([QPixmap(100, 130) for _ in range(3)])
        assert panel.get_selected_pages() == []

    def test_get_selected_pages_single(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.set_thumbnails([QPixmap(100, 130) for _ in range(3)])
        item = panel._thumbnail_list.item(1)
        assert item is not None
        item.setSelected(True)
        assert panel.get_selected_pages() == [1]

    def test_get_selected_pages_multi(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.set_thumbnails([QPixmap(100, 130) for _ in range(5)])
        for i in [0, 2, 4]:
            item = panel._thumbnail_list.item(i)
            assert item is not None
            item.setSelected(True)
        assert panel.get_selected_pages() == [0, 2, 4]


class TestPageManagerPanelSignals:
    def test_rotate_left_signal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        with qtbot.waitSignal(panel.rotate_left_clicked, timeout=1000):
            panel._rotate_left_action.trigger()

    def test_rotate_right_signal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        with qtbot.waitSignal(panel.rotate_right_clicked, timeout=1000):
            panel._rotate_right_action.trigger()

    def test_delete_signal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        with qtbot.waitSignal(panel.delete_clicked, timeout=1000):
            panel._delete_action.trigger()

    def test_add_signal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        with qtbot.waitSignal(panel.add_clicked, timeout=1000):
            panel._add_action.trigger()


class TestPageManagerPanelProgress:
    def test_show_progress(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.show_progress("Deleting pages...")
        assert panel._progress_bar.isVisible()

    def test_hide_progress(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.show_progress("Working...")
        panel.hide_progress()
        assert not panel._progress_bar.isVisible()


class TestPageManagerPanelPageCount:
    def test_set_page_count_label(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        panel.set_page_count_label(42)
        assert "42" in panel._page_count_label.text()

    def test_no_document_state(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = PageManagerPanel()
        qtbot.addWidget(panel)
        # Initially should show no-document message
        assert "No document" in panel._page_count_label.text()
```

### GREEN — Implement PageManagerPanel

**File: `k_pdf/views/page_manager_panel.py`**

```python
"""Page management panel.

QDockWidget containing a thumbnail grid with multi-select support
and toolbar with page manipulation actions. F7 toggle visibility.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger("k_pdf.views.page_manager_panel")


class PageManagerPanel(QDockWidget):
    """Left-docked page management panel with thumbnail grid and toolbar.

    Provides multi-select thumbnails and actions for rotating, deleting,
    adding, and reordering pages. Page rotation here modifies the PDF
    (unlike Feature 5 view-only rotation).
    """

    rotate_left_clicked = Signal()
    rotate_right_clicked = Signal()
    delete_clicked = Signal()
    add_clicked = Signal()
    page_moved = Signal(int, int)  # (from_index, to_index)
    selection_changed = Signal(list)  # list of selected indices

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the page manager panel."""
        super().__init__("Page Manager", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setMinimumWidth(180)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Page count label
        self._page_count_label = QLabel("No document open")
        self._page_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._page_count_label)

        # Toolbar
        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)

        self._rotate_left_action = QAction("Rotate Left (modifies file)", self)
        self._rotate_left_action.setToolTip(
            "Rotate selected pages 90 degrees counter-clockwise (modifies PDF)"
        )
        self._rotate_left_action.triggered.connect(self.rotate_left_clicked.emit)
        self._toolbar.addAction(self._rotate_left_action)

        self._rotate_right_action = QAction("Rotate Right (modifies file)", self)
        self._rotate_right_action.setToolTip(
            "Rotate selected pages 90 degrees clockwise (modifies PDF)"
        )
        self._rotate_right_action.triggered.connect(self.rotate_right_clicked.emit)
        self._toolbar.addAction(self._rotate_right_action)

        self._delete_action = QAction("Delete Pages", self)
        self._delete_action.setToolTip("Delete selected pages from the document")
        self._delete_action.triggered.connect(self.delete_clicked.emit)
        self._toolbar.addAction(self._delete_action)

        self._add_action = QAction("Add Pages", self)
        self._add_action.setToolTip("Insert pages from another PDF")
        self._add_action.triggered.connect(self.add_clicked.emit)
        self._toolbar.addAction(self._add_action)

        layout.addWidget(self._toolbar)

        # Thumbnail grid
        self._thumbnail_list = QListWidget()
        self._thumbnail_list.setViewMode(QListWidget.ViewMode.IconMode)
        self._thumbnail_list.setFlow(QListWidget.Flow.TopToBottom)
        self._thumbnail_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._thumbnail_list.setWrapping(False)
        self._thumbnail_list.setSpacing(4)
        self._thumbnail_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._thumbnail_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self._thumbnail_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._thumbnail_list.setIconSize(self._thumbnail_list.iconSize())
        self._thumbnail_list.itemSelectionChanged.connect(self._on_selection_changed)
        self._thumbnail_list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self._thumbnail_list)

        # Progress bar (hidden by default)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        self.setWidget(container)

    def set_thumbnails(self, pixmaps: list[QPixmap]) -> None:
        """Populate the thumbnail grid with page thumbnails.

        Args:
            pixmaps: List of QPixmap thumbnails, one per page.
        """
        self._thumbnail_list.clear()
        for i, pixmap in enumerate(pixmaps):
            item = QListWidgetItem(QIcon(pixmap), f"Page {i + 1}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._thumbnail_list.addItem(item)

    def update_thumbnail(self, page_index: int, pixmap: QPixmap) -> None:
        """Replace a single thumbnail after rotation or other change.

        Args:
            page_index: Zero-based page index.
            pixmap: New thumbnail pixmap.
        """
        if 0 <= page_index < self._thumbnail_list.count():
            item = self._thumbnail_list.item(page_index)
            if item is not None:
                item.setIcon(QIcon(pixmap))

    def get_selected_pages(self) -> list[int]:
        """Return zero-based indices of selected thumbnails.

        Returns:
            Sorted list of selected page indices.
        """
        indices: list[int] = []
        for item in self._thumbnail_list.selectedItems():
            data = item.data(Qt.ItemDataRole.UserRole)
            if data is not None:
                indices.append(int(data))
        return sorted(indices)

    def show_progress(self, message: str) -> None:
        """Show the progress bar with the given message.

        Args:
            message: Description of the current operation.
        """
        self._progress_bar.setFormat(message)
        self._progress_bar.show()

    def hide_progress(self) -> None:
        """Hide the progress bar."""
        self._progress_bar.hide()

    def set_page_count_label(self, count: int) -> None:
        """Update the panel header with total page count.

        Args:
            count: Total number of pages.
        """
        self._page_count_label.setText(f"{count} page{'s' if count != 1 else ''}")

    def set_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable all toolbar buttons.

        Args:
            enabled: True to enable, False to disable.
        """
        self._rotate_left_action.setEnabled(enabled)
        self._rotate_right_action.setEnabled(enabled)
        self._delete_action.setEnabled(enabled)
        self._add_action.setEnabled(enabled)

    def _on_selection_changed(self) -> None:
        """Emit selection_changed with current selected indices."""
        self.selection_changed.emit(self.get_selected_pages())

    def _on_rows_moved(self) -> None:
        """Handle internal drag-drop reorder.

        After Qt moves the row, we read the new order and emit page_moved.
        """
        # Rebuild page index data from new order
        for i in range(self._thumbnail_list.count()):
            item = self._thumbnail_list.item(i)
            if item is not None:
                old_index = item.data(Qt.ItemDataRole.UserRole)
                if old_index is not None and int(old_index) != i:
                    self.page_moved.emit(int(old_index), i)
                    # Update stored index
                    item.setData(Qt.ItemDataRole.UserRole, i)
```

---

## Task 4: PageManagementPresenter (Replace Stub)

### RED — Write failing tests

**File: `tests/test_page_management_presenter.py`**

```python
"""Tests for PageManagementPresenter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf
import pytest
from PySide6.QtGui import QPixmap

from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.core.page_model import PageOperation, PageOperationResult
from k_pdf.presenters.page_management_presenter import PageManagementPresenter
from k_pdf.services.page_engine import PageEngine


@pytest.fixture
def mock_tab_manager() -> MagicMock:
    manager = MagicMock()
    manager.active_session_id = "test-session"
    manager.get_active_presenter.return_value = MagicMock()
    return manager


@pytest.fixture
def mock_panel() -> MagicMock:
    panel = MagicMock()
    panel.get_selected_pages.return_value = []
    return panel


@pytest.fixture
def mock_engine() -> MagicMock:
    return MagicMock(spec=PageEngine)


@pytest.fixture
def sample_model(tmp_path: Path) -> DocumentModel:
    path = tmp_path / "test.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1}")
    doc.save(str(path))
    doc.close()

    doc_handle = pymupdf.open(str(path))
    metadata = DocumentMetadata(
        file_path=path,
        page_count=3,
        title=None,
        author=None,
        has_forms=False,
        has_outline=False,
        has_javascript=False,
        is_encrypted=False,
        file_size_bytes=path.stat().st_size,
    )
    pages = [
        PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
        for i in range(3)
    ]
    return DocumentModel(
        file_path=path,
        doc_handle=doc_handle,
        metadata=metadata,
        pages=pages,
    )


class TestRotatePages:
    def test_rotate_calls_engine(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        mock_engine.rotate_pages.return_value = PageOperationResult(
            operation=PageOperation.ROTATE,
            success=True,
            new_page_count=3,
            affected_pages=[0, 1],
        )
        mock_engine.render_thumbnail.return_value = QPixmap(100, 130)

        presenter.rotate_pages([0, 1], 90)

        mock_engine.rotate_pages.assert_called_once_with(model.doc_handle, [0, 1], 90)

    def test_rotate_sets_dirty(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        mock_engine.rotate_pages.return_value = PageOperationResult(
            operation=PageOperation.ROTATE,
            success=True,
            new_page_count=3,
            affected_pages=[0],
        )
        mock_engine.render_thumbnail.return_value = QPixmap(100, 130)

        presenter.rotate_pages([0], 90)

        assert model.dirty is True


class TestDeletePages:
    def test_delete_calls_engine_on_confirm(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        mock_engine.delete_pages.return_value = PageOperationResult(
            operation=PageOperation.DELETE,
            success=True,
            new_page_count=2,
            affected_pages=[1],
        )
        mock_engine.get_page_count.return_value = 2
        mock_engine.render_thumbnail.return_value = QPixmap(100, 130)

        with patch(
            "k_pdf.presenters.page_management_presenter.QMessageBox"
        ) as mock_msgbox:
            mock_msgbox.StandardButton.Yes = 1
            mock_msgbox.StandardButton.No = 0
            mock_msgbox.question.return_value = 1  # Yes

            presenter.delete_pages([1])

        mock_engine.delete_pages.assert_called_once_with(model.doc_handle, [1])

    def test_delete_blocked_when_all_pages(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        doc_presenter = mock_tab_manager.get_active_presenter.return_value
        doc_presenter.model = model

        mock_engine.delete_pages.return_value = PageOperationResult(
            operation=PageOperation.DELETE,
            success=False,
            new_page_count=3,
            affected_pages=[0, 1, 2],
            error_message="Cannot delete all pages. A PDF must contain at least one page.",
        )

        with patch(
            "k_pdf.presenters.page_management_presenter.QMessageBox"
        ) as mock_msgbox:
            mock_msgbox.StandardButton.Yes = 1
            mock_msgbox.StandardButton.No = 0
            mock_msgbox.question.return_value = 1  # Yes

            presenter.delete_pages([0, 1, 2])

        assert model.dirty is False


class TestInsertPages:
    def test_insert_calls_engine(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        mock_engine.insert_pages_from.return_value = PageOperationResult(
            operation=PageOperation.INSERT,
            success=True,
            new_page_count=5,
            affected_pages=[2, 3],
        )
        mock_engine.get_page_count.return_value = 5
        mock_engine.render_thumbnail.return_value = QPixmap(100, 130)

        presenter.insert_pages(Path("/fake/source.pdf"), 2)

        mock_engine.insert_pages_from.assert_called_once()


class TestMovePage:
    def test_move_calls_engine(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        mock_engine.move_page.return_value = PageOperationResult(
            operation=PageOperation.MOVE,
            success=True,
            new_page_count=3,
            affected_pages=[0, 2],
        )
        mock_engine.get_page_count.return_value = 3
        mock_engine.render_thumbnail.return_value = QPixmap(100, 130)

        presenter.move_page(0, 2)

        mock_engine.move_page.assert_called_once_with(model.doc_handle, 0, 2)

    def test_move_same_position_is_noop(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        model.dirty = False
        mock_tab_manager.get_active_presenter.return_value.model = model

        presenter.move_page(2, 2)

        mock_engine.move_page.assert_not_called()
        assert model.dirty is False


class TestTabLifecycle:
    def test_on_tab_switched_refreshes_panel(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        model = MagicMock()
        model.doc_handle = MagicMock()
        mock_tab_manager.get_active_presenter.return_value.model = model
        mock_engine.get_page_count.return_value = 3
        mock_engine.render_thumbnail.return_value = QPixmap(100, 130)

        presenter.on_tab_switched("new-session")

        mock_panel.set_thumbnails.assert_called_once()
        mock_panel.set_buttons_enabled.assert_called_with(True)

    def test_on_tab_closed_clears_panel(
        self, mock_tab_manager: MagicMock, mock_panel: MagicMock, mock_engine: MagicMock
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=mock_engine,
            tab_manager=mock_tab_manager,
            panel=mock_panel,
        )
        mock_tab_manager.get_active_presenter.return_value = None

        presenter.on_tab_closed("closed-session")

        mock_panel.set_thumbnails.assert_called_with([])
        mock_panel.set_buttons_enabled.assert_called_with(False)
```

### GREEN — Implement PageManagementPresenter

**File: `k_pdf/presenters/page_management_presenter.py`**

```python
"""Page management presenter.

Coordinates page operations between the PageManagerPanel view
and PageEngine service. Manages dirty flag and thumbnail refresh.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QMessageBox

from k_pdf.core.page_model import PageOperationResult
from k_pdf.services.page_engine import PageEngine

logger = logging.getLogger("k_pdf.presenters.page_management_presenter")


class PageManagementPresenter(QObject):
    """Manages page operations, dirty flag, and thumbnail refresh."""

    dirty_changed = Signal(bool)
    pages_changed = Signal()
    operation_started = Signal(str)
    operation_finished = Signal()

    def __init__(
        self,
        page_engine: PageEngine,
        tab_manager: Any,
        panel: Any,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the page management presenter.

        Args:
            page_engine: The PageEngine service for PDF operations.
            tab_manager: The TabManager for accessing active tab state.
            panel: The PageManagerPanel view.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._page_engine = page_engine
        self._tab_manager = tab_manager
        self._panel = panel

    def _get_active_model(self) -> Any | None:
        """Return the active tab's DocumentModel, or None."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is None or presenter.model is None:
            return None
        return presenter.model

    def rotate_pages(self, page_indices: list[int], angle: int) -> None:
        """Rotate selected pages and update thumbnails.

        Args:
            page_indices: Zero-based indices of pages to rotate.
            angle: Rotation angle (90 for right, 270 for left).
        """
        model = self._get_active_model()
        if model is None or not page_indices:
            return

        result = self._page_engine.rotate_pages(
            model.doc_handle, page_indices, angle
        )
        if result.success:
            model.dirty = True
            self.dirty_changed.emit(True)
            self._update_thumbnails_for(model.doc_handle, result.affected_pages)
            self.pages_changed.emit()

    def delete_pages(self, page_indices: list[int]) -> None:
        """Delete selected pages after confirmation.

        Args:
            page_indices: Zero-based indices of pages to delete.
        """
        model = self._get_active_model()
        if model is None or not page_indices:
            return

        count = len(page_indices)
        reply = QMessageBox.question(
            None,
            "Delete Pages",
            f"Delete {count} selected page(s)? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        result = self._page_engine.delete_pages(model.doc_handle, page_indices)
        if result.success:
            model.dirty = True
            self.dirty_changed.emit(True)
            self._refresh_all_thumbnails(model.doc_handle)
            self.pages_changed.emit()
        else:
            QMessageBox.warning(
                None,
                "Cannot Delete Pages",
                result.error_message,
            )

    def insert_pages(self, source_path: Path, insert_index: int) -> None:
        """Insert pages from another PDF at the given position.

        Args:
            source_path: Path to the source PDF.
            insert_index: Zero-based insertion position.
        """
        model = self._get_active_model()
        if model is None:
            return

        result = self._page_engine.insert_pages_from(
            model.doc_handle, source_path, insert_index
        )
        if result.success:
            model.dirty = True
            self.dirty_changed.emit(True)
            self._refresh_all_thumbnails(model.doc_handle)
            self.pages_changed.emit()
        else:
            QMessageBox.warning(
                None,
                "Insert Failed",
                result.error_message,
            )

    def move_page(self, from_index: int, to_index: int) -> None:
        """Move a page to a new position.

        Args:
            from_index: Current zero-based page index.
            to_index: Target zero-based page index.
        """
        if from_index == to_index:
            return

        model = self._get_active_model()
        if model is None:
            return

        result = self._page_engine.move_page(
            model.doc_handle, from_index, to_index
        )
        if result.success:
            model.dirty = True
            self.dirty_changed.emit(True)
            self._refresh_all_thumbnails(model.doc_handle)
            self.pages_changed.emit()

    def refresh_thumbnails(self) -> None:
        """Regenerate all thumbnails from current document state."""
        model = self._get_active_model()
        if model is None:
            return
        self._refresh_all_thumbnails(model.doc_handle)

    def on_tab_switched(self, session_id: str) -> None:
        """Refresh panel for the newly active document.

        Args:
            session_id: The session ID of the new active tab.
        """
        model = self._get_active_model()
        if model is None:
            self._panel.set_thumbnails([])
            self._panel.set_buttons_enabled(False)
            self._panel.set_page_count_label(0)
            return

        self._panel.set_buttons_enabled(True)
        self._refresh_all_thumbnails(model.doc_handle)

    def on_tab_closed(self, session_id: str) -> None:
        """Clear panel if no tabs remain.

        Args:
            session_id: The session ID of the closed tab.
        """
        model = self._get_active_model()
        if model is None:
            self._panel.set_thumbnails([])
            self._panel.set_buttons_enabled(False)
            self._panel.set_page_count_label(0)

    def _refresh_all_thumbnails(self, doc_handle: Any) -> None:
        """Regenerate all thumbnails and update the panel.

        Args:
            doc_handle: The pymupdf.Document handle.
        """
        count = self._page_engine.get_page_count(doc_handle)
        pixmaps: list[QPixmap] = []
        for i in range(count):
            pixmaps.append(self._page_engine.render_thumbnail(doc_handle, i))
        self._panel.set_thumbnails(pixmaps)
        self._panel.set_page_count_label(count)

    def _update_thumbnails_for(
        self, doc_handle: Any, page_indices: list[int]
    ) -> None:
        """Update thumbnails for specific pages.

        Args:
            doc_handle: The pymupdf.Document handle.
            page_indices: Pages to re-render.
        """
        for idx in page_indices:
            pixmap = self._page_engine.render_thumbnail(doc_handle, idx)
            self._panel.update_thumbnail(idx, pixmap)
```

---

## Task 5: MainWindow — Add Page Manager Dock + F7 Toggle

### RED — Add test to existing test_views.py

Add to `tests/test_views.py`:

```python
class TestMainWindowPageManager:
    def test_page_manager_panel_exists(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from k_pdf.views.main_window import MainWindow
        from k_pdf.views.page_manager_panel import PageManagerPanel
        w = MainWindow()
        qtbot.addWidget(w)
        assert isinstance(w.page_manager_panel, PageManagerPanel)

    def test_page_manager_panel_initially_hidden(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from k_pdf.views.main_window import MainWindow
        w = MainWindow()
        qtbot.addWidget(w)
        assert not w.page_manager_panel.isVisible()
```

### GREEN — Modify MainWindow

Add to `k_pdf/views/main_window.py`:
- Import `PageManagerPanel`
- Create `_page_manager_panel` dock widget in `__init__`
- Add `page_manager_panel` property
- Add "Page &Manager" toggle in View menu with F7 shortcut

---

## Task 6: KPdfApp — Wire All Signals + Integration Tests

### RED — Write integration tests

**File: `tests/test_page_management_integration.py`**

```python
"""Integration tests for Feature 9: Page Management."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf
import pytest
from PySide6.QtGui import QPixmap

from k_pdf.core.page_model import PageOperation
from k_pdf.presenters.page_management_presenter import PageManagementPresenter
from k_pdf.services.page_engine import PageEngine


@pytest.fixture
def multi_page_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "multi.pdf"
    doc = pymupdf.open()
    for i in range(5):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1} content")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def source_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "source.pdf"
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Source {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def engine() -> PageEngine:
    return PageEngine()


@pytest.fixture
def panel() -> MagicMock:
    p = MagicMock()
    p.get_selected_pages.return_value = []
    return p


@pytest.fixture
def tab_manager_with_doc(multi_page_pdf: Path) -> MagicMock:
    from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo

    doc_handle = pymupdf.open(str(multi_page_pdf))
    metadata = DocumentMetadata(
        file_path=multi_page_pdf,
        page_count=5,
        title=None,
        author=None,
        has_forms=False,
        has_outline=False,
        has_javascript=False,
        is_encrypted=False,
        file_size_bytes=multi_page_pdf.stat().st_size,
    )
    pages = [
        PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
        for i in range(5)
    ]
    model = DocumentModel(
        file_path=multi_page_pdf,
        doc_handle=doc_handle,
        metadata=metadata,
        pages=pages,
    )
    doc_presenter = MagicMock()
    doc_presenter.model = model
    manager = MagicMock()
    manager.active_session_id = model.session_id
    manager.get_active_presenter.return_value = doc_presenter
    manager._model = model  # for test access
    return manager


class TestDeleteSinglePage:
    def test_delete_single_page(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        with patch(
            "k_pdf.presenters.page_management_presenter.QMessageBox"
        ) as mock_msgbox:
            mock_msgbox.StandardButton.Yes = 1
            mock_msgbox.StandardButton.No = 0
            mock_msgbox.question.return_value = 1

            presenter.delete_pages([2])

        assert model.doc_handle.page_count == 4
        assert model.dirty is True


class TestDeleteMultiplePages:
    def test_delete_multiple_pages(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        with patch(
            "k_pdf.presenters.page_management_presenter.QMessageBox"
        ) as mock_msgbox:
            mock_msgbox.StandardButton.Yes = 1
            mock_msgbox.StandardButton.No = 0
            mock_msgbox.question.return_value = 1

            presenter.delete_pages([0, 2, 4])

        assert model.doc_handle.page_count == 2
        assert model.dirty is True


class TestDeleteAllPagesBlocked:
    def test_delete_all_pages_blocked(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        with patch(
            "k_pdf.presenters.page_management_presenter.QMessageBox"
        ) as mock_msgbox:
            mock_msgbox.StandardButton.Yes = 1
            mock_msgbox.StandardButton.No = 0
            mock_msgbox.question.return_value = 1

            presenter.delete_pages([0, 1, 2, 3, 4])

        assert model.doc_handle.page_count == 5  # unchanged
        assert model.dirty is False


class TestRotatePageLeft:
    def test_rotate_page_left(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        presenter.rotate_pages([0], 270)

        assert model.doc_handle[0].rotation == 270
        assert model.dirty is True


class TestRotatePageRight:
    def test_rotate_page_right(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        presenter.rotate_pages([0], 90)

        assert model.doc_handle[0].rotation == 90
        assert model.dirty is True


class TestRotateMultiplePages:
    def test_rotate_multiple_pages(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        presenter.rotate_pages([0, 1, 2], 90)

        for i in [0, 1, 2]:
            assert model.doc_handle[i].rotation == 90
        assert model.dirty is True


class TestAddPagesFromPdf:
    def test_add_pages(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
        source_pdf: Path,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model

        presenter.insert_pages(source_pdf, 2)

        assert model.doc_handle.page_count == 7
        assert model.dirty is True


class TestDragReorder:
    def test_move_page(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model
        original_p3_text = model.doc_handle[3].get_text("text").strip()

        presenter.move_page(3, 1)

        assert model.doc_handle[1].get_text("text").strip() == original_p3_text
        assert model.dirty is True


class TestDirtyFlagOnPageOperation:
    def test_dirty_after_rotate(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )
        model = tab_manager_with_doc.get_active_presenter().model
        assert model.dirty is False

        presenter.rotate_pages([0], 90)
        assert model.dirty is True


class TestPanelEmptyNoDocument:
    def test_panel_empty_no_document(
        self, panel: MagicMock, engine: PageEngine
    ) -> None:
        manager = MagicMock()
        manager.get_active_presenter.return_value = None

        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=manager,
            panel=panel,
        )
        presenter.on_tab_switched("any-session")

        panel.set_thumbnails.assert_called_with([])
        panel.set_buttons_enabled.assert_called_with(False)


class TestTabSwitchRefreshesPanel:
    def test_tab_switch_refreshes(
        self,
        tab_manager_with_doc: MagicMock,
        panel: MagicMock,
        engine: PageEngine,
    ) -> None:
        presenter = PageManagementPresenter(
            page_engine=engine,
            tab_manager=tab_manager_with_doc,
            panel=panel,
        )

        presenter.on_tab_switched("new-session")

        panel.set_thumbnails.assert_called_once()
        args = panel.set_thumbnails.call_args[0][0]
        assert len(args) == 5  # 5 page thumbnails
```

### GREEN — Wire in KPdfApp

Add to `k_pdf/app.py`:
- Import `PageEngine`, `PageManagementPresenter`
- Create instances in `__init__`
- Add `page_management_presenter` property
- Wire signals in `_connect_signals`

---

## Task 7: Mypy Overrides + CLAUDE.md Update

- Add mypy overrides for `k_pdf/services/page_engine`, `k_pdf/presenters/page_management_presenter`, `k_pdf/views/page_manager_panel`
- Update `CLAUDE.md` "Current State" with Feature 9 completion details
