"""Floating annotation toolbar for text markup creation.

Appears near text selections. Offers Highlight, Underline, Strikethrough
buttons plus a color picker dropdown. Frameless widget that auto-dismisses.
"""

from __future__ import annotations

import logging
from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QHideEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

from k_pdf.core.annotation_model import AnnotationType

logger = logging.getLogger("k_pdf.views.annotation_toolbar")

# Named colors with text labels for accessibility
_COLORS: list[tuple[str, tuple[float, float, float]]] = [
    ("Yellow", (1.0, 1.0, 0.0)),
    ("Red", (1.0, 0.0, 0.0)),
    ("Green", (0.0, 0.8, 0.0)),
    ("Blue", (0.0, 0.0, 1.0)),
    ("Orange", (1.0, 0.65, 0.0)),
    ("Purple", (0.5, 0.0, 0.5)),
]


class AnnotationToolbar(QWidget):
    """Floating frameless toolbar for text markup annotation creation.

    Layout: [Highlight] [Underline] [Strikethrough] | [Color picker]

    Emits annotation_requested when user clicks a type button.
    Emits dismissed when toolbar is hidden or loses focus.
    """

    annotation_requested = Signal(object, object)  # (AnnotationType, color tuple)
    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the toolbar with annotation buttons and color picker."""
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Annotation type buttons -- icon + text for accessibility
        self._highlight_btn = QPushButton("Highlight")
        self._highlight_btn.setToolTip("Add highlight annotation")
        self._highlight_btn.clicked.connect(lambda: self._emit_annotation(AnnotationType.HIGHLIGHT))
        layout.addWidget(self._highlight_btn)

        self._underline_btn = QPushButton("Underline")
        self._underline_btn.setToolTip("Add underline annotation")
        self._underline_btn.clicked.connect(lambda: self._emit_annotation(AnnotationType.UNDERLINE))
        layout.addWidget(self._underline_btn)

        self._strikethrough_btn = QPushButton("Strikethrough")
        self._strikethrough_btn.setToolTip("Add strikethrough annotation")
        self._strikethrough_btn.clicked.connect(
            lambda: self._emit_annotation(AnnotationType.STRIKETHROUGH)
        )
        layout.addWidget(self._strikethrough_btn)

        # Color picker dropdown with named colors
        self._color_combo = QComboBox()
        for name, _rgb in _COLORS:
            self._color_combo.addItem(name)
        self._color_combo.setCurrentIndex(0)  # Yellow default
        self._color_combo.setToolTip("Annotation color")
        layout.addWidget(self._color_combo)

    @property
    def current_color(self) -> tuple[float, float, float]:
        """Return the currently selected color as RGB floats."""
        idx = self._color_combo.currentIndex()
        if 0 <= idx < len(_COLORS):
            color: tuple[float, float, float] = _COLORS[idx][1]
            return color
        default: tuple[float, float, float] = _COLORS[0][1]
        return default

    def set_color(self, color: tuple[float, float, float]) -> None:
        """Set the active color in the picker.

        Args:
            color: RGB color as 0.0-1.0 floats.
        """
        for i, (_name, rgb) in enumerate(_COLORS):
            if rgb == color:
                self._color_combo.setCurrentIndex(i)
                return
        # If color not in presets, default to first
        logger.debug("Color %s not in presets, keeping current selection", color)

    def show_near(self, x: int, y: int) -> None:
        """Position the toolbar near the given coordinates, clamped to screen.

        Args:
            x: X coordinate in screen pixels.
            y: Y coordinate in screen pixels.
        """
        self.adjustSize()
        screen = self.screen()
        if screen is not None:
            screen_rect = screen.availableGeometry()
            # Clamp to screen bounds
            clamped_x = max(screen_rect.left(), min(x, screen_rect.right() - self.width()))
            clamped_y = max(screen_rect.top(), min(y, screen_rect.bottom() - self.height()))
            self.move(clamped_x, clamped_y)
        else:
            self.move(x, y)
        self.show()

    @override
    def hideEvent(self, event: QHideEvent) -> None:
        """Emit dismissed when toolbar is hidden."""
        super().hideEvent(event)
        self.dismissed.emit()

    def _emit_annotation(self, ann_type: AnnotationType) -> None:
        """Emit annotation_requested with the given type and current color."""
        self.annotation_requested.emit(ann_type, self.current_color)
