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


class TestAddStickyNote:
    def test_creates_text_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annot = engine.add_sticky_note(doc, 0, (100.0, 100.0), "Test note")
        assert annot is not None
        page = doc[0]
        annots = list(page.annots())
        assert len(annots) == 1
        doc.close()

    def test_sticky_note_has_content(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        engine.add_sticky_note(doc, 0, (100.0, 100.0), "My note content")
        content = engine.get_annotation_content(doc, 0, next(iter(doc[0].annots())))
        assert content == "My note content"
        doc.close()

    def test_sticky_note_with_author(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annot = engine.add_sticky_note(doc, 0, (100.0, 100.0), "Note", author="Karl")
        info = annot.info
        assert info["title"] == "Karl"
        doc.close()


class TestAddTextBox:
    def test_creates_freetext_annotation(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annot = engine.add_text_box(doc, 0, (100.0, 200.0, 300.0, 250.0), "Box content")
        assert annot is not None
        page = doc[0]
        annots = list(page.annots())
        assert len(annots) == 1
        doc.close()

    def test_text_box_has_correct_rect(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annot = engine.add_text_box(doc, 0, (100.0, 200.0, 300.0, 250.0), "Content")
        # Access rect from the returned annot directly (avoids stale ref segfault)
        r = annot.rect
        assert abs(r.x0 - 100.0) < 1.0
        assert abs(r.y0 - 200.0) < 1.0
        doc.close()


class TestUpdateAnnotationContent:
    def test_updates_sticky_note_content(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        engine.add_sticky_note(doc, 0, (100.0, 100.0), "Original")
        annot = next(iter(doc[0].annots()))
        engine.update_annotation_content(doc, 0, annot, "Updated")
        refreshed = next(iter(doc[0].annots()))
        content = engine.get_annotation_content(doc, 0, refreshed)
        assert content == "Updated"
        doc.close()


class TestGetAnnotationContent:
    def test_reads_content_from_sticky_note(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        engine.add_sticky_note(doc, 0, (100.0, 100.0), "Read me")
        annot = next(iter(doc[0].annots()))
        content = engine.get_annotation_content(doc, 0, annot)
        assert content == "Read me"
        doc.close()

    def test_empty_content_returns_empty_string(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        engine.add_sticky_note(doc, 0, (100.0, 100.0), "")
        annot = next(iter(doc[0].annots()))
        content = engine.get_annotation_content(doc, 0, annot)
        assert content == ""
        doc.close()


class TestGetAnnotationInfo:
    def test_highlight_info(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        page = doc[0]
        words = page.get_text("words")
        quads = [pymupdf.Rect(*w[:4]).quad for w in words[:2]]
        annot = page.add_highlight_annot(quads=quads)
        annot.set_colors(stroke=(1.0, 1.0, 0.0))
        annot.set_info(title="TestAuthor")
        annot.update()
        info = engine.get_annotation_info(doc, 0, annot)
        assert info["type_name"] == "Highlight"
        assert info["author"] == "TestAuthor"
        assert info["color"] is not None
        doc.close()

    def test_underline_info(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        page = doc[0]
        words = page.get_text("words")
        quads = [pymupdf.Rect(*w[:4]).quad for w in words[:2]]
        annot = page.add_underline_annot(quads=quads)
        annot.update()
        info = engine.get_annotation_info(doc, 0, annot)
        assert info["type_name"] == "Underline"
        doc.close()

    def test_strikeout_info(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        page = doc[0]
        words = page.get_text("words")
        quads = [pymupdf.Rect(*w[:4]).quad for w in words[:2]]
        annot = page.add_strikeout_annot(quads=quads)
        annot.update()
        info = engine.get_annotation_info(doc, 0, annot)
        assert info["type_name"] == "Strikethrough"
        doc.close()

    def test_sticky_note_info(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annot = doc[0].add_text_annot((72, 72), "Test note", icon="Note")
        annot.set_info(title="NoteAuthor")
        annot.update()
        info = engine.get_annotation_info(doc, 0, annot)
        assert info["type_name"] == "Note"
        assert info["content"] == "Test note"
        assert info["author"] == "NoteAuthor"
        doc.close()

    def test_freetext_info(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annot = doc[0].add_freetext_annot((72, 200, 300, 240), "Box text", fontsize=11)
        info = engine.get_annotation_info(doc, 0, annot)
        assert info["type_name"] == "Text Box"
        assert info["content"] == "Box text"
        doc.close()

    def test_info_has_rect(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        annot = doc[0].add_text_annot((72, 72), "Note")
        info = engine.get_annotation_info(doc, 0, annot)
        assert "rect" in info
        assert len(info["rect"]) == 4
        doc.close()


class TestExtractTextInRects:
    def test_extracts_single_word(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        # Use the bounding box of the first word
        first_word_rect = [(words[0][0], words[0][1], words[0][2], words[0][3])]
        text = engine.extract_text_in_rects(doc, 0, first_word_rect)
        assert text == words[0][4]
        doc.close()

    def test_extracts_multiple_words_reading_order(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        # Select all words on the first block (first visual line)
        first_block = words[0][5]
        block0_words = [w for w in words if w[5] == first_block]
        rects = [(w[0], w[1], w[2], w[3]) for w in block0_words]
        text = engine.extract_text_in_rects(doc, 0, rects)
        expected = " ".join(w[4] for w in block0_words)
        assert text == expected
        doc.close()

    def test_returns_empty_for_image_only_page(self, image_only_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(image_only_pdf))
        text = engine.extract_text_in_rects(doc, 0, [(0, 0, 1000, 1000)])
        assert text == ""
        doc.close()

    def test_returns_empty_for_empty_rects(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        text = engine.extract_text_in_rects(doc, 0, [])
        assert text == ""
        doc.close()

    def test_multiline_selection_preserves_lines(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        # Words from insert_text have different block_no for each line
        block_nos = sorted({w[5] for w in words})
        assert len(block_nos) >= 2, "Need at least 2 blocks for this test"
        # Select all words on the first two blocks (visual lines)
        two_block_words = [w for w in words if w[5] in (block_nos[0], block_nos[1])]
        rects = [(w[0], w[1], w[2], w[3]) for w in two_block_words]
        text = engine.extract_text_in_rects(doc, 0, rects)
        assert "\n" in text
        doc.close()

    def test_all_words_on_page(self, annotatable_pdf: Path) -> None:
        engine = AnnotationEngine()
        doc = pymupdf.open(str(annotatable_pdf))
        words = engine.get_text_words(doc, 0)
        # Select with a huge bounding box that covers everything
        rects = [(0, 0, 1000, 1000)]
        text = engine.extract_text_in_rects(doc, 0, rects)
        # Should contain all words
        for w in words:
            assert w[4] in text
        doc.close()
