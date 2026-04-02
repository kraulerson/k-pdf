"""Tests for PdfEngine service."""

from __future__ import annotations

from pathlib import Path

import pytest

from k_pdf.services.pdf_engine import PdfEngine
from k_pdf.services.pdf_errors import (
    PdfOpenError,
    PdfPasswordIncorrectError,
    PdfPasswordRequiredError,
    PdfValidationError,
)


class TestValidatePdfPath:
    """Tests for PdfEngine.validate_pdf_path."""

    def setup_method(self) -> None:
        """Instantiate a fresh PdfEngine before each test."""
        self.engine = PdfEngine()

    def test_raises_when_file_not_found(self, nonexistent_pdf: Path) -> None:
        """PdfValidationError raised with 'not found' when path does not exist."""
        with pytest.raises(PdfValidationError, match="not found"):
            self.engine.validate_pdf_path(nonexistent_pdf)

    def test_raises_when_file_not_readable(self, unreadable_pdf: Path) -> None:
        """PdfValidationError raised with 'permission' when file is unreadable."""
        with pytest.raises(PdfValidationError, match="permission"):
            self.engine.validate_pdf_path(unreadable_pdf)

    def test_raises_when_not_a_pdf(self, not_a_pdf: Path) -> None:
        """PdfValidationError raised when file lacks a valid PDF header."""
        with pytest.raises(PdfValidationError, match="does not appear to be a valid PDF"):
            self.engine.validate_pdf_path(not_a_pdf)

    def test_passes_for_valid_pdf(self, valid_pdf: Path) -> None:
        """No exception raised for a well-formed PDF file."""
        self.engine.validate_pdf_path(valid_pdf)  # should not raise

    def test_passes_for_encrypted_pdf(self, encrypted_pdf: Path) -> None:
        """No exception raised for an encrypted PDF — header check still passes."""
        self.engine.validate_pdf_path(encrypted_pdf)  # header check passes


class TestOpenDocument:
    """Tests for PdfEngine.open_document."""

    def setup_method(self) -> None:
        """Set up test engine instance."""
        self.engine = PdfEngine()

    def test_opens_valid_pdf_returns_metadata(self, valid_pdf: Path) -> None:
        """Test opening a valid PDF returns correct metadata."""
        result = self.engine.open_document(valid_pdf)
        assert result.metadata.page_count == 3
        assert result.metadata.file_path == valid_pdf
        assert result.metadata.is_encrypted is False
        assert len(result.pages) == 3
        assert result.doc_handle is not None
        self.engine.close_document(result.doc_handle)

    def test_pages_have_correct_dimensions(self, valid_pdf: Path) -> None:
        """Test pages have US Letter dimensions."""
        result = self.engine.open_document(valid_pdf)
        page = result.pages[0]
        assert page.index == 0
        assert page.width == pytest.approx(612.0, abs=1.0)
        assert page.height == pytest.approx(792.0, abs=1.0)
        assert page.rotation == 0
        self.engine.close_document(result.doc_handle)

    def test_raises_password_required_for_encrypted_pdf(self, encrypted_pdf: Path) -> None:
        """Test encrypted PDF without password raises PdfPasswordRequiredError."""
        with pytest.raises(PdfPasswordRequiredError):
            self.engine.open_document(encrypted_pdf)

    def test_opens_encrypted_pdf_with_correct_password(self, encrypted_pdf: Path) -> None:
        """Test encrypted PDF opens with correct password."""
        result = self.engine.open_document(encrypted_pdf, password="testpass")
        assert result.metadata.page_count == 1
        assert result.metadata.is_encrypted is True
        self.engine.close_document(result.doc_handle)

    def test_raises_password_incorrect_for_wrong_password(self, encrypted_pdf: Path) -> None:
        """Test wrong password raises PdfPasswordIncorrectError."""
        with pytest.raises(PdfPasswordIncorrectError):
            self.engine.open_document(encrypted_pdf, password="wrong")

    def test_raises_open_error_for_corrupt_pdf(self, corrupt_pdf: Path) -> None:
        """Test corrupt PDF raises PdfOpenError."""
        with pytest.raises(PdfOpenError):
            self.engine.open_document(corrupt_pdf)
