"""Tests for AnnotationType enum and AnnotationData dataclass."""

from __future__ import annotations

from datetime import datetime

from k_pdf.core.annotation_model import AnnotationData, AnnotationInfo, AnnotationType


class TestAnnotationType:
    def test_enum_values(self) -> None:
        assert AnnotationType.HIGHLIGHT.value == "highlight"
        assert AnnotationType.UNDERLINE.value == "underline"
        assert AnnotationType.STRIKETHROUGH.value == "strikethrough"

    def test_enum_member_count(self) -> None:
        assert len(AnnotationType) == 5

    def test_sticky_note_value(self) -> None:
        assert AnnotationType.STICKY_NOTE.value == "sticky_note"

    def test_text_box_value(self) -> None:
        assert AnnotationType.TEXT_BOX.value == "text_box"


class TestAnnotationData:
    def test_construction_required_fields(self) -> None:
        data = AnnotationData(
            type=AnnotationType.HIGHLIGHT,
            page=0,
            quads=[(0.0, 0.0, 100.0, 10.0)],
            color=(1.0, 1.0, 0.0),
        )
        assert data.type is AnnotationType.HIGHLIGHT
        assert data.page == 0
        assert data.quads == [(0.0, 0.0, 100.0, 10.0)]
        assert data.color == (1.0, 1.0, 0.0)

    def test_default_author_is_empty(self) -> None:
        data = AnnotationData(
            type=AnnotationType.UNDERLINE,
            page=1,
            quads=[(0.0, 0.0, 50.0, 10.0)],
            color=(1.0, 0.0, 0.0),
        )
        assert data.author == ""

    def test_default_created_at_is_set(self) -> None:
        before = datetime.now()
        data = AnnotationData(
            type=AnnotationType.STRIKETHROUGH,
            page=2,
            quads=[(10.0, 20.0, 80.0, 30.0)],
            color=(0.0, 0.0, 1.0),
        )
        after = datetime.now()
        assert before <= data.created_at <= after

    def test_custom_author(self) -> None:
        data = AnnotationData(
            type=AnnotationType.HIGHLIGHT,
            page=0,
            quads=[],
            color=(1.0, 1.0, 0.0),
            author="Karl",
        )
        assert data.author == "Karl"

    def test_is_mutable(self) -> None:
        data = AnnotationData(
            type=AnnotationType.HIGHLIGHT,
            page=0,
            quads=[],
            color=(1.0, 1.0, 0.0),
        )
        data.color = (0.0, 0.8, 0.0)
        assert data.color == (0.0, 0.8, 0.0)

    def test_default_content_is_empty(self) -> None:
        data = AnnotationData(
            type=AnnotationType.STICKY_NOTE,
            page=0,
            quads=[],
            color=(1.0, 1.0, 0.0),
        )
        assert data.content == ""

    def test_custom_content(self) -> None:
        data = AnnotationData(
            type=AnnotationType.STICKY_NOTE,
            page=0,
            quads=[],
            color=(1.0, 1.0, 0.0),
            content="Hello note",
        )
        assert data.content == "Hello note"

    def test_default_rect_is_none(self) -> None:
        data = AnnotationData(
            type=AnnotationType.TEXT_BOX,
            page=0,
            quads=[],
            color=(0.0, 0.0, 0.0),
        )
        assert data.rect is None

    def test_custom_rect(self) -> None:
        data = AnnotationData(
            type=AnnotationType.TEXT_BOX,
            page=0,
            quads=[],
            color=(0.0, 0.0, 0.0),
            rect=(100.0, 200.0, 300.0, 250.0),
        )
        assert data.rect == (100.0, 200.0, 300.0, 250.0)


class TestAnnotationInfo:
    def test_construction_all_fields(self) -> None:
        info = AnnotationInfo(
            page=2,
            ann_type="Highlight",
            author="Karl",
            content="Important text",
            color=(1.0, 1.0, 0.0),
            rect=(72.0, 100.0, 300.0, 120.0),
        )
        assert info.page == 2
        assert info.ann_type == "Highlight"
        assert info.author == "Karl"
        assert info.content == "Important text"
        assert info.color == (1.0, 1.0, 0.0)
        assert info.rect == (72.0, 100.0, 300.0, 120.0)

    def test_default_values(self) -> None:
        info = AnnotationInfo(page=0, ann_type="Note")
        assert info.author == ""
        assert info.content == ""
        assert info.color == (0.0, 0.0, 0.0)
        assert info.rect == (0.0, 0.0, 0.0, 0.0)

    def test_different_types(self) -> None:
        for ann_type in ("Highlight", "Underline", "Strikethrough", "Note", "Text Box"):
            info = AnnotationInfo(page=0, ann_type=ann_type)
            assert info.ann_type == ann_type
