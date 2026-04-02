# Feature 1: Open and Render PDF — Implementation Design

## Date: 2026-04-02
## Status: Draft

---

## 1. Scope

Implement the foundational "Open and Render PDF" feature per FRD Feature 1. This covers:
- File open via File > Open dialog (Ctrl+O / Cmd+O)
- File open via drag-and-drop onto viewport
- File open via CLI argument (`k-pdf /path/to/file.pdf`)
- File validation (`%PDF-` header, permissions, existence)
- Password-protected PDF handling
- PDF parsing via PyMuPDF
- Page rendering in a scrollable viewport
- Lazy rendering (visible pages + buffer)
- LRU page cache (max 50 pages per tab)
- All failure states from FRD (file not found, permissions, corrupt, password, page render error)
- Status bar updates (page count, loading progress)
- Recent files list updated on successful open

**Not in scope:** Multi-tab (Feature 2), thumbnails/outline (Feature 3), search (Feature 4), zoom/rotate beyond default fit-width (Feature 5). These are designed to plug into the interfaces established here.

---

## 2. Architecture — Component Interaction

```
User Action (Open File)
    │
    ▼
MainWindow (view)
    │  emits: file_open_requested(path)
    ▼
DocumentPresenter
    │  validates path, dispatches to worker thread
    ▼
PdfEngine (service, runs in QThread)
    │  PyMuPDF: fitz.open(), page rendering
    │  emits: document_loaded / load_failed / page_rendered
    ▼
DocumentPresenter
    │  updates DocumentModel, populates PageCache
    │  emits: document_ready / page_ready
    ▼
PdfViewport (view)
    │  displays rendered pages via QGraphicsView
    ▼
StatusBar (view)
    │  shows page count, zoom, loading state
```

All PyMuPDF calls are isolated in `k_pdf/services/pdf_engine.py`. Views and presenters never import `fitz`.

---

## 3. Service Layer — PdfEngine

**File:** `k_pdf/services/pdf_engine.py`

### Public API

```python
@dataclass
class OpenResult:
    """Result of opening a PDF document."""
    doc_handle: Any               # fitz.Document (opaque outside services/)
    metadata: DocumentMetadata
    pages: list[PageInfo]

class PdfEngine:
    """PyMuPDF wrapper. All fitz imports are contained here."""

    def open_document(self, path: Path, password: str | None = None) -> OpenResult:
        """Open a PDF, return handle + metadata + page info. Raises on failure."""

    def render_page(self, doc_handle: Any, page_index: int, zoom: float = 1.0,
                    rotation: int = 0) -> QImage:
        """Render a single page to QImage (thread-safe, off main thread).
        Presenter converts QImage → QPixmap on main thread for display.
        Raises PageRenderError on failure."""

    def close_document(self, doc_handle: Any) -> None:
        """Close the PyMuPDF document handle and release memory."""

    def validate_pdf_path(self, path: Path) -> None:
        """Check existence, permissions, %PDF- header. Raises PdfValidationError."""
```

### Error Types

```python
class PdfError(Exception): ...
class PdfValidationError(PdfError): ...    # File not found, permissions, not a PDF
class PdfOpenError(PdfError): ...          # Corrupt, unexpected PyMuPDF error
class PdfPasswordRequired(PdfError): ...   # Encrypted, needs password
class PdfPasswordIncorrect(PdfError): ...  # Wrong password provided
class PageRenderError(PdfError): ...       # Single page render failure
```

### Validation Order (per FRD)

1. File exists at path
2. File is readable (OS permissions)
3. First bytes contain `%PDF-` header
4. PyMuPDF can parse the document
5. If encrypted → raise PdfPasswordRequired

### Threading

PdfEngine methods are called from worker threads dispatched by the presenter. The engine itself is stateless — it receives a path or doc handle and returns results. The PyMuPDF document handle is stored in DocumentModel, not in the engine.

---

## 4. Core Layer — DocumentModel and PageCache

**File:** `k_pdf/core/document_model.py`

```python
@dataclass
class DocumentModel:
    """Per-tab in-memory document state."""
    file_path: Path
    doc_handle: Any                     # fitz.Document (opaque to non-service code)
    metadata: DocumentMetadata
    pages: list[PageInfo]
    dirty: bool = False
    session_id: str = field(default_factory=lambda: str(uuid4()))
```

**File:** `k_pdf/core/page_cache.py` (new file)

```python
class PageCache:
    """LRU cache of rendered QPixmap objects, max capacity per tab."""

    def __init__(self, max_pages: int = 50) -> None: ...
    def get(self, page_index: int) -> QPixmap | None: ...
    def put(self, page_index: int, pixmap: QPixmap) -> None: ...
    def invalidate(self, page_index: int | None = None) -> None: ...
    def size(self) -> int: ...
```

Uses `collections.OrderedDict` for O(1) LRU eviction. When `put` exceeds `max_pages`, the least-recently-accessed entry is evicted.

---

## 5. Presenter Layer — DocumentPresenter

**File:** `k_pdf/presenters/document_presenter.py`

### Responsibilities

1. Receive file-open requests from views
2. Run validation and PyMuPDF operations off the main thread
3. Manage DocumentModel lifecycle
4. Drive the viewport by emitting signals when pages are ready
5. Handle all error states by emitting error signals (views show dialogs)
6. Update recent files on successful open

### Threading Approach

Uses `QThread` with a worker object pattern:

```python
class PdfWorker(QObject):
    """Runs PdfEngine operations off the Qt event loop."""
    document_loaded = Signal(DocumentModel)
    load_failed = Signal(str, str)          # (error_title, error_message)
    password_required = Signal(Path)
    page_rendered = Signal(int, QPixmap)    # (page_index, pixmap)
    progress_updated = Signal(int)          # percentage

    def open_document(self, path: Path, password: str | None = None) -> None: ...
    def render_pages(self, doc_handle: Any, page_indices: list[int],
                     zoom: float, rotation: int) -> None: ...
```

The presenter creates a `QThread`, moves the `PdfWorker` to it, and connects signals. This ensures:
- Qt event loop never blocks on file I/O or PyMuPDF rendering
- Views receive results via signal/slot (thread-safe)
- Progress updates reach the status bar during large file loads

### Open Flow

```
1. View emits file_open_requested(path)
2. Presenter calls PdfEngine.validate_pdf_path(path) [quick, main thread OK]
3. If validation fails → emit error signal → view shows dialog
4. If valid → start PdfWorker.open_document(path) on worker thread
5. Worker calls PdfEngine.open_document(path)
6. On PdfPasswordRequired → emit password_required → view shows password dialog
7. On success → emit document_loaded(model)
8. Presenter stores model, requests visible page renders
9. Worker renders pages → emit page_rendered(index, pixmap) per page
10. Presenter puts pixmaps in PageCache, emits page_ready for viewport
```

---

## 6. View Layer

### MainWindow (`k_pdf/views/main_window.py`)

- Sets up the three-panel layout with QSplitter
- Creates menu bar with File > Open, recent files submenu
- Accepts drag-and-drop (filter for .pdf files)
- Emits `file_open_requested(path: Path)` signal
- Shows error/password dialogs when presenter signals errors
- Creates the status bar

### PdfViewport (`k_pdf/views/pdf_viewport.py`)

- Subclass of `QGraphicsView` with a `QGraphicsScene`
- Each rendered page is a `QGraphicsPixmapItem` positioned vertically with gap
- Manages viewport states: Empty (welcome), Loading, Error, Success, PageError
- Lazy rendering: on scroll, calculates which pages are visible + 1-page buffer, requests renders for uncached pages
- Failed pages show a gray `QGraphicsRectItem` with "Render error on page N" text

### StatusBar

- Integrated into MainWindow
- Shows: "Page X of Y", zoom percentage, loading progress, mode text
- Updated by presenter signals

---

## 7. Lazy Rendering Strategy

1. Viewport calculates visible page range from scroll position and viewport size
2. Extends range by 1 page above and 1 page below (buffer)
3. For each page in range:
   - If in PageCache → display immediately
   - If not cached → show placeholder, request render from worker
4. Worker renders pages sequentially, emitting `page_rendered` per page
5. Presenter puts result in PageCache, emits `page_ready`
6. Viewport replaces placeholder with rendered pixmap
7. On scroll, repeat from step 1 — already-cached pages are instant

---

## 8. File Open Entry Points

| Entry Point | Implementation |
|---|---|
| File > Open (Ctrl+O) | QFileDialog.getOpenFileName with PDF filter → emit signal |
| Drag-and-drop | MainWindow.dragEnterEvent / dropEvent → validate .pdf → emit signal |
| CLI argument | main.py reads sys.argv → passes to App → App emits signal after window shown |
| OS file association | Same as CLI argument (OS passes path as argv) |

---

## 9. Error Handling

All errors map to FRD failure states. The presenter translates PdfEngine exceptions into user-facing error signals. Views show QMessageBox dialogs.

| Exception | Dialog Title | Dialog Message |
|---|---|---|
| PdfValidationError (not found) | "File not found" | "File not found: [full path]." |
| PdfValidationError (permissions) | "Permission denied" | "Cannot open [filename]: permission denied." |
| PdfValidationError (not PDF) | "Invalid file" | "Cannot open [filename]: this file does not appear to be a valid PDF." |
| PdfOpenError | "Cannot open file" | "Cannot open [filename]: the file is damaged or corrupted. [detail]." |
| PdfPasswordRequired | Password dialog | "This document is protected. Enter the password to open it." |
| PdfPasswordIncorrect | Password dialog remains | "Incorrect password. Try again." |
| PageRenderError | No dialog | Gray placeholder on that page with text "Render error on page [N]" |
| Unexpected exception | "Unexpected error" | "An unexpected error occurred while opening [filename]: [type]: [message]." |

---

## 10. Testing Strategy

### Unit Tests (no Qt, no GUI)

- **PdfEngine.validate_pdf_path:** test with nonexistent file, unreadable file, non-PDF file, valid PDF
- **PdfEngine.open_document:** test with valid PDF, corrupt PDF, encrypted PDF (correct/wrong password)
- **PdfEngine.render_page:** test with valid page index, invalid index, page that triggers render error
- **PageCache:** test LRU eviction, get/put, invalidation, capacity limit
- **DocumentModel:** test construction, dirty flag
- **Migrations:** (already done — 6 tests passing)

### Integration Tests (pytest-qt)

- **Open flow:** simulate File > Open → verify viewport shows rendered page
- **Error dialogs:** simulate opening nonexistent file → verify error dialog text
- **Password flow:** simulate opening encrypted PDF → verify password dialog appears
- **Drag-and-drop:** simulate drop event → verify document opens
- **Status bar:** verify page count and loading indicators update correctly
- **Lazy rendering:** verify only visible pages + buffer are rendered on scroll

### Test Fixtures

- Small valid PDF (1-3 pages, generated by PyMuPDF in conftest.py)
- Encrypted PDF (generated with known password)
- Non-PDF file (text file with .pdf extension)
- Corrupt PDF (valid header, truncated content)

All test PDFs are generated programmatically in `conftest.py` — no binary fixtures committed.

---

## 11. Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| `k_pdf/services/pdf_engine.py` | Implement | PyMuPDF wrapper with full API |
| `k_pdf/core/document_model.py` | Implement | DocumentModel, DocumentMetadata, PageInfo dataclasses |
| `k_pdf/core/page_cache.py` | Create | LRU page cache |
| `k_pdf/core/event_bus.py` | Implement | Central signal bus for app-wide events |
| `k_pdf/presenters/document_presenter.py` | Implement | Open flow, threading, error handling |
| `k_pdf/views/main_window.py` | Implement | Main window with menus, layout, drag-drop |
| `k_pdf/views/pdf_viewport.py` | Implement | QGraphicsView-based PDF rendering viewport |
| `k_pdf/main.py` | Update | CLI argument handling, app launch |
| `k_pdf/app.py` | Implement | QApplication subclass, startup wiring |
| `k_pdf/persistence/recent_files.py` | Implement | Recent files tracking via SQLite |
| `tests/conftest.py` | Create | PDF test fixtures |
| `tests/test_pdf_engine.py` | Create | PdfEngine unit tests |
| `tests/test_page_cache.py` | Create | PageCache unit tests |
| `tests/test_document_presenter.py` | Create | Presenter integration tests |
| `tests/test_main_window.py` | Create | UI integration tests |
