"""Form presenter — manages form field overlays, save flow, and dirty coordination.

Detects AcroForm fields on document open, creates Qt widget overlays,
tracks per-tab field values, and coordinates save/save-as operations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from k_pdf.core.document_model import DocumentModel
from k_pdf.core.form_model import FormFieldDescriptor
from k_pdf.services.form_engine import FormEngine

logger = logging.getLogger("k_pdf.presenters.form_presenter")


class FormPresenter(QObject):
    """Coordinates form field detection, overlay lifecycle, and save flow."""

    dirty_changed = Signal(bool)
    form_detected = Signal(int)  # field count
    xfa_detected = Signal(str)  # notification message
    save_succeeded = Signal()
    save_failed = Signal(str)  # error message

    def __init__(
        self,
        form_engine: FormEngine,
        tab_manager: Any,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the form presenter.

        Args:
            form_engine: The FormEngine service.
            tab_manager: The TabManager for accessing active tab state.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._engine = form_engine
        self._tab_manager = tab_manager

        # Per-session state
        self._models: dict[str, DocumentModel] = {}
        self._field_values: dict[str, dict[str, str]] = {}
        self._field_descriptors: dict[str, list[FormFieldDescriptor]] = {}

    def on_document_opened(self, session_id: str, model: DocumentModel) -> None:
        """Handle document open — detect form fields and emit signals.

        Args:
            session_id: The tab session ID.
            model: The document model.
        """
        self._models[session_id] = model

        # Check for XFA forms first
        if self._engine.is_xfa_form(model.doc_handle):
            self.xfa_detected.emit("XFA dynamic forms not supported. Only AcroForms supported.")
            return

        # Detect AcroForm fields
        fields = self._engine.detect_fields(model.doc_handle)
        if not fields:
            return

        self._field_descriptors[session_id] = fields
        self._field_values[session_id] = {f.name: f.value for f in fields}

        self.form_detected.emit(len(fields))
        logger.debug("Detected %d form fields for session %s", len(fields), session_id)

    def on_field_changed(self, session_id: str, field_name: str, value: Any) -> None:
        """Handle form field value change.

        Args:
            session_id: The tab session ID.
            field_name: The changed field name.
            value: The new value.
        """
        model = self._models.get(session_id)
        if model is None:
            return

        if session_id not in self._field_values:
            self._field_values[session_id] = {}
        self._field_values[session_id][field_name] = str(value)

        model.dirty = True
        self.dirty_changed.emit(True)

    def save(self, session_id: str) -> None:
        """Save the document (form values + file).

        Args:
            session_id: The tab session ID.
        """
        model = self._models.get(session_id)
        if model is None:
            return

        field_values = self._field_values.get(session_id, {})
        try:
            self._engine.write_fields(model.doc_handle, field_values)
            self._engine.save_document(model.doc_handle, model.file_path, is_new_path=False)
            model.dirty = False
            self.dirty_changed.emit(False)
            self.save_succeeded.emit()
            logger.debug("Saved document for session %s", session_id)
        except Exception as e:
            error_msg = (
                f"Could not save to {model.file_path}. {e}. "
                "Try File > Save As to save to a different location."
            )
            self.save_failed.emit(error_msg)
            logger.warning("Save failed for session %s: %s", session_id, e)

    def save_as(self, session_id: str, new_path: Path) -> None:
        """Save the document to a new path.

        Args:
            session_id: The tab session ID.
            new_path: The target file path.
        """
        model = self._models.get(session_id)
        if model is None:
            return

        field_values = self._field_values.get(session_id, {})
        try:
            self._engine.write_fields(model.doc_handle, field_values)
            self._engine.save_document(model.doc_handle, new_path, is_new_path=True)
            model.file_path = new_path
            model.dirty = False
            self.dirty_changed.emit(False)
            self.save_succeeded.emit()
            logger.debug("Saved document as %s for session %s", new_path, session_id)
        except Exception as e:
            error_msg = f"Could not save to {new_path}. {e}. Try a different location."
            self.save_failed.emit(error_msg)

    def on_tab_switched(self, session_id: str) -> None:
        """Handle tab switch.

        Args:
            session_id: The new active tab's session ID.
        """
        # Form overlays are managed per-viewport by the viewport itself.
        # This hook exists for future per-tab state management.

    def on_tab_closed(self, session_id: str) -> None:
        """Clean up per-tab form state.

        Args:
            session_id: The closed tab's session ID.
        """
        self._models.pop(session_id, None)
        self._field_values.pop(session_id, None)
        self._field_descriptors.pop(session_id, None)

    def get_field_descriptors(self, session_id: str) -> list[FormFieldDescriptor]:
        """Return the form field descriptors for a session.

        Args:
            session_id: The tab session ID.

        Returns:
            List of descriptors, or empty list.
        """
        return self._field_descriptors.get(session_id, [])

    def has_form_fields(self, session_id: str) -> bool:
        """Check if a session has form fields.

        Args:
            session_id: The tab session ID.

        Returns:
            True if the session has detected form fields.
        """
        return bool(self._field_descriptors.get(session_id))
