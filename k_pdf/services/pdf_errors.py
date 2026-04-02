"""PDF operation error types.

All PDF-related exceptions inherit from PdfError.
Used by PdfEngine; caught and translated by DocumentPresenter.
"""

from __future__ import annotations


class PdfError(Exception):
    """Base class for all PDF operation errors."""


class PdfValidationError(PdfError):
    """File validation failed (not found, permissions, not a PDF)."""


class PdfOpenError(PdfError):
    """PDF parsing/opening failed (corrupt file, unexpected error)."""


class PdfPasswordRequiredError(PdfError):
    """PDF is encrypted and requires a password."""


class PdfPasswordIncorrectError(PdfError):
    """Provided password was incorrect."""


class PageRenderError(PdfError):
    """A single page failed to render."""
