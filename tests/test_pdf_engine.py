"""Tests for PdfEngine service."""

from __future__ import annotations

from pathlib import Path

import pytest

from k_pdf.services.pdf_engine import PdfEngine
from k_pdf.services.pdf_errors import PdfValidationError


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
