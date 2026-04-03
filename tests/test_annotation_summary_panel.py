"""Tests for AnnotationSummaryPanel view."""

from __future__ import annotations

from k_pdf.core.annotation_model import AnnotationInfo
from k_pdf.views.annotation_panel import AnnotationSummaryPanel


class TestAnnotationSummaryPanel:
    def test_set_annotations_populates_table(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = AnnotationSummaryPanel()
        qtbot.addWidget(panel)
        annotations = [
            AnnotationInfo(page=0, ann_type="Highlight", author="Karl"),
            AnnotationInfo(page=1, ann_type="Note", content="A note"),
            AnnotationInfo(page=2, ann_type="Text Box", content="Box text"),
        ]
        panel.set_annotations(annotations)
        assert panel._table.rowCount() == 3

    def test_set_annotations_columns(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = AnnotationSummaryPanel()
        qtbot.addWidget(panel)
        annotations = [
            AnnotationInfo(
                page=0,
                ann_type="Highlight",
                author="Karl",
                content="",
                color=(1.0, 1.0, 0.0),
            ),
        ]
        panel.set_annotations(annotations)
        # Column 0: Page (1-based)
        assert panel._table.item(0, 0).text() == "1"
        # Column 1: Type
        assert panel._table.item(0, 1).text() == "Highlight"
        # Column 2: Author
        assert panel._table.item(0, 2).text() == "Karl"
        # Column 3: Preview (empty for highlight)
        assert panel._table.item(0, 3).text() == ""

    def test_clear_shows_empty_state(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = AnnotationSummaryPanel()
        qtbot.addWidget(panel)
        panel.show()
        annotations = [
            AnnotationInfo(page=0, ann_type="Highlight"),
        ]
        panel.set_annotations(annotations)
        panel.clear()
        assert panel._table.rowCount() == 0
        assert panel._empty_label.isVisible()

    def test_annotation_clicked_signal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = AnnotationSummaryPanel()
        qtbot.addWidget(panel)
        annotations = [
            AnnotationInfo(page=5, ann_type="Note"),
        ]
        panel.set_annotations(annotations)
        with qtbot.waitSignal(panel.annotation_clicked, timeout=1000) as blocker:
            panel._table.selectRow(0)
            panel._on_row_clicked(panel._table.model().index(0, 0))
        assert blocker.args == [5]

    def test_empty_state_on_no_annotations(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = AnnotationSummaryPanel()
        qtbot.addWidget(panel)
        panel.show()
        panel.set_annotations([])
        assert panel._table.rowCount() == 0
        assert panel._empty_label.isVisible()

    def test_type_column_has_text_label(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = AnnotationSummaryPanel()
        qtbot.addWidget(panel)
        for ann_type in ("Highlight", "Underline", "Strikethrough", "Note", "Text Box"):
            panel.set_annotations([AnnotationInfo(page=0, ann_type=ann_type)])
            assert panel._table.item(0, 1).text() == ann_type

    def test_preview_truncated(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = AnnotationSummaryPanel()
        qtbot.addWidget(panel)
        long_content = "A" * 60
        annotations = [
            AnnotationInfo(page=0, ann_type="Note", content=long_content),
        ]
        panel.set_annotations(annotations)
        preview = panel._table.item(0, 3).text()
        assert len(preview) <= 43  # 40 chars + "..."
        assert preview.endswith("...")

    def test_empty_label_hidden_when_annotations_present(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = AnnotationSummaryPanel()
        qtbot.addWidget(panel)
        panel.show()
        annotations = [
            AnnotationInfo(page=0, ann_type="Highlight"),
        ]
        panel.set_annotations(annotations)
        assert not panel._empty_label.isVisible()
        assert panel._table.isVisible()

    def test_sorted_by_page_by_default(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = AnnotationSummaryPanel()
        qtbot.addWidget(panel)
        annotations = [
            AnnotationInfo(page=2, ann_type="Note"),
            AnnotationInfo(page=0, ann_type="Highlight"),
            AnnotationInfo(page=1, ann_type="Underline"),
        ]
        panel.set_annotations(annotations)
        # Rows should be sorted by page number
        assert panel._table.item(0, 0).text() == "1"
        assert panel._table.item(1, 0).text() == "2"
        assert panel._table.item(2, 0).text() == "3"

    def test_panel_is_dock_widget(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from PySide6.QtWidgets import QDockWidget

        panel = AnnotationSummaryPanel()
        qtbot.addWidget(panel)
        assert isinstance(panel, QDockWidget)
