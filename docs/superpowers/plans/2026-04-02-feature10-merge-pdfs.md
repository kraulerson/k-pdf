# Feature 10: Merge Multiple PDFs — Implementation Plan

**Date:** 2026-04-02
**Spec:** `docs/superpowers/specs/2026-04-02-feature10-merge-pdfs-design.md`
**Branch:** `feature/merge-pdfs`
**Depends on:** Feature 1 (complete)

---

## Task Overview

| # | Task | Type | Files |
|---|------|------|-------|
| 1 | MergeEngine service (replace stub) | service | `k_pdf/services/merge_engine.py`, `tests/test_merge_engine.py` |
| 2 | MergeDialog view (replace stub) | view | `k_pdf/views/merge_dialog.py`, `tests/test_merge_dialog.py` |
| 3 | MainWindow: add Merge Documents menu action | view | `k_pdf/views/main_window.py`, `tests/test_views.py` |
| 4 | KPdfApp: wire merge dialog + open result | app | `k_pdf/app.py`, `tests/test_merge_integration.py` |
| 5 | Mypy overrides + CLAUDE.md update | config | `pyproject.toml`, `CLAUDE.md` |

---

## Task 1: MergeEngine Service

### RED — Write failing tests

**File: `tests/test_merge_engine.py`**

Tests:
- `test_probe_file_valid` — probe a valid 3-page PDF, get MergeFileInfo with page_count=3, no error
- `test_probe_file_nonexistent` — probe a nonexistent path, get MergeFileInfo with error
- `test_probe_file_corrupt` — probe a corrupt file, get MergeFileInfo with error
- `test_probe_file_not_a_pdf` — probe a text file with .pdf extension, get MergeFileInfo with error
- `test_merge_two_pdfs` — merge two valid PDFs, verify output page count = sum of input page counts
- `test_merge_three_pdfs` — merge three valid PDFs, verify total pages
- `test_merge_skips_corrupt_file` — merge list with one corrupt file, verify it's skipped and recorded
- `test_merge_progress_callback` — merge with callback, verify it's called with (current, total)
- `test_merge_empty_list` — merge empty list, get error result
- `test_merge_single_file` — merge single file, get error result (need >= 2)
- `test_merge_all_invalid` — merge list of all corrupt files, get error result
- `test_merge_output_has_correct_content` — verify text from each source is present in merged output

### GREEN — Implement MergeEngine

**File: `k_pdf/services/merge_engine.py`**

Implement `MergeFileInfo`, `MergeResult` dataclasses and `MergeEngine` class with `probe_file()` and `merge()` methods per spec.

### REFACTOR — Clean up

Ensure docstrings, type annotations, and logging are consistent with existing services.

---

## Task 2: MergeDialog View

### RED — Write failing tests

**File: `tests/test_merge_dialog.py`**

Tests:
- `test_dialog_initial_state` — dialog opens with empty file list, merge button disabled
- `test_add_files_populates_list` — add files and verify list items show filename + page count
- `test_remove_selected` — add files, select one, remove, verify list updated
- `test_merge_button_disabled_with_one_file` — add 1 file, merge button still disabled
- `test_merge_button_enabled_with_two_files` — add 2 valid files, merge button enabled
- `test_info_label_shows_counts` — add files, verify info label text
- `test_error_file_shown_with_error_text` — add corrupt file, verify "Error:" in item text
- `test_merge_button_disabled_when_all_error` — add only error files, merge button disabled

### GREEN — Implement MergeDialog

**File: `k_pdf/views/merge_dialog.py`**

Implement `MergeDialog(QDialog)` per spec with file list, buttons, progress bar, result area.

### REFACTOR — Clean up

Ensure accessibility labels and keyboard navigation.

---

## Task 3: MainWindow Merge Menu Action

### RED — Write failing tests

**File: `tests/test_views.py` (append)**

Tests:
- `test_merge_action_in_file_menu` — verify File menu has "Merge Documents..." action
- `test_merge_action_emits_signal` — trigger action, verify `merge_requested` signal emitted

### GREEN — Implement

**File: `k_pdf/views/main_window.py`**

Add `merge_requested = Signal()` and "Merge &Documents..." action to File menu with Ctrl+Shift+M shortcut.

### REFACTOR — Clean up

---

## Task 4: KPdfApp Wiring + Integration Tests

### RED — Write failing tests

**File: `tests/test_merge_integration.py`**

Tests:
- `test_merge_two_pdfs_creates_output` — create MergeEngine, merge two fixture PDFs, verify output file exists with correct page count
- `test_merge_with_corrupt_skips` — merge valid + corrupt, verify skipped list and output page count
- `test_merge_dialog_merge_complete_signal` — verify dialog emits merge_complete with path

### GREEN — Implement

**File: `k_pdf/app.py`**

Wire `merge_requested` signal to `_on_merge_requested()` handler that creates and shows MergeDialog, and on `merge_complete` opens file via TabManager.

### REFACTOR — Clean up

---

## Task 5: Mypy Overrides + CLAUDE.md Update

- Add mypy overrides for `k_pdf.services.merge_engine` (no-untyped-call) and `k_pdf.views.merge_dialog` (misc) to `pyproject.toml`
- Update CLAUDE.md current state to include Feature 10 as built
