"""Text edit presenter — coordinates find-replace, inline edit, undo.

Manages the TextEditEngine, FindReplaceBar interactions, inline edit
overlay, font limitation dialogs, and undo actions.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal

from k_pdf.core.annotation_model import ToolMode
from k_pdf.core.text_edit_model import EditResult, ReplaceAllResult
from k_pdf.core.undo_manager import UndoAction
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.text_edit_engine import TextEditEngine

logger = logging.getLogger("k_pdf.presenters.text_edit_presenter")


class TextEditPresenter(QObject):
    """Coordinates text editing between views and TextEditEngine.

    Signals:
        dirty_changed: Emitted when the document dirty flag transitions.
        text_changed: Emitted after text is modified (for re-render).
        tool_mode_changed: Emitted when the text edit tool mode changes.
        replace_status: Emitted with a status message for the replace bar.
    """

    dirty_changed = Signal(bool)
    text_changed = Signal()
    tool_mode_changed = Signal(int)
    replace_status = Signal(str)

    def __init__(
        self,
        text_edit_engine: TextEditEngine,
        tab_manager: TabManager,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the text edit presenter.

        Args:
            text_edit_engine: The TextEditEngine service.
            tab_manager: The TabManager for accessing active tab state.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._engine = text_edit_engine
        self._tab_manager = tab_manager
        self._tool_mode: ToolMode = ToolMode.NONE

        self._tab_manager.tab_switched.connect(self.on_tab_switched)

    @property
    def tool_mode(self) -> ToolMode:
        """Return the current tool mode."""
        return self._tool_mode

    def set_tool_mode(self, mode: ToolMode) -> None:
        """Set the active text edit tool mode.

        Args:
            mode: TEXT_EDIT or NONE.
        """
        self._tool_mode = mode
        self.tool_mode_changed.emit(int(mode))

    def replace_current(
        self,
        page_index: int,
        search_rect: tuple[float, float, float, float],
        old_text: str,
        new_text: str,
    ) -> bool:
        """Replace text at the current match location.

        Args:
            page_index: Zero-based page index.
            search_rect: Bounding rect of the match.
            old_text: Original text.
            new_text: Replacement text.

        Returns:
            True if replacement succeeded.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return False

        model = doc_presenter.model

        success = self._engine.replace_text(
            model.doc_handle, page_index, search_rect, old_text, new_text
        )

        if success:
            model.dirty = True
            self.dirty_changed.emit(True)
            self.text_changed.emit()

            # Push undo
            undo_mgr = self._tab_manager.get_active_undo_manager()
            if undo_mgr is not None:
                stored_rect = search_rect

                def undo() -> None:
                    self._engine.replace_text(
                        model.doc_handle, page_index, stored_rect, new_text, old_text
                    )
                    model.dirty = True
                    self.dirty_changed.emit(True)
                    self.text_changed.emit()

                def redo() -> None:
                    self._engine.replace_text(
                        model.doc_handle, page_index, stored_rect, old_text, new_text
                    )
                    model.dirty = True
                    self.dirty_changed.emit(True)
                    self.text_changed.emit()

                desc = f"Replace '{old_text[:20]}' with '{new_text[:20]}'"
                undo_mgr.push(
                    UndoAction(
                        description=desc,
                        undo_fn=undo,
                        redo_fn=redo,
                    )
                )

        return success

    def replace_all(
        self,
        search_results: dict[int, list[tuple[float, float, float, float]]],
        old_text: str,
        new_text: str,
    ) -> ReplaceAllResult | None:
        """Replace all matched text across the document.

        Args:
            search_results: Dict mapping page_index to list of match rects.
            old_text: Search text being replaced.
            new_text: Replacement text.

        Returns:
            ReplaceAllResult with counts and skipped locations, or None.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return None

        model = doc_presenter.model

        result = self._engine.replace_all(model.doc_handle, search_results, old_text, new_text)

        if result.replaced_count > 0:
            model.dirty = True
            self.dirty_changed.emit(True)
            self.text_changed.emit()

            # Push compound undo
            undo_mgr = self._tab_manager.get_active_undo_manager()
            if undo_mgr is not None:
                desc = (
                    f"Replace All '{old_text[:20]}' with '{new_text[:20]}' "
                    f"({result.replaced_count} replacements)"
                )
                undo_mgr.push(
                    UndoAction(
                        description=desc,
                        undo_fn=lambda: None,  # Compound undo not feasible for redactions
                        redo_fn=lambda: None,
                    )
                )

            # Emit status
            if result.skipped_count > 0:
                msg = (
                    f"Replaced {result.replaced_count} of "
                    f"{result.replaced_count + result.skipped_count}. "
                    f"{result.skipped_count} skipped (subset font)."
                )
            else:
                msg = f"Replaced {result.replaced_count} matches."
            self.replace_status.emit(msg)

        return result

    def edit_inline(
        self,
        page_index: int,
        block_rect: tuple[float, float, float, float],
        old_text: str,
        new_text: str,
    ) -> EditResult:
        """Attempt inline text edit at the given block.

        Args:
            page_index: Zero-based page index.
            block_rect: Bounding rect of the text block.
            old_text: Original text content.
            new_text: New text content.

        Returns:
            EditResult indicating success or failure.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return EditResult(success=False, error_message="No active document.")

        model = doc_presenter.model

        result = self._engine.edit_text_inline(
            model.doc_handle, page_index, block_rect, old_text, new_text
        )

        if result.success:
            model.dirty = True
            self.dirty_changed.emit(True)
            self.text_changed.emit()

            undo_mgr = self._tab_manager.get_active_undo_manager()
            if undo_mgr is not None:

                def undo() -> None:
                    self._engine.replace_text(
                        model.doc_handle, page_index, block_rect, new_text, old_text
                    )
                    model.dirty = True
                    self.dirty_changed.emit(True)
                    self.text_changed.emit()

                def redo() -> None:
                    self._engine.replace_text(
                        model.doc_handle, page_index, block_rect, old_text, new_text
                    )
                    model.dirty = True
                    self.dirty_changed.emit(True)
                    self.text_changed.emit()

                undo_mgr.push(
                    UndoAction(
                        description=f"Edit text on page {page_index + 1}",
                        undo_fn=undo,
                        redo_fn=redo,
                    )
                )

        return result

    def redact_and_overlay(
        self,
        page_index: int,
        block_rect: tuple[float, float, float, float],
        new_text: str,
        font_size: float,
    ) -> None:
        """Apply redact-and-overlay fallback for subset fonts.

        Args:
            page_index: Zero-based page index.
            block_rect: Area to redact and overlay.
            new_text: Text to insert after redaction.
            font_size: Font size for the overlay.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return

        model = doc_presenter.model

        self._engine.redact_and_overlay(
            model.doc_handle, page_index, block_rect, new_text, font_size
        )

        model.dirty = True
        self.dirty_changed.emit(True)
        self.text_changed.emit()

        undo_mgr = self._tab_manager.get_active_undo_manager()
        if undo_mgr is not None:
            undo_mgr.push(
                UndoAction(
                    description=f"Redact and replace text on page {page_index + 1}",
                    undo_fn=lambda: None,  # Redaction is permanent in PyMuPDF
                    redo_fn=lambda: None,
                )
            )

    def get_text_block_at(
        self,
        page_index: int,
        x: float,
        y: float,
    ) -> Any:
        """Get text block info at the given PDF coordinates.

        Args:
            page_index: Zero-based page index.
            x: X coordinate in PDF page space.
            y: Y coordinate in PDF page space.

        Returns:
            TextBlockInfo or None.
        """
        doc_presenter = self._tab_manager.get_active_presenter()
        if doc_presenter is None or doc_presenter.model is None:
            return None

        return self._engine.get_text_block(doc_presenter.model.doc_handle, page_index, x, y)

    def on_tab_switched(self, session_id: str) -> None:
        """Reset tool mode on tab switch.

        Args:
            session_id: New active tab session ID.
        """
        self._tool_mode = ToolMode.NONE
