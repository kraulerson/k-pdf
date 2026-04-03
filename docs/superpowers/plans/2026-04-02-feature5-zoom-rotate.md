# Feature 5: Zoom, Rotate, Page Fit Modes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add zoom (10%–3200%), rotation (0/90/180/270), and page fit modes (Fit Page, Fit Width) with a dedicated toolbar. Each tab maintains independent zoom/rotation state. Ctrl+scroll zooms at cursor, window resize recalculates fit modes, and tab switches push state to toolbar.

**Architecture:** Framework-free `ZoomState` dataclass + `FitMode` enum in `core/zoom_model.py`. `DocumentPresenter` owns a `ZoomState` per tab, exposes `set_zoom`/`set_rotation`/`set_fit_mode` methods that invalidate cache and re-render. `ZoomToolBar(QToolBar)` provides slider, percentage input, presets, and rotation buttons. `PdfViewport` emits `viewport_resized` and `zoom_at_cursor` signals. `KPdfApp` wires everything together.

**Tech Stack:** Python 3.13, PySide6 6.11, PyMuPDF 1.27, pytest + pytest-qt

**Spec:** `docs/superpowers/specs/2026-04-02-feature5-zoom-rotate-design.md`

---

## File Map

**New files:**
- `k_pdf/core/zoom_model.py` — `FitMode` enum + `ZoomState` dataclass
- `k_pdf/views/zoom_toolbar.py` — `ZoomToolBar(QToolBar)` with slider, input, presets, rotation buttons
- `tests/test_zoom_model.py` — unit tests for ZoomState and FitMode
- `tests/test_document_presenter_zoom.py` — unit tests for DocumentPresenter zoom/rotation methods
- `tests/test_zoom_toolbar.py` — unit tests for ZoomToolBar widget
- `tests/test_zoom_integration.py` — integration tests with real PDFs

**Modified files:**
- `k_pdf/presenters/document_presenter.py` — add `ZoomState`, zoom/rotation/fit_mode methods and signals
- `k_pdf/views/pdf_viewport.py` — add `viewport_resized`, `zoom_at_cursor` signals, `resizeEvent`/`wheelEvent` overrides
- `k_pdf/views/main_window.py` — add `ZoomToolBar`, View menu rotation actions, zoom shortcuts
- `k_pdf/app.py` — wire ZoomToolBar signals to presenter and vice versa
- `pyproject.toml` — add mypy overrides for new modules
- `CLAUDE.md` — update current state

---

### Task 1: ZoomModel (core/zoom_model.py)

**Files:**
- Create: `k_pdf/core/zoom_model.py`
- Create: `tests/test_zoom_model.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_zoom_model.py`:

```python
"""Tests for ZoomState dataclass and FitMode enum."""

from __future__ import annotations

from k_pdf.core.zoom_model import FitMode, ZoomState


class TestFitMode:
    def test_enum_values(self) -> None:
        assert FitMode.NONE.value == "none"
        assert FitMode.PAGE.value == "page"
        assert FitMode.WIDTH.value == "width"

    def test_enum_members(self) -> None:
        assert len(FitMode) == 3


class TestZoomStateConstruction:
    def test_defaults(self) -> None:
        state = ZoomState()
        assert state.zoom == 1.0
        assert state.rotation == 0
        assert state.fit_mode is FitMode.NONE
        assert state.min_zoom == 0.1
        assert state.max_zoom == 32.0

    def test_custom_values(self) -> None:
        state = ZoomState(zoom=2.0, rotation=90, fit_mode=FitMode.PAGE)
        assert state.zoom == 2.0
        assert state.rotation == 90
        assert state.fit_mode is FitMode.PAGE

    def test_is_mutable(self) -> None:
        state = ZoomState()
        state.zoom = 1.5
        state.rotation = 180
        state.fit_mode = FitMode.WIDTH
        assert state.zoom == 1.5
        assert state.rotation == 180
        assert state.fit_mode is FitMode.WIDTH


class TestClampZoom:
    def test_within_range_unchanged(self) -> None:
        state = ZoomState()
        assert state.clamp_zoom(1.0) == 1.0
        assert state.clamp_zoom(5.0) == 5.0

    def test_below_min_clamped(self) -> None:
        state = ZoomState()
        assert state.clamp_zoom(0.05) == 0.1
        assert state.clamp_zoom(0.0) == 0.1
        assert state.clamp_zoom(-1.0) == 0.1

    def test_above_max_clamped(self) -> None:
        state = ZoomState()
        assert state.clamp_zoom(50.0) == 32.0
        assert state.clamp_zoom(100.0) == 32.0

    def test_at_boundaries(self) -> None:
        state = ZoomState()
        assert state.clamp_zoom(0.1) == 0.1
        assert state.clamp_zoom(32.0) == 32.0


class TestNormalizeRotation:
    def test_zero(self) -> None:
        state = ZoomState()
        assert state.normalize_rotation(0) == 0

    def test_valid_multiples(self) -> None:
        state = ZoomState()
        assert state.normalize_rotation(90) == 90
        assert state.normalize_rotation(180) == 180
        assert state.normalize_rotation(270) == 270

    def test_full_rotation_wraps_to_zero(self) -> None:
        state = ZoomState()
        assert state.normalize_rotation(360) == 0

    def test_negative_wraps(self) -> None:
        state = ZoomState()
        assert state.normalize_rotation(-90) == 270
        assert state.normalize_rotation(-180) == 180
        assert state.normalize_rotation(-270) == 90

    def test_large_positive_wraps(self) -> None:
        state = ZoomState()
        assert state.normalize_rotation(450) == 90
        assert state.normalize_rotation(720) == 0

    def test_large_negative_wraps(self) -> None:
        state = ZoomState()
        assert state.normalize_rotation(-360) == 0
        assert state.normalize_rotation(-450) == 270

    def test_non_multiple_of_90_rounds_down(self) -> None:
        state = ZoomState()
        # Non-multiples of 90 snap to nearest lower multiple
        assert state.normalize_rotation(45) == 0
        assert state.normalize_rotation(135) == 90
        assert state.normalize_rotation(200) == 180
        assert state.normalize_rotation(300) == 270
```

- [ ] **Step 2: Run tests — verify RED**

```bash
uv run pytest tests/test_zoom_model.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — all tests fail.

- [ ] **Step 3: Implement ZoomModel**

Create `k_pdf/core/zoom_model.py`:

```python
"""Zoom and rotation state model.

Framework-free data layer for zoom level, rotation angle, and fit mode.
Each DocumentPresenter instance owns one ZoomState.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FitMode(Enum):
    """Page fit mode for automatic zoom calculation."""

    NONE = "none"
    PAGE = "page"
    WIDTH = "width"


@dataclass
class ZoomState:
    """Mutable zoom/rotation state for a single document tab.

    Attributes:
        zoom: Current zoom level (1.0 = 100%).
        rotation: Current rotation in degrees (0, 90, 180, 270).
        fit_mode: Active fit mode for automatic zoom.
        min_zoom: Minimum allowed zoom (10%).
        max_zoom: Maximum allowed zoom (3200%).
    """

    zoom: float = 1.0
    rotation: int = 0
    fit_mode: FitMode = field(default=FitMode.NONE)
    min_zoom: float = 0.1
    max_zoom: float = 32.0

    def clamp_zoom(self, value: float) -> float:
        """Clamp a zoom value to [min_zoom, max_zoom].

        Args:
            value: The zoom value to clamp.

        Returns:
            The clamped zoom value.
        """
        return max(self.min_zoom, min(self.max_zoom, value))

    def normalize_rotation(self, degrees: int) -> int:
        """Normalize rotation to 0, 90, 180, or 270.

        Non-multiples of 90 are rounded down to the nearest multiple.
        Wraps around for values outside [0, 360).

        Args:
            degrees: Rotation in degrees (any integer).

        Returns:
            Normalized rotation: 0, 90, 180, or 270.
        """
        # Round down to nearest multiple of 90, then wrap
        snapped = (degrees // 90) * 90
        return snapped % 360
```

- [ ] **Step 4: Run tests — verify GREEN**

```bash
uv run pytest tests/test_zoom_model.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Lint and type-check**

```bash
uv run ruff check k_pdf/core/zoom_model.py tests/test_zoom_model.py
uv run ruff format k_pdf/core/zoom_model.py tests/test_zoom_model.py
uv run mypy k_pdf/core/zoom_model.py
```

- [ ] **Step 6: Commit**

```
feat(f5): add ZoomState dataclass and FitMode enum

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

---

### Task 2: Extend DocumentPresenter with zoom/rotation methods

**Files:**
- Edit: `k_pdf/presenters/document_presenter.py`
- Create: `tests/test_document_presenter_zoom.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_document_presenter_zoom.py`:

```python
"""Tests for DocumentPresenter zoom, rotation, and fit mode methods."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from k_pdf.core.document_model import DocumentModel, DocumentMetadata, PageInfo
from k_pdf.core.zoom_model import FitMode, ZoomState
from k_pdf.presenters.document_presenter import DocumentPresenter

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_presenter_with_model() -> DocumentPresenter:
    """Create a presenter with a mock document model for zoom testing."""
    presenter = DocumentPresenter()
    # Inject a mock model so set_fit_mode can read page dimensions
    model = MagicMock(spec=DocumentModel)
    model.pages = [
        PageInfo(
            index=0, width=612.0, height=792.0,
            rotation=0, has_text=True, annotation_count=0,
        ),
        PageInfo(
            index=1, width=612.0, height=792.0,
            rotation=0, has_text=True, annotation_count=0,
        ),
    ]
    model.doc_handle = MagicMock()
    presenter._model = model
    return presenter


class TestDocumentPresenterZoom:
    def test_initial_zoom_is_1(self) -> None:
        presenter = DocumentPresenter()
        assert presenter.zoom == 1.0
        presenter.shutdown()

    def test_initial_rotation_is_0(self) -> None:
        presenter = DocumentPresenter()
        assert presenter.rotation == 0
        presenter.shutdown()

    def test_initial_fit_mode_is_none(self) -> None:
        presenter = DocumentPresenter()
        assert presenter.fit_mode is FitMode.NONE
        presenter.shutdown()

    def test_set_zoom_updates_value(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_zoom(2.0)
        assert presenter.zoom == 2.0
        presenter.shutdown()

    def test_set_zoom_clamps_below_min(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_zoom(0.01)
        assert presenter.zoom == 0.1
        presenter.shutdown()

    def test_set_zoom_clamps_above_max(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_zoom(50.0)
        assert presenter.zoom == 32.0
        presenter.shutdown()

    def test_set_zoom_emits_signal(self) -> None:
        presenter = _make_presenter_with_model()
        spy = MagicMock()
        presenter.zoom_changed.connect(spy)
        presenter.set_zoom(1.5)
        spy.assert_called_once_with(1.5)
        presenter.shutdown()

    def test_set_zoom_clears_fit_mode(self) -> None:
        presenter = _make_presenter_with_model()
        presenter._zoom_state.fit_mode = FitMode.PAGE
        presenter.set_zoom(2.0)
        assert presenter.fit_mode is FitMode.NONE
        presenter.shutdown()

    def test_set_zoom_invalidates_cache(self) -> None:
        presenter = _make_presenter_with_model()
        presenter._cache.put(0, MagicMock())
        assert presenter._cache.size() == 1
        presenter.set_zoom(2.0)
        assert presenter._cache.size() == 0
        presenter.shutdown()

    def test_set_zoom_no_signal_when_unchanged(self) -> None:
        presenter = _make_presenter_with_model()
        spy = MagicMock()
        presenter.zoom_changed.connect(spy)
        presenter.set_zoom(1.0)  # Same as default
        spy.assert_not_called()
        presenter.shutdown()


class TestDocumentPresenterRotation:
    def test_set_rotation_updates_value(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_rotation(90)
        assert presenter.rotation == 90
        presenter.shutdown()

    def test_set_rotation_normalizes(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_rotation(450)
        assert presenter.rotation == 90
        presenter.shutdown()

    def test_set_rotation_negative(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_rotation(-90)
        assert presenter.rotation == 270
        presenter.shutdown()

    def test_set_rotation_emits_signal(self) -> None:
        presenter = _make_presenter_with_model()
        spy = MagicMock()
        presenter.rotation_changed.connect(spy)
        presenter.set_rotation(90)
        spy.assert_called_once_with(90)
        presenter.shutdown()

    def test_set_rotation_invalidates_cache(self) -> None:
        presenter = _make_presenter_with_model()
        presenter._cache.put(0, MagicMock())
        assert presenter._cache.size() == 1
        presenter.set_rotation(90)
        assert presenter._cache.size() == 0
        presenter.shutdown()

    def test_set_rotation_no_signal_when_unchanged(self) -> None:
        presenter = _make_presenter_with_model()
        spy = MagicMock()
        presenter.rotation_changed.connect(spy)
        presenter.set_rotation(0)  # Same as default
        spy.assert_not_called()
        presenter.shutdown()

    def test_rotation_wraps_through_360(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_rotation(90)
        presenter.set_rotation(180)
        presenter.set_rotation(270)
        presenter.set_rotation(360)
        assert presenter.rotation == 0
        presenter.shutdown()


class TestDocumentPresenterFitMode:
    def test_set_fit_mode_page(self) -> None:
        presenter = _make_presenter_with_model()
        # Viewport 612x792 with page 612x792 => zoom = 1.0
        presenter.set_fit_mode(FitMode.PAGE, 612.0, 792.0)
        assert presenter.fit_mode is FitMode.PAGE
        assert presenter.zoom == 1.0
        presenter.shutdown()

    def test_set_fit_mode_width(self) -> None:
        presenter = _make_presenter_with_model()
        # Viewport 306 wide with page 612 wide => zoom = 0.5
        presenter.set_fit_mode(FitMode.WIDTH, 306.0, 792.0)
        assert presenter.fit_mode is FitMode.WIDTH
        assert presenter.zoom == 0.5
        presenter.shutdown()

    def test_set_fit_mode_page_smaller_viewport(self) -> None:
        presenter = _make_presenter_with_model()
        # Viewport 300x400 with page 612x792
        # min(300/612, 400/792) = min(0.4902, 0.5050) = 0.4902...
        presenter.set_fit_mode(FitMode.PAGE, 300.0, 400.0)
        assert presenter.fit_mode is FitMode.PAGE
        expected = min(300.0 / 612.0, 400.0 / 792.0)
        assert abs(presenter.zoom - expected) < 0.001
        presenter.shutdown()

    def test_set_fit_mode_preserves_fit_mode(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_fit_mode(FitMode.PAGE, 612.0, 792.0)
        assert presenter.fit_mode is FitMode.PAGE
        # Explicit set_zoom clears it
        presenter.set_zoom(2.0)
        assert presenter.fit_mode is FitMode.NONE
        presenter.shutdown()

    def test_set_fit_mode_emits_zoom_changed(self) -> None:
        presenter = _make_presenter_with_model()
        spy = MagicMock()
        presenter.zoom_changed.connect(spy)
        presenter.set_fit_mode(FitMode.WIDTH, 306.0, 792.0)
        spy.assert_called_once_with(0.5)
        presenter.shutdown()

    def test_set_fit_mode_none_is_noop(self) -> None:
        presenter = _make_presenter_with_model()
        spy = MagicMock()
        presenter.zoom_changed.connect(spy)
        presenter.set_fit_mode(FitMode.NONE, 612.0, 792.0)
        spy.assert_not_called()
        presenter.shutdown()

    def test_set_fit_mode_respects_rotation(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_rotation(90)
        # At 90 degrees, width/height swap: page becomes 792x612
        # FitWidth: viewport_width / page_width = 306 / 792 ~= 0.386
        presenter.set_fit_mode(FitMode.WIDTH, 306.0, 612.0)
        assert presenter.fit_mode is FitMode.WIDTH
        expected = 306.0 / 792.0
        assert abs(presenter.zoom - expected) < 0.001
        presenter.shutdown()

    def test_set_fit_mode_no_model_is_noop(self) -> None:
        presenter = DocumentPresenter()
        spy = MagicMock()
        presenter.zoom_changed.connect(spy)
        presenter.set_fit_mode(FitMode.PAGE, 612.0, 792.0)
        spy.assert_not_called()
        presenter.shutdown()
```

- [ ] **Step 2: Run tests — verify RED**

```bash
uv run pytest tests/test_document_presenter_zoom.py -v
```

Expected: `AttributeError` — `DocumentPresenter` has no `zoom_changed` signal, no `set_zoom` method, etc.

- [ ] **Step 3: Implement DocumentPresenter zoom/rotation extensions**

Edit `k_pdf/presenters/document_presenter.py`:

Add import at top (after existing imports):

```python
from k_pdf.core.zoom_model import FitMode, ZoomState
```

Add new signals to `DocumentPresenter` class (after existing signals):

```python
    zoom_changed = Signal(float)  # emitted after zoom level changes
    rotation_changed = Signal(int)  # emitted after rotation changes
```

Replace the `__init__` method to use `ZoomState` (replace `self._zoom = 1.0` and `self._rotation = 0` with `self._zoom_state`):

```python
    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the presenter with worker thread and page cache."""
        super().__init__(parent)
        self._engine = PdfEngine()
        self._model: DocumentModel | None = None
        self._cache = PageCache()
        self._pending_renders: set[int] = set()
        self._zoom_state = ZoomState()

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
```

Add new properties (after existing `cache` property):

```python
    @property
    def zoom(self) -> float:
        """Return the current zoom level."""
        return self._zoom_state.zoom

    @property
    def rotation(self) -> int:
        """Return the current rotation in degrees."""
        return self._zoom_state.rotation

    @property
    def fit_mode(self) -> FitMode:
        """Return the current fit mode."""
        return self._zoom_state.fit_mode
```

Add new methods (before `shutdown()`):

```python
    def set_zoom(self, zoom: float) -> None:
        """Set the zoom level, clamp, clear fit mode, invalidate cache, re-render.

        Emits zoom_changed if the value actually changed.

        Args:
            zoom: Desired zoom level (1.0 = 100%).
        """
        clamped = self._zoom_state.clamp_zoom(zoom)
        if clamped == self._zoom_state.zoom:
            return
        self._zoom_state.zoom = clamped
        self._zoom_state.fit_mode = FitMode.NONE
        self._cache.invalidate()
        self._pending_renders.clear()
        self.zoom_changed.emit(clamped)

    def set_rotation(self, rotation: int) -> None:
        """Set the rotation, normalize, invalidate cache, re-render.

        Emits rotation_changed if the value actually changed.

        Args:
            rotation: Desired rotation in degrees (any integer).
        """
        normalized = self._zoom_state.normalize_rotation(rotation)
        if normalized == self._zoom_state.rotation:
            return
        self._zoom_state.rotation = normalized
        self._cache.invalidate()
        self._pending_renders.clear()
        self.rotation_changed.emit(normalized)

    def set_fit_mode(
        self, mode: FitMode, viewport_width: float, viewport_height: float
    ) -> None:
        """Set a fit mode and calculate zoom from viewport and page dimensions.

        Emits zoom_changed if the calculated zoom differs from current.
        Does nothing if mode is NONE or no document is loaded.

        Args:
            mode: The fit mode to apply.
            viewport_width: Current viewport width in pixels.
            viewport_height: Current viewport height in pixels.
        """
        if mode is FitMode.NONE or self._model is None or not self._model.pages:
            return

        page = self._model.pages[0]
        # Account for rotation: swap width/height at 90/270 degrees
        if self._zoom_state.rotation in (90, 270):
            page_w = page.height
            page_h = page.width
        else:
            page_w = page.width
            page_h = page.height

        if mode is FitMode.PAGE:
            new_zoom = min(viewport_width / page_w, viewport_height / page_h)
        else:  # FitMode.WIDTH
            new_zoom = viewport_width / page_w

        new_zoom = self._zoom_state.clamp_zoom(new_zoom)
        self._zoom_state.fit_mode = mode
        if new_zoom != self._zoom_state.zoom:
            self._zoom_state.zoom = new_zoom
            self._cache.invalidate()
            self._pending_renders.clear()
            self.zoom_changed.emit(new_zoom)
```

Update `request_pages()` to use `self._zoom_state.zoom` and `self._zoom_state.rotation` instead of `self._zoom` and `self._rotation`:

```python
    def request_pages(self, page_indices: list[int]) -> None:
        """Request rendering for a list of page indices.

        Pages already in the cache are emitted immediately.
        Missing pages are dispatched to the worker thread.
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
                self._model.doc_handle,
                to_render,
                self._zoom_state.zoom,
                self._zoom_state.rotation,
            )
```

- [ ] **Step 4: Run tests — verify GREEN**

```bash
uv run pytest tests/test_document_presenter_zoom.py -v
uv run pytest tests/test_document_presenter.py -v
```

Expected: All new zoom tests pass. All existing presenter tests still pass (no regressions from `_zoom`/`_rotation` removal).

- [ ] **Step 5: Lint and type-check**

```bash
uv run ruff check k_pdf/presenters/document_presenter.py tests/test_document_presenter_zoom.py
uv run ruff format k_pdf/presenters/document_presenter.py tests/test_document_presenter_zoom.py
uv run mypy k_pdf/presenters/document_presenter.py
```

- [ ] **Step 6: Commit**

```
feat(f5): add zoom/rotation/fit-mode methods to DocumentPresenter

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

---

### Task 3: PdfViewport — viewport_resized, wheelEvent zoom, resize recalculation

**Files:**
- Edit: `k_pdf/views/pdf_viewport.py`
- Edit: `tests/test_views.py` (add new tests to `TestPdfViewport`)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_views.py` inside `TestPdfViewport`:

```python
    def test_viewport_resized_signal_exists(self) -> None:
        """Test that viewport_resized signal exists."""
        viewport = PdfViewport()
        spy = MagicMock()
        viewport.viewport_resized.connect(spy)

    def test_zoom_at_cursor_signal_exists(self) -> None:
        """Test that zoom_at_cursor signal exists."""
        viewport = PdfViewport()
        spy = MagicMock()
        viewport.zoom_at_cursor.connect(spy)

    def test_set_document_with_zoom(self) -> None:
        """Test set_document applies zoom to page dimensions."""
        viewport = PdfViewport()
        pages = [
            PageInfo(
                index=0, width=612, height=792,
                rotation=0, has_text=True, annotation_count=0,
            ),
        ]
        viewport.set_document(pages, zoom=2.0)
        assert viewport.state == ViewportState.SUCCESS
        # Scene rect should reflect zoomed page width
        scene_rect = viewport.scene().sceneRect()
        assert scene_rect.width() >= 612 * 2.0

    def test_resize_event_emits_viewport_resized(self, qtbot: object) -> None:
        """Test that resizeEvent emits viewport_resized signal."""
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QResizeEvent

        viewport = PdfViewport()
        spy = MagicMock()
        viewport.viewport_resized.connect(spy)
        viewport.show()
        viewport.resize(800, 600)

        # Force a resize event
        event = QResizeEvent(QSize(800, 600), QSize(400, 300))
        viewport.resizeEvent(event)

        assert spy.call_count >= 1
        width, height = spy.call_args[0]
        assert width > 0
        assert height > 0

    def test_wheel_event_with_ctrl_emits_zoom_at_cursor(self, qtbot: object) -> None:
        """Test that Ctrl+scroll emits zoom_at_cursor signal."""
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QWheelEvent

        viewport = PdfViewport()
        pages = [
            PageInfo(
                index=0, width=612, height=792,
                rotation=0, has_text=True, annotation_count=0,
            ),
        ]
        viewport.set_document(pages)
        viewport.show()
        viewport.resize(800, 600)

        spy = MagicMock()
        viewport.zoom_at_cursor.connect(spy)

        # Simulate Ctrl+scroll up
        event = QWheelEvent(
            QPointF(400, 300),           # pos
            QPointF(400, 300),           # globalPos
            QPoint(0, 120),              # pixelDelta
            QPoint(0, 120),              # angleDelta
            Qt.MouseButton.NoButton,     # buttons
            Qt.KeyboardModifier.ControlModifier,  # modifiers
            Qt.ScrollPhase.NoScrollPhase,
            False,                       # inverted
        )
        viewport.wheelEvent(event)
        spy.assert_called_once()
        step, _pos = spy.call_args[0]
        assert step > 0  # scroll up = zoom in
```

- [ ] **Step 2: Run tests — verify RED**

```bash
uv run pytest tests/test_views.py::TestPdfViewport::test_viewport_resized_signal_exists -v
uv run pytest tests/test_views.py::TestPdfViewport::test_zoom_at_cursor_signal_exists -v
```

Expected: `AttributeError` — `PdfViewport` has no `viewport_resized` or `zoom_at_cursor` signals.

- [ ] **Step 3: Implement PdfViewport changes**

Edit `k_pdf/views/pdf_viewport.py`:

Add imports at top (after existing imports):

```python
from typing import override

from PySide6.QtCore import QPointF
from PySide6.QtGui import QResizeEvent, QWheelEvent
```

Add new signals to `PdfViewport` class (after existing signals):

```python
    viewport_resized = Signal(float, float)  # (width, height)
    zoom_at_cursor = Signal(float, QPointF)  # (step_direction, scene_pos)
```

Add `resizeEvent` override (after `scroll_to_page` method):

```python
    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Emit viewport_resized on resize for fit mode recalculation."""
        super().resizeEvent(event)
        vp = self.viewport()
        self.viewport_resized.emit(float(vp.width()), float(vp.height()))

    @override
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle Ctrl+scroll for zoom, delegate normal scroll to parent."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            event.accept()
            angle = event.angleDelta().y()
            if angle == 0:
                return
            # +0.1 per notch (120 units = 1 notch)
            step = 0.1 * (angle / 120.0)
            scene_pos = self.mapToScene(event.position().toPoint())
            self.zoom_at_cursor.emit(step, scene_pos)
        else:
            super().wheelEvent(event)
```

- [ ] **Step 4: Run tests — verify GREEN**

```bash
uv run pytest tests/test_views.py -v
```

Expected: All tests pass including the new ones. Existing viewport tests unaffected.

- [ ] **Step 5: Lint and type-check**

```bash
uv run ruff check k_pdf/views/pdf_viewport.py
uv run ruff format k_pdf/views/pdf_viewport.py
uv run mypy k_pdf/views/pdf_viewport.py
```

- [ ] **Step 6: Commit**

```
feat(f5): add viewport_resized and zoom_at_cursor signals to PdfViewport

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

---

### Task 4: ZoomToolBar view (views/zoom_toolbar.py)

**Files:**
- Create: `k_pdf/views/zoom_toolbar.py`
- Create: `tests/test_zoom_toolbar.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_zoom_toolbar.py`:

```python
"""Tests for ZoomToolBar widget."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from k_pdf.core.zoom_model import FitMode
from k_pdf.views.zoom_toolbar import ZoomToolBar

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestZoomToolBarConstruction:
    def test_creates_without_error(self) -> None:
        toolbar = ZoomToolBar()
        assert toolbar is not None

    def test_has_zoom_changed_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)

    def test_has_fit_page_requested_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.fit_page_requested.connect(spy)

    def test_has_fit_width_requested_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.fit_width_requested.connect(spy)

    def test_has_rotate_cw_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.rotate_cw_requested.connect(spy)

    def test_has_rotate_ccw_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.rotate_ccw_requested.connect(spy)


class TestZoomToolBarSlider:
    def test_slider_emits_zoom_changed(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        # Simulate slider move (slider range 10–3200 representing 10%–3200%)
        toolbar._slider.setValue(200)
        spy.assert_called()
        zoom_val = spy.call_args[0][0]
        assert abs(zoom_val - 2.0) < 0.01

    def test_set_zoom_updates_slider_without_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        toolbar.set_zoom(1.5)
        # set_zoom should NOT re-emit zoom_changed
        spy.assert_not_called()
        # Slider should reflect the new value
        assert toolbar._slider.value() == 150

    def test_set_zoom_updates_percentage_text(self) -> None:
        toolbar = ZoomToolBar()
        toolbar.set_zoom(1.5)
        assert "150" in toolbar._percent_input.text()


class TestZoomToolBarPercentageInput:
    def test_valid_percentage_emits_zoom_changed(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        toolbar._percent_input.setText("200")
        toolbar._percent_input.editingFinished.emit()
        spy.assert_called()
        assert abs(spy.call_args[0][0] - 2.0) < 0.01

    def test_invalid_percentage_ignored(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        toolbar._percent_input.setText("abc")
        toolbar._percent_input.editingFinished.emit()
        spy.assert_not_called()

    def test_out_of_range_percentage_clamped(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        toolbar._percent_input.setText("5000")
        toolbar._percent_input.editingFinished.emit()
        spy.assert_called()
        assert spy.call_args[0][0] == 32.0  # 3200% max


class TestZoomToolBarPresetDropdown:
    def test_fit_page_emits_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.fit_page_requested.connect(spy)
        # Find "Fit Page" index in dropdown
        idx = -1
        for i in range(toolbar._preset_combo.count()):
            if "Fit Page" in toolbar._preset_combo.itemText(i):
                idx = i
                break
        assert idx >= 0
        toolbar._preset_combo.setCurrentIndex(idx)
        spy.assert_called_once()

    def test_fit_width_emits_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.fit_width_requested.connect(spy)
        idx = -1
        for i in range(toolbar._preset_combo.count()):
            if "Fit Width" in toolbar._preset_combo.itemText(i):
                idx = i
                break
        assert idx >= 0
        toolbar._preset_combo.setCurrentIndex(idx)
        spy.assert_called_once()

    def test_numeric_preset_emits_zoom_changed(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        # Find "200%" preset
        idx = -1
        for i in range(toolbar._preset_combo.count()):
            if "200%" in toolbar._preset_combo.itemText(i):
                idx = i
                break
        assert idx >= 0
        toolbar._preset_combo.setCurrentIndex(idx)
        spy.assert_called()
        assert abs(spy.call_args[0][0] - 2.0) < 0.01

    def test_actual_size_preset(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        idx = -1
        for i in range(toolbar._preset_combo.count()):
            if "100%" in toolbar._preset_combo.itemText(i):
                idx = i
                break
        assert idx >= 0
        toolbar._preset_combo.setCurrentIndex(idx)
        spy.assert_called()
        assert abs(spy.call_args[0][0] - 1.0) < 0.01


class TestZoomToolBarRotation:
    def test_rotate_cw_emits(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.rotate_cw_requested.connect(spy)
        toolbar._rotate_cw_btn.click()
        spy.assert_called_once()

    def test_rotate_ccw_emits(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.rotate_ccw_requested.connect(spy)
        toolbar._rotate_ccw_btn.click()
        spy.assert_called_once()


class TestZoomToolBarZoomButtons:
    def test_zoom_in_button_emits(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        toolbar.set_zoom(1.0)  # Reset to known state
        toolbar._zoom_in_btn.click()
        spy.assert_called()
        # Should zoom in by some increment
        assert spy.call_args[0][0] > 1.0

    def test_zoom_out_button_emits(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        toolbar.set_zoom(1.0)
        toolbar._zoom_out_btn.click()
        spy.assert_called()
        assert spy.call_args[0][0] < 1.0


class TestZoomToolBarSetFitMode:
    def test_set_fit_mode_page(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.fit_page_requested.connect(spy)
        toolbar.set_fit_mode(FitMode.PAGE)
        # Should update combo box without re-emitting signal
        spy.assert_not_called()

    def test_set_fit_mode_width(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.fit_width_requested.connect(spy)
        toolbar.set_fit_mode(FitMode.WIDTH)
        spy.assert_not_called()

    def test_set_fit_mode_none(self) -> None:
        toolbar = ZoomToolBar()
        toolbar.set_fit_mode(FitMode.NONE)
        # Should not select a fit preset
        text = toolbar._preset_combo.currentText()
        assert "Fit" not in text
```

- [ ] **Step 2: Run tests — verify RED**

```bash
uv run pytest tests/test_zoom_toolbar.py -v
```

Expected: `ModuleNotFoundError` — `k_pdf.views.zoom_toolbar` does not exist.

- [ ] **Step 3: Implement ZoomToolBar**

Create `k_pdf/views/zoom_toolbar.py`:

```python
"""Zoom toolbar — slider, percentage input, presets, and rotation buttons.

Layout: [Rotate CCW] [Rotate CW] | [Zoom Out] [Slider] [Percentage] [Zoom In] | [Presets]
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QLineEdit,
    QPushButton,
    QSlider,
    QToolBar,
    QWidget,
)

from k_pdf.core.zoom_model import FitMode

logger = logging.getLogger("k_pdf.views.zoom_toolbar")

# Slider range: 10 to 3200 (representing 10% to 3200%)
_SLIDER_MIN = 10
_SLIDER_MAX = 3200

# Zoom step for +/- buttons and Ctrl+scroll
_ZOOM_STEP = 0.1

# Preset items: (display_text, action_type, value)
# action_type: "fit_page", "fit_width", "zoom"
_PRESETS: list[tuple[str, str, float]] = [
    ("--", "none", 0.0),
    ("Fit Page", "fit_page", 0.0),
    ("Fit Width", "fit_width", 0.0),
    ("Actual Size (100%)", "zoom", 1.0),
    ("50%", "zoom", 0.5),
    ("75%", "zoom", 0.75),
    ("150%", "zoom", 1.5),
    ("200%", "zoom", 2.0),
]


class ZoomToolBar(QToolBar):
    """Toolbar with zoom and rotation controls."""

    zoom_changed = Signal(float)
    fit_page_requested = Signal()
    fit_width_requested = Signal()
    rotate_cw_requested = Signal()
    rotate_ccw_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the zoom toolbar with all controls."""
        super().__init__("Zoom", parent)
        self.setObjectName("zoom_toolbar")
        self.setMovable(False)

        self._updating = False  # Guard against signal loops

        # --- Rotation buttons ---
        self._rotate_ccw_btn = QPushButton("Rotate CCW")
        self._rotate_ccw_btn.setToolTip("Rotate Counter-Clockwise (Ctrl+Shift+R)")
        self._rotate_ccw_btn.clicked.connect(self.rotate_ccw_requested.emit)
        self.addWidget(self._rotate_ccw_btn)

        self._rotate_cw_btn = QPushButton("Rotate CW")
        self._rotate_cw_btn.setToolTip("Rotate Clockwise (Ctrl+R)")
        self._rotate_cw_btn.clicked.connect(self.rotate_cw_requested.emit)
        self.addWidget(self._rotate_cw_btn)

        self.addSeparator()

        # --- Zoom out button ---
        self._zoom_out_btn = QPushButton("-")
        self._zoom_out_btn.setToolTip("Zoom Out (Ctrl+-)")
        self._zoom_out_btn.setFixedWidth(30)
        self._zoom_out_btn.clicked.connect(self._on_zoom_out)
        self.addWidget(self._zoom_out_btn)

        # --- Zoom slider ---
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(_SLIDER_MIN, _SLIDER_MAX)
        self._slider.setValue(100)
        self._slider.setFixedWidth(150)
        self._slider.setToolTip("Zoom level")
        self._slider.valueChanged.connect(self._on_slider_changed)
        self.addWidget(self._slider)

        # --- Percentage input ---
        self._percent_input = QLineEdit("100%")
        self._percent_input.setFixedWidth(60)
        self._percent_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._percent_input.setToolTip("Zoom percentage (10%–3200%)")
        self._percent_input.editingFinished.connect(self._on_percent_edited)
        self.addWidget(self._percent_input)

        # --- Zoom in button ---
        self._zoom_in_btn = QPushButton("+")
        self._zoom_in_btn.setToolTip("Zoom In (Ctrl+=)")
        self._zoom_in_btn.setFixedWidth(30)
        self._zoom_in_btn.clicked.connect(self._on_zoom_in)
        self.addWidget(self._zoom_in_btn)

        self.addSeparator()

        # --- Preset dropdown ---
        self._preset_combo = QComboBox()
        self._preset_combo.setToolTip("Zoom presets")
        for text, _, _ in _PRESETS:
            self._preset_combo.addItem(text)
        self._preset_combo.setCurrentIndex(0)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        self.addWidget(self._preset_combo)

        # Track current zoom for +/- button calculations
        self._current_zoom = 1.0

    def set_zoom(self, zoom: float) -> None:
        """Update slider and percentage display without re-emitting signals.

        Args:
            zoom: The zoom level (1.0 = 100%).
        """
        self._updating = True
        self._current_zoom = zoom
        self._slider.setValue(int(zoom * 100))
        self._percent_input.setText(f"{int(zoom * 100)}%")
        self._updating = False

    def set_rotation(self, rotation: int) -> None:
        """Update rotation display if shown.

        Args:
            rotation: Rotation in degrees (0, 90, 180, 270).
        """
        # Rotation state is visual only — buttons always emit signals
        # No persistent display to update in current design

    def set_fit_mode(self, mode: FitMode) -> None:
        """Update dropdown to reflect active fit mode without re-emitting.

        Args:
            mode: The active fit mode.
        """
        self._updating = True
        if mode is FitMode.PAGE:
            for i, (text, action, _) in enumerate(_PRESETS):
                if action == "fit_page":
                    self._preset_combo.setCurrentIndex(i)
                    break
        elif mode is FitMode.WIDTH:
            for i, (text, action, _) in enumerate(_PRESETS):
                if action == "fit_width":
                    self._preset_combo.setCurrentIndex(i)
                    break
        else:
            self._preset_combo.setCurrentIndex(0)  # "--" (no preset)
        self._updating = False

    # --- Internal signal handlers ---

    def _on_slider_changed(self, value: int) -> None:
        """Handle slider value change."""
        if self._updating:
            return
        zoom = value / 100.0
        self._current_zoom = zoom
        self._updating = True
        self._percent_input.setText(f"{value}%")
        self._updating = False
        self.zoom_changed.emit(zoom)

    def _on_percent_edited(self) -> None:
        """Handle percentage input editing finished."""
        if self._updating:
            return
        text = self._percent_input.text().strip().rstrip("%")
        try:
            percent = float(text)
        except ValueError:
            # Restore current value on invalid input
            self._percent_input.setText(f"{int(self._current_zoom * 100)}%")
            return

        zoom = percent / 100.0
        # Clamp to valid range
        zoom = max(0.1, min(32.0, zoom))
        self._current_zoom = zoom

        self._updating = True
        self._slider.setValue(int(zoom * 100))
        self._percent_input.setText(f"{int(zoom * 100)}%")
        self._updating = False
        self.zoom_changed.emit(zoom)

    def _on_preset_selected(self, index: int) -> None:
        """Handle preset dropdown selection."""
        if self._updating or index < 0 or index >= len(_PRESETS):
            return

        _, action, value = _PRESETS[index]
        if action == "fit_page":
            self.fit_page_requested.emit()
        elif action == "fit_width":
            self.fit_width_requested.emit()
        elif action == "zoom" and value > 0:
            self._current_zoom = value
            self._updating = True
            self._slider.setValue(int(value * 100))
            self._percent_input.setText(f"{int(value * 100)}%")
            self._updating = False
            self.zoom_changed.emit(value)

    def _on_zoom_in(self) -> None:
        """Zoom in by one step."""
        new_zoom = min(32.0, self._current_zoom + _ZOOM_STEP)
        self._current_zoom = new_zoom
        self._updating = True
        self._slider.setValue(int(new_zoom * 100))
        self._percent_input.setText(f"{int(new_zoom * 100)}%")
        self._updating = False
        self.zoom_changed.emit(new_zoom)

    def _on_zoom_out(self) -> None:
        """Zoom out by one step."""
        new_zoom = max(0.1, self._current_zoom - _ZOOM_STEP)
        self._current_zoom = new_zoom
        self._updating = True
        self._slider.setValue(int(new_zoom * 100))
        self._percent_input.setText(f"{int(new_zoom * 100)}%")
        self._updating = False
        self.zoom_changed.emit(new_zoom)
```

- [ ] **Step 4: Run tests — verify GREEN**

```bash
uv run pytest tests/test_zoom_toolbar.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Add mypy override for zoom_toolbar**

Edit `pyproject.toml` — add a new `[[tool.mypy.overrides]]` block:

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.views.zoom_toolbar"]
disable_error_code = ["misc"]
```

- [ ] **Step 6: Lint and type-check**

```bash
uv run ruff check k_pdf/views/zoom_toolbar.py tests/test_zoom_toolbar.py
uv run ruff format k_pdf/views/zoom_toolbar.py tests/test_zoom_toolbar.py
uv run mypy k_pdf/views/zoom_toolbar.py
```

- [ ] **Step 7: Commit**

```
feat(f5): add ZoomToolBar with slider, percentage input, presets, rotation buttons

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

---

### Task 5: Add ZoomToolBar + rotation/zoom actions to MainWindow

**Files:**
- Edit: `k_pdf/views/main_window.py`
- Edit: `tests/test_views.py` (add new tests to `TestMainWindow`)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_views.py` inside `TestMainWindow`:

```python
    def test_zoom_toolbar_exists(self) -> None:
        """Test that MainWindow has a zoom toolbar."""
        from k_pdf.views.main_window import MainWindow
        from k_pdf.views.zoom_toolbar import ZoomToolBar

        window = MainWindow()
        assert isinstance(window.zoom_toolbar, ZoomToolBar)

    def test_view_menu_has_rotate_cw(self) -> None:
        """Test View menu has Rotate Clockwise action with Ctrl+R."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        menu_bar = window.menuBar()
        view_menu = None
        for action in menu_bar.actions():
            if action.text() == "&View":
                view_menu = action.menu()
                break
        assert view_menu is not None
        rotate_cw = None
        for action in view_menu.actions():
            if "Clockwise" in action.text() and "Counter" not in action.text():
                rotate_cw = action
                break
        assert rotate_cw is not None
        assert rotate_cw.shortcut().toString() == "Ctrl+R"

    def test_view_menu_has_rotate_ccw(self) -> None:
        """Test View menu has Rotate Counter-Clockwise action with Ctrl+Shift+R."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        menu_bar = window.menuBar()
        view_menu = None
        for action in menu_bar.actions():
            if action.text() == "&View":
                view_menu = action.menu()
                break
        assert view_menu is not None
        rotate_ccw = None
        for action in view_menu.actions():
            if "Counter" in action.text():
                rotate_ccw = action
                break
        assert rotate_ccw is not None
        assert rotate_ccw.shortcut().toString() == "Ctrl+Shift+R"

    def test_zoom_in_action_signal(self) -> None:
        """Test that Ctrl+= zoom in action exists."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert hasattr(window, "zoom_in_triggered")
        spy = MagicMock()
        window.zoom_in_triggered.connect(spy)

    def test_zoom_out_action_signal(self) -> None:
        """Test that Ctrl+- zoom out action exists."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert hasattr(window, "zoom_out_triggered")
        spy = MagicMock()
        window.zoom_out_triggered.connect(spy)

    def test_zoom_reset_action_signal(self) -> None:
        """Test that Ctrl+0 reset zoom action exists."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert hasattr(window, "zoom_reset_triggered")
        spy = MagicMock()
        window.zoom_reset_triggered.connect(spy)

    def test_rotate_cw_action_signal(self) -> None:
        """Test that rotate CW menu action exists as a signal."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert hasattr(window, "rotate_cw_triggered")
        spy = MagicMock()
        window.rotate_cw_triggered.connect(spy)

    def test_rotate_ccw_action_signal(self) -> None:
        """Test that rotate CCW menu action exists as a signal."""
        from k_pdf.views.main_window import MainWindow

        window = MainWindow()
        assert hasattr(window, "rotate_ccw_triggered")
        spy = MagicMock()
        window.rotate_ccw_triggered.connect(spy)
```

- [ ] **Step 2: Run tests — verify RED**

```bash
uv run pytest tests/test_views.py::TestMainWindow::test_zoom_toolbar_exists -v
```

Expected: `AttributeError` — `MainWindow` has no `zoom_toolbar` property.

- [ ] **Step 3: Implement MainWindow changes**

Edit `k_pdf/views/main_window.py`:

Add import at top:

```python
from k_pdf.views.zoom_toolbar import ZoomToolBar
```

Add new signals to `MainWindow` class (after existing signals):

```python
    zoom_in_triggered = Signal()
    zoom_out_triggered = Signal()
    zoom_reset_triggered = Signal()
    rotate_cw_triggered = Signal()
    rotate_ccw_triggered = Signal()
```

In `__init__`, add the zoom toolbar (after status bar setup, before menus):

```python
        # Zoom toolbar
        self._zoom_toolbar = ZoomToolBar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._zoom_toolbar)
```

Add property (after `search_bar` property):

```python
    @property
    def zoom_toolbar(self) -> ZoomToolBar:
        """Return the zoom toolbar widget."""
        return self._zoom_toolbar
```

Extend `_setup_menus` — add to the View menu section (after `toggle_nav` lines):

```python
        view_menu.addSeparator()

        rotate_cw_action = QAction("Rotate &Clockwise", self)
        rotate_cw_action.setShortcut(QKeySequence("Ctrl+R"))
        rotate_cw_action.setToolTip("Rotate page 90 degrees clockwise")
        rotate_cw_action.triggered.connect(self.rotate_cw_triggered.emit)
        view_menu.addAction(rotate_cw_action)

        rotate_ccw_action = QAction("Rotate C&ounter-Clockwise", self)
        rotate_ccw_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        rotate_ccw_action.setToolTip("Rotate page 90 degrees counter-clockwise")
        rotate_ccw_action.triggered.connect(self.rotate_ccw_triggered.emit)
        view_menu.addAction(rotate_ccw_action)

        view_menu.addSeparator()

        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut(QKeySequence("Ctrl+="))
        zoom_in_action.setToolTip("Zoom in")
        zoom_in_action.triggered.connect(self.zoom_in_triggered.emit)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.setToolTip("Zoom out")
        zoom_out_action.triggered.connect(self.zoom_out_triggered.emit)
        view_menu.addAction(zoom_out_action)

        zoom_reset_action = QAction("&Reset Zoom", self)
        zoom_reset_action.setShortcut(QKeySequence("Ctrl+0"))
        zoom_reset_action.setToolTip("Reset zoom to 100%")
        zoom_reset_action.triggered.connect(self.zoom_reset_triggered.emit)
        view_menu.addAction(zoom_reset_action)
```

- [ ] **Step 4: Run tests — verify GREEN**

```bash
uv run pytest tests/test_views.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Lint and type-check**

```bash
uv run ruff check k_pdf/views/main_window.py
uv run ruff format k_pdf/views/main_window.py
uv run mypy k_pdf/views/main_window.py
```

- [ ] **Step 6: Commit**

```
feat(f5): add ZoomToolBar and zoom/rotation actions to MainWindow

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

---

### Task 6: Wire ZoomToolBar in KPdfApp

**Files:**
- Edit: `k_pdf/app.py`
- Edit: `tests/test_views.py` (add integration tests to `TestKPdfAppIntegration`)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_views.py` inside `TestKPdfAppIntegration`:

```python
    def test_app_has_zoom_toolbar(self) -> None:
        """Test that KPdfApp's window has a zoom toolbar."""
        from k_pdf.views.zoom_toolbar import ZoomToolBar

        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert isinstance(kpdf.window.zoom_toolbar, ZoomToolBar)
        kpdf.shutdown()

    def test_zoom_toolbar_zoom_routes_to_presenter(self) -> None:
        """Test that toolbar zoom_changed reaches the active presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_presenter = MagicMock()
        mock_presenter.zoom = 1.0
        mock_presenter.rotation = 0
        mock_presenter.fit_mode = FitMode.NONE
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )
        kpdf.window.zoom_toolbar.zoom_changed.emit(2.0)
        mock_presenter.set_zoom.assert_called_once_with(2.0)
        kpdf.shutdown()

    def test_zoom_toolbar_rotate_cw_routes(self) -> None:
        """Test that toolbar rotate_cw_requested reaches the active presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_presenter = MagicMock()
        mock_presenter.rotation = 0
        mock_presenter.zoom = 1.0
        mock_presenter.fit_mode = FitMode.NONE
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )
        kpdf.window.zoom_toolbar.rotate_cw_requested.emit()
        mock_presenter.set_rotation.assert_called_once_with(90)
        kpdf.shutdown()

    def test_zoom_toolbar_rotate_ccw_routes(self) -> None:
        """Test that toolbar rotate_ccw_requested reaches the active presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_presenter = MagicMock()
        mock_presenter.rotation = 0
        mock_presenter.zoom = 1.0
        mock_presenter.fit_mode = FitMode.NONE
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )
        kpdf.window.zoom_toolbar.rotate_ccw_requested.emit()
        mock_presenter.set_rotation.assert_called_once_with(-90)
        kpdf.shutdown()

    def test_zoom_in_shortcut_routes(self) -> None:
        """Test that Ctrl+= zoom in routes to presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_presenter = MagicMock()
        mock_presenter.zoom = 1.0
        mock_presenter.rotation = 0
        mock_presenter.fit_mode = FitMode.NONE
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )
        kpdf.window.zoom_in_triggered.emit()
        mock_presenter.set_zoom.assert_called_once_with(1.1)
        kpdf.shutdown()

    def test_zoom_out_shortcut_routes(self) -> None:
        """Test that Ctrl+- zoom out routes to presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_presenter = MagicMock()
        mock_presenter.zoom = 1.0
        mock_presenter.rotation = 0
        mock_presenter.fit_mode = FitMode.NONE
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )
        kpdf.window.zoom_out_triggered.emit()
        mock_presenter.set_zoom.assert_called_once_with(0.9)
        kpdf.shutdown()

    def test_zoom_reset_shortcut_routes(self) -> None:
        """Test that Ctrl+0 reset zoom routes to presenter."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_presenter = MagicMock()
        mock_presenter.zoom = 2.0
        mock_presenter.rotation = 0
        mock_presenter.fit_mode = FitMode.NONE
        kpdf.tab_manager.get_active_presenter = MagicMock(  # type: ignore[method-assign]
            return_value=mock_presenter,
        )
        kpdf.window.zoom_reset_triggered.emit()
        mock_presenter.set_zoom.assert_called_once_with(1.0)
        kpdf.shutdown()
```

Add import at the top of `tests/test_views.py`:

```python
from k_pdf.core.zoom_model import FitMode
```

- [ ] **Step 2: Run tests — verify RED**

```bash
uv run pytest tests/test_views.py::TestKPdfAppIntegration::test_zoom_toolbar_zoom_routes_to_presenter -v
```

Expected: `AssertionError` — `set_zoom` not called because wiring does not exist yet.

- [ ] **Step 3: Implement KPdfApp wiring**

Edit `k_pdf/app.py`:

Add import at top:

```python
from PySide6.QtCore import QPointF

from k_pdf.core.zoom_model import FitMode
```

Add to `_connect_signals()` method (after existing search wiring):

```python
        # ZoomToolBar → presenter
        zoom_tb = self._window.zoom_toolbar
        zoom_tb.zoom_changed.connect(self._on_toolbar_zoom_changed)
        zoom_tb.fit_page_requested.connect(self._on_fit_page_requested)
        zoom_tb.fit_width_requested.connect(self._on_fit_width_requested)
        zoom_tb.rotate_cw_requested.connect(self._on_rotate_cw)
        zoom_tb.rotate_ccw_requested.connect(self._on_rotate_ccw)

        # MainWindow zoom/rotation shortcuts → presenter
        self._window.zoom_in_triggered.connect(self._on_zoom_in)
        self._window.zoom_out_triggered.connect(self._on_zoom_out)
        self._window.zoom_reset_triggered.connect(self._on_zoom_reset)
        self._window.rotate_cw_triggered.connect(self._on_rotate_cw)
        self._window.rotate_ccw_triggered.connect(self._on_rotate_ccw)

        # Tab switch → push zoom state to toolbar
        self._tab_manager.tab_switched.connect(self._on_tab_switched_zoom)
```

Add handler methods (before `shutdown()` method):

```python
    def _on_toolbar_zoom_changed(self, zoom: float) -> None:
        """Route toolbar zoom change to active presenter."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_zoom(zoom)

    def _on_fit_page_requested(self) -> None:
        """Route Fit Page request to active presenter."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and viewport is not None:
            vp = viewport.viewport()
            presenter.set_fit_mode(FitMode.PAGE, float(vp.width()), float(vp.height()))

    def _on_fit_width_requested(self) -> None:
        """Route Fit Width request to active presenter."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and viewport is not None:
            vp = viewport.viewport()
            presenter.set_fit_mode(FitMode.WIDTH, float(vp.width()), float(vp.height()))

    def _on_rotate_cw(self) -> None:
        """Route rotate clockwise to active presenter."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_rotation(presenter.rotation + 90)

    def _on_rotate_ccw(self) -> None:
        """Route rotate counter-clockwise to active presenter."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_rotation(presenter.rotation - 90)

    def _on_zoom_in(self) -> None:
        """Zoom in by 10% via keyboard shortcut."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_zoom(presenter.zoom + 0.1)

    def _on_zoom_out(self) -> None:
        """Zoom out by 10% via keyboard shortcut."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_zoom(presenter.zoom - 0.1)

    def _on_zoom_reset(self) -> None:
        """Reset zoom to 100% via keyboard shortcut."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_zoom(1.0)

    def _on_viewport_resized(self, width: float, height: float) -> None:
        """Recalculate fit mode zoom on viewport resize."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None and presenter.fit_mode is not FitMode.NONE:
            presenter.set_fit_mode(presenter.fit_mode, width, height)

    def _on_zoom_at_cursor(self, step: float, _scene_pos: QPointF) -> None:
        """Handle Ctrl+scroll zoom from viewport."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            presenter.set_zoom(presenter.zoom + step)

    def _on_presenter_zoom_changed(self, zoom: float) -> None:
        """Push zoom changes from presenter back to toolbar."""
        self._window.zoom_toolbar.set_zoom(zoom)
        self._window._zoom_label.setText(f"{int(zoom * 100)}%")

    def _on_presenter_rotation_changed(self, rotation: int) -> None:
        """Push rotation changes from presenter back to toolbar."""
        self._window.zoom_toolbar.set_rotation(rotation)

    def _on_tab_switched_zoom(self, session_id: str) -> None:
        """Push the new tab's zoom/rotation/fit_mode state to toolbar."""
        presenter = self._tab_manager.get_active_presenter()
        if presenter is not None:
            self._window.zoom_toolbar.set_zoom(presenter.zoom)
            self._window.zoom_toolbar.set_rotation(presenter.rotation)
            self._window.zoom_toolbar.set_fit_mode(presenter.fit_mode)
            self._window._zoom_label.setText(f"{int(presenter.zoom * 100)}%")
```

Update the `_on_search_highlight_page` method to pass the active zoom:

```python
    def _on_search_highlight_page(
        self,
        page_index: int,
        rects: list[tuple[float, float, float, float]],
    ) -> None:
        """Route highlight overlay to the active viewport."""
        viewport = self._tab_manager.get_active_viewport()
        presenter = self._tab_manager.get_active_presenter()
        if viewport is not None:
            zoom = presenter.zoom if presenter is not None else 1.0
            viewport.add_search_highlights(page_index, rects, zoom=zoom)
```

Wire per-tab presenter signals and viewport signals in `TabManager.open_file`. This requires modifying `TabManager` to connect viewport and presenter zoom signals. Since `KPdfApp` needs to connect per-tab signals, the wiring happens in `_connect_signals`. We need a hook for when a new tab is created. Extend the existing `document_ready` signal connection in `_connect_signals`:

Add to `_connect_signals()`:

```python
        # When a new tab's document is ready, wire its zoom signals
        self._tab_manager.document_ready.connect(self._on_document_ready_zoom)
```

Add handler:

```python
    def _on_document_ready_zoom(self, session_id: str, model: object) -> None:
        """Wire zoom/rotation signals for a newly loaded document tab."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None:
            presenter.zoom_changed.connect(self._on_presenter_zoom_changed)
            presenter.rotation_changed.connect(self._on_presenter_rotation_changed)
        if viewport is not None:
            viewport.viewport_resized.connect(self._on_viewport_resized)
            viewport.zoom_at_cursor.connect(self._on_zoom_at_cursor)
```

- [ ] **Step 4: Run tests — verify GREEN**

```bash
uv run pytest tests/test_views.py -v
```

Expected: All tests pass including the new wiring tests.

- [ ] **Step 5: Lint and type-check**

```bash
uv run ruff check k_pdf/app.py
uv run ruff format k_pdf/app.py
uv run mypy k_pdf/app.py
```

- [ ] **Step 6: Commit**

```
feat(f5): wire ZoomToolBar signals and zoom/rotation routing in KPdfApp

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

---

### Task 7: Integration tests

**Files:**
- Create: `tests/test_zoom_integration.py`

- [ ] **Step 1: Write integration tests**

Create `tests/test_zoom_integration.py`:

```python
"""Integration tests for zoom, rotation, and fit modes with real PDFs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.core.zoom_model import FitMode

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestZoomIntegration:
    def _open_pdf(self, kpdf: KPdfApp, pdf_path: Path, qtbot: object) -> None:
        """Helper to open a PDF and wait for it to load."""
        spy = MagicMock()
        kpdf.tab_manager.document_ready.connect(spy)
        kpdf.tab_manager.open_file(pdf_path)

        def check_ready() -> None:
            assert spy.call_count >= 1

        qtbot.waitUntil(check_ready, timeout=5000)

    def test_zoom_in_out(self, valid_pdf: Path, qtbot: object) -> None:
        """Test that zoom in/out changes presenter zoom and updates toolbar."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None
        assert presenter.zoom == 1.0

        # Zoom in
        kpdf.window.zoom_in_triggered.emit()
        assert abs(presenter.zoom - 1.1) < 0.01

        # Zoom out
        kpdf.window.zoom_out_triggered.emit()
        assert abs(presenter.zoom - 1.0) < 0.01

        kpdf.shutdown()

    def test_reset_zoom(self, valid_pdf: Path, qtbot: object) -> None:
        """Test that Ctrl+0 resets zoom to 100%."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None
        presenter.set_zoom(2.0)
        assert presenter.zoom == 2.0

        kpdf.window.zoom_reset_triggered.emit()
        assert presenter.zoom == 1.0

        kpdf.shutdown()

    def test_fit_page(self, valid_pdf: Path, qtbot: object) -> None:
        """Test Fit Page mode calculates zoom from viewport size."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None

        # Manually trigger fit page with known dimensions
        presenter.set_fit_mode(FitMode.PAGE, 306.0, 396.0)
        assert presenter.fit_mode is FitMode.PAGE
        # Page is 612x792, viewport 306x396 => min(0.5, 0.5) = 0.5
        assert abs(presenter.zoom - 0.5) < 0.01

        kpdf.shutdown()

    def test_fit_width(self, valid_pdf: Path, qtbot: object) -> None:
        """Test Fit Width mode calculates zoom from viewport width."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None

        presenter.set_fit_mode(FitMode.WIDTH, 306.0, 1000.0)
        assert presenter.fit_mode is FitMode.WIDTH
        assert abs(presenter.zoom - 0.5) < 0.01

        kpdf.shutdown()

    def test_fit_mode_cleared_on_manual_zoom(self, valid_pdf: Path, qtbot: object) -> None:
        """Test that manual zoom clears fit mode to NONE."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None

        presenter.set_fit_mode(FitMode.PAGE, 612.0, 792.0)
        assert presenter.fit_mode is FitMode.PAGE

        presenter.set_zoom(2.0)
        assert presenter.fit_mode is FitMode.NONE

        kpdf.shutdown()

    def test_rotation_cw_ccw(self, valid_pdf: Path, qtbot: object) -> None:
        """Test rotation through 0 -> 90 -> 180 -> 270 -> 0."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None
        assert presenter.rotation == 0

        # Rotate CW: 0 -> 90 -> 180 -> 270 -> 0
        kpdf.window.rotate_cw_triggered.emit()
        assert presenter.rotation == 90
        kpdf.window.rotate_cw_triggered.emit()
        assert presenter.rotation == 180
        kpdf.window.rotate_cw_triggered.emit()
        assert presenter.rotation == 270
        kpdf.window.rotate_cw_triggered.emit()
        assert presenter.rotation == 0

        # Rotate CCW: 0 -> 270
        kpdf.window.rotate_ccw_triggered.emit()
        assert presenter.rotation == 270

        kpdf.shutdown()

    def test_tab_switch_preserves_zoom(self, valid_pdf: Path, qtbot: object) -> None:
        """Test that switching tabs pushes each tab's zoom state to toolbar."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        # Open first tab
        self._open_pdf(kpdf, valid_pdf, qtbot)
        presenter1 = kpdf.tab_manager.get_active_presenter()
        assert presenter1 is not None
        presenter1.set_zoom(2.0)

        # Open second tab (need a different path for duplicate detection)
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            second_pdf = Path(tmpdir) / "second.pdf"
            shutil.copy(str(valid_pdf), str(second_pdf))

            spy2 = MagicMock()
            kpdf.tab_manager.document_ready.connect(spy2)
            kpdf.tab_manager.open_file(second_pdf)

            def check_ready2() -> None:
                assert spy2.call_count >= 1

            qtbot.waitUntil(check_ready2, timeout=5000)

            presenter2 = kpdf.tab_manager.get_active_presenter()
            assert presenter2 is not None
            assert presenter2 is not presenter1
            assert presenter2.zoom == 1.0  # Default zoom for new tab

            # Switch back to first tab
            kpdf.window.tab_widget.setCurrentIndex(0)
            # Toolbar should reflect tab 1's zoom
            assert abs(kpdf.window.zoom_toolbar._current_zoom - 2.0) < 0.01

        kpdf.shutdown()

    def test_toolbar_updates_on_presenter_zoom_change(
        self, valid_pdf: Path, qtbot: object
    ) -> None:
        """Test that presenter zoom changes push back to toolbar display."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None

        presenter.set_zoom(1.5)
        # Toolbar should show 150%
        assert "150" in kpdf.window.zoom_toolbar._percent_input.text()

        kpdf.shutdown()
```

- [ ] **Step 2: Run integration tests**

```bash
uv run pytest tests/test_zoom_integration.py -v
```

Expected: All tests pass.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest -v
```

Expected: No regressions. All existing and new tests pass.

- [ ] **Step 4: Check coverage**

```bash
uv run pytest --cov=k_pdf --cov-report=term-missing
```

Expected: Coverage remains 65%+.

- [ ] **Step 5: Commit**

```
feat(f5): add integration tests for zoom, rotation, and fit modes

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

---

### Task 8: Update CLAUDE.md

**Files:**
- Edit: `CLAUDE.md`

- [ ] **Step 1: Update current state**

Edit the `## Current State` section in `CLAUDE.md`:

```markdown
## Current State
- **Project:** K-PDF
- **Phase:** 2 (Construction)
- **Track:** Standard
- **Features built:** Feature 1 (Open and Render PDF), Feature 2 (Multi-Tab), Feature 3 (Page Navigation), Feature 4 (Text Search), Feature 5 (Zoom, Rotate, Page Fit Modes)
- **Features remaining:** Features 6-12 + 7 implicit (see MVP Cutline)
- **Known issues:** Coverage at 65%+ (threshold 65%)
- **Last session summary:** Feature 5 complete — ZoomState/FitMode model, DocumentPresenter zoom/rotation/fit-mode methods, PdfViewport resize/wheel signals, ZoomToolBar with slider/input/presets/rotation, MainWindow View menu actions and keyboard shortcuts, KPdfApp full wiring
```

- [ ] **Step 2: Final lint/type-check/test**

```bash
uv run ruff check .
uv run ruff format .
uv run mypy k_pdf/
uv run pytest -v
```

- [ ] **Step 3: Commit**

```
feat(f5): update CLAUDE.md for Feature 5 completion

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

---

## Self-Review Checklist

1. **Spec compliance:** All items from spec sections 2 (new files), 3 (modified files), 5 (accessibility), 6 (edge cases), and 7 (testing) are covered.
2. **TDD workflow:** Every task follows write-test-RED, implement-GREEN, lint, commit.
3. **Signal flow:** Toolbar -> App -> Presenter -> signal back -> Toolbar. Viewport resize/wheel -> App -> Presenter. Tab switch -> App reads state -> Toolbar.
4. **No placeholders:** All code blocks are complete and runnable.
5. **Existing patterns followed:** `setup_module()` with `_app`, `MagicMock` spies, `qtbot.waitUntil`, `presenter.shutdown()` cleanup.
6. **mypy overrides:** New `zoom_toolbar` module gets `disable_error_code = ["misc"]` for PySide6 subclass issues.
7. **Fit mode logic:** `set_fit_mode` accounts for rotation swapping width/height. Fit mode preserved on `set_fit_mode`, cleared on `set_zoom`.
8. **Per-tab isolation:** `ZoomState` lives inside each `DocumentPresenter`. Tab switch reads the new presenter's state.
9. **Accessibility:** All buttons have text labels and tooltips. No icon-only controls. Keyboard shortcuts for every zoom/rotation action.
10. **Cache invalidation:** `set_zoom`, `set_rotation`, and `set_fit_mode` all call `self._cache.invalidate()` and `self._pending_renders.clear()`.
11. **Edge cases:** No-signal on unchanged value, no-op on `FitMode.NONE`, no-op when no model loaded, invalid percentage input ignored, out-of-range clamped silently.
12. **Commit prefix:** All commits use `feat(f5):` prefix with co-author line.
