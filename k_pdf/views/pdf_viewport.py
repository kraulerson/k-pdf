"""PDF rendering viewport using QGraphicsView.

Displays rendered PDF pages vertically in a scrollable scene.
Manages viewport states: Empty, Loading, Error, Success.
Requests rendering for visible pages plus a 1-page buffer.
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import override

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QMouseEvent,
    QPen,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsProxyWidget,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QMenu,
    QWidget,
)

from k_pdf.core.annotation_model import ToolMode
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
    viewport_resized = Signal(float, float)  # (width, height)
    zoom_at_cursor = Signal(float, QPointF)  # (step_direction, scene_pos)
    text_selected = Signal(int, list)  # (page_index, word_rects)
    annotation_delete_requested = Signal(int, object)  # (page_index, annot)
    note_placed = Signal(int, tuple)  # (page_index, (x, y))
    textbox_drawn = Signal(int, tuple)  # (page_index, (x0, y0, x1, y1))
    annotation_double_clicked = Signal(int, object)  # (page_index, annot)
    form_field_placed = Signal(int, tuple, int)  # (page_index, (x, y), tool_mode_int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the PDF viewport with an empty scene."""
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        # Disable drop acceptance on both the QGraphicsView and its
        # internal viewport widget so file drag-drop events propagate
        # up to MainWindow instead of being swallowed by QGraphicsView.
        self.setAcceptDrops(False)
        self.viewport().setAcceptDrops(False)

        self._state = ViewportState.EMPTY
        self._pages: list[PageInfo] = []
        self._page_items: dict[int, QGraphicsPixmapItem | QGraphicsRectItem] = {}
        self._page_y_offsets: list[float] = []
        self._current_page: int = -1
        self._search_highlights: list[QGraphicsRectItem] = []
        self._current_highlight: QGraphicsRectItem | None = None
        self._tool_mode: ToolMode = ToolMode.NONE
        self._selection_mode: bool = False
        self._selection_overlays: list[QGraphicsRectItem] = []
        self._drag_start: QPointF | None = None
        self._textbox_drag_start: QPointF | None = None
        self._textbox_preview: QGraphicsRectItem | None = None
        self._annotation_engine: object | None = None
        self._doc_handle: object | None = None
        self._form_overlays: list[QGraphicsProxyWidget] = []
        self._invert_pdf: bool = False

        # Connect scroll changes to lazy render requests
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    @property
    def state(self) -> ViewportState:
        """Return the current viewport state."""
        return self._state

    @property
    def invert_pdf(self) -> bool:
        """Return whether PDF inversion is active."""
        return self._invert_pdf

    def set_invert_pdf(self, invert: bool) -> None:
        """Enable or disable PDF color inversion.

        When enabled, incoming pixmaps in set_page_pixmap() will have
        their RGB channels inverted before display. This is view-only
        and does not modify the PDF file.

        Args:
            invert: True to enable inversion, False to disable.
        """
        self._invert_pdf = invert

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

    def set_document(self, pages: list[PageInfo], zoom: float = 1.0, rotation: int = 0) -> None:
        """Set up the viewport for a new document.

        Creates placeholder rectangles for all pages and calculates
        vertical layout. Does not render pages — rendering is triggered
        by scroll position via visible_pages_changed signal.

        Args:
            pages: List of PageInfo for each page in the document.
            zoom: Current zoom factor.
            rotation: Current rotation in degrees (0, 90, 180, 270).
        """
        self._state = ViewportState.SUCCESS
        self._scene.clear()
        self._page_items.clear()
        self._pages = pages
        self._page_y_offsets = []

        y_offset = 0.0
        for page_info in pages:
            if rotation in (90, 270):
                w = page_info.height * zoom
                h = page_info.width * zoom
            else:
                w = page_info.width * zoom
                h = page_info.height * zoom

            # Create a placeholder rectangle using palette color
            rect_item = self._scene.addRect(
                QRectF(0, 0, w, h),
                brush=QBrush(self.palette().window().color()),
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

        If PDF inversion is active, the pixmap's RGB channels are
        inverted before display (alpha is preserved).

        Args:
            page_index: The page to update.
            pixmap: The rendered page image.
        """
        if page_index not in self._page_items:
            return

        if self._invert_pdf:
            pixmap = self._invert_pixmap(pixmap)

        old_item = self._page_items[page_index]
        y_pos = old_item.pos().y()
        self._scene.removeItem(old_item)

        pixmap_item = QGraphicsPixmapItem(pixmap)
        pixmap_item.setPos(0, y_pos)
        self._scene.addItem(pixmap_item)
        self._page_items[page_index] = pixmap_item

    @staticmethod
    def _invert_pixmap(pixmap: QPixmap) -> QPixmap:
        """Invert the RGB channels of a QPixmap, preserving alpha.

        Args:
            pixmap: The source pixmap.

        Returns:
            A new QPixmap with inverted RGB channels.
        """
        image = pixmap.toImage()
        image.invertPixels(QImage.InvertMode.InvertRgb)
        return QPixmap.fromImage(image)

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
            brush=QBrush(self.palette().mid().color()),
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

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Emit viewport_resized on resize for fit mode recalculation."""
        super().resizeEvent(event)
        vp = self.viewport()
        self.viewport_resized.emit(float(vp.width()), float(vp.height()))

    @override
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle Ctrl+scroll for zoom, delegate normal scroll to parent."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            event.accept()
            angle = event.angleDelta().y()
            if angle == 0:
                return
            # +0.1 per notch (120 units = 1 notch)
            step = 0.1 * (angle / 120.0)
            scene_pos = self.mapToScene(event.position().toPoint())
            self.zoom_at_cursor.emit(step, scene_pos)
        else:
            super().wheelEvent(event)

    def add_search_highlights(
        self,
        page_index: int,
        rects: list[tuple[float, float, float, float]],
        zoom: float,
    ) -> None:
        """Add semi-transparent highlight overlays for search matches on a page.

        Creates QGraphicsRectItems with visible fill and border at the
        specified rect positions. Highlights are non-destructive overlays
        on the existing scene.

        Args:
            page_index: 0-based page index.
            rects: List of (x0, y0, x1, y1) bounding boxes in page coordinates.
            zoom: Current zoom factor applied to coordinates.
        """
        if page_index < 0 or page_index >= len(self._page_y_offsets):
            return

        y_base = self._page_y_offsets[page_index]
        pen = QPen(QColor(0, 0, 0, 180))
        pen.setWidthF(1.0)
        brush = QBrush(QColor(255, 200, 0, 80))

        for x0, y0, x1, y1 in rects:
            sx0 = x0 * zoom
            sy0 = y0 * zoom
            sw = (x1 - x0) * zoom
            sh = (y1 - y0) * zoom
            rect_item = self._scene.addRect(
                QRectF(0, 0, sw, sh),
                pen=pen,
                brush=brush,
            )
            rect_item.setPos(sx0, y_base + sy0)
            rect_item.setZValue(10)
            self._search_highlights.append(rect_item)

    def set_current_highlight(
        self,
        page_index: int,
        rect: tuple[float, float, float, float],
        zoom: float,
    ) -> None:
        """Mark one match as the current highlight with a thicker border.

        Removes any previous current-highlight overlay and creates
        a new one with a distinct, thicker pen.

        Args:
            page_index: 0-based page index.
            rect: (x0, y0, x1, y1) bounding box in page coordinates.
            zoom: Current zoom factor applied to coordinates.
        """
        # Remove previous current highlight
        if self._current_highlight is not None:
            self._scene.removeItem(self._current_highlight)
            self._current_highlight = None

        if page_index < 0 or page_index >= len(self._page_y_offsets):
            return

        y_base = self._page_y_offsets[page_index]
        x0, y0, x1, y1 = rect
        sx0 = x0 * zoom
        sy0 = y0 * zoom
        sw = (x1 - x0) * zoom
        sh = (y1 - y0) * zoom

        pen = QPen(QColor(0, 0, 0, 255))
        pen.setWidthF(3.0)
        pen.setStyle(Qt.PenStyle.DashLine)
        brush = QBrush(QColor(255, 150, 0, 120))

        current_item = self._scene.addRect(
            QRectF(0, 0, sw, sh),
            pen=pen,
            brush=brush,
        )
        current_item.setPos(sx0, y_base + sy0)
        current_item.setZValue(11)
        self._current_highlight = current_item

    def clear_search_highlights(self) -> None:
        """Remove all search highlight overlays from the scene."""
        for item in self._search_highlights:
            self._scene.removeItem(item)
        self._search_highlights.clear()

        if self._current_highlight is not None:
            self._scene.removeItem(self._current_highlight)
            self._current_highlight = None

    @property
    def selection_mode(self) -> bool:
        """Return whether text selection mode is active."""
        return self._selection_mode

    def set_tool_mode(self, mode: ToolMode) -> None:
        """Set the active tool mode for viewport interaction.

        Args:
            mode: The tool mode to activate.
        """
        self._tool_mode = mode
        self._selection_mode = mode is ToolMode.TEXT_SELECT

        if mode is ToolMode.NONE:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.unsetCursor()
            self.clear_selection_overlay()
        elif mode is ToolMode.TEXT_SELECT:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.IBeamCursor)
        elif mode in (ToolMode.STICKY_NOTE, ToolMode.TEXT_BOX) or mode.value >= 10:
            # STICKY_NOTE, TEXT_BOX, and all FORM_* modes use cross cursor
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)

        # setDragMode(ScrollHandDrag) can re-enable acceptDrops on
        # the internal viewport widget; keep drops disabled so file
        # drag-drop propagates to MainWindow.
        self.setAcceptDrops(False)
        self.viewport().setAcceptDrops(False)

        self._drag_start = None
        self._textbox_drag_start = None

    def set_selection_mode(self, active: bool) -> None:
        """Toggle between pan mode and text selection mode.

        Compatibility shim that delegates to set_tool_mode.

        Args:
            active: True to enable text selection, False for pan.
        """
        self.set_tool_mode(ToolMode.TEXT_SELECT if active else ToolMode.NONE)

    def set_annotation_engine(self, engine: object) -> None:
        """Set the annotation engine for word rect queries.

        Args:
            engine: An AnnotationEngine instance.
        """
        self._annotation_engine = engine

    def set_doc_handle(self, doc_handle: object) -> None:
        """Set the document handle for annotation operations.

        Args:
            doc_handle: A pymupdf.Document handle (opaque to this layer).
        """
        self._doc_handle = doc_handle

    def show_selection_overlay(
        self,
        page_index: int,
        word_rects: list[tuple[float, float, float, float]],
    ) -> None:
        """Draw selection overlays for a list of word rects on a page.

        Used by select-all to show visual feedback. Clears any existing
        selection overlay before drawing.

        Args:
            page_index: 0-based page index.
            word_rects: List of (x0, y0, x1, y1) in PDF coordinates.
        """
        self.clear_selection_overlay()
        if page_index < 0 or page_index >= len(self._page_y_offsets):
            return

        page_info = self._pages[page_index]
        item = self._page_items.get(page_index)
        if item is None:
            return
        zoom = item.boundingRect().width() / page_info.width if page_info.width else 1.0
        y_base = self._page_y_offsets[page_index]

        pen = QPen(QColor(0, 100, 200, 100))
        pen.setWidthF(0.5)
        brush = QBrush(QColor(51, 153, 255, 80))

        for wx0, wy0, wx1, wy1 in word_rects:
            sx = wx0 * zoom
            sy = wy0 * zoom + y_base
            sw = (wx1 - wx0) * zoom
            sh = (wy1 - wy0) * zoom
            rect_item = self._scene.addRect(QRectF(0, 0, sw, sh), pen=pen, brush=brush)
            rect_item.setPos(sx, sy)
            rect_item.setZValue(15)
            self._selection_overlays.append(rect_item)

    def clear_selection_overlay(self) -> None:
        """Remove all text selection overlay items from the scene."""
        for item in self._selection_overlays:
            self._scene.removeItem(item)
        self._selection_overlays.clear()

    def _page_at_scene_pos(self, scene_pos: QPointF) -> int:
        """Return the page index at the given scene position, or -1.

        Uses the rendered page item bounding rect so the hit area
        matches the actual (zoomed) page dimensions on screen.
        """
        if not self._pages or not self._page_y_offsets:
            return -1
        for i, y_off in enumerate(self._page_y_offsets):
            item = self._page_items.get(i)
            page_h = item.boundingRect().height() if item is not None else self._pages[i].height
            page_bottom = y_off + page_h
            if y_off <= scene_pos.y() <= page_bottom:
                return i
        return -1

    def _scene_to_pdf_coords(
        self, scene_pos: QPointF, page_index: int, zoom: float
    ) -> tuple[float, float]:
        """Map scene coordinates to PDF page coordinates.

        Args:
            scene_pos: Position in scene coordinates.
            page_index: The page index.
            zoom: Current zoom factor.

        Returns:
            (x, y) in PDF page coordinates.
        """
        y_off = self._page_y_offsets[page_index]
        x = (scene_pos.x()) / zoom if zoom else scene_pos.x()
        y = (scene_pos.y() - y_off) / zoom if zoom else (scene_pos.y() - y_off)
        return (x, y)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press — text selection, sticky note, text box, or context menu."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._tool_mode is ToolMode.TEXT_SELECT:
                self._drag_start = self.mapToScene(event.pos())
                self.clear_selection_overlay()
                event.accept()
                return
            if self._tool_mode is ToolMode.STICKY_NOTE:
                self._handle_sticky_note_click(event)
                event.accept()
                return
            if self._tool_mode is ToolMode.TEXT_BOX:
                self._textbox_drag_start = self.mapToScene(event.pos())
                event.accept()
                return
            if self._tool_mode.value >= 10:  # FORM_* modes
                self._handle_form_field_click(event)
                event.accept()
                return
        if event.button() == Qt.MouseButton.RightButton:
            self._show_annotation_context_menu(event)
            event.accept()
            return
        super().mousePressEvent(event)

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move — text selection or text box drag preview."""
        if self._tool_mode is ToolMode.TEXT_SELECT and self._drag_start is not None:
            current = self.mapToScene(event.pos())
            self._update_selection_overlay(self._drag_start, current)
            event.accept()
            return
        if self._tool_mode is ToolMode.TEXT_BOX and self._textbox_drag_start is not None:
            current = self.mapToScene(event.pos())
            self._update_textbox_preview(self._textbox_drag_start, current)
            event.accept()
            return
        super().mouseMoveEvent(event)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release — finalize text selection or text box drawing."""
        if (
            self._tool_mode is ToolMode.TEXT_SELECT
            and event.button() == Qt.MouseButton.LeftButton
            and self._drag_start is not None
        ):
            end = self.mapToScene(event.pos())
            page_index, selected_rects = self._finalize_selection(self._drag_start, end)
            self._drag_start = None
            if page_index >= 0 and selected_rects:
                self.text_selected.emit(page_index, selected_rects)
            event.accept()
            return
        if (
            self._tool_mode is ToolMode.TEXT_BOX
            and event.button() == Qt.MouseButton.LeftButton
            and self._textbox_drag_start is not None
        ):
            end = self.mapToScene(event.pos())
            self._finalize_textbox_draw(self._textbox_drag_start, end)
            self._textbox_drag_start = None
            self._clear_textbox_preview()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    @override
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Handle double-click — open editor for existing annotation.

        When a tool mode is active (STICKY_NOTE, TEXT_BOX, TEXT_SELECT) the
        event is always consumed so the default QGraphicsView double-click
        handler never fires and cannot cause crashes.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            annot = self._hit_test_annotation(scene_pos)
            if annot is not None:
                page_index = self._page_at_scene_pos(scene_pos)
                if page_index >= 0:
                    self.annotation_double_clicked.emit(page_index, annot)
                    event.accept()
                    return
            # When a tool mode is active, consume the double-click to prevent
            # the default QGraphicsView handler from causing unexpected behavior.
            if self._tool_mode is not ToolMode.NONE:
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def _handle_sticky_note_click(self, event: QMouseEvent) -> None:
        """Handle click in sticky note mode — emit note_placed signal."""
        scene_pos = self.mapToScene(event.pos())
        page_index = self._page_at_scene_pos(scene_pos)
        if page_index < 0:
            return

        page_info = self._pages[page_index]
        item = self._page_items.get(page_index)
        if item is None:
            return
        zoom = item.boundingRect().width() / page_info.width if page_info.width else 1.0

        pdf_x, pdf_y = self._scene_to_pdf_coords(scene_pos, page_index, zoom)

        # Snap to page bounds
        pdf_x = max(0.0, min(pdf_x, page_info.width))
        pdf_y = max(0.0, min(pdf_y, page_info.height))

        self.note_placed.emit(page_index, (pdf_x, pdf_y))

    def _handle_form_field_click(self, event: QMouseEvent) -> None:
        """Handle click in form field placement mode — emit form_field_placed."""
        scene_pos = self.mapToScene(event.pos())
        page_index = self._page_at_scene_pos(scene_pos)
        if page_index < 0:
            return

        page_info = self._pages[page_index]
        item = self._page_items.get(page_index)
        if item is None:
            return
        zoom = item.boundingRect().width() / page_info.width if page_info.width else 1.0

        pdf_x, pdf_y = self._scene_to_pdf_coords(scene_pos, page_index, zoom)

        # Snap to page bounds
        pdf_x = max(0.0, min(pdf_x, page_info.width))
        pdf_y = max(0.0, min(pdf_y, page_info.height))

        self.form_field_placed.emit(page_index, (pdf_x, pdf_y), int(self._tool_mode))

    def _update_textbox_preview(self, start: QPointF, current: QPointF) -> None:
        """Draw a preview rectangle during text box drag."""
        self._clear_textbox_preview()

        x0 = min(start.x(), current.x())
        y0 = min(start.y(), current.y())
        w = abs(current.x() - start.x())
        h = abs(current.y() - start.y())

        pen = QPen(QColor(0, 0, 200, 180))
        pen.setWidthF(1.5)
        pen.setStyle(Qt.PenStyle.DashLine)
        brush = QBrush(QColor(0, 0, 200, 30))

        self._textbox_preview = self._scene.addRect(QRectF(0, 0, w, h), pen=pen, brush=brush)
        self._textbox_preview.setPos(x0, y0)
        self._textbox_preview.setZValue(20)

    def _clear_textbox_preview(self) -> None:
        """Remove the text box drag preview from the scene."""
        if self._textbox_preview is not None:
            self._scene.removeItem(self._textbox_preview)
            self._textbox_preview = None

    def _finalize_textbox_draw(self, start: QPointF, end: QPointF) -> None:
        """Finalize text box drawing and emit textbox_drawn signal."""
        page_index = self._page_at_scene_pos(start)
        if page_index < 0:
            return

        page_info = self._pages[page_index]
        item = self._page_items.get(page_index)
        if item is None:
            return
        zoom = item.boundingRect().width() / page_info.width if page_info.width else 1.0

        pdf_start = self._scene_to_pdf_coords(start, page_index, zoom)
        pdf_end = self._scene_to_pdf_coords(end, page_index, zoom)

        # Normalize and snap to page bounds
        x0 = max(0.0, min(pdf_start[0], pdf_end[0]))
        y0 = max(0.0, min(pdf_start[1], pdf_end[1]))
        x1 = min(page_info.width, max(pdf_start[0], pdf_end[0]))
        y1 = min(page_info.height, max(pdf_start[1], pdf_end[1]))

        # Minimum size check
        if abs(x1 - x0) < 5.0 or abs(y1 - y0) < 5.0:
            return

        self.textbox_drawn.emit(page_index, (x0, y0, x1, y1))

    def _hit_test_annotation(self, scene_pos: QPointF) -> object | None:
        """Hit-test annotations at the given scene position.

        Returns the topmost sticky note or text box annotation at the point.
        Delegates to AnnotationEngine.hit_test_annotation() which keeps the
        page object alive to prevent pymupdf stale-reference crashes.
        """
        if self._annotation_engine is None or self._doc_handle is None:
            return None

        page_index = self._page_at_scene_pos(scene_pos)
        if page_index < 0:
            return None

        page_info = self._pages[page_index]
        item = self._page_items.get(page_index)
        if item is None:
            return None
        zoom = item.boundingRect().width() / page_info.width if page_info.width else 1.0

        pdf_x, pdf_y = self._scene_to_pdf_coords(scene_pos, page_index, zoom)

        return self._annotation_engine.hit_test_annotation(  # type: ignore[attr-defined]
            self._doc_handle, page_index, pdf_x, pdf_y
        )

    def _update_selection_overlay(self, start: QPointF, current: QPointF) -> None:
        """Draw selection overlay rectangles over words in the drag range."""
        self.clear_selection_overlay()
        if self._annotation_engine is None or self._doc_handle is None:
            return

        page_index = self._page_at_scene_pos(start)
        if page_index < 0:
            return

        # Determine zoom from page geometry
        page_info = self._pages[page_index]
        item = self._page_items.get(page_index)
        if item is None:
            return
        zoom = item.boundingRect().width() / page_info.width if page_info.width else 1.0

        pdf_start = self._scene_to_pdf_coords(start, page_index, zoom)
        pdf_end = self._scene_to_pdf_coords(current, page_index, zoom)

        # Get selection rectangle in PDF coords
        x0 = min(pdf_start[0], pdf_end[0])
        y0 = min(pdf_start[1], pdf_end[1])
        x1 = max(pdf_start[0], pdf_end[0])
        y1 = max(pdf_start[1], pdf_end[1])

        words = self._annotation_engine.get_text_words(self._doc_handle, page_index)  # type: ignore[attr-defined]
        y_base = self._page_y_offsets[page_index]

        pen = QPen(QColor(0, 100, 200, 100))
        pen.setWidthF(0.5)
        brush = QBrush(QColor(51, 153, 255, 80))

        for w in words:
            wx0, wy0, wx1, wy1 = w[0], w[1], w[2], w[3]
            # Check if word overlaps selection rectangle
            if wx1 >= x0 and wx0 <= x1 and wy1 >= y0 and wy0 <= y1:
                sx = wx0 * zoom
                sy = wy0 * zoom + y_base
                sw = (wx1 - wx0) * zoom
                sh = (wy1 - wy0) * zoom
                rect_item = self._scene.addRect(QRectF(0, 0, sw, sh), pen=pen, brush=brush)
                rect_item.setPos(sx, sy)
                rect_item.setZValue(15)
                self._selection_overlays.append(rect_item)

    def _finalize_selection(
        self, start: QPointF, end: QPointF
    ) -> tuple[int, list[tuple[float, float, float, float]]]:
        """Finalize selection and return page index + selected word rects.

        Returns word bounding-box tuples (not pymupdf Quads) to keep pymupdf
        out of the view layer. The presenter converts to quads via
        AnnotationEngine.rects_to_quads() before creating annotations.

        Args:
            start: Drag start in scene coordinates.
            end: Drag end in scene coordinates.

        Returns:
            Tuple of (page_index, word_rects) where word_rects is a list
            of (x0, y0, x1, y1) tuples in PDF coordinates for selected words.
            page_index is -1 if no words selected.
        """
        if self._annotation_engine is None or self._doc_handle is None:
            return (-1, [])

        page_index = self._page_at_scene_pos(start)
        if page_index < 0:
            return (-1, [])

        page_info = self._pages[page_index]
        item = self._page_items.get(page_index)
        if item is None:
            return (-1, [])
        zoom = item.boundingRect().width() / page_info.width if page_info.width else 1.0

        pdf_start = self._scene_to_pdf_coords(start, page_index, zoom)
        pdf_end = self._scene_to_pdf_coords(end, page_index, zoom)

        x0 = min(pdf_start[0], pdf_end[0])
        y0 = min(pdf_start[1], pdf_end[1])
        x1 = max(pdf_start[0], pdf_end[0])
        y1 = max(pdf_start[1], pdf_end[1])

        words = self._annotation_engine.get_text_words(self._doc_handle, page_index)  # type: ignore[attr-defined]

        selected_rects: list[tuple[float, float, float, float]] = []
        for w in words:
            wx0, wy0, wx1, wy1 = w[0], w[1], w[2], w[3]
            if wx1 >= x0 and wx0 <= x1 and wy1 >= y0 and wy0 <= y1:
                selected_rects.append((wx0, wy0, wx1, wy1))

        return (page_index, selected_rects)

    def _show_annotation_context_menu(self, event: QMouseEvent) -> None:
        """Show a context menu for deleting annotations on right-click.

        Delegates hit-testing to AnnotationEngine.hit_test_annotation() to
        keep the page object alive and prevent stale-reference crashes.
        """
        if self._annotation_engine is None or self._doc_handle is None:
            return

        scene_pos = self.mapToScene(event.pos())
        page_index = self._page_at_scene_pos(scene_pos)
        if page_index < 0:
            return

        page_info = self._pages[page_index]
        item = self._page_items.get(page_index)
        if item is None:
            return
        zoom = item.boundingRect().width() / page_info.width if page_info.width else 1.0

        pdf_x, pdf_y = self._scene_to_pdf_coords(scene_pos, page_index, zoom)

        hit_annot = self._annotation_engine.hit_test_annotation(  # type: ignore[attr-defined]
            self._doc_handle, page_index, pdf_x, pdf_y
        )

        if hit_annot is None:
            return

        menu = QMenu(self)
        delete_action = menu.addAction("Delete Annotation")
        chosen = menu.exec(event.globalPosition().toPoint())
        if chosen == delete_action:
            self.annotation_delete_requested.emit(page_index, hit_annot)

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

    # --- Form overlay methods ---

    def add_form_overlay(
        self,
        widget: QWidget,
        page_index: int,
        rect: tuple[float, float, float, float],
        zoom: float = 1.0,
    ) -> None:
        """Add a form field widget overlay to the scene.

        Args:
            widget: The Qt widget (QLineEdit, QCheckBox, QComboBox).
            page_index: Zero-based page index.
            rect: Bounding rectangle (x0, y0, x1, y1) in PDF coordinates.
            zoom: Current zoom factor.
        """
        if page_index < 0 or page_index >= len(self._page_y_offsets):
            return

        x0, y0, x1, y1 = rect
        y_base = self._page_y_offsets[page_index]

        proxy = self._scene.addWidget(widget)
        proxy.setPos(x0 * zoom, y_base + y0 * zoom)
        proxy.setZValue(20)
        widget.setFixedSize(int((x1 - x0) * zoom), int((y1 - y0) * zoom))
        self._form_overlays.append(proxy)

    def remove_form_overlays(self) -> None:
        """Remove all form overlay proxy widgets from the scene."""
        for proxy in self._form_overlays:
            self._scene.removeItem(proxy)
        self._form_overlays.clear()
