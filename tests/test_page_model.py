"""Tests for page management data model."""

from __future__ import annotations

import pytest

from k_pdf.core.page_model import PageOperation, PageOperationResult


class TestPageOperation:
    def test_rotate_value(self) -> None:
        assert PageOperation.ROTATE.value == "rotate"

    def test_delete_value(self) -> None:
        assert PageOperation.DELETE.value == "delete"

    def test_insert_value(self) -> None:
        assert PageOperation.INSERT.value == "insert"

    def test_move_value(self) -> None:
        assert PageOperation.MOVE.value == "move"

    def test_all_members(self) -> None:
        assert set(PageOperation) == {
            PageOperation.ROTATE,
            PageOperation.DELETE,
            PageOperation.INSERT,
            PageOperation.MOVE,
        }


class TestPageOperationResult:
    def test_construction_success(self) -> None:
        result = PageOperationResult(
            operation=PageOperation.DELETE,
            success=True,
            new_page_count=2,
            affected_pages=[1],
        )
        assert result.operation == PageOperation.DELETE
        assert result.success is True
        assert result.new_page_count == 2
        assert result.affected_pages == [1]
        assert result.error_message == ""

    def test_construction_failure(self) -> None:
        result = PageOperationResult(
            operation=PageOperation.DELETE,
            success=False,
            new_page_count=3,
            affected_pages=[],
            error_message="Cannot delete all pages",
        )
        assert result.success is False
        assert result.error_message == "Cannot delete all pages"

    def test_frozen(self) -> None:
        result = PageOperationResult(
            operation=PageOperation.ROTATE,
            success=True,
            new_page_count=3,
            affected_pages=[0, 1],
        )
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_default_error_message(self) -> None:
        result = PageOperationResult(
            operation=PageOperation.MOVE,
            success=True,
            new_page_count=5,
            affected_pages=[2],
        )
        assert result.error_message == ""
