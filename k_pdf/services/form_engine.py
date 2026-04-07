"""AcroForm field detection, filling, and document saving.

PyMuPDF form operations isolated here per AGPL containment rule.
No other layer imports fitz/pymupdf directly for form operations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

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

    # Map our field types to pymupdf widget type constants
    _CREATE_TYPE_MAP: ClassVar[dict[FormFieldType, int]] = {
        FormFieldType.TEXT: pymupdf.PDF_WIDGET_TYPE_TEXT,
        FormFieldType.CHECKBOX: pymupdf.PDF_WIDGET_TYPE_CHECKBOX,
        FormFieldType.DROPDOWN: pymupdf.PDF_WIDGET_TYPE_COMBOBOX,
        FormFieldType.RADIO: pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON,
    }

    @staticmethod
    def widget_type_to_field_type(widget_type_int: int) -> FormFieldType | None:
        """Map a pymupdf widget type integer to FormFieldType.

        Covers all five supported field types including SIGNATURE (type 7),
        which is absent from _CREATE_TYPE_MAP because PyMuPDF has no named
        constant for it.

        Args:
            widget_type_int: The pymupdf Widget.field_type integer value.

        Returns:
            The matching FormFieldType, or None if the type is unsupported.
        """
        _reverse: dict[int, FormFieldType] = {
            pymupdf.PDF_WIDGET_TYPE_TEXT: FormFieldType.TEXT,
            pymupdf.PDF_WIDGET_TYPE_CHECKBOX: FormFieldType.CHECKBOX,
            pymupdf.PDF_WIDGET_TYPE_COMBOBOX: FormFieldType.DROPDOWN,
            pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON: FormFieldType.RADIO,
            7: FormFieldType.SIGNATURE,  # no named constant in pymupdf
        }
        return _reverse.get(widget_type_int)

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
            widget.field_type = 7  # pymupdf signature widget type
        else:
            widget.field_type = self._CREATE_TYPE_MAP[field_type]

        widget.rect = pymupdf.Rect(*rect)
        widget.field_name = props.get("name", f"field_{page_index}_{id(widget)}")

        if field_type is FormFieldType.TEXT and "max_length" in props:
            widget.text_maxlen = props["max_length"]

        if field_type is FormFieldType.DROPDOWN and "options" in props:
            widget.choice_values = props["options"]

        # Radio buttons must start in the Off state when first created;
        # PyMuPDF's _checker will error on bad xref if field_value is truthy.
        if field_type is FormFieldType.RADIO and "value" not in props:
            widget.field_value = "Off"
        elif "value" in props:
            widget.field_value = props["value"]

        page.add_widget(widget)
        widget.update()  # Generate appearance stream so get_pixmap renders it
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
