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
