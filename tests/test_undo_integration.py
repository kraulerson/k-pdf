"""Integration tests for Undo/Redo wiring through KPdfApp."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.core.undo_manager import UndoAction, UndoManager

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestUndoRedoIntegration:
    def test_undo_calls_active_undo_manager(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_undo_mgr = MagicMock(spec=UndoManager)
        mock_undo_mgr.can_undo = True
        mock_undo_mgr.can_redo = False
        mock_undo_mgr.undo_description = ""
        mock_undo_mgr.redo_description = ""
        kpdf.tab_manager.get_active_undo_manager = MagicMock(  # type: ignore[method-assign]
            return_value=mock_undo_mgr,
        )

        kpdf.window.undo_requested.emit()
        mock_undo_mgr.undo.assert_called_once()
        kpdf.shutdown()

    def test_redo_calls_active_undo_manager(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        mock_undo_mgr = MagicMock(spec=UndoManager)
        mock_undo_mgr.can_undo = False
        mock_undo_mgr.can_redo = True
        mock_undo_mgr.undo_description = ""
        mock_undo_mgr.redo_description = ""
        kpdf.tab_manager.get_active_undo_manager = MagicMock(  # type: ignore[method-assign]
            return_value=mock_undo_mgr,
        )

        kpdf.window.redo_requested.emit()
        mock_undo_mgr.redo.assert_called_once()
        kpdf.shutdown()

    def test_undo_when_no_tab_is_noop(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        # No tab open -> get_active_undo_manager returns None
        kpdf.window.undo_requested.emit()  # should not raise
        kpdf.shutdown()

    def test_redo_when_no_tab_is_noop(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        kpdf.window.redo_requested.emit()  # should not raise
        kpdf.shutdown()

    def test_undo_manager_state_change_updates_menu(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        # Create a real UndoManager and wire it
        undo_mgr = UndoManager()
        kpdf.tab_manager.get_active_undo_manager = MagicMock(  # type: ignore[method-assign]
            return_value=undo_mgr,
        )
        # Connect state_changed
        kpdf._connect_undo_manager(undo_mgr)

        # Push an action -> should update menu
        undo_fn = MagicMock()
        redo_fn = MagicMock()
        action = UndoAction(description="Add Highlight", undo_fn=undo_fn, redo_fn=redo_fn)
        undo_mgr.push(action)

        assert kpdf.window._undo_action.isEnabled()
        assert not kpdf.window._redo_action.isEnabled()
        assert "Add Highlight" in kpdf.window._undo_action.text()
        kpdf.shutdown()

    def test_undo_updates_menu_state_after_undo(self) -> None:
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        undo_mgr = UndoManager()
        kpdf.tab_manager.get_active_undo_manager = MagicMock(  # type: ignore[method-assign]
            return_value=undo_mgr,
        )
        kpdf._connect_undo_manager(undo_mgr)

        action = UndoAction(description="Add Note", undo_fn=MagicMock(), redo_fn=MagicMock())
        undo_mgr.push(action)
        undo_mgr.undo()

        # After undo: can_undo=False, can_redo=True
        assert not kpdf.window._undo_action.isEnabled()
        assert kpdf.window._redo_action.isEnabled()
        assert "Add Note" in kpdf.window._redo_action.text()
        kpdf.shutdown()
