"""Outline parsing service — transforms PyMuPDF TOC into OutlineNode tree.

PyMuPDF import is isolated here per AGPL containment rule.
"""

from __future__ import annotations

from typing import Any

from k_pdf.core.outline_model import OutlineNode


def get_outline(doc_handle: Any) -> list[OutlineNode]:
    """Parse a document's table of contents into an OutlineNode tree.

    Args:
        doc_handle: A pymupdf.Document handle.

    Returns:
        List of top-level OutlineNode objects. Empty list if no outline.
    """
    try:
        toc = doc_handle.get_toc()
    except Exception:
        return []

    if not toc:
        return []

    page_count: int = doc_handle.page_count
    root: list[OutlineNode] = []
    stack: list[tuple[int, list[OutlineNode]]] = [(0, root)]

    for entry in toc:
        level: int = entry[0]
        title: str = str(entry[1])
        page_1based: int = int(entry[2])

        # Convert to 0-based, mark invalid as -1
        page_0based = page_1based - 1
        if page_0based < 0 or page_0based >= page_count:
            page_0based = -1

        node = OutlineNode(title=title, page=page_0based, children=[])

        # Find the right parent level
        while len(stack) > 1 and stack[-1][0] >= level:
            stack.pop()

        stack[-1][1].append(node)
        stack.append((level, node.children))

    return root
