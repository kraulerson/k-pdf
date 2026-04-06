"""Tests for text_edit_model dataclasses."""

from __future__ import annotations

from k_pdf.core.text_edit_model import (
    EditResult,
    FontCheckResult,
    ReplaceAllResult,
    TextBlockInfo,
)


class TestTextBlockInfo:
    """Tests for TextBlockInfo dataclass."""

    def test_creation(self) -> None:
        """Test basic TextBlockInfo creation."""
        block = TextBlockInfo(
            page=0,
            rect=(72.0, 100.0, 272.0, 124.0),
            text="Hello world",
            font_name="Helvetica",
            font_size=12.0,
            is_fully_embedded=True,
        )
        assert block.page == 0
        assert block.text == "Hello world"
        assert block.is_fully_embedded is True
        assert block.font_name == "Helvetica"
        assert block.font_size == 12.0

    def test_subset_font(self) -> None:
        """Test TextBlockInfo with subset-embedded font."""
        block = TextBlockInfo(
            page=1,
            rect=(0, 0, 100, 20),
            text="Test",
            font_name="TimesNewRoman-Subset",
            font_size=11.0,
            is_fully_embedded=False,
        )
        assert block.is_fully_embedded is False
        assert block.page == 1
        assert block.font_name == "TimesNewRoman-Subset"

    def test_immutability(self) -> None:
        """Test that TextBlockInfo is frozen (immutable)."""
        block = TextBlockInfo(
            page=0,
            rect=(0, 0, 100, 20),
            text="Test",
            font_name="Helvetica",
            font_size=12.0,
            is_fully_embedded=True,
        )
        try:
            block.page = 1  # type: ignore[misc]
            assert False, "TextBlockInfo should be frozen"
        except AttributeError:
            pass


class TestFontCheckResult:
    """Tests for FontCheckResult dataclass."""

    def test_supported(self) -> None:
        """Test FontCheckResult for supported font."""
        result = FontCheckResult(supported=True, font_name="Helvetica", reason="")
        assert result.supported is True
        assert result.font_name == "Helvetica"
        assert result.reason == ""

    def test_not_supported(self) -> None:
        """Test FontCheckResult for unsupported font."""
        result = FontCheckResult(
            supported=False,
            font_name="Arial-Subset",
            reason="Font is subset-embedded",
        )
        assert result.supported is False
        assert result.font_name == "Arial-Subset"
        assert result.reason == "Font is subset-embedded"

    def test_immutability(self) -> None:
        """Test that FontCheckResult is frozen (immutable)."""
        result = FontCheckResult(supported=True, font_name="Arial", reason="")
        try:
            result.supported = False  # type: ignore[misc]
            assert False, "FontCheckResult should be frozen"
        except AttributeError:
            pass


class TestEditResult:
    """Tests for EditResult dataclass."""

    def test_success(self) -> None:
        """Test EditResult for successful edit."""
        result = EditResult(success=True, error_message="")
        assert result.success is True
        assert result.error_message == ""

    def test_failure(self) -> None:
        """Test EditResult for failed edit."""
        result = EditResult(success=False, error_message="Font not supported")
        assert result.success is False
        assert result.error_message == "Font not supported"

    def test_immutability(self) -> None:
        """Test that EditResult is frozen (immutable)."""
        result = EditResult(success=True, error_message="")
        try:
            result.success = False  # type: ignore[misc]
            assert False, "EditResult should be frozen"
        except AttributeError:
            pass


class TestReplaceAllResult:
    """Tests for ReplaceAllResult dataclass."""

    def test_full_success(self) -> None:
        """Test ReplaceAllResult with all replacements successful."""
        result = ReplaceAllResult(replaced_count=5, skipped_count=0, skipped_locations=[])
        assert result.replaced_count == 5
        assert result.skipped_count == 0
        assert len(result.skipped_locations) == 0

    def test_partial_success(self) -> None:
        """Test ReplaceAllResult with some skipped replacements."""
        result = ReplaceAllResult(
            replaced_count=3,
            skipped_count=2,
            skipped_locations=[(2, "subset font"), (7, "subset font")],
        )
        assert result.replaced_count == 3
        assert result.skipped_count == 2
        assert len(result.skipped_locations) == 2
        assert result.skipped_locations[0] == (2, "subset font")
        assert result.skipped_locations[1] == (7, "subset font")

    def test_all_skipped(self) -> None:
        """Test ReplaceAllResult with all replacements skipped."""
        result = ReplaceAllResult(
            replaced_count=0,
            skipped_count=3,
            skipped_locations=[(0, "no match"), (1, "no match"), (2, "no match")],
        )
        assert result.replaced_count == 0
        assert result.skipped_count == 3
        assert len(result.skipped_locations) == 3

    def test_default_empty_locations(self) -> None:
        """Test ReplaceAllResult creates empty list by default."""
        result = ReplaceAllResult(replaced_count=0, skipped_count=0)
        assert result.skipped_locations == []
        assert isinstance(result.skipped_locations, list)
