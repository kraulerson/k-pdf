"""Floating editor widget for sticky note and text box content.

Provides a QTextEdit with Save/Cancel buttons. Positioned near
the annotation on screen. Emits editing_finished or editing_cancelled.
"""

from __future__ import annotations

import logging
from typing import Any, override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger("k_pdf.views.note_editor")


class NoteEditor(QWidget):
    """Floating frameless widget for editing annotation text content.

    Layout: [QTextEdit] / [Save] [Cancel]
    """

    editing_finished = Signal(str)
    editing_cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the note editor with text area and buttons."""
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedSize(250, 150)

        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("Enter note text...")

        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self._save_btn)
        btn_layout.addWidget(self._cancel_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._text_edit)
        layout.addLayout(btn_layout)

        self._target_page: int = 0
        self._target_annot: Any | None = None
        self._mode: str = "sticky_note"

    def show_for_new(self, mode: str, page_index: int, x: int, y: int) -> None:
        """Position editor for a new annotation.

        Args:
            mode: "sticky_note" or "text_box".
            page_index: Page index for the annotation.
            x: X coordinate in viewport pixels.
            y: Y coordinate in viewport pixels.
        """
        self._mode = mode
        self._target_page = page_index
        self._target_annot = None
        self._text_edit.clear()
        self.move(x, y)
        self.show()
        self._text_edit.setFocus()

    def show_for_existing(
        self,
        mode: str,
        page_index: int,
        annot: Any,
        content: str,
        x: int,
        y: int,
    ) -> None:
        """Position editor for an existing annotation.

        Args:
            mode: "sticky_note" or "text_box".
            page_index: Page index for the annotation.
            annot: Existing annotation reference.
            content: Current text content to pre-fill.
            x: X coordinate in viewport pixels.
            y: Y coordinate in viewport pixels.
        """
        self._mode = mode
        self._target_page = page_index
        self._target_annot = annot
        self._text_edit.setPlainText(content)
        self.move(x, y)
        self.show()
        self._text_edit.setFocus()

    def _on_save(self) -> None:
        """Handle Save click — emit editing_finished or show confirmation for empty."""
        content = self._text_edit.toPlainText()
        if not content:
            result = QMessageBox.question(
                self,
                "Empty Content",
                "Save annotation with empty content?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                return
        self.editing_finished.emit(content)
        self.hide()

    def _on_cancel(self) -> None:
        """Handle Cancel click — emit editing_cancelled and hide."""
        self.editing_cancelled.emit()
        self.hide()

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle Escape key to cancel editing."""
        if event.key() == Qt.Key.Key_Escape:
            self._on_cancel()
            return
        super().keyPressEvent(event)
