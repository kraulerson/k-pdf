# Feature 12: Annotation Summary Panel — Implementation Plan

**Date:** 2026-04-02
**Spec:** `docs/superpowers/specs/2026-04-02-feature12-annotation-summary-design.md`
**Branch:** `feature/annotation-summary`
**Depends on:** Features 1, 2, 6, 7 (all complete)

---

## Task Overview

| # | Task | Type | Files |
|---|------|------|-------|
| 1 | AnnotationInfo dataclass | model | `k_pdf/core/annotation_model.py`, `tests/test_annotation_model.py` |
| 2 | AnnotationEngine.get_annotation_info | service | `k_pdf/services/annotation_engine.py`, `tests/test_annotation_engine.py` |
| 3 | AnnotationSummaryPanel view (replace stub) | view | `k_pdf/views/annotation_panel.py`, `tests/test_annotation_summary_panel.py` |
| 4 | AnnotationSummaryPresenter | presenter | `k_pdf/presenters/annotation_summary_presenter.py`, `tests/test_annotation_summary_presenter.py` |
| 5 | MainWindow: add Annotation Panel dock + F6 toggle | view | `k_pdf/views/main_window.py`, `tests/test_views.py` |
| 6 | KPdfApp: wire all signals + integration tests | app | `k_pdf/app.py`, `tests/test_annotation_summary_integration.py` |
| 7 | Mypy overrides + CLAUDE.md update | config | `pyproject.toml`, `CLAUDE.md` |

---

## Task 1: AnnotationInfo Dataclass

### RED — Write failing tests

**File: `tests/test_annotation_model.py`** (append to existing)

```python
class TestAnnotationInfo:
    def test_construction_all_fields(self) -> None:
        info = AnnotationInfo(
            page=2,
            ann_type="Highlight",
            author="Karl",
            content="Important text",
            color=(1.0, 1.0, 0.0),
            rect=(72.0, 100.0, 300.0, 120.0),
        )
        assert info.page == 2
        assert info.ann_type == "Highlight"
        assert info.author == "Karl"
        assert info.content == "Important text"
        assert info.color == (1.0, 1.0, 0.0)
        assert info.rect == (72.0, 100.0, 300.0, 120.0)

    def test_default_values(self) -> None:
        info = AnnotationInfo(page=0, ann_type="Note")
        assert info.author == ""
        assert info.content == ""
        assert info.color == (0.0, 0.0, 0.0)
        assert info.rect == (0.0, 0.0, 0.0, 0.0)
```

### GREEN — Implement

**File: `k_pdf/core/annotation_model.py`** — Add `AnnotationInfo` dataclass.

### REFACTOR — None needed.

---

## Task 2: AnnotationEngine.get_annotation_info

### RED — Write failing tests

**File: `tests/test_annotation_engine.py`** (append to existing)

```python
class TestGetAnnotationInfo:
    def test_highlight_info(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        page = doc[0]
        words = page.get_text("words")
        quads = [pymupdf.Rect(*w[:4]).quad for w in words[:2]]
        annot = page.add_highlight_annot(quads=quads)
        annot.set_colors(stroke=(1.0, 1.0, 0.0))
        annot.set_info(title="TestAuthor")
        annot.update()
        info = engine.get_annotation_info(doc, 0, annot)
        assert info["type_name"] == "Highlight"
        assert info["author"] == "TestAuthor"
        assert info["color"] is not None
        doc.close()

    def test_sticky_note_info(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annot = doc[0].add_text_annot((72, 72), "Test note", icon="Note")
        annot.set_info(title="NoteAuthor")
        annot.update()
        info = engine.get_annotation_info(doc, 0, annot)
        assert info["type_name"] == "Note"
        assert info["content"] == "Test note"
        assert info["author"] == "NoteAuthor"
        doc.close()

    def test_freetext_info(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annot = doc[0].add_freetext_annot(
            (72, 200, 300, 240), "Box text", fontsize=11
        )
        info = engine.get_annotation_info(doc, 0, annot)
        assert info["type_name"] == "Text Box"
        assert info["content"] == "Box text"
        doc.close()
```

### GREEN — Implement

**File: `k_pdf/services/annotation_engine.py`** — Add `get_annotation_info()` method.

PyMuPDF annotation type mapping:
- type 8 (Highlight) -> "Highlight"
- type 9 (Underline) -> "Underline"
- type 10 (StrikeOut) -> "Strikethrough"
- type 0 (Text) -> "Note"
- type 2 (FreeText) -> "Text Box"
- other -> "Unknown"

### REFACTOR — None needed.

---

## Task 3: AnnotationSummaryPanel View

### RED — Write failing tests

**File: `tests/test_annotation_summary_panel.py`** (new)

```python
class TestAnnotationSummaryPanel:
    def test_set_annotations_populates_table(self, qtbot) -> None:
        # Create panel, set 3 annotations, verify 3 rows
    
    def test_set_annotations_columns(self, qtbot) -> None:
        # Verify Page, Type, Author, Preview, Color columns

    def test_clear_shows_empty_state(self, qtbot) -> None:
        # Call clear(), verify empty label visible

    def test_annotation_clicked_signal(self, qtbot) -> None:
        # Click a row, verify signal emitted with correct page_index

    def test_empty_state_on_no_annotations(self, qtbot) -> None:
        # set_annotations([]) shows empty label

    def test_type_column_has_text_label(self, qtbot) -> None:
        # Verify type column shows text like "Highlight", not just icon
    
    def test_color_swatch_present(self, qtbot) -> None:
        # Verify color column has a colored pixmap
    
    def test_preview_truncated(self, qtbot) -> None:
        # Long content truncated to 40 chars + "..."
```

### GREEN — Implement

**File: `k_pdf/views/annotation_panel.py`** — Full QDockWidget with QTableWidget.

### REFACTOR — Extract helper for color swatch creation.

---

## Task 4: AnnotationSummaryPresenter

### RED — Write failing tests

**File: `tests/test_annotation_summary_presenter.py`** (new)

```python
class TestOnDocumentReady:
    def test_scans_pages_and_updates_panel(self) -> None:
    def test_stores_per_tab_annotations(self) -> None:
    def test_no_model_is_noop(self) -> None:

class TestRefreshAnnotations:
    def test_rescans_and_updates_panel(self) -> None:
    def test_no_active_model_clears_panel(self) -> None:

class TestTabSwitch:
    def test_swaps_to_stored_annotations(self) -> None:
    def test_unknown_session_clears_panel(self) -> None:

class TestTabClosed:
    def test_removes_stored_data(self) -> None:

class TestAnnotationClicked:
    def test_navigates_to_page(self) -> None:
    def test_no_viewport_is_noop(self) -> None:
```

### GREEN — Implement

**File: `k_pdf/presenters/annotation_summary_presenter.py`** — New file.

### REFACTOR — None needed.

---

## Task 5: MainWindow — Annotation Panel Dock + F6 Toggle

### RED — Write failing tests

**File: `tests/test_views.py`** (append)

```python
class TestAnnotationPanelToggle:
    def test_annotation_panel_exists(self, qtbot) -> None:
        # MainWindow has annotation_summary_panel property

    def test_annotation_panel_starts_hidden(self, qtbot) -> None:
        # Panel is hidden on construction

    def test_annotation_panel_right_dock(self, qtbot) -> None:
        # Panel is docked on the right side

    def test_f6_shortcut_in_view_menu(self, qtbot) -> None:
        # View menu has "Annotation Panel" action with F6 shortcut
```

### GREEN — Implement

**File: `k_pdf/views/main_window.py`** — Add AnnotationSummaryPanel import, dock widget creation, View menu toggle.

### REFACTOR — None needed.

---

## Task 6: KPdfApp Wiring + Integration Tests

### RED — Write failing tests

**File: `tests/test_annotation_summary_integration.py`** (new)

```python
class TestAnnotationSummaryIntegration:
    def test_panel_shows_annotations_on_load(self) -> None:
    def test_panel_updates_on_annotation_created(self) -> None:
    def test_panel_updates_on_annotation_deleted(self) -> None:
    def test_click_navigates_to_page(self) -> None:
    def test_tab_switch_swaps_annotations(self) -> None:
    def test_empty_document_shows_empty_state(self) -> None:
    def test_panel_toggle_f6(self) -> None:
```

### GREEN — Implement

**File: `k_pdf/app.py`** — Create AnnotationSummaryPresenter, wire signals.

### REFACTOR — None needed.

---

## Task 7: Mypy Overrides + CLAUDE.md Update

### Files

- `pyproject.toml` — add mypy overrides for `k_pdf.views.annotation_panel` and `k_pdf.presenters.annotation_summary_presenter`
- `CLAUDE.md` — update current state to include Feature 12 completion

### Verification

```bash
uv run mypy k_pdf/
uv run pytest --cov=k_pdf --cov-report=term-missing
```

Coverage target: 65%+.
