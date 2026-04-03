"""Tests for form field model types."""

from __future__ import annotations

import pytest

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
        descriptor = FormFieldDescriptor(
            name="first_name",
            field_type=FormFieldType.TEXT,
            page=0,
            rect=(72.0, 100.0, 300.0, 120.0),
        )
        assert descriptor.name == "first_name"
        assert descriptor.field_type is FormFieldType.TEXT
        assert descriptor.page == 0
        assert descriptor.rect == (72.0, 100.0, 300.0, 120.0)

    def test_default_value_is_empty_string(self) -> None:
        descriptor = FormFieldDescriptor(
            name="f", field_type=FormFieldType.TEXT, page=0, rect=(0, 0, 1, 1)
        )
        assert descriptor.value == ""

    def test_default_options_is_empty_list(self) -> None:
        descriptor = FormFieldDescriptor(
            name="f", field_type=FormFieldType.DROPDOWN, page=0, rect=(0, 0, 1, 1)
        )
        assert descriptor.options == []

    def test_default_read_only_is_false(self) -> None:
        descriptor = FormFieldDescriptor(
            name="f", field_type=FormFieldType.TEXT, page=0, rect=(0, 0, 1, 1)
        )
        assert descriptor.read_only is False

    def test_default_max_length_is_none(self) -> None:
        descriptor = FormFieldDescriptor(
            name="f", field_type=FormFieldType.TEXT, page=0, rect=(0, 0, 1, 1)
        )
        assert descriptor.max_length is None

    def test_frozen_immutable(self) -> None:
        descriptor = FormFieldDescriptor(
            name="f", field_type=FormFieldType.TEXT, page=0, rect=(0, 0, 1, 1)
        )
        with pytest.raises(AttributeError):
            descriptor.name = "changed"  # type: ignore[misc]

    def test_custom_options(self) -> None:
        descriptor = FormFieldDescriptor(
            name="state",
            field_type=FormFieldType.DROPDOWN,
            page=0,
            rect=(0, 0, 1, 1),
            options=["CA", "TX", "NY"],
        )
        assert descriptor.options == ["CA", "TX", "NY"]

    def test_custom_max_length(self) -> None:
        descriptor = FormFieldDescriptor(
            name="zip",
            field_type=FormFieldType.TEXT,
            page=0,
            rect=(0, 0, 1, 1),
            max_length=5,
        )
        assert descriptor.max_length == 5
