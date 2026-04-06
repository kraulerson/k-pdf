"""Data models for text editing operations.

Pure dataclasses with no Qt or PyMuPDF imports.
Used by TextEditEngine and TextEditPresenter to represent
text blocks, font checks, edit results, and bulk replace operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TextBlockInfo:
    """Information about a text span at a PDF location.

    Attributes:
        page: Zero-based page index.
        rect: Bounding rectangle in PDF coordinates (x0, y0, x1, y1).
        text: The extracted text content.
        font_name: Name of the font used for this text span.
        font_size: Font size in points.
        is_fully_embedded: Whether the font is fully embedded (supports direct editing).
    """

    page: int
    rect: tuple[float, float, float, float]
    text: str
    font_name: str
    font_size: float
    is_fully_embedded: bool


@dataclass(frozen=True)
class FontCheckResult:
    """Result of checking whether a text region supports direct editing.

    Attributes:
        supported: Whether the text region can be directly edited.
        font_name: Name of the font being checked.
        reason: Human-readable explanation if not supported (e.g., "Font is subset-embedded").
    """

    supported: bool
    font_name: str
    reason: str


@dataclass(frozen=True)
class EditResult:
    """Result of an inline text edit attempt.

    Attributes:
        success: Whether the edit succeeded.
        error_message: Error description if success is False; empty string if successful.
    """

    success: bool
    error_message: str


@dataclass
class ReplaceAllResult:
    """Result of a bulk find-and-replace operation.

    Attributes:
        replaced_count: Number of text regions successfully replaced.
        skipped_count: Number of text regions skipped (e.g., due to font limitations).
        skipped_locations: List of (page_index, reason) tuples for each skipped location.
    """

    replaced_count: int
    skipped_count: int
    skipped_locations: list[tuple[int, str]] = field(default_factory=list)
