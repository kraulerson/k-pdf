"""Tests for AnnotationEngine — uses real PDFs via PyMuPDF."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from k_pdf.services.annotation_engine import AnnotationEngine


class TestGetTextWords:
    def test_returns_words_for_text_page(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        assert len(words) > 0
        # Each word tuple: (x0, y0, x1, y1, word, block_no, line_no, word_no)
        assert len(words[0]) == 8
        doc.close()

    def test_returns_empty_for_image_only_page(self, image_only_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(image_only_pdf))
        words = engine.get_text_words(doc, 0)
        assert words == []
        doc.close()


class TestAddHighlight:
    def test_creates_highlight_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        assert len(words) > 0
        # Use the first word's rect as a quad
        w = words[0]
        quads = [pymupdf.Rect(w[0], w[1], w[2], w[3]).quad]
        annot = engine.add_highlight(doc, 0, quads, (1.0, 1.0, 0.0))
        assert annot is not None
        # Verify annotation exists on page
        page = doc[0]
        annots = list(page.annots())
        assert len(annots) == 1
        doc.close()

    def test_highlight_has_correct_color(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        w = words[0]
        quads = [pymupdf.Rect(w[0], w[1], w[2], w[3]).quad]
        annot = engine.add_highlight(doc, 0, quads, (0.0, 0.8, 0.0))
        colors = annot.colors
        # Stroke color for highlights
        assert colors["stroke"] is not None
        stroke = tuple(round(c, 1) for c in colors["stroke"])
        assert stroke == (0.0, 0.8, 0.0)
        doc.close()


class TestAddUnderline:
    def test_creates_underline_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        w = words[0]
        quads = [pymupdf.Rect(w[0], w[1], w[2], w[3]).quad]
        annot = engine.add_underline(doc, 0, quads, (1.0, 0.0, 0.0))
        assert annot is not None
        page = doc[0]
        annots = list(page.annots())
        assert len(annots) == 1
        doc.close()


class TestAddStrikeout:
    def test_creates_strikeout_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        w = words[0]
        quads = [pymupdf.Rect(w[0], w[1], w[2], w[3]).quad]
        annot = engine.add_strikeout(doc, 0, quads, (1.0, 0.0, 0.0))
        assert annot is not None
        page = doc[0]
        annots = list(page.annots())
        assert len(annots) == 1
        doc.close()


class TestDeleteAnnotation:
    def test_removes_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        w = words[0]
        quads = [pymupdf.Rect(w[0], w[1], w[2], w[3]).quad]
        annot = engine.add_highlight(doc, 0, quads, (1.0, 1.0, 0.0))
        # Verify it exists
        page = doc[0]
        assert len(list(page.annots())) == 1
        # Delete it
        engine.delete_annotation(doc, 0, annot)
        assert len(list(page.annots())) == 0
        doc.close()


class TestGetAnnotations:
    def test_returns_empty_for_unannotated_page(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annots = engine.get_annotations(doc, 0)
        assert annots == []
        doc.close()

    def test_returns_annotations_after_adding(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        w = words[0]
        quads = [pymupdf.Rect(w[0], w[1], w[2], w[3]).quad]
        engine.add_highlight(doc, 0, quads, (1.0, 1.0, 0.0))
        engine.add_underline(doc, 0, quads, (1.0, 0.0, 0.0))
        annots = engine.get_annotations(doc, 0)
        assert len(annots) == 2
        doc.close()


class TestRectsToQuads:
    def test_converts_rects_to_quads(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
        quads = engine.rects_to_quads(rects)
        assert len(quads) == 2
        # Each quad should be a pymupdf.Quad object
        for q in quads:
            assert hasattr(q, "ul")  # Quad has corner attributes
        doc.close()

    def test_empty_rects_returns_empty(self) -> None:
        engine = AnnotationEngine()
        quads = engine.rects_to_quads([])
        assert quads == []

    def test_quads_usable_for_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        rects = [(w[0], w[1], w[2], w[3]) for w in words[:1]]
        quads = engine.rects_to_quads(rects)
        # Should be usable to create an annotation without error
        annot = engine.add_highlight(doc, 0, quads, (1.0, 1.0, 0.0))
        assert annot is not None
        doc.close()
