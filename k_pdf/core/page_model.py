"""Page management data model.

Framework-free data layer for page operations.
Used by PageEngine and PageManagementPresenter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PageOperation(Enum):
    """Types of page manipulation operations."""

    ROTATE = "rotate"
    DELETE = "delete"
    INSERT = "insert"
    MOVE = "move"


@dataclass(frozen=True)
class PageOperationResult:
    """Immutable result of a page operation.

    Attributes:
        operation: The operation that was performed.
        success: Whether the operation succeeded.
        new_page_count: Total page count after operation.
        affected_pages: Zero-based indices of pages affected.
        error_message: Error description if success is False.
    """

    operation: PageOperation
    success: bool
    new_page_count: int
    affected_pages: list[int] = field(default_factory=list)
    error_message: str = ""
