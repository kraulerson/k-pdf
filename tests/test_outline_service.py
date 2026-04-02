"""Tests for OutlineService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pymupdf

from k_pdf.services.outline_service import get_outline


def test_parse_flat_toc_into_tree(pdf_with_outline: Path) -> None:
    doc = pymupdf.open(str(pdf_with_outline))
    nodes = get_outline(doc)
    doc.close()

    assert len(nodes) == 3  # 3 top-level chapters
    assert nodes[0].title == "Chapter 1"
    assert nodes[0].page == 0  # 1-based page 1 → 0-based 0
    assert len(nodes[0].children) == 2
    assert nodes[0].children[0].title == "Section 1.1"
    assert nodes[0].children[1].title == "Section 1.2"
    assert nodes[1].title == "Chapter 2"
    assert nodes[1].page == 2
    assert nodes[2].title == "Chapter 3"
    assert nodes[2].page == 4


def test_empty_outline(valid_pdf: Path) -> None:
    doc = pymupdf.open(str(valid_pdf))
    nodes = get_outline(doc)
    doc.close()
    assert nodes == []


def test_invalid_page_gets_negative_one() -> None:
    doc = MagicMock()
    doc.get_toc.return_value = [[1, "Bad Link", 999]]
    doc.page_count = 5
    nodes = get_outline(doc)
    assert len(nodes) == 1
    assert nodes[0].page == -1
