"""Tests for MergeEngine service."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from k_pdf.services.merge_engine import MergeEngine, MergeFileInfo, MergeResult


@pytest.fixture
def merge_engine() -> MergeEngine:
    """Create a MergeEngine instance."""
    return MergeEngine()


@pytest.fixture
def three_page_pdf(tmp_path: Path) -> Path:
    """Create a valid 3-page PDF."""
    path = tmp_path / "three_page.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Three-page doc, page {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def two_page_pdf(tmp_path: Path) -> Path:
    """Create a valid 2-page PDF."""
    path = tmp_path / "two_page.pdf"
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Two-page doc, page {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def one_page_pdf(tmp_path: Path) -> Path:
    """Create a valid 1-page PDF."""
    path = tmp_path / "one_page.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(pymupdf.Point(72, 72), "One-page doc content")
    doc.save(str(path))
    doc.close()
    return path


class TestMergeFileInfo:
    def test_construction_valid(self) -> None:
        info = MergeFileInfo(path=Path("/tmp/test.pdf"), page_count=5)
        assert info.path == Path("/tmp/test.pdf")
        assert info.page_count == 5
        assert info.error == ""

    def test_construction_with_error(self) -> None:
        info = MergeFileInfo(path=Path("/tmp/bad.pdf"), page_count=0, error="Corrupt file")
        assert info.error == "Corrupt file"
        assert info.page_count == 0

    def test_frozen(self) -> None:
        info = MergeFileInfo(path=Path("/tmp/test.pdf"), page_count=3)
        with pytest.raises(AttributeError):
            info.page_count = 10  # type: ignore[misc]


class TestMergeResult:
    def test_construction_success(self) -> None:
        result = MergeResult(
            success=True,
            output_path=Path("/tmp/merged.pdf"),
            total_pages=10,
            files_merged=3,
        )
        assert result.success is True
        assert result.output_path == Path("/tmp/merged.pdf")
        assert result.total_pages == 10
        assert result.files_merged == 3
        assert result.skipped_files == []
        assert result.error_message == ""

    def test_construction_failure(self) -> None:
        result = MergeResult(
            success=False,
            error_message="Need at least 2 files",
        )
        assert result.success is False
        assert result.error_message == "Need at least 2 files"

    def test_frozen(self) -> None:
        result = MergeResult(success=True, total_pages=5)
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]


class TestProbeFile:
    def test_probe_valid_pdf(self, merge_engine: MergeEngine, three_page_pdf: Path) -> None:
        info = merge_engine.probe_file(three_page_pdf)
        assert info.page_count == 3
        assert info.error == ""
        assert info.path == three_page_pdf

    def test_probe_nonexistent_file(self, merge_engine: MergeEngine, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.pdf"
        info = merge_engine.probe_file(path)
        assert info.page_count == 0
        assert info.error != ""

    def test_probe_corrupt_file(self, merge_engine: MergeEngine, tmp_path: Path) -> None:
        path = tmp_path / "corrupt.pdf"
        path.write_bytes(b"%PDF-1.4\n% corrupt\n%%EOF")
        info = merge_engine.probe_file(path)
        # PyMuPDF may or may not open this; either way we should get valid info
        assert info.path == path

    def test_probe_not_a_pdf(self, merge_engine: MergeEngine, tmp_path: Path) -> None:
        path = tmp_path / "fake.pdf"
        path.write_text("This is not a PDF")
        info = merge_engine.probe_file(path)
        assert info.page_count == 0
        assert info.error != ""

    def test_probe_two_page_pdf(self, merge_engine: MergeEngine, two_page_pdf: Path) -> None:
        info = merge_engine.probe_file(two_page_pdf)
        assert info.page_count == 2
        assert info.error == ""


class TestMerge:
    def test_merge_two_pdfs(
        self,
        merge_engine: MergeEngine,
        three_page_pdf: Path,
        two_page_pdf: Path,
        tmp_path: Path,
    ) -> None:
        output = tmp_path / "merged.pdf"
        result = merge_engine.merge([three_page_pdf, two_page_pdf], output)
        assert result.success is True
        assert result.output_path == output
        assert result.total_pages == 5
        assert result.files_merged == 2
        assert result.skipped_files == []
        assert output.exists()

    def test_merge_three_pdfs(
        self,
        merge_engine: MergeEngine,
        three_page_pdf: Path,
        two_page_pdf: Path,
        one_page_pdf: Path,
        tmp_path: Path,
    ) -> None:
        output = tmp_path / "merged3.pdf"
        result = merge_engine.merge([three_page_pdf, two_page_pdf, one_page_pdf], output)
        assert result.success is True
        assert result.total_pages == 6
        assert result.files_merged == 3

    def test_merge_skips_corrupt_file(
        self,
        merge_engine: MergeEngine,
        three_page_pdf: Path,
        two_page_pdf: Path,
        tmp_path: Path,
    ) -> None:
        corrupt = tmp_path / "bad.pdf"
        corrupt.write_text("not a pdf at all")
        output = tmp_path / "merged_skip.pdf"
        result = merge_engine.merge([three_page_pdf, corrupt, two_page_pdf], output)
        assert result.success is True
        assert result.files_merged == 2
        assert result.total_pages == 5
        assert len(result.skipped_files) == 1
        assert "bad.pdf" in result.skipped_files[0]

    def test_merge_progress_callback(
        self,
        merge_engine: MergeEngine,
        three_page_pdf: Path,
        two_page_pdf: Path,
        tmp_path: Path,
    ) -> None:
        output = tmp_path / "merged_prog.pdf"
        calls: list[tuple[int, int]] = []
        result = merge_engine.merge(
            [three_page_pdf, two_page_pdf],
            output,
            progress_callback=lambda cur, tot: calls.append((cur, tot)),
        )
        assert result.success is True
        assert len(calls) == 2
        assert calls[0] == (1, 2)
        assert calls[1] == (2, 2)

    def test_merge_empty_list(self, merge_engine: MergeEngine, tmp_path: Path) -> None:
        output = tmp_path / "empty_merge.pdf"
        result = merge_engine.merge([], output)
        assert result.success is False
        assert "at least 2" in result.error_message.lower()

    def test_merge_single_file(
        self,
        merge_engine: MergeEngine,
        three_page_pdf: Path,
        tmp_path: Path,
    ) -> None:
        output = tmp_path / "single_merge.pdf"
        result = merge_engine.merge([three_page_pdf], output)
        assert result.success is False
        assert "at least 2" in result.error_message.lower()

    def test_merge_all_invalid(self, merge_engine: MergeEngine, tmp_path: Path) -> None:
        bad1 = tmp_path / "bad1.pdf"
        bad1.write_text("not a pdf")
        bad2 = tmp_path / "bad2.pdf"
        bad2.write_text("also not a pdf")
        output = tmp_path / "all_bad.pdf"
        result = merge_engine.merge([bad1, bad2], output)
        assert result.success is False
        assert len(result.skipped_files) == 2

    def test_merge_output_has_correct_content(
        self,
        merge_engine: MergeEngine,
        three_page_pdf: Path,
        two_page_pdf: Path,
        tmp_path: Path,
    ) -> None:
        output = tmp_path / "content_check.pdf"
        merge_engine.merge([three_page_pdf, two_page_pdf], output)
        doc = pymupdf.open(str(output))
        assert doc.page_count == 5
        # Check text from first source on page 0
        text_p0 = doc[0].get_text("text")
        assert "Three-page doc" in text_p0
        # Check text from second source on page 3
        text_p3 = doc[3].get_text("text")
        assert "Two-page doc" in text_p3
        doc.close()

    def test_merge_preserves_order(
        self,
        merge_engine: MergeEngine,
        three_page_pdf: Path,
        one_page_pdf: Path,
        tmp_path: Path,
    ) -> None:
        output = tmp_path / "order_check.pdf"
        merge_engine.merge([one_page_pdf, three_page_pdf], output)
        doc = pymupdf.open(str(output))
        assert doc.page_count == 4
        text_p0 = doc[0].get_text("text")
        assert "One-page doc" in text_p0
        text_p1 = doc[1].get_text("text")
        assert "Three-page doc" in text_p1
        doc.close()
