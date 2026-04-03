"""Annotation data model.

Framework-free data layer for annotation type and annotation metadata.
Used by AnnotationPresenter and AnnotationEngine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum


class ToolMode(IntEnum):
    """Active tool mode for viewport interaction."""

    NONE = 0
    TEXT_SELECT = 1
    STICKY_NOTE = 2
    TEXT_BOX = 3


class AnnotationType(Enum):
    """Text markup and note annotation types."""

    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    STICKY_NOTE = "sticky_note"
    TEXT_BOX = "text_box"


@dataclass
class AnnotationData:
    """Metadata for a single annotation.

    Attributes:
        type: The annotation kind.
        page: Zero-based page index.
        quads: Quad-point coordinates defining the annotated region.
        color: RGB color as 0.0-1.0 floats.
        author: Author name (optional metadata).
        created_at: Creation timestamp.
        content: Text content for sticky notes and text boxes.
        rect: Bounding rectangle (x0, y0, x1, y1) for text boxes; None for text markup.
    """

    type: AnnotationType
    page: int
    quads: list[tuple[float, ...]]
    color: tuple[float, float, float]
    author: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    content: str = ""
    rect: tuple[float, float, float, float] | None = None


@dataclass
class AnnotationInfo:
    """Summary info for an annotation displayed in the summary panel.

    Attributes:
        page: Zero-based page index.
        ann_type: Human-readable type label (e.g. "Highlight", "Note").
        author: Author name from annotation metadata.
        content: Text content for notes/text boxes.
        color: RGB color as 0.0-1.0 floats.
        rect: Bounding rectangle (x0, y0, x1, y1).
    """

    page: int
    ann_type: str
    author: str = ""
    content: str = ""
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rect: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
