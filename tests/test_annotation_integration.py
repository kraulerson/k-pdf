"""Integration tests for text markup annotation flows with real PDFs."""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.core.annotation_model import AnnotationType

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


def test_create_highlight_annotation(annotatable_pdf: Path, qtbot: object) -> None:
    """Toggle selection mode, select text, create highlight -- annotation exists on page."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    # Get word rects from engine
    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    assert len(words) > 0

    # Simulate text selection: first 3 words
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:3]]
    ap.on_text_selected(0, rects)
    ap.create_annotation(AnnotationType.HIGHLIGHT, (1.0, 1.0, 0.0))

    # Verify annotation exists on page
    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) >= 1
    assert presenter.model.dirty is True

    kpdf.shutdown()


def test_create_underline_annotation(annotatable_pdf: Path, qtbot: object) -> None:
    """Same flow with underline type."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
    ap.on_text_selected(0, rects)
    ap.create_annotation(AnnotationType.UNDERLINE, (1.0, 0.0, 0.0))

    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) >= 1

    kpdf.shutdown()


def test_create_strikethrough_annotation(annotatable_pdf: Path, qtbot: object) -> None:
    """Same flow with strikethrough type."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
    ap.on_text_selected(0, rects)
    ap.create_annotation(AnnotationType.STRIKETHROUGH, (1.0, 0.0, 0.0))

    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) >= 1

    kpdf.shutdown()


def test_delete_annotation(annotatable_pdf: Path, qtbot: object) -> None:
    """Create annotation, then delete it -- annotation removed, dirty still True."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
    ap.on_text_selected(0, rects)
    ap.create_annotation(AnnotationType.HIGHLIGHT, (1.0, 1.0, 0.0))

    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) == 1

    # Delete it
    annot = annots[0]
    ap.delete_annotation(0, annot)

    annots_after = list(page.annots())
    assert len(annots_after) == 0
    # Dirty flag is still True (changes were made)
    assert presenter.model.dirty is True

    kpdf.shutdown()


def test_dirty_flag_updates_tab_title(annotatable_pdf: Path, qtbot: object) -> None:
    """Create annotation -- verify tab title starts with '*'."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    # Verify tab title does NOT start with * before annotation
    viewport = tm.get_active_viewport()
    assert viewport is not None
    idx = kpdf.window.tab_widget.indexOf(viewport)
    title_before = kpdf.window.tab_widget.tabText(idx)
    assert not title_before.startswith("*")

    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
    ap.on_text_selected(0, rects)
    ap.create_annotation(AnnotationType.HIGHLIGHT, (1.0, 1.0, 0.0))

    # Process events to let dirty_changed propagate
    QApplication.processEvents()

    title_after = kpdf.window.tab_widget.tabText(idx)
    assert title_after.startswith("*")

    kpdf.shutdown()


def test_no_text_layer_returns_empty(image_only_pdf: Path, qtbot: object) -> None:
    """Open image-only PDF -- get_text_words returns empty, no crash."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager

    tm.open_file(image_only_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    assert words == []

    kpdf.shutdown()


def test_color_picker_changes_annotation_color(annotatable_pdf: Path, qtbot: object) -> None:
    """Select text, change color to Green, Highlight -- verify annotation color is green."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None

    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
    ap.on_text_selected(0, rects)

    green = (0.0, 0.8, 0.0)
    ap.create_annotation(AnnotationType.HIGHLIGHT, green)

    page = presenter.model.doc_handle[0]
    annots = list(page.annots())
    assert len(annots) == 1
    colors = annots[0].colors
    stroke = tuple(round(c, 1) for c in colors["stroke"])
    assert stroke == green

    kpdf.shutdown()


def test_tab_switch_clears_selection(annotatable_pdf: Path, qtbot: object) -> None:
    """Select text on tab 1, switch to tab 2 -- verify selection cleared."""
    app_instance = QApplication.instance()
    assert app_instance is not None
    kpdf = KPdfApp(app_instance)
    tm = kpdf.tab_manager
    ap = kpdf.annotation_presenter

    # Open two tabs
    tm.open_file(annotatable_pdf)
    _wait_for_document(kpdf, qtbot)

    # Create a second copy for second tab
    second_pdf = annotatable_pdf.parent / "second.pdf"
    shutil.copy(annotatable_pdf, second_pdf)
    tm.open_file(second_pdf)

    def check_two_tabs() -> None:
        assert kpdf.window.tab_widget.count() == 2

    qtbot.waitUntil(check_two_tabs, timeout=10000)  # type: ignore[union-attr]

    # Switch to first tab
    kpdf.window.tab_widget.setCurrentIndex(0)
    QApplication.processEvents()

    # Select text on first tab
    presenter = tm.get_active_presenter()
    assert presenter is not None
    assert presenter.model is not None
    words = kpdf._annotation_engine.get_text_words(presenter.model.doc_handle, 0)
    rects = [(w[0], w[1], w[2], w[3]) for w in words[:2]]
    ap.on_text_selected(0, rects)
    assert ap._selected_rects == rects

    # Switch to second tab
    kpdf.window.tab_widget.setCurrentIndex(1)
    QApplication.processEvents()

    # Selection should be cleared
    assert ap._selected_rects == []
    assert ap._selected_page == -1

    kpdf.shutdown()
