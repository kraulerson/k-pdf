# Feature 7: Sticky Notes & Text Box Annotations — Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Depends on:** Feature 1 (Open/Render), Feature 2 (Multi-Tab), Feature 5 (Zoom/Rotate), Feature 6 (Text Markup Annotations)
**FRD Reference:** FUNCTIONAL_REQUIREMENTS.md Section 2, Feature 7
**UI Reference:** UI_SCAFFOLDING.md Section 2.2 (Annotation Toolbar)

---

## 1. Architecture Overview

**AnnotationEngine extensions:** Extend the existing AnnotationEngine (services/) with `add_sticky_note()` and `add_text_box()` methods. PyMuPDF isolation rule unchanged — all fitz calls remain in this service. Also adds `update_annotation_content()` to modify note/textbox text after creation.

**AnnotationPresenter extensions:** Extend the existing AnnotationPresenter (presenters/) with a `ToolMode` enum (NONE, TEXT_SELECT, STICKY_NOTE, TEXT_BOX) replacing the boolean `_selection_mode`. The active tool mode determines viewport interaction behavior: NONE is pan mode, TEXT_SELECT is existing drag-to-select, STICKY_NOTE is click-to-place, TEXT_BOX is drag-to-draw.

**NoteEditor:** New floating QWidget for editing sticky note and text box content. Contains a QTextEdit, positioned near the annotation on screen. Emits `editing_finished(str)` when the user clicks Save. If content is empty on save, shows a "Save anyway?" confirmation dialog.

### Signal Flow

1. User selects "Sticky Note" or "Text Box" from Tools menu -> `AnnotationPresenter.set_tool_mode(ToolMode.STICKY_NOTE)` or `set_tool_mode(ToolMode.TEXT_BOX)` — viewport cursor changes to crosshair
2. **Sticky Note:** User clicks a point on the page -> `PdfViewport` emits `note_placed(page_index, point)` -> `AnnotationPresenter` opens `NoteEditor` near click point
3. **Text Box:** User click-drags a rectangle on the page -> `PdfViewport` emits `textbox_drawn(page_index, rect)` -> `AnnotationPresenter` opens `NoteEditor` for the drawn region
4. User types content in `NoteEditor`, clicks Save -> `NoteEditor` emits `editing_finished(str)` -> `AnnotationPresenter` calls `AnnotationEngine.add_sticky_note()` or `add_text_box()` -> page re-rendered -> `model.dirty = True` -> tab title shows `*` prefix
5. User double-clicks existing sticky note icon or text box -> `PdfViewport` emits `annotation_double_clicked(page_index, annot)` -> `AnnotationPresenter` opens `NoteEditor` pre-filled with existing content -> on save, calls `AnnotationEngine.update_annotation_content()`
6. Annotation placed outside page bounds -> snapped to nearest page edge before creation

---

## 2. New Files

### `k_pdf/views/note_editor.py`

**`NoteEditor(QWidget)` — floating editor widget, frameless with shadow.**

Layout: [QTextEdit] | [Save btn] [Cancel btn]

Instance variables:
- `_text_edit: QTextEdit` — multi-line text input
- `_target_page: int` — page index of the annotation being edited
- `_target_annot: Any | None` — existing annotation reference (None for new)
- `_mode: str` — `"sticky_note"` or `"text_box"`, determines which engine method to call

Signals:
- `editing_finished(str)` — emitted when user clicks Save; str is the content text
- `editing_cancelled()` — emitted when user clicks Cancel or presses Escape

Methods:
- `show_for_new(mode: str, page_index: int, x: int, y: int)` — positions editor near (x, y) in viewport coordinates, clears text, sets mode
- `show_for_existing(mode: str, page_index: int, annot: Any, content: str, x: int, y: int)` — positions editor near annotation, pre-fills QTextEdit with existing content
- `_on_save()` — if content is empty, shows "Save annotation with empty content?" dialog (QMessageBox Yes/No); if Yes or non-empty, emits `editing_finished`
- `_on_cancel()` — emits `editing_cancelled`, hides widget

Size: 250x150 default, resizable. QTextEdit has placeholder text "Enter note text...".

---

## 3. Modified Files

### `k_pdf/core/annotation_model.py`

**Extend `AnnotationType` enum:**

| Value | Description |
|---|---|
| `HIGHLIGHT` | (existing) Filled background behind text |
| `UNDERLINE` | (existing) Line drawn below text |
| `STRIKETHROUGH` | (existing) Line drawn through text |
| `STICKY_NOTE` | Note icon placed at a point on the page |
| `TEXT_BOX` | Free-text box drawn as a rectangle on the page |

**Extend `AnnotationData` dataclass:**

| Field | Type | Default | Description |
|---|---|---|---|
| `content` | `str` | `""` | Text content for sticky notes and text boxes |
| `rect` | `tuple[float, float, float, float] \| None` | `None` | Bounding rectangle (x0, y0, x1, y1) for text boxes; None for text markup types |

Existing fields (`type`, `page`, `quads`, `color`, `author`, `created_at`) unchanged.

### `k_pdf/services/annotation_engine.py`

New methods:

- `add_sticky_note(doc_handle, page_index: int, point: tuple[float, float], content: str, author: str = "") -> fitz.Annot` — calls `page.add_text_annot(point, content, icon="Note")`, sets author if provided, returns annotation reference
- `add_text_box(doc_handle, page_index: int, rect: tuple[float, float, float, float], content: str, color: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> fitz.Annot` — calls `page.add_freetext_annot(rect, content, fontsize=11, fontname="helv", text_color=color)`, returns annotation reference
- `update_annotation_content(doc_handle, page_index: int, annot, content: str)` — updates the text content of an existing sticky note or text box annotation via `annot.set_info(content=content)` and `annot.update()`
- `get_annotation_content(doc_handle, page_index: int, annot) -> str` — reads text content from an annotation via `annot.info["content"]`

### `k_pdf/presenters/annotation_presenter.py`

**New `ToolMode` enum** (defined at module level):

| Value | Description |
|---|---|
| `NONE` | Pan mode (default) |
| `TEXT_SELECT` | Existing text selection mode from Feature 6 |
| `STICKY_NOTE` | Click-to-place sticky note |
| `TEXT_BOX` | Drag-to-draw text box |

Replace `_selection_mode: bool` with `_tool_mode: ToolMode`.

New instance variable:
- `_note_editor: NoteEditor` — reference to the floating editor widget

New/modified methods:
- `set_tool_mode(mode: ToolMode)` — replaces `set_selection_mode()`. Sets viewport interaction mode, updates cursor (I-beam for TEXT_SELECT, crosshair for STICKY_NOTE/TEXT_BOX, arrow for NONE)
- `set_selection_mode(active: bool)` — kept as compatibility shim, calls `set_tool_mode(ToolMode.TEXT_SELECT if active else ToolMode.NONE)`
- `on_note_placed(page_index: int, point: tuple[float, float])` — opens NoteEditor for new sticky note
- `on_textbox_drawn(page_index: int, rect: tuple[float, float, float, float])` — opens NoteEditor for new text box
- `on_annotation_double_clicked(page_index: int, annot)` — reads existing content from engine, opens NoteEditor for editing
- `_on_editing_finished(content: str)` — calls appropriate engine method (add or update), sets dirty flag, re-renders page, resets tool mode to NONE

New signals:
- `tool_mode_changed(int)` — emitted when tool mode changes (int is ToolMode value)

### `k_pdf/views/pdf_viewport.py`

New signals:
- `note_placed(int, tuple)` — emitted when user clicks in STICKY_NOTE mode; int is page_index, tuple is (x, y) in PDF coordinates
- `textbox_drawn(int, tuple)` — emitted when user completes drag in TEXT_BOX mode; int is page_index, tuple is (x0, y0, x1, y1) in PDF coordinates
- `annotation_double_clicked(int, object)` — emitted when user double-clicks an existing annotation

New behavior:
- `mousePressEvent` override: if STICKY_NOTE mode, map click to PDF coordinates, snap to page bounds, emit `note_placed`
- `mousePressEvent`/`mouseMoveEvent`/`mouseReleaseEvent` override: if TEXT_BOX mode, track drag rectangle, render preview outline during drag, snap to page bounds, emit `textbox_drawn` on release
- `mouseDoubleClickEvent` override: hit-test annotations at click point via `AnnotationEngine.get_annotations()`, emit `annotation_double_clicked` if a sticky note or text box annotation found
- Render sticky note icons (small note glyph) at annotation position during page paint
- Render text box borders (dashed rectangle outline) during page paint

### `k_pdf/views/main_window.py`

New additions to Tools menu:
- "Sticky &Note" action — checkable, exclusive with other tool modes, sets ToolMode.STICKY_NOTE
- "Text &Box" action — checkable, exclusive with other tool modes, sets ToolMode.TEXT_BOX
- Existing "Text Selection Mode" updated to participate in exclusive tool mode group (QActionGroup)

New signals:
- `sticky_note_toggled(bool)` — emitted when Sticky Note tool toggled
- `text_box_toggled(bool)` — emitted when Text Box tool toggled

### `k_pdf/app.py`

New wiring:
- Create `NoteEditor` instance
- Connect MainWindow Sticky Note / Text Box toggle -> `AnnotationPresenter.set_tool_mode`
- Connect `PdfViewport.note_placed` -> `AnnotationPresenter.on_note_placed`
- Connect `PdfViewport.textbox_drawn` -> `AnnotationPresenter.on_textbox_drawn`
- Connect `PdfViewport.annotation_double_clicked` -> `AnnotationPresenter.on_annotation_double_clicked`
- Connect `NoteEditor.editing_finished` -> `AnnotationPresenter._on_editing_finished`
- Connect `NoteEditor.editing_cancelled` -> hide editor, reset tool mode
- Connect `AnnotationPresenter.tool_mode_changed` -> update MainWindow tool menu check states

---

## 4. Unchanged Files

- `k_pdf/core/document_model.py` — unchanged (dirty flag is a simple bool attribute)
- `k_pdf/core/page_cache.py` — unchanged (annotation rendering handled by PyMuPDF during page render)
- `k_pdf/core/zoom_model.py` — unchanged
- `k_pdf/core/search_model.py` — unchanged
- `k_pdf/services/pdf_engine.py` — unchanged (`render_page` already renders annotations embedded in the PDF page)
- `k_pdf/services/search_engine.py` — unchanged
- `k_pdf/presenters/document_presenter.py` — unchanged
- `k_pdf/presenters/navigation_presenter.py` — unchanged
- `k_pdf/presenters/search_presenter.py` — unchanged
- `k_pdf/presenters/tab_manager.py` — unchanged (existing `tab_switched` signal reused)
- `k_pdf/views/annotation_toolbar.py` — unchanged (floating toolbar for text markup remains separate from NoteEditor)
- `k_pdf/views/zoom_toolbar.py` — unchanged
- `k_pdf/views/search_bar.py` — unchanged
- `k_pdf/views/navigation_panel.py` — unchanged

---

## 5. Accessibility

- Tool modes distinguished by cursor shape (arrow, I-beam, crosshair) and checkable menu item state — never by color alone
- Tools menu items have text labels with keyboard mnemonics ("Sticky &Note", "Text &Box")
- NoteEditor uses standard QTextEdit with full keyboard support (Tab for indent, Shift+Tab for outdent)
- Save and Cancel buttons in NoteEditor have text labels, not icon-only
- NoteEditor accessible via keyboard: double-click annotation or use tool mode + click — no mouse-only activation path for editing
- Empty-content confirmation dialog uses standard QMessageBox with labeled buttons
- Sticky note icons rendered with a distinct shape (note glyph), not differentiated from text boxes by color alone — text boxes have a visible rectangular border

---

## 6. Error Handling & Edge Cases

**Annotation outside page bounds:** If the user clicks or drags outside the page area (but within the viewport), the annotation point or rectangle is snapped to the nearest page edge. No error shown — the operation proceeds silently with the clamped coordinates.

**Empty content on save:** NoteEditor shows "Save annotation with empty content?" confirmation dialog (Yes/No). If Yes, annotation is created with empty content. If No, editor stays open.

**Double-click on overlapping annotations:** Hit-tests the topmost annotation at the click point. Only one NoteEditor opens at a time.

**NoteEditor open during tab switch:** Editor is hidden and editing is cancelled (no save). The partially typed content is discarded. Tool mode resets to NONE.

**Read-only file:** Annotations still work in-memory and render on screen. Save restriction handled in Feature 8.

**Dirty flag:** `model.dirty = True` on annotation create, update, or delete. Tab title gains `*` prefix. Save/Discard/Cancel close-guard dialog deferred to Feature 8.

**Very large text content:** QTextEdit has no artificial character limit. PyMuPDF handles large content strings natively. If the text exceeds the text box rect, PyMuPDF clips the rendered text.

**Zoom/rotation:** Annotation placement coordinates are mapped through the current zoom and rotation transform. NoteEditor positioning uses viewport (screen) coordinates so it always appears near the annotation regardless of zoom level.

---

## 7. Testing Strategy

### Unit Tests

| File | Tests |
|---|---|
| `tests/test_annotation_model.py` | Extended: `AnnotationType` enum includes STICKY_NOTE and TEXT_BOX, `AnnotationData` construction with `content` and `rect` fields, default `content` is empty string, default `rect` is None |
| `tests/test_annotation_engine.py` | Extended: `add_sticky_note` creates text annotation on page (real PDF fixture), `add_text_box` creates freetext annotation, `update_annotation_content` modifies existing annotation content, `get_annotation_content` reads content from annotation |
| `tests/test_annotation_presenter.py` | Extended: `set_tool_mode` sets correct mode and cursor, `on_note_placed` opens NoteEditor, `on_textbox_drawn` opens NoteEditor, `on_annotation_double_clicked` opens NoteEditor with existing content, `_on_editing_finished` calls engine and sets dirty flag, tool mode resets to NONE after creation |
| `tests/test_note_editor.py` | `show_for_new` positions editor and clears text, `show_for_existing` pre-fills content, Save click emits `editing_finished` with content, Cancel click emits `editing_cancelled`, empty content triggers confirmation dialog, Escape key cancels editing |
| `tests/test_viewport_note_placement.py` | Click in STICKY_NOTE mode emits `note_placed` with correct page and point, drag in TEXT_BOX mode emits `textbox_drawn` with correct rect, double-click on annotation emits `annotation_double_clicked`, out-of-bounds click snaps to page edge |

### Integration Tests (`tests/test_sticky_note_integration.py`)

| Test | Verifies |
|---|---|
| `test_place_sticky_note` | Select Sticky Note tool -> click on page -> type content -> Save -> annotation exists on page, dirty flag is True |
| `test_draw_text_box` | Select Text Box tool -> drag rectangle -> type content -> Save -> freetext annotation exists with correct rect |
| `test_edit_existing_sticky_note` | Create sticky note -> double-click icon -> editor shows existing content -> modify -> Save -> content updated |
| `test_edit_existing_text_box` | Create text box -> double-click border -> editor shows existing content -> modify -> Save -> content updated |
| `test_empty_content_confirmation` | Place note -> leave content empty -> Save -> confirmation dialog appears -> click Yes -> annotation created with empty content |
| `test_cancel_editing` | Place note -> type content -> Cancel -> no annotation created |
| `test_snap_to_page_bounds` | Click outside page area -> annotation snapped to page edge |
| `test_tab_switch_cancels_editing` | Open NoteEditor -> switch tab -> editor hidden, no annotation created |

**Mocking:** PyMuPDF mocked in presenter unit tests. Engine tests and integration tests use real fixture PDFs.

**Coverage target:** Maintain 65%+.

---

## 8. Deferred Items

- **Edit Properties context menu** — changing color, icon style, font size of existing sticky notes and text boxes deferred to a future feature.
- **Annotation summary panel** — list/filter/navigate all annotations including notes deferred to Feature 12.
- **Undo/redo** — annotation create/edit/delete undo stack deferred to a future feature.
- **Rich text in notes** — NoteEditor uses plain text only; rich text formatting (bold, italic) deferred.
- **Resize existing text boxes** — drag handles on text box borders for resizing deferred.
- **Note icon style selection** — PyMuPDF supports multiple icon styles (Note, Comment, Help, etc.); hardcoded to "Note" in MVP.
- **Annotation reply threads** — threaded replies to sticky notes deferred.
