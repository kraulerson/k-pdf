"""Multi-PDF merge engine.

Wraps PyMuPDF doc.insert_pdf() to combine multiple source PDFs
into a single output document. All pymupdf imports are isolated here.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

logger = logging.getLogger("k_pdf.services.merge_engine")


@dataclass(frozen=True)
class MergeFileInfo:
    """Information about a source file for merging.

    Attributes:
        path: Absolute path to the source PDF.
        page_count: Number of pages in the source PDF.
        error: Error message if the file could not be read.
    """

    path: Path
    page_count: int
    error: str = ""


@dataclass(frozen=True)
class MergeResult:
    """Result of a merge operation.

    Attributes:
        success: Whether the merge completed successfully.
        output_path: Path to the merged output file.
        total_pages: Total page count in the merged file.
        files_merged: Number of files successfully merged.
        skipped_files: Filenames that were skipped due to errors.
        error_message: Overall error if merge failed entirely.
    """

    success: bool
    output_path: Path | None = None
    total_pages: int = 0
    files_merged: int = 0
    skipped_files: list[str] = field(default_factory=list)
    error_message: str = ""


class MergeEngine:
    """Wraps PyMuPDF merge operations.

    All pymupdf document manipulation for merging is isolated here.
    """

    def probe_file(self, path: Path) -> MergeFileInfo:
        """Open a file to read its page count.

        Args:
            path: Path to the PDF file.

        Returns:
            MergeFileInfo with page count or error message.
        """
        if not path.exists():
            return MergeFileInfo(
                path=path,
                page_count=0,
                error=f"File not found: {path.name}",
            )

        try:
            doc = pymupdf.open(str(path))
        except Exception as exc:
            logger.debug("Failed to open %s for probing: %s", path, exc)
            return MergeFileInfo(
                path=path,
                page_count=0,
                error=f"Cannot read: {exc}",
            )

        try:
            if doc.needs_pass:
                doc.close()
                return MergeFileInfo(
                    path=path,
                    page_count=0,
                    error="Password-protected",
                )
            count = doc.page_count
            doc.close()
            if count == 0:
                return MergeFileInfo(
                    path=path,
                    page_count=0,
                    error="File contains 0 pages",
                )
            return MergeFileInfo(path=path, page_count=count)
        except Exception as exc:
            doc.close()
            logger.debug("Error probing %s: %s", path, exc)
            return MergeFileInfo(
                path=path,
                page_count=0,
                error=f"Cannot read: {exc}",
            )

    def merge(
        self,
        sources: list[Path],
        output_path: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> MergeResult:
        """Merge multiple PDF files into a single output file.

        Args:
            sources: List of source PDF file paths.
            output_path: Path where the merged PDF will be saved.
            progress_callback: Optional callback called after each file
                with (current_file_number, total_file_count).

        Returns:
            MergeResult indicating success or failure.
        """
        if len(sources) < 2:
            return MergeResult(
                success=False,
                error_message="Select at least 2 files to merge.",
            )

        output_doc = pymupdf.open()
        skipped: list[str] = []
        merged_count = 0
        total = len(sources)

        for idx, source_path in enumerate(sources):
            try:
                source_doc = pymupdf.open(str(source_path))
            except Exception as exc:
                logger.warning("Skipping %s during merge: %s", source_path.name, exc)
                skipped.append(source_path.name)
                if progress_callback is not None:
                    progress_callback(idx + 1, total)
                continue

            try:
                if source_doc.needs_pass:
                    # nosemgrep: python-logger-credential-disclosure (logs filename, not a password)
                    logger.warning("Skipping encrypted file %s", source_path.name)
                    skipped.append(source_path.name)
                    source_doc.close()
                    if progress_callback is not None:
                        progress_callback(idx + 1, total)
                    continue

                output_doc.insert_pdf(source_doc)
                source_doc.close()
                merged_count += 1
            except Exception as exc:
                logger.warning("Error merging %s: %s", source_path.name, exc)
                skipped.append(source_path.name)
                source_doc.close()

            if progress_callback is not None:
                progress_callback(idx + 1, total)

        if merged_count == 0:
            output_doc.close()
            return MergeResult(
                success=False,
                skipped_files=skipped,
                error_message="No valid files to merge. All files were skipped.",
            )

        try:
            output_doc.save(str(output_path))
            total_pages = output_doc.page_count
            output_doc.close()
        except Exception as exc:
            output_doc.close()
            logger.warning("Failed to save merged PDF to %s: %s", output_path, exc)
            return MergeResult(
                success=False,
                skipped_files=skipped,
                error_message=f"Cannot save to {output_path}: {exc}",
            )

        logger.info(
            "Merged %d files (%d pages) into %s, skipped %d",
            merged_count,
            total_pages,
            output_path.name,
            len(skipped),
        )

        return MergeResult(
            success=True,
            output_path=output_path,
            total_pages=total_pages,
            files_merged=merged_count,
            skipped_files=skipped,
        )
