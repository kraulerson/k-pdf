"""PDF rendering viewport using QGraphicsView.

Displays rendered PDF pages vertically in a scrollable scene.
Manages viewport states: Empty, Loading, Error, Success.
Requests rendering for visible pages plus a 1-page buffer.
"""

from __future__ import annotations

import logging
from enum import Enum, auto

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QWidget,
)

from k_pdf.core.document_model import PageInfo

logger = logging.getLogger("k_pdf.views.pdf_viewport")

_PAGE_GAP = 20  # pixels between pages


class ViewportState(Enum):
    """States for the PDF viewport."""

    EMPTY = auto()
    LOADING = auto()
    ERROR = auto()
    SUCCESS = auto()


class PdfViewport(QGraphicsView):
    """QGraphicsView that displays rendered PDF pages.

    Pages are laid out vertically with gaps between them.
    Emits visible_pages_changed when the user scrolls so the
    presenter can request rendering for uncached pages.
    """

    visible_pages_changed = Signal(list)  # list[int] of visible page indices
    current_page_changed = Signal(int)  # topmost visible page index

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the PDF viewport with an empty scene."""
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self._state = ViewportState.EMPTY
        self._pages: list[PageInfo] = []
        self._page_items: dict[int, QGraphicsPixmapItem | QGraphicsRectItem] = {}
        self._page_y_offsets: list[float] = []
        self._current_page: int = -1

        # Connect scroll changes to lazy render requests
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    @property
    def state(self) -> ViewportState:
        """Return the current viewport state."""
        return self._state

    def set_loading(self, filename: str) -> None:
        """Switch to loading state."""
        self._state = ViewportState.LOADING
        self._scene.clear()
        self._page_items.clear()
        text = self._scene.addSimpleText(f"Loading {filename}...")
        text.setPos(50, 50)

    def set_error(self, message: str) -> None:
        """Switch to error state."""
        self._state = ViewportState.ERROR
        self._scene.clear()
        self._page_items.clear()
        text = self._scene.addSimpleText(message)
        text.setPos(50, 50)

    def set_document(self, pages: list[PageInfo], zoom: float = 1.0) -> None:
        """Set up the viewport for a new document.

        Creates placeholder rectangles for all pages and calculates
        vertical layout. Does not render pages — rendering is triggered
        by scroll position via visible_pages_changed signal.

        Args:
            pages: List of PageInfo for each page in the document.
            zoom: Current zoom factor.
        """
        self._state = ViewportState.SUCCESS
        self._scene.clear()
        self._page_items.clear()
        self._pages = pages
        self._page_y_offsets = []

        y_offset = 0.0
        for page_info in pages:
            w = page_info.width * zoom
            h = page_info.height * zoom

            # Create a placeholder rectangle
            rect_item = self._scene.addRect(
                QRectF(0, 0, w, h),
                brush=QBrush(QColor(240, 240, 240)),
            )
            rect_item.setPos(0, y_offset)
            self._page_items[page_info.index] = rect_item

            # Page number label centered in placeholder
            label = QGraphicsSimpleTextItem(f"Page {page_info.index + 1}")
            label.setFont(QFont("", 12))
            label_rect = label.boundingRect()
            label.setPos(
                (w - label_rect.width()) / 2,
                y_offset + (h - label_rect.height()) / 2,
            )
            self._scene.addItem(label)

            self._page_y_offsets.append(y_offset)
            y_offset += h + _PAGE_GAP

        self._scene.setSceneRect(QRectF(0, 0, self._max_page_width(zoom), y_offset))
        self.centerOn(0, 0)

        # Trigger initial render request
        self._emit_visible_pages()

    def set_page_pixmap(self, page_index: int, pixmap: QPixmap) -> None:
        """Replace a page placeholder with a rendered pixmap.

        Args:
            page_index: The page to update.
            pixmap: The rendered page image.
        """
        if page_index not in self._page_items:
            return

        old_item = self._page_items[page_index]
        y_pos = old_item.pos().y()
        self._scene.removeItem(old_item)

        pixmap_item = QGraphicsPixmapItem(pixmap)
        pixmap_item.setPos(0, y_pos)
        self._scene.addItem(pixmap_item)
        self._page_items[page_index] = pixmap_item

    def set_page_error(self, page_index: int) -> None:
        """Show an error placeholder for a page that failed to render.

        Args:
            page_index: The page that failed.
        """
        if page_index >= len(self._pages):
            return

        page_info = self._pages[page_index]
        if page_index in self._page_items:
            old_item = self._page_items[page_index]
            y_pos = old_item.pos().y()
            self._scene.removeItem(old_item)
        else:
            y_pos = (
                self._page_y_offsets[page_index] if page_index < len(self._page_y_offsets) else 0
            )

        rect_item = self._scene.addRect(
            QRectF(0, 0, page_info.width, page_info.height),
            brush=QBrush(QColor(200, 200, 200)),
        )
        rect_item.setPos(0, y_pos)
        self._page_items[page_index] = rect_item

        label = QGraphicsSimpleTextItem(f"Render error on page {page_index + 1}")
        label.setFont(QFont("", 11))
        label_rect = label.boundingRect()
        label.setPos(
            (page_info.width - label_rect.width()) / 2,
            y_pos + (page_info.height - label_rect.height()) / 2,
        )
        self._scene.addItem(label)

    def scroll_to_page(self, page_index: int) -> None:
        """Scroll the viewport to show the specified page at the top.

        Args:
            page_index: 0-based page index to scroll to.
        """
        if page_index < 0 or page_index >= len(self._page_y_offsets):
            return
        y = self._page_y_offsets[page_index]
        self.verticalScrollBar().setValue(int(y))

    def get_visible_page_range(self) -> tuple[int, int]:
        """Calculate which pages are currently visible plus 1-page buffer.

        Returns:
            Tuple of (first_visible_index, last_visible_index) inclusive.
            Returns (-1, -1) if no pages.
        """
        if not self._pages or not self._page_y_offsets:
            return (-1, -1)

        viewport_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        top = viewport_rect.top()
        bottom = viewport_rect.bottom()

        first_visible = -1
        last_visible = -1

        for i, y_off in enumerate(self._page_y_offsets):
            page_bottom = y_off + self._pages[i].height
            if page_bottom >= top and y_off <= bottom:
                if first_visible == -1:
                    first_visible = i
                last_visible = i

        if first_visible == -1:
            return (-1, -1)

        # Add 1-page buffer
        first_visible = max(0, first_visible - 1)
        last_visible = min(len(self._pages) - 1, last_visible + 1)
        return (first_visible, last_visible)

    def _on_scroll(self) -> None:
        """Handle scroll events — emit visible page range for lazy rendering."""
        self._emit_visible_pages()

    def _emit_visible_pages(self) -> None:
        """Calculate and emit the list of visible page indices."""
        first, last = self.get_visible_page_range()
        if first >= 0:
            self.visible_pages_changed.emit(list(range(first, last + 1)))
            if first != self._current_page:
                self._current_page = first
                self.current_page_changed.emit(first)

    def _max_page_width(self, zoom: float) -> float:
        """Return the maximum page width at the given zoom."""
        if not self._pages:
            return 0.0
        return max(p.width * zoom for p in self._pages)
