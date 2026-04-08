"""Tests for TextEditPresenter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
import pytest
from PySide6.QtWidgets import QTabWidget

from k_pdf.core.annotation_model import ToolMode
from k_pdf.core.text_edit_model import ReplaceAllResult
from k_pdf.persistence.recent_files import RecentFiles
from k_pdf.persistence.settings_db import init_db
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.presenters.text_edit_presenter import TextEditPresenter
from k_pdf.services.text_edit_engine import TextEditEngine


@pytest.fixture
def engine() -> TextEditEngine:
    """Return a fresh TextEditEngine."""
    return TextEditEngine()


@pytest.fixture
def tab_manager(qtbot, tmp_path: Path) -> TabManager:
    """Return a TabManager backed by a temporary database."""
    db = init_db(tmp_path / "test.db")
    recent = RecentFiles(db)
    tw = QTabWidget()
    qtbot.addWidget(tw)
    return TabManager(tab_widget=tw, recent_files=recent)


@pytest.fixture
def presenter(engine: TextEditEngine, tab_manager: TabManager) -> TextEditPresenter:
    """Return a TextEditPresenter wired to the engine and tab manager."""
    return TextEditPresenter(
        text_edit_engine=engine,
        tab_manager=tab_manager,
    )


class TestTextEditPresenterToolMode:
    def test_set_text_edit_mode(self, presenter: TextEditPresenter) -> None:
        presenter.set_tool_mode(ToolMode.TEXT_EDIT)
        assert presenter.tool_mode is ToolMode.TEXT_EDIT

    def test_set_none_clears_mode(self, presenter: TextEditPresenter) -> None:
        presenter.set_tool_mode(ToolMode.TEXT_EDIT)
        presenter.set_tool_mode(ToolMode.NONE)
        assert presenter.tool_mode is ToolMode.NONE


class TestTextEditPresenterReplace:
    def test_replace_current_marks_dirty(
        self, presenter: TextEditPresenter, tmp_path: Path
    ) -> None:
        path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 100), "Hello World", fontname="helv", fontsize=12)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        mock_model = MagicMock()
        mock_model.doc_handle = doc
        mock_model.dirty = False

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)

        rects = doc[0].search_for("Hello World")
        search_rect = (rects[0].x0, rects[0].y0, rects[0].x1, rects[0].y1)

        dirty_signals: list[bool] = []
        presenter.dirty_changed.connect(dirty_signals.append)

        presenter.replace_current(0, search_rect, "Hello World", "Hi Earth")

        assert mock_model.dirty is True
        assert dirty_signals == [True]
        doc.close()

    def test_replace_current_emits_text_changed(
        self, presenter: TextEditPresenter, tmp_path: Path
    ) -> None:
        path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 100), "Hello World", fontname="helv", fontsize=12)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        mock_model = MagicMock()
        mock_model.doc_handle = doc

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)

        rects = doc[0].search_for("Hello World")
        search_rect = (rects[0].x0, rects[0].y0, rects[0].x1, rects[0].y1)

        changed: list[bool] = []
        presenter.text_changed.connect(lambda: changed.append(True))

        presenter.replace_current(0, search_rect, "Hello World", "Hi Earth")

        assert len(changed) == 1
        doc.close()


class TestTextEditPresenterReplaceAll:
    def test_replace_all_returns_result(self, presenter: TextEditPresenter, tmp_path: Path) -> None:
        path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(72, 100), "Hello World", fontname="helv", fontsize=12)
        page.insert_text(pymupdf.Point(72, 140), "Goodbye World", fontname="helv", fontsize=12)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        mock_model = MagicMock()
        mock_model.doc_handle = doc

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)

        rects = doc[0].search_for("World")
        search_results = {0: [(r.x0, r.y0, r.x1, r.y1) for r in rects]}

        result = presenter.replace_all(search_results, "World", "Earth")

        assert result is not None
        assert isinstance(result, ReplaceAllResult)
        assert result.replaced_count > 0
        doc.close()


class TestTextEditPresenterTabSwitch:
    def test_resets_on_tab_switch(self, presenter: TextEditPresenter) -> None:
        presenter.set_tool_mode(ToolMode.TEXT_EDIT)
        presenter.on_tab_switched("new-session")
        assert presenter.tool_mode is ToolMode.NONE
