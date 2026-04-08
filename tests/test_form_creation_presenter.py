"""Tests for FormCreationPresenter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
import pytest
from PySide6.QtWidgets import QTabWidget

from k_pdf.core.annotation_model import ToolMode
from k_pdf.core.form_model import FormFieldType
from k_pdf.persistence.recent_files import RecentFiles
from k_pdf.persistence.settings_db import init_db
from k_pdf.presenters.form_creation_presenter import FormCreationPresenter
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.form_engine import FormEngine


@pytest.fixture
def form_engine() -> FormEngine:
    """Return a fresh FormEngine."""
    return FormEngine()


@pytest.fixture
def tab_manager(qtbot, tmp_path: Path) -> TabManager:
    """Return a TabManager backed by a temporary SQLite database."""
    db = init_db(tmp_path / "test.db")
    recent = RecentFiles(db)
    tw = QTabWidget()
    qtbot.addWidget(tw)
    return TabManager(tab_widget=tw, recent_files=recent)


@pytest.fixture
def presenter(form_engine: FormEngine, tab_manager: TabManager) -> FormCreationPresenter:
    """Return a FormCreationPresenter wired to the test fixtures."""
    return FormCreationPresenter(
        form_engine=form_engine,
        tab_manager=tab_manager,
    )


class TestFormCreationPresenterToolMode:
    def test_set_form_text_mode(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_TEXT)
        assert presenter.tool_mode is ToolMode.FORM_TEXT
        assert presenter.pending_field_type is FormFieldType.TEXT

    def test_set_form_checkbox_mode(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_CHECKBOX)
        assert presenter.pending_field_type is FormFieldType.CHECKBOX

    def test_set_form_dropdown_mode(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_DROPDOWN)
        assert presenter.pending_field_type is FormFieldType.DROPDOWN

    def test_set_form_radio_mode(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_RADIO)
        assert presenter.pending_field_type is FormFieldType.RADIO

    def test_set_form_signature_mode(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_SIGNATURE)
        assert presenter.pending_field_type is FormFieldType.SIGNATURE

    def test_set_none_clears_pending(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_TEXT)
        presenter.set_tool_mode(ToolMode.NONE)
        assert presenter.pending_field_type is None

    def test_tool_mode_changed_emitted(self, presenter: FormCreationPresenter) -> None:
        emitted: list[int] = []
        presenter.tool_mode_changed.connect(emitted.append)
        presenter.set_tool_mode(ToolMode.FORM_CHECKBOX)
        assert emitted == [int(ToolMode.FORM_CHECKBOX)]

    def test_initial_tool_mode_is_none(self, presenter: FormCreationPresenter) -> None:
        assert presenter.tool_mode is ToolMode.NONE
        assert presenter.pending_field_type is None


class TestFormCreationPresenterCreate:
    def test_create_field_marks_dirty(
        self, presenter: FormCreationPresenter, tmp_path: Path
    ) -> None:
        path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        doc.new_page(width=612, height=792)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        mock_model = MagicMock()
        mock_model.doc_handle = doc
        mock_model.dirty = False

        mock_presenter = MagicMock()
        mock_presenter.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_presenter)

        dirty_signals: list[bool] = []
        presenter.dirty_changed.connect(dirty_signals.append)

        presenter.create_field(
            page_index=0,
            point=(100.0, 200.0),
            field_type=FormFieldType.TEXT,
            properties={"name": "test_field"},
        )

        assert mock_model.dirty is True
        assert dirty_signals == [True]
        doc.close()

    def test_create_field_emits_field_created(
        self, presenter: FormCreationPresenter, tmp_path: Path
    ) -> None:
        path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        doc.new_page(width=612, height=792)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        mock_model = MagicMock()
        mock_model.doc_handle = doc

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)

        created: list[bool] = []
        presenter.field_created.connect(lambda: created.append(True))

        presenter.create_field(
            page_index=0,
            point=(100.0, 200.0),
            field_type=FormFieldType.TEXT,
            properties={"name": "emit_test"},
        )

        assert len(created) == 1
        doc.close()

    def test_create_field_no_active_presenter_does_nothing(
        self, presenter: FormCreationPresenter
    ) -> None:
        """create_field with no active presenter is a no-op."""
        presenter._tab_manager.get_active_presenter = MagicMock(return_value=None)
        dirty_signals: list[bool] = []
        presenter.dirty_changed.connect(dirty_signals.append)
        # Should not raise
        presenter.create_field(0, (0.0, 0.0), FormFieldType.TEXT)
        assert dirty_signals == []

    def test_create_field_pushes_undo_action(
        self, presenter: FormCreationPresenter, tmp_path: Path
    ) -> None:
        path = tmp_path / "undo_test.pdf"
        doc = pymupdf.open()
        doc.new_page(width=612, height=792)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        mock_model = MagicMock()
        mock_model.doc_handle = doc

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        mock_undo = MagicMock()
        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)
        presenter._tab_manager.get_active_undo_manager = MagicMock(return_value=mock_undo)

        presenter.create_field(0, (50.0, 50.0), FormFieldType.CHECKBOX)
        mock_undo.push.assert_called_once()
        action = mock_undo.push.call_args[0][0]
        assert "Checkbox" in action.description
        doc.close()

    def test_create_field_uses_default_size_for_type(
        self, presenter: FormCreationPresenter, tmp_path: Path
    ) -> None:
        """Signature field should get a larger default rect than a checkbox."""
        path = tmp_path / "size_test.pdf"
        doc = pymupdf.open()
        doc.new_page(width=612, height=792)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        mock_model = MagicMock()
        mock_model.doc_handle = doc

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)

        presenter.create_field(0, (10.0, 10.0), FormFieldType.SIGNATURE)
        page = doc[0]
        widgets = list(page.widgets())
        assert len(widgets) == 1
        # Signature height is 60 points
        assert abs(widgets[0].rect.height - 60.0) < 1.0
        doc.close()


class TestFormCreationPresenterDelete:
    def test_delete_field_marks_dirty(
        self, presenter: FormCreationPresenter, tmp_path: Path
    ) -> None:
        path = tmp_path / "delete_test.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        # Add a widget first
        w = pymupdf.Widget()
        w.field_name = "to_delete"
        w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        w.rect = pymupdf.Rect(50, 50, 200, 70)
        w.field_value = ""
        page.add_widget(w)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        widget = next(iter(doc[0].widgets()))

        mock_model = MagicMock()
        mock_model.doc_handle = doc

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)

        dirty_signals: list[bool] = []
        presenter.dirty_changed.connect(dirty_signals.append)

        presenter.delete_field(0, widget)

        assert mock_model.dirty is True
        assert dirty_signals == [True]
        doc.close()

    def test_delete_field_emits_field_deleted(
        self, presenter: FormCreationPresenter, tmp_path: Path
    ) -> None:
        path = tmp_path / "delete_emit_test.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        w = pymupdf.Widget()
        w.field_name = "del_field"
        w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        w.rect = pymupdf.Rect(50, 50, 200, 70)
        w.field_value = ""
        page.add_widget(w)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        widget = next(iter(doc[0].widgets()))

        mock_model = MagicMock()
        mock_model.doc_handle = doc

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)

        deleted: list[bool] = []
        presenter.field_deleted.connect(lambda: deleted.append(True))

        presenter.delete_field(0, widget)
        assert len(deleted) == 1
        doc.close()

    def test_delete_field_pushes_undo_action(
        self, presenter: FormCreationPresenter, tmp_path: Path
    ) -> None:
        path = tmp_path / "delete_undo.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        w = pymupdf.Widget()
        w.field_name = "undo_del"
        w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        w.rect = pymupdf.Rect(50, 50, 200, 70)
        w.field_value = ""
        page.add_widget(w)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        widget = next(iter(doc[0].widgets()))

        mock_model = MagicMock()
        mock_model.doc_handle = doc

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        mock_undo = MagicMock()
        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)
        presenter._tab_manager.get_active_undo_manager = MagicMock(return_value=mock_undo)

        presenter.delete_field(0, widget)
        mock_undo.push.assert_called_once()
        action = mock_undo.push.call_args[0][0]
        assert "undo_del" in action.description
        doc.close()


class TestFormCreationPresenterUpdateProperties:
    def test_update_marks_dirty(self, presenter: FormCreationPresenter, tmp_path: Path) -> None:
        path = tmp_path / "update_test.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        w = pymupdf.Widget()
        w.field_name = "upd_field"
        w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        w.rect = pymupdf.Rect(50, 50, 200, 70)
        w.field_value = "old"
        page.add_widget(w)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        widget = next(iter(doc[0].widgets()))

        mock_model = MagicMock()
        mock_model.doc_handle = doc

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)

        dirty_signals: list[bool] = []
        presenter.dirty_changed.connect(dirty_signals.append)

        presenter.update_field_properties(0, widget, {"value": "new"})

        assert mock_model.dirty is True
        assert dirty_signals == [True]
        doc.close()

    def test_update_pushes_undo_action(
        self, presenter: FormCreationPresenter, tmp_path: Path
    ) -> None:
        path = tmp_path / "update_undo.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        w = pymupdf.Widget()
        w.field_name = "edit_field"
        w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        w.rect = pymupdf.Rect(50, 50, 200, 70)
        w.field_value = "original"
        page.add_widget(w)
        doc.save(str(path))
        doc.close()

        doc = pymupdf.open(str(path))
        widget = next(iter(doc[0].widgets()))

        mock_model = MagicMock()
        mock_model.doc_handle = doc

        mock_pres = MagicMock()
        mock_pres.model = mock_model

        mock_undo = MagicMock()
        presenter._tab_manager.get_active_presenter = MagicMock(return_value=mock_pres)
        presenter._tab_manager.get_active_undo_manager = MagicMock(return_value=mock_undo)

        presenter.update_field_properties(0, widget, {"name": "renamed_field"})
        mock_undo.push.assert_called_once()
        action = mock_undo.push.call_args[0][0]
        assert "edit_field" in action.description
        doc.close()


class TestFormCreationPresenterTabSwitch:
    def test_on_tab_switched_resets_tool_mode(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_TEXT)
        presenter.on_tab_switched("some-session-id")
        assert presenter.tool_mode is ToolMode.NONE
        assert presenter.pending_field_type is None

    def test_on_tab_switched_clears_pending_type(self, presenter: FormCreationPresenter) -> None:
        presenter.set_tool_mode(ToolMode.FORM_DROPDOWN)
        assert presenter.pending_field_type is FormFieldType.DROPDOWN
        presenter.on_tab_switched("another-session")
        assert presenter.pending_field_type is None
