"""Outline/bookmark tree model.

OutlineNode is a pure data structure — no Qt or PyMuPDF imports.
Used by OutlineService (services/) and NavigationPanel (views/).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OutlineNode:
    """A single node in the document outline/bookmark tree."""

    title: str
    page: int  # 0-based page index, -1 if invalid
    children: list[OutlineNode] = field(default_factory=list)
