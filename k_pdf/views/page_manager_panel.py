"""Page management panel.

QDockWidget containing a thumbnail grid with multi-select support
and toolbar with page manipulation actions. F7 toggle visibility.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger("k_pdf.views.page_manager_panel")


class PageManagerPanel(QDockWidget):
    """Left-docked page management panel with thumbnail grid and toolbar.

    Provides multi-select thumbnails and actions for rotating, deleting,
    adding, and reordering pages. Page rotation here modifies the PDF
    (unlike Feature 5 view-only rotation).
    """

    rotate_left_clicked = Signal()
    rotate_right_clicked = Signal()
    delete_clicked = Signal()
    add_clicked = Signal()
    page_moved = Signal(int, int)  # (from_index, to_index)
    selection_changed = Signal(list)  # list of selected indices
    page_clicked = Signal(int)  # page index — emitted on single-click for navigation

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the page manager panel."""
        super().__init__("Page Manager", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setMinimumWidth(180)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Page count label
        self._page_count_label = QLabel("No document open")
        self._page_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._page_count_label)

        # Toolbar
        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)

        self._rotate_left_action = QAction("Rotate Left (modifies file)", self)
        self._rotate_left_action.setToolTip(
            "Rotate selected pages 90 degrees counter-clockwise (modifies PDF)"
        )
        self._rotate_left_action.triggered.connect(self.rotate_left_clicked.emit)
        self._toolbar.addAction(self._rotate_left_action)

        self._rotate_right_action = QAction("Rotate Right (modifies file)", self)
        self._rotate_right_action.setToolTip(
            "Rotate selected pages 90 degrees clockwise (modifies PDF)"
        )
        self._rotate_right_action.triggered.connect(self.rotate_right_clicked.emit)
        self._toolbar.addAction(self._rotate_right_action)

        self._delete_action = QAction("Delete Pages", self)
        self._delete_action.setToolTip("Delete selected pages from the document")
        self._delete_action.triggered.connect(self.delete_clicked.emit)
        self._toolbar.addAction(self._delete_action)

        self._add_action = QAction("Add Pages", self)
        self._add_action.setToolTip("Insert pages from another PDF")
        self._add_action.triggered.connect(self.add_clicked.emit)
        self._toolbar.addAction(self._add_action)

        layout.addWidget(self._toolbar)

        # Thumbnail grid
        self._thumbnail_list = QListWidget()
        self._thumbnail_list.setViewMode(QListWidget.ViewMode.IconMode)
        self._thumbnail_list.setFlow(QListWidget.Flow.TopToBottom)
        self._thumbnail_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._thumbnail_list.setWrapping(False)
        self._thumbnail_list.setSpacing(4)
        self._thumbnail_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._thumbnail_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._thumbnail_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._thumbnail_list.itemSelectionChanged.connect(self._on_selection_changed)
        self._thumbnail_list.itemClicked.connect(self._on_item_clicked)
        self._thumbnail_list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self._thumbnail_list)

        # Progress bar (hidden by default)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        self.setWidget(container)

    def set_thumbnails(self, pixmaps: list[QPixmap]) -> None:
        """Populate the thumbnail grid with page thumbnails.

        Args:
            pixmaps: List of QPixmap thumbnails, one per page.
        """
        self._thumbnail_list.clear()
        for i, pixmap in enumerate(pixmaps):
            item = QListWidgetItem(QIcon(pixmap), f"Page {i + 1}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._thumbnail_list.addItem(item)

    def update_thumbnail(self, page_index: int, pixmap: QPixmap) -> None:
        """Replace a single thumbnail after rotation or other change.

        Args:
            page_index: Zero-based page index.
            pixmap: New thumbnail pixmap.
        """
        if 0 <= page_index < self._thumbnail_list.count():
            item = self._thumbnail_list.item(page_index)
            if item is not None:
                item.setIcon(QIcon(pixmap))

    def get_selected_pages(self) -> list[int]:
        """Return zero-based indices of selected thumbnails.

        Returns:
            Sorted list of selected page indices.
        """
        indices: list[int] = []
        for item in self._thumbnail_list.selectedItems():
            data = item.data(Qt.ItemDataRole.UserRole)
            if data is not None:
                indices.append(int(data))
        return sorted(indices)

    def show_progress(self, message: str) -> None:
        """Show the progress bar with the given message.

        Args:
            message: Description of the current operation.
        """
        self._progress_bar.setFormat(message)
        self._progress_bar.show()

    def hide_progress(self) -> None:
        """Hide the progress bar."""
        self._progress_bar.hide()

    def set_page_count_label(self, count: int) -> None:
        """Update the panel header with total page count.

        Args:
            count: Total number of pages.
        """
        self._page_count_label.setText(f"{count} page{'s' if count != 1 else ''}")

    def set_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable all toolbar buttons.

        Args:
            enabled: True to enable, False to disable.
        """
        self._rotate_left_action.setEnabled(enabled)
        self._rotate_right_action.setEnabled(enabled)
        self._delete_action.setEnabled(enabled)
        self._add_action.setEnabled(enabled)

    def _on_selection_changed(self) -> None:
        """Emit selection_changed with current selected indices."""
        self.selection_changed.emit(self.get_selected_pages())

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle single thumbnail click — emit page_clicked for navigation."""
        page_index = item.data(Qt.ItemDataRole.UserRole)
        if page_index is not None:
            self.page_clicked.emit(int(page_index))

    def _on_rows_moved(self) -> None:
        """Handle internal drag-drop reorder.

        After Qt moves the row, we read the new order and emit page_moved.
        """
        for i in range(self._thumbnail_list.count()):
            item = self._thumbnail_list.item(i)
            if item is not None:
                old_index = item.data(Qt.ItemDataRole.UserRole)
                if old_index is not None and int(old_index) != i:
                    self.page_moved.emit(int(old_index), i)
                    # Update stored index
                    item.setData(Qt.ItemDataRole.UserRole, i)
