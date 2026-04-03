"""Tests for AnnotationPresenter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QTabWidget

from k_pdf.core.annotation_model import AnnotationType, ToolMode
from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.presenters.annotation_presenter import AnnotationPresenter
from k_pdf.presenters.tab_manager import TabManager
from k_pdf.services.annotation_engine import AnnotationEngine
from k_pdf.views.annotation_toolbar import AnnotationToolbar
from k_pdf.views.note_editor import NoteEditor

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


def _make_tab_manager() -> TabManager:
    tab_widget = QTabWidget()
    recent_files = MagicMock()
    return TabManager(tab_widget=tab_widget, recent_files=recent_files)


def _make_presenter(
    tab_manager: TabManager | None = None,
) -> tuple[AnnotationPresenter, TabManager, AnnotationEngine, AnnotationToolbar]:
    tm = tab_manager or _make_tab_manager()
    engine = AnnotationEngine()
    toolbar = AnnotationToolbar()
    presenter = AnnotationPresenter(
        tab_manager=tm,
        engine=engine,
        toolbar=toolbar,
    )
    return presenter, tm, engine, toolbar


class TestAnnotationPresenterInit:
    def test_creates_without_error(self) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        assert presenter is not None

    def test_initial_selection_mode_false(self) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        assert presenter._selection_mode is False

    def test_initial_selected_quads_empty(self) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        assert presenter._selected_rects == []

    def test_initial_selected_page_negative(self) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        assert presenter._selected_page == -1


class TestSetSelectionMode:
    def test_toggle_on(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter.set_selection_mode(True)
        assert presenter._selection_mode is True
        mock_viewport.set_tool_mode.assert_called_with(ToolMode.TEXT_SELECT)

    def test_toggle_off(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter.set_selection_mode(True)
        presenter.set_selection_mode(False)
        assert presenter._selection_mode is False

    def test_no_viewport_no_crash(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        tm.get_active_viewport = MagicMock(return_value=None)
        presenter.set_selection_mode(True)
        assert presenter._selection_mode is True


class TestOnTextSelected:
    def test_stores_selection(self) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        rects = [(10.0, 20.0, 80.0, 30.0), (10.0, 32.0, 80.0, 42.0)]
        presenter.on_text_selected(0, rects)
        assert presenter._selected_page == 0
        assert presenter._selected_rects == rects

    def test_shows_toolbar(self, qtbot: object) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        mock_viewport.mapToGlobal.return_value = MagicMock(
            x=MagicMock(return_value=100), y=MagicMock(return_value=200)
        )
        rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter.on_text_selected(0, rects)
        assert presenter._selected_page == 0

    def test_empty_rects_does_not_store(self) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        presenter.on_text_selected(0, [])
        assert presenter._selected_page == -1
        assert presenter._selected_rects == []


class TestCreateAnnotation:
    def test_calls_engine_highlight(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)

        # Simulate selection
        rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_rects = rects
        presenter._selected_page = 0

        with (
            patch.object(engine, "rects_to_quads", return_value=["quad1"]) as mock_r2q,
            patch.object(engine, "add_highlight", return_value=MagicMock()) as mock_add,
        ):
            presenter.create_annotation(AnnotationType.HIGHLIGHT, (1.0, 1.0, 0.0))
            mock_r2q.assert_called_once_with(rects)
            mock_add.assert_called_once_with(model.doc_handle, 0, ["quad1"], (1.0, 1.0, 0.0))

    def test_calls_engine_underline(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)
        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0

        with (
            patch.object(engine, "rects_to_quads", return_value=["quad1"]),
            patch.object(engine, "add_underline", return_value=MagicMock()) as mock_add,
        ):
            presenter.create_annotation(AnnotationType.UNDERLINE, (1.0, 0.0, 0.0))
            mock_add.assert_called_once()

    def test_calls_engine_strikeout(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)
        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0

        with (
            patch.object(engine, "rects_to_quads", return_value=["quad1"]),
            patch.object(engine, "add_strikeout", return_value=MagicMock()) as mock_add,
        ):
            presenter.create_annotation(AnnotationType.STRIKETHROUGH, (1.0, 0.0, 0.0))
            mock_add.assert_called_once()

    def test_sets_dirty_flag(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)
        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0

        with (
            patch.object(engine, "rects_to_quads", return_value=["quad1"]),
            patch.object(engine, "add_highlight", return_value=MagicMock()),
        ):
            presenter.create_annotation(AnnotationType.HIGHLIGHT, (1.0, 1.0, 0.0))
            assert model.dirty is True

    def test_no_selection_is_noop(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)
        # No selection stored
        with patch.object(engine, "add_highlight") as mock_add:
            presenter.create_annotation(AnnotationType.HIGHLIGHT, (1.0, 1.0, 0.0))
            mock_add.assert_not_called()


class TestDeleteAnnotation:
    def test_calls_engine_delete(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)

        mock_annot = MagicMock()
        with patch.object(engine, "delete_annotation") as mock_del:
            presenter.delete_annotation(0, mock_annot)
            mock_del.assert_called_once_with(model.doc_handle, 0, mock_annot)

    def test_sets_dirty_flag(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_presenter = MagicMock()
        model = _make_model()
        mock_presenter.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_presenter)

        with patch.object(engine, "delete_annotation"):
            presenter.delete_annotation(0, MagicMock())
            assert model.dirty is True


class TestOnTabSwitched:
    def test_clears_selection(self) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0
        presenter.on_tab_switched("some-session-id")
        assert presenter._selected_rects == []
        assert presenter._selected_page == -1

    def test_hides_toolbar(self) -> None:
        presenter, _tm, _engine, toolbar = _make_presenter()
        toolbar.show()
        presenter.on_tab_switched("some-session-id")
        assert not toolbar.isVisible()


class TestToolMode:
    def test_enum_has_none(self) -> None:
        assert ToolMode.NONE.value == 0

    def test_enum_has_text_select(self) -> None:
        assert ToolMode.TEXT_SELECT.value == 1

    def test_enum_has_sticky_note(self) -> None:
        assert ToolMode.STICKY_NOTE.value == 2

    def test_enum_has_text_box(self) -> None:
        assert ToolMode.TEXT_BOX.value == 3


class TestSetToolMode:
    def test_sets_sticky_note_mode(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter.set_tool_mode(ToolMode.STICKY_NOTE)
        assert presenter._tool_mode is ToolMode.STICKY_NOTE

    def test_sets_text_box_mode(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter.set_tool_mode(ToolMode.TEXT_BOX)
        assert presenter._tool_mode is ToolMode.TEXT_BOX

    def test_emits_tool_mode_changed(self, qtbot: object) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        with qtbot.waitSignal(presenter.tool_mode_changed, timeout=1000) as blocker:  # type: ignore[union-attr]
            presenter.set_tool_mode(ToolMode.STICKY_NOTE)
        assert blocker.args == [2]

    def test_set_selection_mode_shim_true(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter.set_selection_mode(True)
        assert presenter._tool_mode is ToolMode.TEXT_SELECT

    def test_set_selection_mode_shim_false(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter.set_selection_mode(True)
        presenter.set_selection_mode(False)
        assert presenter._tool_mode is ToolMode.NONE


class TestOnNotePlaced:
    def test_opens_note_editor(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        mock_viewport.mapToGlobal.return_value = MagicMock(
            x=MagicMock(return_value=100), y=MagicMock(return_value=200)
        )
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        presenter.on_note_placed(0, (100.0, 100.0))
        assert note_editor._mode == "sticky_note"
        assert note_editor._target_page == 0


class TestOnTextboxDrawn:
    def test_opens_note_editor(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        mock_viewport.mapToGlobal.return_value = MagicMock(
            x=MagicMock(return_value=100), y=MagicMock(return_value=200)
        )
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        presenter.on_textbox_drawn(0, (100.0, 200.0, 300.0, 250.0))
        assert note_editor._mode == "text_box"
        assert note_editor._target_page == 0


class TestOnEditingFinished:
    def test_creates_sticky_note(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)

        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        note_editor._mode = "sticky_note"
        note_editor._target_page = 0
        note_editor._target_annot = None
        presenter._pending_point = (100.0, 100.0)

        with patch.object(engine, "add_sticky_note", return_value=MagicMock()) as mock_add:
            presenter._on_editing_finished("My note")
            mock_add.assert_called_once_with(model.doc_handle, 0, (100.0, 100.0), "My note")

    def test_creates_text_box(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)

        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        note_editor._mode = "text_box"
        note_editor._target_page = 0
        note_editor._target_annot = None
        presenter._pending_rect = (100.0, 200.0, 300.0, 250.0)

        with patch.object(engine, "add_text_box", return_value=MagicMock()) as mock_add:
            presenter._on_editing_finished("Box text")
            mock_add.assert_called_once_with(
                model.doc_handle, 0, (100.0, 200.0, 300.0, 250.0), "Box text"
            )

    def test_sets_dirty_flag(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)

        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        note_editor._mode = "sticky_note"
        note_editor._target_page = 0
        note_editor._target_annot = None
        presenter._pending_point = (100.0, 100.0)

        with patch.object(engine, "add_sticky_note", return_value=MagicMock()):
            presenter._on_editing_finished("Note")
            assert model.dirty is True

    def test_resets_tool_mode(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)

        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        note_editor._mode = "sticky_note"
        note_editor._target_page = 0
        note_editor._target_annot = None
        presenter._pending_point = (100.0, 100.0)
        presenter._tool_mode = ToolMode.STICKY_NOTE

        with patch.object(engine, "add_sticky_note", return_value=MagicMock()):
            presenter._on_editing_finished("Note")
            assert presenter._tool_mode is ToolMode.NONE

    def test_updates_existing_annotation(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)

        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        mock_annot = MagicMock()
        note_editor._mode = "sticky_note"
        note_editor._target_page = 0
        note_editor._target_annot = mock_annot

        with patch.object(engine, "update_annotation_content") as mock_update:
            presenter._on_editing_finished("Updated content")
            mock_update.assert_called_once_with(model.doc_handle, 0, mock_annot, "Updated content")


class TestOnAnnotationDoubleClicked:
    def test_opens_editor_with_existing_content(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)
        mock_viewport = MagicMock()
        mock_viewport.mapToGlobal.return_value = MagicMock(
            x=MagicMock(return_value=100), y=MagicMock(return_value=200)
        )
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)

        note_editor = NoteEditor()
        presenter._note_editor = note_editor

        mock_annot = MagicMock()
        mock_annot.type = (0, 0)

        with patch.object(engine, "get_annotation_content", return_value="Existing"):
            presenter.on_annotation_double_clicked(0, mock_annot)
            assert note_editor._text_edit.toPlainText() == "Existing"


class TestTabSwitchCancelsEditor:
    def test_tab_switch_hides_editor_and_resets_mode(self) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        note_editor = NoteEditor()
        presenter._note_editor = note_editor
        note_editor.show()
        presenter._tool_mode = ToolMode.STICKY_NOTE
        presenter.on_tab_switched("some-session-id")
        assert not note_editor.isVisible()
        assert presenter._tool_mode is ToolMode.NONE


class TestHasSelection:
    def test_false_initially(self) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        assert presenter.has_selection is False

    def test_true_after_text_selected(self) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0
        assert presenter.has_selection is True

    def test_false_after_clear(self) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0
        presenter._clear_selection()
        assert presenter.has_selection is False


class TestCopySelectedText:
    def test_copies_text_to_clipboard(self) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)

        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0

        with patch.object(engine, "extract_text_in_rects", return_value="Hello world"):
            text = presenter.copy_selected_text()
            assert text == "Hello world"
            clipboard = QApplication.clipboard()
            assert clipboard is not None
            assert clipboard.text() == "Hello world"

    def test_returns_empty_when_no_selection(self) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        text = presenter.copy_selected_text()
        assert text == ""

    def test_emits_text_copied(self, qtbot: object) -> None:
        presenter, tm, engine, _toolbar = _make_presenter()
        mock_dp = MagicMock()
        model = _make_model()
        mock_dp.model = model
        tm.get_active_presenter = MagicMock(return_value=mock_dp)

        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0

        with patch.object(engine, "extract_text_in_rects", return_value="Hello"):
            with qtbot.waitSignal(presenter.text_copied, timeout=1000) as blocker:  # type: ignore[union-attr]
                presenter.copy_selected_text()
            assert blocker.args == ["Hello"]

    def test_no_document_returns_empty(self) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        tm.get_active_presenter = MagicMock(return_value=None)
        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0
        text = presenter.copy_selected_text()
        assert text == ""


class TestSelectionChanged:
    def test_emits_on_text_selected(self, qtbot: object) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        with qtbot.waitSignal(presenter.selection_changed, timeout=1000) as blocker:  # type: ignore[union-attr]
            presenter.on_text_selected(0, [(10.0, 20.0, 80.0, 30.0)])
        assert blocker.args == [True]

    def test_emits_false_on_clear(self, qtbot: object) -> None:
        presenter, tm, _engine, _toolbar = _make_presenter()
        mock_viewport = MagicMock()
        tm.get_active_viewport = MagicMock(return_value=mock_viewport)
        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0
        with qtbot.waitSignal(presenter.selection_changed, timeout=1000) as blocker:  # type: ignore[union-attr]
            presenter.set_tool_mode(ToolMode.NONE)
        assert blocker.args == [False]

    def test_emits_false_on_tab_switch(self, qtbot: object) -> None:
        presenter, _tm, _engine, _toolbar = _make_presenter()
        presenter._selected_rects = [(10.0, 20.0, 80.0, 30.0)]
        presenter._selected_page = 0
        with qtbot.waitSignal(presenter.selection_changed, timeout=1000) as blocker:  # type: ignore[union-attr]
            presenter.on_tab_switched("some-session-id")
        assert blocker.args == [False]
