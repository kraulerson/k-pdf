# Post-MVP Design: Form Field Creation & Text Editing

**Date:** 2026-04-06
**Status:** Approved
**Features:** Form Field Creation (authoring new AcroForm fields), Text Editing (find-and-replace + click-to-edit inline)

---

## 1. Overview

Two post-MVP features extending K-PDF's editing capabilities:

1. **Form Field Creation** — Author new AcroForm fields from scratch (text, checkbox, dropdown, radio, signature). Click-to-place with default size, inline popup for quick config, docked properties panel for advanced settings.

2. **Text Editing** — Find-and-replace across document pages, plus click-to-edit for inline text modifications. Font validation with redact-and-overlay fallback when subset fonts prevent direct editing.

Both features are ungated (free tier), following existing MVP architecture patterns.

---

## 2. Architecture

### 2.1 Component Map

| Layer | Form Field Creation | Text Editing |
|-------|-------------------|--------------|
| **Service** | `FormEngine` (extended) | `TextEditEngine` (new) |
| **Presenter** | `FormCreationPresenter` (new) | `TextEditPresenter` (new) |
| **View** | `FormFieldPopup` (new), `FormPropertiesPanel` (new) | `FindReplaceBar` (new), inline edit overlay in viewport |
| **Model** | `FormFieldDescriptor` (existing), `ToolMode` (extended) | `TextEditModel` (new) |

### 2.2 Design Decisions

- **FormEngine extended, not new service:** FormEngine already wraps `pymupdf.Widget` for detection and filling. Creating widgets is a natural extension. Keeps all widget logic in one place.
- **TextEditEngine is new:** Text content stream manipulation is fundamentally different from search (read-only) and annotation (annotation layer, not content stream). Warrants its own service with PyMuPDF isolation.
- **Both new presenters connect to TabManager:** Per-tab state management follows the same pattern as all existing presenters (SearchPresenter, AnnotationPresenter, etc.).
- **All wiring in KPdfApp._connect_signals():** Consistent with existing feature integration pattern.

---

## 3. Feature 1: Form Field Creation

### 3.1 Supported Field Types

| Type | Icon + Label | Default Size (pts) | Quick Config Fields |
|------|-------------|-------------------|-------------------|
| Text | 📝 Text Field | 200 × 24 | name, placeholder, max_length |
| Checkbox | ☑ Checkbox | 14 × 14 | name, default_checked |
| Dropdown | ▼ Dropdown | 200 × 24 | name, options (comma-separated), default_value |
| Radio | ◉ Radio Button | 14 × 14 | name, group_name, value |
| Signature | ✍ Signature Field | 200 × 60 | name |

### 3.2 Interaction Flow

1. User selects field type from **Tools → Form Fields** submenu
2. Viewport cursor changes to crosshair, status bar shows "Form Field Mode: [type] — click to place"
3. User clicks a point on the page
4. Viewport emits `form_field_placed(page_index, point, field_type)` signal
5. `FormCreationPresenter` receives signal, shows `FormFieldPopup` near the click point
6. User configures basic properties in the popup
7. **"Create"**: presenter calls `FormEngine.create_widget()`, document marked dirty, page re-renders, undo action pushed
8. **"More..."**: presenter opens `FormPropertiesPanel` (docked right), user configures all properties, then confirms
9. **"Cancel"**: no field created, tool mode remains active for next placement

### 3.3 Tool Mode Integration

Extend `ToolMode` enum in `k_pdf/core/annotation_model.py`:

```
FORM_TEXT = 10
FORM_CHECKBOX = 11
FORM_DROPDOWN = 12
FORM_RADIO = 13
FORM_SIGNATURE = 14
```

Values start at 10 to leave room for future annotation tool modes. The viewport handles these modes the same way it handles STICKY_NOTE: crosshair cursor, click emits a signal with page coordinates.

### 3.4 FormEngine Extensions

New methods added to existing `k_pdf/services/form_engine.py`:

- `create_widget(doc_handle, page_index, field_type, rect, properties) -> Any` — Creates a pymupdf.Widget, configures it, adds to page, returns widget reference
- `delete_widget(doc_handle, page_index, widget) -> None` — Removes a widget from a page (for undo and explicit delete)
- `update_widget_properties(doc_handle, page_index, widget, properties) -> None` — Updates widget properties (name, value, options, etc.)
- `get_widget_at(doc_handle, page_index, x, y) -> Any | None` — Hit-test for selecting existing form fields

### 3.5 FormFieldPopup (Inline Quick Config)

Floating frameless widget, same pattern as `NoteEditor`:
- Appears near the placed field
- Shows field-type-appropriate inputs (see Quick Config Fields in §3.1)
- Auto-generates field name (e.g., `text_field_1`, `checkbox_2`) with user override
- Three buttons: **More...** (opens properties panel), **Cancel**, **Create**
- Escape key cancels

### 3.6 FormPropertiesPanel (Docked Advanced Config)

QDockWidget docked right, toggled via View menu ("Form Properties", F8):
- Shows all properties for the selected form field
- **Common properties:** name, field_type (read-only), page (read-only), rect (x, y, width, height spinboxes), read_only checkbox
- **Text-specific:** placeholder, max_length, multiline checkbox
- **Dropdown-specific:** options list (add/remove/reorder), default_value
- **Radio-specific:** group_name, value
- **Signature-specific:** (name only — signature fields are blank areas)
- **Delete Field** button at bottom
- Updates apply immediately to the widget (document marked dirty)

### 3.7 Undo Support

Each field creation pushes an `UndoAction`:
- `description`: "Add [Type] Field"
- `undo_fn`: calls `FormEngine.delete_widget()`
- `redo_fn`: calls `FormEngine.create_widget()` with stored parameters

Field property changes push separate undo actions:
- `description`: "Edit Field [name]"
- `undo_fn`: restores previous properties
- `redo_fn`: applies new properties

Field deletion pushes:
- `description`: "Delete Field [name]"
- `undo_fn`: recreates widget with stored parameters
- `redo_fn`: deletes widget

### 3.8 Visual Feedback

- **Placement mode:** Crosshair cursor, status bar shows field type
- **Placed field (before save):** Blue dashed border with field type icon + name label
- **Selected field:** Solid blue border with resize handles (future: resize not in initial implementation)
- **Existing fields:** Rendered normally by PyMuPDF (no special overlay needed)

---

## 4. Feature 2: Text Editing

### 4.1 Find and Replace

#### 4.1.1 FindReplaceBar

New view widget extending the search bar pattern. Activated via **Edit → Find and Replace (Ctrl+H)**:

- **Row 1 (Find):** Query input, match counter ("3 of 7 matches"), Previous/Next buttons, Case-sensitive (Aa) toggle, Whole-word (W) toggle, Close (×) button
- **Row 2 (Replace):** Replacement input, Replace button (replaces current match), Replace All button (replaces all matches)
- Debounced search (300ms) on query input, same as existing SearchBar
- Escape closes the bar

The existing SearchBar (Ctrl+F) remains unchanged for search-only use. FindReplaceBar is a separate widget that includes all search functionality plus the replace row.

#### 4.1.2 Replace Flow

1. User enters find query → matches highlighted (reuses existing search highlight infrastructure)
2. User enters replacement text
3. **"Replace"**: `TextEditPresenter` calls `TextEditEngine.check_font_support()` for current match → if supported, calls `replace_text()` → page re-renders → advances to next match
4. **"Replace All"**: checks font support for all matches → replaces all supported → reports results ("Replaced 5 of 7. 2 skipped — subset font.")
5. If font check fails: shows font limitation dialog with Redact & Overlay option
6. Each replacement pushes an undo action. "Replace All" pushes a single compound undo action.

#### 4.1.3 TextEditEngine — Replace Methods

- `check_font_support(doc_handle, page_index, text_rect) -> FontCheckResult` — Returns whether the text at the given rect uses a fully embedded font that supports arbitrary character replacement
- `replace_text(doc_handle, page_index, search_rect, old_text, new_text) -> bool` — Direct text replacement in the content stream. Returns False if replacement doesn't fit or font fails.
- `replace_all(doc_handle, search_results, old_text, new_text) -> ReplaceAllResult` — Bulk replacement across pages. Returns count of successes and list of skipped locations with reasons.

### 4.2 Click-to-Edit Inline

#### 4.2.1 Activation

- **Tools → Edit Text** menu item (checkable, same pattern as Text Selection Mode)
- New `ToolMode.TEXT_EDIT = 5` enum value
- Cursor changes to I-beam
- Status bar: "Text Edit Mode — double-click text to edit"

#### 4.2.2 Edit Flow

1. User double-clicks a text span on the page
2. Viewport emits `text_edit_requested(page_index, scene_pos)` signal
3. `TextEditPresenter` calls `TextEditEngine.get_text_block(doc_handle, page_index, x, y)` → returns text content, font info, bounding rect
4. If no text at position: no-op
5. If text found: presenter shows floating edit overlay (similar to NoteEditor) positioned over the text block
6. Edit overlay shows:
   - Font info line: "Editing text (font: Helvetica, fully embedded)" or "Editing text (font: TimesNewRoman-Subset — limited editing)"
   - Editable text field pre-filled with current text
   - **Apply** / **Cancel** buttons
7. On **Apply**: presenter calls `TextEditEngine.edit_text_inline()` → font check → direct edit or fallback dialog
8. On **Cancel**: overlay dismissed, no changes

#### 4.2.3 TextEditEngine — Inline Edit Methods

- `get_text_block(doc_handle, page_index, x, y) -> TextBlockInfo | None` — Returns the text span at the given PDF coordinates with content, font name, font flags, bounding rect
- `edit_text_inline(doc_handle, page_index, block_rect, old_text, new_text) -> EditResult` — Attempts direct text edit. Returns success/failure with reason.
- `redact_and_overlay(doc_handle, page_index, block_rect, new_text, font_size) -> None` — Fallback: redacts the original text area and inserts new text using Helvetica at the specified size.

### 4.3 TextEditModel

New dataclass in `k_pdf/core/`:

```python
@dataclass
class TextBlockInfo:
    page: int
    rect: tuple[float, float, float, float]
    text: str
    font_name: str
    font_size: float
    is_fully_embedded: bool  # True if font supports arbitrary edits

@dataclass
class FontCheckResult:
    supported: bool
    font_name: str
    reason: str  # empty if supported, explanation if not

@dataclass
class EditResult:
    success: bool
    error_message: str  # empty on success

@dataclass
class ReplaceAllResult:
    replaced_count: int
    skipped_count: int
    skipped_locations: list[tuple[int, str]]  # (page_index, reason)
```

### 4.4 Font Limitation Dialog

Modal QMessageBox-style dialog shown when font check fails:

- **Title:** "Cannot Edit Text Directly"
- **Icon:** Warning (⚠)
- **Body:** "This text uses a subset font ([font_name]) that only contains the original characters. Direct editing is not possible."
- **Alternative:** "Redact the original text and overlay new text using a standard font (Helvetica). The result will look similar but use a different font."
- **Buttons:** "Cancel" (abort edit), "Redact & Overlay" (apply fallback)

### 4.5 Undo Support

- **Single replace:** description "Replace '[old]' with '[new]'", undo restores original text
- **Replace All:** description "Replace All '[old]' with '[new]' (N replacements)", single undo reverses all
- **Inline edit:** description "Edit text on page [N]", undo restores original
- **Redact & Overlay:** description "Redact and replace text on page [N]" — note: PyMuPDF redaction permanently removes content from the content stream. Undo is implemented by storing the original text content and rect before redaction. Undo removes the overlay text and inserts the original text back as a new text insertion at the same position. The visual result is equivalent to the original, though the PDF internals differ. This is an acceptable trade-off documented in the undo action description.

### 4.6 Error Handling

| Scenario | Behavior |
|----------|----------|
| Font is subset-embedded | Block direct edit, offer Redact & Overlay fallback |
| Replacement text doesn't fit in original rect | Warning: "Replacement text may extend beyond the original area. Continue?" with Yes/No |
| No text at double-click position | No-op (no error shown) |
| Document is read-only | "This file is read-only. Use File > Save As to save a copy." |
| Empty replacement in find-replace | Confirmation: "Remove all instances of '[text]'?" |
| Replace All with mixed fonts | Partial success: "Replaced 5 of 7. 2 skipped (subset font on pages 3, 8)." |

---

## 5. New Files Summary

| File | Type | Purpose |
|------|------|---------|
| `k_pdf/core/text_edit_model.py` | Model | TextBlockInfo, FontCheckResult, EditResult, ReplaceAllResult dataclasses |
| `k_pdf/services/text_edit_engine.py` | Service | PyMuPDF text editing operations (replace, redact, overlay, font check) |
| `k_pdf/presenters/form_creation_presenter.py` | Presenter | Form field placement, popup/panel coordination, undo |
| `k_pdf/presenters/text_edit_presenter.py` | Presenter | Find-replace flow, inline edit flow, font validation |
| `k_pdf/views/form_field_popup.py` | View | Inline quick-config popup for new form fields |
| `k_pdf/views/form_properties_panel.py` | View | Docked advanced property editor for form fields |
| `k_pdf/views/find_replace_bar.py` | View | Two-row find and replace bar widget |

### Modified Files

| File | Changes |
|------|---------|
| `k_pdf/core/annotation_model.py` | Add FORM_* and TEXT_EDIT values to ToolMode enum |
| `k_pdf/services/form_engine.py` | Add create_widget(), delete_widget(), update_widget_properties(), get_widget_at() |
| `k_pdf/views/main_window.py` | Add Form Fields submenu to Tools menu, Edit Text action, Find and Replace action, Form Properties panel dock |
| `k_pdf/views/pdf_viewport.py` | Handle FORM_* tool modes (click-to-place), TEXT_EDIT mode (double-click), form_field_placed signal, text_edit_requested signal |
| `k_pdf/app.py` | Wire new presenters, connect signals |

---

## 6. Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Find and Replace | Ctrl+H |
| Form Properties Panel | F8 |
| Edit Text Mode | Ctrl+E |

---

## 7. Accessibility

- All form field type menu items use icon + text label (never icon-only)
- Form Properties Panel labels all inputs with accessible names
- Font limitation dialog uses text explanation, not color-coded warnings
- Status bar messages describe the active mode in text
- All new interactive elements are keyboard navigable with visible focus indicators
