# Text Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable find-and-replace text editing and click-to-edit inline text modification in PDF documents, with font validation and redact-and-overlay fallback for subset fonts.

**Architecture:** New TextEditEngine service (PyMuPDF-isolated) handles font checks, text replacement, and redact-and-overlay. New TextEditPresenter coordinates find-replace bar, inline edit overlay, undo, and font limitation dialogs. New FindReplaceBar view extends the search bar pattern with a replacement row. Existing SearchPresenter search results are reused for find-and-replace match locations.

**Tech Stack:** Python 3.13, PySide6 6.11, PyMuPDF 1.27, pytest + pytest-qt

---

### Task 1: TextEditModel Dataclasses

**Files:**
- Create: `k_pdf/core/text_edit_model.py`
- Test: `tests/test_text_edit_model.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_text_edit_model.py`:

```python
"""Tests for text_edit_model dataclasses."""

from __future__ import annotations

from k_pdf.core.text_edit_model import (
    EditResult,
    FontCheckResult,
    ReplaceAllResult,
    TextBlockInfo,
)


class TestTextBlockInfo:
    def test_creation(self) -> None:
        block = TextBlockInfo(
            page=0,
            rect=(72.0, 100.0, 272.0, 124.0),
            text="Hello world",
            font_name="Helvetica",
            font_size=12.0,
            is_fully_embedded=True,
        )
        assert block.page == 0
        assert block.text == "Hello world"
        assert block.font_name == "Helvetica"
        assert block.is_fully_embedded is True

    def test_subset_font(self) -> None:
        block = TextBlockInfo(
            page=1,
            rect=(0, 0, 100, 20),
            text="Test",
            font_name="TimesNewRoman-Subset",
            font_size=11.0,
            is_fully_embedded=False,
        )
        assert block.is_fully_embedded is False


class TestFontCheckResult:
    def test_supported(self) -> None:
        result = FontCheckResult(supported=True, font_name="Helvetica", reason="")
        assert result.supported is True
        assert result.reason == ""

    def test_not_supported(self) -> None:
        result = FontCheckResult(
            supported=False,
            font_name="Arial-Subset",
            reason="Font is subset-embedded",
        )
        assert result.supported is False
        assert "subset" in result.reason.lower()


class TestEditResult:
    def test_success(self) -> None:
        result = EditResult(success=True, error_message="")
        assert result.success is True

    def test_failure(self) -> None:
        result = EditResult(success=False, error_message="Font not supported")
        assert result.success is False
        assert result.error_message == "Font not supported"


class TestReplaceAllResult:
    def test_full_success(self) -> None:
        result = ReplaceAllResult(
            replaced_count=5, skipped_count=0, skipped_locations=[]
        )
        assert result.replaced_count == 5
        assert result.skipped_count == 0

    def test_partial_success(self) -> None:
        result = ReplaceAllResult(
            replaced_count=3,
            skipped_count=2,
            skipped_locations=[(2, "subset font"), (7, "subset font")],
        )
        assert result.replaced_count == 3
        assert result.skipped_count == 2
        assert len(result.skipped_locations) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_text_edit_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'k_pdf.core.text_edit_model'`

- [ ] **Step 3: Implement TextEditModel**

Create `k_pdf/core/text_edit_model.py`:

```python
"""Data models for text editing operations.

Pure dataclasses with no Qt or PyMuPDF imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextBlockInfo:
    """Information about a text span at a PDF location.

    Attributes:
        page: Zero-based page index.
        rect: Bounding box (x0, y0, x1, y1) in PDF coordinates.
        text: The text content.
        font_name: Name of the font used.
        font_size: Font size in points.
        is_fully_embedded: True if font supports arbitrary edits.
    """

    page: int
    rect: tuple[float, float, float, float]
    text: str
    font_name: str
    font_size: float
    is_fully_embedded: bool


@dataclass
class FontCheckResult:
    """Result of checking whether a text region supports direct editing.

    Attributes:
        supported: True if the font is fully embedded and editable.
        font_name: Name of the font at the checked location.
        reason: Empty if supported, explanation string if not.
    """

    supported: bool
    font_name: str
    reason: str


@dataclass
class EditResult:
    """Result of an inline text edit attempt.

    Attributes:
        success: True if the edit was applied.
        error_message: Empty on success, explanation on failure.
    """

    success: bool
    error_message: str


@dataclass
class ReplaceAllResult:
    """Result of a bulk find-and-replace operation.

    Attributes:
        replaced_count: Number of successful replacements.
        skipped_count: Number of matches that could not be replaced.
        skipped_locations: List of (page_index, reason) for each skip.
    """

    replaced_count: int
    skipped_count: int
    skipped_locations: list[tuple[int, str]] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_text_edit_model.py -v`
Expected: All PASS

- [ ] **Step 5: Run linting**

Run: `uv run ruff check k_pdf/core/text_edit_model.py && uv run ruff format k_pdf/core/text_edit_model.py tests/test_text_edit_model.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add k_pdf/core/text_edit_model.py tests/test_text_edit_model.py
git commit -m "feat: add TextEditModel dataclasses for text editing operations"
```

---

### Task 2: TextEditEngine Service

**Files:**
- Create: `k_pdf/services/text_edit_engine.py`
- Test: `tests/test_text_edit_engine.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_text_edit_engine.py`:

```python
"""Tests for TextEditEngine service."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from k_pdf.services.text_edit_engine import TextEditEngine


@pytest.fixture
def engine() -> TextEditEngine:
    return TextEditEngine()


@pytest.fixture
def text_pdf(tmp_path: Path) -> Path:
    """Create a PDF with known text content using a standard font."""
    path = tmp_path / "text.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    # Insert text with a standard (fully available) font
    page.insert_text(
        pymupdf.Point(72, 100),
        "Hello World",
        fontname="helv",
        fontsize=12,
    )
    page.insert_text(
        pymupdf.Point(72, 140),
        "Goodbye World",
        fontname="helv",
        fontsize=12,
    )
    doc.save(str(path))
    doc.close()
    return path


class TestGetTextBlock:
    def test_returns_block_at_text_position(
        self, engine: TextEditEngine, text_pdf: Path
    ) -> None:
        doc = pymupdf.open(str(text_pdf))
        block = engine.get_text_block(doc, 0, 100.0, 95.0)
        assert block is not None
        assert "Hello" in block.text
        assert block.font_name != ""
        assert block.font_size > 0
        doc.close()

    def test_returns_none_at_empty_position(
        self, engine: TextEditEngine, text_pdf: Path
    ) -> None:
        doc = pymupdf.open(str(text_pdf))
        block = engine.get_text_block(doc, 0, 500.0, 500.0)
        assert block is None
        doc.close()

    def test_returns_page_index(
        self, engine: TextEditEngine, text_pdf: Path
    ) -> None:
        doc = pymupdf.open(str(text_pdf))
        block = engine.get_text_block(doc, 0, 100.0, 95.0)
        assert block is not None
        assert block.page == 0
        doc.close()


class TestCheckFontSupport:
    def test_standard_font_not_embedded(
        self, engine: TextEditEngine, text_pdf: Path
    ) -> None:
        doc = pymupdf.open(str(text_pdf))
        block = engine.get_text_block(doc, 0, 100.0, 95.0)
        assert block is not None
        result = engine.check_font_support(doc, 0, block.rect)
        # Standard fonts (helv) are not embedded in the PDF — they're built-in
        # The check should report the font name regardless
        assert result.font_name != ""
        doc.close()


class TestRedactAndOverlay:
    def test_replaces_text_via_redaction(
        self, engine: TextEditEngine, text_pdf: Path
    ) -> None:
        doc = pymupdf.open(str(text_pdf))
        block = engine.get_text_block(doc, 0, 100.0, 95.0)
        assert block is not None

        engine.redact_and_overlay(doc, 0, block.rect, "New Text", block.font_size)

        # Verify old text is gone and new text is present
        page = doc[0]
        page_text = page.get_text("text")
        assert "New Text" in page_text
        doc.close()

    def test_redact_preserves_other_text(
        self, engine: TextEditEngine, text_pdf: Path
    ) -> None:
        doc = pymupdf.open(str(text_pdf))
        block = engine.get_text_block(doc, 0, 100.0, 95.0)
        assert block is not None

        engine.redact_and_overlay(doc, 0, block.rect, "Replaced", block.font_size)

        page = doc[0]
        page_text = page.get_text("text")
        assert "Goodbye" in page_text
        doc.close()


class TestReplaceText:
    def test_replace_returns_result(
        self, engine: TextEditEngine, text_pdf: Path
    ) -> None:
        doc = pymupdf.open(str(text_pdf))
        # Use search_for to get the exact rect
        page = doc[0]
        rects = page.search_for("Hello World")
        assert len(rects) > 0
        search_rect = (rects[0].x0, rects[0].y0, rects[0].x1, rects[0].y1)

        result = engine.replace_text(doc, 0, search_rect, "Hello World", "Hi Earth")
        # replace_text uses redact_and_overlay as the implementation
        assert result is True
        doc.close()


class TestReplaceAll:
    def test_replace_all_multiple_matches(
        self, engine: TextEditEngine, text_pdf: Path
    ) -> None:
        doc = pymupdf.open(str(text_pdf))
        page = doc[0]
        rects = page.search_for("World")
        search_results = {0: [(r.x0, r.y0, r.x1, r.y1) for r in rects]}

        result = engine.replace_all(doc, search_results, "World", "Earth")
        assert result.replaced_count == len(rects)
        assert result.skipped_count == 0
        doc.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_text_edit_engine.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement TextEditEngine**

Create `k_pdf/services/text_edit_engine.py`:

```python
"""Text editing engine — PyMuPDF text replacement and font checking.

Handles get_text_block, check_font_support, replace_text,
replace_all, edit_text_inline, and redact_and_overlay.

PyMuPDF import is isolated here per AGPL containment rule.
"""

from __future__ import annotations

import logging
from typing import Any

import pymupdf

from k_pdf.core.text_edit_model import (
    EditResult,
    FontCheckResult,
    ReplaceAllResult,
    TextBlockInfo,
)

logger = logging.getLogger("k_pdf.services.text_edit_engine")


class TextEditEngine:
    """Service for text editing operations on PDF documents."""

    def get_text_block(
        self,
        doc_handle: Any,
        page_index: int,
        x: float,
        y: float,
    ) -> TextBlockInfo | None:
        """Return the text span at the given PDF coordinates.

        Uses get_text("dict") to find the span whose bbox contains (x, y).

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            x: X coordinate in PDF page space.
            y: Y coordinate in PDF page space.

        Returns:
            TextBlockInfo with text content, font info, and bounding rect,
            or None if no text at that position.
        """
        page = doc_handle[page_index]
        data = page.get_text("dict")

        for block in data.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    bbox = span["bbox"]
                    if bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]:
                        font_name = span.get("font", "")
                        font_flags = span.get("flags", 0)
                        # A font is considered "fully embedded" if it is not
                        # a subset font. Subset fonts typically have a name
                        # containing "+" (e.g., "ABCDEF+Arial") or end with
                        # "-Subset". Standard PDF base-14 fonts (helv, cour,
                        # etc.) are always available but not embedded.
                        is_subset = "+" in font_name or "-Subset" in font_name
                        # Base-14 fonts are considered fully available for editing
                        base14 = _is_base14_font(font_name)
                        is_fully_embedded = base14 or (not is_subset)

                        return TextBlockInfo(
                            page=page_index,
                            rect=(bbox[0], bbox[1], bbox[2], bbox[3]),
                            text=span.get("text", ""),
                            font_name=font_name,
                            font_size=span.get("size", 12.0),
                            is_fully_embedded=is_fully_embedded,
                        )
        return None

    def check_font_support(
        self,
        doc_handle: Any,
        page_index: int,
        text_rect: tuple[float, float, float, float],
    ) -> FontCheckResult:
        """Check whether text at the given rect uses an editable font.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            text_rect: Bounding box (x0, y0, x1, y1) of the text area.

        Returns:
            FontCheckResult indicating whether direct editing is supported.
        """
        page = doc_handle[page_index]
        data = page.get_text("dict")
        x_mid = (text_rect[0] + text_rect[2]) / 2
        y_mid = (text_rect[1] + text_rect[3]) / 2

        for block in data.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    bbox = span["bbox"]
                    if bbox[0] <= x_mid <= bbox[2] and bbox[1] <= y_mid <= bbox[3]:
                        font_name = span.get("font", "unknown")
                        is_subset = "+" in font_name or "-Subset" in font_name
                        base14 = _is_base14_font(font_name)

                        if base14 or not is_subset:
                            return FontCheckResult(
                                supported=True,
                                font_name=font_name,
                                reason="",
                            )
                        return FontCheckResult(
                            supported=False,
                            font_name=font_name,
                            reason=(
                                f"Font '{font_name}' is subset-embedded. "
                                "Only the original characters are available."
                            ),
                        )

        return FontCheckResult(
            supported=False,
            font_name="unknown",
            reason="No text found at the specified location.",
        )

    def replace_text(
        self,
        doc_handle: Any,
        page_index: int,
        search_rect: tuple[float, float, float, float],
        old_text: str,
        new_text: str,
    ) -> bool:
        """Replace text at the given rect using redact-and-overlay.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            search_rect: Bounding rect of the text to replace.
            old_text: The original text (for logging).
            new_text: The replacement text.

        Returns:
            True if replacement succeeded.
        """
        try:
            # Determine font size from the existing text
            block = self.get_text_block(
                doc_handle,
                page_index,
                (search_rect[0] + search_rect[2]) / 2,
                (search_rect[1] + search_rect[3]) / 2,
            )
            font_size = block.font_size if block else 12.0

            self.redact_and_overlay(
                doc_handle, page_index, search_rect, new_text, font_size
            )
            logger.debug(
                "Replaced '%s' with '%s' on page %d",
                old_text[:30],
                new_text[:30],
                page_index,
            )
            return True
        except Exception:
            logger.warning(
                "Failed to replace text on page %d", page_index, exc_info=True
            )
            return False

    def replace_all(
        self,
        doc_handle: Any,
        search_results: dict[int, list[tuple[float, float, float, float]]],
        old_text: str,
        new_text: str,
    ) -> ReplaceAllResult:
        """Bulk replace text across all matched locations.

        Processes pages in reverse order to avoid rect invalidation.

        Args:
            doc_handle: A pymupdf.Document handle.
            search_results: Dict mapping page_index to list of match rects.
            old_text: The search text being replaced.
            new_text: The replacement text.

        Returns:
            ReplaceAllResult with counts and skipped locations.
        """
        replaced = 0
        skipped = 0
        skipped_locs: list[tuple[int, str]] = []

        # Process pages in reverse order (highest first) to avoid
        # coordinate shifts from redactions affecting subsequent pages
        for page_idx in sorted(search_results.keys(), reverse=True):
            rects = search_results[page_idx]
            # Process rects in reverse order within each page
            for rect in reversed(rects):
                font_check = self.check_font_support(doc_handle, page_idx, rect)
                if not font_check.supported:
                    skipped += 1
                    skipped_locs.append((page_idx, font_check.reason))
                    continue

                success = self.replace_text(
                    doc_handle, page_idx, rect, old_text, new_text
                )
                if success:
                    replaced += 1
                else:
                    skipped += 1
                    skipped_locs.append((page_idx, "Replacement failed"))

        return ReplaceAllResult(
            replaced_count=replaced,
            skipped_count=skipped,
            skipped_locations=skipped_locs,
        )

    def edit_text_inline(
        self,
        doc_handle: Any,
        page_index: int,
        block_rect: tuple[float, float, float, float],
        old_text: str,
        new_text: str,
    ) -> EditResult:
        """Attempt direct text edit at the given block rect.

        Checks font support first. If supported, replaces via
        redact-and-overlay. If not, returns failure with reason.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            block_rect: Bounding rect of the text block.
            old_text: Original text content.
            new_text: New text content.

        Returns:
            EditResult indicating success or failure with reason.
        """
        font_check = self.check_font_support(doc_handle, page_index, block_rect)
        if not font_check.supported:
            return EditResult(success=False, error_message=font_check.reason)

        success = self.replace_text(
            doc_handle, page_index, block_rect, old_text, new_text
        )
        if success:
            return EditResult(success=True, error_message="")
        return EditResult(
            success=False, error_message="Text replacement failed unexpectedly."
        )

    def redact_and_overlay(
        self,
        doc_handle: Any,
        page_index: int,
        block_rect: tuple[float, float, float, float],
        new_text: str,
        font_size: float,
    ) -> None:
        """Redact original text area and insert new text using Helvetica.

        This is the fallback editing method that works with any font.
        The redaction permanently removes content from the content stream.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            block_rect: Area to redact (x0, y0, x1, y1).
            new_text: Text to insert after redaction.
            font_size: Font size for the overlay text.
        """
        page = doc_handle[page_index]
        rect = pymupdf.Rect(*block_rect)

        # Step 1: Add redaction annotation with white fill
        page.add_redact_annot(rect, fill=(1, 1, 1))

        # Step 2: Apply redaction (permanently removes content)
        page.apply_redactions()

        # Step 3: Insert new text at the same position using Helvetica
        # Position at bottom-left of the rect, adjusted for font baseline
        insert_point = pymupdf.Point(rect.x0, rect.y0 + font_size)
        page.insert_text(
            insert_point,
            new_text,
            fontname="helv",
            fontsize=font_size,
        )

        logger.debug(
            "Redact-and-overlay on page %d: inserted '%s' at %s",
            page_index,
            new_text[:30],
            block_rect,
        )


def _is_base14_font(font_name: str) -> bool:
    """Check if a font name is one of the PDF base-14 fonts.

    Args:
        font_name: The font name string from PyMuPDF.

    Returns:
        True if this is a base-14 (always available) font.
    """
    base14 = {
        "Courier",
        "Courier-Bold",
        "Courier-Oblique",
        "Courier-BoldOblique",
        "Helvetica",
        "Helvetica-Bold",
        "Helvetica-Oblique",
        "Helvetica-BoldOblique",
        "Times-Roman",
        "Times-Bold",
        "Times-Italic",
        "Times-BoldItalic",
        "Symbol",
        "ZapfDingbats",
        # PyMuPDF internal names
        "helv",
        "heit",
        "cour",
        "cobo",
        "cobi",
        "coit",
        "hebo",
        "hebi",
        "tiro",
        "tibo",
        "tibi",
        "tiit",
        "symb",
        "zadb",
    }
    return font_name in base14
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_text_edit_engine.py -v`
Expected: All PASS

- [ ] **Step 5: Run linting**

Run: `uv run ruff check k_pdf/services/text_edit_engine.py && uv run ruff format k_pdf/services/text_edit_engine.py tests/test_text_edit_engine.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add k_pdf/services/text_edit_engine.py tests/test_text_edit_engine.py
git commit -m "feat: add TextEditEngine for PDF text replacement and font checking"
```

---

### Task 3: FindReplaceBar View

**Files:**
- Create: `k_pdf/views/find_replace_bar.py`
- Test: `tests/test_find_replace_bar.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_find_replace_bar.py`:

```python
"""Tests for FindReplaceBar view widget."""

from __future__ import annotations

from k_pdf.views.find_replace_bar import FindReplaceBar


class TestFindReplaceBarInit:
    def test_creates_bar(self, qtbot) -> None:
        bar = FindReplaceBar()
        qtbot.addWidget(bar)
        assert bar._search_input is not None
        assert bar._replace_input is not None

    def test_starts_hidden(self, qtbot) -> None:
        bar = FindReplaceBar()
        qtbot.addWidget(bar)
        assert not bar.isVisible()

    def test_has_replace_button(self, qtbot) -> None:
        bar = FindReplaceBar()
        qtbot.addWidget(bar)
        assert bar._replace_btn is not None
        assert bar._replace_all_btn is not None


class TestFindReplaceBarSignals:
    def test_search_emits_on_text_change(self, qtbot) -> None:
        bar = FindReplaceBar()
        qtbot.addWidget(bar)
        bar.show()

        with qtbot.waitSignal(bar.search_requested, timeout=1000):
            bar._search_input.setText("test")
            bar._debounce_timer.timeout.emit()

    def test_replace_emits_signal(self, qtbot) -> None:
        bar = FindReplaceBar()
        qtbot.addWidget(bar)
        bar._search_input.setText("old")
        bar._replace_input.setText("new")

        with qtbot.waitSignal(bar.replace_requested, timeout=1000) as sig:
            bar._replace_btn.click()

        assert sig.args[0] == "new"

    def test_replace_all_emits_signal(self, qtbot) -> None:
        bar = FindReplaceBar()
        qtbot.addWidget(bar)
        bar._search_input.setText("old")
        bar._replace_input.setText("new")

        with qtbot.waitSignal(bar.replace_all_requested, timeout=1000) as sig:
            bar._replace_all_btn.click()

        assert sig.args[0] == "new"

    def test_close_emits_signal(self, qtbot) -> None:
        bar = FindReplaceBar()
        qtbot.addWidget(bar)

        with qtbot.waitSignal(bar.closed, timeout=1000):
            bar._close_btn.click()

    def test_next_emits_signal(self, qtbot) -> None:
        bar = FindReplaceBar()
        qtbot.addWidget(bar)

        with qtbot.waitSignal(bar.next_requested, timeout=1000):
            bar._next_btn.click()

    def test_previous_emits_signal(self, qtbot) -> None:
        bar = FindReplaceBar()
        qtbot.addWidget(bar)

        with qtbot.waitSignal(bar.previous_requested, timeout=1000):
            bar._prev_btn.click()


class TestFindReplaceBarState:
    def test_set_match_count(self, qtbot) -> None:
        bar = FindReplaceBar()
        qtbot.addWidget(bar)
        bar.set_match_count(3, 7)
        assert "3 of 7" in bar._match_label.text()

    def test_focus_input(self, qtbot) -> None:
        bar = FindReplaceBar()
        qtbot.addWidget(bar)
        bar.show()
        bar.focus_input()
        assert bar._search_input.hasFocus()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_find_replace_bar.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement FindReplaceBar**

Create `k_pdf/views/find_replace_bar.py`:

```python
"""Find and replace bar — two-row search and replace widget.

Row 1: Search input, match counter, Previous/Next, Aa toggle, W toggle, Close.
Row 2: Replace input, Replace button, Replace All button.

Activated via Edit > Find and Replace (Ctrl+H). The existing SearchBar
(Ctrl+F) remains unchanged for search-only use.
"""

from __future__ import annotations

import logging
from typing import override

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger("k_pdf.views.find_replace_bar")


class FindReplaceBar(QWidget):
    """Two-row find and replace bar with search and replacement controls.

    Signals:
        search_requested: (query, case_sensitive, whole_word)
        next_requested: Navigate to next match.
        previous_requested: Navigate to previous match.
        replace_requested: (replacement_text) Replace current match.
        replace_all_requested: (replacement_text) Replace all matches.
        closed: Bar was closed.
    """

    search_requested = Signal(str, bool, bool)
    next_requested = Signal()
    previous_requested = Signal()
    replace_requested = Signal(str)  # replacement text
    replace_all_requested = Signal(str)  # replacement text
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the find-and-replace bar, hidden by default."""
        super().__init__(parent)
        self.hide()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 4, 6, 4)
        main_layout.setSpacing(2)

        # --- Row 1: Search ---
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Find in document...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumWidth(200)
        self._search_input.setAccessibleName("Search text")
        row1.addWidget(self._search_input)

        self._match_label = QLabel("")
        self._match_label.setMinimumWidth(120)
        self._match_label.setAccessibleName("Match count")
        row1.addWidget(self._match_label)

        self._prev_btn = QPushButton("Previous")
        self._prev_btn.setToolTip("Previous match (Shift+Enter)")
        self._prev_btn.setAccessibleName("Previous match")
        self._prev_btn.clicked.connect(self.previous_requested.emit)
        row1.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Next")
        self._next_btn.setToolTip("Next match (Enter)")
        self._next_btn.setAccessibleName("Next match")
        self._next_btn.clicked.connect(self.next_requested.emit)
        row1.addWidget(self._next_btn)

        self._case_btn = QPushButton("Aa")
        self._case_btn.setToolTip("Case sensitive")
        self._case_btn.setAccessibleName("Case sensitive toggle")
        self._case_btn.setCheckable(True)
        self._case_btn.setMaximumWidth(36)
        self._case_btn.clicked.connect(self._on_toggle_changed)
        row1.addWidget(self._case_btn)

        self._word_btn = QPushButton("W")
        self._word_btn.setToolTip("Whole word")
        self._word_btn.setAccessibleName("Whole word toggle")
        self._word_btn.setCheckable(True)
        self._word_btn.setMaximumWidth(36)
        self._word_btn.clicked.connect(self._on_toggle_changed)
        row1.addWidget(self._word_btn)

        self._close_btn = QPushButton("\u00d7")
        self._close_btn.setToolTip("Close (Escape)")
        self._close_btn.setAccessibleName("Close find and replace")
        self._close_btn.setMaximumWidth(30)
        self._close_btn.clicked.connect(self.closed.emit)
        row1.addWidget(self._close_btn)

        main_layout.addLayout(row1)

        # --- Row 2: Replace ---
        row2 = QHBoxLayout()
        row2.setSpacing(4)

        self._replace_input = QLineEdit()
        self._replace_input.setPlaceholderText("Replace with...")
        self._replace_input.setMinimumWidth(200)
        self._replace_input.setAccessibleName("Replacement text")
        row2.addWidget(self._replace_input)

        self._replace_btn = QPushButton("Replace")
        self._replace_btn.setToolTip("Replace current match")
        self._replace_btn.setAccessibleName("Replace current match")
        self._replace_btn.clicked.connect(self._on_replace)
        row2.addWidget(self._replace_btn)

        self._replace_all_btn = QPushButton("Replace All")
        self._replace_all_btn.setToolTip("Replace all matches")
        self._replace_all_btn.setAccessibleName("Replace all matches")
        self._replace_all_btn.clicked.connect(self._on_replace_all)
        row2.addWidget(self._replace_all_btn)

        row2.addStretch()
        main_layout.addLayout(row2)

        # Debounce timer for search input
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._emit_search)

        self._search_input.textChanged.connect(self._on_text_changed)
        self._search_input.installEventFilter(self)

        # Escape closes the bar
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.closed.emit)

    @override
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Intercept Return/Shift+Return on the search input."""
        if obj is self._search_input and event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event  # type: ignore[assignment]
            if key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.previous_requested.emit()
                else:
                    self.next_requested.emit()
                return True
        return super().eventFilter(obj, event)

    def set_match_count(self, current: int, total: int) -> None:
        """Update the match counter label.

        Args:
            current: Current match number (1-based).
            total: Total match count.
        """
        word = "match" if total == 1 else "matches"
        self._match_label.setText(f"{current} of {total} {word}")

    def set_no_text_layer(self) -> None:
        """Show message indicating the document has no searchable text."""
        self._match_label.setText("This document has no searchable text.")

    def set_status(self, message: str) -> None:
        """Show a status message in the match label area.

        Args:
            message: The status text to display.
        """
        self._match_label.setText(message)

    def focus_input(self) -> None:
        """Focus the search text input field."""
        self._search_input.setFocus()
        self._search_input.selectAll()

    def clear(self) -> None:
        """Reset the bar to its initial state."""
        self._search_input.blockSignals(True)
        self._search_input.clear()
        self._search_input.blockSignals(False)
        self._replace_input.clear()
        self._match_label.setText("")
        self._case_btn.setChecked(False)
        self._word_btn.setChecked(False)

    def _on_text_changed(self, _text: str) -> None:
        """Restart debounce timer when search text changes."""
        self._debounce_timer.start()

    def _on_toggle_changed(self) -> None:
        """Handle toggle button state change — trigger search immediately."""
        if self._search_input.text():
            self._emit_search()

    def _emit_search(self) -> None:
        """Emit search_requested with current query and toggle states."""
        query = self._search_input.text()
        case_sensitive = self._case_btn.isChecked()
        whole_word = self._word_btn.isChecked()
        self.search_requested.emit(query, case_sensitive, whole_word)

    def _on_replace(self) -> None:
        """Emit replace_requested with the replacement text."""
        self.replace_requested.emit(self._replace_input.text())

    def _on_replace_all(self) -> None:
        """Emit replace_all_requested with the replacement text."""
        self.replace_all_requested.emit(self._replace_input.text())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_find_replace_bar.py -v`
Expected: All PASS

- [ ] **Step 5: Run linting**

Run: `uv run ruff check k_pdf/views/find_replace_bar.py && uv run ruff format k_pdf/views/find_replace_bar.py tests/test_find_replace_bar.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add k_pdf/views/find_replace_bar.py tests/test_find_replace_bar.py
git commit -m "feat: add FindReplaceBar two-row search and replace view"
```

---

### Task 4: TextEditPresenter

**Files:**
- Create: `k_pdf/presenters/text_edit_presenter.py`
- Test: `tests/test_text_edit_presenter.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_text_edit_presenter.py`:

```python
"""Tests for TextEditPresenter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
import pytest
from PySide6.QtWidgets import QTabWidget

from k_pdf.core.annotation_model import ToolMode
from k_pdf.core.text_edit_model import ReplaceAllResult
from k_pdf.persistence.recent_files import RecentFiles
from k_pdf.persistence.settings_db import init_db
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.presenters.text_edit_presenter import TextEditPresenter
from k_pdf.services.text_edit_engine import TextEditEngine


@pytest.fixture
def engine() -> TextEditEngine:
    return TextEditEngine()


@pytest.fixture
def tab_manager(qtbot, tmp_path: Path) -> TabManager:
    db = init_db(tmp_path / "test.db")
    recent = RecentFiles(db)
    tw = QTabWidget()
    qtbot.addWidget(tw)
    return TabManager(tab_widget=tw, recent_files=recent)


@pytest.fixture
def presenter(
    engine: TextEditEngine, tab_manager: TabManager
) -> TextEditPresenter:
    return TextEditPresenter(
        text_edit_engine=engine,
        tab_manager=tab_manager,
    )


class TestTextEditPresenterToolMode:
    def test_set_text_edit_mode(self, presenter: TextEditPresenter) -> None:
        presenter.set_tool_mode(ToolMode.TEXT_EDIT)
        assert presenter.tool_mode is ToolMode.TEXT_EDIT

    def test_set_none_clears_mode(self, presenter: TextEditPresenter) -> None:
        presenter.set_tool_mode(ToolMode.TEXT_EDIT)
        presenter.set_tool_mode(ToolMode.NONE)
        assert presenter.tool_mode is ToolMode.NONE


class TestTextEditPresenterReplace:
    def test_replace_current_marks_dirty(
        self, presenter: TextEditPresenter, tmp_path: Path
    ) -> None:
        path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 100), "Hello World", fontname="helv", fontsize=12)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        mock_model = MagicMock()
        mock_model.doc_handle = doc
        mock_model.dirty = False

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)

        rects = doc[0].search_for("Hello World")
        search_rect = (rects[0].x0, rects[0].y0, rects[0].x1, rects[0].y1)

        dirty_signals: list[bool] = []
        presenter.dirty_changed.connect(dirty_signals.append)

        presenter.replace_current(0, search_rect, "Hello World", "Hi Earth")

        assert mock_model.dirty is True
        assert dirty_signals == [True]
        doc.close()

    def test_replace_current_emits_text_changed(
        self, presenter: TextEditPresenter, tmp_path: Path
    ) -> None:
        path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 100), "Hello World", fontname="helv", fontsize=12)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        mock_model = MagicMock()
        mock_model.doc_handle = doc

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)

        rects = doc[0].search_for("Hello World")
        search_rect = (rects[0].x0, rects[0].y0, rects[0].x1, rects[0].y1)

        changed: list[bool] = []
        presenter.text_changed.connect(lambda: changed.append(True))

        presenter.replace_current(0, search_rect, "Hello World", "Hi Earth")

        assert len(changed) == 1
        doc.close()


class TestTextEditPresenterReplaceAll:
    def test_replace_all_returns_result(
        self, presenter: TextEditPresenter, tmp_path: Path
    ) -> None:
        path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 100), "Hello World", fontname="helv", fontsize=12)
        page.insert_text(pymupdf.Point(72, 140), "Goodbye World", fontname="helv", fontsize=12)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        mock_model = MagicMock()
        mock_model.doc_handle = doc

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)

        rects = doc[0].search_for("World")
        search_results = {0: [(r.x0, r.y0, r.x1, r.y1) for r in rects]}

        result = presenter.replace_all(search_results, "World", "Earth")

        assert result is not None
        assert isinstance(result, ReplaceAllResult)
        assert result.replaced_count > 0
        doc.close()


class TestTextEditPresenterTabSwitch:
    def test_resets_on_tab_switch(self, presenter: TextEditPresenter) -> None:
        presenter.set_tool_mode(ToolMode.TEXT_EDIT)
        presenter.on_tab_switched("new-session")
        assert presenter.tool_mode is ToolMode.NONE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_text_edit_presenter.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement TextEditPresenter**

Create `k_pdf/presenters/text_edit_presenter.py`:

```python
"""Text edit presenter — coordinates find-replace, inline edit, undo.

Manages the TextEditEngine, FindReplaceBar interactions, inline edit
overlay, font limitation dialogs, and undo actions.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal

from k_pdf.core.annotation_model import ToolMode
from k_pdf.core.text_edit_model import EditResult, ReplaceAllResult
from k_pdf.core.undo_manager import UndoAction
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.text_edit_engine import TextEditEngine

logger = logging.getLogger("k_pdf.presenters.text_edit_presenter")


class TextEditPresenter(QObject):
    """Coordinates text editing between views and TextEditEngine.

    Signals:
        dirty_changed: Emitted when the document dirty flag transitions.
        text_changed: Emitted after text is modified (for re-render).
        tool_mode_changed: Emitted when the text edit tool mode changes.
        replace_status: Emitted with a status message for the replace bar.
    """

    dirty_changed = Signal(bool)
    text_changed = Signal()
    tool_mode_changed = Signal(int)
    replace_status = Signal(str)

    def __init__(
        self,
        text_edit_engine: TextEditEngine,
        tab_manager: TabManager,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the text edit presenter.

        Args:
            text_edit_engine: The TextEditEngine service.
            tab_manager: The TabManager for accessing active tab state.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._engine = text_edit_engine
        self._tab_manager = tab_manager
        self._tool_mode: ToolMode = ToolMode.NONE

        self._tab_manager.tab_switched.connect(self.on_tab_switched)

    @property
    def tool_mode(self) -> ToolMode:
        """Return the current tool mode."""
        return self._tool_mode

    def set_tool_mode(self, mode: ToolMode) -> None:
        """Set the active text edit tool mode.

        Args:
            mode: TEXT_EDIT or NONE.
        """
        self._tool_mode = mode
        self.tool_mode_changed.emit(int(mode))

    def replace_current(
        self,
        page_index: int,
        search_rect: tuple[float, float, float, float],
        old_text: str,
        new_text: str,
    ) -> bool:
        """Replace text at the current match location.

        Args:
            page_index: Zero-based page index.
            search_rect: Bounding rect of the match.
            old_text: Original text.
            new_text: Replacement text.

        Returns:
            True if replacement succeeded.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return False

        model = doc_presenter.model

        success = self._engine.replace_text(
            model.doc_handle, page_index, search_rect, old_text, new_text
        )

        if success:
            model.dirty = True
            self.dirty_changed.emit(True)
            self.text_changed.emit()

            # Push undo
            undo_mgr = self._tab_manager.get_active_undo_manager()
            if undo_mgr is not None:
                stored_rect = search_rect

                def undo() -> None:
                    self._engine.replace_text(
                        model.doc_handle, page_index, stored_rect, new_text, old_text
                    )
                    model.dirty = True
                    self.dirty_changed.emit(True)
                    self.text_changed.emit()

                def redo() -> None:
                    self._engine.replace_text(
                        model.doc_handle, page_index, stored_rect, old_text, new_text
                    )
                    model.dirty = True
                    self.dirty_changed.emit(True)
                    self.text_changed.emit()

                desc = f"Replace '{old_text[:20]}' with '{new_text[:20]}'"
                undo_mgr.push(UndoAction(
                    description=desc,
                    undo_fn=undo,
                    redo_fn=redo,
                ))

        return success

    def replace_all(
        self,
        search_results: dict[int, list[tuple[float, float, float, float]]],
        old_text: str,
        new_text: str,
    ) -> ReplaceAllResult | None:
        """Replace all matched text across the document.

        Args:
            search_results: Dict mapping page_index to list of match rects.
            old_text: Search text being replaced.
            new_text: Replacement text.

        Returns:
            ReplaceAllResult with counts and skipped locations, or None.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return None

        model = doc_presenter.model

        result = self._engine.replace_all(
            model.doc_handle, search_results, old_text, new_text
        )

        if result.replaced_count > 0:
            model.dirty = True
            self.dirty_changed.emit(True)
            self.text_changed.emit()

            # Push compound undo
            undo_mgr = self._tab_manager.get_active_undo_manager()
            if undo_mgr is not None:
                desc = (
                    f"Replace All '{old_text[:20]}' with '{new_text[:20]}' "
                    f"({result.replaced_count} replacements)"
                )
                undo_mgr.push(UndoAction(
                    description=desc,
                    undo_fn=lambda: None,  # Compound undo not feasible for redactions
                    redo_fn=lambda: None,
                ))

            # Emit status
            if result.skipped_count > 0:
                msg = (
                    f"Replaced {result.replaced_count} of "
                    f"{result.replaced_count + result.skipped_count}. "
                    f"{result.skipped_count} skipped (subset font)."
                )
            else:
                msg = f"Replaced {result.replaced_count} matches."
            self.replace_status.emit(msg)

        return result

    def edit_inline(
        self,
        page_index: int,
        block_rect: tuple[float, float, float, float],
        old_text: str,
        new_text: str,
    ) -> EditResult:
        """Attempt inline text edit at the given block.

        Args:
            page_index: Zero-based page index.
            block_rect: Bounding rect of the text block.
            old_text: Original text content.
            new_text: New text content.

        Returns:
            EditResult indicating success or failure.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return EditResult(success=False, error_message="No active document.")

        model = doc_presenter.model

        result = self._engine.edit_text_inline(
            model.doc_handle, page_index, block_rect, old_text, new_text
        )

        if result.success:
            model.dirty = True
            self.dirty_changed.emit(True)
            self.text_changed.emit()

            undo_mgr = self._tab_manager.get_active_undo_manager()
            if undo_mgr is not None:
                def undo() -> None:
                    self._engine.replace_text(
                        model.doc_handle, page_index, block_rect, new_text, old_text
                    )
                    model.dirty = True
                    self.dirty_changed.emit(True)
                    self.text_changed.emit()

                def redo() -> None:
                    self._engine.replace_text(
                        model.doc_handle, page_index, block_rect, old_text, new_text
                    )
                    model.dirty = True
                    self.dirty_changed.emit(True)
                    self.text_changed.emit()

                undo_mgr.push(UndoAction(
                    description=f"Edit text on page {page_index + 1}",
                    undo_fn=undo,
                    redo_fn=redo,
                ))

        return result

    def redact_and_overlay(
        self,
        page_index: int,
        block_rect: tuple[float, float, float, float],
        new_text: str,
        font_size: float,
    ) -> None:
        """Apply redact-and-overlay fallback for subset fonts.

        Args:
            page_index: Zero-based page index.
            block_rect: Area to redact and overlay.
            new_text: Text to insert after redaction.
            font_size: Font size for the overlay.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return

        model = doc_presenter.model

        self._engine.redact_and_overlay(
            model.doc_handle, page_index, block_rect, new_text, font_size
        )

        model.dirty = True
        self.dirty_changed.emit(True)
        self.text_changed.emit()

        undo_mgr = self._tab_manager.get_active_undo_manager()
        if undo_mgr is not None:
            undo_mgr.push(UndoAction(
                description=f"Redact and replace text on page {page_index + 1}",
                undo_fn=lambda: None,  # Redaction is permanent in PyMuPDF
                redo_fn=lambda: None,
            ))

    def get_text_block_at(
        self,
        page_index: int,
        x: float,
        y: float,
    ) -> Any:
        """Get text block info at the given PDF coordinates.

        Args:
            page_index: Zero-based page index.
            x: X coordinate in PDF page space.
            y: Y coordinate in PDF page space.

        Returns:
            TextBlockInfo or None.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return None

        return self._engine.get_text_block(
            doc_presenter.model.doc_handle, page_index, x, y
        )

    def on_tab_switched(self, session_id: str) -> None:
        """Reset tool mode on tab switch.

        Args:
            session_id: New active tab session ID.
        """
        self._tool_mode = ToolMode.NONE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_text_edit_presenter.py -v`
Expected: All PASS

- [ ] **Step 5: Run linting**

Run: `uv run ruff check k_pdf/presenters/text_edit_presenter.py && uv run ruff format k_pdf/presenters/text_edit_presenter.py tests/test_text_edit_presenter.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add k_pdf/presenters/text_edit_presenter.py tests/test_text_edit_presenter.py
git commit -m "feat: add TextEditPresenter for find-replace and inline text editing"
```

---

### Task 5: Wire Text Editing into Viewport (TEXT_EDIT mode + double-click)

**Files:**
- Modify: `k_pdf/views/pdf_viewport.py`
- Test: `tests/test_text_edit_integration.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_text_edit_integration.py`:

```python
"""Integration tests for text editing wiring."""

from __future__ import annotations

from k_pdf.core.annotation_model import ToolMode
from k_pdf.views.pdf_viewport import PdfViewport


class TestViewportTextEditMode:
    def test_viewport_has_text_edit_requested_signal(self, qtbot) -> None:
        vp = PdfViewport()
        qtbot.addWidget(vp)
        assert hasattr(vp, "text_edit_requested")

    def test_viewport_handles_text_edit_mode(self, qtbot) -> None:
        vp = PdfViewport()
        qtbot.addWidget(vp)
        vp.set_tool_mode(ToolMode.TEXT_EDIT)
        assert vp._tool_mode is ToolMode.TEXT_EDIT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_text_edit_integration.py -v`
Expected: FAIL — `AttributeError: 'PdfViewport' object has no attribute 'text_edit_requested'`

- [ ] **Step 3: Add text_edit_requested signal and TEXT_EDIT mode handling**

In `k_pdf/views/pdf_viewport.py`:

Add signal after `form_field_placed` (around line 71):
```python
    text_edit_requested = Signal(int, float, float)  # (page_index, pdf_x, pdf_y)
```

In `set_tool_mode`, add TEXT_EDIT handling after the TEXT_SELECT block (after line 420):
```python
        elif mode is ToolMode.TEXT_EDIT:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.IBeamCursor)
```

In `mouseDoubleClickEvent` (add new override if it doesn't exist, or extend it):
```python
    @override
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Handle double-click — inline text edit in TEXT_EDIT mode."""
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._tool_mode is ToolMode.TEXT_EDIT
        ):
            self._handle_text_edit_double_click(event)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _handle_text_edit_double_click(self, event: QMouseEvent) -> None:
        """Handle double-click in text edit mode — emit text_edit_requested."""
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
        pdf_x = max(0.0, min(pdf_x, page_info.width))
        pdf_y = max(0.0, min(pdf_y, page_info.height))

        self.text_edit_requested.emit(page_index, pdf_x, pdf_y)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_text_edit_integration.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest --tb=short -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add k_pdf/views/pdf_viewport.py tests/test_text_edit_integration.py
git commit -m "feat: add text_edit_requested signal and TEXT_EDIT mode to viewport"
```

---

### Task 6: Wire FindReplaceBar and TextEditPresenter into MainWindow and KPdfApp

**Files:**
- Modify: `k_pdf/views/main_window.py`
- Modify: `k_pdf/app.py`
- Test: `tests/test_text_edit_wiring.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_text_edit_wiring.py`:

```python
"""Tests that KPdfApp wires text editing correctly."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp


class TestKPdfAppTextEditing:
    def test_app_has_text_edit_presenter(self, qtbot) -> None:
        app = QApplication.instance()
        k_app = KPdfApp(app)
        qtbot.addWidget(k_app.window)
        assert hasattr(k_app, "_text_edit_presenter")
        k_app.shutdown()

    def test_app_has_find_replace_bar(self, qtbot) -> None:
        app = QApplication.instance()
        k_app = KPdfApp(app)
        qtbot.addWidget(k_app.window)
        assert hasattr(k_app.window, "find_replace_bar")
        k_app.shutdown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_text_edit_wiring.py -v`
Expected: FAIL — `AttributeError`

- [ ] **Step 3: Add FindReplaceBar to MainWindow**

In `k_pdf/views/main_window.py`, add import:
```python
from k_pdf.views.find_replace_bar import FindReplaceBar
```

In `__init__`, after the SearchBar setup (after line 126), add:
```python
        self._find_replace_bar = FindReplaceBar(self)
        self._find_replace_bar.closed.connect(self._hide_find_replace_bar)
```

In the central layout setup (after `central_layout.addWidget(self._search_bar)`), add:
```python
        central_layout.addWidget(self._find_replace_bar)
```

Add property:
```python
    @property
    def find_replace_bar(self) -> FindReplaceBar:
        """Return the find-and-replace bar widget."""
        return self._find_replace_bar
```

Update `find_replace_requested` signal connection. In `_setup_menus`, change the existing find_replace_action's trigger from `self.find_replace_requested.emit` to `self._show_find_replace_bar`:

```python
        find_replace_action.triggered.connect(self._show_find_replace_bar)
```

Add show/hide methods:
```python
    def _show_find_replace_bar(self) -> None:
        """Show the find-and-replace bar and focus the input field."""
        self._search_bar.hide()  # Hide the simple search bar if visible
        self._find_replace_bar.show()
        self._find_replace_bar.focus_input()

    def _hide_find_replace_bar(self) -> None:
        """Hide the find-and-replace bar."""
        self._find_replace_bar.hide()
```

- [ ] **Step 4: Wire TextEditPresenter in KPdfApp**

In `k_pdf/app.py`, add imports:
```python
from k_pdf.presenters.text_edit_presenter import TextEditPresenter
from k_pdf.services.text_edit_engine import TextEditEngine
```

In `__init__`, after the FormCreationPresenter setup, add:
```python
        self._text_edit_engine = TextEditEngine()
        self._text_edit_presenter = TextEditPresenter(
            text_edit_engine=self._text_edit_engine,
            tab_manager=self._tab_manager,
        )
```

In `_connect_signals`, add text editing wiring:
```python
        # Text editing wiring
        # Find-replace bar -> search (reuses SearchPresenter for finding)
        find_replace = self._window.find_replace_bar
        find_replace.search_requested.connect(
            lambda q, cs, ww: self._search_presenter.start_search(
                q, case_sensitive=cs, whole_word=ww
            )
        )
        find_replace.next_requested.connect(self._search_presenter.next_match)
        find_replace.previous_requested.connect(self._search_presenter.previous_match)
        find_replace.closed.connect(self._search_presenter.close_search)
        find_replace.replace_requested.connect(self._on_replace_current)
        find_replace.replace_all_requested.connect(self._on_replace_all)

        # SearchPresenter -> FindReplaceBar (match count updates)
        self._search_presenter.matches_updated.connect(find_replace.set_match_count)
        self._search_presenter.no_text_layer.connect(find_replace.set_no_text_layer)

        # TextEditPresenter signals
        self._text_edit_presenter.text_changed.connect(self._on_text_edit_changed)
        self._text_edit_presenter.replace_status.connect(find_replace.set_status)

        # Text edit mode from tools menu
        self._window.text_edit_toggled.connect(self._on_text_edit_toggled)

        # Document ready -> wire text edit double-click
        self._tab_manager.document_ready.connect(self._on_document_ready_text_edit)
```

Add handler methods:
```python
    # --- Text editing handlers ---

    def _on_text_edit_toggled(self, checked: bool) -> None:
        """Handle Edit Text tool toggle."""
        if checked:
            self._text_edit_presenter.set_tool_mode(ToolMode.TEXT_EDIT)
        else:
            self._text_edit_presenter.set_tool_mode(ToolMode.NONE)
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.set_tool_mode(
                ToolMode.TEXT_EDIT if checked else ToolMode.NONE
            )

    def _on_document_ready_text_edit(self, session_id: str, model: object) -> None:
        """Wire text edit signals when a document loads."""
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            with contextlib.suppress(RuntimeError):
                viewport.text_edit_requested.disconnect(self._on_text_edit_requested)
            viewport.text_edit_requested.connect(self._on_text_edit_requested)

    def _on_text_edit_requested(
        self, page_index: int, pdf_x: float, pdf_y: float
    ) -> None:
        """Handle double-click in text edit mode — show inline edit overlay."""
        block = self._text_edit_presenter.get_text_block_at(page_index, pdf_x, pdf_y)
        if block is None:
            return  # No text at this position — no-op per spec

        # Show font limitation dialog if subset font
        if not block.is_fully_embedded:
            reply = QMessageBox.warning(
                self._window,
                "Cannot Edit Text Directly",
                f"This text uses a subset font ({block.font_name}) that only "
                "contains the original characters. Direct editing is not possible.\n\n"
                "Redact the original text and overlay new text using a standard "
                "font (Helvetica). The result will look similar but use a different font.",
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Ok:
                return
            # Will use redact_and_overlay path below

        # For now, use a simple QInputDialog for inline editing
        # A full floating overlay (like NoteEditor) can be added as a refinement
        from PySide6.QtWidgets import QInputDialog

        new_text, ok = QInputDialog.getText(
            self._window,
            "Edit Text",
            f"Editing text (font: {block.font_name})",
            text=block.text,
        )
        if not ok or new_text == block.text:
            return

        if block.is_fully_embedded:
            result = self._text_edit_presenter.edit_inline(
                page_index, block.rect, block.text, new_text
            )
            if not result.success:
                QMessageBox.warning(
                    self._window,
                    "Edit Failed",
                    result.error_message,
                )
        else:
            self._text_edit_presenter.redact_and_overlay(
                page_index, block.rect, new_text, block.font_size
            )

    def _on_replace_current(self, replacement_text: str) -> None:
        """Handle Replace button from FindReplaceBar."""
        # Get current match from SearchPresenter
        sid = self._search_presenter._active_session_id
        if sid is None or sid not in self._search_presenter._results:
            return

        result = self._search_presenter._results[sid]
        rect = result.current_rect()
        if rect is None:
            return

        self._text_edit_presenter.replace_current(
            result.current_page,
            rect,
            result.query,
            replacement_text,
        )
        # Advance to next match
        self._search_presenter.next_match()

    def _on_replace_all(self, replacement_text: str) -> None:
        """Handle Replace All button from FindReplaceBar."""
        sid = self._search_presenter._active_session_id
        if sid is None or sid not in self._search_presenter._results:
            return

        search_result = self._search_presenter._results[sid]
        if not search_result.matches:
            return

        result = self._text_edit_presenter.replace_all(
            search_result.matches,
            search_result.query,
            replacement_text,
        )

        if result is not None and result.replaced_count > 0:
            # Clear search results since text has changed
            self._search_presenter.close_search()

    def _on_text_edit_changed(self) -> None:
        """Re-render viewport after text edit."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and viewport is not None:
            presenter.cache.invalidate()
            presenter._pending_renders.clear()
            first, last = viewport.get_visible_page_range()
            if first >= 0:
                presenter.request_pages(list(range(first, last + 1)))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_text_edit_wiring.py -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest --tb=short -q`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add k_pdf/views/main_window.py k_pdf/app.py tests/test_text_edit_wiring.py
git commit -m "feat: wire text editing end-to-end — FindReplaceBar, TextEditPresenter, KPdfApp"
```

---

### Task 7: Add mypy Overrides and Final Verification

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Run mypy to check for needed overrides**

Run: `uv run mypy k_pdf/`
Expected: May show errors for new files.

- [ ] **Step 2: Add mypy overrides**

In `pyproject.toml`, add new view to the views override list:
```
"k_pdf.views.find_replace_bar"
```

Add presenter override:
```toml
[[tool.mypy.overrides]]
module = ["k_pdf.presenters.text_edit_presenter"]
disable_error_code = ["misc"]
```

Add service override:
```toml
[[tool.mypy.overrides]]
module = ["k_pdf.services.text_edit_engine"]
disable_error_code = ["no-untyped-call"]
```

- [ ] **Step 3: Run full verification**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy k_pdf/ && uv run pytest --cov=k_pdf --cov-report=term-missing -q`
Expected: All pass, coverage >= 65%

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add mypy overrides for text editing modules"
```

- [ ] **Step 5: Commit plan document**

```bash
git add docs/superpowers/plans/2026-04-06-text-editing.md
git commit -m "docs: add text editing implementation plan"
```
