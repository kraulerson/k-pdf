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

                max_len: int | None = None
                if hasattr(widget, "text_maxlen") and widget.text_maxlen > 0:
                    max_len = widget.text_maxlen

                fields.append(
                    FormFieldDescriptor(
                        name=widget.field_name or f"unnamed_{page_index}_{len(fields)}",
                        field_type=field_type,
                        page=page_index,
                        rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                        value=str(widget.field_value or ""),
                        options=options,
                        read_only=bool(widget.field_flags & 1),
                        max_length=max_len,
                    )
                )

        logger.debug("Detected %d form fields", len(fields))
        return fields

    def is_xfa_form(self, doc_handle: Any) -> bool:
        """Check if the document contains XFA form data.

        PyMuPDF's is_form_pdf returns:
        - 0: not a form
        - 1: XFA only
        - 2: XFA + AcroForm
        - 3: AcroForm only

        Args:
            doc_handle: A pymupdf.Document handle.

        Returns:
            True if the document has XFA data (is_form_pdf in {1, 2}).
        """
        form_type = doc_handle.is_form_pdf
        return form_type in (1, 2)

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
