"""Integration tests for Feature 8 — form filling and save through KPdfApp."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pymupdf
from PySide6.QtWidgets import QApplication, QMessageBox

from k_pdf.app import KPdfApp
from k_pdf.services.form_engine import FormEngine

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestFormDetection:
    def test_open_form_pdf_emits_form_detected(self, qtbot, form_pdf: Path) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        qtbot.addWidget(kapp.window)
        signals: list[int] = []
        kapp._form_presenter.form_detected.connect(signals.append)
        kapp.tab_manager.open_file(form_pdf)
        qtbot.waitUntil(lambda: len(signals) > 0, timeout=3000)
        assert signals == [3]
        kapp.shutdown()

    def test_open_non_form_pdf_no_form_message(self, qtbot, valid_pdf: Path) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        qtbot.addWidget(kapp.window)
        signals: list[int] = []
        kapp._form_presenter.form_detected.connect(signals.append)
        kapp.tab_manager.open_file(valid_pdf)
        qtbot.waitUntil(lambda: kapp.tab_manager.active_session_id is not None, timeout=3000)
        assert signals == []
        kapp.shutdown()

    def test_save_enabled_after_document_open(self, qtbot, form_pdf: Path) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        qtbot.addWidget(kapp.window)
        kapp.tab_manager.open_file(form_pdf)
        qtbot.waitUntil(lambda: kapp.window._save_action.isEnabled(), timeout=3000)
        assert kapp.window._save_action.isEnabled()
        assert kapp.window._save_as_action.isEnabled()
        kapp.shutdown()


class TestFormEngineIntegration:
    def test_detect_and_write_roundtrip(self, form_pdf: Path, tmp_path: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        assert len(fields) == 3

        engine.write_fields(doc, {"full_name": "Integration Test"})
        out = tmp_path / "roundtrip.pdf"
        engine.save_document(doc, out, is_new_path=True)
        doc.close()

        doc2 = pymupdf.open(str(out))
        fields2 = engine.detect_fields(doc2)
        name_field = next(f for f in fields2 if f.name == "full_name")
        assert name_field.value == "Integration Test"
        doc2.close()

    def test_checkbox_roundtrip(self, form_pdf: Path, tmp_path: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"agree": "Yes"})
        out = tmp_path / "checkbox.pdf"
        engine.save_document(doc, out, is_new_path=True)
        doc.close()

        doc2 = pymupdf.open(str(out))
        fields2 = engine.detect_fields(doc2)
        agree = next(f for f in fields2 if f.name == "agree")
        assert agree.value == "Yes"
        doc2.close()

    def test_dropdown_roundtrip(self, form_pdf: Path, tmp_path: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"country": "Mexico"})
        out = tmp_path / "dropdown.pdf"
        engine.save_document(doc, out, is_new_path=True)
        doc.close()

        doc2 = pymupdf.open(str(out))
        fields2 = engine.detect_fields(doc2)
        country = next(f for f in fields2 if f.name == "country")
        assert country.value == "Mexico"
        doc2.close()


class TestSaveIntegration:
    def test_save_clears_dirty_indicator(self, qtbot, form_pdf: Path, tmp_path: Path) -> None:
        copy_path = tmp_path / "form_copy.pdf"
        shutil.copy2(form_pdf, copy_path)

        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        qtbot.addWidget(kapp.window)
        kapp.tab_manager.open_file(copy_path)
        qtbot.waitUntil(lambda: kapp.tab_manager.active_session_id is not None, timeout=3000)
        sid = kapp.tab_manager.active_session_id
        assert sid is not None
        presenter = kapp.tab_manager.get_active_presenter()
        assert presenter is not None
        assert presenter.model is not None

        # Simulate dirty via form change
        presenter.model.dirty = True
        kapp._form_presenter._models[sid] = presenter.model
        kapp._form_presenter._field_values[sid] = {"full_name": "New Value"}
        kapp._form_presenter.save(sid)
        assert presenter.model.dirty is False
        kapp.shutdown()


class TestDirtyCloseGuardIntegration:
    @patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Discard)
    def test_discard_closes_dirty_tab(self, mock_exec, qtbot, form_pdf: Path) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        qtbot.addWidget(kapp.window)
        kapp.tab_manager.open_file(form_pdf)
        qtbot.waitUntil(lambda: kapp.tab_manager.active_session_id is not None, timeout=3000)
        sid = kapp.tab_manager.active_session_id
        assert sid is not None
        presenter = kapp.tab_manager.get_active_presenter()
        if presenter and presenter.model:
            presenter.model.dirty = True

        kapp.tab_manager.close_tab(sid)
        # Discard chosen -> tab should be closed
        assert sid not in kapp.tab_manager._tabs
        kapp.shutdown()

    @patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Cancel)
    def test_cancel_keeps_dirty_tab_open(self, mock_exec, qtbot, form_pdf: Path) -> None:
        app = QApplication.instance()
        assert app is not None
        kapp = KPdfApp(app)
        qtbot.addWidget(kapp.window)
        kapp.tab_manager.open_file(form_pdf)
        qtbot.waitUntil(lambda: kapp.tab_manager.active_session_id is not None, timeout=3000)
        sid = kapp.tab_manager.active_session_id
        assert sid is not None
        presenter = kapp.tab_manager.get_active_presenter()
        if presenter and presenter.model:
            presenter.model.dirty = True

        kapp.tab_manager.close_tab(sid)
        # Cancel chosen -> tab should stay open
        assert sid in kapp.tab_manager._tabs
        kapp.shutdown()
