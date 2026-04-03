"""Tests for FormPresenter — form lifecycle, save flow, dirty coordination."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from k_pdf.core.document_model import DocumentMetadata, DocumentModel, PageInfo
from k_pdf.core.form_model import FormFieldDescriptor, FormFieldType
from k_pdf.presenters.form_presenter import FormPresenter
from k_pdf.services.form_engine import FormEngine


def _make_model(tmp_path: Path, dirty: bool = False) -> DocumentModel:
    """Create a minimal DocumentModel for testing."""
    path = tmp_path / "test.pdf"
    path.touch()
    return DocumentModel(
        file_path=path,
        doc_handle=MagicMock(),
        metadata=DocumentMetadata(
            file_path=path,
            page_count=1,
            title=None,
            author=None,
            has_forms=True,
            has_outline=False,
            has_javascript=False,
            is_encrypted=False,
            file_size_bytes=1024,
        ),
        pages=[
            PageInfo(
                index=0,
                width=612,
                height=792,
                rotation=0,
                has_text=True,
                annotation_count=0,
            )
        ],
        dirty=dirty,
    )


class TestOnDocumentOpened:
    def test_emits_form_detected_with_count(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        engine.detect_fields.return_value = [
            FormFieldDescriptor(
                name="f1", field_type=FormFieldType.TEXT, page=0, rect=(0, 0, 1, 1)
            ),
            FormFieldDescriptor(
                name="f2", field_type=FormFieldType.CHECKBOX, page=0, rect=(0, 0, 1, 1)
            ),
        ]
        engine.is_xfa_form.return_value = False
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path)
        signals: list[int] = []
        presenter.form_detected.connect(signals.append)
        presenter.on_document_opened(model.session_id, model)
        assert signals == [2]

    def test_xfa_emits_xfa_detected(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        engine.is_xfa_form.return_value = True
        engine.detect_fields.return_value = []
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path)
        signals: list[str] = []
        presenter.xfa_detected.connect(signals.append)
        presenter.on_document_opened(model.session_id, model)
        assert len(signals) == 1
        assert "XFA" in signals[0]

    def test_no_fields_no_signal(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        engine.is_xfa_form.return_value = False
        engine.detect_fields.return_value = []
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path)
        signals: list[int] = []
        presenter.form_detected.connect(signals.append)
        presenter.on_document_opened(model.session_id, model)
        assert signals == []

    def test_stores_model_and_descriptors(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        engine.is_xfa_form.return_value = False
        engine.detect_fields.return_value = [
            FormFieldDescriptor(
                name="f1", field_type=FormFieldType.TEXT, page=0, rect=(0, 0, 1, 1), value="hello"
            ),
        ]
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path)
        presenter.on_document_opened(model.session_id, model)
        assert model.session_id in presenter._models
        assert model.session_id in presenter._field_descriptors
        assert presenter._field_values[model.session_id] == {"f1": "hello"}


class TestOnFieldChanged:
    def test_sets_dirty_flag(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path)
        presenter._models[model.session_id] = model
        presenter.on_field_changed(model.session_id, "f1", "new_val")
        assert model.dirty is True

    def test_emits_dirty_changed(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path)
        presenter._models[model.session_id] = model
        signals: list[bool] = []
        presenter.dirty_changed.connect(signals.append)
        presenter.on_field_changed(model.session_id, "f1", "val")
        assert signals == [True]

    def test_stores_field_value(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path)
        presenter._models[model.session_id] = model
        presenter.on_field_changed(model.session_id, "f1", "new_val")
        assert presenter._field_values[model.session_id]["f1"] == "new_val"

    def test_no_model_does_nothing(self, qtbot) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        signals: list[bool] = []
        presenter.dirty_changed.connect(signals.append)
        presenter.on_field_changed("nonexistent", "f1", "val")
        assert signals == []


class TestSave:
    def test_save_calls_engine(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path, dirty=True)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {"f1": "val1"}

        presenter.save(model.session_id)
        engine.write_fields.assert_called_once()
        engine.save_document.assert_called_once()

    def test_save_clears_dirty(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path, dirty=True)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {}

        presenter.save(model.session_id)
        assert model.dirty is False

    def test_save_emits_succeeded(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path, dirty=True)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {}

        signals: list[bool] = []
        presenter.save_succeeded.connect(lambda: signals.append(True))
        presenter.save(model.session_id)
        assert signals == [True]

    def test_save_emits_failed_on_error(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        engine.save_document.side_effect = PermissionError("denied")
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path, dirty=True)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {}

        signals: list[str] = []
        presenter.save_failed.connect(signals.append)
        presenter.save(model.session_id)
        assert len(signals) == 1
        assert "denied" in signals[0]

    def test_save_failed_keeps_dirty(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        engine.save_document.side_effect = PermissionError("denied")
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path, dirty=True)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {}

        presenter.save(model.session_id)
        assert model.dirty is True

    def test_save_no_model_does_nothing(self, qtbot) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        presenter.save("nonexistent")
        engine.write_fields.assert_not_called()


class TestSaveAs:
    def test_save_as_writes_to_new_path(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path, dirty=True)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {}

        new_path = tmp_path / "copy.pdf"
        presenter.save_as(model.session_id, new_path)
        engine.save_document.assert_called_once_with(model.doc_handle, new_path, is_new_path=True)

    def test_save_as_updates_file_path(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path, dirty=True)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {}

        new_path = tmp_path / "copy.pdf"
        presenter.save_as(model.session_id, new_path)
        assert model.file_path == new_path

    def test_save_as_clears_dirty(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path, dirty=True)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {}

        presenter.save_as(model.session_id, tmp_path / "copy.pdf")
        assert model.dirty is False


class TestOnTabClosed:
    def test_cleanup_removes_state(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        model = _make_model(tmp_path)
        presenter._models[model.session_id] = model
        presenter._field_values[model.session_id] = {}
        presenter._field_descriptors[model.session_id] = []
        presenter.on_tab_closed(model.session_id)
        assert model.session_id not in presenter._models
        assert model.session_id not in presenter._field_values
        assert model.session_id not in presenter._field_descriptors

    def test_cleanup_nonexistent_session_no_error(self, qtbot) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        # Should not raise
        presenter.on_tab_closed("nonexistent")


class TestHelperMethods:
    def test_get_field_descriptors_empty(self, qtbot) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        assert presenter.get_field_descriptors("nonexistent") == []

    def test_has_form_fields_false_when_no_session(self, qtbot) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        assert presenter.has_form_fields("nonexistent") is False

    def test_has_form_fields_true_when_fields_exist(self, qtbot, tmp_path: Path) -> None:
        engine = MagicMock(spec=FormEngine)
        tab_manager = MagicMock()
        presenter = FormPresenter(form_engine=engine, tab_manager=tab_manager)

        presenter._field_descriptors["sid"] = [
            FormFieldDescriptor(name="f", field_type=FormFieldType.TEXT, page=0, rect=(0, 0, 1, 1))
        ]
        assert presenter.has_form_fields("sid") is True
