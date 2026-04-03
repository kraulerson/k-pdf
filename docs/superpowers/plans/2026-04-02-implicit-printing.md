# Implicit Feature: Printing (Ctrl+P) -- Implementation Plan

**Date:** 2026-04-02
**Spec:** `docs/superpowers/specs/2026-04-02-implicit-printing-design.md`
**Branch:** `feature/printing`
**Depends on:** Feature 1 (complete)

---

## Task Overview

| # | Task | Type | Files |
|---|------|------|-------|
| 1 | PrintService service | service | `k_pdf/services/print_service.py`, `tests/test_print_service.py` |
| 2 | MainWindow: add Print action to File menu | view | `k_pdf/views/main_window.py`, `tests/test_views.py` |
| 3 | KPdfApp: wire print flow end-to-end | app | `k_pdf/app.py`, `tests/test_print_integration.py` |
| 4 | Mypy overrides + CLAUDE.md update | config | `pyproject.toml`, `CLAUDE.md` |

---

## Task 1: PrintService Service

### RED -- Write failing tests

**File: `tests/test_print_service.py`**

Tests:
- `test_print_all_pages` -- print 3-page doc with fromPage=0/toPage=0, verify all 3 rendered
- `test_print_page_range` -- print pages 2-3 of 3-page doc, verify only 2 rendered
- `test_print_single_page` -- print page 1 only, verify 1 rendered, no newPage called
- `test_progress_callback` -- verify callback called with (current, total) for each page
- `test_render_failure` -- PdfEngine.render_page raises, verify error result returned
- `test_painter_begin_failure` -- QPainter.begin returns False, verify error result
- `test_result_success_fields` -- verify PrintResult fields on success
- `test_result_failure_fields` -- verify PrintResult fields on failure

### GREEN -- Implement PrintService

**File: `k_pdf/services/print_service.py`**

Implement `PrintResult` dataclass and `PrintService` class with `print_document()` method per spec.

### REFACTOR -- Clean up

Ensure docstrings, type annotations, and logging consistent with existing services.

---

## Task 2: MainWindow Print Action

### RED -- Write failing tests

**File: `tests/test_views.py` (append)**

Tests:
- `test_print_action_exists` -- verify _print_action exists in File menu
- `test_print_action_shortcut` -- verify Ctrl+P shortcut
- `test_print_action_disabled_by_default` -- verify disabled initially
- `test_set_print_enabled` -- verify set_print_enabled(True/False) toggles state
- `test_print_action_emits_signal` -- verify triggering action emits print_requested

### GREEN -- Modify MainWindow

Add print_requested signal, _print_action, and set_print_enabled() method.

### REFACTOR -- Clean up

Verify menu item placement (after Save As, before Merge).

---

## Task 3: KPdfApp Print Wiring

### RED -- Write failing tests

**File: `tests/test_print_integration.py`**

Tests:
- `test_print_action_disabled_no_document` -- verify print disabled on startup
- `test_print_action_enabled_after_open` -- verify print enabled after document loads
- `test_print_action_disabled_after_all_tabs_closed` -- verify print disabled when 0 tabs
- `test_print_flow_calls_service` -- mock QPrintDialog.exec to return Accepted, verify PrintService called
- `test_print_cancelled_no_service_call` -- mock QPrintDialog.exec to return Rejected, verify no print
- `test_print_error_shows_dialog` -- mock PrintService to return error, verify error shown
- `test_print_status_bar_updates` -- verify status bar shows progress messages

### GREEN -- Modify KPdfApp

Wire print signal, create PrintService, implement _on_print_requested handler.

### REFACTOR -- Clean up

---

## Task 4: Config Updates

- Add mypy override for `k_pdf.services.print_service` if needed
- Update CLAUDE.md current state
- Run full lint + type check + test suite
