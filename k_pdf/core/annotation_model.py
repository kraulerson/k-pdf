"""Annotation data model.

Framework-free data layer for annotation type and annotation metadata.
Used by AnnotationPresenter and AnnotationEngine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AnnotationType(Enum):
    """Text markup annotation types."""

    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"


@dataclass
class AnnotationData:
    """Metadata for a single text markup annotation.

    Attributes:
        type: The annotation kind (highlight, underline, strikethrough).
        page: Zero-based page index.
        quads: Quad-point coordinates defining the annotated region.
        color: RGB color as 0.0-1.0 floats.
        author: Author name (optional metadata).
        created_at: Creation timestamp.
    """

    type: AnnotationType
    page: int
    quads: list[tuple[float, ...]]
    color: tuple[float, float, float]
    author: str = ""
    created_at: datetime = field(default_factory=datetime.now)
