# Text Copy (Ctrl+C) — Design Spec

## Summary
Enable copying selected text from a PDF to the system clipboard via Ctrl+C / Cmd+C,
with Select All (Ctrl+A) and an Edit menu Copy action.

## Components Modified

### 1. AnnotationEngine (services/annotation_engine.py)
**New method:** `extract_text_in_rects(doc_handle, page_index, rects) -> str`
- Takes a list of (x0, y0, x1, y1) bounding rectangles
- Calls `page.get_text("words")` to get word tuples
- Filters words whose bounding boxes intersect any of the given rects
- Orders words by (line_no, word_no) to preserve reading order
- Joins with spaces (newline between different lines)
- Returns the extracted text string

### 2. AnnotationPresenter (presenters/annotation_presenter.py)
**New methods:**
- `copy_selected_text() -> str` — extracts text from `_selected_rects` via engine,
  copies to system clipboard via `QApplication.clipboard().setText()`, returns the text
- `select_all_text() -> None` — gets all word rects from engine for current page,
  stores them as selection, shows overlay, emits text_selected
- `has_selection -> bool` property — True when `_selected_rects` is non-empty

**New signals:**
- `text_copied = Signal(str)` — emitted after text is copied (carries the text)
- `selection_changed = Signal(bool)` — emitted when selection state changes (has/no selection)

### 3. MainWindow (views/main_window.py)
**Edit menu additions:**
- "Copy" action (Ctrl+C) — grayed when no selection, enabled on selection_changed(True)
- "Select All" action (Ctrl+A) — selects all text on current page

**Signal additions:**
- `copy_requested = Signal()` — emitted when Copy action triggered
- `select_all_requested = Signal()` — emitted when Select All action triggered

### 4. KPdfApp (app.py)
**Wiring:**
- `MainWindow.copy_requested` -> `AnnotationPresenter.copy_selected_text()`
- `MainWindow.select_all_requested` -> `AnnotationPresenter.select_all_text()`
- `AnnotationPresenter.text_copied` -> `MainWindow.update_status_message("Copied to clipboard")`
- `AnnotationPresenter.selection_changed` -> `MainWindow.set_copy_enabled(enabled)`

## Data Flow
1. User selects text (drag in text-selection mode) -> viewport emits text_selected
2. AnnotationPresenter stores rects, emits selection_changed(True)
3. User presses Ctrl+C -> MainWindow emits copy_requested
4. KPdfApp routes to AnnotationPresenter.copy_selected_text()
5. Presenter calls engine.extract_text_in_rects() to get text string
6. Presenter copies to clipboard, emits text_copied
7. KPdfApp routes text_copied to status bar message

## Edge Cases
- No document open: Copy action disabled
- No text selected: Copy action disabled (grayed)
- Image-only PDF: Selection returns empty rects -> no text to copy
- Select All on image-only page: empty selection
- Tab switch: selection cleared -> copy disabled

## Accessibility
- Standard keyboard shortcuts (Ctrl+C, Ctrl+A)
- Edit menu items with keyboard accelerators
- Status bar feedback on copy
