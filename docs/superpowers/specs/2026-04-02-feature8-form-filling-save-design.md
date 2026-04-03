# Feature 8: AcroForm Filling & Save — Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Depends on:** Feature 1 (Open/Render), Feature 2 (Multi-Tab)
**FRD Reference:** FUNCTIONAL_REQUIREMENTS.md Section 2, Feature 8
**UI Reference:** UI_SCAFFOLDING.md Section 2.3 (Form Fields)

---

## 1. Architecture Overview

**FormEngine (service):** New service in services/ replacing the existing stub. Reads form fields from PyMuPDF (`page.widgets`), creates Qt widget overlays, collects user-entered values, and writes values back to the PDF on save. PyMuPDF isolation rule unchanged — all fitz calls for form operations remain in this service. Also handles `doc.save(path)` and `doc.save(new_path)` for Save/Save As.

**FormPresenter:** New presenter in presenters/ that manages the form field widget lifecycle. Detects forms on document open, creates overlay widgets per page, tracks per-tab form state (original values vs. current values), coordinates save flow, and manages the dirty flag.

**Widget overlays:** Qt widgets (QLineEdit, QCheckBox, QComboBox, QRadioButton) placed as QGraphicsProxyWidget overlays on the PdfViewport's QGraphicsScene, positioned and scaled to match each form field's PDF coordinates under the current zoom/rotation. Overlays move and resize when zoom or rotation changes.

**Save flow:** Save writes form values back into the PDF via PyMuPDF, then calls `doc.save(path)` for Save or `doc.save(new_path)` for Save As. Clears dirty flag on success. Save failure shows an error dialog with "Try Save As" guidance.

### Signal Flow

1. User opens a PDF with AcroForm fields -> `FormEngine.detect_fields(doc_handle)` returns field descriptors -> `FormPresenter` creates Qt widget overlays on the viewport -> status bar shows "This document contains [N] form fields"
2. User edits a field value (types in QLineEdit, toggles QCheckBox, selects from QComboBox) -> `FormPresenter.on_field_changed()` -> `model.dirty = True` -> tab title shows `*` prefix
3. User clicks File > Save (Ctrl+S) -> `FormPresenter.save()` -> collects all field values -> `FormEngine.write_fields(doc_handle, field_values)` -> `FormEngine.save_document(doc_handle, path)` -> dirty flag cleared -> tab title `*` removed
4. User clicks File > Save As (Ctrl+Shift+S) -> file picker -> `FormEngine.save_document(doc_handle, new_path)` -> dirty flag cleared -> tab title updated to new filename
5. User closes tab with dirty=True -> Save/Discard/Cancel dialog (from Feature 2) activated -> Save triggers step 3, Discard closes without saving, Cancel aborts close
6. XFA form detected -> notification "XFA dynamic forms not supported. Only AcroForms supported." -> form overlays not created

---

## 2. New Files

### `k_pdf/presenters/form_presenter.py`

Replaces existing stub.

Instance variables:
- `_form_engine: FormEngine` — reference to the form engine service
- `_tab_manager: TabManager` — reference to the tab manager
- `_field_widgets: dict[str, dict[str, QWidget]]` — maps session_id -> {field_name: QWidget} for per-tab form state
- `_original_values: dict[str, dict[str, Any]]` — maps session_id -> {field_name: original_value} for dirty detection

Signals:
- `dirty_changed(bool)` — emitted when form dirty flag transitions
- `form_detected(int)` — emitted with field count when AcroForm detected on open
- `save_succeeded()` — emitted after successful save
- `save_failed(str)` — emitted with error message on save failure

Methods:
- `on_document_opened(session_id: str, doc_handle)` — calls `FormEngine.detect_fields()`, creates overlay widgets, stores original values, emits `form_detected` with count
- `on_field_changed(session_id: str, field_name: str, value)` — sets `model.dirty = True`, emits `dirty_changed`
- `save(session_id: str)` — collects current values from widgets, calls `FormEngine.write_fields()` then `FormEngine.save_document()`, clears dirty flag on success, emits `save_succeeded` or `save_failed`
- `save_as(session_id: str, new_path: Path)` — same as save but writes to new_path, updates document model path
- `on_tab_switched(session_id: str)` — shows/hides form overlays for the active tab
- `on_tab_closed(session_id: str)` — removes field widgets and original values for the closed tab
- `create_field_overlay(field_descriptor: dict, viewport) -> QWidget` — factory method: creates QLineEdit for text fields, QCheckBox for checkboxes, QComboBox for dropdowns, QRadioButton group for radio buttons
- `reposition_overlays(session_id: str)` — recalculates overlay positions from PDF coordinates to viewport coordinates under current zoom/rotation

### `k_pdf/core/form_model.py`

**`FormFieldType` enum:**

| Value | Description |
|---|---|
| `TEXT` | Single-line or multi-line text input |
| `CHECKBOX` | Boolean toggle |
| `DROPDOWN` | Single-select from a list of options |
| `RADIO` | Radio button group (one selection from N options) |

**`FormFieldDescriptor` dataclass (frozen=True):**

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | — | Field name from the PDF form |
| `field_type` | `FormFieldType` | — | Widget type to create |
| `page` | `int` | — | Zero-based page index |
| `rect` | `tuple[float, float, float, float]` | — | Bounding rectangle in PDF coordinates |
| `value` | `str` | `""` | Current field value |
| `options` | `list[str]` | `field(default_factory=list)` | Choice options (for DROPDOWN and RADIO types) |
| `read_only` | `bool` | `False` | Whether the field is marked read-only in the PDF |
| `max_length` | `int \| None` | `None` | Maximum character count for text fields |

---

## 3. Modified Files

### `k_pdf/services/form_engine.py`

Replaces existing stub. PyMuPDF form operations isolated here.

Methods:
- `detect_fields(doc_handle) -> list[FormFieldDescriptor]` — iterates all pages, calls `page.widgets` on each, maps PyMuPDF widget types to `FormFieldDescriptor` instances. Returns empty list if no AcroForm. Detects XFA forms via `doc_handle.is_form_pdf` and `doc_handle.xfa` and returns a sentinel indicating XFA.
- `is_xfa_form(doc_handle) -> bool` — returns True if the document contains XFA form data
- `write_fields(doc_handle, field_values: dict[str, str])` — iterates widgets across all pages, sets values from the dict by field name, calls `widget.update()` on each
- `save_document(doc_handle, path: Path)` — calls `doc_handle.save(str(path), incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)` for existing files; uses `doc_handle.save(str(path))` for Save As to a new path
- `get_field_value(widget) -> str` — reads the current value from a PyMuPDF widget

### `k_pdf/views/main_window.py`

New additions to File menu (after Open, before Close Tab separator):
- "Save" action (Ctrl+S) — grayed out when no document open or document is read-only
- "Save As..." action (Ctrl+Shift+S) — grayed out when no document open

New signals:
- `save_requested()` — emitted when Save action triggered
- `save_as_requested()` — emitted when Save As action triggered

New method:
- `set_save_enabled(enabled: bool)` — enables/disables Save action (for read-only files)

### `k_pdf/views/pdf_viewport.py`

New methods:
- `add_form_overlay(widget: QWidget, rect: tuple[float, float, float, float])` — adds a QGraphicsProxyWidget to the scene at the specified PDF-coordinate rect, transformed by current zoom/rotation
- `remove_form_overlays()` — removes all form overlay proxy widgets from the scene
- `reposition_form_overlays()` — recalculates positions of all form overlays when zoom/rotation changes

Existing `zoom_changed` / `rotation_changed` handlers extended to call `reposition_form_overlays()`.

### `k_pdf/app.py`

New wiring:
- Create `FormEngine` and `FormPresenter` instances
- Connect document-opened flow -> `FormPresenter.on_document_opened`
- Connect MainWindow save_requested -> `FormPresenter.save`
- Connect MainWindow save_as_requested -> file picker dialog -> `FormPresenter.save_as`
- Connect `FormPresenter.form_detected` -> status bar message "This document contains [N] form fields"
- Connect `FormPresenter.dirty_changed` -> update tab title with `*` prefix
- Connect `FormPresenter.save_succeeded` -> status bar message "Document saved"
- Connect `FormPresenter.save_failed` -> error dialog with Save As guidance
- Connect `TabManager.tab_switched` -> `FormPresenter.on_tab_switched`
- Connect `TabManager.tab_close_requested` with dirty check -> Save/Discard/Cancel dialog -> route to FormPresenter.save or discard

### `k_pdf/presenters/tab_manager.py`

Modified `close_tab()` to check `model.dirty` before closing. If dirty, emits a new `close_guard_requested(session_id)` signal. The Save/Discard/Cancel dialog logic (from Feature 2's unsaved-changes guard) is activated here, routing Save to `FormPresenter.save()`.

### `k_pdf/core/document_model.py`

New field:
- `file_path: Path | None` — stores the current file path for Save operations (already partially present; ensured to be writable for Save As path updates)

---

## 4. Unchanged Files

- `k_pdf/core/page_cache.py` — unchanged
- `k_pdf/core/zoom_model.py` — unchanged
- `k_pdf/core/search_model.py` — unchanged
- `k_pdf/core/annotation_model.py` — unchanged
- `k_pdf/services/pdf_engine.py` — unchanged (rendering unaffected by form filling)
- `k_pdf/services/annotation_engine.py` — unchanged
- `k_pdf/services/search_engine.py` — unchanged
- `k_pdf/presenters/document_presenter.py` — unchanged
- `k_pdf/presenters/navigation_presenter.py` — unchanged
- `k_pdf/presenters/search_presenter.py` — unchanged
- `k_pdf/presenters/annotation_presenter.py` — unchanged
- `k_pdf/views/annotation_toolbar.py` — unchanged
- `k_pdf/views/zoom_toolbar.py` — unchanged
- `k_pdf/views/search_bar.py` — unchanged
- `k_pdf/views/navigation_panel.py` — unchanged

---

## 5. Accessibility

- All form field overlays are standard Qt widgets — QLineEdit, QCheckBox, QComboBox, QRadioButton — which inherit platform accessibility support (screen reader labels, focus indicators)
- Tab key navigates between form fields in document order (top-to-bottom, left-to-right per page)
- Save and Save As actions have keyboard shortcuts (Ctrl+S, Ctrl+Shift+S) — no mouse-only activation path
- Form field count announced in status bar as text, not just a visual indicator
- XFA notification uses standard status bar message with text — not color-coded
- Save/Discard/Cancel dialog uses standard QMessageBox with labeled buttons
- Save error dialog uses standard QMessageBox with text explanation and guidance

---

## 6. Error Handling & Edge Cases

**XFA forms:** When `FormEngine.is_xfa_form()` returns True, show notification: "XFA dynamic forms not supported. Only AcroForms supported." No form overlays are created. The document still opens for reading.

**No form fields:** When `detect_fields()` returns an empty list and `is_xfa_form()` is False, no status bar message is shown. Save/Save As remain available for saving annotation changes or other modifications.

**Read-only file:** When the file is read-only on disk (checked via `os.access(path, os.W_OK)`), Save action is grayed out. Save As remains available. Status bar shows "Read-only" indicator.

**Save failure:** When `doc.save()` raises an exception (e.g., file locked, disk full, permission denied), show error dialog: "Could not save to [path]. [error message]. Try File > Save As to save to a different location." Dirty flag remains True.

**Save As to same path:** Allowed. Treated as a normal save (incremental write).

**Dirty flag coordination:** Both FormPresenter and AnnotationPresenter can set `model.dirty = True`. The dirty flag is a single bool on the document model. Either presenter setting it to True marks the tab dirty. Clearing requires a successful save that writes both form values and annotations.

**Form fields spanning page break:** Each field belongs to exactly one page (as defined in the PDF). No cross-page fields.

**Tab close with dirty form:** Save/Discard/Cancel dialog from Feature 2 is activated. Save collects form values and saves. Discard closes without saving. Cancel aborts the close.

**Large forms (100+ fields):** Widget overlays created lazily per visible page. Off-screen pages do not have active overlays until scrolled into view. This prevents performance issues with very large forms.

**Field with max_length:** QLineEdit `setMaxLength()` set from `FormFieldDescriptor.max_length`. None means no limit.

**Radio button groups:** Grouped by field name. All radio buttons with the same name form one group — selecting one deselects others.

---

## 7. Testing Strategy

### Unit Tests

| File | Tests |
|---|---|
| `tests/test_form_model.py` | `FormFieldType` enum values (TEXT, CHECKBOX, DROPDOWN, RADIO), `FormFieldDescriptor` construction with all fields, default `value` is empty string, default `options` is empty list, `read_only` default is False |
| `tests/test_form_engine.py` | `detect_fields` returns descriptors for a real AcroForm PDF fixture, `detect_fields` returns empty list for non-form PDF, `is_xfa_form` returns True for XFA fixture, `write_fields` updates field values in PDF, `save_document` writes file to disk, `save_document` with new path creates new file, `get_field_value` reads current value |
| `tests/test_form_presenter.py` | `on_document_opened` creates overlays and emits `form_detected`, `on_field_changed` sets dirty flag, `save` collects values and calls engine, `save` clears dirty flag on success, `save` emits `save_failed` on exception, `save_as` writes to new path, `on_tab_switched` shows/hides correct overlays, `on_tab_closed` cleans up state, XFA form triggers notification instead of overlays |
| `tests/test_form_overlays.py` | `create_field_overlay` returns QLineEdit for TEXT type, returns QCheckBox for CHECKBOX, returns QComboBox for DROPDOWN, returns QRadioButton for RADIO, overlay positioned correctly at PDF rect, overlay repositions on zoom change |
| `tests/test_save_flow.py` | Save with clean document is no-op, Save with dirty form writes values and saves file, Save As shows file picker and saves to new path, Save failure shows error dialog, Save grayed out for read-only file, Save clears `*` from tab title |

### Integration Tests (`tests/test_form_filling_integration.py`)

| Test | Verifies |
|---|---|
| `test_open_form_pdf_shows_overlays` | Open AcroForm PDF -> form overlays appear on viewport -> status bar shows field count |
| `test_fill_text_field_and_save` | Open form PDF -> type in text field -> Ctrl+S -> reopen file -> value persisted |
| `test_fill_checkbox_and_save` | Open form PDF -> toggle checkbox -> Save -> reopen -> checkbox state persisted |
| `test_fill_dropdown_and_save` | Open form PDF -> select dropdown option -> Save -> reopen -> selection persisted |
| `test_save_as_new_path` | Open form PDF -> edit field -> Save As -> new file exists with correct values |
| `test_dirty_flag_on_field_edit` | Edit a form field -> dirty flag True, tab title has `*` -> Save -> dirty flag False, `*` removed |
| `test_close_dirty_tab_save` | Edit field -> close tab -> Save/Discard/Cancel dialog -> Save -> file saved, tab closed |
| `test_close_dirty_tab_discard` | Edit field -> close tab -> Discard -> tab closed without saving |
| `test_close_dirty_tab_cancel` | Edit field -> close tab -> Cancel -> tab remains open |
| `test_xfa_form_notification` | Open XFA PDF -> notification shown -> no form overlays created |
| `test_readonly_file_save_disabled` | Open read-only PDF -> Save action grayed out -> Save As still available |
| `test_tab_navigation_between_fields` | Open form PDF -> Tab key moves focus between form fields in order |

**Mocking:** PyMuPDF mocked in presenter unit tests. Engine tests and integration tests use real fixture PDFs (one AcroForm, one XFA, one non-form).

**Coverage target:** Maintain 65%+.

---

## 8. Deferred Items

- **Form field validation rules** — min/max values, required fields, format masks deferred to a future feature.
- **JavaScript-driven forms** — PDF JavaScript actions (calculate, validate, format) not executed; deferred.
- **Digital signatures** — signature fields displayed but not fillable; signing deferred.
- **Flatten forms** — converting form fields to static content deferred.
- **Undo/redo** — form field edit undo stack deferred to a future feature.
- **Auto-save / recovery** — periodic auto-save of dirty documents deferred.
- **Print with form values** — printing deferred to a separate feature.
- **Form field appearance customization** — font, color, alignment of form fields rendered as-is from PDF; custom styling deferred.
