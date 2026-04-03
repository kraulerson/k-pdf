"""Multi-PDF merge dialog.

Self-contained modal QDialog for selecting, ordering, and merging
multiple PDF files into a single output document.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from k_pdf.services.merge_engine import MergeEngine, MergeFileInfo

logger = logging.getLogger("k_pdf.views.merge_dialog")


class MergeDialog(QDialog):
    """Modal dialog for merging multiple PDF files."""

    merge_complete = Signal(str)  # output path string

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the merge dialog with file list, buttons, and progress bar."""
        super().__init__(parent)
        self.setWindowTitle("Merge Documents")
        self.setMinimumSize(500, 400)
        self.resize(600, 500)

        self._merge_engine = MergeEngine()
        self._file_infos: list[MergeFileInfo] = []
        self._output_path: Path | None = None

        layout = QVBoxLayout(self)

        # File list
        self._file_list = QListWidget(self)
        self._file_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._file_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._file_list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self._file_list)

        # Buttons row
        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("Add Files...", self)
        self._add_btn.clicked.connect(self._add_files)
        btn_layout.addWidget(self._add_btn)

        self._remove_btn = QPushButton("Remove Selected", self)
        self._remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(self._remove_btn)

        btn_layout.addStretch()

        self._merge_btn = QPushButton("Merge", self)
        self._merge_btn.setEnabled(False)
        self._merge_btn.clicked.connect(self._start_merge)
        btn_layout.addWidget(self._merge_btn)
        layout.addLayout(btn_layout)

        # Info label
        self._info_label = QLabel("Select at least 2 files to merge.", self)
        layout.addWidget(self._info_label)

        # Progress bar
        self._progress_bar = QProgressBar(self)
        self._progress_bar.setVisible(False)
        self._progress_bar.setFormat("Merging... %v of %m files")
        layout.addWidget(self._progress_bar)

        # Result area
        result_layout = QHBoxLayout()
        self._result_label = QLabel("", self)
        self._result_label.setVisible(False)
        self._result_label.setWordWrap(True)
        result_layout.addWidget(self._result_label)

        self._open_btn = QPushButton("Open Merged File", self)
        self._open_btn.setVisible(False)
        self._open_btn.clicked.connect(self._open_merged_file)
        result_layout.addWidget(self._open_btn)
        layout.addLayout(result_layout)

    def _add_files(self) -> None:
        """Open file picker and add selected PDFs to the list."""
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF Files",
            "",
            "PDF Files (*.pdf);;All Files (*)",
        )
        if paths:
            self._add_file_paths([Path(p) for p in paths])

    def _add_file_paths(self, paths: list[Path]) -> None:
        """Add files to the list by probing them with the merge engine.

        Args:
            paths: List of file paths to add.
        """
        for path in paths:
            info = self._merge_engine.probe_file(path)
            self._file_infos.append(info)

            if info.error:
                item = QListWidgetItem(f"{info.path.name} -- Error: {info.error}")
            else:
                item = QListWidgetItem(f"{info.path.name} -- {info.page_count} pages")
            self._file_list.addItem(item)

        self._update_info()

    def _remove_selected(self) -> None:
        """Remove selected items from the file list."""
        selected_rows = sorted(
            [self._file_list.row(item) for item in self._file_list.selectedItems()],
            reverse=True,
        )
        for row in selected_rows:
            self._file_list.takeItem(row)
            if row < len(self._file_infos):
                self._file_infos.pop(row)

        self._update_info()

    def _on_rows_moved(self) -> None:
        """Sync internal file_infos list with widget order after drag-reorder."""
        new_infos: list[MergeFileInfo] = []
        for i in range(self._file_list.count()):
            item_text = self._file_list.item(i).text()
            # Find matching info by filename in item text
            for info in self._file_infos:
                if info.path.name in item_text and info not in new_infos:
                    new_infos.append(info)
                    break
        self._file_infos = new_infos

    def _update_info(self) -> None:
        """Update info label and merge button enabled state."""
        valid_count = sum(1 for info in self._file_infos if not info.error)
        total_pages = sum(info.page_count for info in self._file_infos)
        total_files = len(self._file_infos)

        if valid_count < 2:
            self._merge_btn.setEnabled(False)
            if total_files == 0:
                self._info_label.setText("Select at least 2 files to merge.")
            else:
                self._info_label.setText(
                    f"{total_files} file{'s' if total_files != 1 else ''}, "
                    f"{total_pages} total pages. Need at least 2 valid files to merge."
                )
        else:
            self._merge_btn.setEnabled(True)
            self._info_label.setText(
                f"{total_files} file{'s' if total_files != 1 else ''}, {total_pages} total pages."
            )

    def _start_merge(self) -> None:
        """Run the merge operation after prompting for output path."""
        output_path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save Merged PDF",
            "",
            "PDF Files (*.pdf);;All Files (*)",
        )
        if not output_path_str:
            return

        output_path = Path(output_path_str)
        sources = [info.path for info in self._file_infos if not info.error]

        if len(sources) < 2:
            QMessageBox.warning(
                self,
                "Cannot Merge",
                "Select at least 2 valid files to merge.",
            )
            return

        # Show progress
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(len(sources))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._merge_btn.setEnabled(False)

        result = self._merge_engine.merge(
            sources,
            output_path,
            progress_callback=self._on_merge_progress,
        )

        self._progress_bar.setVisible(False)

        if result.success:
            self._output_path = result.output_path
            msg = (
                f"Merge complete. {result.files_merged} files merged "
                f"into {output_path.name} ({result.total_pages} pages)."
            )
            if result.skipped_files:
                msg += f"\n\nSkipped files: {', '.join(result.skipped_files)}"
            self._result_label.setText(msg)
            self._result_label.setVisible(True)
            self._open_btn.setVisible(True)
        else:
            self._result_label.setText(f"Merge failed: {result.error_message}")
            self._result_label.setVisible(True)
            self._merge_btn.setEnabled(True)

    def _on_merge_progress(self, current: int, total: int) -> None:
        """Update the progress bar during merge.

        Args:
            current: Current file number (1-based).
            total: Total number of files.
        """
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)

    def _open_merged_file(self) -> None:
        """Emit merge_complete signal with the output path and close dialog."""
        if self._output_path is not None:
            self.merge_complete.emit(str(self._output_path))
        self.accept()

    def get_output_path(self) -> Path | None:
        """Return the output path after a successful merge.

        Returns:
            Path to the merged file, or None if no merge has been performed.
        """
        return self._output_path
