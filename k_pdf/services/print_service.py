"""Print service — renders PDF pages to a QPrinter.

Uses PdfEngine.render_page() to produce QImages at print resolution,
then paints them onto the QPrinter via QPainter. Does NOT import
fitz/pymupdf directly — all PDF access goes through PdfEngine.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtPrintSupport import QPrinter

from k_pdf.services.pdf_engine import PdfEngine

logger = logging.getLogger("k_pdf.services.print_service")

# 300 DPI / 72 DPI (PDF points) = zoom factor for print quality
PRINT_ZOOM = 300 / 72


@dataclass(frozen=True)
class PrintResult:
    """Result of a print operation."""

    success: bool
    pages_printed: int = 0
    error_message: str = ""


class PrintService:
    """Renders PDF pages to a QPrinter at 300 DPI."""

    def print_document(
        self,
        printer: QPrinter,
        doc_handle: Any,
        page_count: int,
        pdf_engine: PdfEngine,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> PrintResult:
        """Render and print pages per QPrinter settings.

        Args:
            printer: Configured QPrinter (from QPrintDialog).
            doc_handle: Opaque PyMuPDF document handle.
            page_count: Total number of pages in the document.
            pdf_engine: PdfEngine instance for rendering pages.
            progress_callback: Optional (current, total) callback per page.

        Returns:
            PrintResult indicating success/failure and pages printed.
        """
        # Determine page range (QPrinter uses 1-based; 0 means all)
        from_page = printer.fromPage()
        to_page = printer.toPage()

        if from_page == 0:
            # Print all pages
            page_indices = list(range(page_count))
        else:
            # Convert 1-based to 0-based
            page_indices = list(range(from_page - 1, to_page))

        total = len(page_indices)

        painter = QPainter()
        if not painter.begin(printer):
            return PrintResult(
                success=False,
                pages_printed=0,
                error_message="Failed to begin painting — printer may be unavailable",
            )

        try:
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)

            for i, page_index in enumerate(page_indices):
                image: QImage = pdf_engine.render_page(doc_handle, page_index, zoom=PRINT_ZOOM)

                # Scale image to fit printer page rect while maintaining aspect ratio
                target = self._fit_rect(image, page_rect)
                painter.drawImage(target, image)

                if progress_callback is not None:
                    progress_callback(i + 1, total)

                # Insert page break between pages (not after last)
                if i < total - 1:
                    printer.newPage()

        except Exception as exc:
            painter.end()
            logger.exception("Print failed")
            return PrintResult(
                success=False,
                pages_printed=0,
                error_message=str(exc),
            )

        painter.end()
        return PrintResult(success=True, pages_printed=total)

    @staticmethod
    def _fit_rect(image: QImage, page_rect: QRectF) -> QRectF:
        """Compute a target rect that fits image into page_rect keeping aspect ratio.

        Args:
            image: The source QImage.
            page_rect: The printable area on the page.

        Returns:
            QRectF centered in page_rect with correct aspect ratio.
        """
        img_w = float(image.width())
        img_h = float(image.height())
        page_w = page_rect.width()
        page_h = page_rect.height()

        if img_w <= 0 or img_h <= 0:
            return QRectF(0, 0, page_w, page_h)

        scale = min(page_w / img_w, page_h / img_h)
        scaled_w = img_w * scale
        scaled_h = img_h * scale

        x = page_rect.x() + (page_w - scaled_w) / 2
        y = page_rect.y() + (page_h - scaled_h) / 2

        return QRectF(x, y, scaled_w, scaled_h)
