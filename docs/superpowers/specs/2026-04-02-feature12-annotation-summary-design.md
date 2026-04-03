# Feature 12: Annotation Summary Panel — Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Depends on:** Feature 1 (Open/Render), Feature 2 (Multi-Tab), Feature 6 (Text Markup), Feature 7 (Sticky Notes & Text Box)
**FRD Reference:** FUNCTIONAL_REQUIREMENTS.md Section 2, Feature 12
**UI Reference:** UI_SCAFFOLDING.md Section 1 (Right-side Annotation Panel)

---

## 1. Architecture Overview

**AnnotationSummaryPanel (view):** New QDockWidget (right-docked, F6 toggle) replacing the existing stub in `views/annotation_panel.py`. Contains a QTableWidget listing all annotations across every page of the active document. Panel starts hidden and is toggled via View > Annotation Panel (F6).

**AnnotationSummaryPresenter:** New presenter in `presenters/annotation_summary_presenter.py`. Subscribes to TabManager and AnnotationPresenter signals to maintain per-tab annotation lists. Scans all pages on document load. Coordinates navigation when the user clicks a row.

**AnnotationEngine:** Existing service — already has `get_annotations()` and `get_annotation_type()` methods. A new `get_annotation_info()` method is added to extract all metadata (type, author, content, color, rect) for a single annotation in one call, avoiding multiple round-trips.

### Signal Flow

1. Document loads -> `TabManager.document_ready` -> `AnnotationSummaryPresenter.on_document_ready()` -> scans all pages via `AnnotationEngine.get_annotations()` -> builds annotation list -> pushes to panel
2. Annotation created -> `AnnotationPresenter.annotation_created` -> `AnnotationSummaryPresenter.refresh_annotations()` -> rescans and updates panel
3. Annotation deleted -> `AnnotationPresenter.annotation_deleted` -> `AnnotationSummaryPresenter.refresh_annotations()` -> rescans and updates panel
4. Tab switched -> `TabManager.tab_switched` -> `AnnotationSummaryPresenter.on_tab_switched()` -> swaps to the target tab's annotation list
5. Tab closed -> `TabManager.tab_closed` -> `AnnotationSummaryPresenter.on_tab_closed()` -> removes stored state for that tab
6. User clicks annotation row -> `AnnotationSummaryPanel.annotation_clicked(page_index)` -> `AnnotationSummaryPresenter` -> `DocumentPresenter.request_pages([page_index])` + viewport scroll to page

---

## 2. New Files

### `k_pdf/presenters/annotation_summary_presenter.py`

**`AnnotationSummaryPresenter(QObject)`:**

Instance variables:
- `_tab_manager: TabManager` — reference to the tab manager
- `_annotation_engine: AnnotationEngine` — reference to the annotation engine
- `_panel: AnnotationSummaryPanel` — reference to the panel view
- `_per_tab_annotations: dict[str, list[AnnotationInfo]]` — per-tab annotation data keyed by session_id

Signals:
- None (panel directly emits click signals; presenter calls panel methods)

Methods:
- `on_document_ready(session_id: str, model: DocumentModel)` — scans all pages for annotations, builds list, stores per-tab, updates panel if active tab
- `on_tab_switched(session_id: str)` — swaps panel content to stored annotations for the new tab
- `on_tab_closed(session_id: str)` — removes stored annotations for the closed tab
- `refresh_annotations()` — rescans active document, updates stored list and panel
- `on_annotation_clicked(page_index: int)` — navigates viewport to the given page

### `k_pdf/core/annotation_model.py` (modified)

**`AnnotationInfo` dataclass (new, added to existing file):**

| Field | Type | Default | Description |
|---|---|---|---|
| `page` | `int` | — | Zero-based page index |
| `ann_type` | `str` | — | Human-readable type: "Highlight", "Underline", "Strikethrough", "Note", "Text Box" |
| `author` | `str` | `""` | Author name from annotation metadata |
| `content` | `str` | `""` | Text content (for notes/text boxes) |
| `color` | `tuple[float, float, float]` | `(0.0, 0.0, 0.0)` | RGB color |
| `rect` | `tuple[float, float, float, float]` | `(0.0, 0.0, 0.0, 0.0)` | Bounding rectangle |

---

## 3. Modified Files

### `k_pdf/views/annotation_panel.py`

Replaces existing one-line stub.

**`AnnotationSummaryPanel(QDockWidget)` — right-docked, F6 toggle.**

Layout:
- Header label: "Annotations" (or "No annotations in this document" when empty)
- QTableWidget with columns: Page, Type, Author, Preview, Color
- Sorted by Page number ascending by default

Table columns:

| Column | Data | Width |
|---|---|---|
| Page | `str(page + 1)` (1-based) | 50px |
| Type | Icon + text label ("Highlight", "Underline", "Strikethrough", "Note", "Text Box") | 120px |
| Author | Author name or "" | 100px |
| Preview | Truncated content (first 40 chars) for notes/text boxes; "" for markup | stretch |
| Color | Small colored swatch (16x16 QPixmap) | 40px |

Instance variables:
- `_table: QTableWidget` — the annotation table
- `_empty_label: QLabel` — "No annotations in this document" (shown when table is empty)

Signals:
- `annotation_clicked(int)` — emitted with page_index when a row is clicked

Methods:
- `set_annotations(annotations: list[AnnotationInfo])` — populates the table from annotation data
- `clear()` — clears the table and shows empty state label

Accessibility:
- Type column always shows icon + text label, never color alone
- Table supports keyboard navigation (arrow keys between rows, Enter to navigate)
- Column headers are sortable by clicking
- Color swatch is supplementary; type is identified by text label

### `k_pdf/services/annotation_engine.py`

New method:
- `get_annotation_info(doc_handle, page_index: int, annot) -> dict[str, Any]` — returns a dict with keys: `type_code`, `type_name`, `author`, `content`, `color`, `rect`. Single call per annotation avoids multiple xref lookups.

### `k_pdf/views/main_window.py`

New additions:
- View menu: "Annotation &Panel" toggle action (F6) — toggles AnnotationSummaryPanel dock widget visibility
- `_annotation_summary_panel: AnnotationSummaryPanel` — new dock widget, added to right dock area
- New property: `annotation_summary_panel -> AnnotationSummaryPanel`

### `k_pdf/app.py`

New wiring:
- Create `AnnotationSummaryPresenter` instance
- Connect `TabManager.document_ready` -> `AnnotationSummaryPresenter.on_document_ready`
- Connect `TabManager.tab_switched` -> `AnnotationSummaryPresenter.on_tab_switched`
- Connect `TabManager.tab_closed` -> `AnnotationSummaryPresenter.on_tab_closed`
- Connect `AnnotationPresenter.annotation_created` -> `AnnotationSummaryPresenter.refresh_annotations`
- Connect `AnnotationPresenter.annotation_deleted` -> `AnnotationSummaryPresenter.refresh_annotations`
- Connect `AnnotationSummaryPanel.annotation_clicked` -> `AnnotationSummaryPresenter.on_annotation_clicked`

---

## 4. Unchanged Files

- `k_pdf/core/page_cache.py` — unchanged
- `k_pdf/core/zoom_model.py` — unchanged
- `k_pdf/core/search_model.py` — unchanged
- `k_pdf/core/page_model.py` — unchanged
- `k_pdf/services/pdf_engine.py` — unchanged
- `k_pdf/services/search_engine.py` — unchanged
- `k_pdf/services/form_engine.py` — unchanged
- `k_pdf/services/page_engine.py` — unchanged
- `k_pdf/presenters/document_presenter.py` — unchanged
- `k_pdf/presenters/search_presenter.py` — unchanged
- `k_pdf/presenters/annotation_presenter.py` — unchanged (existing signals reused; no modifications)
- `k_pdf/presenters/form_presenter.py` — unchanged
- `k_pdf/presenters/page_management_presenter.py` — unchanged
- `k_pdf/views/annotation_toolbar.py` — unchanged
- `k_pdf/views/zoom_toolbar.py` — unchanged
- `k_pdf/views/search_bar.py` — unchanged
- `k_pdf/views/pdf_viewport.py` — unchanged
- `k_pdf/views/navigation_panel.py` — unchanged
- `k_pdf/views/page_manager_panel.py` — unchanged

---

## 5. Accessibility

- Type column: always icon + text label ("Highlight", "Underline", "Strikethrough", "Note", "Text Box") — never icon-only, never color-only
- Color swatch is supplementary decoration — type is always identifiable by text label
- Table is keyboard navigable: arrow keys move between rows, Enter navigates to annotation
- Column headers have text labels and support click-to-sort
- Empty state uses centered text: "No annotations in this document"
- F6 keyboard shortcut to toggle panel — no mouse-only activation path
- Panel dock widget has a title bar readable by screen readers
- Sorted by page number by default for predictable navigation order

---

## 6. Error Handling & Edge Cases

**No annotations:** Empty state label "No annotations in this document" shown centered in panel. Table hidden.

**500+ annotations:** QTableWidget handles large row counts. No virtual scrolling needed for MVP — QTableWidget is efficient for thousands of rows.

**Missing metadata:** If annotation has no author, show "". If content is empty, show "". No crash.

**External annotations:** Annotations created by other tools are displayed with original metadata. Type mapped to closest K-PDF type: PyMuPDF type 8 = Highlight, type 9 = Underline, type 10 = StrikeOut, type 0 = Text (sticky note), type 2 = FreeText (text box). Unknown types shown as "Unknown".

**Tab switch:** Panel swaps to the new tab's stored annotation list immediately. No rescan needed.

**Annotation on deleted page:** After page deletion (Feature 9), `refresh_annotations()` rescans. Deleted page annotations disappear naturally because the page no longer exists.

**Panel open with no document:** Shows empty state. Table is empty.

**Document with no text layer:** Annotations panel still works — it lists all annotation objects regardless of text layer.

---

## 7. Testing Strategy

### Unit Tests

| File | Tests |
|---|---|
| `tests/test_annotation_model.py` | `AnnotationInfo` construction with all fields, default values for optional fields |
| `tests/test_annotation_engine.py` | `get_annotation_info` returns correct dict for highlight, underline, strikethrough, sticky note, text box |
| `tests/test_annotation_summary_panel.py` | `set_annotations` populates table with correct row count and column data, `clear` empties table and shows empty label, `annotation_clicked` signal emitted on row click, empty state shown when no annotations, sorting by column works |
| `tests/test_annotation_summary_presenter.py` | `on_document_ready` scans pages and updates panel, `refresh_annotations` rescans and updates, `on_tab_switched` swaps to correct tab data, `on_tab_closed` removes stored data, `on_annotation_clicked` requests correct page, no-model no-op for all methods |

### Integration Tests (`tests/test_annotation_summary_integration.py`)

| Test | Verifies |
|---|---|
| `test_panel_shows_annotations_on_load` | Open annotated PDF -> panel lists all annotations with correct page/type/author |
| `test_panel_updates_on_create` | Create highlight -> panel adds new row |
| `test_panel_updates_on_delete` | Delete annotation -> panel removes row |
| `test_click_navigates_to_page` | Click annotation row -> viewport navigates to that page |
| `test_tab_switch_swaps_annotations` | Open two docs -> switch tabs -> panel shows correct annotations |
| `test_empty_document_shows_empty_state` | Open PDF with no annotations -> panel shows "No annotations in this document" |
| `test_panel_toggle_f6` | Press F6 -> panel opens -> press F6 -> panel closes |

**Mocking:** AnnotationEngine mocked in presenter unit tests. Panel tests use AnnotationInfo data objects directly. Integration tests use real fixture PDFs with annotations.

**Coverage target:** Maintain 65%+.

---

## 8. Deferred Items

- **Filter by type** — dropdown to filter annotation list by type (deferred to post-MVP)
- **Sort persistence** — remembering sort column/order across sessions (deferred)
- **Annotation editing from panel** — double-click to edit note content from the panel (deferred)
- **Export annotations** — exporting annotation list as text/CSV (deferred)
- **Timestamp column** — PyMuPDF annotation timestamps are unreliable; deferred until tested
- **Annotation position highlighting** — briefly highlighting the target annotation after navigation (deferred)
