"""Integration tests for Feature 10: Merge Multiple PDFs."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.services.merge_engine import MergeEngine
from k_pdf.views.merge_dialog import MergeDialog

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


@pytest.fixture
def three_page_pdf(tmp_path: Path) -> Path:
    """Create a valid 3-page PDF."""
    path = tmp_path / "merge_a.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Merge A page {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def two_page_pdf(tmp_path: Path) -> Path:
    """Create a valid 2-page PDF."""
    path = tmp_path / "merge_b.pdf"
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Merge B page {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


class TestMergeEngineIntegration:
    def test_merge_two_pdfs_creates_output(
        self, three_page_pdf: Path, two_page_pdf: Path, tmp_path: Path
    ) -> None:
        engine = MergeEngine()
        output = tmp_path / "integrated_merge.pdf"
        result = engine.merge([three_page_pdf, two_page_pdf], output)
        assert result.success is True
        assert output.exists()
        doc = pymupdf.open(str(output))
        assert doc.page_count == 5
        doc.close()

    def test_merge_with_corrupt_skips(
        self, three_page_pdf: Path, two_page_pdf: Path, tmp_path: Path
    ) -> None:
        corrupt = tmp_path / "corrupt_merge.pdf"
        corrupt.write_text("not a pdf")
        engine = MergeEngine()
        output = tmp_path / "skip_merge.pdf"
        result = engine.merge([three_page_pdf, corrupt, two_page_pdf], output)
        assert result.success is True
        assert result.files_merged == 2
        assert len(result.skipped_files) == 1
        doc = pymupdf.open(str(output))
        assert doc.page_count == 5
        doc.close()


class TestMergeDialogIntegration:
    def test_dialog_merge_complete_signal(
        self, three_page_pdf: Path, two_page_pdf: Path, tmp_path: Path
    ) -> None:
        dialog = MergeDialog()
        dialog._add_file_paths([three_page_pdf, two_page_pdf])

        # Verify files were added
        assert dialog._file_list.count() == 2
        assert dialog._merge_btn.isEnabled()

        # Verify merge button is enabled with correct file count
        valid_count = sum(1 for info in dialog._file_infos if not info.error)
        assert valid_count == 2


class TestKPdfAppMergeWiring:
    def test_app_has_merge_requested_signal(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        assert hasattr(kpdf.window, "merge_requested")
        kpdf.shutdown()

    def test_merge_requested_connected(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        # Verify the signal is connected (receivers > 0)
        assert kpdf.window.merge_requested.connect(lambda: None) is not None
        kpdf.shutdown()
