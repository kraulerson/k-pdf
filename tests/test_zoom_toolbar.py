"""Tests for ZoomToolBar widget."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from k_pdf.core.zoom_model import FitMode
from k_pdf.views.zoom_toolbar import ZoomToolBar

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestZoomToolBarConstruction:
    def test_creates_without_error(self) -> None:
        toolbar = ZoomToolBar()
        assert toolbar is not None

    def test_has_zoom_changed_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)

    def test_has_fit_page_requested_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.fit_page_requested.connect(spy)

    def test_has_fit_width_requested_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.fit_width_requested.connect(spy)

    def test_has_rotate_cw_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.rotate_cw_requested.connect(spy)

    def test_has_rotate_ccw_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.rotate_ccw_requested.connect(spy)


class TestZoomToolBarSlider:
    def test_slider_emits_zoom_changed(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        # Simulate slider move (slider range 10-300 representing 10%-300%)
        toolbar._slider.setValue(200)
        spy.assert_called()
        zoom_val = spy.call_args[0][0]
        assert abs(zoom_val - 2.0) < 0.01

    def test_set_zoom_updates_slider_without_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        toolbar.set_zoom(1.5)
        # set_zoom should NOT re-emit zoom_changed
        spy.assert_not_called()
        # Slider should reflect the new value
        assert toolbar._slider.value() == 150

    def test_set_zoom_updates_percentage_text(self) -> None:
        toolbar = ZoomToolBar()
        toolbar.set_zoom(1.5)
        assert "150" in toolbar._percent_input.text()


class TestZoomToolBarPercentageInput:
    def test_valid_percentage_emits_zoom_changed(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        toolbar._percent_input.setText("200")
        toolbar._percent_input.editingFinished.emit()
        spy.assert_called()
        assert abs(spy.call_args[0][0] - 2.0) < 0.01

    def test_invalid_percentage_ignored(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        toolbar._percent_input.setText("abc")
        toolbar._percent_input.editingFinished.emit()
        spy.assert_not_called()

    def test_out_of_range_percentage_clamped(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        toolbar._percent_input.setText("5000")
        toolbar._percent_input.editingFinished.emit()
        spy.assert_called()
        assert spy.call_args[0][0] == 3.0  # 300% max


class TestZoomToolBarPresetDropdown:
    def test_fit_page_emits_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.fit_page_requested.connect(spy)
        # Find "Fit Page" index in dropdown
        idx = -1
        for i in range(toolbar._preset_combo.count()):
            if "Fit Page" in toolbar._preset_combo.itemText(i):
                idx = i
                break
        assert idx >= 0
        toolbar._preset_combo.setCurrentIndex(idx)
        spy.assert_called_once()

    def test_fit_width_emits_signal(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.fit_width_requested.connect(spy)
        idx = -1
        for i in range(toolbar._preset_combo.count()):
            if "Fit Width" in toolbar._preset_combo.itemText(i):
                idx = i
                break
        assert idx >= 0
        toolbar._preset_combo.setCurrentIndex(idx)
        spy.assert_called_once()

    def test_numeric_preset_emits_zoom_changed(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        # Find "200%" preset
        idx = -1
        for i in range(toolbar._preset_combo.count()):
            if "200%" in toolbar._preset_combo.itemText(i):
                idx = i
                break
        assert idx >= 0
        toolbar._preset_combo.setCurrentIndex(idx)
        spy.assert_called()
        assert abs(spy.call_args[0][0] - 2.0) < 0.01

    def test_actual_size_preset(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        idx = -1
        for i in range(toolbar._preset_combo.count()):
            if "100%" in toolbar._preset_combo.itemText(i):
                idx = i
                break
        assert idx >= 0
        toolbar._preset_combo.setCurrentIndex(idx)
        spy.assert_called()
        assert abs(spy.call_args[0][0] - 1.0) < 0.01


class TestZoomToolBarRotation:
    def test_rotate_cw_emits(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.rotate_cw_requested.connect(spy)
        toolbar._rotate_cw_btn.click()
        spy.assert_called_once()

    def test_rotate_ccw_emits(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.rotate_ccw_requested.connect(spy)
        toolbar._rotate_ccw_btn.click()
        spy.assert_called_once()


class TestZoomToolBarZoomButtons:
    def test_zoom_in_button_emits(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        toolbar.set_zoom(1.0)  # Reset to known state
        toolbar._zoom_in_btn.click()
        spy.assert_called()
        # Should zoom in by some increment
        assert spy.call_args[0][0] > 1.0

    def test_zoom_out_button_emits(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.zoom_changed.connect(spy)
        toolbar.set_zoom(1.0)
        toolbar._zoom_out_btn.click()
        spy.assert_called()
        assert spy.call_args[0][0] < 1.0


class TestZoomToolBarSetFitMode:
    def test_set_fit_mode_page(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.fit_page_requested.connect(spy)
        toolbar.set_fit_mode(FitMode.PAGE)
        # Should update combo box without re-emitting signal
        spy.assert_not_called()

    def test_set_fit_mode_width(self) -> None:
        toolbar = ZoomToolBar()
        spy = MagicMock()
        toolbar.fit_width_requested.connect(spy)
        toolbar.set_fit_mode(FitMode.WIDTH)
        spy.assert_not_called()

    def test_set_fit_mode_none(self) -> None:
        toolbar = ZoomToolBar()
        toolbar.set_fit_mode(FitMode.NONE)
        # Should not select a fit preset
        text = toolbar._preset_combo.currentText()
        assert "Fit" not in text
