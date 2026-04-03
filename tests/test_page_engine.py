"""Tests for PageEngine — page manipulation via PyMuPDF."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from k_pdf.core.page_model import PageOperation
from k_pdf.services.page_engine import PageEngine


@pytest.fixture
def multi_page_pdf(tmp_path: Path) -> Path:
    """Create a 5-page PDF with identifiable text on each page."""
    path = tmp_path / "multi.pdf"
    doc = pymupdf.open()
    for i in range(5):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Page {i + 1} content")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def single_page_pdf(tmp_path: Path) -> Path:
    """Create a 1-page PDF."""
    path = tmp_path / "single.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(pymupdf.Point(72, 72), "Only page")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def source_pdf(tmp_path: Path) -> Path:
    """Create a 2-page PDF to insert from."""
    path = tmp_path / "source.pdf"
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Source page {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


class TestPageEngineDeletePages:
    def test_delete_single_page(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.delete_pages(doc, [2])
        assert result.success is True
        assert result.operation == PageOperation.DELETE
        assert result.new_page_count == 4
        assert doc.page_count == 4
        doc.close()

    def test_delete_multiple_pages(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.delete_pages(doc, [0, 2, 4])
        assert result.success is True
        assert result.new_page_count == 2
        doc.close()

    def test_delete_all_pages_blocked(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.delete_pages(doc, [0, 1, 2, 3, 4])
        assert result.success is False
        assert "at least one page" in result.error_message.lower()
        assert doc.page_count == 5  # unchanged
        doc.close()

    def test_delete_single_page_doc_blocked(self, single_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(single_page_pdf))
        result = engine.delete_pages(doc, [0])
        assert result.success is False
        assert doc.page_count == 1
        doc.close()

    def test_delete_returns_affected_pages(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.delete_pages(doc, [1, 3])
        assert result.affected_pages == [1, 3]
        doc.close()


class TestPageEngineMovePage:
    def test_move_page_forward(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        text_before = doc[0].get_text("text").strip()
        # move_page(0, 3) moves page 0 to before position 3 -> ends up at index 2
        result = engine.move_page(doc, 0, 3)
        assert result.success is True
        assert result.operation == PageOperation.MOVE
        assert doc[2].get_text("text").strip() == text_before
        doc.close()

    def test_move_page_backward(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        text_before = doc[3].get_text("text").strip()
        # move_page(3, 1) moves page 3 to before position 1 -> ends up at index 1
        result = engine.move_page(doc, 3, 1)
        assert result.success is True
        assert doc[1].get_text("text").strip() == text_before
        doc.close()

    def test_move_page_same_position(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.move_page(doc, 2, 2)
        assert result.success is True
        assert result.new_page_count == 5
        doc.close()


class TestPageEngineRotatePages:
    def test_rotate_single_page_90(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        original = doc[0].rotation
        result = engine.rotate_pages(doc, [0], 90)
        assert result.success is True
        assert result.operation == PageOperation.ROTATE
        assert doc[0].rotation == (original + 90) % 360
        doc.close()

    def test_rotate_multiple_pages(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.rotate_pages(doc, [0, 1, 2], 90)
        assert result.success is True
        assert result.affected_pages == [0, 1, 2]
        for i in [0, 1, 2]:
            assert doc[i].rotation == 90
        doc.close()

    def test_rotate_270(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.rotate_pages(doc, [0], 270)
        assert result.success is True
        assert doc[0].rotation == 270
        doc.close()

    def test_rotate_180(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.rotate_pages(doc, [0], 180)
        assert result.success is True
        assert doc[0].rotation == 180
        doc.close()

    def test_rotate_invalid_angle(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.rotate_pages(doc, [0], 45)
        assert result.success is False
        assert "angle" in result.error_message.lower()
        doc.close()


class TestPageEngineInsertPages:
    def test_insert_at_end(self, multi_page_pdf: Path, source_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.insert_pages_from(doc, source_pdf, 5)
        assert result.success is True
        assert result.operation == PageOperation.INSERT
        assert result.new_page_count == 7
        assert doc.page_count == 7
        doc.close()

    def test_insert_at_beginning(self, multi_page_pdf: Path, source_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.insert_pages_from(doc, source_pdf, 0)
        assert result.success is True
        assert result.new_page_count == 7
        # Source pages should be at position 0 and 1
        text_p0 = doc[0].get_text("text").strip()
        assert "Source" in text_p0
        doc.close()

    def test_insert_at_middle(self, multi_page_pdf: Path, source_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.insert_pages_from(doc, source_pdf, 2)
        assert result.success is True
        assert result.new_page_count == 7
        doc.close()

    def test_insert_from_invalid_path(self, multi_page_pdf: Path, tmp_path: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        bad_path = tmp_path / "nonexistent.pdf"
        result = engine.insert_pages_from(doc, bad_path, 0)
        assert result.success is False
        assert result.new_page_count == 5  # unchanged
        doc.close()

    def test_insert_affected_pages(self, multi_page_pdf: Path, source_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        result = engine.insert_pages_from(doc, source_pdf, 2)
        assert result.affected_pages == [2, 3]
        doc.close()


class TestPageEngineGetPageCount:
    def test_get_page_count(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        assert engine.get_page_count(doc) == 5
        doc.close()

    def test_get_page_count_after_delete(self, multi_page_pdf: Path) -> None:
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        engine.delete_pages(doc, [0])
        assert engine.get_page_count(doc) == 4
        doc.close()


class TestPageEngineRenderThumbnail:
    def test_render_thumbnail_returns_pixmap(self, multi_page_pdf: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        pixmap = engine.render_thumbnail(doc, 0, width=150)
        assert pixmap is not None
        assert not pixmap.isNull()
        assert pixmap.width() == 150
        doc.close()

    def test_render_thumbnail_correct_aspect(self, multi_page_pdf: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
        engine = PageEngine()
        doc = pymupdf.open(str(multi_page_pdf))
        pixmap = engine.render_thumbnail(doc, 0, width=150)
        # US Letter: 612x792 -> aspect ~0.77 -> height ~194 for width 150
        assert pixmap.height() > pixmap.width()
        doc.close()
