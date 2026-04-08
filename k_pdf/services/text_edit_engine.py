"""Text editing engine — PyMuPDF text replacement and font checking.

Handles get_text_block, check_font_support, replace_text,
replace_all, edit_text_inline, and redact_and_overlay.

PyMuPDF import is isolated here per AGPL containment rule.
"""

from __future__ import annotations

import logging
from typing import Any

import pymupdf

from k_pdf.core.text_edit_model import (
    EditResult,
    FontCheckResult,
    ReplaceAllResult,
    TextBlockInfo,
)

logger = logging.getLogger("k_pdf.services.text_edit_engine")


class TextEditEngine:
    """Service for text editing operations on PDF documents."""

    def get_text_block(
        self,
        doc_handle: Any,
        page_index: int,
        x: float,
        y: float,
    ) -> TextBlockInfo | None:
        """Return the text word at the given PDF coordinates.

        Uses get_text("words") for word-level hit detection, then
        get_text("dict") for font information.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            x: X coordinate in PDF page space.
            y: Y coordinate in PDF page space.

        Returns:
            TextBlockInfo with word text, font info, and bounding rect,
            or None if no text at that position.
        """
        page = doc_handle[page_index]

        # Step 1: Find the word at (x, y) using word-level bounding boxes
        words = page.get_text("words")  # (x0, y0, x1, y1, text, block, line, word)
        hit_word = None
        for w in words:
            wx0, wy0, wx1, wy1 = w[0], w[1], w[2], w[3]
            if wx0 <= x <= wx1 and wy0 <= y <= wy1:
                hit_word = w
                break

        if hit_word is None:
            return None

        word_rect = (hit_word[0], hit_word[1], hit_word[2], hit_word[3])
        word_text = hit_word[4]

        # Step 2: Get font info from the dict extraction at the word's midpoint
        mid_x = (word_rect[0] + word_rect[2]) / 2
        mid_y = (word_rect[1] + word_rect[3]) / 2
        font_name = ""
        font_size = 12.0
        is_fully_embedded = True

        data = page.get_text("dict")
        for block in data.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    bbox = span["bbox"]
                    if bbox[0] <= mid_x <= bbox[2] and bbox[1] <= mid_y <= bbox[3]:
                        font_name = span.get("font", "")
                        is_subset = "+" in font_name or "-Subset" in font_name
                        base14 = _is_base14_font(font_name)
                        is_fully_embedded = base14 or (not is_subset)
                        break

        return TextBlockInfo(
            page=page_index,
            rect=word_rect,
            text=word_text,
            font_name=font_name,
            font_size=font_size,
            is_fully_embedded=is_fully_embedded,
        )

    def check_font_support(
        self,
        doc_handle: Any,
        page_index: int,
        text_rect: tuple[float, float, float, float],
    ) -> FontCheckResult:
        """Check whether text at the given rect uses an editable font.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            text_rect: Bounding box (x0, y0, x1, y1) of the text area.

        Returns:
            FontCheckResult indicating whether direct editing is supported.
        """
        page = doc_handle[page_index]
        data = page.get_text("dict")
        x_mid = (text_rect[0] + text_rect[2]) / 2
        y_mid = (text_rect[1] + text_rect[3]) / 2

        for block in data.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    bbox = span["bbox"]
                    if bbox[0] <= x_mid <= bbox[2] and bbox[1] <= y_mid <= bbox[3]:
                        font_name = span.get("font", "unknown")
                        is_subset = "+" in font_name or "-Subset" in font_name
                        base14 = _is_base14_font(font_name)

                        if base14 or not is_subset:
                            return FontCheckResult(
                                supported=True,
                                font_name=font_name,
                                reason="",
                            )
                        return FontCheckResult(
                            supported=False,
                            font_name=font_name,
                            reason=(
                                f"Font '{font_name}' is subset-embedded. "
                                "Only the original characters are available."
                            ),
                        )

        return FontCheckResult(
            supported=False,
            font_name="unknown",
            reason="No text found at the specified location.",
        )

    def replace_text(
        self,
        doc_handle: Any,
        page_index: int,
        search_rect: tuple[float, float, float, float],
        old_text: str,
        new_text: str,
    ) -> bool:
        """Replace text at the given rect using redact-and-overlay.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            search_rect: Bounding rect of the text to replace.
            old_text: The original text (for logging).
            new_text: The replacement text.

        Returns:
            True if replacement succeeded.
        """
        try:
            # Determine font size from the existing text
            block = self.get_text_block(
                doc_handle,
                page_index,
                (search_rect[0] + search_rect[2]) / 2,
                (search_rect[1] + search_rect[3]) / 2,
            )
            font_size = block.font_size if block else 12.0

            self.redact_and_overlay(doc_handle, page_index, search_rect, new_text, font_size)
            logger.debug(
                "Replaced '%s' with '%s' on page %d",
                old_text[:30],
                new_text[:30],
                page_index,
            )
            return True
        except Exception:
            logger.warning("Failed to replace text on page %d", page_index, exc_info=True)
            return False

    def replace_all(
        self,
        doc_handle: Any,
        search_results: dict[int, list[tuple[float, float, float, float]]],
        old_text: str,
        new_text: str,
    ) -> ReplaceAllResult:
        """Bulk replace text across all matched locations.

        Processes pages in reverse order to avoid rect invalidation.

        Args:
            doc_handle: A pymupdf.Document handle.
            search_results: Dict mapping page_index to list of match rects.
            old_text: The search text being replaced.
            new_text: The replacement text.

        Returns:
            ReplaceAllResult with counts and skipped locations.
        """
        replaced = 0
        skipped = 0
        skipped_locs: list[tuple[int, str]] = []

        # Process pages in reverse order (highest first) to avoid
        # coordinate shifts from redactions affecting subsequent pages
        for page_idx in sorted(search_results.keys(), reverse=True):
            rects = search_results[page_idx]
            # Process rects in reverse order within each page
            for rect in reversed(rects):
                font_check = self.check_font_support(doc_handle, page_idx, rect)
                if not font_check.supported:
                    skipped += 1
                    skipped_locs.append((page_idx, font_check.reason))
                    continue

                success = self.replace_text(doc_handle, page_idx, rect, old_text, new_text)
                if success:
                    replaced += 1
                else:
                    skipped += 1
                    skipped_locs.append((page_idx, "Replacement failed"))

        return ReplaceAllResult(
            replaced_count=replaced,
            skipped_count=skipped,
            skipped_locations=skipped_locs,
        )

    def edit_text_inline(
        self,
        doc_handle: Any,
        page_index: int,
        block_rect: tuple[float, float, float, float],
        old_text: str,
        new_text: str,
    ) -> EditResult:
        """Attempt direct text edit at the given block rect.

        Checks font support first. If supported, replaces via
        redact-and-overlay. If not, returns failure with reason.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            block_rect: Bounding rect of the text block.
            old_text: Original text content.
            new_text: New text content.

        Returns:
            EditResult indicating success or failure with reason.
        """
        font_check = self.check_font_support(doc_handle, page_index, block_rect)
        if not font_check.supported:
            return EditResult(success=False, error_message=font_check.reason)

        success = self.replace_text(doc_handle, page_index, block_rect, old_text, new_text)
        if success:
            return EditResult(success=True, error_message="")
        return EditResult(success=False, error_message="Text replacement failed unexpectedly.")

    def redact_and_overlay(
        self,
        doc_handle: Any,
        page_index: int,
        block_rect: tuple[float, float, float, float],
        new_text: str,
        font_size: float,
    ) -> None:
        """Redact original text area and insert new text using Helvetica.

        This is the fallback editing method that works with any font.
        The redaction permanently removes content from the content stream.

        Args:
            doc_handle: A pymupdf.Document handle.
            page_index: Zero-based page index.
            block_rect: Area to redact (x0, y0, x1, y1).
            new_text: Text to insert after redaction.
            font_size: Font size for the overlay text.
        """
        page = doc_handle[page_index]
        rect = pymupdf.Rect(*block_rect)

        # Step 1: Add redaction annotation with white fill
        page.add_redact_annot(rect, fill=(1, 1, 1))

        # Step 2: Apply redaction (permanently removes content)
        page.apply_redactions()

        # Step 3: Insert new text at the same position using Helvetica
        # Position at bottom-left of the rect, adjusted for font baseline
        insert_point = pymupdf.Point(rect.x0, rect.y0 + font_size)
        page.insert_text(
            insert_point,
            new_text,
            fontname="helv",
            fontsize=font_size,
        )

        logger.debug(
            "Redact-and-overlay on page %d: inserted '%s' at %s",
            page_index,
            new_text[:30],
            block_rect,
        )


def _is_base14_font(font_name: str) -> bool:
    """Check if a font name is one of the PDF base-14 fonts.

    Args:
        font_name: The font name string from PyMuPDF.

    Returns:
        True if this is a base-14 (always available) font.
    """
    base14 = {
        "Courier",
        "Courier-Bold",
        "Courier-Oblique",
        "Courier-BoldOblique",
        "Helvetica",
        "Helvetica-Bold",
        "Helvetica-Oblique",
        "Helvetica-BoldOblique",
        "Times-Roman",
        "Times-Bold",
        "Times-Italic",
        "Times-BoldItalic",
        "Symbol",
        "ZapfDingbats",
        # PyMuPDF internal names
        "helv",
        "heit",
        "cour",
        "cobo",
        "cobi",
        "coit",
        "hebo",
        "hebi",
        "tiro",
        "tibo",
        "tibi",
        "tiit",
        "symb",
        "zadb",
    }
    return font_name in base14
