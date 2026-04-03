"""Integration tests for sticky note and text box annotation flows."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.core.annotation_model import ToolMode

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _wait_for_document(kpdf: KPdfApp, qtbot: object) -> None:
    """Wait until the active tab has a loaded document."""
    tm = kpdf.tab_manager

    def check_loaded() -> None:
        assert tm.get_active_presenter() is not None
        assert tm.get_active_presenter().model is not None  # type: ignore[union-attr]

    qtbot.waitUntil(check_loaded, timeout=10000)  # type: ignore[union-attr]


def test_place_sticky_note(annotatable_pdf: Path, qtbot: object) -> None:
    """Set sticky note mode, place note, fill content, save -- annotation exists."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None and presenter.model is not None

    ap.set_tool_mode(ToolMode.STICKY_NOTE)
    ap._pending_point = (100.0, 100.0)
    ap._note_editor._mode = "sticky_note"  # type: ignore[union-attr]
    ap._note_editor._target_page = 0  # type: ignore[union-attr]
    ap._note_editor._target_annot = None  # type: ignore[union-attr]
    ap._on_editing_finished("Test sticky note")

    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) >= 1
    assert presenter.model.dirty is True

    kpdf.shutdown()


def test_draw_text_box(annotatable_pdf: Path, qtbot: object) -> None:
    """Select Text Box tool, drag rectangle, fill content, save -- annotation exists."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None and presenter.model is not None

    ap.set_tool_mode(ToolMode.TEXT_BOX)
    ap._pending_rect = (100.0, 200.0, 300.0, 250.0)
    ap._note_editor._mode = "text_box"  # type: ignore[union-attr]
    ap._note_editor._target_page = 0  # type: ignore[union-attr]
    ap._note_editor._target_annot = None  # type: ignore[union-attr]
    ap._on_editing_finished("Text box content")

    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) >= 1

    kpdf.shutdown()


def test_edit_existing_sticky_note(annotatable_pdf: Path, qtbot: object) -> None:
    """Create sticky note, double-click to edit, save updated content."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None and presenter.model is not None

    # Create a note first
    kpdf._annotation_engine.add_sticky_note(
        presenter.model.doc_handle, 0, (100.0, 100.0), "Original"
    )
    annot = next(iter(presenter.model.doc_handle[0].annots()))

    # Simulate double-click edit
    ap.on_annotation_double_clicked(0, annot)
    assert ap._note_editor is not None
    assert ap._note_editor._text_edit.toPlainText() == "Original"

    # Update content
    ap._note_editor._target_annot = annot
    ap._on_editing_finished("Updated content")

    # Verify update
    refreshed = next(iter(presenter.model.doc_handle[0].annots()))
    content = kpdf._annotation_engine.get_annotation_content(
        presenter.model.doc_handle, 0, refreshed
    )
    assert content == "Updated content"

    kpdf.shutdown()


def test_cancel_editing(annotatable_pdf: Path, qtbot: object) -> None:
    """Place note, cancel editing -- no annotation created."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None and presenter.model is not None

    ap.set_tool_mode(ToolMode.STICKY_NOTE)
    ap._pending_point = (100.0, 100.0)
    ap._on_editing_cancelled()

    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) == 0

    kpdf.shutdown()


def test_tool_mode_resets_after_creation(annotatable_pdf: Path, qtbot: object) -> None:
    """After creating annotation, tool mode resets to NONE."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    ap.set_tool_mode(ToolMode.STICKY_NOTE)
    ap._pending_point = (100.0, 100.0)
    ap._note_editor._mode = "sticky_note"  # type: ignore[union-attr]
    ap._note_editor._target_page = 0  # type: ignore[union-attr]
    ap._note_editor._target_annot = None  # type: ignore[union-attr]
    ap._on_editing_finished("Note")

    assert ap._tool_mode is ToolMode.NONE

    kpdf.shutdown()


def test_dirty_flag_on_note_creation(annotatable_pdf: Path, qtbot: object) -> None:
    """Dirty flag set and tab title updated after note creation."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None and presenter.model is not None

    # Verify not dirty before
    assert presenter.model.dirty is False

    ap.set_tool_mode(ToolMode.STICKY_NOTE)
    ap._pending_point = (100.0, 100.0)
    ap._note_editor._mode = "sticky_note"  # type: ignore[union-attr]
    ap._note_editor._target_page = 0  # type: ignore[union-attr]
    ap._note_editor._target_annot = None  # type: ignore[union-attr]
    ap._on_editing_finished("Note")

    assert presenter.model.dirty is True

    # Process events for dirty signal propagation
    QApplication.processEvents()

    viewport = tm.get_active_viewport()
    assert viewport is not None
    idx = kpdf.window.tab_widget.indexOf(viewport)
    title = kpdf.window.tab_widget.tabText(idx)
    assert title.startswith("*")

    kpdf.shutdown()
