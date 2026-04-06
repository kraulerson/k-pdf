"""Tests for FormEngine — AcroForm field detection, writing, and saving."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from k_pdf.core.form_model import FormFieldType
from k_pdf.services.form_engine import FormEngine


class TestDetectFields:
    def test_returns_descriptors_for_form_pdf(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        assert len(fields) == 3
        doc.close()

    def test_field_names_match(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        names = {f.name for f in fields}
        assert names == {"full_name", "agree", "country"}
        doc.close()

    def test_field_types_correct(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        type_map = {f.name: f.field_type for f in fields}
        assert type_map["full_name"] is FormFieldType.TEXT
        assert type_map["agree"] is FormFieldType.CHECKBOX
        assert type_map["country"] is FormFieldType.DROPDOWN
        doc.close()

    def test_dropdown_has_options(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        country = next(f for f in fields if f.name == "country")
        assert "USA" in country.options
        assert "Canada" in country.options
        assert "Mexico" in country.options
        doc.close()

    def test_returns_empty_for_non_form_pdf(self, valid_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(valid_pdf))
        fields = engine.detect_fields(doc)
        assert fields == []
        doc.close()

    def test_field_rect_is_tuple(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        for f in fields:
            assert isinstance(f.rect, tuple)
            assert len(f.rect) == 4
        doc.close()

    def test_field_page_is_zero(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        for f in fields:
            assert f.page == 0
        doc.close()

    def test_text_field_default_value(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        name_field = next(f for f in fields if f.name == "full_name")
        assert name_field.value == ""
        doc.close()

    def test_dropdown_initial_value(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc)
        country = next(f for f in fields if f.name == "country")
        assert country.value == "USA"
        doc.close()


class TestIsXfaForm:
    def test_returns_false_for_acroform(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        assert engine.is_xfa_form(doc) is False
        doc.close()

    def test_returns_false_for_non_form(self, valid_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(valid_pdf))
        assert engine.is_xfa_form(doc) is False
        doc.close()


class TestWriteFields:
    def test_writes_text_field_value(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"full_name": "Karl Raulerson"})
        # Re-read to verify
        fields = engine.detect_fields(doc)
        name_field = next(f for f in fields if f.name == "full_name")
        assert name_field.value == "Karl Raulerson"
        doc.close()

    def test_writes_checkbox_value(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"agree": "Yes"})
        fields = engine.detect_fields(doc)
        agree_field = next(f for f in fields if f.name == "agree")
        assert agree_field.value == "Yes"
        doc.close()

    def test_writes_dropdown_value(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"country": "Canada"})
        fields = engine.detect_fields(doc)
        country = next(f for f in fields if f.name == "country")
        assert country.value == "Canada"
        doc.close()

    def test_ignores_unknown_field_names(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        # Should not raise
        engine.write_fields(doc, {"nonexistent_field": "value"})
        doc.close()

    def test_writes_multiple_fields(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"full_name": "Test", "country": "Mexico"})
        fields = engine.detect_fields(doc)
        name_field = next(f for f in fields if f.name == "full_name")
        country = next(f for f in fields if f.name == "country")
        assert name_field.value == "Test"
        assert country.value == "Mexico"
        doc.close()


class TestSaveDocument:
    def test_save_creates_file(self, form_pdf: Path, tmp_path: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"full_name": "Test User"})
        output = tmp_path / "saved.pdf"
        engine.save_document(doc, output, is_new_path=True)
        assert output.exists()
        doc.close()

    def test_save_persists_field_values(self, form_pdf: Path, tmp_path: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"full_name": "Saved Value"})
        output = tmp_path / "persisted.pdf"
        engine.save_document(doc, output, is_new_path=True)
        doc.close()

        # Reopen and verify
        doc2 = pymupdf.open(str(output))
        fields = engine.detect_fields(doc2)
        name_field = next(f for f in fields if f.name == "full_name")
        assert name_field.value == "Saved Value"
        doc2.close()

    def test_save_incremental_to_same_path(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        engine.write_fields(doc, {"full_name": "Incremental"})
        # Save back to same path (incremental)
        engine.save_document(doc, form_pdf, is_new_path=False)
        doc.close()

        doc2 = pymupdf.open(str(form_pdf))
        fields = engine.detect_fields(doc2)
        name_field = next(f for f in fields if f.name == "full_name")
        assert name_field.value == "Incremental"
        doc2.close()

    def test_save_raises_on_bad_path(self, form_pdf: Path, tmp_path: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        bad_path = tmp_path / "nonexistent_dir" / "out.pdf"
        with pytest.raises(Exception):  # noqa: B017
            engine.save_document(doc, bad_path, is_new_path=True)
        doc.close()


class TestGetFieldValue:
    def test_reads_text_field(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        page = doc[0]
        for widget in page.widgets():
            if widget.field_name == "country":
                val = engine.get_field_value(widget)
                assert val == "USA"
                break
        doc.close()

    def test_reads_empty_field(self, form_pdf: Path) -> None:
        engine = FormEngine()
        doc = pymupdf.open(str(form_pdf))
        page = doc[0]
        for widget in page.widgets():
            if widget.field_name == "full_name":
                val = engine.get_field_value(widget)
                assert val == ""
                break
        doc.close()


class TestCreateWidget:
    @pytest.fixture
    def engine(self) -> FormEngine:
        return FormEngine()

    @pytest.fixture
    def blank_pdf(self, tmp_path: Path) -> Path:
        path = tmp_path / "blank.pdf"
        doc = pymupdf.open()
        doc.new_page(width=612, height=792)
        doc.save(str(path))
        doc.close()
        return path

    def test_create_text_field(self, engine: FormEngine, blank_pdf: Path) -> None:
        doc = pymupdf.open(str(blank_pdf))
        widget = engine.create_widget(
            doc_handle=doc,
            page_index=0,
            field_type=FormFieldType.TEXT,
            rect=(72, 100, 272, 124),
            properties={"name": "user_name", "max_length": 50},
        )
        assert widget is not None
        assert widget.field_name == "user_name"
        assert widget.field_type == pymupdf.PDF_WIDGET_TYPE_TEXT
        doc.close()

    def test_create_checkbox(self, engine: FormEngine, blank_pdf: Path) -> None:
        doc = pymupdf.open(str(blank_pdf))
        widget = engine.create_widget(
            doc_handle=doc,
            page_index=0,
            field_type=FormFieldType.CHECKBOX,
            rect=(72, 140, 86, 154),
            properties={"name": "agree_terms"},
        )
        assert widget is not None
        assert widget.field_name == "agree_terms"
        assert widget.field_type == pymupdf.PDF_WIDGET_TYPE_CHECKBOX
        doc.close()

    def test_create_dropdown(self, engine: FormEngine, blank_pdf: Path) -> None:
        doc = pymupdf.open(str(blank_pdf))
        widget = engine.create_widget(
            doc_handle=doc,
            page_index=0,
            field_type=FormFieldType.DROPDOWN,
            rect=(72, 180, 272, 204),
            properties={"name": "country", "options": ["USA", "Canada", "Mexico"]},
        )
        assert widget is not None
        assert widget.field_name == "country"
        assert widget.field_type == pymupdf.PDF_WIDGET_TYPE_COMBOBOX
        doc.close()

    def test_create_radio(self, engine: FormEngine, blank_pdf: Path) -> None:
        doc = pymupdf.open(str(blank_pdf))
        widget = engine.create_widget(
            doc_handle=doc,
            page_index=0,
            field_type=FormFieldType.RADIO,
            rect=(72, 220, 86, 234),
            properties={"name": "gender_male"},
        )
        assert widget is not None
        assert widget.field_name == "gender_male"
        assert widget.field_type == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON
        doc.close()

    def test_create_signature(self, engine: FormEngine, blank_pdf: Path) -> None:
        doc = pymupdf.open(str(blank_pdf))
        widget = engine.create_widget(
            doc_handle=doc,
            page_index=0,
            field_type=FormFieldType.SIGNATURE,
            rect=(72, 260, 272, 320),
            properties={"name": "applicant_sig"},
        )
        assert widget is not None
        assert widget.field_name == "applicant_sig"
        doc.close()

    def test_created_field_persists_after_save(
        self, engine: FormEngine, blank_pdf: Path, tmp_path: Path
    ) -> None:
        doc = pymupdf.open(str(blank_pdf))
        engine.create_widget(
            doc_handle=doc,
            page_index=0,
            field_type=FormFieldType.TEXT,
            rect=(72, 100, 272, 124),
            properties={"name": "persist_test"},
        )
        out_path = tmp_path / "saved.pdf"
        doc.save(str(out_path))
        doc.close()

        doc2 = pymupdf.open(str(out_path))
        fields = engine.detect_fields(doc2)
        assert any(f.name == "persist_test" for f in fields)
        doc2.close()


class TestDeleteWidget:
    @pytest.fixture
    def engine(self) -> FormEngine:
        return FormEngine()

    def test_delete_widget_removes_field(self, engine: FormEngine, form_pdf: Path) -> None:
        doc = pymupdf.open(str(form_pdf))
        fields_before = engine.detect_fields(doc)
        count_before = len(fields_before)

        page = doc[0]
        widget = next(page.widgets())
        engine.delete_widget(doc, 0, widget)

        fields_after = engine.detect_fields(doc)
        assert len(fields_after) == count_before - 1
        doc.close()


class TestUpdateWidgetProperties:
    @pytest.fixture
    def engine(self) -> FormEngine:
        return FormEngine()

    def test_update_field_name(self, engine: FormEngine, form_pdf: Path) -> None:
        doc = pymupdf.open(str(form_pdf))
        page = doc[0]
        widget = next(page.widgets())
        engine.update_widget_properties(doc, 0, widget, {"name": "updated_name"})

        fields = engine.detect_fields(doc)
        names = [f.name for f in fields]
        assert "updated_name" in names
        doc.close()


class TestGetWidgetAt:
    @pytest.fixture
    def engine(self) -> FormEngine:
        return FormEngine()

    def test_hit_test_on_field(self, engine: FormEngine, form_pdf: Path) -> None:
        doc = pymupdf.open(str(form_pdf))
        # full_name field is at rect (72, 100, 300, 120)
        widget = engine.get_widget_at(doc, 0, 150.0, 110.0)
        assert widget is not None
        doc.close()

    def test_hit_test_on_empty_area(self, engine: FormEngine, form_pdf: Path) -> None:
        doc = pymupdf.open(str(form_pdf))
        widget = engine.get_widget_at(doc, 0, 500.0, 500.0)
        assert widget is None
        doc.close()
