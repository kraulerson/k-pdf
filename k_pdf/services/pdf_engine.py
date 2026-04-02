"""PyMuPDF wrapper: open, render, save.

All fitz/pymupdf imports are contained in this file.
No other module in k_pdf may import fitz or pymupdf.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf
from PySide6.QtGui import QImage

from k_pdf.core.document_model import DocumentMetadata, PageInfo
from k_pdf.services.pdf_errors import (
    PageRenderError,
    PdfOpenError,
    PdfPasswordIncorrectError,
    PdfPasswordRequiredError,
    PdfValidationError,
)

logger = logging.getLogger("k_pdf.services.pdf_engine")

_PDF_HEADER = b"%PDF-"


@dataclass
class OpenResult:
    """Result of opening a PDF document."""

    doc_handle: Any  # pymupdf.Document
    metadata: DocumentMetadata
    pages: list[PageInfo]


class PdfEngine:
    """Stateless PyMuPDF wrapper. Thread-safe for concurrent reads."""

    def validate_pdf_path(self, path: Path) -> None:
        """Check file exists, is readable, and has a PDF header.

        Args:
            path: Path to the file to validate.

        Raises:
            PdfValidationError: If any validation check fails.
        """
        if not path.exists():
            msg = f"File not found: {path}"
            raise PdfValidationError(msg)

        if not path.is_file():
            msg = f"Not a file: {path}"
            raise PdfValidationError(msg)

        try:
            with path.open("rb") as f:
                header = f.read(len(_PDF_HEADER))
        except PermissionError as e:
            msg = f"Cannot open {path.name}: permission denied"
            raise PdfValidationError(msg) from e

        if header != _PDF_HEADER:
            msg = f"Cannot open {path.name}: this file does not appear to be a valid PDF"
            raise PdfValidationError(msg)

    def open_document(self, path: Path, password: str | None = None) -> OpenResult:
        """Open a PDF and return handle, metadata, and page info.

        Args:
            path: Path to the PDF file (should be pre-validated).
            password: Optional password for encrypted PDFs.

        Returns:
            OpenResult with doc handle, metadata, and page list.

        Raises:
            PdfPasswordRequiredError: If the PDF is encrypted and no password given.
            PdfPasswordIncorrectError: If the provided password is wrong.
            PdfOpenError: If the PDF is corrupt or cannot be parsed.
        """
        try:
            doc = pymupdf.open(str(path))
        except Exception as e:
            msg = f"Cannot open {path.name}: the file is damaged or corrupted. {e}"
            raise PdfOpenError(msg) from e

        # Capture encryption state before authentication clears it.
        was_encrypted = doc.is_encrypted
        if doc.needs_pass:
            if password is None:
                doc.close()
                raise PdfPasswordRequiredError(str(path))
            if not doc.authenticate(password):
                doc.close()
                raise PdfPasswordIncorrectError(str(path))

        if doc.page_count == 0:
            doc.close()
            msg = f"Cannot open {path.name}: the file is damaged or corrupted (0 pages)."
            raise PdfOpenError(msg)

        try:
            toc = doc.get_toc()
        except Exception:
            toc = []

        raw_meta = doc.metadata or {}
        metadata = DocumentMetadata(
            file_path=path,
            page_count=doc.page_count,
            title=raw_meta.get("title") or None,
            author=raw_meta.get("author") or None,
            has_forms=bool(doc.is_form_pdf),
            has_outline=len(toc) > 0,
            has_javascript=False,  # detected per-field in Feature 8
            is_encrypted=was_encrypted,
            file_size_bytes=path.stat().st_size,
        )

        pages: list[PageInfo] = []
        for i in range(doc.page_count):
            page = doc[i]
            pages.append(
                PageInfo(
                    index=i,
                    width=page.rect.width,
                    height=page.rect.height,
                    rotation=page.rotation,
                    has_text=bool(page.get_text("text").strip()),
                    annotation_count=len(list(page.annots())),
                )
            )

        return OpenResult(doc_handle=doc, metadata=metadata, pages=pages)

    def close_document(self, doc_handle: Any) -> None:
        """Close a PyMuPDF document handle and release memory.

        Args:
            doc_handle: The pymupdf.Document to close.
        """
        try:
            doc_handle.close()
        except Exception:
            logger.warning("Failed to close document handle", exc_info=True)

    def render_page(
        self,
        doc_handle: Any,
        page_index: int,
        zoom: float = 1.0,
        rotation: int = 0,
    ) -> QImage:
        """Render a single PDF page to a QImage.

        This method is thread-safe and intended to be called from worker threads.
        The caller should convert QImage to QPixmap on the main thread.

        Args:
            doc_handle: The pymupdf.Document containing the page.
            page_index: 0-based page index.
            zoom: Zoom factor (1.0 = 100%).
            rotation: Additional rotation in degrees (0, 90, 180, 270).

        Returns:
            QImage with the rendered page content.

        Raises:
            PageRenderError: If the page cannot be rendered.
        """
        try:
            if page_index < 0 or page_index >= doc_handle.page_count:
                msg = f"Page index {page_index} out of range (0-{doc_handle.page_count - 1})"
                raise IndexError(msg)

            page = doc_handle[page_index]
            mat = pymupdf.Matrix(zoom, zoom).prerotate(rotation)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            image = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                QImage.Format.Format_RGB888,
            )
            # QImage references pix.samples buffer — make a deep copy
            return image.copy()

        except IndexError as e:
            raise PageRenderError(str(e)) from e
        except Exception as e:
            msg = f"Failed to render page {page_index}: {e}"
            raise PageRenderError(msg) from e
