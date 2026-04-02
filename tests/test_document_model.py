"""Tests for core data classes."""

from __future__ import annotations

from pathlib import Path

from k_pdf.core.document_model import DocumentMetadata, PageInfo


def test_document_metadata_construction() -> None:
    meta = DocumentMetadata(
        file_path=Path("/tmp/test.pdf"),
        page_count=5,
        title="Test Doc",
        author="Author",
        has_forms=False,
        has_outline=True,
        has_javascript=False,
        is_encrypted=False,
        file_size_bytes=1024,
    )
    assert meta.page_count == 5
    assert meta.title == "Test Doc"
    assert meta.has_outline is True


def test_page_info_construction() -> None:
    page = PageInfo(
        index=0,
        width=612.0,
        height=792.0,
        rotation=0,
        has_text=True,
        annotation_count=0,
    )
    assert page.index == 0
    assert page.width == 612.0
    assert page.rotation == 0
