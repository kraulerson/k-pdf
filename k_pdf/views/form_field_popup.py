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

    create_requested = Signal(dict)
    more_requested = Signal(dict)
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

        type_label = _TYPE_PREFIX.get(field_type, "field").replace("_", " ").title()
        title = QLabel(f"{type_label} Properties")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        layout.addWidget(QLabel("Field Name"))
        self._name_edit = QLineEdit()
        self._name_edit.setText(_next_auto_name(field_type))
        self._name_edit.setAccessibleName("Field name")
        layout.addWidget(self._name_edit)

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
