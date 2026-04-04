"""Tests for DocumentPresenter zoom, rotation, and fit mode methods."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from k_pdf.core.document_model import DocumentModel, PageInfo
from k_pdf.core.zoom_model import FitMode
from k_pdf.presenters.document_presenter import DocumentPresenter

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


def _make_presenter_with_model() -> DocumentPresenter:
    """Create a presenter with a mock document model for zoom testing."""
    presenter = DocumentPresenter()
    # Inject a mock model so set_fit_mode can read page dimensions
    model = MagicMock(spec=DocumentModel)
    model.pages = [
        PageInfo(
            index=0,
            width=612.0,
            height=792.0,
            rotation=0,
            has_text=True,
            annotation_count=0,
        ),
        PageInfo(
            index=1,
            width=612.0,
            height=792.0,
            rotation=0,
            has_text=True,
            annotation_count=0,
        ),
    ]
    model.doc_handle = MagicMock()
    presenter._model = model
    return presenter


class TestDocumentPresenterZoom:
    def test_initial_zoom_is_1(self) -> None:
        presenter = DocumentPresenter()
        assert presenter.zoom == 1.0
        presenter.shutdown()

    def test_initial_rotation_is_0(self) -> None:
        presenter = DocumentPresenter()
        assert presenter.rotation == 0
        presenter.shutdown()

    def test_initial_fit_mode_is_none(self) -> None:
        presenter = DocumentPresenter()
        assert presenter.fit_mode is FitMode.NONE
        presenter.shutdown()

    def test_set_zoom_updates_value(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_zoom(2.0)
        assert presenter.zoom == 2.0
        presenter.shutdown()

    def test_set_zoom_clamps_below_min(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_zoom(0.01)
        assert presenter.zoom == 0.1
        presenter.shutdown()

    def test_set_zoom_clamps_above_max(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_zoom(50.0)
        assert presenter.zoom == 3.0
        presenter.shutdown()

    def test_set_zoom_emits_signal(self) -> None:
        presenter = _make_presenter_with_model()
        spy = MagicMock()
        presenter.zoom_changed.connect(spy)
        presenter.set_zoom(1.5)
        spy.assert_called_once_with(1.5)
        presenter.shutdown()

    def test_set_zoom_clears_fit_mode(self) -> None:
        presenter = _make_presenter_with_model()
        presenter._zoom_state.fit_mode = FitMode.PAGE
        presenter.set_zoom(2.0)
        assert presenter.fit_mode is FitMode.NONE
        presenter.shutdown()

    def test_set_zoom_invalidates_cache(self) -> None:
        presenter = _make_presenter_with_model()
        presenter._cache.put(0, MagicMock())
        assert presenter._cache.size() == 1
        presenter.set_zoom(2.0)
        assert presenter._cache.size() == 0
        presenter.shutdown()

    def test_set_zoom_no_signal_when_unchanged(self) -> None:
        presenter = _make_presenter_with_model()
        spy = MagicMock()
        presenter.zoom_changed.connect(spy)
        presenter.set_zoom(1.0)  # Same as default
        spy.assert_not_called()
        presenter.shutdown()


class TestDocumentPresenterRotation:
    def test_set_rotation_updates_value(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_rotation(90)
        assert presenter.rotation == 90
        presenter.shutdown()

    def test_set_rotation_normalizes(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_rotation(450)
        assert presenter.rotation == 90
        presenter.shutdown()

    def test_set_rotation_negative(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_rotation(-90)
        assert presenter.rotation == 270
        presenter.shutdown()

    def test_set_rotation_emits_signal(self) -> None:
        presenter = _make_presenter_with_model()
        spy = MagicMock()
        presenter.rotation_changed.connect(spy)
        presenter.set_rotation(90)
        spy.assert_called_once_with(90)
        presenter.shutdown()

    def test_set_rotation_invalidates_cache(self) -> None:
        presenter = _make_presenter_with_model()
        presenter._cache.put(0, MagicMock())
        assert presenter._cache.size() == 1
        presenter.set_rotation(90)
        assert presenter._cache.size() == 0
        presenter.shutdown()

    def test_set_rotation_no_signal_when_unchanged(self) -> None:
        presenter = _make_presenter_with_model()
        spy = MagicMock()
        presenter.rotation_changed.connect(spy)
        presenter.set_rotation(0)  # Same as default
        spy.assert_not_called()
        presenter.shutdown()

    def test_rotation_wraps_through_360(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_rotation(90)
        presenter.set_rotation(180)
        presenter.set_rotation(270)
        presenter.set_rotation(360)
        assert presenter.rotation == 0
        presenter.shutdown()


class TestDocumentPresenterFitMode:
    def test_set_fit_mode_page(self) -> None:
        presenter = _make_presenter_with_model()
        # Viewport 612x792 with page 612x792 => zoom = 1.0
        presenter.set_fit_mode(FitMode.PAGE, 612.0, 792.0)
        assert presenter.fit_mode is FitMode.PAGE
        assert presenter.zoom == 1.0
        presenter.shutdown()

    def test_set_fit_mode_width(self) -> None:
        presenter = _make_presenter_with_model()
        # Viewport 306 wide with page 612 wide => zoom = 0.5
        presenter.set_fit_mode(FitMode.WIDTH, 306.0, 792.0)
        assert presenter.fit_mode is FitMode.WIDTH
        assert presenter.zoom == 0.5
        presenter.shutdown()

    def test_set_fit_mode_page_smaller_viewport(self) -> None:
        presenter = _make_presenter_with_model()
        # Viewport 300x400 with page 612x792
        # min(300/612, 400/792) = min(0.4902, 0.5050) = 0.4902...
        presenter.set_fit_mode(FitMode.PAGE, 300.0, 400.0)
        assert presenter.fit_mode is FitMode.PAGE
        expected = min(300.0 / 612.0, 400.0 / 792.0)
        assert abs(presenter.zoom - expected) < 0.001
        presenter.shutdown()

    def test_set_fit_mode_preserves_fit_mode(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_fit_mode(FitMode.PAGE, 612.0, 792.0)
        assert presenter.fit_mode is FitMode.PAGE
        # Explicit set_zoom clears it
        presenter.set_zoom(2.0)
        assert presenter.fit_mode is FitMode.NONE
        presenter.shutdown()

    def test_set_fit_mode_emits_zoom_changed(self) -> None:
        presenter = _make_presenter_with_model()
        spy = MagicMock()
        presenter.zoom_changed.connect(spy)
        presenter.set_fit_mode(FitMode.WIDTH, 306.0, 792.0)
        spy.assert_called_once_with(0.5)
        presenter.shutdown()

    def test_set_fit_mode_none_is_noop(self) -> None:
        presenter = _make_presenter_with_model()
        spy = MagicMock()
        presenter.zoom_changed.connect(spy)
        presenter.set_fit_mode(FitMode.NONE, 612.0, 792.0)
        spy.assert_not_called()
        presenter.shutdown()

    def test_set_fit_mode_respects_rotation(self) -> None:
        presenter = _make_presenter_with_model()
        presenter.set_rotation(90)
        # At 90 degrees, width/height swap: page becomes 792x612
        # FitWidth: viewport_width / page_width = 306 / 792 ~= 0.386
        presenter.set_fit_mode(FitMode.WIDTH, 306.0, 612.0)
        assert presenter.fit_mode is FitMode.WIDTH
        expected = 306.0 / 792.0
        assert abs(presenter.zoom - expected) < 0.001
        presenter.shutdown()

    def test_set_fit_mode_no_model_is_noop(self) -> None:
        presenter = DocumentPresenter()
        spy = MagicMock()
        presenter.zoom_changed.connect(spy)
        presenter.set_fit_mode(FitMode.PAGE, 612.0, 792.0)
        spy.assert_not_called()
        presenter.shutdown()
