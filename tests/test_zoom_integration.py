"""Integration tests for zoom, rotation, and fit modes with real PDFs."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from k_pdf.app import KPdfApp
from k_pdf.core.zoom_model import FitMode

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestZoomIntegration:
    def _open_pdf(self, kpdf: KPdfApp, pdf_path: Path, qtbot: object) -> None:
        """Helper to open a PDF and wait for it to load."""
        spy = MagicMock()
        kpdf.tab_manager.document_ready.connect(spy)
        kpdf.tab_manager.open_file(pdf_path)

        def check_ready() -> None:
            assert spy.call_count >= 1

        qtbot.waitUntil(check_ready, timeout=5000)  # type: ignore[union-attr]

    def test_zoom_in_out(self, valid_pdf: Path, qtbot: object) -> None:
        """Test that zoom in/out changes presenter zoom and updates toolbar."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None
        assert presenter.zoom == 1.0

        # Zoom in
        kpdf.window.zoom_in_triggered.emit()
        assert abs(presenter.zoom - 1.1) < 0.01

        # Zoom out
        kpdf.window.zoom_out_triggered.emit()
        assert abs(presenter.zoom - 1.0) < 0.01

        kpdf.shutdown()

    def test_reset_zoom(self, valid_pdf: Path, qtbot: object) -> None:
        """Test that Ctrl+0 resets zoom to 100%."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None
        presenter.set_zoom(2.0)
        assert presenter.zoom == 2.0

        kpdf.window.zoom_reset_triggered.emit()
        assert presenter.zoom == 1.0

        kpdf.shutdown()

    def test_fit_page(self, valid_pdf: Path, qtbot: object) -> None:
        """Test Fit Page mode calculates zoom from viewport size."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None

        # Manually trigger fit page with known dimensions
        presenter.set_fit_mode(FitMode.PAGE, 306.0, 396.0)
        assert presenter.fit_mode is FitMode.PAGE
        # Page is 612x792, viewport 306x396 => min(0.5, 0.5) = 0.5
        assert abs(presenter.zoom - 0.5) < 0.01

        kpdf.shutdown()

    def test_fit_width(self, valid_pdf: Path, qtbot: object) -> None:
        """Test Fit Width mode calculates zoom from viewport width."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None

        presenter.set_fit_mode(FitMode.WIDTH, 306.0, 1000.0)
        assert presenter.fit_mode is FitMode.WIDTH
        assert abs(presenter.zoom - 0.5) < 0.01

        kpdf.shutdown()

    def test_fit_mode_cleared_on_manual_zoom(self, valid_pdf: Path, qtbot: object) -> None:
        """Test that manual zoom clears fit mode to NONE."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None

        presenter.set_fit_mode(FitMode.PAGE, 612.0, 792.0)
        assert presenter.fit_mode is FitMode.PAGE

        presenter.set_zoom(2.0)
        assert presenter.fit_mode is FitMode.NONE

        kpdf.shutdown()

    def test_rotation_cw_ccw(self, valid_pdf: Path, qtbot: object) -> None:
        """Test rotation through 0 -> 90 -> 180 -> 270 -> 0."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None
        assert presenter.rotation == 0

        # Rotate CW: 0 -> 90 -> 180 -> 270 -> 0
        kpdf.window.rotate_cw_triggered.emit()
        assert presenter.rotation == 90
        kpdf.window.rotate_cw_triggered.emit()
        assert presenter.rotation == 180
        kpdf.window.rotate_cw_triggered.emit()
        assert presenter.rotation == 270
        kpdf.window.rotate_cw_triggered.emit()
        assert presenter.rotation == 0

        # Rotate CCW: 0 -> 270
        kpdf.window.rotate_ccw_triggered.emit()
        assert presenter.rotation == 270

        kpdf.shutdown()

    def test_tab_switch_preserves_zoom(self, valid_pdf: Path, qtbot: object) -> None:
        """Test that switching tabs pushes each tab's zoom state to toolbar."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)

        # Open first tab
        self._open_pdf(kpdf, valid_pdf, qtbot)
        presenter1 = kpdf.tab_manager.get_active_presenter()
        assert presenter1 is not None
        presenter1.set_zoom(2.0)

        # Open second tab (need a different path for duplicate detection)
        with tempfile.TemporaryDirectory() as tmpdir:
            second_pdf = Path(tmpdir) / "second.pdf"
            shutil.copy(str(valid_pdf), str(second_pdf))

            spy2 = MagicMock()
            kpdf.tab_manager.document_ready.connect(spy2)
            kpdf.tab_manager.open_file(second_pdf)

            def check_ready2() -> None:
                assert spy2.call_count >= 1

            qtbot.waitUntil(check_ready2, timeout=5000)  # type: ignore[union-attr]

            presenter2 = kpdf.tab_manager.get_active_presenter()
            assert presenter2 is not None
            assert presenter2 is not presenter1
            assert presenter2.zoom == 1.0  # Default zoom for new tab

            # Switch back to first tab
            kpdf.window.tab_widget.setCurrentIndex(0)
            # Toolbar should reflect tab 1's zoom
            assert abs(kpdf.window.zoom_toolbar._current_zoom - 2.0) < 0.01

        kpdf.shutdown()

    def test_toolbar_updates_on_presenter_zoom_change(self, valid_pdf: Path, qtbot: object) -> None:
        """Test that presenter zoom changes push back to toolbar display."""
        app_instance = QApplication.instance()
        assert app_instance is not None
        kpdf = KPdfApp(app_instance)
        self._open_pdf(kpdf, valid_pdf, qtbot)

        presenter = kpdf.tab_manager.get_active_presenter()
        assert presenter is not None

        presenter.set_zoom(1.5)
        # Toolbar should show 150%
        assert "150" in kpdf.window.zoom_toolbar._percent_input.text()

        kpdf.shutdown()
