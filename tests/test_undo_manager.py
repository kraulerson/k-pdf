"""Tests for UndoManager and UndoAction."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from k_pdf.core.undo_manager import UndoAction, UndoManager

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_action(desc: str = "test action") -> tuple[UndoAction, MagicMock, MagicMock]:
    """Create an UndoAction with mock callables."""
    undo_fn = MagicMock()
    redo_fn = MagicMock()
    action = UndoAction(description=desc, undo_fn=undo_fn, redo_fn=redo_fn)
    return action, undo_fn, redo_fn


class TestUndoAction:
    def test_construction(self) -> None:
        undo_fn = MagicMock()
        redo_fn = MagicMock()
        action = UndoAction(description="Add Highlight", undo_fn=undo_fn, redo_fn=redo_fn)
        assert action.description == "Add Highlight"
        assert action.undo_fn is undo_fn
        assert action.redo_fn is redo_fn

    def test_fields_are_accessible(self) -> None:
        action, undo_fn, redo_fn = _make_action("Delete Page")
        assert action.description == "Delete Page"
        action.undo_fn()
        undo_fn.assert_called_once()
        action.redo_fn()
        redo_fn.assert_called_once()


class TestUndoManagerInitialState:
    def test_empty_stacks(self) -> None:
        mgr = UndoManager()
        assert not mgr.can_undo
        assert not mgr.can_redo

    def test_descriptions_empty(self) -> None:
        mgr = UndoManager()
        assert mgr.undo_description == ""
        assert mgr.redo_description == ""

    def test_default_max_size(self) -> None:
        mgr = UndoManager()
        assert mgr.max_size == 50

    def test_custom_max_size(self) -> None:
        mgr = UndoManager(max_size=10)
        assert mgr.max_size == 10


class TestUndoManagerPush:
    def test_push_makes_can_undo_true(self) -> None:
        mgr = UndoManager()
        action, _, _ = _make_action()
        mgr.push(action)
        assert mgr.can_undo

    def test_push_sets_undo_description(self) -> None:
        mgr = UndoManager()
        action, _, _ = _make_action("Add Highlight")
        mgr.push(action)
        assert mgr.undo_description == "Add Highlight"

    def test_push_clears_redo_stack(self) -> None:
        mgr = UndoManager()
        action1, _, _ = _make_action("first")
        action2, _, _ = _make_action("second")
        mgr.push(action1)
        mgr.undo()  # moves action1 to redo
        assert mgr.can_redo
        mgr.push(action2)  # should clear redo
        assert not mgr.can_redo

    def test_push_trims_to_max_size(self) -> None:
        mgr = UndoManager(max_size=3)
        for i in range(5):
            action, _, _ = _make_action(f"action {i}")
            mgr.push(action)
        # Only last 3 should remain
        count = 0
        while mgr.can_undo:
            mgr.undo()
            count += 1
        assert count == 3

    def test_push_emits_state_changed(self) -> None:
        mgr = UndoManager()
        signal_spy = MagicMock()
        mgr.state_changed.connect(signal_spy)
        action, _, _ = _make_action()
        mgr.push(action)
        signal_spy.assert_called_once()


class TestUndoManagerUndo:
    def test_undo_calls_undo_fn(self) -> None:
        mgr = UndoManager()
        action, undo_fn, _ = _make_action()
        mgr.push(action)
        mgr.undo()
        undo_fn.assert_called_once()

    def test_undo_moves_to_redo_stack(self) -> None:
        mgr = UndoManager()
        action, _, _ = _make_action("test")
        mgr.push(action)
        mgr.undo()
        assert not mgr.can_undo
        assert mgr.can_redo
        assert mgr.redo_description == "test"

    def test_undo_empty_is_noop(self) -> None:
        mgr = UndoManager()
        mgr.undo()  # should not raise
        assert not mgr.can_undo
        assert not mgr.can_redo

    def test_undo_emits_state_changed(self) -> None:
        mgr = UndoManager()
        action, _, _ = _make_action()
        mgr.push(action)
        signal_spy = MagicMock()
        mgr.state_changed.connect(signal_spy)
        mgr.undo()
        signal_spy.assert_called_once()

    def test_multiple_undos(self) -> None:
        mgr = UndoManager()
        actions = []
        for i in range(3):
            action, undo_fn, _ = _make_action(f"action {i}")
            actions.append((action, undo_fn))
            mgr.push(action)

        # Undo all three in reverse order
        for i in range(2, -1, -1):
            assert mgr.undo_description == f"action {i}"
            mgr.undo()
            actions[i][1].assert_called_once()

        assert not mgr.can_undo


class TestUndoManagerRedo:
    def test_redo_calls_redo_fn(self) -> None:
        mgr = UndoManager()
        action, _, redo_fn = _make_action()
        mgr.push(action)
        mgr.undo()
        mgr.redo()
        redo_fn.assert_called_once()

    def test_redo_moves_back_to_undo_stack(self) -> None:
        mgr = UndoManager()
        action, _, _ = _make_action("test")
        mgr.push(action)
        mgr.undo()
        mgr.redo()
        assert mgr.can_undo
        assert not mgr.can_redo
        assert mgr.undo_description == "test"

    def test_redo_empty_is_noop(self) -> None:
        mgr = UndoManager()
        mgr.redo()  # should not raise
        assert not mgr.can_undo
        assert not mgr.can_redo

    def test_redo_emits_state_changed(self) -> None:
        mgr = UndoManager()
        action, _, _ = _make_action()
        mgr.push(action)
        mgr.undo()
        signal_spy = MagicMock()
        mgr.state_changed.connect(signal_spy)
        mgr.redo()
        signal_spy.assert_called_once()

    def test_undo_redo_cycle(self) -> None:
        mgr = UndoManager()
        action, undo_fn, redo_fn = _make_action()
        mgr.push(action)
        mgr.undo()
        mgr.redo()
        mgr.undo()
        mgr.redo()
        assert undo_fn.call_count == 2
        assert redo_fn.call_count == 2


class TestUndoManagerClear:
    def test_clear_empties_both_stacks(self) -> None:
        mgr = UndoManager()
        action1, _, _ = _make_action("a")
        action2, _, _ = _make_action("b")
        mgr.push(action1)
        mgr.push(action2)
        mgr.undo()
        assert mgr.can_undo
        assert mgr.can_redo
        mgr.clear()
        assert not mgr.can_undo
        assert not mgr.can_redo

    def test_clear_emits_state_changed(self) -> None:
        mgr = UndoManager()
        action, _, _ = _make_action()
        mgr.push(action)
        signal_spy = MagicMock()
        mgr.state_changed.connect(signal_spy)
        mgr.clear()
        signal_spy.assert_called_once()
