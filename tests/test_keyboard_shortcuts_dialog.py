"""Tests for the KeyboardShortcutsDialog view."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QApplication, QHeaderView

from k_pdf.views.keyboard_shortcuts_dialog import (
    KeyboardShortcutsDialog,
    get_shortcut_definitions,
)

_app: QApplication | None = None


def setup_module() -> None:
    """Ensure QApplication exists."""
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])


class TestGetShortcutDefinitions:
    """Tests for the shortcut definitions data function."""

    def test_returns_list_of_tuples(self) -> None:
        defs = get_shortcut_definitions()
        assert isinstance(defs, list)
        assert len(defs) > 0
        for category_name, shortcuts in defs:
            assert isinstance(category_name, str)
            assert isinstance(shortcuts, list)
            for action, shortcut in shortcuts:
                assert isinstance(action, str)
                assert isinstance(shortcut, str)

    def test_has_all_five_categories(self) -> None:
        defs = get_shortcut_definitions()
        category_names = [name for name, _ in defs]
        assert category_names == ["File", "Edit", "View", "Tools", "Navigation"]

    def test_file_category_has_six_shortcuts(self) -> None:
        defs = get_shortcut_definitions()
        file_shortcuts = defs[0][1]
        assert len(file_shortcuts) == 6
        actions = [a for a, _ in file_shortcuts]
        assert "Open" in actions
        assert "Save" in actions
        assert "Save As" in actions
        assert "Close Tab" in actions
        assert "Merge Documents" in actions
        assert "Quit" in actions

    def test_edit_category_has_five_shortcuts(self) -> None:
        defs = get_shortcut_definitions()
        edit_shortcuts = defs[1][1]
        assert len(edit_shortcuts) == 5
        actions = [a for a, _ in edit_shortcuts]
        assert "Undo" in actions
        assert "Redo" in actions
        assert "Find" in actions
        assert "Copy" in actions
        assert "Find and Replace" in actions

    def test_view_category_has_ten_shortcuts(self) -> None:
        defs = get_shortcut_definitions()
        view_shortcuts = defs[2][1]
        assert len(view_shortcuts) == 10

    def test_tools_category_has_two_shortcuts(self) -> None:
        defs = get_shortcut_definitions()
        tools_shortcuts = defs[3][1]
        assert len(tools_shortcuts) == 2
        actions = [a for a, _ in tools_shortcuts]
        assert "Text Selection" in actions
        assert "Edit Text" in actions

    def test_navigation_category_has_four_shortcuts(self) -> None:
        defs = get_shortcut_definitions()
        nav_shortcuts = defs[4][1]
        assert len(nav_shortcuts) == 4

    def test_platform_modifier_macos(self) -> None:
        """On macOS, modifier should be Cmd; on others, Ctrl."""
        defs = get_shortcut_definitions()
        # Find the Open shortcut in File category
        file_shortcuts = defs[0][1]
        open_shortcut = next(s for a, s in file_shortcuts if a == "Open")
        if sys.platform == "darwin":
            assert "Cmd" in open_shortcut
            assert "Ctrl" not in open_shortcut
        else:
            assert "Ctrl" in open_shortcut

    def test_non_modifier_shortcuts_unchanged(self) -> None:
        """F-keys and Page Up/Down should not have Ctrl/Cmd prefix."""
        defs = get_shortcut_definitions()
        nav_shortcuts = defs[4][1]
        page_down = next(s for a, s in nav_shortcuts if a == "Page Down")
        assert page_down == "Page Down"
        page_up = next(s for a, s in nav_shortcuts if a == "Page Up")
        assert page_up == "Page Up"

    def test_total_shortcut_count(self) -> None:
        defs = get_shortcut_definitions()
        total = sum(len(shortcuts) for _, shortcuts in defs)
        assert total == 27


class TestKeyboardShortcutsDialog:
    """Tests for the KeyboardShortcutsDialog QDialog."""

    def test_dialog_title(self) -> None:
        dialog = KeyboardShortcutsDialog()
        assert dialog.windowTitle() == "Keyboard Shortcuts"

    def test_dialog_minimum_size(self) -> None:
        dialog = KeyboardShortcutsDialog()
        assert dialog.minimumWidth() >= 400
        assert dialog.minimumHeight() >= 400

    def test_table_exists_with_two_columns(self) -> None:
        dialog = KeyboardShortcutsDialog()
        table = dialog._table
        assert table.columnCount() == 2

    def test_table_column_headers(self) -> None:
        dialog = KeyboardShortcutsDialog()
        table = dialog._table
        assert table.horizontalHeaderItem(0).text() == "Action"
        assert table.horizontalHeaderItem(1).text() == "Shortcut"

    def test_table_is_read_only(self) -> None:
        dialog = KeyboardShortcutsDialog()
        table = dialog._table
        assert table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers

    def test_table_selection_mode(self) -> None:
        dialog = KeyboardShortcutsDialog()
        table = dialog._table
        assert table.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows

    def test_table_has_category_headers(self) -> None:
        """Category header rows should span all columns."""
        dialog = KeyboardShortcutsDialog()
        table = dialog._table
        # Find rows where columnSpan > 1 (category headers)
        category_rows = []
        for row in range(table.rowCount()):
            if table.columnSpan(row, 0) == 2:
                category_rows.append(row)
        assert len(category_rows) == 5  # File, Edit, View, Tools, Navigation

    def test_category_header_text(self) -> None:
        dialog = KeyboardShortcutsDialog()
        table = dialog._table
        # Collect category header texts
        category_texts = []
        for row in range(table.rowCount()):
            if table.columnSpan(row, 0) == 2:
                item = table.item(row, 0)
                category_texts.append(item.text())
        assert category_texts == ["File", "Edit", "View", "Tools", "Navigation"]

    def test_category_headers_not_selectable(self) -> None:
        dialog = KeyboardShortcutsDialog()
        table = dialog._table
        for row in range(table.rowCount()):
            if table.columnSpan(row, 0) == 2:
                item = table.item(row, 0)
                assert not (item.flags() & Qt.ItemFlag.ItemIsSelectable)

    def test_total_row_count(self) -> None:
        """5 category headers + 27 shortcut rows = 32 total rows."""
        dialog = KeyboardShortcutsDialog()
        table = dialog._table
        assert table.rowCount() == 32

    def test_shortcut_rows_have_correct_data(self) -> None:
        """Verify first shortcut under File category is Open."""
        dialog = KeyboardShortcutsDialog()
        table = dialog._table
        # Row 0 is File header, Row 1 should be the first File shortcut
        action_item = table.item(1, 0)
        shortcut_item = table.item(1, 1)
        assert action_item.text().strip() == "Open"
        expected_mod = "Cmd" if sys.platform == "darwin" else "Ctrl"
        assert shortcut_item.text() == f"{expected_mod}+O"

    def test_close_button_exists(self) -> None:
        dialog = KeyboardShortcutsDialog()
        assert dialog._close_btn is not None
        assert dialog._close_btn.text() == "Close"

    def test_shortcut_column_stretch(self) -> None:
        """Action column should stretch to fill available space."""
        dialog = KeyboardShortcutsDialog()
        table = dialog._table
        header = table.horizontalHeader()
        assert header.stretchLastSection() or (
            header.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
        )


class TestFormCreationShortcuts:
    def test_find_replace_shortcut_listed(self) -> None:
        defs = get_shortcut_definitions()
        all_actions = [action for _, shortcuts in defs for action, _ in shortcuts]
        assert "Find and Replace" in all_actions

    def test_form_properties_shortcut_listed(self) -> None:
        defs = get_shortcut_definitions()
        all_actions = [action for _, shortcuts in defs for action, _ in shortcuts]
        assert "Form Properties" in all_actions

    def test_edit_text_shortcut_listed(self) -> None:
        defs = get_shortcut_definitions()
        all_actions = [action for _, shortcuts in defs for action, _ in shortcuts]
        assert "Edit Text" in all_actions
