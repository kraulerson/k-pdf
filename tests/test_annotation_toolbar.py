"""Tests for AnnotationToolbar floating widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from k_pdf.core.annotation_model import AnnotationType
from k_pdf.views.annotation_toolbar import AnnotationToolbar

_app: QApplication | None = None


def setup_module() -> None:
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestAnnotationToolbarConstruction:
    def test_creates_without_error(self) -> None:
        toolbar = AnnotationToolbar()
        assert toolbar is not None

    def test_is_frameless(self) -> None:
        toolbar = AnnotationToolbar()
        flags = toolbar.windowFlags()
        assert flags & Qt.WindowType.FramelessWindowHint

    def test_has_three_annotation_buttons(self) -> None:
        toolbar = AnnotationToolbar()
        assert toolbar._highlight_btn is not None
        assert toolbar._underline_btn is not None
        assert toolbar._strikethrough_btn is not None

    def test_has_color_picker(self) -> None:
        toolbar = AnnotationToolbar()
        assert toolbar._color_combo is not None


class TestAnnotationToolbarSignals:
    def test_highlight_button_emits_signal(self, qtbot: object) -> None:
        toolbar = AnnotationToolbar()
        with qtbot.waitSignal(toolbar.annotation_requested, timeout=1000) as blocker:  # type: ignore[union-attr]
            toolbar._highlight_btn.click()
        ann_type, _color = blocker.args
        assert ann_type is AnnotationType.HIGHLIGHT

    def test_underline_button_emits_signal(self, qtbot: object) -> None:
        toolbar = AnnotationToolbar()
        with qtbot.waitSignal(toolbar.annotation_requested, timeout=1000) as blocker:  # type: ignore[union-attr]
            toolbar._underline_btn.click()
        ann_type, _color = blocker.args
        assert ann_type is AnnotationType.UNDERLINE

    def test_strikethrough_button_emits_signal(self, qtbot: object) -> None:
        toolbar = AnnotationToolbar()
        with qtbot.waitSignal(toolbar.annotation_requested, timeout=1000) as blocker:  # type: ignore[union-attr]
            toolbar._strikethrough_btn.click()
        ann_type, _color = blocker.args
        assert ann_type is AnnotationType.STRIKETHROUGH


class TestAnnotationToolbarColor:
    def test_default_color_is_yellow(self) -> None:
        toolbar = AnnotationToolbar()
        assert toolbar.current_color == (1.0, 1.0, 0.0)

    def test_set_color_updates_picker(self) -> None:
        toolbar = AnnotationToolbar()
        toolbar.set_color((0.0, 0.8, 0.0))
        assert toolbar.current_color == (0.0, 0.8, 0.0)

    def test_color_picker_selection_changes_color(self) -> None:
        toolbar = AnnotationToolbar()
        # Select "Red" (index 1)
        toolbar._color_combo.setCurrentIndex(1)
        assert toolbar.current_color == (1.0, 0.0, 0.0)

    def test_highlight_emits_selected_color(self, qtbot: object) -> None:
        toolbar = AnnotationToolbar()
        toolbar._color_combo.setCurrentIndex(2)  # Green
        with qtbot.waitSignal(toolbar.annotation_requested, timeout=1000) as blocker:  # type: ignore[union-attr]
            toolbar._highlight_btn.click()
        _, color = blocker.args
        assert color == (0.0, 0.8, 0.0)


class TestAnnotationToolbarPosition:
    def test_show_near_sets_position(self) -> None:
        toolbar = AnnotationToolbar()
        toolbar.show_near(100, 200)
        pos = toolbar.pos()
        # Position should be near the requested coordinates
        # Exact values depend on clamping, but should not be (0, 0)
        assert pos.x() >= 0
        assert pos.y() >= 0


class TestAnnotationToolbarDismiss:
    def test_dismissed_signal_exists(self) -> None:
        toolbar = AnnotationToolbar()
        assert hasattr(toolbar, "dismissed")

    def test_hide_emits_dismissed(self, qtbot: object) -> None:
        toolbar = AnnotationToolbar()
        toolbar.show()
        with qtbot.waitSignal(toolbar.dismissed, timeout=1000):  # type: ignore[union-attr]
            toolbar.hide()
