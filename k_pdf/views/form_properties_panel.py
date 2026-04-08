"""FormPropertiesPanel — docked advanced form field property editor.

QDockWidget that shows a form with all editable properties for the currently
selected form field. Uses a QStackedWidget to toggle between an empty state
and the property form.
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
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from k_pdf.core.form_model import FormFieldType

logger = logging.getLogger("k_pdf.views.form_properties_panel")


class FormPropertiesPanel(QDockWidget):
    """Right-docked advanced property editor for form fields.

    Signals:
        properties_changed: Emitted with a dict of current values when any
            property changes.
        delete_requested: Emitted when the user clicks Delete Field.
    """

    properties_changed = Signal(dict)
    delete_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the FormPropertiesPanel dock widget."""
        super().__init__("Form Properties", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.setMinimumWidth(220)

        # Track whether we are currently loading (suppress spurious signals)
        self._loading = False

        # Track current field type for gather_properties() (avoids isVisible() in headless env)
        self._current_field_type: FormFieldType | None = None

        # Root stacked widget — index 0: empty, index 1: form
        self._stack = QStackedWidget()

        # --- Empty state (index 0) ---
        self._empty_label = QLabel("Select a form field to edit properties")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._stack.addWidget(self._empty_label)

        # --- Form container (index 1) ---
        self._form_container = self._build_form_container()
        self._stack.addWidget(self._form_container)

        # Start with empty state
        self._stack.setCurrentIndex(0)

        self.setWidget(self._stack)

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _build_form_container(self) -> QWidget:
        """Build and return the scrollable form container widget."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # --- Common properties group ---
        common_group = QGroupBox("Field Properties")
        form = QFormLayout(common_group)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self._type_label = QLabel()
        self._type_label.setAccessibleName("Field type")
        form.addRow("Type:", self._type_label)

        self._page_label = QLabel()
        self._page_label.setAccessibleName("Page number")
        form.addRow("Page:", self._page_label)

        self._name_edit = QLineEdit()
        self._name_edit.setAccessibleName("Field name")
        self._name_edit.editingFinished.connect(self._on_property_changed)
        form.addRow("Name:", self._name_edit)

        # Geometry
        geo_group = QGroupBox("Position & Size")
        geo_layout = QFormLayout(geo_group)
        geo_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self._x_spin = QDoubleSpinBox()
        self._x_spin.setRange(-9999, 9999)
        self._x_spin.setDecimals(2)
        self._x_spin.setAccessibleName("X position")
        self._x_spin.editingFinished.connect(self._on_property_changed)
        geo_layout.addRow("X:", self._x_spin)

        self._y_spin = QDoubleSpinBox()
        self._y_spin.setRange(-9999, 9999)
        self._y_spin.setDecimals(2)
        self._y_spin.setAccessibleName("Y position")
        self._y_spin.editingFinished.connect(self._on_property_changed)
        geo_layout.addRow("Y:", self._y_spin)

        self._w_spin = QDoubleSpinBox()
        self._w_spin.setRange(0, 9999)
        self._w_spin.setDecimals(2)
        self._w_spin.setAccessibleName("Width")
        self._w_spin.editingFinished.connect(self._on_property_changed)
        geo_layout.addRow("Width:", self._w_spin)

        self._h_spin = QDoubleSpinBox()
        self._h_spin.setRange(0, 9999)
        self._h_spin.setDecimals(2)
        self._h_spin.setAccessibleName("Height")
        self._h_spin.editingFinished.connect(self._on_property_changed)
        geo_layout.addRow("Height:", self._h_spin)

        self._readonly_check = QCheckBox("Read-only")
        self._readonly_check.setAccessibleName("Read-only field")
        self._readonly_check.checkStateChanged.connect(self._on_property_changed)
        form.addRow("", self._readonly_check)

        layout.addWidget(common_group)
        layout.addWidget(geo_group)

        # --- Text-specific group ---
        self._text_group = QGroupBox("Text Field Options")
        text_layout = QFormLayout(self._text_group)
        text_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self._placeholder_edit = QLineEdit()
        self._placeholder_edit.setAccessibleName("Placeholder text")
        self._placeholder_edit.editingFinished.connect(self._on_property_changed)
        text_layout.addRow("Placeholder:", self._placeholder_edit)

        self._max_length_spin = QSpinBox()
        self._max_length_spin.setRange(0, 10000)
        self._max_length_spin.setSpecialValueText("No limit")
        self._max_length_spin.setAccessibleName("Maximum character length")
        self._max_length_spin.editingFinished.connect(self._on_property_changed)
        text_layout.addRow("Max Length:", self._max_length_spin)

        self._multiline_check = QCheckBox("Multiline")
        self._multiline_check.setAccessibleName("Multiline text field")
        self._multiline_check.checkStateChanged.connect(self._on_property_changed)
        text_layout.addRow("", self._multiline_check)

        layout.addWidget(self._text_group)

        # --- Dropdown-specific group ---
        self._dropdown_group = QGroupBox("Dropdown Options")
        dd_layout = QVBoxLayout(self._dropdown_group)

        self._options_list = QListWidget()
        self._options_list.setAccessibleName("Dropdown options")
        self._options_list.setMaximumHeight(120)
        dd_layout.addWidget(self._options_list)

        dd_btn_row = QHBoxLayout()
        self._add_option_btn = QPushButton("Add")
        self._add_option_btn.setAccessibleName("Add option")
        self._add_option_btn.clicked.connect(self._on_add_option)
        self._remove_option_btn = QPushButton("Remove")
        self._remove_option_btn.setAccessibleName("Remove selected option")
        self._remove_option_btn.clicked.connect(self._on_remove_option)
        dd_btn_row.addWidget(self._add_option_btn)
        dd_btn_row.addWidget(self._remove_option_btn)
        dd_btn_row.addStretch()
        dd_layout.addLayout(dd_btn_row)

        layout.addWidget(self._dropdown_group)

        # --- Radio-specific group ---
        self._radio_group = QGroupBox("Radio Button Options")
        radio_layout = QFormLayout(self._radio_group)
        radio_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self._radio_group_edit = QLineEdit()
        self._radio_group_edit.setAccessibleName("Radio button group name")
        self._radio_group_edit.editingFinished.connect(self._on_property_changed)
        radio_layout.addRow("Group:", self._radio_group_edit)

        self._radio_value_edit = QLineEdit()
        self._radio_value_edit.setAccessibleName("Radio button value")
        self._radio_value_edit.editingFinished.connect(self._on_property_changed)
        radio_layout.addRow("Value:", self._radio_value_edit)

        layout.addWidget(self._radio_group)

        # --- Delete button ---
        self._delete_btn = QPushButton("Delete Field")
        self._delete_btn.setAccessibleName("Delete this form field")
        self._delete_btn.clicked.connect(self.delete_requested)
        layout.addWidget(self._delete_btn)

        layout.addStretch()

        scroll.setWidget(inner)
        return scroll

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_properties(self, props: dict[str, Any]) -> None:
        """Populate all property fields from *props* and show the form.

        Args:
            props: Property dict — keys as produced by FormFieldDescriptor or
                gather_properties().
        """
        self._loading = True
        try:
            field_type: FormFieldType = props.get("field_type", FormFieldType.TEXT)
            self._current_field_type = field_type

            # Common fields
            self._type_label.setText(field_type.value.title())
            page = props.get("page", 0)
            self._page_label.setText(str(page + 1))  # display 1-based
            self._name_edit.setText(props.get("name", ""))
            self._readonly_check.setChecked(bool(props.get("read_only", False)))

            # Geometry from rect (x0, y0, x1, y1)
            rect = props.get("rect", (0.0, 0.0, 0.0, 0.0))
            x0, y0, x1, y1 = rect
            self._x_spin.setValue(x0)
            self._y_spin.setValue(y0)
            self._w_spin.setValue(max(0.0, x1 - x0))
            self._h_spin.setValue(max(0.0, y1 - y0))

            # Show/hide type-specific groups
            is_text = field_type is FormFieldType.TEXT
            is_dropdown = field_type is FormFieldType.DROPDOWN
            is_radio = field_type is FormFieldType.RADIO

            self._text_group.setVisible(is_text)
            self._dropdown_group.setVisible(is_dropdown)
            self._radio_group.setVisible(is_radio)

            # Text-specific
            if is_text:
                self._placeholder_edit.setText(props.get("placeholder", ""))
                self._max_length_spin.setValue(props.get("max_length", 0) or 0)
                self._multiline_check.setChecked(bool(props.get("multiline", False)))

            # Dropdown-specific
            if is_dropdown:
                self._options_list.clear()
                for opt in props.get("options", []):
                    self._options_list.addItem(opt)

            # Radio-specific
            if is_radio:
                self._radio_group_edit.setText(props.get("group_name", ""))
                self._radio_value_edit.setText(props.get("value", ""))

        finally:
            self._loading = False

        # Switch to form view
        self._stack.setCurrentIndex(1)

    def clear(self) -> None:
        """Clear all inputs and show the empty state."""
        self._current_field_type = None
        self._stack.setCurrentIndex(0)

    def gather_properties(self) -> dict[str, Any]:
        """Collect current widget values into a properties dict.

        Returns:
            A dict of property name → value for the currently displayed field.
        """
        props: dict[str, Any] = {
            "name": self._name_edit.text(),
            "read_only": self._readonly_check.isChecked(),
        }

        x = self._x_spin.value()
        y = self._y_spin.value()
        w = self._w_spin.value()
        h = self._h_spin.value()
        props["rect"] = (x, y, x + w, y + h)

        # Text-specific
        if self._current_field_type is FormFieldType.TEXT:
            props["placeholder"] = self._placeholder_edit.text()
            max_len = self._max_length_spin.value()
            if max_len > 0:
                props["max_length"] = max_len
            props["multiline"] = self._multiline_check.isChecked()

        # Dropdown-specific
        if self._current_field_type is FormFieldType.DROPDOWN:
            props["options"] = [
                self._options_list.item(i).text() for i in range(self._options_list.count())
            ]

        # Radio-specific
        if self._current_field_type is FormFieldType.RADIO:
            props["group_name"] = self._radio_group_edit.text()
            props["value"] = self._radio_value_edit.text()

        return props

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_property_changed(self) -> None:
        """Emit properties_changed with the current gathered values."""
        if self._loading:
            return
        self.properties_changed.emit(self.gather_properties())

    def _on_add_option(self) -> None:
        """Prompt (inline) to add an option to the dropdown list."""
        # Use a simple inline approach: add a blank editable item
        self._options_list.addItem("")
        new_row = self._options_list.count() - 1
        item = self._options_list.item(new_row)
        if item is not None:
            self._options_list.editItem(item)
        self._on_property_changed()

    def _on_remove_option(self) -> None:
        """Remove the currently selected option from the list."""
        row = self._options_list.currentRow()
        if row >= 0:
            self._options_list.takeItem(row)
            self._on_property_changed()
