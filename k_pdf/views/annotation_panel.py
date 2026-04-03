"""Annotation summary panel.

QDockWidget docked right, containing a QTableWidget listing all
annotations across the active document. F6 toggle visibility.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QDockWidget,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from k_pdf.core.annotation_model import AnnotationInfo

logger = logging.getLogger("k_pdf.views.annotation_panel")

# RGB-tuple-to-name mapping derived from annotation_toolbar._COLORS
_RGB_TO_NAME: dict[tuple[float, float, float], str] = {
    (1.0, 1.0, 0.0): "Yellow",
    (1.0, 0.0, 0.0): "Red",
    (0.0, 0.8, 0.0): "Green",
    (0.0, 0.0, 1.0): "Blue",
    (1.0, 0.65, 0.0): "Orange",
    (0.5, 0.0, 0.5): "Purple",
}


def _color_name(rgb: tuple[float, float, float]) -> str:
    """Return a human-readable name for an RGB color tuple.

    Looks up exact matches first, then falls back to an ``(R, G, B)``
    representation so the cell is never blank.
    """
    name = _RGB_TO_NAME.get(rgb)
    if name is not None:
        return name
    # Fallback: display integer RGB values
    r = int(rgb[0] * 255)
    g = int(rgb[1] * 255)
    b = int(rgb[2] * 255)
    return f"({r}, {g}, {b})"


# Type label -> icon character for accessibility (icon + text, never icon-only)
_TYPE_ICONS: dict[str, str] = {
    "Highlight": "\U0001f58d",  # marker
    "Underline": "U\u0332",  # underlined U
    "Strikethrough": "S\u0336",  # strikethrough S
    "Note": "\U0001f4dd",  # note
    "Text Box": "\u2610",  # box
}

_PREVIEW_MAX_LEN = 40


def _make_color_swatch(color: tuple[float, float, float], size: int = 16) -> QPixmap:
    """Create a small colored swatch pixmap.

    Args:
        color: RGB as 0.0-1.0 floats.
        size: Swatch size in pixels.

    Returns:
        A QPixmap filled with the given color.
    """
    pixmap = QPixmap(size, size)
    r = int(color[0] * 255)
    g = int(color[1] * 255)
    b = int(color[2] * 255)
    pixmap.fill(QColor(r, g, b))
    return pixmap


class _NumericTableItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically by its text content."""

    def __lt__(self, other: QTableWidgetItem) -> bool:  # type: ignore[override]
        """Compare items numerically for sorting."""
        try:
            return int(self.text()) < int(other.text())
        except (ValueError, TypeError):
            return self.text() < other.text()


class AnnotationSummaryPanel(QDockWidget):
    """Right-docked annotation summary panel with annotation table.

    Lists all annotations in the active document with page number,
    type (icon + text), author, preview, and color swatch.
    """

    annotation_clicked = Signal(int)  # page_index (zero-based)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the annotation summary panel."""
        super().__init__("Annotations", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.setMinimumWidth(200)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Empty state label
        self._empty_label = QLabel("No annotations in this document")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Page", "Type", "Author", "Preview", "Color"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)

        # Column sizing
        header = self._table.horizontalHeader()
        header.resizeSection(0, 50)
        header.resizeSection(1, 120)
        header.resizeSection(2, 100)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.resizeSection(4, 90)

        self._table.clicked.connect(self._on_row_clicked)
        layout.addWidget(self._table)

        self._table.hide()
        self._empty_label.show()

        self.setWidget(container)

        # Store annotations for lookup
        self._annotations: list[AnnotationInfo] = []

    def set_annotations(self, annotations: list[AnnotationInfo]) -> None:
        """Populate the table from annotation data.

        Sorts by page number by default.

        Args:
            annotations: List of AnnotationInfo objects.
        """
        # Sort by page number
        sorted_annotations = sorted(annotations, key=lambda a: a.page)
        self._annotations = sorted_annotations

        # Temporarily disable sorting to avoid interference during population
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(sorted_annotations))

        for row, info in enumerate(sorted_annotations):
            # Page (1-based) — use numeric sort key via __lt__
            page_item = _NumericTableItem(str(info.page + 1))
            page_item.setData(Qt.ItemDataRole.UserRole, info.page)
            self._table.setItem(row, 0, page_item)

            # Type (icon + text label)
            icon = _TYPE_ICONS.get(info.ann_type, "?")
            type_item = QTableWidgetItem(info.ann_type)
            type_item.setToolTip(f"{icon} {info.ann_type}")
            self._table.setItem(row, 1, type_item)

            # Author
            author_item = QTableWidgetItem(info.author)
            self._table.setItem(row, 2, author_item)

            # Preview (truncated content)
            preview = info.content
            if len(preview) > _PREVIEW_MAX_LEN:
                preview = preview[:_PREVIEW_MAX_LEN] + "..."
            preview_item = QTableWidgetItem(preview)
            if info.content:
                preview_item.setToolTip(info.content)
            self._table.setItem(row, 3, preview_item)

            # Color swatch + text name for accessibility
            color_name = _color_name(info.color)
            color_item = QTableWidgetItem()
            color_item.setText(color_name)
            swatch = _make_color_swatch(info.color)
            color_item.setData(Qt.ItemDataRole.DecorationRole, swatch)
            self._table.setItem(row, 4, color_item)

        self._table.setSortingEnabled(True)
        self._table.sortItems(0, Qt.SortOrder.AscendingOrder)

        if sorted_annotations:
            self._table.show()
            self._empty_label.hide()
        else:
            self._table.hide()
            self._empty_label.show()

    def clear(self) -> None:
        """Clear the table and show empty state."""
        self._table.setRowCount(0)
        self._annotations = []
        self._table.hide()
        self._empty_label.show()

    def _on_row_clicked(self, index: QModelIndex) -> None:
        """Handle row click — emit annotation_clicked with page index."""
        row = index.row()
        page_item = self._table.item(row, 0)
        if page_item is not None:
            page_index = page_item.data(Qt.ItemDataRole.UserRole)
            if page_index is not None:
                self.annotation_clicked.emit(int(page_index))
