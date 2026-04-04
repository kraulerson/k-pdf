"""Zoom toolbar -- slider, percentage input, presets, and rotation buttons.

Layout: [Rotate CCW] [Rotate CW] | [Zoom Out] [Slider] [Percentage] [Zoom In] | [Presets]
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QLineEdit,
    QPushButton,
    QSlider,
    QToolBar,
    QWidget,
)

from k_pdf.core.zoom_model import FitMode

logger = logging.getLogger("k_pdf.views.zoom_toolbar")

# Slider range: 10 to 300 (representing 10% to 300%)
_SLIDER_MIN = 10
_SLIDER_MAX = 300

# Zoom step for +/- buttons and Ctrl+scroll
_ZOOM_STEP = 0.1

# Preset items: (display_text, action_type, value)
# action_type: "fit_page", "fit_width", "zoom"
_PRESETS: list[tuple[str, str, float]] = [
    ("--", "none", 0.0),
    ("Fit Page", "fit_page", 0.0),
    ("Fit Width", "fit_width", 0.0),
    ("Actual Size (100%)", "zoom", 1.0),
    ("50%", "zoom", 0.5),
    ("75%", "zoom", 0.75),
    ("150%", "zoom", 1.5),
    ("200%", "zoom", 2.0),
]


class ZoomToolBar(QToolBar):
    """Toolbar with zoom and rotation controls."""

    zoom_changed = Signal(float)
    fit_page_requested = Signal()
    fit_width_requested = Signal()
    rotate_cw_requested = Signal()
    rotate_ccw_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the zoom toolbar with all controls."""
        super().__init__("Zoom", parent)
        self.setObjectName("zoom_toolbar")
        self.setMovable(False)

        self._updating = False  # Guard against signal loops

        # --- Rotation buttons ---
        self._rotate_ccw_btn = QPushButton("Rotate CCW")
        self._rotate_ccw_btn.setToolTip("Rotate Counter-Clockwise (Ctrl+Shift+R)")
        self._rotate_ccw_btn.clicked.connect(self.rotate_ccw_requested.emit)
        self.addWidget(self._rotate_ccw_btn)

        self._rotate_cw_btn = QPushButton("Rotate CW")
        self._rotate_cw_btn.setToolTip("Rotate Clockwise (Ctrl+R)")
        self._rotate_cw_btn.clicked.connect(self.rotate_cw_requested.emit)
        self.addWidget(self._rotate_cw_btn)

        self.addSeparator()

        # --- Zoom out button ---
        self._zoom_out_btn = QPushButton("-")
        self._zoom_out_btn.setToolTip("Zoom Out (Ctrl+-)")
        self._zoom_out_btn.setFixedWidth(30)
        self._zoom_out_btn.clicked.connect(self._on_zoom_out)
        self.addWidget(self._zoom_out_btn)

        # --- Zoom slider ---
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(_SLIDER_MIN, _SLIDER_MAX)
        self._slider.setValue(100)
        self._slider.setFixedWidth(150)
        self._slider.setToolTip("Zoom level")
        self._slider.valueChanged.connect(self._on_slider_changed)
        self.addWidget(self._slider)

        # --- Percentage input ---
        self._percent_input = QLineEdit("100%")
        self._percent_input.setFixedWidth(60)
        self._percent_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._percent_input.setToolTip("Zoom percentage (10%-300%)")
        self._percent_input.editingFinished.connect(self._on_percent_edited)
        self.addWidget(self._percent_input)

        # --- Zoom in button ---
        self._zoom_in_btn = QPushButton("+")
        self._zoom_in_btn.setToolTip("Zoom In (Ctrl+=)")
        self._zoom_in_btn.setFixedWidth(30)
        self._zoom_in_btn.clicked.connect(self._on_zoom_in)
        self.addWidget(self._zoom_in_btn)

        self.addSeparator()

        # --- Preset dropdown ---
        self._preset_combo = QComboBox()
        self._preset_combo.setToolTip("Zoom presets")
        for text, _, _ in _PRESETS:
            self._preset_combo.addItem(text)
        self._preset_combo.setCurrentIndex(0)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        self.addWidget(self._preset_combo)

        # Track current zoom for +/- button calculations
        self._current_zoom = 1.0

    def set_zoom(self, zoom: float) -> None:
        """Update slider and percentage display without re-emitting signals.

        Args:
            zoom: The zoom level (1.0 = 100%).
        """
        self._updating = True
        self._current_zoom = zoom
        self._slider.setValue(int(zoom * 100))
        self._percent_input.setText(f"{int(zoom * 100)}%")
        self._updating = False

    def set_rotation(self, rotation: int) -> None:
        """Update rotation display if shown.

        Args:
            rotation: Rotation in degrees (0, 90, 180, 270).
        """
        # Rotation state is visual only -- buttons always emit signals
        # No persistent display to update in current design

    def set_fit_mode(self, mode: FitMode) -> None:
        """Update dropdown to reflect active fit mode without re-emitting.

        Args:
            mode: The active fit mode.
        """
        self._updating = True
        if mode is FitMode.PAGE:
            for i, (_text, action, _) in enumerate(_PRESETS):
                if action == "fit_page":
                    self._preset_combo.setCurrentIndex(i)
                    break
        elif mode is FitMode.WIDTH:
            for i, (_text, action, _) in enumerate(_PRESETS):
                if action == "fit_width":
                    self._preset_combo.setCurrentIndex(i)
                    break
        else:
            self._preset_combo.setCurrentIndex(0)  # "--" (no preset)
        self._updating = False

    # --- Internal signal handlers ---

    def _on_slider_changed(self, value: int) -> None:
        """Handle slider value change."""
        if self._updating:
            return
        zoom = value / 100.0
        self._current_zoom = zoom
        self._updating = True
        self._percent_input.setText(f"{value}%")
        self._updating = False
        self.zoom_changed.emit(zoom)

    def _on_percent_edited(self) -> None:
        """Handle percentage input editing finished."""
        if self._updating:
            return
        text = self._percent_input.text().strip().rstrip("%")
        try:
            percent = float(text)
        except ValueError:
            # Restore current value on invalid input
            self._percent_input.setText(f"{int(self._current_zoom * 100)}%")
            return

        zoom = percent / 100.0
        # Clamp to valid range
        zoom = max(0.1, min(3.0, zoom))
        self._current_zoom = zoom

        self._updating = True
        self._slider.setValue(int(zoom * 100))
        self._percent_input.setText(f"{int(zoom * 100)}%")
        self._updating = False
        self.zoom_changed.emit(zoom)

    def _on_preset_selected(self, index: int) -> None:
        """Handle preset dropdown selection."""
        if self._updating or index < 0 or index >= len(_PRESETS):
            return

        _, action, value = _PRESETS[index]
        if action == "fit_page":
            self.fit_page_requested.emit()
        elif action == "fit_width":
            self.fit_width_requested.emit()
        elif action == "zoom" and value > 0:
            self._current_zoom = value
            self._updating = True
            self._slider.setValue(int(value * 100))
            self._percent_input.setText(f"{int(value * 100)}%")
            self._updating = False
            self.zoom_changed.emit(value)

    def _on_zoom_in(self) -> None:
        """Zoom in by one step."""
        new_zoom = min(3.0, self._current_zoom + _ZOOM_STEP)
        self._current_zoom = new_zoom
        self._updating = True
        self._slider.setValue(int(new_zoom * 100))
        self._percent_input.setText(f"{int(new_zoom * 100)}%")
        self._updating = False
        self.zoom_changed.emit(new_zoom)

    def _on_zoom_out(self) -> None:
        """Zoom out by one step."""
        new_zoom = max(0.1, self._current_zoom - _ZOOM_STEP)
        self._current_zoom = new_zoom
        self._updating = True
        self._slider.setValue(int(new_zoom * 100))
        self._percent_input.setText(f"{int(new_zoom * 100)}%")
        self._updating = False
        self.zoom_changed.emit(new_zoom)
