"""Tests for MergeDialog view."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from PySide6.QtWidgets import QApplication

from k_pdf.views.merge_dialog import MergeDialog

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists for widget tests."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


@pytest.fixture
def dialog() -> MergeDialog:
    """Create a MergeDialog instance."""
    dlg = MergeDialog()
    return dlg


@pytest.fixture
def three_page_pdf(tmp_path: Path) -> Path:
    """Create a valid 3-page PDF."""
    path = tmp_path / "doc_a.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Doc A page {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def two_page_pdf(tmp_path: Path) -> Path:
    """Create a valid 2-page PDF."""
    path = tmp_path / "doc_b.pdf"
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 72), f"Doc B page {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


class TestMergeDialogInitialState:
    def test_dialog_opens_empty(self, dialog: MergeDialog) -> None:
        assert dialog._file_list.count() == 0

    def test_merge_button_disabled_initially(self, dialog: MergeDialog) -> None:
        assert not dialog._merge_btn.isEnabled()

    def test_info_label_initial_text(self, dialog: MergeDialog) -> None:
        assert "at least 2" in dialog._info_label.text().lower()

    def test_has_add_button(self, dialog: MergeDialog) -> None:
        assert dialog._add_btn is not None
        assert dialog._add_btn.text() == "Add Files..."

    def test_has_remove_button(self, dialog: MergeDialog) -> None:
        assert dialog._remove_btn is not None
        assert dialog._remove_btn.text() == "Remove Selected"

    def test_progress_bar_hidden(self, dialog: MergeDialog) -> None:
        assert not dialog._progress_bar.isVisible()

    def test_open_button_hidden(self, dialog: MergeDialog) -> None:
        assert not dialog._open_btn.isVisible()

    def test_result_label_hidden(self, dialog: MergeDialog) -> None:
        assert not dialog._result_label.isVisible()


class TestAddFiles:
    def test_add_files_populates_list(
        self, dialog: MergeDialog, three_page_pdf: Path, two_page_pdf: Path
    ) -> None:
        dialog._add_file_paths([three_page_pdf, two_page_pdf])
        assert dialog._file_list.count() == 2

    def test_item_text_shows_filename_and_pages(
        self, dialog: MergeDialog, three_page_pdf: Path
    ) -> None:
        dialog._add_file_paths([three_page_pdf])
        item_text = dialog._file_list.item(0).text()
        assert "doc_a.pdf" in item_text
        assert "3" in item_text

    def test_error_file_shown_with_error_text(self, dialog: MergeDialog, tmp_path: Path) -> None:
        bad = tmp_path / "bad.pdf"
        bad.write_text("not a pdf")
        dialog._add_file_paths([bad])
        item_text = dialog._file_list.item(0).text()
        assert "bad.pdf" in item_text
        assert "Error" in item_text


class TestRemoveFiles:
    def test_remove_selected(
        self, dialog: MergeDialog, three_page_pdf: Path, two_page_pdf: Path
    ) -> None:
        dialog._add_file_paths([three_page_pdf, two_page_pdf])
        assert dialog._file_list.count() == 2
        dialog._file_list.setCurrentRow(0)
        dialog._remove_selected()
        assert dialog._file_list.count() == 1


class TestMergeButtonState:
    def test_disabled_with_one_file(self, dialog: MergeDialog, three_page_pdf: Path) -> None:
        dialog._add_file_paths([three_page_pdf])
        assert not dialog._merge_btn.isEnabled()

    def test_enabled_with_two_valid_files(
        self, dialog: MergeDialog, three_page_pdf: Path, two_page_pdf: Path
    ) -> None:
        dialog._add_file_paths([three_page_pdf, two_page_pdf])
        assert dialog._merge_btn.isEnabled()

    def test_disabled_when_all_error(self, dialog: MergeDialog, tmp_path: Path) -> None:
        bad1 = tmp_path / "bad1.pdf"
        bad1.write_text("not a pdf")
        bad2 = tmp_path / "bad2.pdf"
        bad2.write_text("also not a pdf")
        dialog._add_file_paths([bad1, bad2])
        assert not dialog._merge_btn.isEnabled()


class TestInfoLabel:
    def test_shows_correct_counts(
        self, dialog: MergeDialog, three_page_pdf: Path, two_page_pdf: Path
    ) -> None:
        dialog._add_file_paths([three_page_pdf, two_page_pdf])
        text = dialog._info_label.text()
        assert "2" in text  # 2 files
        assert "5" in text  # 5 total pages


class TestOutputPath:
    def test_get_output_path_initially_none(self, dialog: MergeDialog) -> None:
        assert dialog.get_output_path() is None
