"""Create, modify, delete annotations.

PyMuPDF annotation operations isolated here per AGPL containment rule.
No other layer imports fitz/pymupdf directly for annotations.
"""

from __future__ import annotations

import logging
from typing import Any

import pymupdf

logger = logging.getLogger("k_pdf.services.annotation_engine")


class AnnotationEngine:
    """Wraps PyMuPDF annotation creation, deletion, and query operations.

    All methods take a doc_handle (pymupdf.Document) and page_index.
    The caller (AnnotationPresenter) never imports pymupdf directly.
    """

    def get_text_words(self, doc_handle: Any, page_index: int) -> list[tuple[Any, ...]]:
        """Return word rectangles for text selection hit-testing.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.

        Returns:
            List of (x0, y0, x1, y1, word, block_no, line_no, word_no) tuples.
            Empty list if the page has no text layer.
        """
        page = doc_handle[page_index]
        words: list[tuple[Any, ...]] = page.get_text("words")
        return words

    def add_highlight(
        self,
        doc_handle: Any,
        page_index: int,
        quads: list[Any],
        color: tuple[float, float, float],
    ) -> Any:
        """Add a highlight annotation to a page.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            quads: Quad-point coordinates defining the region.
            color: RGB color as 0.0-1.0 floats.

        Returns:
            The created pymupdf.Annot object.
        """
        page = doc_handle[page_index]
        annot = page.add_highlight_annot(quads=quads)
        annot.set_colors(stroke=color)
        annot.update()
        logger.debug("Added highlight on page %d with color %s", page_index, color)
        return annot

    def add_underline(
        self,
        doc_handle: Any,
        page_index: int,
        quads: list[Any],
        color: tuple[float, float, float],
    ) -> Any:
        """Add an underline annotation to a page.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            quads: Quad-point coordinates defining the region.
            color: RGB color as 0.0-1.0 floats.

        Returns:
            The created pymupdf.Annot object.
        """
        page = doc_handle[page_index]
        annot = page.add_underline_annot(quads=quads)
        annot.set_colors(stroke=color)
        annot.update()
        logger.debug("Added underline on page %d with color %s", page_index, color)
        return annot

    def add_strikeout(
        self,
        doc_handle: Any,
        page_index: int,
        quads: list[Any],
        color: tuple[float, float, float],
    ) -> Any:
        """Add a strikethrough annotation to a page.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            quads: Quad-point coordinates defining the region.
            color: RGB color as 0.0-1.0 floats.

        Returns:
            The created pymupdf.Annot object.
        """
        page = doc_handle[page_index]
        annot = page.add_strikeout_annot(quads=quads)
        annot.set_colors(stroke=color)
        annot.update()
        logger.debug("Added strikeout on page %d with color %s", page_index, color)
        return annot

    def delete_annotation(
        self,
        doc_handle: Any,
        page_index: int,
        annot: Any,
    ) -> None:
        """Delete an annotation from a page.

        Re-fetches the annotation from the page by xref to avoid
        PyMuPDF stale-reference errors when the original page object
        that created the annotation has been garbage-collected.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            annot: The pymupdf.Annot object to delete (used for xref lookup).
        """
        page = doc_handle[page_index]
        target_xref = annot.xref
        for page_annot in page.annots():
            if page_annot.xref == target_xref:
                page.delete_annot(page_annot)
                logger.debug("Deleted annotation xref=%d on page %d", target_xref, page_index)
                return
        logger.warning("Annotation xref=%d not found on page %d", target_xref, page_index)

    def get_annotations(self, doc_handle: Any, page_index: int) -> list[Any]:
        """Return all annotations on a page.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.

        Returns:
            List of pymupdf.Annot objects. Empty list if none.
        """
        page = doc_handle[page_index]
        return list(page.annots())

    def add_sticky_note(
        self,
        doc_handle: Any,
        page_index: int,
        point: tuple[float, float],
        content: str,
        author: str = "",
    ) -> Any:
        """Add a sticky note annotation at a point on a page.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            point: (x, y) position in PDF coordinates.
            content: Text content for the note.
            author: Optional author name.

        Returns:
            The created pymupdf.Annot object.
        """
        page = doc_handle[page_index]
        annot = page.add_text_annot(point, content, icon="Note")
        if author:
            annot.set_info(title=author)
            annot.update()
        logger.debug("Added sticky note on page %d at %s", page_index, point)
        return annot

    def add_text_box(
        self,
        doc_handle: Any,
        page_index: int,
        rect: tuple[float, float, float, float],
        content: str,
        color: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> Any:
        """Add a free-text box annotation on a page.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            rect: (x0, y0, x1, y1) bounding rectangle.
            content: Text content for the box.
            color: Text color as RGB 0.0-1.0 floats.

        Returns:
            The created pymupdf.Annot object.
        """
        page = doc_handle[page_index]
        annot = page.add_freetext_annot(
            rect,
            content,
            fontsize=11,
            fontname="helv",
            text_color=color,
        )
        logger.debug("Added text box on page %d at rect %s", page_index, rect)
        return annot

    def update_annotation_content(
        self,
        doc_handle: Any,
        page_index: int,
        annot: Any,
        content: str,
    ) -> None:
        """Update the text content of an existing annotation.

        Re-fetches the annotation from the page by xref to avoid
        stale-reference errors, similar to delete_annotation.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            annot: The pymupdf.Annot to update (used for xref lookup).
            content: New text content.
        """
        page = doc_handle[page_index]
        target_xref = annot.xref
        for page_annot in page.annots():
            if page_annot.xref == target_xref:
                page_annot.set_info(content=content)
                page_annot.update()
                logger.debug("Updated annotation content on page %d", page_index)
                return
        logger.warning(
            "Annotation xref=%d not found on page %d for update", target_xref, page_index
        )

    def get_annotation_content(
        self,
        doc_handle: Any,
        page_index: int,
        annot: Any,
    ) -> str:
        """Read text content from an annotation.

        Re-fetches the annotation from the page by xref to avoid
        stale-reference errors.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            annot: The pymupdf.Annot to read (used for xref lookup).

        Returns:
            The annotation's text content, or empty string.
        """
        page = doc_handle[page_index]
        target_xref = annot.xref
        for page_annot in page.annots():
            if page_annot.xref == target_xref:
                info = page_annot.info
                return str(info.get("content", ""))
        return ""

    def get_annotation_type(
        self,
        doc_handle: Any,
        page_index: int,
        annot: Any,
    ) -> tuple[int, str]:
        """Get the type of an annotation as (type_code, type_name).

        Re-fetches the annotation from the page by xref to avoid
        stale-reference errors.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            annot: The pymupdf.Annot (used for xref lookup).

        Returns:
            Tuple of (type_code, type_name). Returns (0, "Text") for sticky notes,
            (2, "FreeText") for text boxes, etc.
        """
        page = doc_handle[page_index]
        target_xref = annot.xref
        for page_annot in page.annots():
            if page_annot.xref == target_xref:
                return page_annot.type  # type: ignore[no-any-return]
        return (0, "Text")

    def rects_to_quads(self, rects: list[tuple[float, float, float, float]]) -> list[Any]:
        """Convert word bounding-box rectangles to quad points.

        Used by AnnotationPresenter to convert viewport selection rects
        (plain tuples) into pymupdf Quad objects, keeping pymupdf isolated
        to the services layer.

        Args:
            rects: List of (x0, y0, x1, y1) bounding boxes.

        Returns:
            List of pymupdf.Quad objects suitable for annotation creation.
        """
        quads = []
        for x0, y0, x1, y1 in rects:
            quads.append(pymupdf.Rect(x0, y0, x1, y1).quad)
        return quads
