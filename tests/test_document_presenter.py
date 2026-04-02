"""Tests for DocumentPresenter open flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from k_pdf.core.document_model import DocumentModel
from k_pdf.presenters.document_presenter import DocumentPresenter

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestDocumentPresenter:
    """Test the DocumentPresenter open flow."""

    def test_open_file_emits_error_for_nonexistent(
        self, nonexistent_pdf: Path, qtbot: object
    ) -> None:
        """Test that opening a nonexistent file emits an error signal."""
        presenter = DocumentPresenter()
        error_spy = MagicMock()
        presenter.error_occurred.connect(error_spy)

        presenter.open_file(nonexistent_pdf)

        error_spy.assert_called_once()
        title, msg = error_spy.call_args[0]
        assert "Validation" in title
        assert "not found" in msg.lower()
        presenter.shutdown()

    def test_open_file_emits_error_for_not_a_pdf(self, not_a_pdf: Path, qtbot: object) -> None:
        """Test that opening a non-PDF file emits an error signal."""
        presenter = DocumentPresenter()
        error_spy = MagicMock()
        presenter.error_occurred.connect(error_spy)

        presenter.open_file(not_a_pdf)

        error_spy.assert_called_once()
        _, msg = error_spy.call_args[0]
        assert "does not appear to be a valid PDF" in msg
        presenter.shutdown()

    def test_open_valid_file_emits_document_ready(self, valid_pdf: Path, qtbot: object) -> None:
        """Test that opening a valid PDF emits document_ready with model."""
        presenter = DocumentPresenter()
        ready_spy = MagicMock()
        presenter.document_ready.connect(ready_spy)

        presenter.open_file(valid_pdf)

        # Wait for the worker thread to finish
        def check_ready() -> None:
            assert ready_spy.call_count == 1

        qtbot.waitUntil(check_ready, timeout=5000)

        model = ready_spy.call_args[0][0]
        assert isinstance(model, DocumentModel)
        assert model.metadata.page_count == 3
        presenter.shutdown()

    def test_open_encrypted_emits_password_requested(
        self, encrypted_pdf: Path, qtbot: object
    ) -> None:
        """Test that an encrypted PDF triggers the password flow."""
        presenter = DocumentPresenter()
        pw_spy = MagicMock()
        presenter.password_requested.connect(pw_spy)

        presenter.open_file(encrypted_pdf)

        def check_pw() -> None:
            assert pw_spy.call_count == 1

        qtbot.waitUntil(check_pw, timeout=5000)
        presenter.shutdown()
