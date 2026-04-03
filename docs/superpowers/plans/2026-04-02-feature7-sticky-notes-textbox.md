# Feature 7: Sticky Notes & Text Box Annotations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add sticky note (click-to-place) and text box (drag-to-draw) annotations with a floating NoteEditor widget for content input. Extend existing AnnotationEngine, AnnotationPresenter, PdfViewport, and MainWindow. Support editing existing annotations via double-click.

**Architecture:** Extend `AnnotationType` enum with STICKY_NOTE and TEXT_BOX. Extend `AnnotationData` with `content` and `rect` fields. Add `add_sticky_note()`, `add_text_box()`, `update_annotation_content()`, `get_annotation_content()` to `AnnotationEngine`. Introduce `ToolMode` enum in `AnnotationPresenter` replacing `_selection_mode` boolean. New `NoteEditor(QWidget)` floating editor. `PdfViewport` gains click-to-place and drag-to-draw mouse handling plus `note_placed`, `textbox_drawn`, `annotation_double_clicked` signals. `MainWindow` Tools menu gains "Sticky Note" and "Text Box" checkable items in a QActionGroup. `KPdfApp` wires all new signals.

**Tech Stack:** Python 3.13, PySide6 6.11, PyMuPDF 1.27, pytest + pytest-qt

**Spec:** `docs/superpowers/specs/2026-04-02-feature7-sticky-notes-textbox-design.md`

---

## File Map

**New files:**
- `k_pdf/views/note_editor.py` — `NoteEditor(QWidget)` floating editor for sticky note / text box content
- `tests/test_note_editor.py` — unit tests for NoteEditor widget
- `tests/test_viewport_note_placement.py` — unit tests for PdfViewport sticky note and text box modes
- `tests/test_sticky_note_integration.py` — integration tests through KPdfApp

**Modified files:**
- `k_pdf/core/annotation_model.py` — extend AnnotationType enum, extend AnnotationData dataclass
- `k_pdf/services/annotation_engine.py` — add sticky note, text box, update, get content methods
- `k_pdf/presenters/annotation_presenter.py` — add ToolMode enum, replace _selection_mode, note/textbox handlers
- `k_pdf/views/pdf_viewport.py` — add note_placed, textbox_drawn, annotation_double_clicked signals and mouse handling
- `k_pdf/views/main_window.py` — add Sticky Note and Text Box menu items with QActionGroup
- `k_pdf/app.py` — create NoteEditor, wire all new signals
- `pyproject.toml` — add mypy overrides for new modules
- `CLAUDE.md` — update current state
- `tests/test_annotation_model.py` — extend tests for new enum members and fields
- `tests/test_annotation_engine.py` — extend tests for new engine methods
- `tests/test_annotation_presenter.py` — extend tests for ToolMode and note/textbox handlers

---

### Task 1: Extend AnnotationModel (core/annotation_model.py)

**Files:**
- Modify: `k_pdf/core/annotation_model.py`
- Modify: `tests/test_annotation_model.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_annotation_model.py`:

```python
class TestAnnotationTypeExtended:
    def test_sticky_note_value(self) -> None:
        assert AnnotationType.STICKY_NOTE.value == "sticky_note"

    def test_text_box_value(self) -> None:
        assert AnnotationType.TEXT_BOX.value == "text_box"

    def test_enum_member_count_includes_new_types(self) -> None:
        assert len(AnnotationType) == 5


class TestAnnotationDataExtended:
    def test_default_content_is_empty(self) -> None:
        data = AnnotationData(
            type=AnnotationType.STICKY_NOTE,
            page=0,
            quads=[],
            color=(1.0, 1.0, 0.0),
        )
        assert data.content == ""

    def test_custom_content(self) -> None:
        data = AnnotationData(
            type=AnnotationType.STICKY_NOTE,
            page=0,
            quads=[],
            color=(1.0, 1.0, 0.0),
            content="Hello note",
        )
        assert data.content == "Hello note"

    def test_default_rect_is_none(self) -> None:
        data = AnnotationData(
            type=AnnotationType.TEXT_BOX,
            page=0,
            quads=[],
            color=(0.0, 0.0, 0.0),
        )
        assert data.rect is None

    def test_custom_rect(self) -> None:
        data = AnnotationData(
            type=AnnotationType.TEXT_BOX,
            page=0,
            quads=[],
            color=(0.0, 0.0, 0.0),
            rect=(100.0, 200.0, 300.0, 250.0),
        )
        assert data.rect == (100.0, 200.0, 300.0, 250.0)
```

Run: `uv run pytest tests/test_annotation_model.py -x` — expect failures for STICKY_NOTE, TEXT_BOX, content, rect.

- [ ] **Step 2: Write implementation**

Update `k_pdf/core/annotation_model.py`:

```python
class AnnotationType(Enum):
    """Text markup and note annotation types."""

    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    STICKY_NOTE = "sticky_note"
    TEXT_BOX = "text_box"


@dataclass
class AnnotationData:
    """Metadata for a single annotation.

    Attributes:
        type: The annotation kind.
        page: Zero-based page index.
        quads: Quad-point coordinates defining the annotated region.
        color: RGB color as 0.0-1.0 floats.
        author: Author name (optional metadata).
        created_at: Creation timestamp.
        content: Text content for sticky notes and text boxes.
        rect: Bounding rectangle (x0, y0, x1, y1) for text boxes; None for text markup.
    """

    type: AnnotationType
    page: int
    quads: list[tuple[float, ...]]
    color: tuple[float, float, float]
    author: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    content: str = ""
    rect: tuple[float, float, float, float] | None = None
```

Update existing test `test_enum_member_count` to assert 5.

Run: `uv run pytest tests/test_annotation_model.py -x` — expect all pass.

- [ ] **Step 3: Lint/type-check**

Run: `uv run ruff check k_pdf/core/annotation_model.py` and `uv run mypy k_pdf/core/annotation_model.py`

---

### Task 2: Extend AnnotationEngine (services/annotation_engine.py)

**Files:**
- Modify: `k_pdf/services/annotation_engine.py`
- Modify: `tests/test_annotation_engine.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_annotation_engine.py`:

```python
class TestAddStickyNote:
    def test_creates_text_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annot = engine.add_sticky_note(doc, 0, (100.0, 100.0), "Test note")
        assert annot is not None
        page = doc[0]
        annots = list(page.annots())
        assert len(annots) == 1
        doc.close()

    def test_sticky_note_has_content(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        engine.add_sticky_note(doc, 0, (100.0, 100.0), "My note content")
        content = engine.get_annotation_content(doc, 0, list(doc[0].annots())[0])
        assert content == "My note content"
        doc.close()

    def test_sticky_note_with_author(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annot = engine.add_sticky_note(doc, 0, (100.0, 100.0), "Note", author="Karl")
        info = annot.info
        assert info["title"] == "Karl"
        doc.close()


class TestAddTextBox:
    def test_creates_freetext_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annot = engine.add_text_box(doc, 0, (100.0, 200.0, 300.0, 250.0), "Box content")
        assert annot is not None
        page = doc[0]
        annots = list(page.annots())
        assert len(annots) == 1
        doc.close()

    def test_text_box_has_correct_rect(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        engine.add_text_box(doc, 0, (100.0, 200.0, 300.0, 250.0), "Content")
        annot = list(doc[0].annots())[0]
        r = annot.rect
        assert abs(r.x0 - 100.0) < 1.0
        assert abs(r.y0 - 200.0) < 1.0
        doc.close()


class TestUpdateAnnotationContent:
    def test_updates_sticky_note_content(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        engine.add_sticky_note(doc, 0, (100.0, 100.0), "Original")
        annot = list(doc[0].annots())[0]
        engine.update_annotation_content(doc, 0, annot, "Updated")
        refreshed = list(doc[0].annots())[0]
        content = engine.get_annotation_content(doc, 0, refreshed)
        assert content == "Updated"
        doc.close()


class TestGetAnnotationContent:
    def test_reads_content_from_sticky_note(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        engine.add_sticky_note(doc, 0, (100.0, 100.0), "Read me")
        annot = list(doc[0].annots())[0]
        content = engine.get_annotation_content(doc, 0, annot)
        assert content == "Read me"
        doc.close()

    def test_empty_content_returns_empty_string(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        engine.add_sticky_note(doc, 0, (100.0, 100.0), "")
        annot = list(doc[0].annots())[0]
        content = engine.get_annotation_content(doc, 0, annot)
        assert content == ""
        doc.close()
```

Run: `uv run pytest tests/test_annotation_engine.py -x` — expect failures for missing methods.

- [ ] **Step 2: Write implementation**

Add to `k_pdf/services/annotation_engine.py`:

```python
def add_sticky_note(
    self,
    doc_handle: Any,
    page_index: int,
    point: tuple[float, float],
    content: str,
    author: str = "",
) -> Any:
    """Add a sticky note annotation at a point on a page.

    Args:
        doc_handle: A pymupdf.Document handle.
        page_index: Zero-based page index.
        point: (x, y) position in PDF coordinates.
        content: Text content for the note.
        author: Optional author name.

    Returns:
        The created pymupdf.Annot object.
    """
    page = doc_handle[page_index]
    annot = page.add_text_annot(point, content, icon="Note")
    if author:
        annot.set_info(title=author)
        annot.update()
    logger.debug("Added sticky note on page %d at %s", page_index, point)
    return annot

def add_text_box(
    self,
    doc_handle: Any,
    page_index: int,
    rect: tuple[float, float, float, float],
    content: str,
    color: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Any:
    """Add a free-text box annotation on a page.

    Args:
        doc_handle: A pymupdf.Document handle.
        page_index: Zero-based page index.
        rect: (x0, y0, x1, y1) bounding rectangle.
        content: Text content for the box.
        color: Text color as RGB 0.0-1.0 floats.

    Returns:
        The created pymupdf.Annot object.
    """
    page = doc_handle[page_index]
    annot = page.add_freetext_annot(
        rect,
        content,
        fontsize=11,
        fontname="helv",
        text_color=color,
    )
    logger.debug("Added text box on page %d at rect %s", page_index, rect)
    return annot

def update_annotation_content(
    self,
    doc_handle: Any,
    page_index: int,
    annot: Any,
    content: str,
) -> None:
    """Update the text content of an existing annotation.

    Args:
        doc_handle: A pymupdf.Document handle.
        page_index: Zero-based page index.
        annot: The pymupdf.Annot to update.
        content: New text content.
    """
    annot.set_info(content=content)
    annot.update()
    logger.debug("Updated annotation content on page %d", page_index)

def get_annotation_content(
    self,
    doc_handle: Any,
    page_index: int,
    annot: Any,
) -> str:
    """Read text content from an annotation.

    Args:
        doc_handle: A pymupdf.Document handle.
        page_index: Zero-based page index.
        annot: The pymupdf.Annot to read.

    Returns:
        The annotation's text content, or empty string.
    """
    info = annot.info
    return str(info.get("content", ""))
```

Run: `uv run pytest tests/test_annotation_engine.py -x` — expect all pass.

- [ ] **Step 3: Lint/type-check**

Run: `uv run ruff check k_pdf/services/annotation_engine.py` and `uv run mypy k_pdf/services/annotation_engine.py`

---

### Task 3: NoteEditor Widget (views/note_editor.py)

**Files:**
- Create: `k_pdf/views/note_editor.py`
- Create: `tests/test_note_editor.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_note_editor.py`:

```python
"""Tests for NoteEditor floating widget."""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from k_pdf.views.note_editor import NoteEditor

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestNoteEditorInit:
    def test_creates_without_error(self) -> None:
        editor = NoteEditor()
        assert editor is not None

    def test_has_editing_finished_signal(self) -> None:
        editor = NoteEditor()
        assert hasattr(editor, "editing_finished")

    def test_has_editing_cancelled_signal(self) -> None:
        editor = NoteEditor()
        assert hasattr(editor, "editing_cancelled")


class TestShowForNew:
    def test_clears_text(self) -> None:
        editor = NoteEditor()
        editor._text_edit.setPlainText("old text")
        editor.show_for_new("sticky_note", 0, 100, 200)
        assert editor._text_edit.toPlainText() == ""

    def test_sets_mode(self) -> None:
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        assert editor._mode == "sticky_note"

    def test_sets_page_index(self) -> None:
        editor = NoteEditor()
        editor.show_for_new("text_box", 2, 100, 200)
        assert editor._target_page == 2

    def test_target_annot_is_none(self) -> None:
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        assert editor._target_annot is None


class TestShowForExisting:
    def test_prefills_content(self) -> None:
        editor = NoteEditor()
        editor.show_for_existing("sticky_note", 0, "mock_annot", "Existing text", 100, 200)
        assert editor._text_edit.toPlainText() == "Existing text"

    def test_sets_target_annot(self) -> None:
        editor = NoteEditor()
        editor.show_for_existing("sticky_note", 0, "mock_annot", "content", 100, 200)
        assert editor._target_annot == "mock_annot"

    def test_sets_mode(self) -> None:
        editor = NoteEditor()
        editor.show_for_existing("text_box", 1, "annot", "content", 100, 200)
        assert editor._mode == "text_box"


class TestSave:
    def test_emits_editing_finished_with_content(self, qtbot) -> None:
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        editor._text_edit.setPlainText("My note")
        with qtbot.waitSignal(editor.editing_finished, timeout=1000) as blocker:
            editor._on_save()
        assert blocker.args == ["My note"]

    def test_empty_content_shows_confirmation(self, qtbot) -> None:
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        editor._text_edit.setPlainText("")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            with qtbot.waitSignal(editor.editing_finished, timeout=1000) as blocker:
                editor._on_save()
            assert blocker.args == [""]

    def test_empty_content_cancel_keeps_open(self, qtbot) -> None:
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        editor._text_edit.setPlainText("")
        editor.show()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            editor._on_save()
        assert editor.isVisible()


class TestCancel:
    def test_emits_editing_cancelled(self, qtbot) -> None:
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        editor.show()
        with qtbot.waitSignal(editor.editing_cancelled, timeout=1000):
            editor._on_cancel()

    def test_hides_widget(self) -> None:
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        editor.show()
        editor._on_cancel()
        assert not editor.isVisible()

    def test_escape_key_cancels(self, qtbot) -> None:
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        editor.show()
        with qtbot.waitSignal(editor.editing_cancelled, timeout=1000):
            qtbot.keyPress(editor, Qt.Key.Key_Escape)
```

Run: `uv run pytest tests/test_note_editor.py -x` — expect ImportError (module doesn't exist).

- [ ] **Step 2: Write implementation**

Create `k_pdf/views/note_editor.py`:

```python
"""Floating editor widget for sticky note and text box content.

Provides a QTextEdit with Save/Cancel buttons. Positioned near
the annotation on screen. Emits editing_finished or editing_cancelled.
"""

from __future__ import annotations

import logging
from typing import Any, override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger("k_pdf.views.note_editor")


class NoteEditor(QWidget):
    """Floating frameless widget for editing annotation text content.

    Layout: [QTextEdit] / [Save] [Cancel]
    """

    editing_finished = Signal(str)
    editing_cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the note editor with text area and buttons."""
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedSize(250, 150)

        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("Enter note text...")

        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self._save_btn)
        btn_layout.addWidget(self._cancel_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._text_edit)
        layout.addLayout(btn_layout)

        self._target_page: int = 0
        self._target_annot: Any | None = None
        self._mode: str = "sticky_note"

    def show_for_new(self, mode: str, page_index: int, x: int, y: int) -> None:
        """Position editor for a new annotation.

        Args:
            mode: "sticky_note" or "text_box".
            page_index: Page index for the annotation.
            x: X coordinate in viewport pixels.
            y: Y coordinate in viewport pixels.
        """
        self._mode = mode
        self._target_page = page_index
        self._target_annot = None
        self._text_edit.clear()
        self.move(x, y)
        self.show()
        self._text_edit.setFocus()

    def show_for_existing(
        self,
        mode: str,
        page_index: int,
        annot: Any,
        content: str,
        x: int,
        y: int,
    ) -> None:
        """Position editor for an existing annotation.

        Args:
            mode: "sticky_note" or "text_box".
            page_index: Page index for the annotation.
            annot: Existing annotation reference.
            content: Current text content to pre-fill.
            x: X coordinate in viewport pixels.
            y: Y coordinate in viewport pixels.
        """
        self._mode = mode
        self._target_page = page_index
        self._target_annot = annot
        self._text_edit.setPlainText(content)
        self.move(x, y)
        self.show()
        self._text_edit.setFocus()

    def _on_save(self) -> None:
        """Handle Save click — emit editing_finished or show confirmation for empty."""
        content = self._text_edit.toPlainText()
        if not content:
            result = QMessageBox.question(
                self,
                "Empty Content",
                "Save annotation with empty content?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                return
        self.editing_finished.emit(content)
        self.hide()

    def _on_cancel(self) -> None:
        """Handle Cancel click — emit editing_cancelled and hide."""
        self.editing_cancelled.emit()
        self.hide()

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle Escape key to cancel editing."""
        if event.key() == Qt.Key.Key_Escape:
            self._on_cancel()
            return
        super().keyPressEvent(event)
```

Run: `uv run pytest tests/test_note_editor.py -x` — expect all pass.

- [ ] **Step 3: Lint/type-check**

Run: `uv run ruff check k_pdf/views/note_editor.py` and `uv run mypy k_pdf/views/note_editor.py`

Add mypy override for `k_pdf.views.note_editor` in pyproject.toml if needed.

---

### Task 4: Extend AnnotationPresenter (presenters/annotation_presenter.py)

**Files:**
- Modify: `k_pdf/presenters/annotation_presenter.py`
- Modify: `tests/test_annotation_presenter.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_annotation_presenter.py`:

```python
from k_pdf.presenters.annotation_presenter import AnnotationPresenter, ToolMode
from k_pdf.views.note_editor import NoteEditor


class TestToolMode:
    def test_enum_has_none(self) -> None:
        assert ToolMode.NONE.value == 0

    def test_enum_has_text_select(self) -> None:
        assert ToolMode.TEXT_SELECT.value == 1

    def test_enum_has_sticky_note(self) -> None:
        assert ToolMode.STICKY_NOTE.value == 2

    def test_enum_has_text_box(self) -> None:
        assert ToolMode.TEXT_BOX.value == 3


class TestSetToolMode:
    def test_sets_sticky_note_mode(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter.set_tool_mode(ToolMode.STICKY_NOTE)
        assert presenter._tool_mode is ToolMode.STICKY_NOTE

    def test_sets_text_box_mode(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter.set_tool_mode(ToolMode.TEXT_BOX)
        assert presenter._tool_mode is ToolMode.TEXT_BOX

    def test_emits_tool_mode_changed(self, qtbot) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        with qtbot.waitSignal(presenter.tool_mode_changed, timeout=1000) as blocker:
            presenter.set_tool_mode(ToolMode.STICKY_NOTE)
        assert blocker.args == [2]

    def test_set_selection_mode_shim_true(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter.set_selection_mode(True)
        assert presenter._tool_mode is ToolMode.TEXT_SELECT

    def test_set_selection_mode_shim_false(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter.set_selection_mode(True)
        presenter.set_selection_mode(False)
        assert presenter._tool_mode is ToolMode.NONE

    def test_none_mode_resets_cursor(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter.set_tool_mode(ToolMode.NONE)
        mock_viewport.set_tool_mode.assert_called_with(ToolMode.NONE)


class TestOnNotePlaced:
    def test_opens_note_editor(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        mock_viewport.mapToGlobal.return_value = MagicMock(
            x=MagicMock(return_value=100), y=MagicMock(return_value=200)
        )
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        presenter.on_note_placed(0, (100.0, 100.0))
        assert note_editor._mode == "sticky_note"
        assert note_editor._target_page == 0


class TestOnTextboxDrawn:
    def test_opens_note_editor(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        mock_viewport.mapToGlobal.return_value = MagicMock(
            x=MagicMock(return_value=100), y=MagicMock(return_value=200)
        )
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        presenter.on_textbox_drawn(0, (100.0, 200.0, 300.0, 250.0))
        assert note_editor._mode == "text_box"
        assert note_editor._target_page == 0


class TestOnEditingFinished:
    def test_creates_sticky_note(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)

        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        note_editor._mode = "sticky_note"
        note_editor._target_page = 0
        note_editor._target_annot = None
        presenter._pending_point = (100.0, 100.0)

        with patch.object(engine, "add_sticky_note", return_value=MagicMock()) as mock_add:
            presenter._on_editing_finished("My note")
            mock_add.assert_called_once_with(
                model.doc_handle, 0, (100.0, 100.0), "My note"
            )

    def test_creates_text_box(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)

        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        note_editor._mode = "text_box"
        note_editor._target_page = 0
        note_editor._target_annot = None
        presenter._pending_rect = (100.0, 200.0, 300.0, 250.0)

        with patch.object(engine, "add_text_box", return_value=MagicMock()) as mock_add:
            presenter._on_editing_finished("Box text")
            mock_add.assert_called_once_with(
                model.doc_handle, 0, (100.0, 200.0, 300.0, 250.0), "Box text"
            )

    def test_sets_dirty_flag(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)

        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        note_editor._mode = "sticky_note"
        note_editor._target_page = 0
        note_editor._target_annot = None
        presenter._pending_point = (100.0, 100.0)

        with patch.object(engine, "add_sticky_note", return_value=MagicMock()):
            presenter._on_editing_finished("Note")
            assert model.dirty is True

    def test_resets_tool_mode(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)

        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        note_editor._mode = "sticky_note"
        note_editor._target_page = 0
        note_editor._target_annot = None
        presenter._pending_point = (100.0, 100.0)
        presenter._tool_mode = ToolMode.STICKY_NOTE

        with patch.object(engine, "add_sticky_note", return_value=MagicMock()):
            presenter._on_editing_finished("Note")
            assert presenter._tool_mode is ToolMode.NONE

    def test_updates_existing_annotation(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)

        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        mock_annot = MagicMock()
        note_editor._mode = "sticky_note"
        note_editor._target_page = 0
        note_editor._target_annot = mock_annot

        with patch.object(engine, "update_annotation_content") as mock_update:
            presenter._on_editing_finished("Updated content")
            mock_update.assert_called_once_with(
                model.doc_handle, 0, mock_annot, "Updated content"
            )


class TestOnAnnotationDoubleClicked:
    def test_opens_editor_with_existing_content(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)
        mock_viewport = MagicMock()
        mock_viewport.mapToGlobal.return_value = MagicMock(
            x=MagicMock(return_value=100), y=MagicMock(return_value=200)
        )
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)

        note_editor = NoteEditor()
        presenter._note_editor = note_editor

        mock_annot = MagicMock()
        mock_annot.type = (0, 0)  # will be checked for type

        with patch.object(engine, "get_annotation_content", return_value="Existing"):
            presenter.on_annotation_double_clicked(0, mock_annot)
            assert note_editor._text_edit.toPlainText() == "Existing"


class TestTabSwitchCancelsEditor:
    def test_tab_switch_hides_editor_and_resets_mode(self) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        note_editor.show()
        presenter._tool_mode = ToolMode.STICKY_NOTE
        presenter.on_tab_switched("some-session-id")
        assert not note_editor.isVisible()
        assert presenter._tool_mode is ToolMode.NONE
```

Run: `uv run pytest tests/test_annotation_presenter.py -x` — expect failures for ToolMode import and missing methods.

- [ ] **Step 2: Write implementation**

Rewrite `k_pdf/presenters/annotation_presenter.py` with ToolMode enum, keeping all existing behavior for text markup:

```python
"""Annotation presenter — coordinates text selection, toolbar, note editor, and annotation engine.

Manages tool modes (text selection, sticky note, text box), floating toolbar visibility,
annotation creation/deletion/update, and the dirty flag. Subscribes to TabManager signals.
"""

from __future__ import annotations

import logging
from enum import IntEnum

from PySide6.QtCore import QObject, Signal

from k_pdf.core.annotation_model import AnnotationType
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.annotation_engine import AnnotationEngine
from k_pdf.views.annotation_toolbar import AnnotationToolbar

logger = logging.getLogger("k_pdf.presenters.annotation_presenter")


class ToolMode(IntEnum):
    """Active tool mode for viewport interaction."""

    NONE = 0
    TEXT_SELECT = 1
    STICKY_NOTE = 2
    TEXT_BOX = 3


class AnnotationPresenter(QObject):
    """Coordinates text selection, note editing, annotation toolbar, and annotation engine."""

    dirty_changed = Signal(bool)
    annotation_created = Signal()
    annotation_deleted = Signal()
    tool_mode_changed = Signal(int)

    def __init__(
        self,
        tab_manager: TabManager,
        engine: AnnotationEngine,
        toolbar: AnnotationToolbar,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._tab_manager = tab_manager
        self._engine = engine
        self._toolbar = toolbar

        self._tool_mode: ToolMode = ToolMode.NONE
        self._selection_mode: bool = False  # compat property
        self._selected_rects: list[tuple[float, float, float, float]] = []
        self._selected_page: int = -1

        self._note_editor: object | None = None
        self._pending_point: tuple[float, float] | None = None
        self._pending_rect: tuple[float, float, float, float] | None = None

        self._toolbar.annotation_requested.connect(self._on_annotation_requested)
        self._toolbar.dismissed.connect(self._on_toolbar_dismissed)
        self._tab_manager.tab_switched.connect(self.on_tab_switched)

    def set_note_editor(self, editor: object) -> None:
        """Set the NoteEditor widget reference."""
        self._note_editor = editor

    def set_tool_mode(self, mode: ToolMode) -> None:
        """Set the active tool mode."""
        self._tool_mode = mode
        self._selection_mode = mode is ToolMode.TEXT_SELECT
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.set_tool_mode(mode)
        if mode is ToolMode.NONE:
            self._clear_selection()
            self._toolbar.hide()
        self.tool_mode_changed.emit(int(mode))

    def set_selection_mode(self, active: bool) -> None:
        """Compatibility shim — sets TEXT_SELECT or NONE mode."""
        self.set_tool_mode(ToolMode.TEXT_SELECT if active else ToolMode.NONE)

    # ... (all existing methods preserved: on_text_selected, create_annotation,
    #      delete_annotation, _clear_selection, _on_annotation_requested,
    #      _on_toolbar_dismissed)

    def on_note_placed(self, page_index: int, point: tuple[float, float]) -> None:
        """Handle sticky note placement click from viewport."""
        self._pending_point = point
        self._pending_rect = None
        if self._note_editor is not None:
            viewport = self._tab_manager.get_active_viewport()
            x, y = 100, 200
            if viewport is not None:
                global_pos = viewport.mapToGlobal(viewport.rect().center())
                x, y = global_pos.x(), global_pos.y()
            self._note_editor.show_for_new("sticky_note", page_index, x, y)

    def on_textbox_drawn(
        self, page_index: int, rect: tuple[float, float, float, float]
    ) -> None:
        """Handle text box drag completion from viewport."""
        self._pending_rect = rect
        self._pending_point = None
        if self._note_editor is not None:
            viewport = self._tab_manager.get_active_viewport()
            x, y = 100, 200
            if viewport is not None:
                global_pos = viewport.mapToGlobal(viewport.rect().center())
                x, y = global_pos.x(), global_pos.y()
            self._note_editor.show_for_new("text_box", page_index, x, y)

    def on_annotation_double_clicked(self, page_index: int, annot: object) -> None:
        """Handle double-click on existing annotation — open editor with content."""
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return
        model = doc_presenter.model
        content = self._engine.get_annotation_content(model.doc_handle, page_index, annot)
        # Determine mode from annotation type
        annot_type = getattr(annot, "type", (0, 0))
        mode = "sticky_note" if annot_type[0] == 0 else "text_box"
        if self._note_editor is not None:
            viewport = self._tab_manager.get_active_viewport()
            x, y = 100, 200
            if viewport is not None:
                global_pos = viewport.mapToGlobal(viewport.rect().center())
                x, y = global_pos.x(), global_pos.y()
            self._note_editor.show_for_existing(mode, page_index, annot, content, x, y)

    def _on_editing_finished(self, content: str) -> None:
        """Handle NoteEditor save — create or update annotation."""
        if self._note_editor is None:
            return

        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return
        model = doc_presenter.model

        editor = self._note_editor
        target_annot = editor._target_annot
        page_index = editor._target_page
        mode = editor._mode

        if target_annot is not None:
            self._engine.update_annotation_content(
                model.doc_handle, page_index, target_annot, content
            )
        elif mode == "sticky_note" and self._pending_point is not None:
            self._engine.add_sticky_note(
                model.doc_handle, page_index, self._pending_point, content
            )
        elif mode == "text_box" and self._pending_rect is not None:
            self._engine.add_text_box(
                model.doc_handle, page_index, self._pending_rect, content
            )

        model.dirty = True
        self.dirty_changed.emit(True)
        self.annotation_created.emit()
        self._pending_point = None
        self._pending_rect = None
        self.set_tool_mode(ToolMode.NONE)

    def _on_editing_cancelled(self) -> None:
        """Handle NoteEditor cancel."""
        self._pending_point = None
        self._pending_rect = None
        self.set_tool_mode(ToolMode.NONE)

    def on_tab_switched(self, session_id: str) -> None:
        """Handle tab switch — clear selection, hide toolbar, cancel editing."""
        self._clear_selection()
        self._toolbar.hide()
        if self._note_editor is not None:
            self._note_editor.hide()
        self._tool_mode = ToolMode.NONE
        self._selection_mode = False
```

Run: `uv run pytest tests/test_annotation_presenter.py -x` — expect all pass.

- [ ] **Step 3: Lint/type-check**

---

### Task 5: Extend PdfViewport (views/pdf_viewport.py)

**Files:**
- Modify: `k_pdf/views/pdf_viewport.py`
- Create: `tests/test_viewport_note_placement.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_viewport_note_placement.py`:

```python
"""Tests for PdfViewport sticky note and text box placement modes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from k_pdf.core.document_model import PageInfo
from k_pdf.presenters.annotation_presenter import ToolMode
from k_pdf.views.pdf_viewport import PdfViewport

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestToolModeOnViewport:
    def test_default_mode_is_none(self) -> None:
        viewport = PdfViewport()
        assert viewport._tool_mode is ToolMode.NONE

    def test_set_tool_mode_sticky_note(self) -> None:
        viewport = PdfViewport()
        viewport.set_tool_mode(ToolMode.STICKY_NOTE)
        assert viewport._tool_mode is ToolMode.STICKY_NOTE

    def test_set_tool_mode_text_box(self) -> None:
        viewport = PdfViewport()
        viewport.set_tool_mode(ToolMode.TEXT_BOX)
        assert viewport._tool_mode is ToolMode.TEXT_BOX

    def test_sticky_note_mode_sets_crosshair_cursor(self) -> None:
        viewport = PdfViewport()
        viewport.set_tool_mode(ToolMode.STICKY_NOTE)
        assert viewport.cursor().shape() == Qt.CursorShape.CrossCursor

    def test_text_box_mode_sets_crosshair_cursor(self) -> None:
        viewport = PdfViewport()
        viewport.set_tool_mode(ToolMode.TEXT_BOX)
        assert viewport.cursor().shape() == Qt.CursorShape.CrossCursor

    def test_none_mode_restores_drag(self) -> None:
        viewport = PdfViewport()
        viewport.set_tool_mode(ToolMode.STICKY_NOTE)
        viewport.set_tool_mode(ToolMode.NONE)
        from PySide6.QtWidgets import QGraphicsView
        assert viewport.dragMode() == QGraphicsView.DragMode.ScrollHandDrag

    def test_text_select_mode_sets_ibeam(self) -> None:
        viewport = PdfViewport()
        viewport.set_tool_mode(ToolMode.TEXT_SELECT)
        assert viewport.cursor().shape() == Qt.CursorShape.IBeamCursor


class TestNotePlacedSignal:
    def test_signal_exists(self) -> None:
        viewport = PdfViewport()
        assert hasattr(viewport, "note_placed")

    def test_textbox_drawn_signal_exists(self) -> None:
        viewport = PdfViewport()
        assert hasattr(viewport, "textbox_drawn")

    def test_annotation_double_clicked_signal_exists(self) -> None:
        viewport = PdfViewport()
        assert hasattr(viewport, "annotation_double_clicked")
```

Run: `uv run pytest tests/test_viewport_note_placement.py -x` — expect failures for missing set_tool_mode and signals.

- [ ] **Step 2: Write implementation**

Modify `k_pdf/views/pdf_viewport.py`:
- Import ToolMode
- Add `note_placed`, `textbox_drawn`, `annotation_double_clicked` signals
- Add `_tool_mode` attribute, `set_tool_mode()` method
- Update `set_selection_mode` to call `set_tool_mode`
- Update `mousePressEvent` to handle STICKY_NOTE click
- Update `mousePressEvent`/`mouseMoveEvent`/`mouseReleaseEvent` for TEXT_BOX drag
- Add `mouseDoubleClickEvent` for annotation editing
- Add `_textbox_drag_start`/`_textbox_drag_rect` for drag preview

Run: `uv run pytest tests/test_viewport_note_placement.py tests/test_viewport_selection.py -x` — expect all pass.

- [ ] **Step 3: Lint/type-check**

---

### Task 6: Extend MainWindow (views/main_window.py)

**Files:**
- Modify: `k_pdf/views/main_window.py`

- [ ] **Step 1: Write failing tests** (tested via existing test_views.py pattern + integration)

Add assertions in test_sticky_note_integration.py (Task 8).

- [ ] **Step 2: Write implementation**

Modify `k_pdf/views/main_window.py`:
- Add `sticky_note_toggled = Signal(bool)` and `text_box_toggled = Signal(bool)` signals
- In `_setup_menus`, create QActionGroup for tool modes
- Add "Sticky &Note" and "Text &Box" checkable actions
- Make existing "Text Selection Mode" part of the action group

- [ ] **Step 3: Lint/type-check**

---

### Task 7: Wire KPdfApp (app.py)

**Files:**
- Modify: `k_pdf/app.py`

- [ ] **Step 1: Write implementation**

Modify `k_pdf/app.py`:
- Import NoteEditor, ToolMode
- Create NoteEditor instance
- Pass to AnnotationPresenter via `set_note_editor()`
- Connect MainWindow sticky_note_toggled -> set_tool_mode(ToolMode.STICKY_NOTE)
- Connect MainWindow text_box_toggled -> set_tool_mode(ToolMode.TEXT_BOX)
- Connect viewport note_placed -> presenter on_note_placed
- Connect viewport textbox_drawn -> presenter on_textbox_drawn
- Connect viewport annotation_double_clicked -> presenter on_annotation_double_clicked
- Connect NoteEditor editing_finished -> presenter _on_editing_finished
- Connect NoteEditor editing_cancelled -> presenter _on_editing_cancelled
- Connect presenter tool_mode_changed -> update MainWindow tool check states

- [ ] **Step 2: Lint/type-check**

---

### Task 8: Integration Tests

**Files:**
- Create: `tests/test_sticky_note_integration.py`

- [ ] **Step 1: Write integration tests**

```python
"""Integration tests for sticky note and text box annotation flows."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.presenters.annotation_presenter import ToolMode


_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _wait_for_document(kpdf: KPdfApp, qtbot: object) -> None:
    tm = kpdf.tab_manager

    def check_loaded() -> None:
        assert tm.get_active_presenter() is not None
        assert tm.get_active_presenter().model is not None

    qtbot.waitUntil(check_loaded, timeout=10000)


def test_place_sticky_note(annotatable_pdf: Path, qtbot: object) -> None:
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None and presenter.model is not None

    # Simulate: set sticky note mode, place note, fill content, save
    ap.set_tool_mode(ToolMode.STICKY_NOTE)
    ap._pending_point = (100.0, 100.0)
    ap._note_editor._mode = "sticky_note"
    ap._note_editor._target_page = 0
    ap._note_editor._target_annot = None
    ap._on_editing_finished("Test sticky note")

    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) >= 1
    assert presenter.model.dirty is True

    kpdf.shutdown()


def test_draw_text_box(annotatable_pdf: Path, qtbot: object) -> None:
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None and presenter.model is not None

    ap.set_tool_mode(ToolMode.TEXT_BOX)
    ap._pending_rect = (100.0, 200.0, 300.0, 250.0)
    ap._note_editor._mode = "text_box"
    ap._note_editor._target_page = 0
    ap._note_editor._target_annot = None
    ap._on_editing_finished("Text box content")

    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) >= 1

    kpdf.shutdown()


def test_edit_existing_sticky_note(annotatable_pdf: Path, qtbot: object) -> None:
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None and presenter.model is not None

    # Create a note first
    kpdf._annotation_engine.add_sticky_note(
        presenter.model.doc_handle, 0, (100.0, 100.0), "Original"
    )
    annot = list(presenter.model.doc_handle[0].annots())[0]

    # Simulate double-click edit
    ap.on_annotation_double_clicked(0, annot)
    assert ap._note_editor._text_edit.toPlainText() == "Original"

    # Update content
    ap._note_editor._target_annot = annot
    ap._on_editing_finished("Updated content")

    # Verify update
    refreshed = list(presenter.model.doc_handle[0].annots())[0]
    content = kpdf._annotation_engine.get_annotation_content(
        presenter.model.doc_handle, 0, refreshed
    )
    assert content == "Updated content"

    kpdf.shutdown()


def test_cancel_editing(annotatable_pdf: Path, qtbot: object) -> None:
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None and presenter.model is not None

    ap.set_tool_mode(ToolMode.STICKY_NOTE)
    ap._pending_point = (100.0, 100.0)
    ap._on_editing_cancelled()

    # No annotation should be created
    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) == 0

    kpdf.shutdown()


def test_tool_mode_resets_after_creation(annotatable_pdf: Path, qtbot: object) -> None:
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    ap.set_tool_mode(ToolMode.STICKY_NOTE)
    ap._pending_point = (100.0, 100.0)
    ap._note_editor._mode = "sticky_note"
    ap._note_editor._target_page = 0
    ap._note_editor._target_annot = None
    ap._on_editing_finished("Note")

    assert ap._tool_mode is ToolMode.NONE

    kpdf.shutdown()
```

Run: `uv run pytest tests/test_sticky_note_integration.py -x` — expect all pass.

---

### Task 9: Update pyproject.toml and CLAUDE.md

**Files:**
- Modify: `pyproject.toml` — add mypy overrides for `k_pdf.views.note_editor`
- Modify: `CLAUDE.md` — update Features built, session summary

- [ ] **Step 1: Update pyproject.toml**
- [ ] **Step 2: Update CLAUDE.md**
- [ ] **Step 3: Run full test suite**

Run: `uv run pytest --cov=k_pdf --cov-report=term-missing`

---

## Summary

| Task | Files | Type |
|------|-------|------|
| 1 | annotation_model.py + tests | Extend model |
| 2 | annotation_engine.py + tests | Extend engine |
| 3 | note_editor.py + tests | New widget |
| 4 | annotation_presenter.py + tests | Extend presenter |
| 5 | pdf_viewport.py + tests | Extend viewport |
| 6 | main_window.py | Extend menu |
| 7 | app.py | Wire signals |
| 8 | test_sticky_note_integration.py | Integration tests |
| 9 | pyproject.toml + CLAUDE.md | Config + docs |
