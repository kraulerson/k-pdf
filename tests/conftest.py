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
def searchable_pdf(tmp_path: Path) -> Path:
    """Create a 3-page PDF with known searchable text."""
    path = tmp_path / "searchable.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1} content")
        page.insert_text(pymupdf.Point(72, 120), "Hello world")
        if i == 1:
            page.insert_text(pymupdf.Point(72, 168), "Hello world again")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def image_only_pdf(tmp_path: Path) -> Path:
    """Create a PDF with only image content (no text layer)."""
    path = tmp_path / "image_only.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    # Insert a small colored rectangle as an "image"
    rect = pymupdf.Rect(72, 72, 200, 200)
    page.draw_rect(rect, color=(1, 0, 0), fill=(0.8, 0.8, 0.8))
    doc.save(str(path))
    doc.close()
    return path


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


@pytest.fixture
def annotatable_pdf(tmp_path: Path) -> Path:
    """Create a 2-page PDF with selectable text suitable for annotation tests."""
    path = tmp_path / "annotatable.pdf"
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1} first line of text")
        page.insert_text(pymupdf.Point(72, 100), f"Page {i + 1} second line of text")
        page.insert_text(pymupdf.Point(72, 128), f"Page {i + 1} third line of text")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def form_pdf(tmp_path: Path) -> Path:
    """Create a PDF with AcroForm text, checkbox, and dropdown fields."""
    path = tmp_path / "form.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(pymupdf.Point(72, 50), "Form Test Document")

    # Text field
    widget = pymupdf.Widget()
    widget.field_name = "full_name"
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.rect = pymupdf.Rect(72, 100, 300, 120)
    widget.field_value = ""
    page.add_widget(widget)

    # Checkbox
    widget2 = pymupdf.Widget()
    widget2.field_name = "agree"
    widget2.field_type = pymupdf.PDF_WIDGET_TYPE_CHECKBOX
    widget2.rect = pymupdf.Rect(72, 140, 92, 160)
    widget2.field_value = "Off"
    page.add_widget(widget2)

    # Dropdown / Choice
    widget3 = pymupdf.Widget()
    widget3.field_name = "country"
    widget3.field_type = pymupdf.PDF_WIDGET_TYPE_COMBOBOX
    widget3.rect = pymupdf.Rect(72, 180, 300, 200)
    widget3.choice_values = ["USA", "Canada", "Mexico"]
    widget3.field_value = "USA"
    page.add_widget(widget3)

    doc.save(str(path))
    doc.close()
    return path
