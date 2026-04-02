# Feature 1: Open and Render PDF — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the foundational PDF open-and-render feature so a user can open a PDF file and see its pages rendered in a scrollable viewport.

**Architecture:** Model-View-Presenter with Event Bus. PdfEngine (service) wraps PyMuPDF behind a clean API. DocumentPresenter coordinates threading via QThread worker. PdfViewport (QGraphicsView) displays rendered pages. All PyMuPDF imports isolated in `k_pdf/services/`.

**Tech Stack:** Python 3.13, PySide6 6.11, PyMuPDF 1.27, pytest, pytest-qt

**Spec:** `docs/superpowers/specs/2026-04-02-feature1-open-render-pdf-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `k_pdf/services/pdf_errors.py` | Create | PdfError exception hierarchy |
| `k_pdf/services/pdf_engine.py` | Implement | PyMuPDF wrapper: validate, open, render, close |
| `k_pdf/core/document_model.py` | Implement | DocumentMetadata, PageInfo, DocumentModel dataclasses |
| `k_pdf/core/page_cache.py` | Create | LRU cache of rendered QPixmap objects |
| `k_pdf/core/event_bus.py` | Implement | App-wide Qt signal bus |
| `k_pdf/persistence/recent_files.py` | Implement | Recent files CRUD via SQLite |
| `k_pdf/presenters/document_presenter.py` | Implement | PdfWorker + DocumentPresenter, threading, open flow |
| `k_pdf/views/pdf_viewport.py` | Implement | QGraphicsView-based PDF page renderer |
| `k_pdf/views/main_window.py` | Implement | Main window, menus, layout, drag-drop, dialogs |
| `k_pdf/app.py` | Implement | QApplication subclass, wiring |
| `k_pdf/main.py` | Update | CLI arg handling, app launch |
| `tests/conftest.py` | Create | Programmatic PDF test fixtures |
| `tests/test_pdf_engine.py` | Create | PdfEngine unit tests |
| `tests/test_page_cache.py` | Create | PageCache unit tests |
| `tests/test_recent_files.py` | Create | RecentFiles unit tests |
| `tests/test_document_presenter.py` | Create | Presenter tests |
| `tests/test_views.py` | Create | MainWindow + PdfViewport integration tests |

---

### Task 1: Test Fixtures and Error Types

**Files:**
- Create: `tests/conftest.py`
- Create: `k_pdf/services/pdf_errors.py`
- Create: `k_pdf/services/__init__.py` (update exports)

- [ ] **Step 1: Create test fixtures — programmatic PDF generation**

Write `tests/conftest.py`:

```python
"""Shared test fixtures — programmatically generated PDF files."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest


@pytest.fixture
def valid_pdf(tmp_path: Path) -> Path:
    """Create a valid 3-page PDF with text content."""
    path = tmp_path / "test.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page(width=612, height=792)  # US Letter
        text_point = pymupdf.Point(72, 72)
        page.insert_text(text_point, f"Page {i + 1} content")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def encrypted_pdf(tmp_path: Path) -> Path:
    """Create an encrypted PDF with password 'testpass'."""
    path = tmp_path / "encrypted.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(pymupdf.Point(72, 72), "Secret content")
    doc.save(
        str(path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="testpass",
        owner_pw="testpass",
    )
    doc.close()
    return path


@pytest.fixture
def not_a_pdf(tmp_path: Path) -> Path:
    """Create a text file with .pdf extension (no %PDF- header)."""
    path = tmp_path / "fake.pdf"
    path.write_text("This is not a PDF file.")
    return path


@pytest.fixture
def corrupt_pdf(tmp_path: Path) -> Path:
    """Create a file with %PDF- header but truncated/corrupt content."""
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"%PDF-1.4\n% corrupt data that cannot be parsed\n%%EOF")
    return path


@pytest.fixture
def nonexistent_pdf(tmp_path: Path) -> Path:
    """Return a path that does not exist."""
    return tmp_path / "does_not_exist.pdf"


@pytest.fixture
def unreadable_pdf(tmp_path: Path) -> Path:
    """Create a valid PDF then remove read permissions."""
    path = tmp_path / "unreadable.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    path.chmod(0o000)
    yield path
    path.chmod(0o644)  # restore for cleanup
```

- [ ] **Step 2: Create error types**

Write `k_pdf/services/pdf_errors.py`:

```python
"""PDF operation error types.

All PDF-related exceptions inherit from PdfError.
Used by PdfEngine; caught and translated by DocumentPresenter.
"""

from __future__ import annotations


class PdfError(Exception):
    """Base class for all PDF operation errors."""


class PdfValidationError(PdfError):
    """File validation failed (not found, permissions, not a PDF)."""


class PdfOpenError(PdfError):
    """PDF parsing/opening failed (corrupt file, unexpected error)."""


class PdfPasswordRequired(PdfError):
    """PDF is encrypted and requires a password."""


class PdfPasswordIncorrect(PdfError):
    """Provided password was incorrect."""


class PageRenderError(PdfError):
    """A single page failed to render."""
```

- [ ] **Step 3: Verify fixtures load correctly**

Run: `cd "/Users/karl/Documents/AI Projects/PDF writer /k-pdf" && uv run pytest tests/conftest.py --collect-only`
Expected: fixtures collected, no import errors

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py k_pdf/services/pdf_errors.py
git commit -m "feat(f1): add test fixtures and PDF error types"
```

---

### Task 2: Data Classes — DocumentMetadata, PageInfo

**Files:**
- Modify: `k_pdf/core/document_model.py`
- Create: `tests/test_document_model.py`

- [ ] **Step 1: Write failing tests for data classes**

Write `tests/test_document_model.py`:

```python
"""Tests for core data classes."""

from __future__ import annotations

from pathlib import Path

from k_pdf.core.document_model import DocumentMetadata, PageInfo


def test_document_metadata_construction() -> None:
    meta = DocumentMetadata(
        file_path=Path("/tmp/test.pdf"),
        page_count=5,
        title="Test Doc",
        author="Author",
        has_forms=False,
        has_outline=True,
        has_javascript=False,
        is_encrypted=False,
        file_size_bytes=1024,
    )
    assert meta.page_count == 5
    assert meta.title == "Test Doc"
    assert meta.has_outline is True


def test_page_info_construction() -> None:
    page = PageInfo(
        index=0,
        width=612.0,
        height=792.0,
        rotation=0,
        has_text=True,
        annotation_count=0,
    )
    assert page.index == 0
    assert page.width == 612.0
    assert page.rotation == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_document_model.py -v`
Expected: FAIL — ImportError for DocumentMetadata, PageInfo

- [ ] **Step 3: Implement data classes**

Write `k_pdf/core/document_model.py`:

```python
"""In-memory document state.

DocumentMetadata and PageInfo are pure data — no Qt or PyMuPDF imports.
DocumentModel holds the full per-tab state including the opaque doc handle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class DocumentMetadata:
    """Immutable metadata extracted from a PDF document."""

    file_path: Path
    page_count: int
    title: str | None
    author: str | None
    has_forms: bool
    has_outline: bool
    has_javascript: bool
    is_encrypted: bool
    file_size_bytes: int


@dataclass(frozen=True)
class PageInfo:
    """Immutable metadata for a single PDF page."""

    index: int
    width: float       # points (1/72 inch)
    height: float      # points
    rotation: int      # 0, 90, 180, 270 (from PDF, not view rotation)
    has_text: bool
    annotation_count: int


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

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_document_model.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add k_pdf/core/document_model.py tests/test_document_model.py
git commit -m "feat(f1): implement DocumentMetadata, PageInfo, DocumentModel"
```

---

### Task 3: PdfEngine — validate_pdf_path

**Files:**
- Modify: `k_pdf/services/pdf_engine.py`
- Create: `tests/test_pdf_engine.py`

- [ ] **Step 1: Write failing tests for validate_pdf_path**

Write `tests/test_pdf_engine.py`:

```python
"""Tests for PdfEngine service."""

from __future__ import annotations

from pathlib import Path

import pytest

from k_pdf.services.pdf_engine import PdfEngine
from k_pdf.services.pdf_errors import PdfValidationError


class TestValidatePdfPath:
    """Tests for PdfEngine.validate_pdf_path."""

    def setup_method(self) -> None:
        self.engine = PdfEngine()

    def test_raises_when_file_not_found(self, nonexistent_pdf: Path) -> None:
        with pytest.raises(PdfValidationError, match="not found"):
            self.engine.validate_pdf_path(nonexistent_pdf)

    def test_raises_when_file_not_readable(self, unreadable_pdf: Path) -> None:
        with pytest.raises(PdfValidationError, match="permission"):
            self.engine.validate_pdf_path(unreadable_pdf)

    def test_raises_when_not_a_pdf(self, not_a_pdf: Path) -> None:
        with pytest.raises(PdfValidationError, match="does not appear to be a valid PDF"):
            self.engine.validate_pdf_path(not_a_pdf)

    def test_passes_for_valid_pdf(self, valid_pdf: Path) -> None:
        self.engine.validate_pdf_path(valid_pdf)  # should not raise

    def test_passes_for_encrypted_pdf(self, encrypted_pdf: Path) -> None:
        self.engine.validate_pdf_path(encrypted_pdf)  # header check passes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pdf_engine.py::TestValidatePdfPath -v`
Expected: FAIL — ImportError or AttributeError

- [ ] **Step 3: Implement validate_pdf_path**

Write `k_pdf/services/pdf_engine.py`:

```python
"""PyMuPDF wrapper: open, render, save.

All fitz/pymupdf imports are contained in this file.
No other module in k_pdf may import fitz or pymupdf.
"""

from __future__ import annotations

import logging
from pathlib import Path

from k_pdf.services.pdf_errors import PdfValidationError

logger = logging.getLogger("k_pdf.services.pdf_engine")

_PDF_HEADER = b"%PDF-"


class PdfEngine:
    """Stateless PyMuPDF wrapper. Thread-safe for concurrent reads."""

    def validate_pdf_path(self, path: Path) -> None:
        """Check file exists, is readable, and has a PDF header.

        Args:
            path: Path to the file to validate.

        Raises:
            PdfValidationError: If any validation check fails.
        """
        if not path.exists():
            msg = f"File not found: {path}"
            raise PdfValidationError(msg)

        if not path.is_file():
            msg = f"Not a file: {path}"
            raise PdfValidationError(msg)

        try:
            with path.open("rb") as f:
                header = f.read(len(_PDF_HEADER))
        except PermissionError as e:
            msg = f"Cannot open {path.name}: permission denied"
            raise PdfValidationError(msg) from e

        if header != _PDF_HEADER:
            msg = f"Cannot open {path.name}: this file does not appear to be a valid PDF"
            raise PdfValidationError(msg)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pdf_engine.py::TestValidatePdfPath -v`
Expected: 5 passed (Note: unreadable_pdf test may skip on Windows — that's OK)

- [ ] **Step 5: Run linter and type checker**

Run: `uv run ruff check k_pdf/services/ tests/test_pdf_engine.py && uv run mypy k_pdf/services/`
Expected: All checks passed

- [ ] **Step 6: Commit**

```bash
git add k_pdf/services/pdf_engine.py tests/test_pdf_engine.py
git commit -m "feat(f1): implement PdfEngine.validate_pdf_path with TDD"
```

---

### Task 4: PdfEngine — open_document

**Files:**
- Modify: `k_pdf/services/pdf_engine.py`
- Modify: `tests/test_pdf_engine.py`

- [ ] **Step 1: Write failing tests for open_document**

Append to `tests/test_pdf_engine.py`:

```python
from k_pdf.core.document_model import DocumentMetadata, PageInfo
from k_pdf.services.pdf_errors import (
    PdfOpenError,
    PdfPasswordIncorrect,
    PdfPasswordRequired,
    PdfValidationError,
)


class TestOpenDocument:
    """Tests for PdfEngine.open_document."""

    def setup_method(self) -> None:
        self.engine = PdfEngine()

    def test_opens_valid_pdf_returns_metadata(self, valid_pdf: Path) -> None:
        result = self.engine.open_document(valid_pdf)
        assert result.metadata.page_count == 3
        assert result.metadata.file_path == valid_pdf
        assert result.metadata.is_encrypted is False
        assert len(result.pages) == 3
        assert result.doc_handle is not None
        self.engine.close_document(result.doc_handle)

    def test_pages_have_correct_dimensions(self, valid_pdf: Path) -> None:
        result = self.engine.open_document(valid_pdf)
        page = result.pages[0]
        assert page.index == 0
        assert page.width == pytest.approx(612.0, abs=1.0)
        assert page.height == pytest.approx(792.0, abs=1.0)
        assert page.rotation == 0
        self.engine.close_document(result.doc_handle)

    def test_raises_password_required_for_encrypted_pdf(
        self, encrypted_pdf: Path
    ) -> None:
        with pytest.raises(PdfPasswordRequired):
            self.engine.open_document(encrypted_pdf)

    def test_opens_encrypted_pdf_with_correct_password(
        self, encrypted_pdf: Path
    ) -> None:
        result = self.engine.open_document(encrypted_pdf, password="testpass")
        assert result.metadata.page_count == 1
        assert result.metadata.is_encrypted is True
        self.engine.close_document(result.doc_handle)

    def test_raises_password_incorrect_for_wrong_password(
        self, encrypted_pdf: Path
    ) -> None:
        with pytest.raises(PdfPasswordIncorrect):
            self.engine.open_document(encrypted_pdf, password="wrong")

    def test_raises_open_error_for_corrupt_pdf(self, corrupt_pdf: Path) -> None:
        with pytest.raises(PdfOpenError):
            self.engine.open_document(corrupt_pdf)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pdf_engine.py::TestOpenDocument -v`
Expected: FAIL — AttributeError (open_document not defined)

- [ ] **Step 3: Implement open_document and close_document**

Add to `k_pdf/services/pdf_engine.py` (imports at top, methods in class):

```python
# Add these imports at the top of the file:
from dataclasses import dataclass
from typing import Any

import pymupdf

from k_pdf.core.document_model import DocumentMetadata, PageInfo
from k_pdf.services.pdf_errors import (
    PdfOpenError,
    PdfPasswordIncorrect,
    PdfPasswordRequired,
)


@dataclass
class OpenResult:
    """Result of opening a PDF document."""

    doc_handle: Any  # pymupdf.Document
    metadata: DocumentMetadata
    pages: list[PageInfo]


# Add these methods to the PdfEngine class:

    def open_document(
        self, path: Path, password: str | None = None
    ) -> OpenResult:
        """Open a PDF and return handle, metadata, and page info.

        Args:
            path: Path to the PDF file (should be pre-validated).
            password: Optional password for encrypted PDFs.

        Returns:
            OpenResult with doc handle, metadata, and page list.

        Raises:
            PdfPasswordRequired: If the PDF is encrypted and no password given.
            PdfPasswordIncorrect: If the provided password is wrong.
            PdfOpenError: If the PDF is corrupt or cannot be parsed.
        """
        try:
            doc = pymupdf.open(str(path))
        except Exception as e:
            msg = f"Cannot open {path.name}: the file is damaged or corrupted. {e}"
            raise PdfOpenError(msg) from e

        if doc.needs_pass:
            if password is None:
                doc.close()
                raise PdfPasswordRequired(str(path))
            if not doc.authenticate(password):
                doc.close()
                raise PdfPasswordIncorrect(str(path))

        try:
            toc = doc.get_toc()
        except Exception:
            toc = []

        raw_meta = doc.metadata or {}
        metadata = DocumentMetadata(
            file_path=path,
            page_count=doc.page_count,
            title=raw_meta.get("title") or None,
            author=raw_meta.get("author") or None,
            has_forms=bool(doc.is_form_pdf),
            has_outline=len(toc) > 0,
            has_javascript=False,  # detected per-field in Feature 8
            is_encrypted=doc.is_encrypted,
            file_size_bytes=path.stat().st_size,
        )

        pages: list[PageInfo] = []
        for i in range(doc.page_count):
            page = doc[i]
            pages.append(
                PageInfo(
                    index=i,
                    width=page.rect.width,
                    height=page.rect.height,
                    rotation=page.rotation,
                    has_text=bool(page.get_text("text").strip()),
                    annotation_count=len(page.annots() or []),
                )
            )

        return OpenResult(doc_handle=doc, metadata=metadata, pages=pages)

    def close_document(self, doc_handle: Any) -> None:
        """Close a PyMuPDF document handle and release memory.

        Args:
            doc_handle: The pymupdf.Document to close.
        """
        try:
            doc_handle.close()
        except Exception:
            logger.warning("Failed to close document handle", exc_info=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pdf_engine.py -v`
Expected: All tests pass (TestValidatePdfPath + TestOpenDocument)

- [ ] **Step 5: Run linter and type checker**

Run: `uv run ruff check k_pdf/services/ && uv run mypy k_pdf/services/`

- [ ] **Step 6: Commit**

```bash
git add k_pdf/services/pdf_engine.py tests/test_pdf_engine.py
git commit -m "feat(f1): implement PdfEngine.open_document and close_document"
```

---

### Task 5: PdfEngine — render_page

**Files:**
- Modify: `k_pdf/services/pdf_engine.py`
- Modify: `tests/test_pdf_engine.py`

- [ ] **Step 1: Write failing tests for render_page**

Append to `tests/test_pdf_engine.py`:

```python
from PySide6.QtGui import QImage

from k_pdf.services.pdf_errors import PageRenderError


class TestRenderPage:
    """Tests for PdfEngine.render_page."""

    def setup_method(self) -> None:
        self.engine = PdfEngine()

    def test_renders_valid_page_returns_qimage(self, valid_pdf: Path) -> None:
        result = self.engine.open_document(valid_pdf)
        image = self.engine.render_page(result.doc_handle, page_index=0)
        assert isinstance(image, QImage)
        assert image.width() > 0
        assert image.height() > 0
        self.engine.close_document(result.doc_handle)

    def test_renders_with_zoom(self, valid_pdf: Path) -> None:
        result = self.engine.open_document(valid_pdf)
        img_1x = self.engine.render_page(result.doc_handle, 0, zoom=1.0)
        img_2x = self.engine.render_page(result.doc_handle, 0, zoom=2.0)
        assert img_2x.width() > img_1x.width()
        self.engine.close_document(result.doc_handle)

    def test_raises_for_invalid_page_index(self, valid_pdf: Path) -> None:
        result = self.engine.open_document(valid_pdf)
        with pytest.raises(PageRenderError):
            self.engine.render_page(result.doc_handle, page_index=999)
        self.engine.close_document(result.doc_handle)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pdf_engine.py::TestRenderPage -v`
Expected: FAIL — AttributeError (render_page not defined)

- [ ] **Step 3: Implement render_page**

Add to `PdfEngine` class in `k_pdf/services/pdf_engine.py`:

```python
    # Add this import at the top of the file:
    from PySide6.QtGui import QImage

    def render_page(
        self,
        doc_handle: Any,
        page_index: int,
        zoom: float = 1.0,
        rotation: int = 0,
    ) -> QImage:
        """Render a single PDF page to a QImage.

        This method is thread-safe and intended to be called from worker threads.
        The caller should convert QImage to QPixmap on the main thread.

        Args:
            doc_handle: The pymupdf.Document containing the page.
            page_index: 0-based page index.
            zoom: Zoom factor (1.0 = 100%).
            rotation: Additional rotation in degrees (0, 90, 180, 270).

        Returns:
            QImage with the rendered page content.

        Raises:
            PageRenderError: If the page cannot be rendered.
        """
        from k_pdf.services.pdf_errors import PageRenderError

        try:
            if page_index < 0 or page_index >= doc_handle.page_count:
                msg = f"Page index {page_index} out of range (0-{doc_handle.page_count - 1})"
                raise IndexError(msg)

            page = doc_handle[page_index]
            mat = pymupdf.Matrix(zoom, zoom).prerotate(rotation)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            image = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                QImage.Format.Format_RGB888,
            )
            # QImage references pix.samples buffer — make a deep copy
            return image.copy()

        except IndexError as e:
            raise PageRenderError(str(e)) from e
        except Exception as e:
            msg = f"Failed to render page {page_index}: {e}"
            raise PageRenderError(msg) from e
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pdf_engine.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add k_pdf/services/pdf_engine.py tests/test_pdf_engine.py
git commit -m "feat(f1): implement PdfEngine.render_page"
```

---

### Task 6: PageCache — LRU Cache

**Files:**
- Create: `k_pdf/core/page_cache.py`
- Create: `tests/test_page_cache.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_page_cache.py`:

```python
"""Tests for LRU page cache."""

from __future__ import annotations

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from k_pdf.core.page_cache import PageCache

# QPixmap requires a QApplication instance
_app: QApplication | None = None


def setup_module() -> None:
    global _app  # noqa: PLW0603
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_pixmap(w: int = 10, h: int = 10) -> QPixmap:
    """Create a small test QPixmap."""
    img = QImage(w, h, QImage.Format.Format_RGB888)
    img.fill(0)
    return QPixmap.fromImage(img)


def test_put_and_get() -> None:
    cache = PageCache(max_pages=5)
    pix = _make_pixmap()
    cache.put(0, pix)
    assert cache.get(0) is not None
    assert cache.size() == 1


def test_get_returns_none_for_missing() -> None:
    cache = PageCache(max_pages=5)
    assert cache.get(42) is None


def test_lru_eviction_when_full() -> None:
    cache = PageCache(max_pages=3)
    for i in range(4):
        cache.put(i, _make_pixmap())
    # Page 0 should have been evicted (oldest)
    assert cache.get(0) is None
    assert cache.get(1) is not None
    assert cache.get(3) is not None
    assert cache.size() == 3


def test_get_refreshes_lru_order() -> None:
    cache = PageCache(max_pages=3)
    cache.put(0, _make_pixmap())
    cache.put(1, _make_pixmap())
    cache.put(2, _make_pixmap())
    # Access page 0 to refresh it
    cache.get(0)
    # Add page 3 — page 1 should be evicted (oldest untouched)
    cache.put(3, _make_pixmap())
    assert cache.get(0) is not None  # was refreshed
    assert cache.get(1) is None       # evicted
    assert cache.get(3) is not None


def test_invalidate_single_page() -> None:
    cache = PageCache(max_pages=5)
    cache.put(0, _make_pixmap())
    cache.put(1, _make_pixmap())
    cache.invalidate(0)
    assert cache.get(0) is None
    assert cache.get(1) is not None
    assert cache.size() == 1


def test_invalidate_all_pages() -> None:
    cache = PageCache(max_pages=5)
    for i in range(3):
        cache.put(i, _make_pixmap())
    cache.invalidate()
    assert cache.size() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_page_cache.py -v`
Expected: FAIL — ImportError (page_cache module empty)

- [ ] **Step 3: Implement PageCache**

Write `k_pdf/core/page_cache.py`:

```python
"""LRU cache of rendered QPixmap objects.

One PageCache instance per open tab. Capacity defaults to 50 pages.
Uses collections.OrderedDict for O(1) get/put/eviction.
"""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtGui import QPixmap


class PageCache:
    """LRU cache mapping page indices to rendered QPixmap objects."""

    def __init__(self, max_pages: int = 50) -> None:
        """Initialize the cache.

        Args:
            max_pages: Maximum number of pages to cache.
        """
        self._max_pages = max_pages
        self._cache: OrderedDict[int, QPixmap] = OrderedDict()

    def get(self, page_index: int) -> QPixmap | None:
        """Retrieve a cached pixmap, refreshing its LRU position.

        Args:
            page_index: The 0-based page index.

        Returns:
            The cached QPixmap, or None if not cached.
        """
        if page_index not in self._cache:
            return None
        self._cache.move_to_end(page_index)
        return self._cache[page_index]

    def put(self, page_index: int, pixmap: QPixmap) -> None:
        """Cache a rendered pixmap, evicting the oldest entry if full.

        Args:
            page_index: The 0-based page index.
            pixmap: The rendered page pixmap.
        """
        if page_index in self._cache:
            self._cache.move_to_end(page_index)
            self._cache[page_index] = pixmap
            return

        if len(self._cache) >= self._max_pages:
            self._cache.popitem(last=False)

        self._cache[page_index] = pixmap

    def invalidate(self, page_index: int | None = None) -> None:
        """Remove cached entries.

        Args:
            page_index: If given, remove only that page. If None, clear all.
        """
        if page_index is None:
            self._cache.clear()
        else:
            self._cache.pop(page_index, None)

    def size(self) -> int:
        """Return the number of currently cached pages."""
        return len(self._cache)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_page_cache.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add k_pdf/core/page_cache.py tests/test_page_cache.py
git commit -m "feat(f1): implement LRU PageCache"
```

---

### Task 7: EventBus and RecentFiles

**Files:**
- Modify: `k_pdf/core/event_bus.py`
- Modify: `k_pdf/persistence/recent_files.py`
- Create: `tests/test_recent_files.py`

- [ ] **Step 1: Implement EventBus**

Write `k_pdf/core/event_bus.py`:

```python
"""Qt signal-based event system.

Singleton signal hub for app-wide events. Components connect to
signals here rather than directly to each other, reducing coupling.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """Central signal bus for application-wide events."""

    # File operations
    file_open_requested = Signal(Path)
    document_ready = Signal(object)       # DocumentModel
    document_closed = Signal(str)         # session_id

    # Error signals
    error_occurred = Signal(str, str)     # (title, message)
    password_required = Signal(Path)

    # Page rendering
    page_ready = Signal(int, object)      # (page_index, QPixmap)
    pages_requested = Signal(list)        # list[int] page indices

    # Status updates
    status_message = Signal(str)          # status bar text
    loading_progress = Signal(int)        # 0-100 percentage


# Module-level singleton
_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the global EventBus singleton.

    Creates the instance on first call. Must be called after QApplication exists.
    """
    global _bus  # noqa: PLW0603
    if _bus is None:
        _bus = EventBus()
    return _bus
```

- [ ] **Step 2: Write failing tests for RecentFiles**

Write `tests/test_recent_files.py`:

```python
"""Tests for recent files persistence."""

from __future__ import annotations

from pathlib import Path

from k_pdf.persistence.recent_files import RecentFiles
from k_pdf.persistence.settings_db import init_db


def test_add_and_list(tmp_path: Path) -> None:
    db = init_db(tmp_path / "test.db")
    rf = RecentFiles(db)
    rf.add(Path("/tmp/a.pdf"))
    rf.add(Path("/tmp/b.pdf"))
    files = rf.list_recent(limit=10)
    assert len(files) == 2
    # Most recent first
    assert files[0]["file_path"] == "/tmp/b.pdf"
    db.close()


def test_upsert_updates_timestamp(tmp_path: Path) -> None:
    db = init_db(tmp_path / "test.db")
    rf = RecentFiles(db)
    rf.add(Path("/tmp/a.pdf"), page_number=1)
    rf.add(Path("/tmp/a.pdf"), page_number=5)
    files = rf.list_recent(limit=10)
    assert len(files) == 1
    assert files[0]["page_number"] == 5
    db.close()


def test_list_respects_limit(tmp_path: Path) -> None:
    db = init_db(tmp_path / "test.db")
    rf = RecentFiles(db)
    for i in range(10):
        rf.add(Path(f"/tmp/file{i}.pdf"))
    files = rf.list_recent(limit=5)
    assert len(files) == 5
    db.close()


def test_remove_deletes_entry(tmp_path: Path) -> None:
    db = init_db(tmp_path / "test.db")
    rf = RecentFiles(db)
    rf.add(Path("/tmp/a.pdf"))
    rf.remove(Path("/tmp/a.pdf"))
    files = rf.list_recent(limit=10)
    assert len(files) == 0
    db.close()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_recent_files.py -v`
Expected: FAIL — ImportError

- [ ] **Step 4: Implement RecentFiles**

Write `k_pdf/persistence/recent_files.py`:

```python
"""Recent files tracking via SQLite.

Stores file paths, last-viewed page, and zoom level.
Upserts on each open. Ordered by last_opened_at descending.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class RecentFiles:
    """CRUD operations for the recent_files table."""

    def __init__(self, db: sqlite3.Connection) -> None:
        """Initialize with a database connection.

        Args:
            db: SQLite connection (must have recent_files table).
        """
        self._db = db

    def add(
        self,
        file_path: Path,
        page_number: int = 1,
        zoom_level: str = "fit_width",
    ) -> None:
        """Add or update a recent file entry.

        Args:
            file_path: Absolute path to the PDF file.
            page_number: Last viewed page number.
            zoom_level: Last zoom setting.
        """
        self._db.execute(
            """INSERT INTO recent_files (file_path, page_number, zoom_level, last_opened_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(file_path) DO UPDATE SET
                page_number = excluded.page_number,
                zoom_level = excluded.zoom_level,
                last_opened_at = datetime('now')
            """,
            (str(file_path), page_number, zoom_level),
        )
        self._db.commit()

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent files ordered by last opened time (newest first).

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of dicts with file_path, page_number, zoom_level keys.
        """
        cursor = self._db.execute(
            """SELECT file_path, page_number, zoom_level
            FROM recent_files
            ORDER BY last_opened_at DESC
            LIMIT ?""",
            (limit,),
        )
        return [
            {
                "file_path": row[0],
                "page_number": row[1],
                "zoom_level": row[2],
            }
            for row in cursor.fetchall()
        ]

    def remove(self, file_path: Path) -> None:
        """Remove a file from the recent list.

        Args:
            file_path: Path to remove.
        """
        self._db.execute(
            "DELETE FROM recent_files WHERE file_path = ?",
            (str(file_path),),
        )
        self._db.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_recent_files.py -v`
Expected: 4 passed

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass (migrations + document_model + pdf_engine + page_cache + recent_files)

- [ ] **Step 7: Commit**

```bash
git add k_pdf/core/event_bus.py k_pdf/persistence/recent_files.py tests/test_recent_files.py
git commit -m "feat(f1): implement EventBus and RecentFiles"
```

---

### Task 8: PdfViewport — QGraphicsView Rendering

**Files:**
- Modify: `k_pdf/views/pdf_viewport.py`

- [ ] **Step 1: Implement PdfViewport**

Write `k_pdf/views/pdf_viewport.py`:

```python
"""PDF rendering viewport using QGraphicsView.

Displays rendered PDF pages vertically in a scrollable scene.
Manages viewport states: Empty, Loading, Error, Success.
Requests rendering for visible pages plus a 1-page buffer.
"""

from __future__ import annotations

import logging
from enum import Enum, auto

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from k_pdf.core.document_model import PageInfo

logger = logging.getLogger("k_pdf.views.pdf_viewport")

_PAGE_GAP = 20  # pixels between pages


class ViewportState(Enum):
    """States for the PDF viewport."""

    EMPTY = auto()
    LOADING = auto()
    ERROR = auto()
    SUCCESS = auto()


class WelcomeWidget(QWidget):
    """Welcome screen shown when no document is open."""

    open_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("K-PDF")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(24)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        subtitle = QLabel("Free, offline PDF reader and editor")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        open_btn = QPushButton("Open File")
        open_btn.setFixedWidth(200)
        open_btn.clicked.connect(self.open_clicked.emit)
        layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)


class PdfViewport(QGraphicsView):
    """QGraphicsView that displays rendered PDF pages.

    Pages are laid out vertically with gaps between them.
    Emits visible_pages_changed when the user scrolls so the
    presenter can request rendering for uncached pages.
    """

    visible_pages_changed = Signal(list)  # list[int] of visible page indices

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.setRenderHint(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self._state = ViewportState.EMPTY
        self._pages: list[PageInfo] = []
        self._page_items: dict[int, QGraphicsPixmapItem | QGraphicsRectItem] = {}
        self._page_y_offsets: list[float] = []

        # Welcome widget overlay
        self._welcome = WelcomeWidget(self)
        self._welcome.show()

        # Connect scroll changes to lazy render requests
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    @property
    def welcome_widget(self) -> WelcomeWidget:
        """Return the welcome widget for external signal connections."""
        return self._welcome

    @property
    def state(self) -> ViewportState:
        """Return the current viewport state."""
        return self._state

    def set_loading(self, filename: str) -> None:
        """Switch to loading state.

        Args:
            filename: Name of file being loaded.
        """
        self._state = ViewportState.LOADING
        self._welcome.hide()
        self._scene.clear()
        self._page_items.clear()
        text = self._scene.addSimpleText(f"Loading {filename}...")
        text.setPos(50, 50)

    def set_error(self, message: str) -> None:
        """Switch to error state.

        Args:
            message: Error message to display.
        """
        self._state = ViewportState.ERROR
        self._welcome.hide()
        self._scene.clear()
        self._page_items.clear()
        text = self._scene.addSimpleText(message)
        text.setPos(50, 50)

    def set_document(self, pages: list[PageInfo], zoom: float = 1.0) -> None:
        """Set up the viewport for a new document.

        Creates placeholder rectangles for all pages and calculates
        vertical layout. Does not render pages — rendering is triggered
        by scroll position via visible_pages_changed signal.

        Args:
            pages: List of PageInfo for each page in the document.
            zoom: Current zoom factor.
        """
        self._state = ViewportState.SUCCESS
        self._welcome.hide()
        self._scene.clear()
        self._page_items.clear()
        self._pages = pages
        self._page_y_offsets = []

        y_offset = 0.0
        for page_info in pages:
            w = page_info.width * zoom
            h = page_info.height * zoom

            # Create a placeholder rectangle
            rect_item = self._scene.addRect(
                QRectF(0, 0, w, h),
                brush=QBrush(QColor(240, 240, 240)),
            )
            rect_item.setPos(0, y_offset)
            self._page_items[page_info.index] = rect_item

            # Page number label centered in placeholder
            label = QGraphicsSimpleTextItem(f"Page {page_info.index + 1}")
            label.setFont(QFont("", 12))
            label_rect = label.boundingRect()
            label.setPos(
                (w - label_rect.width()) / 2,
                y_offset + (h - label_rect.height()) / 2,
            )
            self._scene.addItem(label)

            self._page_y_offsets.append(y_offset)
            y_offset += h + _PAGE_GAP

        self._scene.setSceneRect(QRectF(0, 0, self._max_page_width(zoom), y_offset))
        self.centerOn(0, 0)

        # Trigger initial render request
        self._emit_visible_pages()

    def set_page_pixmap(self, page_index: int, pixmap: QPixmap) -> None:
        """Replace a page placeholder with a rendered pixmap.

        Args:
            page_index: The page to update.
            pixmap: The rendered page image.
        """
        if page_index not in self._page_items:
            return

        old_item = self._page_items[page_index]
        y_pos = old_item.pos().y()
        self._scene.removeItem(old_item)

        pixmap_item = QGraphicsPixmapItem(pixmap)
        pixmap_item.setPos(0, y_pos)
        self._scene.addItem(pixmap_item)
        self._page_items[page_index] = pixmap_item

    def set_page_error(self, page_index: int) -> None:
        """Show an error placeholder for a page that failed to render.

        Args:
            page_index: The page that failed.
        """
        if page_index >= len(self._pages):
            return

        page_info = self._pages[page_index]
        if page_index in self._page_items:
            old_item = self._page_items[page_index]
            y_pos = old_item.pos().y()
            self._scene.removeItem(old_item)
        else:
            y_pos = self._page_y_offsets[page_index] if page_index < len(self._page_y_offsets) else 0

        rect_item = self._scene.addRect(
            QRectF(0, 0, page_info.width, page_info.height),
            brush=QBrush(QColor(200, 200, 200)),
        )
        rect_item.setPos(0, y_pos)
        self._page_items[page_index] = rect_item

        label = QGraphicsSimpleTextItem(f"Render error on page {page_index + 1}")
        label.setFont(QFont("", 11))
        label_rect = label.boundingRect()
        label.setPos(
            (page_info.width - label_rect.width()) / 2,
            y_pos + (page_info.height - label_rect.height()) / 2,
        )
        self._scene.addItem(label)

    def show_welcome(self) -> None:
        """Show the welcome screen (no document open)."""
        self._state = ViewportState.EMPTY
        self._scene.clear()
        self._page_items.clear()
        self._pages = []
        self._welcome.show()

    def get_visible_page_range(self) -> tuple[int, int]:
        """Calculate which pages are currently visible plus 1-page buffer.

        Returns:
            Tuple of (first_visible_index, last_visible_index) inclusive.
            Returns (-1, -1) if no pages.
        """
        if not self._pages or not self._page_y_offsets:
            return (-1, -1)

        viewport_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        top = viewport_rect.top()
        bottom = viewport_rect.bottom()

        first_visible = -1
        last_visible = -1

        for i, y_off in enumerate(self._page_y_offsets):
            page_bottom = y_off + self._pages[i].height
            if page_bottom >= top and y_off <= bottom:
                if first_visible == -1:
                    first_visible = i
                last_visible = i

        if first_visible == -1:
            return (-1, -1)

        # Add 1-page buffer
        first_visible = max(0, first_visible - 1)
        last_visible = min(len(self._pages) - 1, last_visible + 1)
        return (first_visible, last_visible)

    def _on_scroll(self) -> None:
        """Handle scroll events — emit visible page range for lazy rendering."""
        self._emit_visible_pages()

    def _emit_visible_pages(self) -> None:
        """Calculate and emit the list of visible page indices."""
        first, last = self.get_visible_page_range()
        if first >= 0:
            self.visible_pages_changed.emit(list(range(first, last + 1)))

    def _max_page_width(self, zoom: float) -> float:
        """Return the maximum page width at the given zoom."""
        if not self._pages:
            return 0.0
        return max(p.width * zoom for p in self._pages)
```

- [ ] **Step 2: Run linter and type checker**

Run: `uv run ruff check k_pdf/views/pdf_viewport.py && uv run mypy k_pdf/views/pdf_viewport.py`
Expected: passes (or minor issues to fix)

- [ ] **Step 3: Commit**

```bash
git add k_pdf/views/pdf_viewport.py
git commit -m "feat(f1): implement PdfViewport with QGraphicsView"
```

---

### Task 9: MainWindow — Layout, Menus, Drag-Drop, Dialogs

**Files:**
- Modify: `k_pdf/views/main_window.py`

- [ ] **Step 1: Implement MainWindow**

Write `k_pdf/views/main_window.py`:

```python
"""Main application window.

Three-panel layout (navigation | viewport | annotations) with
menu bar, toolbar, status bar, and tab bar. For Feature 1, only
the viewport center panel is active. Navigation and annotation
panels are placeholders for Features 3 and 12.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QWidget,
)

from k_pdf.views.pdf_viewport import PdfViewport

logger = logging.getLogger("k_pdf.views.main_window")


class MainWindow(QMainWindow):
    """K-PDF main application window."""

    file_open_requested = Signal(Path)
    password_submitted = Signal(Path, str)  # (path, password)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("K-PDF")
        self.setMinimumSize(800, 600)
        self.resize(1200, 800)
        self.setAcceptDrops(True)

        # Central viewport
        self.viewport = PdfViewport(self)
        self.setCentralWidget(self.viewport)
        self.viewport.welcome_widget.open_clicked.connect(self._open_file_dialog)  # noqa: SLF001

        # Status bar
        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)
        self._page_label = QLabel("No document")
        self._zoom_label = QLabel("100%")
        self._status_bar.addPermanentWidget(self._page_label)
        self._status_bar.addPermanentWidget(self._zoom_label)

        # Menus
        self._setup_menus()

    @property
    def welcome_widget(self) -> QWidget:
        """Return the viewport's welcome widget for signal connections."""
        return self.viewport._welcome

    def _setup_menus(self) -> None:
        """Create the menu bar with File > Open and File > Quit."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _open_file_dialog(self) -> None:
        """Show the native file picker and emit file_open_requested."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF",
            "",
            "PDF Files (*.pdf);;All Files (*)",
        )
        if path:
            self.file_open_requested.emit(Path(path))

    def show_error(self, title: str, message: str) -> None:
        """Show an error dialog.

        Args:
            title: Dialog title.
            message: Error message body.
        """
        QMessageBox.critical(self, title, message)

    def show_password_dialog(self, path: Path) -> None:
        """Show a password input dialog for encrypted PDFs.

        Args:
            path: Path to the encrypted PDF.
        """
        password, ok = QInputDialog.getText(
            self,
            "Password Required",
            f"This document is protected.\nEnter the password to open it.\n\n{path.name}",
            QInputDialog.InputMode.TextInput,
        )
        if ok and password:
            self.password_submitted.emit(path, password)

    def update_page_status(self, current: int, total: int) -> None:
        """Update the page indicator in the status bar.

        Args:
            current: Current page number (1-based).
            total: Total number of pages.
        """
        self._page_label.setText(f"Page {current} of {total}")

    def update_status_message(self, message: str) -> None:
        """Show a temporary message in the status bar.

        Args:
            message: Message text.
        """
        self._status_bar.showMessage(message, 5000)

    # --- Drag and drop ---

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drag events for PDF files."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".pdf"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle dropped PDF files."""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(".pdf"):
                self.file_open_requested.emit(Path(file_path))
                break
```

- [ ] **Step 2: Run linter and type checker**

Run: `uv run ruff check k_pdf/views/main_window.py && uv run mypy k_pdf/views/main_window.py`

- [ ] **Step 3: Commit**

```bash
git add k_pdf/views/main_window.py
git commit -m "feat(f1): implement MainWindow with menus, drag-drop, dialogs"
```

---

### Task 10: DocumentPresenter — Threading and Open Flow

**Files:**
- Modify: `k_pdf/presenters/document_presenter.py`

- [ ] **Step 1: Implement PdfWorker and DocumentPresenter**

Write `k_pdf/presenters/document_presenter.py`:

```python
"""Document presenter — coordinates PDF services with views.

Receives file-open requests, validates paths, dispatches PyMuPDF work
to a background thread via PdfWorker, and updates the viewport via
signals when pages are ready.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QImage, QPixmap

from k_pdf.core.document_model import DocumentModel
from k_pdf.core.page_cache import PageCache
from k_pdf.services.pdf_engine import OpenResult, PdfEngine
from k_pdf.services.pdf_errors import (
    PdfError,
    PdfPasswordIncorrect,
    PdfPasswordRequired,
    PdfValidationError,
    PageRenderError,
)

logger = logging.getLogger("k_pdf.presenters.document_presenter")


class PdfWorker(QObject):
    """Worker that runs PdfEngine operations off the Qt event loop."""

    document_loaded = Signal(object)        # OpenResult
    load_failed = Signal(str, str)          # (title, message)
    password_required = Signal(object)      # Path
    password_incorrect = Signal(object)     # Path
    page_rendered = Signal(int, QImage)     # (page_index, QImage)
    page_render_failed = Signal(int)        # page_index

    def __init__(self) -> None:
        super().__init__()
        self._engine = PdfEngine()

    @Slot(object, object)
    def open_document(self, path: Path, password: str | None = None) -> None:
        """Open a PDF in the background thread.

        Args:
            path: Path to the PDF file.
            password: Optional password for encrypted PDFs.
        """
        try:
            result = self._engine.open_document(path, password=password)
            self.document_loaded.emit(result)
        except PdfPasswordRequired:
            self.password_required.emit(path)
        except PdfPasswordIncorrect:
            self.password_incorrect.emit(path)
        except PdfError as e:
            self.load_failed.emit("Cannot open file", str(e))
        except Exception as e:
            self.load_failed.emit(
                "Unexpected error",
                f"An unexpected error occurred: {type(e).__name__}: {e}",
            )

    @Slot(object, list, float, int)
    def render_pages(
        self,
        doc_handle: Any,
        page_indices: list[int],
        zoom: float,
        rotation: int,
    ) -> None:
        """Render a batch of pages in the background thread.

        Args:
            doc_handle: PyMuPDF document handle.
            page_indices: List of 0-based page indices to render.
            zoom: Zoom factor.
            rotation: Rotation in degrees.
        """
        for idx in page_indices:
            try:
                image = self._engine.render_page(doc_handle, idx, zoom, rotation)
                self.page_rendered.emit(idx, image)
            except PageRenderError:
                logger.warning("Failed to render page %d", idx, exc_info=True)
                self.page_render_failed.emit(idx)


class DocumentPresenter(QObject):
    """Coordinates PdfEngine, DocumentModel, PageCache, and views."""

    # Signals for the view layer
    document_ready = Signal(object)         # DocumentModel
    error_occurred = Signal(str, str)       # (title, message)
    password_requested = Signal(object)     # Path
    password_was_incorrect = Signal(object) # Path
    page_pixmap_ready = Signal(int, object) # (page_index, QPixmap)
    page_error = Signal(int)               # page_index
    status_message = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine = PdfEngine()
        self._model: DocumentModel | None = None
        self._cache = PageCache()
        self._pending_renders: set[int] = set()
        self._zoom = 1.0
        self._rotation = 0

        # Worker thread setup
        self._thread = QThread()
        self._worker = PdfWorker()
        self._worker.moveToThread(self._thread)
        self._thread.finished.connect(self._worker.deleteLater)

        # Connect worker signals
        self._worker.document_loaded.connect(self._on_document_loaded)
        self._worker.load_failed.connect(self._on_load_failed)
        self._worker.password_required.connect(self._on_password_required)
        self._worker.password_incorrect.connect(self._on_password_incorrect)
        self._worker.page_rendered.connect(self._on_page_rendered)
        self._worker.page_render_failed.connect(self._on_page_render_failed)

        self._thread.start()

    @property
    def model(self) -> DocumentModel | None:
        """Return the current document model, or None if no document is open."""
        return self._model

    @property
    def cache(self) -> PageCache:
        """Return the page cache."""
        return self._cache

    def open_file(self, path: Path) -> None:
        """Start the file-open flow.

        Validates the path on the main thread, then dispatches
        the heavy PyMuPDF open to the worker thread.

        Args:
            path: Path to the PDF file to open.
        """
        try:
            self._engine.validate_pdf_path(path)
        except PdfValidationError as e:
            self.error_occurred.emit("Validation Error", str(e))
            return

        self.status_message.emit(f"Opening {path.name}...")
        # Use QMetaObject.invokeMethod via signal for thread safety
        self._worker.open_document(path)

    def open_file_with_password(self, path: Path, password: str) -> None:
        """Retry opening an encrypted file with a password.

        Args:
            path: Path to the encrypted PDF.
            password: Password to try.
        """
        self._worker.open_document(path, password)

    def request_pages(self, page_indices: list[int]) -> None:
        """Request rendering for a list of page indices.

        Pages already in the cache are emitted immediately.
        Missing pages are dispatched to the worker thread.

        Args:
            page_indices: 0-based page indices to render.
        """
        if self._model is None:
            return

        to_render: list[int] = []
        for idx in page_indices:
            cached = self._cache.get(idx)
            if cached is not None:
                self.page_pixmap_ready.emit(idx, cached)
            elif idx not in self._pending_renders:
                to_render.append(idx)
                self._pending_renders.add(idx)

        if to_render:
            self._worker.render_pages(
                self._model.doc_handle, to_render, self._zoom, self._rotation
            )

    def shutdown(self) -> None:
        """Stop the worker thread and clean up."""
        self._thread.quit()
        self._thread.wait()
        if self._model is not None:
            self._engine.close_document(self._model.doc_handle)
            self._model = None

    # --- Worker signal handlers ---

    @Slot(object)
    def _on_document_loaded(self, result: OpenResult) -> None:
        """Handle successful document load from worker."""
        self._model = DocumentModel(
            file_path=result.metadata.file_path,
            doc_handle=result.doc_handle,
            metadata=result.metadata,
            pages=result.pages,
        )
        self._cache.invalidate()
        self._pending_renders.clear()
        self.status_message.emit(
            f"Loaded {result.metadata.file_path.name} "
            f"({result.metadata.page_count} pages)"
        )
        self.document_ready.emit(self._model)

    @Slot(str, str)
    def _on_load_failed(self, title: str, message: str) -> None:
        """Handle load failure from worker."""
        self.error_occurred.emit(title, message)
        self.status_message.emit("Failed to open file")

    @Slot(object)
    def _on_password_required(self, path: Path) -> None:
        """Handle password-required signal from worker."""
        self.password_requested.emit(path)

    @Slot(object)
    def _on_password_incorrect(self, path: Path) -> None:
        """Handle incorrect password from worker."""
        self.password_was_incorrect.emit(path)

    @Slot(int, QImage)
    def _on_page_rendered(self, page_index: int, image: QImage) -> None:
        """Handle rendered page from worker — convert to QPixmap on main thread."""
        self._pending_renders.discard(page_index)
        pixmap = QPixmap.fromImage(image)
        self._cache.put(page_index, pixmap)
        self.page_pixmap_ready.emit(page_index, pixmap)

    @Slot(int)
    def _on_page_render_failed(self, page_index: int) -> None:
        """Handle page render failure."""
        self._pending_renders.discard(page_index)
        self.page_error.emit(page_index)
```

- [ ] **Step 2: Run linter and type checker**

Run: `uv run ruff check k_pdf/presenters/document_presenter.py && uv run mypy k_pdf/presenters/document_presenter.py`

- [ ] **Step 3: Commit**

```bash
git add k_pdf/presenters/document_presenter.py
git commit -m "feat(f1): implement DocumentPresenter with PdfWorker threading"
```

---

### Task 11: App and main.py — Entry Point and Wiring

**Files:**
- Modify: `k_pdf/app.py`
- Modify: `k_pdf/main.py`

- [ ] **Step 1: Implement KPdfApp**

Write `k_pdf/app.py`:

```python
"""QApplication shell and event bus initialization.

Creates the main window, presenter, and wires signals together.
Handles CLI file arguments.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from k_pdf.core.document_model import DocumentModel
from k_pdf.persistence.recent_files import RecentFiles
from k_pdf.persistence.settings_db import init_db
from k_pdf.presenters.document_presenter import DocumentPresenter
from k_pdf.views.main_window import MainWindow

logger = logging.getLogger("k_pdf.app")


class KPdfApp:
    """Application controller — wires presenter to views."""

    def __init__(self, app: QApplication, file_path: str | None = None) -> None:
        self._app = app
        self._db = init_db()
        self._recent_files = RecentFiles(self._db)
        self._window = MainWindow()
        self._presenter = DocumentPresenter()
        self._initial_file = file_path

        self._connect_signals()
        self._window.show()

        # Open file from CLI argument after event loop starts
        if self._initial_file:
            QTimer.singleShot(0, self._open_initial_file)

    @property
    def window(self) -> MainWindow:
        """Return the main window."""
        return self._window

    @property
    def presenter(self) -> DocumentPresenter:
        """Return the document presenter."""
        return self._presenter

    def _connect_signals(self) -> None:
        """Wire presenter signals to view slots and vice versa."""
        # View → Presenter
        self._window.file_open_requested.connect(self._presenter.open_file)
        self._window.password_submitted.connect(
            self._presenter.open_file_with_password
        )
        self._window.viewport.visible_pages_changed.connect(
            self._presenter.request_pages
        )

        # Presenter → View
        self._presenter.document_ready.connect(self._on_document_ready)
        self._presenter.error_occurred.connect(self._window.show_error)
        self._presenter.password_requested.connect(self._window.show_password_dialog)
        self._presenter.password_was_incorrect.connect(self._on_password_incorrect)
        self._presenter.page_pixmap_ready.connect(
            self._window.viewport.set_page_pixmap
        )
        self._presenter.page_error.connect(self._window.viewport.set_page_error)
        self._presenter.status_message.connect(self._window.update_status_message)

    def _on_document_ready(self, model: DocumentModel) -> None:
        """Handle a successfully loaded document."""
        self._window.viewport.set_document(model.pages)
        self._window.update_page_status(1, model.metadata.page_count)
        self._recent_files.add(model.file_path)

    def _on_password_incorrect(self, path: Path) -> None:
        """Re-show the password dialog with an error hint."""
        self._window.show_error(
            "Incorrect password", "Incorrect password. Try again."
        )
        self._window.show_password_dialog(path)

    def _open_initial_file(self) -> None:
        """Open the file passed via CLI argument."""
        if self._initial_file:
            self._presenter.open_file(Path(self._initial_file))

    def shutdown(self) -> None:
        """Clean up resources before exit."""
        self._presenter.shutdown()
```

- [ ] **Step 2: Update main.py**

Write `k_pdf/main.py`:

```python
"""K-PDF application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.core.logging import setup_logging


def main() -> int:
    """Launch the K-PDF application.

    Supports opening a PDF file via CLI argument:
        k-pdf /path/to/file.pdf
    """
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("K-PDF")
    app.setOrganizationName("K-PDF")

    # Check for CLI file argument
    file_path: str | None = None
    args = app.arguments()
    if len(args) > 1 and args[1].lower().endswith(".pdf"):
        file_path = args[1]

    k_pdf_app = KPdfApp(app, file_path=file_path)

    exit_code = app.exec()
    k_pdf_app.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run linter and type checker**

Run: `uv run ruff check k_pdf/app.py k_pdf/main.py && uv run mypy k_pdf/app.py k_pdf/main.py`

- [ ] **Step 4: Commit**

```bash
git add k_pdf/app.py k_pdf/main.py
git commit -m "feat(f1): implement KPdfApp and main entry point with CLI args"
```

---

### Task 12: Integration Tests

**Files:**
- Create: `tests/test_document_presenter.py`
- Create: `tests/test_views.py`

- [ ] **Step 1: Write presenter tests**

Write `tests/test_document_presenter.py`:

```python
"""Tests for DocumentPresenter open flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication

from k_pdf.core.document_model import DocumentModel
from k_pdf.presenters.document_presenter import DocumentPresenter

_app: QApplication | None = None


def setup_module() -> None:
    global _app  # noqa: PLW0603
    if QApplication.instance() is None:
        _app = QApplication([])


class TestDocumentPresenter:
    """Test the DocumentPresenter open flow."""

    def test_open_file_emits_error_for_nonexistent(
        self, nonexistent_pdf: Path, qtbot: object
    ) -> None:
        presenter = DocumentPresenter()
        error_spy = MagicMock()
        presenter.error_occurred.connect(error_spy)

        presenter.open_file(nonexistent_pdf)

        error_spy.assert_called_once()
        title, msg = error_spy.call_args[0]
        assert "Validation" in title
        assert "not found" in msg.lower()
        presenter.shutdown()

    def test_open_file_emits_error_for_not_a_pdf(
        self, not_a_pdf: Path, qtbot: object
    ) -> None:
        presenter = DocumentPresenter()
        error_spy = MagicMock()
        presenter.error_occurred.connect(error_spy)

        presenter.open_file(not_a_pdf)

        error_spy.assert_called_once()
        _, msg = error_spy.call_args[0]
        assert "does not appear to be a valid PDF" in msg
        presenter.shutdown()

    def test_open_valid_file_emits_document_ready(
        self, valid_pdf: Path, qtbot: object
    ) -> None:
        presenter = DocumentPresenter()
        ready_spy = MagicMock()
        presenter.document_ready.connect(ready_spy)

        presenter.open_file(valid_pdf)

        # Wait for the worker thread to finish
        def check_ready() -> None:
            assert ready_spy.call_count == 1

        qtbot.waitUntil(check_ready, timeout=5000)

        model = ready_spy.call_args[0][0]
        assert isinstance(model, DocumentModel)
        assert model.metadata.page_count == 3
        presenter.shutdown()

    def test_open_encrypted_emits_password_requested(
        self, encrypted_pdf: Path, qtbot: object
    ) -> None:
        presenter = DocumentPresenter()
        pw_spy = MagicMock()
        presenter.password_requested.connect(pw_spy)

        presenter.open_file(encrypted_pdf)

        def check_pw() -> None:
            assert pw_spy.call_count == 1

        qtbot.waitUntil(check_pw, timeout=5000)
        presenter.shutdown()
```

- [ ] **Step 2: Run presenter tests**

Run: `uv run pytest tests/test_document_presenter.py -v`
Expected: All 4 tests pass

- [ ] **Step 3: Write view integration tests**

Write `tests/test_views.py`:

```python
"""Integration tests for MainWindow and PdfViewport."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from k_pdf.core.document_model import PageInfo
from k_pdf.views.main_window import MainWindow
from k_pdf.views.pdf_viewport import PdfViewport, ViewportState

_app: QApplication | None = None


def setup_module() -> None:
    global _app  # noqa: PLW0603
    if QApplication.instance() is None:
        _app = QApplication([])


class TestPdfViewport:
    """Tests for PdfViewport states and page display."""

    def test_initial_state_is_empty(self) -> None:
        viewport = PdfViewport()
        assert viewport.state == ViewportState.EMPTY

    def test_set_loading_changes_state(self) -> None:
        viewport = PdfViewport()
        viewport.set_loading("test.pdf")
        assert viewport.state == ViewportState.LOADING

    def test_set_error_changes_state(self) -> None:
        viewport = PdfViewport()
        viewport.set_error("Something went wrong")
        assert viewport.state == ViewportState.ERROR

    def test_set_document_creates_placeholders(self) -> None:
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=612, height=792, rotation=0,
                     has_text=True, annotation_count=0),
            PageInfo(index=1, width=612, height=792, rotation=0,
                     has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        assert viewport.state == ViewportState.SUCCESS

    def test_set_page_pixmap_replaces_placeholder(self) -> None:
        viewport = PdfViewport()
        pages = [
            PageInfo(index=0, width=100, height=100, rotation=0,
                     has_text=True, annotation_count=0),
        ]
        viewport.set_document(pages)
        img = QImage(100, 100, QImage.Format.Format_RGB888)
        img.fill(0)
        viewport.set_page_pixmap(0, QPixmap.fromImage(img))
        # Verify the item was replaced (no crash, item exists)
        assert 0 in viewport._page_items


class TestMainWindow:
    """Tests for MainWindow signals and dialogs."""

    def test_file_open_requested_signal(self, qtbot: object) -> None:
        window = MainWindow()
        spy = MagicMock()
        window.file_open_requested.connect(spy)

        # Simulate emitting directly (dialog is modal, can't test via UI)
        window.file_open_requested.emit(Path("/tmp/test.pdf"))

        spy.assert_called_once_with(Path("/tmp/test.pdf"))

    def test_update_page_status(self) -> None:
        window = MainWindow()
        window.update_page_status(3, 10)
        assert window._page_label.text() == "Page 3 of 10"
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 5: Run full lint + type check**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy k_pdf/`
Expected: All clean

- [ ] **Step 6: Commit**

```bash
git add tests/test_document_presenter.py tests/test_views.py
git commit -m "feat(f1): add presenter and view integration tests"
```

---

### Task 13: Final Verification and Cleanup

**Files:**
- All files from previous tasks

- [ ] **Step 1: Run full test suite with coverage**

Run: `uv run pytest --cov=k_pdf --cov-report=term-missing -v`
Expected: All tests pass, coverage report shows implemented modules

- [ ] **Step 2: Run all linters and security checks**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy k_pdf/ && gitleaks detect --source . --no-git`
Expected: All clean

- [ ] **Step 3: Manual smoke test — launch the app**

Run: `uv run python -m k_pdf.main`
Expected: Window appears with welcome screen. File > Open works. Opening a PDF renders pages.

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "feat(f1): Feature 1 complete — Open and Render PDF"
```
