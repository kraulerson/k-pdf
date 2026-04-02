"""Shared test fixtures — programmatically generated PDF files."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest


@pytest.fixture
def valid_pdf(tmp_path: Path) -> Path:
    """Create a valid 3-page PDF with text content."""
    path = tmp_path / "test.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page(width=612, height=792)  # US Letter
        text_point = pymupdf.Point(72, 72)
        page.insert_text(text_point, f"Page {i + 1} content")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def encrypted_pdf(tmp_path: Path) -> Path:
    """Create an encrypted PDF with password 'testpass'."""
    path = tmp_path / "encrypted.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(pymupdf.Point(72, 72), "Secret content")
    doc.save(
        str(path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="testpass",
        owner_pw="testpass",
    )
    doc.close()
    return path


@pytest.fixture
def not_a_pdf(tmp_path: Path) -> Path:
    """Create a text file with .pdf extension (no %PDF- header)."""
    path = tmp_path / "fake.pdf"
    path.write_text("This is not a PDF file.")
    return path


@pytest.fixture
def corrupt_pdf(tmp_path: Path) -> Path:
    """Create a file with %PDF- header but truncated/corrupt content."""
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"%PDF-1.4\n% corrupt data that cannot be parsed\n%%EOF")
    return path


@pytest.fixture
def nonexistent_pdf(tmp_path: Path) -> Path:
    """Return a path that does not exist."""
    return tmp_path / "does_not_exist.pdf"


@pytest.fixture
def unreadable_pdf(tmp_path: Path) -> Path:
    """Create a valid PDF then remove read permissions."""
    path = tmp_path / "unreadable.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    path.chmod(0o000)
    yield path
    path.chmod(0o644)  # restore for cleanup


@pytest.fixture
def pdf_with_outline(tmp_path: Path) -> Path:
    """Create a PDF with a table of contents / bookmarks."""
    path = tmp_path / "with_outline.pdf"
    doc = pymupdf.open()
    for i in range(5):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Chapter {i + 1}")
    toc = [
        [1, "Chapter 1", 1],
        [2, "Section 1.1", 1],
        [2, "Section 1.2", 2],
        [1, "Chapter 2", 3],
        [1, "Chapter 3", 5],
    ]
    doc.set_toc(toc)
    doc.save(str(path))
    doc.close()
    return path
