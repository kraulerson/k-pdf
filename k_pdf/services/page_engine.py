"""Page manipulation (add, delete, reorder, rotate).

All pymupdf page manipulation calls are isolated in this service.
No other module in k_pdf may import pymupdf for page operations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pymupdf
from PySide6.QtGui import QImage, QPixmap

from k_pdf.core.page_model import PageOperation, PageOperationResult

logger = logging.getLogger("k_pdf.services.page_engine")

_VALID_ANGLES = {90, 180, 270}


class PageEngine:
    """Wraps PyMuPDF page manipulation operations.

    All methods take a doc_handle (pymupdf.Document).
    The caller (PageManagementPresenter) never imports pymupdf directly.
    """

    def delete_pages(self, doc_handle: Any, page_indices: list[int]) -> PageOperationResult:
        """Delete pages from the document.

        Blocks deletion if it would remove all pages.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_indices: Zero-based indices of pages to delete.

        Returns:
            PageOperationResult indicating success or failure.
        """
        current_count = doc_handle.page_count
        if len(page_indices) >= current_count:
            return PageOperationResult(
                operation=PageOperation.DELETE,
                success=False,
                new_page_count=current_count,
                affected_pages=page_indices,
                error_message=("Cannot delete all pages. A PDF must contain at least one page."),
            )

        try:
            doc_handle.delete_pages(page_indices)
            new_count = doc_handle.page_count
            logger.debug("Deleted pages %s, new count: %d", page_indices, new_count)
            return PageOperationResult(
                operation=PageOperation.DELETE,
                success=True,
                new_page_count=new_count,
                affected_pages=page_indices,
            )
        except Exception as e:
            logger.warning("Failed to delete pages %s: %s", page_indices, e)
            return PageOperationResult(
                operation=PageOperation.DELETE,
                success=False,
                new_page_count=doc_handle.page_count,
                affected_pages=page_indices,
                error_message=str(e),
            )

    def move_page(self, doc_handle: Any, from_index: int, to_index: int) -> PageOperationResult:
        """Move a page from one position to another.

        Args:
            doc_handle: A pymupdf.Document handle.
            from_index: Current zero-based page index.
            to_index: Target zero-based page index.

        Returns:
            PageOperationResult indicating success or failure.
        """
        try:
            doc_handle.move_page(from_index, to_index)
            logger.debug("Moved page %d to %d", from_index, to_index)
            return PageOperationResult(
                operation=PageOperation.MOVE,
                success=True,
                new_page_count=doc_handle.page_count,
                affected_pages=[from_index, to_index],
            )
        except Exception as e:
            logger.warning("Failed to move page %d to %d: %s", from_index, to_index, e)
            return PageOperationResult(
                operation=PageOperation.MOVE,
                success=False,
                new_page_count=doc_handle.page_count,
                affected_pages=[from_index, to_index],
                error_message=str(e),
            )

    def rotate_pages(
        self, doc_handle: Any, page_indices: list[int], angle: int
    ) -> PageOperationResult:
        """Rotate selected pages by the given angle.

        Modifies the PDF /Rotate attribute (permanent, unlike Feature 5 view rotation).

        Args:
            doc_handle: A pymupdf.Document handle.
            page_indices: Zero-based indices of pages to rotate.
            angle: Rotation angle — must be 90, 180, or 270.

        Returns:
            PageOperationResult indicating success or failure.
        """
        if angle not in _VALID_ANGLES:
            return PageOperationResult(
                operation=PageOperation.ROTATE,
                success=False,
                new_page_count=doc_handle.page_count,
                affected_pages=page_indices,
                error_message=f"Invalid angle {angle}. Must be 90, 180, or 270.",
            )

        try:
            for idx in page_indices:
                page = doc_handle[idx]
                new_rotation = (page.rotation + angle) % 360
                page.set_rotation(new_rotation)
            logger.debug("Rotated pages %s by %d degrees", page_indices, angle)
            return PageOperationResult(
                operation=PageOperation.ROTATE,
                success=True,
                new_page_count=doc_handle.page_count,
                affected_pages=page_indices,
            )
        except Exception as e:
            logger.warning("Failed to rotate pages %s: %s", page_indices, e)
            return PageOperationResult(
                operation=PageOperation.ROTATE,
                success=False,
                new_page_count=doc_handle.page_count,
                affected_pages=page_indices,
                error_message=str(e),
            )

    def insert_pages_from(
        self, doc_handle: Any, source_path: Path, insert_index: int
    ) -> PageOperationResult:
        """Insert all pages from a source PDF at the given position.

        Args:
            doc_handle: A pymupdf.Document handle (target).
            source_path: Path to the source PDF file.
            insert_index: Zero-based position to insert pages.

        Returns:
            PageOperationResult indicating success or failure.
        """
        original_count = doc_handle.page_count
        try:
            source_doc = pymupdf.open(str(source_path))
        except Exception as e:
            logger.warning("Failed to open source PDF %s: %s", source_path, e)
            return PageOperationResult(
                operation=PageOperation.INSERT,
                success=False,
                new_page_count=original_count,
                affected_pages=[],
                error_message=f"Could not insert pages from {source_path.name}. {e}",
            )

        try:
            source_count = source_doc.page_count
            doc_handle.insert_pdf(
                source_doc,
                from_page=0,
                to_page=source_count - 1,
                start_at=insert_index,
            )
            source_doc.close()
            new_count = doc_handle.page_count
            affected = list(range(insert_index, insert_index + source_count))
            logger.debug(
                "Inserted %d pages from %s at index %d",
                source_count,
                source_path.name,
                insert_index,
            )
            return PageOperationResult(
                operation=PageOperation.INSERT,
                success=True,
                new_page_count=new_count,
                affected_pages=affected,
            )
        except Exception as e:
            source_doc.close()
            logger.warning("Failed to insert pages from %s: %s", source_path, e)
            return PageOperationResult(
                operation=PageOperation.INSERT,
                success=False,
                new_page_count=doc_handle.page_count,
                affected_pages=[],
                error_message=f"Could not insert pages from {source_path.name}. {e}",
            )

    def render_thumbnail(self, doc_handle: Any, page_index: int, width: int = 150) -> QPixmap:
        """Render a page at thumbnail resolution.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            width: Target thumbnail width in pixels.

        Returns:
            QPixmap with the rendered thumbnail.
        """
        page = doc_handle[page_index]
        zoom = width / page.rect.width
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        image = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format.Format_RGB888,
        )
        # Deep copy — QImage references pix.samples buffer
        return QPixmap.fromImage(image.copy())

    def get_page_count(self, doc_handle: Any) -> int:
        """Return the document page count.

        Args:
            doc_handle: A pymupdf.Document handle.

        Returns:
            Number of pages in the document.
        """
        result: int = doc_handle.page_count
        return result
