"""Zoom and rotation state model.

Framework-free data layer for zoom level, rotation angle, and fit mode.
Each DocumentPresenter instance owns one ZoomState.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FitMode(Enum):
    """Page fit mode for automatic zoom calculation."""

    NONE = "none"
    PAGE = "page"
    WIDTH = "width"


@dataclass
class ZoomState:
    """Mutable zoom/rotation state for a single document tab.

    Attributes:
        zoom: Current zoom level (1.0 = 100%).
        rotation: Current rotation in degrees (0, 90, 180, 270).
        fit_mode: Active fit mode for automatic zoom.
        min_zoom: Minimum allowed zoom (10%).
        max_zoom: Maximum allowed zoom (300%).
    """

    zoom: float = 1.0
    rotation: int = 0
    fit_mode: FitMode = field(default=FitMode.NONE)
    min_zoom: float = 0.1
    max_zoom: float = 3.0

    def clamp_zoom(self, value: float) -> float:
        """Clamp a zoom value to [min_zoom, max_zoom].

        Args:
            value: The zoom value to clamp.

        Returns:
            The clamped zoom value.
        """
        return max(self.min_zoom, min(self.max_zoom, value))

    def normalize_rotation(self, degrees: int) -> int:
        """Normalize rotation to 0, 90, 180, or 270.

        Non-multiples of 90 are rounded down to the nearest multiple.
        Wraps around for values outside [0, 360).

        Args:
            degrees: Rotation in degrees (any integer).

        Returns:
            Normalized rotation: 0, 90, 180, or 270.
        """
        # Round down to nearest multiple of 90, then wrap
        snapped = (degrees // 90) * 90
        return snapped % 360
