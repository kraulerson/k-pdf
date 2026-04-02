"""Tests for OutlineNode dataclass."""

from __future__ import annotations

from k_pdf.core.outline_model import OutlineNode


def test_outline_node_construction() -> None:
    node = OutlineNode(title="Chapter 1", page=0, children=[])
    assert node.title == "Chapter 1"
    assert node.page == 0
    assert node.children == []


def test_outline_node_with_children() -> None:
    child = OutlineNode(title="Section 1.1", page=2, children=[])
    parent = OutlineNode(title="Chapter 1", page=0, children=[child])
    assert len(parent.children) == 1
    assert parent.children[0].title == "Section 1.1"


def test_outline_node_is_frozen() -> None:
    import pytest

    node = OutlineNode(title="Test", page=0, children=[])
    with pytest.raises(AttributeError):
        node.title = "Changed"  # type: ignore[misc]


def test_outline_node_invalid_page() -> None:
    node = OutlineNode(title="Bad Link", page=-1, children=[])
    assert node.page == -1
