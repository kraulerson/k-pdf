"""Tests for NoteEditor floating widget."""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from k_pdf.views.note_editor import NoteEditor

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestNoteEditorInit:
    def test_creates_without_error(self) -> None:
        editor = NoteEditor()
        assert editor is not None

    def test_has_editing_finished_signal(self) -> None:
        editor = NoteEditor()
        assert hasattr(editor, "editing_finished")

    def test_has_editing_cancelled_signal(self) -> None:
        editor = NoteEditor()
        assert hasattr(editor, "editing_cancelled")


class TestShowForNew:
    def test_clears_text(self) -> None:
        editor = NoteEditor()
        editor._text_edit.setPlainText("old text")
        editor.show_for_new("sticky_note", 0, 100, 200)
        assert editor._text_edit.toPlainText() == ""

    def test_sets_mode(self) -> None:
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        assert editor._mode == "sticky_note"

    def test_sets_page_index(self) -> None:
        editor = NoteEditor()
        editor.show_for_new("text_box", 2, 100, 200)
        assert editor._target_page == 2

    def test_target_annot_is_none(self) -> None:
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        assert editor._target_annot is None


class TestShowForExisting:
    def test_prefills_content(self) -> None:
        editor = NoteEditor()
        editor.show_for_existing("sticky_note", 0, "mock_annot", "Existing text", 100, 200)
        assert editor._text_edit.toPlainText() == "Existing text"

    def test_sets_target_annot(self) -> None:
        editor = NoteEditor()
        editor.show_for_existing("sticky_note", 0, "mock_annot", "content", 100, 200)
        assert editor._target_annot == "mock_annot"

    def test_sets_mode(self) -> None:
        editor = NoteEditor()
        editor.show_for_existing("text_box", 1, "annot", "content", 100, 200)
        assert editor._mode == "text_box"


class TestSave:
    def test_emits_editing_finished_with_content(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        editor._text_edit.setPlainText("My note")
        with qtbot.waitSignal(editor.editing_finished, timeout=1000) as blocker:
            editor._on_save()
        assert blocker.args == ["My note"]

    def test_empty_content_shows_confirmation(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        editor._text_edit.setPlainText("")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            with qtbot.waitSignal(editor.editing_finished, timeout=1000) as blocker:
                editor._on_save()
            assert blocker.args == [""]

    def test_empty_content_cancel_keeps_open(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        editor._text_edit.setPlainText("")
        editor.show()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            editor._on_save()
        assert editor.isVisible()


class TestCancel:
    def test_emits_editing_cancelled(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        editor.show()
        with qtbot.waitSignal(editor.editing_cancelled, timeout=1000):
            editor._on_cancel()

    def test_hides_widget(self) -> None:
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        editor.show()
        editor._on_cancel()
        assert not editor.isVisible()

    def test_escape_key_cancels(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        editor = NoteEditor()
        editor.show_for_new("sticky_note", 0, 100, 200)
        editor.show()
        with qtbot.waitSignal(editor.editing_cancelled, timeout=1000):
            qtbot.keyPress(editor, Qt.Key.Key_Escape)
