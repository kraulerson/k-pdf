"""Tests for TabManager tab lifecycle."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QTabWidget

from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.presenters.tab_manager import TabManager

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_model(file_path: Path) -> DocumentModel:
    """Create a minimal DocumentModel for testing."""
    metadata = DocumentMetadata(
        file_path=file_path,
        page_count=3,
        title=None,
        author=None,
        has_forms=False,
        has_outline=False,
        has_javascript=False,
        is_encrypted=False,
        file_size_bytes=1000,
    )
    pages = [
        PageInfo(index=i, width=612, height=792, rotation=0, has_text=True, annotation_count=0)
        for i in range(3)
    ]
    return DocumentModel(
        file_path=file_path,
        doc_handle=MagicMock(),
        metadata=metadata,
        pages=pages,
    )


class TestTabManagerOpenFile:
    """Tests for TabManager.open_file flow."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_open_file_creates_tab(self, mock_presenter_cls: MagicMock) -> None:
        """Test that open_file creates a TabContext and adds a tab."""
        mock_presenter = MagicMock()
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))

        assert tab_widget.count() == 1
        assert tab_widget.tabText(0) == "Loading..."
        assert len(manager._tabs) == 1
        mock_presenter.open_file.assert_called_once()

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_open_duplicate_activates_existing(self, mock_presenter_cls: MagicMock) -> None:
        """Test that opening an already-open file activates the existing tab."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        status_spy = MagicMock()
        manager.status_message.connect(status_spy)

        # Open a file and simulate document_ready to register the path
        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        manager._on_document_ready(session_id, model)

        # Try to open the same file again
        manager.open_file(Path("/tmp/test.pdf"))

        assert tab_widget.count() == 1
        assert len(manager._tabs) == 1
        status_spy.assert_called_with("This file is already open")


class TestTabManagerCloseTab:
    """Tests for TabManager.close_tab flow."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_close_tab_removes_tab(self, mock_presenter_cls: MagicMock) -> None:
        """Test that close_tab removes the tab and shuts down the presenter."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))

        manager.close_tab(session_id)

        assert tab_widget.count() == 0
        assert len(manager._tabs) == 0
        mock_presenter.shutdown.assert_called_once()

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_close_last_tab_emits_zero_count(self, mock_presenter_cls: MagicMock) -> None:
        """Test that closing the last tab emits tab_count_changed(0)."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        count_spy = MagicMock()
        manager.tab_count_changed.connect(count_spy)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        manager.close_tab(session_id)

        count_spy.assert_called_with(0)


class TestTabManagerDocumentReady:
    """Tests for TabManager._on_document_ready flow."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_document_ready_updates_title(self, mock_presenter_cls: MagicMock) -> None:
        """Test that document_ready updates the tab title to the filename."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        manager._on_document_ready(session_id, model)

        assert tab_widget.tabText(0) == "test.pdf"

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_document_ready_registers_path(self, mock_presenter_cls: MagicMock) -> None:
        """Test that document_ready registers the resolved path for duplicate detection."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        manager._on_document_ready(session_id, model)

        resolved = Path("/tmp/test.pdf").resolve()
        assert resolved in manager._open_paths

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_document_ready_adds_to_recent_files(self, mock_presenter_cls: MagicMock) -> None:
        """Test that document_ready adds the file to recent files."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        manager._on_document_ready(session_id, model)

        recent_files.add.assert_called_once_with(Path("/tmp/test.pdf"))

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_tab_title_dirty_prefix(self, mock_presenter_cls: MagicMock) -> None:
        """Test that dirty documents show * prefix in tab title."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        model.dirty = True
        manager._on_document_ready(session_id, model)

        assert tab_widget.tabText(0) == "* test.pdf"


class TestTabManagerActivate:
    """Tests for TabManager.activate_tab flow."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_activate_tab_switches_widget(self, mock_presenter_cls: MagicMock) -> None:
        """Test that activate_tab changes the QTabWidget current index."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/a.pdf"))
        manager.open_file(Path("/tmp/b.pdf"))

        session_ids = list(manager._tabs.keys())
        manager.activate_tab(session_ids[0])

        assert tab_widget.currentIndex() == 0


class TestTabManagerShutdown:
    """Tests for TabManager.shutdown flow."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_shutdown_cleans_all_tabs(self, mock_presenter_cls: MagicMock) -> None:
        """Test that shutdown calls presenter.shutdown() for all tabs."""
        presenters: list[MagicMock] = []

        def make_presenter() -> MagicMock:
            p = MagicMock()
            p.model = None
            presenters.append(p)
            return p

        mock_presenter_cls.side_effect = make_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/a.pdf"))
        manager.open_file(Path("/tmp/b.pdf"))
        manager.shutdown()

        for p in presenters:
            p.shutdown.assert_called_once()
        assert len(manager._tabs) == 0


class TestTabManagerErrorHandling:
    """Tests for TabManager error and password flows."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_load_failure_removes_tab(self, mock_presenter_cls: MagicMock) -> None:
        """Test that a load error removes the empty Loading... tab."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        error_spy = MagicMock()
        manager.error_occurred.connect(error_spy)

        manager.open_file(Path("/tmp/bad.pdf"))
        session_id = next(iter(manager._tabs))

        # Simulate load failure (resolved_path is still None)
        manager._on_error(session_id, "Cannot open file", "File is corrupt")

        assert tab_widget.count() == 0
        assert len(manager._tabs) == 0
        error_spy.assert_called_once_with("Cannot open file", "File is corrupt")

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_error_after_load_does_not_remove_tab(self, mock_presenter_cls: MagicMock) -> None:
        """Test that an error after successful load does NOT remove the tab."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        session_id = next(iter(manager._tabs))
        model = _make_model(Path("/tmp/test.pdf"))
        manager._on_document_ready(session_id, model)

        # Error after load (e.g., save failure) — tab should stay
        manager._on_error(session_id, "Save error", "Cannot save")

        assert tab_widget.count() == 1
        assert len(manager._tabs) == 1


class TestTabManagerNewSignals:
    """Tests for TabManager tab_switched, tab_closed signals and get_active_viewport."""

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_tab_switched_emits_session_id(self, mock_presenter_cls: MagicMock) -> None:
        """Test that switching tabs emits tab_switched with session_id."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        switched_spy = MagicMock()
        manager.tab_switched.connect(switched_spy)

        manager.open_file(Path("/tmp/a.pdf"))
        manager.open_file(Path("/tmp/b.pdf"))

        sids = list(manager._tabs.keys())
        tab_widget.setCurrentIndex(0)

        switched_spy.assert_called_with(sids[0])

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_tab_closed_emits_session_id(self, mock_presenter_cls: MagicMock) -> None:
        """Test that closing a tab emits tab_closed with session_id."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)
        closed_spy = MagicMock()
        manager.tab_closed.connect(closed_spy)

        manager.open_file(Path("/tmp/test.pdf"))
        sid = next(iter(manager._tabs))
        manager.close_tab(sid)

        closed_spy.assert_called_once_with(sid)

    @patch("k_pdf.presenters.tab_manager.DocumentPresenter")
    def test_get_active_viewport_returns_viewport(self, mock_presenter_cls: MagicMock) -> None:
        """Test get_active_viewport returns the active tab's PdfViewport."""
        mock_presenter = MagicMock()
        mock_presenter.model = None
        mock_presenter_cls.return_value = mock_presenter
        tab_widget = QTabWidget()
        recent_files = MagicMock()
        manager = TabManager(tab_widget=tab_widget, recent_files=recent_files)

        manager.open_file(Path("/tmp/test.pdf"))
        viewport = manager.get_active_viewport()

        assert viewport is not None
        from k_pdf.views.pdf_viewport import PdfViewport

        assert isinstance(viewport, PdfViewport)
