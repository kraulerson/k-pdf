# Implicit Feature: Printing (Ctrl+P) -- Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Depends on:** Feature 1 (Open/Render)
**FRD Reference:** FUNCTIONAL_REQUIREMENTS.md -- Implicit Features
**UI Reference:** File > Print... (Ctrl+P)

---

## 1. Architecture Overview

**PrintService (service):** New service in `services/print_service.py`. Renders pages to a QPrinter using PdfEngine.render_page() to produce QImages at print resolution (300 DPI, zoom ~4.17), then paints them onto the QPrinter via QPainter. All rendering goes through PdfEngine -- PrintService does NOT import fitz/pymupdf.

**No separate presenter:** Printing is a one-shot, fire-and-forget operation. KPdfApp handles the Ctrl+P action, gets the active document's doc_handle and page count, shows QPrintDialog, and calls PrintService.print_document(). No persistent state to manage.

**Print flow:**
1. User presses Ctrl+P or File > Print...
2. If no document open, action is disabled (grayed out)
3. QPrintDialog shown (modal) -- user selects printer, page range, copies
4. If user accepts, PrintService renders selected pages at 300 DPI
5. Status bar shows "Printing page X of Y..." during rendering
6. On completion: status bar shows "Printing complete"
7. On error: QMessageBox with error details

**Page range support:** QPrintDialog provides native page range selection. PrintService respects fromPage/toPage from QPrinter.

**Print resolution:** 300 DPI. PDF points are 72 DPI, so zoom = 300/72 = 4.166... for print quality output.

### Signal Flow

1. User triggers File > Print... (Ctrl+P)
2. MainWindow emits `print_requested` signal
3. KPdfApp._on_print_requested():
   a. Gets active presenter + model
   b. If no document, returns (action already disabled)
   c. Creates QPrinter + QPrintDialog
   d. If dialog accepted, calls PrintService.print_document()
   e. Status bar updates during printing
   f. Error dialog on failure

---

## 2. New / Modified Files

### `k_pdf/services/print_service.py` (NEW)

**`PrintResult` dataclass (frozen=True):**

| Field | Type | Default | Description |
|---|---|---|---|
| `success` | `bool` | -- | Whether printing completed without error |
| `pages_printed` | `int` | `0` | Number of pages sent to printer |
| `error_message` | `str` | `""` | Error details if printing failed |

**`PrintService` class:**

| Method | Signature | Description |
|---|---|---|
| `print_document` | `(printer: QPrinter, doc_handle: Any, page_count: int, pdf_engine: PdfEngine, progress_callback: Callable[[int, int], None] \| None = None) -> PrintResult` | Renders and prints pages per QPrinter settings |

**print_document logic:**
1. Read `printer.fromPage()` and `printer.toPage()` (0 = all pages; QPrinter uses 1-based)
2. Compute page range: if fromPage==0, print all; else print fromPage..toPage (convert to 0-based)
3. Create QPainter on the QPrinter
4. For each page in range:
   a. Call `pdf_engine.render_page(doc_handle, page_index, zoom=300/72)` to get QImage
   b. Scale QImage to fit printer page rect (maintaining aspect ratio)
   c. Paint QImage onto QPainter
   d. If not last page, call `printer.newPage()`
   e. Call progress_callback(current, total) if provided
5. End QPainter
6. Return PrintResult(success=True, pages_printed=count)
7. On any exception: return PrintResult(success=False, error_message=str(error))

### `k_pdf/views/main_window.py` (MODIFIED)

- Add `print_requested = Signal()` to MainWindow
- Add `_print_action` QAction in File menu: "Print..." with Ctrl+P shortcut
- Place after Save As, before Merge Documents
- Initially disabled (no document open)
- Add `set_print_enabled(enabled: bool)` method

### `k_pdf/app.py` (MODIFIED)

- Import PrintService, QPrinter, QPrintDialog
- Create `self._print_service = PrintService()` in __init__
- Connect `self._window.print_requested.connect(self._on_print_requested)`
- Enable print action when document loads: in `_on_document_ready_form` (or a new `_on_document_ready_print`), call `self._window.set_print_enabled(True)`
- Disable print action when all tabs close: in `_on_tab_count_changed`, if count==0, call `self._window.set_print_enabled(False)`
- `_on_print_requested()`: show QPrintDialog, call PrintService, update status bar

---

## 3. Test Strategy

**Unit tests for PrintService (`tests/test_print_service.py`):**
- Mock QPrinter, QPainter, and PdfEngine
- Test full page range (fromPage=0, toPage=0)
- Test partial page range (fromPage=2, toPage=3)
- Test single page print
- Test progress callback invocation
- Test render failure mid-print returns error result
- Test QPainter.begin() failure returns error result

**Integration tests (`tests/test_print_integration.py`):**
- Mock QPrintDialog to auto-accept
- Verify KPdfApp wires print action correctly
- Verify print action disabled when no document
- Verify print action enabled when document loaded
- Verify status bar updates during print
- Verify error dialog on print failure

**What we do NOT test:**
- QPrintDialog modal interaction (cannot test in headless CI)
- Actual printer output (no physical printer in CI)
- QPrinter hardware interaction

---

## 4. Error Handling

| Error | Handling |
|---|---|
| No document open | Print action disabled (grayed out) |
| QPrintDialog cancelled | No-op, return silently |
| PdfEngine.render_page fails | PrintResult with error, shown in QMessageBox |
| QPainter.begin() fails | PrintResult with error, shown in QMessageBox |
| Printer hardware error | Caught by QPainter/QPrinter, surfaced in PrintResult |

---

## 5. Accessibility

- Print action has keyboard shortcut (Ctrl+P)
- Status bar messages provide non-visual feedback on print progress
- QPrintDialog is a native OS dialog with built-in accessibility
- Print action has text label "Print..." (no color-only indication)
