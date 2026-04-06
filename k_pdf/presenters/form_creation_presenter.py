"""Form field creation presenter.

Coordinates tool modes, click-to-place, FormFieldPopup, FormPropertiesPanel,
undo actions, and dirty flag management for new form field creation.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal

from k_pdf.core.annotation_model import ToolMode
from k_pdf.core.form_model import FormFieldType
from k_pdf.core.undo_manager import UndoAction
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.form_engine import FormEngine

logger = logging.getLogger("k_pdf.presenters.form_creation_presenter")

# Map form tool modes to field types
_MODE_TO_TYPE: dict[ToolMode, FormFieldType] = {
    ToolMode.FORM_TEXT: FormFieldType.TEXT,
    ToolMode.FORM_CHECKBOX: FormFieldType.CHECKBOX,
    ToolMode.FORM_DROPDOWN: FormFieldType.DROPDOWN,
    ToolMode.FORM_RADIO: FormFieldType.RADIO,
    ToolMode.FORM_SIGNATURE: FormFieldType.SIGNATURE,
}

# Default field sizes in PDF points
_DEFAULT_SIZES: dict[FormFieldType, tuple[float, float]] = {
    FormFieldType.TEXT: (200.0, 24.0),
    FormFieldType.CHECKBOX: (14.0, 14.0),
    FormFieldType.DROPDOWN: (200.0, 24.0),
    FormFieldType.RADIO: (14.0, 14.0),
    FormFieldType.SIGNATURE: (200.0, 60.0),
}


class FormCreationPresenter(QObject):
    """Coordinates form field creation between views and FormEngine.

    Signals:
        dirty_changed: Emitted when the document dirty flag transitions.
        field_created: Emitted after a field is successfully created.
        field_deleted: Emitted after a field is deleted.
        tool_mode_changed: Emitted when the form tool mode changes.
    """

    dirty_changed = Signal(bool)
    field_created = Signal()
    field_deleted = Signal()
    tool_mode_changed = Signal(int)  # ToolMode int value

    def __init__(
        self,
        form_engine: FormEngine,
        tab_manager: TabManager,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the form creation presenter.

        Args:
            form_engine: The FormEngine for PyMuPDF widget operations.
            tab_manager: The TabManager for accessing active tab state.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._engine = form_engine
        self._tab_manager = tab_manager
        self._tool_mode: ToolMode = ToolMode.NONE
        self._pending_field_type: FormFieldType | None = None
        self._tab_manager.tab_switched.connect(self.on_tab_switched)

    @property
    def tool_mode(self) -> ToolMode:
        """Return the current active tool mode."""
        return self._tool_mode

    @property
    def pending_field_type(self) -> FormFieldType | None:
        """Return the field type associated with the current tool mode, or None."""
        return self._pending_field_type

    def set_tool_mode(self, mode: ToolMode) -> None:
        """Set the active form tool mode.

        Updates the pending field type based on the mode and emits tool_mode_changed.

        Args:
            mode: The ToolMode to activate.
        """
        self._tool_mode = mode
        self._pending_field_type = _MODE_TO_TYPE.get(mode)
        self.tool_mode_changed.emit(int(mode))

    def create_field(
        self,
        page_index: int,
        point: tuple[float, float],
        field_type: FormFieldType,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create a new form field at the given point.

        Places a new field widget on the page with the default size for that
        field type, marks the document dirty, emits field_created, and pushes
        an undo action.

        Args:
            page_index: Zero-based page index.
            point: (x, y) top-left position in PDF coordinates.
            field_type: The type of form field to create.
            properties: Optional initial property overrides (name, value, etc.).
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return

        model = doc_presenter.model
        props = properties or {}

        w, h = _DEFAULT_SIZES.get(field_type, (200.0, 24.0))
        x0, y0 = point
        rect = (x0, y0, x0 + w, y0 + h)

        widget = self._engine.create_widget(
            doc_handle=model.doc_handle,
            page_index=page_index,
            field_type=field_type,
            rect=rect,
            properties=props,
        )

        model.dirty = True
        self.dirty_changed.emit(True)
        self.field_created.emit()

        logger.debug(
            "Created %s field '%s' on page %d at (%s, %s)",
            field_type.value,
            widget.field_name,
            page_index,
            x0,
            y0,
        )

        # Push undo action
        undo_mgr = self._tab_manager.get_active_undo_manager()
        if undo_mgr is not None:
            stored_props = dict(props)
            stored_props["name"] = widget.field_name

            def undo() -> None:
                self._engine.delete_widget(model.doc_handle, page_index, widget)
                model.dirty = True
                self.dirty_changed.emit(True)
                self.field_deleted.emit()

            def redo() -> None:
                self._engine.create_widget(
                    model.doc_handle, page_index, field_type, rect, stored_props
                )
                model.dirty = True
                self.dirty_changed.emit(True)
                self.field_created.emit()

            undo_mgr.push(
                UndoAction(
                    description=f"Add {field_type.value.title()} Field",
                    undo_fn=undo,
                    redo_fn=redo,
                )
            )

    def delete_field(self, page_index: int, widget: Any) -> None:
        """Delete a form field and push undo action.

        Args:
            page_index: Zero-based page index.
            widget: The pymupdf Widget to delete.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return

        model = doc_presenter.model
        field_name = widget.field_name
        field_type = self._engine.widget_type_to_field_type(widget.field_type)
        rect = (widget.rect.x0, widget.rect.y0, widget.rect.x1, widget.rect.y1)

        self._engine.delete_widget(model.doc_handle, page_index, widget)

        model.dirty = True
        self.dirty_changed.emit(True)
        self.field_deleted.emit()

        logger.debug("Deleted field '%s' on page %d", field_name, page_index)

        undo_mgr = self._tab_manager.get_active_undo_manager()
        if undo_mgr is not None:

            def undo() -> None:
                if field_type is not None:
                    self._engine.create_widget(
                        model.doc_handle, page_index, field_type, rect, {"name": field_name}
                    )
                model.dirty = True
                self.dirty_changed.emit(True)
                self.field_created.emit()

            def redo() -> None:
                page = model.doc_handle[page_index]
                for w in page.widgets():
                    if w.field_name == field_name:
                        self._engine.delete_widget(model.doc_handle, page_index, w)
                        break
                model.dirty = True
                self.dirty_changed.emit(True)
                self.field_deleted.emit()

            undo_mgr.push(
                UndoAction(
                    description=f"Delete Field {field_name}",
                    undo_fn=undo,
                    redo_fn=redo,
                )
            )

    def update_field_properties(
        self, page_index: int, widget: Any, properties: dict[str, Any]
    ) -> None:
        """Update properties of an existing field and push undo action.

        Args:
            page_index: Zero-based page index.
            widget: The pymupdf Widget to update.
            properties: Dict of properties to update (name, value, options, etc.).
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return

        model = doc_presenter.model
        old_name = widget.field_name
        old_value = str(widget.field_value or "")

        self._engine.update_widget_properties(model.doc_handle, page_index, widget, properties)

        model.dirty = True
        self.dirty_changed.emit(True)

        logger.debug("Updated field '%s' on page %d", old_name, page_index)

        undo_mgr = self._tab_manager.get_active_undo_manager()
        if undo_mgr is not None:
            old_props = {"name": old_name, "value": old_value}

            def undo() -> None:
                self._engine.update_widget_properties(
                    model.doc_handle, page_index, widget, old_props
                )
                model.dirty = True
                self.dirty_changed.emit(True)

            def redo() -> None:
                self._engine.update_widget_properties(
                    model.doc_handle, page_index, widget, properties
                )
                model.dirty = True
                self.dirty_changed.emit(True)

            undo_mgr.push(
                UndoAction(
                    description=f"Edit Field {old_name}",
                    undo_fn=undo,
                    redo_fn=redo,
                )
            )

    def on_tab_switched(self, session_id: str) -> None:
        """Handle tab switch — reset tool mode and pending field type.

        Args:
            session_id: The new active tab's session ID.
        """
        self._tool_mode = ToolMode.NONE
        self._pending_field_type = None
