"""Keyboard Shortcuts reference dialog.

Read-only table listing all keyboard shortcuts grouped by category.
Platform-aware: shows Cmd on macOS, Ctrl on Windows/Linux.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


def _modifier() -> str:
    """Return the platform-appropriate modifier key name."""
    return "Cmd" if sys.platform == "darwin" else "Ctrl"


def get_shortcut_definitions() -> list[tuple[str, list[tuple[str, str]]]]:
    """Return all keyboard shortcuts grouped by category.

    Returns:
        List of (category_name, [(action, shortcut), ...]) tuples.
        Shortcut strings use platform-appropriate modifier names.
    """
    mod = _modifier()
    return [
        (
            "File",
            [
                ("Open", f"{mod}+O"),
                ("Save", f"{mod}+S"),
                ("Save As", f"{mod}+Shift+S"),
                ("Close Tab", f"{mod}+W"),
                ("Merge Documents", f"{mod}+Shift+M"),
                ("Quit", f"{mod}+Q"),
            ],
        ),
        (
            "Edit",
            [
                ("Undo", f"{mod}+Z"),
                ("Redo", f"{mod}+Shift+Z"),
                ("Find", f"{mod}+F"),
                ("Copy", f"{mod}+C"),
                ("Find and Replace", f"{mod}+Shift+H"),
            ],
        ),
        (
            "View",
            [
                ("Zoom In", f"{mod}+="),
                ("Zoom Out", f"{mod}+-"),
                ("Reset Zoom", f"{mod}+0"),
                ("Rotate Clockwise", f"{mod}+R"),
                ("Rotate Counter-Clockwise", f"{mod}+Shift+R"),
                ("Navigation Panel", "F5"),
                ("Annotation Panel", "F6"),
                ("Page Manager", "F7"),
                ("Form Properties", "F8"),
                ("Toggle Dark Mode", f"{mod}+D"),
            ],
        ),
        (
            "Tools",
            [
                ("Text Selection", f"{mod}+T"),
                ("Edit Text", f"{mod}+E"),
            ],
        ),
        (
            "Navigation",
            [
                ("Next Tab", f"{mod}+Tab"),
                ("Previous Tab", f"{mod}+Shift+Tab"),
                ("Page Down", "Page Down"),
                ("Page Up", "Page Up"),
            ],
        ),
    ]


class KeyboardShortcutsDialog(QDialog):
    """Read-only dialog showing all keyboard shortcuts in a categorized table."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the keyboard shortcuts dialog.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(450, 500)
        self.resize(500, 600)

        layout = QVBoxLayout(self)

        # Build table
        self._table = QTableWidget(self)
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Action", "Shortcut"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)

        # Stretch action column, resize shortcut to contents
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        self._populate_table()

        layout.addWidget(self._table)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self._close_btn = QPushButton("Close", self)
        self._close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self._close_btn)
        layout.addLayout(button_layout)

    def _populate_table(self) -> None:
        """Fill the table with category headers and shortcut rows."""
        definitions = get_shortcut_definitions()

        # Calculate total rows: categories + shortcuts
        total_rows = sum(1 + len(shortcuts) for _, shortcuts in definitions)
        self._table.setRowCount(total_rows)

        row = 0
        bold_font = QFont()
        bold_font.setBold(True)

        for category_name, shortcuts in definitions:
            # Category header row — spans both columns
            header_item = QTableWidgetItem(category_name)
            header_item.setFont(bold_font)
            header_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # Not selectable
            header_item.setBackground(self.palette().alternateBase())
            self._table.setItem(row, 0, header_item)
            self._table.setSpan(row, 0, 1, 2)
            row += 1

            # Shortcut rows
            for action, shortcut in shortcuts:
                action_item = QTableWidgetItem(f"  {action}")
                action_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                shortcut_item = QTableWidgetItem(shortcut)
                shortcut_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self._table.setItem(row, 0, action_item)
                self._table.setItem(row, 1, shortcut_item)
                row += 1
