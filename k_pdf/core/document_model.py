"""In-memory document state.

DocumentMetadata and PageInfo are pure data — no Qt or PyMuPDF imports.
DocumentModel holds the full per-tab state including the opaque doc handle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class DocumentMetadata:
    """Immutable metadata extracted from a PDF document."""

    file_path: Path
    page_count: int
    title: str | None
    author: str | None
    has_forms: bool
    has_outline: bool
    has_javascript: bool
    is_encrypted: bool
    file_size_bytes: int


@dataclass(frozen=True)
class PageInfo:
    """Immutable metadata for a single PDF page."""

    index: int
    width: float  # points (1/72 inch)
    height: float  # points
    rotation: int  # 0, 90, 180, 270 (from PDF, not view rotation)
    has_text: bool
    annotation_count: int


@dataclass
class DocumentModel:
    """Per-tab in-memory document state."""

    file_path: Path
    doc_handle: Any  # fitz.Document (opaque to non-service code)
    metadata: DocumentMetadata
    pages: list[PageInfo]
    dirty: bool = False
    session_id: str = field(default_factory=lambda: str(uuid4()))
