"""Tests for ZoomState dataclass and FitMode enum."""

from __future__ import annotations

from k_pdf.core.zoom_model import FitMode, ZoomState


class TestFitMode:
    def test_enum_values(self) -> None:
        assert FitMode.NONE.value == "none"
        assert FitMode.PAGE.value == "page"
        assert FitMode.WIDTH.value == "width"

    def test_enum_members(self) -> None:
        assert len(FitMode) == 3


class TestZoomStateConstruction:
    def test_defaults(self) -> None:
        state = ZoomState()
        assert state.zoom == 1.0
        assert state.rotation == 0
        assert state.fit_mode is FitMode.NONE
        assert state.min_zoom == 0.1
        assert state.max_zoom == 3.0

    def test_custom_values(self) -> None:
        state = ZoomState(zoom=2.0, rotation=90, fit_mode=FitMode.PAGE)
        assert state.zoom == 2.0
        assert state.rotation == 90
        assert state.fit_mode is FitMode.PAGE

    def test_is_mutable(self) -> None:
        state = ZoomState()
        state.zoom = 1.5
        state.rotation = 180
        state.fit_mode = FitMode.WIDTH
        assert state.zoom == 1.5
        assert state.rotation == 180
        assert state.fit_mode is FitMode.WIDTH


class TestClampZoom:
    def test_within_range_unchanged(self) -> None:
        state = ZoomState()
        assert state.clamp_zoom(1.0) == 1.0
        assert state.clamp_zoom(2.5) == 2.5

    def test_below_min_clamped(self) -> None:
        state = ZoomState()
        assert state.clamp_zoom(0.05) == 0.1
        assert state.clamp_zoom(0.0) == 0.1
        assert state.clamp_zoom(-1.0) == 0.1

    def test_above_max_clamped(self) -> None:
        state = ZoomState()
        assert state.clamp_zoom(50.0) == 3.0
        assert state.clamp_zoom(100.0) == 3.0

    def test_at_boundaries(self) -> None:
        state = ZoomState()
        assert state.clamp_zoom(0.1) == 0.1
        assert state.clamp_zoom(3.0) == 3.0


class TestNormalizeRotation:
    def test_zero(self) -> None:
        state = ZoomState()
        assert state.normalize_rotation(0) == 0

    def test_valid_multiples(self) -> None:
        state = ZoomState()
        assert state.normalize_rotation(90) == 90
        assert state.normalize_rotation(180) == 180
        assert state.normalize_rotation(270) == 270

    def test_full_rotation_wraps_to_zero(self) -> None:
        state = ZoomState()
        assert state.normalize_rotation(360) == 0

    def test_negative_wraps(self) -> None:
        state = ZoomState()
        assert state.normalize_rotation(-90) == 270
        assert state.normalize_rotation(-180) == 180
        assert state.normalize_rotation(-270) == 90

    def test_large_positive_wraps(self) -> None:
        state = ZoomState()
        assert state.normalize_rotation(450) == 90
        assert state.normalize_rotation(720) == 0

    def test_large_negative_wraps(self) -> None:
        state = ZoomState()
        assert state.normalize_rotation(-360) == 0
        assert state.normalize_rotation(-450) == 270

    def test_non_multiple_of_90_rounds_down(self) -> None:
        state = ZoomState()
        # Non-multiples of 90 snap to nearest lower multiple
        assert state.normalize_rotation(45) == 0
        assert state.normalize_rotation(135) == 90
        assert state.normalize_rotation(200) == 180
        assert state.normalize_rotation(300) == 270
