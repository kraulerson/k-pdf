"""K-PDF application entry point."""

from __future__ import annotations

import os
import sys

# For macOS .app bundles: pymupdf/fitz live in Contents/Resources/python-packages
# (kept out of Contents/MacOS/ because codesign rejects .py files there)
_resources_pkg = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(sys.executable))),
    "Resources",
    "python-packages",
)
if os.path.isdir(_resources_pkg) and _resources_pkg not in sys.path:
    sys.path.insert(0, _resources_pkg)

from PySide6.QtWidgets import QApplication  # noqa: E402

from k_pdf.app import KPdfApp  # noqa: E402
from k_pdf.core.logging import setup_logging  # noqa: E402


def main() -> int:
    """Launch the K-PDF application.

    Supports opening a PDF file via CLI argument:
        k-pdf /path/to/file.pdf
    """
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("K-PDF")
    app.setOrganizationName("K-PDF")

    # Check for CLI file argument
    file_path: str | None = None
    args = app.arguments()
    if len(args) > 1 and args[1].lower().endswith(".pdf"):
        file_path = args[1]

    k_pdf_app = KPdfApp(app, file_path=file_path)

    exit_code = int(app.exec())
    k_pdf_app.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
