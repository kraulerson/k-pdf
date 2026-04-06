# Form Field Creation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to create new AcroForm fields (text, checkbox, dropdown, radio, signature) by clicking on PDF pages, with inline quick-config and a docked properties panel.

**Architecture:** Extends existing FormEngine with create/delete/update widget methods. New FormCreationPresenter coordinates tool modes, click-to-place, and property editing. New FormFieldPopup (floating quick config) and FormPropertiesPanel (docked advanced editor) views. All wiring in KPdfApp.

**Tech Stack:** Python 3.13, PySide6 6.11, PyMuPDF 1.27, pytest + pytest-qt

---

### Task 1: Extend ToolMode Enum with Form Field Modes

**Files:**
- Modify: `k_pdf/core/annotation_model.py:14-21`
- Test: `tests/test_annotation_model.py` (create new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_annotation_model.py`:

```python
"""Tests for annotation_model ToolMode enum extensions."""

from __future__ import annotations

from k_pdf.core.annotation_model import ToolMode


class TestToolModeFormFields:
    def test_form_text_mode_exists(self) -> None:
        assert ToolMode.FORM_TEXT == 10

    def test_form_checkbox_mode_exists(self) -> None:
        assert ToolMode.FORM_CHECKBOX == 11

    def test_form_dropdown_mode_exists(self) -> None:
        assert ToolMode.FORM_DROPDOWN == 12

    def test_form_radio_mode_exists(self) -> None:
        assert ToolMode.FORM_RADIO == 13

    def test_form_signature_mode_exists(self) -> None:
        assert ToolMode.FORM_SIGNATURE == 14

    def test_text_edit_mode_exists(self) -> None:
        assert ToolMode.TEXT_EDIT == 5

    def test_original_modes_unchanged(self) -> None:
        assert ToolMode.NONE == 0
        assert ToolMode.TEXT_SELECT == 1
        assert ToolMode.STICKY_NOTE == 2
        assert ToolMode.TEXT_BOX == 3

    def test_form_modes_are_distinct(self) -> None:
        form_modes = [
            ToolMode.FORM_TEXT,
            ToolMode.FORM_CHECKBOX,
            ToolMode.FORM_DROPDOWN,
            ToolMode.FORM_RADIO,
            ToolMode.FORM_SIGNATURE,
        ]
        assert len(set(form_modes)) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_annotation_model.py -v`
Expected: FAIL — `AttributeError: FORM_TEXT is not a member of ToolMode`

- [ ] **Step 3: Add new ToolMode values**

In `k_pdf/core/annotation_model.py`, replace the ToolMode class:

```python
class ToolMode(IntEnum):
    """Active tool mode for viewport interaction."""

    NONE = 0
    TEXT_SELECT = 1
    STICKY_NOTE = 2
    TEXT_BOX = 3
    TEXT_EDIT = 5
    FORM_TEXT = 10
    FORM_CHECKBOX = 11
    FORM_DROPDOWN = 12
    FORM_RADIO = 13
    FORM_SIGNATURE = 14
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_annotation_model.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite to check no regressions**

Run: `uv run pytest --tb=short -q`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add k_pdf/core/annotation_model.py tests/test_annotation_model.py
git commit -m "feat: add form field and text edit tool modes to ToolMode enum"
```

---

### Task 2: Extend FormEngine with Create/Delete/Update Widget Methods

**Files:**
- Modify: `k_pdf/services/form_engine.py`
- Test: `tests/test_form_engine.py` (extend existing)

- [ ] **Step 1: Write failing tests for create_widget**

Append to `tests/test_form_engine.py`:

```python
import pymupdf
import pytest
from pathlib import Path

from k_pdf.services.form_engine import FormEngine
from k_pdf.core.form_model import FormFieldType


class TestCreateWidget:
    @pytest.fixture
    def engine(self) -> FormEngine:
        return FormEngine()

    @pytest.fixture
    def blank_pdf(self, tmp_path: Path) -> Path:
        path = tmp_path / "blank.pdf"
        doc = pymupdf.open()
        doc.new_page(width=612, height=792)
        doc.save(str(path))
        doc.close()
        return path

    def test_create_text_field(self, engine: FormEngine, blank_pdf: Path) -> None:
        doc = pymupdf.open(str(blank_pdf))
        widget = engine.create_widget(
            doc_handle=doc,
            page_index=0,
            field_type=FormFieldType.TEXT,
            rect=(72, 100, 272, 124),
            properties={"name": "user_name", "max_length": 50},
        )
        assert widget is not None
        assert widget.field_name == "user_name"
        assert widget.field_type == pymupdf.PDF_WIDGET_TYPE_TEXT
        doc.close()

    def test_create_checkbox(self, engine: FormEngine, blank_pdf: Path) -> None:
        doc = pymupdf.open(str(blank_pdf))
        widget = engine.create_widget(
            doc_handle=doc,
            page_index=0,
            field_type=FormFieldType.CHECKBOX,
            rect=(72, 140, 86, 154),
            properties={"name": "agree_terms"},
        )
        assert widget is not None
        assert widget.field_name == "agree_terms"
        assert widget.field_type == pymupdf.PDF_WIDGET_TYPE_CHECKBOX
        doc.close()

    def test_create_dropdown(self, engine: FormEngine, blank_pdf: Path) -> None:
        doc = pymupdf.open(str(blank_pdf))
        widget = engine.create_widget(
            doc_handle=doc,
            page_index=0,
            field_type=FormFieldType.DROPDOWN,
            rect=(72, 180, 272, 204),
            properties={"name": "country", "options": ["USA", "Canada", "Mexico"]},
        )
        assert widget is not None
        assert widget.field_name == "country"
        assert widget.field_type == pymupdf.PDF_WIDGET_TYPE_COMBOBOX
        doc.close()

    def test_create_radio(self, engine: FormEngine, blank_pdf: Path) -> None:
        doc = pymupdf.open(str(blank_pdf))
        widget = engine.create_widget(
            doc_handle=doc,
            page_index=0,
            field_type=FormFieldType.RADIO,
            rect=(72, 220, 86, 234),
            properties={"name": "gender_male"},
        )
        assert widget is not None
        assert widget.field_name == "gender_male"
        assert widget.field_type == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON
        doc.close()

    def test_create_signature(self, engine: FormEngine, blank_pdf: Path) -> None:
        doc = pymupdf.open(str(blank_pdf))
        widget = engine.create_widget(
            doc_handle=doc,
            page_index=0,
            field_type=FormFieldType.SIGNATURE,
            rect=(72, 260, 272, 320),
            properties={"name": "applicant_sig"},
        )
        assert widget is not None
        assert widget.field_name == "applicant_sig"
        doc.close()

    def test_created_field_persists_after_save(
        self, engine: FormEngine, blank_pdf: Path, tmp_path: Path
    ) -> None:
        doc = pymupdf.open(str(blank_pdf))
        engine.create_widget(
            doc_handle=doc,
            page_index=0,
            field_type=FormFieldType.TEXT,
            rect=(72, 100, 272, 124),
            properties={"name": "persist_test"},
        )
        out_path = tmp_path / "saved.pdf"
        doc.save(str(out_path))
        doc.close()

        doc2 = pymupdf.open(str(out_path))
        fields = engine.detect_fields(doc2)
        assert any(f.name == "persist_test" for f in fields)
        doc2.close()


class TestDeleteWidget:
    @pytest.fixture
    def engine(self) -> FormEngine:
        return FormEngine()

    def test_delete_widget_removes_field(self, engine: FormEngine, form_pdf: Path) -> None:
        doc = pymupdf.open(str(form_pdf))
        fields_before = engine.detect_fields(doc)
        count_before = len(fields_before)

        page = doc[0]
        widget = next(page.widgets())
        engine.delete_widget(doc, 0, widget)

        fields_after = engine.detect_fields(doc)
        assert len(fields_after) == count_before - 1
        doc.close()


class TestUpdateWidgetProperties:
    @pytest.fixture
    def engine(self) -> FormEngine:
        return FormEngine()

    def test_update_field_name(self, engine: FormEngine, form_pdf: Path) -> None:
        doc = pymupdf.open(str(form_pdf))
        page = doc[0]
        widget = next(page.widgets())
        engine.update_widget_properties(doc, 0, widget, {"name": "updated_name"})

        fields = engine.detect_fields(doc)
        names = [f.name for f in fields]
        assert "updated_name" in names
        doc.close()


class TestGetWidgetAt:
    @pytest.fixture
    def engine(self) -> FormEngine:
        return FormEngine()

    def test_hit_test_on_field(self, engine: FormEngine, form_pdf: Path) -> None:
        doc = pymupdf.open(str(form_pdf))
        # full_name field is at rect (72, 100, 300, 120)
        widget = engine.get_widget_at(doc, 0, 150.0, 110.0)
        assert widget is not None
        doc.close()

    def test_hit_test_on_empty_area(self, engine: FormEngine, form_pdf: Path) -> None:
        doc = pymupdf.open(str(form_pdf))
        widget = engine.get_widget_at(doc, 0, 500.0, 500.0)
        assert widget is None
        doc.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_form_engine.py::TestCreateWidget -v`
Expected: FAIL — `AttributeError: 'FormEngine' object has no attribute 'create_widget'`

- [ ] **Step 3: Add SIGNATURE to FormFieldType enum**

In `k_pdf/core/form_model.py`, add to the `FormFieldType` enum:

```python
class FormFieldType(Enum):
    """AcroForm field widget types."""

    TEXT = "text"
    CHECKBOX = "checkbox"
    DROPDOWN = "dropdown"
    RADIO = "radio"
    SIGNATURE = "signature"
```

- [ ] **Step 4: Implement FormEngine extensions**

Add the following methods to `k_pdf/services/form_engine.py`. Add `from k_pdf.core.form_model import FormFieldDescriptor, FormFieldType` to the existing import (FormFieldType is already imported, just verify). Add these methods to the `FormEngine` class:

```python
    # Map our field types to pymupdf widget type constants
    _CREATE_TYPE_MAP: ClassVar[dict[FormFieldType, int]] = {
        FormFieldType.TEXT: pymupdf.PDF_WIDGET_TYPE_TEXT,
        FormFieldType.CHECKBOX: pymupdf.PDF_WIDGET_TYPE_CHECKBOX,
        FormFieldType.DROPDOWN: pymupdf.PDF_WIDGET_TYPE_COMBOBOX,
        FormFieldType.RADIO: pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON,
    }

    def create_widget(
        self,
        doc_handle: Any,
        page_index: int,
        field_type: FormFieldType,
        rect: tuple[float, float, float, float],
        properties: dict[str, Any] | None = None,
    ) -> Any:
        """Create a new form field widget on a page.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            field_type: The type of form field to create.
            rect: Bounding rectangle (x0, y0, x1, y1) in PDF coordinates.
            properties: Optional dict with keys: name, max_length, options, value.

        Returns:
            The created pymupdf Widget object.
        """
        props = properties or {}
        page = doc_handle[page_index]
        widget = pymupdf.Widget()

        if field_type is FormFieldType.SIGNATURE:
            # Signature fields are PDF_WIDGET_TYPE_SIGNATURE (value 7 in pymupdf)
            widget.field_type = 7  # pymupdf signature widget type
        else:
            widget.field_type = self._CREATE_TYPE_MAP[field_type]

        widget.rect = pymupdf.Rect(*rect)
        widget.field_name = props.get("name", f"field_{page_index}_{id(widget)}")

        if field_type is FormFieldType.TEXT:
            if "max_length" in props:
                widget.text_maxlen = props["max_length"]

        if field_type is FormFieldType.DROPDOWN and "options" in props:
            widget.choice_values = props["options"]

        if "value" in props:
            widget.field_value = props["value"]

        page.add_widget(widget)
        logger.debug(
            "Created %s widget '%s' on page %d",
            field_type.value,
            widget.field_name,
            page_index,
        )
        return widget

    def delete_widget(
        self,
        doc_handle: Any,
        page_index: int,
        widget: Any,
    ) -> None:
        """Delete a form field widget from a page.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            widget: The pymupdf Widget to delete.
        """
        page = doc_handle[page_index]
        target_name = widget.field_name
        for w in page.widgets():
            if w.field_name == target_name:
                page.delete_widget(w)
                logger.debug("Deleted widget '%s' on page %d", target_name, page_index)
                return
        logger.warning("Widget '%s' not found on page %d for deletion", target_name, page_index)

    def update_widget_properties(
        self,
        doc_handle: Any,
        page_index: int,
        widget: Any,
        properties: dict[str, Any],
    ) -> None:
        """Update properties of an existing form field widget.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            widget: The pymupdf Widget to update.
            properties: Dict of properties to update (name, value, options, etc.).
        """
        page = doc_handle[page_index]
        target_name = widget.field_name
        for w in page.widgets():
            if w.field_name == target_name:
                if "name" in properties:
                    w.field_name = properties["name"]
                if "value" in properties:
                    w.field_value = properties["value"]
                if "options" in properties and hasattr(w, "choice_values"):
                    w.choice_values = properties["options"]
                w.update()
                logger.debug("Updated widget '%s' on page %d", target_name, page_index)
                return
        logger.warning("Widget '%s' not found on page %d for update", target_name, page_index)

    def get_widget_at(
        self,
        doc_handle: Any,
        page_index: int,
        x: float,
        y: float,
    ) -> Any | None:
        """Return the form field widget at the given PDF coordinates, or None.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            x: X coordinate in PDF page space.
            y: Y coordinate in PDF page space.

        Returns:
            The pymupdf Widget at the point, or None.
        """
        page = doc_handle[page_index]
        for w in page.widgets():
            r = w.rect
            if r.x0 <= x <= r.x1 and r.y0 <= y <= r.y1:
                return w
        return None
```

Also add `from typing import Any, ClassVar` at the top of form_engine.py (ClassVar is new).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_form_engine.py -v`
Expected: All PASS (including new and existing tests)

- [ ] **Step 6: Run linting and type check**

Run: `uv run ruff check k_pdf/services/form_engine.py && uv run mypy k_pdf/services/form_engine.py`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add k_pdf/core/form_model.py k_pdf/services/form_engine.py tests/test_form_engine.py
git commit -m "feat: add form field create/delete/update/hit-test to FormEngine"
```

---

### Task 3: FormFieldPopup View (Inline Quick Config)

**Files:**
- Create: `k_pdf/views/form_field_popup.py`
- Test: `tests/test_form_field_popup.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_form_field_popup.py`:

```python
"""Tests for FormFieldPopup inline quick-config widget."""

from __future__ import annotations

from k_pdf.core.form_model import FormFieldType
from k_pdf.views.form_field_popup import FormFieldPopup


class TestFormFieldPopupInit:
    def test_creates_for_text_field(self, qtbot) -> None:
        popup = FormFieldPopup(FormFieldType.TEXT)
        qtbot.addWidget(popup)
        assert popup._field_type is FormFieldType.TEXT
        assert popup._name_edit is not None

    def test_creates_for_checkbox(self, qtbot) -> None:
        popup = FormFieldPopup(FormFieldType.CHECKBOX)
        qtbot.addWidget(popup)
        assert popup._field_type is FormFieldType.CHECKBOX

    def test_creates_for_dropdown_with_options(self, qtbot) -> None:
        popup = FormFieldPopup(FormFieldType.DROPDOWN)
        qtbot.addWidget(popup)
        assert popup._options_edit is not None

    def test_creates_for_radio(self, qtbot) -> None:
        popup = FormFieldPopup(FormFieldType.RADIO)
        qtbot.addWidget(popup)
        assert popup._group_edit is not None

    def test_creates_for_signature(self, qtbot) -> None:
        popup = FormFieldPopup(FormFieldType.SIGNATURE)
        qtbot.addWidget(popup)
        assert popup._field_type is FormFieldType.SIGNATURE


class TestFormFieldPopupSignals:
    def test_create_emits_with_properties(self, qtbot) -> None:
        popup = FormFieldPopup(FormFieldType.TEXT)
        qtbot.addWidget(popup)
        popup._name_edit.setText("my_field")

        with qtbot.waitSignal(popup.create_requested, timeout=1000) as sig:
            popup._on_create()

        props = sig.args[0]
        assert props["name"] == "my_field"

    def test_cancel_emits_signal(self, qtbot) -> None:
        popup = FormFieldPopup(FormFieldType.TEXT)
        qtbot.addWidget(popup)

        with qtbot.waitSignal(popup.cancel_requested, timeout=1000):
            popup._on_cancel()

    def test_more_emits_signal(self, qtbot) -> None:
        popup = FormFieldPopup(FormFieldType.TEXT)
        qtbot.addWidget(popup)
        popup._name_edit.setText("my_field")

        with qtbot.waitSignal(popup.more_requested, timeout=1000) as sig:
            popup._on_more()

        props = sig.args[0]
        assert props["name"] == "my_field"

    def test_auto_generates_name(self, qtbot) -> None:
        popup = FormFieldPopup(FormFieldType.TEXT)
        qtbot.addWidget(popup)
        name = popup._name_edit.text()
        assert name.startswith("text_field_")

    def test_dropdown_options_parsed(self, qtbot) -> None:
        popup = FormFieldPopup(FormFieldType.DROPDOWN)
        qtbot.addWidget(popup)
        popup._options_edit.setText("Red, Green, Blue")
        popup._name_edit.setText("colors")

        with qtbot.waitSignal(popup.create_requested, timeout=1000) as sig:
            popup._on_create()

        props = sig.args[0]
        assert props["options"] == ["Red", "Green", "Blue"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_form_field_popup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'k_pdf.views.form_field_popup'`

- [ ] **Step 3: Implement FormFieldPopup**

Create `k_pdf/views/form_field_popup.py`:

```python
"""Floating inline popup for quick form field configuration.

Appears after clicking to place a form field. Shows field-type-appropriate
inputs. Emits create_requested, more_requested, or cancel_requested.
Same frameless window pattern as NoteEditor.
"""

from __future__ import annotations

import logging
from typing import Any, override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from k_pdf.core.form_model import FormFieldType

logger = logging.getLogger("k_pdf.views.form_field_popup")

_AUTO_NAME_COUNTERS: dict[FormFieldType, int] = {}

_TYPE_PREFIX: dict[FormFieldType, str] = {
    FormFieldType.TEXT: "text_field",
    FormFieldType.CHECKBOX: "checkbox",
    FormFieldType.DROPDOWN: "dropdown",
    FormFieldType.RADIO: "radio",
    FormFieldType.SIGNATURE: "signature",
}


def _next_auto_name(field_type: FormFieldType) -> str:
    """Generate an auto-incremented field name."""
    count = _AUTO_NAME_COUNTERS.get(field_type, 0) + 1
    _AUTO_NAME_COUNTERS[field_type] = count
    return f"{_TYPE_PREFIX[field_type]}_{count}"


class FormFieldPopup(QWidget):
    """Floating frameless popup for quick form field configuration.

    Signals:
        create_requested: Emitted with a properties dict when Create is clicked.
        more_requested: Emitted with a properties dict when More... is clicked.
        cancel_requested: Emitted when Cancel is clicked or Escape pressed.
    """

    create_requested = Signal(dict)  # properties dict
    more_requested = Signal(dict)  # properties dict
    cancel_requested = Signal()

    def __init__(
        self,
        field_type: FormFieldType,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the popup with field-type-appropriate inputs.

        Args:
            field_type: The type of form field being created.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self._field_type = field_type

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Title
        type_label = _TYPE_PREFIX.get(field_type, "field").replace("_", " ").title()
        title = QLabel(f"{type_label} Properties")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # Field Name (all types)
        layout.addWidget(QLabel("Field Name"))
        self._name_edit = QLineEdit()
        self._name_edit.setText(_next_auto_name(field_type))
        self._name_edit.setAccessibleName("Field name")
        layout.addWidget(self._name_edit)

        # Type-specific fields
        self._max_length_spin: QSpinBox | None = None
        self._placeholder_edit: QLineEdit | None = None
        self._options_edit: QLineEdit | None = None
        self._group_edit: QLineEdit | None = None
        self._default_check: QCheckBox | None = None

        if field_type is FormFieldType.TEXT:
            layout.addWidget(QLabel("Placeholder"))
            self._placeholder_edit = QLineEdit()
            self._placeholder_edit.setAccessibleName("Placeholder text")
            layout.addWidget(self._placeholder_edit)

            layout.addWidget(QLabel("Max Length"))
            self._max_length_spin = QSpinBox()
            self._max_length_spin.setRange(0, 10000)
            self._max_length_spin.setValue(0)
            self._max_length_spin.setSpecialValueText("No limit")
            self._max_length_spin.setAccessibleName("Maximum character length")
            layout.addWidget(self._max_length_spin)

        elif field_type is FormFieldType.CHECKBOX:
            self._default_check = QCheckBox("Checked by default")
            self._default_check.setAccessibleName("Default checked state")
            layout.addWidget(self._default_check)

        elif field_type is FormFieldType.DROPDOWN:
            layout.addWidget(QLabel("Options (comma-separated)"))
            self._options_edit = QLineEdit()
            self._options_edit.setPlaceholderText("Option 1, Option 2, Option 3")
            self._options_edit.setAccessibleName("Dropdown options")
            layout.addWidget(self._options_edit)

        elif field_type is FormFieldType.RADIO:
            layout.addWidget(QLabel("Group Name"))
            self._group_edit = QLineEdit()
            self._group_edit.setPlaceholderText("e.g. gender, priority")
            self._group_edit.setAccessibleName("Radio button group name")
            layout.addWidget(self._group_edit)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        more_btn = QPushButton("More...")
        more_btn.setToolTip("Open full properties panel")
        more_btn.clicked.connect(self._on_more)
        btn_layout.addWidget(more_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(cancel_btn)

        create_btn = QPushButton("Create")
        create_btn.setDefault(True)
        create_btn.clicked.connect(self._on_create)
        btn_layout.addWidget(create_btn)

        layout.addLayout(btn_layout)
        self.adjustSize()

    def _gather_properties(self) -> dict[str, Any]:
        """Collect current input values into a properties dict."""
        props: dict[str, Any] = {
            "name": self._name_edit.text().strip() or _next_auto_name(self._field_type),
            "field_type": self._field_type,
        }

        if self._placeholder_edit is not None:
            props["placeholder"] = self._placeholder_edit.text()

        if self._max_length_spin is not None and self._max_length_spin.value() > 0:
            props["max_length"] = self._max_length_spin.value()

        if self._options_edit is not None:
            raw = self._options_edit.text()
            props["options"] = [o.strip() for o in raw.split(",") if o.strip()]

        if self._group_edit is not None:
            props["group_name"] = self._group_edit.text().strip()

        if self._default_check is not None:
            props["value"] = "Yes" if self._default_check.isChecked() else "Off"

        return props

    def _on_create(self) -> None:
        """Emit create_requested and hide."""
        self.create_requested.emit(self._gather_properties())
        self.hide()

    def _on_more(self) -> None:
        """Emit more_requested and hide."""
        self.more_requested.emit(self._gather_properties())
        self.hide()

    def _on_cancel(self) -> None:
        """Emit cancel_requested and hide."""
        self.cancel_requested.emit()
        self.hide()

    def show_near(self, x: int, y: int) -> None:
        """Position the popup near the given screen coordinates.

        Args:
            x: X coordinate in screen pixels.
            y: Y coordinate in screen pixels.
        """
        self.adjustSize()
        screen = self.screen()
        if screen is not None:
            sr = screen.availableGeometry()
            x = max(sr.left(), min(x, sr.right() - self.width()))
            y = max(sr.top(), min(y, sr.bottom() - self.height()))
        self.move(x, y)
        self.show()
        self._name_edit.setFocus()

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle Escape to cancel."""
        if event.key() == Qt.Key.Key_Escape:
            self._on_cancel()
            return
        super().keyPressEvent(event)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_form_field_popup.py -v`
Expected: All PASS

- [ ] **Step 5: Run linting**

Run: `uv run ruff check k_pdf/views/form_field_popup.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add k_pdf/views/form_field_popup.py tests/test_form_field_popup.py
git commit -m "feat: add FormFieldPopup inline quick-config view"
```

---

### Task 4: FormPropertiesPanel View (Docked Advanced Editor)

**Files:**
- Create: `k_pdf/views/form_properties_panel.py`
- Test: `tests/test_form_properties_panel.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_form_properties_panel.py`:

```python
"""Tests for FormPropertiesPanel docked advanced property editor."""

from __future__ import annotations

from k_pdf.core.form_model import FormFieldType
from k_pdf.views.form_properties_panel import FormPropertiesPanel


class TestFormPropertiesPanelInit:
    def test_creates_panel(self, qtbot) -> None:
        panel = FormPropertiesPanel()
        qtbot.addWidget(panel)
        assert panel.windowTitle() == "Form Properties"

    def test_shows_empty_state_initially(self, qtbot) -> None:
        panel = FormPropertiesPanel()
        qtbot.addWidget(panel)
        assert panel._empty_label.isVisible()
        assert not panel._form_container.isVisible()


class TestFormPropertiesPanelDisplay:
    def test_load_text_field_properties(self, qtbot) -> None:
        panel = FormPropertiesPanel()
        qtbot.addWidget(panel)
        props = {
            "name": "user_name",
            "field_type": FormFieldType.TEXT,
            "page": 0,
            "rect": (72, 100, 272, 124),
            "max_length": 50,
            "placeholder": "Enter name",
        }
        panel.load_properties(props)
        assert panel._name_edit.text() == "user_name"
        assert panel._form_container.isVisible()
        assert not panel._empty_label.isVisible()

    def test_load_dropdown_shows_options(self, qtbot) -> None:
        panel = FormPropertiesPanel()
        qtbot.addWidget(panel)
        props = {
            "name": "country",
            "field_type": FormFieldType.DROPDOWN,
            "page": 0,
            "rect": (72, 180, 272, 204),
            "options": ["USA", "Canada"],
        }
        panel.load_properties(props)
        assert panel._name_edit.text() == "country"

    def test_clear_shows_empty_state(self, qtbot) -> None:
        panel = FormPropertiesPanel()
        qtbot.addWidget(panel)
        panel.load_properties({
            "name": "test",
            "field_type": FormFieldType.TEXT,
            "page": 0,
            "rect": (0, 0, 100, 20),
        })
        panel.clear()
        assert panel._empty_label.isVisible()
        assert not panel._form_container.isVisible()


class TestFormPropertiesPanelSignals:
    def test_delete_emits_signal(self, qtbot) -> None:
        panel = FormPropertiesPanel()
        qtbot.addWidget(panel)
        panel.load_properties({
            "name": "test",
            "field_type": FormFieldType.TEXT,
            "page": 0,
            "rect": (0, 0, 100, 20),
        })

        with qtbot.waitSignal(panel.delete_requested, timeout=1000):
            panel._delete_btn.click()

    def test_property_changed_emits_signal(self, qtbot) -> None:
        panel = FormPropertiesPanel()
        qtbot.addWidget(panel)
        panel.load_properties({
            "name": "test",
            "field_type": FormFieldType.TEXT,
            "page": 0,
            "rect": (0, 0, 100, 20),
        })

        with qtbot.waitSignal(panel.properties_changed, timeout=1000):
            panel._name_edit.setText("new_name")
            panel._name_edit.editingFinished.emit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_form_properties_panel.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement FormPropertiesPanel**

Create `k_pdf/views/form_properties_panel.py`:

```python
"""Docked advanced form field property editor.

QDockWidget showing all properties for a selected form field.
Toggled via View menu (F8). Shares right dock area with Annotation panel.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from k_pdf.core.form_model import FormFieldType

logger = logging.getLogger("k_pdf.views.form_properties_panel")


class FormPropertiesPanel(QDockWidget):
    """Right-docked panel for editing form field properties.

    Signals:
        properties_changed: Emitted with updated properties dict.
        delete_requested: Emitted when Delete Field button is clicked.
    """

    properties_changed = Signal(dict)
    delete_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the form properties panel."""
        super().__init__("Form Properties", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.setMinimumWidth(220)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)

        # Stacked widget: empty state vs form
        self._stack = QStackedWidget()

        # Empty state
        self._empty_label = QLabel("Select a form field\nto edit properties")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._stack.addWidget(self._empty_label)  # index 0

        # Form container
        self._form_container = QWidget()
        form_layout = QVBoxLayout(self._form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)

        # Common properties form
        self._common_form = QFormLayout()

        self._type_label = QLabel()
        self._type_label.setAccessibleName("Field type")
        self._common_form.addRow("Type:", self._type_label)

        self._page_label = QLabel()
        self._page_label.setAccessibleName("Page number")
        self._common_form.addRow("Page:", self._page_label)

        self._name_edit = QLineEdit()
        self._name_edit.setAccessibleName("Field name")
        self._name_edit.editingFinished.connect(self._on_property_changed)
        self._common_form.addRow("Name:", self._name_edit)

        self._x_spin = QDoubleSpinBox()
        self._x_spin.setRange(0, 10000)
        self._x_spin.setDecimals(1)
        self._x_spin.setAccessibleName("X position")
        self._x_spin.editingFinished.connect(self._on_property_changed)
        self._common_form.addRow("X:", self._x_spin)

        self._y_spin = QDoubleSpinBox()
        self._y_spin.setRange(0, 10000)
        self._y_spin.setDecimals(1)
        self._y_spin.setAccessibleName("Y position")
        self._y_spin.editingFinished.connect(self._on_property_changed)
        self._common_form.addRow("Y:", self._y_spin)

        self._w_spin = QDoubleSpinBox()
        self._w_spin.setRange(1, 10000)
        self._w_spin.setDecimals(1)
        self._w_spin.setAccessibleName("Width")
        self._w_spin.editingFinished.connect(self._on_property_changed)
        self._common_form.addRow("Width:", self._w_spin)

        self._h_spin = QDoubleSpinBox()
        self._h_spin.setRange(1, 10000)
        self._h_spin.setDecimals(1)
        self._h_spin.setAccessibleName("Height")
        self._h_spin.editingFinished.connect(self._on_property_changed)
        self._common_form.addRow("Height:", self._h_spin)

        self._readonly_check = QCheckBox("Read-only")
        self._readonly_check.setAccessibleName("Read-only field")
        self._readonly_check.stateChanged.connect(lambda _: self._on_property_changed())
        self._common_form.addRow("", self._readonly_check)

        form_layout.addLayout(self._common_form)

        # Text-specific
        self._text_section = QWidget()
        text_form = QFormLayout(self._text_section)
        text_form.setContentsMargins(0, 8, 0, 0)
        self._placeholder_edit = QLineEdit()
        self._placeholder_edit.setAccessibleName("Placeholder text")
        self._placeholder_edit.editingFinished.connect(self._on_property_changed)
        text_form.addRow("Placeholder:", self._placeholder_edit)
        self._max_length_spin = QSpinBox()
        self._max_length_spin.setRange(0, 10000)
        self._max_length_spin.setSpecialValueText("No limit")
        self._max_length_spin.setAccessibleName("Max character length")
        self._max_length_spin.editingFinished.connect(self._on_property_changed)
        text_form.addRow("Max Length:", self._max_length_spin)
        self._multiline_check = QCheckBox("Multiline")
        self._multiline_check.setAccessibleName("Multiline text field")
        self._multiline_check.stateChanged.connect(lambda _: self._on_property_changed())
        text_form.addRow("", self._multiline_check)
        form_layout.addWidget(self._text_section)

        # Dropdown-specific
        self._dropdown_section = QWidget()
        dd_layout = QVBoxLayout(self._dropdown_section)
        dd_layout.setContentsMargins(0, 8, 0, 0)
        dd_layout.addWidget(QLabel("Options:"))
        self._options_list = QListWidget()
        self._options_list.setAccessibleName("Dropdown options list")
        self._options_list.setMaximumHeight(100)
        dd_layout.addWidget(self._options_list)
        dd_btn_layout = QVBoxLayout()
        self._add_option_btn = QPushButton("Add Option")
        self._add_option_btn.clicked.connect(self._on_add_option)
        dd_btn_layout.addWidget(self._add_option_btn)
        self._remove_option_btn = QPushButton("Remove Selected")
        self._remove_option_btn.clicked.connect(self._on_remove_option)
        dd_btn_layout.addWidget(self._remove_option_btn)
        dd_layout.addLayout(dd_btn_layout)
        form_layout.addWidget(self._dropdown_section)

        # Radio-specific
        self._radio_section = QWidget()
        radio_form = QFormLayout(self._radio_section)
        radio_form.setContentsMargins(0, 8, 0, 0)
        self._group_edit = QLineEdit()
        self._group_edit.setAccessibleName("Radio group name")
        self._group_edit.editingFinished.connect(self._on_property_changed)
        radio_form.addRow("Group:", self._group_edit)
        self._value_edit = QLineEdit()
        self._value_edit.setAccessibleName("Radio button value")
        self._value_edit.editingFinished.connect(self._on_property_changed)
        radio_form.addRow("Value:", self._value_edit)
        form_layout.addWidget(self._radio_section)

        # Delete button
        form_layout.addStretch()
        self._delete_btn = QPushButton("Delete Field")
        self._delete_btn.setToolTip("Remove this form field from the document")
        self._delete_btn.clicked.connect(self.delete_requested.emit)
        form_layout.addWidget(self._delete_btn)

        self._stack.addWidget(self._form_container)  # index 1

        main_layout.addWidget(self._stack)
        self.setWidget(container)

        # Start with empty state
        self._stack.setCurrentIndex(0)
        self._current_field_type: FormFieldType | None = None

    def load_properties(self, props: dict[str, Any]) -> None:
        """Populate the panel with properties for a selected field.

        Args:
            props: Dict with keys: name, field_type, page, rect, and type-specific keys.
        """
        self._stack.setCurrentIndex(1)

        field_type: FormFieldType = props.get("field_type", FormFieldType.TEXT)
        self._current_field_type = field_type

        self._type_label.setText(field_type.value.title())
        self._page_label.setText(str(props.get("page", 0) + 1))
        self._name_edit.setText(props.get("name", ""))

        rect = props.get("rect", (0, 0, 100, 20))
        self._x_spin.setValue(rect[0])
        self._y_spin.setValue(rect[1])
        self._w_spin.setValue(rect[2] - rect[0])
        self._h_spin.setValue(rect[3] - rect[1])

        self._readonly_check.setChecked(props.get("read_only", False))

        # Show/hide type-specific sections
        self._text_section.setVisible(field_type is FormFieldType.TEXT)
        self._dropdown_section.setVisible(field_type is FormFieldType.DROPDOWN)
        self._radio_section.setVisible(field_type is FormFieldType.RADIO)

        if field_type is FormFieldType.TEXT:
            self._placeholder_edit.setText(props.get("placeholder", ""))
            self._max_length_spin.setValue(props.get("max_length", 0))
            self._multiline_check.setChecked(props.get("multiline", False))
        elif field_type is FormFieldType.DROPDOWN:
            self._options_list.clear()
            for opt in props.get("options", []):
                self._options_list.addItem(opt)
        elif field_type is FormFieldType.RADIO:
            self._group_edit.setText(props.get("group_name", ""))
            self._value_edit.setText(props.get("value", ""))

    def clear(self) -> None:
        """Reset to empty state."""
        self._stack.setCurrentIndex(0)
        self._current_field_type = None

    def gather_properties(self) -> dict[str, Any]:
        """Collect current panel values into a properties dict."""
        x = self._x_spin.value()
        y = self._y_spin.value()
        w = self._w_spin.value()
        h = self._h_spin.value()

        props: dict[str, Any] = {
            "name": self._name_edit.text().strip(),
            "rect": (x, y, x + w, y + h),
            "read_only": self._readonly_check.isChecked(),
        }

        if self._current_field_type is FormFieldType.TEXT:
            props["placeholder"] = self._placeholder_edit.text()
            if self._max_length_spin.value() > 0:
                props["max_length"] = self._max_length_spin.value()
            props["multiline"] = self._multiline_check.isChecked()
        elif self._current_field_type is FormFieldType.DROPDOWN:
            props["options"] = [
                self._options_list.item(i).text()
                for i in range(self._options_list.count())
            ]
        elif self._current_field_type is FormFieldType.RADIO:
            props["group_name"] = self._group_edit.text().strip()
            props["value"] = self._value_edit.text().strip()

        return props

    def _on_property_changed(self) -> None:
        """Emit properties_changed with current values."""
        self.properties_changed.emit(self.gather_properties())

    def _on_add_option(self) -> None:
        """Add a new empty option to the dropdown list."""
        self._options_list.addItem("New Option")
        self._on_property_changed()

    def _on_remove_option(self) -> None:
        """Remove the selected option from the dropdown list."""
        current = self._options_list.currentRow()
        if current >= 0:
            self._options_list.takeItem(current)
            self._on_property_changed()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_form_properties_panel.py -v`
Expected: All PASS

- [ ] **Step 5: Run linting**

Run: `uv run ruff check k_pdf/views/form_properties_panel.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add k_pdf/views/form_properties_panel.py tests/test_form_properties_panel.py
git commit -m "feat: add FormPropertiesPanel docked advanced editor view"
```

---

### Task 5: FormCreationPresenter

**Files:**
- Create: `k_pdf/presenters/form_creation_presenter.py`
- Test: `tests/test_form_creation_presenter.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_form_creation_presenter.py`:

```python
"""Tests for FormCreationPresenter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf
import pytest
from PySide6.QtWidgets import QTabWidget

from k_pdf.core.annotation_model import ToolMode
from k_pdf.core.form_model import FormFieldType
from k_pdf.core.undo_manager import UndoManager
from k_pdf.persistence.recent_files import RecentFiles
from k_pdf.persistence.settings_db import init_db
from k_pdf.presenters.form_creation_presenter import FormCreationPresenter
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.form_engine import FormEngine


@pytest.fixture
def form_engine() -> FormEngine:
    return FormEngine()


@pytest.fixture
def tab_manager(qtbot, tmp_path: Path) -> TabManager:
    db = init_db(tmp_path / "test.db")
    recent = RecentFiles(db)
    tw = QTabWidget()
    qtbot.addWidget(tw)
    return TabManager(tab_widget=tw, recent_files=recent)


@pytest.fixture
def presenter(
    form_engine: FormEngine, tab_manager: TabManager
) -> FormCreationPresenter:
    return FormCreationPresenter(
        form_engine=form_engine,
        tab_manager=tab_manager,
    )


class TestFormCreationPresenterToolMode:
    def test_set_form_text_mode(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_TEXT)
        assert presenter.tool_mode is ToolMode.FORM_TEXT
        assert presenter.pending_field_type is FormFieldType.TEXT

    def test_set_form_checkbox_mode(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_CHECKBOX)
        assert presenter.pending_field_type is FormFieldType.CHECKBOX

    def test_set_form_dropdown_mode(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_DROPDOWN)
        assert presenter.pending_field_type is FormFieldType.DROPDOWN

    def test_set_form_radio_mode(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_RADIO)
        assert presenter.pending_field_type is FormFieldType.RADIO

    def test_set_form_signature_mode(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_SIGNATURE)
        assert presenter.pending_field_type is FormFieldType.SIGNATURE

    def test_set_none_clears_pending(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_TEXT)
        presenter.set_tool_mode(ToolMode.NONE)
        assert presenter.pending_field_type is None


class TestFormCreationPresenterCreate:
    def test_create_field_marks_dirty(
        self, presenter: FormCreationPresenter, tmp_path: Path
    ) -> None:
        # Set up a mock active model
        path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        doc.new_page(width=612, height=792)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        mock_model = MagicMock()
        mock_model.doc_handle = doc
        mock_model.dirty = False

        mock_presenter = MagicMock()
        mock_presenter.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_presenter)

        dirty_signals: list[bool] = []
        presenter.dirty_changed.connect(dirty_signals.append)

        presenter.create_field(
            page_index=0,
            point=(100.0, 200.0),
            field_type=FormFieldType.TEXT,
            properties={"name": "test_field"},
        )

        assert mock_model.dirty is True
        assert dirty_signals == [True]
        doc.close()

    def test_create_field_emits_field_created(
        self, presenter: FormCreationPresenter, tmp_path: Path
    ) -> None:
        path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        doc.new_page(width=612, height=792)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        mock_model = MagicMock()
        mock_model.doc_handle = doc

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)

        created: list[bool] = []
        presenter.field_created.connect(lambda: created.append(True))

        presenter.create_field(
            page_index=0,
            point=(100.0, 200.0),
            field_type=FormFieldType.TEXT,
            properties={"name": "emit_test"},
        )

        assert len(created) == 1
        doc.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_form_creation_presenter.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement FormCreationPresenter**

Create `k_pdf/presenters/form_creation_presenter.py`:

```python
"""Form field creation presenter.

Coordinates tool modes, click-to-place, FormFieldPopup, FormPropertiesPanel,
undo actions, and dirty flag management for new form field creation.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal

from k_pdf.core.annotation_model import ToolMode
from k_pdf.core.form_model import FormFieldType
from k_pdf.core.undo_manager import UndoAction
from k_pdf.services.form_engine import FormEngine

logger = logging.getLogger("k_pdf.presenters.form_creation_presenter")

# Map form tool modes to field types
_MODE_TO_TYPE: dict[ToolMode, FormFieldType] = {
    ToolMode.FORM_TEXT: FormFieldType.TEXT,
    ToolMode.FORM_CHECKBOX: FormFieldType.CHECKBOX,
    ToolMode.FORM_DROPDOWN: FormFieldType.DROPDOWN,
    ToolMode.FORM_RADIO: FormFieldType.RADIO,
    ToolMode.FORM_SIGNATURE: FormFieldType.SIGNATURE,
}

# Default field sizes in PDF points
_DEFAULT_SIZES: dict[FormFieldType, tuple[float, float]] = {
    FormFieldType.TEXT: (200.0, 24.0),
    FormFieldType.CHECKBOX: (14.0, 14.0),
    FormFieldType.DROPDOWN: (200.0, 24.0),
    FormFieldType.RADIO: (14.0, 14.0),
    FormFieldType.SIGNATURE: (200.0, 60.0),
}


class FormCreationPresenter(QObject):
    """Coordinates form field creation between views and FormEngine.

    Signals:
        dirty_changed: Emitted when the document dirty flag transitions.
        field_created: Emitted after a field is successfully created.
        field_deleted: Emitted after a field is deleted.
        tool_mode_changed: Emitted when the form tool mode changes.
    """

    dirty_changed = Signal(bool)
    field_created = Signal()
    field_deleted = Signal()
    tool_mode_changed = Signal(int)  # ToolMode int value

    def __init__(
        self,
        form_engine: FormEngine,
        tab_manager: Any,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the form creation presenter.

        Args:
            form_engine: The FormEngine service.
            tab_manager: The TabManager for accessing active tab state.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._engine = form_engine
        self._tab_manager = tab_manager
        self._tool_mode: ToolMode = ToolMode.NONE
        self._pending_field_type: FormFieldType | None = None

    @property
    def tool_mode(self) -> ToolMode:
        """Return the current tool mode."""
        return self._tool_mode

    @property
    def pending_field_type(self) -> FormFieldType | None:
        """Return the field type pending placement, or None."""
        return self._pending_field_type

    def set_tool_mode(self, mode: ToolMode) -> None:
        """Set the active form creation tool mode.

        Args:
            mode: A FORM_* ToolMode or NONE to deactivate.
        """
        self._tool_mode = mode
        self._pending_field_type = _MODE_TO_TYPE.get(mode)
        self.tool_mode_changed.emit(int(mode))

    def create_field(
        self,
        page_index: int,
        point: tuple[float, float],
        field_type: FormFieldType,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create a new form field at the given point.

        Calculates the bounding rect from the click point and default size,
        calls FormEngine.create_widget(), marks dirty, pushes undo action.

        Args:
            page_index: Zero-based page index.
            point: (x, y) click position in PDF coordinates.
            field_type: The type of field to create.
            properties: Optional properties dict from the popup.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return

        model = doc_presenter.model
        props = properties or {}

        # Calculate rect from point + default size
        w, h = _DEFAULT_SIZES.get(field_type, (200.0, 24.0))
        x0, y0 = point
        rect = (x0, y0, x0 + w, y0 + h)

        widget = self._engine.create_widget(
            doc_handle=model.doc_handle,
            page_index=page_index,
            field_type=field_type,
            rect=rect,
            properties=props,
        )

        model.dirty = True
        self.dirty_changed.emit(True)
        self.field_created.emit()

        # Push undo action
        undo_mgr = self._tab_manager.get_active_undo_manager()
        if undo_mgr is not None:
            stored_props = dict(props)
            stored_props["name"] = widget.field_name

            def undo() -> None:
                self._engine.delete_widget(model.doc_handle, page_index, widget)
                model.dirty = True
                self.dirty_changed.emit(True)
                self.field_deleted.emit()

            def redo() -> None:
                self._engine.create_widget(
                    model.doc_handle, page_index, field_type, rect, stored_props
                )
                model.dirty = True
                self.dirty_changed.emit(True)
                self.field_created.emit()

            undo_mgr.push(UndoAction(
                description=f"Add {field_type.value.title()} Field",
                undo_fn=undo,
                redo_fn=redo,
            ))

        logger.debug(
            "Created %s field '%s' on page %d at %s",
            field_type.value,
            widget.field_name,
            page_index,
            rect,
        )

    def delete_field(self, page_index: int, widget: Any) -> None:
        """Delete a form field and push undo action.

        Args:
            page_index: Zero-based page index.
            widget: The pymupdf Widget to delete.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return

        model = doc_presenter.model

        # Store info for undo before deleting
        field_name = widget.field_name
        field_type_int = widget.field_type
        rect = (widget.rect.x0, widget.rect.y0, widget.rect.x1, widget.rect.y1)

        self._engine.delete_widget(model.doc_handle, page_index, widget)

        model.dirty = True
        self.dirty_changed.emit(True)
        self.field_deleted.emit()

        # Push undo
        undo_mgr = self._tab_manager.get_active_undo_manager()
        if undo_mgr is not None:

            def undo() -> None:
                # Recreate with stored parameters — map int type back to enum
                reverse_map = {v: k for k, v in FormEngine._CREATE_TYPE_MAP.items()}
                ft = reverse_map.get(field_type_int)
                if ft is not None:
                    self._engine.create_widget(
                        model.doc_handle, page_index, ft, rect, {"name": field_name}
                    )
                model.dirty = True
                self.dirty_changed.emit(True)
                self.field_created.emit()

            def redo() -> None:
                # Re-find and delete by name
                page = model.doc_handle[page_index]
                for w in page.widgets():
                    if w.field_name == field_name:
                        self._engine.delete_widget(model.doc_handle, page_index, w)
                        break
                model.dirty = True
                self.dirty_changed.emit(True)
                self.field_deleted.emit()

            undo_mgr.push(UndoAction(
                description=f"Delete Field {field_name}",
                undo_fn=undo,
                redo_fn=redo,
            ))

        logger.debug("Deleted field '%s' on page %d", field_name, page_index)

    def update_field_properties(
        self, page_index: int, widget: Any, properties: dict[str, Any]
    ) -> None:
        """Update properties of an existing field and push undo action.

        Args:
            page_index: Zero-based page index.
            widget: The pymupdf Widget to update.
            properties: New property values.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return

        model = doc_presenter.model

        # Store old values for undo
        old_name = widget.field_name
        old_value = str(widget.field_value or "")

        self._engine.update_widget_properties(
            model.doc_handle, page_index, widget, properties
        )

        model.dirty = True
        self.dirty_changed.emit(True)

        undo_mgr = self._tab_manager.get_active_undo_manager()
        if undo_mgr is not None:
            old_props = {"name": old_name, "value": old_value}

            def undo() -> None:
                self._engine.update_widget_properties(
                    model.doc_handle, page_index, widget, old_props
                )
                model.dirty = True
                self.dirty_changed.emit(True)

            def redo() -> None:
                self._engine.update_widget_properties(
                    model.doc_handle, page_index, widget, properties
                )
                model.dirty = True
                self.dirty_changed.emit(True)

            undo_mgr.push(UndoAction(
                description=f"Edit Field {old_name}",
                undo_fn=undo,
                redo_fn=redo,
            ))

    def on_tab_switched(self, session_id: str) -> None:
        """Reset tool mode on tab switch.

        Args:
            session_id: New active tab session ID.
        """
        self._tool_mode = ToolMode.NONE
        self._pending_field_type = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_form_creation_presenter.py -v`
Expected: All PASS

- [ ] **Step 5: Run linting**

Run: `uv run ruff check k_pdf/presenters/form_creation_presenter.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add k_pdf/presenters/form_creation_presenter.py tests/test_form_creation_presenter.py
git commit -m "feat: add FormCreationPresenter for form field creation coordination"
```

---

### Task 6: Wire Form Creation into Viewport and MainWindow

**Files:**
- Modify: `k_pdf/views/pdf_viewport.py`
- Modify: `k_pdf/views/main_window.py`
- Test: `tests/test_form_creation_integration.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/test_form_creation_integration.py`:

```python
"""Integration tests for form field creation wiring."""

from __future__ import annotations

from k_pdf.core.annotation_model import ToolMode
from k_pdf.views.main_window import MainWindow
from k_pdf.views.pdf_viewport import PdfViewport


class TestViewportFormFieldSignal:
    def test_viewport_has_form_field_placed_signal(self, qtbot) -> None:
        vp = PdfViewport()
        qtbot.addWidget(vp)
        assert hasattr(vp, "form_field_placed")

    def test_viewport_handles_form_tool_modes(self, qtbot) -> None:
        vp = PdfViewport()
        qtbot.addWidget(vp)
        vp.set_tool_mode(ToolMode.FORM_TEXT)
        assert vp._tool_mode is ToolMode.FORM_TEXT


class TestMainWindowFormMenu:
    def test_tools_menu_has_form_fields_submenu(self, qtbot) -> None:
        win = MainWindow()
        qtbot.addWidget(win)
        actions = [a.text() for a in win._tools_menu.actions()]
        # Should contain a separator and form field actions
        assert any("Text Field" in a for a in actions) or any(
            "Form" in a.title() for a in win._tools_menu.actions()
            if hasattr(a, "title")
        )

    def test_form_field_signals_exist(self, qtbot) -> None:
        win = MainWindow()
        qtbot.addWidget(win)
        assert hasattr(win, "form_text_field_requested")
        assert hasattr(win, "form_checkbox_requested")
        assert hasattr(win, "form_dropdown_requested")
        assert hasattr(win, "form_radio_requested")
        assert hasattr(win, "form_signature_requested")

    def test_has_form_properties_panel(self, qtbot) -> None:
        win = MainWindow()
        qtbot.addWidget(win)
        assert hasattr(win, "form_properties_panel")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_form_creation_integration.py -v`
Expected: FAIL — `AttributeError: 'PdfViewport' object has no attribute 'form_field_placed'`

- [ ] **Step 3: Add form_field_placed signal to PdfViewport**

In `k_pdf/views/pdf_viewport.py`, add a new signal after the existing ones (around line 69):

```python
    form_field_placed = Signal(int, tuple, int)  # (page_index, (x, y), tool_mode_int)
```

In the `set_tool_mode` method, add handling for FORM_* modes. After the existing `elif mode in (ToolMode.STICKY_NOTE, ToolMode.TEXT_BOX):` block (around line 421), add:

```python
        elif mode.value >= 10:  # FORM_* modes
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
```

In `mousePressEvent`, add form field click handling. After the STICKY_NOTE check (around line 548), add:

```python
            if self._tool_mode.value >= 10:  # FORM_* modes
                self._handle_form_field_click(event)
                event.accept()
                return
```

Add the handler method to PdfViewport:

```python
    def _handle_form_field_click(self, event: QMouseEvent) -> None:
        """Handle click in form field placement mode — emit form_field_placed."""
        scene_pos = self.mapToScene(event.pos())
        page_index = self._page_at_scene_pos(scene_pos)
        if page_index < 0:
            return

        page_info = self._pages[page_index]
        item = self._page_items.get(page_index)
        if item is None:
            return
        zoom = item.boundingRect().width() / page_info.width if page_info.width else 1.0

        pdf_x, pdf_y = self._scene_to_pdf_coords(scene_pos, page_index, zoom)

        # Snap to page bounds
        pdf_x = max(0.0, min(pdf_x, page_info.width))
        pdf_y = max(0.0, min(pdf_y, page_info.height))

        self.form_field_placed.emit(page_index, (pdf_x, pdf_y), int(self._tool_mode))
```

- [ ] **Step 4: Add Form Fields submenu and signals to MainWindow**

In `k_pdf/views/main_window.py`, add new signals to the MainWindow class (after `select_all_requested`):

```python
    form_text_field_requested = Signal()
    form_checkbox_requested = Signal()
    form_dropdown_requested = Signal()
    form_radio_requested = Signal()
    form_signature_requested = Signal()
    find_replace_requested = Signal()
    text_edit_toggled = Signal(bool)
```

In `_setup_menus`, after the existing Tools menu actions (after the text_box_action block, around line 427), add:

```python
        self._tools_menu.addSeparator()

        # Form Fields submenu
        form_menu = QMenu("&Form Fields", self)
        self._tools_menu.addMenu(form_menu)

        self._form_text_action = QAction("\U0001f4dd Text Field", self)
        self._form_text_action.setEnabled(False)
        self._form_text_action.triggered.connect(self.form_text_field_requested.emit)
        form_menu.addAction(self._form_text_action)

        self._form_checkbox_action = QAction("\u2611 Checkbox", self)
        self._form_checkbox_action.setEnabled(False)
        self._form_checkbox_action.triggered.connect(self.form_checkbox_requested.emit)
        form_menu.addAction(self._form_checkbox_action)

        self._form_dropdown_action = QAction("\u25bc Dropdown", self)
        self._form_dropdown_action.setEnabled(False)
        self._form_dropdown_action.triggered.connect(self.form_dropdown_requested.emit)
        form_menu.addAction(self._form_dropdown_action)

        self._form_radio_action = QAction("\u25c9 Radio Button", self)
        self._form_radio_action.setEnabled(False)
        self._form_radio_action.triggered.connect(self.form_radio_requested.emit)
        form_menu.addAction(self._form_radio_action)

        self._form_signature_action = QAction("\u270d Signature Field", self)
        self._form_signature_action.setEnabled(False)
        self._form_signature_action.triggered.connect(self.form_signature_requested.emit)
        form_menu.addAction(self._form_signature_action)
```

In the Edit menu, after the Find action (around line 297), add:

```python
        find_replace_action = QAction("Find and &Replace...", self)
        find_replace_action.setShortcut(QKeySequence("Ctrl+H"))
        find_replace_action.triggered.connect(self.find_replace_requested.emit)
        edit_menu.addAction(find_replace_action)
```

In the Tools menu, after the text_box_action (around line 427), add:

```python
        self._text_edit_action = QAction("&Edit Text", self)
        self._text_edit_action.setShortcut(QKeySequence("Ctrl+E"))
        self._text_edit_action.setCheckable(True)
        self._text_edit_action.setEnabled(False)
        self._text_edit_action.setToolTip("Double-click text to edit in place")
        self._text_edit_action.toggled.connect(self.text_edit_toggled.emit)
        self._tool_action_group.addAction(self._text_edit_action)
        self._tools_menu.addAction(self._text_edit_action)
```

Add FormPropertiesPanel dock. In `__init__`, after the annotation summary panel setup (around line 150):

```python
        # Form Properties panel (right dock)
        from k_pdf.views.form_properties_panel import FormPropertiesPanel
        self._form_properties_panel = FormPropertiesPanel(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._form_properties_panel)
        self._form_properties_panel.hide()
```

Add property and method:

```python
    @property
    def form_properties_panel(self) -> FormPropertiesPanel:
        """Return the form properties panel dock widget."""
        return self._form_properties_panel
```

In the View menu, after the page manager toggle (around line 323), add:

```python
        toggle_form_props = self._form_properties_panel.toggleViewAction()
        toggle_form_props.setText("&Form Properties")
        toggle_form_props.setShortcut(QKeySequence("F8"))
        view_menu.addAction(toggle_form_props)
```

Add `set_form_tools_enabled` method:

```python
    def set_form_tools_enabled(self, enabled: bool) -> None:
        """Enable or disable form field creation actions.

        Args:
            enabled: True to enable, False to disable.
        """
        self._form_text_action.setEnabled(enabled)
        self._form_checkbox_action.setEnabled(enabled)
        self._form_dropdown_action.setEnabled(enabled)
        self._form_radio_action.setEnabled(enabled)
        self._form_signature_action.setEnabled(enabled)
        self._text_edit_action.setEnabled(enabled)
```

- [ ] **Step 4b: Add QMenu import if not present**

Check that `QMenu` is already imported in main_window.py (it is — line 25).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_form_creation_integration.py -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite for regressions**

Run: `uv run pytest --tb=short -q`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add k_pdf/views/pdf_viewport.py k_pdf/views/main_window.py tests/test_form_creation_integration.py
git commit -m "feat: add form field signals to viewport, menu items and properties panel to main window"
```

---

### Task 7: Wire Everything Together in KPdfApp

**Files:**
- Modify: `k_pdf/app.py`
- Test: `tests/test_form_creation_wiring.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_form_creation_wiring.py`:

```python
"""Tests that KPdfApp wires form creation presenter correctly."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp


class TestKPdfAppFormCreation:
    def test_app_has_form_creation_presenter(self, qtbot) -> None:
        app = QApplication.instance()
        k_app = KPdfApp(app)
        qtbot.addWidget(k_app.window)
        assert hasattr(k_app, "_form_creation_presenter")
        k_app.shutdown()

    def test_form_tools_enabled_on_document_load(self, qtbot) -> None:
        app = QApplication.instance()
        k_app = KPdfApp(app)
        qtbot.addWidget(k_app.window)
        # Form tools should be disabled initially
        assert not k_app.window._form_text_action.isEnabled()
        k_app.shutdown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_form_creation_wiring.py -v`
Expected: FAIL — `AttributeError: 'KPdfApp' object has no attribute '_form_creation_presenter'`

- [ ] **Step 3: Wire form creation in KPdfApp**

In `k_pdf/app.py`, add imports at the top (after existing presenter imports):

```python
from k_pdf.presenters.form_creation_presenter import FormCreationPresenter
from k_pdf.views.form_field_popup import FormFieldPopup
```

In `KPdfApp.__init__`, after `self._page_engine = PageEngine()` (around line 85), add:

```python
        self._form_creation_presenter = FormCreationPresenter(
            form_engine=self._form_engine,
            tab_manager=self._tab_manager,
        )
        self._form_field_popup: FormFieldPopup | None = None
```

In `_connect_signals`, add form creation wiring (after the existing undo wiring block):

```python
        # Form creation wiring
        self._window.form_text_field_requested.connect(
            lambda: self._form_creation_presenter.set_tool_mode(ToolMode.FORM_TEXT)
        )
        self._window.form_checkbox_requested.connect(
            lambda: self._form_creation_presenter.set_tool_mode(ToolMode.FORM_CHECKBOX)
        )
        self._window.form_dropdown_requested.connect(
            lambda: self._form_creation_presenter.set_tool_mode(ToolMode.FORM_DROPDOWN)
        )
        self._window.form_radio_requested.connect(
            lambda: self._form_creation_presenter.set_tool_mode(ToolMode.FORM_RADIO)
        )
        self._window.form_signature_requested.connect(
            lambda: self._form_creation_presenter.set_tool_mode(ToolMode.FORM_SIGNATURE)
        )
        self._form_creation_presenter.tool_mode_changed.connect(
            self._on_form_tool_mode_changed
        )
        self._form_creation_presenter.field_created.connect(self._on_form_field_changed)
        self._form_creation_presenter.field_deleted.connect(self._on_form_field_changed)
        self._form_creation_presenter.dirty_changed.connect(self._on_form_dirty_changed)

        # Form properties panel wiring
        self._window.form_properties_panel.delete_requested.connect(
            self._on_form_field_delete_from_panel
        )
        self._window.form_properties_panel.properties_changed.connect(
            self._on_form_field_props_changed
        )

        # Tab manager -> form creation
        self._tab_manager.tab_switched.connect(
            self._form_creation_presenter.on_tab_switched
        )
```

Add handler methods to KPdfApp:

```python
    # --- Form creation handlers ---

    def _on_form_tool_mode_changed(self, mode_int: int) -> None:
        """Update viewport tool mode for form field placement."""
        mode = ToolMode(mode_int)
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.set_tool_mode(mode)

    def _on_document_ready_form_creation(self, session_id: str, model: object) -> None:
        """Enable form creation tools when a document loads."""
        self._window.set_form_tools_enabled(True)
        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            viewport.form_field_placed.connect(self._on_form_field_placed)

    def _on_form_field_placed(
        self, page_index: int, point: tuple[float, float], tool_mode_int: int
    ) -> None:
        """Handle click-to-place from viewport — show FormFieldPopup."""
        field_type = self._form_creation_presenter.pending_field_type
        if field_type is None:
            return

        # Create and show popup
        self._form_field_popup = FormFieldPopup(field_type)
        self._form_field_popup.create_requested.connect(
            lambda props: self._on_popup_create(page_index, point, field_type, props)
        )
        self._form_field_popup.more_requested.connect(
            lambda props: self._on_popup_more(page_index, point, field_type, props)
        )
        self._form_field_popup.cancel_requested.connect(self._on_popup_cancel)

        viewport = self._tab_manager.get_active_viewport()
        if viewport is not None:
            global_pos = viewport.mapToGlobal(viewport.rect().center())
            self._form_field_popup.show_near(global_pos.x(), global_pos.y())

    def _on_popup_create(
        self,
        page_index: int,
        point: tuple[float, float],
        field_type: FormFieldType,
        props: dict,
    ) -> None:
        """Handle Create from FormFieldPopup."""
        self._form_creation_presenter.create_field(page_index, point, field_type, props)

    def _on_popup_more(
        self,
        page_index: int,
        point: tuple[float, float],
        field_type: FormFieldType,
        props: dict,
    ) -> None:
        """Handle More... from FormFieldPopup — create field and open properties panel."""
        self._form_creation_presenter.create_field(page_index, point, field_type, props)
        props["field_type"] = field_type
        props["page"] = page_index
        self._window.form_properties_panel.load_properties(props)
        self._window.form_properties_panel.show()

    def _on_popup_cancel(self) -> None:
        """Handle Cancel from FormFieldPopup."""
        pass  # Tool mode stays active for next click

    def _on_form_field_changed(self) -> None:
        """Re-render viewport after form field create/delete."""
        presenter = self._tab_manager.get_active_presenter()
        viewport = self._tab_manager.get_active_viewport()
        if presenter is not None and viewport is not None:
            presenter.cache.invalidate()
            presenter._pending_renders.clear()
            first, last = viewport.get_visible_page_range()
            if first >= 0:
                presenter.request_pages(list(range(first, last + 1)))

    def _on_form_field_delete_from_panel(self) -> None:
        """Handle Delete button from FormPropertiesPanel."""
        # For now, clear the panel — full widget selection tracking is future work
        self._window.form_properties_panel.clear()

    def _on_form_field_props_changed(self, props: dict) -> None:
        """Handle property changes from FormPropertiesPanel."""
        # Property updates apply via FormCreationPresenter
        pass
```

Also add the document_ready connection. In `_connect_signals`, add:

```python
        self._tab_manager.document_ready.connect(self._on_document_ready_form_creation)
```

Add the `FormFieldType` import at the top of `app.py`:

```python
from k_pdf.core.form_model import FormFieldType
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_form_creation_wiring.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest --tb=short -q`
Expected: All pass

- [ ] **Step 6: Run linting and type check**

Run: `uv run ruff check k_pdf/app.py && uv run ruff check k_pdf/views/main_window.py`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add k_pdf/app.py k_pdf/views/main_window.py k_pdf/views/pdf_viewport.py tests/test_form_creation_wiring.py
git commit -m "feat: wire form field creation end-to-end in KPdfApp"
```

---

### Task 8: Update Keyboard Shortcuts Dialog

**Files:**
- Modify: `k_pdf/views/keyboard_shortcuts_dialog.py`
- Test: `tests/test_keyboard_shortcuts_dialog.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_keyboard_shortcuts_dialog.py`:

```python
from k_pdf.views.keyboard_shortcuts_dialog import get_shortcut_definitions


class TestFormCreationShortcuts:
    def test_find_replace_shortcut_listed(self) -> None:
        defs = get_shortcut_definitions()
        all_actions = [
            action for _, shortcuts in defs for action, _ in shortcuts
        ]
        assert "Find and Replace" in all_actions

    def test_form_properties_shortcut_listed(self) -> None:
        defs = get_shortcut_definitions()
        all_actions = [
            action for _, shortcuts in defs for action, _ in shortcuts
        ]
        assert "Form Properties" in all_actions

    def test_edit_text_shortcut_listed(self) -> None:
        defs = get_shortcut_definitions()
        all_actions = [
            action for _, shortcuts in defs for action, _ in shortcuts
        ]
        assert "Edit Text" in all_actions
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_keyboard_shortcuts_dialog.py::TestFormCreationShortcuts -v`
Expected: FAIL — `AssertionError`

- [ ] **Step 3: Add new shortcuts to definitions**

In `k_pdf/views/keyboard_shortcuts_dialog.py`, in `get_shortcut_definitions()`:

Add to the "Edit" category (after "Copy"):
```python
                ("Find and Replace", f"{mod}+H"),
```

Add to the "View" category (after "Page Manager"):
```python
                ("Form Properties", "F8"),
```

Add to the "Tools" category (after "Text Selection"):
```python
                ("Edit Text", f"{mod}+E"),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_keyboard_shortcuts_dialog.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add k_pdf/views/keyboard_shortcuts_dialog.py tests/test_keyboard_shortcuts_dialog.py
git commit -m "feat: add form creation and text editing shortcuts to keyboard shortcuts dialog"
```

---

### Task 9: Add mypy Overrides for New Files

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Run mypy to identify needed overrides**

Run: `uv run mypy k_pdf/`
Expected: May show errors for new files due to PySide6 signal types.

- [ ] **Step 2: Add mypy overrides for new presenter and view modules**

In `pyproject.toml`, add these overrides (following the existing pattern):

```toml
[[tool.mypy.overrides]]
module = ["k_pdf.presenters.form_creation_presenter"]
disable_error_code = ["misc"]

[[tool.mypy.overrides]]
module = ["k_pdf.views.form_field_popup", "k_pdf.views.form_properties_panel"]
disable_error_code = ["misc", "no-any-return", "unused-ignore"]
```

- [ ] **Step 3: Run mypy and verify it passes**

Run: `uv run mypy k_pdf/`
Expected: No errors

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest --tb=short -q`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add mypy overrides for form creation modules"
```

---

### Task 10: Final Verification — Full Lint, Type Check, Tests

**Files:** None (verification only)

- [ ] **Step 1: Run ruff check**

Run: `uv run ruff check .`
Expected: No errors

- [ ] **Step 2: Run ruff format check**

Run: `uv run ruff format --check .`
Expected: No errors

- [ ] **Step 3: Run mypy strict**

Run: `uv run mypy k_pdf/`
Expected: No errors

- [ ] **Step 4: Run full test suite with coverage**

Run: `uv run pytest --cov=k_pdf --cov-report=term-missing -q`
Expected: All tests pass, coverage ≥ 65%

- [ ] **Step 5: Commit spec document if not already tracked**

```bash
git add docs/superpowers/specs/2026-04-06-form-creation-text-editing-design.md
git add docs/superpowers/plans/2026-04-06-form-creation.md
git commit -m "docs: add form creation and text editing design spec and implementation plan"
```
