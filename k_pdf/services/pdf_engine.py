"""PyMuPDF wrapper: open, render, save.

All fitz/pymupdf imports are contained in this file.
No other module in k_pdf may import fitz or pymupdf.
"""

from __future__ import annotations

import logging
from pathlib import Path

from k_pdf.services.pdf_errors import PdfValidationError

logger = logging.getLogger("k_pdf.services.pdf_engine")

_PDF_HEADER = b"%PDF-"


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
