# Feature 10: Merge Multiple PDFs — Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Depends on:** Feature 1 (Open/Render)
**FRD Reference:** FUNCTIONAL_REQUIREMENTS.md Section 2, Feature 10
**UI Reference:** File > Merge Documents...

---

## 1. Architecture Overview

**MergeEngine (service):** New service in `services/merge_engine.py` replacing the existing stub. Wraps PyMuPDF `doc.insert_pdf()` to combine multiple source PDFs into a single output document. PyMuPDF isolation rule applies — all fitz/pymupdf merge calls remain in this service.

**MergeDialog (view):** New QDialog in `views/merge_dialog.py` replacing the existing stub. A self-contained modal dialog with file list (QListWidget), drag-to-reorder, Add/Remove buttons, page count display per file, Merge button, and progress bar. No separate presenter — the dialog creates a MergeEngine, runs the merge, and reports results.

**No separate presenter:** MergeDialog is a self-contained modal dialog. It creates a MergeEngine internally, orchestrates the merge, and reports results. The merge operation is stateless (no document model to track) and produces a new file rather than modifying an existing one, so MVP pattern adds no value here.

**File menu: "Merge Documents..."** — opens the MergeDialog. Added to MainWindow's File menu.

**After merge:** Status notification with "Open" button in the dialog to open the merged file.

### Signal Flow

1. User selects File > Merge Documents... -> MainWindow emits `merge_requested` signal
2. KPdfApp creates and shows MergeDialog (modal)
3. User clicks Add Files -> native file picker -> selected PDFs added to list with page counts
4. User reorders files by dragging in the QListWidget
5. User removes files with Remove button
6. User clicks Merge -> save dialog for output path -> MergeEngine.merge() called
7. Progress bar shows "Merging... [X] of [N] files"
8. On completion: dialog shows success message with "Open Merged File" button
9. User clicks "Open Merged File" -> dialog returns the output path -> KPdfApp opens it in a new tab

---

## 2. New / Modified Files

### `k_pdf/services/merge_engine.py`

Replaces existing stub. Wraps PyMuPDF merge operations.

**`MergeFileInfo` dataclass (frozen=True):**

| Field | Type | Default | Description |
|---|---|---|---|
| `path` | `Path` | -- | Absolute path to the source PDF |
| `page_count` | `int` | -- | Number of pages in the source PDF |
| `error` | `str` | `""` | Error message if file could not be read |

**`MergeResult` dataclass (frozen=True):**

| Field | Type | Default | Description |
|---|---|---|---|
| `success` | `bool` | -- | Whether the merge completed |
| `output_path` | `Path \| None` | `None` | Path to the merged output file |
| `total_pages` | `int` | `0` | Total page count in the merged file |
| `files_merged` | `int` | `0` | Number of files successfully merged |
| `skipped_files` | `list[str]` | `[]` | Filenames that were skipped due to errors |
| `error_message` | `str` | `""` | Overall error if merge failed entirely |

**`MergeEngine` class:**

Methods:
- `probe_file(path: Path) -> MergeFileInfo` -- Opens the file with PyMuPDF to read page count. Returns `MergeFileInfo` with error set if file is corrupt, unreadable, or not a valid PDF.
- `merge(sources: list[Path], output_path: Path, progress_callback: Callable[[int, int], None] | None = None) -> MergeResult` -- Creates a new PyMuPDF document, iterates through sources calling `output_doc.insert_pdf(source_doc)` for each, calls `progress_callback(current_index, total)` after each file, saves to `output_path`. Skips files that fail to open (records in `skipped_files`). Returns `MergeResult`.

### `k_pdf/views/merge_dialog.py`

Replaces existing stub. Self-contained modal QDialog.

**`MergeDialog(QDialog)` layout:**
- File list: QListWidget with drag-to-reorder (InternalMove), each item shows "[filename] — [N] pages" or "[filename] — Error: [reason]" with error styling
- Buttons row: [Add Files...] [Remove Selected]
- Info label: "N files, M total pages"
- Merge button: [Merge] — disabled until >= 2 valid files
- Progress bar: QProgressBar (hidden by default)
- Result area: QLabel for status + QPushButton "Open Merged File" (hidden until merge complete)

**Instance variables:**
- `_file_list: QListWidget` -- the file list
- `_merge_engine: MergeEngine` -- engine instance
- `_file_infos: list[MergeFileInfo]` -- probed file info list (mirrors list widget order)
- `_add_btn: QPushButton`
- `_remove_btn: QPushButton`
- `_merge_btn: QPushButton`
- `_progress_bar: QProgressBar`
- `_info_label: QLabel`
- `_result_label: QLabel`
- `_open_btn: QPushButton`
- `_output_path: Path | None`

**Signals:**
- `merge_complete(str)` -- emitted with the output file path string when merge completes and user wants to open

**Methods:**
- `_add_files()` -- opens file picker (multi-select PDFs), probes each, adds to list
- `_remove_selected()` -- removes selected items from list
- `_update_info()` -- updates info label and merge button enabled state
- `_start_merge()` -- shows save dialog, calls `MergeEngine.merge()`, updates progress, shows result
- `_on_merge_progress(current: int, total: int)` -- updates progress bar
- `_open_merged_file()` -- emits `merge_complete` with path, closes dialog
- `get_output_path() -> Path | None` -- returns the output path after merge

### `k_pdf/views/main_window.py`

New additions:
- File menu: "Merge &Documents..." action with `Ctrl+Shift+M` shortcut
- New signal: `merge_requested = Signal()`

### `k_pdf/app.py`

New wiring:
- Connect `MainWindow.merge_requested` -> `KPdfApp._on_merge_requested()`
- `_on_merge_requested()` creates `MergeDialog`, shows modal, on `merge_complete` opens the output file in a new tab via `TabManager.open_file()`

---

## 3. Unchanged Files

- `k_pdf/core/document_model.py` -- unchanged (merge creates a new file, no model mutation)
- `k_pdf/core/page_model.py` -- unchanged
- `k_pdf/services/pdf_engine.py` -- unchanged
- `k_pdf/services/page_engine.py` -- unchanged
- `k_pdf/services/annotation_engine.py` -- unchanged
- `k_pdf/services/search_engine.py` -- unchanged
- `k_pdf/services/form_engine.py` -- unchanged
- `k_pdf/presenters/` -- all unchanged (no presenter for merge)
- `k_pdf/views/pdf_viewport.py` -- unchanged
- `k_pdf/views/navigation_panel.py` -- unchanged
- `k_pdf/views/page_manager_panel.py` -- unchanged

---

## 4. Accessibility

- All buttons have text labels: "Add Files...", "Remove Selected", "Merge"
- File list items use text labels with filename and page count (never rely on color alone)
- Error files marked with text prefix "Error:" in the list item text, not just color
- Progress bar has text: "Merging... [X] of [N] files"
- Result message is text-based: "Merge complete. [N] files merged into [filename]."
- "Open Merged File" button is text-labeled
- Dialog fully keyboard-navigable: Tab between controls, Enter to activate buttons
- File list supports keyboard selection (arrow keys, Space to select, Delete to remove)

---

## 5. Error Handling & Edge Cases

**Corrupt/unreadable source file:** Probed at add time. Listed with error text: "[filename] -- Error: [reason]". Shown in the list but skipped during merge. User can remove it or proceed.

**Password-protected source file:** Probed at add time. Listed with error text: "[filename] -- Error: Password-protected". Skipped during merge. Password prompt for merge sources deferred.

**Output path read-only or invalid:** Save dialog reopens with error message: "Cannot save to [path]: [reason]. Choose a different location."

**Fewer than 2 valid files:** Merge button disabled. Info label shows: "Select at least 2 files to merge."

**Same file added twice:** Allowed (user may want to duplicate pages).

**Very large merge (20+ files):** Progress bar shows per-file progress. No cancel button in MVP (deferred).

**Merge with all files errored:** Merge button disabled (0 valid files).

**Merge with some files errored:** Merge proceeds with valid files. Final result lists skipped files.

**Empty output path (user cancels save dialog):** Merge does not proceed.

---

## 6. Testing Strategy

### Unit Tests

| File | Tests |
|---|---|
| `tests/test_merge_engine.py` | `probe_file` returns correct page count for valid PDF, `probe_file` returns error for corrupt file, `probe_file` returns error for nonexistent file, `merge` combines 2 PDFs into output with correct page count, `merge` combines 3+ PDFs, `merge` skips unreadable files and records them, `merge` calls progress callback, `merge` with all invalid files returns error, `merge` with single file returns error, `merge` with empty list returns error |
| `tests/test_merge_dialog.py` | Dialog opens with empty list, Add Files adds items with page counts, Remove Selected removes items, drag reorder changes item order, Merge button disabled with < 2 files, Merge button enabled with >= 2 valid files, info label shows correct counts, error files shown with error text, progress bar updates during merge, result label shows after merge, Open button emits merge_complete signal |

### Integration Tests (`tests/test_merge_integration.py`)

| Test | Verifies |
|---|---|
| `test_merge_menu_action_exists` | File menu has "Merge Documents..." action |
| `test_merge_two_pdfs_end_to_end` | Add 2 PDFs -> Merge -> output file has combined pages |
| `test_merge_with_corrupt_file_skipped` | Add valid + corrupt PDFs -> Merge -> corrupt file skipped, valid merged |
| `test_merge_opens_result_file` | After merge, "Open Merged File" triggers file open in app |

**Mocking:** PyMuPDF mocked in dialog tests. Engine tests use real fixture PDFs. Integration tests use real fixtures.

**Coverage target:** Maintain 65%+.

---

## 7. Deferred Items

- **Cancel merge in progress** -- cancel button during merge deferred
- **Password prompt for encrypted source files** -- deferred
- **Page range selection per source file** -- merge all pages only in MVP
- **Drag files from OS file manager into merge dialog** -- deferred
- **Background thread for merge** -- merge runs synchronously in MVP; QThread for large merges deferred
