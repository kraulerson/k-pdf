"""Navigation panel — thumbnails and outline/bookmarks.

QDockWidget containing a QTabWidget with Thumbnails and Outline tabs.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from k_pdf.core.outline_model import OutlineNode

logger = logging.getLogger("k_pdf.views.navigation_panel")


class NavigationPanel(QDockWidget):
    """Left-side navigation panel with thumbnails and outline."""

    thumbnail_clicked = Signal(int)  # page index
    outline_clicked = Signal(int)  # page index

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the navigation panel."""
        super().__init__("Navigation", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setMinimumWidth(120)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget)

        # Thumbnails tab
        self._thumbnail_list = QListWidget()
        self._thumbnail_list.setViewMode(QListWidget.ViewMode.IconMode)
        self._thumbnail_list.setFlow(QListWidget.Flow.TopToBottom)
        self._thumbnail_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._thumbnail_list.setWrapping(False)
        self._thumbnail_list.setSpacing(4)
        self._thumbnail_list.currentRowChanged.connect(self._on_thumbnail_selected)
        self._tab_widget.addTab(self._thumbnail_list, "Thumbnails")

        # Outline tab with stacked widget for empty state
        self._outline_tree = QTreeWidget()
        self._outline_tree.setHeaderHidden(True)
        self._outline_tree.currentItemChanged.connect(self._on_outline_selected)

        self._no_outline_label = QLabel("No bookmarks in this document.")
        self._no_outline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_outline_label.setWordWrap(True)

        self._outline_stack = QStackedWidget()
        self._outline_stack.addWidget(self._outline_tree)  # index 0
        self._outline_stack.addWidget(self._no_outline_label)  # index 1
        self._tab_widget.addTab(self._outline_stack, "Outline")

        self.setWidget(container)

        # Suppress thumbnail_clicked during programmatic updates
        self._updating = False

    @property
    def tab_widget(self) -> QTabWidget:
        """Return the internal tab widget."""
        return self._tab_widget

    def add_thumbnail(self, page_index: int, pixmap: QPixmap) -> None:
        """Add a single thumbnail to the list.

        Args:
            page_index: 0-based page index.
            pixmap: The rendered thumbnail pixmap.
        """
        item = QListWidgetItem(QIcon(pixmap), f"Page {page_index + 1}")
        item.setData(Qt.ItemDataRole.UserRole, page_index)
        self._thumbnail_list.addItem(item)

    def set_outline(self, nodes: list[OutlineNode]) -> None:
        """Populate the outline tree.

        Args:
            nodes: Top-level outline nodes. Empty list shows "no bookmarks" label.
        """
        logger.debug("set_outline called with %d nodes", len(nodes))
        self._outline_tree.clear()
        if not nodes:
            self._outline_stack.setCurrentIndex(1)
            return

        self._outline_stack.setCurrentIndex(0)
        for node in nodes:
            self._add_outline_node(node, self._outline_tree)
        self._outline_tree.expandAll()

    def set_current_page(self, page_index: int) -> None:
        """Highlight the thumbnail for the current page.

        Args:
            page_index: 0-based page index.
        """
        self._updating = True
        if 0 <= page_index < self._thumbnail_list.count():
            self._thumbnail_list.setCurrentRow(page_index)
            self._thumbnail_list.scrollToItem(
                self._thumbnail_list.item(page_index),
            )
        self._updating = False

    def clear(self) -> None:
        """Reset both tabs to empty state."""
        self._thumbnail_list.clear()
        self._outline_tree.clear()
        self._outline_stack.setCurrentIndex(1)

    def _add_outline_node(
        self,
        node: OutlineNode,
        parent: QTreeWidget | QTreeWidgetItem,
    ) -> None:
        """Recursively add an outline node to the tree."""
        if node.page == -1:
            item = QTreeWidgetItem([f"\u26a0 {node.title} \u2014 Invalid target"])
        else:
            item = QTreeWidgetItem([node.title])
        item.setData(0, Qt.ItemDataRole.UserRole, node.page)

        if isinstance(parent, QTreeWidget):
            parent.addTopLevelItem(item)
        else:
            parent.addChild(item)

        for child in node.children:
            self._add_outline_node(child, item)

    def _on_thumbnail_selected(self, row: int) -> None:
        """Handle thumbnail list selection change."""
        if self._updating or row < 0:
            return
        item = self._thumbnail_list.item(row)
        if item is not None:
            page_index = item.data(Qt.ItemDataRole.UserRole)
            if page_index is not None:
                self.thumbnail_clicked.emit(page_index)

    def _on_outline_selected(
        self,
        current: QTreeWidgetItem | None,
        _previous: QTreeWidgetItem | None,
    ) -> None:
        """Handle outline tree selection change."""
        if current is None:
            return
        page_index = current.data(0, Qt.ItemDataRole.UserRole)
        if page_index is not None and page_index >= 0:
            self.outline_clicked.emit(page_index)
