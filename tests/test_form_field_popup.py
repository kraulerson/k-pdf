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
