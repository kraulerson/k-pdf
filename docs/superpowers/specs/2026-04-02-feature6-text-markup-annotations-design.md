# Feature 6: Text Markup Annotations — Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Depends on:** Feature 1 (Open/Render), Feature 2 (Multi-Tab), Feature 5 (Zoom/Rotate)
**FRD Reference:** FUNCTIONAL_REQUIREMENTS.md Section 2, Feature 6
**UI Reference:** UI_SCAFFOLDING.md Section 2.2 (Annotation Toolbar)

---

## 1. Architecture Overview

**AnnotationEngine (service):** New service in services/ that wraps all PyMuPDF annotation creation/deletion operations. PyMuPDF is isolated entirely within this service — no other layer imports fitz directly for annotations. Also exposes `get_text_words()` for text selection coordinate lookup.

**AnnotationPresenter:** New presenter in presenters/ that manages text selection mode, selected text quads, floating toolbar visibility, annotation creation/deletion, and the dirty flag. Subscribes to TabManager signals for tab-switch coordination.

**Text selection mode:** A toggle — when active, click-drag in the viewport selects text instead of panning. The viewport maps mouse coordinates to PDF coordinates (accounting for zoom/rotation), queries AnnotationEngine for word rectangles, and emits a `text_selected` signal with the page index and quad list.

### Signal Flow

1. User clicks text-select tool in Tools menu → `PdfViewport.set_selection_mode(True)` — drag now selects text instead of panning
2. User click-drags over text → viewport maps mouse coords to PDF coords via current zoom/rotation, calls `AnnotationEngine.get_text_words()` for word rects, highlights selected words, emits `text_selected(page_index, quads)`
3. `AnnotationPresenter` receives `text_selected` → shows floating `AnnotationToolbar` near the selection
4. User clicks Highlight (or Underline/Strikethrough) → `AnnotationPresenter` calls `AnnotationEngine.add_highlight()` (or `add_underline()` / `add_strikeout()`) with doc handle, page, quads, and color → page re-rendered → `model.dirty = True` → tab title shows `*` prefix
5. Right-click on existing annotation → context menu with "Delete" → `AnnotationPresenter` calls `AnnotationEngine.delete_annotation()` → page re-rendered → dirty flag set

---

## 2. New Files

### `k_pdf/core/annotation_model.py`

**`AnnotationType` enum:**

| Value | Description |
|---|---|
| `HIGHLIGHT` | Filled background behind text |
| `UNDERLINE` | Line drawn below text |
| `STRIKETHROUGH` | Line drawn through text |

**`AnnotationData` dataclass (frozen=False):**

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | `AnnotationType` | — | Annotation kind |
| `page` | `int` | — | Zero-based page index |
| `quads` | `list[tuple]` | — | Quad-point coordinates defining the annotated region |
| `color` | `tuple[float, float, float]` | — | RGB color as 0.0–1.0 floats |
| `author` | `str` | `""` | Author name (optional metadata) |
| `created_at` | `datetime` | `field(default_factory=datetime.now)` | Creation timestamp |

### `k_pdf/services/annotation_engine.py`

Replaces existing stub. PyMuPDF annotation operations isolated here.

Methods:
- `add_highlight(doc_handle, page_index: int, quads: list, color: tuple) -> fitz.Annot` — calls `page.add_highlight_annot(quads)`, sets color, returns annotation reference
- `add_underline(doc_handle, page_index: int, quads: list, color: tuple) -> fitz.Annot` — calls `page.add_underline_annot(quads)`, sets color
- `add_strikeout(doc_handle, page_index: int, quads: list, color: tuple) -> fitz.Annot` — calls `page.add_strikeout_annot(quads)`, sets color
- `delete_annotation(doc_handle, page_index: int, annot: fitz.Annot)` — calls `page.delete_annot(annot)`
- `get_text_words(doc_handle, page_index: int) -> list[tuple]` — calls `page.get_text("words")`, returns list of `(x0, y0, x1, y1, word, block_no, line_no, word_no)` tuples for hit-testing during text selection
- `get_annotations(doc_handle, page_index: int) -> list[fitz.Annot]` — returns all annotations on a page for hit-testing right-click context menu

### `k_pdf/presenters/annotation_presenter.py`

Replaces existing stub.

Instance variables:
- `_selection_mode: bool` — whether text selection mode is active
- `_selected_quads: list[tuple]` — quads from the most recent text selection
- `_selected_page: int` — page index of the most recent text selection

Signals:
- `dirty_changed(bool)` — emitted when dirty flag transitions
- `toolbar_requested(int, int, list)` — emitted to show floating toolbar at (x, y) with quads

Methods:
- `set_selection_mode(active: bool)` — toggles text selection mode on the active viewport
- `on_text_selected(page_index: int, quads: list)` — stores selection, calculates toolbar position, shows `AnnotationToolbar`
- `create_annotation(ann_type: AnnotationType, color: tuple)` — calls appropriate `AnnotationEngine` method with stored quads, sets `model.dirty = True`, updates tab title, triggers page re-render
- `delete_annotation(page_index: int, annot)` — calls `AnnotationEngine.delete_annotation()`, sets dirty flag, triggers re-render
- `on_tab_switched(index: int)` — hides toolbar, clears selection state, syncs selection mode to new tab

Subscribes to:
- `TabManager.tab_switched` — to clear selection and hide toolbar
- `PdfViewport.text_selected` — to handle new text selections

### `k_pdf/views/annotation_toolbar.py`

**`AnnotationToolbar(QWidget)` — floating widget, frameless.**

Layout: [Highlight btn] [Underline btn] [Strikethrough btn] | [Color picker dropdown]

Buttons: icon + text label for each annotation type.

Color picker dropdown — named colors with text labels:

| Name | RGB (0–1) | Default for |
|---|---|---|
| Yellow | (1.0, 1.0, 0.0) | Highlight |
| Red | (1.0, 0.0, 0.0) | Underline, Strikethrough |
| Green | (0.0, 0.8, 0.0) | — |
| Blue | (0.0, 0.0, 1.0) | — |
| Orange | (1.0, 0.65, 0.0) | — |
| Purple | (0.5, 0.0, 0.5) | — |

Signals:
- `annotation_requested(AnnotationType, tuple)` — emitted when user clicks a type button; tuple is the selected color
- `dismissed()` — emitted when toolbar loses focus or user clicks away

Methods:
- `show_near(x: int, y: int)` — positions the toolbar near the given viewport coordinates, clamped to stay within the window
- `set_color(color: tuple)` — updates the active color in the picker

---

## 3. Modified Files

### `k_pdf/views/pdf_viewport.py`

New signals:
- `text_selected(int, list)` — emitted after click-drag text selection completes; int is page_index, list is quad-point coordinates of selected words

New methods:
- `set_selection_mode(active: bool)` — toggles between pan mode and text selection mode; changes cursor to I-beam when active

New behavior:
- `mousePressEvent` override: if selection mode active, begin tracking drag start point in scene coordinates
- `mouseMoveEvent` override: if selection mode active and dragging, map mouse position to PDF coordinates (accounting for zoom/rotation), query word rects from `AnnotationEngine.get_text_words()`, paint selection overlay on matching words
- `mouseReleaseEvent` override: if selection mode active and words selected, emit `text_selected(page_index, quads)`
- Selection overlay: semi-transparent blue rectangle over selected word regions, cleared when selection mode toggled off or new selection starts

### `k_pdf/views/main_window.py`

New additions:
- Tools menu: "Text Selection Mode" toggle action (Ctrl+T) — checkable, toggles selection mode on viewport
- Expose `tools_menu` property for wiring

### `k_pdf/app.py`

New wiring:
- Create `AnnotationPresenter` instance
- Connect MainWindow Tools menu text-selection toggle → `AnnotationPresenter.set_selection_mode`
- Connect `PdfViewport.text_selected` → `AnnotationPresenter.on_text_selected`
- Connect `AnnotationPresenter.toolbar_requested` → show `AnnotationToolbar` near selection
- Connect `AnnotationToolbar.annotation_requested` → `AnnotationPresenter.create_annotation`
- Connect `AnnotationToolbar.dismissed` → hide toolbar, clear selection overlay
- Connect `TabManager.tab_switched` → `AnnotationPresenter.on_tab_switched`
- Connect `AnnotationPresenter.dirty_changed` → update tab title with `*` prefix

### `k_pdf/presenters/tab_manager.py`

No structural changes. `AnnotationPresenter` subscribes to the existing `tab_switched` signal. Tab title update for dirty flag uses existing `set_tab_text()` method.

---

## 4. Unchanged Files

- `k_pdf/core/document_model.py` — unchanged (dirty flag is a simple bool attribute, no model changes needed)
- `k_pdf/core/page_cache.py` — unchanged (annotation rendering handled by PyMuPDF during page render)
- `k_pdf/core/zoom_model.py` — unchanged
- `k_pdf/services/pdf_engine.py` — unchanged (`render_page` already renders annotations embedded in the PDF page)
- `k_pdf/presenters/document_presenter.py` — unchanged
- `k_pdf/presenters/navigation_presenter.py` — unchanged
- `k_pdf/presenters/search_presenter.py` — unchanged
- `k_pdf/views/zoom_toolbar.py` — unchanged

---

## 5. Accessibility

- Annotation types distinguished by rendering style (filled background vs. line below vs. line through), never by color alone
- All toolbar buttons have icon + text label (e.g., "Highlight", "Underline", "Strikethrough") — not icon-only
- Color picker uses named color labels (e.g., "Yellow", "Red") alongside swatches
- Text selection mode indicated by cursor change (I-beam) and checkable menu item state
- Keyboard shortcut (Ctrl+T) to toggle selection mode — no mouse-only activation path
- Context menu for annotation deletion accessible via keyboard (Shift+F10 / Menu key)

---

## 6. Error Handling & Edge Cases

**No text layer:** When `get_text_words()` returns an empty list for a page, show a notification: *"Text markup requires selectable text. This page does not have a text layer."* Auto-dismiss after 5 seconds. Selection overlay is not shown.

**Read-only file:** When the PDF is opened read-only (e.g., file permissions), show a notification: *"This file is read-only. Use File > Save As to save a copy with annotations."* Annotations still work in-memory and render on screen — the restriction only applies to saving, which is handled in Feature 8.

**Dirty flag:** `model.dirty = True` on annotation create or delete. Tab title gains `*` prefix (e.g., `*document.pdf`). Full Save/Discard/Cancel close-guard dialog deferred to Feature 8.

**Empty selection:** If click-drag covers no words (e.g., dragging over whitespace), no `text_selected` signal is emitted. Toolbar does not appear.

**Selection across page boundary:** Not supported in MVP. Selection is confined to a single page. If the drag crosses a page boundary, only words on the starting page are selected.

**Zoom/rotation during selection:** Selection coordinates are mapped through the current zoom and rotation transform. Word rectangles from `get_text_words()` are in PDF coordinates and are transformed to viewport coordinates for overlay rendering.

**Annotation overlap:** Multiple annotations on the same text are allowed. PyMuPDF handles stacking natively. Delete operates on the topmost annotation at the click point.

**Tab switch with active selection:** Selection is cleared and toolbar is hidden when switching tabs.

---

## 7. Testing Strategy

### Unit Tests

| File | Tests |
|---|---|
| `tests/test_annotation_model.py` | `AnnotationType` enum values (HIGHLIGHT, UNDERLINE, STRIKETHROUGH), `AnnotationData` construction with all fields, default `author` is empty string, default `created_at` is set automatically |
| `tests/test_annotation_engine.py` | `add_highlight` creates annotation on page (real PDF fixture), `add_underline` creates annotation, `add_strikeout` creates annotation, `delete_annotation` removes annotation, `get_text_words` returns word rects for text page, `get_text_words` returns empty list for image-only page |
| `tests/test_annotation_presenter.py` | `set_selection_mode` toggles mode, `on_text_selected` stores quads and emits toolbar_requested, `create_annotation` calls engine and sets dirty flag, `delete_annotation` calls engine and sets dirty flag, `on_tab_switched` clears selection and hides toolbar |
| `tests/test_annotation_toolbar.py` | Highlight button emits `annotation_requested(HIGHLIGHT, color)`, Underline/Strikethrough buttons emit correctly, color picker selection updates active color, `show_near` positions within window bounds, `dismissed` emitted on focus loss |
| `tests/test_viewport_selection.py` | `set_selection_mode(True)` changes cursor to I-beam, click-drag emits `text_selected` with correct page and quads, drag over whitespace emits nothing, `set_selection_mode(False)` restores pan behavior |

### Integration Tests (`tests/test_annotation_integration.py`)

| Test | Verifies |
|---|---|
| `test_select_text_and_highlight` | Toggle selection mode → drag to select words → click Highlight → annotation exists on page, dirty flag is True |
| `test_select_text_and_underline` | Same flow with Underline type |
| `test_select_text_and_strikethrough` | Same flow with Strikethrough type |
| `test_delete_annotation` | Create annotation → right-click → Delete → annotation removed, dirty flag still True |
| `test_dirty_flag_on_create` | Create annotation → verify `model.dirty` is True, tab title starts with `*` |
| `test_no_text_layer_notification` | Open image-only PDF → attempt selection → verify notification shown |
| `test_color_picker_changes_annotation_color` | Select text → change color to Green → Highlight → verify annotation color is green |
| `test_tab_switch_clears_selection` | Select text on tab 1 → switch to tab 2 → verify toolbar hidden and selection cleared |

**Mocking:** PyMuPDF mocked in presenter unit tests. Engine tests and integration tests use real fixture PDFs (one with text layer, one image-only).

**Coverage target:** Maintain 65%+.

---

## 8. Deferred Items

- **Undo/redo** — annotation create/delete undo stack deferred to a future feature.
- **Annotation summary panel** — list/filter/navigate annotations deferred to Feature 12.
- **Save/Discard/Cancel dialog** — close-guard for dirty documents deferred to Feature 8.
- **Edit Properties context menu** — changing color/type of existing annotations deferred to a future feature.
- **Free-text and shape annotations** — only text markup (highlight, underline, strikethrough) in this feature.
- **Cross-page selection** — selecting text across page boundaries deferred; single-page selection only in MVP.
