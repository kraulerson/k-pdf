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
        assert panel._stack.currentIndex() == 0


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
        assert panel._stack.currentIndex() == 1

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
        assert panel._stack.currentIndex() == 0


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
