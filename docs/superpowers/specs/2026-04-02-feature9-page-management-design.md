# Feature 9: Page Management — Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Depends on:** Feature 1 (Open/Render), Feature 2 (Multi-Tab), Feature 5 (Zoom/Rotate)
**FRD Reference:** FUNCTIONAL_REQUIREMENTS.md Section 2, Feature 9
**UI Reference:** UI_SCAFFOLDING.md Section 2.4 (Page Management Panel)

---

## 1. Architecture Overview

**PageManagerPanel (view):** New QDockWidget (left-docked, F7 toggle) — distinct from the NavigationPanel (F5). Contains a thumbnail grid with multi-select support (Ctrl+Click, Shift+Click) and drag-to-reorder. Includes a toolbar with Rotate Left, Rotate Right, Delete Pages, and Add Pages buttons.

**PageEngine (service):** New service in services/ replacing the existing stub. Wraps PyMuPDF page manipulation operations: `delete_pages()`, `move_page()`, `rotate_pages()`, `insert_pages_from()`. These operations modify the actual PDF document (unlike Feature 5 view rotation which only changes the display transform). PyMuPDF isolation rule unchanged — all fitz page manipulation calls remain in this service.

**PageManagementPresenter:** New presenter in presenters/ replacing the existing stub. Manages the page management panel lifecycle, coordinates page operations between the panel UI and the PageEngine, tracks the dirty flag, and refreshes thumbnails and viewport after operations.

**Clear distinction from Feature 5:** Feature 5 rotation is a view-only transform — it changes how the page is displayed without modifying the PDF. Feature 9 rotation modifies the page's `/Rotate` attribute in the PDF structure, persisting across saves. The panel buttons are explicitly labeled "Rotate Left (modifies file)" and "Rotate Right (modifies file)" to prevent confusion.

### Signal Flow

1. User presses F7 -> `PageManagerPanel` dock widget toggles visibility -> if opening, thumbnails generated for all pages via `PageEngine.render_thumbnail()`
2. User selects pages (Ctrl+Click / Shift+Click for multi-select) -> panel tracks selection internally
3. User clicks "Rotate Left (modifies file)" or "Rotate Right (modifies file)" -> `PageManagementPresenter.rotate_pages(page_indices, angle)` -> `PageEngine.rotate_pages(doc_handle, page_indices, angle)` -> page `/Rotate` attribute modified -> thumbnails regenerated for affected pages -> viewport re-renders current page -> `model.dirty = True`
4. User clicks "Delete Pages" -> confirmation dialog "Delete [N] selected page(s)? This cannot be undone." -> if confirmed, `PageManagementPresenter.delete_pages(page_indices)` -> `PageEngine.delete_pages(doc_handle, page_indices)` -> thumbnails regenerated -> viewport updates -> navigation panel page count updated -> `model.dirty = True`
5. User clicks "Add Pages" -> file picker (PDF only) -> `PageManagementPresenter.insert_pages(source_path, insert_index)` -> `PageEngine.insert_pages_from(doc_handle, source_path, insert_index)` -> thumbnails regenerated -> viewport and navigation updated -> `model.dirty = True`
6. User drags a thumbnail to a new position -> `PageManagementPresenter.move_page(from_index, to_index)` -> `PageEngine.move_page(doc_handle, from_index, to_index)` -> thumbnails reordered -> viewport updates if current page moved -> `model.dirty = True`
7. Operations on large documents (>1 second) -> progress indicator shown in PageManagerPanel

---

## 2. New Files

### `k_pdf/core/page_model.py`

**`PageOperation` enum:**

| Value | Description |
|---|---|
| `ROTATE` | Rotate selected pages by 90/180/270 degrees |
| `DELETE` | Delete selected pages from the document |
| `INSERT` | Insert pages from another PDF |
| `MOVE` | Reorder a page to a new position |

**`PageOperationResult` dataclass (frozen=True):**

| Field | Type | Default | Description |
|---|---|---|---|
| `operation` | `PageOperation` | — | The operation that was performed |
| `success` | `bool` | — | Whether the operation succeeded |
| `new_page_count` | `int` | — | Total page count after operation |
| `affected_pages` | `list[int]` | — | Zero-based indices of pages affected |
| `error_message` | `str` | `""` | Error description if success is False |

---

## 3. Modified Files

### `k_pdf/services/page_engine.py`

Replaces existing stub. PyMuPDF page manipulation operations isolated here.

Methods:
- `delete_pages(doc_handle, page_indices: list[int]) -> PageOperationResult` — validates minimum 1 page remains, calls `doc_handle.delete_pages(page_indices)`, returns result with new page count. Raises if deleting all pages.
- `move_page(doc_handle, from_index: int, to_index: int) -> PageOperationResult` — calls `doc_handle.move_page(from_index, to_index)`, returns result
- `rotate_pages(doc_handle, page_indices: list[int], angle: int) -> PageOperationResult` — validates angle is 90, 180, or 270. For each page index, calls `page.set_rotation((page.rotation + angle) % 360)`. This modifies the PDF `/Rotate` attribute, unlike Feature 5's view-only rotation.
- `insert_pages_from(doc_handle, source_path: Path, insert_index: int) -> PageOperationResult` — opens source PDF, calls `doc_handle.insert_pdf(source_doc, from_page=0, to_page=-1, start_at=insert_index)`, returns result with new page count and affected page indices
- `render_thumbnail(doc_handle, page_index: int, width: int = 150) -> QPixmap` — renders a page at thumbnail resolution for the panel grid, returns QPixmap. Uses existing page cache if available.
- `get_page_count(doc_handle) -> int` — returns `doc_handle.page_count`

### `k_pdf/presenters/page_management_presenter.py`

Replaces existing stub.

Instance variables:
- `_page_engine: PageEngine` — reference to the page engine service
- `_tab_manager: TabManager` — reference to the tab manager
- `_panel: PageManagerPanel` — reference to the panel view
- `_selected_pages: list[int]` — currently selected page indices in the panel

Signals:
- `dirty_changed(bool)` — emitted when dirty flag transitions
- `pages_changed()` — emitted after any page operation (triggers viewport refresh, navigation update)
- `operation_started(str)` — emitted with operation description when a potentially long operation begins
- `operation_finished()` — emitted when operation completes (hides progress indicator)

Methods:
- `rotate_pages(page_indices: list[int], angle: int)` — calls `PageEngine.rotate_pages()`, updates thumbnails, sets dirty flag
- `delete_pages(page_indices: list[int])` — shows confirmation dialog, calls `PageEngine.delete_pages()`, updates thumbnails, updates navigation panel page count, sets dirty flag
- `insert_pages(source_path: Path, insert_index: int)` — calls `PageEngine.insert_pages_from()`, regenerates all thumbnails (page indices shift), updates navigation, sets dirty flag
- `move_page(from_index: int, to_index: int)` — calls `PageEngine.move_page()`, reorders thumbnails, sets dirty flag
- `refresh_thumbnails()` — regenerates all thumbnails from current document state
- `on_tab_switched(session_id: str)` — refreshes panel for the new active document
- `on_tab_closed(session_id: str)` — clears panel if no tabs remain
- `_show_progress(operation: str)` — emits `operation_started`, shows progress indicator in panel for operations >1 second
- `_hide_progress()` — emits `operation_finished`, hides progress indicator

### `k_pdf/views/page_manager_panel.py`

Replaces existing stub.

**`PageManagerPanel(QDockWidget)` — left-docked, F7 toggle.**

Layout:
- Toolbar: [Rotate Left (modifies file)] [Rotate Right (modifies file)] [Delete Pages] [Add Pages]
- Thumbnail grid: QListWidget in IconMode with multi-select enabled
- Progress bar: QProgressBar (hidden by default, shown during long operations)

Instance variables:
- `_thumbnail_list: QListWidget` — icon-mode list with thumbnail pixmaps
- `_toolbar: QToolBar` — action buttons
- `_progress_bar: QProgressBar` — indeterminate progress for long operations

Signals:
- `rotate_left_clicked()` — emitted when Rotate Left button clicked
- `rotate_right_clicked()` — emitted when Rotate Right button clicked
- `delete_clicked()` — emitted when Delete Pages button clicked
- `add_clicked()` — emitted when Add Pages button clicked
- `page_moved(int, int)` — emitted when thumbnail dragged to new position (from_index, to_index)
- `selection_changed(list)` — emitted when page selection changes, list of selected indices

Methods:
- `set_thumbnails(pixmaps: list[QPixmap])` — populates the thumbnail grid with page thumbnails, labeled with page numbers
- `update_thumbnail(page_index: int, pixmap: QPixmap)` — replaces a single thumbnail after rotation or other change
- `get_selected_pages() -> list[int]` — returns zero-based indices of selected thumbnails
- `show_progress(message: str)` — shows the progress bar with the given message
- `hide_progress()` — hides the progress bar
- `set_page_count_label(count: int)` — updates the panel header with total page count

Multi-select behavior:
- Click: select single page (deselect others)
- Ctrl+Click: toggle selection of clicked page
- Shift+Click: extend selection from last clicked to current

Drag-to-reorder:
- QListWidget with `setDragDropMode(InternalMove)` — drag a thumbnail to reorder
- On drop, emits `page_moved(from_index, to_index)`

### `k_pdf/views/main_window.py`

New additions:
- View menu: "Page &Manager" toggle action (F7) — toggles PageManagerPanel dock widget visibility
- `_page_manager_panel: PageManagerPanel` — new dock widget, added to left dock area

New property:
- `page_manager_panel -> PageManagerPanel` — returns the page manager dock widget

### `k_pdf/app.py`

New wiring:
- Create `PageEngine` and `PageManagementPresenter` instances
- Connect MainWindow Page Manager toggle (F7) -> panel visibility
- Connect `PageManagerPanel.rotate_left_clicked` -> `PageManagementPresenter.rotate_pages(selected, 270)`
- Connect `PageManagerPanel.rotate_right_clicked` -> `PageManagementPresenter.rotate_pages(selected, 90)`
- Connect `PageManagerPanel.delete_clicked` -> `PageManagementPresenter.delete_pages(selected)`
- Connect `PageManagerPanel.add_clicked` -> file picker -> `PageManagementPresenter.insert_pages`
- Connect `PageManagerPanel.page_moved` -> `PageManagementPresenter.move_page`
- Connect `PageManagementPresenter.pages_changed` -> refresh viewport, refresh NavigationPanel page count
- Connect `PageManagementPresenter.dirty_changed` -> update tab title with `*` prefix
- Connect `PageManagementPresenter.operation_started` -> `PageManagerPanel.show_progress`
- Connect `PageManagementPresenter.operation_finished` -> `PageManagerPanel.hide_progress`
- Connect `TabManager.tab_switched` -> `PageManagementPresenter.on_tab_switched`

### `k_pdf/presenters/navigation_presenter.py`

Extended to listen for `PageManagementPresenter.pages_changed` signal and refresh the page count / page list in the NavigationPanel after page add/delete/reorder operations.

### `k_pdf/core/document_model.py`

No structural changes. The existing `dirty` bool attribute is set by PageManagementPresenter. The `page_count` property is already dynamic (reads from doc_handle).

---

## 4. Unchanged Files

- `k_pdf/core/page_cache.py` — unchanged (thumbnails in PageManagerPanel use separate rendering, not the viewport page cache)
- `k_pdf/core/zoom_model.py` — unchanged
- `k_pdf/core/search_model.py` — unchanged
- `k_pdf/core/annotation_model.py` — unchanged
- `k_pdf/services/pdf_engine.py` — unchanged (viewport rendering reads page state from PyMuPDF which reflects rotations/deletions automatically)
- `k_pdf/services/annotation_engine.py` — unchanged
- `k_pdf/services/search_engine.py` — unchanged
- `k_pdf/services/form_engine.py` — unchanged
- `k_pdf/presenters/document_presenter.py` — unchanged (Feature 5 view rotation is independent of Feature 9 page rotation)
- `k_pdf/presenters/search_presenter.py` — unchanged
- `k_pdf/presenters/annotation_presenter.py` — unchanged
- `k_pdf/views/annotation_toolbar.py` — unchanged
- `k_pdf/views/zoom_toolbar.py` — unchanged
- `k_pdf/views/search_bar.py` — unchanged
- `k_pdf/views/pdf_viewport.py` — unchanged (viewport reads page dimensions from PyMuPDF which reflects page operations automatically)

---

## 5. Accessibility

- All panel toolbar buttons have text labels, not icon-only: "Rotate Left (modifies file)", "Rotate Right (modifies file)", "Delete Pages", "Add Pages"
- Rotation buttons explicitly labeled "(modifies file)" to distinguish from Feature 5 view-only rotation — prevents confusion for all users
- Thumbnail grid supports keyboard navigation: arrow keys to move between thumbnails, Space/Enter to select, Ctrl+Space to toggle multi-select
- Shift+Arrow keys extend selection in thumbnail grid
- Multi-select state indicated by visual highlight and screen-reader-accessible selection state on QListWidgetItem
- Delete confirmation dialog uses standard QMessageBox with labeled Yes/No buttons
- Page numbers displayed as text labels below each thumbnail (e.g., "Page 1", "Page 2")
- Progress indicator uses QProgressBar with text description of the operation
- F7 keyboard shortcut to toggle panel — no mouse-only activation path
- Panel dock widget has a title bar readable by screen readers

---

## 6. Error Handling & Edge Cases

**Delete all pages:** When the user attempts to delete all pages, show error: "Cannot delete all pages. A PDF must contain at least one page." The operation is blocked — no pages are deleted.

**Delete with single page remaining:** If only one page exists and the user clicks Delete, same error as above.

**Delete confirmation:** Always show confirmation dialog: "Delete [N] selected page(s)? This cannot be undone." Yes/No buttons. No deletion without confirmation.

**Add Pages from invalid file:** If the selected file is not a valid PDF or is encrypted, show error: "Could not insert pages from [filename]. [error message]." No pages are inserted.

**Add Pages from encrypted PDF:** Show error: "Cannot insert pages from a password-protected PDF." Deferred: password prompt for source PDF.

**Move page to same position:** No-op. No dirty flag change, no thumbnail refresh.

**Rotate by invalid angle:** PageEngine validates angle is 90, 180, or 270. The UI only provides 90 (right) and 270 (left) buttons, but the engine guards against invalid values.

**Large document performance (>100 pages):** Thumbnail generation runs on a background thread (QThread). Only visible thumbnails are generated initially; off-screen thumbnails are generated lazily as the user scrolls. Progress indicator shown for operations >1 second.

**Dirty flag coordination:** PageManagementPresenter sets `model.dirty = True` on any page operation. This coordinates with AnnotationPresenter and FormPresenter dirty flags — all share the single `model.dirty` bool. Save (from Feature 8) writes the entire modified document including page changes.

**Panel open with no document:** Thumbnail grid is empty. All toolbar buttons are disabled. Label shows "No document open."

**Tab switch:** Panel refreshes to show thumbnails for the newly active document. Selection is cleared.

**Feature 5 vs. Feature 9 rotation interaction:** Feature 5 view rotation is a transient display transform. Feature 9 page rotation modifies the PDF `/Rotate` attribute. If Feature 5 has a 90-degree view rotation and Feature 9 rotates the page 90 degrees, the combined visual effect is 180 degrees. After save and reopen, only the Feature 9 rotation persists.

---

## 7. Testing Strategy

### Unit Tests

| File | Tests |
|---|---|
| `tests/test_page_model.py` | `PageOperation` enum values (ROTATE, DELETE, INSERT, MOVE), `PageOperationResult` construction with all fields, default `error_message` is empty string |
| `tests/test_page_engine.py` | `delete_pages` removes pages from real PDF fixture, `delete_pages` blocks deletion of all pages (returns error result), `move_page` reorders pages correctly, `rotate_pages` modifies page `/Rotate` attribute (90, 180, 270), `insert_pages_from` adds pages from source PDF at correct position, `render_thumbnail` returns QPixmap of correct width, `get_page_count` returns correct count after operations |
| `tests/test_page_management_presenter.py` | `rotate_pages` calls engine and sets dirty flag, `delete_pages` shows confirmation and calls engine on confirm, `delete_pages` blocks when would delete all pages, `insert_pages` calls engine and refreshes thumbnails, `move_page` calls engine for different indices (no-op for same), `on_tab_switched` refreshes panel, `on_tab_closed` clears panel, progress signals emitted for long operations |
| `tests/test_page_manager_panel.py` | `set_thumbnails` populates grid with correct count, `get_selected_pages` returns correct indices for multi-select, `update_thumbnail` replaces single thumbnail, Ctrl+Click toggles selection, Shift+Click extends selection, drag emits `page_moved` with correct indices, buttons emit correct signals, progress bar shows/hides correctly |

### Integration Tests (`tests/test_page_management_integration.py`)

| Test | Verifies |
|---|---|
| `test_delete_single_page` | Open multi-page PDF -> select page -> Delete -> confirm -> page removed, page count decremented, dirty flag True |
| `test_delete_multiple_pages` | Select multiple pages -> Delete -> confirm -> all selected pages removed |
| `test_delete_all_pages_blocked` | Select all pages -> Delete -> error shown -> no pages deleted |
| `test_rotate_page_left` | Select page -> Rotate Left -> page `/Rotate` modified by -90 degrees, thumbnail updated |
| `test_rotate_page_right` | Select page -> Rotate Right -> page `/Rotate` modified by +90 degrees |
| `test_rotate_multiple_pages` | Select 3 pages -> Rotate Right -> all 3 pages rotated |
| `test_add_pages_from_pdf` | Click Add Pages -> select source PDF -> pages inserted at selection point, page count increased |
| `test_drag_reorder` | Drag page 3 to position 1 -> page moved, thumbnails reordered |
| `test_dirty_flag_on_page_operation` | Perform any page operation -> dirty flag True, tab title has `*` |
| `test_panel_toggle_f7` | Press F7 -> panel opens -> press F7 -> panel closes |
| `test_panel_empty_no_document` | No document open -> panel shows "No document open", buttons disabled |
| `test_tab_switch_refreshes_panel` | Open two PDFs -> switch tabs -> panel thumbnails refresh to new document |

**Mocking:** PyMuPDF mocked in presenter unit tests. Engine tests and integration tests use real fixture PDFs (multi-page and single-page).

**Coverage target:** Maintain 65%+.

---

## 8. Deferred Items

- **Undo/redo** — page operation undo stack (restore deleted pages, reverse moves) deferred to a future feature.
- **Cancel long operations** — cancellation of in-progress page operations on large documents deferred.
- **Extract pages** — saving selected pages as a new PDF deferred.
- **Blank page insertion** — inserting an empty page deferred; only insertion from existing PDFs in MVP.
- **Page labels** — custom page labels (e.g., "i", "ii", "1", "2") deferred.
- **Crop pages** — page cropping / margin adjustment deferred.
- **Password-protected source PDF** — prompting for password when inserting from an encrypted PDF deferred.
- **Thumbnail zoom** — resizing thumbnails in the panel grid deferred.
