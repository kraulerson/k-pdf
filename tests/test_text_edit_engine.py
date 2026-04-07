"""Tests for TextEditEngine service."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from k_pdf.services.text_edit_engine import TextEditEngine


@pytest.fixture
def engine() -> TextEditEngine:
    """Return a fresh TextEditEngine instance."""
    return TextEditEngine()


@pytest.fixture
def text_pdf(tmp_path: Path) -> Path:
    """Create a PDF with known text content using a standard font."""
    path = tmp_path / "text.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    # Insert text with a standard (fully available) font
    page.insert_text(
        pymupdf.Point(72, 100),
        "Hello World",
        fontname="helv",
        fontsize=12,
    )
    page.insert_text(
        pymupdf.Point(72, 140),
        "Goodbye World",
        fontname="helv",
        fontsize=12,
    )
    doc.save(str(path))
    doc.close()
    return path


class TestGetTextBlock:
    def test_returns_block_at_text_position(self, engine: TextEditEngine, text_pdf: Path) -> None:
        doc = pymupdf.open(str(text_pdf))
        # Use x=85.0 to reliably hit the "Hello" word (bbox ~72..99)
        block = engine.get_text_block(doc, 0, 85.0, 95.0)
        assert block is not None
        assert block.text == "Hello"
        assert block.font_name != ""
        assert block.font_size > 0
        doc.close()

    def test_returns_word_not_full_line(self, engine: TextEditEngine, text_pdf: Path) -> None:
        doc = pymupdf.open(str(text_pdf))
        block = engine.get_text_block(doc, 0, 85.0, 95.0)
        assert block is not None
        # Should return a single word, not the entire line
        assert " " not in block.text.strip() or len(block.text.split()) == 1
        doc.close()

    def test_returns_none_at_empty_position(self, engine: TextEditEngine, text_pdf: Path) -> None:
        doc = pymupdf.open(str(text_pdf))
        block = engine.get_text_block(doc, 0, 500.0, 500.0)
        assert block is None
        doc.close()

    def test_returns_page_index(self, engine: TextEditEngine, text_pdf: Path) -> None:
        doc = pymupdf.open(str(text_pdf))
        block = engine.get_text_block(doc, 0, 85.0, 95.0)
        assert block is not None
        assert block.page == 0
        doc.close()


class TestCheckFontSupport:
    def test_standard_font_not_embedded(self, engine: TextEditEngine, text_pdf: Path) -> None:
        doc = pymupdf.open(str(text_pdf))
        block = engine.get_text_block(doc, 0, 85.0, 95.0)
        assert block is not None
        result = engine.check_font_support(doc, 0, block.rect)
        # Standard fonts (helv) are not embedded in the PDF — they're built-in
        # The check should report the font name regardless
        assert result.font_name != ""
        doc.close()


class TestRedactAndOverlay:
    def test_replaces_text_via_redaction(self, engine: TextEditEngine, text_pdf: Path) -> None:
        doc = pymupdf.open(str(text_pdf))
        block = engine.get_text_block(doc, 0, 85.0, 95.0)
        assert block is not None

        engine.redact_and_overlay(doc, 0, block.rect, "New Text", block.font_size)

        # Verify new text is present
        page = doc[0]
        page_text = page.get_text("text")
        assert "New Text" in page_text
        doc.close()

    def test_redact_preserves_other_text(self, engine: TextEditEngine, text_pdf: Path) -> None:
        doc = pymupdf.open(str(text_pdf))
        block = engine.get_text_block(doc, 0, 85.0, 95.0)
        assert block is not None

        engine.redact_and_overlay(doc, 0, block.rect, "Replaced", block.font_size)

        page = doc[0]
        page_text = page.get_text("text")
        assert "Goodbye" in page_text
        doc.close()


class TestReplaceText:
    def test_replace_returns_result(self, engine: TextEditEngine, text_pdf: Path) -> None:
        doc = pymupdf.open(str(text_pdf))
        # Use search_for to get the exact rect
        page = doc[0]
        rects = page.search_for("Hello World")
        assert len(rects) > 0
        search_rect = (rects[0].x0, rects[0].y0, rects[0].x1, rects[0].y1)

        result = engine.replace_text(doc, 0, search_rect, "Hello World", "Hi Earth")
        # replace_text uses redact_and_overlay as the implementation
        assert result is True
        doc.close()


class TestReplaceAll:
    def test_replace_all_multiple_matches(self, engine: TextEditEngine, text_pdf: Path) -> None:
        doc = pymupdf.open(str(text_pdf))
        page = doc[0]
        rects = page.search_for("World")
        search_results = {0: [(r.x0, r.y0, r.x1, r.y1) for r in rects]}

        result = engine.replace_all(doc, search_results, "World", "Earth")
        assert result.replaced_count == len(rects)
        assert result.skipped_count == 0
        doc.close()
