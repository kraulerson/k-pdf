# Feature 5: Zoom, Rotate, Page Fit Modes — Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Depends on:** Feature 1 (Open/Render), Feature 2 (Multi-Tab)
**FRD Reference:** FUNCTIONAL_REQUIREMENTS.md Section 2, Feature 5
**UI Reference:** UI_SCAFFOLDING.md Section 2.1 (Zoom Toolbar)

---

## 1. Architecture Overview

**Zoom/rotation state:** Extend `DocumentPresenter` with zoom level, rotation angle, and fit mode state. New `ZoomState` dataclass and `FitMode` enum in core/ keep the model layer framework-free. Each presenter instance (one per tab) owns its own zoom/rotation state.

**Toolbar:** New `ZoomToolBar(QToolBar)` in views/ provides zoom slider, editable percentage field, preset dropdown, and rotation buttons. MainWindow gains this toolbar plus View menu rotation actions.

**Fit modes:** `FitMode.PAGE` and `FitMode.WIDTH` auto-calculate zoom from viewport dimensions. Recalculated on window resize. Any explicit zoom input (slider, keyboard, Ctrl+scroll) clears fit mode to `NONE`.

### Signal Flow

1. User interacts with ZoomToolBar (slider, input, preset, rotation button) → toolbar emits signal
2. `App` routes signal to active `DocumentPresenter` via `TabManager`
3. `DocumentPresenter.set_zoom()` / `set_rotation()` / `set_fit_mode()` — clamps values, updates state, invalidates page cache, re-renders visible pages, emits `zoom_changed` / `rotation_changed`
4. ZoomToolBar receives signal back, updates display (slider position, percentage text)
5. Ctrl+scroll on viewport → `PdfViewport` emits `zoom_at_cursor(float, QPointF)` → DocumentPresenter adjusts zoom
6. Window resize with fit mode active → `PdfViewport` emits `viewport_resized(float, float)` → DocumentPresenter recalculates zoom via `set_fit_mode`
7. Tab switch → `App` reads new tab's presenter state, pushes to ZoomToolBar

---

## 2. New Files

### `k_pdf/core/zoom_model.py`

**`FitMode` enum:**

| Value | Description |
|---|---|
| `NONE` | User-set zoom, no auto-recalculation |
| `PAGE` | Zoom calculated so entire page fits in viewport |
| `WIDTH` | Zoom calculated so page width fills viewport |

**`ZoomState` dataclass (frozen=False):**

| Field | Type | Default | Description |
|---|---|---|---|
| `zoom` | `float` | `1.0` | Current zoom level (1.0 = 100%) |
| `rotation` | `int` | `0` | Current rotation in degrees (0, 90, 180, 270) |
| `fit_mode` | `FitMode` | `FitMode.NONE` | Active fit mode |
| `min_zoom` | `float` | `0.1` | Minimum allowed zoom (10%) |
| `max_zoom` | `float` | `32.0` | Maximum allowed zoom (3200%) |

Methods:
- `clamp_zoom(value: float) -> float` — clamp to `[min_zoom, max_zoom]`
- `normalize_rotation(degrees: int) -> int` — wrap to 0/90/180/270 (e.g., 270+90=0, -90=270)

### `k_pdf/views/zoom_toolbar.py`

**`ZoomToolBar(QToolBar)` class:**

Layout: [Rotate CCW] [Rotate CW] | [Zoom Out (-)] [Slider] [Percentage Input] [Zoom In (+)] | [Preset Dropdown]

Preset dropdown items: "Fit Page", "Fit Width", "Actual Size (100%)", "50%", "75%", "150%", "200%"

Signals:
- `zoom_changed(float)` — slider moved, percentage input edited, or numeric preset selected
- `fit_page_requested()` — "Fit Page" selected from dropdown
- `fit_width_requested()` — "Fit Width" selected from dropdown
- `rotate_cw_requested()` — Rotate CW button clicked
- `rotate_ccw_requested()` — Rotate CCW button clicked

Methods:
- `set_zoom(zoom: float)` — update slider position and percentage text without re-emitting signals
- `set_rotation(rotation: int)` — update rotation display if shown
- `set_fit_mode(mode: FitMode)` — update dropdown selection to match active fit mode

All buttons have text labels and tooltips. Zoom slider labeled with percentage text.

---

## 3. Modified Files

### `k_pdf/presenters/document_presenter.py`

New signals:
- `zoom_changed = Signal(float)` — emitted after zoom level changes
- `rotation_changed = Signal(int)` — emitted after rotation changes

New properties:
- `zoom -> float` — current zoom level
- `rotation -> int` — current rotation in degrees
- `fit_mode -> FitMode` — current fit mode

New methods:
- `set_zoom(zoom: float)` — clamp to 0.1–32.0, store in `ZoomState`, clear fit mode to `NONE`, invalidate page cache, re-render visible pages, emit `zoom_changed(float)`
- `set_rotation(rotation: int)` — normalize to 0/90/180/270, store in `ZoomState`, invalidate page cache, re-render visible pages, emit `rotation_changed(int)`
- `set_fit_mode(mode: FitMode, viewport_width: float, viewport_height: float)` — calculate zoom from current page dimensions and viewport size, call internal zoom update but preserve fit mode (do not clear to `NONE`), emit `zoom_changed(float)`

New instance variable: `_zoom_state: ZoomState` — initialized with defaults on construction.

`set_fit_mode` logic:
- `FitMode.PAGE`: `zoom = min(viewport_width / page_width, viewport_height / page_height)`
- `FitMode.WIDTH`: `zoom = viewport_width / page_width`
- Page dimensions come from `DocumentModel.page_size(current_page_index)`, accounting for current rotation (width/height swap at 90/270 degrees)

### `k_pdf/views/pdf_viewport.py`

New signals:
- `viewport_resized(float, float)` — emitted from `resizeEvent` override with (width, height)
- `zoom_at_cursor(float, QPointF)` — emitted from `wheelEvent` when Ctrl modifier held; float is step direction (+0.1 or -0.1 per notch), QPointF is cursor position in scene coordinates

New behavior:
- `resizeEvent` override: call `super().resizeEvent()`, then emit `viewport_resized` with viewport dimensions
- `wheelEvent` override: if Ctrl held, consume event, calculate step (10% per notch), emit `zoom_at_cursor`; otherwise delegate to default scroll behavior
- Search highlights (from Feature 4) repositioned on zoom change — existing `add_search_highlights` already takes a zoom parameter

### `k_pdf/views/main_window.py`

New additions:
- Add `ZoomToolBar` to the toolbar area
- Expose `zoom_toolbar` property
- View menu: "Rotate Clockwise" (Ctrl+R), "Rotate Counter-Clockwise" (Ctrl+Shift+R)
- Zoom shortcuts: Ctrl+= (zoom in), Ctrl+- (zoom out), Ctrl+0 (reset to 100%)

### `k_pdf/app.py`

New wiring:
- Connect `ZoomToolBar.zoom_changed` → active `DocumentPresenter.set_zoom`
- Connect `ZoomToolBar.fit_page_requested` → active `DocumentPresenter.set_fit_mode(FitMode.PAGE, ...)`
- Connect `ZoomToolBar.fit_width_requested` → active `DocumentPresenter.set_fit_mode(FitMode.WIDTH, ...)`
- Connect `ZoomToolBar.rotate_cw_requested` → active `DocumentPresenter.set_rotation(current + 90)`
- Connect `ZoomToolBar.rotate_ccw_requested` → active `DocumentPresenter.set_rotation(current - 90)`
- Connect `PdfViewport.viewport_resized` → if fit mode active, call `DocumentPresenter.set_fit_mode` with new dimensions
- Connect `PdfViewport.zoom_at_cursor` → active `DocumentPresenter.set_zoom(current + step)`
- Connect `DocumentPresenter.zoom_changed` → `ZoomToolBar.set_zoom`
- Connect `DocumentPresenter.rotation_changed` → `ZoomToolBar.set_rotation`
- Connect `TabManager.tab_switched` → read new presenter's zoom/rotation/fit_mode, push to ZoomToolBar
- Connect MainWindow zoom/rotation shortcuts → same presenter methods

### `k_pdf/presenters/tab_manager.py`

No structural changes. On tab switch, `App` reads the newly active `DocumentPresenter`'s zoom/rotation/fit_mode properties and pushes them to the toolbar. TabManager already provides the `tab_switched` signal needed for this.

---

## 4. Unchanged Files

- `k_pdf/core/document_model.py` — unchanged
- `k_pdf/core/page_cache.py` — unchanged
- `k_pdf/services/pdf_engine.py` — unchanged (`render_page` already accepts zoom and rotation parameters)
- `k_pdf/presenters/navigation_presenter.py` — unchanged
- `k_pdf/presenters/search_presenter.py` — unchanged

---

## 5. Accessibility

- Zoom slider labeled with percentage text (e.g., "Zoom: 150%")
- All toolbar buttons have text labels and tooltips, not icon-only
- Zoom presets in dropdown with text labels: "Fit Page", "Fit Width", "Actual Size (100%)", "50%", "75%", "150%", "200%"
- Rotation buttons labeled "Rotate CW" / "Rotate CCW" with tooltips
- Keyboard shortcuts for all zoom/rotation actions (no mouse-only operations)

---

## 6. Error Handling & Edge Cases

**Zoom clamping:** Values below 10% clamped to 10%, above 3200% clamped to 3200%. No error shown — silent clamp.

**Rotation wrapping:** 270+90=0, 0-90=270. Only multiples of 90 accepted.

**High zoom rendering:** Render visible area first. Already handled by existing lazy rendering in page cache. No special case needed.

**Fit mode on resize:** Recalculate zoom only when fit mode is active (`PAGE` or `WIDTH`). No-op when fit mode is `NONE`.

**Fit mode cleared on explicit zoom:** Slider, keyboard shortcut, or Ctrl+scroll clears fit mode to `NONE`. Dropdown selection of "Fit Page" or "Fit Width" sets the corresponding fit mode.

**Per-tab isolation:** Zoom, rotation, and fit mode stored in `DocumentPresenter` (one per tab). Tab switch updates toolbar to reflect the new tab's state. Closing a tab discards its state. View rotation does not modify the PDF file.

**Invalid percentage input:** Non-numeric input in the percentage field ignored. Out-of-range numeric input clamped silently.

**Empty document / no pages:** Zoom and rotation controls disabled (grayed out) when no document is open.

---

## 7. Testing Strategy

### Unit Tests

| File | Tests |
|---|---|
| `tests/test_zoom_model.py` | `ZoomState` construction with defaults, `clamp_zoom` at boundaries, `normalize_rotation` wrapping (270+90=0, -90=270), `FitMode` enum values |
| `tests/test_document_presenter_zoom.py` | `set_zoom` clamps and emits signal, `set_zoom` clears fit mode, `set_rotation` normalizes and emits, `set_fit_mode` calculates correct zoom for PAGE/WIDTH, `set_fit_mode` preserves fit mode, zoom/rotation properties return current values |
| `tests/test_zoom_toolbar.py` | `zoom_changed` emitted on slider move, `zoom_changed` emitted on percentage input, `fit_page_requested` / `fit_width_requested` emitted on dropdown selection, `rotate_cw_requested` / `rotate_ccw_requested` emitted on button click, `set_zoom` updates display without re-emitting |

### Integration Tests (`tests/test_zoom_integration.py`)

| Test | Verifies |
|---|---|
| `test_zoom_in_out` | Ctrl+= increases zoom, Ctrl+- decreases zoom, toolbar updates |
| `test_reset_zoom` | Ctrl+0 resets zoom to 100% |
| `test_fit_page` | Fit Page mode calculates correct zoom, recalculates on resize |
| `test_fit_width` | Fit Width mode calculates correct zoom, recalculates on resize |
| `test_fit_mode_cleared_on_manual_zoom` | Slider/keyboard zoom clears fit mode to NONE |
| `test_rotation_cw_ccw` | Ctrl+R rotates CW through 0→90→180→270→0, Ctrl+Shift+R rotates CCW |
| `test_ctrl_scroll_zoom` | Ctrl+scroll changes zoom centered on cursor position |
| `test_tab_switch_preserves_zoom` | Switch tabs, verify toolbar reflects each tab's zoom/rotation state |
| `test_search_highlights_reposition_on_zoom` | Zoom with search highlights visible, verify highlights reposition correctly |

**Mocking:** PyMuPDF mocked in unit tests. Integration tests use real fixture PDFs.

**Coverage target:** Maintain 65%+.

---

## 8. Deferred Items

- **Default zoom level persistence** — saving preferred zoom level across sessions belongs to the Preferences feature.
- **Tile-based rendering for very high zoom** — FRD spec mentions a >500ms progress indicator at extreme zoom levels. Deferred to polish phase.
- **Pinch-to-zoom gesture** — trackpad gesture support deferred; keyboard and mouse wheel cover MVP.
- **Smooth zoom animation** — zoom snaps immediately in MVP; animated transitions deferred to polish.
