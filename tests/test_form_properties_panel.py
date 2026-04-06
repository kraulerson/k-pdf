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
        assert panel._options_list.count() == 2

    def test_load_checkbox_field_properties(self, qtbot) -> None:
        panel = FormPropertiesPanel()
        qtbot.addWidget(panel)
        panel.load_properties(
            {
                "name": "agree",
                "field_type": FormFieldType.CHECKBOX,
                "page": 0,
                "rect": (72, 140, 86, 154),
            }
        )
        assert panel._name_edit.text() == "agree"
        assert panel._stack.currentIndex() == 1

    def test_load_signature_field_properties(self, qtbot) -> None:
        panel = FormPropertiesPanel()
        qtbot.addWidget(panel)
        panel.load_properties(
            {
                "name": "sig",
                "field_type": FormFieldType.SIGNATURE,
                "page": 2,
                "rect": (72, 260, 272, 320),
            }
        )
        assert panel._name_edit.text() == "sig"
        assert panel._stack.currentIndex() == 1

    def test_clear_shows_empty_state(self, qtbot) -> None:
        panel = FormPropertiesPanel()
        qtbot.addWidget(panel)
        panel.load_properties(
            {
                "name": "test",
                "field_type": FormFieldType.TEXT,
                "page": 0,
                "rect": (0, 0, 100, 20),
            }
        )
        panel.clear()
        assert panel._stack.currentIndex() == 0


class TestFormPropertiesPanelSignals:
    def test_delete_emits_signal(self, qtbot) -> None:
        panel = FormPropertiesPanel()
        qtbot.addWidget(panel)
        panel.load_properties(
            {
                "name": "test",
                "field_type": FormFieldType.TEXT,
                "page": 0,
                "rect": (0, 0, 100, 20),
            }
        )

        with qtbot.waitSignal(panel.delete_requested, timeout=1000):
            panel._delete_btn.click()

    def test_property_changed_emits_signal(self, qtbot) -> None:
        panel = FormPropertiesPanel()
        qtbot.addWidget(panel)
        panel.load_properties(
            {
                "name": "test",
                "field_type": FormFieldType.TEXT,
                "page": 0,
                "rect": (0, 0, 100, 20),
            }
        )

        with qtbot.waitSignal(panel.properties_changed, timeout=1000):
            panel._name_edit.setText("new_name")
            panel._name_edit.editingFinished.emit()


class TestFormPropertiesPanelGather:
    def test_gather_properties_includes_text_fields_when_not_shown(self, qtbot) -> None:
        panel = FormPropertiesPanel()
        qtbot.addWidget(panel)
        panel.load_properties(
            {
                "name": "test",
                "field_type": FormFieldType.TEXT,
                "page": 0,
                "rect": (10, 20, 110, 44),
                "placeholder": "hello",
                "max_length": 50,
            }
        )
        props = panel.gather_properties()
        assert props["name"] == "test"
        assert props["placeholder"] == "hello"
        assert props["max_length"] == 50
