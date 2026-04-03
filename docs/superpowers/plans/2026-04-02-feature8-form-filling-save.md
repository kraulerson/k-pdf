# Feature 8: AcroForm Filling & Save — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add AcroForm field detection, form filling via Qt widget overlays, Save/Save As file writing, dirty-tab close guard (Save/Discard/Cancel dialog), XFA detection notification, and status bar field count. Replace existing stubs in `services/form_engine.py`. Coordinate save with existing dirty flag from annotations.

**Architecture:** New `FormFieldType` enum and `FormFieldDescriptor` dataclass in `core/form_model.py`. `FormEngine` service replaces stub — detects fields via `page.widgets`, writes values back, saves document via `doc.save()`. `FormPresenter` manages per-tab form widget lifecycle, dirty tracking, and save flow. Qt widget overlays (QLineEdit, QCheckBox, QComboBox) positioned as QGraphicsProxyWidget on the viewport scene. MainWindow gains Save (Ctrl+S) and Save As (Ctrl+Shift+S) actions. TabManager.close_tab() gains dirty-check guard with Save/Discard/Cancel QMessageBox.

**Tech Stack:** Python 3.13, PySide6 6.11, PyMuPDF 1.27, pytest + pytest-qt

**Spec:** `docs/superpowers/specs/2026-04-02-feature8-form-filling-save-design.md`

---

## File Map

**New files:**
- `k_pdf/core/form_model.py` — `FormFieldType` enum, `FormFieldDescriptor` frozen dataclass
- `k_pdf/presenters/form_presenter.py` — `FormPresenter` manages form overlays, save flow, dirty coordination
- `tests/test_form_model.py` — unit tests for form model types
- `tests/test_form_engine.py` — unit tests for FormEngine with real PDF fixtures
- `tests/test_form_presenter.py` — unit tests for FormPresenter with mocked engine
- `tests/test_save_flow.py` — unit tests for save/save-as flow
- `tests/test_form_filling_integration.py` — integration tests through KPdfApp

**Modified files:**
- `k_pdf/services/form_engine.py` — replace stub with full implementation
- `k_pdf/views/main_window.py` — add Save/Save As actions and signals
- `k_pdf/views/pdf_viewport.py` — add form overlay management methods
- `k_pdf/presenters/tab_manager.py` — add dirty-check close guard with Save/Discard/Cancel dialog
- `k_pdf/app.py` — create FormEngine/FormPresenter, wire save signals
- `tests/conftest.py` — add form PDF and XFA PDF fixtures
- `pyproject.toml` — add mypy overrides for new modules
- `CLAUDE.md` — update current state

---

### Task 1: Form Model (core/form_model.py)

**Files:**
- Create: `k_pdf/core/form_model.py`
- Create: `tests/test_form_model.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_form_model.py`:

```python
"""Tests for form field model types."""

from __future__ import annotations

from k_pdf.core.form_model import FormFieldDescriptor, FormFieldType


class TestFormFieldType:
    def test_text_value(self) -> None:
        assert FormFieldType.TEXT.value == "text"

    def test_checkbox_value(self) -> None:
        assert FormFieldType.CHECKBOX.value == "checkbox"

    def test_dropdown_value(self) -> None:
        assert FormFieldType.DROPDOWN.value == "dropdown"

    def test_radio_value(self) -> None:
        assert FormFieldType.RADIO.value == "radio"

    def test_enum_member_count(self) -> None:
        assert len(FormFieldType) == 4


class TestFormFieldDescriptor:
    def test_construction_with_required_fields(self) -> None:
        field = FormFieldDescriptor(
            name="first_name",
            field_type=FormFieldType.TEXT,
            page=0,
            rect=(72.0, 100.0, 300.0, 120.0),
        )
        assert field.name == "first_name"
        assert field.field_type is FormFieldType.TEXT
        assert field.page == 0
        assert field.rect == (72.0, 100.0, 300.0, 120.0)

    def test_default_value_is_empty_string(self) -> None:
        field = FormFieldDescriptor(
            name="f", field_type=FormFieldType.TEXT, page=0, rect=(0, 0, 1, 1)
        )
        assert field.value == ""

    def test_default_options_is_empty_list(self) -> None:
        field = FormFieldDescriptor(
            name="f", field_type=FormFieldType.DROPDOWN, page=0, rect=(0, 0, 1, 1)
        )
        assert field.options == []

    def test_default_read_only_is_false(self) -> None:
        field = FormFieldDescriptor(
            name="f", field_type=FormFieldType.TEXT, page=0, rect=(0, 0, 1, 1)
        )
        assert field.read_only is False

    def test_default_max_length_is_none(self) -> None:
        field = FormFieldDescriptor(
            name="f", field_type=FormFieldType.TEXT, page=0, rect=(0, 0, 1, 1)
        )
        assert field.max_length is None

    def test_frozen_immutable(self) -> None:
        field = FormFieldDescriptor(
            name="f", field_type=FormFieldType.TEXT, page=0, rect=(0, 0, 1, 1)
        )
        import pytest

        with pytest.raises(AttributeError):
            field.name = "changed"  # type: ignore[misc]

    def test_custom_options(self) -> None:
        field = FormFieldDescriptor(
            name="state",
            field_type=FormFieldType.DROPDOWN,
            page=0,
            rect=(0, 0, 1, 1),
            options=["CA", "TX", "NY"],
        )
        assert field.options == ["CA", "TX", "NY"]

    def test_custom_max_length(self) -> None:
        field = FormFieldDescriptor(
            name="zip",
            field_type=FormFieldType.TEXT,
            page=0,
            rect=(0, 0, 1, 1),
            max_length=5,
        )
        assert field.max_length == 5
```

Run: `uv run pytest tests/test_form_model.py -x` — expect ImportError (module does not exist).

- [ ] **Step 2: Write implementation**

Create `k_pdf/core/form_model.py`:

```python
"""Form field data model.

Framework-free data layer for AcroForm field types and descriptors.
Used by FormEngine and FormPresenter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FormFieldType(Enum):
    """AcroForm field widget types."""

    TEXT = "text"
    CHECKBOX = "checkbox"
    DROPDOWN = "dropdown"
    RADIO = "radio"


@dataclass(frozen=True)
class FormFieldDescriptor:
    """Immutable descriptor for a single form field.

    Attributes:
        name: Field name from the PDF form.
        field_type: Widget type to create.
        page: Zero-based page index.
        rect: Bounding rectangle in PDF coordinates (x0, y0, x1, y1).
        value: Current field value.
        options: Choice options for DROPDOWN and RADIO types.
        read_only: Whether the field is marked read-only in the PDF.
        max_length: Maximum character count for text fields.
    """

    name: str
    field_type: FormFieldType
    page: int
    rect: tuple[float, float, float, float]
    value: str = ""
    options: list[str] = field(default_factory=list)
    read_only: bool = False
    max_length: int | None = None
```

Run: `uv run pytest tests/test_form_model.py -x` — expect all pass.

- [ ] **Step 3: Lint/type-check**

Run: `uv run ruff check k_pdf/core/form_model.py` and `uv run mypy k_pdf/core/form_model.py`

---

### Task 2: Test Fixtures — Form PDFs (tests/conftest.py)

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add form_pdf fixture**

Add to `tests/conftest.py`:

```python
@pytest.fixture
def form_pdf(tmp_path: Path) -> Path:
    """Create a PDF with AcroForm text, checkbox, and dropdown fields."""
    path = tmp_path / "form.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(pymupdf.Point(72, 50), "Form Test Document")

    # Text field
    widget = pymupdf.Widget()
    widget.field_name = "full_name"
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.rect = pymupdf.Rect(72, 100, 300, 120)
    widget.field_value = ""
    page.add_widget(widget)

    # Checkbox
    widget2 = pymupdf.Widget()
    widget2.field_name = "agree"
    widget2.field_type = pymupdf.PDF_WIDGET_TYPE_CHECKBOX
    widget2.rect = pymupdf.Rect(72, 140, 92, 160)
    widget2.field_value = "Off"
    page.add_widget(widget2)

    # Dropdown / Choice
    widget3 = pymupdf.Widget()
    widget3.field_name = "country"
    widget3.field_type = pymupdf.PDF_WIDGET_TYPE_COMBOBOX
    widget3.rect = pymupdf.Rect(72, 180, 300, 200)
    widget3.choice_values = ["USA", "Canada", "Mexico"]
    widget3.field_value = "USA"
    page.add_widget(widget3)

    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def readonly_form_pdf(tmp_path: Path) -> Path:
    """Create a form PDF in a read-only file."""
    path = tmp_path / "readonly_form.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    widget = pymupdf.Widget()
    widget.field_name = "name"
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.rect = pymupdf.Rect(72, 100, 300, 120)
    page.add_widget(widget)
    doc.save(str(path))
    doc.close()
    import os

    os.chmod(str(path), 0o444)
    yield path  # type: ignore[misc]
    os.chmod(str(path), 0o644)
```

- [ ] **Step 2: Verify fixtures work**

Run: `uv run pytest tests/conftest.py --co -q` — expect no errors collecting.

---

### Task 3: FormEngine (services/form_engine.py)

**Files:**
- Replace: `k_pdf/services/form_engine.py`
- Create: `tests/test_form_engine.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_form_engine.py`:

```python
"""Tests for FormEngine — AcroForm field detection, writing, and saving."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from k_pdf.core.form_model import FormFieldDescriptor, FormFieldType
from k_pdf.services.form_engine import FormEngine


class TestDetectFields:
    def test_returns_descriptors_for_form_pdf(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        assert len(fields) == 3
        doc.close()

    def test_field_names_match(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        names = {f.name for f in fields}
        assert names == {"full_name", "agree", "country"}
        doc.close()

    def test_field_types_correct(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        type_map = {f.name: f.field_type for f in fields}
        assert type_map["full_name"] is FormFieldType.TEXT
        assert type_map["agree"] is FormFieldType.CHECKBOX
        assert type_map["country"] is FormFieldType.DROPDOWN
        doc.close()

    def test_dropdown_has_options(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        country = next(f for f in fields if f.name == "country")
        assert "USA" in country.options
        assert "Canada" in country.options
        doc.close()

    def test_returns_empty_for_non_form_pdf(self, valid_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(valid_pdf))
        fields = engine.detect_fields(doc)
        assert fields == []
        doc.close()

    def test_field_rect_is_tuple(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        for f in fields:
            assert isinstance(f.rect, tuple)
            assert len(f.rect) == 4
        doc.close()

    def test_field_page_is_zero(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        for f in fields:
            assert f.page == 0
        doc.close()


class TestIsXfaForm:
    def test_returns_false_for_acroform(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        assert engine.is_xfa_form(doc) is False
        doc.close()

    def test_returns_false_for_non_form(self, valid_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(valid_pdf))
        assert engine.is_xfa_form(doc) is False
        doc.close()


class TestWriteFields:
    def test_writes_text_field_value(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"full_name": "Karl Raulerson"})
        # Re-read to verify
        fields = engine.detect_fields(doc)
        name_field = next(f for f in fields if f.name == "full_name")
        assert name_field.value == "Karl Raulerson"
        doc.close()

    def test_writes_checkbox_value(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"agree": "Yes"})
        fields = engine.detect_fields(doc)
        agree_field = next(f for f in fields if f.name == "agree")
        assert agree_field.value == "Yes"
        doc.close()

    def test_ignores_unknown_field_names(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        # Should not raise
        engine.write_fields(doc, {"nonexistent_field": "value"})
        doc.close()


class TestSaveDocument:
    def test_save_creates_file(self, form_pdf: Path, tmp_path: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"full_name": "Test User"})
        output = tmp_path / "saved.pdf"
        engine.save_document(doc, output, is_new_path=True)
        assert output.exists()
        doc.close()

    def test_save_persists_field_values(self, form_pdf: Path, tmp_path: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"full_name": "Saved Value"})
        output = tmp_path / "persisted.pdf"
        engine.save_document(doc, output, is_new_path=True)
        doc.close()

        # Reopen and verify
        doc2 = pymupdf.open(str(output))
        fields = engine.detect_fields(doc2)
        name_field = next(f for f in fields if f.name == "full_name")
        assert name_field.value == "Saved Value"
        doc2.close()

    def test_save_incremental_to_same_path(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"full_name": "Incremental"})
        # Save back to same path (incremental)
        engine.save_document(doc, form_pdf, is_new_path=False)
        doc.close()

        doc2 = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc2)
        name_field = next(f for f in fields if f.name == "full_name")
        assert name_field.value == "Incremental"
        doc2.close()

    def test_save_raises_on_bad_path(self, form_pdf: Path, tmp_path: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        bad_path = tmp_path / "nonexistent_dir" / "out.pdf"
        with pytest.raises(Exception):
            engine.save_document(doc, bad_path, is_new_path=True)
        doc.close()


class TestGetFieldValue:
    def test_reads_text_field(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        page = doc[0]
        for widget in page.widgets():
            if widget.field_name == "country":
                val = engine.get_field_value(widget)
                assert val == "USA"
                break
        doc.close()
```

Run: `uv run pytest tests/test_form_engine.py -x` — expect failures (FormEngine has no methods).

- [ ] **Step 2: Write implementation**

Replace `k_pdf/services/form_engine.py`:

```python
"""AcroForm field detection, filling, and document saving.

PyMuPDF form operations isolated here per AGPL containment rule.
No other layer imports fitz/pymupdf directly for form operations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pymupdf

from k_pdf.core.form_model import FormFieldDescriptor, FormFieldType

logger = logging.getLogger("k_pdf.services.form_engine")

# Map PyMuPDF widget types to our enum
_WIDGET_TYPE_MAP: dict[int, FormFieldType] = {
    pymupdf.PDF_WIDGET_TYPE_TEXT: FormFieldType.TEXT,
    pymupdf.PDF_WIDGET_TYPE_CHECKBOX: FormFieldType.CHECKBOX,
    pymupdf.PDF_WIDGET_TYPE_COMBOBOX: FormFieldType.DROPDOWN,
    pymupdf.PDF_WIDGET_TYPE_LISTBOX: FormFieldType.DROPDOWN,
    pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON: FormFieldType.RADIO,
}


class FormEngine:
    """Wraps PyMuPDF form field operations.

    All methods take a doc_handle (pymupdf.Document).
    The caller (FormPresenter) never imports pymupdf directly.
    """

    def detect_fields(self, doc_handle: Any) -> list[FormFieldDescriptor]:
        """Detect all AcroForm fields across all pages.

        Args:
            doc_handle: A pymupdf.Document handle.

        Returns:
            List of FormFieldDescriptor for each detected field.
            Empty list if no AcroForm fields found.
        """
        fields: list[FormFieldDescriptor] = []
        for page_index in range(doc_handle.page_count):
            page = doc_handle[page_index]
            for widget in page.widgets():
                field_type = _WIDGET_TYPE_MAP.get(widget.field_type)
                if field_type is None:
                    logger.debug(
                        "Skipping unsupported widget type %d on page %d",
                        widget.field_type,
                        page_index,
                    )
                    continue

                rect = widget.rect
                options: list[str] = []
                if hasattr(widget, "choice_values") and widget.choice_values:
                    options = list(widget.choice_values)

                fields.append(
                    FormFieldDescriptor(
                        name=widget.field_name or f"unnamed_{page_index}_{len(fields)}",
                        field_type=field_type,
                        page=page_index,
                        rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                        value=str(widget.field_value or ""),
                        options=options,
                        read_only=bool(widget.field_flags & 1),
                        max_length=widget.text_maxlen if widget.text_maxlen > 0 else None,
                    )
                )

        logger.debug("Detected %d form fields", len(fields))
        return fields

    def is_xfa_form(self, doc_handle: Any) -> bool:
        """Check if the document contains XFA form data.

        Args:
            doc_handle: A pymupdf.Document handle.

        Returns:
            True if the document has XFA data.
        """
        try:
            xfa = doc_handle.xfa
            return bool(xfa)
        except Exception:
            return False

    def write_fields(self, doc_handle: Any, field_values: dict[str, str]) -> None:
        """Write field values back into the PDF document.

        Args:
            doc_handle: A pymupdf.Document handle.
            field_values: Mapping of field_name -> new value.
        """
        for page_index in range(doc_handle.page_count):
            page = doc_handle[page_index]
            for widget in page.widgets():
                name = widget.field_name
                if name in field_values:
                    widget.field_value = field_values[name]
                    widget.update()
                    logger.debug("Set field '%s' on page %d", name, page_index)

    def save_document(
        self,
        doc_handle: Any,
        path: Path,
        is_new_path: bool = False,
    ) -> None:
        """Save the document to disk.

        Args:
            doc_handle: A pymupdf.Document handle.
            path: Output file path.
            is_new_path: True for Save As (full write), False for Save (incremental).

        Raises:
            Exception: If the save fails (disk full, permission denied, etc.).
        """
        if is_new_path:
            doc_handle.save(str(path))
        else:
            doc_handle.save(
                str(path),
                incremental=True,
                encryption=pymupdf.PDF_ENCRYPT_KEEP,
            )
        logger.debug("Saved document to %s (new_path=%s)", path, is_new_path)

    def get_field_value(self, widget: Any) -> str:
        """Read the current value from a PyMuPDF widget.

        Args:
            widget: A pymupdf Widget object.

        Returns:
            The field value as a string.
        """
        return str(widget.field_value or "")
```

Run: `uv run pytest tests/test_form_engine.py -x` — expect all pass.

- [ ] **Step 3: Lint/type-check**

Run: `uv run ruff check k_pdf/services/form_engine.py` and `uv run mypy k_pdf/services/form_engine.py`

Add mypy override to `pyproject.toml` if needed:

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.services.form_engine"]
disable_error_code = ["no-untyped-call"]
```

---

### Task 4: Save/Save As Menu Actions (views/main_window.py)

**Files:**
- Modify: `k_pdf/views/main_window.py`
- Modify: `tests/test_views.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_views.py`:

```python
class TestMainWindowSaveActions:
    def test_save_signal_exists(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert hasattr(window, "save_requested")

    def test_save_as_signal_exists(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert hasattr(window, "save_as_requested")

    def test_save_action_shortcut(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert window._save_action.shortcut().toString() == "Ctrl+S"

    def test_save_as_action_shortcut(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert window._save_as_action.shortcut().toString() == "Ctrl+Shift+S"

    def test_save_action_initially_disabled(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert not window._save_action.isEnabled()

    def test_save_as_action_initially_disabled(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert not window._save_as_action.isEnabled()

    def test_set_save_enabled(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_save_enabled(True)
        assert window._save_action.isEnabled()
        assert window._save_as_action.isEnabled()

    def test_set_save_enabled_false(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_save_enabled(True)
        window.set_save_enabled(False)
        assert not window._save_action.isEnabled()
        assert not window._save_as_action.isEnabled()
```

Run: `uv run pytest tests/test_views.py::TestMainWindowSaveActions -x` — expect failures.

- [ ] **Step 2: Write implementation**

In `k_pdf/views/main_window.py`:

Add signals to class body:

```python
save_requested = Signal()
save_as_requested = Signal()
```

In `_setup_menus()`, after the Open action and before Close Tab separator, add:

```python
file_menu.addSeparator()

self._save_action = QAction("&Save", self)
self._save_action.setShortcut(QKeySequence("Ctrl+S"))
self._save_action.setEnabled(False)
self._save_action.triggered.connect(self.save_requested.emit)
file_menu.addAction(self._save_action)

self._save_as_action = QAction("Save &As...", self)
self._save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
self._save_as_action.setEnabled(False)
self._save_as_action.triggered.connect(self.save_as_requested.emit)
file_menu.addAction(self._save_as_action)
```

Add method:

```python
def set_save_enabled(self, enabled: bool) -> None:
    """Enable or disable Save and Save As actions.

    Args:
        enabled: True to enable, False to disable.
    """
    self._save_action.setEnabled(enabled)
    self._save_as_action.setEnabled(enabled)
```

Run: `uv run pytest tests/test_views.py::TestMainWindowSaveActions -x` — expect all pass.

- [ ] **Step 3: Lint/type-check**

Run: `uv run ruff check k_pdf/views/main_window.py` and `uv run mypy k_pdf/views/main_window.py`

---

### Task 5: Viewport Form Overlay Methods (views/pdf_viewport.py)

**Files:**
- Modify: `k_pdf/views/pdf_viewport.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_views.py`:

```python
class TestViewportFormOverlays:
    def test_add_form_overlay(self, qtbot) -> None:
        viewport = PdfViewport()
        qtbot.addWidget(viewport)
        from PySide6.QtWidgets import QLineEdit

        widget = QLineEdit()
        viewport.add_form_overlay(widget, page_index=0, rect=(72.0, 100.0, 300.0, 120.0))
        assert len(viewport._form_overlays) == 1

    def test_remove_form_overlays(self, qtbot) -> None:
        viewport = PdfViewport()
        qtbot.addWidget(viewport)
        from PySide6.QtWidgets import QLineEdit

        widget = QLineEdit()
        viewport.add_form_overlay(widget, page_index=0, rect=(72.0, 100.0, 300.0, 120.0))
        viewport.remove_form_overlays()
        assert len(viewport._form_overlays) == 0
```

Run: `uv run pytest tests/test_views.py::TestViewportFormOverlays -x` — expect failures.

- [ ] **Step 2: Write implementation**

Add to `PdfViewport.__init__`:

```python
self._form_overlays: list[QGraphicsProxyWidget] = []
```

Add import at top:

```python
from PySide6.QtWidgets import QGraphicsProxyWidget
```

Add methods to `PdfViewport`:

```python
def add_form_overlay(
    self,
    widget: QWidget,
    page_index: int,
    rect: tuple[float, float, float, float],
    zoom: float = 1.0,
) -> None:
    """Add a form field widget overlay to the scene.

    Args:
        widget: The Qt widget (QLineEdit, QCheckBox, QComboBox).
        page_index: Zero-based page index.
        rect: Bounding rectangle (x0, y0, x1, y1) in PDF coordinates.
        zoom: Current zoom factor.
    """
    if page_index < 0 or page_index >= len(self._page_y_offsets):
        return

    x0, y0, x1, y1 = rect
    y_base = self._page_y_offsets[page_index]

    proxy = self._scene.addWidget(widget)
    proxy.setPos(x0 * zoom, y_base + y0 * zoom)
    proxy.setZValue(20)
    widget.setFixedSize(int((x1 - x0) * zoom), int((y1 - y0) * zoom))
    self._form_overlays.append(proxy)

def remove_form_overlays(self) -> None:
    """Remove all form overlay proxy widgets from the scene."""
    for proxy in self._form_overlays:
        self._scene.removeItem(proxy)
    self._form_overlays.clear()

def reposition_form_overlays(
    self,
    descriptors: list[tuple[QWidget, int, tuple[float, float, float, float]]],
    zoom: float,
) -> None:
    """Recalculate positions of all form overlays for new zoom.

    Args:
        descriptors: List of (widget, page_index, rect) tuples.
        zoom: New zoom factor.
    """
    self.remove_form_overlays()
    for widget, page_index, rect in descriptors:
        self.add_form_overlay(widget, page_index, rect, zoom)
```

Run: `uv run pytest tests/test_views.py::TestViewportFormOverlays -x` — expect all pass.

- [ ] **Step 3: Lint/type-check**

Run: `uv run ruff check k_pdf/views/pdf_viewport.py` and `uv run mypy k_pdf/views/pdf_viewport.py`

---

### Task 6: FormPresenter (presenters/form_presenter.py)

**Files:**
- Create: `k_pdf/presenters/form_presenter.py`
- Create: `tests/test_form_presenter.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_form_presenter.py`:

```python
"""Tests for FormPresenter — form lifecycle, save flow, dirty coordination."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.core.form_model import FormFieldDescriptor, FormFieldType
from k_pdf.presenters.form_presenter import FormPresenter
from k_pdf.services.form_engine import FormEngine


def _make_model(tmp_path: Path, dirty: bool = False) -> DocumentModel:
    """Create a minimal DocumentModel for testing."""
    path = tmp_path / "test.pdf"
    path.touch()
    return DocumentModel(
        file_path=path,
        doc_handle=MagicMock(),
        metadata=DocumentMetadata(
            file_path=path,
            page_count=1,
            title=None,
            author=None,
            has_forms=True,
            has_outline=False,
            has_javascript=False,
            is_encrypted=False,
            file_size_bytes=1024,
        ),
        pages=[PageInfo(index=0, width=612, height=792, rotation=0, has_text=True, annotation_count=0)],
        dirty=dirty,
    )


class TestOnDocumentOpened:
    def test_emits_form_detected_with_count(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        engine.detect_fields.return_value = [
            FormFieldDescriptor(name="f1", field_type=FormFieldType.TEXT, page=0, rect=(0, 0, 1, 1)),
            FormFieldDescriptor(name="f2", field_type=FormFieldType.CHECKBOX, page=0, rect=(0, 0, 1, 1)),
        ]
        engine.is_xfa_form.return_value = False
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)
        qtbot.addWidget(presenter)

        model = _make_model(tmp_path)
        signals = []
        presenter.form_detected.connect(signals.append)
        presenter.on_document_opened(model.session_id, model)
        assert signals == [2]

    def test_xfa_emits_xfa_detected(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        engine.is_xfa_form.return_value = True
        engine.detect_fields.return_value = []
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)
        qtbot.addWidget(presenter)

        model = _make_model(tmp_path)
        signals = []
        presenter.xfa_detected.connect(signals.append)
        presenter.on_document_opened(model.session_id, model)
        assert len(signals) == 1

    def test_no_fields_no_signal(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        engine.is_xfa_form.return_value = False
        engine.detect_fields.return_value = []
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)
        qtbot.addWidget(presenter)

        model = _make_model(tmp_path)
        signals = []
        presenter.form_detected.connect(signals.append)
        presenter.on_document_opened(model.session_id, model)
        assert signals == []


class TestOnFieldChanged:
    def test_sets_dirty_flag(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)
        qtbot.addWidget(presenter)

        model = _make_model(tmp_path)
        presenter._models[model.session_id] = model
        presenter.on_field_changed(model.session_id, "f1", "new_val")
        assert model.dirty is True

    def test_emits_dirty_changed(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)
        qtbot.addWidget(presenter)

        model = _make_model(tmp_path)
        presenter._models[model.session_id] = model
        signals = []
        presenter.dirty_changed.connect(signals.append)
        presenter.on_field_changed(model.session_id, "f1", "val")
        assert signals == [True]


class TestSave:
    def test_save_calls_engine(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)
        qtbot.addWidget(presenter)

        model = _make_model(tmp_path, dirty=True)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {"f1": "val1"}

        presenter.save(model.session_id)
        engine.write_fields.assert_called_once()
        engine.save_document.assert_called_once()

    def test_save_clears_dirty(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)
        qtbot.addWidget(presenter)

        model = _make_model(tmp_path, dirty=True)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {}

        presenter.save(model.session_id)
        assert model.dirty is False

    def test_save_emits_succeeded(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)
        qtbot.addWidget(presenter)

        model = _make_model(tmp_path, dirty=True)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {}

        signals = []
        presenter.save_succeeded.connect(lambda: signals.append(True))
        presenter.save(model.session_id)
        assert signals == [True]

    def test_save_emits_failed_on_error(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        engine.save_document.side_effect = PermissionError("denied")
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)
        qtbot.addWidget(presenter)

        model = _make_model(tmp_path, dirty=True)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {}

        signals = []
        presenter.save_failed.connect(signals.append)
        presenter.save(model.session_id)
        assert len(signals) == 1
        assert "denied" in signals[0]


class TestSaveAs:
    def test_save_as_writes_to_new_path(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)
        qtbot.addWidget(presenter)

        model = _make_model(tmp_path, dirty=True)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {}

        new_path = tmp_path / "copy.pdf"
        presenter.save_as(model.session_id, new_path)
        engine.save_document.assert_called_once_with(
            model.doc_handle, new_path, is_new_path=True
        )


class TestOnTabClosed:
    def test_cleanup_removes_state(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)
        qtbot.addWidget(presenter)

        model = _make_model(tmp_path)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {}
        presenter.on_tab_closed(model.session_id)
        assert model.session_id not in presenter._models
        assert model.session_id not in presenter._field_values
```

Run: `uv run pytest tests/test_form_presenter.py -x` — expect ImportError.

- [ ] **Step 2: Write implementation**

Create `k_pdf/presenters/form_presenter.py`:

```python
"""Form presenter — manages form field overlays, save flow, and dirty coordination.

Detects AcroForm fields on document open, creates Qt widget overlays,
tracks per-tab field values, and coordinates save/save-as operations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from k_pdf.core.document_model import DocumentModel
from k_pdf.core.form_model import FormFieldDescriptor, FormFieldType
from k_pdf.services.form_engine import FormEngine

logger = logging.getLogger("k_pdf.presenters.form_presenter")


class FormPresenter(QObject):
    """Coordinates form field detection, overlay lifecycle, and save flow."""

    dirty_changed = Signal(bool)
    form_detected = Signal(int)  # field count
    xfa_detected = Signal(str)  # notification message
    save_succeeded = Signal()
    save_failed = Signal(str)  # error message

    def __init__(
        self,
        form_engine: FormEngine,
        tab_manager: Any,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the form presenter.

        Args:
            form_engine: The FormEngine service.
            tab_manager: The TabManager for accessing active tab state.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._engine = form_engine
        self._tab_manager = tab_manager

        # Per-session state
        self._models: dict[str, DocumentModel] = {}
        self._field_values: dict[str, dict[str, str]] = {}
        self._field_descriptors: dict[str, list[FormFieldDescriptor]] = {}

    def on_document_opened(self, session_id: str, model: DocumentModel) -> None:
        """Handle document open — detect form fields and create overlays.

        Args:
            session_id: The tab session ID.
            model: The document model.
        """
        self._models[session_id] = model

        # Check for XFA forms first
        if self._engine.is_xfa_form(model.doc_handle):
            self.xfa_detected.emit(
                "XFA dynamic forms not supported. Only AcroForms supported."
            )
            return

        # Detect AcroForm fields
        fields = self._engine.detect_fields(model.doc_handle)
        if not fields:
            return

        self._field_descriptors[session_id] = fields
        self._field_values[session_id] = {f.name: f.value for f in fields}

        self.form_detected.emit(len(fields))
        logger.debug("Detected %d form fields for session %s", len(fields), session_id)

    def on_field_changed(self, session_id: str, field_name: str, value: Any) -> None:
        """Handle form field value change.

        Args:
            session_id: The tab session ID.
            field_name: The changed field name.
            value: The new value.
        """
        model = self._models.get(session_id)
        if model is None:
            return

        if session_id not in self._field_values:
            self._field_values[session_id] = {}
        self._field_values[session_id][field_name] = str(value)

        model.dirty = True
        self.dirty_changed.emit(True)

    def save(self, session_id: str) -> None:
        """Save the document (form values + file).

        Args:
            session_id: The tab session ID.
        """
        model = self._models.get(session_id)
        if model is None:
            return

        field_values = self._field_values.get(session_id, {})
        try:
            self._engine.write_fields(model.doc_handle, field_values)
            self._engine.save_document(model.doc_handle, model.file_path, is_new_path=False)
            model.dirty = False
            self.dirty_changed.emit(False)
            self.save_succeeded.emit()
            logger.debug("Saved document for session %s", session_id)
        except Exception as e:
            error_msg = (
                f"Could not save to {model.file_path}. {e}. "
                "Try File > Save As to save to a different location."
            )
            self.save_failed.emit(error_msg)
            logger.warning("Save failed for session %s: %s", session_id, e)

    def save_as(self, session_id: str, new_path: Path) -> None:
        """Save the document to a new path.

        Args:
            session_id: The tab session ID.
            new_path: The target file path.
        """
        model = self._models.get(session_id)
        if model is None:
            return

        field_values = self._field_values.get(session_id, {})
        try:
            self._engine.write_fields(model.doc_handle, field_values)
            self._engine.save_document(model.doc_handle, new_path, is_new_path=True)
            model.file_path = new_path
            model.dirty = False
            self.dirty_changed.emit(False)
            self.save_succeeded.emit()
            logger.debug("Saved document as %s for session %s", new_path, session_id)
        except Exception as e:
            error_msg = (
                f"Could not save to {new_path}. {e}. "
                "Try a different location."
            )
            self.save_failed.emit(error_msg)

    def on_tab_switched(self, session_id: str) -> None:
        """Handle tab switch — show/hide form overlays.

        Args:
            session_id: The new active tab's session ID.
        """
        # Form overlays are managed per-viewport by the viewport itself.
        # This method exists for future per-tab state management.
        pass

    def on_tab_closed(self, session_id: str) -> None:
        """Clean up per-tab form state.

        Args:
            session_id: The closed tab's session ID.
        """
        self._models.pop(session_id, None)
        self._field_values.pop(session_id, None)
        self._field_descriptors.pop(session_id, None)

    def get_field_descriptors(self, session_id: str) -> list[FormFieldDescriptor]:
        """Return the form field descriptors for a session.

        Args:
            session_id: The tab session ID.

        Returns:
            List of descriptors, or empty list.
        """
        return self._field_descriptors.get(session_id, [])

    def has_form_fields(self, session_id: str) -> bool:
        """Check if a session has form fields.

        Args:
            session_id: The tab session ID.

        Returns:
            True if the session has detected form fields.
        """
        return session_id in self._field_descriptors and len(self._field_descriptors[session_id]) > 0
```

Run: `uv run pytest tests/test_form_presenter.py -x` — expect all pass.

- [ ] **Step 3: Lint/type-check**

Run: `uv run ruff check k_pdf/presenters/form_presenter.py` and `uv run mypy k_pdf/presenters/form_presenter.py`

Add mypy override to `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.presenters.form_presenter"]
disable_error_code = ["misc"]
```

---

### Task 7: Dirty Close Guard in TabManager (presenters/tab_manager.py)

**Files:**
- Modify: `k_pdf/presenters/tab_manager.py`
- Modify: `tests/test_tab_manager.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tab_manager.py`:

```python
class TestDirtyCloseGuard:
    def test_close_guard_signal_exists(self, qtbot) -> None:
        from k_pdf.presenters.tab_manager import TabManager

        tab_widget = QTabWidget()
        qtbot.addWidget(tab_widget)
        recent = MagicMock()
        tm = TabManager(tab_widget=tab_widget, recent_files=recent)
        assert hasattr(tm, "close_guard_requested")

    def test_close_tab_emits_guard_when_dirty(self, qtbot) -> None:
        from k_pdf.presenters.tab_manager import TabContext, TabManager

        tab_widget = QTabWidget()
        qtbot.addWidget(tab_widget)
        recent = MagicMock()
        tm = TabManager(tab_widget=tab_widget, recent_files=recent)

        # Setup a fake tab with dirty model
        from k_pdf.views.pdf_viewport import PdfViewport

        viewport = PdfViewport()
        qtbot.addWidget(viewport)
        presenter = MagicMock()
        model = MagicMock()
        model.dirty = True
        presenter.model = model
        ctx = TabContext(session_id="test-dirty")
        ctx.presenter = presenter
        ctx.viewport = viewport
        tab_widget.addTab(viewport, "Test")
        tm._tabs["test-dirty"] = ctx

        signals = []
        tm.close_guard_requested.connect(signals.append)
        tm.close_tab("test-dirty")
        assert signals == ["test-dirty"]

    def test_close_tab_no_guard_when_clean(self, qtbot) -> None:
        from k_pdf.presenters.tab_manager import TabContext, TabManager

        tab_widget = QTabWidget()
        qtbot.addWidget(tab_widget)
        recent = MagicMock()
        tm = TabManager(tab_widget=tab_widget, recent_files=recent)

        from k_pdf.views.pdf_viewport import PdfViewport

        viewport = PdfViewport()
        qtbot.addWidget(viewport)
        presenter = MagicMock()
        model = MagicMock()
        model.dirty = False
        presenter.model = model
        ctx = TabContext(session_id="test-clean")
        ctx.presenter = presenter
        ctx.viewport = viewport
        tab_widget.addTab(viewport, "Test")
        tm._tabs["test-clean"] = ctx

        signals = []
        tm.close_guard_requested.connect(signals.append)
        tm.close_tab("test-clean")
        assert signals == []
```

Run: `uv run pytest tests/test_tab_manager.py::TestDirtyCloseGuard -x` — expect failures.

- [ ] **Step 2: Write implementation**

In `k_pdf/presenters/tab_manager.py`:

Add signal:

```python
close_guard_requested = Signal(str)  # session_id — emitted when dirty tab close attempted
```

Modify `close_tab()` to check dirty flag before closing:

```python
def close_tab(self, session_id: str) -> None:
    """Close a tab and clean up its resources.

    If the document has unsaved changes (dirty=True), emits
    close_guard_requested instead of closing. The app layer
    handles the Save/Discard/Cancel dialog and calls
    force_close_tab() or save-then-close.

    Args:
        session_id: The session ID of the tab to close.
    """
    ctx = self._tabs.get(session_id)
    if ctx is None:
        return

    # Check dirty flag — defer to app layer for save dialog
    if ctx.presenter is not None and ctx.presenter.model is not None:
        if ctx.presenter.model.dirty:
            self.close_guard_requested.connect  # signal exists
            self.close_guard_requested.emit(session_id)
            return

    self.force_close_tab(session_id)

def force_close_tab(self, session_id: str) -> None:
    """Close a tab unconditionally (after save or discard).

    Args:
        session_id: The session ID of the tab to close.
    """
    ctx = self._tabs.get(session_id)
    if ctx is None:
        return

    self.tab_closed.emit(session_id)

    if ctx.presenter is not None:
        ctx.presenter.shutdown()

    if ctx.viewport is not None:
        idx = self._tab_widget.indexOf(ctx.viewport)
        if idx >= 0:
            self._tab_widget.removeTab(idx)

    if ctx.resolved_path is not None:
        self._open_paths.pop(ctx.resolved_path, None)
    del self._tabs[session_id]

    self.tab_count_changed.emit(len(self._tabs))
```

Run: `uv run pytest tests/test_tab_manager.py -x` — expect all pass.

- [ ] **Step 3: Lint/type-check**

Run: `uv run ruff check k_pdf/presenters/tab_manager.py` and `uv run mypy k_pdf/presenters/tab_manager.py`

---

### Task 8: App Wiring (app.py)

**Files:**
- Modify: `k_pdf/app.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_save_flow.py`:

```python
"""Tests for save flow integration through KPdfApp."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox


class TestSaveFlowWiring:
    def test_app_has_form_presenter(self, qtbot) -> None:
        from k_pdf.app import KPdfApp

        app = QApplication.instance() or QApplication([])
        kapp = KPdfApp(app)
        qtbot.addWidget(kapp.window)
        assert hasattr(kapp, "_form_presenter")

    def test_app_has_form_engine(self, qtbot) -> None:
        from k_pdf.app import KPdfApp

        app = QApplication.instance() or QApplication([])
        kapp = KPdfApp(app)
        qtbot.addWidget(kapp.window)
        assert hasattr(kapp, "_form_engine")

    def test_save_enabled_after_document_open(self, qtbot, form_pdf: Path) -> None:
        from k_pdf.app import KPdfApp

        app = QApplication.instance() or QApplication([])
        kapp = KPdfApp(app)
        qtbot.addWidget(kapp.window)
        kapp.tab_manager.open_file(form_pdf)
        qtbot.waitUntil(
            lambda: kapp.window._save_action.isEnabled(), timeout=3000
        )
        assert kapp.window._save_action.isEnabled()


class TestDirtyCloseDialog:
    @patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Discard)
    def test_discard_closes_tab(self, mock_exec, qtbot, form_pdf: Path) -> None:
        from k_pdf.app import KPdfApp

        app = QApplication.instance() or QApplication([])
        kapp = KPdfApp(app)
        qtbot.addWidget(kapp.window)
        kapp.tab_manager.open_file(form_pdf)
        qtbot.waitUntil(
            lambda: kapp.tab_manager.active_session_id is not None, timeout=3000
        )
        sid = kapp.tab_manager.active_session_id
        # Mark dirty
        presenter = kapp.tab_manager.get_active_presenter()
        if presenter and presenter.model:
            presenter.model.dirty = True
        kapp.tab_manager.close_tab(sid)
        # Discard was chosen, tab should close
        assert sid not in kapp.tab_manager._tabs
```

Run: `uv run pytest tests/test_save_flow.py -x` — expect failures.

- [ ] **Step 2: Write implementation**

Modify `k_pdf/app.py`:

Add imports:

```python
from PySide6.QtWidgets import QFileDialog, QMessageBox
from k_pdf.presenters.form_presenter import FormPresenter
from k_pdf.services.form_engine import FormEngine
```

In `__init__`, after annotation setup:

```python
self._form_engine = FormEngine()
self._form_presenter = FormPresenter(
    form_engine=self._form_engine,
    tab_manager=self._tab_manager,
)
```

In `_connect_signals()`, add form wiring:

```python
# Form wiring
self._tab_manager.document_ready.connect(self._on_document_ready_form)
self._window.save_requested.connect(self._on_save_requested)
self._window.save_as_requested.connect(self._on_save_as_requested)
self._form_presenter.form_detected.connect(self._on_form_detected)
self._form_presenter.xfa_detected.connect(self._on_xfa_detected)
self._form_presenter.dirty_changed.connect(self._on_form_dirty_changed)
self._form_presenter.save_succeeded.connect(self._on_save_succeeded)
self._form_presenter.save_failed.connect(self._on_save_failed)
self._tab_manager.tab_closed.connect(self._form_presenter.on_tab_closed)
self._tab_manager.close_guard_requested.connect(self._on_close_guard)
```

Add handler methods:

```python
# --- Form / Save handlers ---

def _on_document_ready_form(self, session_id: str, model: object) -> None:
    """Wire form detection for a newly loaded document."""
    from k_pdf.core.document_model import DocumentModel

    if isinstance(model, DocumentModel):
        self._form_presenter.on_document_opened(session_id, model)
        self._window.set_save_enabled(True)

def _on_save_requested(self) -> None:
    """Handle File > Save."""
    sid = self._tab_manager.active_session_id
    if sid is not None:
        self._form_presenter.save(sid)

def _on_save_as_requested(self) -> None:
    """Handle File > Save As — show file picker then save."""
    sid = self._tab_manager.active_session_id
    if sid is None:
        return
    path, _ = QFileDialog.getSaveFileName(
        self._window,
        "Save As",
        "",
        "PDF Files (*.pdf);;All Files (*)",
    )
    if path:
        self._form_presenter.save_as(sid, Path(path))

def _on_form_detected(self, count: int) -> None:
    """Show form field count in status bar."""
    self._window.update_status_message(
        f"This document contains {count} form field{'s' if count != 1 else ''}"
    )

def _on_xfa_detected(self, message: str) -> None:
    """Show XFA notification in status bar."""
    self._window.update_status_message(message)

def _on_form_dirty_changed(self, dirty: bool) -> None:
    """Update tab title with dirty indicator from form changes."""
    presenter = self._tab_manager.get_active_presenter()
    viewport = self._tab_manager.get_active_viewport()
    if presenter is not None and presenter.model is not None and viewport is not None:
        name = presenter.model.file_path.name
        title = f"* {name}" if dirty else name
        idx = self._window.tab_widget.indexOf(viewport)
        if idx >= 0:
            self._window.tab_widget.setTabText(idx, title)

def _on_save_succeeded(self) -> None:
    """Handle successful save."""
    self._window.update_status_message("Document saved")
    # Update tab title to remove dirty indicator
    self._on_form_dirty_changed(False)

def _on_save_failed(self, error: str) -> None:
    """Handle save failure — show error dialog."""
    self._window.show_error("Save Failed", error)

def _on_close_guard(self, session_id: str) -> None:
    """Show Save/Discard/Cancel dialog for dirty tab close."""
    msg_box = QMessageBox(self._window)
    msg_box.setWindowTitle("Unsaved Changes")
    msg_box.setText("This document has unsaved changes.")
    msg_box.setInformativeText("Do you want to save before closing?")
    msg_box.setStandardButtons(
        QMessageBox.StandardButton.Save
        | QMessageBox.StandardButton.Discard
        | QMessageBox.StandardButton.Cancel
    )
    msg_box.setDefaultButton(QMessageBox.StandardButton.Save)
    result = msg_box.exec()

    if result == QMessageBox.StandardButton.Save:
        self._form_presenter.save(session_id)
        # If save succeeded (dirty cleared), close the tab
        ctx = self._tab_manager._tabs.get(session_id)
        if ctx and ctx.presenter and ctx.presenter.model and not ctx.presenter.model.dirty:
            self._tab_manager.force_close_tab(session_id)
    elif result == QMessageBox.StandardButton.Discard:
        self._tab_manager.force_close_tab(session_id)
    # Cancel: do nothing, tab stays open
```

Also update `_on_close_current_tab` to use the same guard-aware flow (it already calls `close_tab` which now has the guard).

Update `shutdown`:

```python
def shutdown(self) -> None:
    """Clean up resources before exit."""
    self._annotation_toolbar.hide()
    self._note_editor.hide()
    self._search_presenter.shutdown()
    self._nav_presenter.shutdown()
    self._tab_manager.shutdown()
```

Run: `uv run pytest tests/test_save_flow.py -x` — expect all pass.

- [ ] **Step 3: Lint/type-check**

Run: `uv run ruff check k_pdf/app.py` and `uv run mypy k_pdf/app.py`

---

### Task 9: Integration Tests (tests/test_form_filling_integration.py)

**Files:**
- Create: `tests/test_form_filling_integration.py`

- [ ] **Step 1: Write integration tests**

Create `tests/test_form_filling_integration.py`:

```python
"""Integration tests for Feature 8 — form filling and save through KPdfApp."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf
import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from k_pdf.app import KPdfApp
from k_pdf.core.form_model import FormFieldType
from k_pdf.services.form_engine import FormEngine


class TestFormDetection:
    def test_open_form_pdf_shows_status_message(self, qtbot, form_pdf: Path) -> None:
        app = QApplication.instance() or QApplication([])
        kapp = KPdfApp(app)
        qtbot.addWidget(kapp.window)
        signals = []
        kapp._tab_manager.status_message.connect(signals.append)
        kapp.tab_manager.open_file(form_pdf)
        qtbot.waitUntil(lambda: any("form field" in s for s in signals), timeout=3000)
        assert any("3 form fields" in s for s in signals)

    def test_open_non_form_pdf_no_form_message(self, qtbot, valid_pdf: Path) -> None:
        app = QApplication.instance() or QApplication([])
        kapp = KPdfApp(app)
        qtbot.addWidget(kapp.window)
        signals = []
        kapp._form_presenter.form_detected.connect(signals.append)
        kapp.tab_manager.open_file(valid_pdf)
        qtbot.waitUntil(
            lambda: kapp.tab_manager.active_session_id is not None, timeout=3000
        )
        assert signals == []


class TestFormEngineIntegration:
    def test_detect_and_write_roundtrip(self, form_pdf: Path, tmp_path: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        assert len(fields) == 3

        engine.write_fields(doc, {"full_name": "Integration Test"})
        out = tmp_path / "roundtrip.pdf"
        engine.save_document(doc, out, is_new_path=True)
        doc.close()

        doc2 = pymupdf.open(str(out))
        fields2 = engine.detect_fields(doc2)
        name_field = next(f for f in fields2 if f.name == "full_name")
        assert name_field.value == "Integration Test"
        doc2.close()


class TestSaveIntegration:
    def test_save_clears_dirty_indicator(self, qtbot, form_pdf: Path, tmp_path: Path) -> None:
        # Use a copy so we can save to it
        copy_path = tmp_path / "form_copy.pdf"
        import shutil

        shutil.copy2(form_pdf, copy_path)

        app = QApplication.instance() or QApplication([])
        kapp = KPdfApp(app)
        qtbot.addWidget(kapp.window)
        kapp.tab_manager.open_file(copy_path)
        qtbot.waitUntil(
            lambda: kapp.tab_manager.active_session_id is not None, timeout=3000
        )
        sid = kapp.tab_manager.active_session_id
        presenter = kapp.tab_manager.get_active_presenter()
        assert presenter is not None
        assert presenter.model is not None
        # Simulate dirty
        presenter.model.dirty = True
        kapp._form_presenter._models[sid] = presenter.model
        kapp._form_presenter._field_values[sid] = {"full_name": "New Value"}
        kapp._form_presenter.save(sid)
        assert presenter.model.dirty is False
```

Run: `uv run pytest tests/test_form_filling_integration.py -x` — expect all pass.

- [ ] **Step 2: Lint**

Run: `uv run ruff check tests/test_form_filling_integration.py`

---

### Task 10: mypy Overrides and pyproject.toml Updates

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add mypy overrides for new modules**

Add to `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.services.form_engine"]
disable_error_code = ["no-untyped-call"]

[[tool.mypy.overrides]]
module = ["k_pdf.presenters.form_presenter"]
disable_error_code = ["misc"]
```

- [ ] **Step 2: Full lint/type-check pass**

Run: `uv run ruff check .` and `uv run mypy k_pdf/`

---

### Task 11: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update current state**

Update `## Current State` in `CLAUDE.md`:

```markdown
## Current State
- **Project:** K-PDF
- **Phase:** 2 (Construction)
- **Track:** Standard
- **Features built:** Feature 1 (Open and Render PDF), Feature 2 (Multi-Tab), Feature 3 (Page Navigation), Feature 4 (Text Search), Feature 5 (Zoom, Rotate, Page Fit Modes), Feature 6 (Text Markup Annotations), Feature 7 (Sticky Notes & Text Box Annotations), Feature 8 (AcroForm Filling & Save)
- **Features remaining:** Features 9-12 + 7 implicit (see MVP Cutline)
- **Known issues:** Coverage at 65%+ (threshold 65%)
- **Last session summary:** Feature 8 complete — FormFieldType/FormFieldDescriptor in form_model, FormEngine (detect_fields/is_xfa_form/write_fields/save_document/get_field_value), FormPresenter (on_document_opened/on_field_changed/save/save_as/on_tab_closed), MainWindow Save/Save As actions (Ctrl+S/Ctrl+Shift+S), TabManager dirty close guard with close_guard_requested/force_close_tab, KPdfApp full wiring with Save/Discard/Cancel dialog, status bar form field count, XFA detection notification
```

---

## Task Summary

| Task | Description | Files Changed |
|------|-------------|---------------|
| 1 | Form Model | `core/form_model.py`, `tests/test_form_model.py` |
| 2 | Test Fixtures | `tests/conftest.py` |
| 3 | FormEngine | `services/form_engine.py`, `tests/test_form_engine.py` |
| 4 | Save Menu Actions | `views/main_window.py`, `tests/test_views.py` |
| 5 | Viewport Overlays | `views/pdf_viewport.py`, `tests/test_views.py` |
| 6 | FormPresenter | `presenters/form_presenter.py`, `tests/test_form_presenter.py` |
| 7 | Dirty Close Guard | `presenters/tab_manager.py`, `tests/test_tab_manager.py` |
| 8 | App Wiring | `app.py`, `tests/test_save_flow.py` |
| 9 | Integration Tests | `tests/test_form_filling_integration.py` |
| 10 | mypy/pyproject | `pyproject.toml` |
| 11 | CLAUDE.md Update | `CLAUDE.md` |
