"""Integration tests for Text Copy feature — Ctrl+C, Select All, clipboard, status bar."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QTabWidget

from k_pdf.core.annotation_model import ToolMode
from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.presenters.annotation_presenter import AnnotationPresenter
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.annotation_engine import AnnotationEngine
from k_pdf.views.annotation_toolbar import AnnotationToolbar
from k_pdf.views.main_window import MainWindow

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_model(file_path: Path | None = None, page_count: int = 3) -> DocumentModel:
    fp = file_path or Path("/tmp/test.pdf")
    metadata = DocumentMetadata(
        file_path=fp,
        page_count=page_count,
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
        for i in range(page_count)
    ]
    return DocumentModel(
        file_path=fp,
        doc_handle=MagicMock(),
        metadata=metadata,
        pages=pages,
    )


def _make_presenter_and_window() -> tuple[
    AnnotationPresenter, TabManager, AnnotationEngine, MainWindow
]:
    tab_widget = QTabWidget()
    recent_files = MagicMock()
    tm = TabManager(tab_widget=tab_widget, recent_files=recent_files)
    engine = AnnotationEngine()
    toolbar = AnnotationToolbar()
    presenter = AnnotationPresenter(tab_manager=tm, engine=engine, toolbar=toolbar)
    window = MainWindow()
    return presenter, tm, engine, window


class TestCopyWithSelection:
    def test_ctrl_c_copies_text(self) -> None:
        presenter, tm, engine, window = _make_presenter_and_window()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)

        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0

        # Wire signal
        window.copy_requested.connect(presenter.copy_selected_text)

        with patch.object(engine, "extract_text_in_rects", return_value="Hello world"):
            window._copy_action.setEnabled(True)
            window._copy_action.trigger()
            clipboard = QApplication.clipboard()
            assert clipboard is not None
            assert clipboard.text() == "Hello world"

    def test_status_bar_shows_copied_message(self) -> None:
        presenter, tm, engine, window = _make_presenter_and_window()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)

        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0

        # Wire signals as KPdfApp would
        window.copy_requested.connect(presenter.copy_selected_text)
        presenter.text_copied.connect(lambda _: window.update_status_message("Copied to clipboard"))

        with patch.object(engine, "extract_text_in_rects", return_value="Test text"):
            window._copy_action.setEnabled(True)
            window._copy_action.trigger()
            # Status bar should show the message
            assert window._status_bar.currentMessage() == "Copied to clipboard"


class TestCopyDisabledWithoutSelection:
    def test_copy_grayed_without_selection(self) -> None:
        _presenter, _tm, _engine, window = _make_presenter_and_window()
        assert not window._copy_action.isEnabled()

    def test_copy_enabled_on_selection(self) -> None:
        presenter, _tm, _engine, window = _make_presenter_and_window()

        # Wire selection_changed -> set_copy_enabled
        presenter.selection_changed.connect(window.set_copy_enabled)

        presenter.on_text_selected(0, [(10.0, 20.0, 80.0, 30.0)])
        assert window._copy_action.isEnabled()

    def test_copy_disabled_on_clear(self) -> None:
        presenter, tm, _engine, window = _make_presenter_and_window()
        mock_viewport = MagicMock()
        mock_global = MagicMock()
        mock_global.x.return_value = 100
        mock_global.y.return_value = 200
        mock_viewport.mapToGlobal.return_value = mock_global
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)

        presenter.selection_changed.connect(window.set_copy_enabled)

        presenter.on_text_selected(0, [(10.0, 20.0, 80.0, 30.0)])
        assert window._copy_action.isEnabled()

        presenter.set_tool_mode(ToolMode.NONE)
        assert not window._copy_action.isEnabled()


class TestSelectAllIntegration:
    def test_select_all_selects_text(self) -> None:
        presenter, tm, engine, window = _make_presenter_and_window()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        type(mock_dp).current_page = property(lambda _: 0)
        tm.get_active_presenter = MagicMock(return_value=mock_dp)
        mock_viewport = MagicMock()
        mock_global = MagicMock()
        mock_global.x.return_value = 100
        mock_global.y.return_value = 200
        mock_viewport.mapToGlobal.return_value = mock_global
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)

        # Wire signal
        window.select_all_requested.connect(presenter.select_all_text)
        presenter.selection_changed.connect(window.set_copy_enabled)

        fake_words = [
            (10.0, 20.0, 50.0, 30.0, "Hello", 0, 0, 0),
            (55.0, 20.0, 100.0, 30.0, "world", 0, 0, 1),
        ]
        with patch.object(engine, "get_text_words", return_value=fake_words):
            window._select_all_action.trigger()

        assert presenter.has_selection
        assert len(presenter._selected_rects) == 2
        assert window._copy_action.isEnabled()

    def test_select_all_then_copy(self) -> None:
        presenter, tm, engine, window = _make_presenter_and_window()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        type(mock_dp).current_page = property(lambda _: 0)
        tm.get_active_presenter = MagicMock(return_value=mock_dp)
        mock_viewport = MagicMock()
        mock_global = MagicMock()
        mock_global.x.return_value = 100
        mock_global.y.return_value = 200
        mock_viewport.mapToGlobal.return_value = mock_global
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)

        # Wire signals
        window.select_all_requested.connect(presenter.select_all_text)
        window.copy_requested.connect(presenter.copy_selected_text)
        presenter.selection_changed.connect(window.set_copy_enabled)

        fake_words = [
            (10.0, 20.0, 50.0, 30.0, "Hello", 0, 0, 0),
            (55.0, 20.0, 100.0, 30.0, "world", 0, 0, 1),
        ]
        with (
            patch.object(engine, "get_text_words", return_value=fake_words),
            patch.object(engine, "extract_text_in_rects", return_value="Hello world"),
        ):
            window._select_all_action.trigger()
            window._copy_action.trigger()

        clipboard = QApplication.clipboard()
        assert clipboard is not None
        assert clipboard.text() == "Hello world"
